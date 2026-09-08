"""
Ingest: evaluate a new fund from its CIK
    python src/ingest.py <cik> --key <product_key> [--model ID] [--only 2.1,2.3]
                         [--skip-fetch] [--dry-run DIR] [--budget-usd N]
                         [--time-budget-s N] [--context-tokens N]

As a library (the worker of R3-P4, the tests):
    os.environ["TARK_DATA_DIR"] = "<workdir>/data"   # before the first import
    from src.ingest import run_product
    result = run_product(cik, workdir, on_progress=callback, model_client=client)

Stages, each a function an offline test drives with a mock client:
  1 registry check   data/registry.json must already carry the product (the
                     cohort, strategy and wrapper are judgments a person makes)
  2 scaffold         data/products/<key>.json and the evidence CSV through
                     promote.scaffold (55 cells, census prefills at structured)
  3 fetch            src/fetch_edgar.fetch_product (the registry's document
                     sets, plus the exhibits it names) unless --skip-fetch
  4 text             every held filing to plain text with page anchors:
                     HTML with inline XBRL headers and hidden blocks removed,
                     PDF through pdftotext, anything else as it is
  5 estimate         the token count of the documents and a cost estimate at
                     the configured price list, before any call, refused when
                     the estimate is over the budget (TARK_BUDGET_USD, 50)
  6 extract          one structured call per extractable cell (CELL_CONTRACT).
                     The filings ride as a cached prefix when they fit the
                     context cap, otherwise each cell receives the pages
                     ranked for it. A context or validation error is retried
                     once at half the context, any other error leaves the
                     cell pending with the error named. Nothing escapes the
                     loop except an interrupt.
  7 verify           the returned quote must appear verbatim (whitespace and
                     quote marks normalized) in the cited document. Verified:
                     status extracted-unverified. Not located: status partial
                     with the reason. Not found: the cell stays pending and the
                     reason goes to the report. Nothing is ever verified here.
  8 write            product JSON and evidence CSV together after every cell,
                     atomically, then the report with the progress so far, so
                     a kill mid-run loses one cell at most
  9 stop             the wall-time budget and the cost budget stop the run
                     cleanly: the remaining cells stay pending with the reason,
                     the report says why, the exit code says so

Env: ANTHROPIC_API_KEY (or an `ant auth login` profile), TARK_INGEST_MODEL
(default claude-opus-5), TARK_DATA_DIR (--dry-run sets it for the run),
TARK_BUDGET_USD (default 50, raised only by Oscar), TARK_TIME_BUDGET_S
(default none), TARK_INGEST_CONTEXT_TOKENS (default 150000), TARK_PRICES_JSON
(a price list override, see PRICES_USD_PER_MTOK).
The model never sees a cell it may not write: engine-owned, advisor-completed
and census-prefilled cells are not in the contract, and an existing
extracted, verified or structured cell is never overwritten.
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:      # `import src.ingest` from the repository root
    sys.path.insert(0, str(_HERE))

from resolve_citations import references  # noqa: E402
from tark_data import (CELLS, DATA, EVIDENCE_COLUMNS, load_evidence, load_product,  # noqa: E402
                       status_kind, validate_product)

DEFAULT_MODEL = "claude-opus-5"
MODEL = os.environ.get("TARK_INGEST_MODEL", DEFAULT_MODEL)
DEFAULT_BUDGET_USD = 50.0            # decision 8.13, raised only by Oscar in the environment
DEFAULT_CONTEXT_TOKENS = 150_000     # the prefix cap under which the whole corpus rides cached
CHARS_PER_TOKEN = 3.5                # the heuristic when the client cannot count tokens
OUTPUT_TOKENS_PER_CALL = 800         # the allowance the estimate reserves per call
MAX_OUTPUT_TOKENS = 4096

# USD per million tokens. Configuration, not a measurement: every dollar
# figure the ingest prints is an estimate at this list. The list is read from
# TARK_PRICES_JSON when set, and the laptop session confirms it against the
# published prices before the proof run (decision 8.34). A model without an
# entry is refused before any call.
PRICES_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-opus-5": {"input": 5.0, "output": 25.0, "cache_write": 6.25, "cache_read": 0.5},
}


def prices_for(model: str) -> dict[str, float] | None:
    table = dict(PRICES_USD_PER_MTOK)
    override = os.environ.get("TARK_PRICES_JSON", "").strip()
    if override:
        table.update(json.loads(override))
    p = table.get(model)
    if not p:
        return None
    return {k: float(p[k]) for k in ("input", "output", "cache_write", "cache_read")}


# cells the model may not write: engine outputs, the adopting fiduciary's own
# cells, and the two the census prefills at status structured
ENGINE_OWNED = ("1.6", "1.7", "1.8", "1.9", "2.9", "3.8", "3.9", "5.2", "5.3", "5.4", "5.5", "5.6", "5.7")
ADVISOR_CELLS = ("2.8", "2.10", "3.5", "3.7", "4.9", "6.6", "6.8")
CENSUS_CELLS = ("4.5", "4.6")
# (element instruction, preferred document sets, retrieval terms). The
# instruction says what the cell holds, never what the answer should be. The
# terms rank pages when the documents do not fit the context cap.
CELL_CONTRACT: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "1.1": ("The fund's net total return series as printed: the table or paragraph giving annual or "
            "cumulative net total returns per share class, with the period ends.", ("annual_report",),
            ("total return", "net asset value per share", "financial highlights", "performance")),
    "1.2": ("Trailing (1, 3, 5 year, since inception) and calendar or fiscal year net returns as "
            "printed, per share class, with the as-of date.", ("annual_report", "prospectus"),
            ("average annual total return", "since inception", "one year", "five year", "as of")),
    "1.3": ("Any gross vs net return figures, or the expense drag between them, as printed.", ("annual_report",),
            ("gross", "net of", "expense", "before fees")),
    "1.4": ("Distribution history and composition: rate, frequency, and the share that is return of "
            "capital vs income, as printed (Section 19 notices count).", ("annual_report", "prospectus"),
            ("distribution", "return of capital", "section 19", "per share")),
    "1.5": ("Performance of underlying sleeves, funds or general partners where the fund reports it.", ("annual_report",),
            ("underlying", "portfolio fund", "general partner", "sleeve")),
    "1.10": ("Market price and premium or discount to NAV, if the shares trade on an exchange. If the "
             "filing states the shares are not listed, that statement.", ("annual_report", "prospectus"),
             ("market price", "premium", "discount", "not listed", "exchange")),
    "1.11": ("Inception date of the fund and of each share class, and the tenure of the portfolio "
             "managers as printed.", ("prospectus", "annual_report"),
             ("inception", "commenced operations", "portfolio manager", "since")),
    "2.1": ("The management fee: the annual rate AND the base it is charged on (net assets, managed "
            "assets, gross assets including borrowings, NAV), exactly as the fee table or advisory "
            "agreement states it.", ("prospectus",),
            ("management fee", "advisory fee", "managed assets", "net assets", "annual rate")),
    "2.2": ("Incentive or performance fee terms: rate, hurdle, catch-up, high-water mark, crystallization "
            "period, or the statement that there is none.", ("prospectus",),
            ("incentive fee", "performance fee", "hurdle", "catch-up", "high water mark")),
    "2.3": ("Total annual expense ratio per share class, gross and net of any waiver, and the waiver "
            "or expense limitation terms including recoupment.", ("prospectus", "annual_report"),
            ("total annual", "expense limitation", "waiver", "recoupment", "annual fund operating expenses")),
    "2.4": ("Acquired fund fees and expenses (AFFE) line of the fee table, or the statement that there is none.", ("prospectus",),
            ("acquired fund fees", "affe")),
    "2.5": ("Economics of underlying general partners or funds borne indirectly: carried interest, "
            "underlying management fees, as disclosed.", ("prospectus", "annual_report"),
            ("carried interest", "underlying fund", "portfolio fund", "indirectly")),
    "2.6": ("Sales loads, distribution and servicing fees per share class, as the fee table states.", ("prospectus",),
            ("sales load", "distribution fee", "servicing fee", "shareholder servicing", "12b-1")),
    "2.7": ("Early repurchase fee or short-term trading fee: rate and holding period, or the statement "
            "that there is none.", ("prospectus",),
            ("early repurchase fee", "repurchase fee", "short-term", "holding period")),
    "3.1": ("Wrapper liquidity terms: repurchase or tender frequency, the cap per offer and its base "
            "(percent of outstanding shares or NAV), and whether offers are mandatory or discretionary.", ("prospectus",),
            ("repurchase offer", "tender offer", "quarterly", "outstanding shares", "discretion", "rule 23c-3")),
    "3.2": ("Repurchase mechanics: notice periods, pricing date, payment timing, pro-rata rules when "
            "oversubscribed.", ("prospectus", "tender_offer"),
            ("repurchase request deadline", "repurchase pricing date", "repurchase payment deadline", "notification", "pro rata")),
    "3.3": ("Repurchase history: amounts requested and accepted per offer, and any proration or "
            "suspension, as reported.", ("annual_report", "tender_offer", "repurchase_history"),
            ("repurchase", "tendered", "accepted", "proration", "pro rata", "suspend")),
    "3.4": ("Portfolio liquidity profile: share of illiquid holdings, liquidity classifications, "
            "credit facilities available for repurchases, as reported.", ("annual_report",),
            ("illiquid", "liquidity", "credit facility", "line of credit", "level 3")),
    "3.6": ("Fund leverage: borrowings outstanding, facility size, asset coverage, and limits, as reported.", ("annual_report", "prospectus"),
            ("borrowings", "credit facility", "asset coverage", "leverage", "outstanding")),
    "4.1": ("Valuation policy and NAV frequency: how often NAV is struck and who determines fair value.", ("prospectus", "annual_report"),
            ("net asset value", "valuation", "fair value", "valuation designee", "calculated")),
    "4.2": ("Fair value hierarchy: the Level 1, 2 and 3 amounts or percentages of the portfolio as of "
            "the period end.", ("annual_report",),
            ("level 1", "level 2", "level 3", "fair value hierarchy")),
    "4.3": ("Independent valuation agent or third-party pricing service, named, and its role.", ("prospectus", "annual_report"),
            ("independent valuation", "third-party", "pricing service", "valuation agent")),
    "4.4": ("Valuation methodology by asset type as described in the notes to the financial statements.", ("annual_report",),
            ("valuation", "fair value", "methodolog", "discounted cash flow", "market approach")),
    "4.7": ("Premium or discount to NAV where a market price exists, or the statement that none exists.", ("annual_report",),
            ("premium", "discount", "market price", "net asset value")),
    "4.8": ("Any smoothing, appraisal-lag or stale-pricing disclosure about the NAV.", ("prospectus", "annual_report"),
            ("stale", "lag", "smooth", "appraisal", "delay")),
    "5.1": ("The benchmark or index the fund itself declares for performance comparison, or the "
            "statement that it declares none (the SEC-required broad index counts, and say so).", ("annual_report", "prospectus"),
            ("benchmark", "index", "compared", "broad-based")),
    "6.1": ("Legal structure and wrapper: registration type, interval or tender-offer status, "
            "exchange listing, as the filing states.", ("prospectus",),
            ("registered under", "investment company act", "closed-end", "interval fund", "listed", "non-diversified")),
    "6.2": ("Investment strategy and principal holdings types as the filing states them.", ("prospectus",),
            ("investment objective", "principal investment strategies", "invests primarily", "principal")),
    "6.3": ("Fiduciary or advice disclaimers directed at retirement plans or plan fiduciaries.", ("prospectus",),
            ("erisa", "plan fiduciary", "retirement plan", "fiduciary")),
    "6.4": ("Tax reporting form delivered to shareholders (Form 1099 or Schedule K-1) and the fund's "
            "tax status (RIC, REIT, partnership).", ("prospectus",),
            ("form 1099", "schedule k-1", "regulated investment company", "subchapter m", "tax")),
    "6.5": ("Eligibility and minimums: who may invest, minimum initial investment per class, "
            "accredited or qualified client requirements.", ("prospectus",),
            ("minimum initial investment", "eligible investor", "accredited investor", "qualified client", "minimum")),
    "6.7": ("Conflicts of interest and affiliated transactions disclosed.", ("prospectus", "annual_report"),
            ("conflicts of interest", "affiliated", "affiliate", "related party")),
}
WRITABLE_KINDS = ("pending", "partial")   # the ingest never overwrites evidence or structured cells


def extractable_cells() -> list[str]:
    out = []
    for cid in CELLS:
        if cid in ENGINE_OWNED or cid in ADVISOR_CELLS or cid in CENSUS_CELLS:
            continue
        if cid in CELL_CONTRACT:
            out.append(cid)
    return out


class Refusal(Exception):
    """A run that does not start: the reason in plain words and the commands
    a person runs by hand instead."""

    def __init__(self, reason: str, commands: list[str] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.commands = commands or []


# ------------------------------------------------------------- filing text
VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "col", "area", "base", "embed", "param",
             "source", "track", "wbr"}
HIDDEN_TAGS = {"script", "style", "ix:header", "ix:hidden"}
HIDDEN_STYLE_RE = re.compile(r"display\s*:\s*none", re.I)


class _Text(HTMLParser):
    """HTML to text with block breaks. Script and style blocks, inline XBRL
    headers (contexts, units, hidden facts) and anything styled display:none
    never reach the text, so a quote cannot come from what a reader cannot see."""
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "td", "th", "hr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._open: list[tuple[str, bool]] = []
        self._skip = 0

    def _break(self, tag: str) -> None:
        if tag in self.BLOCK:
            self.parts.append(" " if tag in ("td", "th") else "\n")

    def handle_starttag(self, tag, attrs):
        hidden = tag in HIDDEN_TAGS or any(
            k == "style" and v and HIDDEN_STYLE_RE.search(v) for k, v in attrs)
        if tag in VOID_TAGS:
            self._break(tag)
            return
        self._open.append((tag, hidden))
        if hidden:
            self._skip += 1
        self._break(tag)

    def handle_startendtag(self, tag, attrs):
        self._break(tag)

    def handle_endtag(self, tag):
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i][0] == tag:
                self._skip -= sum(1 for _, h in self._open[i:] if h)
                del self._open[i:]
                break
        self._break(tag)

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


PAGE_BREAK = re.compile(r"<[^>]*page-break-(?:before|after)\s*:\s*always[^>]*>", re.I)
CHARSET_RE = re.compile(rb"charset=[\"']?([A-Za-z0-9_-]+)", re.I)


def html_to_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    text = "".join(p.parts)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def read_html(path: Path) -> str:
    """The file decoded by its declared charset, UTF-8 otherwise, so a quote
    never carries a decoding artifact the filing does not."""
    raw = path.read_bytes()
    m = CHARSET_RE.search(raw[:4096])
    enc = m.group(1).decode("ascii", "replace") if m else "utf-8"
    try:
        return raw.decode(enc, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


class ReaderMissing(RuntimeError):
    """A document type this machine cannot read, named."""


def split_form_feeds(text: str) -> list[str]:
    """pdftotext emits one form feed per page."""
    pages = [pg.strip() for pg in text.split("\f")]
    return [pg for pg in pages if pg]


def pdf_pages(path: Path) -> list[str]:
    tool = shutil.which("pdftotext")
    if tool is None:
        raise ReaderMissing(f"pdftotext is not installed here, so {path.name} was not read (install poppler-utils)")
    r = subprocess.run([tool, "-layout", "-enc", "UTF-8", str(path), "-"], capture_output=True, text=True)
    if r.returncode:
        raise ReaderMissing(f"pdftotext could not read {path.name}: {(r.stderr or '').strip()[:200]}")
    return split_form_feeds(r.stdout)


@dataclass
class FilingText:
    label: str            # "N-CSR filed 2026-06-09 (accession 0001234567-26-000001)"
    path: str
    pages: list[str]
    accession: str = ""   # from the manifest row, the ledger's accession column
    local_path: str = ""  # the row's path under the record ('data/raw/...')
    doc_set: str = ""
    form: str = ""
    kind: str = "html"    # html, pdf, xml or text

    @property
    def text(self) -> str:
        return "\n".join(f"[page {i}]\n{pg}" for i, pg in enumerate(self.pages, 1))

    def page_of(self, needle: str) -> int | None:
        n = normalize(needle)
        for i, pg in enumerate(self.pages, 1):
            if n and n in normalize(pg):
                return i
        return None

    def render(self, pages: list[int] | None = None) -> str:
        """The document block a call carries: every page, or the pages named
        with their true anchors so a cited page resolves either way."""
        if pages is None:
            body = self.text
            head = f"=== DOCUMENT: {self.label} ==="
        else:
            body = "\n".join(f"[page {i}]\n{self.pages[i - 1]}" for i in pages)
            head = f"=== DOCUMENT: {self.label} (pages {', '.join(str(i) for i in pages)} of {len(self.pages)}) ==="
        return f"{head}\n{body}"


def filing_text(path: Path, label: str, **fields) -> FilingText:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        pages, kind = pdf_pages(path), "pdf"
    else:
        raw = read_html(path)
        if "<" in raw and ">" in raw:
            chunks = PAGE_BREAK.split(raw)
            pages = [t for t in (html_to_text(c) for c in chunks) if t]
            kind = "xml" if suffix == ".xml" else "html"
        else:
            pages, kind = [raw.strip()], "text"
    return FilingText(label=label, path=str(path), pages=pages or [""], kind=kind, **fields)


def held_filings(key: str, manifest_path: Path | None = None) -> list[dict]:
    mp = manifest_path or (DATA / "manifest.csv")
    if not mp.exists():
        return []
    with open(mp, newline="") as fh:
        return [r for r in csv.DictReader(fh) if r["product"] == key]


def doc_label(row: dict, rows: list[dict] | None = None) -> str:
    """The document label the model cites and the ledger resolves. When an
    accession holds more than one document (an exhibit beside the primary
    document) the label names the document too."""
    label = f"{row['form']} filed {row['filing_date']} (accession {row['accession']}"
    siblings = [r for r in (rows or []) if r.get("accession") == row.get("accession")]
    if len(siblings) > 1 and row.get("primary_document"):
        label += f", document {row['primary_document']}"
    return label + ")"


def filing_from_row(row: dict, rows: list[dict] | None = None) -> FilingText | None:
    """A manifest row to its text, None when the row names no document on
    disk (a structured-dataset row) or the file is absent here."""
    lp = row.get("local_path") or ""
    if not lp:
        return None
    p = Path(lp) if Path(lp).is_absolute() else DATA.parent / lp
    if not p.is_file():
        return None
    return filing_text(p, doc_label(row, rows), accession=row.get("accession", ""),
                       local_path=_record_relative(str(p)), doc_set=row.get("doc_set", ""),
                       form=row.get("form", ""))


def documents_for(key: str) -> tuple[list[FilingText], list[dict]]:
    """Every held filing as text, and the rows that could not be read with
    the reason (never a silent drop)."""
    rows = held_filings(key)
    docs, skipped = [], []
    for r in rows:
        if not r.get("local_path"):
            continue    # a structured-dataset row names an accession, not a document on disk
        try:
            d = filing_from_row(r, rows)
        except ReaderMissing as e:
            skipped.append({"document": doc_label(r, rows), "reason": str(e)})
            continue
        if d is None:
            skipped.append({"document": doc_label(r, rows), "reason": "not on disk here"})
        else:
            docs.append(d)
    return docs, skipped


# ---------------------------------------------------------------- normalize
_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"',
                         "—": "-", "–": "-", "\xa0": " "})


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").translate(_QUOTES)).strip().lower()


# ----------------------------------------------------------------- extraction
try:
    from pydantic import BaseModel
except ImportError:      # the offline test path does not need pydantic
    BaseModel = object   # type: ignore[misc,assignment]


class CellExtraction(BaseModel):  # type: ignore[misc]
    """What one structured call returns for one cell."""
    found: bool
    value: str            # one to three sentences stating the fact with the figures exactly as printed
    quote: str            # the supporting passage copied character for character from the document
    source_doc: str       # one of the document labels given, verbatim
    section: str          # the section heading, table title or page anchor the quote sits in
    not_found_reason: str


SYSTEM = (
    "You extract one evidence cell at a time from SEC filings for a fiduciary record. Rules: "
    "the value states only what the documents say, with every figure exactly as printed and "
    "the period or share class it applies to. The quote is copied character for character "
    "from one of the documents, long enough to support the whole value, never stitched from "
    "two places. source_doc is one of the document labels given, verbatim. If the documents do "
    "not answer the cell, set found to false and say in not_found_reason what you looked for "
    "and where. Never infer a figure, never compute one, never fill a gap from general "
    "knowledge. Do not use semicolons or em dashes in the value."
)


def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 1


# a selection: {document index: [page numbers]} or None for the whole corpus
Selection = dict[int, list[int]] | None


def corpus_tokens(docs: list[FilingText]) -> int:
    return sum(estimate_tokens(d.render()) for d in docs)


def select_pages(cid: str, docs: list[FilingText], cap_tokens: int, preferred_only: bool = False) -> Selection:
    """The pages a cell receives when the corpus does not fit the cap: ranked
    by the cell's preferred document sets and its retrieval terms, neighbours
    kept, read in document order. None when everything fits (one identical
    prefix for every cell, which the cache pays for once)."""
    if not preferred_only and corpus_tokens(docs) <= cap_tokens:
        return None
    _, prefer, terms = CELL_CONTRACT[cid]
    has_preferred = any(d.doc_set in prefer for d in docs)
    ranked = []
    for di, d in enumerate(docs):
        if preferred_only and has_preferred and d.doc_set not in prefer:
            continue
        pref = 3 if d.doc_set in prefer else (1 if not d.doc_set else 0)
        for pi, pg in enumerate(d.pages, 1):
            low = normalize(pg)
            hits = sum(1 for t in terms if t in low)
            ranked.append((-(pref + min(hits, 5)), di, pi, estimate_tokens(pg) + 4))
    ranked.sort()
    chosen: dict[int, set[int]] = {}
    used = 0
    for _, di, pi, tok in ranked:
        if used + tok > cap_tokens:
            continue
        chosen.setdefault(di, set()).add(pi)
        used += tok
    # neighbours, while the budget allows: a table often runs over a break
    for di, pages in list(chosen.items()):
        for pi in sorted(pages):
            for nb in (pi - 1, pi + 1):
                if 1 <= nb <= len(docs[di].pages) and nb not in chosen[di]:
                    tok = estimate_tokens(docs[di].pages[nb - 1]) + 4
                    if used + tok <= cap_tokens:
                        chosen[di].add(nb)
                        used += tok
    return {di: sorted(p) for di, p in sorted(chosen.items())}


def build_messages(cid: str, docs: list[FilingText], selection: Selection = None) -> tuple[str, list[dict]]:
    instruction, prefer = CELL_CONTRACT[cid][:2]
    if selection is None:
        doc_blocks = "\n\n".join(d.render() for d in docs)
    else:
        doc_blocks = "\n\n".join(docs[di].render(pages) for di, pages in selection.items())
    user = [
        {"type": "text", "text": "Documents on record for this fund:\n\n" + doc_blocks,
         "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": (f"Cell {cid}, {CELLS[cid]}. What it holds: {instruction} "
                                  f"Prefer these document sets when several answer: {', '.join(prefer)}. "
                                  "Return the structured result.")},
    ]
    return SYSTEM, [{"role": "user", "content": user}]


def usage_of(response) -> dict[str, int]:
    """The token usage a response reports, zero for a client that reports none."""
    u = getattr(response, "usage", None)
    out = {}
    for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"):
        v = getattr(u, k, None) if not isinstance(u, dict) else u.get(k)
        out[k] = int(v or 0)
    return out


def usd_of(usage: dict[str, int], prices: dict[str, float] | None) -> float:
    if not prices:
        return 0.0
    return (usage.get("input_tokens", 0) * prices["input"]
            + usage.get("cache_creation_input_tokens", 0) * prices["cache_write"]
            + usage.get("cache_read_input_tokens", 0) * prices["cache_read"]
            + usage.get("output_tokens", 0) * prices["output"]) / 1_000_000


def extract_cell(client, cid: str, docs: list[FilingText], model: str = MODEL,
                 selection: Selection = None) -> tuple[CellExtraction, dict[str, int]]:
    system, messages = build_messages(cid, docs, selection)
    response = client.messages.parse(model=model, max_tokens=MAX_OUTPUT_TOKENS, system=system,
                                     messages=messages, output_format=CellExtraction)
    usage = usage_of(response)
    if getattr(response, "stop_reason", None) == "refusal":
        return CellExtraction(found=False, value="", quote="", source_doc="", section="",
                              not_found_reason="the model declined the request (stop_reason refusal)"), usage
    return response.parsed_output, usage


# errors worth one retry at half the context: the request was too large or
# the structured answer did not parse. Matched by class name so the offline
# path needs no SDK import.
CONTEXT_ERROR_NAMES = ("BadRequestError", "RequestTooLargeError", "APIResponseValidationError", "ValidationError")


def is_context_error(e: BaseException) -> bool:
    return any(c.__name__ in CONTEXT_ERROR_NAMES for c in type(e).__mro__)


@dataclass
class Outcome:
    cid: str
    status: str                      # extracted-unverified | partial - ... | pending extraction
    record: dict | None              # the cell record to write, None when the cell is left alone
    reason: str = ""
    local_file: str = ""             # the cited filing's path under the record, when the filing was held
    accession: str = ""              # its accession number, from the manifest row
    tokens: dict = field(default_factory=dict)
    usd: float = 0.0
    seconds: float = 0.0
    attempts: int = 0
    pages_sent: dict = field(default_factory=dict)   # {document label: [pages]} or {} for the whole corpus

    def as_report_row(self) -> dict:
        return {"cell": self.cid, "status": self.status, "reason": self.reason, "attempts": self.attempts,
                "pages_sent": self.pages_sent or "all", "tokens": self.tokens, "usd": round(self.usd, 6),
                "seconds": round(self.seconds, 3)}


def _record_relative(path: str) -> str:
    """A held filing's path as the evidence ledger writes it: under the
    record ('data/raw/...'), never a machine path."""
    try:
        return str(Path(path).resolve().relative_to(DATA.parent.resolve()))
    except ValueError:
        return path


def verify(cid: str, ex: CellExtraction, docs: list[FilingText], model: str, today: str) -> Outcome:
    """The per-cell contract: found needs a verbatim quote in the cited document."""
    if not ex.found or not (ex.value or "").strip():
        return Outcome(cid, "pending extraction", None, ex.not_found_reason or "not found")
    doc = next((d for d in docs if d.label == ex.source_doc), None)
    if doc is None:
        doc = next((d for d in docs if normalize(ex.source_doc) and normalize(ex.source_doc) in normalize(d.label)), None)
    page = doc.page_of(ex.quote) if (doc and ex.quote) else None
    located = page is not None
    section = (ex.section or "").strip()
    if located:
        section = f"{section}, page {page}" if section else f"page {page}"
        status = "extracted-unverified"
        extracted_by = f"Tark ingest ({model}, {today}), quote located verbatim on page {page}"
    else:
        why = ("cited document not among the held filings" if doc is None
               else "quote not located verbatim in the cited document")
        status = f"partial - {why}, value kept for a human check"
        extracted_by = f"Tark ingest ({model}, {today}), {why}"
    src = doc.label if doc else (ex.source_doc or "document not identified")
    record = {"element": CELLS[cid], "value": ex.value.strip(), "status": status,
              "source": src + (f", {section}" if section else ""), "section": section,
              "quote": (ex.quote or "").strip(), "extracted_by": extracted_by, "verified_by": ""}
    # the ledger columns the verification tool resolves the document by
    # (audit item 41): the held filing's path and its accession, carried from
    # the manifest row the document came from, with the label parse as the
    # fallback for a document built without a row
    acc = doc.accession if doc else ""
    if doc and not acc:
        refs = references(doc.label)
        acc = refs[0]["accessions"][0] if refs and refs[0].get("accessions") else ""
    local_file = (doc.local_path or _record_relative(doc.path)) if doc else ""
    return Outcome(cid, status, record, "" if located else why, local_file=local_file, accession=acc)


# --------------------------------------------------------------------- write
def _atomic_write(path: Path, text: str) -> None:
    """Write to a sibling and rename, so a kill mid-write leaves the old file whole."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_cells(key: str, outcomes: list[Outcome], today: str) -> list[str]:
    product = load_product(key)
    rows = load_evidence(key)
    written = []
    for o in outcomes:
        if o.record is None:
            continue
        kind = status_kind(str(product["cells"][o.cid].get("status", "pending")))
        if kind not in WRITABLE_KINDS:
            raise SystemExit(f"refusing to overwrite {key} {o.cid}: status kind {kind!r} is evidence")
        assert o.record["verified_by"] == "" and not o.record["status"].startswith("verified")
        product["cells"][o.cid] = o.record
        for r in rows:
            if r["cell_id"] == o.cid:
                r.update({"element": o.record["element"], "value": o.record["value"],
                          "source_doc": o.record["source"], "source_section": o.record["section"],
                          "quote": o.record["quote"], "local_file": o.local_file, "accession": o.accession,
                          "date_pulled": today,
                          "extracted_by": o.record["extracted_by"], "verified_by": "",
                          "status": o.record["status"]})
        written.append(o.cid)
    if not written:
        return written
    _atomic_write(DATA / "products" / f"{key}.json", json.dumps(product, indent=2, ensure_ascii=False) + "\n")
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=EVIDENCE_COLUMNS, lineterminator="\r\n")
    w.writeheader()
    w.writerows(rows)
    _atomic_write(DATA / "evidence" / f"{key}_evidence.csv", buf.getvalue())
    return written


# ---------------------------------------------------------------- the run
@dataclass
class RunCost:
    model: str
    calls: int = 0
    input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0
    wall_seconds: float = 0.0

    def add(self, usage: dict[str, int], usd: float) -> None:
        self.calls += 1
        for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"):
            setattr(self, k, getattr(self, k) + int(usage.get(k, 0)))
        self.usd += usd

    def as_dict(self) -> dict:
        return {"model": self.model, "calls": self.calls, "input_tokens": self.input_tokens,
                "cache_creation_input_tokens": self.cache_creation_input_tokens,
                "cache_read_input_tokens": self.cache_read_input_tokens, "output_tokens": self.output_tokens,
                "usd": round(self.usd, 6), "usd_per_call": round(self.usd / self.calls, 6) if self.calls else 0.0,
                "wall_seconds": round(self.wall_seconds, 1)}

    def line(self, budget_usd: float, spent_before_usd: float = 0.0) -> str:
        return (f"cost: {self.calls} calls, {self.input_tokens:,} in / {self.cache_creation_input_tokens:,} cache write / "
                f"{self.cache_read_input_tokens:,} cache read / {self.output_tokens:,} out tokens, "
                f"${self.usd:.2f} of ${budget_usd:.2f} budget (estimate at the configured price list"
                + (f", ${spent_before_usd:.2f} spent before this run" if spent_before_usd else "")
                + f"), {self.wall_seconds:.0f} s")


class Outcomes(list):
    """The outcomes of one run, with the run's cost, estimate and stop."""
    cost: RunCost
    estimate: dict
    stopped: dict | None
    report_path: Path
    callback_errors: list
    written: list


def count_prefix_tokens(client, model: str, docs: list[FilingText], cid: str, selection: Selection) -> tuple[int, str]:
    """The prefix's token count from the client when it can count, the
    character heuristic otherwise, and which one it was."""
    system, messages = build_messages(cid, docs, selection)
    counter = getattr(getattr(client, "messages", None), "count_tokens", None)
    if counter is not None:
        try:
            r = counter(model=model, system=system, messages=messages)
            n = int(getattr(r, "input_tokens", None) or (r.get("input_tokens") if isinstance(r, dict) else 0))
            if n > 0:
                return n, "count_tokens"
        except Exception as e:  # noqa: BLE001  (a counting failure never stops the run, the heuristic does)
            return estimate_tokens(messages[0]["content"][0]["text"]), f"heuristic after {type(e).__name__}"
    return estimate_tokens(messages[0]["content"][0]["text"]), "heuristic"


def estimate_cost(client, model: str, docs: list[FilingText], cells: list[str], prices: dict[str, float],
                  cap_tokens: int) -> dict:
    """The cost estimate before the first call, at the configured price list.
    Whole corpus: one cache write then cache reads. Per-cell pages: every
    call pays its own prefix at the input price."""
    n = len(cells)
    tail = estimate_tokens(CELLS[cells[0]] + CELL_CONTRACT[cells[0]][0]) + 40 if cells else 0
    if n == 0:
        return {"usd": 0.0, "calls": 0, "method": "none", "whole_corpus": True, "prefix_tokens": 0,
                "note": "no cell to call"}
    whole = corpus_tokens(docs) <= cap_tokens
    if whole:
        prefix, method = count_prefix_tokens(client, model, docs, cells[0], None)
        usd = (prefix * prices["cache_write"] + (n - 1) * prefix * prices["cache_read"]
               + n * tail * prices["input"] + n * OUTPUT_TOKENS_PER_CALL * prices["output"]) / 1_000_000
        prefix_total = prefix
    else:
        prefix_total, method = 0, "heuristic"
        for cid in cells:
            sel = select_pages(cid, docs, cap_tokens)
            p, method = count_prefix_tokens(client, model, docs, cid, sel)
            prefix_total += p
        usd = (prefix_total * prices["input"] + n * tail * prices["input"]
               + n * OUTPUT_TOKENS_PER_CALL * prices["output"]) / 1_000_000
    return {"usd": round(usd, 4), "calls": n, "method": method, "whole_corpus": whole,
            "prefix_tokens": prefix_total, "output_tokens_per_call": OUTPUT_TOKENS_PER_CALL,
            "cap_tokens": cap_tokens, "prices_usd_per_mtok": prices,
            "note": "an estimate at the configured price list, not a measurement"}


def _emit(on_progress, errors: list, event: dict) -> None:
    if on_progress is None:
        return
    try:
        on_progress(event)
    except Exception as e:  # noqa: BLE001  (a reporting failure never aborts an extraction)
        errors.append(f"{event.get('event')}: {type(e).__name__}: {str(e)[:120]}")


def run_extraction(client, key: str, docs: list[FilingText], only: set[str] | None = None,
                   model: str = MODEL, today: str | None = None, *,
                   on_progress: Callable[[dict], None] | None = None,
                   budget_usd: float | None = None, spent_before_usd: float = 0.0,
                   time_budget_s: float | None = None, clock: Callable[[], float] = time.monotonic,
                   context_tokens: int | None = None) -> Outcomes:
    """Extract, verify and write every writable cell in the contract, one
    cell at a time with a write after each. Returns the outcomes, including
    the cells left pending with their reasons, with the run's cost attached."""
    today = today or date.today().isoformat()
    budget = float(os.environ.get("TARK_BUDGET_USD", DEFAULT_BUDGET_USD)) if budget_usd is None else float(budget_usd)
    if time_budget_s is None and os.environ.get("TARK_TIME_BUDGET_S", "").strip():
        time_budget_s = float(os.environ["TARK_TIME_BUDGET_S"])
    cap = int(context_tokens or os.environ.get("TARK_INGEST_CONTEXT_TOKENS") or DEFAULT_CONTEXT_TOKENS)
    prices = prices_for(model)
    if prices is None:
        raise Refusal(f"no price list for model {model}: set TARK_PRICES_JSON with input, output, cache_write "
                      "and cache_read in USD per million tokens, or use a model the list names")
    t0 = clock()
    product = load_product(key)
    targets = [c for c in extractable_cells() if not only or c in only]
    to_call = [c for c in targets
               if status_kind(str(product["cells"][c].get("status", "pending"))) in WRITABLE_KINDS]
    outcomes = Outcomes()
    outcomes.cost = RunCost(model)
    outcomes.stopped = None
    outcomes.callback_errors = []
    outcomes.written = []
    outcomes.estimate = estimate_cost(client, model, docs, to_call, prices, cap)
    report_path = DATA / "ingest" / f"{key}_report.json"
    outcomes.report_path = report_path
    whole = outcomes.estimate["whole_corpus"]

    def write_report(final: bool) -> None:
        cost = outcomes.cost
        cost.wall_seconds = clock() - t0
        report = {"product": key, "model": model, "date": today,
                  "documents": [{"label": d.label, "kind": d.kind, "pages": len(d.pages),
                                 "tokens_estimate": estimate_tokens(d.render()), "accession": d.accession,
                                 "doc_set": d.doc_set} for d in docs],
                  "context": {"cap_tokens": cap, "corpus_tokens_estimate": corpus_tokens(docs),
                              "whole_corpus": whole, "note": "token figures are estimates unless counted"},
                  "estimate": outcomes.estimate, "budget_usd": budget, "spent_before_usd": spent_before_usd,
                  "time_budget_s": time_budget_s, "cost": cost.as_dict(),
                  "progress": {"done": len(outcomes), "total": len(targets), "final": final},
                  "stopped": outcomes.stopped, "callback_errors": outcomes.callback_errors,
                  "outcomes": [o.as_report_row() for o in outcomes]}
        _atomic_write(report_path, json.dumps(report, indent=2))

    _emit(on_progress, outcomes.callback_errors,
          {"event": "run_start", "product": key, "model": model, "cells": len(targets), "calls_planned": len(to_call),
           "documents": len(docs), "estimate": outcomes.estimate, "budget_usd": budget,
           "spent_before_usd": spent_before_usd, "time_budget_s": time_budget_s})
    if spent_before_usd + outcomes.estimate["usd"] > budget:
        outcomes.stopped = {"reason": "estimate over budget", "after_cells": 0,
                            "detail": (f"the cost estimate ${outcomes.estimate['usd']:.2f} plus ${spent_before_usd:.2f} "
                                       f"already spent exceeds the budget ${budget:.2f}, no call was made")}
    for i, cid in enumerate(targets):
        kind = status_kind(str(product["cells"][cid].get("status", "pending")))
        _emit(on_progress, outcomes.callback_errors,
              {"event": "cell_start", "cell": cid, "index": i + 1, "total": len(targets),
               "elapsed_s": round(clock() - t0, 1), "usd_so_far": round(outcomes.cost.usd, 4)})
        if kind not in WRITABLE_KINDS:
            o = Outcome(cid, product["cells"][cid]["status"], None, f"kept: {kind} cell")
        elif outcomes.stopped is not None:
            o = Outcome(cid, "pending extraction", None, f"stopped: {outcomes.stopped['detail']}")
        elif time_budget_s is not None and clock() - t0 >= time_budget_s:
            outcomes.stopped = {"reason": "time", "after_cells": outcomes.cost.calls,
                                "detail": (f"the wall-time budget of {time_budget_s:.0f} s ran out after "
                                           f"{outcomes.cost.calls} calls, this cell was not sent")}
            o = Outcome(cid, "pending extraction", None, f"stopped: {outcomes.stopped['detail']}")
        else:
            o = _extract_one(client, cid, docs, model, today, cap, whole, prices, clock)
            outcomes.cost.add(o.tokens, o.usd)
            written = write_cells(key, [o], today)
            outcomes.written.extend(written)
            if spent_before_usd + outcomes.cost.usd >= budget:
                outcomes.stopped = {"reason": "budget", "after_cells": outcomes.cost.calls,
                                    "detail": (f"the running cost estimate reached the budget of ${budget:.2f} "
                                               f"after {outcomes.cost.calls} calls, the remaining cells were not sent")}
        outcomes.append(o)
        _emit(on_progress, outcomes.callback_errors,
              {"event": "cell_done", "cell": cid, "index": i + 1, "total": len(targets), "status": o.status,
               "reason": o.reason, "tokens": o.tokens, "usd": round(o.usd, 6), "seconds": round(o.seconds, 3),
               "attempts": o.attempts, "usd_so_far": round(outcomes.cost.usd, 4),
               "elapsed_s": round(clock() - t0, 1)})
        write_report(final=False)
    outcomes.cost.wall_seconds = clock() - t0
    _emit(on_progress, outcomes.callback_errors,
          {"event": "run_end", "product": key, "cost": outcomes.cost.as_dict(), "stopped": outcomes.stopped,
           "written": list(outcomes.written), "report": str(report_path)})
    write_report(final=True)   # after the last event, so a failing callback is in the record too
    return outcomes


def _extract_one(client, cid, docs, model, today, cap, whole, prices, clock) -> Outcome:
    """One cell: the full context first, one retry at half the context on a
    context or validation error, any other error recorded and the loop kept."""
    t = clock()
    attempts = 0
    selection: Selection = None if whole else select_pages(cid, docs, cap)
    last_err = None
    for attempt in (1, 2):
        attempts = attempt
        try:
            ex, usage = extract_cell(client, cid, docs, model, selection)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:  # noqa: BLE001  (every error of one cell is recorded, none escapes the loop)
            last_err = e
            if attempt == 1 and is_context_error(e):
                selection = select_pages(cid, docs, max(cap // 2, 1000), preferred_only=True)
                continue
            o = Outcome(cid, "pending extraction", None,
                        f"extraction error: {type(e).__name__}: {str(e)[:200]}")
            break
        o = verify(cid, ex, docs, model, today)
        o.tokens = usage
        o.usd = usd_of(usage, prices)
        break
    else:  # pragma: no cover
        o = Outcome(cid, "pending extraction", None, f"extraction error: {type(last_err).__name__}")
    o.attempts = attempts
    o.seconds = clock() - t
    if selection is not None:
        o.pages_sent = {docs[di].label: pages for di, pages in selection.items()}
    return o


# --------------------------------------------------------------- run_product
@dataclass
class RunResult:
    product: str
    cik: str
    outcomes: list[Outcome]
    cost: RunCost
    estimate: dict
    stopped: dict | None
    report_path: Path
    validate_errors: list[str]
    documents: list[str]
    skipped_documents: list[dict]
    written: list[str]
    ok: bool

    def summary(self) -> str:
        n_ex = sum(1 for o in self.outcomes if o.status.startswith("extracted"))
        n_pa = sum(1 for o in self.outcomes if o.status.startswith("partial"))
        n_pe = sum(1 for o in self.outcomes if o.status.startswith("pending"))
        s = (f"{self.product}: {len(self.documents)} documents, {n_ex} extracted, {n_pa} partial, "
             f"{n_pe} pending, {len(self.written)} cells written")
        if self.stopped:
            s += f", stopped ({self.stopped['reason']})"
        if self.validate_errors:
            s += f", {len(self.validate_errors)} validation errors"
        return s


def registry_entry(key: str) -> dict | None:
    rp = DATA / "registry.json"
    if not rp.exists():
        return None
    return json.loads(rp.read_text())["products"].get(key)


def resolve_key(cik: str) -> str | None:
    """The product key for a CIK: the census promotion when there is one,
    else the product file that carries the CIK. None when neither exists,
    since the key is a person's choice at promotion."""
    cp = DATA / "census" / "census.json"
    if cp.exists():
        rec = json.loads(cp.read_text())["entities"].get(cik) or {}
        pk = (rec.get("promotion") or {}).get("product_key")
        if pk:
            return pk
    for p in sorted((DATA / "products").glob("*.json")):
        try:
            d = json.loads(p.read_text())
        except ValueError:
            continue
        if str(d.get("cik", "")).lstrip("0") == cik.lstrip("0"):
            return d.get("product_key") or p.stem
    return None


def hand_commands(cik: str, key: str) -> list[str]:
    return [f"python src/promote.py {cik} --key {key}",
            f"# write the data/registry.json entry for {key} and add it to its cohort's members list",
            f"python src/fetch_edgar.py {key}",
            f"python src/ingest.py {cik} --key {key} --skip-fetch",
            "python src/produce.py && python src/build_site.py && bash hooks/pre-commit"]


def run_product(cik: str, workdir: str | Path, on_progress: Callable[[dict], None] | None = None,
                model_client=None, *, key: str | None = None, model: str | None = None,
                only: set[str] | None = None, skip_fetch: bool = False, budget_usd: float | None = None,
                spent_before_usd: float = 0.0, time_budget_s: float | None = None, today: str | None = None,
                context_tokens: int | None = None, wrapper: str = "",
                clock: Callable[[], float] = time.monotonic) -> RunResult:
    """The one call the worker makes. workdir is the directory that holds
    data/, and TARK_DATA_DIR must already point at that data/ when the
    pipeline was first imported (every module binds its data root at import).
    Raises Refusal when the run cannot start, returns a RunResult otherwise,
    with ok False when the run stopped or the product does not validate."""
    workdir = Path(workdir).resolve()
    if DATA != (workdir / "data").resolve():
        raise Refusal(f"the data root bound at import is {DATA}, not {workdir / 'data'}: set TARK_DATA_DIR to "
                      "<workdir>/data before the first import of the pipeline")
    cik = str(int(str(cik).strip()))
    model = model or MODEL
    key = key or resolve_key(cik)
    if key is None:
        raise Refusal(f"no product key for CIK {cik}: the key is chosen at promotion (python src/promote.py "
                      f"{cik} --key <key>) and the registry entry is a person's judgment",
                      hand_commands(cik, "<key>"))
    if not re.fullmatch(r"[a-z0-9_]{2,32}", key):
        raise Refusal(f"product key {key!r} must match [a-z0-9_]{{2,32}}", hand_commands(cik, key))
    if registry_entry(key) is None:
        raise Refusal(f"data/registry.json has no entry for {key}. Add it first (cohort, strategy, asset_class, "
                      "sub_strategy, wrapper_type, pricing_class, nav_cadence, leverage_regime, held_returns, "
                      "advisers, adviser_keys, declared_benchmarks, source_cells, as_of, depth, "
                      "membership_rationale, filings, each with its source). Those are judgments a person makes.",
                      hand_commands(cik, key))
    if not (DATA / "products" / f"{key}.json").exists():
        import promote
        try:
            promote.scaffold(cik, key, wrapper=wrapper)
        except promote.ScaffoldRefused as e:
            raise Refusal(str(e), hand_commands(cik, key)) from e
    prod = load_product(key)
    if str(prod.get("cik", "")).lstrip("0") != cik.lstrip("0"):
        raise Refusal(f"data/products/{key}.json carries CIK {prod.get('cik')}, not {cik}", hand_commands(cik, key))
    if not skip_fetch:
        import fetch_edgar
        fetch_edgar.fetch_product(key)
    docs, skipped = documents_for(key)
    if not held_filings(key):
        raise Refusal("no filings held for this product in data/manifest.csv (run without --skip-fetch)",
                      hand_commands(cik, key))
    if not docs:
        raise Refusal("manifest rows exist but no filing text could be read here: "
                      + "; ".join(f"{s['document']}: {s['reason']}" for s in skipped),  # copy-exempt: a list joiner in a console refusal, not a surface
                      hand_commands(cik, key))
    client = model_client
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    outcomes = run_extraction(client, key, docs, only, model, today, on_progress=on_progress,
                              budget_usd=budget_usd, spent_before_usd=spent_before_usd,
                              time_budget_s=time_budget_s, clock=clock, context_tokens=context_tokens)
    errs = validate_product(key)
    return RunResult(product=key, cik=cik, outcomes=list(outcomes), cost=outcomes.cost, estimate=outcomes.estimate,
                     stopped=outcomes.stopped, report_path=outcomes.report_path, validate_errors=errs,
                     documents=[d.label for d in docs], skipped_documents=skipped, written=list(outcomes.written),
                     ok=not errs and outcomes.stopped is None)


def dry_run_copy(src_data: Path, dst_data: Path, key: str | None = None, cik: str | None = None) -> Path:
    """A copy of the data root for a run that must not touch the record: every
    tracked file, the census, this product's raw filings and this CIK's cached
    submissions, and no other product's raw filings."""
    src_data, dst_data = Path(src_data), Path(dst_data)
    shutil.copytree(src_data, dst_data, ignore=shutil.ignore_patterns("raw", "memos", "__pycache__"))
    if key and (src_data / "raw" / key).is_dir():
        shutil.copytree(src_data / "raw" / key, dst_data / "raw" / key)
    if cik:
        sub = src_data / "census" / "raw" / "submissions" / f"CIK{int(cik):010d}.json"
        if sub.is_file():
            (dst_data / "census" / "raw" / "submissions").mkdir(parents=True, exist_ok=True)
            shutil.copy(sub, dst_data / "census" / "raw" / "submissions" / sub.name)
    return dst_data


# ---------------------------------------------------------------------- main
def print_progress(ev: dict) -> None:
    e = ev.get("event")
    if e == "run_start":
        est = ev["estimate"]
        print(f"{ev['documents']} documents, {ev['cells']} cells ({ev['calls_planned']} to call), estimate "
              f"${est['usd']:.2f} ({est['method']}, {'whole corpus cached' if est['whole_corpus'] else 'pages per cell'}) "
              f"of ${ev['budget_usd']:.2f} budget")
    elif e == "cell_done":
        print(f"  {ev['cell']:5s} {ev['status'][:60]:60s} ${ev['usd']:.4f} {ev['seconds']:.1f}s "
              f"{ev['reason'][:50]}")
    elif e == "run_end" and ev.get("stopped"):
        print(f"stopped: {ev['stopped']['detail']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cik")
    ap.add_argument("--key", default="")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--only", default="", help="comma-separated cell ids")
    ap.add_argument("--skip-fetch", action="store_true")
    ap.add_argument("--dry-run", default="", metavar="DIR",
                    help="run against DIR/data, a copy of the record with this product's raw filings, the repository is not touched")
    ap.add_argument("--workdir", default="", help=argparse.SUPPRESS)
    ap.add_argument("--budget-usd", default=None, type=float)
    ap.add_argument("--time-budget-s", default=None, type=float)
    ap.add_argument("--context-tokens", default=None, type=int)
    a = ap.parse_args()
    if a.dry_run:
        dst = Path(a.dry_run).resolve()
        if not (dst / "data").exists():
            dry_run_copy(DATA, dst / "data", a.key or None, a.cik)
        os.environ["TARK_DATA_DIR"] = str(dst / "data")
        print(f"dry run against {dst / 'data'}")
        argv = [sys.executable, __file__, a.cik, "--key", a.key, "--model", a.model, "--only", a.only,
                "--workdir", str(dst)] + (["--skip-fetch"] if a.skip_fetch else [])
        for flag, val in (("--budget-usd", a.budget_usd), ("--time-budget-s", a.time_budget_s),
                          ("--context-tokens", a.context_tokens)):
            if val is not None:
                argv += [flag, str(val)]
        os.execv(sys.executable, argv)
    workdir = Path(a.workdir) if a.workdir else DATA.parent
    only = {c for c in a.only.split(",") if c} or None
    try:
        res = run_product(a.cik, workdir, on_progress=print_progress, key=a.key or None, model=a.model, only=only,
                          skip_fetch=a.skip_fetch, budget_usd=a.budget_usd, time_budget_s=a.time_budget_s,
                          context_tokens=a.context_tokens)
    except Refusal as r:
        print(f"refused: {r.reason}")
        for c in r.commands:
            print("  " + c)
        return 1
    for s in res.skipped_documents:
        print(f"  [skipped] {s['document']}: {s['reason']}")
    print(res.summary())
    print(res.cost.line(float(os.environ.get("TARK_BUDGET_USD", DEFAULT_BUDGET_USD)) if a.budget_usd is None else a.budget_usd))
    print(f"report: {res.report_path}")
    print("validate:", "clean" if not res.validate_errors else "\n  ".join(res.validate_errors))
    print("next: python src/produce.py && python src/build_site.py, then the full gate chain")
    if res.validate_errors:
        return 1
    if res.stopped and res.stopped["reason"] == "estimate over budget":
        return 3
    return 2 if res.stopped else 0


if __name__ == "__main__":
    sys.exit(main())

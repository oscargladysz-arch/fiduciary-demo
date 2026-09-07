"""
Ingest: evaluate a new fund from its CIK
    python src/ingest.py <cik> --key <product_key> [--model ID] [--only 2.1,2.3]
                         [--skip-fetch] [--dry-run DIR]

Stages, each a function an offline test drives with a mock client:
  1 registry check   data/registry.json must already carry the product (the
                     cohort, strategy and wrapper are judgments a person makes)
  2 scaffold         data/products/<key>.json and the evidence CSV via the
                     promote helpers (55 cells, census prefills at structured)
  3 fetch            src/fetch_edgar.fetch_product (the registry's document
                     sets) unless --skip-fetch
  4 text             every held filing to plain text with page anchors
  5 extract          one structured call per extractable cell (CELL_CONTRACT),
                     the filings as a cached prefix
  6 verify           the returned quote must appear verbatim (whitespace and
                     quote marks normalized) in the cited document. Verified:
                     status extracted-unverified. Not located: status partial
                     with the reason. Not found: the cell stays pending and the
                     reason goes to the report. Nothing is ever verified here.
  7 write            product JSON and evidence CSV together, then validate

Env: ANTHROPIC_API_KEY (or an `ant auth login` profile), TARK_INGEST_MODEL
(default claude-opus-5), TARK_DATA_DIR (--dry-run sets it for the run).
The model never sees a cell it may not write: engine-owned, advisor-completed
and census-prefilled cells are not in the contract, and an existing
extracted, verified or structured cell is never overwritten.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from resolve_citations import references
from tark_data import (CELLS, DATA, EVIDENCE_COLUMNS, load_evidence, load_product,
                       status_kind, validate_product)

DEFAULT_MODEL = "claude-opus-5"
MODEL = os.environ.get("TARK_INGEST_MODEL", DEFAULT_MODEL)

# cells the model may not write: engine outputs, the adopting fiduciary's own
# cells, and the two the census prefills at status structured
ENGINE_OWNED = ("1.6", "1.7", "1.8", "1.9", "2.9", "3.8", "3.9", "5.2", "5.3", "5.4", "5.5", "5.6", "5.7")
ADVISOR_CELLS = ("2.8", "2.10", "3.5", "3.7", "4.9", "6.6", "6.8")
CENSUS_CELLS = ("4.5", "4.6")
# (element instruction, preferred document sets). The instruction says what the
# cell holds, never what the answer should be.
CELL_CONTRACT: dict[str, tuple[str, tuple[str, ...]]] = {
    "1.1": ("The fund's net total return series as printed: the table or paragraph giving annual or "
            "cumulative net total returns per share class, with the period ends.", ("annual_report",)),
    "1.2": ("Trailing (1, 3, 5 year, since inception) and calendar or fiscal year net returns as "
            "printed, per share class, with the as-of date.", ("annual_report", "prospectus")),
    "1.3": ("Any gross vs net return figures, or the expense drag between them, as printed.", ("annual_report",)),
    "1.4": ("Distribution history and composition: rate, frequency, and the share that is return of "
            "capital vs income, as printed (Section 19 notices count).", ("annual_report", "prospectus")),
    "1.5": ("Performance of underlying sleeves, funds or general partners where the fund reports it.", ("annual_report",)),
    "1.10": ("Market price and premium or discount to NAV, if the shares trade on an exchange. If the "
             "filing states the shares are not listed, that statement.", ("annual_report", "prospectus")),
    "1.11": ("Inception date of the fund and of each share class, and the tenure of the portfolio "
             "managers as printed.", ("prospectus", "annual_report")),
    "2.1": ("The management fee: the annual rate AND the base it is charged on (net assets, managed "
            "assets, gross assets including borrowings, NAV), exactly as the fee table or advisory "
            "agreement states it.", ("prospectus",)),
    "2.2": ("Incentive or performance fee terms: rate, hurdle, catch-up, high-water mark, crystallization "
            "period, or the statement that there is none.", ("prospectus",)),
    "2.3": ("Total annual expense ratio per share class, gross and net of any waiver, and the waiver "
            "or expense limitation terms including recoupment.", ("prospectus", "annual_report")),
    "2.4": ("Acquired fund fees and expenses (AFFE) line of the fee table, or the statement that there is none.", ("prospectus",)),
    "2.5": ("Economics of underlying general partners or funds borne indirectly: carried interest, "
            "underlying management fees, as disclosed.", ("prospectus", "annual_report")),
    "2.6": ("Sales loads, distribution and servicing fees per share class, as the fee table states.", ("prospectus",)),
    "2.7": ("Early repurchase fee or short-term trading fee: rate and holding period, or the statement "
            "that there is none.", ("prospectus",)),
    "3.1": ("Wrapper liquidity terms: repurchase or tender frequency, the cap per offer and its base "
            "(percent of outstanding shares or NAV), and whether offers are mandatory or discretionary.", ("prospectus",)),
    "3.2": ("Repurchase mechanics: notice periods, pricing date, payment timing, pro-rata rules when "
            "oversubscribed.", ("prospectus", "tender_offer")),
    "3.3": ("Repurchase history: amounts requested and accepted per offer, and any proration or "
            "suspension, as reported.", ("annual_report", "tender_offer", "repurchase_history")),
    "3.4": ("Portfolio liquidity profile: share of illiquid holdings, liquidity classifications, "
            "credit facilities available for repurchases, as reported.", ("annual_report",)),
    "3.6": ("Fund leverage: borrowings outstanding, facility size, asset coverage, and limits, as reported.", ("annual_report", "prospectus")),
    "4.1": ("Valuation policy and NAV frequency: how often NAV is struck and who determines fair value.", ("prospectus", "annual_report")),
    "4.2": ("Fair value hierarchy: the Level 1, 2 and 3 amounts or percentages of the portfolio as of "
            "the period end.", ("annual_report",)),
    "4.3": ("Independent valuation agent or third-party pricing service, named, and its role.", ("prospectus", "annual_report")),
    "4.4": ("Valuation methodology by asset type as described in the notes to the financial statements.", ("annual_report",)),
    "4.7": ("Premium or discount to NAV where a market price exists, or the statement that none exists.", ("annual_report",)),
    "4.8": ("Any smoothing, appraisal-lag or stale-pricing disclosure about the NAV.", ("prospectus", "annual_report")),
    "5.1": ("The benchmark or index the fund itself declares for performance comparison, or the "
            "statement that it declares none (the SEC-required broad index counts, and say so).", ("annual_report", "prospectus")),
    "6.1": ("Legal structure and wrapper: registration type, interval or tender-offer status, "
            "exchange listing, as the filing states.", ("prospectus",)),
    "6.2": ("Investment strategy and principal holdings types as the filing states them.", ("prospectus",)),
    "6.3": ("Fiduciary or advice disclaimers directed at retirement plans or plan fiduciaries.", ("prospectus",)),
    "6.4": ("Tax reporting form delivered to shareholders (Form 1099 or Schedule K-1) and the fund's "
            "tax status (RIC, REIT, partnership).", ("prospectus",)),
    "6.5": ("Eligibility and minimums: who may invest, minimum initial investment per class, "
            "accredited or qualified client requirements.", ("prospectus",)),
    "6.7": ("Conflicts of interest and affiliated transactions disclosed.", ("prospectus", "annual_report")),
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


# ------------------------------------------------------------- filing text
class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "td", "th"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        if tag in self.BLOCK:
            self.parts.append("\n" if tag != "td" and tag != "th" else " ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        if tag in self.BLOCK:
            self.parts.append("\n" if tag != "td" and tag != "th" else " ")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


PAGE_BREAK = re.compile(r"<[^>]*page-break-(?:before|after)\s*:\s*always[^>]*>", re.I)


def html_to_text(html: str) -> str:
    p = _Text()
    p.feed(html)
    text = "".join(p.parts)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


@dataclass
class FilingText:
    label: str            # "N-CSR filed 2026-06-09 (accession 0001234567-26-000001)"
    path: str
    pages: list[str]

    @property
    def text(self) -> str:
        return "\n".join(f"[page {i}]\n{pg}" for i, pg in enumerate(self.pages, 1))

    def page_of(self, needle: str) -> int | None:
        n = normalize(needle)
        for i, pg in enumerate(self.pages, 1):
            if n and n in normalize(pg):
                return i
        return None


def filing_text(path: Path, label: str) -> FilingText:
    raw = path.read_text(errors="replace")
    if "<" in raw and ">" in raw:
        chunks = PAGE_BREAK.split(raw)
        pages = [t for t in (html_to_text(c) for c in chunks) if t]
    else:
        pages = [raw.strip()]
    return FilingText(label=label, path=str(path), pages=pages or [""])


def held_filings(key: str, manifest_path: Path | None = None) -> list[dict]:
    mp = manifest_path or (DATA / "manifest.csv")
    if not mp.exists():
        return []
    with open(mp, newline="") as fh:
        return [r for r in csv.DictReader(fh) if r["product"] == key]


def doc_label(row: dict) -> str:
    return f"{row['form']} filed {row['filing_date']} (accession {row['accession']})"


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


def build_messages(cid: str, docs: list[FilingText]) -> tuple[str, list[dict]]:
    instruction, prefer = CELL_CONTRACT[cid]
    doc_blocks = "\n\n".join(f"=== DOCUMENT: {d.label} ===\n{d.text}" for d in docs)
    user = [
        {"type": "text", "text": "Documents on record for this fund:\n\n" + doc_blocks,
         "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": (f"Cell {cid}, {CELLS[cid]}. What it holds: {instruction} "
                                  f"Prefer these document sets when several answer: {', '.join(prefer)}. "
                                  "Return the structured result.")},
    ]
    return SYSTEM, [{"role": "user", "content": user}]


def extract_cell(client, cid: str, docs: list[FilingText], model: str = MODEL) -> CellExtraction:
    system, messages = build_messages(cid, docs)
    response = client.messages.parse(model=model, max_tokens=4096, system=system,
                                     messages=messages, output_format=CellExtraction)
    if getattr(response, "stop_reason", None) == "refusal":
        return CellExtraction(found=False, value="", quote="", source_doc="", section="",
                              not_found_reason="the model declined the request (stop_reason refusal)")
    return response.parsed_output


@dataclass
class Outcome:
    cid: str
    status: str                      # extracted-unverified | partial - ... | pending extraction
    record: dict | None              # the cell record to write, None when the cell is left alone
    reason: str = ""
    local_file: str = ""             # the cited filing's path under the record, when the filing was held
    accession: str = ""              # its accession number, from the document label


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
    # (audit item 41): the held filing's path and its accession, from the
    # label the ingest itself wrote, so a person signing the row later
    # finds the filing without retyping anything
    refs = references(doc.label) if doc else []
    acc = refs[0]["accessions"][0] if refs and refs[0].get("accessions") else ""
    return Outcome(cid, status, record, "" if located else why,
                   local_file=_record_relative(doc.path) if doc else "", accession=acc)


# --------------------------------------------------------------------- write
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
    (DATA / "products" / f"{key}.json").write_text(json.dumps(product, indent=2, ensure_ascii=False) + "\n")
    with open(DATA / "evidence" / f"{key}_evidence.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=EVIDENCE_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return written


def run_extraction(client, key: str, docs: list[FilingText], only: set[str] | None = None,
                   model: str = MODEL, today: str | None = None) -> list[Outcome]:
    """Extract, verify and write every writable cell in the contract. Returns
    the outcomes, including the cells left pending with their reasons."""
    today = today or date.today().isoformat()
    product = load_product(key)
    outcomes = []
    for cid in extractable_cells():
        if only and cid not in only:
            continue
        kind = status_kind(str(product["cells"][cid].get("status", "pending")))
        if kind not in WRITABLE_KINDS:
            outcomes.append(Outcome(cid, product["cells"][cid]["status"], None, f"kept: {kind} cell"))
            continue
        ex = extract_cell(client, cid, docs, model)
        outcomes.append(verify(cid, ex, docs, model, today))
    write_cells(key, outcomes, today)
    report = {"product": key, "model": model, "date": today,
              "documents": [d.label for d in docs],
              "outcomes": [{"cell": o.cid, "status": o.status, "reason": o.reason} for o in outcomes]}
    (DATA / "ingest").mkdir(exist_ok=True)
    (DATA / "ingest" / f"{key}_report.json").write_text(json.dumps(report, indent=2))
    return outcomes


# ---------------------------------------------------------------------- main
def registry_entry(key: str) -> dict | None:
    rp = DATA / "registry.json"
    if not rp.exists():
        return None
    return json.loads(rp.read_text())["products"].get(key)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cik")
    ap.add_argument("--key", required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--only", default="", help="comma-separated cell ids")
    ap.add_argument("--skip-fetch", action="store_true")
    ap.add_argument("--dry-run", default="", metavar="DIR",
                    help="run against a copy of data/ in DIR, the repository is not touched")
    a = ap.parse_args()
    if a.dry_run:
        import shutil
        dst = Path(a.dry_run).resolve()
        if not dst.exists():
            shutil.copytree(DATA, dst, ignore=shutil.ignore_patterns("raw", "census"))
        os.environ["TARK_DATA_DIR"] = str(dst)
        print(f"dry run against {dst}")
        os.execv(sys.executable, [sys.executable, __file__, a.cik, "--key", a.key, "--model", a.model,
                                  "--only", a.only] + (["--skip-fetch"] if a.skip_fetch else []))

    reg = registry_entry(a.key)
    if reg is None:
        print(f"refused: data/registry.json has no entry for {a.key}. Add it first (cohort, strategy, "
              "asset_class, sub_strategy, wrapper_type, pricing_class, nav_cadence, leverage_regime, "
              "held_returns, advisers, adviser_keys, declared_benchmarks, source_cells, as_of, depth, "
              "membership_rationale, filings, each with its source). Those are judgments a person makes.")
        return 1
    if not (DATA / "products" / f"{a.key}.json").exists():
        import subprocess
        r = subprocess.run([sys.executable, str(Path(__file__).with_name("promote.py")), a.cik, "--key", a.key])
        if r.returncode:
            return r.returncode
    if not a.skip_fetch:
        import fetch_edgar
        fetch_edgar.fetch_product(a.key)
    rows = held_filings(a.key)
    if not rows:
        print("refused: no filings held for this product in data/manifest.csv (run without --skip-fetch)")
        return 1
    docs = []
    for r in rows:
        if not r.get("local_path"):
            continue    # a structured-dataset row names an accession, not a document on disk
        p = DATA.parent / r["local_path"] if not Path(r["local_path"]).is_absolute() else Path(r["local_path"])
        if p.is_file():
            docs.append(filing_text(p, doc_label(r)))
    if not docs:
        print("refused: manifest rows exist but no local filing text is on disk (data/raw is not in git)")
        return 1
    chars = sum(len(d.text) for d in docs)
    print(f"{len(docs)} documents, {chars:,} characters of text (roughly {chars // 4:,} tokens, an estimate)")
    import anthropic
    client = anthropic.Anthropic()
    only = {c for c in a.only.split(",") if c} or None
    outcomes = run_extraction(client, a.key, docs, only, a.model)
    for o in outcomes:
        print(f"  {o.cid:5s} {o.status[:60]:60s} {o.reason[:50]}")
    errs = validate_product(a.key)
    print("validate:", "clean" if not errs else "\n  ".join(errs))
    print("next: python src/produce.py && python src/build_site.py, then the full gate chain")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())

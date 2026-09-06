"""
Case law for cell 5.7: fetch the documents, then write the cell from them
=========================================================================
Cell 5.7 (case-law tracker) is cross-product: every product carries the
same row. Round 1 seeded it from search-result snippets. This script
replaces that row with text drawn from the saved documents only: the
Supreme Court docket page for No. 25-498, the questions presented document
that page links, and the Ninth Circuit opinion under review. No sentence
of the cell comes from memory or from a search snippet.

Two steps, always in this order.

Step 1, fetch (a networked machine, from the repository root)
--------------------------------------------------------------
    export TARK_SEC_CONTACT='Your Name your@email'
    python src/fetch_caselaw.py fetch --opinion-url URL

  Files that appear under data/raw/caselaw/ (not tracked, like the filings):
    25-498_docket.html            the docket page as served, and 25-498_docket_text.txt
    25-498_qp.pdf                 the questions presented document, and 25-498_qp_text.txt
    ca9_opinion.pdf               the opinion under review, and ca9_opinion_text.txt
  and data/caselaw/manifest.csv (tracked): one row per document with the URL,
  the fetch time, the sha256 of the bytes as served, the sha256 of the
  extracted text and a note. Nothing is saved unless the docket page names
  docket No. 25-498. The opinion is recorded only when the lower-court case
  number the docket page states appears in its text.

  PDF text needs pypdf (pip install pypdf in the venv) or the pdftotext
  command. Install one before the fetch step.

Step 2, apply (any machine that holds the files the manifest lists)
-------------------------------------------------------------------
    python src/fetch_caselaw.py apply             prints the parsed fields and the
                                                  new cell, writes nothing
    python src/fetch_caselaw.py apply --write     writes cell 5.7 in every product
                                                  JSON and evidence CSV

  Refuses when the manifest or any listed file is absent or a hash differs
  from the manifest. Writes status extracted-unverified, never verified,
  and never overwrites a verified row. The cell states: the title and the
  docketed date as the page states them, the question presented quoted
  from the questions presented document, the dated docket entries for the
  petition, the grant and any decision, an argument entry only when the
  docket page lists one with its date, the lower-court block, and that the
  cell draws no consequence. Then commit data/caselaw/manifest.csv with the
  sixteen product files and the sixteen evidence files, log the change
  (python src/corrections_log.py write --cause "R2-P1-14: ...") and add the
  allowlist rows the apply step prints.

URLs, none confirmed from the build container (which cannot reach the courts)
----------------------------------------------------------------------------
  Docket page, default --docket-url:
      https://www.supremecourt.gov/docket/docketfiles/html/public/25-498.html
    This is the layout of the Court's public docket files. Confirm it in a
    browser first. The page's own docket number is checked before anything
    is saved, so a wrong URL saves nothing.
  Questions presented: taken from the docket page's own link whose path
    contains /qp/, never guessed. If the page links none, the fetch step
    says so, and --qp-url may be passed after confirming the link by hand.
  Ninth Circuit opinion (137 F.4th 1015 per the task brief): no default.
    The Court of Appeals publishes opinions under
      https://cdn.ca9.uscourts.gov/datastore/opinions/YYYY/MM/DD/<case number>.pdf
    with the case number and decision date the docket page's lower-court
    block states. Confirm the exact URL and pass --opinion-url. The
    reporter citation is recorded in the manifest note as supplied by the
    brief, not read from the document.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tark_data import (BASE, CELLS, DATA, EVIDENCE_COLUMNS, load_evidence, load_product,  # noqa: E402
                       product_keys, sec_user_agent, status_kind)

DOCKET = "25-498"
DOCKET_URL = f"https://www.supremecourt.gov/docket/docketfiles/html/public/{DOCKET}.html"
OPINION_CITATION_PER_BRIEF = "137 F.4th 1015"
MANIFEST_COLUMNS = ["document", "docket", "url", "local_path", "sha256", "bytes",
                    "text_path", "text_sha256", "fetched_at_utc", "note"]
DOC_DOCKET, DOC_QP, DOC_OPINION = "scotus_docket", "scotus_questions_presented", "ca9_opinion"
CELL = "5.7"

DATE_ROW = re.compile(r"^([A-Z][a-z]{2} \d{1,2} \d{4})\t+(.+)$")
# the heading as the Court's document prints it: capitals, at the start of a
# line. Lower-case mentions of the phrase in running text are not the heading.
QP_HEAD = re.compile(r"^[ \t]*QUESTIONS? PRESENTED\b", re.M)
FIELD_RES = {
    "title": re.compile(r"^Title:\s*(.*)$", re.M),
    "docketed": re.compile(r"^Docketed:\s*(.+)$", re.M),
    "lower_ct": re.compile(r"^Lower Ct:\s*(.+)$", re.M),
    "case_numbers": re.compile(r"^Case (?:Numbers?|Nos?\.?):\s*(.+)$", re.M),
    "decision_date": re.compile(r"^Decision Date:\s*(.+)$", re.M),
}


# ------------------------------------------------------------------ paths
def raw_dir() -> Path:
    return DATA / "raw" / "caselaw"


def manifest_path() -> Path:
    return DATA / "caselaw" / "manifest.csv"


def local_path_of(path: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(BASE))
    except ValueError:
        return str(path)


def resolve_local(rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else BASE / p


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------- fetching
def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": sec_user_agent(),
                                               "Accept": "text/html, application/pdf, text/plain"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


class _Text(HTMLParser):
    """HTML to text: block tags break lines, table cells are tab-separated,
    scripts and styles are dropped."""
    BLOCK = {"p", "div", "tr", "br", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6",
             "section", "header", "footer", "ul", "ol"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag in ("td", "th"):
            self.parts.append("\t")
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.hrefs.append(v)

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def parse_html(data: bytes) -> tuple[str, list[str]]:
    p = _Text()
    p.feed(data.decode("utf-8", errors="replace"))
    p.close()
    lines = [re.sub(r"[ \xa0]+", " ", ln).strip(" \t") for ln in "".join(p.parts).splitlines()]
    return "\n".join(ln for ln in lines if ln), p.hrefs


def html_text(data: bytes) -> str:
    return parse_html(data)[0]


def qp_links(data: bytes, page_url: str) -> list[str]:
    _, hrefs = parse_html(data)
    return sorted({urllib.parse.urljoin(page_url, h) for h in hrefs if "/qp/" in h.lower()})


def pdf_text(pdf_path: Path) -> str:
    try:
        import pypdf  # type: ignore
        return "\n".join((pg.extract_text() or "") for pg in pypdf.PdfReader(str(pdf_path)).pages)
    except ImportError:
        pass
    if shutil.which("pdftotext"):
        r = subprocess.run(["pdftotext", "-layout", str(pdf_path), "-"],
                           capture_output=True, text=True, check=True)
        return r.stdout
    raise SystemExit("no PDF text tool: pip install pypdf in the venv (or install pdftotext), "
                     "then rerun the fetch step")


def save_document(stem: str, data: bytes) -> tuple[Path, Path]:
    """The bytes as served under their kind's suffix, and the extracted text
    beside them as <stem>_text.txt."""
    d = raw_dir()
    d.mkdir(parents=True, exist_ok=True)
    head = data[:512].lower()
    if data[:5] == b"%PDF-":
        path = d / f"{stem}.pdf"
        path.write_bytes(data)
        text = pdf_text(path)
    elif b"<html" in head or b"<!doctype" in head:
        path = d / f"{stem}.html"
        path.write_bytes(data)
        text = html_text(data)
    else:
        path = d / f"{stem}.txt"
        path.write_bytes(data)
        text = data.decode("utf-8", errors="replace")
    text_path = d / f"{stem}_text.txt"
    text_path.write_text(text, encoding="utf-8")
    return path, text_path


def manifest_row(document: str, docket: str, url: str, path: Path, text_path: Path,
                 fetched_at: str, note: str) -> dict:
    data = path.read_bytes()
    return {"document": document, "docket": docket, "url": url,
            "local_path": local_path_of(path), "sha256": sha256(data), "bytes": str(len(data)),
            "text_path": local_path_of(text_path), "text_sha256": sha256(text_path.read_bytes()),
            "fetched_at_utc": fetched_at, "note": note}


def write_manifest(rows: list[dict]) -> Path:
    """Replace the rows of the same document kind, keep the others."""
    mpath = manifest_path()
    mpath.parent.mkdir(parents=True, exist_ok=True)
    kinds = {r["document"] for r in rows}
    kept: list[dict] = []
    if mpath.exists():
        with mpath.open(newline="", encoding="utf-8") as fh:
            kept = [r for r in csv.DictReader(fh) if r["document"] not in kinds]
    with mpath.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        w.writeheader()
        w.writerows(kept + rows)
    return mpath


def fetch(docket: str, docket_url: str, opinion_url: str | None, qp_url: str | None,
          getter=get, fetched_at: str | None = None) -> list[dict]:
    """Save the documents and write their manifest rows. Returns the rows."""
    fetched_at = fetched_at or now_utc()
    page = getter(docket_url)
    page_text = html_text(page)
    if docket not in page_text:
        raise SystemExit(f"the page at {docket_url} does not name docket No. {docket}. Nothing saved.")
    rows = []
    path, text_path = save_document(f"{docket}_docket", page)
    rows.append(manifest_row(DOC_DOCKET, docket, docket_url, path, text_path, fetched_at,
                             "Supreme Court docket page as served"))
    print(f"saved docket page {path} ({rows[-1]['bytes']} bytes)")
    fields = docket_fields(page_text)

    links = [qp_url] if qp_url else qp_links(page, docket_url)
    if len(links) == 1:
        qp = getter(links[0])
        path, text_path = save_document(f"{docket}_qp", qp)
        qp_text = text_path.read_text(encoding="utf-8")
        note = ("questions presented document linked from the docket page"
                if not qp_url else "questions presented document at the URL passed by hand")
        if not QP_HEAD.search(qp_text):
            note += ". No questions presented heading found in its text, the apply step will refuse"
        rows.append(manifest_row(DOC_QP, docket, links[0], path, text_path, fetched_at, note))
        print(f"saved questions presented {path} ({rows[-1]['bytes']} bytes)")
    elif not links:
        print("the docket page links no questions presented document (no href containing /qp/). "
              "Confirm the link by hand and pass --qp-url. The apply step refuses without it.")
    else:
        print("the docket page links several /qp/ documents, pass the right one with --qp-url:")
        for u in links:
            print("   ", u)

    if opinion_url:
        op = getter(opinion_url)
        path, text_path = save_document("ca9_opinion", op)
        op_text = text_path.read_text(encoding="utf-8")
        numbers = re.findall(r"\d{2}-\d{4,5}", fields.get("case_numbers") or "")
        if numbers and not any(n in op_text for n in numbers):
            path.unlink()
            text_path.unlink()
            print(f"the document at {opinion_url} does not carry the lower-court case number the "
                  f"docket page states ({', '.join(numbers)}). Not recorded.")
        else:
            note = (f"opinion under review. Reporter citation {OPINION_CITATION_PER_BRIEF} per the "
                    "task brief, not read from the document")
            if not numbers:
                note += ". The docket page states no lower-court case number, identity not checked"
            rows.append(manifest_row(DOC_OPINION, docket, opinion_url, path, text_path, fetched_at, note))
            print(f"saved opinion {path} ({rows[-1]['bytes']} bytes)")
    else:
        print("no --opinion-url passed, the opinion under review is not fetched")
    mpath = write_manifest(rows)
    print(f"manifest {mpath}: {len(rows)} row(s) written")
    return rows


# ----------------------------------------------------------------- parsing
def docket_fields(text: str) -> dict:
    """What the docket page states, read from its text: the title block and
    every dated proceedings row."""
    out: dict = {}
    lines = text.splitlines()
    for name, rx in FIELD_RES.items():
        m = rx.search(text)
        val = m.group(1).strip() if m else ""
        if m and not val:
            # the value sits on the next line when the page puts it in its own block
            idx = text[:m.start()].count("\n")
            val = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
        out[name] = val
    out["entries"] = [(m.group(1), m.group(2).strip()) for ln in lines if (m := DATE_ROW.match(ln))]
    return out


def question_presented(text: str) -> str:
    m = QP_HEAD.search(text)
    if not m:
        raise SystemExit("no questions presented heading in the saved document text, refusing to quote it")
    return re.sub(r"\s+", " ", text[m.end():]).strip()


def key_entries(entries: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    picked = []
    for d, t in entries:
        low = t.lower()
        if "petition for a writ of certiorari" in low and "filed" in low:
            tag = "petition"
        elif re.search(r"\bpetition (?:granted|denied)\b", low):
            tag = "grant"
        elif re.search(r"\bargu", low):
            tag = "argument"
        elif re.search(r"\bjudgment\b|\badjudged\b|\baffirmed\b|\breversed\b|\bvacated\b", low):
            tag = "decision"
        else:
            continue
        picked.append((tag, d, t))
    return picked


def compose(rows: dict[str, dict], docket_text: str, qp_text: str) -> dict:
    """Cell 5.7 from the documents alone. Every sentence names the document
    it comes from."""
    dk = rows[DOC_DOCKET]
    docket = dk["docket"]
    fetched_date = dk["fetched_at_utc"][:10]
    f = docket_fields(docket_text)
    qp = question_presented(qp_text)
    picked = key_entries(f["entries"])
    parts = []
    title = f["title"] or f"docket No. {docket}"
    parts.append(f"{title}, No. {docket}, Supreme Court of the United States, as the docket page states.")
    if f["docketed"]:
        parts.append(f"Docketed {f['docketed']} per the docket page.")
    parts.append(f'Question presented, quoted from the questions presented document the docket page links: "{qp}"')
    core = [(d, t) for tag, d, t in picked if tag in ("petition", "grant", "decision")]
    if core:
        parts.append("Docket entries the docket page states: "
                     + ". ".join(f"{d}, {t.rstrip('.')}" for d, t in core) + ".")
    arg = [(d, t) for tag, d, t in picked if tag == "argument"]
    if arg:
        parts.append("Argument entries the docket page states: "
                     + ". ".join(f"{d}, {t.rstrip('.')}" for d, t in arg) + ".")
    if not any(tag == "decision" for tag, _, _ in picked):
        parts.append(f"As of the fetch date {fetched_date} the docket page lists no entry recording "
                     "a decision of the Court.")
    if f["entries"]:
        parts.append(f"The docket page lists {len(f['entries'])} entries from {f['entries'][0][0]} "
                     f"to {f['entries'][-1][0]}.")
    if f["lower_ct"]:
        s = f"Decision under review as the docket page states: {f['lower_ct']}"
        if f["case_numbers"]:
            s += f", case number {f['case_numbers']}"
        if f["decision_date"]:
            s += f", decision date {f['decision_date']}"
        s += (". The opinion is held in the record with its content hash." if DOC_OPINION in rows
              else ". The opinion is not held in the record.")
        parts.append(s)
    parts.append("This cell draws no consequence for the evaluation.")
    source = (f"Supreme Court docket No. {docket}, {dk['url']}, fetched {fetched_date}. "
              f"Questions presented document linked from the docket page, {rows[DOC_QP]['url']}, "
              f"fetched {rows[DOC_QP]['fetched_at_utc'][:10]}.")
    if DOC_OPINION in rows:
        source += (f" Decision under review, {rows[DOC_OPINION]['url']}, "
                   f"fetched {rows[DOC_OPINION]['fetched_at_utc'][:10]}.")
    source += " Content hashes are in the case-law manifest."
    return {
        "element": CELLS[CELL],
        "value": " ".join(parts),
        "status": "extracted-unverified",
        "source": source,
        "section": ("docket page (title, docketed date, lower court block, proceedings and orders) "
                    "and the questions presented document (full text)"),
        "quote": qp,
        "extracted_by": f"Tark case-law fetcher ({fetched_date})",
        "verified_by": "",
        "local_file": dk["local_path"],
        "date_pulled": fetched_date,
    }


# ------------------------------------------------------------------- apply
def load_manifest() -> dict[str, dict]:
    mpath = manifest_path()
    if not mpath.exists():
        raise SystemExit("the case-law manifest is absent. Run the fetch step on a networked machine first. "
                         "Nothing written.")
    with mpath.open(newline="", encoding="utf-8") as fh:
        rows = {r["document"]: r for r in csv.DictReader(fh)}
    problems = []
    for kind in (DOC_DOCKET, DOC_QP):
        if kind not in rows:
            problems.append(f"no manifest row for {kind}")
    for kind, r in rows.items():
        for col, hcol in (("local_path", "sha256"), ("text_path", "text_sha256")):
            p = resolve_local(r[col])
            if not p.exists():
                problems.append(f"{kind}: {r[col]} is absent")
            elif sha256(p.read_bytes()) != r[hcol]:
                problems.append(f"{kind}: {r[col]} does not match its manifest hash")
    if problems:
        raise SystemExit("refusing to apply: " + ". ".join(problems) + ". Nothing written.")
    return rows


def new_cell() -> dict:
    rows = load_manifest()
    docket_text = resolve_local(rows[DOC_DOCKET]["text_path"]).read_text(encoding="utf-8")
    if rows[DOC_DOCKET]["docket"] not in docket_text:
        raise SystemExit("the saved docket page does not name the docket number in its manifest row. Nothing written.")
    qp_text = resolve_local(rows[DOC_QP]["text_path"]).read_text(encoding="utf-8")
    return compose(rows, docket_text, qp_text)


def apply(write: bool) -> list[str]:
    """Print the new cell, then per product the old and the new status. With
    write, rewrite the product JSON and the evidence CSV row. Returns the
    keys changed (or that would change)."""
    cell = new_cell()
    print("new cell 5.7 (identical for every product):")
    for k in ("value", "status", "source", "section", "quote", "extracted_by"):
        print(f"  {k}: {cell[k]}")
    changed = []
    for key in product_keys():
        product = load_product(key)
        old = product["cells"][CELL]
        if status_kind(str(old.get("status", ""))) == "verified":
            raise SystemExit(f"refusing to overwrite {key} {CELL}: it is verified. Nothing written.")
        same = all(old.get(k) == cell[k] for k in ("value", "status", "source", "section", "quote"))
        print(f"{key:<18} {CELL}: {old.get('status', '')[:40]!r} -> {cell['status']!r}"
              + ("  (no change)" if same else ""))
        if same:
            continue
        changed.append(key)
        if not write:
            continue
        product["cells"][CELL] = {k: cell[k] for k in ("element", "value", "status", "source", "section",
                                                       "quote", "extracted_by", "verified_by")}
        (DATA / "products" / f"{key}.json").write_text(
            json.dumps(product, indent=2, ensure_ascii=False) + "\n")
        rows = load_evidence(key)
        for r in rows:
            if r["cell_id"] == CELL:
                r.update({"element": cell["element"], "value": cell["value"], "source_doc": cell["source"],
                          "source_section": cell["section"], "quote": cell["quote"],
                          "local_file": cell["local_file"], "accession": "", "date_pulled": cell["date_pulled"],
                          "extracted_by": cell["extracted_by"], "verified_by": "", "status": cell["status"]})
        with open(DATA / "evidence" / f"{key}_evidence.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=EVIDENCE_COLUMNS)
            w.writeheader()
            w.writerows(rows)
    if changed and not write:
        print(f"\ndry run: {len(changed)} product(s) would change. Rerun with --write.")
    elif changed:
        print(f"\nwrote cell {CELL} for {len(changed)} product(s). Now log it and allowlist the rows:")
        print('  python src/corrections_log.py write --cause "R2-P1-14: cell 5.7 written from the '
              'saved court documents"')
        for key in changed:
            for col in ("value", "source_doc", "source_section", "quote", "local_file", "date_pulled",
                        "extracted_by", "status"):
                print(f"  python src/corrections_log.py allow --product {key} --cell {CELL} --column {col} "
                      f'--reason "R2-P1-14: cell 5.7 rewritten from the saved court documents"')
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="save the documents and write the manifest (networked machine)")
    f.add_argument("--docket-url", default=DOCKET_URL,
                   help="docket page URL (default is the Court's public docket file layout, confirm it first)")
    f.add_argument("--qp-url", default=None,
                   help="questions presented URL, only when the docket page's own link is not usable")
    f.add_argument("--opinion-url", default=None,
                   help="URL of the opinion under review, confirmed by hand (no default)")
    a_ = sub.add_parser("apply", help="write cell 5.7 from the saved documents")
    a_.add_argument("--write", action="store_true", help="write the product and evidence files")
    a = ap.parse_args()
    if a.cmd == "fetch":
        fetch(DOCKET, a.docket_url, a.opinion_url, a.qp_url)
    else:
        apply(a.write)
    return 0


if __name__ == "__main__":
    sys.exit(main())

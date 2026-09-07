"""
Human verification of one evidence cell
    python src/verify_cell.py <product> <cell> --signer "Name, role" --date YYYY-MM-DD
                              [--document <file>] [--fetch] [--note "..."] [--dry-run]

The only path that writes a `verified` status, and only a person runs it:
  - signer and an ISO date are required, a signer that names a script,
    pipeline, model or agent is refused (verification is human work)
  - only a cell at extracted-unverified with a source and a verbatim quote
    can be verified (partial, computed, structured and n/a cannot)
  - the quote is checked against the cited document before anything is
    written. The document is the manifest row for the evidence row's
    accession (or every row the citations file lists when the accession
    column says "multiple"), read from its local file, or --document <file>
    when the person holds a copy, or --fetch, which downloads the manifest
    URL with TARK_SEC_CONTACT set. No document on this machine, no
    signature. A quote with an ellipsis is checked fragment by fragment,
    in order, whitespace and typographic quotes normalized, nothing else.
  - the row keeps its value, source, section and quote unchanged: verifying
    signs, it does not edit
  - status becomes "verified - <signer>, <date>" and verified_by
    "<signer>, <date>", in the product JSON and the evidence CSV together,
    and the two columns are allowlisted in the corrections log with the
    reason "verified by <signer> on <date>, quote found in <document>". The
    evidence immutability gate reads that row, and the invariants gate
    accepts a verified row only when the row is there (decision 7.4).
  - --dry-run runs every check including the quote, prints the row it
    would write and writes nothing
No producer, build or test calls this without --dry-run or a scratch record.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from tark_data import CELLS, DATA, EVIDENCE_COLUMNS, load_evidence, load_manifest, load_product, status_kind

# word-bounded: "Talbot" and "Cabot" are people, "bot" alone is not
NOT_A_PERSON = re.compile(r"\b(claude|gpt|model|pipeline|agent|script|bot|automation|assistant|copilot|gemini|llm)\b"
                          r"|ingest\.py", re.I)
ALLOW_REASON = "verified by {signer} on {date}, quote found in {document}"
ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…|\.\s\.\s\.|\[\.\.\.\]|\[…\])\s*")
_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "—": "-", "–": "-", "\xa0": " "})
MIN_FRAGMENT = 8


class Refused(SystemExit):
    pass


def refuse(msg: str) -> None:
    print(f"refused: {msg}")
    raise Refused(1)


# ------------------------------------------------------------ the quote check
def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").translate(_QUOTES)).strip().lower()


def _abs(rel: str) -> Path:
    """A record-relative path ('data/raw/...') under the record in use, so a
    scratch record resolves its own files."""
    p = Path(rel)
    return p if p.is_absolute() else DATA.parent / rel


def quote_fragments(quote: str) -> list[str]:
    """The quote split at its ellipses, each fragment normalized. Fragments
    shorter than MIN_FRAGMENT characters are dropped unless nothing else is
    left, so a stray '...' never makes an empty needle."""
    parts = [normalize(p) for p in ELLIPSIS.split(quote or "")]
    long = [p for p in parts if len(p) >= MIN_FRAGMENT]
    return long or [p for p in parts if p]


def quote_in_text(quote: str, text: str) -> tuple[bool, str]:
    """Every fragment of the quote in the normalized text, in order. Returns
    (found, first missing fragment)."""
    frags = quote_fragments(quote)
    if not frags:
        return False, "(empty quote)"
    pos = 0
    for f in frags:
        i = text.find(f, pos)
        if i < 0:
            return False, f
        pos = i + len(f)
    return True, ""


def document_text(path: Path) -> str:
    """The document as normalized text: HTML stripped through the ingest
    reader, anything else read as it is."""
    raw = path.read_text(errors="replace")
    if "<" in raw and ">" in raw and re.search(r"<(html|body|div|p|table)\b", raw, re.I):
        from ingest import html_to_text
        raw = html_to_text(raw)
    return normalize(raw)


def cited_documents(product: str, cid: str) -> list[dict]:
    """The documents the evidence row cites, from the record: manifest rows
    for the row's accession, or the citations file's rows when the accession
    column says 'multiple', plus the row's own local_file. Each entry:
    label, url, path (relative to the repository)."""
    row = next((r for r in load_evidence(product) if r["cell_id"] == cid), None)
    if row is None:
        return []
    acc = (row.get("accession") or "").strip()
    docs: list[dict] = []
    if acc.startswith("multiple"):
        cit = DATA / "citations" / f"{product}.json"
        if cit.exists():
            for r in (json.loads(cit.read_text()).get("cells", {}).get(cid) or []):
                if r.get("local_path"):
                    docs.append({"label": f"{r.get('form', '')} {r.get('accession', '')}".strip(),
                                 "url": r.get("url"), "path": r["local_path"]})
    elif acc:
        for r in load_manifest():
            if r.get("accession") == acc and r.get("product") == product:
                docs.append({"label": f"{r['form']} {acc}", "url": r.get("url"), "path": r["local_path"]})
    lf = (row.get("local_file") or "").strip()
    if lf and lf not in {d["path"] for d in docs}:
        docs.append({"label": Path(lf).name, "url": None, "path": lf})
    return docs


def fetch_document(doc: dict) -> Path:
    """Download the manifest URL to its local path. Needs the network and
    TARK_SEC_CONTACT (the SEC asks for an identified user agent)."""
    if not doc.get("url"):
        refuse(f"{doc['label']} has no URL in the record, pass --document <file>")
    from fetch_edgar import polite_get   # networked path only
    dest = _abs(doc["path"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(polite_get(doc["url"]))
    print(f"fetched {doc['label']} to {doc['path']}")
    return dest


def check_quote(product: str, cid: str, cell: dict, document: str | None = None, fetch: bool = False) -> str:
    """The quote must be found in a cited document. Returns the label of the
    document it was found in, refuses otherwise. A --document copy is read
    as given, the record's documents are read from disk, fetched on --fetch."""
    quote = str(cell.get("quote") or "")
    if document:
        p = Path(document)
        if not p.exists():
            refuse(f"--document {document} does not exist")
        ok, missing = quote_in_text(quote, document_text(p))
        if not ok:
            refuse(f"the quote is not in {p.name}: fragment {missing!r} not found. The cell is not verified.")
        return p.name
    docs = cited_documents(product, cid)
    if not docs:
        refuse(f"{product} {cid} cites no document the record can resolve (no accession, no local file), "
               "pass --document <file> with the filing you checked")
    missing_docs, misses = [], []
    for d in docs:
        p = _abs(d["path"])
        if not p.exists():
            if fetch:
                p = fetch_document(d)
            else:
                missing_docs.append(d)
                continue
        ok, missing = quote_in_text(quote, document_text(p))
        if ok:
            return d["label"]
        misses.append(f"{d['label']}: fragment {missing!r} not found")
    if misses:
        refuse("the quote is not in the cited document. " + " | ".join(misses) + ". The cell is not verified.")
    refuse("the cited document is not on this machine: " + ", ".join(d["path"] for d in missing_docs)
           + ". Run again with --fetch (TARK_SEC_CONTACT set) or --document <file>.")
    return ""   # unreachable, refuse raises


# ------------------------------------------------------------- the signature
def verified_row(cell: dict, signer: str, date: str, note: str = "") -> dict:
    """The record after a person verifies it: the same content, signed."""
    stamp = f"{signer}, {date}"
    return {**cell, "status": f"verified - {stamp}" + (f", {note}" if note else ""),
            "verified_by": stamp}


def check_request(product: str, cid: str, signer: str, date: str) -> dict:
    signer = (signer or "").strip()
    if not signer:
        refuse("a signer (name and role) is required")
    if NOT_A_PERSON.search(signer):
        refuse(f"signer {signer!r} names a script, model or agent, verification is human work")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", (date or "").strip()):
        refuse("an ISO date (YYYY-MM-DD) is required")
    if cid not in CELLS:
        refuse(f"unknown cell {cid}")
    try:
        prod = load_product(product)
    except FileNotFoundError:
        refuse(f"unknown product {product}")
    cell = prod["cells"][cid]
    if status_kind(str(cell.get("status", ""))) != "extracted":
        refuse(f"{product} {cid} is {cell.get('status', '')!r}, only an extracted-unverified cell can be verified")
    if not str(cell.get("source") or "").strip() or not str(cell.get("quote") or "").strip():
        refuse(f"{product} {cid} has no source or no verbatim quote to verify against")
    return cell


def apply(product: str, cid: str, signer: str, date: str, note: str = "", dry_run: bool = True,
          document: str | None = None, fetch: bool = False, report: Path | None = None) -> dict:
    cell = check_request(product, cid, signer, date)
    found_in = check_quote(product, cid, cell, document=document, fetch=fetch)
    print(f"quote found in {found_in}")
    row = verified_row(cell, signer.strip(), date.strip(), note.strip())
    if dry_run:
        print("dry run, nothing written. The row would become:")
        print(json.dumps({k: row[k] for k in ("status", "verified_by", "value", "source", "quote")}, indent=2))
        return row
    prod = load_product(product)
    prod["cells"][cid] = row
    (DATA / "products" / f"{product}.json").write_text(json.dumps(prod, indent=2, ensure_ascii=False) + "\n")
    rows = load_evidence(product)
    for r in rows:
        if r["cell_id"] == cid:
            r["status"], r["verified_by"] = row["status"], row["verified_by"]
    with open(DATA / "evidence" / f"{product}_evidence.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=EVIDENCE_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    from corrections_log import add_allow_row
    reason = ALLOW_REASON.format(signer=signer.strip(), date=date.strip(), document=found_in)
    for col in ("status", "verified_by"):
        add_allow_row(product, cid, col, reason, report=report)
    print(f"{product} {cid} verified by {signer.strip()} on {date.strip()}. Run the gate chain before committing.")
    return row


# ---------------------------------------------------------------- the gate
def verified_row_problems(keys: list[str] | None = None, allow: list[dict] | None = None) -> list[str]:
    """Every verified row in the record, checked against the contract this
    tool writes (decision 7.4): status 'verified - <signer>, <date>[, note]',
    verified_by '<signer>, <date>', a human signer, the product JSON in
    agreement with the CSV, and the allowlist rows this tool adds for the
    status and verified_by columns (the marker that a person ran it). A
    signed verified_by on a row that is not verified is a problem too."""
    from corrections_log import allow_rows
    from tark_data import product_keys
    allow = allow if allow is not None else allow_rows()
    problems: list[str] = []
    for key in keys or product_keys():
        prod = load_product(key)
        for r in load_evidence(key):
            st, vb = r["status"], (r.get("verified_by") or "").strip()
            if not st.startswith("verified"):
                if vb:
                    problems.append(f"{key} {r['cell_id']}: verified_by {vb!r} on a row that is not verified")
                continue
            m = re.fullmatch(r"verified - (.+?), (\d{4}-\d{2}-\d{2})(?:, .*)?", st)
            if not m:
                problems.append(f"{key} {r['cell_id']}: status {st!r} is not the form the verification tool writes")
                continue
            signer, date = m.group(1), m.group(2)
            if vb != f"{signer}, {date}":
                problems.append(f"{key} {r['cell_id']}: verified_by {vb!r} does not match the status signature")
            if NOT_A_PERSON.search(signer):
                problems.append(f"{key} {r['cell_id']}: signer {signer!r} is not a person")
            cell = prod["cells"].get(r["cell_id"], {})
            if cell.get("status") != st or (cell.get("verified_by") or "") != vb:
                problems.append(f"{key} {r['cell_id']}: product JSON and evidence CSV disagree on the signature")
            marker = f"verified by {signer} on {date}"
            for col in ("status", "verified_by"):
                if not any(a["product"] == key and a["cell"] == r["cell_id"] and a["column"] == col
                           and a["reason"].startswith(marker) for a in allow):
                    problems.append(f"{key} {r['cell_id']}: no allowlist row for {col} with the reason "
                                    f"{marker!r}, which only the verification tool writes")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("product")
    ap.add_argument("cell")
    ap.add_argument("--signer", default="")
    ap.add_argument("--date", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--document", default=None, help="a local copy of the cited filing, when the record's file is not on this machine")
    ap.add_argument("--fetch", action="store_true", help="download the cited filing from its manifest URL (network, TARK_SEC_CONTACT)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    apply(a.product, a.cell, a.signer, a.date, a.note, a.dry_run, document=a.document, fetch=a.fetch)
    return 0


if __name__ == "__main__":
    sys.exit(main())

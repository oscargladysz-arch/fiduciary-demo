"""
Human verification of one evidence cell
    python src/verify_cell.py <product> <cell> --signer "Name, role" --date YYYY-MM-DD
                              [--note "..."] [--dry-run]

The only path that writes a `verified` status, and only a person runs it:
  - signer and an ISO date are required, a signer that names a script,
    pipeline, model or agent is refused (verification is human work)
  - only a cell at extracted-unverified with a source and a verbatim quote
    can be verified (partial, computed, structured and n/a cannot)
  - the row keeps its value, source, section and quote unchanged: verifying
    signs, it does not edit
  - status becomes "verified - <signer>, <date>" and verified_by
    "<signer>, <date>", in the product JSON and the evidence CSV together,
    and the two columns are allowlisted in the corrections log with the
    signer as the reason (the evidence immutability gate reads it)
  - --dry-run prints the row it would write and writes nothing
No producer, build or test calls this without --dry-run.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

from tark_data import CELLS, DATA, EVIDENCE_COLUMNS, load_evidence, load_product, status_kind

NOT_A_PERSON = re.compile(r"claude|gpt|model|pipeline|agent|script|ingest\.py|bot\b|automation", re.I)


class Refused(SystemExit):
    pass


def refuse(msg: str) -> None:
    print(f"refused: {msg}")
    raise Refused(1)


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


def apply(product: str, cid: str, signer: str, date: str, note: str = "", dry_run: bool = True) -> dict:
    cell = check_request(product, cid, signer, date)
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
    for col in ("status", "verified_by"):
        subprocess.run([sys.executable, str(Path(__file__).with_name("corrections_log.py")), "allow",
                        "--product", product, "--cell", cid, "--column", col,
                        "--reason", f"verified by {signer.strip()} on {date.strip()}"], check=False)
    print(f"{product} {cid} verified by {signer.strip()} on {date.strip()}. Run the gate chain before committing.")
    return row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("product")
    ap.add_argument("cell")
    ap.add_argument("--signer", default="")
    ap.add_argument("--date", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    apply(a.product, a.cell, a.signer, a.date, a.note, a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())

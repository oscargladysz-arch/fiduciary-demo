"""
One-off: remove the unverified argument-timing sentence from cell 5.7
=====================================================================
Round 1 seeded cell 5.7 on all sixteen products with one sentence stating
an argument term that no document in the record supports (round-2 audit,
item 31). This script removes that sentence from the cell value and the
matching snippet from the quote column, in every product JSON and its
evidence CSV row, keeps the status partial and every other field as it is,
and prints the old and the new text per product for the corrections log.

    python src/strip_caselaw_timing.py                        dry run, prints, writes nothing
    python src/strip_caselaw_timing.py --write                writes
    python src/strip_caselaw_timing.py --write --value-only   leaves the quote column alone

The sentence is found by its subject, not by a stored copy of it: the one
sentence of the value that speaks of an argument and a term. The quote
snippet is the quoted string that speaks of an argument. A product whose
5.7 is not partial, or whose value holds no such sentence or more than one,
is left alone and reported. Running it twice changes nothing the second time.

After --write the coordinator logs and allowlists the change (the script
prints the exact commands for the products it changed):
    python src/corrections_log.py write --cause "R2-P1-14: unverified argument-timing sentence removed from cell 5.7"
    python src/corrections_log.py allow --product <key> --cell 5.7 --column value --reason "..."
    python src/corrections_log.py allow --product <key> --cell 5.7 --column quote --reason "..."
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tark_data import DATA, EVIDENCE_COLUMNS, load_evidence, load_product, product_keys, status_kind  # noqa: E402

CELL = "5.7"
# a sentence (from a sentence start to its end mark and the following space)
# that speaks of an argument and of a term
TIMING_SENTENCE_RE = re.compile(r"(?:(?<=[.?!]\s)|^)[^.?!]*\bargument\b[^.?!]*\bterm\b[^.?!]*[.?!]\s?", re.I)
# the quoted snippet, joined with "and", that speaks of an argument
TIMING_QUOTE_RE = re.compile(r'\s+and\s+"[^"]*\bargument\b[^"]*"', re.I)


def strip_value(value: str) -> tuple[str, str | None]:
    """(new value, the removed sentence) or (value, None) when the value
    does not hold exactly one such sentence."""
    hits = list(TIMING_SENTENCE_RE.finditer(value))
    if len(hits) != 1:
        return value, None
    h = hits[0]
    # the match consumes the space after the sentence, so the text before and
    # after it join with the one space that was already there. When the
    # sentence was the last one, the space before it is dropped.
    return (value[:h.start()] + value[h.end():]).rstrip(), h.group(0)


def strip_quote(quote: str) -> tuple[str, str | None]:
    hits = list(TIMING_QUOTE_RE.finditer(quote))
    if len(hits) != 1:
        return quote, None
    h = hits[0]
    return quote[:h.start()] + quote[h.end():], h.group(0)


def run(write: bool, value_only: bool = False) -> list[dict]:
    """Per product: what changes (or would). Prints old and new text."""
    out = []
    for key in product_keys():
        product = load_product(key)
        cell = product["cells"][CELL]
        status = str(cell.get("status", ""))
        if status_kind(status) != "partial":
            print(f"{key:<18} {CELL} is {status_kind(status)}, not partial: left alone")
            continue
        old_value = str(cell.get("value") or "")
        old_quote = str(cell.get("quote") or "")
        new_value, removed = strip_value(old_value)
        if removed is None:
            print(f"{key:<18} {CELL}: no single argument-timing sentence in the value: left alone")
            continue
        new_quote, removed_q = (old_quote, None) if value_only else strip_quote(old_quote)
        rec = {"key": key, "old_value": old_value, "new_value": new_value, "removed_sentence": removed,
               "old_quote": old_quote, "new_quote": new_quote, "removed_quote": removed_q,
               "columns": ["value"] + (["quote"] if removed_q else [])}
        out.append(rec)
        print(f"\n== {key} {CELL} (status stays {status!r})")
        print(f"old value: {old_value}")
        print(f"new value: {new_value}")
        print(f"removed:   {removed.strip()}")
        if removed_q:
            print(f"old quote: {old_quote}")
            print(f"new quote: {new_quote}")
        if not write:
            continue
        cell["value"] = new_value
        if removed_q:
            cell["quote"] = new_quote
        (DATA / "products" / f"{key}.json").write_text(
            json.dumps(product, indent=2, ensure_ascii=False) + "\n")
        rows = load_evidence(key)
        for r in rows:
            if r["cell_id"] == CELL:
                r["value"] = new_value
                if removed_q:
                    r["quote"] = new_quote
        with open(DATA / "evidence" / f"{key}_evidence.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=EVIDENCE_COLUMNS)
            w.writeheader()
            w.writerows(rows)
    if not out:
        print("\nnothing to strip")
    elif not write:
        print(f"\ndry run: {len(out)} product(s) would change. Rerun with --write.")
    else:
        print(f"\nwrote {len(out)} product(s). Now log it and allowlist the rows:")
        print('  python src/corrections_log.py write --cause "R2-P1-14: unverified argument-timing '
              'sentence removed from cell 5.7"')
        for rec in out:
            for col in rec["columns"]:
                print(f"  python src/corrections_log.py allow --product {rec['key']} --cell {CELL} --column {col} "
                      f'--reason "R2-P1-14: unverified argument-timing sentence removed, audit item 31"')
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="write the product and evidence files")
    ap.add_argument("--value-only", action="store_true", help="leave the quote column as it is")
    a = ap.parse_args()
    run(a.write, a.value_only)
    return 0


if __name__ == "__main__":
    sys.exit(main())

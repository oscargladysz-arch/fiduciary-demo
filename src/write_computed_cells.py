"""
Engine-derived cells: one writer, owned cells only
===================================================
Several cells restate the pipeline's own outputs as evidence (status
`computed`). Until now no committed script produced that prose, so it went
stale (cell 5.4 still described the roster of the first build). This module is the
only writer of those cells.

Guard rails:
- OWNED lists the cells this writer may touch. It refuses any target whose
  current status kind is not `computed`, `n/a` or `pending`. T2 evidence is
  never overwritten.
- Each owned cell is a machine sentence built from the artifact it cites,
  plus an optional analyst note carried verbatim from data/notes/<key>.json,
  so judgment written by a person is not lost in regeneration.
- extracted_by names this script and the record as-of date (never the wall
  clock, never a git sha: the freshness gate must reproduce the file
  byte-for-byte on any commit).
- Idempotent: a second run with the same inputs changes nothing.
- Writes the product JSON and the evidence CSV together.

Run: python src/write_computed_cells.py [--only 5.4,2.9] [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from tark_data import (CELLS, DATA, EVIDENCE_COLUMNS, load_evidence,
                       load_product, product_keys, record_as_of, status_kind)

WRITABLE_KINDS = ("computed", "n/a", "pending")


def analyst_note(key: str, cid: str) -> str:
    p = DATA / "notes" / f"{key}.json"
    if not p.exists():
        return ""
    return str(json.loads(p.read_text()).get("cells", {}).get(cid, "")).strip()


def _cohort_for(key: str) -> tuple[str | None, dict | None]:
    fp = DATA / "facts" / f"{key}.json"
    if not fp.exists():
        return None, None
    cid = json.loads(fp.read_text()).get("cohort_id")
    cp = DATA / "cohorts" / f"{cid}.json" if cid else None
    if not cp or not cp.exists():
        return cid, None
    return cid, json.loads(cp.read_text())


# --------------------------------------------------------------- producers
def cell_5_4(key: str) -> dict | None:
    """Peer universe and returns, from the cohort artifact."""
    cid, co = _cohort_for(key)
    if not co:
        return None
    members = list(co["members"].keys())
    comp = co.get("composite") or {}
    if comp.get("refused"):
        comp_txt = f"Composite REFUSED: {comp.get('reason', '').rstrip('.')}."
    else:
        rows = comp.get("rows", [])
        years = ", ".join(f"{r['year']} (n={r['n']})" for r in rows)
        comp_txt = ("Equal-weight annual composite on printed fiscal-year returns "
                    "for years with 2 or more reporting members: "
                    + (years if years else "none, no year has 2 reporting members")
                    + ".")
    wrappers = sorted({m["wrapper_type"] for m in co["members"].values()})
    n_cav = len(co.get("caveats") or [])
    text = (f"Peer cohort {cid} (n={co['n']}: {', '.join(members)}). {comp_txt} "
            f"Wrapper types in the cohort: {', '.join(wrappers)}. "
            f"Cross-wrapper differences are disclosed in the cohort caveat block "
            f"({n_cav} caveat{'s' if n_cav != 1 else ''}). Membership rationales are "
            f"in data/facts, exclusions in data/roster_decisions.md.")
    note = analyst_note(key, "5.4")
    if note:
        text += f" Analyst note: {note}"
    return {"value": text, "source": f"data/cohorts/{cid}.json",
            "section": "members, composite and caveats blocks", "quote": ""}


OWNED = {
    "5.4": cell_5_4,
}


# ------------------------------------------------------------------ writer
def write_cell(key: str, cid: str, new: dict, as_of: str,
               product: dict, ev_rows: list[dict]) -> bool:
    cell = product["cells"][cid]
    kind = status_kind(str(cell.get("status", "pending")))
    if kind not in WRITABLE_KINDS:
        raise SystemExit(f"refusing to overwrite {key} {cid}: status kind "
                         f"'{kind}' is evidence, not an engine output")
    record = {
        "element": CELLS[cid],
        "value": new["value"],
        "status": "computed",
        "source": new["source"],
        "section": new.get("section", ""),
        "quote": new.get("quote", ""),
        "extracted_by": f"src/write_computed_cells.py (as-of {as_of})",
        "verified_by": "",
    }
    changed = any(cell.get(k) != v for k, v in record.items())
    product["cells"][cid] = record
    for r in ev_rows:
        if r["cell_id"] == cid:
            row = {"cell_id": cid, "element": CELLS[cid], "value": new["value"],
                   "source_doc": new["source"],
                   "source_section": new.get("section", ""),
                   "quote": new.get("quote", ""), "local_file": "",
                   "date_pulled": as_of,
                   "extracted_by": record["extracted_by"], "verified_by": "",
                   "status": "computed"}
            changed = changed or any(r.get(k) != v for k, v in row.items())
            r.update(row)
    return changed


def run(only: set[str] | None = None, dry_run: bool = False) -> int:
    as_of = record_as_of()
    total = 0
    for key in product_keys():
        product = load_product(key)
        ev_rows = load_evidence(key)
        touched = []
        for cid, producer in OWNED.items():
            if only and cid not in only:
                continue
            new = producer(key)
            if new is None:
                continue
            if write_cell(key, cid, new, as_of, product, ev_rows):
                touched.append(cid)
        if touched and not dry_run:
            (DATA / "products" / f"{key}.json").write_text(
                json.dumps(product, indent=2, ensure_ascii=False) + "\n")
            with open(DATA / "evidence" / f"{key}_evidence.csv", "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=EVIDENCE_COLUMNS)
                w.writeheader()
                w.writerows(ev_rows)
        total += len(touched)
        print(f"{key:<18} {'would write' if dry_run else 'wrote'} "
              f"{', '.join(touched) if touched else 'nothing (unchanged)'}")
    return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated cell ids")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    only = {c for c in a.only.split(",") if c}
    n = run(only or None, a.dry_run)
    print(f"{n} owned cell(s) {'would change' if a.dry_run else 'changed'}")


if __name__ == "__main__":
    main()

"""
Evidence immutability gate
===========================
T2 evidence (rows at status extracted, partial, fetched, structured, and
any verified row) must not change as a side effect of regeneration. This
gate diffs every such row of every data/evidence/*.csv against the base ref
(default origin/main) across all columns. Any difference must be listed in
the evidence allowlist block of docs/crosscheck_report.md with a reason
(python src/corrections_log.py allow ...).

Run: python src/test_evidence_immutable.py   (exit 0 = immutable or allowlisted)
Env: TARK_BASE_REF overrides the base ref.
"""
from __future__ import annotations

import csv
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from corrections_log import allow_rows, git_show  # noqa: E402
from tark_data import EVIDENCE_COLUMNS, product_keys, status_kind  # noqa: E402

PROTECTED = ("extracted", "partial", "fetched", "structured", "verified")


def rows_of(text: str) -> dict[str, dict]:
    return {r["cell_id"]: r for r in csv.DictReader(io.StringIO(text))}


def main() -> int:
    base = os.environ.get("TARK_BASE_REF", "origin/main")
    allowed = {(r["product"], r["cell"], r["column"]) for r in allow_rows()}
    covered: dict[tuple, int] = {}

    def is_allowed(key: str, cid: str, col: str) -> bool:
        # an exact row, a product-wide row, or a record-wide row for one
        # column: every one carries a reason in the report (P0-6, P2-10)
        for probe in ((key, cid, col), (key, "*", col), ("*", "*", col)):
            if probe in allowed:
                covered[probe] = covered.get(probe, 0) + 1
                return True
        return False
    fails = 0
    checked = 0
    for key in product_keys():
        rel = f"data/evidence/{key}_evidence.csv"
        base_text = git_show(base, rel)
        if base_text is None:
            print(f"[ok]   {key}: new product (no base row set to protect)")
            continue
        head_text = (Path(__file__).resolve().parents[1] / rel).read_text()
        b, h = rows_of(base_text), rows_of(head_text)
        for cid, brow in b.items():
            if status_kind(brow["status"]) not in PROTECTED:
                continue
            checked += 1
            hrow = h.get(cid)
            if hrow is None:
                print(f"[FAIL] {key} {cid}: protected row removed")
                fails += 1
                continue
            for col in EVIDENCE_COLUMNS:
                if brow.get(col, "") != hrow.get(col, ""):
                    if is_allowed(key, cid, col):
                        continue
                    print(f"[FAIL] {key} {cid} {col}: T2 evidence changed without "
                          f"an allowlist entry: {brow.get(col,'')[:60]!r} -> "
                          f"{hrow.get(col,'')[:60]!r}")
                    fails += 1
    for probe, n in sorted(covered.items()):
        if "*" in probe:
            print(f"[ok]   allowlist {probe[0]} {probe[1]} {probe[2]}: covered {n} changed cells")
    print(f"\n{fails} violation(s)." if fails else
          f"\nEvidence immutable: {checked} protected rows unchanged or allowlisted vs {base}.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

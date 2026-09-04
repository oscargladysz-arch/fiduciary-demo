"""
Invariants of the record and its surfaces (grows with every phase)
==================================================================
Each check is a property the audit found violated or a rule the brief makes
non-negotiable. Run: python src/test_invariants.py   (exit 0 = all hold)
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tark_data import (BASE, DATA, coverage_summary, coverage_totals,  # noqa: E402
                       load_evidence, product_keys)

FAILS: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}{(' : ' + extra) if extra and not cond else ''}")
    if not cond:
        FAILS.append(name)


# 1. verified is human-only: this remediation never sets it
verified_rows = 0
signed = 0
for key in product_keys():
    for r in load_evidence(key):
        if r["status"].startswith("verified"):
            verified_rows += 1
        if r["verified_by"].strip():
            signed += 1
check("no cell is verified and no verified_by is signed in this pull request",
      verified_rows == 0 and signed == 0, f"verified={verified_rows} signed={signed}")

# 2. one coverage formula: build_site and app.py call tark_data.coverage_summary
bs = (BASE / "src" / "build_site.py").read_text()
ap = (BASE / "app.py").read_text()
check("build_site.evidence_counts delegates to coverage_summary",
      "return coverage_summary(key)" in bs)
check("app.py uses coverage_summary and has no local coverage formula",
      "coverage_summary(" in ap and "def coverage_pct" not in ap)
tot = coverage_totals()["counts"]
check("record totals per kind (recomputed): extracted 406, n/a 237, computed 145, "
      "partial 59, fetched 16, structured 1, verified 0, pending 0",
      (tot["extracted"], tot["na"], tot["computed"], tot["partial"], tot["fetched"],
       tot["structured"], tot["verified"], tot["pending"]) == (406, 237, 145, 59, 16, 1, 0, 0),
      str(tot))
c = coverage_summary("cion_ares")
check("cion_ares: structured counts as resolved (structured 1, pending 0)",
      c["structured"] == 1 and c["pending"] == 0)

# 3. no product-count "six" copy on any surface or in the record
SIX = re.compile(r"six (real )?products|six-product|six rows|six hundred|six wrappers", re.I)
hits = []
for pattern in ("site/js/*.js", "site/index.html", "app.py", "data/products/*.json",
                "data/evidence/*.csv", "data/analytics/*.json", "data/roster_decisions.md"):
    for f in BASE.glob(pattern):
        for i, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
            if SIX.search(line):
                hits.append(f"{f.relative_to(BASE)}:{i}")
check("no product-count 'six' string in site/, app.py or data/", not hits, "; ".join(hits[:5]))

# 4. every non-raw data/ path a cell cites exists (raw paths are checked
#    against the manifest by the validator, as warnings until P2-10)
from tark_data import data_paths_in, load_product  # noqa: E402
dangling = []
for key in product_keys():
    for cid, cell in load_product(key)["cells"].items():
        for field in ("value", "source", "section", "quote"):
            for pth in data_paths_in(str(cell.get(field) or "")):
                if not pth.startswith("data/raw/") and not (BASE / pth).exists():
                    dangling.append(f"{key}:{cid}:{pth}")
check("every non-raw data/ path cited by a cell exists", not dangling, "; ".join(dangling[:5]))

# 5. the frozen taxonomy file is gone (the build computes it)
check("data/analytics/taxonomy.json no longer exists",
      not (DATA / "analytics" / "taxonomy.json").exists())

# data/roster_decisions.md claims to be validator-enforced: every product key
# in the record must be named in it
from tark_data import product_keys as _product_keys  # noqa: E402
_roster_md = (BASE / "data" / "roster_decisions.md").read_text()
_missing = [k for k in _product_keys() if k not in _roster_md]
check("data/roster_decisions.md names every product key in the record",
      not _missing, ", ".join(_missing))

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll invariants hold.")
sys.exit(1 if FAILS else 0)

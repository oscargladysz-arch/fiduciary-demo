"""
Run the M3 benchmark engine for every profiled product.
    python src/run_benchmark.py
Writes data/benchmarks/<product>_selection.json and prints the decisions.
"""
import json
from pathlib import Path

from tark_data import DATA
from tark_benchmark import PRODUCT_PROFILES, run_selection

outdir = DATA / "benchmarks"
outdir.mkdir(exist_ok=True)

for key in PRODUCT_PROFILES:
    sel = run_selection(key)
    (outdir / f"{key}_selection.json").write_text(json.dumps(sel, indent=2))
    print(f"\n=== {key} ({sel['strategy']}) ===")
    if sel["primary"]:
        p = sel["primary"]
        print(f"  PRIMARY   {p['candidate']}  [{p['score']}/12]")
        if p.get("comparison"):
            c = p["comparison"]
            print(f"            window {c['window']}: fund {c['fund_growth_x']}x "
                  f"({c['fund_ann_pct']}%/yr) vs index {c['index_growth_x']}x "
                  f"({c['index_ann_pct']}%/yr) | KS-PME {c['ks_pme']} | "
                  f"Direct Alpha {c['direct_alpha_pct']}%/yr")
    if sel["secondary"]:
        s = sel["secondary"]
        print(f"  SECONDARY {s['candidate']}  [{s['score']}/12]")
        if s.get("comparison"):
            c = s["comparison"]
            print(f"            KS-PME {c['ks_pme']} | Direct Alpha {c['direct_alpha_pct']}%/yr")
    for r in sel["rejected"]:
        print(f"  rejected  {r['candidate']}  [{r['score']}/12] - {r['rejection']}")
    if sel["escalation"]:
        print(f"  ESCALATION: {sel['escalation']}")
print("\nwrote data/benchmarks/*.json")

"""
Run the benchmark engine (rubric v2) for every product with a return input.
    python src/run_benchmark.py
Writes data/benchmarks/<product>_selection.json and prints the decisions.
Profiles are assembled at import from data/registry.json and
data/benchmarks/profiles_input.json (facts live in the data layer, not in
engine code).
"""
import json

from tark_benchmark import PRODUCT_PROFILES, run_selection
from tark_data import DATA

outdir = DATA / "benchmarks"
outdir.mkdir(exist_ok=True)

for key in PRODUCT_PROFILES:
    sel = run_selection(key)
    (outdir / f"{key}_selection.json").write_text(json.dumps(sel, indent=2))
    print(f"\n=== {key} ({sel['strategy']}) max attainable {sel['max_attainable']}/12 ===")
    if sel["primary"]:
        p = sel["primary"]
        print(f"  PRIMARY   {p['candidate']}  [{p['score']}/12]")
        if p.get("comparison"):
            c = p["comparison"]
            print(f"            window {c['window']}: fund {c['fund_growth_x']}x "
                  f"({c['fund_ann_pct']}%/yr) vs index {c['index_growth_x']}x "
                  f"({c['index_ann_pct']}%/yr), KS-PME {c['ks_pme']}, "
                  f"Direct Alpha {c['direct_alpha_pct']}%/yr")
    if sel["secondary"]:
        s = sel["secondary"]
        print(f"  SECONDARY {s['candidate']}  [{s['score']}/12]")
    elif sel["primary"]:
        print(f"  SECONDARY {sel['secondary_note']}")
    if sel["escalation"]:
        print(f"  ESCALATION {sel['escalation'][:90]}")
    for r in sel["rejected"]:
        print(f"  rejected  {r['id']:16s} {r['score']:2d}/12  {r['rejection'][:80]}")

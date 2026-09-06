"""
Run the benchmark engine (architecture v3) for every product.
    python src/run_benchmark.py
Writes data/benchmarks/<product>_selection.json and prints the decisions:
Slot K (meaningful benchmark), the reference comparison when Slot K carries
no number, Slot G (peer comparison) and every rejection with its reason.
Profiles are assembled at import from data/registry.json, return inputs
included (facts live in the data layer, not in engine code).
"""
import json

from tark_benchmark import PRODUCT_PROFILES, run_selection
from tark_data import DATA

outdir = DATA / "benchmarks"
outdir.mkdir(exist_ok=True)


def _stat(c: dict) -> str:
    if c.get("kind") == "series":
        return f"KS-PME {c['ks_pme']}, Direct Alpha {c['direct_alpha_pct']}%/yr"
    return f"relative wealth ratio {c['relative_wealth_ratio']}, excess return {c['excess_return_pct']}%/yr"


for key in PRODUCT_PROFILES:
    sel = run_selection(key)
    (outdir / f"{key}_selection.json").write_text(json.dumps(sel, indent=2))
    sk = sel["slot_k"]
    print(f"\n=== {key} ({sel['strategy']}) max attainable {sk['max_attainable']}/12, basis: {sel['basis']['label']} ===")
    if sk["selected"]:
        p = sk["selected"]
        print(f"  SLOT K    {p['candidate']}  [{p['score']}/12]" + ("" if p["held"] else "  (cited, not held)"))
        c = p.get("comparison")
        if c:
            print(f"            window {c['window']}: fund {c['fund_growth_x']}x ({c['fund_ann_pct']}%/yr) vs "
                  f"comparator {c['index_growth_x']}x ({c['index_ann_pct']}%/yr), {_stat(c)}")
        elif p.get("comparison_note"):
            print(f"            no comparison: {p['comparison_note'][:90]}")
        if sk["ties"]:
            print(f"            tied: {', '.join(sk['ties'])}")
    if sk["escalation"]:
        print(f"  ESCALATION {sk['escalation'][:90]}")
    ref = sel.get("reference_comparison")
    if ref:
        print(f"  REFERENCE {ref['candidate']}  {_stat(ref['comparison'])} over {ref['comparison']['window']}")
    g = (sel.get("slot_g") or {}).get("composite") or {}
    if g:
        print(f"  SLOT G    {'computed ' + _stat(g) + ' over ' + g['window'] + f' (n={g[chr(110)]})' if g['status'] == 'computed' else 'refused: ' + g['reason'][:80]}")
    for d in sel.get("declared") or []:
        print(f"  lane A    {d['type_label']:<24} {d['name']:<36} {d['status'][:60]}")
    for r in sel["rejected"]:
        print(f"  rejected  {r['id']:16s} {r['score']:2d}/12  {r['rejection'][:80]}")

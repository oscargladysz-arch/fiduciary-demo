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

from tark_benchmark import PRODUCT_PROFILES, RUBRIC_MAX, run_selection, x_of_n
from tark_data import DATA

outdir = DATA / "benchmarks"
outdir.mkdir(exist_ok=True)
history = outdir / "history"


def keep_history(key: str, sel: dict) -> None:
    """The selection lock's history (R3-P2-19): a dated copy is kept the
    first time a record hash appears, named by the recorded date and the
    first eight characters of the hash, so a re-record on the same date
    never overwrites a prior record."""
    h = sel["record_hash"]
    folder = history / key
    folder.mkdir(parents=True, exist_ok=True)
    if any(json.loads(f.read_text()).get("record_hash") == h for f in folder.glob("*.json")):
        return
    (folder / f"{sel['recorded_at'][:10]}_{h[:8]}.json").write_text(json.dumps(sel, indent=2))


def _stat(c: dict) -> str:
    if c.get("kind") == "series":
        return f"KS-PME {c['ks_pme']}, Direct Alpha {c['direct_alpha_pct']}%/yr"
    return f"relative wealth ratio {c['relative_wealth_ratio']}, excess return {c['excess_return_pct']}%/yr"


for key in PRODUCT_PROFILES:
    sel = run_selection(key)
    (outdir / f"{key}_selection.json").write_text(json.dumps(sel, indent=2))
    keep_history(key, sel)
    sk = sel["slot_k"]
    print(f"\n=== {key} ({sel['strategy']}) max attainable {sk['max_attainable']} of {RUBRIC_MAX}, "
          f"basis: {sel['basis']['label']}, record {sel['record_hash'][:8]} ===")
    if sk["selected"]:
        p = sk["selected"]
        print(f"  SLOT K    {p['candidate']}  [{x_of_n(p['score'], RUBRIC_MAX)}]" + ("" if p["held"] else "  (cited, not held)"))
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
        print(f"  rejected  {r['id']:16s} {x_of_n(r['score'], RUBRIC_MAX):>8s}  {r['rejection'][:80]}")

"""
Unit tests for the M3 benchmark engine.
Run: python src/test_benchmark.py   (exit 0 = all pass)
"""
import sys
from pathlib import Path

from tark_benchmark import (MIN_PRIMARY_SCORE, PRODUCT_PROFILES, STRATEGY_MENU,
                            run_selection, score_candidate)

FAILS = []


def check_true(name: str, cond: bool):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        FAILS.append(name)


# --- rubric mechanics on synthetic candidates ---
prof = {"strategy": "x"}
perfect = {"id": "p", "name": "perfect", "lane": "B", "series": "spy",
           "provider": "indep", "independent": True, "data": "daily",
           "strategy_match": 3, "match_note": "exact"}
s = score_candidate(prof, perfect)
# strategy 3 + risk 1 (daily proxy) + invest 2 + data 2 + indep 2 = 10
check_true("perfect candidate arithmetic = 10", s["score"] == 10)

affiliated = dict(perfect, id="a", independent=False,
                  provider="the fund's own adviser")
sa = score_candidate(prof, affiliated)
check_true("affiliated provider loses exactly the 2 independence points",
           s["score"] - sa["score"] == 2)
check_true("independence zero is reasoned in the log",
           any("manufacturer-owned" in r for r in sa["reasons"]))

paid = dict(perfect, id="q", series=None, data="quarterly-paid")
sq = score_candidate(prof, paid)
check_true("unlicensed paid index cannot outscore computable proxy",
           sq["score"] < s["score"])
check_true("paid-data rejection reason names the missing license",
           any("licensed data not held" in r for r in sq["reasons"]))

# --- selection behavior on real profiles ---
sel_c = run_selection("cliffwater_cclfx")
check_true("CCLFX selects a primary", sel_c["primary"] is not None)
check_true("CCLFX primary is independent BKLN lane, not adviser-owned CDLI",
           sel_c["primary"]["id"] in ("bkln", "pme_bkln"))
check_true("CDLI appears in rejected with independence reasoning",
           any(r["id"] == "cdli" and any("manufacturer-owned" in x for x in r["reasons"])
               for r in sel_c["rejected"]))
check_true("CCLFX primary carries computed comparison stats",
           sel_c["primary"]["comparison"] is not None
           and sel_c["primary"]["comparison"]["ks_pme"] > 0)

sel_d = run_selection("dxyz")
check_true("DXYZ returns NO primary (the fail case)", sel_d["primary"] is None)
check_true("DXYZ escalates with a reasoned message",
           sel_d["escalation"] is not None and "NO MEANINGFUL BENCHMARK"
           in sel_d["escalation"])
check_true("DXYZ rejection log gives the premium-decoupling reason on every row",
           all("premium" in r["rejection"] for r in sel_d["rejected"]))

# --- rejection-log completeness: every candidate is accounted for ---
for key in PRODUCT_PROFILES:
    sel = run_selection(key)
    menu = STRATEGY_MENU[PRODUCT_PROFILES[key]["strategy"]]
    accounted = len(sel["rejected"]) + (1 if sel["primary"] else 0) \
        + (1 if sel["secondary"] else 0)
    check_true(f"{key}: every candidate selected or rejected-with-reason "
               f"({accounted}/{len(menu)})", accounted == len(menu))
    check_true(f"{key}: every rejection carries a reason string",
               all(r.get("rejection") for r in sel["rejected"]))

# --- rejection-reason TRUTHFULNESS: no false statements in the audit log ---
for key in PRODUCT_PROFILES:
    sel = run_selection(key)
    for r in sel["rejected"]:
        if r["score"] >= MIN_PRIMARY_SCORE and not PRODUCT_PROFILES[key].get("price_nav_decoupled"):
            check_true(f"{key}/{r['id']}: above-threshold rejection says 'outranked', "
                       f"never 'below threshold'",
                       "outranked" in r["rejection"] and "below" not in r["rejection"])
        if r["score"] < MIN_PRIMARY_SCORE and not PRODUCT_PROFILES[key].get("price_nav_decoupled"):
            check_true(f"{key}/{r['id']}: below-threshold rejection states the threshold",
                       "below primary threshold" in r["rejection"])

check_true("threshold constant sane", 0 < MIN_PRIMARY_SCORE <= 12)

# ---- P1-1: every comparison window lives inside proxy coverage and one
# anchor serves the displayed growth and the PME (two-point identity)
import json  # noqa: E402
from tark_analytics import _level_on, effective_window, cumulative_growth  # noqa: E402
from tark_benchmark import (STRATEGY_MENU, WindowNotComputable,  # noqa: E402
                            comparison_stats, fiscal_year_bounds)
from tark_data import load_series  # noqa: E402
try:
    _level_on([("2020-01-02", 1.0)], "2019-12-31")
    raised = False
except ValueError:
    raised = True
check_true("_level_on refuses a date before the series starts", raised)
e0, e1, note = effective_window("2016-03-31", "2026-03-31",
                                [("2018-07-18", 1.0), ("2026-07-17", 2.0)])
check_true("effective_window clips to the proxy start and says so",
           (e0, e1) == ("2018-07-18", "2026-03-31")
           and note == "clipped: proxy series begins 2018-07-18")
check_true("fiscal_year_bounds: consecutive whole years ending on the window end",
           fiscal_year_bounds(("2016-03-31", "2019-03-31"), 3)
           == [("2016-03-31", "2017-03-31"), ("2017-03-31", "2018-03-31"),
               ("2018-03-31", "2019-03-31")])
try:
    comparison_stats({"aatr": 0.10, "aatr_years": 3.0,
                      "fy_window": ("2017-01-01", "2019-12-31")}, {"series": "vnq"})
    single_ok = False
except WindowNotComputable as e:
    single_ok = "proxy series begins 2018-07-18" in str(e)
check_true("a single disclosed figure outside proxy coverage is not computable, "
           "with the reason", single_ok)

series_of = {c["id"]: c["series"] for menu in STRATEGY_MENU.values() for c in menu}
bench_dir = Path(__file__).resolve().parents[1] / "data" / "benchmarks"
outside, broken_identity = [], []
for sp in sorted(bench_dir.glob("*_selection.json")):
    sel = json.loads(sp.read_text())
    for slot in ("primary", "secondary"):
        s_ = sel.get(slot)
        comp = (s_ or {}).get("comparison")
        if not comp:
            continue
        ser = load_series(series_of[s_["id"]], "adj_close")
        d0, d1 = comp["window"].split(" to ")
        if not (ser[0][0] <= d0 < d1 <= ser[-1][0]):
            outside.append(f"{sp.stem}/{slot}: {comp['window']} vs {ser[0][0]}..{ser[-1][0]}")
        if abs(comp["ks_pme"] - comp["fund_growth_x"] / comp["index_growth_x"]) > 2e-3:
            broken_identity.append(f"{sp.stem}/{slot}: {comp['ks_pme']} vs "
                                   f"{comp['fund_growth_x']}/{comp['index_growth_x']}")
check_true("every committed comparison window lies inside its proxy's coverage"
           + (": " + "; ".join(outside) if outside else ""), not outside)
check_true("two-point identity: KS-PME equals fund growth over index growth on "
           "every committed comparison" + (": " + "; ".join(broken_identity)
                                            if broken_identity else ""),
           not broken_identity)
# ---- P1-2: annualization is the day count of the effective window
from tark_analytics import year_frac  # noqa: E402
DISCLOSED_ANNUALIZED = {"kkr_kpec": 12.94, "stepstone_spm": 12.92}   # cell 1.2 figures
ann_bad = []
for sp in sorted(bench_dir.glob("*_selection.json")):
    sel = json.loads(sp.read_text())
    for slot in ("primary", "secondary"):
        s_ = sel.get(slot)
        comp = (s_ or {}).get("comparison")
        if not comp:
            continue
        d0, d1 = comp["window"].split(" to ")
        if sp.stem.replace("_selection", "") in DISCLOSED_ANNUALIZED:
            want = DISCLOSED_ANNUALIZED[sp.stem.replace("_selection", "")]
            if abs(comp["fund_ann_pct"] - want) > 0.005:
                ann_bad.append(f"{sp.stem}/{slot}: disclosed {want} printed as {comp['fund_ann_pct']}")
            continue
        yf = year_frac(d0, d1)
        for side in ("fund", "index"):
            want = (comp[f"{side}_growth_x"] ** (1 / yf) - 1) * 100
            if abs(comp[f"{side}_ann_pct"] - want) > 0.02:
                ann_bad.append(f"{sp.stem}/{slot}/{side}: {comp[f'{side}_ann_pct']} vs day-count {want:.2f}")
check_true("annualized figures are the day count of the effective window "
           "(disclosed figures print as disclosed)" + (": " + "; ".join(ann_bad) if ann_bad else ""),
           not ann_bad)
def _ann(key):
    return json.loads((bench_dir / f"{key}_selection.json").read_text())["primary"]["comparison"]["fund_ann_pct"]
# hand values on the effective windows: cclfx 2019-06-05 to 2026-07-17
# (7.116 years), pflex 2018-07-18 to 2026-07-17 (7.997), arkvx 2022-08-31 to
# 2026-07-17 (3.877)
check_true("cclfx annualized 7.89% by day count", abs(_ann("cliffwater_cclfx") - 7.89) < 0.005)
check_true("pflex annualized 5.74% by day count", abs(_ann("pflex") - 5.74) < 0.005)
check_true("arkvx annualized 30.12% by day count", abs(_ann("arkvx") - 30.12) < 0.005)

amg = json.loads((bench_dir / "amg_pantheon_selection.json").read_text())
comp = amg["primary"]["comparison"]
psp = load_series("psp", "adj_close")
fy = json.loads((bench_dir / "profiles_input.json").read_text())["amg_pantheon"]["profile"]["fy_returns"]
hand_fund = cumulative_growth(fy[3:])        # FY2020 to FY2026, seven whole years
hand_index = _level_on(psp, "2026-03-31") / _level_on(psp, "2019-03-31")
check_true("amg_pantheon: window clipped to the seven whole fiscal years inside PSP coverage",
           comp["window"] == "2019-03-31 to 2026-03-31"
           and comp["window_note"].startswith("clipped: proxy series begins 2018-07-18"))
check_true("amg_pantheon: fund growth is the hand product of FY2020 to FY2026 (2.3970)",
           abs(comp["fund_growth_x"] - hand_fund) < 1e-3 and abs(hand_fund - 2.397042) < 1e-5)
check_true("amg_pantheon: KS-PME equals the hand ratio on the clipped window",
           abs(comp["ks_pme"] - hand_fund / hand_index) < 1e-3)

# ---- v1 snapshot is frozen history: every byte pinned by its manifest
import hashlib  # noqa: E402
SNAP = Path(__file__).resolve().parents[1] / "data" / "benchmarks" / "v1_snapshot"
manifest = dict(reversed(line.split()) for line in
                (SNAP / "MANIFEST.sha256").read_text().splitlines() if line.strip())
snap_files = sorted(f.name for f in SNAP.glob("*.json"))
# 15 selections (jll_ipt had no computable v1 selection, see P1-13) plus
# profiles_input.json
check_true("v1 snapshot: manifest lists every json file and nothing else",
           sorted(manifest) == snap_files and len(snap_files) == 16)
check_true("v1 snapshot: every file matches its recorded sha256",
           all(hashlib.sha256((SNAP / n).read_bytes()).hexdigest() == h
               for n, h in manifest.items()))

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll benchmark engine tests pass.")
sys.exit(1 if FAILS else 0)

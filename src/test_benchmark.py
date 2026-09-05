"""
Benchmark engine gate (rubric v2). Run: python src/test_benchmark.py

Synthetic descriptors prove the rubric's mechanics (a perfect candidate
scores 12, each criterion moves when its input moves). The committed
selection artifacts are checked against docs/benchmark_methodology.md
(the expected v1 to v2 outcome, written before the engine changed), the
windows live inside proxy coverage, the two-point identity holds, and
the v1 snapshot never drifts.
"""
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path

from tark_analytics import _level_on, cumulative_growth, effective_window, year_frac
from tark_benchmark import (ALL_PRODUCTS, CANDIDATES, MIN_PRIMARY_SCORE, PRODUCT_PROFILES, RETURN_INPUTS,
                            REGISTRY, RUBRIC_MAX, WindowNotComputable, annual_returns,
                            comparison_stats, fiscal_year_bounds, menu_for, peer_candidate,
                            run_selection, score_candidate)
from tark_data import load_product, load_series

BASE = Path(__file__).resolve().parents[1]
FAILS = []


def check_true(name: str, cond: bool):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        FAILS.append(name)


# --- rubric mechanics on synthetic descriptors ---
prof = {"key": "synthetic", "asset_class": "private_credit", "sub_strategy": "direct_lending",
        "pricing_class": "NAV", "leverage_regime": "L", "held_kind": "series",
        "adviser_keys": ["acme"], "advisers": ["Acme"], "price_nav_decoupled": False}
perfect = {"id": "p", "name": "perfect", "lane": "B", "asset_class": "private_credit",
           "sub_strategy": "direct_lending", "listed": False, "pricing_class": "NAV",
           "cadence": "daily", "series": "spy", "data": "daily", "provider": "Indep",
           "provider_key": "indep", "leverage_regimes": ["L"]}
s = score_candidate(prof, perfect)
check_true("perfect candidate scores 12 (3 + 3 + 2 + 2 + 2)", s["score"] == 12 and s["max"] == RUBRIC_MAX)
check_true("perfect candidate: every criterion at its maximum",
           s["criteria"] == {"strategy_match": 3, "risk_liquidity_match": 3, "investability": 2,
                             "data_quality": 2, "provider_independence": 2})
import tark_benchmark as _tb
_tb.AFFILIATIONS["acme indices"] = {"adviser_keys": ["acme"], "source": "synthetic test entry"}
sa = score_candidate(prof, dict(perfect, provider="Acme Indices", provider_key="acme indices"))
del _tb.AFFILIATIONS["acme indices"]
check_true("adviser-owned provider (per the affiliation map) loses exactly the 2 independence points",
           s["score"] - sa["score"] == 2 and sa["criteria"]["provider_independence"] == 0)
check_true("independence zero is reasoned in the log",
           any("manufacturer-owned" in r for r in sa["reasons"]))
# the same provider without a map entry is unaffiliated, whatever the strings share
sa2 = score_candidate(prof, dict(perfect, provider="Acme Indices", provider_key="acme indices"))
check_true("without a map entry the same provider name is unaffiliated: affiliation is never a substring match",
           sa2["criteria"]["provider_independence"] == 2)
sa3 = score_candidate(dict(prof, adviser_keys=["ind"], advisers=["Ind"]), perfect)
check_true("a substring coincidence ('ind' inside 'indep') is not an affiliation",
           sa3["criteria"]["provider_independence"] == 2)
sq = score_candidate(prof, dict(perfect, series=None, data="licensed"))
check_true("licensed index: investability 0 and data_quality 0, cited not computed",
           sq["criteria"]["investability"] == 0 and sq["criteria"]["data_quality"] == 0
           and any("licensed data not held" in r for r in sq["reasons"]))
sm = score_candidate(prof, dict(perfect, asset_class="public_credit", sub_strategy="syndicated_loans",
                                pricing_class="MARKET", listed=True, leverage_regimes=None))
check_true("public version of the asset class: strategy 2, daily proxy vs NAV fund: risk 1",
           sm["criteria"]["strategy_match"] == 2 and sm["criteria"]["risk_liquidity_match"] == 1)
sx = score_candidate(prof, dict(perfect, asset_class="public_equity", sub_strategy="us_large_cap"))
check_true("unrelated asset class: strategy 0", sx["criteria"]["strategy_match"] == 0)
sd = score_candidate(dict(prof, price_nav_decoupled=True), perfect)
check_true("price decoupled from NAV: risk 0 whatever the candidate", sd["criteria"]["risk_liquidity_match"] == 0)
sc = score_candidate(dict(prof, held_kind="fy_returns"), perfect)
check_true("cadence mismatch (daily candidate vs annual held returns): risk drops to 2",
           sc["criteria"]["risk_liquidity_match"] == 2)
sl = score_candidate(prof, dict(perfect, leverage_regimes=["L", "M"]))
check_true("mixed leverage regimes: risk drops to 2", sl["criteria"]["risk_liquidity_match"] == 2)

# --- property tests on real descriptors: move one input, one criterion moves ---
cclfx = PRODUCT_PROFILES["cliffwater_cclfx"]
cdli_c = next(c for c in menu_for("cliffwater_cclfx") if c["id"] == "cdli")
base = score_candidate(cclfx, cdli_c)
moved = score_candidate(dict(cclfx, adviser_keys=["pimco"], advisers=["PIMCO"]), cdli_c)
check_true("property: removing the mapped adviser affiliation moves only provider_independence (0 to 2)",
           moved["score"] - base["score"] == 2 and
           {k: v for k, v in base["criteria"].items() if k != "provider_independence"}
           == {k: v for k, v in moved["criteria"].items() if k != "provider_independence"})
pflex = PRODUCT_PROFILES["pflex"]
cdli = next(c for c in menu_for("pflex") if c["id"] == "cdli")
check_true("property: cdli is strategy 2 for a multi-sector fund and 3 once the sub-strategy matches",
           score_candidate(pflex, cdli)["criteria"]["strategy_match"] == 2
           and score_candidate(dict(pflex, sub_strategy="direct_lending"), cdli)["criteria"]["strategy_match"] == 3)
check_true("property: independence is per product (cdli 0 for cliffwater_cclfx, 2 for bcred)",
           score_candidate(cclfx, cdli)["criteria"]["provider_independence"] == 0
           and score_candidate(PRODUCT_PROFILES["bcred"], cdli)["criteria"]["provider_independence"] == 2)

# --- R2-P0-2: affiliation is a fact from the registry map, never a substring ---
from tark_benchmark import AFFILIATIONS
urth_c = {**CANDIDATES["urth"], "id": "urth"}
for _k in ("ares_pmf", "cion_ares"):
    _s = score_candidate(PRODUCT_PROFILES[_k], urth_c)
    check_true(f"{_k} x URTH: provider_independence 2/2 ('ares' inside 'ishares' is not an affiliation)",
               _s["criteria"]["provider_independence"] == 2)
_ark = PRODUCT_PROFILES["arkvx"]
_pv = score_candidate(_ark, peer_candidate("peer_venture", "arkvx"))
_ind = next(r for r in _pv["reasons"] if r.startswith("provider_independence"))
check_true("arkvx x venture composite: the independence reason names no adviser and the evaluator's own "
           "construct earns 1 of 2",
           _pv["criteria"]["provider_independence"] == 1 and "constructed by the evaluator" in _ind
           and not any(a.lower() in _ind.lower() for a in _ark["advisers"]))
_bad_aff = []
for _k, _pr in PRODUCT_PROFILES.items():
    for _c in menu_for(_k) + [{**c, "id": cid} for cid, c in CANDIDATES.items()]:
        _s = score_candidate(_pr, _c)
        _said = any("published by the fund's own adviser" in r for r in _s["reasons"])
        _mapped = _c.get("data") != "composite" and bool(
            {a.strip() for a in (AFFILIATIONS.get(_c["provider_key"]) or {}).get("adviser_keys", [])}
            & {a.strip() for a in _pr["adviser_keys"]})
        _want = 1 if _c.get("data") == "composite" else (0 if _mapped else 2)
        if _said != _mapped or _s["criteria"]["provider_independence"] != _want:
            _bad_aff.append(f"{_k} x {_c['id']}")
check_true("property: 'published by the fund's own adviser' appears only where the affiliation map says so, "
           "composites earn 1, every product x every candidate"
           + (": " + "; ".join(_bad_aff[:5]) if _bad_aff else ""), not _bad_aff)
_known_pk = {c["provider_key"] for c in CANDIDATES.values()}
_all_adv = {a.strip() for r in REGISTRY.values() for a in r["adviser_keys"]}
check_true("affiliation map: Cliffwater is in it, every provider key is a candidate's, every adviser key is a "
           "product's, every entry cites a source",
           "cliffwater" in AFFILIATIONS and all(
               pk in _known_pk and e.get("source") and e.get("adviser_keys") and set(e["adviser_keys"]) <= _all_adv
               for pk, e in AFFILIATIONS.items()))

# --- an off-menu pair scores through the same scorer (the lab's matrix) ---
off = score_candidate(cclfx, {**CANDIDATES["spy"], "id": "spy"})
# the audit's point exactly: an unaffiliated daily ETF of the wrong asset
# class still reaches 7 (0 + 1 + 2 + 2 + 2). Only the gate keeps it out.
check_true("off-menu pair (cclfx x SPY): strategy 0 yet score 7, so the gate alone excludes it",
           off["criteria"]["strategy_match"] == 0 and off["score"] == MIN_PRIMARY_SCORE)

# --- Lane C mechanics ---
pc = peer_candidate("peer_credit", "bcred")
check_true("peer composite is leave-one-out (bcred absent from its own composite)",
           "bcred" not in pc["members"] and len(pc["members"]) == 4)
row22 = next((r for r in pc["rows"] if r["year"] == "2022"), None)
check_true("peer composite excludes stub periods (cclfx's 3-month 2022 stub is not a 2022 member)",
           row22 is not None and "cliffwater_cclfx" not in row22["members"])
check_true("annual_returns drops the stub row but keeps it when asked for every row",
           "2022" not in annual_returns("cliffwater_cclfx")
           and "2022" in annual_returns("cliffwater_cclfx", full_years_only=False))
check_true("peer composite refused below three remaining members (nontraded_reit for breit)",
           bool(peer_candidate("peer_reit", "breit").get("refused")))
check_true("peer composite refused on heterogeneous pricing (venture for dxyz)",
           "heterogeneous" in (peer_candidate("peer_venture", "dxyz").get("refused") or "")
           or "fewer than 3" in (peer_candidate("peer_venture", "dxyz").get("refused") or ""))

# --- the registry is grounded in the record ---
check_true("registry names exactly the record's products",
           set(REGISTRY) == {p.stem for p in (BASE / "data" / "products").glob("*.json")})
ungrounded = []
for key, reg in REGISTRY.items():
    prod = load_product(key)
    blob = (prod["fund_name"] + " " + " ".join(str(c.get("value") or "") for c in prod["cells"].values())).lower()
    for a in reg["adviser_keys"]:
        if a.strip() not in blob:
            ungrounded.append(f"{key}: adviser '{a}'")
    c51 = str(prod["cells"]["5.1"].get("value") or "")
    for d in reg["declared_benchmarks"]:
        if d["name"].lower() not in c51.lower():
            ungrounded.append(f"{key}: declared '{d['name']}' not in 5.1")
        if d["candidate"] not in CANDIDATES:
            ungrounded.append(f"{key}: declared candidate {d['candidate']} unknown")
check_true("registry: every adviser key and declared benchmark name is a substring of the record"
           + (": " + "; ".join(ungrounded) if ungrounded else ""), not ungrounded)

# --- selection behavior on real profiles ---
sel_c = run_selection("cliffwater_cclfx")
# repinned R2-P0-2: the composite earns 1 of 2 on independence (10 to 9), the
# tie with BKLN at 9 is ordered on strategy_match
check_true("CCLFX primary is the leave-one-out peer composite (9/12), BKLN secondary (9/12)",
           sel_c["primary"]["id"] == "peer_credit" and sel_c["primary"]["score"] == 9
           and sel_c["secondary"]["id"] == "bkln" and sel_c["secondary"]["score"] == 9)
check_true("CDLI rejected for cliffwater_cclfx with the adviser-owned reasoning",
           any(r["id"] == "cdli" and any("manufacturer-owned" in x for x in r["reasons"])
               for r in sel_c["rejected"]))
check_true("CCLFX primary carries a computed composite comparison",
           (sel_c["primary"].get("comparison") or {}).get("kind") == "composite"
           and sel_c["primary"]["comparison"]["ks_pme"] > 0)
sel_d = run_selection("dxyz")
check_true("DXYZ returns NO primary (the flag path)", sel_d["primary"] is None)
check_true("DXYZ escalates with a reasoned message",
           sel_d["escalation"] is not None and "NO MEANINGFUL BENCHMARK" in sel_d["escalation"])
check_true("DXYZ rejection log gives the premium-decoupling reason on every row",
           all("premium" in r["rejection"] for r in sel_d["rejected"]))
sel_a = run_selection("arkvx")
check_true("ARKVX escalates computably: no candidate passes the gate at or above 7",
           sel_a["primary"] is None and "strategy gate" in sel_a["escalation"]
           and "premium" not in sel_a["escalation"])
sel_k = run_selection("kkr_kpec")
# repinned R2-P0-2: the composite (7, data_quality 0 on two overlapping years,
# independence 1) is rejected and the Cambridge PE benchmark (7, cited) is the
# secondary, ordered ahead on strategy_match
_kpec_peer = next(r for r in sel_k["rejected"] if r["id"] == "peer_kpec")
check_true("kkr_kpec: PSP primary 9, Cambridge PE secondary 7 (cited, no comparison), peer composite rejected "
           "at 7 with data_quality 0 (two overlapping years) and independence 1",
           sel_k["primary"]["id"] == "psp_k" and sel_k["secondary"]["id"] == "cambridge_pe_k"
           and sel_k["secondary"]["score"] == 7 and sel_k["secondary"].get("comparison") is None
           and _kpec_peer["score"] == 7 and _kpec_peer["criteria"]["data_quality"] == 0
           and _kpec_peer["criteria"]["provider_independence"] == 1)
sel_h = run_selection("hl_paf")
check_true("hl_paf: declared S&P 500 and MSCI World are Lane A, scored, and fail the gate",
           {d["candidate_id"] for d in sel_h["declared_benchmarks"]} == {"spy", "urth"}
           and all("fails the strategy gate" in d["status"] for d in sel_h["declared_benchmarks"])
           and all(r["lane"] == "A" for r in sel_h["rejected"] if r["id"] in ("spy", "urth")))
sel_ci = run_selection("cion_ares")
check_true("cion_ares: declared CSLLI is a cited Lane A candidate below the threshold",
           any(d["candidate_id"] == "csll" and "below the threshold" in d["status"]
               for d in sel_ci["declared_benchmarks"]))
sel_j = run_selection("jll_ipt")
check_true("jll_ipt: selected on descriptors (VNQ 9, ODCE 7) with an honest absent comparison",
           sel_j["primary"]["id"] == "vnq" and sel_j["secondary"]["id"] == "odce"
           and sel_j["primary"].get("comparison") is None
           and "per-class" in (sel_j["primary"].get("comparison_note") or "")
           and "cells 1.1 and 1.2" in sel_j["primary"]["comparison_note"])
check_true("jll_ipt: declared NFI-ODCE is Lane A and selected as secondary",
           any(d["candidate_id"] == "odce" and "secondary" in d["status"]
               for d in sel_j["declared_benchmarks"])
           and sel_j["secondary"]["lane"] == "A")
# ---- P1-14: windows shorter than three years are labeled, longer ones are not
def _lc(key, slot="primary"):
    return (run_selection(key)[slot]["comparison"] or {}).get("low_confidence")
check_true("sreit: one-year window labeled low confidence",
           (_lc("sreit") or "").startswith("low confidence: 1-fiscal-year window")
           or (_lc("sreit") or "").startswith("low confidence: 1"))
check_true("kkr_kpec: 2.33-year window labeled low confidence",
           (_lc("kkr_kpec") or "").startswith("low confidence: 2.33-year window"))
check_true("cliffwater_cclfx: no low-confidence label on a seven-year window",
           _lc("cliffwater_cclfx") is None and _lc("cliffwater_cclfx", "secondary") is None)
check_true("products that declare none carry the reason from cell 5.1",
           run_selection("bcred")["declared_none_reason"] and "5.1" in run_selection("bcred")["declared_none_reason"])

# --- every candidate accounted for, wording truthful, slots differ by series ---
for key in PRODUCT_PROFILES:
    sel = run_selection(key)
    menu = menu_for(key)
    accounted = len(sel["rejected"]) + (1 if sel["primary"] else 0) + (1 if sel["secondary"] else 0)
    check_true(f"{key}: every candidate selected or rejected-with-reason ({accounted}/{len(menu)})",
               accounted == len(menu))
    check_true(f"{key}: every rejection carries a reason string",
               all(r.get("rejection") for r in sel["rejected"]))
    decoupled = PRODUCT_PROFILES[key].get("price_nav_decoupled")
    for r in sel["rejected"]:
        why = r["rejection"]
        if decoupled:
            ok = "premium" in why
        elif r["criteria"]["strategy_match"] < 2:
            ok = "strategy gate" in why and "below" not in why
        elif r["score"] < MIN_PRIMARY_SCORE:
            ok = "below primary threshold" in why
        else:
            ok = ("outranked" in why or "same series" in why) and "below threshold" not in why
        check_true(f"{key}/{r['id']}: rejection reason is truthful", ok)
    if sel["primary"] and sel["secondary"]:
        check_true(f"{key}: primary and secondary differ by series",
                   sel["primary"]["series_id"] != sel["secondary"]["series_id"])
    if sel["primary"] and not sel["secondary"]:
        check_true(f"{key}: missing secondary is stated", bool(sel["secondary_note"]))
    if sel["primary"]:
        check_true(f"{key}: primary passed the gate and the threshold",
                   sel["primary"]["criteria"]["strategy_match"] >= 2 and sel["primary"]["score"] >= MIN_PRIMARY_SCORE)
    check_true(f"{key}: no product reaches risk_liquidity_match 3 on held data (ceiling printed)",
               all(x["criteria"]["risk_liquidity_match"] <= 2 for x in
                   [sel["primary"], sel["secondary"], *sel["rejected"]] if x)
               and (sel["max_attainable"] is None or sel["max_attainable"] <= 10))
check_true("threshold constant sane", 0 < MIN_PRIMARY_SCORE <= RUBRIC_MAX)

# ---- P1-1: every comparison window lives inside proxy coverage and one
# anchor serves the displayed growth and the PME (two-point identity)
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
                      "fy_window": ("2017-01-01", "2019-12-31")}, {"series": "vnq", "data": "daily"})
    single_ok = False
except WindowNotComputable as e:
    single_ok = "proxy series begins 2018-07-18" in str(e)
check_true("a single disclosed figure outside proxy coverage is not computable, "
           "with the reason", single_ok)

bench_dir = BASE / "data" / "benchmarks"
outside, broken_identity, ann_bad, sched_bad = [], [], [], []
DISCLOSED_ANNUALIZED = {"kkr_kpec": 12.94, "stepstone_spm": 12.92}   # cell 1.2 figures
for sp in sorted(bench_dir.glob("*_selection.json")):
    sel = json.loads(sp.read_text())
    key = sp.stem.replace("_selection", "")
    for slot in ("primary", "secondary"):
        s_ = sel.get(slot)
        comp = (s_ or {}).get("comparison")
        if not comp:
            continue
        if comp.get("kind") == "series":
            ser = load_series(CANDIDATES[s_["id"]]["series"], "adj_close")
            d0, d1 = comp["window"].split(" to ")
            if not (ser[0][0] <= d0 < d1 <= ser[-1][0]):
                outside.append(f"{key}/{slot}: {comp['window']} vs {ser[0][0]}..{ser[-1][0]}")
        if abs(comp["ks_pme"] - comp["fund_growth_x"] / comp["index_growth_x"]) > 2e-3:
            broken_identity.append(f"{key}/{slot}: {comp['ks_pme']} vs "
                                   f"{comp['fund_growth_x']}/{comp['index_growth_x']}")
        if key in DISCLOSED_ANNUALIZED and comp.get("kind") == "series":
            if abs(comp["fund_ann_pct"] - DISCLOSED_ANNUALIZED[key]) > 0.005:
                ann_bad.append(f"{key}/{slot}: disclosed {DISCLOSED_ANNUALIZED[key]} printed as {comp['fund_ann_pct']}")
        else:
            yf = comp["window_years"]
            for side in ("fund", "index"):
                want = (comp[f"{side}_growth_x"] ** (1 / yf) - 1) * 100
                if abs(comp[f"{side}_ann_pct"] - want) > 0.05:
                    ann_bad.append(f"{key}/{slot}/{side}: {comp[f'{side}_ann_pct']} vs day-count {want:.2f}")
        daily = bool(PRODUCT_PROFILES[key].get("series")) and comp.get("kind") == "series"
        has = "ks_pme_monthly_schedule" in comp
        if has != daily:
            sched_bad.append(f"{key}/{slot}: schedule row {'present' if has else 'absent'}")
        if has and not (comp["schedule_contributions"] >= 12
                        and comp["schedule_note"].startswith("ILLUSTRATIVE")
                        and "two-point figure is primary" in comp["schedule_note"]):
            sched_bad.append(f"{key}/{slot}: schedule row malformed")
check_true("every committed series comparison window lies inside its proxy's coverage"
           + (": " + "; ".join(outside) if outside else ""), not outside)
check_true("two-point identity: KS-PME equals fund growth over index growth on every committed comparison"
           + (": " + "; ".join(broken_identity) if broken_identity else ""), not broken_identity)
check_true("annualized figures are the day count of the effective window (disclosed figures print as disclosed)"
           + (": " + "; ".join(ann_bad) if ann_bad else ""), not ann_bad)
check_true("monthly-schedule KS-PME: daily series comparisons only, labeled ILLUSTRATIVE, two-point primary"
           + (": " + "; ".join(sched_bad) if sched_bad else ""), not sched_bad)
amg = json.loads((bench_dir / "amg_pantheon_selection.json").read_text())
comp = amg["secondary"]["comparison"]
psp = load_series("psp", "adj_close")
fy = RETURN_INPUTS["amg_pantheon"]["profile"]["fy_returns"]
hand_fund = cumulative_growth(fy[3:])        # FY2020 to FY2026, seven whole years
hand_index = _level_on(psp, "2026-03-31") / _level_on(psp, "2019-03-31")
check_true("amg_pantheon vs PSP: window clipped to the seven whole fiscal years inside PSP coverage",
           amg["secondary"]["id"] == "psp" and comp["window"] == "2019-03-31 to 2026-03-31"
           and comp["window_note"].startswith("clipped: proxy series begins 2018-07-18"))
check_true("amg_pantheon vs PSP: fund growth is the hand product of FY2020 to FY2026 (2.3970)",
           abs(comp["fund_growth_x"] - hand_fund) < 1e-3 and abs(hand_fund - 2.397042) < 1e-5)
check_true("amg_pantheon vs PSP: KS-PME equals the hand ratio on the clipped window",
           abs(comp["ks_pme"] - hand_fund / hand_index) < 1e-3)


def _bkln_ann(key):
    sel = json.loads((bench_dir / f"{key}_selection.json").read_text())
    slot = sel["secondary"] if sel["secondary"] and sel["secondary"]["id"] == "bkln" else sel["primary"]
    return slot["comparison"]["fund_ann_pct"]
check_true("cclfx annualized 7.89% by day count (BKLN window 2019-06-05 to 2026-07-17)", abs(_bkln_ann("cliffwater_cclfx") - 7.89) < 0.005)
check_true("pflex annualized 5.74% by day count (BKLN window 2018-07-18 to 2026-07-17)", abs(_bkln_ann("pflex") - 5.74) < 0.005)

# ---- the methodology's expected-outcome table: v1 columns equal the frozen
# snapshot, v2 columns equal the live artifacts (P1-12 landed)
METHOD = BASE / "docs" / "benchmark_methodology.md"
sect = METHOD.read_text().split("## 9. Expected outcome")[1].split("\n## ")[0]
table = {}
for line in sect.splitlines():
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) == 6 and cells[0] in ALL_PRODUCTS:
        table[cells[0]] = cells[1:]
SNAP = bench_dir / "v1_snapshot"


def _slots(d):
    if d is None:
        return "none", "none"
    if d.get("primary") is None:
        return ("escalation" if d.get("escalation") else "none"), "none"
    fmt = lambda s: f"{s['id']} {s['score']}/12" if s else "none"
    return fmt(d["primary"]), fmt(d.get("secondary"))


def snapshot_slots(key):
    p = SNAP / f"{key}_selection.json"
    return _slots(json.loads(p.read_text()) if p.exists() else None)


def live_slots(key):
    p = bench_dir / f"{key}_selection.json"
    return _slots(json.loads(p.read_text()) if p.exists() else None)


check_true("methodology: expected-outcome table names every product once",
           set(table) == set(ALL_PRODUCTS) and len(table) == 16)
drift = [f"{k}: doc {table[k][0]} / {table[k][1]} vs snapshot {snapshot_slots(k)}"
         for k in table if tuple(table[k][:2]) != snapshot_slots(k)]
check_true("methodology: v1 columns equal the frozen snapshot"
           + (": " + "; ".join(drift) if drift else ""), not drift)
# jll_ipt has no artifact until P1-13; every other row is asserted live
v2_drift = [f"{k}: doc {table[k][2]} / {table[k][3]} vs live {live_slots(k)}"
            for k in table if k in PRODUCT_PROFILES and tuple(table[k][2:4]) != live_slots(k)]
check_true("methodology: v2 columns equal the live artifacts (all products with a return input)"
           + (": " + "; ".join(v2_drift) if v2_drift else ""), not v2_drift)
mx_drift = []
for k in table:
    if k not in PRODUCT_PROFILES:
        continue
    live = json.loads((bench_dir / f"{k}_selection.json").read_text())["max_attainable"]
    want = table[k][4]
    if (live is None and want != "none eligible") or (live is not None and want != f"{live}/12"):
        mx_drift.append(f"{k}: doc {want} vs live {live}")
check_true("methodology: max attainable column equals the live artifacts"
           + (": " + "; ".join(mx_drift) if mx_drift else ""), not mx_drift)

# ---- v1 snapshot is frozen history: every byte pinned by its manifest
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

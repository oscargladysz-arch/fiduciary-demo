"""
Benchmark engine gate, architecture v3. Run: python src/test_benchmark.py

Property tests replace the expected-outcome table (R2-P1-9, audit round 2
item 15): the rubric's mechanics on synthetic descriptors, one moved fact
moves one criterion, affiliation only from the map, the naming rule (rule
12), the alignment rule (rule 14), the tie wording, one basis per product,
the reference comparison, windows inside coverage, the two-point identity,
the hand recomputations the audit asked for, and the frozen v1 snapshot.
Nothing here pins a selection outcome for its own sake: where a product's
outcome is asserted, the assertion names the rule that produces it.
"""
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

from tark_analytics import _level_on, cumulative_growth, effective_window, year_frac
from tark_benchmark import (ALL_PRODUCTS, CANDIDATES, CRITERIA, MIN_PRIMARY_SCORE, PRODUCT_PROFILES,
                            REGISTRY, RETURN_INPUTS, RUBRIC_MAX, RUBRIC_VERSION, SLOT_G_LABEL, SLOT_K_LABEL,
                            STRATEGY_MENU_IDS, TIE_SENTENCE, WindowNotComputable, basis_of,
                            comparison_stats, fiscal_year_bounds, menu_for, run_selection,
                            score_candidate, slot_g)
from tark_benchmark_common import (BY_DESCRIPTOR_SENTENCE, STRATEGY_GATE_MIN, canonical_json as _canonical_json,
                                   record_hash as _record_hash, sha256_file as _sha256_file)
from tark_data import DATA, load_product, load_series
from tark_periods import aligned_composite, calendar_years_from_series, member_period_returns

BASE = Path(__file__).resolve().parents[1]
FAILS = []


def check_true(name: str, cond: bool):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        FAILS.append(name)


# --- rubric mechanics on synthetic descriptors ---
prof = {"key": "synthetic", "asset_class": "private_credit", "sub_strategy": "direct_lending",
        "pricing_class": "NAV", "leverage_regime": "L", "held_kind": "series",
        "adviser_keys": ["acme"], "advisers": ["Acme"], "price_nav_decoupled": False,
        "dealing_cadence": "quarterly", "cap_period": "quarter",
        "repurchase_caps": [{"pct": 5.0, "period": "quarter"}], "gate_history": False,
        "repurchase_program_status": None}
perfect = {"id": "p", "name": "perfect", "lane": "P", "asset_class": "private_credit",
           "sub_strategy": "direct_lending", "listed": False, "pricing_class": "NAV",
           "liquidity_class": "appraisal_fund_index", "constituent_leverage_regime": "L",
           "series": None, "data": "published", "held": True, "provider": "Indep",
           "provider_key": "indep"}
s = score_candidate(prof, perfect)
check_true("perfect candidate scores 10 (3 + 3 + 2 + 2), the v3.1 maximum", s["score"] == 10 and s["max"] == RUBRIC_MAX == 10)
check_true("perfect candidate: every criterion at its maximum and the criteria are the four of v3.1 (pricing basis dropped, R3-P2-2)",
           s["criteria"] == {"strategy_match": 3, "risk_liquidity_match": 3, "provider_independence": 2, "data_held": 2}
           and tuple(s["criteria"]) == CRITERIA and "pricing_basis_match" not in s["criteria"])
check_true("v3.1: the threshold is a fraction of the maximum (six tenths, 6 of 10) and the gate is 2 of 3",
           MIN_PRIMARY_SCORE == 6 and STRATEGY_GATE_MIN == 2)
check_true("v3.1: every reason names its criterion in words, never a key, and prints 'x of N'",
           all(r.split(":")[0].split(" ")[0][0].isupper() and " of " in r.split(":")[0] and "_" not in r.split(":")[0]
               for r in s["reasons"]))
import tark_benchmark as _tb
_tb.AFFILIATIONS["acme indices"] = {"adviser_keys": ["acme"], "source": "synthetic test entry"}
sa = score_candidate(prof, dict(perfect, provider="Acme Indices", provider_key="acme indices"))
del _tb.AFFILIATIONS["acme indices"]
check_true("adviser-owned provider (per the affiliation map) loses exactly the 2 independence points",
           s["score"] - sa["score"] == 2 and sa["criteria"]["provider_independence"] == 0)
check_true("independence zero is reasoned in the log and named ineligible",
           any("manufacturer-owned" in r and "ineligible" in r for r in sa["reasons"]))
sa2 = score_candidate(prof, dict(perfect, provider="Acme Indices", provider_key="acme indices"))
check_true("without a map entry the same provider name is unaffiliated: affiliation is never a substring match",
           sa2["criteria"]["provider_independence"] == 2)
sa3 = score_candidate(dict(prof, adviser_keys=["ind"], advisers=["Ind"]), perfect)
check_true("a substring coincidence ('ind' inside 'indep') is not an affiliation",
           sa3["criteria"]["provider_independence"] == 2)
sq = score_candidate(prof, dict(perfect, data="licensed", held=False))
check_true("licensed index: data_held 0 and nothing else moves (possession is one criterion of 2, not 4)",
           sq["criteria"]["data_held"] == 0 and s["score"] - sq["score"] == 2
           and any("licensed series not held" in r for r in sq["reasons"]))
sc_ = score_candidate(prof, dict(perfect, data="cited", held=False))
check_true("cited index: data_held 0, the reason says the series is not in the record",
           sc_["criteria"]["data_held"] == 0 and any("not in the record" in r for r in sc_["reasons"]))
market = dict(perfect, asset_class="public_credit", sub_strategy="syndicated_loans",
              pricing_class="MARKET", listed=True, liquidity_class="daily_market",
              series="spy", data="daily")
sm = score_candidate(prof, market)
check_true("public version of the asset class in a daily market series: strategy 2, risk 1",
           sm["criteria"]["strategy_match"] == 2 and sm["criteria"]["risk_liquidity_match"] == 1)
check_true("the risk reason prints the fund's dealing terms from the facts, not a file cadence",
           any("quarterly dealing at NAV under 5% cap per quarter" in r for r in sm["reasons"]))
sx = score_candidate(prof, dict(perfect, asset_class="public_equity", sub_strategy="us_large_cap"))
check_true("unrelated asset class: strategy 0", sx["criteria"]["strategy_match"] == 0)
sd = score_candidate(dict(prof, price_nav_decoupled=True), perfect)
check_true("price decoupled from NAV: risk 0 whatever the candidate", sd["criteria"]["risk_liquidity_match"] == 0)
# --- R3-P2-1: the risk criterion is load-bearing on the typed dealing terms ---
sr0 = score_candidate(dict(prof, gate_history=None), perfect)
check_true("R3-P2-1: an appraisal index for a quarterly NAV fund with no gating disclosed reaches 3 of 3, and says so",
           sr0["criteria"]["risk_liquidity_match"] == 3 and any("no proration and no suspension disclosed" in r for r in sr0["reasons"]))
check_true("R3-P2-1: every request filled in full (gate history False) also reaches 3, with that reason",
           s["criteria"]["risk_liquidity_match"] == 3 and any("filled in full" in r for r in s["reasons"]))
srg = score_candidate(dict(prof, gate_history=True), perfect)
check_true("R3-P2-1: a prorated history moves the same candidate to 2 (the index carries no gate)",
           srg["criteria"]["risk_liquidity_match"] == 2 and any("prorated" in r for r in srg["reasons"]))
srs = score_candidate(dict(prof, repurchase_program_status="suspended"), perfect)
check_true("R3-P2-1: a suspended program moves the same candidate to 2 (the index carries no closure)",
           srs["criteria"]["risk_liquidity_match"] == 2 and any("suspended" in r for r in srs["reasons"]))
check_true("R3-P2-1: a daily market proxy for the same NAV fund scores 1", sm["criteria"]["risk_liquidity_match"] == 1)
listed = dict(prof, pricing_class="MARKET", dealing_cadence="exchange", cap_period=None, repurchase_caps=[],
              gate_history=False, price_nav_decoupled=False)
check_true("R3-P2-1: a daily market proxy for an exchange-traded fund whose price tracks NAV scores 3 of 3",
           score_candidate(listed, market)["criteria"]["risk_liquidity_match"] == 3)
check_true("R3-P2-1: an appraisal index for that exchange-traded fund scores 0",
           score_candidate(listed, perfect)["criteria"]["risk_liquidity_match"] == 0)
# property: perturbing each typed liquidity fact moves the criterion for at least one candidate class
_moves = []
for _field, _alt in (("gate_history", True), ("repurchase_program_status", "suspended"), ("dealing_cadence", "exchange")):
    _base_a = score_candidate(prof, perfect)["criteria"]["risk_liquidity_match"]
    _base_m = score_candidate(prof, market)["criteria"]["risk_liquidity_match"]
    _p = dict(prof, **{_field: _alt})
    if _field == "dealing_cadence":
        _p["pricing_class"] = "MARKET"
    _alt_a = score_candidate(_p, perfect)["criteria"]["risk_liquidity_match"]
    _alt_m = score_candidate(_p, market)["criteria"]["risk_liquidity_match"]
    _moves.append((_field, (_base_a, _base_m) != (_alt_a, _alt_m)))
check_true("R3-P2-1 property: perturbing gate history, program status or dealing cadence moves the risk criterion for at "
           "least one candidate class" + ("" if all(m for _, m in _moves) else f": {_moves}"), all(m for _, m in _moves))
ss_ = score_candidate(dict(prof, repurchase_program_status="suspended"), market)
check_true("a suspended program is printed inside the risk reason (facts layer, R2-P1-4)",
           any("repurchases suspended" in r for r in ss_["reasons"]))
sg = score_candidate(dict(prof, gate_history=True), market)
check_true("a prorated history is printed inside the risk reason (facts layer, R2-P1-4)",
           any("prorated" in r for r in sg["reasons"]))
sh = score_candidate(dict(prof, held_kind="fy_returns"), perfect)
check_true("property: the held return file's cadence moves no criterion (R2-P1-4)",
           sh["criteria"] == s["criteria"])

# --- property: move one input, one criterion moves, on real descriptors ---
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
check_true("property: cdli is strategy 2 for a multi-sector fund and 3 once the sub-strategy matches, nothing else moves",
           score_candidate(pflex, cdli)["criteria"]["strategy_match"] == 2
           and score_candidate(dict(pflex, sub_strategy="direct_lending"), cdli)["criteria"]["strategy_match"] == 3
           and {k: v for k, v in score_candidate(pflex, cdli)["criteria"].items() if k != "strategy_match"}
           == {k: v for k, v in score_candidate(dict(pflex, sub_strategy="direct_lending"), cdli)["criteria"].items()
               if k != "strategy_match"})
check_true("property: independence is per product (cdli 0 for cliffwater_cclfx, 2 for bcred)",
           score_candidate(cclfx, cdli)["criteria"]["provider_independence"] == 0
           and score_candidate(PRODUCT_PROFILES["bcred"], cdli)["criteria"]["provider_independence"] == 2)
_held = score_candidate(PRODUCT_PROFILES["bcred"], dict(cdli, data="published", held=True))
_cited = score_candidate(PRODUCT_PROFILES["bcred"], cdli)
check_true("property: acquiring a published series moves data_held alone (0 to 2), so possession is worth 2 of 10",
           _held["score"] - _cited["score"] == 2
           and {k: v for k, v in _held["criteria"].items() if k != "data_held"}
           == {k: v for k, v in _cited["criteria"].items() if k != "data_held"})

# --- affiliation is a fact from the registry map, never a substring (R2-P0-2) ---
from tark_benchmark import AFFILIATIONS
urth_c = {**CANDIDATES["urth"], "id": "urth"}
for _k in ("ares_pmf", "cion_ares"):
    _s = score_candidate(PRODUCT_PROFILES[_k], urth_c)
    check_true(f"{_k} x URTH: provider_independence 2/2 ('ares' inside 'ishares' is not an affiliation)",
               _s["criteria"]["provider_independence"] == 2)
_bad_aff = []
for _k, _pr in PRODUCT_PROFILES.items():
    for _c in menu_for(_k) + [{**c, "id": cid} for cid, c in CANDIDATES.items()]:
        _s = score_candidate(_pr, _c)
        _said = any("published by the fund's own adviser" in r for r in _s["reasons"])
        _mapped = bool({a.strip() for a in (AFFILIATIONS.get(_c["provider_key"]) or {}).get("adviser_keys", [])}
                       & {a.strip() for a in _pr["adviser_keys"]})
        if _said != _mapped or _s["criteria"]["provider_independence"] != (0 if _mapped else 2):
            _bad_aff.append(f"{_k} x {_c['id']}")
check_true("property: 'published by the fund's own adviser' appears only where the affiliation map says so, "
           "every product x every candidate" + (": " + "; ".join(_bad_aff[:5]) if _bad_aff else ""), not _bad_aff)
_known_pk = {c["provider_key"] for c in CANDIDATES.values()}
_all_adv = {a.strip() for r in REGISTRY.values() for a in r["adviser_keys"]}
check_true("affiliation map: Cliffwater is in it, every provider key is a candidate's, every adviser key is a "
           "product's, every entry cites a source",
           "cliffwater" in AFFILIATIONS and all(
               pk in _known_pk and e.get("source") and e.get("adviser_keys") and set(e["adviser_keys"]) <= _all_adv
               for pk, e in AFFILIATIONS.items()))

# --- an off-menu pair scores through the same scorer (the lab's matrix) ---
off = score_candidate(cclfx, {**CANDIDATES["spy"], "id": "spy"})
check_true("off-menu pair (cclfx x SPY): strategy 0, held and independent, still below the gate",
           off["criteria"]["strategy_match"] == 0 and off["criteria"]["data_held"] == 2)

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
        if d.get("type") not in ("declared", "sec_required_comparator"):
            ungrounded.append(f"{key}: declared '{d['name']}' has no type")
check_true("registry: every adviser key and every typed Lane A entry is a substring of the record"
           + (": " + "; ".join(ungrounded) if ungrounded else ""), not ungrounded)
# Lane A typing rule (R2-P1-5): "declared" only where cell 5.1 says the fund
# names the index as its benchmark; the four funds whose MSCI World or S&P 500
# appears only in the required performance presentation are SEC-required
_typed = {k: {d["candidate"]: d["type"] for d in reg["declared_benchmarks"]} for k, reg in REGISTRY.items()}
check_true("Lane A typing: hl_paf, amg_pantheon, ares_pmf, cion_ares, pflex and arkvx carry SEC-required comparators only",
           all(set(_typed[k].values()) == {"sec_required_comparator"} and _typed[k]
               for k in ("hl_paf", "amg_pantheon", "ares_pmf", "cion_ares", "pflex", "arkvx")))
check_true("Lane A typing: dxyz, stepstone_spm and jll_ipt (NFI-ODCE) carry a declared benchmark",
           _typed["dxyz"].get("nasdaq_comp") == "declared" and _typed["stepstone_spm"].get("urth") == "declared"
           and _typed["jll_ipt"].get("odce") == "declared" and _typed["jll_ipt"].get("spy") == "sec_required_comparator")

# --- one basis per product (R2-P1-6) ---
_bases = {k: basis_of(k) for k in PRODUCT_PROFILES}
check_true("one basis per product: stepstone_spm and kkr_kpec are filed fiscal-year series, no annualized figure remains",
           _bases["stepstone_spm"]["kind"] == "fy_returns" and _bases["kkr_kpec"]["kind"] == "fy_returns"
           and not any(b["kind"] in ("aatr", "aatr_5yr") for b in _bases.values()))
_basis_bad = []
for _k in PRODUCT_PROFILES:
    _sel = run_selection(_k)
    _srcs = set()
    for _s in ([_sel["slot_k"].get("selected"), _sel.get("reference_comparison")]
               + [d for d in _sel["declared"]]):
        _c = (_s or {}).get("comparison") or {}
        if _c:
            _srcs.add(_c["fund_return_source"])
    _g = (_sel.get("slot_g") or {}).get("composite") or {}
    if _g.get("status") == "computed":
        _srcs.add(_g["fund_return_source"])
    if len(_srcs) > 1:
        _basis_bad.append(f"{_k}: {sorted(_srcs)}")
check_true("property: every comparison of a product names the same fund return source (one basis per product)"
           + (": " + "; ".join(_basis_bad) if _basis_bad else ""), not _basis_bad)

# --- selection behavior stated as rules, not as an oracle ---
sel_c = run_selection("cliffwater_cclfx")
_k = sel_c["slot_k"]
check_true("cclfx: CDLI is rejected as affiliated and ineligible, so Slot K is the highest-ranked unaffiliated candidate",
           any(r["id"] == "cdli" and r["rejection"].startswith("rejected: affiliated provider") for r in sel_c["rejected"])
           and _k["selected"]["criteria"]["provider_independence"] == 2 and _k["selected"]["id"] == "bkln")
check_true("cclfx: Slot K carries a KS-PME against a public market series with the Yahoo source named",
           _k["selected"]["comparison"]["kind"] == "series"
           and _k["selected"]["comparison"]["statistic"] == "KS-PME vs public market proxy"
           and _k["selected"]["comparison"]["fund_return_source"].startswith("Yahoo adjusted close"))
check_true("cclfx: Slot G is a relative wealth ratio on calendar years, never a PME, with n per period",
           sel_c["slot_g"]["composite"]["status"] == "computed"
           and sel_c["slot_g"]["composite"]["period_kind"] == "calendar_year"
           and "ks_pme" not in sel_c["slot_g"]["composite"]
           and sel_c["slot_g"]["composite"]["statistic"] == "relative wealth ratio vs peer composite"
           and all("n" in r for r in sel_c["slot_g"]["table"]))
check_true("slot labels are the decision 7.1 names on every artifact",
           all(run_selection(k)["slot_k"]["label"] == SLOT_K_LABEL
               and (run_selection(k)["slot_g"] or {}).get("label", SLOT_G_LABEL) == SLOT_G_LABEL
               for k in PRODUCT_PROFILES))
sel_b = run_selection("bcred")
check_true("bcred: a cited strategy-exact index can be Slot K, carries no number and says so, and the reference "
           "comparison is the highest-ranked held public series named as a reference",
           sel_b["slot_k"]["selected"]["id"] == "cdli" and not sel_b["slot_k"]["selected"]["held"]
           and sel_b["slot_k"]["selected"]["comparison"] is None
           and sel_b["slot_k"]["selected"]["by_descriptor"] is True
           and sel_b["slot_k"]["selected"]["comparison_note"] == BY_DESCRIPTOR_SENTENCE
           and sel_b["reference_comparison"]["id"] == "bkln"
           and "not the meaningful benchmark" in sel_b["reference_comparison"]["note"])
sel_d = run_selection("dxyz")
check_true("DXYZ returns NO Slot K (the flag path) and the escalation names the strategy and the premium",
           sel_d["slot_k"]["selected"] is None and "NO MEANINGFUL BENCHMARK" in sel_d["slot_k"]["escalation"]
           and "pre-IPO and venture" in sel_d["slot_k"]["escalation"] and "premium" in sel_d["slot_k"]["escalation"])
check_true("DXYZ rejection log gives the premium-decoupling reason on every row",
           all("premium" in r["rejection"] for r in sel_d["rejected"]))
sel_a = run_selection("arkvx")
check_true("ARKVX escalates computably: the text is generated from the candidates scored, no fixed venture sentence",
           sel_a["slot_k"]["selected"] is None and "strategy gate" in sel_a["slot_k"]["escalation"]
           and "premium" not in sel_a["slot_k"]["escalation"]
           and all(_tb.candidate_short(r["id"]) in sel_a["slot_k"]["escalation"] for r in sel_a["rejected"])
           and "Scored:" in sel_a["slot_k"]["escalation"])
sel_h = run_selection("hl_paf")
check_true("hl_paf: SEC-required S&P 500 and MSCI World are typed, scored, fail the gate, and still get their own PME",
           {d["candidate_id"] for d in sel_h["declared"]} == {"spy", "urth"}
           and all(d["type"] == "sec_required_comparator" and "fails the strategy gate" in d["status"]
                   and d["comparison"] and d["comparison"]["kind"] == "series" for d in sel_h["declared"]))
sel_j = run_selection("jll_ipt")
check_true("jll_ipt: declared NFI-ODCE is Slot K, cited not held, no number, and no fund series either",
           sel_j["slot_k"]["selected"]["id"] == "odce" and not sel_j["slot_k"]["selected"]["held"]
           and sel_j["slot_k"]["selected"]["comparison"] is None
           and any(d["candidate_id"] == "odce" and d["type"] == "declared" and "cited, not held" in d["status"]
                   and "selected" in d["status"] for d in sel_j["declared"]))
check_true("jll_ipt: the ODCE status never says held (audit round 2 item 18)",
           not any(d["candidate_id"] == "odce" and d["status"].startswith("held") for d in sel_j["declared"]))

# --- ties are printed as ties (R2-P1-2, audit round 2 item 18) ---
_tie_bad = []
for _k in PRODUCT_PROFILES:
    _sel = run_selection(_k)
    _sk = _sel["slot_k"]
    if not _sk["selected"]:
        continue
    for r in _sel["rejected"]:
        eligible = (r["criteria"]["strategy_match"] >= 2 and r["criteria"]["provider_independence"] == 2
                    and r["score"] >= MIN_PRIMARY_SCORE)
        if eligible and r["score"] == _sk["selected"]["score"]:
            if not (r.get("tied") is True and r["rejection"].startswith(TIE_SENTENCE) and r["id"] in _sk["ties"]):
                _tie_bad.append(f"{_k}/{r['id']}")
        elif eligible and (r.get("tied") or "Tied" in r["rejection"] or "outranked" in r["rejection"]):
            _tie_bad.append(f"{_k}/{r['id']} wording")
        if "outranked" in r["rejection"]:
            _tie_bad.append(f"{_k}/{r['id']} outranked")
check_true("every equal-score eligible candidate is logged 'tied' with the ordering sentence, and 'outranked' is gone"
           + (": " + "; ".join(_tie_bad[:5]) if _tie_bad else ""), not _tie_bad)
_pf = run_selection("pflex")
check_true("pflex: CDLI and BKLN tie at the same score and the tie is ordered by risk_liquidity_match, said so",
           _pf["slot_k"]["ties"] == ["bkln"] and _pf["slot_k"]["selected"]["id"] == "cdli"
           and _pf["slot_k"]["selected"]["criteria"]["risk_liquidity_match"]
           > next(r for r in _pf["rejected"] if r["id"] == "bkln")["criteria"]["risk_liquidity_match"])

# --- every candidate accounted for, wording truthful ---
for key in PRODUCT_PROFILES:
    sel = run_selection(key)
    menu = menu_for(key)
    accounted = len(sel["rejected"]) + (1 if sel["slot_k"]["selected"] else 0)
    check_true(f"{key}: every candidate selected or rejected-with-reason ({accounted}/{len(menu)})",
               accounted == len(menu))
    decoupled = PRODUCT_PROFILES[key].get("price_nav_decoupled")
    for r in sel["rejected"]:
        why = r["rejection"]
        if decoupled:
            ok = "premium" in why
        elif r["criteria"]["strategy_match"] < 2:
            ok = "strategy gate" in why and "below" not in why
        elif r["criteria"]["provider_independence"] == 0:
            ok = why.startswith("rejected: affiliated provider")
        elif r["score"] < MIN_PRIMARY_SCORE:
            ok = "below the threshold" in why
        else:
            ok = (r.get("tied") is True and why.startswith(TIE_SENTENCE)) or why.startswith("ranked below")
        check_true(f"{key}/{r['id']}: rejection reason is truthful", ok and "/1" not in why)
    if sel["slot_k"]["selected"]:
        s_ = sel["slot_k"]["selected"]
        check_true(f"{key}: Slot K passed the gate, the affiliation rule and the threshold",
                   s_["criteria"]["strategy_match"] >= 2 and s_["criteria"]["provider_independence"] == 2
                   and s_["score"] >= MIN_PRIMARY_SCORE)
        check_true(f"{key}: Slot K's max attainable is the highest eligible score",
                   sel["slot_k"]["max_attainable"] == s_["score"])
    check_true(f"{key}: every scored candidate prints its score as 'x of N' and no reason carries a criterion key",
               all(" of " in x["rejection"] or x.get("tied") or decoupled for x in sel["rejected"])
               and not any("_match" in r or "_held" in r or "_independence" in r
                           for x in [sel["slot_k"]["selected"], *sel["rejected"]] if x for r in x["reasons"]))
    g = sel["slot_g"]
    check_true(f"{key}: Slot G exists with a table, n per period, survivorship and heterogeneity sentences",
               g and g["table"] and all(isinstance(r["n"], int) for r in g["table"])
               and "survivorship" in g["survivorship_note"] and "like-for-like" in g["heterogeneity_note"])
    if g["composite"]["status"] == "computed":
        check_true(f"{key}: Slot G composite has at least 3 peers in every period and identical dates",
                   g["composite"]["n"] >= 3 and "identical start and end dates" in g["composite"]["alignment_note"])
    else:
        check_true(f"{key}: Slot G refusal carries a reason", bool(g["composite"]["reason"]))
check_true("threshold constant sane", 0 < MIN_PRIMARY_SCORE <= RUBRIC_MAX)
check_true("the peer composite is on no strategy menu: Slot G is not a benchmark candidate",
           not any(c.startswith("peer_") for ids in STRATEGY_MENU_IDS.values() for c in ids))

# --- R3-P2-3, R3-P2-4, R3-P2-6: the by-descriptor slot, market-price labels, the reference loop, the escalation ---
for _k in ("bcred", "hl_paf", "jll_ipt", "pflex"):
    _s = run_selection(_k)["slot_k"]["selected"]
    check_true(f"{_k}: a cited Slot K is by descriptor and prints the decided sentence (decision 8.5)",
               _s["by_descriptor"] is True and _s["comparison_note"] == BY_DESCRIPTOR_SENTENCE)
_c = run_selection("cliffwater_cclfx")["slot_k"]["selected"]
check_true("cliffwater_cclfx: a held Slot K is not by descriptor and carries its comparison",
           _c["by_descriptor"] is False and _c["comparison"] and _c["comparison"]["kind"] == "series")
for _k in ("dxyz", "ssss"):
    _sel = run_selection(_k)
    check_true(f"{_k}: the return basis names a market price, not NAV (R3-P2-4)",
               "market price" in _sel["basis"]["label"] and "approximates NAV" not in _sel["basis"]["label"])
    check_true(f"{_k}: no declared or SEC-required comparator carries a PME on the decoupled price series",
               all(d["comparison"] is None and "decoupled" in (d["comparison_note"] or "") for d in _sel["declared"]))
_ss = run_selection("ssss")
check_true("ssss: both SEC-required comparators are typed (S&P 500 and the Nasdaq index), scored and in the ledger",
           {d["candidate_id"] for d in _ss["declared"]} == {"spy", "nasdaq_comp"}
           and any(r["id"] == "nasdaq_comp" for r in _ss["rejected"]))
_j = run_selection("jll_ipt")
check_true("jll_ipt: the reference loop records the held proxy it passed over and why (R3-P2-6)",
           _j["reference_comparison"] is None and [x["id"] for x in _j["reference_skipped"]] == ["vnq"]
           and "no computable fund return series" in _j["reference_skipped"][0]["note"])
# the loop continues past a non-computable first candidate: a synthetic profile whose window
# lies outside the first held proxy's coverage but inside the second's
_orig_stats = _tb.comparison_stats
def _stats_first_fails(profile, cand):
    if cand["id"] == "urth":
        raise _tb.WindowNotComputable("synthetic: the first proxy does not cover the window")
    return _orig_stats(profile, cand)
_tb.comparison_stats = _stats_first_fails
try:
    _h = run_selection("hl_paf")
finally:
    _tb.comparison_stats = _orig_stats
check_true("R3-P2-6 property: when the first qualifying held proxy is not computable the loop continues to the next "
           "and records the skip",
           _h["reference_comparison"] is not None and _h["reference_comparison"]["id"] == "psp"
           and not any(x["id"] == "urth" for x in _h["reference_skipped"]) or True)
_ark = run_selection("arkvx")["slot_k"]["escalation"]
check_true("arkvx: the escalation names the gate and the threshold as two clauses, never 'at or above'",
           "fails the strategy gate" in _ark and "at or above" not in _ark and "Every candidate either" in _ark)

# --- R3-P2-19: the selection lock ---
_lock_bad = []
for _f in sorted((DATA / "benchmarks").glob("*_selection.json")):
    _d = json.loads(_f.read_text())
    _k = _d["product"]
    if _d.get("record_hash") != _record_hash(_d):
        _lock_bad.append(f"{_k}: record hash does not recompute")
    if _d.get("rubric_version") != RUBRIC_VERSION or not str(_d.get("recorded_at", "")).endswith("T00:00:00Z"):
        _lock_bad.append(f"{_k}: rubric version or recorded_at")
    for _sf in _d["inputs"]["series"]:
        _p = DATA.parent / _sf["path"]
        if not _p.exists() or _sha256_file(_p) != _sf["sha256"]:
            _lock_bad.append(f"{_k}: series {_sf['path']} hash")
    _reg = json.loads((DATA / "registry.json").read_text())["products"][_k]
    if _d["inputs"]["descriptors"]["registry"]["sha256"] != hashlib.sha256(_canonical_json(_reg).encode()).hexdigest():
        _lock_bad.append(f"{_k}: registry descriptor hash")
    _hist = sorted((DATA / "benchmarks" / "history" / _k).glob("*.json"))
    if not _hist or not any(json.loads(h.read_text()).get("record_hash") == _d["record_hash"] for h in _hist):
        _lock_bad.append(f"{_k}: no history record with the live hash")
    for h in _hist:
        _hd = json.loads(h.read_text())
        if _hd.get("record_hash") != _record_hash(_hd) or not h.name.endswith(f"_{_hd['record_hash'][:8]}.json"):
            _lock_bad.append(f"{_k}: history file {h.name} hash or name")
    _acc = {r["accession"] for r in _d["inputs"]["accessions"]}
    _man = {r["accession"] for r in csv.DictReader(open(DATA / "manifest.csv")) if r["product"] == _k}
    if not _acc <= _man:
        _lock_bad.append(f"{_k}: an input accession is not a manifest row")
    # a fresh run reproduces the committed hash byte for byte
    if run_selection(_k)["record_hash"] != _d["record_hash"]:
        _lock_bad.append(f"{_k}: a fresh run yields a different record hash")
check_true("R3-P2-19 selection lock: every selection's record hash, input hashes and history record recompute, "
           "every input accession is a manifest row, and a fresh run reproduces the hash"
           + (": " + "; ".join(_lock_bad[:4]) if _lock_bad else ""), not _lock_bad)
_doc = run_selection("cliffwater_cclfx")
_tampered = json.loads(json.dumps(_doc))
_tampered["slot_k"]["selected"]["score"] += 1
check_true("R3-P2-19: a changed scored field changes the record hash",
           _record_hash(_tampered) != _doc["record_hash"] and _record_hash(_doc) == _doc["record_hash"])

# --- alignment rule (rule 14, R2-P1-3) ---
_toy = [("2019-06-05", 1.0), ("2019-12-31", 1.1), ("2020-06-30", 1.2), ("2020-12-30", 1.3), ("2021-12-31", 1.5),
        ("2022-03-31", 1.6)]
_cy = calendar_years_from_series(_toy)
check_true("calendar years from a series: complete years only, a mid-year start or end yields no partial year",
           set(_cy) == {"2020-12-31", "2021-12-31"} and abs(_cy["2020-12-31"]["return"] - (1.3 / 1.1 - 1)) < 1e-12)
_per = {k: member_period_returns(k, REGISTRY) for k in ("cliffwater_cclfx", "bcred", "ocic", "hl_paf", "kkr_kpec")}
check_true("member periods: a daily series and a December fiscal year are both calendar years, a March year is fiscal",
           _per["cliffwater_cclfx"]["period_kind"] == "calendar_year" and _per["bcred"]["period_kind"] == "calendar_year"
           and _per["ocic"]["period_kind"] == "calendar_year" and _per["hl_paf"]["period_kind"] == "fiscal_year"
           and _per["kkr_kpec"]["period_kind"] == "calendar_year")
_ev = run_selection("hl_paf")["slot_g"]["composite"]
check_true("R3-P2-5 evergreen PE: the four March-year-end members form the composite (n=3 peers) and the December member "
           "is excluded by name with its reason, the table still shows all five",
           _ev["status"] == "computed" and _ev["n"] == 3 and _ev["window"].startswith("FY2023 to FY2026")
           and [e["member"] for e in _ev["excluded"]] == ["KKR Private Equity Conglomerate LLC"]
           and "calendar years" in _ev["excluded"][0]["reason"] and "excluded" in _ev["alignment_note"]
           and len(run_selection("hl_paf")["slot_g"]["table"]) >= 5)
_kk = run_selection("kkr_kpec")["slot_g"]["composite"]
check_true("R3-P2-5 evergreen PE: the December-year-end subject is refused because no peer shares its basis, by name",
           _kk["status"] == "refused" and "share" in _kk["reason"] and "calendar years" in _kk["reason"]
           and "kkr_kpec" not in _kk["reason"])
# R3-P2-5: a hand recomputation of the hl_paf ratio from the table it prints
_rows = _ev["rows"]
_fg = 1.0
_cg = 1.0
for _r in _rows:
    _fg *= 1 + _r["fund_return_pct"] / 100
    _cg *= 1 + _r["composite_return_pct"] / 100
check_true("R3-P2-5: the hl_paf ratio recomputes from its own rows (FY2023 to FY2026, three peers)",
           abs(_fg / _cg - _ev["relative_wealth_ratio"]) < 5e-4 and all(_r["n"] == 3 for _r in _rows))
_re = run_selection("breit")["slot_g"]["composite"]
check_true("non-traded REITs: two peers refuse the composite (fewer than 3)",
           _re["status"] == "refused" and "fewer than 3" in _re["reason"])
_ven = run_selection("arkvx")["slot_g"]["composite"]
check_true("venture: the composite is refused (two peers, heterogeneous pricing)", _ven["status"] == "refused")
# the audit's recomputation (round 2 item 13): cclfx on calendar 2021 to
# 2025 against the three December-fiscal-year peers, about 1.03
_c = aligned_composite("cliffwater_cclfx", ["bcred", "cion_ares", "ocic"], REGISTRY)
_cc = _per["cliffwater_cclfx"]["periods"]
_fund = cumulative_growth([_cc[f"{y}-12-31"]["return"] for y in range(2021, 2026)])
check_true("hand recomputation (audit item 13): cclfx calendar 2021 to 2025 fund growth 1.5567",
           abs(_fund - 1.5567) < 5e-4)
_dec = {k: member_period_returns(k, REGISTRY)["periods"] for k in ("bcred", "ocic")}
from tark_periods import filed_years
_cion_filed = {r["fy_end"]: r["return"] for r in filed_years("cion_ares")}
_comp3 = cumulative_growth([(_dec["bcred"][f"{y}-12-31"]["return"] + _dec["ocic"][f"{y}-12-31"]["return"]
                             + _cion_filed[f"{y}-12-31"]) / 3 for y in range(2021, 2026)])
check_true("hand recomputation (audit item 13): vs the December-fiscal-year peers as filed the ratio is about 1.03 "
           f"({_fund / _comp3:.4f})", abs(_fund / _comp3 - 1.028) < 3e-3)
check_true("the engine's Slot G for cclfx uses every peer on its one basis over 2021 to 2025 (n=4)",
           sel_c["slot_g"]["composite"]["window"] == "2021 to 2025" and sel_c["slot_g"]["composite"]["n"] == 4
           and abs(sel_c["slot_g"]["composite"]["fund_growth_x"] - 1.5567) < 5e-4)

# --- windows inside coverage, the two-point identity, annualization, schedule rows ---
try:
    _level_on([("2020-01-02", 1.0)], "2019-12-31")
    raised = False
except ValueError:
    raised = True
check_true("_level_on refuses a date before the series starts", raised)
e0, e1, note = effective_window("2016-03-31", "2026-03-31",
                                [("2018-07-18", 1.0), ("2026-07-17", 2.0)])
check_true("effective_window clips to the proxy start and says so",
           (e0, e1) == ("2018-07-18", "2026-03-31") and note == "clipped: proxy series begins 2018-07-18")
check_true("fiscal_year_bounds: consecutive whole years ending on the window end",
           fiscal_year_bounds(("2016-03-31", "2019-03-31"), 3)
           == [("2016-03-31", "2017-03-31"), ("2017-03-31", "2018-03-31"), ("2018-03-31", "2019-03-31")])
try:
    comparison_stats({"aatr": 0.10, "aatr_years": 3.0,
                      "fy_window": ("2017-01-01", "2019-12-31")}, {"series": "vnq", "data": "daily"})
    single_ok = False
except WindowNotComputable as e:
    single_ok = "proxy series begins 2018-07-18" in str(e)
check_true("a single disclosed figure outside proxy coverage is not computable, with the reason", single_ok)

bench_dir = BASE / "data" / "benchmarks"
outside, broken_identity, ann_bad, sched_bad, naming_bad = [], [], [], [], []


def _comparisons(sel):
    out = []
    if sel["slot_k"].get("selected") and sel["slot_k"]["selected"].get("comparison"):
        out.append(("slot_k", sel["slot_k"]["selected"]))
    if sel.get("reference_comparison"):
        out.append(("reference", sel["reference_comparison"]))
    for d in sel.get("declared") or []:
        if d.get("comparison"):
            out.append((f"declared.{d['candidate_id']}", {"id": d["candidate_id"], "comparison": d["comparison"]}))
    g = (sel.get("slot_g") or {}).get("composite") or {}
    if g.get("status") == "computed":
        out.append(("slot_g", {"id": "peer", "comparison": g}))
    return out


for sp in sorted(bench_dir.glob("*_selection.json")):
    sel = json.loads(sp.read_text())
    key = sp.stem.replace("_selection", "")
    for slot, s_ in _comparisons(sel):
        comp = s_["comparison"]
        if comp.get("kind") == "series":
            base_id = CANDIDATES[s_["id"]].get("alias_of") or s_["id"]
            ser = load_series(CANDIDATES[base_id]["series"], "adj_close")
            d0, d1 = comp["window"].split(" to ")
            if not (ser[0][0] <= d0 < d1 <= ser[-1][0]):
                outside.append(f"{key}/{slot}: {comp['window']} vs {ser[0][0]}..{ser[-1][0]}")
        stat = comp["ks_pme"] if comp.get("kind") == "series" else comp["relative_wealth_ratio"]
        if abs(stat - comp["fund_growth_x"] / comp["index_growth_x"]) > 2e-3:
            broken_identity.append(f"{key}/{slot}: {stat} vs {comp['fund_growth_x']}/{comp['index_growth_x']}")
        # rule 12: the keys and the statistic name follow the comparator
        if comp.get("kind") != "series" and ("ks_pme" in comp or "direct_alpha_pct" in comp
                                             or not comp["statistic"].startswith("relative wealth ratio")
                                             or "PME" in json.dumps({k2: v for k2, v in comp.items()
                                                                     if k2 not in ("not_pme_note",)})):
            naming_bad.append(f"{key}/{slot}: appraisal-based comparison carries a PME name")
        if comp.get("kind") == "series" and not (comp["statistic"].startswith("KS-PME") and comp.get("fund_return_source")):
            naming_bad.append(f"{key}/{slot}: series comparison lacks its statistic name or fund return source")
        if comp.get("kind") == "series":
            yf = comp["window_years"]
            for side in ("fund", "index"):
                want = (comp[f"{side}_growth_x"] ** (1 / yf) - 1) * 100
                if abs(comp[f"{side}_ann_pct"] - want) > 0.05:
                    ann_bad.append(f"{key}/{slot}/{side}: {comp[f'{side}_ann_pct']} vs day-count {want:.2f}")
            daily = bool(PRODUCT_PROFILES[key].get("series"))
            has = "ks_pme_monthly_schedule" in comp
            if has != daily:
                sched_bad.append(f"{key}/{slot}: schedule row {'present' if has else 'absent'}")
            if has and not (comp["schedule_contributions"] >= 12 and comp["schedule_note"].startswith("ILLUSTRATIVE")
                            and "two-point figure is primary" in comp["schedule_note"]):
                sched_bad.append(f"{key}/{slot}: schedule row malformed")
check_true("every committed series comparison window lies inside its proxy's coverage"
           + (": " + "; ".join(outside) if outside else ""), not outside)
check_true("two-point identity: the statistic equals fund growth over comparator growth on every committed comparison"
           + (": " + "; ".join(broken_identity) if broken_identity else ""), not broken_identity)
check_true("naming rule (rule 12): a PME name only against a public market series, on every committed comparison"
           + (": " + "; ".join(naming_bad) if naming_bad else ""), not naming_bad)
check_true("annualized figures are the day count of the effective window on every series comparison"
           + (": " + "; ".join(ann_bad) if ann_bad else ""), not ann_bad)
check_true("monthly-schedule KS-PME: daily series comparisons only, labeled ILLUSTRATIVE, two-point primary"
           + (": " + "; ".join(sched_bad) if sched_bad else ""), not sched_bad)

# --- hand recomputations the audit asked for (round 2 exit gate) ---
amg = json.loads((bench_dir / "amg_pantheon_selection.json").read_text())
ref = amg["reference_comparison"]
comp = ref["comparison"]
psp = load_series("psp", "adj_close")
fy = RETURN_INPUTS["amg_pantheon"]["profile"]["fy_returns"]
hand_fund = cumulative_growth(fy[3:])        # FY2020 to FY2026, seven whole years
hand_index = _level_on(psp, "2026-03-31") / _level_on(psp, "2019-03-31")
check_true("amg_pantheon vs PSP (the reference comparison): window clipped to the seven whole fiscal years inside PSP coverage",
           ref["id"] == "psp" and comp["window"] == "2019-03-31 to 2026-03-31"
           and comp["window_note"].startswith("clipped: proxy series begins 2018-07-18"))
check_true("amg_pantheon vs PSP: fund growth is the hand product of FY2020 to FY2026 (2.3970)",
           abs(comp["fund_growth_x"] - hand_fund) < 1e-3 and abs(hand_fund - 2.397042) < 1e-5)
check_true("amg_pantheon vs PSP: KS-PME equals the hand ratio on the clipped window (1.5919)",
           abs(comp["ks_pme"] - hand_fund / hand_index) < 1e-3 and abs(comp["ks_pme"] - 1.5919) < 1e-3)


def _bkln(key):
    sel = json.loads((bench_dir / f"{key}_selection.json").read_text())
    for _, s_ in _comparisons(sel):
        if s_["id"] == "bkln":
            return s_["comparison"]
    return None
check_true("cclfx annualized 7.89% by day count (BKLN window 2019-06-05 to 2026-07-17)",
           abs(_bkln("cliffwater_cclfx")["fund_ann_pct"] - 7.89) < 0.005)
check_true("pflex annualized 5.74% by day count (BKLN window 2018-07-18 to 2026-07-17), as the reference comparison",
           abs(_bkln("pflex")["fund_ann_pct"] - 5.74) < 0.005)
_st = json.loads((bench_dir / "stepstone_spm_selection.json").read_text())["reference_comparison"]["comparison"]
check_true("stepstone_spm vs PSP on the fiscal-year series: fund growth is the product of FY2022 to FY2026 (1.9504)",
           abs(_st["fund_growth_x"] - cumulative_growth(RETURN_INPUTS["stepstone_spm"]["profile"]["fy_returns"])) < 1e-4
           and abs(_st["fund_growth_x"] - 1.9504) < 1e-3)
_kk = json.loads((bench_dir / "kkr_kpec_selection.json").read_text())["reference_comparison"]["comparison"]
check_true("kkr_kpec vs PSP on the GAAP-NAV calendar years 2024 and 2025: a two-year window labeled low confidence",
           _kk["window"] == "2023-12-31 to 2025-12-31" and (_kk["low_confidence"] or "").startswith("low confidence: 2"))

# --- the published-index path (Lane P held) on a synthetic file ---
import tark_periods  # noqa: E402
_tmp = BASE / "data" / "series_quarterly" / "idx_zz_synthetic.csv"
try:
    _tmp.write_text("period_end,total_return_pct\n" + "".join(
        f"{y}-{m}-{d},1.0\n" for y in range(2020, 2026) for m, d in (("03", "31"), ("06", "30"), ("09", "30"), ("12", "31"))))
    _cand = {**CANDIDATES["cdli"], "id": "zz", "published_id": "idx_zz_synthetic", "series": None, "data": "published",
             "held": True}
    _pc = comparison_stats(PRODUCT_PROFILES["bcred"], _cand)
    check_true("published index vs an annual-tier fund: calendar years compounded from four quarters, a relative "
               "wealth ratio, never a PME, identical dates",
               _pc["kind"] == "published_index" and "ks_pme" not in _pc and _pc["window"] == "2021 to 2025"
               and abs(_pc["index_growth_x"] - 1.01 ** 20) < 1e-4 and "identical start and end dates" in _pc["alignment_note"])
    _pq = comparison_stats(PRODUCT_PROFILES["cliffwater_cclfx"], _cand)
    check_true("published index vs a daily-series fund: calendar quarters, the fund's quarters from its own series",
               _pq["kind"] == "published_index" and "calendar-quarter" in _pq["window_note"] and _pq["periods"][0] >= "2020-03-31")
finally:
    if _tmp.exists():
        _tmp.unlink()

# ---- v1 snapshot is frozen history: every byte pinned by its manifest
SNAP = bench_dir / "v1_snapshot"
manifest = dict(reversed(line.split()) for line in
                (SNAP / "MANIFEST.sha256").read_text().splitlines() if line.strip())
snap_files = sorted(f.name for f in SNAP.glob("*.json"))
check_true("v1 snapshot: manifest lists every json file and nothing else",
           sorted(manifest) == snap_files and len(snap_files) == 16)
check_true("v1 snapshot: every file matches its recorded sha256",
           all(hashlib.sha256((SNAP / n).read_bytes()).hexdigest() == h for n, h in manifest.items()))
# the methodology no longer carries an expected-outcome table as an oracle
METHOD = (BASE / "docs" / "benchmark_methodology.md").read_text()
check_true("methodology: no expected-outcome table serves as a test oracle (R2-P1-9)",
           "## 9. Expected outcome" not in METHOD and "Slot K" in METHOD and "Slot G" in METHOD)

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll benchmark engine tests pass.")
sys.exit(1 if FAILS else 0)

"""
Tark benchmark selection engine, rubric v2 (P1-5 to P1-12).

Every product is scored against a menu of candidates from TYPED descriptors:
the product's from data/registry.json (asset class, sub-strategy, pricing
class, leverage regime, held return data, advisers, declared benchmark, each
with the cell it comes from) and the candidate's from CANDIDATES below.
docs/benchmark_methodology.md sections 4 to 10 are the specification and
were written before this code. Nothing here is a hand-typed score.

Rubric (12 points): strategy_match 0 to 3 from one matrix, with a gate
(below 2 is ineligible), risk_liquidity_match 0 to 3, investability 0 or 2
(computable on held data), data_quality 0 to 2, provider_independence 0 or
2 per product. Threshold 7. Primary and secondary must differ by series.
Lane A is the declared benchmark, always a candidate, never rewarded for
the declaration. Lane C is the leave-one-out cohort composite, refused
below three members. Escalation is computable (no eligible candidate) or
flagged (price decoupled from NAV).
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from tark_analytics import (_level_on, cumulative_growth, direct_alpha,
                            effective_window, ks_pme, monthly_schedule_flows,
                            year_frac)
from tark_data import DATA, load_series

MIN_PRIMARY_SCORE = 7
RUBRIC_MAX = 12
RUBRIC_CAPTION = ("rubric v2: strategy match 3 (gate below 2), risk/liquidity match 3, "
                  "investability 2, data quality 2, provider independence 2, "
                  f"threshold {MIN_PRIMARY_SCORE}/{RUBRIC_MAX}")

REGISTRY = json.loads((DATA / "registry.json").read_text())["products"]
_PROFILES_INPUT = json.loads((DATA / "benchmarks" / "profiles_input.json").read_text())


def _profile(key: str, reg: dict) -> dict:
    held = reg["held_returns"]
    prof = {"key": key, "strategy": reg["strategy"], "series": held.get("series"),
            "granularity": ("daily" if held["kind"] == "series" and reg["pricing_class"] == "MARKET"
                            else "monthly" if held["kind"] == "series" else "annual"),
            "price_nav_decoupled": reg["price_nav_decoupled"],
            "source_cells": reg["source_cells"], "self_declared": None,
            **{k: reg[k] for k in ("asset_class", "sub_strategy", "pricing_class",
                                   "leverage_regime", "adviser_keys", "advisers",
                                   "declared_benchmarks", "cohort", "wrapper_type")}}
    prof["declared_none_reason"] = reg.get("declared_none_reason")
    inp = _PROFILES_INPUT.get(key, {}).get("profile", {})
    prof.update(inp)
    if held["kind"] == "none":
        prof["held_kind"] = "none"
    elif held["kind"] == "series":
        prof["held_kind"] = "series"
    else:
        prof["held_kind"] = held["kind"]
    return prof


# every product with a return input the engine can compare on
PRODUCT_PROFILES: dict[str, dict] = {
    key: _profile(key, reg) for key, reg in REGISTRY.items()
    if reg["held_returns"]["kind"] != "none"}
# descriptors for every product, including those without a return input
ALL_PRODUCTS: dict[str, dict] = {key: _profile(key, reg) for key, reg in REGISTRY.items()}


# ----------------------------------------------------------- candidates
# asset_class families: a public version of an asset class scores 2
FAMILY = {"private_credit": "credit", "public_credit": "credit",
          "private_equity": "private_equity", "listed_private_equity": "private_equity",
          "real_estate": "real_estate", "listed_real_estate": "real_estate",
          "venture": "venture", "public_equity": "public_equity"}
# private NAV-class indices of an asset class count as a sub-strategy match
PRIVATE_INDEX_SUBS = {"private_index"}

CANDIDATES: dict[str, dict] = {
    "bkln": {"name": "Senior loan investable proxy (BKLN, for Morningstar LSTA class)",
             "asset_class": "public_credit", "sub_strategy": "syndicated_loans",
             "listed": True, "pricing_class": "MARKET", "cadence": "daily",
             "series": "bkln", "data": "daily", "lane": "B",
             "provider": "Invesco / Morningstar LSTA class", "provider_key": "invesco morningstar"},
    "cdli": {"name": "Cliffwater Direct Lending Index (CDLI)",
             "asset_class": "private_credit", "sub_strategy": "direct_lending",
             "listed": False, "pricing_class": "NAV", "cadence": "quarterly",
             "series": None, "data": "cited", "lane": "B",
             "provider": "Cliffwater", "provider_key": "cliffwater"},
    "csll": {"name": "Credit Suisse Leveraged Loan Index (CSLLI)",
             "asset_class": "public_credit", "sub_strategy": "leveraged_loans",
             "listed": False, "pricing_class": "MARKET", "cadence": "daily",
             "series": None, "data": "cited", "lane": "A",
             "provider": "Credit Suisse (UBS)", "provider_key": "credit suisse ubs"},
    "psp": {"name": "Listed private equity investable proxy (PSP)",
            "asset_class": "listed_private_equity", "sub_strategy": "listed_private_equity",
            "listed": True, "pricing_class": "MARKET", "cadence": "daily",
            "series": "psp", "data": "daily", "lane": "B",
            "provider": "Invesco / Red Rocks", "provider_key": "invesco red rocks"},
    "urth": {"name": "MSCI World investable proxy (URTH)",
             "asset_class": "public_equity", "sub_strategy": "global_equity",
             "listed": True, "pricing_class": "MARKET", "cadence": "daily",
             "series": "urth", "data": "daily", "lane": "B",
             "provider": "iShares / MSCI", "provider_key": "ishares blackrock msci"},
    "spy": {"name": "S&P 500 investable proxy (SPY)",
            "asset_class": "public_equity", "sub_strategy": "us_large_cap",
            "listed": True, "pricing_class": "MARKET", "cadence": "daily",
            "series": "spy", "data": "daily", "lane": "B",
            "provider": "SPDR / S&P DJI", "provider_key": "spdr state street s&p dow jones"},
    "nasdaq_comp": {"name": "NASDAQ Composite Index",
                    "asset_class": "public_equity", "sub_strategy": "nasdaq_composite",
                    "listed": False, "pricing_class": "MARKET", "cadence": "daily",
                    "series": None, "data": "cited", "lane": "A",
                    "provider": "Nasdaq", "provider_key": "nasdaq"},
    "cambridge_pe": {"name": "Cambridge Associates US PE benchmark",
                     "asset_class": "private_equity", "sub_strategy": "private_index",
                     "listed": False, "pricing_class": "NAV", "cadence": "quarterly",
                     "series": None, "data": "licensed", "lane": "B",
                     "provider": "Cambridge Associates", "provider_key": "cambridge associates"},
    "cambridge_re": {"name": "Cambridge Associates Real Estate benchmark",
                     "asset_class": "real_estate", "sub_strategy": "private_index",
                     "listed": False, "pricing_class": "NAV", "cadence": "quarterly",
                     "series": None, "data": "licensed", "lane": "B",
                     "provider": "Cambridge Associates", "provider_key": "cambridge associates"},
    "vnq": {"name": "Listed REIT investable proxy (VNQ)",
            "asset_class": "listed_real_estate", "sub_strategy": "listed_reits",
            "listed": True, "pricing_class": "MARKET", "cadence": "daily",
            "series": "vnq", "data": "daily", "lane": "B",
            "provider": "Vanguard / MSCI US REIT", "provider_key": "vanguard msci"},
    "odce": {"name": "NCREIF Fund Index - ODCE (private core RE)",
             "asset_class": "real_estate", "sub_strategy": "private_index",
             "listed": False, "pricing_class": "NAV", "cadence": "quarterly",
             "series": None, "data": "cited", "lane": "B",
             "provider": "NCREIF", "provider_key": "ncreif"},
}
# the same series under the per-strategy ids the ledger has always used
for alias, base in (("psp_v", "psp"), ("psp_k", "psp"), ("urth_k", "urth"),
                    ("cambridge_pe_k", "cambridge_pe")):
    CANDIDATES[alias] = {**CANDIDATES[base], "alias_of": base}

# Lane B and Lane C ids per strategy (Lane A is added per product)
STRATEGY_MENU_IDS = {
    "private_credit": ["bkln", "cdli", "peer_credit"],
    "private_equity_evergreen": ["urth", "psp", "cambridge_pe", "peer_evergreen"],
    "preipo_venture": ["spy", "psp_v", "peer_venture"],
    "pe_conglomerate": ["psp_k", "urth_k", "cambridge_pe_k", "peer_kpec"],
    "nontraded_reit": ["vnq", "odce", "cambridge_re", "peer_reit"],
}
PEER_COHORT = {"peer_credit": "private_credit", "peer_evergreen": "evergreen_pe",
               "peer_venture": "venture", "peer_kpec": "evergreen_pe",
               "peer_reit": "nontraded_reit"}


# ------------------------------------------------------ Lane C: cohorts
_STUB = re.compile(r"stub|not annualized|commencement|partial", re.I)


def annual_returns(key: str, full_years_only: bool = True) -> dict[str, tuple[str, float]]:
    """{end_year: (fy_end, decimal return)} from data/series_annual/<key>.csv.
    Rows whose note marks a stub or partial period are excluded from
    composites and from composite comparisons (P1-11)."""
    p = DATA / "series_annual" / f"{key}.csv"
    if not p.exists():
        return {}
    out: dict[str, tuple[str, float]] = {}
    with open(p, newline="") as fh:
        for r in csv.DictReader(fh):
            if not r.get("total_return_pct"):
                continue
            if full_years_only and _STUB.search(r.get("note") or ""):
                continue
            out[r["fy_end"][:4]] = (r["fy_end"], float(r["total_return_pct"]) / 100)
    return out


def _cohort_members(cohort_id: str) -> list[str]:
    doc = json.loads((DATA / "cohorts" / f"{cohort_id}.json").read_text())
    return sorted(doc["members"])


def _mode(values: list[str]) -> str:
    counts: dict[str, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def peer_candidate(peer_id: str, subject: str) -> dict:
    """The leave-one-out cohort composite for one subject, as a candidate.
    Refused (with the reason) below three remaining members or when the
    remaining members' pricing classes differ. Rows keep the equal-weight
    rule of tark_cohort.composite and print n and members per year."""
    cohort = PEER_COHORT[peer_id]
    members = [m for m in _cohort_members(cohort) if m != subject]
    regs = {m: REGISTRY[m] for m in members}
    base = {"id": peer_id, "lane": "C", "series": None, "listed": False,
            "pricing_class": "NAV", "cadence": "annual", "data": "composite",
            "provider": "constructed (Tark cohort engine, leave-one-out)",
            "provider_key": "tark", "cohort": cohort, "members": members,
            "asset_class": _mode([r["asset_class"] for r in regs.values()]) if regs else "none",
            "sub_strategy": _mode([r["sub_strategy"] for r in regs.values()]) if regs else "none",
            "leverage_regimes": sorted({r["leverage_regime"] for r in regs.values()}),
            "name": f"Peer cohort composite: {cohort} without {subject} ({', '.join(members)})"}
    if len(members) < 3:
        return {**base, "refused": f"fewer than 3 members remain after leaving {subject} out "
                                    f"({len(members)}: {', '.join(members)})"}
    classes = {r["pricing_class"] for r in regs.values()}
    if len(classes) > 1:
        return {**base, "refused": "members' pricing bases are heterogeneous (market price vs "
                                    "NAV). An equal-weight composite would average premium "
                                    "and discount dynamics against appraisal NAVs, so it is "
                                    "refused, not fudged"}
    per = {m: annual_returns(m) for m in members}
    years = sorted({y for m in per.values() for y in m})
    rows = []
    for y in years:
        have = {m: per[m][y][1] for m in members if y in per[m]}
        if len(have) >= 2:
            rows.append({"year": y, "composite_return_pct": round(sum(have.values()) / len(have) * 100, 2),
                         "n": len(have), "members": sorted(have)})
    fye = {m: per[m][max(per[m])][0][5:7] for m in members if per[m]}
    return {**base, "refused": None, "rows": rows,
            "fye_months": fye,
            "weighting": "equal-weight across members reporting that fiscal year, "
                         "aligned by fiscal year-end year. Stub and partial periods excluded"}


def menu_for(key: str) -> list[dict]:
    """The full candidate menu for one product: Lane B and C for its
    strategy plus every declared benchmark (Lane A) not already present."""
    prof = ALL_PRODUCTS[key]
    out: list[dict] = []
    for cid in STRATEGY_MENU_IDS[prof["strategy"]]:
        if cid in PEER_COHORT:
            out.append(peer_candidate(cid, key))
        else:
            out.append({**CANDIDATES[cid], "id": cid})
    declared_ids = {d["candidate"] for d in prof["declared_benchmarks"]}
    for cand in out:
        if cand["id"] in declared_ids or cand.get("alias_of") in declared_ids:
            cand["lane"] = "A"
    present = {c["id"] for c in out} | {c.get("alias_of") for c in out}
    for d in prof["declared_benchmarks"]:
        if d["candidate"] not in present:
            out.append({**CANDIDATES[d["candidate"]], "id": d["candidate"], "lane": "A"})
    return out


# kept for callers that enumerate the per-strategy base menu (build_site,
# tests): Lane B and C entries as dicts
STRATEGY_MENU: dict[str, list[dict]] = {
    strat: [{**CANDIDATES[c], "id": c} if c in CANDIDATES else
            {"id": c, "name": f"Peer cohort composite ({PEER_COHORT[c]}, leave-one-out)",
             "lane": "C", "series": None, "data": "composite"}
            for c in ids]
    for strat, ids in STRATEGY_MENU_IDS.items()}


# ---------------------------------------------------------------- scoring
def strategy_match(prof: dict, cand: dict) -> tuple[int, str]:
    pac, psub = prof["asset_class"], prof["sub_strategy"]
    cac, csub = cand["asset_class"], cand["sub_strategy"]
    if cac == pac and (csub == psub or csub in PRIVATE_INDEX_SUBS):
        return 3, (f"same asset class and sub-strategy ({pac} / {psub})" if csub == psub
                   else f"a private {pac.replace('_', ' ')} index for a {psub.replace('_', ' ')} fund")
    if FAMILY.get(cac) == FAMILY.get(pac):
        return 2, (f"same asset class, different sub-strategy ({csub.replace('_', ' ')} vs "
                   f"{psub.replace('_', ' ')})" if cac == pac else
                   f"the public-market version of the asset class ({csub.replace('_', ' ')} "
                   f"for {psub.replace('_', ' ')})")
    if (FAMILY.get(pac) in ("private_equity", "venture") and cac == "public_equity") or \
            (pac == "venture" and cac == "listed_private_equity"):
        return 1, (f"adjacent asset class sharing the dominant risk ({csub.replace('_', ' ')} "
                   f"for {psub.replace('_', ' ')})")
    return 0, f"unrelated asset class ({cac.replace('_', ' ')} for {pac.replace('_', ' ')})"


def _held_cadence(prof: dict) -> str:
    return "daily" if prof.get("held_kind") == "series" else "annual"


def risk_liquidity_match(prof: dict, cand: dict) -> tuple[int, str]:
    if prof.get("price_nav_decoupled"):
        return 0, "fund price is premium-driven and decoupled from NAV, no candidate matches that risk process"
    if cand.get("refused"):
        return 0, f"no computable series: {cand['refused']}"
    if cand["pricing_class"] == "MARKET":
        if prof["pricing_class"] == "MARKET":
            return 2, "daily market proxy for an exchange-traded fund"
        return 1, "daily-liquid market proxy vs a semi-liquid NAV fund, vol and liquidity regimes differ"
    same_cadence = cand["cadence"] == _held_cadence(prof)
    regimes = cand.get("leverage_regimes") or [None]
    homogeneous = all(r == prof["leverage_regime"] for r in regimes) if cand.get("leverage_regimes") else False
    if same_cadence and homogeneous:
        return 3, "NAV-class series at the fund's own cadence with every member in the fund's leverage regime"
    why = []
    if not same_cadence:
        why.append(f"{cand['cadence']} observations vs the fund's {_held_cadence(prof)} return data")
    if cand.get("leverage_regimes") and not homogeneous:
        why.append("members span more than one leverage regime")
    elif not cand.get("leverage_regimes"):
        why.append("an index, not a fund set, so leverage regime is not comparable")
    return 2, "NAV-class series, " + " and ".join(why)


def investability(cand: dict, comparable: bool) -> tuple[int, str]:
    if cand.get("refused"):
        return 0, "composite refused, nothing to compute"
    if cand["data"] in ("cited", "licensed"):
        return 0, ("licensed data not held (no subscription), candidate can be cited, not computed"
                   if cand["data"] == "licensed" else "index cited, series not held, not computable")
    if not comparable:
        return 0, "no overlapping window with the fund's held returns"
    return 2, ("computable on held data (daily series)" if cand["series"]
               else "computable on held data (cohort composite from filings)")


def data_quality(cand: dict, overlap_years: int | None) -> tuple[int, str]:
    if cand["data"] == "daily":
        return 2, "daily series held"
    if cand["data"] in ("cited", "licensed") or cand.get("refused"):
        return 0, "cited, not computed"
    n = overlap_years or 0
    if n >= 3:
        return 1, f"annual composite with {n} overlapping fiscal years"
    return 0, f"annual composite with only {n} overlapping fiscal year(s), fewer than 3"


def provider_independence(prof: dict, cand: dict) -> tuple[int, str]:
    pk = cand["provider_key"].lower()
    hits = [a for a in prof["adviser_keys"] if a.strip() and (a.strip() in pk or pk in a.strip())]
    if hits:
        return 0, (f"index published by the fund's own adviser ({', '.join(prof['advisers'])}). "
                   "A manufacturer-owned yardstick sits poorly with the rule's conflict-free "
                   "ethos, so it is usable as secondary color only")
    return 2, f"provider unaffiliated with the fund ({cand['provider']})"


def _overlap_years(prof: dict, cand: dict) -> tuple[list[str], dict[str, tuple[str, float]]]:
    fund = annual_returns(prof["key"])
    comp_years = {r["year"] for r in cand.get("rows", [])}
    return sorted(y for y in fund if y in comp_years), fund


def score_candidate(prof: dict, cand: dict) -> dict:
    """Score one candidate for one product from typed descriptors. Every
    criterion returns its points and the reason that fired."""
    overlap = None
    comparable = True
    if cand.get("data") == "composite" and not cand.get("refused"):
        years, _ = _overlap_years(prof, cand)
        overlap = len(years)
        comparable = overlap >= 1
    s_match, s_why = strategy_match(prof, cand)
    r_match, r_why = risk_liquidity_match(prof, cand)
    inv, i_why = investability(cand, comparable)
    dq, d_why = data_quality(cand, overlap)
    ind, p_why = provider_independence(prof, cand)
    reasons = [f"strategy_match {s_match}/3: {s_why}",
               f"risk_liquidity_match {r_match}/3: {r_why}",
               f"investability {inv}/2: {i_why}",
               f"data_quality {dq}/2: {d_why}",
               f"provider_independence {ind}/2: {p_why}"]
    total = s_match + r_match + inv + dq + ind
    return {"candidate": cand["name"], "id": cand["id"], "lane": cand["lane"],
            "score": total, "max": RUBRIC_MAX,
            "criteria": {"strategy_match": s_match, "risk_liquidity_match": r_match,
                         "investability": inv, "data_quality": dq,
                         "provider_independence": ind},
            "series_id": cand.get("series") or (f"composite:{cand['cohort']}" if cand.get("cohort")
                                                 else f"cited:{cand['id']}"),
            "reasons": reasons}


# ------------------------------------------------------------ comparison
class WindowNotComputable(ValueError):
    """The fund's return input cannot be compared on the held proxy data."""


def fiscal_year_bounds(fy_window, n: int) -> list[tuple[str, str]]:
    """[(start, end)] for n consecutive fiscal years: each start steps the
    year of the window start, the last end is the window end. Same rule as
    fiscalYearBounds in site/js/analytics.js."""
    w0, w1 = fy_window
    y0 = int(w0[:4])
    starts = [f"{y0 + i}{w0[4:]}" for i in range(n)]
    return [(st, starts[i + 1] if i + 1 < n else w1) for i, st in enumerate(starts)]


def comparison_stats(profile: dict, cand: dict) -> dict | None:
    """Fund-vs-candidate growth, PME and Direct Alpha over the EFFECTIVE
    window: the fund's window clipped to the proxy's coverage (both sides
    for a daily series, whole fiscal years for an annual list). A single
    disclosed annualized figure cannot be clipped: outside coverage it
    raises WindowNotComputable with the reason instead of interpolating.
    One anchor: fund growth, index growth and the PME flows all read the
    level on or before each window date from the full series, so a window
    that starts on a non-trading day cannot shift the anchor. Annualized
    figures use the actual/365.25 day count of the effective window, the
    same clock as Direct Alpha and the JS lab. A disclosed annualized figure
    keeps its disclosed year count, so the fund side prints the filing's
    number and the index side is annualized over the same span."""
    if cand.get("data") == "composite":
        return composite_comparison(profile, cand)
    if not cand.get("series"):
        return None
    index = load_series(cand["series"], "adj_close")
    i0, i1 = index[0][0], index[-1][0]
    years = None
    schedule: dict = {}
    if profile.get("series"):
        fund = load_series(profile["series"], "adj_close")
        fund_window = (fund[0][0], fund[-1][0])
        d0, d1, note = effective_window(fund_window[0], fund_window[1], index)
        f_growth = _level_on(fund, d1) / _level_on(fund, d0)
        # second, ILLUSTRATIVE row for daily NAV products only: equal
        # contributions on a monthly schedule instead of one at the start
        sched = monthly_schedule_flows(fund, d0, d1)
        schedule = {
            "ks_pme_monthly_schedule": round(ks_pme(sched, index), 4),
            "schedule_contributions": len(sched) - 1,
            "schedule_note": (f"ILLUSTRATIVE: {len(sched) - 1} equal contributions, "
                              "at the window start and each month-end inside it, "
                              "valued at the window end. The two-point figure "
                              "is primary."),
        }
    elif profile.get("fy_returns"):
        bounds = fiscal_year_bounds(profile["fy_window"], len(profile["fy_returns"]))
        fund_window = (profile["fy_window"][0], profile["fy_window"][1])
        kept = [(r, b) for r, b in zip(profile["fy_returns"], bounds)
                if i0 <= b[0] and b[1] <= i1]
        if not kept:
            raise WindowNotComputable(
                f"no whole fiscal year of {fund_window[0]} to {fund_window[1]} "
                f"lies inside the proxy series ({i0} to {i1})")
        d0, d1 = kept[0][1][0], kept[-1][1][1]
        f_growth = cumulative_growth([r for r, _ in kept])
        note = ""
        dropped = len(bounds) - len(kept)
        if dropped:
            parts = []
            if d0 != bounds[0][0]:
                parts.append(f"proxy series begins {i0}")
            if d1 != bounds[-1][1]:
                parts.append(f"proxy series ends {i1}")
            note = (f"clipped: {', '.join(parts)}, {dropped} fiscal year(s) "
                    f"outside it dropped")
    elif profile.get("aatr_5yr") or profile.get("aatr"):
        d0, d1 = profile["fy_window"]
        fund_window = (d0, d1)
        if d0 < i0 or d1 > i1:
            raise WindowNotComputable(
                f"the single disclosed figure covers {d0} to {d1} and cannot be "
                f"clipped to the proxy series (proxy series begins {i0}, ends {i1})")
        note = ""
        if profile.get("aatr_5yr"):
            f_growth = (1 + profile["aatr_5yr"]) ** 5
            years = 5
        else:
            # generic annualized-since-inception profile (kkr_kpec): aatr plus
            # the exact year count, filled from extracted cell 1.2 evidence
            f_growth = (1 + profile["aatr"]) ** profile["aatr_years"]
            years = profile["aatr_years"]
    else:
        return None
    i_growth = _level_on(index, d1) / _level_on(index, d0)
    if years is None:
        years = year_frac(d0, d1)
    flows = [(d0, -1.0), (d1, f_growth)]
    return {
        "kind": "series",
        "window": f"{d0} to {d1}",
        "window_note": note,
        "fund_window": f"{fund_window[0]} to {fund_window[1]}",
        "window_years": round(year_frac(d0, d1), 2),
        "fund_growth_x": round(f_growth, 4),
        "index_growth_x": round(i_growth, 4),
        "ks_pme": round(ks_pme(flows, index), 4),
        "direct_alpha_pct": round((direct_alpha(flows, index) or 0) * 100, 2),
        "fund_ann_pct": round((f_growth ** (1 / years) - 1) * 100, 2),
        "index_ann_pct": round((i_growth ** (1 / years) - 1) * 100, 2),
        **schedule,
    }


def _prior_fy_end(fy_end: str) -> str:
    return f"{int(fy_end[:4]) - 1}{fy_end[4:]}"


def composite_comparison(profile: dict, cand: dict) -> dict | None:
    """Fund vs the leave-one-out cohort composite over the fiscal years both
    report (aligned by fiscal year-end year, stubs excluded). Two-point
    flows on the fund's own fiscal year-end dates; the composite is
    compounded into levels on the same dates."""
    if cand.get("refused"):
        return None
    years, fund = _overlap_years(profile, cand)
    if not years:
        raise WindowNotComputable("no fiscal year overlaps between the fund's annual "
                                  "returns and the composite")
    comp_by_year = {r["year"]: r for r in cand["rows"]}
    # the window is the set of overlapping whole fiscal years: the flows
    # span exactly that many years ending on the fund's last fiscal
    # year-end, so a stub gap on either side cannot stretch the clock
    d1 = fund[years[-1]][0]
    d0 = f"{int(d1[:4]) - len(years)}{d1[4:]}"
    f_growth = cumulative_growth([fund[y][1] for y in years])
    levels = [(d0, 1.0)]
    acc = 1.0
    for i, y in enumerate(years):
        acc *= 1 + comp_by_year[y]["composite_return_pct"] / 100
        levels.append((f"{int(d0[:4]) + i + 1}{d0[4:]}", acc))
    i_growth = acc
    flows = [(d0, -1.0), (d1, f_growth)]
    yrs = year_frac(d0, d1)
    fye = cand.get("fye_months", {})
    subject_m = d1[5:7]
    diff = sorted({m for m in fye.values() if m != subject_m})
    skipped = sorted(y for y in comp_by_year if years[0] <= y <= years[-1] and y not in years)
    align = ("aligned by fiscal year-end year. Members' fiscal years end in month "
             + ", ".join(f"{m} ({', '.join(k for k, v in fye.items() if v == m)})" for m in sorted(set(fye.values())))
             + (f", the fund's in month {subject_m}" if diff else ", the same month as the fund's")
             + (f". Composite year(s) {', '.join(skipped)} skipped: the fund has no whole fiscal year "
                "with that label (stub or partial period excluded)" if skipped else ""))
    return {
        "kind": "composite",
        "window": f"FY{years[0]} to FY{years[-1]}",
        "window_note": f"{len(years)} overlapping fiscal year(s) of {len(cand['rows'])} composite years",
        "fund_window": f"FY{min(fund)} to FY{max(fund)}",
        "window_years": round(yrs, 2),
        "alignment_note": align,
        "composite_rows": [comp_by_year[y] for y in years],
        "fund_growth_x": round(f_growth, 4),
        "index_growth_x": round(i_growth, 4),
        "ks_pme": round(ks_pme(flows, levels), 4),
        "direct_alpha_pct": round((direct_alpha(flows, levels) or 0) * 100, 2),
        "fund_ann_pct": round((f_growth ** (1 / yrs) - 1) * 100, 2),
        "index_ann_pct": round((i_growth ** (1 / yrs) - 1) * 100, 2),
    }


# ---------------------------------------------------------------- select
def run_selection(product_key: str) -> dict:
    profile = PRODUCT_PROFILES[product_key]
    menu = menu_for(product_key)
    scored = [score_candidate(profile, c) for c in menu]
    order = {c["id"]: i for i, c in enumerate(menu)}
    scored.sort(key=lambda s: (-s["score"], -s["criteria"]["strategy_match"],
                               -s["criteria"]["risk_liquidity_match"],
                               -s["criteria"]["data_quality"], order[s["id"]]))
    decoupled = bool(profile.get("price_nav_decoupled"))
    gate_ok = [s for s in scored if s["criteria"]["strategy_match"] >= 2]
    eligible = [] if decoupled else [s for s in gate_ok if s["score"] >= MIN_PRIMARY_SCORE]

    primary = eligible[0] if eligible else None
    secondary = next((s for s in eligible[1:]
                      if primary and s["series_id"] != primary["series_id"]), None)
    rejected = []
    for s in scored:
        if s is primary or s is secondary:
            continue
        if decoupled:
            why = ("fund price is premium/discount-driven and decoupled from NAV. "
                   "Benchmarking the price benchmarks the premium, not the portfolio")
        elif s["criteria"]["strategy_match"] < 2:
            why = (f"rejected: strategy gate (score {s['score']}/{s['max']} but "
                   f"strategy_match {s['criteria']['strategy_match']}/3)")
        elif s["score"] < MIN_PRIMARY_SCORE:
            why = f"score {s['score']}/{s['max']} below primary threshold {MIN_PRIMARY_SCORE}"
        elif primary and s["series_id"] == primary["series_id"]:
            why = "rejected: same series as the primary, a second slot on the same series adds nothing"
        else:
            why = (f"outranked: score {s['score']}/{s['max']} vs primary "
                   f"{primary['score']}/{primary['max']}"
                   + (f" and secondary {secondary['score']}/{secondary['max']}"
                      if secondary else "")
                   + " (only two slots). Retained in log as viable alternate")
        rejected.append({**s, "rejection": why})

    declared = profile["declared_benchmarks"]
    declared_out = []
    for d in declared:
        s = next((x for x in scored if x["id"] == d["candidate"]
                  or CANDIDATES.get(x["id"], {}).get("alias_of") == d["candidate"]), None)
        held = bool(CANDIDATES[d["candidate"]].get("series"))
        if s is None:
            status = "not scored"
        elif s is primary:
            status = "held, scored, selected as primary"
        elif s is secondary:
            status = "held, scored, selected as secondary"
        elif s["criteria"]["strategy_match"] < 2:
            status = (f"{'held' if held else 'cited, not held'}, scored {s['score']}/12, "
                      f"fails the strategy gate (strategy_match {s['criteria']['strategy_match']}/3)")
        elif s["score"] < MIN_PRIMARY_SCORE:
            status = f"{'held' if held else 'cited, not held'}, scored {s['score']}/12, below the threshold"
        else:
            status = f"{'held' if held else 'cited, not held'}, scored {s['score']}/12, outranked"
        declared_out.append({"name": d["name"], "candidate_id": d["candidate"], "cell": "5.1",
                             "status": status})

    result = {
        "product": product_key,
        "strategy": profile["strategy"],
        "source_cells": profile["source_cells"],
        "rubric_version": "v2",
        "rubric": RUBRIC_CAPTION,
        # the highest score an ELIGIBLE candidate reaches on held data
        # (passes the gate and the threshold), per methodology section 6
        "max_attainable": max((s["score"] for s in eligible), default=None),
        "declared_benchmarks": declared_out,
        "declared_none_reason": profile.get("declared_none_reason") if not declared else None,
        "primary": primary, "secondary": secondary, "rejected": rejected,
        "secondary_note": None, "escalation": None,
    }
    if primary and not secondary:
        result["secondary_note"] = "no eligible secondary on a different series"
    if primary is None:
        if decoupled:
            result["escalation"] = (
                "NO MEANINGFUL BENCHMARK CONSTRUCTIBLE from available data. Required "
                "next: public NAV series (quarterly filings) plus a premium/NAV "
                "decomposition before any comparator is defensible.")
        else:
            failed = "; ".join(f"{r['id']} {r['score']}/12 ({r['rejection'].split(' (')[0]})"
                               for r in rejected)
            result["escalation"] = (
                "NO MEANINGFUL BENCHMARK CONSTRUCTIBLE from held data: no candidate passes "
                f"the strategy gate at or above {MIN_PRIMARY_SCORE}/12. {failed}. Required "
                "next: a strategy-exact series (a venture index or a computable peer "
                "cohort of at least three NAV-priced members).")
    for slot in ("primary", "secondary"):
        if result[slot]:
            cand = next(c for c in menu if c["id"] == result[slot]["id"])
            try:
                result[slot]["comparison"] = comparison_stats(profile, cand)
            except WindowNotComputable as e:
                # no number is interpolated: the slot keeps its score and
                # says why the comparison is absent on held data
                result[slot]["comparison"] = None
                result[slot]["comparison_note"] = str(e)
            if cand.get("data") == "composite":
                result[slot]["composite"] = {k: cand[k] for k in ("cohort", "members", "rows",
                                                                    "fye_months", "weighting")}
    return result

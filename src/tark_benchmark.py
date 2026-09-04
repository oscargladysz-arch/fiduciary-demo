"""
Tark benchmark selection & justification engine (M3) — v0
=========================================================
The moat module. Does NOT construct proprietary indices; it generates
candidates across four lanes, scores each against a rubric, selects primary /
secondary, and — the legally load-bearing half — logs every REJECTED candidate
with its reason. Index-agnostic by design (post BlackRock/Preqin).

Lanes:
    A self-declared      the fund's own stated benchmark (cell 5.1)
    B asset-class index  named indices incl. paid/manual ones we DON'T have —
                         they enter the menu and get rejected with reasons
                         (the honest audit trail beats silent omission)
    C peer cohort        built from our own product universe (cell 5.4)
    D pme_construct      PME / Direct Alpha vs a public investable proxy

Rubric (0-12): strategy_match 0-3 · risk_liquidity_match 0-3 ·
investability 0-2 · data_quality 0-2 · provider_independence 0-2.
Primary requires >= 7/12; otherwise the engine returns None and escalates —
"no meaningful benchmark constructible" is a legitimate, documented outcome.

v0 profiles are explicit dicts with source-cell citations (values already in
data/evidence/*). Wiring profiles straight from product JSONs is a later
increment; prose-parsing evidence strings would be brittle now.
"""
from __future__ import annotations

from tark_analytics import (_level_on, cumulative_growth, direct_alpha,
                            effective_window, ks_pme, monthly_schedule_flows,
                            year_frac)
from tark_data import load_series

MIN_PRIMARY_SCORE = 7

# ---------------------------------------------------------------- profiles
PRODUCT_PROFILES = {
    "cliffwater_cclfx": {
        "strategy": "private_credit",
        "series": "cclfx",                      # daily adj_close on disk
        "granularity": "monthly",
        "self_declared": None,   # cell 5.1: fund EXPRESSLY declares no benchmark
        "source_cells": ["5.1", "1.1", "1.2"],
    },
    "hl_paf": {
        "strategy": "private_equity_evergreen",
        "series": None,
        "granularity": "annual",
        # FY total returns FY22..FY26 (cell 1.2), fiscal year ends 3/31
        "fy_returns": [0.2077, 0.1610, 0.1268, 0.1259, 0.1460],
        "fy_window": ("2021-03-31", "2026-03-31"),
        "self_declared": "S&P 500 / MSCI World (N-CSR Fund Performance)",  # cell 5.1
        "source_cells": ["1.2", "5.1"],
    },
    "stepstone_spm": {
        "strategy": "private_equity_evergreen",
        "series": None,
        "granularity": "annual",
        # AATR-derived: SI 19.19% since 10/2020 (cell 1.2); use 5yr 12.92% window
        "fy_returns": None,
        "aatr_5yr": 0.1292,
        "fy_window": ("2021-03-31", "2026-03-31"),
        "self_declared": "MSCI World Index",    # cell 5.1
        "source_cells": ["1.2", "5.1"],
    },
    "dxyz": {
        "strategy": "preipo_venture",
        "series": "dxyz",
        "granularity": "daily",
        "self_declared": None,
        "price_nav_decoupled": True,            # cells 1.10 / 4.7: -90.3% DD,
        "source_cells": ["1.10", "4.7"],        # +188.6% cum, 162.6% vol
    },
    "ares_pmf": {
        "strategy": "private_equity_evergreen",
        "series": None, "granularity": "annual",
        "fy_returns": None, "fy_window": None,   # injected from profiles_input
        "self_declared": "see cell 5.1",
        "source_cells": ["1.2", "5.1"],
    },
    "amg_pantheon": {
        "strategy": "private_equity_evergreen",
        "series": None, "granularity": "annual",
        "fy_returns": None, "fy_window": None,   # injected (10 fiscal years)
        "self_declared": "see cell 5.1",
        "source_cells": ["1.2", "5.1"],
    },
    "sreit": {
        "strategy": "nontraded_reit",
        "series": None, "granularity": "annual",
        "fy_returns": None, "fy_window": None,   # injected (single printed year
                                                 # - SHORT window, disclosed)
        "self_declared": "see cell 5.1",
        "source_cells": ["1.2", "5.1"],
    },
    "arkvx": {
        "strategy": "preipo_venture",
        "series": "arkvx",
        "granularity": "monthly",
        "self_declared": "see cell 5.1",
        "source_cells": ["1.2", "5.1"],
    },
    "ssss": {
        "strategy": "preipo_venture",
        "series": "nslr",
        "granularity": "daily",
        "self_declared": "see cell 5.1",
        "price_nav_decoupled": True,   # listed BDC trading at persistent
                                       # discount/premium to NAV (cells 1.10/4.7)
        "source_cells": ["1.10", "5.1"],
    },
    "pflex": {
        "strategy": "private_credit",
        "series": "pflex",
        "granularity": "monthly",
        "self_declared": None,   # cell 5.1: documented absence (comparator
                                 # index shown in shareholder report is
                                 # expressly not a designated benchmark)
        "source_cells": ["5.1", "1.1", "1.2"],
    },
    "cion_ares": {
        "strategy": "private_credit",
        "series": "cadux",           # CLASS I daily NAV (ticker CADUX;
        "granularity": "monthly",    # CADCX is the Class C ticker)
        "self_declared": "Credit Suisse Leveraged Loan Index",  # cell 5.1
        "source_cells": ["5.1", "1.1", "1.2"],
    },
    # profiles below are filled by fill_profile_from_cells() at selection time
    # from the extracted 1.2 evidence (annualized since-inception, Class I) —
    # values injected by run_benchmark.py, never hard-coded here
    "bcred": {
        "strategy": "private_credit",
        "series": None,
        "granularity": "annual",
        "fy_returns": None, "fy_window": None,   # injected from profiles_input
        "self_declared": None,                    # cell 5.1: documented absence
        "source_cells": ["1.2", "5.1"],
    },
    "ocic": {
        "strategy": "private_credit",
        "series": None,
        "granularity": "annual",
        "fy_returns": None, "fy_window": None,   # injected from profiles_input
        "self_declared": None,                    # cell 5.1: documented absence
        "source_cells": ["1.2", "5.1"],
    },
    "kkr_kpec": {
        "strategy": "pe_conglomerate",
        "series": None,
        "granularity": "annual",
        "aatr": None, "aatr_years": None, "fy_window": None,
        "self_declared": None,                  # cell 5.1
        "source_cells": ["1.2", "5.1"],
    },
    "breit": {
        "strategy": "nontraded_reit",
        "series": None,
        "granularity": "annual",
        "aatr": None, "aatr_years": None, "fy_window": None,
        "self_declared": None,                  # cell 5.1
        "source_cells": ["1.2", "5.1"],
    },
}

# ------------------------------------------------------------- candidates
STRATEGY_MENU = {
    "private_credit": [
        {"id": "bkln", "name": "Senior loan investable proxy (BKLN, for Morningstar LSTA class)",
         "lane": "B", "series": "bkln", "provider": "Invesco / Morningstar LSTA class",
         "independent": True, "data": "daily", "strategy_match": 2,
         "match_note": "broadly syndicated loans vs direct lending (close cousin, not twin). "
                       "Fund itself declares NO benchmark (5.1), so the engine constructs one"},
        {"id": "cdli", "name": "Cliffwater Direct Lending Index (CDLI)",
         "lane": "B", "series": None, "provider": "Cliffwater (the Fund's own adviser)",
         "independent": False, "data": "quarterly-manual", "strategy_match": 3,
         "match_note": "direct lending - exact strategy match"},
        {"id": "peer_credit", "name": "Peer cohort: private_credit (cclfx, "
                                      "bcred, pflex, cion_ares, ocic)",
         "lane": "C", "series": None, "provider": "constructed (Tark cohort engine)",
         "independent": True, "data": "annual", "strategy_match": 3,
         "match_note": "n=5 equal-weight annual composite on printed FY "
                       "returns (data/cohorts/private_credit.json). "
                       "Cross-wrapper mix (interval + BDC) disclosed in the "
                       "cohort caveat block"},
        {"id": "pme_bkln", "name": "PME / Direct Alpha vs BKLN",
         "lane": "D", "series": "bkln", "provider": "constructed (Tark)",
         "independent": True, "data": "daily", "strategy_match": 2,
         "match_note": "wealth-ratio PME vs investable loan proxy"},
    ],
    "private_equity_evergreen": [
        {"id": "urth", "name": "MSCI World investable proxy (URTH)",
         "lane": "A/B", "series": "urth", "provider": "iShares / MSCI",
         "independent": True, "data": "daily", "strategy_match": 1,
         "match_note": "public equities - liquidity/leverage profile differs materially"},
        {"id": "psp", "name": "Listed private equity investable proxy (PSP)",
         "lane": "B", "series": "psp", "provider": "Invesco / Red Rocks",
         "independent": True, "data": "daily", "strategy_match": 2,
         "match_note": "listed GPs/holdcos - PE exposure with public-market beta"},
        {"id": "cambridge_pe", "name": "Cambridge Associates US PE benchmark",
         "lane": "B", "series": None, "provider": "Cambridge Associates",
         "independent": True, "data": "quarterly-paid", "strategy_match": 3,
         "match_note": "drawdown-fund universe - wrapper mismatch vs evergreen also applies"},
        {"id": "peer_evergreen", "name": "Peer cohort: evergreen_pe (hl_paf, "
                                         "stepstone_spm, kkr_kpec, ares_pmf, "
                                         "amg_pantheon)",
         "lane": "C", "series": None, "provider": "constructed (Tark cohort engine)",
         "independent": True, "data": "annual", "strategy_match": 3,
         "match_note": "n=5 equal-weight annual composite on printed FY returns "
                       "(data/cohorts/evergreen_pe.json). Fiscal year-ends "
                       "differ and kkr_kpec joins cross-wrapper under the "
                       "documented fallback, both disclosed in the caveat block"},
        {"id": "pme_psp", "name": "PME / Direct Alpha vs PSP",
         "lane": "D", "series": "psp", "provider": "constructed (Tark)",
         "independent": True, "data": "annual-window", "strategy_match": 2,
         "match_note": "wealth-ratio PME over the fund's fiscal window"},
    ],
    "preipo_venture": [
        {"id": "spy", "name": "S&P 500 investable proxy (SPY)",
         "lane": "B", "series": "spy", "provider": "SPDR / S&P DJI",
         "independent": True, "data": "daily", "strategy_match": 0,
         "match_note": "large-cap public equity - wrong asset class"},
        {"id": "psp_v", "name": "Listed private equity proxy (PSP)",
         "lane": "B", "series": "psp", "provider": "Invesco / Red Rocks",
         "independent": True, "data": "daily", "strategy_match": 1,
         "match_note": "nearest liquid cousin to pre-IPO exposure"},
        {"id": "peer_venture", "name": "Peer cohort: venture (dxyz, ssss, arkvx)",
         "lane": "C", "series": None, "provider": "constructed (Tark cohort engine)",
         "independent": True, "data": "none", "strategy_match": 3,
         "match_note": "n=3 but composite REFUSED: members' pricing bases are "
                       "heterogeneous (market price vs NAV) - averaging "
                       "premiums against appraisals would fabricate a series "
                       "(data/cohorts/venture.json)"},
    ],
    "pe_conglomerate": [
        {"id": "psp_k", "name": "Listed private equity investable proxy (PSP)",
         "lane": "B", "series": "psp", "provider": "Invesco / Red Rocks",
         "independent": True, "data": "daily", "strategy_match": 2,
         "match_note": "listed GPs/holdcos - closest liquid proxy for a "
                       "PE-conglomerate of controlled operating companies"},
        {"id": "urth_k", "name": "MSCI World investable proxy (URTH)",
         "lane": "B", "series": "urth", "provider": "iShares / MSCI",
         "independent": True, "data": "daily", "strategy_match": 1,
         "match_note": "public equities - liquidity/leverage profile differs "
                       "materially from private controlled businesses"},
        {"id": "cambridge_pe_k", "name": "Cambridge Associates US PE benchmark",
         "lane": "B", "series": None, "provider": "Cambridge Associates",
         "independent": True, "data": "quarterly-paid", "strategy_match": 3,
         "match_note": "drawdown-fund universe - wrapper mismatch vs perpetual "
                       "conglomerate also applies"},
        {"id": "peer_kpec", "name": "Peer cohort: evergreen PE funds in universe",
         "lane": "C", "series": None, "provider": "constructed",
         "independent": True, "data": "annual", "strategy_match": 2,
         "match_note": "hl_paf / stepstone_spm are fund-of-funds evergreens, "
                       "not conglomerates of controlled companies - inexact peers"},
        {"id": "pme_psp_k", "name": "PME / Direct Alpha vs PSP",
         "lane": "D", "series": "psp", "provider": "constructed (Tark)",
         "independent": True, "data": "annual-window", "strategy_match": 2,
         "match_note": "wealth-ratio PME over the fund's since-inception window"},
    ],
    "nontraded_reit": [
        {"id": "vnq", "name": "Listed REIT investable proxy (VNQ)",
         "lane": "B", "series": "vnq", "provider": "Vanguard / MSCI US REIT",
         "independent": True, "data": "daily", "strategy_match": 2,
         "match_note": "listed equity REITs - same asset class, but exchange "
                       "pricing vs monthly appraisal NAV is a regime difference"},
        {"id": "odce", "name": "NCREIF Fund Index - ODCE (private core RE)",
         "lane": "B", "series": None, "provider": "NCREIF",
         "independent": True, "data": "quarterly-manual", "strategy_match": 3,
         "match_note": "private open-end core RE funds, the strategy-exact "
                       "yardstick. Index data is member/subscription "
                       "distribution, series not held"},
        {"id": "cambridge_re", "name": "Cambridge Associates Real Estate benchmark",
         "lane": "B", "series": None, "provider": "Cambridge Associates",
         "independent": True, "data": "quarterly-paid", "strategy_match": 3,
         "match_note": "private RE drawdown-fund universe - licensed data not held"},
        {"id": "peer_reit", "name": "Peer cohort: nontraded_reit (breit, "
                                    "sreit, jll_ipt)",
         "lane": "C", "series": None, "provider": "constructed (Tark cohort engine)",
         "independent": True, "data": "annual", "strategy_match": 3,
         "match_note": "n=3. Equal-weight annual composite overlap currently "
                       "one year (2025: breit + sreit, while jll_ipt prints returns "
                       "only as per-class ranges). THIN, disclosed "
                       "(data/cohorts/nontraded_reit.json)"},
        {"id": "pme_vnq", "name": "PME / Direct Alpha vs VNQ",
         "lane": "D", "series": "vnq", "provider": "constructed (Tark)",
         "independent": True, "data": "annual-window", "strategy_match": 2,
         "match_note": "wealth-ratio PME vs listed-REIT proxy over the "
                       "since-inception window"},
    ],
}


# ---------------------------------------------------------------- scoring
def score_candidate(profile: dict, cand: dict) -> dict:
    reasons = []
    s_match = cand["strategy_match"]
    reasons.append(f"strategy_match {s_match}/3: {cand['match_note']}")

    # risk/liquidity match: daily-liquid proxies vs semi-liquid funds
    if cand["data"] == "none":
        r_match = 0; reasons.append("risk_liquidity_match 0/3: no computable series")
    elif profile.get("price_nav_decoupled"):
        r_match = 0; reasons.append("risk_liquidity_match 0/3: fund price is premium-driven, "
                                    "no candidate matches that risk process")
    elif cand["data"].startswith("quarterly"):
        r_match = 2; reasons.append("risk_liquidity_match 2/3: appraisal-cadence series, "
                                    "closer to the fund's NAV process")
    else:
        r_match = 1; reasons.append("risk_liquidity_match 1/3: daily-liquid proxy vs "
                                    "semi-liquid fund - vol/liquidity regimes differ")

    invest = 2 if cand["series"] else 0
    reasons.append(f"investability {invest}/2: "
                   + ("investable, priced daily" if invest else "not investable / not held"))

    dq = {"daily": 2, "annual": 1, "annual-window": 1,
          "quarterly-manual": 1, "quarterly-paid": 0, "none": 0}[cand["data"]]
    if cand["data"] == "quarterly-paid":
        reasons.append("data_quality 0/2: licensed data not held (no Preqin/Cambridge "
                       "subscription) - candidate cannot be computed, only cited")
    else:
        reasons.append(f"data_quality {dq}/2: {cand['data']} series")

    indep = 2 if cand["independent"] else 0
    if not cand["independent"]:
        reasons.append("provider_independence 0/2: index published by the fund's own "
                       "adviser. A manufacturer-owned yardstick sits poorly with the "
                       "rule's conflict-free ethos, so it is usable as secondary color only")
    else:
        reasons.append("provider_independence 2/2: provider unaffiliated with the fund")

    total = s_match + r_match + invest + dq + indep
    return {"candidate": cand["name"], "id": cand["id"], "lane": cand["lane"],
            "score": total, "max": 12, "reasons": reasons}


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
    if not cand["series"]:
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
        "window": f"{d0} to {d1}",
        "window_note": note,
        "fund_window": f"{fund_window[0]} to {fund_window[1]}",
        "fund_growth_x": round(f_growth, 4),
        "index_growth_x": round(i_growth, 4),
        "ks_pme": round(ks_pme(flows, index), 4),
        "direct_alpha_pct": round((direct_alpha(flows, index) or 0) * 100, 2),
        "fund_ann_pct": round((f_growth ** (1 / years) - 1) * 100, 2),
        "index_ann_pct": round((i_growth ** (1 / years) - 1) * 100, 2),
        **schedule,
    }


# ---------------------------------------------------------------- select
def run_selection(product_key: str) -> dict:
    profile = PRODUCT_PROFILES[product_key]
    scored = [score_candidate(profile, c) for c in STRATEGY_MENU[profile["strategy"]]]
    scored.sort(key=lambda s: -s["score"])

    decoupled = profile.get("price_nav_decoupled", False)
    eligible = [] if decoupled else [s for s in scored if s["score"] >= MIN_PRIMARY_SCORE]

    primary = eligible[0] if eligible else None
    secondary = eligible[1] if len(eligible) > 1 else None
    rejected = []
    for s in scored:
        if s is primary or s is secondary:
            continue
        if decoupled:
            why = ("fund price is premium/discount-driven and decoupled from NAV. "
                   "Benchmarking the price benchmarks the premium, not the portfolio")
        elif s["score"] >= MIN_PRIMARY_SCORE:
            why = (f"outranked: score {s['score']}/{s['max']} vs primary "
                   f"{primary['score']}/{primary['max']}"
                   + (f" and secondary {secondary['score']}/{secondary['max']}"
                      if secondary else "")
                   + " (only two slots). Retained in log as viable alternate")
        else:
            why = (f"score {s['score']}/{s['max']} below primary threshold "
                   f"{MIN_PRIMARY_SCORE}")
        rejected.append({**s, "rejection": why})

    result = {
        "product": product_key,
        "strategy": profile["strategy"],
        "source_cells": profile["source_cells"],
        "primary": primary, "secondary": secondary, "rejected": rejected,
        "escalation": None,
    }
    if primary is None:
        result["escalation"] = (
            "NO MEANINGFUL BENCHMARK CONSTRUCTIBLE from available data. "
            + ("Required next: public NAV series (quarterly filings) plus a "
               "premium/NAV decomposition before any comparator is defensible."
               if decoupled else
               "All candidates scored below threshold. Expand the candidate "
               "menu or obtain licensed data before selection."))
    for slot in ("primary", "secondary"):
        if result[slot]:
            cand = next(c for c in STRATEGY_MENU[profile["strategy"]]
                        if c["id"] == result[slot]["id"])
            try:
                result[slot]["comparison"] = comparison_stats(profile, cand)
            except WindowNotComputable as e:
                # no number is interpolated: the slot keeps its score and
                # says why the comparison is absent on held data
                result[slot]["comparison"] = None
                result[slot]["comparison_note"] = str(e)
    return result

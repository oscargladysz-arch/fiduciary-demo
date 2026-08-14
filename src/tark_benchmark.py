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

from tark_analytics import (_level_on, ann_return, cumulative_growth,
                            direct_alpha, ks_pme, month_end_points,
                            period_returns)
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
         "match_note": "broadly syndicated loans vs direct lending - close cousin, not twin; "
                       "fund itself declares NO benchmark (5.1) - engine constructs"},
        {"id": "cdli", "name": "Cliffwater Direct Lending Index (CDLI)",
         "lane": "B", "series": None, "provider": "Cliffwater (the Fund's own adviser)",
         "independent": False, "data": "quarterly-manual", "strategy_match": 3,
         "match_note": "direct lending - exact strategy match"},
        {"id": "peer_credit", "name": "Peer cohort: private_credit (cclfx, "
                                      "bcred, pflex)",
         "lane": "C", "series": None, "provider": "constructed (Tark cohort engine)",
         "independent": True, "data": "annual", "strategy_match": 3,
         "match_note": "n=3 equal-weight annual composite on printed FY "
                       "returns (data/cohorts/private_credit.json); "
                       "cross-wrapper mix (interval + BDC) disclosed in the "
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
                       "(data/cohorts/evergreen_pe.json); fiscal year-ends "
                       "differ and kkr_kpec joins cross-wrapper under the "
                       "documented fallback - both disclosed in the caveat block"},
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
         "match_note": "private open-end core RE funds - the strategy-exact "
                       "yardstick; index data is member/subscription "
                       "distribution, series not held"},
        {"id": "cambridge_re", "name": "Cambridge Associates Real Estate benchmark",
         "lane": "B", "series": None, "provider": "Cambridge Associates",
         "independent": True, "data": "quarterly-paid", "strategy_match": 3,
         "match_note": "private RE drawdown-fund universe - licensed data not held"},
        {"id": "peer_reit", "name": "Peer cohort: nontraded_reit (breit, "
                                    "sreit, jll_ipt)",
         "lane": "C", "series": None, "provider": "constructed (Tark cohort engine)",
         "independent": True, "data": "annual", "strategy_match": 3,
         "match_note": "n=3; equal-weight annual composite overlap currently "
                       "one year (2025: breit + sreit; jll_ipt prints returns "
                       "only as per-class ranges) - THIN, disclosed "
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
                       "adviser - a manufacturer-owned yardstick sits poorly with the "
                       "rule's conflict-free ethos; usable as secondary color only")
    else:
        reasons.append("provider_independence 2/2: provider unaffiliated with the fund")

    total = s_match + r_match + invest + dq + indep
    return {"candidate": cand["name"], "id": cand["id"], "lane": cand["lane"],
            "score": total, "max": 12, "reasons": reasons}


# ------------------------------------------------------------ comparison
def _window_growth(ticker: str, d0: str, d1: str) -> float:
    """Daily-anchored growth: level on/just-before d1 over level on/just-before
    d0 (adj close). Month-end sampling here previously DROPPED the first
    partial month when d0 fell on a non-trading day, so the displayed index
    growth disagreed with the index growth inside KS-PME (which always
    anchored daily). Corrected 2026-08-09; both sides now use these levels."""
    s = load_series(ticker, "adj_close")
    return _level_on(s, d1) / _level_on(s, d0)


def comparison_stats(profile: dict, cand: dict) -> dict | None:
    """Fund-vs-candidate growth, PME, Direct Alpha over a common window."""
    if not cand["series"]:
        return None
    if profile.get("series"):
        fund = load_series(profile["series"], "adj_close")
        d0, d1 = fund[0][0], fund[-1][0]
        f_growth = fund[-1][1] / fund[0][1]
    elif profile.get("fy_returns"):
        d0, d1 = profile["fy_window"]
        f_growth = cumulative_growth(profile["fy_returns"])
    elif profile.get("aatr_5yr"):
        d0, d1 = profile["fy_window"]
        f_growth = (1 + profile["aatr_5yr"]) ** 5
    elif profile.get("aatr"):
        # generic annualized-since-inception profile (kkr_kpec, breit):
        # aatr + exact year count, filled from extracted cell 1.2 evidence
        d0, d1 = profile["fy_window"]
        f_growth = (1 + profile["aatr"]) ** profile["aatr_years"]
    else:
        return None
    i_growth = _window_growth(cand["series"], d0, d1)
    years = (profile.get("aatr_years")
             or max((int(d1[:4]) - int(d0[:4])), 1))
    flows = [(d0, -1.0), (d1, f_growth)]
    idx = [(d, v) for d, v in load_series(cand["series"], "adj_close")
           if d0 <= d <= d1]
    return {
        "window": f"{d0} to {d1}",
        "fund_growth_x": round(f_growth, 4),
        "index_growth_x": round(i_growth, 4),
        "ks_pme": round(ks_pme(flows, idx), 4),
        "direct_alpha_pct": round((direct_alpha(flows, idx) or 0) * 100, 2),
        "fund_ann_pct": round((f_growth ** (1 / years) - 1) * 100, 2),
        "index_ann_pct": round((i_growth ** (1 / years) - 1) * 100, 2),
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
            why = ("fund price is premium/discount-driven and decoupled from NAV; "
                   "benchmarking the price benchmarks the premium, not the portfolio")
        elif s["score"] >= MIN_PRIMARY_SCORE:
            why = (f"outranked: score {s['score']}/{s['max']} vs primary "
                   f"{primary['score']}/{primary['max']}"
                   + (f" and secondary {secondary['score']}/{secondary['max']}"
                      if secondary else "")
                   + " - only two slots; retained in log as viable alternate")
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
               "All candidates scored below threshold; expand the candidate "
               "menu or obtain licensed data before selection."))
    for slot in ("primary", "secondary"):
        if result[slot]:
            cand = next(c for c in STRATEGY_MENU[profile["strategy"]]
                        if c["id"] == result[slot]["id"])
            result[slot]["comparison"] = comparison_stats(profile, cand)
    return result

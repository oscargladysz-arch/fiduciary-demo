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

from tark_analytics import (ann_return, cumulative_growth, direct_alpha,
                            ks_pme, month_end_points, period_returns)
from tark_data import load_series

MIN_PRIMARY_SCORE = 7

# ---------------------------------------------------------------- profiles
PRODUCT_PROFILES = {
    "cliffwater_cclfx": {
        "strategy": "private_credit",
        "series": "cclfx",                      # daily adj_close on disk
        "granularity": "monthly",
        "self_declared": "Morningstar LSTA US Leveraged Loan Index",  # cell 5.1
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
}

# ------------------------------------------------------------- candidates
STRATEGY_MENU = {
    "private_credit": [
        {"id": "bkln", "name": "Senior loan investable proxy (BKLN, for Morningstar LSTA class)",
         "lane": "A/B", "series": "bkln", "provider": "Invesco / Morningstar LSTA class",
         "independent": True, "data": "daily", "strategy_match": 2,
         "match_note": "broadly syndicated loans vs direct lending - close cousin, not twin"},
        {"id": "cdli", "name": "Cliffwater Direct Lending Index (CDLI)",
         "lane": "B", "series": None, "provider": "Cliffwater (the Fund's own adviser)",
         "independent": False, "data": "quarterly-manual", "strategy_match": 3,
         "match_note": "direct lending - exact strategy match"},
        {"id": "peer_credit", "name": "Peer cohort: same-strategy interval credit funds",
         "lane": "C", "series": None, "provider": "constructed",
         "independent": True, "data": "none", "strategy_match": 3,
         "match_note": "no same-strategy peer in current 6-product universe"},
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
        {"id": "peer_evergreen", "name": "Peer cohort: evergreen PE funds in universe",
         "lane": "C", "series": None, "provider": "constructed",
         "independent": True, "data": "annual", "strategy_match": 3,
         "match_note": "hl_paf / stepstone_spm / kkr_kpec - n small, annual granularity"},
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
def _monthly_growth(ticker: str, d0: str, d1: str) -> tuple[float, list]:
    s = [(d, v) for d, v in load_series(ticker, "adj_close") if d0 <= d <= d1]
    me = month_end_points(s)
    rets = period_returns([v for _, v in me])
    return cumulative_growth(rets), [(me[0][0], -1.0), (me[-1][0], None)]


def comparison_stats(profile: dict, cand: dict) -> dict | None:
    """Fund-vs-candidate growth, PME, Direct Alpha over a common window."""
    if not cand["series"]:
        return None
    if profile.get("series"):
        fund = load_series(profile["series"], "adj_close")
        d0, d1 = fund[0][0], fund[-1][0]
        f_growth = cumulative_growth(period_returns(
            [v for _, v in month_end_points(fund)]))
    elif profile.get("fy_returns"):
        d0, d1 = profile["fy_window"]
        f_growth = cumulative_growth(profile["fy_returns"])
    elif profile.get("aatr_5yr"):
        d0, d1 = profile["fy_window"]
        f_growth = (1 + profile["aatr_5yr"]) ** 5
    else:
        return None
    i_growth, _ = _monthly_growth(cand["series"], d0, d1)
    years = max((int(d1[:4]) - int(d0[:4])), 1)
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

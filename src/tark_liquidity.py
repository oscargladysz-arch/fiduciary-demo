"""
Tark product-to-plan liquidity match (M6, plan-parameterized)
=============================================================
Answers cell 3.9: does this product's liquidity structure fit THIS plan?
Three layers, honestly separated:
  1. FACTS — wrapper terms from cell 3.1 (extracted, cited).
  2. STRUCTURE — plan-aware: for a fully participant-directed 404(c) plan
     (codes 2F+2G) the DIA test applies squarely; for a PARTIALLY
     participant-directed plan (2H) a trustee-directed sleeve is
     structurally available and the daily-menu constraint narrows.
  3. SCENARIO — an ILLUSTRATIVE demand model (labeled, never presented as
     fact): plan allocates 5% of assets; annual liquidity demand from the
     separated-with-balances tail plus active-participant turnover.

Run:  python src/tark_liquidity.py
      -> data/liquidity/<plan_key>__<product_key>_match.json  (all plans)
      -> data/liquidity/<product_key>_match.json              (legacy copy,
         anchor plan, kept while the v9 Streamlit app is alive)
"""
from __future__ import annotations

import json
from pathlib import Path

from tark_data import ANCHOR_PLAN_KEY, DATA, load_plan, load_products, plan_keys

# wrapper liquidity facts — sourced from cells 3.1 / 2.7 of each product (extracted)
LIQUIDITY_PROFILES = {
    "hl_paf": {"kind": "tender_offer", "cadence_per_year": 4, "cap_pct": 5.0,
               "cap_base": "net assets", "exchange": False, "gate_history": False,
               "early_fee": "2.00% if held < 1 year", "source_cell": "3.1"},
    "stepstone_spm": {"kind": "tender_offer", "cadence_per_year": 4, "cap_pct": 5.0,
                      "cap_base": "outstanding shares", "exchange": False,
                      "gate_history": False,
                      "early_fee": "none identified at fund level (2.7)",
                      "source_cell": "3.1"},
    "cliffwater_cclfx": {"kind": "interval_23c3", "cadence_per_year": 4,
                         "cap_pct": 5.0, "cap_base": "outstanding shares",
                         "exchange": False, "gate_history": False,
                         "early_fee": "n/a", "source_cell": "3.1",
                         "history": "8 quarterly N-23C3A filings on disk (3.3)"},
    "kkr_kpec": {"kind": "share_repurchase_plan", "cadence_per_year": 4,
                 "cap_pct": 5.0, "cap_base": "aggregate NAV (Investor Shares)",
                 "exchange": False, "gate_history": False,
                 "early_fee": "5.0% of NAV if repurchased within 24 months (2.7)",
                 "source_cell": "3.1"},
    "breit": {"kind": "share_repurchase_plan", "cadence_per_year": 12,
              "cap_pct": 2.0, "cap_base": "aggregate NAV (monthly; 5% quarterly)",
              "exchange": False, "gate_history": True,
              "early_fee": "Early Repurchase Deduction: repurchased at 98% of "
                           "transaction price if held < 1 year (2.7)",
              "source_cell": "3.1 + 3.3"},
    "dxyz": {"kind": "listed_cef", "cadence_per_year": 252, "cap_pct": None,
             "cap_base": "on-exchange (NYSE)", "exchange": True,
             "gate_history": False, "early_fee": "n/a", "source_cell": "3.1"},
    # ---- cohort-tier roster ----
    "bcred": {"kind": "share_repurchase_plan", "cadence_per_year": 4,
              "cap_pct": 5.0, "cap_base": "NAV of outstanding shares "
              "(board-discretionary quarterly tenders)", "exchange": False,
              "gate_history": False,
              "early_fee": "2% Early Repurchase Deduction: repurchased at 98% "
                           "of NAV if held < 1 year (2.7)",
              "source_cell": "3.1 + 3.3",
              "history": "completed quarterly tenders printed for every "
                         "quarter 2023-2026H1, all requests satisfied (3.3)"},
    "pflex": {"kind": "interval_23c3", "cadence_per_year": 4, "cap_pct": 5.0,
              "cap_base": "outstanding shares (fundamental 5-25% policy; "
              "currently 5%)", "exchange": False, "gate_history": False,
              "early_fee": "none at fund level; 1.00% contingent load on "
                           "A-2/A-4 classes only (2.7)",
              "source_cell": "3.1",
              "history": "8 N-23C3A filings on disk; FY2025 offers "
                         "undersubscribed (max 4.32% tendered vs 5% cap) (3.3)"},
    "ares_pmf": {"kind": "tender_offer", "cadence_per_year": 4, "cap_pct": 5.0,
                 "cap_base": "NAV (board-discretionary quarterly tenders, "
                 "Rule 13e-4 - NOT an interval fund)", "exchange": False,
                 "gate_history": False,
                 "early_fee": "2.00% of NAV if held < 1 year, FIFO (2.7)",
                 "source_cell": "3.1 + 3.3",
                 "history": "four offers conducted in EACH of FY2025/FY2026 (3.3)"},
    "amg_pantheon": {"kind": "tender_offer", "cadence_per_year": 4,
                     "cap_pct": 5.0, "cap_base": "outstanding Units "
                     "(board-discretionary tenders)", "exchange": False,
                     "gate_history": False,
                     "early_fee": "2.00% if held < 1 year, FIFO (2.7)",
                     "source_cell": "3.1 + 3.3"},
    "sreit": {"kind": "share_repurchase_plan", "cadence_per_year": 12,
              "cap_pct": 0.0,
              "cap_base": "SUSPENDED (April 2026): ordinary repurchases no "
              "longer accepted - death/qualifying-disability and sub-$5,000 "
              "accounts only (up to $5.0M/month each). Cap history: 2%/month "
              "+ 5%/quarter (2017) -> 0.33%/1% (May 2024) -> 0.5%/1.5% "
              "(June 2025) -> closed (April 2026)", "exchange": False,
              "gate_history": True,
              "early_fee": "5% Early Repurchase Deduction: 95% of transaction "
                           "price if held < 1 year (2.7)",
              "source_cell": "3.1 + 3.3"},
    "jll_ipt": {"kind": "share_repurchase_plan", "cadence_per_year": 4,
                "cap_pct": 5.0, "cap_base": "combined NAV of all classes "
                "(prior quarter-end)", "exchange": False,
                "dealing": "DAILY repurchase requests at that day's NAV, "
                           "capped at 5% of NAV per calendar quarter",
                "gate_history": False,
                "early_fee": "no fee; one-year holding period with "
                             "death/disability exceptions (2.7)",
                "source_cell": "3.1 + 3.3",
                "history": "never deferred nor rejected a repurchase request "
                           "through 2025-12-31; 100% honored in later printed "
                           "periods (3.3)"},
    "ssss": {"kind": "listed_bdc", "cadence_per_year": 252, "cap_pct": None,
             "cap_base": "on-exchange (Nasdaq: NSLR, fka SSSS)",
             "exchange": True, "gate_history": False, "early_fee": "n/a",
             "source_cell": "3.1"},
    "arkvx": {"kind": "interval_23c3", "cadence_per_year": 4, "cap_pct": 5.0,
              "cap_base": "outstanding shares (fundamental 5-25% policy; "
              "every completed offer at 5%)", "exchange": False,
              "gate_history": False, "early_fee": "none - repurchases at NAV, "
              "no early repurchase fee (2.7)",
              "source_cell": "3.1 + 3.3",
              "history": "8 N-23C3A filings on disk; no gating or "
                         "postponement disclosed (3.3)"},
}

# illustrative scenario parameters — LABELED, adjustable, never asserted as fact
SCENARIO = {"allocation_pct_of_plan": 5.0, "tail_annual_turnover_pct": 20.0,
            "active_annual_turnover_pct": 5.0}

# stressed variant (cell 3.8): separated tail exits at double speed, active
# churn 1.5x — an ILLUSTRATIVE redemption stress test, not a prediction
STRESS = {"tail_multiple": 2.0, "active_multiple": 1.5}


def plan_direction(plan: dict) -> str:
    """'total' (2F+2G filed), 'partial' (2H filed), or 'other' — from the
    plan's own Form 5500 pension characteristic codes."""
    codes = plan.get("plan_characteristics", {}).get("pension_benefit_codes", "")
    if "2G" in codes:
        return "total"
    if "2H" in codes:
        return "partial"
    return "other"


def run_match(key: str, plan_key: str = ANCHOR_PLAN_KEY,
              scenario: dict | None = None) -> dict:
    prof = LIQUIDITY_PROFILES[key]
    sc_in = {**SCENARIO, **(scenario or {})}
    a = load_plan(plan_key)
    part, fin = a["participants"], a["financials"]
    net = fin["net_assets_eoy"]
    tail_share = part["separated_deferred_vested"] / part["with_account_balances"]
    direction = plan_direction(a)

    alloc = net * sc_in["allocation_pct_of_plan"] / 100
    tail_demand = alloc * tail_share * sc_in["tail_annual_turnover_pct"] / 100
    active_demand = alloc * (1 - tail_share) * sc_in["active_annual_turnover_pct"] / 100
    demand = tail_demand + active_demand
    demand_pct_of_position = demand / alloc * 100

    if prof["exchange"]:
        capacity_note = "daily on-exchange liquidity; capacity is market depth, not a fund cap"
        annual_capacity_pct = None
    else:
        annual_capacity_pct = prof["cadence_per_year"] * prof["cap_pct"]
        capacity_note = (f"{prof['cadence_per_year']}x per year at "
                         f"{prof['cap_pct']}% of {prof['cap_base']} — a FUND-level "
                         f"cap; at a {sc_in['allocation_pct_of_plan']:.0f}% plan "
                         f"allocation the plan's position is far inside it unless "
                         f"offers are oversubscribed")

    reasons = []
    if prof["exchange"]:
        verdict = "aligned-mechanical"
        reasons.append("Daily exchange liquidity mechanically satisfies daily "
                       "participant dealing (3.1).")
        reasons.append("BUT price-vs-NAV decoupling means participants transact "
                       "at the premium/discount, not at portfolio value — the "
                       "liquidity is real, the price basis is not (1.10, 4.7).")
    else:
        verdict = "conditional"
        dealing = prof.get("dealing",
                           f"this wrapper deals {prof['cadence_per_year']}x/year")
        if direction == "total":
            reasons.append("STRUCTURAL GAP: a participant-directed 404(c) menu "
                           "assumes daily pricing and daily participant liquidity; "
                           f"{dealing}. "
                           "Direct DIA use requires a bridging structure — CIT "
                           "sleeve, managed account, or TDF sleeve (cell 3.5).")
        elif direction == "partial":
            reasons.append("STRUCTURAL GAP (narrowed): this plan is PARTIALLY "
                           "participant-directed per its own Form 5500 codes (2H, "
                           "no 2G/404(c) code filed) — a trustee-directed sleeve "
                           "could hold this wrapper directly; the daily-menu "
                           f"constraint ({dealing}) "
                           "applies only to the participant-directed portion "
                           "(cell 3.5).")
        else:
            reasons.append("STRUCTURAL: plan direction codes do not show full "
                           "participant direction; DIA daily-menu framing may "
                           f"not bind. Wrapper deals {prof['cadence_per_year']}x/"
                           "year (cell 3.5).")
        reasons.append(f"Capacity: {capacity_note}.")
        reasons.append(f"Scenario demand (illustrative): "
                       f"{demand_pct_of_position:.1f}% of the position per year "
                       f"vs {annual_capacity_pct:.0f}% annual wrapper capacity — "
                       + ("adequate headroom at this allocation if offers are "
                          "not prorated."
                          if demand_pct_of_position <= 0.6 * annual_capacity_pct
                          else "THIN HEADROOM: demand consumes over 60% of wrapper "
                               "capacity; proration in any oversubscribed quarter "
                               "would push the shortfall into the next window."))
        if prof["gate_history"]:
            verdict = "conditional-weak"
            reasons.append("Gating precedent: this issuer has prorated "
                           "repurchases when requests exceeded caps (3.3) — "
                           "capacity on paper has failed in stress before.")
        if prof.get("history"):
            reasons.append(f"Cadence reliability evidence: {prof['history']}.")
        if prof["early_fee"] not in ("n/a",):
            reasons.append(f"Early repurchase economics: {prof['early_fee']} — "
                           "relevant to participant-level churn (2.7).")

    # stressed scenario (cell 3.8) — same demand model, stressed turnover
    s_tail = alloc * tail_share * (sc_in["tail_annual_turnover_pct"]
                                   * STRESS["tail_multiple"]) / 100
    s_active = alloc * (1 - tail_share) * (sc_in["active_annual_turnover_pct"]
                                           * STRESS["active_multiple"]) / 100
    s_demand = s_tail + s_active
    s_pct = s_demand / alloc * 100
    stressed = {
        "illustrative": True,
        "assumptions": f"tail turnover x{STRESS['tail_multiple']:.0f}, active "
                       f"turnover x{STRESS['active_multiple']:.1f} vs base scenario",
        "annual_demand_usd": round(s_demand),
        "demand_pct_of_position": round(s_pct, 1),
        "annual_wrapper_capacity_pct": annual_capacity_pct,
        "outcome": ("daily exchange liquidity; stress transmits to price, "
                    "not to a fund gate" if prof["exchange"] else
                    ("EXCEEDS annual wrapper capacity — unmet demand rolls "
                     "into later windows (gating-equivalent outcome)"
                     if s_pct > annual_capacity_pct else
                     f"within wrapper capacity ({s_pct:.1f}% vs "
                     f"{annual_capacity_pct:.0f}%) IF offers are not prorated"
                     + (" — but this issuer HAS prorated under stress (3.3)"
                        if prof["gate_history"] else ""))),
    }

    return {
        "product": key, "plan": plan_key, "verdict": verdict, "reasons": reasons,
        "stressed_scenario": stressed,
        "plan_display_label": a["display_label"],
        "plan_direction": direction,
        "wrapper_facts": {k: v for k, v in prof.items()},
        "scenario": {**sc_in, "illustrative": True,
                     "plan_allocation_usd": round(alloc),
                     "annual_demand_usd": round(demand),
                     "demand_pct_of_position": round(demand_pct_of_position, 1),
                     "annual_wrapper_capacity_pct": annual_capacity_pct},
        "plan_inputs": {"net_assets": net,
                        "tail_share_pct": round(tail_share * 100, 1),
                        "separated_with_balances": part["separated_deferred_vested"]},
        "citations": ["3.1", "3.3", "3.5", "3.7", "3.9",
                      f"plan: {plan_key}.json (Form 5500, plan year "
                      f"{a.get('plan_year', '?')})"],
    }


if __name__ == "__main__":
    out = DATA / "liquidity"
    out.mkdir(exist_ok=True)
    for pk in plan_keys():
        for key in load_products():
            if key not in LIQUIDITY_PROFILES:
                continue  # cohort-tier product whose 3.1 has not landed yet
            m = run_match(key, pk)
            (out / f"{pk}__{key}_match.json").write_text(json.dumps(m, indent=2))
            if pk == ANCHOR_PLAN_KEY:
                # legacy filename kept while the v9 app remains deployed
                (out / f"{key}_match.json").write_text(json.dumps(m, indent=2))
            print(f"{pk:<26} {key:<18} {m['verdict']:<18} "
                  f"demand {m['scenario']['demand_pct_of_position']}%/yr")

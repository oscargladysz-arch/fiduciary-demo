"""
Tark product-to-plan liquidity match (M6)
=========================================
Answers cell 3.9: does this product's liquidity structure fit THIS plan?
Three layers, honestly separated:
  1. FACTS — wrapper terms from cell 3.1 (extracted, cited).
  2. STRUCTURE — the DIA test: participant-directed 404(c) menus assume
     daily pricing and daily participant liquidity; non-exchange wrappers
     need a bridging structure (CIT sleeve / managed-account / TDF sleeve,
     cell 3.5) regardless of capacity math.
  3. SCENARIO — an ILLUSTRATIVE demand model (labeled, never presented as
     fact): plan allocates 5% of assets; annual liquidity demand from the
     separated-with-balances tail plus active-participant turnover.

Run:  python src/tark_liquidity.py   -> data/liquidity/<key>_match.json
"""
from __future__ import annotations

import json
from pathlib import Path

from tark_data import DATA, load_anchor_plan, load_products

# wrapper liquidity facts — sourced from cell 3.1 of each product (extracted)
LIQUIDITY_PROFILES = {
    "hl_paf": {"kind": "tender_offer", "cadence_per_year": 4, "cap_pct": 5.0,
               "cap_base": "net assets", "exchange": False, "gate_history": False,
               "early_fee": "2.00% if held < 1 year", "source_cell": "3.1"},
    "stepstone_spm": {"kind": "tender_offer", "cadence_per_year": 4, "cap_pct": 5.0,
                      "cap_base": "outstanding shares", "exchange": False,
                      "gate_history": False, "early_fee": "none identified (2.7)",
                      "source_cell": "3.1"},
    "cliffwater_cclfx": {"kind": "interval_23c3", "cadence_per_year": 4,
                         "cap_pct": 5.0, "cap_base": "outstanding shares",
                         "exchange": False, "gate_history": False,
                         "early_fee": "n/a", "source_cell": "3.1",
                         "history": "8 quarterly N-23C3A filings on disk (3.3)"},
    "kkr_kpec": {"kind": "share_repurchase_plan", "cadence_per_year": 4,
                 "cap_pct": 5.0, "cap_base": "aggregate NAV (Investor Shares)",
                 "exchange": False, "gate_history": False,
                 "early_fee": "exists; rate pending (2.7)", "source_cell": "3.1"},
    "breit": {"kind": "share_repurchase_plan", "cadence_per_year": 12,
              "cap_pct": 2.0, "cap_base": "aggregate NAV (monthly; 5% quarterly)",
              "exchange": False, "gate_history": True,
              "early_fee": "Early Repurchase Deduction; rate pending (2.7)",
              "source_cell": "3.1 + 3.3"},
    "dxyz": {"kind": "listed_cef", "cadence_per_year": 252, "cap_pct": None,
             "cap_base": "on-exchange (NYSE)", "exchange": True,
             "gate_history": False, "early_fee": "n/a", "source_cell": "3.1"},
}

# illustrative scenario parameters — LABELED, adjustable, never asserted as fact
SCENARIO = {"allocation_pct_of_plan": 5.0, "tail_annual_turnover_pct": 20.0,
            "active_annual_turnover_pct": 5.0}


def run_match(key: str) -> dict:
    prof = LIQUIDITY_PROFILES[key]
    a = load_anchor_plan()
    part, fin = a["participants"], a["financials"]
    net = fin["net_assets_eoy"]
    tail_share = part["separated_deferred_vested"] / part["with_account_balances"]

    alloc = net * SCENARIO["allocation_pct_of_plan"] / 100
    tail_demand = alloc * tail_share * SCENARIO["tail_annual_turnover_pct"] / 100
    active_demand = alloc * (1 - tail_share) * SCENARIO["active_annual_turnover_pct"] / 100
    demand = tail_demand + active_demand
    demand_pct_of_position = demand / alloc * 100

    if prof["exchange"]:
        capacity_note = "daily on-exchange liquidity; capacity is market depth, not a fund cap"
        annual_capacity_pct = None
    else:
        annual_capacity_pct = prof["cadence_per_year"] * prof["cap_pct"]
        capacity_note = (f"{prof['cadence_per_year']}x per year at "
                         f"{prof['cap_pct']}% of {prof['cap_base']} — a FUND-level "
                         f"cap; at a 5% plan allocation the plan's position is far "
                         f"inside it unless offers are oversubscribed")

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
        reasons.append("STRUCTURAL GAP: a participant-directed 404(c) menu "
                       "assumes daily pricing and daily participant liquidity; "
                       f"this wrapper deals {prof['cadence_per_year']}x/year. "
                       "Direct DIA use requires a bridging structure — CIT "
                       "sleeve, managed account, or TDF sleeve (cell 3.5).")
        reasons.append(f"Capacity: {capacity_note}.")
        reasons.append(f"Scenario demand (illustrative): "
                       f"{demand_pct_of_position:.1f}% of the position per year "
                       f"vs {annual_capacity_pct:.0f}% annual wrapper capacity — "
                       "adequate headroom at this allocation if offers are not "
                       "prorated.")
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

    return {
        "product": key, "verdict": verdict, "reasons": reasons,
        "wrapper_facts": {k: v for k, v in prof.items()},
        "scenario": {**SCENARIO, "illustrative": True,
                     "plan_allocation_usd": round(alloc),
                     "annual_demand_usd": round(demand),
                     "demand_pct_of_position": round(demand_pct_of_position, 1),
                     "annual_wrapper_capacity_pct": annual_capacity_pct},
        "plan_inputs": {"net_assets": net,
                        "tail_share_pct": round(tail_share * 100, 1),
                        "separated_with_balances": part["separated_deferred_vested"]},
        "citations": ["3.1", "3.3", "3.5", "3.7", "3.9",
                      "plan: anchor_plan.json (Form 5500 PY2024)"],
    }


if __name__ == "__main__":
    out = DATA / "liquidity"
    out.mkdir(exist_ok=True)
    for key in load_products():
        m = run_match(key)
        (out / f"{key}_match.json").write_text(json.dumps(m, indent=2))
        print(f"{key:<18} {m['verdict']:<20} "
              f"demand {m['scenario']['demand_pct_of_position']}%/yr of position")

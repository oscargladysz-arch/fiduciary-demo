"""
Tark structured-facts layer (workbench pass)
============================================
Typed projections of ALREADY-EVIDENCED cells — zero new facts. Each field is
{value, source_cell, status[, reason][, note][, approx]} where status mirrors
the cited cell's status. A field whose cell is partial / documented-n/a maps
to value null with the reason — the screener renders honest gaps, not blanks.

The hand-mapping below is the transcription layer; it is machine-checked two
ways: validate_data.py enforces (a) every source_cell exists with status
extracted/verified/computed for non-null values, (b) numeric fields WITHOUT
the approx flag appear verbatim in the cited cell's text. Engine outputs are
pulled live from the selection/match artifacts, never retyped.

Run: python src/build_facts.py   -> data/facts/<product>.json
"""
from __future__ import annotations

import json
from pathlib import Path

from tark_data import DATA, load_product, plan_keys, product_keys

# --------------------------------------------------------- the hand-mapping
# F(value, cell, **kw) -> typed field dict; null(reason, cell, status)
def F(value, cell, **kw):
    return {"value": value, "source_cell": cell, **kw}


def null(reason, cell):
    return {"value": None, "source_cell": cell, "reason": reason}


MAPPING = {
    "hl_paf": {
        "wrapper_type": F("tender_offer", "3.1"),
        "mgmt_fee_pct": F(1.40, "2.1"),
        "mgmt_fee_base": F("managed_assets", "2.1",
                           note="Managed Assets = leverage-inclusive"),
        "incentive_fee": F({"present": True, "rate_pct": 10.00,
                            "hurdle_pct": None,
                            "structure": "10% of quarterly net profits over the "
                                         "Loss Recovery Account (loss-carryforward "
                                         "HWM; terms approved 2025-03-14; 2021 "
                                         "12.5% deal-by-deal terms superseded)"},
                           "2.2"),
        "early_repurchase": F({"present": True, "rate_pct": 2.00,
                               "window": "< 1 year"}, "2.7"),
        "repurchase_cadence_per_year": F(4, "3.1"),
        "repurchase_cap_pct": F(5.0, "3.1"),
        "repurchase_cap_base": F("net_assets", "3.1"),
        "gate_history": null("offer continuity since Q2-2021 evidenced; "
                             "per-offer proration incidence not printed in "
                             "on-disk filings", "3.3"),
        "tax_form": F("1099", "6.4"),
        "auditor": F("Cohen & Company, Ltd.", "4.5"),
        "big4": F(False, "4.5"),
        "expense_ratio_pct": F(3.40, "2.3",
                               note="FY2026 net, incl. incentive-fee drag; AFFE excluded"),
        "net_assets_usd": F(5785749989, "3.4"),
        "inception": F("2021-01-04", "1.11", note="commenced operations"),
    },
    "cliffwater_cclfx": {
        "wrapper_type": F("interval_23c3", "6.1"),
        "mgmt_fee_pct": F(1.00, "2.1"),
        "mgmt_fee_base": F("net_assets", "2.1"),
        "incentive_fee": null("cell 2.2 is partial: no incentive fee identified "
                              "in the fee note; prospectus confirmation pending "
                              "(verification queue)", "2.2"),
        "early_repurchase": F({"present": False}, "2.7",
                              note="'The Fund will not charge a repurchase fee' (N-23C3A)"),
        "repurchase_cadence_per_year": F(4, "3.1"),
        "repurchase_cap_pct": F(5.0, "3.1"),
        "repurchase_cap_base": F("outstanding_shares", "3.1"),
        "gate_history": null("N-23C3A filings are offer NOTIFICATIONS, not "
                             "results; per-offer proration outcomes not yet "
                             "evidenced", "3.3"),
        "tax_form": null("form number not printed in any on-disk filing; RIC "
                         "status implies 1099 but the cell is partial", "6.4"),
        "auditor": F("Cohen & Company, Ltd.", "4.5"),
        "big4": F(False, "4.5"),
        "expense_ratio_pct": F(1.36, "2.3",
                               note="FY2026 before waivers, EXCLUDING interest "
                                    "expense; 3.31% including interest"),
        "net_assets_usd": null("net assets ~$31.26B printed, but the carrying "
                               "cells (1.1/3.6) are partial - verification "
                               "unlocks this fact", "3.4"),
        "inception": F("2019-06-05", "1.2", note="performance inception as disclosed"),
    },
    "dxyz": {
        "wrapper_type": F("listed_cef", "6.1"),
        "mgmt_fee_pct": F(2.50, "2.1"),
        "mgmt_fee_base": F("gross_incl_borrowings", "2.1",
                           note="average GROSS assets incl. assets bought with borrowings"),
        "incentive_fee": F({"present": False}, "2.2",
                           note="absence documented three ways in the record"),
        "early_repurchase": null("exchange-listed; no repurchase program — "
                                 "fee inapplicable", "2.7"),
        "repurchase_cadence_per_year": F(252, "3.1", status="computed",
                                         note="trading-days convention for daily "
                                              "on-exchange dealing - a derived "
                                              "figure, not a fund program"),
        "repurchase_cap_pct": null("on-exchange liquidity; no fund-level cap", "3.1"),
        "repurchase_cap_base": null("on-exchange liquidity; no fund-level cap", "3.1"),
        "gate_history": F(False, "3.1",
                          note="exchange wrapper has no gating mechanism; "
                               "'no fund-level repurchase program' is itself "
                               "an absence-inference flagged in the cell"),
        "tax_form": null("form number not printed in any on-disk filing; RIC "
                         "status implies 1099 but the cell is partial", "6.4"),
        "auditor": F("KPMG LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": F(4.53, "2.3", note="FY2025, of average net assets"),
        "net_assets_usd": F(438000000, "2.3", approx=True,
                            note="$438.0M at 12/31/2025 as printed"),
        "inception": F("2022-05-12", "1.11",
                       note="commenced operations as printed; NYSE listing "
                            "2024-03-26 (3.1) is the trading-history start"),
    },
    "kkr_kpec": {
        "wrapper_type": F("nontraded_llc", "6.1"),
        "mgmt_fee_pct": F(1.25, "2.1"),
        "mgmt_fee_base": F("nav", "2.1", note="month-end NAV, Investor Shares"),
        "incentive_fee": F({"present": True, "rate_pct": 15.0,
                            "hurdle_pct": 5.0,
                            "structure": "Performance Participation Allocation; "
                                         "high-water mark; 100% catch-up"}, "2.2"),
        "early_repurchase": F({"present": True, "rate_pct": 5.0,
                               "window": "< 24 months"}, "2.7"),
        "repurchase_cadence_per_year": F(4, "3.1"),
        "repurchase_cap_pct": F(5.0, "3.1"),
        "repurchase_cap_base": F("aggregate_nav", "3.1"),
        "gate_history": F(False, "3.3"),
        "tax_form": F("K-1", "6.4"),
        "auditor": F("Deloitte & Touche LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": F(3.19, "1.3",
                               note="GAAP financial-highlights total operating "
                                    "expenses FY2025 Class I, INCL. 2.75% "
                                    "performance participation - NOT a "
                                    "1940-Act TER; class range 2.74-3.59%"),
        "net_assets_usd": F(9500000000, "3.3", approx=True,
                            note="net assets $9.5bn at 12/31/2025 as printed"),
        "inception": F("2023-08-01", "1.11", note="commenced principal operations"),
    },
    "breit": {
        "wrapper_type": F("nontraded_reit", "6.1"),
        "mgmt_fee_pct": F(1.25, "2.1"),
        "mgmt_fee_base": F("nav", "2.1"),
        "incentive_fee": F({"present": True, "rate_pct": 12.5,
                            "hurdle_pct": 5.0,
                            "structure": "performance participation, 100% "
                                         "catch-up; FY2024 hurdle MISS produced "
                                         "a $105.0M shortfall obligation (2.2)"},
                           "2.4",
                           note="rate/hurdle printed in cell 2.4's fee-structure "
                                "discussion; mechanics + shortfall in 2.2 (partial)"),
        "early_repurchase": F({"present": True, "rate_pct": 2.0,
                               "window": "< 1 year"}, "2.7",
                              note="repurchased at 98% of transaction price"),
        "repurchase_cadence_per_year": F(12, "3.1"),
        "repurchase_cap_pct": F(2.0, "3.1", note="monthly; 5% quarterly"),
        "repurchase_cap_base": F("aggregate_nav", "3.1"),
        "gate_history": F(True, "3.3",
                          note="prorated repurchases 2022-24; FY2025 fulfilled 100%"),
        "tax_form": null("form number not printed in on-disk 10-K/10-Q; REIT "
                         "status implies 1099-DIV but the cell is partial", "6.4"),
        "auditor": F("Deloitte & Touche LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": null("no TER line item exists for this '34-Act "
                                  "wrapper; components in 2.1/2.2/2.6", "2.9"),
        "net_assets_usd": null("aggregate NAV printed in the MD&A NAV-by-class "
                               "table but not yet carried into a typed cell; "
                               "verification-queue item", "1.1"),
        "inception": null("explicit Class I inception date not printed in "
                          "on-disk filings; ITD basis year (2017 REIT "
                          "election) sits in partial cell 6.4", "6.4"),
    },
    "stepstone_spm": {
        "wrapper_type": F("tender_offer", "3.1"),
        "mgmt_fee_pct": F(1.40, "2.1"),
        "mgmt_fee_base": F("net_assets", "2.1", note="daily net assets"),
        "incentive_fee": null("cell 2.2 is partial: no fund-level incentive fee "
                              "identified; underlying funds charge performance "
                              "fees (AFFE layer)", "2.2"),
        "early_repurchase": null("cell 2.7 is partial: no early-repurchase-fee "
                                 "language matched; confirmation pending", "2.7"),
        "repurchase_cadence_per_year": F(4, "3.1"),
        "repurchase_cap_pct": F(5.0, "3.1"),
        "repurchase_cap_base": F("outstanding_shares", "3.1"),
        "gate_history": null("per-offer tendered-vs-purchased counts not "
                             "printed in on-disk filings; Sept 2025 offer was "
                             "Board-UPSIZED (demand signal) - proration "
                             "incidence unevidenced", "3.3"),
        "tax_form": F("1099", "6.4"),
        "auditor": F("Ernst & Young LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": F(1.91, "2.3", note="FY2026 Class I; AFFE excluded"),
        "net_assets_usd": F(5828900000, "3.6", approx=True,
                            note="$5,828.9M at 3/31/2026 as printed"),
        "inception": F("2020-10-01", "1.2", note="Class I/D/S inception"),
    },
}

# per-product as-of dates for track-record math (latest fiscal period end in
# the record; used only for the computed track_record_years field)
AS_OF = {"hl_paf": "2026-03-31", "cliffwater_cclfx": "2026-03-31",
         "dxyz": "2025-12-31", "kkr_kpec": "2025-12-31",
         "breit": "2025-12-31", "stepstone_spm": "2026-03-31"}


def years_between(d0: str, d1: str) -> float:
    from datetime import date
    a = date(*map(int, d0.split("-")))
    b = date(*map(int, d1.split("-")))
    return round((b - a).days / 365.25, 1)


def main() -> None:
    out_dir = DATA / "facts"
    out_dir.mkdir(exist_ok=True)
    plans = plan_keys()
    for key in product_keys():
        cells = load_product(key)["cells"]
        facts = {}
        for field, f in MAPPING[key].items():
            cell = cells[f["source_cell"]]
            facts[field] = {**f, "status": cell.get("status", "pending")}
        # computed: track record from inception to the record's as-of date
        inc = facts["inception"]["value"]
        if inc:
            facts["track_record_years"] = {
                "value": years_between(inc, AS_OF[key]),
                "source_cell": facts["inception"]["source_cell"],
                "status": "computed",
                "note": f"(as-of {AS_OF[key]} minus inception) / 365.25"}
        else:
            facts["track_record_years"] = {
                "value": None, "source_cell": facts["inception"]["source_cell"],
                "status": facts["inception"]["status"],
                "reason": facts["inception"].get("reason", "inception unmapped")}
        # engine outputs — pulled from artifacts, never retyped
        sel_path = DATA / "benchmarks" / f"{key}_selection.json"
        sel = json.loads(sel_path.read_text())
        if sel.get("primary"):
            comp = sel["primary"].get("comparison") or {}
            facts["primary_benchmark_id"] = F(sel["primary"]["id"], "5.3",
                                              status="computed")
            facts["selection_score"] = F(sel["primary"]["score"], "5.3",
                                         status="computed")
            facts["pme_primary"] = F(comp.get("ks_pme"), "1.8", status="computed")
            facts["direct_alpha_primary"] = F(comp.get("direct_alpha_pct"),
                                              "1.8", status="computed")
        else:
            esc = ("engine escalation: no meaningful benchmark constructible "
                   "(premium-driven price)")
            for fld in ("primary_benchmark_id", "selection_score",
                        "pme_primary", "direct_alpha_primary"):
                facts[fld] = {"value": None, "source_cell": "1.8",
                              "status": "computed", "reason": esc}
        facts["liquidity_verdict_by_plan"] = {
            "value": {pk: json.loads((DATA / "liquidity" /
                                      f"{pk}__{key}_match.json").read_text())["verdict"]
                      for pk in plans},
            "source_cell": "3.9", "status": "computed"}
        doc = {"product_key": key,
               "what": "typed projections of evidenced cells - zero new facts; "
                       "every field carries its source_cell and mirrors its status",
               "generated_by": "src/build_facts.py (hand-mapping machine-checked "
                               "by validate_data.py)",
               "facts": facts}
        (out_dir / f"{key}.json").write_text(json.dumps(doc, indent=2))
        print(f"{key}: {len(facts)} fields, "
              f"{sum(1 for f in facts.values() if f['value'] is None)} honest nulls")


if __name__ == "__main__":
    main()

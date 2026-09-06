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
                                         "HWM). Terms approved 2025-03-14. The 2021 "
                                         "12.5% deal-by-deal terms are superseded"},
                           "2.2"),
        "early_repurchase": F({"present": True, "rate_pct": 2.00,
                               "window": "< 1 year"}, "2.7"),
        "repurchase_cadence_per_year": F(4, "3.1"),
        "repurchase_cap_pct": F(5.0, "3.1"),
        "repurchase_cap_base": F("net_assets", "3.1"),
        "gate_history": null("offer continuity since Q2-2021 evidenced. "
                             "Per-offer proration incidence not printed in "
                             "on-disk filings", "3.3"),
        "tax_form": F("1099", "6.4"),
        "auditor": F("Cohen & Company, Ltd.", "4.5"),
        "big4": F(False, "4.5"),
        "expense_ratio_pct": F(3.40, "2.3",
                               note="FY2026 net, incl. incentive-fee drag, AFFE excluded"),
        "net_assets_usd": F(5785749989, "3.4"),
        "inception": F("2021-01-04", "1.11", note="commenced operations"),
    },
    "cliffwater_cclfx": {
        "wrapper_type": F("interval_23c3", "6.1"),
        "mgmt_fee_pct": F(1.00, "2.1"),
        "mgmt_fee_base": F("net_assets", "2.1"),
        "incentive_fee": null("cell 2.2 is partial: no incentive fee identified "
                              "in the fee note. Prospectus confirmation pending "
                              "(verification queue)", "2.2"),
        "early_repurchase": F({"present": False}, "2.7",
                              note="'The Fund will not charge a repurchase fee' (N-23C3A)"),
        "repurchase_cadence_per_year": F(4, "3.1"),
        "repurchase_cap_pct": F(5.0, "3.1"),
        "repurchase_cap_base": F("outstanding_shares", "3.1"),
        "gate_history": null("N-23C3A filings are offer NOTIFICATIONS, not "
                             "results. Per-offer proration outcomes not yet "
                             "evidenced", "3.3"),
        "tax_form": null("form number not printed in any on-disk filing. RIC "
                         "status implies 1099 but the cell is partial", "6.4"),
        "auditor": F("Cohen & Company, Ltd.", "4.5"),
        "big4": F(False, "4.5"),
        "expense_ratio_pct": F(1.36, "2.3",
                               note="FY2026 before waivers, EXCLUDING interest "
                                    "expense. 3.31% including interest"),
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
        "early_repurchase": null("exchange-listed with no repurchase program, "
                                 "so the fee is inapplicable", "2.7"),
        "repurchase_cadence_per_year": F(252, "3.1", status="computed",
                                         note="trading-days convention for daily "
                                              "on-exchange dealing - a derived "
                                              "figure, not a fund program"),
        "repurchase_cap_pct": null("on-exchange liquidity with no fund-level cap", "3.1"),
        "repurchase_cap_base": null("on-exchange liquidity with no fund-level cap", "3.1"),
        "gate_history": F(False, "3.1",
                          note="exchange wrapper has no gating mechanism. The "
                               "'no fund-level repurchase program' finding is "
                               "itself an absence-inference flagged in the cell"),
        "tax_form": null("form number not printed in any on-disk filing. RIC "
                         "status implies 1099 but the cell is partial", "6.4"),
        "auditor": F("KPMG LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": F(4.53, "2.3", note="FY2025, of average net assets"),
        "net_assets_usd": F(438000000, "2.3", approx=True,
                            note="$438.0M at 12/31/2025 as printed"),
        "inception": F("2022-05-12", "1.11",
                       note="commenced operations as printed. NYSE listing "
                            "2024-03-26 (3.1) is the trading-history start"),
    },
    "kkr_kpec": {
        "wrapper_type": F("nontraded_llc", "6.1"),
        "mgmt_fee_pct": F(1.25, "2.1"),
        "mgmt_fee_base": F("nav", "2.1", note="month-end NAV, Investor Shares"),
        "incentive_fee": F({"present": True, "rate_pct": 15.0,
                            "hurdle_pct": 5.0,
                            "structure": "Performance Participation Allocation "
                                         "with a high-water mark and 100% catch-up"},
                           "2.2"),
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
                                    "performance participation. NOT a "
                                    "1940-Act TER. Class range 2.74-3.59%"),
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
                                         "catch-up. FY2024 hurdle MISS produced "
                                         "a $105.0M shortfall obligation (2.2)"},
                           "2.4",
                           note="rate/hurdle printed in cell 2.4's fee-structure "
                                "discussion. Mechanics and shortfall in 2.2 (partial)"),
        "early_repurchase": F({"present": True, "rate_pct": 2.0,
                               "window": "< 1 year"}, "2.7",
                              note="repurchased at 98% of transaction price"),
        "repurchase_cadence_per_year": F(12, "3.1"),
        "repurchase_cap_pct": F(2.0, "3.1", note="monthly, with 5% quarterly"),
        "repurchase_cap_base": F("aggregate_nav", "3.1"),
        "gate_history": F(True, "3.3",
                          note="prorated repurchases 2022-24. FY2025 fulfilled 100%"),
        "tax_form": null("form number not printed in on-disk 10-K/10-Q. REIT "
                         "status implies 1099-DIV but the cell is partial", "6.4"),
        "auditor": F("Deloitte & Touche LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": null("no TER line item exists for this '34-Act "
                                  "wrapper. Components in 2.1/2.2/2.6", "2.9"),
        "net_assets_usd": null("aggregate NAV printed in the MD&A NAV-by-class "
                               "table but not yet carried into a typed cell. "
                               "Verification-queue item", "1.1"),
        "inception": null("explicit Class I inception date not printed in "
                          "on-disk filings. ITD basis year (2017 REIT "
                          "election) sits in partial cell 6.4", "6.4"),
    },
    "bcred": {
        "wrapper_type": F("nontraded_bdc", "6.1"),
        "mgmt_fee_pct": F(1.25, "2.1"),
        "mgmt_fee_base": F("net_assets", "2.1",
                           note="month-start net assets, payable monthly and "
                                "settled quarterly"),
        "incentive_fee": F({"present": True, "rate_pct": 12.5,
                            "hurdle_pct": 5.0,
                            "structure": "two-part BDC fee: 12.5% of income over "
                                         "a 5.0% annualized hurdle with 100% "
                                         "catch-up, PLUS 12.5% of realized "
                                         "capital gains"}, "2.2"),
        "early_repurchase": F({"present": True, "rate_pct": 2.0,
                               "window": "< 1 year"}, "2.7",
                              note="repurchased at 98% of NAV"),
        "repurchase_cadence_per_year": F(4, "3.1"),
        "repurchase_cap_pct": F(5.0, "3.1"),
        "repurchase_cap_base": F("nav", "3.1",
                                 note="board-discretionary quarterly tenders"),
        "gate_history": F(False, "3.3",
                          note="completed tenders printed every quarter "
                               "2023-2026H1, all requests satisfied"),
        "tax_form": F("1099", "6.4"),
        "auditor": F("Deloitte & Touche LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": F(7.0, "2.3",
                               note="FY2025 Class I, INCLUDES interest/financing "
                                    "cost of BDC leverage - not like-for-like "
                                    "with unlevered '40-Act ratios"),
        "net_assets_usd": null("aggregate net assets not yet carried into a "
                               "typed cell. Verification-queue item", "3.6"),
        "inception": F("2021-01-07", "1.11", note="escrow break / operations start"),
    },
    "pflex": {
        "wrapper_type": F("interval_23c3", "6.1"),
        "mgmt_fee_pct": F(1.30, "2.1"),
        "mgmt_fee_base": F("lesser_of_dual_base", "2.1",
                           note="LESSER of 1.30% of average daily total managed "
                                "assets (leverage-inclusive) and the net-assets "
                                "formulation, a hybrid base. Effective 4/1/2025"),
        "incentive_fee": F({"present": False}, "2.2",
                           note="unified management fee. No incentive-fee line "
                                "in the fee table"),
        "early_repurchase": F({"present": False}, "2.7",
                              note="no Rule 23c-3 early repurchase fee. 1.00% "
                                   "contingent load on A-2/A-4 classes only"),
        "repurchase_cadence_per_year": F(4, "3.1"),
        "repurchase_cap_pct": F(5.0, "3.1",
                                note="fundamental 5-25% policy, currently 5%"),
        "repurchase_cap_base": F("outstanding_shares", "3.1"),
        "gate_history": F(False, "3.3",
                          note="FY2025 offers undersubscribed (max 4.32% "
                               "tendered vs 5% cap)"),
        "tax_form": F("1099", "6.4"),
        "auditor": F("PricewaterhouseCoopers LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": F(1.97, "2.3",
                               note="FY2025 Institutional, EXCLUDING interest "
                                    "expense (5.12% including reverse-repo "
                                    "interest). Gross=net, no waivers"),
        "net_assets_usd": F(3596873000, "3.6", approx=True,
                            note="$3,596,873k net assets as printed"),
        "inception": F("2017-02-22", "1.11",
                       note="fund and Institutional class inception"),
    },
    "ocic": {
        "wrapper_type": F("nontraded_bdc", "6.1"),
        "mgmt_fee_pct": F(1.25, "2.1"),
        "mgmt_fee_base": F("net_assets", "2.1",
                           note="average net assets at the two most recently "
                                "completed month-ends, payable monthly in "
                                "arrears (advisory-agreement language "
                                "governs over contradictory risk-factor "
                                "boilerplate)"),
        "incentive_fee": F({"present": True, "rate_pct": 12.5,
                            "hurdle_pct": 5.0,
                            "structure": "two-part BDC fee: 12.5% of income "
                                         "over a 1.25%/quarter (5.0% "
                                         "annualized) NAV hurdle with 100% "
                                         "catch-up to 1.43%, PLUS 12.5% of "
                                         "cumulative net realized gains"},
                           "2.2"),
        "early_repurchase": F({"present": False}, "2.7",
                              note="N-2 fee table: no early withdrawal "
                                   "charge for any class - unlike bcred's "
                                   "2% deduction"),
        "repurchase_cadence_per_year": F(4, "3.1"),
        "repurchase_cap_pct": F(5.0, "3.1"),
        "repurchase_cap_base": F("outstanding_shares", "3.1",
                                 note="board-discretionary 13e-4 tenders "
                                      "that may be suspended or terminated "
                                      "at any time"),
        "gate_history": null("12 consecutive quarterly tenders completed "
                             "FY2023-FY2025 with no disclosed suspension, "
                             "BUT tendered-vs-repurchased counts are never "
                             "disclosed - proration cannot be ruled out "
                             "from public filings, so a clean False would "
                             "overclaim", "3.3"),
        "tax_form": F("1099", "6.4"),
        "auditor": F("KPMG LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": F(8.4, "2.3",
                               note="FY2025 actual net expense ratio, Class "
                                    "I, INCLUDES interest/financing cost of "
                                    "BDC leverage (N-2 fee-table totals "
                                    "9.94/9.34/9.09 S/D/I incl. 7.59% "
                                    "interest) - not like-for-like with "
                                    "unlevered '40-Act ratios"),
        "net_assets_usd": F(19760273000, "3.6", approx=True,
                            note="FY2025 net assets as printed"),
        "inception": F("2020-11-10", "1.11",
                       note="commenced operations. Renamed from Owl Rock "
                            "Core Income Corp. 2023-07-06"),
    },
    "cion_ares": {
        "wrapper_type": F("interval_23c3", "6.1"),
        "mgmt_fee_pct": F(1.25, "2.1"),
        "mgmt_fee_base": F("managed_assets", "2.1",
                           note="leverage-inclusive: total assets (incl. "
                                "assets attributable to Preferred Shares or "
                                "indebtedness) minus non-debt liabilities. "
                                "Equals 1.89% of net assets at FY2025 actual "
                                "leverage per the prospectus's own "
                                "restatement"),
        "incentive_fee": F({"present": True, "rate_pct": 15.0,
                            "hurdle_pct": 6.0,
                            "structure": "15% of income-only pre-incentive-fee "
                                         "net investment income per class, "
                                         "quarterly. 1.50%/quarter hurdle on "
                                         "average daily class NAV, full "
                                         "catch-up at 1.765%"}, "2.2"),
        "early_repurchase": F({"present": False}, "2.7",
                              note="'The Fund will not charge a repurchase "
                                   "fee' as printed. The only charge is a "
                                   "1.00% Class C CDSC on shares held < 365 "
                                   "days"),
        "repurchase_cadence_per_year": F(4, "3.1"),
        "repurchase_cap_pct": F(5.0, "3.1",
                                note="fundamental 5-25% policy. Fund states "
                                     "it expects only the 5% minimum"),
        "repurchase_cap_base": F("outstanding_shares", "3.1"),
        "gate_history": F(False, "3.3",
                          note="all four FY2025 offers at 5.00%, "
                               "undersubscribed (2.09-2.88% repurchased)"),
        "tax_form": F("1099", "6.4"),
        "auditor": F("Ernst & Young LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": F(3.76, "2.3",
                               note="FY2025 actual Class I EXCLUDING interest "
                                    "expense. Prospectus fee-table totals "
                                    "6.90% (I) to 7.74% (C) including 3.14% "
                                    "interest. No contractual cap: "
                                    "discretionary expense support only, $0 "
                                    "paid FY2025"),
        "net_assets_usd": F(5160261000, "3.6", approx=True,
                            note="FY2025 net assets as printed"),
        "inception": F("2017-01-26", "1.11",
                       note="commencement of operations (Class A). Class I "
                            "7/12/2017"),
    },
    "ares_pmf": {
        "wrapper_type": F("tender_offer", "6.1"),
        "mgmt_fee_pct": F(1.40, "2.1"),
        "mgmt_fee_base": F("managed_assets", "2.1",
                           note="leverage-inclusive: total assets incl. "
                                "borrowings minus non-borrowing liabilities"),
        "incentive_fee": F({"present": True, "rate_pct": 12.5,
                            "structure": "12.5% of quarterly net profits above "
                                         "the Loss Recovery Account balance "
                                         "(no fixed hurdle, the LRA carries "
                                         "losses forward)"}, "2.2"),
        "early_repurchase": F({"present": True, "rate_pct": 2.00,
                               "window": "< 1 year"}, "2.7", note="FIFO"),
        "repurchase_cadence_per_year": F(4, "3.1"),
        "repurchase_cap_pct": F(5.0, "3.1",
                                note="intended cap: 'quarterly repurchase offers of no "
                                     "more than 5% of the Fund's NET ASSETS', "
                                     "board-discretionary (Rule 13e-4 tenders)"),
        "repurchase_cap_base": F("net_assets", "3.1",
                                 note="board-discretionary quarterly tenders"),
        "gate_history": F(False, "3.3",
                          note="four offers conducted in each of FY2025/FY2026"),
        "tax_form": F("1099", "6.4"),
        "auditor": F("Ernst & Young LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": F(5.02, "2.3",
                               note="FY2026 Class I gross (net 4.99% after "
                                    "0.03% waiver). Includes 1.60% incentive-"
                                    "fee drag. AFFE excluded"),
        "net_assets_usd": null("aggregate net assets not yet carried into a "
                               "typed cell. Verification-queue item", "3.6"),
        "inception": F("2022-04-01", "1.11", note="commenced operations"),
    },
    "amg_pantheon": {
        "wrapper_type": F("tender_offer", "6.1"),
        "mgmt_fee_pct": F(0.70, "2.1", note="the cohort's lowest headline rate"),
        "mgmt_fee_base": F("net_assets", "2.1", note="month-end net assets"),
        "incentive_fee": F({"present": False}, "2.2",
                           note="no incentive fee at Fund or Master level - "
                                "fee tables print none"),
        "early_repurchase": F({"present": True, "rate_pct": 2.00,
                               "window": "< 1 year"}, "2.7", note="FIFO"),
        "repurchase_cadence_per_year": F(4, "3.3"),
        "repurchase_cap_pct": F(5.0, "3.3",
                                note="live offer approx. 5% of outstanding Units"),
        "repurchase_cap_base": F("outstanding_shares", "3.3"),
        "gate_history": F(False, "3.3"),
        "tax_form": F("1099", "6.4"),
        "auditor": F("KPMG LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": F(2.38, "2.3",
                               note="Class 4 (inception class) Total Annual "
                                    "Expenses. Classes range 2.38-3.38% "
                                    "(differ only by distribution/servicing)"),
        "net_assets_usd": null("aggregate net assets not yet carried into a "
                               "typed cell. Verification-queue item", "3.6"),
        "inception": F("2014-09-30", "1.11",
                       note="Fund inception (Class 4) - the roster's longest "
                            "'40-Act evergreen-PE record"),
    },
    "sreit": {
        "wrapper_type": F("nontraded_reit", "6.1"),
        "mgmt_fee_pct": F(1.25, "2.1"),
        "mgmt_fee_base": F("nav", "2.1"),
        "incentive_fee": F({"present": True, "rate_pct": 12.5,
                            "structure": "performance participation to the "
                                         "Special Limited Partner (see cell "
                                         "2.2 for full mechanics)"}, "2.2"),
        "early_repurchase": F({"present": True, "rate_pct": 5.0,
                               "window": "< 1 year"}, "2.7",
                              note="repurchased at 95% of transaction price - "
                                   "the cohort's steepest early deduction"),
        "repurchase_cadence_per_year": F(12, "3.1",
                                         note="monthly share repurchase plan. Ordinary "
                                              "requests closed by the April 29, 2026 "
                                              "amendment"),
        "repurchase_cap_pct": F(0.0, "3.1",
                                note="0% for ordinary requests since April 29, 2026 "
                                     "(death, qualifying disability and sub-$5,000 "
                                     "accounts only). Cap history: 2%/month and 5%/quarter "
                                     "(2017), 0.33%/1% (May 2024), 0.5%/1.5% (June 2025)"),
        "repurchase_cap_base": F("aggregate_nav", "3.1",
                                 note="measured on prior month and quarter NAV before "
                                      "the closure"),
        "gate_history": F(True, "3.3",
                          note="requests exceeded plan limits continuously "
                               "since October 2022. Caps shrank three times, "
                               "then the plan closed"),
        "tax_form": null("form number not printed in on-disk filings. REIT "
                         "status implies 1099-DIV but the cell is partial",
                         "6.4"),
        "auditor": F("Deloitte & Touche LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": null("no TER line exists for this '34-Act "
                                  "wrapper. Components in 2.1/2.2/2.6", "2.3"),
        "net_assets_usd": null("aggregate NAV not yet carried into a typed "
                               "cell. Verification-queue item", "1.1"),
        "inception": F("2017-12-27", "1.11", note="IPO commencement"),
    },
    "jll_ipt": {
        "wrapper_type": F("nontraded_reit", "6.1"),
        "mgmt_fee_pct": F(1.25, "2.1",
                          note="temporary partial waiver 2025-10-07 through "
                               "2026-12-31 (see cell 2.1)"),
        "mgmt_fee_base": F("nav", "2.1", note="NAV calculated DAILY"),
        "incentive_fee": F({"present": True, "rate_pct": 10.0,
                            "hurdle_pct": 7.0,
                            "structure": "10% of each class's total return "
                                         "above 7%/yr, per calendar year. No "
                                         "fees earned FY2023-FY2025"}, "2.2"),
        "early_repurchase": F({"present": False}, "2.7",
                              note="no fee. One-year holding period with "
                                   "death/disability exceptions"),
        "repurchase_cadence_per_year": F(252, "3.1", status="computed",
                                         note="daily repurchase requests per cell "
                                              "3.1, trading-day convention, the "
                                              "cap applies per quarter"),
        "repurchase_cap_pct": F(5.0, "3.1"),
        "repurchase_cap_base": F("nav", "3.1",
                                 note="combined NAV of all classes, prior "
                                      "quarter-end"),
        "gate_history": F(False, "3.3",
                          note="never deferred nor rejected a request "
                               "through 2025-12-31, as disclosed"),
        "tax_form": null("tax-form name not literally printed. REIT status "
                         "and possible return-of-capital character are "
                         "printed (cell 6.4)", "6.4"),
        "auditor": F("KPMG LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": null("no TER line exists for this '34-Act "
                                  "wrapper. Components in 2.1/2.2/2.6", "2.3"),
        "net_assets_usd": null("aggregate NAV not yet carried into a typed "
                               "cell. Verification-queue item", "3.6"),
        "inception": F("2012-10-01", "1.11",
                       note="continuous public offering commencement (REIT-"
                            "taxed since 2004 as a private predecessor)"),
    },
    "ssss": {
        "wrapper_type": F("listed_bdc", "6.1"),
        "mgmt_fee_pct": F(1.75, "2.1",
                          note="EFFECTIVE 2026-07-15 (externalization): prior "
                               "history was internally managed with no "
                               "external fee - the track record and the fee "
                               "regime do not overlap"),
        "mgmt_fee_base": F("gross_incl_borrowings", "2.1",
                           note="GROSS assets - leverage-inclusive base"),
        "incentive_fee": F({"present": True, "hurdle_pct": 7.0,
                            "structure": "two-part BDC fee (income + capital "
                                         "gains) per the 2026-07-15 "
                                         "externalization. Hurdle 7.00% "
                                         "annualized. Full terms in cell 2.2"},
                           "2.2"),
        "early_repurchase": null("exchange-listed. Exit is on-market, so no "
                                 "repurchase program fee applies", "2.7"),
        "repurchase_cadence_per_year": F(252, "3.1",
                                         note="daily on-exchange dealing "
                                              "(Nasdaq: NSLR)"),
        "repurchase_cap_pct": null("on-exchange liquidity with no fund-level cap",
                                   "3.1"),
        "repurchase_cap_base": null("on-exchange liquidity with no fund-level cap",
                                    "3.1"),
        "gate_history": F(False, "3.3",
                          note="no redemption right exists to gate"),
        "tax_form": null("form number not printed in on-disk filings. RIC "
                         "status implies 1099 but the cell is partial", "6.4"),
        "auditor": F("CBIZ CPAs P.C.", "4.5"),
        "big4": F(False, "4.5",
                  note="the venture cohort's only non-Big-4 audit"),
        "expense_ratio_pct": F(9.46, "2.3",
                               note="FY2025 net operating expenses/avg net "
                                    "assets UNDER INTERNAL MANAGEMENT. The "
                                    "fee regime changed 2026-07-15, so forward "
                                    "ratios will differ (see 2.1/2.2)"),
        "net_assets_usd": null("aggregate net assets not yet carried into a "
                               "typed cell. Verification-queue item", "3.6"),
        "inception": F("2011-01-06", "1.11",
                       note="the roster's longest listed record (~15 years)"),
    },
    "arkvx": {
        "wrapper_type": F("interval_23c3", "6.1"),
        "mgmt_fee_pct": F(2.75, "2.1"),
        "mgmt_fee_base": F("net_assets", "2.1", note="average daily net assets"),
        "incentive_fee": F({"present": False}, "2.2",
                           note="flat management fee only - absence documented"),
        "early_repurchase": F({"present": False}, "2.7",
                              note="all repurchases at NAV, no early fee"),
        "repurchase_cadence_per_year": F(4, "3.1"),
        "repurchase_cap_pct": F(5.0, "3.1",
                                note="fundamental 5-25% policy. Every "
                                     "completed offer at 5%"),
        "repurchase_cap_base": F("outstanding_shares", "3.1"),
        "gate_history": F(False, "3.3",
                          note="no gating or postponement disclosed"),
        "tax_form": F("1099", "6.4"),
        "auditor": F("Ernst & Young LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": F(2.90, "2.3",
                               note="FY2025 net of waivers (gross 4.39%), "
                                    "single class"),
        "net_assets_usd": null("aggregate net assets not yet carried into a "
                               "typed cell. Verification-queue item", "3.6"),
        "inception": F("2022-09-01", "1.11", note="commencement of operations"),
    },
    "stepstone_spm": {
        "wrapper_type": F("tender_offer", "3.1"),
        "mgmt_fee_pct": F(1.40, "2.1"),
        "mgmt_fee_base": F("net_assets", "2.1", note="daily net assets"),
        "incentive_fee": null("cell 2.2 is partial: no fund-level incentive fee "
                              "identified. Underlying funds charge performance "
                              "fees (AFFE layer)", "2.2"),
        "early_repurchase": null("cell 2.7 is partial: no early-repurchase-fee "
                                 "language matched. Confirmation pending", "2.7"),
        "repurchase_cadence_per_year": F(4, "3.1"),
        "repurchase_cap_pct": F(5.0, "3.1"),
        "repurchase_cap_base": F("outstanding_shares", "3.1"),
        "gate_history": null("per-offer tendered-vs-purchased counts not "
                             "printed in on-disk filings. Sept 2025 offer was "
                             "Board-UPSIZED (demand signal). Proration "
                             "incidence unevidenced", "3.3"),
        "tax_form": F("1099", "6.4"),
        "auditor": F("Ernst & Young LLP", "4.5"),
        "big4": F(True, "4.5"),
        "expense_ratio_pct": F(1.91, "2.3", note="FY2026 Class I, AFFE excluded"),
        "net_assets_usd": F(5828900000, "3.6", approx=True,
                            note="$5,828.9M at 3/31/2026 as printed"),
        "inception": F("2020-10-01", "1.2", note="Class I/D/S inception"),
    },
}

# Acquired fund fees and expenses, typed from cell 2.4: the printed line where
# a 1940-Act fee table exists, an explicit absence where the filing says the
# line does not exist, null with the cell's reason where the cell itself is
# n/a or partial. Feeds the Fee Matrix chip, which used to be a regex over
# the cell prose and read the opposite of the finding.
AFFE = {
    "amg_pantheon": F({"present": True, "rate_pct": 0.81}, "2.4"),
    "ares_pmf": F({"present": True, "rate_pct": 1.00}, "2.4"),
    "arkvx": F({"present": True, "rate_pct": 0.01}, "2.4"),
    "bcred": F({"present": True, "rate_pct": 0.02}, "2.4"),
    "breit": F({"present": False}, "2.4",
               note="10-K REIT, no 1940-Act fee table, so no AFFE line exists"),
    "cion_ares": null("cell 2.4 is n/a (documented-unavailable): no AFFE line in "
                      "any class fee table", "2.4"),
    "cliffwater_cclfx": F({"present": True, "rate_pct": 0.25}, "2.4"),
    "dxyz": F({"present": True, "rate_pct": 0.03}, "2.4"),
    "hl_paf": F({"present": True, "rate_pct": 0.49}, "2.4",
                note="2021 486BPOS fee table"),
    "jll_ipt": F({"present": False}, "2.4",
                 note="10-K REIT, no 1940-Act fee table, so no AFFE line exists"),
    "kkr_kpec": null("cell 2.4 is partial: no 1940-Act fee table, absence "
                     "inferred from a full-text search", "2.4"),
    "ocic": F({"present": True, "rate_pct": 0.0}, "2.4",
              note="line printed as 0% (shown as a dash) for all classes"),
    "pflex": F({"present": False}, "2.4",
               note="no AFFE line in the Summary of Fund Expenses"),
    "sreit": F({"present": False}, "2.4",
               note="10-K REIT, no 1940-Act fee table, so no AFFE line exists"),
    "ssss": F({"present": True, "rate_pct": 0.06}, "2.4"),
    "stepstone_spm": F({"present": True, "rate_pct": 0.59}, "2.4"),
}
for _k, _v in AFFE.items():
    MAPPING[_k]["affe"] = _v


# per-product as-of dates and cohort metadata come from the one registry
_REG = json.loads((DATA / "registry.json").read_text())["products"]
AS_OF = {k: v["as_of"] for k, v in _REG.items()}
COHORT_META = {k: (v["cohort"], v["depth"], v["membership_rationale"]) for k, v in _REG.items()}

# expense_ratio_pct basis (R2-P0-8, audit round 2 item 10): the headline
# prints what the record holds, never "net" unless the note says net. Each
# clause restates the fact's own note in reader words.
EXPENSE_BASIS = {
    "hl_paf": "net, including the incentive fee, AFFE excluded (FY2026, Class I)",
    "cliffwater_cclfx": "before waivers, excluding interest expense (3.31% including interest, FY2026)",
    "dxyz": "of average net assets (FY2025)",
    "kkr_kpec": "GAAP total operating expenses including the 2.75% performance participation, not a 1940-Act ratio (FY2025, Class I)",
    "bcred": "including the interest and financing cost of BDC leverage (FY2025, Class I)",
    "pflex": "excluding interest expense (5.12% including reverse-repo interest), gross equals net, no waivers (FY2025, Institutional)",
    "ocic": "net, including the interest and financing cost of BDC leverage (FY2025, Class I)",
    "cion_ares": "excluding interest expense (6.90% including interest per the fee table), no contractual cap (FY2025, Class I)",
    "ares_pmf": "gross, before a 0.03% waiver, including the 1.60% incentive-fee drag, AFFE excluded (FY2026, Class I)",
    "amg_pantheon": "total annual expenses of the inception class, classes range 2.38% to 3.38%",
    "ssss": "net operating expenses under internal management, the fee regime changed 2026-07-15 (FY2025)",
    "arkvx": "net of waivers, 4.39% gross (FY2025)",
    "stepstone_spm": "AFFE excluded (FY2026, Class I)",
}
for _k, _b in EXPENSE_BASIS.items():
    assert MAPPING[_k]["expense_ratio_pct"]["value"] is not None, _k
    MAPPING[_k]["expense_ratio_pct"]["basis"] = _b

# repurchase_program_status (P1-17): "suspended" only where cell 3.1 or 3.3
# carries suspension language. Everything else is null with the reason, so
# nothing is ever "active" by default.
for _key, _m in MAPPING.items():
    if _key == "sreit":
        _m["repurchase_program_status"] = F(
            "suspended", "3.1", since="April 29, 2026 amendment",
            note="April 29, 2026 amendment: 'no repurchase requests will be accepted' "
                 "except death, qualifying disability and accounts below $5,000")
    elif _m["wrapper_type"]["value"] in ("listed_cef", "listed_bdc"):
        _m["repurchase_program_status"] = null("exchange-listed, no repurchase program", "3.1")
    else:
        _m["repurchase_program_status"] = null(
            f"no suspension language in 3.1 or 3.3 as of {AS_OF[_key]}", "3.1")

# Dealing cadence and repurchase caps (R2-P0-5), typed from cell 3.1's own
# words. The dealing cadence is how often a holder can deal (daily, monthly,
# quarterly, or on an exchange). Each cap names the period it is measured
# over, and a product may carry more than one cap. The two are separate facts
# because jll_ipt takes repurchase requests daily under a quarterly cap and
# breit carries a monthly cap and a quarterly cap at once. The engine takes
# the binding annual figure from the cap list, never cadence * cap.
# Row: (dealing cadence, cap period, caps as (pct, period) pairs, the words
# of cell 3.1 that support them). An exchange-listed row carries None for the
# cap period and the caps, with the reason below.
_NO_FUND_CAP = "on-exchange liquidity with no fund-level cap"
DEALING_TERMS = {
    "hl_paf": ("quarterly", "quarter", [(5.0, "quarter")],
               "'Quarterly tender offers', 'up to 5.00% of net assets'"),
    "cliffwater_cclfx": ("quarterly", "quarter", [(5.0, "quarter")],
                         "'up to five percent (5%) of outstanding shares, quarterly'"),
    "dxyz": ("exchange", None, None,
             "'daily on-exchange liquidity' and 'no fund-level repurchase program'"),
    "kkr_kpec": ("quarterly", "quarter", [(5.0, "quarter")],
                 "'Quarterly share repurchase plan: limited to 5.0% of aggregate NAV "
                 "... per calendar quarter'"),
    "breit": ("monthly", "month", [(2.0, "month"), (5.0, "quarter")],
              "'Repurchase caps: 2% of aggregate NAV per MONTH, 5% per QUARTER'. "
              "The monthly cap is the headline cap and the quarterly cap binds "
              "over a year (2 * 12 = 24 versus 5 * 4 = 20)"),
    "bcred": ("quarterly", "quarter", [(5.0, "quarter")],
              "'CADENCE: quarterly tender offers at Board discretion', 'CAP: up to "
              "5% of the NAV of Common Shares outstanding'"),
    "pflex": ("quarterly", "quarter", [(5.0, "quarter")],
              "'quarterly repurchase offers for between 5% and 25% of outstanding "
              "Common Shares', 'currently expects 5% per quarter'"),
    "ocic": ("quarterly", "quarter", [(5.0, "quarter")],
             "'quarterly issuer tender offers', 'capped at 5.00% of outstanding "
             "shares per quarter'"),
    "cion_ares": ("quarterly", "quarter", [(5.0, "quarter")],
                  "'quarterly repurchase offers of between 5% and 25% of outstanding "
                  "shares', 'expects to offer only the 5% minimum each quarter'"),
    "ares_pmf": ("quarterly", "quarter", [(5.0, "quarter")],
                 "'quarterly repurchase offers of no more than 5% of the Fund's NET "
                 "ASSETS'"),
    "amg_pantheon": ("quarterly", "quarter", [(5.0, "quarter")],
                     "'recommending quarterly offers', 'CAP: expected up to 5% per "
                     "offer'"),
    "sreit": ("monthly", "month", [(0.0, "month")],
              "'Monthly share repurchase plan'. 0% for ordinary requests since the "
              "April 29, 2026 amendment ('no repurchase requests will be accepted' "
              "except death, qualifying disability and accounts below $5,000). Cap "
              "history: 2% per month and 5% per quarter (2017), 0.33% and 1% (May "
              "2024), 0.5% and 1.5% (June 2025)"),
    "jll_ipt": ("daily", "quarter", [(5.0, "quarter")],
                "'CADENCE: DAILY - stockholders may request repurchase ... any day at "
                "that day's NAV per share', 'CAP: 5% of the combined NAV of all "
                "classes per calendar quarter'"),
    "ssss": ("exchange", None, None,
             "'cadence: any trading day' and 'cap: none (market depth only)'"),
    "arkvx": ("quarterly", "quarter", [(5.0, "quarter")],
              "'CADENCE: quarterly Rule 23c-3 repurchase offers', 'every actual "
              "offer to date has been, the 5% minimum'"),
    "stepstone_spm": ("quarterly", "quarter", [(5.0, "quarter")],
                      "'Quarterly tender offers: up to 5% of OUTSTANDING SHARES'"),
}
for _key, (_dc, _cp, _caps, _words) in DEALING_TERMS.items():
    _m = MAPPING[_key]
    _m["dealing_cadence"] = F(_dc, "3.1", note=f"cell 3.1: {_words}")
    if _caps is None:
        _m["cap_period"] = null(_NO_FUND_CAP, "3.1")
        _m["repurchase_caps"] = null(_NO_FUND_CAP, "3.1")
    else:
        _m["cap_period"] = F(_cp, "3.1", note=f"cell 3.1: {_words}")
        _m["repurchase_caps"] = F([{"pct": p, "period": per} for p, per in _caps],
                                  "3.1", note=f"cell 3.1: {_words}")


def years_between(d0: str, d1: str) -> float:
    from datetime import date
    a = date(*map(int, d0.split("-")))
    b = date(*map(int, d1.split("-")))
    return round((b - a).days / 365.25, 1)


def main() -> None:
    out_dir = DATA / "facts"
    out_dir.mkdir(exist_ok=True)
    plans = plan_keys()
    FIELD_ORDER = list(MAPPING["hl_paf"].keys())
    for key in product_keys():
        cells = load_product(key)["cells"]
        cohort_id, depth, rationale = COHORT_META[key]
        if key not in MAPPING:
            # cohort-tier product whose extraction has not landed: an honest
            # all-null scaffold (screener shows the reason, never a blank)
            facts = {field: {"value": None, "source_cell": "6.1",
                             "status": "pending",
                             "reason": "cohort-tier extraction in progress "
                                       "(see data/roster_decisions.md)"}
                     for field in FIELD_ORDER}
            facts["track_record_years"] = dict(facts["inception"])
            doc = {"product_key": key, "cohort_id": cohort_id, "depth": depth,
                   "membership_rationale": rationale,
                   "what": "typed projections of evidenced cells - scaffold "
                           "pending cohort-tier extraction",
                   "generated_by": "src/build_facts.py",
                   "facts": facts}
            (out_dir / f"{key}.json").write_text(json.dumps(doc, indent=2))
            print(f"{key}: SCAFFOLD (extraction in progress)")
            continue
        facts = {}
        for field, f in MAPPING[key].items():
            cell = cells[f["source_cell"]]
            # the cell's status is the default; an explicit status on the
            # mapping (a derived convention such as 252 trading days) wins,
            # so a computed figure never masquerades as extracted evidence
            facts[field] = {**f, "status": f.get("status") or cell.get("status", "pending")}
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
        # engine outputs: pulled from artifacts, never retyped. The liquidity
        # verdicts come from the match files whenever they exist, independent
        # of whether a benchmark selection exists (P1-13 decoupling).
        match_paths = {pk: DATA / "liquidity" / f"{pk}__{key}_match.json" for pk in plans}
        if all(mp.exists() for mp in match_paths.values()):
            matches = {pk: json.loads(mp.read_text()) for pk, mp in match_paths.items()}
            # the first facts pass of produce.py runs before the liquidity
            # pass, so the match files it sees may predate this build: read
            # tolerantly, the engine pass fills the final values
            structural = {m.get("verdict") for m in matches.values()}
            assert len(structural) == 1, f"{key}: structural verdict differs across plans"
            facts["liquidity_structural_verdict"] = {
                "value": structural.pop(), "source_cell": "3.9", "status": "computed",
                "note": "from typed facts only (cells 3.1, 3.3, 2.7), plan-independent"}
            facts["liquidity_verdict_by_plan"] = {
                "value": {pk: m.get("scenario_verdict") for pk, m in matches.items()},
                "source_cell": "3.9", "status": "computed",
                "note": "ILLUSTRATIVE scenario verdict per plan (demand model at the "
                        "default sliders against the typed capacity)"}
        else:
            facts["liquidity_structural_verdict"] = {
                "value": None, "source_cell": "3.9", "status": "pending",
                "reason": "liquidity match not yet run"}
            facts["liquidity_verdict_by_plan"] = {
                "value": None, "source_cell": "3.9", "status": "pending",
                "reason": "liquidity match not yet run"}
        sel_path = DATA / "benchmarks" / f"{key}_selection.json"
        sel = json.loads(sel_path.read_text()) if sel_path.exists() else None
        # the statistic is named for its comparator (R2-P0-6, rule 12): a PME
        # only against a public market series, a relative wealth ratio against
        # the peer composite, each from whichever slot carries that comparator
        ENGINE_NULL = ("primary_benchmark_id", "selection_score", "pme_public_proxy",
                       "pme_public_proxy_name", "direct_alpha_public_proxy", "peer_relative_wealth_ratio")
        if sel is None:
            for fld in ENGINE_NULL:
                facts[fld] = {"value": None, "source_cell": "1.8",
                              "status": "pending",
                              "reason": "engine selection not yet run for this product"}
        elif sel.get("primary"):
            from tark_display import candidate_short
            slots = [s for s in (sel.get("primary"), sel.get("secondary")) if s]
            series_slot = next((s for s in slots if (s.get("comparison") or {}).get("kind") == "series"), None)
            comp_slot = next((s for s in slots if (s.get("comparison") or {}).get("kind") == "composite"), None)
            facts["primary_benchmark_id"] = F(sel["primary"]["id"], "5.3",
                                              status="computed")
            facts["selection_score"] = F(sel["primary"]["score"], "5.3",
                                         status="computed")
            # .get throughout: the first facts pass of the producer runs before
            # the benchmark step and may read an older artifact, which the
            # facts-engine pass then overwrites
            if series_slot:
                c = series_slot["comparison"]
                name = candidate_short(series_slot["id"])
                note = (f"KS-PME vs {name} over {c.get('window')}, fund return source: "
                        f"{c.get('fund_return_source', '')}")
                facts["pme_public_proxy"] = F(c.get("ks_pme"), "1.8", status="computed", note=note)
                facts["pme_public_proxy_name"] = F(name, "1.8", status="computed")
                facts["direct_alpha_public_proxy"] = F(c.get("direct_alpha_pct"), "1.8", status="computed", note=note)
            else:
                why = ((sel["primary"].get("comparison_note") or
                        "no public market proxy comparison computable on held data"))
                for fld in ("pme_public_proxy", "pme_public_proxy_name", "direct_alpha_public_proxy"):
                    facts[fld] = {"value": None, "source_cell": "1.8",
                                  "status": "computed", "reason": why}
            if comp_slot:
                c = comp_slot["comparison"]
                facts["peer_relative_wealth_ratio"] = F(
                    c.get("relative_wealth_ratio"), "1.8", status="computed",
                    note=(f"relative wealth ratio vs {candidate_short(comp_slot['id'])} over {c.get('window')}, "
                          "fund return source: filed fiscal-year returns. Not a public market equivalent"))
            else:
                facts["peer_relative_wealth_ratio"] = {
                    "value": None, "source_cell": "1.8", "status": "computed",
                    "reason": "no peer composite comparison in either slot for this product"}
        else:
            esc = ("engine escalation: no meaningful benchmark constructible "
                   "(see the selection artifact)")
            for fld in ENGINE_NULL:
                facts[fld] = {"value": None, "source_cell": "1.8",
                              "status": "computed", "reason": esc}
        doc = {"product_key": key, "cohort_id": cohort_id, "depth": depth,
               "membership_rationale": rationale,
               "what": "typed projections of evidenced cells, zero new facts. "
                       "Every field carries its source_cell and mirrors its status",
               "generated_by": "src/build_facts.py (hand-mapping machine-checked "
                               "by validate_data.py)",
               "facts": facts}
        (out_dir / f"{key}.json").write_text(json.dumps(doc, indent=2))
        print(f"{key}: {len(facts)} fields, "
              f"{sum(1 for f in facts.values() if f['value'] is None)} honest nulls")


if __name__ == "__main__":
    main()

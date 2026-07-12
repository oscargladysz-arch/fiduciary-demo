# Extraction Worksheet — Hamilton Lane Private Assets Fund (hl_paf)
### Maps every dictionary cell to the exact downloaded document + section. Standard: script fetches, HUMAN reads and extracts, CF2 verifies.

**The documents you have (data/raw/hl_paf/):**
| File | What it is | Use it for |
|---|---|---|
| `N-CSR_2026-06-09_...ncsr.htm` (7.5MB) | FY2026 annual report (fiscal year ended Mar 31, 2026) | **FRESHEST source.** Returns, expense ratios, fee notes, fair-value note, auditor, schedule of investments, repurchase notes |
| `SC TO-I_2026-05-06_...sctoi.htm` | Current quarterly tender offer | Live liquidity terms (5.00% + 2.00% upsize), derived net assets ~$5.80B |
| `486BPOS_2021-07-29_...` (1.9MB) | BASE prospectus (2021) | Structure, policy language, incentive-fee TERMS, share classes, tax section. Numbers here are 2021-dated — confirm currency against N-CSR |
| `424B3_2026-05-08_...` (8KB) | Prospectus supplement | Check what changed vs. base |
| `486BXT_2023-09-25_...` | Effectiveness extension | Low value; skip |
| `NPORT-P_2026-05-29_...xml` | Monthly portfolio holdings (XML) | Portfolio liquidity profile, cash sleeve |

**Workflow per cell:** open the file in a browser → Cmd+F the search terms below → paste value + short quote + section name into `data/evidence/hl_paf_evidence.csv` → set status `extracted-unverified` → CF2 independently re-checks and flips to `verified`.

## Cell-by-cell map
| Cell | Where | Search terms / notes | Status |
|---|---|---|---|
| 1.1 Net return series | N-CSR Financial Highlights (annual NAV/share seeded); monthly series → HL fund website fact sheets (external) | "Net Asset Value per share" | partial (seeded) |
| 1.2 Trailing returns | N-CSR "Fund Performance" | seeded — verify | extracted |
| 1.3 Gross vs net | N-CSR highlights + 2.x cells | "Gross expenses" | pending |
| 1.4 Distributions | N-CSR Financial Highlights distribution rows + Statements of Changes; 19(a) notices on fund site | "Total distributions" — check income vs return-of-capital split | pending |
| 1.5 Underlying GP funds | **N-CSR Consolidated Schedule of Investments = the named list of underlying funds. This IS CF2's pension-backdoor target list — hand it to him.** | "Schedule of Investments" | pending → CF2 |
| 1.6/1.8/1.9 Computed | L3 — after 1.1 monthly series exists | — | blocked on 1.1 |
| 1.11 Track record | 486BPOS "Management of the Fund" + adviser Form ADV (adviserinfo.sec.gov) | "portfolio manager" | pending |
| 2.1 Mgmt fee | seeded: 1.40% on MANAGED ASSETS (N-CSR note). Cross-check 486BPOS fee table | "Investment Management Fee" | extracted |
| 2.2 Incentive fee TERMS | 486BPOS "Incentive Fee" section (rate/hurdle/crystallization); drag already seeded from N-CSR fn.5. Confirm terms unchanged via 424B3 | "Incentive Fee" | partial |
| 2.3 Expense ratios | seeded from highlights + expense-limit note | — | extracted |
| 2.4 AFFE | 486BPOS fee table footnotes | "Acquired Fund Fees" | pending |
| 2.5 Underlying GP economics | NOT in filings — L2 (CF2 lane) | — | L2 hole |
| 2.6 Loads/servicing | 486BPOS share class table + Distribution Plan | "Distribution and Servicing" | pending |
| 2.7 Early repurchase fee | seeded: 2.00% < 1yr | — | extracted |
| 3.1/3.2 Liquidity terms | seeded from SC TO-I; policy language in 486BPOS "Repurchases" | "offer to purchase" | extracted |
| 3.3 Repurchase history | N-CSR repurchase note (shares tendered vs bought). Fuller history = pull prior SC TO-I filings (fetcher can be extended) | "tendered" | pending |
| 3.4 Portfolio liquidity | NPORT-P xml + N-CSR SOI (% Level 3, cash) | — | pending |
| 3.6 Leverage | seeded: $76.5M credit line | — | extracted |
| 3.7–3.9 | Plan-side / L3 workflow — not product cells | — | n/a here |
| 4.1 Valuation policy | 486BPOS "Determination of Net Asset Value" + N-CSR fair-value note ("Valuation Designee") | "net asset value" | pending |
| 4.2 ASC 820 table | N-CSR "Fair Value Measurements" — read the Level 1/2/3 dollar table by hand | "Level 3" | partial |
| 4.3 Valuation agent | Same sections — identify independent valuation firm if named | "independent valuation" | pending |
| 4.5 Auditor | seeded: Cohen & Company, Cleveland — NOT Big-4 (evaluative datum) | — | extracted |
| 5.1 Stated benchmark | N-CSR "Fund Performance" comparison index (an index is referenced there) + 486BPOS | "Index" | pending — likely quick |
| 6.1–6.3, 6.5 | 486BPOS body + SAI part | "Conflicts of Interest" | pending |
| 6.4 Tax reporting | 486BPOS "U.S. Federal Income Tax" — PAF is a RIC → expect 1099 (confirm) | "Form 1099" | pending |

**Time estimate for the pending cells: one focused hour.** Everything is Cmd+F, not archaeology.

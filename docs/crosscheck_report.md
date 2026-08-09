# Cross-check report — independent re-location pass (CF2 accelerator)

**Date:** 2026-08-08
**Run by:** Claude Code (evidence pass 3) — six independent checker agents, one per product, each re-locating every `extracted-unverified` cell in the cited on-disk document from scratch.
**Scope:** all 44 cells at status `extracted-unverified` across the six products at the time of the run.
**Integrity note:** no cell statuses were changed by this pass. Nothing here is `verified` — that flip is reserved for the human verifier (CF2). Cells marked ✦ were extracted earlier the same day by this same workstream (pass 3); their cross-check was done by separate agent instances against the raw document, but CF2 should weight them as less independent than the checks of the older extractions.

Locations are given as document + section + a searchable anchor phrase (open the HTML in a browser and Cmd+F the anchor).

---

## 1. Confirmed (42 cells)

### breit — 7/7 confirmed (10-K 2026-02-27 unless noted)
- **2.1 Management fee** — 1.25% of NAV payable monthly (cash/shares/OP units at Adviser's election) + DST program fee 1.0% of gross rents; Notes, Related Party Transactions ("Accrued Management Fee" / "DST Program").
- **2.7 Early repurchase fee** ✦ — 98% of transaction price for shares held <1 year; DRIP, Adviser fee-share and SLP performance-share exemptions and the 2%/5% cap-math exclusion all present; Part II Item 5 ("Early Repurchase Deduction").
- **3.1 Wrapper liquidity terms** — 2%/month + 5%/quarter of aggregate NAV, board may modify/suspend; Part II Item 5 + Item 1A.
- **3.3 Repurchase history** ✦ — cash-flow rows 6,132,773 / 9,307,418 / 12,419,310 ($000s, FY25/24/23); "$6.2 billion … all repurchase requests received"; 441.1M shares + 5.6M OP units; Q4-25 monthly 0.9/0.8/0.7% NAV all satisfied; "periods of prorated fulfillment" in Item 1A. All verified.
- **3.6 Leverage** — charter cap: no borrowing >300% of cost of net assets (≈75% LTC) absent independent-director approval; Item 1 Financing Strategy.
- **4.4 Methodology by asset type** ✦ — all eight discount/exit-cap pairs match exactly (Rental Housing 7.2/5.4 … Retail 7.9/6.3); sensitivity range 1.0%–3.1% confirmed; MD&A NAV tables.
- **4.5 Auditor** — Deloitte & Touche LLP, New York, "auditor since 2016", report dated 2026-02-27; audit-report signature block.

### cliffwater_cclfx — 5/6 confirmed (N-CSR 2026-06-08 unless noted)
- **1.2 Trailing returns** — 9.34% since-inception (verbatim, in Letter to Shareholders rather than the cited Fund Performance section — same document, adjacent section); AATR 7.63/10.89/9.79/9.34 vs index 4.81/8.00/5.93/5.51; FY total-return row 7.61/11.58/13.34/7.06/1.79/10.38 all match.
- **2.1 Management fee** — 1.00% annualized of daily net assets, monthly; Note 4 Investment Advisory Agreements, verbatim.
- **2.3 Expense ratios** — ex-interest before-waiver 1.36/1.32/1.20/1.23/1.28/1.32 (FY26→FY21) and 3.31% incl. interest FY26; Financial Highlights ratio rows.
- **3.1 Wrapper liquidity terms** — Rule 23c-3 periodic repurchase offer (box A checked on Form N-23c-3 cover), quarterly, at NAV; 8-quarter N-23C3A series matches the 8 files on disk; N-23C3A 2026-05-08.
- **4.5 Auditor** ✦ — Cohen & Company, Ltd., Cleveland, Ohio, "auditor … since 2019", unqualified, dated May 30, 2026; audit-report signature block.
- *(5.1 — see Discrepancies)*

### dxyz — 4/5 confirmed (N-CSR 2026-03-10)
- **1.2 Trailing returns** — market-value total return (47.96)% 2025 / 613.45% 2024-from-listing (footnote 6 confirms 3/26/2024 listing at $8.25); Financial Highlights. Checker also noted NAV total return 209.59% (2025) / 33.12% (2024) is available in the same table if wanted.
- **2.3 Expense ratios** — 4.53/6.28/5.92/5.13% (FY25→FY22); net assets $438.0M vs $70.1M; Jefferies ATM 2025-08-08, 11,096,400 shares at wavg $29.48, $324.0M net proceeds; Financial Highlights + Note 4.
- **3.1 Wrapper liquidity terms** — non-diversified closed-end fund, NYSE "DXYZ" since 3/26/2024 (Note 1, verbatim). Note: "no fund-level repurchase program" is an absence-of-mention inference — the word "repurchase" appears nowhere in the N-CSR; nothing contradicts it.
- **4.5 Auditor** ✦ — KPMG LLP, Philadelphia, "auditor since 2025", unqualified, dated March 5, 2026; replaced Marcum LLP (appointed 2025-09-08); confirmed from the audit-report signature block, not the shareholder-letter KPMG research citation.
- *(2.1 — see Discrepancies)*

### hl_paf — 11/11 confirmed
- **1.2 Trailing returns** — Class I AATR 14.60/13.28/15.31/15.36 and FY total returns 14.60/12.59/12.68/16.10/20.77 all match; N-CSR Fund Performance + Financial Highlights.
- **2.1 Management fee** — 1.40% annualized of Managed Assets (leverage-inclusive base confirmed by definition), calculated monthly, paid quarterly; N-CSR Note 7. *Checker side-observation for CF2: the 2021 486BPOS fee table said 1.50% of average daily Managed Assets — the rate was reduced to 1.40% at some point between 2021 and FY2026; cell 2.1 cites the current N-CSR so its content is correct as recorded.*
- **2.2 Incentive fee terms** ✦ — 12.50% deal-by-deal with 8% (6% direct credit) preferred return compounded annually, 100% catch-up, no fee on primaries/hedges/cash, accrued monthly payable on exit; 486BPOS INCENTIVE FEE section, waterfall verbatim.
- **2.3 Expense ratios** — gross=net 3.40/2.93/4.26 (FY26/25/24), expense limits 1.45/0.75/1.00% (R/I/D) with exclusion list; N-CSR highlights + expense-limitation note.
- **2.7 Early repurchase fee** — 2.00% if repurchased <1 year from purchase, FIFO; N-CSR repurchase note, verbatim.
- **3.1 Wrapper liquidity terms** — tender offer up to 5.00% of net assets (~$290,123,923 / ~15,084,500 shares) + 2.00% upsize; quarterly offers since Q2-2021; board discretion; SC TO-I 2026-05-06, verbatim. Note: "NOT Rule 23c-3 interval" is an inference — the SC TO-I never cites 23c-3, consistent with the discretionary tender structure.
- **3.6 Leverage** — line of credit payable $76,482,442; senior-securities row $76,482K FY26 vs $36,192K FY25; N-CSR statements + highlights.
- **4.2 ASC 820 hierarchy** ✦ — L1 $529,492,964 / L2 $0 (footnote confirms none held) / L3 $562,354,022 (components sum) / total $1,091,846,986; $5,037,585,848 NAV-practical-expedient exclusion verbatim; L3 transfers in $30,651,521 / out $(85,361,200); N-CSR Note 4.
- **4.5 Auditor** — Cohen & Company, Ltd., Cleveland, "auditor of … Hamilton Lane Advisors … companies since 2020", dated May 29, 2026; signature block verbatim.
- **5.1 Stated benchmark** — S&P 500 and MSCI World defined in Fund Performance footnotes 2–3 as the shareholder-report comparators; N-CSR.
- **6.4 Tax reporting** ✦ — Form 1099-DIV verbatim in Tax Reports section; zero "K-1"/"Schedule K" hits in the entire prospectus; cost-basis 1099 and UBTI-blocking language confirmed; 486BPOS.

### kkr_kpec — 7/7 confirmed (10-K 2026-03-26)
- **1.2 Total returns** ✦ — all seven classes match for FY2025 / ITD-annualized / Q4-2025, all seven inception dates match, no-distributions footnote confirmed; MD&A Transactional NAV Total Returns table.
- **2.1 Management fee** — 1.25%/yr of month-end NAV for S/D/U/I, monthly in arrears (R-classes 1.00% for 60 months post-offering, then 1.25%); Management Agreement note.
- **2.2 Incentive fee terms** — Performance Participation Allocation 15.0% of Total Return, 5.0% annual hurdle, high-water mark, 100% catch-up; verbatim.
- **2.7 Early repurchase fee** ✦ — 5.0% of NAV within 24 months, inures to the Company, death/disability/divorce waivers, DRIP exempt, Manager sole discretion; Item 1 "Early Repurchase Fee", verbatim.
- **3.1 Wrapper liquidity terms** — 5.0% of aggregate NAV per quarter (avg of preceding quarter-end NAV), discretionary. *Precision note for CF2: the limit's base includes Class F Shares alongside the eight Investor Share classes ("Class S, D, U, I, R-S, R-D, R-U, R-I and Class F Shares"); the recorded paraphrase omits Class F. No number contradicted.*
- **4.5 Auditor** — Deloitte & Touche LLP, San Francisco, "auditor since 2022", dated March 26, 2026; signature block.
- **6.4 Tax reporting** — Schedule K-1, ~75 days after calendar year-end, delivery may be delayed; partnership (not corporate) taxation confirmed; risk-factor tax section + income-taxes note.

### stepstone_spm — 8/8 confirmed (N-CSR 2026-06-09 unless noted)
- **1.2 Trailing returns** — Class I FY2026 10.47% verbatim; AATR I 10.47/12.92/19.19, D 10.19/12.72/18.96; inceptions 10/1/2020 (I/D/S) and 1/2/2026 (R); MD of Fund Performance.
- **2.1 Management fee** — 1.40% annualized of daily NET assets; Note 5, verbatim.
- **2.3 Expense ratios** ✦ — all 15 before-recoupment ratios match (I 1.91…3.38; D 2.17…3.44; S 2.77…3.45); FY2026 before=after confirmed; footnotes 4–5 (no underlying-fund expenses; deferred tax excluded) confirmed; Financial Highlights.
- **3.1 Wrapper liquidity terms** — tender up to 5% of outstanding shares at NAV per share, quarterly program (Mar 16 / Jun 16 / Sep 15 / Dec 15); SC TO-I 2026-05-12, verbatim.
- **3.6 Leverage** — $247.3M cash, $300.0M available under credit facility, net assets $5,828.9M; MD&A Liquidity ($200.0M drawn shown separately in statements, consistent).
- **4.5 Auditor** — Ernst & Young LLP, New York (One Manhattan West letterhead on the audit report).
- **5.1 Stated benchmark** — "MSCI World Index … SPRIM's primary benchmark" (footnote 2), matches.
- **6.4 Tax reporting** — "Form 1099 DIV or Form 1099-B tax reporting instead of K-1s" verbatim under the "Favorable Structure" bullet; 486BPOS 2025-10-20.

---

## 2. Discrepancies (2 cells — cells NOT changed; CF2 to adjudicate)

### dxyz 2.1 (Management fee) — recorded rate/base is the PRE-listing fee; the fee in force is 2.50% of GROSS assets
- **Recorded:** base management fee 2.00% per annum (evaluated in the value as "High for a listed CEF").
- **Document says instead:** the 2.00% fee was the "Original Base Management Fee," payable only *prior to the public listing* and calculated on average *invested capital*. Since shares began trading on NYSE on **March 26, 2024**, the Adviser receives the **"Revised Base Management Fee": 0.625% per quarter (2.50% annualized) of the average value of the Fund's GROSS assets, including assets purchased with borrowings**. This was the fee for the entire FY2025 reporting period; FY2025 management fees incurred: $3,525,027.
- **Where:** `data/raw/dxyz/N-CSR_2026-03-10_ea0276106-01_ncsr.htm`, Note 5 — Agreements and Related Party Transactions, (a) Management Fee (search "Revised Base Management Fee").
- **Why it matters:** both the rate (2.00% → 2.50%) and the base (invested capital → gross assets incl. leverage) are understated in the cell; the recorded verbatim quote exists but is quoted out of its pre-listing context. This is the highest-priority fix on the roster.

### cliffwater_cclfx 5.1 (Self-declared benchmark) — filing expressly disclaims having a benchmark
- **Recorded:** Morningstar LSTA US Leveraged Loan Index (primary) / Bloomberg US Aggregate (secondary) as the fund's self-declared benchmark.
- **Document says instead:** the two comparator indices are correct as comparators, but the N-CSR states: "**These indices do not serve as benchmarks for the Fund and are shown for illustrative purposes only. The Fund does not have a designated performance benchmark.**" No primary/secondary ranking is assigned anywhere in the filing.
- **Where:** `data/raw/cliffwater_cclfx/N-CSR_2026-06-08_ea0291746-01_ncsr.htm`, Fund Performance, March 31, 2026 (Unaudited) (search "do not serve as benchmarks").
- **Why it matters:** under an element titled "Self-declared benchmark," recording these indices as (primary)/(secondary) contradicts the filing's express disclaimer. The comparison data is fine; the characterization needs CF2's call (e.g., reword to "shareholder-report comparator indices; fund expressly declares NO designated benchmark" — itself an evaluative datum for factor 5). Also: the CDLI/provider-independence sentence in the cell is editorial — CDLI appears nowhere in this N-CSR.

---

## 3. Could not locate (0 cells)

None. Every one of the 44 cells was re-located in its cited on-disk document (including cells whose evidence-CSV `local_file` field was blank — see housekeeping note below).

---

## Appendix — housekeeping notes for CF2 (no action forced)

1. **Blank `local_file` fields:** breit 3.1 / 3.6 / 4.5, kkr_kpec 2.2 / 4.5, hl_paf 5.1, stepstone_spm 5.1 cite documents that ARE on disk but have an empty `local_file` in the evidence CSV. Trivial to backfill during verification.
2. **hl_paf management fee history:** 486BPOS (2021) fee table says 1.50% of average daily Managed Assets; the FY2026 N-CSR says 1.40% calculated monthly. Cell 2.1 (citing the N-CSR) is correct as recorded, but the rate changed sometime after 2021 — worth a one-line note in the cell when verifying.
3. **Location nuance:** cliffwater 1.2's quote lives in the Letter to Shareholders, not the cited "Fund Performance" section (same document, pages apart).
4. **Inference flags:** dxyz 3.1 "no fund-level repurchase program" and hl_paf 3.1 "NOT Rule 23c-3 interval" are absence-of-mention inferences, consistent with (but not stated by) the filings.

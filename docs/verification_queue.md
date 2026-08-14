# Human Verification Queue (CF2 / Justin)

The evidence CSVs (`data/evidence/*.csv`) are the verification interface: check
the row against the cited document, then set `status` to `verified` and sign
`verified_by` in BOTH the CSV and the product JSON. Nothing else may do this.
The site's Verification view renders this queue with live progress computed
from the statuses (machine-parsed: keep the `- key cell_id —` line format).

## Queue (demo-load-bearing first)

### Tier 1 — numbers spoken aloud in the demo
- hl_paf 2.1 — Managed Assets fee base (the fee-base trap beat)
- dxyz 2.1 — 2.50% on gross assets incl. borrowings (corrected cell)
- cliffwater_cclfx 5.1 — no-declared-benchmark finding (corrected cell)
- kkr_kpec 6.4 — Schedule K-1 (the recordkeeper beat)
- stepstone_spm 6.4 — 1099 'favorable structure' quote
- breit 3.3 — repurchase history + proration (gating beat)
- breit 1.1 — printed monthly NAV table (feeds rho 0.483)
- hl_paf 2.2 — incentive fee CURRENT terms (10.00% over Loss Recovery Account, approved 2025-03-14; 2021 12.5% terms superseded — corrected by facts-layer verification)
- kkr_kpec 2.7 — 5.0% / 24-month early repurchase fee
- breit 2.7 — Early Repurchase Deduction (98% of price)

### Tier 2 — screener-facing facts (typed layer inputs)
- hl_paf 2.3 — expense ratios
- cliffwater_cclfx 2.3 — expense ratios (excl/incl interest)
- dxyz 2.3 — expense ratio + net assets
- stepstone_spm 2.3 — expense ratios (3 classes)
- hl_paf 4.5 / cliffwater_cclfx 4.5 / dxyz 4.5 / kkr_kpec 4.5 / breit 4.5 / stepstone_spm 4.5 — auditors
- cliffwater_cclfx 2.7 — 'will not charge a repurchase fee'
- kkr_kpec 2.2 — 15% / 5% hurdle / HWM
- hl_paf 3.4 — net assets $5,785,749,989
- stepstone_spm 3.6 — net assets $5,828.9M

### Tier 3 — partial cells whose resolution unlocks typed facts
- cliffwater_cclfx 2.2 — confirm no incentive fee in prospectus (unlocks fact)
- stepstone_spm 2.2 — confirm no fund-level incentive fee (unlocks fact)
- stepstone_spm 2.7 — confirm no early repurchase fee (unlocks fact)
- breit 2.2 — type the performance-participation rate (unlocks fact)
- cliffwater_cclfx 6.4 / dxyz 6.4 / breit 6.4 — tax form confirmations (fund
  tax FAQs are the likely source; cite URL + access date)
- cliffwater_cclfx net assets — carry the aggregate figure into a typed cell
- kkr_kpec net assets — carry members' equity into a typed cell
- breit net assets — carry the NAV-by-class total into a typed cell

### Then: everything else at `extracted-unverified`, per product, in cell order.

## Cohort roster additions (2026-08-15) — ordered by demo salience

The eight cohort-tier products' comparison-critical cells, queued after the
existing items. Fee/liquidity traps and the exhibits the demo leans on first:

- ssss 2.1 — the 1.75%-on-GROSS-assets externalization fee (regime change; demo-load-bearing)
- sreit 3.1 — the cap shrink-and-suspension chronology (2% -> 0.33% -> 0.5% -> closed)
- sreit 3.3 — gating story quantified (requests exceeded limits since Oct 2022)
- bcred 2.2 — two-part BDC incentive fee (12.5% income / 5% hurdle / 12.5% gains)
- pflex 2.1 — the LESSER-of dual fee base (novel base enum)
- ares_pmf 2.2 — 12.5% Loss-Recovery-Account incentive (mirrors hl_paf's 2025 restructure)
- jll_ipt 2.2 — 10%-over-7% performance fee with three fee-free years
- jll_ipt 3.1 — daily-dealing / quarterly-cap plan (the liquidity contrast)
- amg_pantheon 2.1 — 0.70% on net assets (cohort's lowest headline rate)
- arkvx 3.1/3.3 — interval cadence + clean 5% fulfillment record
- ssss 1.11 — rename/ticker lineage (SuRo -> Neostellar, SSSS -> NSLR)
- bcred/sreit/pantheon/ssss quarterly NAV series spot-checks (data/series_quarterly/)
- remaining critical-set cells (1.2, 2.3, 2.6, 2.7, 4.1, 4.5, 5.1, 6.2, 6.4) per product
- facts hand-mappings for the 8 new products (data/facts/ vs cells)

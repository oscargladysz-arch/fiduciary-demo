# Roster Decisions — Cohort Build (verified live on EDGAR, 2026-08-14)

Rule R1: no product enters the registry without live EDGAR verification —
CIK resolves, filing profile matches the expected wrapper, and a current
prospectus/annual exists. Rule R3: every membership reasoned; every candidate
considered and excluded logged here with its reason. This file must mention
every registry key (validator-enforced).

## Cohorts as landed

| cohort_id | members | n | note |
|---|---|---|---|
| private_credit | cliffwater_cclfx (full), bcred, pflex | 3 | deliberately cross-wrapper: interval fund + non-traded BDC |
| evergreen_pe | hl_paf (full), stepstone_spm (full), kkr_kpec (full), ares_pmf, amg_pantheon | 5 | includes kkr_kpec under the authorized fallback (below) |
| nontraded_reit | breit (full), sreit, jll_ipt | 3 | |
| venture | dxyz (full), ssss, arkvx | 3 | listed CEF + listed BDC + interval fund — premium/discount comparability is the point |

Roster: 6 full-depth + 8 cohort-depth = **14 products** (vs the 18 aspiration —
see "Depth discipline" below).

## Accepted (verification evidence)

- **bcred** — Blackstone Private Credit Fund, CIK 1803498. Profile: 10-K
  2026-03-13, 10-Q 2026-08-12, 486BPOS/N-2 2026-05-01, 424B3 stream, SC TO-I
  x22 (quarterly tenders). Non-traded BDC ✓. Membership: direct-lending
  private credit, perpetual continuous offering, quarterly liquidity —
  strategy twin of CCLFX on a different chassis ('40-Act interval vs BDC);
  the cross-wrapper caveat matrix carries the difference (BDC leverage norms,
  tender vs 23c-3 obligation).
- **pflex** — PIMCO Flexible Credit Income Fund, CIK 1688554. Profile: N-CSR
  2025-09-05 (FYE June), 486BPOS 2025-10-24, N-23C3A x38 — a Rule 23c-3
  paper trail like CCLFX's own ✓. Membership: multi-sector/flexible credit
  interval fund; same wrapper and cadence as CCLFX, broader credit mandate
  (caveat recorded).
- **ares_pmf** — Ares Private Markets Fund, CIK 1876006 (was already
  registered, unfetched). Profile: N-CSR 2026-06-04, 486BPOS 2026-07-29,
  SC TO-I x16 ✓ tender-offer evergreen PE (secondaries-led). Membership:
  same wrapper and strategy class as hl_paf/stepstone_spm.
- **amg_pantheon** — AMG Pantheon Fund, LLC, CIK 1609211. Profile: N-CSR
  2026-06-09, N-2 2026-07-30, SC TO-I x40 ✓ tender-offer evergreen PE.
  Membership: as ares_pmf.
- **sreit** — Starwood Real Estate Income Trust, CIK 1711929, SIC 6798.
  Profile: 10-K 2026-03-20, 10-Q 2026-08-12, 424B3 stream ✓ non-traded NAV
  REIT. Membership: BREIT's closest structural twin (monthly NAV, share
  classes, 2%/5% repurchase plan — to be evidenced, not assumed).
- **jll_ipt** — JLL Income Property Trust, CIK 1314152, SIC 6798. Profile:
  10-K 2026-03-26, 10-Q 2026-08-11, 424B3 ✓ perpetual NAV REIT (older
  vintage, daily NAV — comparability caveat on NAV cadence).
- **ssss** — CIK 1509470 verified as **Neostellar Capital Corp.** — the
  entity formerly named SuRo Capital Corp. (SSSS). R1 CAUGHT A RENAME the
  candidate menu didn't know about. Profile: 10-K 2026-03-11, 10-Q
  2026-08-06, N-2 2026-07-31 ✓ listed BDC. CONDITION: strategy continuity
  (pre-IPO growth portfolio) must be confirmed from the current 10-K during
  extraction before membership is final; if the strategy pivoted with the
  rename, replace with an alternate and re-log.
- **arkvx** — ARK Venture Fund, CIK 1905088. Profile: N-CSR 2025-10-08 (FYE
  July), 486BPOS 2025-10-27, N-23C3A x15 ✓ interval fund holding
  venture/growth. Membership: venture exposure in a registered wrapper —
  the NAV-priced contrast to DXYZ's premium-priced listed shell.

## Considered and excluded (R3 log)

- **StepStone Private Venture & Growth (SPRING)** — CIK 1918642 verified
  (N-2 2026-07-29, N-CSR 2026-06-09, SC TO-I x11): it is a '40-Act
  tender-offer venture/growth fund, NOT a '34-Act PE conglomerate — it
  cannot make kkr_kpec a pure-cohort peer. Not admitted this pass (depth
  discipline); strong future candidate for the venture cohort.
- **Blue Owl Credit Income (OCIC)** — CIK 1812554 verified (non-traded BDC).
  Viable private-credit alternate; NOT admitted this pass: cohort already
  n=3 with a deliberate wrapper mix, and cohort-tier depth for a fourth
  member was judged worse than full depth on three (R2 bandwidth
  discipline). Next-wave candidate.
- **Variant Alternative Income (NICHX)** — CIK 1736510 verified. Excluded
  from private_credit: strategy is niche alternative income (royalties,
  litigation finance, specialty), not direct corporate lending — a
  strategy-tag mismatch, not a data problem.
- **FS Specialty Lending** — not admitted: private-credit cohort filled by
  stronger twins (bcred/pflex); not individually verified this pass.
- **Partners Group Private Equity (multiple entities, CIKs 1438089/1480506/
  1447246)** — verified to exist as several feeder/master entities; picking
  the right registrant needs a structure read we did not spend this pass
  (evergreen cohort already n=5). Next-wave candidate.
- **Pomona Investment Fund** — CIK 1616203 verified. Viable evergreen-PE
  alternate; not admitted (cohort at n=5 already). Next-wave candidate.
- **Ares REIT (AREIT) / Invesco INREIT / Brookfield REIT** — not admitted:
  REIT cohort filled at n=3; not individually profiled this pass.
- **Fundrise Innovation Fund** — CIK 1867090 verified to resolve. Not
  admitted: venture cohort at n=3; its Reg A+/interval hybrid structure
  needs a wrapper read before membership. Next-wave candidate.
- **BXPE / Apollo Aligned Alternatives (kkr_kpec's true twins)** — Reg D
  private placements with no public prospectus or periodic public NAV: NOT
  verifiable public peers. This is WHY the authorized fallback applies.

## The kkr_kpec ruling (authorized fallback, invoked)

A pure '34-Act PE-conglomerate cohort is impossible from public data: the
structural twins (BXPE, Apollo AAA) are Reg D vehicles with no public
filings, and the one verified adjacent candidate (SPRING) is a different
wrapper AND a different strategy stage. kkr_kpec therefore joins
**evergreen_pe** as a cross-wrapper member (n=5): same economic exposure
class (diversified private-equity portfolios in perpetual wrappers), with
these caveats carried by the cohort caveat matrix: '34-Act conglomerate of
CONTROLLED operating companies vs '40-Act funds-of-funds; K-1 vs 1099;
transactional-NAV dealing vs prospectus NAV; no 1940-Act leverage limits.
An honest mixed cohort beats fake twins.

## Depth discipline (6 → 14, not 18)

The menu's per-cohort arithmetic yields 8 verified new members with every
cohort at n≥3 (evergreen at n=5). Admitting alternates to reach 18 would
have spread cohort-tier extraction thinner without changing any cohort's
statistical honesty (R4 phrasing gates bind at n=3 and n=5 either way).
Choice: 14 products fully landed over 18 partially landed, per the
mission's own priority rule. The four next-wave candidates above are
verified leads for the next roster pass.

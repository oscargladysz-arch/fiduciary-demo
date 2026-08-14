# Tark Build Report 4 — The Cohort Build
**2026-08-15 · branches `workbench`→`cohort-ux` merged to `main` · rollback tag `pre-cohort`**

## The number that matters
**Roster 6 → 14 products** (not the aspirational 18 — see the depth-discipline
ruling), **756/756 cells resolved (zero bare pendings across the entire
roster)**, four cohorts with every membership argued and every exclusion
logged, and lane C of the benchmark engine finally fed with real peer data.

## Phase 0 — verification-first roster (R1)
Every candidate verified against live EDGAR (CIK, filing profile, current
docs). **R1 caught a rename the candidate menu didn't know about**: CIK
1509470 is no longer SuRo Capital (SSSS) — it is **Neostellar Capital Corp.
(NSLR)** after a July 2026 externalization. Strategy continuity was CONFIRMED
from the filings (verbatim-identical investment objective), and the fee-regime
change (internal management → 1.75% of GROSS assets + two-part incentive) is
now typed evidence. Accepted: bcred, pflex, ares_pmf, amg_pantheon, sreit,
jll_ipt, ssss (Neostellar), arkvx. Rejected with reasons (9 candidates,
including SPRING — verified but wrong wrapper AND wrong purpose):
`data/roster_decisions.md`.

**Depth discipline (6→14, not 18):** the per-cohort menu arithmetic yields 8
verified members with every cohort at n≥3 (evergreen n=5). Admitting
alternates to hit 18 would have thinned extraction without changing any
cohort's statistical honesty (R4 binds identically). Four verified next-wave
leads are logged.

**The kkr_kpec ruling (authorized fallback, invoked):** its true twins (BXPE,
Apollo AAA) are Reg D vehicles with no public filings. kkr_kpec joins
evergreen_pe cross-wrapper with caveats carried by the matrix. An honest
mixed cohort beats fake twins.

## Phase 1 — cohort-tier extraction (R2)
12 extract+verify agent pairs over 44 fetched filings: **327 cells landed
adversarially verified**, every product 100% resolved under the
zero-bare-pending law. Evidence highlights the demo will lean on:
- **SREIT's liquidity chronology**: repurchase caps shrank three times
  (2%/mo → 0.33% → 0.5%) and the plan **suspended entirely April 2026** —
  encoded as cap `null` with the full chronology, and the strongest gating
  exhibit in the dataset (breit's proration now has a worse sibling).
- **PFLEX's LESSER-OF dual fee base** — a new enum the trap detector renders.
- **JLL IPT's daily-dealing repurchase plan** (quarterly 5% cap) — the
  liquidity spectrum's opposite pole, with a 10%-over-7% performance fee that
  earned zero for three straight years.
- **BCRED's two-part BDC incentive** (12.5% income / 5% hurdle / 12.5% gains)
  and clean tender record; **ares' Loss-Recovery-Account incentive**
  mirroring hl_paf's 2025 restructure; **pantheon's 0.70%** — the cohort's
  cheapest headline rate with a 10-year printed annual series.
Series tiers extended: daily (PFLEX/ARKVX/NSLR pulled), quarterly-NAV tier
created (bcred, sreit, jll via extraction; pantheon fiscal quarters; ssss 16
points; breit backfilled from its monthly table).

## Phases 2-3 — facts at 14 + the cohort engine
`data/facts/` extended with `cohort_id`/`depth`/`membership_rationale`;
validator enforces numeric agreement (it caught two of my own transcription
errors mid-build: breit's partial 2.2 and a mis-cited inception). New
`src/tark_cohort.py` (16 unit tests):
- **R4 phrasing law machine-enforced**: ordinal percentiles only at n≥4;
  n=3 cohorts get "above/below the cohort median (n=3)" — e2e sweeps the
  whole bundle for violations.
- **Composite refusal law**: the venture cohort's composite is REFUSED (not
  fudged) because members' pricing bases are heterogeneous — the refusal
  renders in the UI where the chart would be.
- Caveat matrix as data (`data/cohorts/caveat_matrix.json`): pricing-class,
  leverage-regime, liquidity-law, NAV-cadence mixes assemble each cohort's
  caveat block and surface automatically on cross-wrapper comparisons.
- **Cell 2.9 recomputed for all 14** from cohort stats (the old
  universe-of-6 percentile superseded, noted in each cell).
- **Lane C fed**: peer cohorts now score on real composites — private_credit
  peer reaches 7/12 (threshold) and is outranked at 9 — an honest near-miss
  retained in the ledger; venture's peer entry carries its refusal reason.
- Selections at 14: arkvx gets the venture cohort's one real selection (PSP
  8/12); **ssss escalates exactly like dxyz** — and with **NSLR at −21.7%
  discount vs DXYZ's premium**, "benchmarking the price benchmarks the
  premium" is now SHOWN as a two-fund pattern (the site's premium-pattern
  exhibit pairs the charts).

## Phase 4 — cohort UX
Cohort pages (facts grid with per-member source buttons, range bars with
member markers, composite chart or refusal block, rationales, the exclusion
log rendered from roster_decisions.md, caveats); depth-tier chips + "view
cohort" links on evaluation; screener at 14 with cohort/depth filters; compare
gets one-click peer-suggest and automatic cross-wrapper caveat banners;
palette gains cohort commands; URL state extended (IDs only, whitelisted).

## Phase 5 — gates, perf, kit
- e2e grew to **110 checks** (cohort pages, R4 bundle sweep, refusal
  rendering, screener cohort/depth correctness, exhibit, peer-suggest,
  fallback note). The screener's fee-base test now expects TWO managed-assets
  products (ares joined hl_paf) — the roster changing an answer honestly.
- **Perf**: bundle split — data.js 1.08MB first paint + 499KB lazy series
  chunk (loaded only by chart/lab views); total capped at 2.4MB by test.
- **R5 ruling: no hook split.** The full suite runs in ~13 seconds (the
  optimized harness); pre-commit keeps everything. Both hooks remain tracked
  in `hooks/`.
- Memos ×14 regenerated with a "Peer cohort placement" section (depth tier,
  rationale, 2.9 placement, composite/refusal, caveats, exclusion-log
  pointer). `docs/verification_queue.md` extended with the new cells ordered
  by demo salience. 14 fresh screenshots; demo script v5 with the cohort beat
  ("here's the fund inside its cohort — and every fund we excluded, with
  reasons").

## Deferred, with reasons
- **kkr_kpec quarterly-NAV backfill** — its 10-K prints transactional-NAV
  returns but not a clean quarterly NAV/share table in the cells we mapped;
  queued rather than approximated.
- **jll_ipt PME** — annual returns print only as per-class RANGES; a point
  series cannot be typed without fabrication (n/a with reason; queue item).
- **Cohort-tier net_assets figures** (5 products) — printed but not yet
  carried into typed cells; queued.
- **Next-wave roster leads** — OCIC, Pomona, Partners Group entity selection,
  Fundrise structure read: verified, logged, not admitted this pass.

Build-chat sync required: `zip -r ~/Desktop/tark_repo_sync4.zip . -x 'data/raw/*' -x '.venv/*' -x '.git/*'` and upload to the build chat for review.

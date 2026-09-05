# BUILD REPORT 6, remediation of the 2026-09-03 audit

Specification: `docs/GAP_ANALYSIS_2026-09-03.md`. Decisions and every
discrepancy between the brief, the audit and the record:
`docs/DECISIONS_2026-09.md`. Branch `claude/tark-audit-defects-t2vfel`
(the harness-assigned branch, see decision 2), 47 task-tagged commits from
`bf0da75` (ORIENT) to `1d56936` (VERIFY) plus this DELIVER commit, every one
through the pre-commit hook. Nothing was squashed, `main` was not touched,
and `gh-pages` was not redeployed: the rule is redeploy only after this pull
request is green, and no CI exists yet (P3-2).

The four non-negotiables held throughout, and the gates now assert them:
zero cells are `verified` and every `verified_by` is empty
(`test_invariants`), no number reaches a surface unless it is in the cited
data layer or recomputed from it (`reconcile`, `test_frontend`), tier
language is never blurred (`test_liquidity`, `test_memo`, `test_frontend`),
and the four reference plans stay anonymized on every surface and in every
generated document (`build_site`, `test_memo`, `test_frontend`).

## 1. Baseline (before any change), recorded 2026-09-04

Environment: Python 3.11.15, Playwright 1.56.0 against the preinstalled
Chromium build 1194, python-docx 1.x, Streamlit 1.x. Branch
`claude/tark-audit-defects-t2vfel` at `bd9ebdc` (main `3d9b93e` plus the
audit document). Network policy: `sec.gov`, `federalregister.gov`,
`dol.gov` and every other primary source blocked, PyPI and the Anthropic API
host reachable, no `ANTHROPIC_API_KEY`, `data/raw/` absent (decision 0).

Gates, in `hooks/pre-commit` order, before the work:

| gate | result | wall time |
|---|---|---:|
| validate_data | pass | 0.1 s |
| validate_census | pass | 0.1 s |
| test_analytics | pass | 0.0 s |
| test_cohort | pass | 0.0 s |
| test_benchmark | pass | 0.2 s |
| test_memo | pass | 0.2 s |
| test_app | pass | 5.9 s |
| build_site | pass | 0.4 s |
| test_frontend | pass, 135 checks | 27.6 s |

Assertion sites (static): test_analytics 32, test_cohort 16, test_benchmark
17, test_memo 7, test_app 22 (about 89 at runtime), test_frontend 129 (135
at runtime). validate_data and validate_census accumulate error lists and
were not countable as assertions.

Bundle sizes from `python src/build_site.py`: `site/data.js` 1,096,876
bytes, `site/series.js` 696,940 bytes, `site/census.data.js` 302,842 bytes,
64 census detail shards (4.4 MB), 16 memos (708 KB).

Screenshots: `docs/screenshots/baseline_2026-09/`, produced by
`python src/shots.py`: all 18 views under `plan_tech_media`, with the eight
product-specific views (compare, packet, evaluation, benchmarks, liquidity,
pme, dxyz, desmooth) shot for each of `hl_paf`, `cion_ares`, `sreit`,
`jll_ipt` and the ten product-independent views shot once. 42 JPEG files,
7.8 MB, pages clipped at 8,000 px.

## 2. Gates, before and after

The hook grew from 9 gates to 18. Counts are passing checks printed by each
gate when run alone on the final tree, 2026-09-04. "absent" means the gate
did not exist at baseline.

| gate (hook order) | baseline | now | what it holds |
|---|---:|---:|---|
| validate_data | pass | 26 | data contract, JSON equals CSV on value, source, quote and extracted_by, registry, advisor files, every cited `data/` path exists, accession format, no laptop paths |
| validate_census | pass | 1 | 3,599 entities, provenance complete, 16 promoted links, counts consistent |
| test_evidence_immutable | absent | 2 | 482 protected T2 rows diffed against `origin/main`, changes only through the allowlist (two wildcard rows cover 464 accession and 263 local_file cells) |
| corrections_log check | absent | pass | every changed published number versus `origin/main` is in the generated table (677 rows) |
| test_invariants | absent | 16 | verified count 0, no product-count copy, no dead data paths, record totals pinned |
| test_copy | absent | 39 | no em dash or semicolon in user-facing copy, generated strings and the owned documents |
| test_docs | absent | 27 | runbook agrees with the hook, the record and `main.js`, queue names the structured cell, superseded claims marked |
| test_analytics | 32 | 35 | window intersection, one anchor, day-count annualization, JS parity |
| test_cohort | 16 | 27 | mid-rank ties, typed caveats, composite refusal on pricing class |
| test_benchmark | 17 | 164 | rubric v2, strategy gate, expected outcome table, property tests that move one fact and watch one criterion |
| test_liquidity | absent | 29 | structural and scenario layers, sreit misaligned under every plan, plan-sensitivity of the scenario layer |
| test_ingest | absent | 57 | extraction contract offline with a mock client, calibration arithmetic, verify_cell refusals, plan intake, service refusals |
| test_memo | 7 | 39 | 64 memos and 64 packets, sections, provenance, no mid-word cut, no anonymization token |
| test_app | 89 | 196 | Streamlit surface over all 16 products |
| test_artifacts_fresh | absent | 9 | nine artifact families reproduce from a clean `produce.py` run |
| build_site | pass | pass | first-paint budget, anonymization gate over bundles and 128 documents |
| reconcile | absent | 4 | expense ratio, management fee, KS-PME and Direct Alpha, liquidity verdict agree across facts, headlines, cards, cells 1.8 and 3.9, match files and memo |
| test_frontend | 135 | 216 | 18 views by 16 products by 4 plans with the HTML parsed, recording proxy over every bundle, mobile 390 px, print, Tier 1 drawer against the CSV |

Full hook wall time: 39 seconds at P0 exit, 101 seconds now (memo and packet
generation and the wider frontend sweep account for the difference). Bundle
now: `site/data.js` 1,035,599 bytes (budget 1,200,000), `site/series.js`
1,247,495 bytes (lazy, carries the per-cell evidence detail with EDGAR
links), `site/census.data.js` 303,113 bytes, 128 generated documents.

## 3. What changed, by phase

Commits are listed in order. Each commit message carries its task id.

### P0, correctness and copy on live surfaces (13 commits, bf0da75 to 292eca9)

- `1708ed5` P0-0 guard rails before any writer ran: one anonymization token
  module shared by the build and three test suites, evidence immutability
  gate, deterministic producer chain (`src/produce.py`, `--as-of`,
  `TARK_DATA_DIR`), freshness gate, generated corrections log, SEC contact
  from `TARK_SEC_CONTACT`.
- `f70dff3` P0-1 `gloss()` glosses text segments only. No `data-def` can
  contain markup, so the `">interval fund` fragments are gone.
- `baabbba` P0-2 all product-count copy removed, cell 5.4 regenerated for
  16 products from cohort membership by the new owned-cells writer.
- `ed60eaa` P0-3 Fee Matrix chips and bars from typed facts (`affe` fact
  added, `fee_percentile` rebuilt from facts, the `build_facts` status
  clobber fixed), cell headlines typed-fact-first on every card.
- `f2b0383` P0-4 Analysis Lab and De-smoothing Lab never fall back to
  another product, de-smoothing extended to every daily series.
- `20c609d` P0-5 one coverage formula (`coverage_summary`), per-kind
  segments everywhere, taxonomy regenerated each build, crosscheck tile
  parsed from the report header and worded as an agent pass.
- `22b2a79` P0-6 dangling paths repointed, validator resolves every cited
  `data/` path.
- `140711e` P0-7 percentile ties share one mid-rank, cell 2.9 regenerated
  for 16 products.
- `0e16c23` P0-8 dead data, dead bundle keys and dead code removed, the
  census `or True` deleted, runtime dead-key check through a recording
  proxy.
- `df63843` P0-9 Verification view: Tier 1 first with the spoken-aloud
  badge.
- `bf6620d` P0-10 runbook consistency, README, copy sweep, `test_docs` and
  `test_copy` gates.
- `292eca9` P0 exit: the gates enumerate the record (16 products, 18 views)
  instead of a hand-typed subset.

### P1, engines that mean what they claim (22 commits, 9527c0e to f3b35e2)

- `9527c0e` v1 benchmark snapshot frozen in `data/benchmarks/v1_snapshot/`
  before any engine change (decision 1.3).
- `7e981cc` P1-1 comparison window is the intersection of fund and proxy
  coverage, anchored once, whole fiscal years for annual lists, JS port.
- `d9c616e` P1-2 actual/365.25 day count on the effective window.
- `72e231c` P1-3 two-point flows stated on card, memo and methodology, an
  ILLUSTRATIVE monthly-schedule KS-PME row for daily NAV products.
- `2c72c9e` P1-4 Yahoo adjusted close labeled from one source map,
  `run_analytics` reads the record.
- `e32df9c` P1-B prep: `src/fetch_authority.py` (Federal Register API,
  document 2026-06178), methodology rubric sections and the expected v1 to
  v2 outcome table committed before the engine changed.
- `98074c7` P1-5 to P1-12 rubric v2 as one change: typed descriptors from
  the registry, strategy gate, reachable 12, Lane A from typed declared
  benchmarks (no points for the declaration), per-product independence,
  Lane C leave-one-out composite, secondary on a different series, Lane D
  removed, computable escalation.
- `12f9d67` P1-13 `jll_ipt` selected on descriptors with an honest absent
  comparison, no fact left `pending`.
- `5ec21ed` P1-14 windows under three years labeled low confidence on card
  and memo.
- `72adb74` P1-15 Analysis Lab verdict from the real v2 scorer for every
  proxy and every product with a series.
- `67ebc88` P1-16 and P1-17 liquidity verdict v2: structural layer from
  typed facts, scenario layer ILLUSTRATIVE per plan, `LIQUIDITY_PROFILES`
  deleted.
- `9eaf0f9` P1-18 plan schema: Schedule H benefit payments, contributions
  and QDIA as null-with-reason.
- `94dbb9b` P1-D prep: offline accession resolver over `data/manifest.csv`
  (729 references, 683 exact, 0 unresolved, 2 ambiguous left as notes).
- `a8c9994` P1-19 memos per plan and product generated by the build (64),
  links and the pin hash follow the selected plan, memo date is the record
  as-of.
- `d2afca3` P1-20 findings table: typed facts plus complete first sentences,
  one paragraph per line, no truncation.
- `b259466` P1-21 memo sections: liquidity match, recommendation, scope,
  case law.
- `78f7a2a` P1-22 provenance with true per-kind counts and resolvable
  citations with accession and EDGAR URL.
- `abedf28` P1-23 cell 5.6 written by the owned-cells writer, cell 5.7
  seeded `partial` from the docket listing, the hardcoded case-law sentence
  removed, the partial validator tightened.
- `e142e4b` P1-24 caveats compare typed per-product values, contradicted
  caveats suppressed.
- `ce5a0dd` P1-25 `test_memo` over all 64 memos.
- `6c4d19e` P1-D2 engine-owned cells 1.8, 1.9, 3.8, 3.9, 5.3 and 5.5
  restated by the writer from the v2 artifacts.
- `f3b35e2` P1-26 authority panel with the rule paragraphs, `rule_ref` per
  cell, no paraphrase, cells 6.6 and 6.8 relabeled advisor-completed.

### P2, an advisor can run their own fund (10 commits, d4324eb to d716701)

- `d4324eb` P2-1 one product registry (`data/registry.json`), every
  duplicate table deleted, registry validator.
- `715a7f8` P2-2 `src/ingest.py`: structured extraction with a per-cell
  contract and a verbatim-quote check, offline gate with a mock client.
- `f01fe31` P2-3 and P2-4 calibration harness written, both runs documented
  as blocked here (section 6).
- `0d95762` P2-5 census "Evaluate this fund": copyable command, honest
  button, one-endpoint service without job state.
- `fffdb92` P2-6 advisor-stated cells: storage, validator, badge, form, memo
  section, never counted as evidence.
- `c8cfea1` P2-7 verification: signer and date required, quote beside the
  value, the site writes nothing, `src/verify_cell.py` is the only path.
- `b4a5ccd` P2-8 plan intake under an anonymized label.
- `016d888` P2-9 committee packet per plan and product, print scoped to
  pins.
- `e09ff70` P2-10 accession column on every evidence row, EDGAR links in
  the drawer, laptop paths purged, raw-path check hard.
- `d716701` P2-11 share-class aware listing, N-23C3A 24-month recency rule,
  both census files updated by a committed script.

### P3 and verification

- `5cfcb62` P3 plan written into `docs/DECISIONS_2026-09.md` (decision
  6.32), CI first. No P3 code: P2-3 and P2-4 cannot be green here.
- `1d56936` VERIFY: reconcile gate, Tier 1 drawer check, mobile and print
  checks, after screenshots.

## 4. Corrected numbers

Every changed published number is in the generated table under
"Corrections 2026-09" in `docs/crosscheck_report.md` (`src/corrections_log.py`,
677 rows: product, field, old, new, cause, surfaces, date). By cause:

| rows | cause |
|---:|---|
| 182 | P1-5 to P1-12 rubric v2 (typed descriptors, strategy gate, reachable 12, Lane A, independence per product, Lane C composite, secondary on a different series, Lane D removed, computable escalation) |
| 143 | P1-16 and P1-17 liquidity verdict v2 (sreit misaligned on the typed suspension, four products partial where gating history is not established) |
| 89 | P1-D2 cells 1.8, 1.9, 3.8, 3.9, 5.3, 5.5 regenerated from the v2 artifacts |
| 64 | P1-23 cell 5.6 written from the selection artifact, cell 5.7 seeded partial |
| 74 | P1-1 window intersection with one anchor (62 selection backfills plus 12 first-pass rows) |
| 25 | P1-13 jll_ipt selection and facts |
| 23 | P0-3 fee_percentile from typed facts, affe typed, status clobber fixed |
| 19 | P1-2 day-count annualization |
| 16 | P0-2 cell 5.4 from cohort membership |
| 16 | P0-7 percentile ties |
| 10 | P0-10 copy sweep, punctuation only |
| 8 | P1-3 ILLUSTRATIVE monthly-schedule row |
| 8 | P1-24 caveat counts in cell 5.4 |

By field family: selection 255, cell 204, facts 127, liquidity 84,
fee_percentile 7. Headline movements, old to new, with the cause:

| product | figure | v1 (published) | after P1-1 and P1-2 | after rubric v2 (now) |
|---|---|---|---|---|
| amg_pantheon | primary KS-PME | 2.4551 vs PSP | 1.5919 vs PSP | 0.8357 vs the evergreen-PE peer composite (primary changed) |
| cion_ares | primary KS-PME | 1.2376 vs BKLN | 1.1374 vs BKLN | 0.9461 vs the private-credit peer composite, BKLN 1.1374 as secondary |
| pflex | primary KS-PME | 1.2639 vs BKLN | 1.1089 vs BKLN | 0.9799 vs the peer composite |
| cliffwater_cclfx | primary | BKLN 1.2532, secondary the same BKLN | unchanged figure | peer composite 0.9756 (10/12), BKLN 1.2532 as secondary (9/12) |
| cliffwater_cclfx | annualized fund return | 8.02% | 7.89% (day count) | 10.57% on the fiscal-year window of the composite, 7.89% on the BKLN window |
| arkvx | annualized fund return | 30.67% | 30.12% | no primary: escalated, no candidate passes the strategy gate |
| hl_paf | primary, secondary | PSP 9, URTH 8 | unchanged | peer composite 10 (KS-PME 1.0693), PSP 9, declared S&P 500 and MSCI World fail the gate |
| jll_ipt | selection | absent | absent | VNQ 9/12 with an honest absent comparison (no computable fund series) |
| sreit | liquidity verdict, every plan | conditional-weak | unchanged | misaligned (structural, typed suspension and 0% cap) |
| hl_paf | liquidity verdict | conditional | unchanged | structural partial (gating history not established), scenario conditional or conditional-weak by plan, ILLUSTRATIVE |

The annualized fund return on a card is always over the effective window of
the selected comparator, so it moves when the comparator moves. Record totals
after the writer and the seeds: 406 extracted-unverified, 161 computed, 75
partial, 16 fetched, 205 documented n/a, 1 structured, 0 pending, 0
verified, 864 cells, 659 resolvable.

## 5. Ingestion calibration (P2-3): blocked here, not faked

`src/calibrate_ingest.py` runs the extraction contract on an already
evaluated product in a scratch copy with the target cells reset to pending,
compares each outcome with the committed cell (quote located, same form and
filing date cited, share of the committed figures reproduced, status) and
writes `data/ingest/calibration_<key>.json`. Its comparison arithmetic is
covered by `test_ingest`. The run itself needs filing text on disk and an
Anthropic key. Neither exists in this container (`data/raw/` is not in git,
`sec.gov` is blocked, no key). No agreement rate is reported because none
was measured. On a networked machine with the key in the environment:

```
export TARK_SEC_CONTACT='Your Name your@email'
export ANTHROPIC_API_KEY=...
python src/fetch_edgar.py cliffwater_cclfx
python src/calibrate_ingest.py cliffwater_cclfx
```

## 6. Seventeenth product (P2-4): blocked here, not faked

Candidate: ACAP Strategic Fund (XCAPX), CIK 1467631, in the census as an
unlisted Rule 23c-3 interval fund with promotion status none, so
`promote.py` accepts it. Nothing about it was written into the record. On a
networked machine:

```
python src/promote.py 1467631 --key acap_strategic
# write the data/registry.json entry for acap_strategic (cohort, strategy,
# wrapper_type, pricing_class, nav_cadence, leverage_regime, held_returns,
# advisers, declared_benchmarks, as_of, depth, membership_rationale,
# filings, each with its source) and add it to that cohort's members list,
# then an admission entry in data/roster_decisions.md
python src/fetch_edgar.py acap_strategic
python src/ingest.py 1467631 --key acap_strategic --skip-fetch
python src/produce.py && python src/build_site.py && bash hooks/pre-commit
```

`validate_data` refuses a product in `data/products` without a registry
entry, so a half-added product cannot pass the hook.

## 7. Verification protocol (section 8 of the brief), results

1. All gates through `hooks/pre-commit`: green, 101 seconds, counts in
   section 2.
2. `src/reconcile.py` (gated): 4 checks over 16 products, following each
   fact's `source_cell` (kkr_kpec's expense ratio is typed from cell 1.3
   and its headline says so).
3. `src/test_invariants.py` (gated): 16 checks including verified count 0,
   empty `verified_by` in every CSV, no product-count copy, no dead data
   path, record totals pinned at 205 n/a, 161 computed, 75 partial (the pin
   moved from 237, 145, 59 with the reason in commit `abedf28`).
4. Playwright sweep 18 views by 16 products by 4 plans with the HTML parsed
   (`test_frontend`): zero stray fragments, zero `undefined` or `NaN`, zero
   console errors, no unread bundle key. After screenshots:
   `docs/screenshots/after_2026-09/`, 42 JPEG files, 8.5 MB, same views and
   products as the baseline set.
5. Mobile (390 px) and print renders of Roster, Evaluation and Benchmarks:
   a 452 px horizontal overflow from the header selects and unwrapped stat
   rows was found and fixed with a 600 px media query. Both renders are now
   gated with zero overflow and no page error.
6. The Tier 1 cells, drawer against the CSV: automated for every Tier 1 row
   (document, verbatim quote and accession equal the CSV). EDGAR HTTP 200
   cannot be checked from this container and is recorded as not checked.
7. Audit reproduction table: section 8 below.

## 8. Audit reproduction table (section 3 of the audit, item by item)

Status vocabulary: Fixed, Partially fixed, Not attempted.

### 3.1 Six-factor grid

| finding | status | where |
|---|---|---|
| "864/864 resolved" counts n/a as resolved | Fixed | per-kind coverage, headline states resolvable, n/a and verified separately (P0-5) |
| cells 5.6 and 5.7 n/a for all products | Fixed for 5.6, Partially fixed for 5.7 | 5.6 computed by the writer from the selection, 5.7 `partial` from the docket listing until the source documents are fetched (P1-23) |
| about 125 computed cells restate prose no script produces | Fixed | `src/write_computed_cells.py` owns 1.8, 1.9, 2.9, 3.8, 3.9, 5.3, 5.4, 5.5, 5.6 (P0-2, P0-7, P1-D2, P1-23) |
| three coverage formulas, structured shown as pending | Fixed | `coverage_summary` used by every surface (P0-5) |
| rule mapping asserted, no paragraph quoted, FR document not in the manifest | Partially fixed | `rule_ref` per cell with its basis, authority panel with FR link and docket, fetcher written, verbatim text not fetched here (P1-26, decision 3.14) |
| no EDGAR link, 8 accessions in 481 rows, laptop paths | Fixed offline | accession column on every row from the offline resolver, EDGAR links in the drawer, laptop paths purged, validator hard (P1-D prep, P2-10). Online resolution of the 46 non-exact references waits for network |
| `anchor_plan.json` dangling in six cells | Fixed | P0-6 plus the path validator |

### 3.2 Benchmark-selection engine

| item | status | where |
|---|---|---|
| 1 scores strategies, not products | Fixed | typed descriptors from `data/registry.json` and facts, property tests (P1-7) |
| 2 secondary equals primary | Fixed | secondary on a different series or "no eligible secondary" (P1-10) |
| 3 risk_liquidity 3/3 unreachable | Fixed | perfect candidate scores 12 (P1-6) |
| 4 wrong asset class passes | Fixed | strategy gate, below 2 is ineligible (P1-5) |
| 5 Lane A not implemented | Fixed | typed declared benchmarks scored on merits, no points for the declaration (P1-8) |
| 6 CDLI independence wrong per product | Fixed | independence against the registry's advisers per product (P1-9) |
| 7 escalation hand-flagged | Fixed | computable escalation, arkvx escalates on the gate (P1-12) |
| 8 Lane C never scored | Fixed | leave-one-out composite, fiscal alignment printed, primary for nine products (amg_pantheon, ares_pmf, bcred, cion_ares, cliffwater_cclfx, hl_paf, ocic, pflex, stepstone_spm), secondary for kkr_kpec (P1-11) |
| 9 silent proxy-window truncation | Fixed | intersection window, one anchor, JS parity (P1-1) |
| 10 integer-year annualization | Fixed | actual/365.25 (P1-2) |
| 11 KS-PME and Direct Alpha are one number | Partially fixed | stated as such on card and methodology, ILLUSTRATIVE monthly-schedule row, real cash flows still not held (P1-3) |
| 12 override is a lookup | Partially fixed | lab verdict from the real v2 scorer for every proxy and product with a series (P1-15), no UI to edit weights or load a series (P3) |
| 13 jll_ipt has no selection | Fixed | P1-13 |
| 14 short windows | Fixed as labeling | low confidence on card and memo (P1-14), the windows are what the record holds |

### 3.3 Liquidity match

| finding | status | where |
|---|---|---|
| verdict from two hand-typed booleans | Fixed | structural layer from typed facts, `LIQUIDITY_PROFILES` deleted (P1-16, P1-17) |
| demand never changes the verdict | Fixed | scenario layer, ILLUSTRATIVE, moves with the plan (P1-16) |
| plan data is Form 5500 only | Partially fixed | Schedule H fields in the schema as null-with-reason, used when present (P1-18), values to be filled from the bulk files on a networked machine |
| 16 legacy match files | Fixed | P0-8 |

### 3.4 Decision memo

| finding | status | where |
|---|---|---|
| one plan for every memo | Fixed | 64 memos, one per plan and product, links follow the plan (P1-19) |
| findings table truncated mid-sentence | Fixed | P1-20 |
| no recommendation section | Fixed | recommendation, liquidity match, scope, case law (P1-21) |
| citations are cell ids only | Fixed | accession and EDGAR URL per citation, "accession not on record" otherwise (P1-22) |
| provenance claims verification | Fixed | true counts, verified sentence only when the count is above 0 (P1-22) |
| hardcoded case-law sentence | Fixed | removed, cell 5.7 `partial` and labeled (P1-23) |
| caveats contradict typed facts | Fixed | P1-24 |
| test covers 6 of 16 | Fixed | 64 of 64 (P1-25) |
| memo dated with the build date | Fixed | record as-of, build date in provenance only (P1-19) |
| cannot regenerate from the UI | Not attempted | build-side by design, the service is one endpoint (decision 1.5) |

### 3.5 Cohorts

| finding | status | where |
|---|---|---|
| membership hardcoded | Fixed | registry (P2-1) |
| percentile ties | Fixed | mid-rank (P0-7) |
| composite unconsumed | Fixed | Lane C (P1-11) |

### 3.6 Fee Matrix

| finding | status | where |
|---|---|---|
| bars and chips from a first-number regex | Fixed | typed facts only, bars only where a net expense ratio exists, absences named with their reason (P0-3) |

### 3.7 Labs

| finding | status | where |
|---|---|---|
| Analysis Lab falls back to cclfx | Fixed | P0-4 |
| De-smoothing Lab covers 2 products | Fixed | every daily series (P0-4) |
| run_analytics hardcodes returns | Fixed | reads the record (P1-4) |
| Yahoo series labeled as NAV | Fixed | P1-4 |

### 3.8 Coverage and Verification

| finding | status | where |
|---|---|---|
| stale hero from the 6-product taxonomy | Fixed | regenerated each build (P0-5) |
| crosscheck tile hardcoded and worded as independent | Fixed | parsed from the report header, worded as an agent pass (P0-5) |
| "0 human-verified" literal | Fixed | live count (P0-5) |
| Verification view read-only | Partially fixed | the form makes the `verify_cell.py` command with signer and date, the site still writes nothing by design (P2-7) |

### 3.9 Stale and broken copy

| finding | status | where |
|---|---|---|
| all seven items | Fixed | P0-1, P0-2, P0-10, held by `test_invariants`, `test_copy`, `test_docs` |

### 3.10 Census

| finding | status | where |
|---|---|---|
| "Evaluate this fund" is a paragraph | Fixed | button plus copyable command, service endpoint (P2-5) |
| accessions not hyperlinked to EDGAR | Partially fixed | evidence drawer links every resolved accession (P2-10), the census entity detail does not link yet |
| build outputs not in `.gitignore` | Fixed | P0-8 |
| exchange flag not share-class aware | Fixed | `listed_common` and `listed_other_classes`, recency rule, four funds reclassified, two null with reason (P2-11) |

### 3.11 What a 3(21) advisor cannot do

| item | status | where |
|---|---|---|
| 1 evaluate their own fund | Partially fixed | `ingest.py` and the registry make it one command and one declaration (P2-1, P2-2), live run and calibration blocked here (sections 5 and 6) |
| 2 add a plan | Fixed | anonymized intake (P2-8) |
| 3 edit a rubric weight or menu | Not attempted | P3, design-partner input (decision 1.3) |
| 4 supply a benchmark series | Not attempted | P3 |
| 5 sign off, annotate, dissent | Partially fixed | signing through `verify_cell.py` (P2-7), advisor-stated cells (P2-6), no free-text dissent |
| 6 export a committee packet | Fixed | P2-9 |
| 7 share with a committee | Not attempted | P3, accounts and audit trail |
| 8 evaluate a TDF sleeve or CIT | Not attempted | P3-1 vehicle model (decision 1.4) |
| 9 open a cited source document | Partially fixed | EDGAR link per row, raw filings still not distributed |
| 10 PME on real cash flows | Not attempted | ILLUSTRATIVE schedule only (P1-3) |
| 11 restrict access | Not attempted | P3 |

### 3.12 Rule alignment

| finding | status | where |
|---|---|---|
| peer cohort is central to the rule, engine rejects it | Fixed | Lane C composite is the primary for nine of the 13 non-escalated products, wherever three or more members overlap (P1-11). arkvx, dxyz and ssss escalate |
| rubric rewards what the rule does not mention, strategy 0 passes | Fixed | strategy gate, no candidate below strategy_match 2 is eligible, investability, data quality and independence remain 6 of 12 points behind the gate (decision 3.8) |
| selection-only scope not stated | Fixed | scope sentence on the authority panel and a scope section in every memo (P1-21, P1-26) |
| cannot represent a sleeve | Not attempted | P3-1 |
| complexity factor cells 6.6 and 6.8 empty | Fixed | advisor-completed under paragraph (l), advisor-stated inputs with their own status (P1-26, P2-6) |

## 9. Decisions for Oscar to confirm or reverse

All reversible. The entry number is in `docs/DECISIONS_2026-09.md`.

1. Branch name: work is on the harness-assigned branch, not
   `remediation-2026-09` (section 2). Rename or re-point the PR at will.
2. Audience 3(21) advisors, October milestone stands (1.1, 1.2).
3. Rubric v2 is the default and v1 survives only as a frozen snapshot plus
   the corrections table, no live `TARK_RUBRIC=v1` switch (1.3).
4. Standalone products through P2, static site through P1 with the
   one-endpoint service as the first backend, verification stays human
   (1.4, 1.5, 1.6).
5. `stepstone_spm` return basis: the fiscal-year series, not the 5-year
   AATR, with the correction logged (section 2).
6. Lane A earns no points for the declaration (3.5). Lane C composite is
   leave-one-out, needs three overlapping members, earns data_quality 1 only
   with three or more overlapping years (3.6). Threshold 7, tie-breaks on
   strategy_match then risk_liquidity_match then data_quality (3.8).
7. Liquidity vocabulary gained `misaligned` and `partial`, structural
   precedence of suspension over a null fact, `repurchase_program_status`
   never `active` by default (3.3, 3.4).
8. Cell 5.7 case law at `partial` from the docket listing and search
   snippets, never `extracted` (3.15). Regulatory text is never written from
   memory or a law-firm summary (3.14).
9. Corrections log is a generated table and evidence rows are immutable by
   gate, with two wildcard allowlist rows for the accession column and the
   laptop-path purge (3.11, 3.12, 6.30).
10. Census: four interval-era funds reclassified to `listed_cef` by the
    24-month N-23C3A recency rule, two active ones set to `listed_common`
    null with reason (3.19). The `or True` is deleted and the N-CEN adviser
    lists are not regenerated here (3.18).
11. Plan Schedule H fields are null-with-reason until filled from the bulk
    files (3.20).
12. Demo script v7 speaks the numbers in its closing table and nothing else,
    Tier 1 is derived from that table (3.16).
13. P3 order: CI first, then the vehicle model, identity out of the repo,
    `app.py` retirement, `make refresh` (6.32). No P3 code shipped.
14. `gh-pages` not redeployed from this session. The live URL still shows
    the pre-audit build until the PR is merged and redeployed.

## 10. Deferred to a machine with network and a key

- `python src/fetch_authority.py`: paragraphs (g) to (l) of the proposed
  rule into `data/authority/` with a manifest row and content hash. Until
  then every surface says the text is not yet in the build.
- P2-3 calibration and P2-4 the 17th product (sections 5 and 6).
- Online half of the accession resolver (submissions JSON) for the 46
  references that are not exact matches (28 form-only, 2 ranges, 5 sets,
  9 accession-in-text, 2 ambiguous on breit 1.3).
- Census adviser lists from the N-CEN checkpoint after the `or True`
  deletion, and the census entity detail's EDGAR links.
- Plan Schedule H fields from `F_SCH_H_2024_latest.csv`.
- EDGAR HTTP 200 on the Tier 1 accessions.
- CI (P3-2) running all 18 gates, then the `gh-pages` redeploy from a green
  `main`.

## 11. How to review this pull request

```
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cp hooks/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
sh hooks/pre-commit                      # 18 gates, about 100 seconds
python -m http.server 8410 -d site       # then docs/demo_script.md v7
```

Read `docs/DECISIONS_2026-09.md` sections 1 to 3 first, then the
"Corrections 2026-09" table in `docs/crosscheck_report.md`, then the
after screenshots against the baseline set.

## Superseded

`docs/BUILD_REPORT_5.md` remains the record of the census build. Its
statements about the six-product-era surfaces, the "Lane C fed" claim in
`docs/BUILD_REPORT_4.md` and every published KS-PME figure before this
report are superseded by the corrections table.

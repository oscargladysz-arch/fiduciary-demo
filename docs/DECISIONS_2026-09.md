# Decisions log, remediation 2026-09

Every judgment call taken during the remediation of the 2026-09-03 audit
(`docs/GAP_ANALYSIS_2026-09-03.md`). Each entry states the default taken and
who can reverse it. Oscar can reverse any of them. New entries are appended
as they are made, with the date and the task id.

Conventions in this file: `*` is multiplication, `/` is division, no em
dashes, no semicolons.

## 0. Environment facts that constrained the work (2026-09-04)

- Outbound network from the build environment is policy-limited. Blocked at
  the egress proxy (403 on CONNECT, for both curl and the WebFetch tool):
  `www.sec.gov`, `data.sec.gov`, `efts.sec.gov`, `www.federalregister.gov`,
  `www.dol.gov`, `www.govinfo.gov`, `www.ecfr.gov`, `www.regulations.gov`,
  `www.supremecourt.gov`, `www.congress.gov`, law-firm and news hosts,
  `query1.finance.yahoo.com`, `oscargladysz-arch.github.io`,
  `cdnjs.cloudflare.com`. Open: `pypi.org`, `api.github.com`,
  `raw.githubusercontent.com`, `api.anthropic.com` (reachable, but no
  `ANTHROPIC_API_KEY` is set). Web search works and returns snippets and
  URLs only.
- `data/raw/` and `data/census/raw/` are gitignored and absent in this
  clone. No source filing and no census checkpoint is on disk.
- Playwright 1.62 expects Chromium build 1234. The environment ships build
  1194, which matches Playwright 1.56.0. The venv pins 1.56.0 (within the
  `>=1.55` requirement). No browser was downloaded and no test was changed
  for this.
- Identifiers established by web search on 2026-09-04, with the URLs that
  returned them, so the record shows where they came from:
  - Federal Register document 2026-06178, published 2026-03-31, 91 FR 16088,
    RIN 1210-AC38: https://www.federalregister.gov/documents/2026/03/31/2026-06178/fiduciary-duties-in-selecting-designated-investment-alternatives
  - DOL copy of the proposed rule (PDF): https://www.dol.gov/sites/dolgov/files/ebsa/laws-and-regulations/laws/erisa/fiduciary-duties-in-selecting-designated-investment-alternatives.pdf
  - Docket EBSA-2026-0166: https://www.regulations.gov/docket/EBSA-2026-0166
  - Anderson v. Intel Corp. Investment Policy Committee, No. 25-498,
    certiorari granted 2026-01-16: https://www.supremecourt.gov/docket/docketfiles/html/public/25-498.html
  - CRS Legal Sidebar LSB11396, "Supreme Court to Examine ERISA Pleading
    Standards": https://www.congress.gov/crs-product/LSB11396
  None of these pages could be opened from the build environment. They were
  not read. Only the identifiers and one-line descriptions returned by the
  search engine are used, and every surface that relies on them says so.

## 1. Section 6 of the audit: decisions only Oscar can make (defaults taken)

### 1.1 Audience for the September 8 outreach
Default: 3(21) advisors. Site copy addresses "the advisor" and "the
committee", not "the investor". Reverse by: search-and-replace in
`site/js/*.js`, `docs/demo_script.md`, `docs/INVESTOR_DEMO.md`.

### 1.2 The October milestone
Default: it stands. P2-2 (ingestion pipeline), P2-3 (calibration) and P2-4
(17th product) are the definition of done. In this environment P2-3 and P2-4
cannot run (no EDGAR, no filings on disk, no API key). They are delivered as
runnable code plus the exact commands, and reported as not run. No wall time,
cost or agreement table is estimated.

### 1.3 Rubric v2 versus design-partner input
Default: v2 ships as the default and is presented to design partners as the
thing they critique. Deviation from the brief's default: instead of a live
`TARK_RUBRIC=v1` switch (a switch that can republish known-wrong numbers and
doubles every artifact path for a build), v1 survives as a frozen read-only
snapshot in `data/benchmarks/v1_snapshot/` taken before any P1 change, and
the generated corrections log shows old and new side by side. Before and
after are therefore visible without a code path that can regress.

### 1.4 Standalone product versus sleeve
Default: standalone products remain the unit of record through P2. The
sleeve model is P3-1 and is written as a plan only.

### 1.5 Stack narrative
Default: the site stays static and build-time through P1. The P2 service in
`service/` is the first real backend and is described as such. The product
is not described as FastAPI plus Postgres plus React anywhere.

### 1.6 Verification
Default: verification stays human. Nothing in this remediation sets a cell
to `verified`. The Tier 1 queue is prepared for a human with the quote and
the source side by side. An invariant test asserts `verified` count is 0 and
`verified_by` is empty in every committed evidence CSV for this pull request.

## 2. Discrepancies between the brief, the audit and the record

The audit wins on scope. The record wins on counts. Both are logged.

- Branch: the brief names `remediation-2026-09`. The session harness assigns
  `claude/tark-audit-defects-t2vfel` and forbids pushing elsewhere. Work is
  on the assigned branch. Oscar can rename or re-point the PR.
- Cell 5.4 "six-product universe": the literal exists only in `breit`. The
  cells for `hl_paf`, `stepstone_spm` and `kkr_kpec` are stale by omission
  (they name 2 of the 5 evergreen-PE peers). All 16 cells 5.4 are regenerated
  from cohort membership through the new writer.
- Percentile-tie contradictions: 12 contradictory sub-phrases in 10 cells
  (5 at "10th percentile, at the median" with n=5, 4 at "12th" with n=4 from
  banker's rounding of 12.5, 3 at "30th"), not 16. All 16 cells 2.9 are
  regenerated.
- Rubric ceiling: brute force over `score_candidate` gives a maximum of 10,
  not 11. `test_benchmark.py:26` already asserts 10. v2 makes 12 reachable.
- A second window defect the audit missed: `tark_benchmark.py:368` computes
  the displayed index growth on the full series while lines 372 to 373 hand
  `ks_pme` a list pre-filtered to dates at or after the start, so on a
  non-trading-day start the card's growth ratio and its KS-PME disagree
  (ocic 1.1541 versus published 1.1520, breit 0.9064 versus 0.9073). Fixed
  together with P1-1 by using one anchor on both sides.
- The JS port already annualizes by day count (`site/js/analytics.js`), so
  the Analysis Lab and the benchmark card beside it disagree today. P1-2
  makes Python match.
- `stepstone_spm`: the engine uses a 5-year AATR of 12.92% (growth 1.8359)
  while `data/series_annual/stepstone_spm.csv` FY2022 to FY2026 compounds to
  1.9504 over the same window. Default: use the fiscal-year series, the same
  method as hl_paf and amg_pantheon and the one the whole-fiscal-year window
  rule requires. The correction is logged and the cell goes to Tier 1 of the
  verification queue. Flagged for Oscar because both figures are printed in
  the filing.
- `data/analytics/supplement.json` was generated 2026-08-15 for 14 products.
  The Fee Matrix therefore omitted `cion_ares` and `ocic` entirely and ranked
  "of 11". The supplement is regenerated inside the build.
- `src/build_facts.py:676` spreads the cell status after the explicit
  keyword status, so dxyz `repurchase_cadence_per_year` 252 (a trading-day
  convention) ships as `extracted-unverified` although cell 3.1 contains no
  "252". Fixed in P0-3.
- `jll_ipt` has five facts fields at status `pending`, not four. The fifth
  is `liquidity_verdict_by_plan`, gated on a benchmark artifact at
  `build_facts.py:691-702`. Decoupled in P1-13. `jll_ipt` has no computable
  fund return series at all (`series_annual/jll_ipt.csv` prints a per-class
  range 3.0% to 3.8%), so its selection carries scored candidates and an
  explicit "no computable fund series" comparison. No return is invented.
- Memos are not generated at build time. `build_site.py:560-563` only copies
  prebuilt files. Generation moves into the build.
- Laptop paths: 369 evidence rows (252 under `/private/tmp`, 117 under
  `/Users`) plus 4 notes in `data/series_annual/manifest.json`. Purged in
  P2-10 with each change allowlisted in the corrections log.
- Accessions: 9 of 482 evidenced rows carry one, and only two distinct
  accession numbers exist in the whole record.
- `data/plans/*.json` commit sponsor names, plan names, EINs and Form 5500
  ack ids. The build screens 5 tokens. `test_app.py:19` and
  `test_frontend.py:31` list 4 (missing `psrp`). EINs and ack ids are never
  screened. A shared forbidden-token module lands in P0-0. The at-rest move
  out of the public repo is P3-3.
- No typed adviser, sub-adviser, declared-benchmark, pricing-class,
  exchange-listing or repurchase-program-status field exists in the facts
  layer. They are added in P1 (registry for identity, `build_facts.MAPPING`
  for cell-cited facts) and every string fact is substring-checked against
  its cited cell by the validator.

## 3. Design decisions taken during the remediation

### 3.1 Coverage vocabulary (P0-5)
Segments per status kind: structured, extracted-unverified, verified,
computed, partial plus fetched, n/a, pending. A legend names the tier of
each. The headline reads "47 of 54 resolvable, 0 verified, 7 n/a by
wrapper". There is never one merged "covered" count, because that would blur
T1, T2 and T3.

### 3.2 Cell headline chips (P0-3b)
`build_site.cell_display` derived headlines with a first-figure regex for all
864 cells and fed every Evaluation card, not only the Fee Matrix. New rule:
the headline is the typed fact when a fact cites the cell, otherwise the
first complete sentence of the value. No figure is extracted by regex.

### 3.3 Liquidity verdict, two layers (P1-16, P1-17)
`structural_verdict` is computed from facts only: exchange-listed gives
`aligned-mechanical`, a suspended program or a zero cap gives `misaligned`,
gating history gives `conditional-weak`, otherwise `conditional`, and a null
required fact gives `partial` (suspended takes precedence over null).
`scenario_verdict` is labeled ILLUSTRATIVE and comes from the demand model:
base demand above capacity gives `misaligned`, stressed demand above capacity
gives `conditional-weak`. The full pro-rata proration assumption behind the
comparison of a plan position's demand to a fund-level cap is printed. The
brief's test that a verdict changes between plans is asserted on the scenario
layer. The memo Recommendation reads the structural verdict and quotes the
scenario layer as ILLUSTRATIVE.

### 3.4 `repurchase_program_status` (P1-17)
Typed `suspended` only when cell 3.1 or 3.3 text carries suspension language
(sreit). Otherwise null with the reason "no suspension language in 3.1/3.3 as
of <as-of>". Never `active` by default, because no filing says "active".

### 3.5 Lane A earns no points for the declaration (P1-8)
Four evergreen-PE funds declare MSCI World in cell 5.1. Awarding a point for
the declaration would push a public-equity ETF through the strategy gate for
all four. The declaration is recorded as a fact on the card and in the memo.
Lane A candidates are scored on the same criteria as every other candidate.
When the declared benchmark fails the gate, the card says so in one sentence.

### 3.6 Lane C composite (P1-11)
Leave-one-out per subject (a fund is never a third of its own benchmark).
Partial-period rows are excluded (`period_months` under 12, derived from the
row notes that already state the stub). Members are aligned on fiscal-year
overlap and the misalignment is printed. The composite is refused under 3
remaining members. `data_quality` is 1 only with 3 or more overlapping years.

### 3.7 Expected outcomes before code (P1-B)
An expected v1 to v2 outcome table per product is written into
`docs/benchmark_methodology.md` before the engine changes and asserted in
`test_benchmark.py`. arkvx is expected to move to computable escalation once
SPY and PSP fail the strategy gate and the venture composite stays refused.
The threshold stays 7 of 12. Ties break on strategy_match, then
risk_liquidity_match, then data_quality, then menu order.

### 3.8 Rubric criteria (P1-6, P1-7)
`risk_liquidity_match` 3 requires a NAV-class series whose cadence matches
the fund's dealing cadence and whose leverage regime matches. Provider
affiliation is scored only in `provider_independence`. `investability` is 0
or 2 (held or not). Window clipping is reported in the window note and not
scored. The card prints "max attainable on held data: N/12" so a 12-point
scale is never advertised where 12 cannot be reached.

### 3.9 Single writer for engine-derived cells (P0-2, P0-7, P1-23)
No committed script produced the computed cell prose, so
`src/write_computed_cells.py` is created. It declares the cells it owns,
refuses any target whose status kind is not `computed` or `n/a`, writes a
machine sentence plus an `analyst_note` carried from committed
`data/notes/<key>.json` (seeded from today's prose so analyst judgment is not
lost), stamps `extracted_by` with the script name and git sha, and is
idempotent.

### 3.10 Deterministic producers and a freshness gate (P0-0)
Producers take `--as-of` and never write wall-clock dates into artifacts.
`tark_data.DATA` honours `TARK_DATA_DIR`. `src/produce.py` runs the chain in
a fixed order (supplement, liquidity, facts, cohorts, benchmark, computed
cells, memos) and is the only way producers run. The freshness gate re-runs
the chain into a temporary directory and compares normalized artifacts. The
memo date is the record as-of date. The build date appears only in
provenance.

### 3.11 Generated corrections log (P0-0, P1)
`src/corrections_log.py` diffs old versus new selection JSON, facts and owned
cells and writes old, new, cause tag and surfaces under "Corrections 2026-09"
in `docs/crosscheck_report.md`. The freshness gate refuses an artifact change
with no log entry.

### 3.12 Evidence immutability by gate (P0-0)
`src/test_evidence_immutable.py` diffs every extracted, partial, fetched and
structured row (all columns) against `origin/main` and fails on any change
not allowlisted in the corrections log. `validate_product` compares value,
source, quote and extracted_by between JSON and CSV, not only status.

### 3.13 Copy rule scope (P0-10)
No em dashes and no semicolons in generated and user-facing strings: JS
string literals, engine reason strings, memo text, writer prose. One
mechanical sweep with `src/test_copy.py`. Verbatim filing quotes are exempt.
Docs are exempt (the verification-queue parser format depends on its
current line shape).

### 3.14 Regulatory text (P1-26)
`src/fetch_authority.py` fetches Federal Register document 2026-06178 and
extracts paragraphs (g) to (l) of proposed 29 CFR 2550.404a-6 verbatim into
`data/authority/2550-404a-6_proposed.md` with a manifest row and a content
hash. It cannot run from the build environment. Until it has run, the
authority panel and the memo show the factor names, the citation, the link
and the docket, plus the sentence "regulatory text not yet fetched into this
build". Each cell's `rule_ref` carries a `basis` string ("factor order per
the 2026-09-03 audit's check of 91 FR 16088, verbatim text not in this
build"). No regulatory text is written from memory or from summaries.

### 3.15 Case-law cell 5.7 (P1-23)
Populated at status `partial`. Value limited to what the search results
support: certiorari granted 2026-01-16, docket 25-498, the question presented
(whether an underperformance claim must plead a meaningful benchmark),
argument not yet held as of the build date. Source is the URL plus access
date. The quote is the search snippet, labeled "search snippet, not the
source document". `extracted_by` is "Claude Code (WebSearch snippet, date)".
It is never `extracted`.

### 3.16 Demo script v7 (deliverable 3)
Demo script v6 speaks three numbers the record cannot support: "$19.8B of
net assets" (the figure appears nowhere in `data/`), "46 quarterly tenders"
(an EFTS filing count that includes 26 amendments), and "a human-verified
core" (0 cells are verified). v7 drops them. Tier 1 of the verification
queue is re-derived from the numbers v7 speaks. Census counts are labeled
validator-enforced T1, not human-verified. The three files that named three
different landing views (script, INVESTOR_DEMO, `main.js`) are made to
agree.

### 3.17 `app.py` while it remains deployed
Retirement is P3-4. Its live defects are fixed in P0 and P1 instead of left:
the roster caption, the coverage caption and formula, the rubric caption
(`:188-191`), the plan label on the liquidity view (`:239`), the verdict
styling (`:245`).

### 3.18 The census `or True` (P0-8)
Deleted as the brief requires, with the exact rebuild command in a comment.
The N-CEN checkpoint it reads is gitignored and absent, so `census.json`
adviser lists are not regenerated here. A rebuild on a machine with the
checkpoint may change adviser lists for up to 709 entities.

### 3.19 Census listed flag (P2-11)
Of the six `interval_23c3` entities flagged listed, four (MXF, IFN, CCIF,
DMA) stopped filing N-23C3A between 2009 and 2021 and are listed CEFs today.
They are reclassified by an N-23C3A recency rule from stored data, with the
rule appended to `detection_evidence`. The two still-active ones (CIK
1551047, 1644771) get `listed_common: null` with the reason "share-class
resolution requires a submissions refetch". Both `census.json` and
`universe.json` are updated so `counts_by_class` stay equal.

### 3.20 Plan Schedule H fields (P1-18)
The DOL bulk CSVs are not in the repo and the host is blocked. The fields
(benefit payments, participant contributions, QDIA code) are added to the
schema as null with reason and documented in `dictionary_cells`. The demand
model uses the outflow rate when present and names which model produced the
number. Oscar can fill them from `F_SCH_H_2024_latest.csv`.

### 3.21 P3 plan (not started)
Order: P3-2 CI first (GitHub Actions running all gates on every push, gh-pages
deploy only from a green `main`), then P3-3 anonymization at rest
(`validate_plan` changes first, the token module reads the private source),
P3-4 retire or thin `app.py` (the `test_app.py` gate is replaced, not
deleted), P3-5 `make refresh` with per-layer as-of dates, P3-1 the vehicle
model with one ILLUSTRATIVE sleeve example.

## 4. Baseline recorded 2026-09-04 (before any change)

See `docs/BUILD_REPORT_6.md`, section "Baseline".

## 5. Entries appended during P0

### 5.1 P0-0: the 33 JSON versus CSV `extracted_by` drifts
All 33 were the same shape: the product JSON carried the extraction pass
date ("Claude (Inc-1 2026-07-18)") and the CSV omitted it ("Claude
(Inc-1)"). The CSV was synced to the JSON. Nothing was invented, the date
was already in the record. Each of the 33 rows is allowlisted in
`docs/crosscheck_report.md` with this reason, and `validate_product` now
compares value, source, section, quote, extracted_by and verified_by
between the two stores, not only status.

### 5.2 P0-0: identified User-Agent from the environment
The three hardcoded contact strings (`src/fetch_edgar.py`,
`src/fetch_series.py`, `src/census/edgar_api.py`) now read
`TARK_SEC_CONTACT`. There is no fallback contact value: SEC fair-access
policy requires a real name and email, and a made-up default would be a
false identity, so the fetchers refuse to run until the variable is set
(`export TARK_SEC_CONTACT='Your Name your@email'`). The Yahoo fetcher no
longer spoofs a browser User-Agent. `promote.py` keeps the wall-clock date
for `date_pulled`, because that field records when a pull happened, not
the record's as-of date.

### 5.3 P0-0: the freshness gate covers four artifact families first
`src/test_artifacts_fresh.py` compares liquidity, facts, cohorts, benchmark
selections and memos. All five reproduced exactly from a fresh run on
2026-09-04 (the memos only after the date moved from the wall clock to the
record as-of). `data/analytics/supplement.json` joins the set in P0-3, once
`fee_percentile` reads typed facts, so that the regex-derived bars for
`cion_ares` and `ocic` are never regenerated and published.

### 5.4 P0-0: the pre-commit chain grew from 9 to 12 gates
Added: `test_evidence_immutable`, `corrections_log check`,
`test_artifacts_fresh`. `docs/INVESTOR_DEMO.md` is updated in P0-10 and a
test derives the count from `hooks/pre-commit`.

### 5.5 P0-8: a bundle key ships only with its reader
The dead-key check is a runtime one: the Playwright sweep wraps
`window.TARK`, `TARK_SERIES`, `TARK_LIQ` and `TARK_CENSUS` in a recording
Proxy the moment the bundle scripts assign them, keeps the read set across
the share-link reloads through `sessionStorage`, and diffs every emitted
key against every read key at the end of the run. It found the eight keys
the plan named and four more. Consequences:

- `series_sources` (the small map that replaces `series_manifest`) does not
  ship yet. No view reads it until P1-4 labels every Yahoo chart from it,
  so the map and its reader land together in P1-4. Emitting it early would
  fail the gate the plan itself requires.
- `supplement.fee_percentile` stays in `data/analytics/supplement.json`
  (the corrections log tracks its bars and P1 owned cells read it) but no
  longer ships: since P0-3 the Fee Matrix bars come from typed facts.
- The `nslr` adjusted-close series is dropped from the series chunk. The
  ssss profile is market-priced, so every surface reads `nslr_daily`
  (close) with the market-price warning, and the engine reads the file.
- The census chunk no longer carries `what` and `tiers`. Both stay in
  `data/census/census.json` as file-level documentation. The chunk's
  `row_fields` is now the one source for the compact row format: the
  screener decodes rows from it instead of hand-typed indices, and the
  census surface prints the census as-of date it always shipped.
- Two keys are read only on interaction (`census.shards` behind an entity
  click, the `urth` and `spy` proxy series behind the lab's proxy radio),
  so the sweep now exercises both paths: it opens the cclfx census entity
  from its detail shard and selects every offered proxy in the lab. Those
  are real checks (the shard fetch path and every proxy computing a
  KS-PME), not only bookkeeping for the dead-key rule.
- The 16 legacy `data/liquidity/<product>_match.json` files, their writer,
  the `liquidity_profiles`, `scenario_defaults`, `metrics.dxyz`,
  `metrics.hl_paf_annual`, `series_monthly.breit_nav_manifest`,
  `supplement.stress_windows` and unread `series_quarterly` keys, the
  drawer's "Local file (repo)" field, `charts.ring`, and the unused imports
  are gone. The stress-window parity checkpoint in the frontend gate now
  reads the committed supplement file, so the assertion survives without
  shipping the key.
- `src/census/build_census.py` no longer forces adviser regeneration
  (`or True`). The N-CEN checkpoint is not in this environment, so the
  adviser lists were not regenerated here. The rebuild command sits in the
  comment that replaced the override.

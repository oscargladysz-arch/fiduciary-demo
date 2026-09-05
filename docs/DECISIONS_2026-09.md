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

### 5.6 P0-10: the copy rule is a gate, and documents derive their numbers
`src/test_copy.py` scans every string and template literal in
`site/js/*.js`, every string constant in the Python modules that write
surface text, and the documents this engagement owns, for an em dash or a
semicolon. Its scope and exemptions are stated in its docstring and
repeated here because they are judgment calls:

- Exempt by construction: regex patterns, inline CSS and attribute
  plumbing, and literals with no letters once HTML tags and entities are
  stripped (a dash glyph alone in an empty table cell is a symbol, not
  punctuation). A `copy-exempt` marker with its reason on the line covers
  the few code strings the heuristics miss. Verbatim filing language keeps
  its punctuation and carries the marker.
- Out of scope: `data/` (the record and its verbatim quotes), the
  verification queue (its row format is what the parser reads), the older
  build reports and the v6 demo script (v7 replaces it in the deliverables
  and joins the owned list then), the console-only scripts (validators,
  tests, fetchers, `produce.py`, `shots.py`), whose output reaches a
  developer, not a surface.
- The 242 literals the gate found on 2026-09-04 were rewritten in one pass
  without changing any number, name, citation or quoted phrase. Reason
  strings that live in generated artifacts (facts, liquidity, selections,
  cohorts, memos) were regenerated by `produce.py` in the same commit and
  every changed published field is in the corrections log under the cause
  `copy sweep (P0-10)`.

`src/test_docs.py` pins `docs/INVESTOR_DEMO.md` to its sources of truth:
the gate count and the gate list come from `hooks/pre-commit`, the roster
count from the record, the landing view from `site/js/main.js`, the
universe counts from `data/census/*.json`. The runbook therefore no longer
carries record coverage percentages at all. The person presenting reads
them off the Coverage view, which recomputes them per status kind. The
same gate checks that the verification queue names exactly the cells the
record holds at `structured` (one, `cion_ares 4.6`, as of 2026-09-04. The
other census prefills were re-extracted on 2026-08-25 or are `n/a`), that
the superseded Lane C claim in `docs/BUILD_REPORT_4.md` stays marked, and
that `hook_snapshot.txt` and `README_SPIKE.md` (deleted, both stale) are
not referenced by any living document. `README.md` is new and short.

The landing view: the runbook now says the app opens on the Screener,
which is what `main.js` does. Demo script v7 (deliverable) either keeps
that or changes the default in one place, and the docs gate holds the
three in agreement from then on.

Two refinements the sweep forced on the gate itself. First, the JS scanner
is a recursive descent: the body of every `${...}` is code and is scanned
too, because nine of the prose strings in `views.js` sat inside ternaries
and nested templates that a flat scan skipped. Second, an interpolation
slot counts: the memo row label was an f-string joining the row number
and the factor label with a dash, which has no letters in its constant
part but renders an em dash in every memo row, so a dash or semicolon
between two slots is a violation, while a lone glyph beside a sibling
element is not.

The census modules were the one place where a rewritten string also lives
in committed T1 data (`what`, `method_notes`, the name-hint note on all
3,599 entities and the constant halves of `detection_evidence` on 1,419).
The census build cannot run here, so `src/census/sync_notes.py` rewrites
exactly those documentation fields from the module constants (it imports
them, it does not copy the text, and it refuses to write a file that does
not round-trip byte for byte), and `src/validate_census.py` now asserts
that the fields equal the constants. No count, CIK, date, form type or
class changed. `git diff --stat` on the two files equals the leaf count
exactly.

### 5.7 P0 exit: the gates enumerate the record, not a hand-typed subset
- `src/test_app.py` runs every product in the record across its five
  views and asserts the product picker offers exactly that set. It ran six
  products before, chosen by hand in 2026-08.
- `src/test_frontend.py` asserts that its two view lists together equal
  the views `site/js/main.js` registers, so a view cannot be added without
  entering the sweep.
- The two census-promoted products (`cion_ares`, `ocic`) carried integer
  CIKs while the other fourteen carried digit strings. The Streamlit roster
  table logged an Arrow conversion failure on every render because of the
  mixed column (visible in the gate output, asserted by nothing). Both files
  now carry strings, `promote.py` writes strings, and `validate_product`
  requires a digit string.
- P0 exit criteria met on 2026-09-04: fifteen gates green through the hook,
  the frontend sweep parses every rendered page with zero stray markup,
  `undefined` or `NaN`, zero product-count "six" strings in `site/`,
  `app.py` and `data/`, and every surface change in P0 logged in the
  corrections log. `docs/BUILD_REPORT_6.md` carries the assertion counts.

## 6. P1 decisions (appended as the work lands)

### 6.1 P1-1: a comparison window is the intersection, anchored once
The rule, in `tark_benchmark.comparison_stats` and mirrored in the lab
(`site/js/analytics.js`, `views.js`): the fund's window is clipped to the
proxy's coverage on both sides for a daily series, and to whole fiscal
years inside the coverage for an annual return list. `_level_on` now
refuses a date before its series starts instead of silently returning the
first observation, and the fund growth, the index growth and the PME flows
all read the level on or before each window date from the full series, so
a window that starts on a Saturday or a holiday cannot shift the anchor.
The card, the lab, the memo and the Streamlit view print the effective
window and the clip note.

A single disclosed annualized figure (kkr_kpec's ITD return, stepstone's
five-year figure) cannot be clipped. Interpolating it over a shorter
window would assume a constant-rate path the filing never disclosed, so
outside coverage the slot keeps its score and carries "comparison not
computable on held data" with the reason and the fix. No product hits
that case today (both windows lie inside coverage). It is asserted on a
synthetic profile.

What moved, KS-PME v1 to v2 (Direct Alpha moved with it, all twelve
fields in the corrections log):

| product | v1 | v2 | why |
|---|---:|---:|---|
| amg_pantheon | 2.4551 | 1.5919 | ten fiscal years from 2016 against a proxy that begins 2018-07-18: the seven whole years FY2020 to FY2026 remain (hand product 2.3970 over PSP 1.5058) |
| pflex | 1.2639 | 1.1089 | daily series from 2017-02-23 clipped to 2018-07-18, and to the proxy's last date 2026-07-17 |
| cion_ares | 1.2376 | 1.1374 | daily series from 2017-07-11 clipped the same way at both ends |
| arkvx | 1.9927 | 1.8974 | inside coverage at the start, but the fund series runs to 2026-08-13 while PSP ends 2026-07-17: v1 compared fund growth through August with an index that stopped in July |
| ocic | 1.1520 | 1.1541 | window starts 2021-01-01, a holiday: anchor moved from the first trading day after to the level on or before |
| breit | 0.9073 | 0.9064 | window starts 2022-12-31, a Saturday: same anchor correction |

Unchanged: cliffwater_cclfx, hl_paf, stepstone_spm, kkr_kpec, sreit,
bcred, ares_pmf (windows inside coverage, trading-day starts). The
two-point identity KS-PME = fund growth / index growth now holds on every
committed comparison and is asserted.

Two facts about the held data, not the engine, sit behind the largest
moves. Every proxy series begins 2018-07-18 and ends 2026-07-17 because
`src/fetch_series.py` pulled eight years as of that day, while three fund
series were fetched later and run into August 2026. Refetching the five
proxies from 2014 on a machine with network restores amg_pantheon's full
ten years and the August tails, and the gates will recompute and relog
the numbers. Until then the clip note says so on the card.

### 6.2 P1-2: one clock for every annualized figure
`fund_ann_pct` and `index_ann_pct` in a comparison are annualized over the
actual/365.25 day count of the effective window, the clock Direct Alpha
and the JS lab already used. v1 divided by the difference of the calendar
years in the window's end dates, so a window of 7.116 years annualized as
7 and a window of 3.877 years as 4. A disclosed annualized figure keeps
its disclosed span: kkr_kpec prints 12.94% and stepstone_spm 12.92%, the
numbers in cell 1.2, and the index side is annualized over the same span.

The plan's provisional pins (pflex 6.29%, cclfx 7.89%, arkvx 31.10%) were
computed at orientation on the unclipped windows. On the effective windows
P1-1 established, the gate pins cclfx 7.89% (window unchanged), pflex 5.74%
(2018-07-18 to 2026-07-17) and arkvx 30.12% (2022-08-31 to 2026-07-17),
each checked by hand against growth ** (1 / years) - 1, and asserts the
identity on every committed comparison.

Found while logging: the corrections collector listed `data/benchmarks`
recursively, so from the moment the v1 snapshot landed the frozen files
shadowed the live ones (same product key, later path) and the log saw no
selection change at all. P1-1's twelve facts rows were logged, its
selection rows were not. The listing is now direct children only, the
tool gained `--head` so a past commit's state can be logged under its own
task, and the P1-1 selection rows are backfilled under the P1-1 cause with
that note. The gate `check` still compares the working tree with
`origin/main`, so nothing published can now change without a row.

### 6.3 P1-3: the flows are stated, and a second schedule is labeled
Every comparison is two-point: one contribution at the window start, one
valuation at the end. The card, the memo and the methodology now say so,
and say that Direct Alpha is the annualized form of the same two flows
rather than a second piece of evidence. For the four daily NAV products a
second row, `ks_pme_monthly_schedule`, contributes one unit of cash at the
window start and at each fund month-end inside the window, each buying
`1 / NAV` units, valued once at the end. It is labeled ILLUSTRATIVE on the
card, in the lab, in the memo and in the methodology, the contribution
count is printed beside it, and the two-point figure stays primary in the
rubric. Annual-tier products get no such row because no intra-year NAV
path is on record, and the lab prints "n/a on annual data" for them
rather than leaving the cell blank. The lab computes the schedule with
the same code path and the frontend gate asserts parity with the
artifact. `docs/benchmark_methodology.md` starts here with sections 1 to
3 (windows, annualization, flows) and joins the copy gate's owned
documents. The rubric sections follow in the P1-B preparation.

### 6.4 P1-4: one label per series, from the manifest
`series_sources` is back in the bundle, this time with its readers: every
chart that draws a held series prints the label from that map ("Yahoo
adjusted close (approximates NAV total return)" for a fund or proxy class
ticker, "Yahoo daily close (market price)" for an exchange-traded price)
in the lab legend, the evaluation mini-chart, the De-smoothing Lab's basis
line and the lab's workbench tables. The map is built from
`data/series/series_manifest.json` and nothing in the JS types a series
label any more.

`src/run_analytics.py` kept three things the site never read and the
record already held elsewhere: a since-inception return and standard
deviation for CCLFX typed into the script (9.34% and 1.71%, which live in
cells 1.2 and 4.8), the HL PAF fiscal-year returns and NAVs typed as
literals (held in `data/series_annual/hl_paf.csv`), and a DXYZ price block
superseded by the supplement's premium series. It now writes only the
CCLFX monthly de-smoothing diagnostic the lab prints, from the held
series, and runs inside `produce.py` under the freshness gate. Cells 1.6
and 1.7 (computed, not yet owned by the cell writer) still carry the
earlier "TR-gap vs disclosed" sentence. They join the writer's owned set
with the memo work (P1-D) and are regenerated from this artifact then.

### 6.5 P1-B preparation: the outcome is committed before the code
`docs/benchmark_methodology.md` sections 4 to 10 now hold the typed
descriptors per product and candidate (each with the cell it comes from),
the strategy matrix and gate, the v2 rubric, the lanes, the tie-breaks,
the expected v1 to v2 outcome for all sixteen products and the rule
mapping as basis strings. The gate reads the v1 columns from the frozen
snapshot and fails on drift. The v2 columns are the prediction. Design
calls the table forced, each reversible by Oscar:

- A computable cohort composite can be primary. The rule's own fallback
  is "the history of a similar type of investment", and v1's structure,
  where any unaffiliated daily ETF cleared the threshold and outscored an
  exact-strategy comparison, is what the audit called the opposite of a
  meaningful benchmark. Under v2 the leave-one-out composite wins private
  credit and evergreen PE (10 against BKLN's or PSP's 9), the ETF becomes
  the secondary, and the card shows both.
- Listed private equity (PSP) is strategy 1 for venture, not 2: buyout
  managers and listed PE vehicles are not venture, so arkvx escalates
  computably instead of carrying PSP 8. That is what the plan expected.
- `investability` means computable on held data. A composite built from
  filings is computable. A licensed or cited index is not, whatever its
  fit, and it says so.
- `risk_liquidity_match` 3 is reachable in the rubric and unreached on
  held data, because every cohort mixes leverage regimes. The card prints
  the ceiling per product rather than hiding it.
- ODCE stays a cited secondary for the non-traded REITs at 7 (v1 gave it
  8 with a data_quality point for data it does not hold).
- Lane D is removed. A PME against a proxy is that proxy's comparison.
- `src/fetch_authority.py` verifies the citation and the RIN, extracts
  paragraphs (g) to (l) of proposed 2550.404a-6 verbatim from the Federal
  Register XML, and writes nothing if any paragraph cannot be located.
  It cannot run here (federalregister.gov is blocked). Until it has run on
  a machine with network, no surface quotes the rule and every rule
  reference carries the basis string.

### 6.6 P1-5 to P1-12: rubric v2 landed as one change, and reproduced the table
The eight rubric tasks landed in one commit. Each intermediate state (a
gate on hand-typed integers, a 12-point scale on the old menus, Lane A
without Lane C) would have regenerated and published selection numbers
the methodology had already called wrong, and every one of them would
have needed its own corrections rows and its own memo regeneration. One
engine, one regeneration, one set of rows. Every criterion is still
asserted on its own in the gate (synthetic descriptors move one input and
one criterion moves).

The engine reproduced the expected outcome table in
`docs/benchmark_methodology.md` section 9 row for row, including the max
attainable column, and the gate now asserts both against the live
artifacts. What the surfaces show that they did not before:

- Nine products now carry a Lane C composite as primary with a real
  comparison. KS-PME against the leave-one-out peer composite: cclfx
  0.9756, pflex 0.9799, cion_ares 0.9461, bcred 1.0798, ocic 0.9973,
  hl_paf 1.0693, stepstone_spm 1.0206, ares_pmf 1.0822, amg_pantheon
  0.8357. The ETF comparison each product carried before is unchanged and
  sits in the secondary slot. The Fee Matrix and screener PME columns read
  the primary, so they now show the peer figure.
- The composite comparison is fiscal-year aligned by year label. cclfx
  changed its fiscal year-end from December to March in 2022, so its
  three-month stub is excluded and the composite's 2022 year is skipped
  and named on the card. Members' fiscal year-end months are printed.
- kkr_kpec keeps PSP as primary: its held figure spans 2023-09 to 2025-12,
  so the composite overlaps two fiscal years and earns data_quality 0.
- arkvx escalates computably. The ledger shows SPY and PSP at 8 failing
  the strategy gate and the venture composite refused.
- Declared benchmarks are on every card with their fate: hl_paf's S&P 500
  and MSCI World, stepstone's, ares_pmf's and amg_pantheon's MSCI World
  all fail the gate at strategy 1. cion_ares's CSLLI is cited and below
  the threshold. jll_ipt's NFI-ODCE waits for P1-13. dxyz's NASDAQ
  Composite sits in the ledger under the price-decoupling flag.
- CDLI is adviser-owned for cliffwater_cclfx only (independence 0) and an
  independent cited candidate at 7 for bcred and ocic.

`data/registry.json` is new: the typed descriptors with the cell each
comes from, checked by the gate against the record (every adviser key and
declared benchmark name is a substring of the product's own text). The
two return inputs that lived in engine code (hl_paf's fiscal-year returns,
stepstone_spm's five-year figure) moved into `profiles_input.json` with
their provenance. `PRODUCT_PROFILES` and the menus are assembled from
data at import. P2-1 merges the remaining duplicate registries into this
file.

### 6.7 P1-13: a product with no return series still gets a selection
jll_ipt prints no multi-year per-class return series (the FY2025 10-K
gives a 3.0% to 3.8% range across classes and an eight-quarter NAV path
without distributions, cells 1.1 and 1.2), so no comparison can be
computed without inventing one. The engine now runs for it anyway:
candidates are scored on their own descriptors (VNQ 9/12, the declared
NFI-ODCE 7/12 as Lane A secondary), and each slot carries the reason the
comparison is absent, on the card, in the memo and in the facts mirror.
An unlisted NAV REIT's declared benchmark selected on its merits and a
listed-REIT proxy in the primary slot is exactly the state the audit
asked to see stated rather than hidden behind a missing artifact.

The five pending facts resolve without a new number: benchmark id and
score are computed, PME and Direct Alpha are null with the reason, and
the liquidity verdicts come from the match files, which always existed.
`build_facts` had tied the liquidity fact to the presence of a benchmark
selection. It now reads the match files on their own.

### 6.8 P1-14: a short window says so wherever the number appears
Every comparison shorter than three years carries "low confidence:
N-year window, shorter than 3 years" beside the window on the card and as
a sentence in the memo. Today that is sreit (one calendar year, the only
annual return the filings print) and kkr_kpec (2.33 years since class
inception, and two fiscal years against its cohort). The threshold is a
constant in the engine, not a judgment made per product, and the gate
asserts both the labeled and the unlabeled cases.

### 6.9 P1-15: the lab grades any choice with the real scorer
The Analysis Lab's "engine's judgment of your choice" was a lookup that
answered "off the engine's menu, no rubric basis" for any proxy not on
the strategy's menu. Rubric v2 scores from descriptors, so every product
and proxy pair is scored by the same `score_candidate` at build time,
and the panel now prints the score, each criterion's reason, whether the
pair would be eligible (passes the strategy gate and the 7/12 threshold)
and whether the proxy sits on the engine's menu for that product. The
lab covers every product with a return input (fifteen). jll_ipt keeps the
empty state that names it, because there is nothing to recompute.

### 6.10 P1-16 and P1-17: two liquidity layers, both from the record
The liquidity match now has two verdicts that never blur. The structural
verdict reads typed facts only (cells 3.1, 3.3, 2.7 and the registry's
pricing class) and is the same under every plan: exchange-listed is
aligned-mechanical, a suspended program or a 0% cap is misaligned, a
gating history is conditional-weak, a required fact left null is partial
(suspension wins over a null), and everything else is conditional. The
scenario verdict is ILLUSTRATIVE and per plan: base demand above the
typed annual capacity is misaligned, stressed demand above it is
conditional-weak, otherwise conditional. The proration assumption is
printed beside it and the lab recomputes it live with the sliders. The
screener's liquidity column and filter read the structural fact. The
hand-typed `LIQUIDITY_PROFILES` dict is gone, and both tasks landed in one
commit because the v2 ladder cannot run on the old inputs.

What the typed layer changed, honestly:

- Four products are structurally partial, not conditional: the record
  does not establish whether cliffwater_cclfx, hl_paf, ocic or
  stepstone_spm has ever prorated. Cell 3.3 holds offer notifications, an
  unbroken offer record, or the filing's own statement that shares
  tendered are not disclosed. The old profile typed `gate_history: False`
  for all four without that evidence. The card names the missing fact and
  its reason.
- sreit is misaligned, not conditional-weak. Cell 3.1 carries the April
  29, 2026 closure ("no repurchase requests will be accepted" except death,
  disability and sub-$5,000 accounts), so `repurchase_program_status` is
  typed `suspended`, the cap is 0% and capacity is 0% under every plan.
  No other product carries a status: the field is null with "no
  suspension language in 3.1 or 3.3 as of <as-of>", never "active".
- ares_pmf's cap is typed 5% of net assets from cell 3.1's own words
  ("no more than 5% of the Fund's NET ASSETS"), where the facts layer had
  a null and the old profile a hand-typed 5.
- No capacity text says a position is "far inside" a cap. A closed
  program says its capacity is 0% until it reopens.

`src/test_liquidity.py` is the sixteenth gate: the ladders on synthetic
facts, sreit misaligned under all four plans, the structural verdict
plan-independent, the scenario verdict plan-dependent for at least one
product, every committed match equal to a fresh run, and the JS port in
parity (the frontend gate checks the scenario verdict on all 64 matches).
`produce.py` now runs the facts pass before the liquidity pass, because
the verdict reads the typed layer.

### 6.11 P1-18: the plan schema names what the demand model would rather read
Each reference plan now carries a `schedule_h` block with three records:
benefit payments (Schedule H line 2e), participant contributions (line
2a(1)(B)) and a QDIA indicator. All twelve values are null with the
reason: the DOL bulk file `F_SCH_H_2024_latest.csv` is not in the
repository and its host is blocked from the build container, and the
Form 5500 does not code a QDIA election at all (the plan document or the
404a-5 disclosure does). The validator requires the block, refuses a
null without a reason and a value without a source. The
`dictionary_cells` entries say how each feeds the model.

The match uses them when present, with the model named: a filed line 2e
prints the plan's outflow rate applied to the position as a "Schedule H
based" estimate beside the slider model, never blended with it,
contributions print as a plan-level inflow, and a typed QDIA adds the
sleeve sentence to the structural reasons. Until they are typed, every
non-exchange match says the figure is not in this build and that demand
uses the illustrative sliders only. Oscar fills the values from the bulk
file on the laptop, citing the row, and the gates will pick them up.

### 6.12 P1-D preparation: accessions resolved offline, never invented
`src/resolve_citations.py` reads every evidence row's `source_doc`, finds
the filing references in it (a form token and, usually, a filed date) and
resolves each against `data/manifest.csv` for the same product: exact
when form and filed date (or a written accession) match one held filing,
range or set when the citation names a run of filings of one form (every
held filing between the two dates, or every held filing of that form),
form-only when no date is written and exactly one filing of that form is
held (flagged as such), accession-in-text when the citation carries an
accession the manifest does not hold (the URL is the EDGAR archive
folder for that accession), otherwise ambiguous or unresolved with the
reason written out. A date after a workflow verb ("searched", "run on")
is a workflow date and never a filing date. It writes
`data/citations/<product>.json` and a summary, runs inside `produce.py`,
and the invariants gate checks that every resolved accession is that
product's manifest row with the manifest's own EDGAR URL. The memo work
(P1-22) prints these accessions and URLs, and says "accession not on
record" where the resolver could not. The online half, EDGAR submissions
JSON for filings the manifest does not hold, runs where sec.gov is
reachable (P2-10), together with the laptop-path purge.

### 6.13 P1-19: memos are build output, one per plan and product
`tark_memo.build_memo(key, plan_key)` writes
`<plan>__<product>_decision_memo.docx`, and `src/build_site.py` generates
all of them (4 plans x 16 products) into `site/memos/` on every build, so a
memo can never be stale against the record and `data/memos/` is gone from
the repository. The memo carries its own plan's label and that plan's
product-to-plan liquidity match (structural verdict and ILLUSTRATIVE
scenario verdict). Every memo link on the site and the pin hash follow the
selected plan. The docx bytes are deterministic (fixed zip timestamps), so
the same record yields the same file. `test_memo` runs the writer into a
scratch directory rather than reading committed files.

### 6.14 P1-20: the findings table is complete, not a 220-character cut
Per factor the memo now lists the typed facts the engines read (each with
its cell id), then the complete first sentence of every evidenced cell
with its status word, then the cells marked not applicable with their
reasons, one paragraph per line. Nothing is truncated and no cell ends
mid-word. The headline logic moved from the site build into
`src/tark_display.py`, shared by the build and the memo writer, so the
site's Evaluation headline and the memo's typed-fact line come from the
same function. `test_memo` asserts, for all 16 products, that every
evidenced cell's full first sentence and every typed headline appear in
the memo verbatim.

### 6.15 P1-21: memo sections, and what "red flags" means here
The memo gains four sections. Product-to-plan liquidity match: the
structural verdict with its reasons, the wrapper facts in a table with
their cells (null facts print their reason), then the ILLUSTRATIVE
scenario with the plan's Form 5500 inputs, the adjustable parameters, base
and stressed demand against wrapper capacity, the scenario verdict and
the citations. Recommendation: both verdicts, the benchmark state
(selected or escalated), then "flags raised by the record". No red-flag
layer exists in the record and none is invented: a flag is a restatement
of a typed value or a verdict already in the artifacts (benchmark
escalation, no eligible secondary, low-confidence window, program
suspended, gating precedent, missing structural facts, an ILLUSTRATIVE
scenario verdict of misaligned or conditional-weak, Schedule K-1), each
with its source. The memo says it does not decide and lists the
committee-completed cells. Scope: selection record as of the record
date, not monitoring, verbatim regulatory text present or not. Case law:
cell 5.7 only, which is n/a for every product until P1-23. The unsourced
"argument expected October Term 2026" sentence left the regulatory
paragraph with this change.

### 6.16 P1-22: provenance says what the record holds
The memo's provenance paragraph reads the record's one coverage formula
(`coverage_summary`) for every status kind, then counts live how many
evidenced cells carry a source, a section, a verbatim quote and an
extractor, and writes "Verified cells have been independently re-checked
by a person" only when the verified count is above zero. Until then it
says no cell is verified and verified_by is empty on every row. The
former "every populated cell carries its source document, section,
quote, extractor and verifier" was false on two counts (computed cells
carry no quote, no cell has a verifier) and is gone. A "Sources cited"
table lists every evidenced cell's source as written with the accession
and EDGAR URL from the offline resolver (6.12), or "accession not on
record" with the reason.

### 6.17 P1-23: cells 5.6 and 5.7 hold what the record supports
Cell 5.6 (benchmark suitability) is now an owned computed cell written by
`src/write_computed_cells.py` from the selection artifact: primary and
secondary with scores, the comparison figures or why none is computable,
the escalation, the maximum attainable on held data, the fund-declared
benchmarks with their status, the rejected count. The product-side
fragments in the former placeholder prose (arkvx, pflex, amg_pantheon)
survive as analyst notes in `data/notes/`. Cell 5.7 (case-law tracker) is
one `partial` row on all sixteen products, written by
`src/seed_case_law_cell.py`: Anderson v. Intel, No. 25-498, certiorari
granted 2026-01-16 per the docket listing, the question presented and the
argument term as relayed by search snippets accessed 2026-09-04, no
holding, no consequence drawn. The quote column is labeled a search
snippet, the extractor names the snippet source, and the status says the
source documents were not fetched. It is never `extracted`: a person with
access to supremecourt.gov replaces the snippet with the document quote.
The validator now rejects any partial cell that has a value but no source
or no extractor (the existing 59 partial rows already satisfy it).
The two cells added about 32 KB to every product and pushed the first-paint
bundle past its 1.2 MB budget. The budget stays. The citation-drawer detail
of every cell (source, section, quote, extractor, about 210 KB across the
record) now rides in the lazy chunk as `TARK_EVIDENCE` and is merged into
the products on load. First paint keeps element, value, status and
verifier. The views that open the drawer or search quotes (evaluation,
cohorts, search, packet, verification, fees) wait for the chunk like the
chart views already did. The screener, compare, plans, roster and
benchmark views still paint from the core bundle.

### 6.18 P1-24: a caveat fires only when the members' own values differ
`tark_cohort.member_values` reads one comparability attribute per member
from the typed registry when every member has it typed, and from the
wrapper-type matrix only otherwise, never mixing the two vocabularies.
The pricing rule compares `pricing_class` (NAV or MARKET), not the
pricing-basis caption. Result: the evergreen PE cohort loses the
pricing-basis caveat that contradicted five NAV-priced members and the
NAV-cadence caveat that five monthly-NAV members did not support, and
keeps the leverage-regime and liquidity-law caveats its members do
support. The composite refusal reads the same typed pricing class. The
Compare view applies the identical rule from the shipped per-product
descriptors. The leverage-regime vocabulary is normalized to four values
across the registry and the matrix, and the caveat prose carries no
semicolon. `test_cohort` asserts, for every committed cohort, that each
caveat is written exactly when the typed values differ.

### 6.19 P1-D2: the engine restates itself, nothing else does
Cells 1.8, 1.9, 3.8, 3.9, 5.3 and 5.5 were engine restatements dated
2026-08-09 that no committed script wrote, and by the memo sweep they
contradicted the record: cell 1.8 named BKLN as cclfx's primary where the
v2 selection names the peer composite, cell 3.9 said CONDITIONAL for the
reference plan where the record says PARTIAL, cell 5.5 described v1
windows. `src/write_computed_cells.py` now owns all six and writes them
from the v2 selection, the supplement's stress windows and the four plan
match files: 1.8 states the primary comparison (and the secondary, the
ILLUSTRATIVE schedule row and the low-confidence label where present),
1.9 the stress windows or the fiscal-year stress observation with its
caveat, 3.8 the ILLUSTRATIVE stress test per reference plan, 3.9 the
structural verdict with missing facts and the scenario verdict per plan,
5.3 every candidate with its outcome, 5.5 the PME inputs as the formula
(KS-PME = fund growth / benchmark growth). The writer regenerates these
six only where the cell is already computed, so no n/a or evidence row
changes kind and the coverage totals stand. hl_paf's window judgment
survives as an analyst note. 89 changed cells are logged. Two invariants
pin cell 1.8's KS-PME and cell 3.9's opening verdict to their artifacts.

### 6.20 P1-26: the rule is cited and mapped, never paraphrased
`tark_data.RULE` is the one record of the regulation's identifiers (title,
issuer, citation, RIN, section, Federal Register document and URL, docket
and URL), all recorded with their sources in section 0. The site caption,
the memo and the Streamlit app read it instead of three string constants.
`rule_ref(cid)` gives every cell its paragraph letter ((g) to (l) by factor,
per the 2026-09-03 audit's check of the text) and a basis string that
states whether verbatim text is in the build. `authority()` parses
`data/authority/*_proposed.md` when `src/fetch_authority.py` has written
it and otherwise reports "not fetched" with the command to run. The
authority panel shows the identifiers with links, the scope sentence
(selection, not monitoring), the six factors with their letters and
either the verbatim paragraphs or the not-fetched state. The Evaluation
view shows the paragraph and basis per factor and marks cells 6.6 and
6.8 advisor-completed under paragraph (l). The memo's two paragraphs
that paraphrased the safe harbor and the benchmark requirement are gone,
replaced by statements about the memo itself, and a verbatim appendix
renders when the authority file exists. Deviation from the plan's
letter: `CELLS` keeps its id-to-title shape and `rule_ref` is a function
beside it, because five modules index `CELLS[cid]` as a title.

### 6.21 P1 exit record (2026-09-04)
Commits 9527c0e to f3b35e2 on the working branch, 22 task-tagged commits
from the P1-B snapshot freeze to P1-26, every one committed through the
16-gate hook. Full hook at exit: 750 assertions, 0 failures, 73 s. Per
gate, run alone: validate_data 22, validate_census 1, evidence
immutability 482 protected rows unchanged or allowlisted, corrections log
complete, invariants 15, copy 33, docs 27, analytics 35, cohort 27,
benchmark 164, liquidity 29, memo 36 (64 memos), app 196, artifacts fresh
9 groups, frontend 188. First paint 1,032,562 bytes (budget 1,200,000),
lazy chunk 1,077,092 bytes, census chunk 302,512 bytes, 64 memos 3.1 MB
generated by the build. Record totals: extracted 406, n/a 205, computed
161, partial 75, fetched 16, structured 1, verified 0, pending 0.
Deferred to P2 or a networked machine, each already logged: laptop paths
and the online accession half (P2-10), the regulatory text fetch
(fetch_authority.py), proxy series refetch from 2014, Schedule H lines
from the DOL bulk file.

### 6.22 P2-1: one product registry
`data/registry.json` now also carries, per product, the as-of date and the
cohort depth and membership rationale (moved from `build_facts.py`), the
document sets to fetch (moved from `fetch_edgar.py`, which hand-listed 14
of 16 products, cion_ares and ocic derived from the filings held in the
manifest), and the return inputs (moved from `profiles_input.json`, now
deleted, the v1 snapshot keeps its frozen copy), plus a `cohorts` block
with label, ordered members and fallback note. The cohort engine builds
its membership table from the registry, the facts builder reads its
dates and cohort metadata from it, the EDGAR fetcher builds its table
from the registry and `data/products`, and the benchmark engine reads
return inputs from it. `validate_registry` (in the validate gate) refuses
a registry whose product set differs from `data/products`, a product
with a typed field missing or unsourced, a wrapper outside the
vocabulary, a member whose own cohort field disagrees with the cohort
list, or a cohort with no member. The site reads the wrapper and
fee-base vocabularies from the bundle, the same maps the memo uses,
instead of two JavaScript copies. The census class taxonomy is a
different enumeration and stays in `census.js`. Moved prose lost its
semicolons. The promote checklist names the registry entry.

### 6.23 P2-2: ingestion with a per-cell contract, tested offline
`src/ingest.py <cik> --key <key>` runs in stages a test can drive one by
one: registry check (the cohort, strategy and wrapper are a person's
judgments, so the registry entry comes first), scaffold through the
promote helpers, fetch through the EDGAR fetcher, filing text with page
anchors (split on the filings' own page-break styles), one structured
call per extractable cell with the held filings as a cached prefix, and
the contract: the returned quote must appear verbatim (whitespace and
quote marks normalized) in the cited document. Located: status
extracted-unverified with the page in the source string. Not located, or
a document not on record: status partial with the reason and the value
kept for a person. Not found: the cell stays pending and the reason goes
to `data/ingest/<key>_report.json`. Engine-owned, advisor-completed and
census-prefilled cells are not in the contract, and an extracted,
verified or structured cell is never overwritten. The extractor string
names the script, the model and the date. Model `claude-opus-5` by
default (the Anthropic API skill's default), `TARK_INGEST_MODEL`
overrides, the key comes from the environment. A refusal is recorded as
not found, not rerouted to another model. The source string is written
as "FORM filed DATE (accession N)" so the offline resolver reads it. The
gate `test_ingest.py` (17th, before the memo gate) drives all of it with
a mock client and a synthetic three-page filing, including a deliberate
wrong figure that must land as partial. No live extraction ran here: no
key, no filings on disk, EDGAR blocked (P2-3 and P2-4).

### 6.24 P2-3 and P2-4: calibration and the 17th product cannot run here
Neither run is possible in this container: no Anthropic key, no filing text
on disk (`data/raw/` is not in git) and sec.gov is blocked. Nothing was
faked. What exists: `src/calibrate_ingest.py` runs the extraction
contract on an already-evaluated product in a scratch copy with the
target cells reset to pending, then compares each outcome with the
committed cell (quote located, same form and filing date cited, share of
the committed cell's figures reproduced, status) and writes
`data/ingest/calibration_<key>.json`. Its comparison arithmetic is
covered by the offline ingest gate. The 17th product, ACAP Strategic
Fund (XCAPX), CIK 1467631, is in the census as an unlisted Rule 23c-3
interval fund with promotion status none and an N-CEN reference
0001193125-25-317592 as of 30-SEP-2025, so the promote step will accept
it. On a machine that reaches sec.gov, with a key in the environment:

```
python src/promote.py 1467631 --key acap_strategic
# write the data/registry.json entry for acap_strategic (cohort, strategy,
# wrapper_type, pricing_class, nav_cadence, leverage_regime, held_returns,
# advisers, declared_benchmarks, as_of, depth, membership_rationale,
# filings, each with its source) and add it to that cohort's members list,
# then an admission entry in data/roster_decisions.md
python src/fetch_edgar.py acap_strategic
python src/ingest.py 1467631 --key acap_strategic --skip-fetch
python src/calibrate_ingest.py cliffwater_cclfx
python src/produce.py && python src/build_site.py && bash hooks/pre-commit
```

The validate gate refuses a product in `data/products` without a registry
entry, so a half-added product cannot pass. No cost or time estimate is
given for either run.

### 6.25 P2-5: evaluate this fund, with nothing pretended
The census entity card for an unevaluated fund now shows the exact ingest
command for that CIK with a suggested product key and a copy button, and
says that the registry entry comes first. When a service URL was given
at build time (`TARK_SERVICE_URL`), an "Evaluate this fund" button posts
to `POST /evaluate` and prints the service's answer as returned. Without
one the card says no service is connected and shows no button. The
service (`service/app.py`, FastAPI, one route, no docs pages) runs the
ingest synchronously and answers refused (reason and commands), completed
or failed (exit code, output tail, report path), or timed out. There is
no queue, no job id and no progress state: the service reports only what
happened. The offline ingest gate drives it with the test client:
outside-census, no-registry, already-evaluated and malformed-key
refusals, one route, no job fields. The frontend gate opens an
unevaluated entity and checks the command and the honest no-service
state. fastapi, uvicorn and httpx join the requirements.

### 6.26 P2-6: advisor-stated cells are inputs, not evidence
The six committee cells (6.6, 6.8, 3.7, 2.8, 3.5, 4.9) can be stated by
the adopting fiduciary for its own plan in
`data/advisor/<plan>__<product>.json`, each entry with a value, a signer
and an ISO date and the status prefix `advisor-stated`. `validate_advisor`
(in the validate gate) refuses an unknown plan or product, any other
cell, a missing value or signer, a non-ISO date, and `validate_product`
refuses the status inside an evidence cell: an advisor statement never
enters `data/evidence/` and the record's cell stays as it is. The
Evaluation view shows a stated cell with its own badge, signer, date and
the not-evidence sentence, and otherwise a form that emits the exact
file to save (a static site writes nothing), refusing to produce
anything without value, signer and date. The header counts stated cells
for the selected plan. The memo gains an "Advisor-stated inputs (this
plan)" section and marks each committee cell stated or open in the
recommendation. No advisor file is committed: inventing a signer would
be fabrication. The offline gates exercise the validator, the
not-evidence rule, the form and the memo section.

### 6.27 P2-7: verification is a person signing, and only that
`src/verify_cell.py <product> <cell> --signer "Name, role" --date
YYYY-MM-DD` is the one path that writes a verified status. It refuses an
empty signer, a signer that names a script, model or agent, a non-ISO
date, any cell that is not extracted-unverified, and any cell without a
source and a verbatim quote. It changes only the status and verified_by
(the value, source, section and quote stay as they were), writes the
product JSON and the evidence CSV together, and allowlists the two
columns in the corrections log with the signer as the reason.
`--dry-run` prints the signed row and writes nothing. The Verification
view shows, under every queue row in the document's order, the recorded
value beside the verbatim quote with its source, and a signer-and-date
form that emits that exact command, refusing to emit anything without
both. The site writes nothing, and the service stays one endpoint. The
tests exercise every refusal and the dry run in a scratch copy and
assert that no verified row exists afterwards: no test, producer or
build ever writes verified, and the record's verified count stays 0
until a person runs the command.

### 6.28 P2-8: a plan enters the record anonymized or not at all
`src/plan_intake.py <intake.json>` writes `data/plans/<plan_key>.json`
from the plan's own Form 5500 and Schedule H primitives. The
anonymization label is required and must equal the display label, and a
label that looks like a sponsor name or an EIN is refused (the CLI and
the Plans view share the same pattern). No identity block is stored for
an intake plan, `validate_plan` accepts `identity_private` absent when
`anonymization_label` is present and equal to the label, and now
requires the pension benefit codes the liquidity engine reads for plan
direction. Derived figures are recomputed from the primitives and never
taken from the form. Schedule H lines left empty are null with a reason.
The Plans view carries an "Add your plan" form that emits the intake
file and refuses to emit anything without the label, the confirmation,
the required figures and the codes. The new plan gets its liquidity
matches and memos for every product on the next producer run and build,
with no code change. Tests: the CLI's refusals and its recomputation in a
scratch copy, the form's refusals and its output in the browser.

### 6.29 P2-9: the committee packet is build output too
`src/tark_packet.py` writes one committee packet per plan and product
into `site/memos/` on every build, next to the memo: a summary (both
liquidity verdicts, the benchmark state, the flags the record raises,
coverage and the verified count, advisor-stated inputs for the plan, and
that the committee decides), Exhibit A the benchmark selection with its
rejection ledger, Exhibit B the liquidity match for this plan (the
memo's own section), Exhibit C the typed fee row, Exhibit D the cohort
placement with its caveats, then the advisor inputs and a provenance
page. Every figure comes from the artifacts the site and the memo read.
The Packet view links the packet for the selected plan and product, and
its print button prints the pinned exhibits only (a body class for the
print stylesheet while the dialog is open). Bytes are deterministic.
The memo gate checks all 64 packets, the frontend gate checks that all
are served, that the link follows the plan and that printing scopes to
the pins.

### 6.30 P2-10: the ledger names its filings and nothing on a laptop
The evidence CSVs gain an `accession` column, filled by
`src/purge_paths.py` from the offline resolver: the one resolved
accession, "multiple (N), data/citations/<key>.json" for a set or a
range, or empty when no filing reference resolves. The resolver now also
reads "all on-disk filings" as the set of every filing held for the
product. Every `local_file` that pointed at a laptop path is the
manifest's own local path when exactly one filing resolves and empty
otherwise, and the series manifest notes lost their laptop paths. The
validate gate now refuses a raw-filing citation the manifest does not
cover (a warning until now), an accession that is neither a manifest row
for the product nor written in the citation, and any laptop path in the
ledger, and the invariants gate refuses a laptop path anywhere under
`data/`. The citation drawer shows the resolved EDGAR filings as links
(the manifest URL) or says the accession is not on record. Hundreds of
protected rows changed in two columns, so the evidence allowlist accepts
wildcard rows (`* * local_file`, `* * accession`) that carry a reason,
and the immutability gate prints how many changed cells each covered.
The online half (EDGAR submissions JSON for filings the manifest does
not hold) still needs a machine that reaches sec.gov. No extracted row
changed status: the three "all on-disk filings" citations moved from
unresolved to a set, and the two ambiguous breit references stay
ambiguous with their candidates listed.

### 6.31 P2-11: listing is about a share class, and an old interval fund is a listed CEF
The submissions oracle says whether some class of an entity trades on an
exchange, which is not the same as the common shares being listed, and
four funds the census classed as interval funds (MXF, IFN, CCIF, DMA)
stopped filing N-23C3A between 2009 and 2021 while their shares trade on
the NYSE. `src/census/reclassify_listed.py`, applied to both census
files and called by the census build on a rebuild, gives every record
`listed_common` and `listed_other_classes` (the latter null: the census
does not enumerate share classes), reclassifies an exchange-listed
interval record whose last N-23C3A is more than 24 months before the
census as-of to listed_cef with the rule and dates appended to its
evidence (reversible on a fresh N-23C3A), and leaves the two exchange-
listed interval funds that still file N-23C3A (CIK 1551047 and 1644771)
with listing null and the reason that offline the census cannot tell
which class is listed. The enumeration keeps listing tri-state instead of
coercing to a boolean, the census validator requires the two fields,
refuses an interval record with listed True, and recomputes the class
counts from the entities in both files. The screener's Listed column
and flag read the common-share field, the entity view shows the raw
signal with its reason when it is null, and promote never prefills
cell 1.10 on a null. Counts moved: interval_23c3 245 to 241, listed_cef
213 to 217, and the runbook and script say the new numbers.

### 6.32 P3 plan (plan only, no P3 code in this engagement)
P3 code lands only when P0 through P2 are green in full. P2-3
(calibration) and P2-4 (the 17th product) cannot run in this container
(no key, no filing text, sec.gov blocked, decision 6.24), so P2 is not
green here and P3 stays a plan. Order and acceptance, each item a
gated commit with a task id, none weakening a gate:

1. P3-2 CI first. `.github/workflows/gates.yml` on every push and pull
   request: Python 3.11, `pip install -r requirements.txt`, the
   preinstalled Chromium or `playwright install chromium`,
   `TARK_SEC_CONTACT` from a repository secret (the fetchers refuse to
   run without it and CI never fetches), then `bash hooks/pre-commit`
   as the one job. A second job deploys `site/` to `gh-pages` only from
   a green run on `main`, with `git push --force-with-lease` to that
   branch alone. Branch protection on `main` requires the gates job.
   Acceptance: a pull request with a failing gate cannot merge, and a
   green `main` publishes within the run. `docs/INVESTOR_DEMO.md`
   replaces its manual redeploy recipe with the workflow's name.
2. P3-3 anonymization at rest. The four reference plans keep their
   figures and lose `identity_private` from the public repository. The
   intake path from P2-8 already lets `validate_plan` accept a plan with
   an `anonymization_label` and no identity block, so each reference
   plan gains the label first. The sponsor tokens the build screens
   move to a private file named by `TARK_PRIVATE_PLANS`, read by
   `tark_anon.forbidden_tokens` when present, and held by CI as a
   secret. Fail closed: with no private source the build refuses to
   emit the bundle and the memos, because an unscreened surface is
   worse than no surface. Acceptance: `git grep` of any sponsor name,
   EIN or ack id over the repository returns nothing, the build with
   the private source screens as before, the build without it refuses.
3. P3-4 retire or thin `app.py`. After the static site has carried a
   demo end to end, the Streamlit app is reduced to a launcher that
   opens the static site, or removed. The `test_app.py` gate is
   replaced by a gate over whatever remains (a smoke check of the
   launcher), never deleted without replacement, and the gate count in
   the runbook moves with the hook. Acceptance: no surface number lives
   only in `app.py`.
4. P3-5 `make refresh` with per-layer as-of dates. `data/as_of.json`
   grows one date per layer (filings, price series, census, plans,
   authority text) written by the fetcher of that layer, `record_as_of`
   becomes the latest of them, and the freshness gate refuses a layer
   whose artifacts are newer than its own as-of. Targets: `make
   refresh-filings`, `refresh-series` (the proxies from 2014, decision
   on the truncated proxy history), `refresh-census`, `refresh-plans`
   (Schedule H lines from the DOL bulk file), `refresh-authority`
   (`fetch_authority.py`). Acceptance: each target is idempotent and
   every surface shows the layer's own date.
5. P3-1 the vehicle model. A `data/vehicles/` schema for the wrapper an
   adopting plan would actually hold (CIT sleeve, managed account, TDF
   sleeve), one worked example labeled ILLUSTRATIVE end to end, a memo
   and packet section that renders only when a vehicle file exists, and
   the liquidity structural verdict extended with the vehicle's own
   dealing terms. Acceptance: no vehicle number is presented as a fact,
   and the record's verdicts are unchanged when no vehicle is attached.

### 6.33 P2 exit record (2026-09-04)
Commits d4324eb to d716701, eleven task-tagged commits P2-1 to P2-11,
every one through the hook. Per gate, run alone: validate_data 26 (now
with registry, advisor, raw-path and accession checks), validate_census
1, evidence immutability 482 protected rows with two wildcard rows
covering 464 and 263 changed cells, corrections log complete, invariants
16, copy 39, docs 27, analytics 35, cohort 27, benchmark 164, liquidity
29, ingest 57 (new gate, offline), memo 39 (64 memos and 64 packets),
app 196, artifacts fresh 9 groups, frontend 213. First paint 1,035,536
bytes (budget 1,200,000), lazy chunk 1,247,495 bytes (the evidence
detail with EDGAR links rides there, total payload 2,283,031 against
the 2,400,000 cap), census chunk 303,113 bytes, 128 build-side
documents. Record totals unchanged since P1 exit. Not green here and
therefore P3 stays a plan: P2-3 and P2-4 (decision 6.24).

## 7. Round 2 (2026-09)

Specification: `docs/GAP_ANALYSIS_2026-09-05.md` (46 findings, every one
reproduced by the auditor on the live site, recomputed from `data/`, or
checked live against EDGAR and the Federal Register API). Where the round-2
brief and the audit disagree on a detail, the audit wins and the
discrepancy is written here. Entries 7.1 and 7.2 were decided by Oscar on
2026-09-05 and are not defaults. Entries 7.3 to 7.6 are defaults taken by
the engineer and reversible by Oscar. Later entries are appended as the
work lands, each with its task id.

### 7.1 Decided: benchmark architecture v3, Slot K and Slot G
Every card, memo and record carries two explicit comparisons that satisfy
different paragraphs of the rule and are named as such. Slot K, "Meaningful
benchmark (paragraph (k))": the fund's declared benchmark (Lane A),
exchange-traded strategy proxies (Lane B) and published strategy indices
(Lane P: CDLI, NFI-ODCE, Cambridge, Burgiss, LSTA, Credit Suisse Leveraged
Loan). A candidate with a public market price series gets a PME. A
candidate with an appraisal-based published series gets a relative wealth
ratio and an excess return on calendar-quarter aligned periods. A candidate
that is cited but not held gets no number and says so. Slot G, "Peer
comparison (paragraphs (g) and (h))": the cohort, members side by side over
identical calendar periods with n per period, an equal-weight composite
only where every member has the period, a relative wealth ratio for the
fund versus that composite, a survivorship sentence and a heterogeneity
sentence. Slot G is never "the benchmark" and never a PME. Not reopened in
this engagement. Implemented in R2-P1-A.

### 7.2 Decided: acquire the public CDLI and NFI-ODCE headline series
Oscar's instruction: whatever makes the product most usable. CDLI quarterly
headline returns from Cliffwater's published index page and NFI-ODCE
quarterly headline returns from NCREIF's published releases, each with a
manifest row (URL, fetch date, license note), into
`data/series_quarterly/idx_cdli.csv` and `idx_odce.csv`. If a source forbids
automated access, download once by hand and record the URL and date.
Cambridge and Burgiss stay cite-only until a license exists. If a public
series turns out to be unavailable without a license, the report says so
and the cite-only path stays. The composite is never substituted.
Constraint recorded on 2026-09-05: the build container reaches neither
cliffwaterdirectlendingindex.com nor ncreif.org (CONNECT 403 at the egress
proxy, section 7.8), so the fetch runs on a networked machine in R2-P1-1.

### 7.3 Default: demo script v8 for Tuesday speaks no composite number
v8 speaks no composite number and no PME number without the data-source
caveat ("Yahoo adjusted close, approximates NAV total return"). BKLN and PSP
comparisons are spoken with that caveat. The sreit misaligned verdict is
spoken. The Authority panel is opened only if the verbatim rule text is in
the build. The closing table is re-derived and Tier 1 of the verification
queue is re-derived from it. Reverse by: edit `docs/demo_script.md`.

### 7.4 Default: the verification gate admits a human signature (rule 16)
The invariant "verified = 0" is replaced in R2-P2-1 by "every verified row
has a signer that is not a script, an ISO date, and was written by
`verify_cell.py` (a marker in `verified_by`)". Zero is the current count,
pinned as a snapshot that any signature may move. Until R2-P2-1 lands the
existing pin stays, and no cell is signed by anyone in this engagement.

### 7.5 Default: sponsor identity leaves tracked files in R2-P3-2, no history rewrite
`identity_private` blocks move to an untracked encrypted file or a private
repository read by `src/tark_anon.py` at build time. Git history still
contains the blocks. A history purge is a separate decision for Oscar and
is not taken here.

### 7.6 Default: the service stays local-only for October
Bearer-token authentication from the environment, CORS restricted to the
site origin, each job in a temporary clone producing a patch a human
applies, a job table with status, a failed job never marking the census
entity evaluated. Not hosted unless Oscar decides otherwise.

### 7.7 Discrepancy: branch name
The brief names `remediation-r2-2026-09`. The session harness assigns
`claude/tark-round-2-audit-jl9q4q` and forbids pushing elsewhere. Work is
on the assigned branch. Oscar can rename or re-point the pull request.

### 7.8 Environment facts that constrain round 2 (2026-09-05)
Blocked at the egress proxy (CONNECT 403): `www.sec.gov`, `data.sec.gov`,
`www.federalregister.gov`, `query1.finance.yahoo.com`,
`www.cliffwaterdirectlendingindex.com`, `www.ncreif.org`,
`askebsa.dol.gov`, `www.supremecourt.gov`, `oscargladysz-arch.github.io`.
Open: `api.github.com`, PyPI, the Anthropic API host. No
`ANTHROPIC_API_KEY`. `data/raw/` absent. Consequences, each recorded where
it bites: the HTTP 200 check of the Tier 1 EDGAR URLs (R2-P0-10) cannot run
from this container and is recorded as such in `docs/DEPLOY_LOG.md` for a
person on a networked machine, the CDLI and ODCE fetch (R2-P1-1), the
Schedule H bulk file (R2-P1-10), the case-law documents (R2-P1-14), the
authority text (R2-P1-16), calibration and the 17th product (R2-P2-7,
R2-P2-8) all need a networked machine. Nothing is faked in their place.
Playwright: the venv pins 1.56.0 to match the shipped Chromium build 1194.

### 7.9 Baseline recorded 2026-09-05 (before any round-2 change)
Branch `claude/tark-round-2-audit-jl9q4q` at `4519e61` (main `3d158ff` plus
the round-2 audit document). `sh hooks/pre-commit`: 18 gates, exit 0, 849
`[PASS]` lines plus the validators' `[ok]` lines, wall time 107 seconds
(1m47s real, of which the frontend gate is about 70 seconds). The audit
counted 657 + 216 checks with a different convention (per-gate printed
counts). Record totals: 406 extracted-unverified, 205 n/a, 161 computed,
75 partial, 16 fetched, 1 structured, 0 verified, 0 pending, 864 cells.
Bundle: `site/data.js` 1,035,854 bytes, census chunk 303,090 bytes, 64
memos and 64 packets. Screenshots: `docs/screenshots/baseline_r2/`, the
same 42 views as `docs/screenshots/after_2026-09/` (hl_paf, cion_ares,
sreit, jll_ipt under the tech/media plan, product-independent views once),
8.5 MB.

### 7.10 R2-P0-1: accessions come from the manifest, and only from it
- The eight hl_paf citations (cells 1.1, 1.2, 2.1, 2.3, 2.7, 3.6, 4.2, 4.5)
  wrote `0001213900-26-054176*` (the July spike placeholder, HTTP 404 on
  EDGAR per the audit). The manifest's N-CSR filed 2026-06-09 for CIK
  1803491 is `0001213900-26-066804` (primary document
  `ea0291054-01_ncsr.htm`). The citation text and the product JSON source
  now carry the manifest accession. Eight source_doc and eight accession
  cells are allowlisted with the reason, and the eight accession changes
  are in the corrections table (old 054176, new 066804, cause "R2-P0-1:
  July spike placeholder accession"). No value, quote or status moved.
- The resolver's `accession_in_text` match type is retired. An accession
  written in a citation resolves only when the manifest holds it for that
  product. When the manifest holds a filing of that form on the written
  date and the written number differs, the manifest row resolves the
  reference and the row carries a `conflict` field that the invariants
  gate fails on. A written number the manifest does not hold resolves
  nothing and gets no URL. `validate_accessions` refuses an accession in
  the accession column or in any citation text that is not a manifest row
  for the product (the "or written in its citation" escape is gone).
- The accession column of every evidence row is now a watched number in
  the corrections log (surface: citation drawer EDGAR link, memo
  provenance table, packet provenance), so a changed accession is logged
  like a changed figure.
- The one other `accession_in_text` reference, cion_ares 4.6 (the N-CEN
  structured-dataset flag, status structured, T1), cites
  `0001049169-26-000801`. That accession is the census record's `ncen.ref`
  for CIK 1678124 (period 31-DEC-2025) from the SEC N-CEN structured
  dataset. The manifest gains a row for it (doc_set
  `structured_dataset_ncen`, form N-CEN, URL the EDGAR folder built from
  the CIK and the accession). Its filing date and primary document are not
  in the record and are left empty rather than guessed, and no document is
  held on disk (local_path empty). The ingest reads only manifest rows that
  name a local file. The URL was not HTTP-checked from this container
  (section 7.8). Reverse by: delete the row, and the cell's accession column
  empties with the reason "not a manifest row".
- "Every EDGAR URL in the bundle is built from the product's CIK and a
  manifest accession" is asserted twice: in `test_invariants` over
  `data/citations/` (the bundle's only source of EDGAR links, before the
  build) and in `reconcile` over the built `TARK_EVIDENCE` chunk (after the
  build). The invariants gate runs before `build_site` in the hook, so the
  bundle itself can only be checked after it.
- The local `origin/main` ref was stale at baseline (3d9b93e, the
  pre-merge main), so the immutability and corrections gates at baseline
  diffed against round 1's base. After `git fetch origin main` the ref is
  `4519e61` (main after PR #1 plus the audit upload), and both gates are
  re-run against it: the round-1 rows stay in the table as history, the
  round-2 rows are attributed to their task ids.

### 7.11 R2-P0-2: affiliation is a fact from a map, and a composite is not a third party
- `provider_independence` no longer tests substrings. `data/registry.json`
  gains an `affiliations.providers` block: provider entity key to adviser
  entity keys, each entry cited to the registry's adviser entries. Today
  it holds one entry, Cliffwater (publisher of CDLI, adviser of
  cliffwater_cclfx). Nothing else is affiliated. "Published by the fund's
  own adviser" is written only where the map says so, and a property test
  over every product and every candidate asserts it.
- A peer composite is never "published by" anyone. Its independence reason
  reads "constructed by the evaluator from the roster, not a third-party
  index" and it earns 1 of 2: a construct the evaluator built from a
  roster the evaluator chose is not an independent yardstick.
- Consequence, recomputed and repinned (rule 6, cause named in the
  commit): every composite loses one point. cliffwater_cclfx, bcred, ocic
  and the four evergreen-PE funds keep the composite as primary at 9
  (tied with BKLN or PSP at 9, ordered on strategy_match). pflex and
  cion_ares move to BKLN as primary (9) with the composite secondary (8).
  kkr_kpec's secondary moves from the composite (7, data_quality 0) to
  the Cambridge PE benchmark (7, licensed and not held, no computable
  comparison), ordered ahead on strategy_match. The tie wording
  ("outranked") is audit item 18 and is R2-P1-2. The expected-outcome
  table in `docs/benchmark_methodology.md` section 9 is repinned from the
  engine's recomputation and says so. Every changed number is in the
  corrections table under the R2-P0-2 cause.
- Not tuned: a cited index taking kkr_kpec's secondary slot is the rubric's
  arithmetic on today's data, and the slot says the comparison is not
  computable. Slot K and Slot G (decision 7.1) replace this rubric in
  R2-P1-A.

### 7.12 R2-P0-3: nothing a developer would say reaches a surface or a document
- `src/tark_display.py` holds the maintained list `SURFACE_FORBIDDEN`
  (case-insensitive patterns) and `src/test_surfaces.py` (new gate, after
  `reconcile` in the hook) scans the built bundle's displayable strings,
  every rendered view including the Authority panel, the citation drawer,
  the three forms with their outputs and the census entity detail, and
  every generated docx. The list only grows.
- The brief's token `run ` is implemented as the developer-instruction
  sense (`run python`, `run src/`, `run the hook`) because the bare token
  appears in ordinary English inside immutable T2 evidence: "tenders run
  contemporaneously" (amg_pantheon 3.2), "offers have run every quarter"
  (cion_ares 3.3), "searches run on stripped text" (bcred 5.1, breit 5.1),
  "expenses run through" (jll_ipt 2.3). None of these is an instruction.
- Internal keys render through display maps (`STRATEGY_LABEL`,
  `COHORT_LABEL`, `LANE_LABEL`, `ASSET_CLASS_LABEL`, `SUB_STRATEGY_LABEL`,
  `CANDIDATE_SHORT`, `RUBRIC_LABEL`) shared by the engine, the writer, the
  memo, the packet and the JS through the bundle. Product keys
  (`hl_paf`, `cliffwater_cclfx`) are the record's own identifiers, appear
  in file names and in the demo script, and are not on the forbidden list.
  Prose written for a reader uses fund short names instead.
- Computed cells no longer cite a repository path as their source or a
  script path as their extractor. The source names the artifact kind and
  the fund or cohort ("benchmark selection artifact (Hamilton Lane Private
  Assets Fund)"), the extractor is "Tark computed-cells writer (as-of
  date)". The artifact files are unchanged and the writer's producer
  functions name them. 18 T2 citations carried "(raw: data/raw/...)"
  locators and 3 T2 values carried a repository folder inside workflow
  prose. The locators are removed (the manifest local_path and the
  citations record carry the file), each row allowlisted with the reason.
  No value figure, quote or status changed.
- The Authority panel and the memo print one sentence while the verbatim
  text is absent: "The verbatim text of paragraphs (g) to (l) is not yet
  in this build. The Federal Register document is linked above." The
  Schedule H sentence is "Schedule H benefit-payment lines are not yet in
  the plan record. Demand uses the illustrative turnover sliders only."
  The plan files' null reasons lose the environment excuse.
- The `anonymization_rule` string is no longer printed anywhere. The plan
  is shown under its anonymized label and the memo says so.
- The three browser forms no longer print a command line or a "save as
  <path>" comment. Each prints valid JSON (or, for verification, a
  signature request naming the product, cell, signer and date) and one
  sentence: send it to Tark to record it. Downloadable files and a copy
  button are R2-P2-3. The census entity card no longer prints an ingest
  command: it names the CIK and says that Tark runs the evaluation.
- Not changed in P0: extractor strings on protected T2 rows such as
  "Claude (spike 2026-07-09)" and "Claude (M6 pipeline)" are provenance
  written by earlier passes. They name no path or script and stay until
  the cells are re-extracted or re-owned (R2-P1-13).

### 7.13 R2-P0-5: liquidity reason strings read the facts they cite
- Two facts where one was conflated: `dealing_cadence` (daily, monthly,
  quarterly, exchange) and `cap_period` (month, quarter, year), plus
  `repurchase_caps`, a list of {pct, period} so breit carries both its
  caps (2% per month and 5% per quarter). Every value quotes cell 3.1's
  words in the fact note. jll_ipt's `repurchase_cadence_per_year` moves
  from 4 to 252 (daily requests, trading-day convention, status computed),
  its cap stays 5% per quarter.
- Annual capacity is the binding figure, min over the caps of pct * periods
  per year, never cadence * cap: breit 24 to 20, jll_ipt 20 (5 * 4, not
  4 * 5), sreit 0 (suspended). No structural or scenario verdict moved.
  breit under the consulting plan now prints THIN HEADROOM (13.7% of 20%
  is 68.5%, over the 60% rule) where it printed adequate headroom.
- The structural-gap sentence reads `repurchase_program_status` first:
  sreit says "repurchases are suspended" and no cadence. Otherwise it says
  the dealing cadence in words and the caps with their periods.
- Citations are the cells the match read (the facts' source cells) plus
  3.5 and 3.7 only when the product's cell is not n/a, never 3.9.
- The JavaScript port reads the binding capacity from the match file and
  yields null, never 0, when no cap is typed (audit item 27).
- Merge note: the work was done by an agent in a worktree from commit
  7e8ba68 and merged three-way into the tree after R2-P0-3. Only the code
  and the plan files were taken. The data artifacts were regenerated here
  by the producer chain, so they carry both tasks' changes.

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

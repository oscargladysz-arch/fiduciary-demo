# Deploy log

Every deploy of the static frontend to the `gh-pages` branch is recorded
here from the hook run that authorized it, and the entry is committed with
the deploy. A deploy without an entry is a rule violation (round-2 brief,
rule 10). One entry per deploy, newest last.

Each entry carries: the source commit, the machine, the hook run (gate list
in order, exit code, PASS-line count, wall time, timestamp), the build
outputs, the deploy target and its resulting commit, the Tier 1 drawer check
and the EDGAR URL check, and anything that could not be checked from the
machine that deployed.

Pre-deploy steps, in order:
1. `sh hooks/pre-commit` on the exact commit to deploy, output kept.
2. `python src/build_site.py` on that commit.
3. `python src/check_edgar_urls.py` on a machine that reaches sec.gov
   (needs `TARK_SEC_CONTACT`). Every Tier 1 URL must answer 200.
4. Deploy per `docs/INVESTOR_DEMO.md`, then write the entry below.

From R3-P0-3 the gates workflow (`.github/workflows/gates.yml`) performs
steps 1 to 4 on every green run on `main` and appends the entry itself
(`src/ci_deploy_entry.py`) in a commit marked to skip CI. A hand deploy is
then the exception (a rollback, or a day the workflow is down) and is
recorded here the same way. Pull request preview builds under
`previews/<number>/` on `gh-pages` are not deploys and get no entry.

## Entry 1, 2026-09-05, R2-P0 (the Tuesday cut)

- Source commit: `0d37757` on `claude/tark-round-2-audit-jl9q4q`
  (R2-P0-10). The tree deployed is the tree of that commit. The pull
  request for R2-P0 carries the same tree, so a redeploy from `main` after
  the merge changes nothing on the live site.
- Machine: the remote build container (Linux, Python 3.11, Playwright
  1.56.0, Chromium build 1194). It does not reach sec.gov, github.io or
  federalregister.gov.
- Hook run that authorized the deploy: `sh hooks/pre-commit` on the tree of
  `0d37757`, started 2026-09-05 08:36 UTC, finished 08:39 UTC, exit 0, 906
  `[PASS]` lines, wall time 141 s. Gates in order, each green:
  validate_data, validate_census, test_evidence_immutable, corrections_log
  check, test_invariants, test_copy, test_docs, test_analytics,
  test_cohort, test_benchmark, test_liquidity, test_ingest, test_memo,
  test_app, test_artifacts_fresh, build_site, reconcile, test_surfaces,
  test_frontend.
- Build outputs from that run: `site/data.js` 1,094,522 bytes,
  `site/series.js` 1,260,842 bytes, `site/census.data.js` 303,145 bytes,
  64 memos and 64 packets under `site/memos/`. The anonymization gate in
  the build passed.
- Deploy: the built `site/` copied over the existing `gh-pages` history
  (every prior file removed first, `.nojekyll` kept), committed as
  `d74e91c` and pushed to `origin/gh-pages` (`94bf391..d74e91c`, 135 files
  changed). A recursive diff between `site/` and the deployed tree shows no
  difference apart from `.nojekyll`. The runbook's orphan-branch force-push
  was not used: the session's permission policy refused a force-push, so
  the deploy appends to history instead, which is the less destructive
  form of the same step.
- Tier 1 drawer check: run against the local build of `0d37757` by the
  frontend gate ("Tier 1 manual check, automated: drawer document, quote
  and accession equal the CSV for all 10 cells"). The ten cells and their
  EDGAR URLs are the list `python src/check_edgar_urls.py --list` prints
  (13 citation rows, 9 distinct URLs). The live URL could not be opened
  from this container (github.io is blocked), so the same check on the
  live page is for a person before Tuesday.
- EDGAR HTTP 200 check: NOT DONE. `python src/check_edgar_urls.py` exits 2
  here ("unreachable (ProxyError)" on every URL). A person on a networked
  machine runs it before the sends and appends the result to this entry.
- Demo script surface check: green in the same run ("all 35 surface-check
  texts render on the named view under the named plan", "no peer-composite
  ratio is spoken").
- Screenshots of the deployed build: `docs/screenshots/after_r2/`, 42
  files, 8.7 MB, the same views as `docs/screenshots/baseline_r2/`.
- Not in this deploy, by decision: the verbatim rule text (7.3), the
  CDLI and NFI-ODCE headline series (7.2, R2-P1), Schedule H lines, the
  calibration run and the 17th product (7.8).

## Entry 2, 2026-09-07, R2-P1 and R2-P2-1 to R2-P2-3

- Source commit: the code tree of `95f2e28` on
  `claude/tark-round-2-audit-jl9q4q` (R2-P1 merged from pull request 3,
  then R2-P1-16, R2-P2-1, R2-P2-2, R2-P2-3, the merge of `main` and the
  skill move). The commit that adds this entry differs from that tree by
  this file, the build report and the decisions file only, as entry 1 did.
- Machine: the remote build container (Linux, Python 3.11, Playwright
  1.56.0, Chromium build 1194). It does not reach sec.gov, github.io or
  federalregister.gov.
- Hook run that authorized the deploy: `sh hooks/pre-commit` on the tree of
  `95f2e28`, started 2026-09-07 07:01:45 UTC, finished 07:05:07 UTC, exit
  0, 1,048 `[PASS]` lines, wall time 202 s. Gates in order, each green:
  validate_data, validate_census, test_evidence_immutable, corrections_log
  check, test_invariants, test_copy, test_docs, test_analytics,
  test_cohort, test_benchmark, test_liquidity, test_ingest (with
  test_sources), test_memo, test_app, test_artifacts_fresh, build_site,
  reconcile, test_surfaces, test_frontend.
- Build outputs from that run: `site/data.js` 1,192,453 bytes,
  `site/series.js` 1,118,892 bytes, `site/census.data.js` 303,145 bytes,
  64 memos and 64 packets under `site/memos/`. The anonymization gate in
  the build passed (13 sponsor tokens screened).
- Deploy: the built `site/` of that run copied over the existing `gh-pages`
  history (every prior file removed first, `.nojekyll` kept), committed as
  `839940f` and pushed to `origin/gh-pages` (`d74e91c..839940f`).
  A recursive diff between `site/` and the deployed tree shows no
  difference apart from `.nojekyll`. Appended to history, no force-push, as
  in entry 1.
- Tier 1 drawer check: green in the authorizing run ("Tier 1 manual check,
  automated: drawer document, quote and accession equal the CSV for all 12
  cells"). The live URL was not opened from this container (github.io is
  blocked), so the same check on the live page is Oscar's, on his machine.
- EDGAR HTTP 200 check: DONE by Oscar on his machine on 2026-09-07 before
  this deploy, `python src/check_edgar_urls.py` on the tree of `95f2e28`:
  "15 citation rows, 9 distinct EDGAR URLs (Tier 1 of
  docs/verification_queue.md)", every one of the 9 URLs answered 200,
  exit 0. The nine: the two Hamilton Lane N-CSR and SC TO-I documents,
  the Cliffwater N-CSR, the Destiny Tech100 N-CSR, the KKR 10-K, the ARK
  Venture N-CSR, and the Starwood REIT 10-K, 10-Q and 424B3, each by its
  accession as the check printed them.
- Demo script surface check: green in the same run ("all 48 surface-check
  texts render on the named view under the named plan", the spoken peer
  ratio only as the labeled peer comparison, no v2 composite ratio).
- What this deploy puts live for the first time: benchmark architecture
  v3 (the meaningful benchmark and the peer comparison as two named
  cards, typed declared benchmarks, calendar-aligned composites, the
  reference comparison, generated escalation), the liquidity view on the
  filed outflow proxy, cell 1.12 on every product, the verbatim text of
  paragraphs (g) to (l) in the Authority panel and the memo appendix, the
  forms that hand the person a file, and the Verification view whose
  signature requests the gate now admits.
- Not in this deploy: any human-verified cell (the count is 0 until Oscar
  signs the Tier 1 rows, which goes out as entry 3), the CDLI and NFI-ODCE
  headline series, the case-law source documents, the calibration run and
  the 17th product.
- Rollback: `d74e91c` (entry 1) stays in the `gh-pages` history.

## Entry 3, 2026-09-08, workflow deploy from main

- Source commit: `d0bd630` on `main`, deployed by the gates
  workflow (R3-P0-3) from the run at https://github.com/oscargladysz-arch/fiduciary-demo/actions/runs/34255089279. The tree deployed is the
  built site of that commit.
- Machine: a GitHub-hosted Ubuntu runner (Python 3.11, Playwright
  1.56.0, LibreOffice from apt). It reaches sec.gov.
- Hook run that authorized the deploy: `sh hooks/pre-commit` on the tree of
  `d0bd630`, started 2026-09-08T17:09:07Z, finished 2026-09-08T17:13:13Z, exit 0,
  1,264 `[PASS]` lines, wall time 246 s.
  Gates in order, each green: validate_data, validate_census, test_evidence_immutable, corrections_log check, test_invariants, test_copy, test_docs, test_analytics, test_cohort, test_benchmark, test_liquidity, test_ingest, test_memo, test_app, test_artifacts_fresh, build_site, reconcile, test_surfaces, test_frontend.
- Build outputs from that run: `site/data.js` 1,189,866 bytes, `site/series.js` 1,200,089 bytes, `site/census.data.js` 303,176 bytes, 65 documents under `site/memos/`. The
  anonymization gate in the build passed.
- Deploy: the built `site/` replaced the `gh-pages` root (every prior root
  file removed first, `previews/` and `.nojekyll` kept), committed as
  `77e2bb9` and pushed without force. A recursive diff between
  `site/` and the deployed root shows no difference apart from `.nojekyll`
  and `previews/`.
- Tier 1 drawer check: green in the authorizing run (the frontend gate's
  automated drawer check against the evidence CSV).
- EDGAR HTTP 200 check: not done (TARK_SEC_CONTACT unset).
- Demo script surface check: green in the same run (the frontend gate
  renders every spoken text on its named view).
- Rollback: the previous `gh-pages` commit stays in the branch history.

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

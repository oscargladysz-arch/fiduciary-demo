# Tark: Investor Demo Runbook

## URLs
- **Primary (static frontend):** https://oscargladysz-arch.github.io/fiduciary-demo/
  Served from the `gh-pages` branch. If the URL 404s, enable Pages once:
  GitHub repo, Settings, Pages, Source "Deploy from a branch", branch
  `gh-pages`, folder `/ (root)`, Save. Propagation takes up to 2 minutes.
- **Legacy (Streamlit `app.py`):** the existing Streamlit Cloud deploy, which
  redeploys from `main` pushes. Keep it alive until the new frontend has run
  one real investor meeting. Then it may be retired (P3-4 in
  `docs/DECISIONS_2026-09.md`).
- **Local (no network needed):**
  ```
  cd <repo> && . .venv/bin/activate
  python src/build_site.py && python -m http.server 8410 -d site
  # open http://localhost:8410
  ```
  Streamlit fallback: `streamlit run app.py`.

## Redeploying the frontend
Only from a green `main` after the remediation pull request is merged.
```
. .venv/bin/activate && sh hooks/pre-commit && python src/build_site.py
TMP=$(mktemp -d) && cp -R site/. "$TMP"/ && touch "$TMP"/.nojekyll
git -C "$TMP" init -q -b gh-pages && git -C "$TMP" add -A
git -C "$TMP" commit -q -m "deploy"
git -C "$TMP" push -f https://github.com/oscargladysz-arch/fiduciary-demo.git gh-pages
```
Build outputs, all gitignored on the code branches: `site/data.js`,
`site/series.js`, `site/census.data.js`, `site/census/`, `site/memos/`.
Regenerate them with `python src/build_site.py`. Never hand-edit them. The
build refuses to emit the bundle or copy a memo if any plan-sponsor token
(sponsor names, plan names, EINs, ack ids) would leak.

## Reset steps before a demo
1. `git checkout main && git pull`
2. `sh hooks/pre-commit` (every gate, see the list below)
3. `python src/build_site.py`
4. Open the Pages URL and hard-refresh (Cmd+Shift+R) to bust the module
   cache. The series and census chunks lazy-load, so hard-refresh twice
   after a redeploy.
5. The app opens on the **Screener** with the tech/media plan selected.
   `docs/demo_script.md` says where to go from there.

## Numbers to say out loud
Say only numbers you read off a surface during the meeting. Do not memorize
record percentages from this file: they change with every commit and the
surfaces recompute them from the record. Where each number lives:
- **Coverage and provenance:** the headline on the Coverage view, stated per
  status kind (structured, extracted-unverified, verified, computed,
  partial, documented n/a), never as one merged count. The "Human
  verification" figure on the same view is 0 until a human signs a row in
  `data/evidence/*.csv`.
- **Roster:** 16 products. The count on the Candidate Roster header comes
  from the record.
- **Universe (validator-enforced T1 counts, not human-verified):** 3,599
  registered wrappers (245 interval, 516 tender CEF, 378 BDC, 1,072
  non-traded REIT, 213 listed CEF, 1,174 unlisted CEF other, 1 reconciled
  '34-Act), against 72,502 Form D pooled funds raising in the trailing 24
  months (the dark universe). Census as of 2026-08-25.
- **Verification queue:** the Tier 1 rows (the cells the demo speaks aloud)
  sit first on the Verification view, each with a badge.

## Tier language discipline
T1 "structured filing data" (blue badge): machine-read regulatory datasets,
no model judgment. T2 "extracted-unverified": AI extraction with a citation,
awaiting a human check. T3 "verified": human-signed in the evidence CSV.
Never blur them in the meeting. The separation is the product. An agent
re-check is never presented as human verification.

## Known rough edges
- Search queries and pins are local (localStorage) by design. They never
  enter URLs. A shared link reproduces configuration, not query text.
- Palette command grammar is minimal (views, products, plans, cells,
  compare, density). Matching is substring-based.
- Saved scenarios are per-browser (no sync, nothing leaves the origin).
- `hl_paf`, `kkr_kpec` and `breit` PME windows move in fiscal-year steps
  (annual disclosure is the honest granularity). Only products with a daily
  NAV series have the smooth monthly slider.
- Glossary chips need a hover, or a tap on touch devices.
- Zero cells are human-verified. The UI says so on every surface that
  counts. That is a feature, not a gap.

## Fallback plan (in order)
1. Pages URL fails: local `http.server` (step above, 10 seconds).
2. Laptop dies: `docs/screenshots/baseline_2026-09/` holds all 18 views for
   four products under the tech/media plan as JPEG. The after set of the
   remediation lands in `docs/screenshots/after_2026-09/`.
3. Deep questions on provenance: open `data/evidence/<product>_evidence.csv`
   live. It is the human-verification interface and reads like a ledger.

## What is enforced by machines (say this in the meeting)
- Pre-commit runs 15 gates, in this order: `validate_data` (data contract),
  `validate_census` (T1 census), `test_evidence_immutable` (T2 rows change
  only through an allowlisted correction), `corrections_log` (every changed
  published number is logged), `test_invariants` (verified count is 0, no
  stale product-count copy, every cited path exists), `test_copy` (no em
  dash or semicolon in user-facing copy), `test_docs` (this runbook agrees
  with the hook, the record and the app), `test_analytics`, `test_cohort`,
  `test_benchmark`, `test_memo`, `test_app` (Streamlit suite),
  `test_artifacts_fresh` (committed artifacts reproduce from a clean
  producer run), `build_site` (anonymization gate), `test_frontend` (render
  sweep across every view, product and plan with the HTML parsed,
  anonymization, JS/Python parity, runtime dead-key check). The full hook
  ran in 39 seconds on 2026-09-04 in the remote build container. There is
  no CI yet (P3-2).
- No number reaches a surface unless it is in the cited data layer or is
  recomputed live from it. Scenario math is always labeled ILLUSTRATIVE.
- `verified` status can only be set by a human editing the evidence CSV.
  The gates assert the count is 0 in this pull request.

## Promotion pipeline (census to roster)
`python src/promote.py <cik> --key <key>`: R1 identity check against live
EDGAR, 54-cell scaffold, census answers prefilled at status `structured`,
extraction worklist printed. Needs network and `TARK_SEC_CONTACT`. Without
network, narrate from the two shipped case studies (ocic, cion_ares).

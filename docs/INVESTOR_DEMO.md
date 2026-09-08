# Tark: Investor Demo Runbook

## URLs
- **Primary (static frontend):** https://oscargladysz-arch.github.io/fiduciary-demo/
  Served from the `gh-pages` branch. If the URL 404s, enable Pages once:
  GitHub repo, Settings, Pages, Source "Deploy from a branch", branch
  `gh-pages`, folder `/ (root)`, Save. Propagation takes up to 2 minutes.
  `docs/DEPLOY_LOG.md` names the commit that is live and the hook run that
  authorized it. A pull request does not redeploy Pages by itself, so if the
  latest entry there is older than the branch you are demoing, demo from a
  local build (next item) or from the after screenshots.
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
Only from a green hook run on the exact commit being deployed, recorded in
`docs/DEPLOY_LOG.md` (rule 10 of the round-2 brief). On a machine that
reaches sec.gov, `python src/check_edgar_urls.py` must report 200 for every
Tier 1 EDGAR URL first (it needs `TARK_SEC_CONTACT`). The build container
cannot run that check, so a deploy from it is logged as pending that check
and a person runs it before the meeting.

From R3-P0-3 the workflow `.github/workflows/gates.yml` does this on its
own: on every push and pull request it installs Python, the pinned
Playwright with its Chromium and LibreOffice, and runs the full hook with
`TARK_SEC_CONTACT` from the repository secrets (Oscar adds that one secret,
the workflow never receives a model key). On a pull request it publishes
the built site to `gh-pages` under `previews/<number>/` and posts the URL
as a comment (the folder is removed when the pull request closes). On a
green run on `main` it replaces the `gh-pages` root (previews kept), runs
the EDGAR check against the deployed tree, and appends the deploy-log entry
in a commit marked to skip CI. Hand deploys stop the day that workflow is
green on `main`. The recipe below stays for a rollback or for a day the
workflow is down, and every hand deploy still gets its entry.
```
. .venv/bin/activate && sh hooks/pre-commit && python src/build_site.py
python src/check_edgar_urls.py
TMP=$(mktemp -d) && cp -R site/. "$TMP"/ && touch "$TMP"/.nojekyll
git -C "$TMP" init -q -b gh-pages && git -C "$TMP" add -A
git -C "$TMP" commit -q -m "deploy"
git -C "$TMP" push -f https://github.com/oscargladysz-arch/fiduciary-demo.git gh-pages
```
Then write the entry in `docs/DEPLOY_LOG.md` (source commit, hook output,
resulting `gh-pages` commit, what was and was not checked) and commit it.
Build outputs, all gitignored on the code branches: `site/data.js`,
`site/series.js`, `site/census.data.js`, `site/census/`, `site/memos/` (64
decision memos and 64 committee packets, one pair per plan and product).
Regenerate them with `python src/build_site.py` (about 15 seconds, most of it
the documents). Never hand-edit them. The build refuses to emit the bundle or
copy a document if any plan-sponsor token (sponsor names, plan names, EINs,
ack ids) would leak.

## Reset steps before a demo
1. `git checkout main && git pull`
2. `sh hooks/pre-commit` (every gate, see the list below)
3. `python src/build_site.py`
4. Open the Pages URL and hard-refresh (Cmd+Shift+R) to bust the module
   cache. The series and census chunks lazy-load, so hard-refresh twice
   after a redeploy.
5. The app opens on the **Screener** with the tech/media plan selected.
   `docs/demo_script.md` (v10, the advisor workflow) says where to go from
   there, and its closing table names the record location of every number
   it speaks.
6. Present at 125% browser zoom (Cmd+Plus twice from 100%). The calls are
   screen-shared and the current type sizes are small at 100%.

## Numbers to say out loud
Say only numbers you read off a surface during the meeting. Do not memorize
record percentages from this file: they change with every commit and the
surfaces recompute them from the record. Where each number lives:
- **Coverage and provenance:** the headline on the Coverage view, stated per
  status kind (structured, extracted-unverified, verified, computed,
  partial, documented n/a, advisor-stated), never as one merged count. The
  "Human verification" figure on the same view is 0 until a human signs a
  row through `src/verify_cell.py`.
- **Roster:** 16 products. The count on the Candidate Roster header comes
  from the record.
- **Benchmark card figures** (score out of 10, the statistic the card names,
  the effective window, the fund return source): read them from the card.
  The card carries two named comparisons (decision 7.1). "Meaningful
  benchmark (paragraph (k))" is the highest-scoring independent index or
  proxy for the strategy: against a public market series the statistic is
  KS-PME and Direct Alpha, against a published appraisal-based series it is
  a relative wealth ratio, and a cited index that is not held shows no
  number and says so, with a reference comparison on the best held public
  series named as a reference. "Peer comparison (paragraphs (g) and (h))"
  is the cohort side by side on identical calendar periods with n per
  period and a relative wealth ratio, never a benchmark and never a PME.
  The reconcile gate ties every figure across the Screener, the card, cells
  1.8 and 1.12 and the memo, so the card is the number.
- **Liquidity verdicts:** two layers on the Liquidity Match view. The
  structural verdict comes from typed facts and does not move with the plan.
  The scenario verdict is labeled ILLUSTRATIVE and does. Never quote the
  scenario layer without the label.
- **Universe (validator-enforced T1 counts, not human-verified):** 3,599
  registered wrappers (241 interval, 516 tender CEF, 378 BDC, 1,072
  non-traded REIT, 217 listed CEF, 1,174 unlisted CEF other, 1 reconciled
  '34-Act), against 72,502 Form D pooled funds raising in the trailing 24
  months (the dark universe). Census as of 2026-08-25.
- **Verification queue:** the Tier 1 rows (the cells the demo speaks aloud)
  sit first on the Verification view, each with a badge.

## Tier language discipline
T1 "structured filing data" (blue badge): machine-read regulatory datasets,
no model judgment. T2 "extracted-unverified": AI extraction with a citation,
awaiting a human check. T3 "verified": human-signed in the evidence CSV.
Advisor-stated cells (6.6, 6.8, 3.7, 2.8, 3.5, 4.9) are inputs the advisor
supplies for one plan, carry their own badge and are never counted as
evidence. Never blur any of these in the meeting. The separation is the
product. An agent re-check is never presented as human verification.

## What an advisor can do in this build
Every action below ends in a file the CLI validates before anything enters
the record. The static site itself writes nothing. Every form offers its
file as a named download and a copy button (decision 7.31).
- **Advisor inputs** (Six-Factor Evaluation, complexity and liquidity
  factors): the form under an advisor-completed cell makes a patch file for
  `data/advisor/<plan>__<product>.json` (value, signer, date). The memo
  carries the answers in their own section.
- **A new plan** (Reference Plans view): the intake form emits the intake
  file for `python src/plan_intake.py <file>`. The intake stores an
  anonymization label and the Form 5500 primitives, never a sponsor
  identity. A description such as "consulting company" or a Colorado plan
  is accepted, a corporate suffix, an EIN or a reference sponsor's token is
  refused.
- **Signing a cell** (Verification view): the form beside a row makes a
  signature request file for `src/verify_cell.py`, run by the person who
  checked the row. Signer and date are required, and the tool refuses to
  sign unless the recorded quote is found in the cited filing on that
  machine (decision 7.30). Nothing else can write `verified`.
- **Memo and committee packet** (Packet view): one decision memo and one
  packet per plan and product, generated by the build, file names carry the
  plan. Print is scoped to pinned exhibits.
- **A new fund** (Universe view, "Evaluate this fund"): the panel names the
  CIK and a suggested record key for
  `python src/ingest.py <cik> --key <key>`, which runs identity check,
  filing fetch, structured extraction under a verbatim-quote contract, and
  the validator. Needs network, `TARK_SEC_CONTACT` and `ANTHROPIC_API_KEY`.
  The one-endpoint service (`service/app.py`, URL from `TARK_SERVICE_URL`)
  does the same for a hosted deployment and keeps no job state.

## Known rough edges
- Search queries and pins are local (localStorage) by design. They never
  enter URLs. A shared link reproduces configuration, not query text.
- Palette command grammar is minimal (views, products, plans, cells,
  compare, density). Matching is substring-based.
- Saved scenarios are per-browser (no sync, nothing leaves the origin).
- Annual-tier products (filed fiscal-year returns) have PME windows that
  move in fiscal-year steps in the Analysis Lab (annual disclosure is the
  honest granularity). Only products with a daily NAV series have the
  smooth monthly slider. The lab opens on the engine's own comparison: the
  meaningful benchmark's series when it is held, else the reference series.
- Glossary chips need a hover, or a tap on touch devices.
- Zero cells are human-verified. The UI says so on every surface that
  counts. That is a feature, not a gap.
- The verbatim rule text was fetched by `python src/fetch_authority.py` on
  2026-09-07 from the Federal Register API (decisions 7.3 and 7.29). The
  Authority panel quotes paragraphs (g) to (l) from the hashed file in the
  record, the rule paragraph in view and the examples folded, and every
  memo quotes the rule paragraphs in its regulatory basis and the full text
  in its last appendix. The demo script opens the panel once, at 0:40.
- Cell 5.7 (case law) is `partial` on all 16 products: docket listing and
  search snippets, not the source documents. The memo labels it so.
- The ingestion pipeline is tested offline with a mock client. Its
  calibration run against an already-evaluated product (P2-3) and the 17th
  product (P2-4) have not run yet. Do not describe either as done.

## Fallback plan (in order)
1. Pages URL fails: local `http.server` (step above, 10 seconds).
2. Laptop dies: `docs/screenshots/after_r2/` holds all 18 views for four
   products under the tech/media plan as JPEG, shot from the round-2 build
   that was deployed. `docs/screenshots/baseline_r2/` holds the same 42
   shots before round 2, and the `_2026-09` pair holds round 1's before and
   after, for a before-and-after.
3. Deep questions on provenance: open `data/evidence/<product>_evidence.csv`
   live. It is the human-verification interface and reads like a ledger,
   accession column included.

## What is enforced by machines (say this in the meeting)
- Pre-commit runs 20 gates, in this order: `validate_data` (data contract,
  registry, advisor files, accessions, no laptop paths), `validate_census`
  (T1 census), `test_evidence_immutable` (T2 rows change only through an
  allowlisted correction), `corrections_log` (every changed published number
  is logged), `test_invariants` (verified count is 0, no stale product-count
  copy, every cited path exists), `test_copy` (no em dash or semicolon in
  user-facing copy), `test_docs` (this runbook agrees with the hook, the
  record and the app), `test_analytics`, `test_cohort`, `test_benchmark`,
  `test_liquidity` (two verdict layers, never blurred), `test_ingest` (the
  extraction contract, offline with a mock client), `test_memo` (all 64
  memos and 64 packets), `test_app` (Streamlit suite), `test_artifacts_fresh`
  (committed artifacts reproduce from a clean producer run), `build_site`
  (anonymization gate), `reconcile` (one number, every surface: facts,
  headlines, cards, cells 1.8, 1.12 and 3.9, match files and memo agree on
  expense ratio, management fee, the meaningful benchmark's KS-PME or ratio,
  the peer ratio and the liquidity verdict, and every EDGAR link in the
  drawer is the manifest's URL), `test_surfaces`
  (no developer instruction, file path, script name or internal key on any
  rendered view, in the bundle or in any generated document),
  `test_frontend` (render sweep across every view, product and plan with the
  HTML parsed, anonymization, JS/Python parity, runtime dead-key check,
  mobile and print renders, Tier 1 drawer against the CSV, and every
  on-screen text the demo script's surface-check block names), `test_web`
  (the rebuilt frontend under `web/`: the token gate, the formatting gate,
  the guideline audit on every rebuilt route at 1440 and 390 px in both
  themes, axe-core with zero serious or critical findings, the performance
  budget and the preview-subpath check). The full hook ran in 240 seconds
  on 2026-09-07 in the remote build container (`docs/DEPLOY_LOG.md` keeps
  each recorded run). CI runs the same hook on every push and pull request
  (`.github/workflows/gates.yml`, R3-P0-3).
- No number reaches a surface unless it is in the cited data layer or is
  recomputed live from it. Scenario math is always labeled ILLUSTRATIVE.
- `verified` status can only be set by a human through `src/verify_cell.py`
  (signer, date and the quote found in the cited filing). The gate accepts
  a verified row only in the form that tool writes, with its allowlist
  marker (decision 7.4, landed as 7.30). The count is 0 until a person
  signs a row.

## Promotion and ingestion pipeline (census to roster)
`python src/promote.py <cik> --key <key>`: R1 identity check against live
EDGAR, 55-cell scaffold, census answers prefilled at status `structured`,
extraction worklist printed. `python src/ingest.py <cik> --key <key>` runs
promote, fetch and the structured extraction in one pass. Both need network
and `TARK_SEC_CONTACT`, ingest also needs `ANTHROPIC_API_KEY`. Without
network, narrate from the two shipped case studies (ocic, cion_ares) and the
census panel's command.

# Tark fiduciary-demo: intended product vs. what is actually shipped

Audit date: September 3, 2026
Subject: https://oscargladysz-arch.github.io/fiduciary-demo/ (gh-pages), source at github.com/oscargladysz-arch/fiduciary-demo, `main` @ `3d9b93e` (tag `census-build`, 2026-08-25)
Method: (1) the intended feature set was taken from the Tark record in memory (the YC application framing, customer discovery with Morgan Lewis, CAPTRUST and Ferenczy, the design-partner offer, the October 2026 milestone). (2) The repo was cloned and read end to end (site/js, src/*.py, data/**, docs/**), with numbers recomputed in Python rather than taken from the build reports. (3) Every defect listed under "Confirmed live" was reproduced in a browser on the deployed site on the audit date. (4) The six-factor mapping was checked against the DOL proposal itself (91 FR 16088, RIN 1210-AC38, proposed 29 CFR 2550.404a-6) and against law-firm summaries of the regulatory text.

Everything below is either a file:line citation, a recomputed number, or a screenshot-verified surface. Nothing is taken from the build reports on trust, because several of the build reports turned out to be wrong.

---

## 1. Bottom line

The demo is far more built than "not investor-presentable" implies, and far less correct than its own build reports claim. The problem is not missing features. It is that the surfaces an investor or an advisor will actually look at carry wrong numbers, stale copy, visibly broken HTML, and engine verdicts that do not depend on the inputs they claim to depend on. For a product whose entire pitch is "every number is real and cited, the honest way," a wrong number on a benchmark card is worse than a missing feature.

Scorecard against the intended product (details in section 3):

| Intended capability (from the Tark record) | Status | Score /10 |
|---|---|---|
| Six-factor grid mapped to the DOL safe harbor, ~50 cited cells per product | Built, 54 cells x 16 products, 0 human-verified, 27% n/a by construction | 7 |
| Benchmark-selection engine, 12-point rubric, index-agnostic | Built as a 5-criterion / 12-point rubric that scores strategies, not products. 3/3 on one criterion is unreachable. Self-declared benchmark lane is defined and never read. Material window bug in the published PME numbers | 3 |
| Rejection ledger of comparators considered | Built (38 entries), but candidates are 3 to 5 hand-typed dicts per strategy, and one canned rejection reason is factually wrong for 4 of 5 private-credit products | 5 |
| Decision memo (docx) | Built, 16 memos, but hardwired to one plan, no liquidity verdict, findings table is truncated raw cell prefixes, no recommendation section in 14 of 16 | 4 |
| 14 (now 16) real products on real SEC filings, 4 anonymized reference plans | Built and real. Raw filings are not distributable, 42% of evidence rows point at `/private/tmp/...` scratch paths on a laptop | 7 |
| Plan-level liquidity suitability match | Built, but the verdict is a function of two hand-typed booleans and is identical across all four plans for every product | 3 |
| Peer cohorts (the rule's "reasonable number of similar investment alternatives") | Built, n = 3 to 5, with a percentile tie bug that prints contradictions into 16 cells and the memos | 5 |
| An advisor can run their own fund lineup through it (the October 2026 target and the design-partner offer) | Missing. No ingestion, no upload, no backend. The "promotion pipeline" scaffolds 3 of 54 cells and leaves 51 to a human plus edits to at least 5 Python dicts and 2 JS files | 1 |
| Evaluate a target-date-fund sleeve / CIT (Ferreira's steer, and the DOL's stated main channel) | Missing by construction. Cells 2.8, 3.5, 4.9 are n/a for all 16 products, 3(21)-advisor persona not addressed anywhere | 0 |
| Stack as described in the Tark record (FastAPI, Postgres, object storage, React/TypeScript, LLM + OCR ingestion) | Not present. It is a Python build script emitting a vanilla-JS static site, plus a legacy Streamlit app. No LLM API call exists anywhere in the repo | n/a, but the narrative and the code disagree |
| Universe census (T1) over 3,599 registered wrappers | Built and the strongest part of the product. Provenance per field. Not in the original intended feature list, added Aug 25 | 8 |
| Human verification tier (T3) | 0 of 406 verifiable cells verified. The CF2 pass has not started. The UI is honest about this | 0 (process, not code) |

Weighted view: the record layer (T1 census + T2 grid) is a 7. The analytical layer that the pitch calls the moat (benchmark engine, liquidity match, cohorts, memo) is a 3 to 4, because its outputs are largely invariant to the inputs they advertise. The "advisor runs their own funds" milestone is a 1 with eight weeks to go.

---

## 2. What the demo actually is (so the fix is scoped correctly)

- Build: `src/build_site.py` reads `data/**` and writes three JS bundles (`site/data.js` 1.10 MB, `site/series.js` 697 KB, `site/census.data.js` 303 KB) plus 64 census detail shards and 16 prebuilt `.docx` memos. Deploy is a force-push of `site/` to `gh-pages` (`docs/INVESTOR_DEMO.md:19-26`).
- Runtime: hash-routed vanilla-JS SPA, 18 views (`site/js/main.js:14-33`). State lives in the URL hash (whitelisted enums) and `localStorage`. Two same-origin `fetch()` calls for census shards. No backend, no API, no database, no auth, no server compute. No outbound network at runtime.
- Extraction: "Script fetches and organizes, humans read and extract" (`src/fetch_edgar.py:14`). In practice, 814 of 864 evidence rows carry `extracted_by = Claude Code / Claude`, so extraction was done in interactive agent sessions and pasted into CSV + JSON. There is no reproducible extraction code in the repo.
- Analytics: `src/tark_analytics.py` (KS-PME, Direct Alpha via bisection XIRR, Geltner AR(1) de-smoothing, drawdown, rolling stats, OLS beta) ported line by line to `site/js/analytics.js`. The Analysis Lab and De-smoothing Lab recompute live in JS. Benchmark cards, screener PME column and cell 1.8 are precomputed Python artifacts.
- Gates: 9 pre-commit gates (`hooks/pre-commit`), opt-in (the hook must be copied by hand), no CI. `test_frontend.py` is ~135 Playwright checks, all `inner_text` based.
- Legacy: `app.py` (Streamlit, 5 views over the same data) is still deployed and duplicates the rule caption, coverage math and product registry.

---

## 3. Feature-by-feature gap detail

### 3.1 Six-factor grid (intended: the core record)

Built. 54 cells per product, identical grid across 16 products, validator-enforced (`src/tark_data.py:39-69`). Real status distribution across 864 cells (recomputed from `data/evidence/*.csv`): extracted-unverified 406 (47.0%), n/a 237 (27.4%), computed 145 (16.8%), partial 59 (6.8%), fetched 16 (1.9%), structured 1 (0.1%), verified 0.

Gaps:
- "864/864 resolved" (`docs/BUILD_REPORT_5.md:154`) counts n/a as resolved. Seven cells are n/a for every product (2.8, 3.5, 4.9, 5.6, 5.7, 6.6, 6.8 = 112 cells, 13% of the grid). The effective grid is ~47 cells, not 54.
- Cell 5.6 "Benchmark suitability memo" and 5.7 "Case-law tracker" are n/a for all 16 products even though a benchmark selection artifact and a memo exist for 15 of them, and the memo hardcodes a case-law claim (see 3.4). The grid says the engine's own outputs do not exist.
- ~125 of the 145 "computed" cells (1.8, 1.9, 2.9, 3.8, 3.9, 5.3, 5.4, 5.5) are the pipeline's own outputs restated as evidence, with prose that no committed script produces.
- The "100%" coverage ring on every product card (Roster, Coverage) is computed with n/a removed from the denominator (`src/coverage.py:10`, `src/build_site.py:121-136`). Three different coverage formulas exist (`coverage.py`, `build_site.py`, `app.py`) and disagree on whether `structured` and `computed` count as pending. The single `structured` cell in the record (cion_ares 4.6) is what drops CION to "98% · 1 pending" on the Roster, so the T1 tier the demo script brags about is displayed as a defect.
- The 6 DOL factors are correctly named (verified against 91 FR 16088: performance, fees and expenses, liquidity, valuation, performance benchmark, complexity, paragraphs (g) to (l) of proposed § 2550.404a-6). But the mapping is asserted, not sourced: the citation exists only as string constants in three files (`src/build_site.py:33-36`, `src/tark_memo.py:25-26`, `app.py:28-31`), no rule paragraph is quoted anywhere, no cell is mapped to a paragraph, and the Federal Register document is not in `data/manifest.csv`.
- Source drawer shows document, section, verbatim quote, extracted-by and verification status, but nothing links to EDGAR. Only 8 of 481 evidenced rows carry an accession number in their source fields (recomputed from `data/evidence/*.csv`), the rest cite document type plus filing date, and 16 rows (all 5.2 series cells plus cclfx 3.3) have no accession or date anchor at all. An EDGAR link therefore needs a resolution step (CIK + form type + filing date to accession via the submissions JSON) before it can exist. `data/raw/` is gitignored, so no cited document is distributable from the repo, and 169 of 406 extracted rows point their `local_file` at `/private/tmp/claude-501/.../scratchpad/` (a laptop scratch path), 71 more at `/Users/oscargladysz/...`.
- Six full-depth product JSONs cite `data/plans/anchor_plan.json` in cell 3.7. That file does not exist (renamed to `plan_tech_media.json`).

### 3.2 Benchmark-selection engine (intended: the moat, "12-point rubric", "index-agnostic", "rejection ledger")

Built in `src/tark_benchmark.py`. The rubric is 5 criteria: `strategy_match` 0-3, `risk_liquidity_match` 0-3, `investability` 0-2, `data_quality` 0-2, `provider_independence` 0-2, max 12, primary threshold 7 (`:33`, `:293-333`). So "12-point rubric" is true as a maximum score and false as "twelve criteria". A rejection ledger exists in every selection file (38 entries total).

Defects, in order of severity:

1. The engine scores strategies, not products. `strategy_match` is a hand-typed integer on each menu entry (`:295`, e.g. `:169,174,179`). `risk_liquidity_match` depends only on the candidate's data cadence and one product flag (`:299-309`). `investability` = 2 iff a CSV exists on disk (`:311`). `data_quality` is a lookup on a hand-typed string (`:315-316`). `provider_independence` = 2 iff a hand-typed `independent: True` (`:323`). The only product-specific input is `price_nav_decoupled` (set by hand on dxyz and ssss, `:70,107`). Consequence, confirmed across all 14 non-escalated selection files: every product in a strategy gets identical primary, secondary, scores and rejection text. Every private-credit product: BKLN 9/12 primary and "PME / Direct Alpha vs BKLN" 9/12 secondary. Every evergreen-PE product: PSP 9, URTH 8. Both non-traded REITs: VNQ 9, ODCE 8. The rubric never reads the product's fees, leverage, liquidity terms, track length, AUM, or declared benchmark.

2. The secondary benchmark is the primary benchmark. For all five private-credit products the "secondary" is the same BKLN ETF with byte-identical KS-PME, Direct Alpha, fund and benchmark returns (confirmed live on the CION Ares benchmark card, 1.2376 / 2.37% / 6.38% / 3.89% in both slots). The ledger then rejects the peer cohort as "outranked ... vs primary 9/12 and secondary 9/12."

3. `risk_liquidity_match` 3/3 is unreachable (`:299-309`). The ceiling is 11, the highest score ever awarded is 9, and `test_benchmark.py:25-26` encodes a "perfect" candidate as 10. The UI (`site/js/views.js:334-335`) and Streamlit (`app.py:188-191`) advertise a 12-point scale.

4. A wrong-asset-class ETF passes. ARKVX secondary is SPY at 7/12 with `strategy_match 0/3` and the engine's own note "large-cap public equity - wrong asset class" (`:217-220`). Any unaffiliated daily ETF scores at least 0 + 1 + 2 + 2 + 2 = 7 and clears the threshold regardless of fit. Structurally, a strategy-exact but unheld index maxes at 8 versus 9 for an investable ETF with strategy_match 2, so an ETF wins every strategy. This is the opposite of the rule's definition of a meaningful benchmark ("similar mandates, strategies, objectives, and risks", proposed § 2550.404a-6(k)). Half the rubric's points (investability, data quality, independence) reward things the rule does not mention.

5. Lane A (self-declared benchmark) is not implemented. `self_declared` is set in every profile (`:41-159`) and read nowhere. Five profiles carry the placeholder string "see cell 5.1". The docstring (`:9-10`) and `docs/benchmark_methodology_skeleton.md:15` both promise it as a candidate. DXYZ declares the NASDAQ Composite (cell 5.1), CION declares the Credit Suisse Leveraged Loan Index, JLL IPT declares NFI-ODCE. None is in any menu.

6. A canned rejection reason is factually wrong. CDLI is hard-coded `independent: False` ("index published by the fund's own adviser") for the whole private-credit menu. True for Cliffwater's fund, false for bcred, pflex, cion_ares and ocic. Confirmed live on the CION benchmark card. BKLN's match note "fund itself declares NO benchmark (5.1)" is also wrong for cion_ares.

7. Escalation is hand-flagged. Every menu contains an ETF scoring at least 7, so the "all candidates below threshold" branch (`:427-428`) is unreachable. The only path to "NO MEANINGFUL BENCHMARK" is the hardcoded `price_nav_decoupled` flag (`:391-392`).

8. Lane C composites are never scored. `tark_benchmark.py` never imports `tark_cohort` or reads `data/cohorts/`. Lane C entries are fixed dicts with `series: None` (`:176-183, 202-210, 225-231, 249-253, 275-282`), so composite returns never enter `comparison_stats`. `docs/BUILD_REPORT_4.md:69-71` ("Lane C fed: peer cohorts now score on real composites") is false.

9. Published PME numbers are wrong for three products because of silent proxy-window truncation. All five ETF series start 2018-07-18 (`data/series/series_manifest.json`). `_level_on` (`src/tark_analytics.py:134-142`) returns the first level for any earlier date, so fund growth spans the full window while index growth spans only from 2018-07-18. Affected: amg_pantheon (window 2016-03-31 to 2026-03-31, published KS-PME 2.4551, recomputed like-for-like FY20-FY26 = 1.59, FY19-FY26 = 1.88), pflex (2017-02-23), cion_ares (2017-07-11). The card prints "window 2016-03-31 to 2026-03-31" as if both sides cover it. The JS port (`site/js/analytics.js:111-118`) reproduces the same error, so the parity test passes. These numbers are on benchmark cards, in the screener PME column, in cell 1.8 and in the memos.

10. Integer-year annualization (`:369-370`, `years = int(d1[:4]) - int(d0[:4])`). pflex fund_ann 6.62% published vs 6.29% by day count, cclfx 8.02% vs 7.89%, arkvx 30.67% vs 31.10%.

11. KS-PME and Direct Alpha carry one number. Flows are always two points (`:371`), so KS-PME = growth ratio and Direct Alpha = KS-PME^(1/T) - 1 exactly. Two headline "metrics" on every card are one metric.

12. The user "override" is a lookup, not a rescore. Analysis Lab lets the user pick 1 of 5 hardcoded proxies (`src/build_site.py:161-167`) for 6 of 16 products (`:176-197`). "The engine's judgment of your choice" reads a precomputed `swap_matrix` (`:201-227`). No UI to edit a weight, a threshold, add a candidate or load a series (a licensed private index cannot be used even if the advisor holds it).

13. jll_ipt has no selection artifact at all (no `PRODUCT_PROFILES` entry), and four of its facts fields are literally `status: "pending"`.

14. sreit's selection runs on a one-year window (2024-12-31 to 2025-12-31), kkr_kpec on 2.33 years.

What is genuinely good here and should be preserved: the ledger concept, the reasons-per-criterion text, the escalation for premium-driven listed vehicles, the refusal to compute on licensed data not held, and the JS/Python port discipline.

### 3.3 Liquidity match (intended: plan x product suitability)

Built in `src/tark_liquidity.py`, 64 match files (4 plans x 16 products). Verdict vocabulary: `conditional` (48), `conditional-weak` (8), `aligned-mechanical` (8). There is no failing verdict.

Defects:
- The verdict is a function of exactly two hand-typed booleans, `exchange` and `gate_history`, in `LIQUIDITY_PROFILES` (`:28-150`, transcribed into Python rather than read from cells 3.1/3.3). `:200-201`, `:208`, `:240-241`. Plan inputs change only the illustrative demand percentage (13.7 / 7.2 / 9.2 / 10.4 across the four plans, identical for every product) and one sentence of wording. Confirmed live: Starwood REIT (repurchases suspended April 2026, 0% capacity, stressed demand "EXCEEDS") is `conditional-weak` under both the $570M tech plan and the $9.8B consulting plan, and the reason text reads "at a 5% plan allocation the plan's position is far inside it" about a 0% cap, then "THIN HEADROOM: demand consumes over 60% of wrapper capacity" where capacity is zero.
- Demand-vs-capacity never changes the verdict, so the one quantitative part of the model is decorative.
- Plan data is Form 5500 only: participant counts, separated count, net assets, loans, benefit codes. Missing anything an advisor would need to size participant liquidity: age or tenure distribution, actual benefit-payment and withdrawal outflows (Schedule H line 2e is not carried), hardship and loan rates, contribution inflows, QDIA identity and glidepath, current menu, brokerage-window usage, IPS constraints.
- 16 legacy `data/liquidity/<key>_match.json` files are byte-identical copies of the tech-plan files, written by `:305-307` and read by no code.

### 3.4 Decision memo (intended: the deliverable a committee files)

Built in `src/tark_memo.py`, 16 docx files served from `site/memos/`, linked from Roster, Benchmarks and Packet. Sections: Regulatory basis, Six-factor findings, Benchmark selection and justification (with rejection log), Peer cohort placement, Provenance, blank signature line.

Defects:
- Every memo is for the tech/media plan only (`:72`, `:83`, `load_anchor_plan()`), regardless of the plan selected in the UI. There is no liquidity-match section, so the one plan-specific verdict the product computes (cell 3.9) never reaches the memo.
- The "Six-factor findings" table is the first 4 populated cells per factor truncated to 220 characters and concatenated (`:48-59`). 5 to 6 of 6 rows per memo end mid-sentence (hl_paf: "...Recoupment/(Reimbursement1.4: FY2026..."). These are not findings.
- No recommendation or verdict section in 14 of 16 memos. Only dxyz and ssss carry "Recommended action: do not proceed."
- Citations are cell IDs only. No accession numbers, no document names outside cell text.
- The Provenance paragraph says "verified cells have been independently re-checked" when 0 are.
- A hardcoded litigation-status sentence (`:42-44`, Anderson v. Intel "argument expected October Term 2026") is baked into every memo. Certiorari was granted January 16, 2026 and the case is pending. The sentence is unsourced and time-sensitive, and cell 5.7 "Case-law tracker" (where it belongs) is n/a for all 16 products.
- Caveat bullets contradict the product's own cells because `caveat_matrix.json` is wrapper-generic: the bcred memo says "quarterly NAV determinations" while its cell 4.1 says monthly. The hl_paf memo says "some members transact at NAV, others at exchange market price" for an all-NAV cohort, because `caveat_block` compares `pricing_basis` strings ("NAV" != "transactional NAV") and the `pricing_class` field built to prevent exactly this is unused.
- Memos are generated at build time with the build date, cannot be regenerated from the UI, and `test_memo.py:20` checks only 6 of the 16.

### 3.5 Cohorts

Built in `src/tark_cohort.py`. Membership hardcoded (`:29-63`), n = 3 to 5. `percentile_of` (`:105-130`) uses `(strictly_below + 0.5)/n` with no tie handling, so with all five private-credit repurchase caps at 5% each member is written into cell 2.9 as "10th percentile of cohort (n=5), at the median". 16 such contradictions exist in the record and flow into the memos via `tark_memo.py:170-172`. Composite = equal-weight mean of fiscal-year returns for years with 2+ reporters (`:164-192`), refused when `pricing_class` differs (`:171-177`). The composite is never consumed by the benchmark engine (3.2 item 8).

### 3.6 Fee Matrix

The bar chart (`site/js/views.js:881-889`) plots `supplement.fee_percentile`, produced by a regex that takes the first `N.NN%` in cell 2.3 prose (`src/run_supplement.py:54, 63-66`). Confirmed live: JLL IPT shows a 1.3% "net expense ratio" bar taken from a cell whose text begins "None exists structurally: '34 Act 10-K REIT wrapper - no 1940-Act fee table", while its two REIT peers correctly show "no TER line". ARKVX shows 4.4% (gross) under a title that says "net" (facts layer: 2.90%). PFLEX 5.1% includes interest expense (facts: 1.97%). AMG Pantheon 3.1 vs facts 2.38. kkr_kpec None vs facts 3.19. Five of 16 bars contradict the Screener/Compare views on the same site.

The same first-number regex produces the headline chips in the matrix table: AMG Pantheon's incentive-fee cell (2.2) headlines "10% to 20% of net profits" above text that says "Documented absence at Fund/Master level". ARKVX 2.2 headlines "2.75% Management Fee only" for a fund with no incentive fee. BREIT 2.4 (AFFE) headlines "1.25% of NAV payable monthly" above "Not applicable". A committee member scanning this table reads the opposite of the finding.

### 3.7 Analysis Lab, De-smoothing Lab, DXYZ view

- Analysis Lab covers 6 of 16 products (`src/build_site.py:176-197`). For any other product it silently falls back to cclfx (`site/js/views.js:390`). Confirmed live: with "Blue Owl Credit Income Corp." selected in the header, the lab renders "Cliffwater Corporate Lending Fund" with Cliffwater's PME and no warning.
- De-smoothing Lab covers 2 products, hardcoded (`views.js:991-1007`), although pflex, arkvx and cadux daily series ship in `series.js` (5,663 rows no JS references).
- `run_analytics.py` computes for 3 products only and hardcodes HL PAF returns (`:74-75`) and the CCLFX disclosed 9.34% (`:40`).
- Yahoo `adj_close` is labeled "Daily NAV (adj, distributions reinvested)" (`views.js:111`), which `run_analytics.py:18` admits "approximates".

### 3.8 Coverage & Provenance, Verification

- The Coverage hero reads "324 cells across six products" and "54% evidenced · 18% computed · 27% documented-unavailable" from `data/analytics/taxonomy.json`, generated 2026-08-09 in the 6-product era and regenerated by nothing (`views.js:1100`). 864 cells exist. Confirmed live.
- The "42/44 cells CONFIRMED by an independent re-location pass" tile is a hardcoded dict (`src/build_site.py:40-43`) from a 6-product, 44-cell pass that was run by Claude agents (`docs/crosscheck_report.md:4`), presented as independent. Coverage of the crosscheck: 10.8% of the 406 extracted cells.
- "0 human-verified" is a literal (`views.js:1107`), currently true.
- Verification view is read-only and tells the user to edit `data/evidence/*.csv` and rebuild.

### 3.9 Stale and broken surface copy (all confirmed live)

- Roster headline: "Six real products, six wrappers" above 16 cards (`views.js:187`, also `app.py:126`).
- Screener footer: "16 of 16 products match. Six rows today, the grid ... built for six hundred" (quoted with the site's punctuation removed, `workbench.js:204-205`).
- Coverage: "324 cells across six products" (above).
- `gloss()` (`views.js:57-67`) nests a `<span>` inside the outer span's `data-def` attribute whenever a glossary definition contains another glossary term (7 pairs). Result on screen: the wrapper chip for ARKVX, CION, CCLFX, HL PAF and PFLEX renders literal `TRUE Rule 23c-3).">interval fund` on the Roster and the Evaluation header. `inner_text` assertions cannot see it, which is why 135 Playwright checks pass.
- "computed" cell 5.4 for hl_paf, stepstone_spm, breit and kkr_kpec still names the old six-product peer set ("no second non-traded REIT in the six-product universe") though cohorts now have 3 to 5 members.
- `docs/INVESTOR_DEMO.md` says 7 gates at line 65 and 9 at line 94. `hook_snapshot.txt` lists 7.

### 3.10 Census (T1)

The strongest layer. 3,599 entities, counts by class match the declared totals, every leaf field carries {source, ref, as-of} or a reason, 78.3% of 30,269 provenance-wrapped fields carry a value, 16 entities link to the roster both ways, `validate_census.py` runs in the gate. Gaps: "Evaluate this fund" is a paragraph, not an action (`site/js/census.js:245-252`). Accession numbers are not hyperlinked to EDGAR. `site/census.data.js` and `site/census/` are build outputs not listed in `.gitignore`. The exchange flag is not share-class aware: 6 of 245 entities classified `interval_23c3` carry `listed: true` (recomputed from `data/census/census.json`), which is a contradiction by construction because Rule 23c-3 common shares are unlisted. Example: CIK 1551047 (Total Income+ Real Estate Fund, an interval fund) shows exchange NYSE and ticker BPRE, which is its listed preferred class, and the Universe screener displays the fund as "Listed: yes". The same class-blindness will misfire on any BDC or REIT with listed preferred or baby bonds.

### 3.11 What a 3(21) advisor cannot do today (the design-partner offer)

The offer in the outreach going out September 8 is "free early access to run their own fund lineup through the six-factor grid and benchmark engine, a seat shaping the rubric." Against the code:

1. Cannot evaluate their own fund. No upload or input. The path is clone repo, Python env, `promote.py` (refuses any CIK not already in the census, `:77-80`), hand-extract ~51 cells into CSV + JSON, edit `build_facts.MAPPING/COHORT_META/AS_OF`, `tark_liquidity.LIQUIDITY_PROFILES`, `tark_benchmark.PRODUCT_PROFILES`, `fetch_edgar.PRODUCTS`, `tark_cohort.COHORTS`, plus `views.js:111-112, 991-1007` and `workbench.js:16-23`, rerun 6 scripts, rebuild, force-push. Product identity is redeclared in at least 8 places.
2. Cannot add a plan (hand-built JSON from DOL bulk files, `plan_order` hardcoded at `build_site.py:488`).
3. Cannot edit a rubric weight, threshold or candidate menu (Python constants).
4. Cannot supply a benchmark proxy or index series.
5. Cannot sign off a cell (UI is read-only, instructs editing CSVs), annotate, dissent or attach a note.
6. Cannot export a committee packet. "Packet" is `window.print()` over localStorage pins (`workbench.js:492`). The memo is prebuilt for one plan.
7. Cannot share with a committee. Copy-link shares hash state, pins and scenarios are per-browser, no accounts, roles, comments, approvals or audit trail.
8. Cannot evaluate a TDF sleeve or CIT (cells 3.5, 2.8, 4.9 are "n/a - CIT only" for all 16, the liquidity match assumes a standalone DIA, `tark_liquidity.py:211-216`).
9. Cannot open a cited source document (raw filings not distributed).
10. Cannot run PME on real cash flows (two-point flows only).
11. Cannot restrict access (public static site).

### 3.12 Rule alignment (checked against 91 FR 16088 / proposed § 2550.404a-6)

- Factor names match the rule. Good.
- The performance and fees factors both require the fiduciary to "consider a reasonable number of similar investment alternatives." That makes the peer cohort central to the rule, not a secondary feature. The engine currently rejects the cohort as "outranked" by a daily ETF in every private-credit selection.
- The benchmark factor defines a meaningful benchmark as one with "similar mandates, strategies, objectives, and risks" and states "no single benchmark is appropriate for all designated investment alternatives." The rubric puts 6 of 12 points on investability, data quality and provider independence, none of which appear in that definition, and lets a benchmark with strategy_match 0 pass.
- The safe harbor covers initial selection only, not monitoring (the DOL says separate guidance will follow). No surface in the demo states this scope, and nothing in the product distinguishes selection-time evidence from monitoring-time evidence.
- The DOL expects the main channel for alternatives to be target-date funds. Ferreira said the same in discovery. The product cannot represent a sleeve.
- Complexity factor: the fiduciary must "determine that it has the skills, knowledge, experience, and capacity" or "seek assistance from qualified professionals." Cells 6.6 and 6.8 (plan operational fit, fiduciary capacity self-assessment) are n/a for all 16 products. This is the factor that most naturally belongs to the 3(21) advisor persona, and it is empty.

---

## 4. What the pitch says that the code does not do

| Claim (where) | Reality |
|---|---|
| "12-point rubric" (UI, memos, app.py) | 5 criteria, 11-point ceiling, max awarded 9 |
| "any product x any of 5 proxies x any window" (`BUILD_REPORT_3.md:45`) | 6 of 16 products, precomputed lookup |
| "PME everywhere: all six products" (`BUILD_REPORT_3.md:51`) | Written at 6, shipped at 16 |
| "Lane C fed: peer cohorts now score on real composites" (`BUILD_REPORT_4.md:69-71`) | Composites never enter scoring |
| Self-declared benchmark "always a candidate" (`benchmark_methodology_skeleton.md:15`) | Field defined, never read |
| "HUMAN reads and extracts, CF2 verifies" (`extraction_worksheet.md:2`) | 814/864 rows extracted by Claude, 0 verified |
| "42/44 confirmed by an independent re-location pass" (Coverage view) | Agent pass, 6 products, 10.8% of extracted cells |
| "Pre-commit runs 7 gates" (`INVESTOR_DEMO.md:65`) | 9 at line 94, opt-in, no CI |
| "864/864 resolved" (`BUILD_REPORT_5.md`) | Counts 237 n/a and 59 partial as resolved |
| Stack: FastAPI, Postgres, object storage, React/TS, LLM + OCR ingestion (Tark record, YC framing) | Static site from a Python build script, Streamlit legacy, no LLM call in the repo |
| "Machine-enforced anonymization" | Display-layer screen of 5 tokens (`build_site.py:405-417`). `data/plans/*.json` commit sponsor names and EINs. `test_frontend.py:31` and `test_app.py:19` list the four sponsors verbatim in a public repo |

---

## 5. Prioritized fix plan

Severity key: P0 = wrong or broken on an investor-facing surface, fix before any demo. P1 = engine outputs that do not mean what they claim. P2 = the October milestone. P3 = structural.

### P0, correctness and copy (1 to 2 days)
1. Fix `gloss()` HTML corruption and add a generated-HTML validity check to the frontend gate.
2. Remove all "six products" copy (Roster, Screener footer, Coverage hero, `app.py`, `run_supplement.py`, cell 5.4 text for four products). Regenerate `taxonomy.json` from the live record in the build and delete the hardcoded `CROSSCHECK` dict or label it truthfully (agent pass, 6 products, 44 cells).
3. Fee Matrix: drive the bar chart from the typed facts layer (net expense ratio), not the first-number regex. Replace regex headline chips with the typed fact or, when the cell is an absence, a labeled "none" chip. Add a test that every bar equals the facts value or is absent.
4. Analysis Lab and De-smoothing Lab: never silently substitute another product. Either render the selected product or show "no daily series for this product" with the list of products that have one.
5. Coverage rings: one coverage formula, shared by `coverage.py`, `build_site.py` and `app.py`, and `structured` counts as covered everywhere. Show n/a in the denominator or label the ring "of resolvable cells".
6. Fix the dangling `anchor_plan.json` citations and the 16 percentile-tie contradictions (rank ties as the same percentile).
7. Delete the 16 dead legacy liquidity files and the dead bundle keys, or wire them.

### P1, make the engines mean what they say (1 to 2 weeks)
8. PME window alignment: refuse or clip the window to the intersection of fund and proxy coverage, print both effective windows, and add a test that fails on any window starting before the proxy series. Recompute and republish every affected number (amg_pantheon, pflex, cion_ares) and note the correction in the crosscheck log.
9. Day-count annualization.
10. Benchmark rubric v2, aligned to the rule's definition: make strategy and risk match load-bearing (a candidate with strategy_match 0 cannot be primary), make risk_liquidity_match reachable at 3, read product characteristics (leverage, dealing cadence, pricing class, track length, declared benchmark) from the facts layer rather than hand-typed integers, implement Lane A (self-declared benchmark always scored, sourced from cell 5.1), fix the CDLI independence flag per product, require primary != secondary series, feed Lane C composites into scoring, and make escalation computable (no candidate at or above threshold after the strategy gate).
11. Liquidity verdict v2: a verdict that depends on capacity vs demand (add a failing state such as "misaligned" when capacity is 0 or stressed demand exceeds capacity), reads cadence, cap and gating history from cells 3.1/3.3 rather than a parallel Python dict, and varies with plan inputs.
12. Memo v2: generated per plan x product, includes the liquidity verdict, real findings (typed facts + the cell's headline sentence, not truncated prefixes), a recommendation section, EDGAR-linked citations, a case-law section sourced from a dated cell 5.7, and a provenance paragraph that states the true verified count.
13. Populate 5.6 and 5.7 with the engine's own artifacts instead of n/a.

### P2, the October milestone: an advisor runs their own fund (3 to 5 weeks)
14. Single product registry. One JSON is the source of truth for identity, cohort, liquidity profile inputs, benchmark profile and chart config. Delete the 8 duplicate registries.
15. Ingestion pipeline that actually exists in code: given a CIK, fetch the primary filings from EDGAR, extract the 54-cell scaffold with an LLM using structured output (cell id, value, verbatim quote, document, section, accession, page/anchor), write straight into the evidence CSV + product JSON at status extracted-unverified, run the validator. This is the feature the YC narrative and the design-partner offer already claim.
16. Make the census's "Evaluate this fund" a real action that triggers the pipeline (locally at first, via a small FastAPI service if hosting is available).
17. Plan intake: a form or JSON upload for plan inputs beyond Form 5500 (outflow rates, QDIA, glidepath, menu), driving the liquidity model.
18. A verification UI that writes `verified` + signer + date back to the CSV/JSON (or a PR), so Justin's CF2 pass can happen in the product instead of a spreadsheet.
19. Committee packet: server- or build-side docx/pdf that composes the six-factor record, benchmark card, liquidity verdict and memo for the selected plan.

### P3, structural
20. TDF/CIT sleeve representation: a "vehicle" concept that holds allocations to products, with the six factors rolled up at the sleeve level. This is what both Ferreira and the DOL say the real unit of decision is.
21. Selection vs monitoring: label every artifact with the evaluation date and scope, since the safe harbor covers selection only.
22. Link every accession number to its EDGAR URL, distribute or host the raw filings, and purge laptop paths from the record.
23. CI that runs the 9 gates on every push, and a real anonymization story (sponsor names and EINs out of the public repo, not just out of the bundle).
24. Retire Streamlit or make it a thin consumer of the same bundle.

---

## 6. Decisions only Oscar can make (these change the order above)

1. Who is the demo for on September 8: the LOI recipients (3(21) advisors) or investors (1789 Capital)? Advisors care about 3.11 and P2. Investors care about P0 and the T1/T2/T3 story. The current build is tuned for investors and is being offered to advisors.
2. Is the end-of-October target still "an advisor runs their own funds"? If yes, P2 items 14 to 16 are the whole of October and P1 item 10 must be scoped down. If no, say so in the outreach before the September 8 sends go out, because the offer as drafted cannot be honored by this code.
3. Does the benchmark rubric change (P1 item 10) need the design partners' input ("a seat shaping the rubric") before it is rewritten, or should v2 ship as the default they then critique?
4. Standalone product vs sleeve (P3 item 20): building the sleeve model now changes the data model for everything else. Deferring it means the demo keeps evaluating the thing the DOL says is not the main channel.
5. Stack: the Tark record describes FastAPI/Postgres/React. Either the narrative changes to "static, build-time, honest" or the P2 service is the first real backend. Do not let an investor discover the difference.
6. Verification: 0 of 406 after eight weeks. This is a founder-hours problem, not a code problem. Decide who verifies the Tier 1 queue (10 cells) before September 8 so at least the numbers spoken aloud in the demo carry a human signature.

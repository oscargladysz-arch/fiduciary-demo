# Tark Build Report 2 — Coverage Max-Out + Design Pass
**2026-08-09 · branch `design-pass` merged to `main` · rollback tag `pre-design-pass`**

## 1. Coverage taxonomy: before → after

| | before (v10) | after |
|---|---|---|
| Evidenced (extracted + partial + fetched) | 149 cells | **176 cells (54%)** |
| Computed (pipeline, with artifact provenance) | 10 | **59 (18%)** |
| Documented-unavailable (specific, true reasons) | 36 | **89 (27%)** |
| Bare `pending` | **129** | **0** |

**The line the UI displays: "54% evidenced · 18% computed · 27% documented-unavailable · 0 unresolved."** (`data/analytics/taxonomy.json`, rendered on Coverage & Provenance.)

Method: a 12-agent extract+adversarial-verify workflow resolved 70 cells from filings (every quote machine-checked against stripped filing text); 48 cells became `computed`/`fetched` via pipeline extensions (stressed redemption scenarios, universe fee percentile, stress windows, dxyz premium decomposition, engine-lane artifacts); the remainder carry specific documented reasons (LP-only economics, workflow cells, attestation-gated fact sheets, granularity limits). `pending-verify` was needed zero times.

Notable finds along the way:
- **BREIT prints a full monthly NAV table in its 10-K** (Jan 2023–Dec 2025, Class I). Extracted, adversarially verified against raw HTML, stored at `data/series_monthly/breit_nav.csv` → de-smoothing now runs on BREIT: **ρ = 0.483 (heavy smoothing), observed 2.41% → de-smoothed 4.12% ann. vol, −7.9% NAV-path drawdown** — the quantitative counterpart of its 2022–24 gating history.
- **kkr_kpec + breit benchmark selections now exist** (the last faked-nothing gap): K-PEC → PSP primary, **KS-PME 0.8964 / −4.58%/yr**; BREIT → VNQ primary (NCREIF ODCE secondary, honestly labeled data-not-held), **KS-PME 0.9073 / −3.19%/yr** — both windows fully on-record (BREIT's 2023/2024 returns fetched from its prior two 10-Ks, now in `data/raw/breit/` + manifest). The engine does not flatter roster products.
- **Methodology correction (disclosed):** displayed index growth was month-end-sampled while KS-PME anchored daily — windows starting on non-trading days silently dropped the first partial month. Both sides are now daily-anchored. Effect: cclfx KS-PME 1.2519 → **1.2532** (+3.21 → +3.22%/yr); hl_paf unchanged (1.9565). All tests, memos, and the JS port updated in lockstep; parity re-verified in-browser.
- DXYZ quarterly NAV table could NOT be extended: the NPORT-P has no NAV-per-share element (documented in the record), and Jan–May 2026 monthly NAVs are printed nowhere — not interpolated.

## 2. Design tokens summary (`site/app.css`)

- **Purple ramp** `--plum-50…950`: #593380 saturated primary (actions/accents), #331d49–#221232 aubergine (headers/nav), pale tints for surfaces — over warm neutrals (paper #faf8f5, ink #262130, warm hairlines).
- **Status colors moved OFF the brand axis** — `computed` re-hued from violet to **teal (#14636d)** so pipeline outputs never read as brand decoration; verified/extracted green, partial amber, fetched steel, escalation crimson, ILLUSTRATIVE burnt-orange badge. All pairings AA on their tints.
- **Type:** Fraunces 600/700 (display headings) + Inter 400/500/600 (text; tabular numerals via `font-variant-numeric` for every figure). Committed woff2 via `@font-face` — zero runtime CDN calls; OFL licenses in `site/fonts/LICENSES.txt`.
- **Components:** 4px spacing scale; ledger table (rejection log as numbered, ruled entries with full rubric rationale printed); **formal-notice** component for escalations (double-rule border, small-caps head); availability-honesty `nochart` block; glossary term chips (dotted underline, hover definition — plain language primary, term-of-art secondary); coverage rings; motion 160–220ms ease only. No gradients, no glassmorphism, no emoji.
- **Numbers-first:** every cell renders headline figure → one plain-language line → full sourced text + provenance behind a "Full text & provenance" disclosure; per-factor rollup strips with anchor links; view intros cut to one sentence; the rule citation lives behind an "Authority" disclosure. ILLUSTRATIVE labels kept prominent everywhere scenario math shows.

## 3. Chart inventory, by data tier (all generated from the bundle)

| Tier | Products | Visuals |
|---|---|---|
| Daily series | cclfx, dxyz | full price/NAV lines (evaluation header chart); DXYZ price-vs-NAV log chart with filed NAV points + premium table; CCLFX observed-vs-de-smoothed monthly series; PME explorer (monthly window slider) |
| Printed monthly | breit | monthly NAV path chart; de-smoothing lab (ρ 0.483 exhibit); NAV-path drawdown stat |
| Filing-annual | hl_paf, stepstone_spm, kkr_kpec (+breit annual returns) | fiscal-year NAV/share charts from `data/series_annual/*.csv`, labeled "annual disclosure cadence"; PME explorer with fiscal-year window steps |
| Per plan × product (24) | all | capacity-vs-demand bar visual (filed capacity vs illustrative base + stressed demand), live with sliders |
| Cross-product | all | fee TER bar chart (no-TER wrappers say so in place); coverage rings ×6; taxonomy donut; crosscheck integrity tiles |
| Impossible → reason rendered | hl/kkr/spm monthly diagnostics; dxyz de-smoothing | availability-honesty blocks with the documented reason, same voice as the DXYZ escalation |

## 4. Punch list status
- Manufacturer plan relabeled → "US industrial manufacturer 401(k) plan (~$0.8B, OH)" ✅
- Chart tooltips (hover values + guide line, all line charts) ✅
- Per-factor anchors (rollup strip) ✅
- `docs/screenshots/` refreshed (10 shots, new design, incl. the BREIT ρ exhibit) ✅
- `docs/demo_script.md` + `docs/INVESTOR_DEMO.md` updated ✅
- e2e extended: details-open anonymization sweep (240 combos), glossary chips, kkr/breit selections asserted, new components (ledger, notice, rings, donut, capacity visual), JS↔Python parity re-verified after the anchoring correction ✅ — suite is now 66 checks; the mid-build hook rejection (stale `#o_dpct` locator) is the gate doing its job.

## 5. Deferred, with reasons
- **BREIT monthly Jan–May 2026 NAVs** — printed nowhere (10-Q carries only the Jun 30 point); not interpolated by policy.
- **hl_paf / stepstone_spm / kkr_kpec monthly series** — fact sheets sit behind investor-attestation gates (not free-public); documented per cell 1.6/1.7/4.8. If the founders obtain them legitimately, the de-smoothing lab picks them up automatically (tier-driven).
- **NCREIF ODCE series ingestion** — member/subscription distribution; kept in the menu as honestly-rejected/secondary-cited.
- **Glossary coverage** — 36 terms; grows by editing one dict in `build_site.py`.

## 6. Gates & deploys
Hook (unchanged 7 steps, assertions strengthened): validator · analytics · benchmark · memo · Streamlit suite · site build (anonymization refusal) · frontend e2e. All green on the merge commit. Deploys: GitHub Pages redeployed from the merged build; Streamlit auto-redeploys from `main` (plan relabel + data updates flow through).

Build-chat sync required: zip the full repo minus data/raw (`zip -r ~/Desktop/tark_repo_sync2.zip . -x 'data/raw/*' -x '.venv/*' -x '.git/*'`) and upload to the build chat for review.

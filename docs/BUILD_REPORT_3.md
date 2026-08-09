# Tark Build Report 3 — The Workbench Pass
**2026-08-09 · branch `workbench` merged to `main` · rollback tag `pre-workbench`**

Founder brief: "there is no Bloomberg for alts" — build the half we can truthfully
own: the workbench (comparison, screening, custom analysis, keyboard speed,
shareable state) on Tark's fully-resolved, citation-carrying dataset, with
provenance preserved through every interaction.

## 1. The structured-facts layer (foundation)
- `data/facts/<product>.json` — **126 typed fields** (21 × 6): fee rate/base enums,
  incentive structure, early-repurchase terms, cadence/caps, gate history, tax
  form, auditor/Big-4, TER, net assets, inception/track record, engine outputs,
  per-plan liquidity verdicts. Every field: `{value, source_cell, status}` with
  status mirroring the cited cell; nulls carry the true reason.
- **Validator extended** (`validate_facts`): every field must cite a real cell;
  non-null values only from extracted/verified/computed/fetched cells; numeric
  fields must appear verbatim in the cited cell's text unless flagged `approx`.
- **Adversarial verification of the mapping** (6 agents): 109 OK, 13 flagged,
  **4 WRONG — all fixed**, including the pass's biggest catch:
  **hl_paf's incentive fee was restructured 2025-03-14** (10.00% of quarterly
  net profits over a Loss Recovery Account; the 2021 12.50% deal-by-deal terms
  the record carried were superseded — "12.50" has zero hits in the FY2026
  N-CSR). Cell corrected with the supersession documented; memo regenerated;
  demo script updated. Three `gate_history: false` claims were downgraded to
  honest nulls (the cells evidence offer *continuity*, not proration *absence*).
- Stale engine prose refreshed (cclfx 1.8/5.5 still carried pre-correction
  1.2519); facts pull engine numbers live from artifacts, never retyped.

## 2. Comparison + Screener
- **Comparison**: 2–4 products side-by-side (18 fact rows + per-plan verdict +
  rejection-ledger links); amber = material difference, red = trap (leverage-
  inclusive bases, K-1, gate history, sub-1.0 PME); every value cites its cell.
  URL-addressable: `#view=compare&compare=hl_paf,breit&plan=…`.
- **Screener**: dense sortable grid over the facts — filters for wrapper, fee
  base, tax form, gate history, Big-4, verdict tier, PME range; column chooser;
  honest gaps (dash + reason on hover). **Filter correctness is e2e-tested**
  (tax=K-1 → exactly kkr_kpec; base=managed_assets → exactly hl_paf).
  The **verified-only** filter renders the honest line: *"independent human
  verification in progress: 0 of 148 typed facts verified."*
- **URL state is keys/IDs only, validated against whitelists on read** — a
  shared link is leak-proof by construction; free text (search queries) never
  enters the hash. Same-document hash navigation re-renders (`hashchange`).

## 3. Custom analysis with the justification layer visible
- **Benchmark swap (the thesis screen)**: any product × any of 5 proxies × any
  window. The engine's rubric verdict renders BESIDE every user choice — full
  scores/reasons for on-menu proxies, and for off-menu picks the truthful
  *"no rubric basis — user-configured analysis only."* Standing window-
  sensitivity disclosure + USER-CONFIGURED banner on all recomputation.
  (Try cclfx × SPY: PME 0.59, and the engine says why that's unsound.)
- **PME everywhere**: all six products at honest granularity — monthly sliders
  (cclfx, dxyz w/ price-series warning), fiscal-year steps (hl_paf, breit),
  fixed disclosed-ITD windows (kkr, spm) with the reason displayed.
- **De-smoothing ρ override**: slider on cclfx + breit; estimated ρ marked;
  overrides labeled USER-CONFIGURED with reset; "what de-smoothing cannot
  detect" caption retained.
- **Liquidity scenario workbench**: named scenarios (localStorage), up to 3
  compared side-by-side with live demand/thin-headroom computation, persistent
  ILLUSTRATIVE labels.
- **Analysis tables** (Python-first → JS parity): calendar-year returns vs
  proxy, top-3 drawdown episodes (with recovery dates), rolling 12-month
  return/vol + OLS beta. New `tark_analytics` functions with hand-checkable
  unit tests; JS ports parity-tested on the same toys PLUS committed real-data
  checkpoints (breit NAV-path drawdown −7.93; cclfx CY2022 return). Annual-tier
  products render the reason intra-year tables can't exist.

## 4. Workbench ergonomics
- **Cmd+K palette**: views, products, plans, cell IDs ("2.7 kkr"), commands
  ("compare hl_paf breit", "density compact"), search handoff; full keyboard.
- **Evidence search**: full-text over all cell values/quotes, results with
  status chips + citations; queries stay in memory (never URLs).
- **Packet**: pin cells (⌖) and view-snapshots; reorder; print stylesheet for a
  clean packet; docx boundary documented honestly in the UI (per-product memos
  remain the prebuilt artifacts; nothing is posted anywhere).
- **Density toggle** (comfortable/compact) + **analyst landing** (screener).
- **Copy-link** affordance on every configured surface.

## 5. Verification surface + gates + perf
- `docs/verification_queue.md` (new): 31-item queue, demo-load-bearing first;
  the Verification view renders it live with per-product progress computed from
  statuses — it moves as the human pass lands in the CSVs.
- e2e grew to **96 checks**: palette entries, URL round-trips (encode → reload →
  identical view), sponsor sweep incl. generated URLs, facts provenance
  spot-checks, screener filter correctness, comparison diff/trap rendering,
  swap-lab off-menu honesty, ρ-override labeling, parity for every new
  function, **perf budget: bundle ≤ 1.2MB (actual: 763KB)**. Zero external
  requests; fonts committed; localStorage-only persistence.
- Mid-build the hook rejected two commits (schema drift, stale locator) —
  the gate wall doing its job.

## 6. Deferred, with reasons
- cclfx/kkr/breit aggregate net-assets facts: printed values sit in partial
  cells — Tier-3 verification queue items; facts unlock when cells firm up.
- Palette fuzzy-match is substring-only; command grammar minimal (by design
  for this pass).
- Packet docx composition remains the prebuilt per-product memos (the packet
  itself exports via print stylesheet) — client-side docx assembly deferred;
  boundary stated in the UI.
- Screener virtualization (600-row scale) not needed at n=6; column/filter/URL
  architecture already generalizes.

Build-chat sync required: `zip -r ~/Desktop/tark_repo_sync3.zip . -x 'data/raw/*' -x '.venv/*' -x '.git/*'` and upload to the build chat for review.

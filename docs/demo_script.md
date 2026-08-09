# Tark Demo Script — 7 minutes (design-pass build)
### Setup: docs/INVESTOR_DEMO.md reset steps done; browser on the Pages URL, Reference Plans view, tech/media plan selected. Fallback: docs/screenshots/.

**0:00 — Reference Plans.** "Four real 401(k) plans from public Form 5500 filings, anonymized by machine-enforced rule. Numbers first: a ~$570M tech plan, a $9.8B consulting plan where 58% of accounts are alumni, a $1.6B restaurant plan where most actives hold no balance, a $790M industrial plan. The plan you pick drives every verdict."

**0:45 — Coverage & Provenance.** "Before any analysis: the state of the record. *54% evidenced, 18% computed, 27% documented-unavailable, zero unresolved.* Every one of 324 cells is either cited to a filing, computed by the pipeline, or carries a specific reason it cannot be public-sourced. And the integrity stat: an independent cross-check re-located 44 cells, confirmed 42, caught 2 errors we corrected in the open. Zero cells are human-verified yet — the record says so itself."

**1:30 — Six-Factor Evaluation (hl_paf).** "Every cell leads with its figure; the prose is one click away, and jargon defines itself on hover." Open 2.1's source: *"1.40% — on Managed Assets, leverage-inclusive. Filing, section, verbatim quote, extractor, and the empty verified-by line a human still has to sign."* Point at the rollup strip: *"six factors, evidenced counts, one click each."*

**2:15 — Fee Matrix.** "The bar chart is only the funds that HAVE an expense ratio — where there's no TER line, the chart says so instead of faking one. Red chips: DXYZ charges 2.50% on GROSS assets including borrowings; K-PEC issues K-1s — StepStone advertises 1099s. Same factor, opposite answers, all cited."

**3:00 — Benchmark Selection (cliffwater_cclfx).** "Four lanes, 12-point rubric, and the rejection LEDGER — every rejected candidate numbered, with its full rubric rationale printed. The CDLI is the most strategy-exact index and it's published by the fund's own adviser: independence 0/2, on the record. KS-PME 1.2532, +3.22% alpha." Download the memo.

**3:45 — Benchmark Selection (kkr_kpec, then breit).** "New since last build: the two 10-K wrappers now have full selections — and the engine is honest when the answer is unflattering. K-PEC: PME 0.90 vs listed PE. BREIT: PME 0.91 vs listed REITs, with NCREIF ODCE as secondary — cited but honestly labeled as data-not-held. No product gets a free pass because it's on the roster."

**4:15 — DXYZ.** "And when no benchmark is defensible, a FORMAL NOTICE, not a hedge." Click through to the chart: *"$8-ish to $99.79 to −90.3%, red dots are the fund's own filed NAV crawling from $5 to $24.56. The gap is the premium; benchmarking the price benchmarks the premium."*

**5:00 — Liquidity Match (cclfx, tech plan → consulting plan).** "Wrapper capacity is a filed fact; demand is an adjustable ILLUSTRATIVE scenario — watch the bars." Switch to the consulting plan: *"58% alumni tail: demand eats two-thirds of capacity — THIN HEADROOM — and under the stress test it EXCEEDS the wrapper entirely. Same fund, two plans, two answers, and the plan's own 5500 codes changed the structural reasoning."* Drag a slider: bars move live.

**5:45 — De-smoothing Lab.** "The smoothing story now has two exhibits. CCLFX: ρ 0.139, mild. BREIT — from its OWN printed monthly NAV table: ρ 0.483, heavy; observed 2.4% de-smooths to 4.1%. That's the quantitative counterpart of its gating history: smoothed NAV, real redemptions. And for the funds where this diagnostic can't run, the reason renders where the chart would be."

**6:15 — PME Window Explorer.** "Our methodology's own disclosure, interactive: drag the window and watch 1.2532 move. Everyone else hides window-sensitivity; we lead with it — the committed number uses the full disclosed window, and the browser runs the same parity-tested code as the engine."

**6:45 — Close.** "A complete record — zero unresolved cells — with its rejections, its stress tests, its corrections, and its unverified-by-a-human honesty all on the surface. This is the workflow layer for the rule's effective date."

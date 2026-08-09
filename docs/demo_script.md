# Tark Demo Script — 7 minutes (workbench build)
### Setup: reset per docs/INVESTOR_DEMO.md; land on the Screener (analyst default). Fallback: docs/screenshots/.

**0:00 — Screener.** "A Mercer alternatives specialist told us 'there is no Bloomberg for alts.' Here's the half we can own today: the workbench. Six products, typed facts, every value with a source button. Watch—" filter tax form to K-1: *"one row. K-PEC is the only K-1 issuer on the roster — that's a screening answer with a citation, not a claim."* Filter fee base to MANAGED assets: *"one row again — the leverage-inclusive trap, isolated in two clicks. And the gaps are honest: the dashes carry the REASON there's no number."*

**1:00 — Verified-only.** Toggle it: *"almost nothing. 'Independent human verification in progress: 0 of 148.' We ship that filter empty on purpose — it's the most honest pixel in fintech, and it fills as our verifier signs rows in the evidence CSVs."*

**1:30 — Comparison.** Cmd+K → "compare hl_paf breit": *"synchronized side-by-side; amber = material difference, red = trap. Fee bases differ; BREIT's gate history is red; sub-1.0 PME is red. Every cell cites its source. And this exact comparison is a URL — share it; the link physically cannot contain a sponsor name because URL state is IDs only."*

**2:30 — Analysis Lab: the thesis screen.** Product CCLFX. *"The engine chose BKLN: PME 1.2532."* Now swap the proxy to SPY: *"PME collapses to 0.59 — and look at the right panel: the engine tells you SPY is OFF ITS MENU for private credit — no rubric basis, user-configured analysis only. Bloomberg gives you the calculator. We give you the calculator AND the judgment, side by side, always. That's the product."* Swap to a menu proxy: the rubric scores render with full reasons.

**3:45 — Analysis tables.** Still in the lab: calendar-year returns vs proxy, top-3 drawdowns, rolling 12-month with beta — every function implemented in Python first with hand-checkable tests, ported to the browser with parity tests on committed checkpoints. Annual-tier products say honestly why intra-year tables can't exist.

**4:30 — De-smoothing Lab, ρ override.** BREIT: *"estimated ρ 0.483 from its own printed NAVs. Drag the override — labeled USER-CONFIGURED, estimated value marked on the track. You can stress OUR assumption; you can't silently replace the record."*

**5:15 — Liquidity scenarios.** Consulting plan × CCLFX: *"save a scenario, compare three side by side — all under the ILLUSTRATIVE banner, computed live against the plan's filed numbers. The stress column shows demand EXCEEDING wrapper capacity."*

**6:00 — Verification view.** *"The human pass is a product surface now: 0 of 148 verified, the queue ordered by demo-load-bearing cells first. When our verifier flips rows in the CSVs, these bars move. The workbench never gets ahead of the record — this build even CAUGHT a stale fee: Hamilton Lane restructured its incentive fee in March 2025; our adversarial facts check found it, and the screener now shows the current 10% Loss-Recovery terms with the supersession documented."*

**6:45 — Close.** "Comparison, screening, custom analysis with judgment attached, keyboard speed, leak-proof shareable state — the Bloomberg workbench feel, on the one thing Bloomberg never had to prove: provenance on every number."

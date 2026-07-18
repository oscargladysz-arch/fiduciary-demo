# Tark Drop v4 — Increment 2: M0, the Data Contract
### Tested live 2026-07-18. The folder of JSONs is now a validated, single-source-of-truth data layer.

## What's new in v4 (over v3)
1. **`src/tark_data.py` — the M0 library.** One canonical cell registry (54 cells, 6 factors), one status vocabulary, and every loader the rest of the build consumes: `load_products()`, `cells_by_factor()`, `load_anchor_plan()`, `load_series()`, `load_evidence()`, `load_manifest()`. From here on, M2 (analytics), M3 (benchmark engine), M4 (UI), and M5 (memo) import from this module and re-declare nothing. Decision confirmed from the plan: **no SQLite** — six products don't need a database; "SQLite at most" is satisfied by less.
2. **`src/validate_data.py` — the integrity gate.** Checks every product against the registry (cell completeness, element-label drift, status vocabulary, extracted-implies-value-and-source), cross-checks evidence CSVs against product JSONs (catches silent drift between the two), recomputes the anchor plan's derived figures from primitives, and sanity-checks both daily series (ascending dates, positive closes, manifest match). Exit 0/1 — **run it before every commit.**
3. **Proof it bites.** First run: all clean. Then a negative test — two violations deliberately injected — and the validator caught both **plus a third it found on its own** (the JSON/CSV status drift from the injected status change). Restored, clean again. A validator you've only seen pass is a validator you can't trust; this one has turned red on demand.
4. **`src/coverage.py` refactored** onto the shared layer — same numbers (15% total), one source of truth for status semantics.

## Install & run
```
cd ~/Projects/fiduciary-demo
unzip -o ~/Downloads/tark_drop_v4.zip -d .
python src/validate_data.py
python src/coverage.py
git add -A && git commit -m "increment 2: M0 data layer + validator" && git push
```
Expected: `All clean — data contract holds.` then the coverage table (TOTAL 15%).

## The new habit
`python src/validate_data.py` before every commit, forever. When your extraction hour or CF2's verification pass edits an evidence CSV, the validator is what catches a typo'd status or a value-less "verified" before it reaches a demo screen.

## Open human items (unchanged from v3)
Oscar's three short reads (PAF 2.2 + 4.2; CCLFX repurchase % + auditor line) · CF2's verification pass · targeted-read pointers in the CSVs for K-PEC and BREIT tables.

## Next from Claude — Increment 3 (M2 analytics core)
Returns/vol/drawdown, AR(1) de-smoothing, Kaplan-Schoar PME, Direct Alpha — pure functions, unit-tested on hand-checkable toy cases, then run against CCLFX's 1,759-point series and the annual filing data. Your §4 hand-worked PAF example (August window) remains the acceptance test of that code. Nothing needed to start.

## Standing
Gate A: **July 31.** Discovery ledger unchanged.

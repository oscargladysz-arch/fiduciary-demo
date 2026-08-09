# Tark Drop v9 — Crosscheck Integration + Corrections
### Built ON your 2026-08-08 data sync (Claude Code's pass included) — safe to `unzip -o`. All five suites green.

## What's in v9
1. **Both crosscheck discrepancies fixed, statuses honest (`extracted-unverified` — CF2 still adjudicates):**
   - **DXYZ 2.1 (the material one):** the recorded 2.00% fee was the *pre-listing* fee quoted out of era. Corrected to the fee in force since the 3/26/2024 listing: **0.625%/quarter = 2.50% annualized on average GROSS assets including borrowings** — the leverage-inclusive fee-base trap, on the fail case itself. FY2025 fees $3,525,027.
   - **CCLFX 5.1:** rewritten to the filing's own words — the fund **expressly declares NO designated performance benchmark**; the shareholder-report indices are illustrative comparators only. This *upgrades* the demo: the engine constructs where the fund declares none. CDLI sentence now attributed as an external fact, not to this filing. Engine profile updated (`self_declared: None`); selections regenerated — primary/secondary and all numbers unchanged, lane labeling corrected.
2. **Housekeeping from the crosscheck appendix:** seven blank `local_file` fields backfilled · PAF 2.1 carries the 1.50%→1.40% fee-history note · the two absence-inference flags (PAF 3.1, DXYZ 3.1) annotated transparently in the cell text.
3. **All six memos regenerated** — DXYZ's memo now states the corrected 2.50% gross-assets fee; CCLFX's memo carries the no-declared-benchmark finding; PAF's memo now includes the complete incentive-fee terms from Claude Code's pass (12.50% deal-by-deal, 8% preferred, 100% catch-up).
4. **State of the record:** coverage **28%** (63 seeded + 15 partial); 44-cell independent crosscheck complete — 42 confirmed, 2 corrected, 0 unlocatable. `docs/crosscheck_report.md` is CF2's adjudication map.

## Install & run
```
cd ~/Projects/fiduciary-demo
unzip -o ~/Downloads/tark_drop_v9.zip -d .
python src/validate_data.py
python src/coverage.py
git add -A && git commit -m "v9: crosscheck corrections (dxyz fee, cclfx benchmark disclaimer) + memo regen" && git push
```
Hook runs all five suites (~2 min). Then reload the deployed app — Streamlit Cloud redeploys from the push automatically; check DXYZ's Fees tab and CCLFX's Benchmark view for the corrected content.

## CF2's pass — now the only step between this data and "verified"
Procedure per cell: open `docs/crosscheck_report.md` → for Confirmed cells, re-check the anchor phrase in the cited document, then set status `verified` + name/date in `verified_by` in BOTH the CSV and the JSON. The two corrected cells (dxyz 2.1, cclfx 5.1) get his independent read of the corrected language. The TR-gap reconciliation (computed 7.98% vs disclosed 9.34%) remains his written paragraph.

## Standing ledger
Methodology window is OPEN (Aug 8–30): `docs/benchmark_methodology_skeleton.md`, §4 hand-worked PAF PME = the acceptance test. Gate A outcome still unreported. Buyer-demo notes (Nick + two) still the pitch's missing evidence. Second-plan "shortlist" offer stands.

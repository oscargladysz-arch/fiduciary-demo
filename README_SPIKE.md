# Tark Drop v6 — Increment 4: M3, the Benchmark Selection & Justification Engine
### Tested live 2026-07-18. The moat module exists, is unit-tested (32 tests), and has made its first real decisions.

## What's new in v6
1. **`src/tark_benchmark.py`** — four-lane candidate generation (self-declared / asset-class index / peer cohort / PME-construct), the 12-point rubric (strategy match 3 · risk-liquidity match 3 · investability 2 · data quality 2 · **provider independence 2**), primary + secondary selection with a 7/12 threshold, and the **rejection log**: every candidate not selected carries a true, stated reason. "No meaningful benchmark constructible" is a legitimate, documented outcome — not a failure state.
2. **Five index-proxy series** pulled (`spy, urth, bkln, psp, vnq` — 2,010 daily rows each, 2018→now), tagged `role: index_proxy` in the series manifest with an explicit proxy disclosure. Paid indices (Cambridge, CDLI) enter the menu and get **rejected with reasons** rather than silently omitted — the honest version of index-agnostic.
3. **`src/test_benchmark.py` — 32 tests**, including a class the project didn't have before: **truthfulness tests on the audit log itself.** Mid-build, reading the engine's output caught it stamping "below threshold 7" on candidates scoring 8/12 — a false statement in a defensibility record. Fixed; now tested: above-threshold rejections must say "outranked," never "below."
4. **`src/run_benchmark.py`** — writes `data/benchmarks/<product>_selection.json` per product.

## The engine's first real decisions
- **CCLFX:** primary = independent senior-loan proxy (BKLN) at 9/12. Computed over the fund's full life: fund 1.71x vs index 1.37x → **KS-PME 1.25, Direct Alpha +3.21%/yr** — a believable direct-lending premium, and the project's first real PME. **CDLI — the index published by the fund's own adviser — scored 0/2 on independence and sits in the rejection log with the manufacturer-owned-yardstick reasoning.** The BlackRock/Preqin argument, encoded and firing.
- **PAF / SPRIM:** primary = listed-PE proxy (PSP) 9/12; PAF shows KS-PME 1.96, Direct Alpha +14.4%/yr — see the methodology finding below before enjoying that number.
- **DXYZ:** the engine **refuses**. No primary; every candidate rejected with the same true reason (price is premium-driven, decoupled from NAV) and a reasoned escalation naming what's required before any comparator is defensible. The fail case works at engine level.

## Methodology finding #2 (feeds the August doc, §3/§4) — read this one twice
PAF's +14.4%/yr alpha vs listed PE is **window-flattered**: the 5-yr window starts at listed PE's 2021 peak, PSP then crashed ~35% in 2022 while PAF's appraisal-lagged NAV sailed through, and the proxy has barely recovered the start point (1.04x over 5 yrs). Evergreen-NAV vs listed-proxy comparisons are **window-sensitive and smoothing-flattered** — the engine's own output just demonstrated why the suitability memo must carry window-sensitivity and smoothing disclosures next to any PME. §4's worked example should compute PME over at least two windows.

## Install & run
```
cd ~/Projects/fiduciary-demo
unzip -o ~/Downloads/tark_drop_v6.zip -d .
python src/validate_data.py
python src/test_analytics.py
python src/test_benchmark.py
python src/run_benchmark.py
git add -A && git commit -m "increment 4: M3 benchmark engine + 32 tests + first selections" && git push
```
**Update your pre-commit hook** so the new tests gate commits too (one paste):
```
cat > .git/hooks/pre-commit << 'HOOK'
#!/bin/sh
source .venv/bin/activate 2>/dev/null
python src/validate_data.py && python src/test_analytics.py && python src/test_benchmark.py
HOOK
chmod +x .git/hooks/pre-commit
```
(Hooks never push — each co-founder installs locally.)

## Open human items
Standing: Oscar's three short reads; CF2's verification pass + CCLFX TR-gap cross-check; Gate A **July 31**. New color for discovery calls: "our engine rejected the adviser-published index on independence grounds — would your committee?"

## Next from Claude — Increment 5 (M4, the screens)
Streamlit multi-page: anchor plan → product picker → six factor tabs with evidence + citations → the benchmark tab showing the construction and the rejection log → DXYZ failing visibly. Nothing needed to start.

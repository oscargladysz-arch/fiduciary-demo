# Tark Drop v5 — Increment 3: M2 Analytics Core
### Tested live 2026-07-18. The math exists, it's unit-tested, and it has already been run against the real data.

## What's new in v5
1. **`src/tark_analytics.py`** — pure stdlib math, no I/O: period/annualized returns, vol, max drawdown, lag-1 autocorrelation, **Geltner AR(1) de-smoothing**, XIRR (bisection), **Kaplan-Schoar PME**, **Direct Alpha**. Every function documented with the formula.
2. **`src/test_analytics.py`** — 19 hand-checkable tests, all passing: exact AR(1) round-trip (smooth a known series, unsmooth, recover to 12 decimals), PME = 1.0 when a fund exactly tracks its index, Direct Alpha = 0 on the same toy, drawdown/XIRR/resample checks, and a 120-point estimator test (the original 8-point estimator assertion was statistically naive — my test bug, replaced, lesson noted).
3. **`src/run_analytics.py`** — applies the core to the real series and filing data; writes `data/analytics/metrics.json`.
4. **Series schema v2:** `date,close,adj_close`. Raw NAV understates distributing funds (CCLFX pays most of its return as monthly distributions); adj_close is the total-return proxy. Data layer + validator updated; both series re-pulled — CCLFX now spans its full life from inception day (2019-06-05).

## The results (data/analytics/metrics.json)
- **PAF cross-validation, exact:** geometric mean of the five FY returns extracted from its N-CSR = **15.31%** — matching the fund's own disclosed 5-yr average annual return **to the basis point**. Independent reproduction of a disclosed figure from raw inputs. Distribution wedge: TR 15.31% vs NAV-only 12.48% = 2.83pp/yr paid out.
- **CCLFX:** sliced to the fund's 3/31/26 FYE for apples-to-apples — computed ann TR **7.98% vs disclosed 9.34%** (gap flagged, not hidden: Yahoo's adjustment approximates official reinvestment math; **CF2 cross-check vs fund fact-sheet monthly TRs is now a named task**). Observed ann vol 2.11%; lag-1 rho **0.139** (mild); de-smoothed vol 2.45%.
- **DXYZ (the fail case, quantified):** listed 2024-03-26 at $9.00 → peak **$99.79 twelve days later** → trough $9.63 by Aug 2024 = **max drawdown −90.3%**, annualized vol 162.6%, yet cumulative +188.6% since listing (last $25.97). The premium/discount pathology in one row.

## A methodology finding (feeds the August doc, §3)
CCLFX's monthly lag-1 autocorrelation is only 0.139 — de-smoothing widens vol modestly (2.11% → 2.45%), nowhere near the index's 6.15%. Read honestly: **simple AR(1) de-smoothing is not a magic wand here**; the stronger smoothing evidence for private credit is the *level* comparison the fund itself discloses (1.71% vs 6.15%). The design doc's §3 must answer "what de-smoothing can and cannot detect" — this is the first empirical input to that section.

## Install & run
```
cd ~/Projects/fiduciary-demo
unzip -o ~/Downloads/tark_drop_v5.zip -d .
python src/validate_data.py
python src/test_analytics.py
python src/run_analytics.py
git add -A && git commit -m "increment 3: M2 analytics core + tests + real-data run" && git push
```
Expected: contract holds · 19 tests pass · the three result blocks above reproduce on your machine.

## Open human items
NEW for CF2: cross-check CCLFX computed TR vs the fund's published monthly returns (fact sheet) — explain or bound the 1.36pp gap. Standing: Oscar's three short reads; CF2's verification pass; Gate A **July 31**.

## Next from Claude — Increment 4 (M3, the benchmark engine)
Candidate generation (self-declared + index shortlist + peer cohort + PME), the scoring rubric with the provider-independence field, primary/secondary selection, and the rejection log. First step: pull free public index proxies for the candidate menu. Nothing needed to start. Reminder: your hand-worked PAF PME (August, §4) remains the acceptance test of this code.

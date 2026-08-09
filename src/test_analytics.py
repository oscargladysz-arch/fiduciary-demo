"""
Unit tests for tark_analytics — every expected value is checkable by hand.
Run: python src/test_analytics.py   (exit 0 = all pass)
"""
import sys

from tark_analytics import (
    ann_return, ann_vol, beta, calendar_year_returns, cumulative_growth,
    desmooth_geltner, direct_alpha, drawdown_episodes, ks_pme, lag1_autocorr,
    max_drawdown, month_end_points, period_returns, rolling_returns,
    rolling_vol, stdev, xirr,
)

FAILS = []


def check(name: str, got, want, tol: float = 1e-9):
    ok = (got is not None and want is not None and abs(got - want) <= tol)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: got {got}, want {want} (tol {tol})")
    if not ok:
        FAILS.append(name)


def check_true(name: str, cond: bool):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        FAILS.append(name)


# --- primitives ---
check("period_returns up", period_returns([100, 110, 99])[0], 0.10, 1e-12)
check("period_returns down", period_returns([100, 110, 99])[1], -0.10, 1e-12)
check("stdev constant = 0", stdev([0.02, 0.02, 0.02]), 0.0, 1e-15)
check("max_drawdown 120->60", max_drawdown([100, 120, 60, 90]), -0.5, 1e-12)
check("cumulative growth", cumulative_growth([0.10, -0.10]), 0.99, 1e-12)
check("ann_return identity", ann_return([0.05] * 12, 12), (1.05 ** 12) - 1, 1e-9)

me = month_end_points([("2024-01-05", 1.0), ("2024-01-31", 2.0),
                       ("2024-02-10", 3.0), ("2024-02-28", 4.0)])
check_true("month_end picks last of month",
           me == [("2024-01-31", 2.0), ("2024-02-28", 4.0)])

# --- AR(1) round-trip: smooth a known series, unsmooth, recover it ---
true = [0.02, -0.01, 0.03, 0.015, -0.005, 0.02, 0.01, 0.025]
rho = 0.4
obs = [true[0]]
for t in range(1, len(true)):
    obs.append((1 - rho) * true[t] + rho * obs[t - 1])
recovered, _ = desmooth_geltner(obs, rho)
check("AR(1) round-trip recovers true[1]", recovered[0], true[1], 1e-12)
check("AR(1) round-trip recovers true[-1]", recovered[-1], true[-1], 1e-12)
check_true("desmoothing raises vol on smoothed series",
           stdev(recovered) > stdev(obs[1:]))
# --- estimator test on a statistically adequate sample (120 points) ---
# (estimating autocorrelation from 8 points is noise; the 8-point block above
#  tests the FORMULA via exact round-trip, this block tests the ESTIMATOR)
import random
random.seed(0)
true_long = [random.gauss(0.008, 0.02) for _ in range(120)]
obs_long = [true_long[0]]
for t in range(1, len(true_long)):
    obs_long.append((1 - 0.4) * true_long[t] + 0.4 * obs_long[t - 1])
rho_est = lag1_autocorr(obs_long)
check_true("estimated rho in plausible band on n=120",
           0.25 < rho_est < 0.55)
rec_long, _ = desmooth_geltner(obs_long)  # rho estimated internally
check_true("desmoothing collapses autocorr toward 0",
           abs(lag1_autocorr(rec_long)) < 0.15)
check_true("desmoothing raises vol (n=120)",
           stdev(rec_long) > stdev(obs_long))

# --- XIRR: -100 then +110 one year later = ~10% ---
irr = xirr([("2020-01-01", -100.0), ("2021-01-01", 110.0)])
check("xirr one-year 10%", irr, 0.10, 3e-3)  # act/365.25 day count wiggle

# --- PME / Direct Alpha toys ---
idx_up = [("2020-01-01", 100.0), ("2021-01-01", 150.0)]
# fund exactly tracks index: invest 100, worth 150 at T
track = [("2020-01-01", -100.0), ("2021-01-01", 150.0)]
check("PME = 1 when fund tracks index", ks_pme(track, idx_up), 1.0, 1e-12)
check("Direct Alpha = 0 when fund tracks index",
      direct_alpha(track, idx_up), 0.0, 3e-3)
# fund beats index: worth 180 vs index 1.5x
beat = [("2020-01-01", -100.0), ("2021-01-01", 180.0)]
check("PME = 1.2 on outperformance", ks_pme(beat, idx_up), 1.2, 1e-12)
check_true("Direct Alpha > 0 on outperformance",
           (direct_alpha(beat, idx_up) or 0) > 0.10)
# flat index: PME reduces to (dist + nav) / contrib
idx_flat = [("2020-01-01", 100.0), ("2021-01-01", 100.0)]
mixed = [("2020-01-01", -100.0), ("2020-07-01", 30.0), ("2021-01-01", 90.0)]
check("PME flat-index = simple multiple", ks_pme(mixed, idx_flat), 1.2, 1e-12)

# --- workbench table math (hand-checkable toys) ---
# calendar years: 100 -> 110 (2023) -> 99 (2024): +10%, -10%
cal = calendar_year_returns([("2023-01-31", 100.0), ("2023-12-29", 110.0),
                             ("2024-06-28", 120.0), ("2024-12-31", 99.0)])
check_true("calendar years labels", [y for y, _ in cal] == ["2023", "2024"])
check("calendar 2023 = +10%", cal[0][1], 0.10, 1e-12)
check("calendar 2024 = -10%", cal[1][1], -0.10, 1e-12)

# drawdowns: 100,120,60,90,130,110 -> deepest 120->60 (-50%), then 130->110
eps = drawdown_episodes([("d1", 100.0), ("d2", 120.0), ("d3", 60.0),
                         ("d4", 90.0), ("d5", 130.0), ("d6", 110.0)], 3)
check("deepest drawdown -50%", eps[0]["depth"], -0.5, 1e-12)
check_true("deepest episode peak/trough dates",
           eps[0]["peak_date"] == "d2" and eps[0]["trough_date"] == "d3"
           and eps[0]["recovery_date"] == "d5")
check("second drawdown 130->110", eps[1]["depth"], 110 / 130 - 1, 1e-12)
check_true("second episode unrecovered", eps[1]["recovery_date"] is None)

# rolling: returns [10%, -10%, 10%], window 2 -> [(1.1*0.9)-1, (0.9*1.1)-1]
rr = rolling_returns([0.10, -0.10, 0.10], 2)
check("rolling[0] = -1%", rr[0], -0.01, 1e-12)
check("rolling[1] = -1%", rr[1], -0.01, 1e-12)
rv = rolling_vol([0.02, 0.02, 0.04, 0.00], 3, 12)
check("rolling vol window count", float(len(rv)), 2.0, 0)
check("rolling vol[0] hand value", rv[0], stdev([0.02, 0.02, 0.04]) * (12 ** 0.5), 1e-12)

# beta: fund = 2x index exactly -> beta 2; fund = index -> beta 1
check("beta of 2x series = 2", beta([0.02, -0.04, 0.06], [0.01, -0.02, 0.03]),
      2.0, 1e-12)
check("beta of identical = 1", beta([0.01, -0.02, 0.03], [0.01, -0.02, 0.03]),
      1.0, 1e-12)

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll analytics tests pass.")
sys.exit(1 if FAILS else 0)

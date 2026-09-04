"""
Tark analytics core (M2)
========================
Pure computational functions — no I/O, no data-layer imports, stdlib only.
Every function is unit-tested in test_analytics.py on toy cases small enough
to check by hand; run_analytics.py applies them to the real series.

Conventions:
- returns are decimal per-period simple returns (0.02 = 2%)
- flows are [(iso_date, amount)]: contributions NEGATIVE, distributions and
  terminal NAV POSITIVE
- index series are [(iso_date, level)] ascending
- notation in docs: `*` multiplication, `/` division
"""
from __future__ import annotations

from datetime import date
from math import sqrt


# ------------------------------------------------------------- primitives
def parse_date(d: str) -> date:
    y, m, dd = d.split("-")
    return date(int(y), int(m), int(dd))


def year_frac(d0: str, d1: str) -> float:
    """Actual/365.25 year fraction between two ISO dates."""
    return (parse_date(d1) - parse_date(d0)).days / 365.25


def period_returns(values: list[float]) -> list[float]:
    """[v0, v1, ...] -> [v1/v0 - 1, ...]"""
    return [values[i] / values[i - 1] - 1 for i in range(1, len(values))]


def month_end_points(series: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Daily [(date, value)] -> last observation of each calendar month."""
    out: dict[str, tuple[str, float]] = {}
    for d, v in series:
        out[d[:7]] = (d, v)  # ascending input: later days overwrite
    return [out[k] for k in sorted(out)]


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def stdev(xs: list[float]) -> float:
    """Sample standard deviation (n - 1)."""
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


# ------------------------------------------------------------ core stats
def cumulative_growth(returns: list[float]) -> float:
    g = 1.0
    for r in returns:
        g = g * (1 + r)
    return g


def ann_return(returns: list[float], periods_per_year: float) -> float:
    """Geometric annualization: growth ** (ppy / n) - 1."""
    n = len(returns)
    return cumulative_growth(returns) ** (periods_per_year / n) - 1


def ann_vol(returns: list[float], periods_per_year: float) -> float:
    return stdev(returns) * sqrt(periods_per_year)


def max_drawdown(values: list[float]) -> float:
    """Most negative peak-to-trough: min over t of v_t / running_max - 1."""
    peak = values[0]
    worst = 0.0
    for v in values:
        peak = max(peak, v)
        worst = min(worst, v / peak - 1)
    return worst


def lag1_autocorr(returns: list[float]) -> float:
    """First-order autocorrelation of the return series."""
    a, b = returns[1:], returns[:-1]
    ma, mb = mean(a), mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else 0.0


def desmooth_geltner(returns: list[float], rho: float | None = None
                     ) -> tuple[list[float], float]:
    """
    First-order (Geltner) unsmoothing for appraisal-based series:
        r_true_t = (r_obs_t - rho * r_obs_t-1) / (1 - rho)
    If rho is None it is estimated as the lag-1 autocorrelation.
    Returns (unsmoothed series of length n - 1, rho used).
    """
    if rho is None:
        rho = lag1_autocorr(returns)
    out = [(returns[t] - rho * returns[t - 1]) / (1 - rho)
           for t in range(1, len(returns))]
    return out, rho


# --------------------------------------------------------------- cash flow
def xnpv(rate: float, flows: list[tuple[str, float]]) -> float:
    """NPV at `rate` with actual/365.25 timing from the first flow date."""
    t0 = flows[0][0]
    return sum(amt / (1 + rate) ** year_frac(t0, d) for d, amt in flows)


def xirr(flows: list[tuple[str, float]],
         lo: float = -0.9999, hi: float = 10.0, tol: float = 1e-8) -> float | None:
    """Bisection IRR. Returns None if xnpv has no sign change on [lo, hi]."""
    f_lo, f_hi = xnpv(lo, flows), xnpv(hi, flows)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = xnpv(mid, flows)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def _level_on(index: list[tuple[str, float]], d: str) -> float:
    """Index level on the nearest date <= d (index ascending). Refuses a
    date before the series starts: a level "on or before" a date the series
    does not cover would silently anchor at the first observation and
    misstate every growth built on it (the 2026-09-03 audit's window
    defect). Callers clip to effective_window first."""
    if d < index[0][0]:
        raise ValueError(f"date {d} is before the series starts ({index[0][0]})")
    lvl = index[0][1]
    for di, vi in index:
        if di <= d:
            lvl = vi
        else:
            break
    return lvl


def effective_window(d0: str, d1: str,
                     index: list[tuple[str, float]]) -> tuple[str, str, str]:
    """The intersection of a fund window with the index's coverage, plus
    the note that says what was clipped ("" when nothing was). Raises when
    the two do not overlap. The same rule runs in site/js/analytics.js."""
    i0, i1 = index[0][0], index[-1][0]
    e0, e1 = max(d0, i0), min(d1, i1)
    if e0 >= e1:
        raise ValueError(f"window {d0} to {d1} does not overlap the series "
                         f"({i0} to {i1})")
    parts = []
    if e0 != d0:
        parts.append(f"proxy series begins {i0}")
    if e1 != d1:
        parts.append(f"proxy series ends {i1}")
    return e0, e1, ("clipped: " + ", ".join(parts)) if parts else ""


def ks_pme(flows: list[tuple[str, float]], index: list[tuple[str, float]]) -> float:
    """
    Kaplan-Schoar PME. Future-value every flow to the final flow date at the
    index's growth, then:
        PME = FV(distributions + terminal NAV) / FV(contributions)
    > 1.0 means the fund beat the index on these flows.
    """
    T = flows[-1][0]
    i_T = _level_on(index, T)
    fv_pos = sum(amt * i_T / _level_on(index, d) for d, amt in flows if amt > 0)
    fv_neg = sum(-amt * i_T / _level_on(index, d) for d, amt in flows if amt < 0)
    return fv_pos / fv_neg


def monthly_schedule_flows(fund: list[tuple[str, float]], d0: str,
                           d1: str) -> list[tuple[str, float]]:
    """ILLUSTRATIVE flow schedule: one unit of cash at the window start and
    at each fund month-end strictly inside the window, each buying 1 / NAV
    units, valued once at the window end. A schedule assumption, not a
    fact: the two-point comparison stays primary. Mirrored by
    monthlyScheduleFlows in site/js/analytics.js."""
    win = [(d, v) for d, v in fund if d0 <= d <= d1]
    dates = [d0] + [d for d, _ in month_end_points(win) if d0 < d < d1]
    units = 0.0
    flows: list[tuple[str, float]] = []
    for d in dates:
        units += 1.0 / _level_on(fund, d)
        flows.append((d, -1.0))
    flows.append((d1, units * _level_on(fund, d1)))
    return flows


def direct_alpha(flows: list[tuple[str, float]],
                 index: list[tuple[str, float]]) -> float | None:
    """
    Direct Alpha (Gredil / Griffiths / Stucke): future-value each flow to the
    final date at the index's growth, then take the IRR of the scaled stream.
    The result is the annualized excess return vs the index; 0 = index-like.
    """
    T = flows[-1][0]
    i_T = _level_on(index, T)
    scaled = [(d, amt * i_T / _level_on(index, d)) for d, amt in flows]
    return xirr(scaled)


# --------------------------------------------------- workbench table math
def calendar_year_returns(series: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """[(year, return)] from a value series: last obs of year over last obs of
    the PRIOR year (first covered year uses the series' first observation as
    its base and is a partial year for a mid-year start — callers label it)."""
    last_by_year: dict[str, tuple[str, float]] = {}
    for d, v in series:
        last_by_year[d[:4]] = (d, v)
    years = sorted(last_by_year)
    out: list[tuple[str, float]] = []
    prev = series[0][1]
    for y in years:
        v = last_by_year[y][1]
        out.append((y, v / prev - 1))
        prev = v
    return out


def drawdown_episodes(series: list[tuple[str, float]], top_n: int = 3
                      ) -> list[dict]:
    """Top-N peak-to-trough episodes, deepest first. Episode = from a running
    peak to the minimum before that peak is regained (or series end).
    Returns [{peak_date, trough_date, depth, recovery_date|None}]."""
    episodes: list[dict] = []
    i = 0
    n = len(series)
    while i < n - 1:
        peak_d, peak_v = series[i]
        j = i + 1
        trough_d, trough_v = peak_d, peak_v
        recovery = None
        while j < n:
            d, v = series[j]
            if v >= peak_v:
                recovery = d
                break
            if v < trough_v:
                trough_d, trough_v = d, v
            j += 1
        if trough_v < peak_v:
            episodes.append({"peak_date": peak_d, "trough_date": trough_d,
                             "depth": trough_v / peak_v - 1,
                             "recovery_date": recovery})
        i = j if j > i else i + 1
    episodes.sort(key=lambda e: e["depth"])
    return episodes[:top_n]


def rolling_returns(returns: list[float], window: int) -> list[float]:
    """Compounded return over each trailing window of per-period returns."""
    out = []
    for i in range(window, len(returns) + 1):
        out.append(cumulative_growth(returns[i - window:i]) - 1)
    return out


def rolling_vol(returns: list[float], window: int,
                periods_per_year: float) -> list[float]:
    """Annualized sample vol over each trailing window."""
    return [ann_vol(returns[i - window:i], periods_per_year)
            for i in range(window, len(returns) + 1)]


def beta(fund_returns: list[float], index_returns: list[float]) -> float:
    """OLS beta of fund on index over paired per-period returns."""
    n = min(len(fund_returns), len(index_returns))
    f, x = fund_returns[:n], index_returns[:n]
    mf, mx = mean(f), mean(x)
    cov = sum((a - mf) * (b - mx) for a, b in zip(f, x)) / (n - 1)
    var = sum((b - mx) ** 2 for b in x) / (n - 1)
    return cov / var if var else 0.0

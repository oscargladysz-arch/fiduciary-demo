"""
Apply the M2 analytics core to the real on-disk data.
Run: python src/run_analytics.py
Writes data/analytics/metrics.json and prints the headline numbers.
"""
import json
from pathlib import Path

from tark_data import DATA, load_series
from tark_analytics import (ann_return, ann_vol, cumulative_growth,
                            desmooth_geltner, lag1_autocorr, max_drawdown,
                            month_end_points, period_returns)

out = {"method_notes": {
    "monthly_resample": "last observation per calendar month",
    "returns": "simple period returns on adj_close (total-return proxy incl. distributions)",
    "desmoothing": "Geltner AR(1): r_true_t = (r_obs_t - rho * r_obs_t-1) / (1 - rho), rho = lag-1 autocorrelation",
    "caveat": "Yahoo adj_close approximates distribution reinvestment; official fund TR calcs may differ modestly - flagged for CF2 cross-check vs fund fact sheets",
}}

# ---------------- CCLFX ----------------
s = load_series("cclfx", "adj_close")
def block(series, label):
    me = month_end_points(series)
    rets = period_returns([v for _, v in me])
    rho = lag1_autocorr(rets)
    des, _ = desmooth_geltner(rets, rho)
    return {
        "window": f"{series[0][0]} to {series[-1][0]}",
        "monthly_obs": len(rets),
        "ann_return_pct": round(ann_return(rets, 12) * 100, 2),
        "ann_vol_observed_pct": round(ann_vol(rets, 12) * 100, 2),
        "lag1_autocorr_rho": round(rho, 3),
        "ann_vol_desmoothed_pct": round(ann_vol(des, 12) * 100, 2),
    }

full = block(s, "full")
sliced = block([(d, v) for d, v in s if d <= "2026-03-31"], "to FYE")
out["cclfx"] = {"full_history": full, "to_2026_03_31_for_disclosure_comparison": sliced,
                "fund_disclosed_at_2026_03_31": {"si_ann_return_pct": 9.34, "si_ann_stdev_pct": 1.71,
                                                 "source": "N-CSR 2026-06-08 Fund Performance"}}

print("=== CCLFX (adj_close, monthly) ===")
print(f"  full window {full['window']}: ann return {full['ann_return_pct']}%, "
      f"obs vol {full['ann_vol_observed_pct']}%, rho {full['lag1_autocorr_rho']}, "
      f"DE-SMOOTHED vol {full['ann_vol_desmoothed_pct']}%")
print(f"  sliced to 3/31/26: ann return {sliced['ann_return_pct']}% vs disclosed 9.34% | "
      f"obs vol {sliced['ann_vol_observed_pct']}% vs disclosed 1.71% | "
      f"desmoothed {sliced['ann_vol_desmoothed_pct']}%")

# ---------------- DXYZ ----------------
d = load_series("dxyz", "close")
vals = [v for _, v in d]
dd = max_drawdown(vals)
peak_i = vals.index(max(vals))
trough_i = min(range(peak_i, len(vals)), key=lambda i: vals[i])
drets = period_returns(vals)
out["dxyz"] = {
    "window": f"{d[0][0]} to {d[-1][0]}",
    "first_close": vals[0], "peak_close": vals[peak_i], "peak_date": d[peak_i][0],
    "trough_after_peak": vals[trough_i], "trough_date": d[trough_i][0],
    "last_close": vals[-1],
    "max_drawdown_pct": round(dd * 100, 1),
    "ann_vol_daily_pct": round(ann_vol(drets, 252) * 100, 1),
    "cumulative_since_listing_pct": round((cumulative_growth(period_returns(vals)) - 1) * 100, 1),
}
print("\n=== DXYZ (close, daily) ===")
print(f"  listed {d[0][0]} at {vals[0]}; peak {vals[peak_i]} on {d[peak_i][0]}; "
      f"trough {vals[trough_i]} on {d[trough_i][0]}; last {vals[-1]}")
print(f"  MAX DRAWDOWN {out['dxyz']['max_drawdown_pct']}% | ann vol {out['dxyz']['ann_vol_daily_pct']}% | "
      f"cumulative since listing {out['dxyz']['cumulative_since_listing_pct']}%")

# ---------------- PAF (annual, from filings) ----------------
fy_tr = [0.1460, 0.1259, 0.1268, 0.1610, 0.2077]      # FY26..FY22, evidence 1.2
nav = [12.35, 14.14, 15.81, 17.55, 19.77]             # FY22..FY26, evidence 1.1
tr_ann = ann_return(list(reversed(fy_tr)), 1)
nav_ann = ann_return(period_returns(nav), 1)
out["hl_paf_annual"] = {
    "fy_total_returns_pct_fy22_to_fy26": [20.77, 16.10, 12.68, 12.59, 14.60],
    "geometric_ann_total_return_pct": round(tr_ann * 100, 2),
    "nav_only_ann_return_pct": round(nav_ann * 100, 2),
    "distribution_wedge_pct": round((tr_ann - nav_ann) * 100, 2),
    "caveat": "5 annual observations - volatility estimates not meaningful at this granularity",
}
print("\n=== HL PAF (annual, from filings) ===")
print(f"  geometric ann total return FY22-FY26: {out['hl_paf_annual']['geometric_ann_total_return_pct']}% | "
      f"NAV-only {out['hl_paf_annual']['nav_only_ann_return_pct']}% | "
      f"distribution wedge {out['hl_paf_annual']['distribution_wedge_pct']}%")

Path(DATA / "analytics").mkdir(exist_ok=True)
(DATA / "analytics" / "metrics.json").write_text(json.dumps(out, indent=2))
print("\nwrote data/analytics/metrics.json")

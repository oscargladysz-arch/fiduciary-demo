"""
Committed analytics diagnostics from the held series.
    python src/run_analytics.py
Writes data/analytics/metrics.json: the CCLFX monthly de-smoothing
diagnostic that the De-smoothing Lab prints beside its live recompute.
Every number is recomputed from data/series/, nothing is typed in, and the
script runs inside src/produce.py so the freshness gate reproduces it.
"""
import json

from tark_analytics import (ann_return, ann_vol, desmooth_geltner,
                            lag1_autocorr, month_end_points, period_returns)
from tark_data import DATA, load_series

METHOD_NOTES = {
    "monthly_resample": "last observation per calendar month",
    "returns": "simple period returns on adj_close (total-return proxy incl. distributions)",
    "desmoothing": "Geltner AR(1): r_true_t = (r_obs_t - rho * r_obs_t-1) / (1 - rho), rho = lag-1 autocorrelation",
    "caveat": "Yahoo adj_close approximates distribution reinvestment. Official fund TR calcs may differ modestly (flagged for CF2 cross-check vs fund fact sheets)",
}


def block(series: list[tuple[str, float]]) -> dict:
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


def main() -> None:
    full = block(load_series("cclfx", "adj_close"))
    out = {"method_notes": METHOD_NOTES, "cclfx": {"full_history": full}}
    (DATA / "analytics").mkdir(exist_ok=True)
    (DATA / "analytics" / "metrics.json").write_text(json.dumps(out, indent=2))
    print(f"CCLFX (adj_close, monthly) {full['window']}: ann return "
          f"{full['ann_return_pct']}%, observed vol {full['ann_vol_observed_pct']}%, "
          f"rho {full['lag1_autocorr_rho']}, de-smoothed vol "
          f"{full['ann_vol_desmoothed_pct']}%")
    print("wrote data/analytics/metrics.json")


if __name__ == "__main__":
    main()

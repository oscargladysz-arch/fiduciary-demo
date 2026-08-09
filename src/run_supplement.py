"""
Supplemental pipeline metrics (coverage max-out pass)
=====================================================
Computes what the data tier legitimately supports and writes
data/analytics/supplement.json with full provenance:
  - dxyz premium/discount stats (cell 4.7): latest close vs latest filed
    quarterly NAV/share, plus the filed premium range
  - fee percentile within the evaluation universe (cell 2.9): each product's
    own primary net expense ratio as extracted in cell 2.3 — universe = this
    six-product roster, bases differ and are quoted per product
  - stress-window stats (cell 1.9) where a daily series exists; annual-tier
    products are computed from data/series_annual/ files when present

Run: python src/run_supplement.py
"""
from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path

from tark_analytics import max_drawdown
from tark_data import DATA, load_product, load_series, product_keys

OUT = DATA / "analytics" / "supplement.json"


def dxyz_premium() -> dict:
    px = load_series("dxyz", "close")
    nav = json.loads((DATA / "analytics" / "dxyz_nav_quarterly.json").read_text())
    last_date, last_close = px[-1]
    latest = nav["rows"][-1]
    prem = (last_close / latest["nav_per_share"] - 1) * 100
    highs = [r["premium_pct_at_high"] for r in nav["rows"]
             if r.get("premium_pct_at_high") is not None]
    lows = [r["premium_pct_at_low"] for r in nav["rows"]
            if r.get("premium_pct_at_low") is not None]
    return {
        "last_close": last_close, "last_close_date": last_date,
        "latest_filed_nav": latest["nav_per_share"],
        "latest_nav_period_end": latest.get("period_end"),
        "premium_pct_vs_latest_filed_nav": round(prem, 1),
        "filed_premium_range_pct": [min(lows), max(highs)],
        "note": "premium computed vs the most recent FILED quarterly NAV - the "
                "live NAV is unobservable between filings; filed range from the "
                "fund's own prospectus table",
        "inputs": ["data/series/dxyz.csv",
                   "data/analytics/dxyz_nav_quarterly.json"],
    }


TER_PAT = re.compile(r"(\d+\.\d+)\s*%")


def fee_percentile() -> dict:
    entries = []
    for k in product_keys():
        cell = load_product(k)["cells"]["2.3"]
        val = str(cell.get("value") or "")
        st = str(cell.get("status", ""))
        m = TER_PAT.search(val)
        if st.startswith(("extracted", "verified")) and m:
            entries.append({"product": k, "ter_pct": float(m.group(1)),
                            "basis_excerpt": val[:140], "cited_cell": "2.3"})
        else:
            entries.append({"product": k, "ter_pct": None,
                            "reason": "no comparable TER line item (see 2.1/2.2)",
                            "cited_cell": "2.3"})
    ranked = sorted([e for e in entries if e["ter_pct"] is not None],
                    key=lambda e: e["ter_pct"])
    n = len(ranked)
    for i, e in enumerate(ranked):
        e["rank"] = i + 1
        e["of"] = n
        e["percentile_low_is_cheap"] = round((i + 0.5) / n * 100)
    return {"universe": "this six-product evaluation roster (n=%d with a TER "
                        "line) - NOT a market-wide database; bases differ per "
                        "product and are quoted from cell 2.3" % n,
            "entries": entries}


def stress_windows() -> dict:
    out = {}
    # daily-series tier
    for key, ticker in (("cliffwater_cclfx", "cclfx"), ("dxyz", "dxyz")):
        s = load_series(ticker, "adj_close" if key != "dxyz" else "close")
        w = {}
        cal22 = [v for d, v in s if "2022-01-01" <= d <= "2022-12-31"]
        if len(cal22) > 30:
            w["cy2022_rate_shock"] = {
                "return_pct": round((cal22[-1] / cal22[0] - 1) * 100, 2),
                "max_drawdown_pct": round(max_drawdown(cal22) * 100, 2)}
        covid = [v for d, v in s if "2020-02-01" <= d <= "2020-04-30"]
        if len(covid) > 20:
            w["covid_feb_apr_2020"] = {
                "return_pct": round((covid[-1] / covid[0] - 1) * 100, 2),
                "max_drawdown_pct": round(max_drawdown(covid) * 100, 2)}
        full = [v for _, v in s]
        w["worst_peak_to_trough_full_history_pct"] = round(
            max_drawdown(full) * 100, 2)
        w["series"] = f"data/series/{ticker}.csv"
        out[key] = w
    # annual tier from series_annual (built from extracted evidence)
    ann_dir = DATA / "series_annual"
    if ann_dir.exists():
        for f in sorted(ann_dir.glob("*.csv")):
            key = f.stem
            with open(f, newline="") as fh:
                rows = list(csv.DictReader(fh))
            shock = [r for r in rows if r.get("total_return_pct") and
                     "2022-06" <= r["fy_end"] <= "2023-06"]
            if shock:
                out[key] = {
                    "fy_spanning_2022_rate_shock": {
                        "fy_end": shock[0]["fy_end"],
                        "return_pct": float(shock[0]["total_return_pct"])},
                    "note": "annual disclosure cadence - the fiscal year "
                            "spanning the 2022 public-market drawdown is the "
                            "finest public stress observation for this wrapper",
                    "series": f"data/series_annual/{key}.csv"}
    return out


def main() -> None:
    doc = {
        "generated": date.today().isoformat(),
        "dxyz_premium": dxyz_premium(),
        "fee_percentile": fee_percentile(),
        "stress_windows": stress_windows(),
    }
    OUT.write_text(json.dumps(doc, indent=2))
    print(f"wrote {OUT}")
    print(json.dumps(doc["fee_percentile"]["entries"], indent=1)[:600])


if __name__ == "__main__":
    main()

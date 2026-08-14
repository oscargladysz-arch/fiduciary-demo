"""
Daily price/NAV series fetcher (build-time only; the site itself makes no
external calls). Pulls date/close/adjclose from the Yahoo Finance v8 chart
API — the same source and file contract as the original six series — and
updates data/series/series_manifest.json.

Usage: python src/fetch_series.py TICKER [role-note...]
"""
from __future__ import annotations

import csv
import json
import sys
import time
from datetime import date, datetime, timezone

import requests

from tark_data import DATA

UA = {"User-Agent": "Mozilla/5.0 (Macintosh) tark-research "
                    "(oscargladysz@gmail.com)"}


def fetch(ticker: str) -> list[tuple[str, float, float]]:
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?range=10y&interval=1d&events=div%2Csplit")
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    ts = res["timestamp"]
    quote = res["indicators"]["quote"][0]["close"]
    adj = res["indicators"]["adjclose"][0]["adjclose"]
    rows = []
    for t, c, a in zip(ts, quote, adj):
        if c is None or a is None or c <= 0 or a <= 0:
            continue
        d = datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat()
        rows.append((d, round(c, 6), round(a, 6)))
    return rows


def main() -> None:
    ticker = sys.argv[1]
    note = " ".join(sys.argv[2:]) or f"{ticker} daily series"
    rows = fetch(ticker)
    if len(rows) < 50:
        raise SystemExit(f"{ticker}: only {len(rows)} rows - refusing "
                         f"(series contract needs >= 50)")
    out = DATA / "series" / f"{ticker.lower()}.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["date", "close", "adj_close"])
        w.writerows(rows)
    man_path = DATA / "series" / "series_manifest.json"
    man = json.loads(man_path.read_text())
    man["series"] = [s for s in man["series"]
                     if s["ticker"].lower() != ticker.lower()]
    man["series"].append({
        "ticker": ticker.upper(),
        "source": "Yahoo Finance v8 chart API (close + adjclose)",
        "rows": len(rows), "first": rows[0][0], "last": rows[-1][0],
        "pulled": date.today().isoformat(), "note": note, "role": "fund",
    })
    man_path.write_text(json.dumps(man, indent=2))
    print(f"{ticker}: {len(rows)} rows {rows[0][0]} -> {rows[-1][0]} -> {out}")
    time.sleep(1.0)


if __name__ == "__main__":
    main()

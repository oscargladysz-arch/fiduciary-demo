"""
Published index series: acquire, normalize, record (R2-P1-1, decision 7.2)
==========================================================================
Turns a published headline return series (Cliffwater Direct Lending Index,
NCREIF Fund Index ODCE) into data/series_quarterly/idx_<id>.csv with the
columns the engine reads (period_end, total_return_pct, one row per
calendar quarter) and records the acquisition in
data/series_quarterly/manifest.json (URL, fetch date, license note, sha256
of the source file, row count, first and last quarter).

Two paths, because both sponsors publish the headline numbers on pages the
build container cannot reach and a licence note has to be typed by the
person who read it:

  python src/fetch_index_series.py --id cdli --url <page or file URL> \
      --license "<the sponsor's terms as read on the page>" [--out data]
      tries an HTTP GET of the URL (CSV, JSON or an HTML table) with the
      contact user agent from TARK_SEC_CONTACT and normalizes what it finds.

  python src/fetch_index_series.py --id cdli --from-file <downloaded file> \
      --url <where it came from> --license "<terms>" --fetched 2026-09-10
      normalizes a file downloaded by hand and records the URL and date you
      give (decision 7.2: download once by hand when automated access is
      refused).

Accepted inputs: a CSV or JSON with a date column (period end, quarter end,
or "2025Q4" style labels) and a quarterly return column in percent or
decimal, or an HTML table with the same two columns. Anything else is
refused with the columns it saw. Nothing is interpolated: only quarter-end
rows are kept, and a quarter that is missing stays missing.

After running: python src/produce.py, then the hook. The engine scores the
candidate as held from the next run and the corrections log records every
number that moved.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))
from tark_data import DATA  # noqa: E402

INDEXES = {
    "cdli": {"file": "idx_cdli", "name": "Cliffwater Direct Lending Index (CDLI)", "provider": "Cliffwater",
             "what": "quarterly headline total return, as published by the sponsor"},
    "odce": {"file": "idx_odce", "name": "NCREIF Fund Index - ODCE", "provider": "NCREIF",
             "what": "quarterly headline total return, as published by the sponsor"},
}
QUARTER_END = {3: "31", 6: "30", 9: "30", 12: "31"}


def user_agent() -> str:
    contact = os.environ.get("TARK_SEC_CONTACT", "").strip()
    if not contact:
        raise SystemExit("set TARK_SEC_CONTACT to 'Your Name your@email' before fetching from a sponsor site")
    return f"Tark fiduciary evaluation ({contact})"


# ------------------------------------------------------------- parsing
def quarter_end(label: str) -> str | None:
    """'2025-12-31', '12/31/2025', '2025Q4', 'Q4 2025', 'Dec 2025', '4Q25' to
    an ISO quarter-end date, else None."""
    s = label.strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        return f"{y}-{mo:02d}-{QUARTER_END[mo]}" if mo in QUARTER_END else None
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        mo, y = int(m.group(1)), int(m.group(3))
        return f"{y}-{mo:02d}-{QUARTER_END[mo]}" if mo in QUARTER_END else None
    m = re.fullmatch(r"(\d{4})\s*[- ]?Q([1-4])", s, re.I) or re.fullmatch(r"Q([1-4])\s*[- ]?(\d{4})", s, re.I)
    if m:
        a, b = m.groups()
        y, q = (int(a), int(b)) if len(a) == 4 else (int(b), int(a))
        mo = q * 3
        return f"{y}-{mo:02d}-{QUARTER_END[mo]}"
    m = re.fullmatch(r"([1-4])Q(\d{2,4})", s, re.I)
    if m:
        q, y = int(m.group(1)), int(m.group(2))
        y = y + 2000 if y < 100 else y
        mo = q * 3
        return f"{y}-{mo:02d}-{QUARTER_END[mo]}"
    m = re.fullmatch(r"([A-Za-z]{3,9})\.?\s+(\d{4})", s)
    if m:
        try:
            mo = datetime.strptime(m.group(1)[:3], "%b").month
        except ValueError:
            return None
        return f"{int(m.group(2))}-{mo:02d}-{QUARTER_END[mo]}" if mo in QUARTER_END else None
    return None


def to_pct(v: str) -> float | None:
    s = v.strip().replace(",", "").replace("%", "")
    if not s or s in ("-", "n/a", "NA"):
        return None
    try:
        x = float(s)
    except ValueError:
        return None
    # a decimal return file (0.0234) is converted to percent. Sponsors
    # publish percent; a whole file below 1 in absolute value is decimal.
    return x


def rows_from_table(header: list[str], body: list[list[str]]) -> list[tuple[str, float]]:
    hl = [h.strip().lower() for h in header]
    date_i = next((i for i, h in enumerate(hl) if any(w in h for w in ("date", "period", "quarter", "as of"))), None)
    ret_i = next((i for i, h in enumerate(hl) if "total" in h and "return" in h), None)
    if ret_i is None:
        ret_i = next((i for i, h in enumerate(hl) if "return" in h), None)
    if date_i is None or ret_i is None:
        raise SystemExit(f"could not find a period column and a return column in {header}")
    out = []
    for r in body:
        if len(r) <= max(date_i, ret_i):
            continue
        q = quarter_end(r[date_i])
        v = to_pct(r[ret_i])
        if q and v is not None:
            out.append((q, v))
    return out


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self.tables:
            self.tables[-1].append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_source(raw: bytes, hint: str) -> list[tuple[str, float]]:
    text = raw.decode("utf-8", errors="replace")
    if hint.endswith(".json") or text.lstrip().startswith(("{", "[")):
        doc = json.loads(text)
        recs = doc if isinstance(doc, list) else next((v for v in doc.values() if isinstance(v, list)), [])
        if not recs or not isinstance(recs[0], dict):
            raise SystemExit("JSON has no list of records")
        header = list(recs[0].keys())
        return rows_from_table(header, [[str(r.get(h, "")) for h in header] for r in recs])
    if hint.endswith((".htm", ".html")) or "<table" in text.lower():
        p = _Tables()
        p.feed(text)
        best: list[tuple[str, float]] = []
        for t in p.tables:
            if len(t) < 2:
                continue
            try:
                rows = rows_from_table(t[0], t[1:])
            except SystemExit:
                continue
            if len(rows) > len(best):
                best = rows
        if not best:
            raise SystemExit("no HTML table with a period column and a return column")
        return best
    rdr = list(csv.reader(io.StringIO(text)))
    if len(rdr) < 2:
        raise SystemExit("CSV has no data rows")
    return rows_from_table(rdr[0], rdr[1:])


def normalize(rows: list[tuple[str, float]]) -> list[tuple[str, float]]:
    by = {}
    for q, v in rows:
        by[q] = v
    vals = list(by.values())
    if vals and max(abs(v) for v in vals) < 1.0:
        by = {q: v * 100 for q, v in by.items()}
    return sorted(by.items())


# -------------------------------------------------------------- record
def write(idx: str, rows: list[tuple[str, float]], url: str, fetched: str, license_note: str,
          source_sha: str, source_name: str, out_dir: Path) -> Path:
    meta = INDEXES[idx]
    out = out_dir / "series_quarterly" / f"{meta['file']}.csv"
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["period_end", "total_return_pct"])
        for q, v in rows:
            w.writerow([q, f"{v:.4f}".rstrip("0").rstrip(".")])
    mp = out_dir / "series_quarterly" / "manifest.json"
    man = json.loads(mp.read_text()) if mp.exists() else {"generated": fetched, "series": {}}
    man["series"][meta["file"]] = {
        "rows": len(rows), "first": rows[0][0], "last": rows[-1][0],
        "name": meta["name"], "provider": meta["provider"], "what": meta["what"],
        "source_url": url, "fetched": fetched, "license_note": license_note,
        "source_file": source_name, "source_sha256": source_sha,
        "status": "published headline series, as fetched, not human-verified",
    }
    mp.write_text(json.dumps(man, indent=2) + "\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", required=True, choices=sorted(INDEXES))
    ap.add_argument("--url", required=True, help="the sponsor page or file the numbers come from")
    ap.add_argument("--license", required=True, help="the sponsor's terms of use as read on the page")
    ap.add_argument("--from-file", help="a file downloaded by hand (CSV, JSON or HTML)")
    ap.add_argument("--fetched", help="ISO date the file was downloaded (required with --from-file)")
    ap.add_argument("--out", default=str(DATA), help="data directory (default: the record)")
    a = ap.parse_args()
    out_dir = Path(a.out).resolve()
    if a.from_file:
        if not a.fetched or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.fetched):
            raise SystemExit("--fetched YYYY-MM-DD is required with --from-file")
        raw = Path(a.from_file).read_bytes()
        hint, fetched, source_name = a.from_file.lower(), a.fetched, Path(a.from_file).name
    else:
        import requests  # noqa: PLC0415
        r = requests.get(a.url, headers={"User-Agent": user_agent()}, timeout=60)
        if r.status_code != 200:
            raise SystemExit(f"{a.url} answered {r.status_code}: download by hand and use --from-file")
        raw, hint = r.content, a.url.lower()
        fetched = date.today().isoformat()
        source_name = a.url
    rows = normalize(parse_source(raw, hint))
    if len(rows) < 4:
        raise SystemExit(f"only {len(rows)} quarter-end rows found, refusing to write a series")
    sha = hashlib.sha256(raw).hexdigest()
    out = write(a.id, rows, a.url, fetched, a.license, sha, source_name, out_dir)
    print(f"wrote {out.relative_to(out_dir.parent) if out.is_relative_to(out_dir.parent) else out}: "
          f"{len(rows)} quarters, {rows[0][0]} to {rows[-1][0]}, source sha256 {sha[:12]}, "
          f"recorded in series_quarterly/manifest.json at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')}")
    print("next: python src/produce.py, then the hook. The engine treats the index as held from now on.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

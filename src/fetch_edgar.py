"""
Tark — EDGAR fetcher (spike v1)
================================
Pulls the current offering documents + latest reports for a product in the
verified registry, saves them under data/raw/<product>/, and records every
pull in data/manifest.csv so any download is reproducible.

Usage (from repo root, venv active):
    python src/fetch_edgar.py --list          # show the product registry
    python src/fetch_edgar.py hl_paf          # fetch one product
    python src/fetch_edgar.py hl_paf dxyz     # fetch several

Design rules:
- Script fetches and organizes; humans read and extract (see docs/extraction_worksheet.md).
- SEC fair-access: identified User-Agent, <=4 requests/sec, retry-once on throttle.
- Idempotent: existing files are skipped, manifest rows are deduped.

Registry verified against live EDGAR on 2026-07-09. Notes:
- "HLPIF" (from earlier project docs) maps to NO registered entity; the
  registered Hamilton Lane evergreen is the PRIVATE ASSETS FUND (hl_paf).
- BXPE (CIK 1930054) files 10-Q + Form D/A only: Reg D private placement,
  no public prospectus -> EXCLUDED from demo roster; StepStone swapped in.
- "K-PRIME" resolves offshore; the SEC-reporting KKR vehicle is K-PEC.
- Capital Group KKR funds did not resolve cleanly as registrants; the
  credit / true-interval-fund slot is OPEN (candidate to verify next:
  Cliffwater Corporate Lending Fund, CCLFX).
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

USER_AGENT = "Oscar Gladysz oscargladysz@gmail.com"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
MANIFEST = REPO_ROOT / "data" / "manifest.csv"
MANIFEST_COLS = [
    "product", "fund_name", "cik", "doc_set", "form", "filing_date",
    "accession", "primary_document", "url", "local_path", "pulled_at_utc",
]
SLEEP = 0.3  # seconds between requests (SEC allows 10/sec; we stay well under)

PRODUCTS = {
    "hl_paf": {
        "name": "Hamilton Lane Private Assets Fund",
        "cik": "1803491",
        "wrapper": "tender-offer fund ('40 Act)",
        "doc_sets": {
            "prospectus": ["486BPOS", "486BXT", "424B3"],
            "annual_report": ["N-CSR"],
            "holdings": ["NPORT-P"],
            "tender_offer": ["SC TO-I"],
        },
    },
    "stepstone_spm": {
        "name": "StepStone Private Markets",
        "cik": "1789470",
        "wrapper": "tender-offer fund ('40 Act)",
        "doc_sets": {
            "prospectus": ["486BPOS", "424B3"],
            "annual_report": ["N-CSR"],
            "holdings": ["NPORT-P"],
            "tender_offer": ["SC TO-I"],
        },
    },
    "kkr_kpec": {
        "name": "KKR Private Equity Conglomerate LLC",
        "cik": "1957845",
        "wrapper": "non-traded '34 Act reporting company",
        "doc_sets": {
            "annual_report": ["10-K"],
            "quarterly_report": ["10-Q"],
        },
    },
    "breit": {
        "name": "Blackstone Real Estate Income Trust Inc",
        "cik": "1662972",
        "wrapper": "non-traded REIT ('34 Act reporting)",
        "doc_sets": {
            "annual_report": ["10-K"],
            "quarterly_report": ["10-Q"],
        },
    },
    "dxyz": {
        "name": "Destiny Tech100 Inc",
        "cik": "1843974",
        "wrapper": "listed closed-end fund (NYSE: DXYZ)",
        "doc_sets": {
            "prospectus": ["N-2/A", "424B3", "424B5"],
            "annual_report": ["N-CSR"],
            "holdings": ["NPORT-P"],
        },
    },
    "ares_pmf": {
        "name": "Ares Private Markets Fund",
        "cik": "1876006",
        "wrapper": "tender-offer fund ('40 Act) [bench: swap candidate]",
        "doc_sets": {
            "prospectus": ["N-2", "424B3"],
            "annual_report": ["N-CSR"],
        },
    },
}


def polite_get(url, as_json=False):
    """GET with identified UA, pacing, and one retry on throttle/outage."""
    for attempt in (1, 2):
        resp = requests.get(url, headers=HEADERS, timeout=60)
        if resp.status_code in (429, 503) and attempt == 1:
            time.sleep(2.0)
            continue
        resp.raise_for_status()
        time.sleep(SLEEP)
        return resp.json() if as_json else resp.content
    raise RuntimeError(f"unreachable: {url}")


def load_submissions(cik):
    url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
    return polite_get(url, as_json=True)


def latest_filing_per_form(subs, forms_wanted):
    """Return {form: filing_dict} for the most recent instance of each form.
    The submissions 'recent' arrays are newest-first, so first hit wins."""
    recent = subs["filings"]["recent"]
    found = {}
    for i, form in enumerate(recent["form"]):
        if form in forms_wanted and form not in found:
            found[form] = {
                "form": form,
                "filing_date": recent["filingDate"][i],
                "accession": recent["accessionNumber"][i],
                "primary_document": recent["primaryDocument"][i],
            }
        if len(found) == len(forms_wanted):
            break
    return found


def download_filing(cik, filing, dest_dir):
    acc_nodash = filing["accession"].replace("-", "")
    doc = filing["primary_document"]
    if not doc:
        return None, None
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_nodash}/{doc}"
    safe_name = f"{filing['form'].replace('/', '-')}_{filing['filing_date']}_{Path(doc).name}"
    local = dest_dir / safe_name
    if local.exists() and local.stat().st_size > 0:
        return url, local  # idempotent skip
    data = polite_get(url)
    local.write_bytes(data)
    return url, local


def read_manifest():
    if not MANIFEST.exists():
        return []
    with open(MANIFEST, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_manifest(rows):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLS)
        w.writeheader()
        w.writerows(rows)


def fetch_product(key):
    p = PRODUCTS[key]
    dest = RAW_DIR / key
    dest.mkdir(parents=True, exist_ok=True)
    print(f"\n== {key}: {p['name']} (CIK {p['cik']}, {p['wrapper']}) ==")
    subs = load_submissions(p["cik"])
    manifest = read_manifest()
    seen = {(r["accession"], r["primary_document"]) for r in manifest}
    pulled_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for doc_set, forms in p["doc_sets"].items():
        for form, filing in latest_filing_per_form(subs, forms).items():
            url, local = download_filing(p["cik"], filing, dest)
            if url is None:
                print(f"  [skip] {form} {filing['filing_date']}: no primary document listed")
                continue
            size_kb = local.stat().st_size // 1024
            print(f"  [ok]   {doc_set:<16} {form:<8} {filing['filing_date']}  ->  {local.name} ({size_kb} KB)")
            key_pair = (filing["accession"], filing["primary_document"])
            if key_pair not in seen:
                manifest.append({
                    "product": key,
                    "fund_name": p["name"],
                    "cik": p["cik"],
                    "doc_set": doc_set,
                    "form": form,
                    "filing_date": filing["filing_date"],
                    "accession": filing["accession"],
                    "primary_document": filing["primary_document"],
                    "url": url,
                    "local_path": str(local.relative_to(REPO_ROOT)),
                    "pulled_at_utc": pulled_at,
                })
                seen.add(key_pair)
    write_manifest(manifest)
    print(f"  manifest: {MANIFEST.relative_to(REPO_ROOT)} ({len(manifest)} rows)")


def main():
    ap = argparse.ArgumentParser(description="Tark EDGAR fetcher (spike v1)")
    ap.add_argument("products", nargs="*", help="product keys to fetch")
    ap.add_argument("--list", action="store_true", help="show the registry and exit")
    args = ap.parse_args()

    if args.list or not args.products:
        print("Verified product registry (2026-07-09):")
        for k, v in PRODUCTS.items():
            print(f"  {k:<15} {v['name']}  [CIK {v['cik']}]  {v['wrapper']}")
        print("\nExcluded: bxpe (Reg D private placement, no public prospectus),")
        print("          capital_group_kkr (registrant unresolved - slot OPEN),")
        print("          blackrock/Great Gray PE TDF (CIT - no EDGAR; partnership slide).")
        if not args.list:
            print("\nPass one or more product keys to fetch, e.g.:  python src/fetch_edgar.py hl_paf")
        return

    for key in args.products:
        if key not in PRODUCTS:
            sys.exit(f"unknown product '{key}' - run with --list to see the registry")
        fetch_product(key)


if __name__ == "__main__":
    main()

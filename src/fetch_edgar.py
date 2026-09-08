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
- Every path under the data root (TARK_DATA_DIR): a run against a copy of
  the record never writes the repository. fetch_product(key) returns the
  product's manifest rows for the caller (the ingest, the worker).
- Exhibits: a registry entry may name `exhibits: {form: [patterns]}`. For
  such a form the filing index is read and every matching document is saved
  beside the primary document, with its own manifest row on the same
  accession (so the document label names the document, see ingest.doc_label).

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
import fnmatch
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from tark_data import DATA, sec_user_agent  # noqa: E402  (contact from TARK_SEC_CONTACT)


def headers() -> dict:
    return {"User-Agent": sec_user_agent(), "Accept-Encoding": "gzip, deflate"}


RAW_DIR = DATA / "raw"
MANIFEST = DATA / "manifest.csv"
MANIFEST_COLS = [
    "product", "fund_name", "cik", "doc_set", "form", "filing_date",
    "accession", "primary_document", "url", "local_path", "pulled_at_utc",
]
SLEEP = 0.3  # seconds between requests (SEC allows 10/sec; we stay well under)


# identity from data/products, document sets and exhibits from the one
# registry: every product in the record is fetchable, none is hand-listed
# here. Read on demand, so a product promoted after import is visible.
def _products_from_record() -> dict:
    reg = json.loads((DATA / "registry.json").read_text())["products"]
    out = {}
    for key, r in reg.items():
        pp = DATA / "products" / f"{key}.json"
        if not pp.exists():
            continue
        prod = json.loads(pp.read_text())
        out[key] = {"name": prod["fund_name"], "cik": prod["cik"], "wrapper": prod.get("wrapper", ""),
                    "doc_sets": r["filings"], "exhibits": r.get("exhibits") or {}}
    return out


def products() -> dict:
    return _products_from_record()


def __getattr__(name):
    if name == "PRODUCTS":
        return _products_from_record()
    raise AttributeError(name)


def polite_get(url, as_json=False):
    """GET with identified UA, pacing, and one retry on throttle/outage."""
    for attempt in (1, 2):
        resp = requests.get(url, headers=headers(), timeout=60)
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


def filings_for_form(subs, form, count):
    """Most recent `count` filings of a single form (newest first)."""
    recent = subs["filings"]["recent"]
    out = []
    for i, f in enumerate(recent["form"]):
        if f == form:
            out.append({
                "form": f,
                "filing_date": recent["filingDate"][i],
                "accession": recent["accessionNumber"][i],
                "primary_document": recent["primaryDocument"][i],
            })
            if len(out) >= count:
                break
    return out


def filing_url(cik, accession, doc):
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{doc}"


def download_filing(cik, filing, dest_dir):
    doc = filing["primary_document"]
    if not doc:
        return None, None
    url = filing_url(cik, filing["accession"], doc)
    safe_name = f"{filing['form'].replace('/', '-')}_{filing['filing_date']}_{Path(doc).name}"
    local = dest_dir / safe_name
    if local.exists() and local.stat().st_size > 0:
        return url, local  # idempotent skip
    data = polite_get(url)
    local.write_bytes(data)
    return url, local


def filing_index(cik, accession) -> list[str]:
    """The document names in a filing's folder, from the EDGAR directory index."""
    idx = polite_get(filing_url(cik, accession, "index.json"), as_json=True)
    items = (idx.get("directory") or {}).get("item") or []
    return [it.get("name", "") for it in items if it.get("name")]


def exhibit_documents(cik, filing, patterns) -> list[str]:
    """The exhibit documents a filing carries that match the registry's
    patterns (case-insensitive globs), the primary document excluded."""
    names = filing_index(cik, filing["accession"])
    out = []
    for n in names:
        if n == filing["primary_document"] or n.lower().endswith((".xml", ".xsd", ".json", ".txt.gz")):
            continue
        if n.lower() == "index.json" or n.lower().endswith("-index.htm"):
            continue
        if any(fnmatch.fnmatch(n.lower(), p.lower()) for p in patterns):
            out.append(n)
    return out


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


def _row(key, p, doc_set, filing, url, local, pulled_at):
    return {"product": key, "fund_name": p["name"], "cik": p["cik"], "doc_set": doc_set,
            "form": filing["form"], "filing_date": filing["filing_date"], "accession": filing["accession"],
            "primary_document": filing["primary_document"], "url": url,
            "local_path": str(local.relative_to(DATA.parent)), "pulled_at_utc": pulled_at}


def fetch_product(key) -> list[dict]:
    """Fetch the registry's document sets for one product into data/raw/<key>
    and record every pull in the manifest. Returns the product's manifest rows."""
    p = products()[key]
    dest = RAW_DIR / key
    dest.mkdir(parents=True, exist_ok=True)
    print(f"\n== {key}: {p['name']} (CIK {p['cik']}, {p['wrapper']}) ==")
    subs = load_submissions(p["cik"])
    manifest = read_manifest()
    seen = {(r["accession"], r["primary_document"]) for r in manifest}
    pulled_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def record(doc_set, filing, url, local):
        key_pair = (filing["accession"], filing["primary_document"])
        if key_pair not in seen:
            manifest.append(_row(key, p, doc_set, filing, url, local, pulled_at))
            seen.add(key_pair)

    for doc_set, forms in p["doc_sets"].items():
        for form, filing in latest_filing_per_form(subs, forms).items():
            url, local = download_filing(p["cik"], filing, dest)
            if url is None:
                print(f"  [skip] {form} {filing['filing_date']}: no primary document listed")
                continue
            size_kb = local.stat().st_size // 1024
            print(f"  [ok]   {doc_set:<16} {form:<8} {filing['filing_date']}  ->  {local.name} ({size_kb} KB)")
            record(doc_set, filing, url, local)
            if p["exhibits"].get(form) and not any(
                    r["accession"] == filing["accession"] and r["primary_document"] != filing["primary_document"]
                    for r in manifest):
                # the filing index is read once per accession: a rerun with the
                # exhibits already in the manifest makes no request
                for name in exhibit_documents(p["cik"], filing, p["exhibits"][form]):
                    ex = {**filing, "primary_document": name}
                    url2, local2 = download_filing(p["cik"], ex, dest)
                    print(f"  [ok]   {doc_set:<16} {form:<8} {filing['filing_date']}  ->  {local2.name} "
                          f"(exhibit, {local2.stat().st_size // 1024} KB)")
                    record(doc_set, ex, url2, local2)
    for set_name, spec in p.get("history_sets", {}).items():
        for filing in filings_for_form(subs, spec["form"], spec["count"]):
            url, local = download_filing(p["cik"], filing, dest)
            if url is None:
                continue
            print(f"  [ok]   {set_name:<16} {filing['form']:<8} {filing['filing_date']}  ->  {local.name} ({local.stat().st_size // 1024} KB)")
            record(set_name, filing, url, local)

    write_manifest(manifest)
    print(f"  manifest: {MANIFEST.relative_to(DATA.parent)} ({len(manifest)} rows)")
    return [r for r in manifest if r["product"] == key]


def main():
    ap = argparse.ArgumentParser(description="Tark EDGAR fetcher (spike v1)")
    ap.add_argument("products", nargs="*", help="product keys to fetch")
    ap.add_argument("--list", action="store_true", help="show the registry and exit")
    args = ap.parse_args()
    reg = products()

    if args.list or not args.products:
        print("Verified product registry (2026-07-09):")
        for k, v in reg.items():
            print(f"  {k:<15} {v['name']}  [CIK {v['cik']}]  {v['wrapper']}")
        print("\nExcluded: bxpe (Reg D private placement, no public prospectus),")
        print("          capital_group_kkr (registrant unresolved - slot OPEN),")
        print("          blackrock/Great Gray PE TDF (CIT - no EDGAR; partnership slide).")
        if not args.list:
            print("\nPass one or more product keys to fetch, e.g.:  python src/fetch_edgar.py hl_paf")
        return

    for key in args.products:
        if key not in reg:
            sys.exit(f"unknown product '{key}' - run with --list to see the registry")
        fetch_product(key)


if __name__ == "__main__":
    main()

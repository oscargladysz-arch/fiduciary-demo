"""
Pre-deploy check: every EDGAR URL the citation drawers link for the Tier 1
cells answers HTTP 200 (rule 15 of the round-2 brief). With --all, every
resolved citation URL in data/citations/*.json is checked.

This is not a hook gate: the build container does not reach sec.gov, so the
check runs on a networked machine before a deploy and its output goes into
docs/DEPLOY_LOG.md. It needs TARK_SEC_CONTACT (SEC fair-access policy) and
paces itself under the SEC rate limit.

Run:  python src/check_edgar_urls.py            # Tier 1 cells
      python src/check_edgar_urls.py --all      # every resolved citation
      python src/check_edgar_urls.py --list     # print the URLs, no network

Exit 0 when every URL answers 200, 1 when any answers otherwise, 2 when the
network cannot be reached at all (a blocked container, not a dead link).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

from build_site import parse_verification_queue  # noqa: E402
from tark_data import product_keys  # noqa: E402

SLEEP = 0.3  # seconds between requests, well under the SEC limit of 10/s


def resolved_urls(cells: list[tuple[str, str]]) -> list[dict]:
    """(product, cell) -> the EDGAR URLs the drawer links, from the offline
    resolver's output. Nothing is invented: an unresolved citation has no
    URL and is reported as such."""
    out = []
    for product, cid in cells:
        cp = BASE / "data" / "citations" / f"{product}.json"
        refs = json.loads(cp.read_text())["cells"].get(cid, []) if cp.exists() else []
        found = False
        for ref in refs:
            if ref.get("match") in ("exact", "form_only") and ref.get("url"):
                out.append({"product": product, "cell": cid, "form": ref.get("form", ""),
                            "filing_date": ref.get("filing_date", ""),
                            "accession": ref.get("accession", ""), "url": ref["url"]})
                found = True
            elif ref.get("match") in ("range", "set"):
                for f in ref.get("filings", []):
                    out.append({"product": product, "cell": cid, "form": ref.get("form", ""),
                                "filing_date": f.get("filing_date", ""),
                                "accession": f.get("accession", ""), "url": f["url"]})
                    found = True
        if not found:
            out.append({"product": product, "cell": cid, "form": "", "filing_date": "",
                        "accession": "", "url": ""})
    return out


def tier1_cells() -> list[tuple[str, str]]:
    q = parse_verification_queue()["queue"]
    return [(it["product"], it["cell"]) for it in q if it["tier"] == 1]


def all_cells() -> list[tuple[str, str]]:
    cells = []
    for k in product_keys():
        cp = BASE / "data" / "citations" / f"{k}.json"
        if cp.exists():
            cells.extend((k, cid) for cid in json.loads(cp.read_text())["cells"])
    return cells


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="every resolved citation, not only Tier 1")
    ap.add_argument("--list", action="store_true", help="print the URLs and exit, no network")
    args = ap.parse_args()

    rows = resolved_urls(all_cells() if args.all else tier1_cells())
    unique = sorted({r["url"] for r in rows if r["url"]})
    print(f"{len(rows)} citation rows, {len(unique)} distinct EDGAR URLs"
          + ("" if args.all else " (Tier 1 of docs/verification_queue.md)"))
    for r in rows:
        print(f"  {r['product']} {r['cell']}: {r['form']} {r['filing_date']} {r['accession']} {r['url'] or 'NO RESOLVED URL'}")
    if args.list:
        return 0

    import requests  # noqa: E402  (only needed on the networked machine)
    from tark_data import sec_user_agent  # noqa: E402  (refuses without TARK_SEC_CONTACT)
    headers = {"User-Agent": sec_user_agent(), "Accept-Encoding": "gzip, deflate"}
    status: dict[str, str] = {}
    unreachable = 0
    for url in unique:
        try:
            resp = requests.get(url, headers=headers, timeout=30, stream=True)
            code = str(resp.status_code)
            resp.close()
        except requests.RequestException as exc:
            code = f"unreachable ({type(exc).__name__})"
            unreachable += 1
        status[url] = code
        print(f"  {code:>6}  {url}")
        time.sleep(SLEEP)
    bad = {u: c for u, c in status.items() if c != "200"}
    missing = [f"{r['product']} {r['cell']}" for r in rows if not r["url"]]
    if unreachable == len(unique) and unique:
        print("\nNo URL could be reached. This machine does not reach sec.gov: run the check "
              "from a networked machine before deploying.")
        return 2
    if bad or missing:
        print(f"\n[FAIL] {len(bad)} URL(s) did not answer 200"
              + (f", {len(missing)} cell(s) have no resolved URL: {', '.join(missing)}" if missing else ""))
        return 1
    print(f"\n[PASS] every one of the {len(unique)} EDGAR URLs answered 200.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

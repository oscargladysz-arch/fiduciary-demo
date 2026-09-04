"""
Tier promotion: census (T1) -> evaluated roster (T2 scaffold).
    python src/promote.py <cik> --key <product_key>

What it does (and what it refuses to do):
  1. R1 identity verification aid: pulls the entity's live SEC submissions
     JSON, cross-checks name/CIK against the census record, and prints the
     identity block (former names included) for the roster decision.
  2. Scaffolds data/products/<key>.json with the canonical 54 cells and the
     paired data/evidence/<key>_evidence.csv (same cells, same statuses).
  3. Prefills ONLY the cells the census fully answers, with status
     'structured' and census provenance (C1/C3):
       4.5 auditor & opinion   (N-CEN PUBLIC_ACCOUNTANT + opinion flag)
       4.6 NAV restatement     (N-CEN IS_NAV_ERROR_CORRECTED - scoped to the
                                latest N-CEN period, stated as such)
       1.10 market price       (unlisted only: documented-unavailable - no
                                exchange listing in SEC submissions)
     Everything else stays 'pending extraction' and lands on the worklist.
     A census field that only PARTLY answers a cell (e.g. N-CEN management
     fee without its base) is NOT prefilled - partial answers dressed as
     facts are how tools lie.
  4. Prints the extraction worklist + the integration checklist (roster
     decision log entry, cohort membership, facts mapping, profiles).
It never touches verified/verified_by, and it never writes a strategy claim.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))
sys.path.insert(0, str(BASE / "src" / "census"))

from edgar_api import submissions  # noqa: E402
from tark_data import CELLS, EVIDENCE_COLUMNS  # noqa: E402

CENSUS = BASE / "data" / "census" / "census.json"
TODAY = date.today().isoformat()
EXTRACTOR = f"census pipeline (structured filing data, {TODAY})"


def blank_cell(element: str) -> dict:
    return {"element": element, "value": "", "status": "pending extraction",
            "source": "", "section": "", "quote": "", "extracted_by": "",
            "verified_by": ""}


def structured_cell(element: str, value: str, source: str, section: str,
                    quote: str, status: str = "structured") -> dict:
    return {"element": element, "value": value, "status": status,
            "source": source, "section": section, "quote": quote,
            "extracted_by": EXTRACTOR, "verified_by": ""}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cik")
    ap.add_argument("--key", required=True,
                    help="product_key for data/products/<key>.json")
    ap.add_argument("--wrapper", default="",
                    help="wrapper label for the registry (defaults to the "
                         "census wrapper class)")
    args = ap.parse_args()
    cik = str(int(args.cik))
    if not re.fullmatch(r"[a-z0-9_]{2,32}", args.key):
        print(f"refused: product key '{args.key}' must be [a-z0-9_]")
        return 1

    census = json.loads(CENSUS.read_text())
    rec = census["entities"].get(cik)
    if rec is None:
        print(f"refused: CIK {cik} is not in the census universe - promote "
              "only what the census can see (or extend enumeration first).")
        return 1
    if rec["promotion"]["status"] != "none":
        print(f"refused: CIK {cik} already promoted as "
              f"{rec['promotion']['product_key']}.")
        return 1
    pj = BASE / "data" / "products" / f"{args.key}.json"
    if pj.exists():
        print(f"refused: {pj} already exists.")
        return 1

    # ---- R1 identity block (live pull, cross-checked against census) ----
    sub = submissions(cik)
    live_name = sub.get("name", "")
    census_name = (rec.get("entity_name_current", {}) or {}).get("value") \
        or rec["name"]
    former = [f.get("name") for f in sub.get("formerNames", [])]
    print("=" * 64)
    print("R1 IDENTITY CHECK")
    print(f"  CIK {cik}")
    print(f"  live submissions name : {live_name}")
    print(f"  census name           : {census_name}")
    print(f"  former names          : {former or 'none'}")
    print(f"  wrapper class (T1)    : {rec['wrapper_class']}")
    for ev in rec["detection_evidence"]:
        print(f"    - {ev}")
    if live_name.strip().lower() != (census_name or "").strip().lower():
        print("  !! name drift between census and live submissions - "
              "resolve before trusting the scaffold (rename? see former "
              "names above). Proceeding, but record this in "
              "data/roster_decisions.md.")
    print("=" * 64)

    # ---- scaffold: 54 canonical cells, census-answerable prefills ----
    cells = {cid: blank_cell(el) for cid, el in CELLS.items()}
    nc = rec.get("ncen")
    if nc:
        ref = nc["investment_company_type"]["ref"]
        as_of = nc["investment_company_type"]["as_of"]
        auditor = nc["auditor"]["value"]
        oq = nc["opinion_qualified"]["value"]
        if auditor:
            cells["4.5"] = structured_cell(
                CELLS["4.5"],
                f"Auditor (N-CEN structured): {auditor}. Audit opinion "
                f"qualified flag: {oq or 'N'} (period {as_of}). Opinion "
                "TEXT and any emphasis-of-matter language require "
                "extraction from the annual report.",
                f"N-CEN {ref} (structured dataset)",
                "PUBLIC_ACCOUNTANT + REGISTRANT.IS_ACCT_OPINION_QUALIFIED",
                f"PUB_ACCOUNTANT_NAME={auditor}; "  # copy-exempt: field=value separator string in the structured-cell quote, not prose
                f"IS_ACCT_OPINION_QUALIFIED={oq or 'N'}")
        nav_err = nc["nav_error_corrected"]["value"]
        cells["4.6"] = structured_cell(
            CELLS["4.6"],
            f"N-CEN structured flag, latest period {as_of} ONLY: "
            f"IS_NAV_ERROR_CORRECTED={nav_err or 'N'}. This is one period's "
            "self-report, not a restatement history - earlier periods "
            "require extraction.",
            f"N-CEN {ref} (structured dataset)",
            "REGISTRANT.IS_NAV_ERROR_CORRECTED",
            f"IS_NAV_ERROR_CORRECTED={nav_err or 'N'}")
    listed = (rec.get("listed", {}) or {}).get("value")
    if listed is False:
        cells["1.10"] = structured_cell(
            CELLS["1.10"],
            "No market price series exists: no exchange listing in SEC "
            "submissions (an OTC quotation, if any, is not an exchange "
            "listing). Premium/discount is structurally n/a for this "
            "wrapper.",
            "SEC submissions JSON + company_tickers.json",
            "exchanges[]",
            f"exchanges={rec.get('exchanges', {}).get('value') or []}",
            status="n/a - documented-unavailable (structured: unlisted)")

    product = {"product_key": args.key, "fund_name": live_name, "cik": cik,
               "wrapper": args.wrapper or rec["wrapper_class"],
               "depth": "cohort", "cells": cells}
    pj.write_text(json.dumps(product, indent=1))

    ev_path = BASE / "data" / "evidence" / f"{args.key}_evidence.csv"
    with open(ev_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=EVIDENCE_COLUMNS)
        w.writeheader()
        for cid, c in cells.items():
            w.writerow({"cell_id": cid, "element": c["element"],
                        "value": c["value"], "source_doc": c["source"],
                        "source_section": c["section"], "quote": c["quote"],
                        "local_file": "", "date_pulled": TODAY
                        if c["value"] else "",
                        "extracted_by": c["extracted_by"],
                        "verified_by": "", "status": c["status"]})

    rec["promotion"] = {"status": "evaluated", "product_key": args.key}
    CENSUS.write_text(json.dumps(census, indent=1))

    prefilled = [cid for cid, c in cells.items()
                 if c["status"].startswith(("structured", "n/a"))]
    worklist = [cid for cid, c in cells.items()
                if c["status"] == "pending extraction"]
    print(f"scaffolded {pj.name}: {len(prefilled)} census-prefilled cells "
          f"({', '.join(prefilled)}), {len(worklist)} on the extraction "
          "worklist.")
    print("EXTRACTION WORKLIST:", ", ".join(worklist))
    print("""INTEGRATION CHECKLIST (gates will hold you to these):
  - data/roster_decisions.md: admission rationale (R1/R3)
  - fetch primary filings into data/raw/<key>/ + data/manifest.csv
  - extract the worklist cells (status extracted-unverified, cite everything)
  - cohort decision: member of an existing cohort, or uncohorted with
    rationale (R3). Depth stays 'cohort' unless argued otherwise
  - src/build_facts.py MAPPING + COHORT_META entry
  - src/tark_liquidity.py LIQUIDITY_PROFILES + src/tark_benchmark.py
    PRODUCT_PROFILES entries
  - python src/build_census.py (refresh promotion links)
  - full gate chain before commit""")
    return 0


if __name__ == "__main__":
    main()

"""
Tier promotion: census (T1) -> evaluated roster (T2 scaffold).
    python src/promote.py <cik> --key <product_key>

What it does (and what it refuses to do):
  1. R1 identity verification aid: pulls the entity's live SEC submissions
     JSON, cross-checks name/CIK against the census record, and prints the
     identity block (former names included) for the roster decision.
  2. Scaffolds data/products/<key>.json with the canonical 55 cells and the
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
As a library: promote.scaffold(cik, key, wrapper='') does steps 2 and 3 under
the data root (TARK_DATA_DIR) and returns what it wrote, so the ingest and
the worker call it without a subprocess. The census lookup and the live
submissions pull are the same in both paths.
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
from tark_data import CELLS, DATA, EVIDENCE_COLUMNS  # noqa: E402

# every path under the data root, so a run against a copy of the record
# (TARK_DATA_DIR) writes the copy and never the repository
CENSUS = DATA / "census" / "census.json"
TODAY = date.today().isoformat()
EXTRACTOR = f"census pipeline (structured filing data, {TODAY})"
KEY_RE = re.compile(r"[a-z0-9_]{2,32}")


class ScaffoldRefused(Exception):
    """The scaffold does not run: the reason in plain words."""


def blank_cell(element: str) -> dict:
    return {"element": element, "value": "", "status": "pending extraction",
            "source": "", "section": "", "quote": "", "extracted_by": "",
            "verified_by": ""}


def structured_cell(element: str, value: str, source: str, section: str,
                    quote: str, status: str = "structured") -> dict:
    return {"element": element, "value": value, "status": status,
            "source": source, "section": section, "quote": quote,
            "extracted_by": EXTRACTOR, "verified_by": ""}


def census_cells(rec: dict) -> tuple[dict, list[str]]:
    """The 55 canonical cells with the census-answerable prefills, and the
    notes a person should read (a cell left pending with the reason)."""
    notes = []
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
    listed = (rec.get("listed_common", rec.get("listed", {})) or {}).get("value")
    if listed is None:
        notes.append("1.10 left pending: the census cannot tell whether the common shares are "
                     "listed (listed_common is null with its reason), nothing prefilled")
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
    return cells, notes


def scaffold(cik: str | int, key: str, wrapper: str = "", submissions_fn=None) -> dict:
    """Steps 2 and 3 as a library call: the identity check against the live
    submissions (submissions_fn, the census cache by default), the product
    JSON and the evidence CSV under the data root, the census promotion
    recorded. Returns what it wrote and the identity block. Refuses a CIK
    the census cannot see, a promoted CIK, an existing product file and a
    malformed key."""
    cik = str(int(cik))
    if not KEY_RE.fullmatch(key):
        raise ScaffoldRefused(f"product key '{key}' must be [a-z0-9_]{{2,32}}")
    if not CENSUS.exists():
        raise ScaffoldRefused(f"census not on disk ({CENSUS})")
    census = json.loads(CENSUS.read_text())
    rec = census["entities"].get(cik)
    if rec is None:
        raise ScaffoldRefused(f"CIK {cik} is not in the census universe, promote only what the census "
                              "can see (or extend enumeration first)")
    if rec.get("promotion", {}).get("status", "none") != "none":
        raise ScaffoldRefused(f"CIK {cik} already promoted as {rec['promotion']['product_key']}")
    pj = DATA / "products" / f"{key}.json"
    if pj.exists():
        raise ScaffoldRefused(f"{pj} already exists")
    sub = (submissions_fn or submissions)(cik)
    live_name = sub.get("name", "")
    census_name = (rec.get("entity_name_current", {}) or {}).get("value") or rec["name"]
    former = [f.get("name") for f in sub.get("formerNames", [])]
    drift = live_name.strip().lower() != (census_name or "").strip().lower()
    cells, notes = census_cells(rec)
    product = {"product_key": key, "fund_name": live_name, "cik": cik,
               "wrapper": wrapper or rec["wrapper_class"],
               "depth": "cohort", "cells": cells}
    pj.parent.mkdir(parents=True, exist_ok=True)
    pj.write_text(json.dumps(product, indent=1))
    ev_path = DATA / "evidence" / f"{key}_evidence.csv"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
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
    rec["promotion"] = {"status": "evaluated", "product_key": key}
    CENSUS.write_text(json.dumps(census, indent=1))
    prefilled = [cid for cid, c in cells.items() if c["status"].startswith(("structured", "n/a"))]
    worklist = [cid for cid, c in cells.items() if c["status"] == "pending extraction"]
    return {"product_path": pj, "evidence_path": ev_path, "prefilled": prefilled, "worklist": worklist,
            "notes": notes, "name_drift": drift,
            "identity": {"cik": cik, "live_name": live_name, "census_name": census_name, "former_names": former,
                         "wrapper_class": rec["wrapper_class"], "detection_evidence": list(rec.get("detection_evidence", []))}}


CHECKLIST = """INTEGRATION CHECKLIST (gates will hold you to these):
  - data/roster_decisions.md: admission rationale (R1/R3)
  - fetch primary filings into data/raw/<key>/ + data/manifest.csv
  - extract the worklist cells (status extracted-unverified, cite everything)
  - cohort decision: member of an existing cohort, or uncohorted with
    rationale (R3). Depth stays 'cohort' unless argued otherwise
  - data/registry.json entry: cohort (and the cohort's members list), depth,
    membership_rationale, as_of, wrapper_type, pricing_class, nav_cadence,
    leverage_regime, held_returns, advisers, adviser_keys,
    declared_benchmarks, source_cells, filings (every field with its
    source). validate_data refuses a product that is in data/products but
    not in the registry
  - src/build_facts.py MAPPING entry (cell to typed fact, machine-checked)
  - python src/build_census.py (refresh promotion links)
  - full gate chain before commit"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cik")
    ap.add_argument("--key", required=True,
                    help="product_key for data/products/<key>.json")
    ap.add_argument("--wrapper", default="",
                    help="wrapper label for the registry (defaults to the "
                         "census wrapper class)")
    args = ap.parse_args()
    try:
        out = scaffold(args.cik, args.key, args.wrapper)
    except ScaffoldRefused as e:
        print(f"refused: {e}.")
        return 1
    ident = out["identity"]
    print("=" * 64)
    print("R1 IDENTITY CHECK")
    print(f"  CIK {ident['cik']}")
    print(f"  live submissions name : {ident['live_name']}")
    print(f"  census name           : {ident['census_name']}")
    print(f"  former names          : {ident['former_names'] or 'none'}")
    print(f"  wrapper class (T1)    : {ident['wrapper_class']}")
    for ev in ident["detection_evidence"]:
        print(f"    - {ev}")
    if out["name_drift"]:
        print("  !! name drift between census and live submissions - "
              "resolve before trusting the scaffold (rename? see former "
              "names above). Proceeding, but record this in "
              "data/roster_decisions.md.")
    print("=" * 64)
    for n in out["notes"]:
        print("  " + n)
    print(f"scaffolded {out['product_path'].name}: {len(out['prefilled'])} census-prefilled cells "
          f"({', '.join(out['prefilled'])}), {len(out['worklist'])} on the extraction "
          "worklist.")
    print("EXTRACTION WORKLIST:", ", ".join(out["worklist"]))
    print(CHECKLIST)
    return 0


if __name__ == "__main__":
    sys.exit(main())

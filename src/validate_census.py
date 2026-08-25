"""
Census validator — run in the pre-commit gate.
    python src/validate_census.py
Enforces: schema shape, C3 provenance completeness (every shipped field has
source/ref/as_of or an explicit unavailable reason), C2 (name_hint always
non-authoritative), classification evidence presence, CIK dedupe by
construction, roster-link resolution (every product CIK links), count sanity.
Exit 0 = clean.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CENSUS = BASE / "data" / "census" / "census.json"
UNIVERSE = BASE / "data" / "census" / "universe.json"

PROVENANCE_SOURCES = {"ncen", "xbrl", "submissions", "efts"}
CLASSES = {"bdc", "interval_23c3", "tender_cef", "nontraded_reit",
           "listed_cef", "unlisted_cef_other", "nontraded_34act_other"}


def field_errors(cik: str, name: str, f, path: str) -> list[str]:
    errs = []
    if not isinstance(f, dict):
        return [f"{cik}:{path}: field is not a provenance dict"]
    if "value" not in f:
        errs.append(f"{cik}:{path}: no value key")
    if f.get("source") not in PROVENANCE_SOURCES:
        errs.append(f"{cik}:{path}: bad source '{f.get('source')}'")
    if not f.get("ref"):
        errs.append(f"{cik}:{path}: no ref")
    if not f.get("as_of"):
        errs.append(f"{cik}:{path}: no as_of")
    if f.get("value") is None and not f.get("reason"):
        errs.append(f"{cik}:{path}: null value without reason")
    return errs


def main() -> int:
    errs: list[str] = []
    if not CENSUS.exists() or not UNIVERSE.exists():
        print("[FAIL] census: data/census/{census,universe}.json missing")
        return 1
    doc = json.loads(CENSUS.read_text())
    uni = json.loads(UNIVERSE.read_text())

    ents = doc.get("entities", {})
    if len(ents) != doc.get("total"):
        errs.append(f"total mismatch: {doc.get('total')} vs {len(ents)}")
    if len(ents) < 300:
        errs.append(f"count sanity: only {len(ents)} entities (expected "
                    "several hundred)")

    roster_ciks = {}
    for pj in sorted((BASE / "data" / "products").glob("*.json")):
        pd = json.loads(pj.read_text())
        roster_ciks[str(int(pd["cik"]))] = pd["product_key"]

    PROV_FIELDS = ("listed", "tickers", "first_filing", "latest_annual",
                   "filing_summary", "total_assets", "n23c3a_activity",
                   "tender_activity", "interval_crosscheck",
                   "entity_name_current", "exchanges",
                   "nav_per_share_structured")
    for cik, rec in ents.items():
        if str(int(rec.get("cik", -1))) != cik:
            errs.append(f"{cik}: cik key/value mismatch")
        if rec.get("wrapper_class") not in CLASSES:
            errs.append(f"{cik}: bad wrapper_class "
                        f"'{rec.get('wrapper_class')}'")
        if not rec.get("detection_evidence"):
            errs.append(f"{cik}: classification without detection_evidence")
        nh = rec.get("name_hint", {})
        if nh and nh.get("authoritative") is not False:
            errs.append(f"{cik}: name_hint not marked non-authoritative (C2)")
        for fld in PROV_FIELDS:
            if fld in rec:
                errs.extend(field_errors(cik, rec["name"], rec[fld], fld))
        for fld, f in rec.get("ncen", {}).items():
            errs.extend(field_errors(cik, rec["name"], f, f"ncen.{fld}"))
        promo = rec.get("promotion", {})
        if promo.get("status") not in ("none", "evaluated", "verified_in_part"):
            errs.append(f"{cik}: bad promotion status")
        if promo.get("status") != "none" and promo.get("product_key") \
                not in roster_ciks.values():
            errs.append(f"{cik}: promotion links unknown product "
                        f"'{promo.get('product_key')}'")

    # every roster product must resolve to a census entity (both ways)
    for cik, key in roster_ciks.items():
        rec = ents.get(cik)
        if rec is None:
            errs.append(f"roster {key} (CIK {cik}): not in census")
        elif rec["promotion"].get("product_key") != key:
            errs.append(f"roster {key}: census promotion link missing/wrong")

    # universe/census class counts must agree
    if doc.get("counts_by_class") != uni.get("counts_by_class"):
        errs.append("counts_by_class drift between universe and census")

    if errs:
        print(f"[FAIL] census: {len(errs)} violation(s)")
        for e in errs[:25]:
            print("       -", e)
        return 1
    promoted = sum(1 for r in ents.values()
                   if r["promotion"]["status"] != "none")
    print(f"[ok]   census: {len(ents)} entities, provenance complete, "
          f"{promoted} promoted links, counts consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())

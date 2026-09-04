"""
Census Phase 2 — structured ingestion (T1 facts; C3: every field carries
{source, ref, as_of} provenance or does not ship).

Sources merged into data/census/census.json (idempotent; all pulls cached):
  - universe.json          wrapper class + detection evidence (Phase 1)
  - N-CEN structured sets  registrant/fund facts for '40-Act filers: adviser,
                           auditor, IS_INTERVAL self-classification (cross-
                           checked against N-23C3A behavior — agreement OR
                           disagreement recorded honestly), avg net assets,
                           management fee, net operating expenses, NAV/share,
                           NAV-error-corrected flag
  - XBRL companyfacts      us-gaap Assets for '34-Act filers (REITs/BDCs);
                           NAV/share is issuer-custom-tagged -> honestly
                           'unavailable-structured'
  - submissions JSON       tickers/exchange, first filing, latest annual,
                           filing-activity summary (all census entities)

Run: python src/census/build_census.py
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

from edgar_api import BASE, RAW, get, submissions

OUT = BASE / "data" / "census"
NCEN_DIR = RAW / "ncen"
QUARTERS = ["2025q3", "2025q4", "2026q1", "2026q2"]  # trailing year (annual form)

# C2: name_hint tokens — derived from the NAME ONLY, non-authoritative,
# excluded from filters by default, always badged "hint" in UI
HINT_TOKENS = {
    "credit": "credit?", "lending": "credit?", "income": "income?",
    "real estate": "real-estate?", "realty": "real-estate?",
    "property": "real-estate?", "infrastructure": "infrastructure?",
    "private equity": "private-equity?", "venture": "venture?",
    "growth": "growth?", "secondaries": "secondaries?", "bond": "bond?",
    "municipal": "municipal?", "tax": "tax-managed?", "energy": "energy?",
    "royalt": "royalties?", "reinsurance": "reinsurance?",
}
# Documentation strings written into data/census/census.json: the note every
# name_hint carries (C2) and the file's 'what' line. sync_notes.py rewrites
# the data from these constants and validate_census.py checks that the two
# agree, so edit the text here only.
NAME_HINT_NOTE = ("derived from the fund NAME only, never a strategy claim "
                  "(C2). Excluded from filters by default")
CENSUS_WHAT = ("Tark T1 census: structured facts with per-field provenance "
               "{source, ref, as_of} (C3). Wrapper classes from filing "
               "behavior with detection evidence (C2: no strategy claims)")


def tsv_rows(path: Path):
    with open(path, newline="", encoding="utf-8", errors="ignore") as fh:
        yield from csv.DictReader(fh, delimiter="\t")


def load_ncen() -> dict[str, dict]:
    """Latest N-CEN per CIK across the trailing four quarterly datasets."""
    ck = RAW / "ncen_extract.json"
    if ck.exists():
        return json.loads(ck.read_text())
    by_cik: dict[str, dict] = {}
    for q in QUARTERS:
        qdir = NCEN_DIR / q
        if not qdir.exists():
            continue
        subs = {}
        for r in tsv_rows(qdir / "SUBMISSION.tsv"):
            subs[r["ACCESSION_NUMBER"]] = {
                "cik": str(int(r["CIK"])), "filed": r["FILING_DATE"],
                "period": r["REPORT_ENDING_PERIOD"]}
        reg = {r["ACCESSION_NUMBER"]: r for r in tsv_rows(qdir / "REGISTRANT.tsv")}
        acct = {}
        for r in tsv_rows(qdir / "PUBLIC_ACCOUNTANT.tsv"):
            acct.setdefault(r["ACCESSION_NUMBER"], []).append(
                {"name": r["PUB_ACCOUNTANT_NAME"], "pcaob": r["PCAOB_NUM"],
                 "state": r["STATE"], "country": r["COUNTRY"]})
        funds: dict[str, list] = {}
        advisers: dict[str, list] = {}
        for r in tsv_rows(qdir / "ADVISER.tsv"):
            # advisers only: sub-adviser rows carry their own ADVISER_TYPE. An
            # "or True" here once folded every row into the adviser list; the
            # shipped census.json was built with it. To regenerate:
            #   rm data/census/raw/ncen_extract.json && python src/census/build_census.py
            # (network and TARK_SEC_CONTACT required; adviser lists may move).
            if r.get("ADVISER_TYPE", "").lower().startswith("adviser"):
                advisers.setdefault(r["FUND_ID"], []).append(
                    {"name": r["ADVISER_NAME"], "type": r["ADVISER_TYPE"],
                     "affiliated": r.get("IS_AFFILIATED", "")})
        for r in tsv_rows(qdir / "FUND_REPORTED_INFO.tsv"):
            funds.setdefault(r["ACCESSION_NUMBER"], []).append({
                "fund_id": r["FUND_ID"], "fund_name": r["FUND_NAME"],
                "series_id": r["SERIES_ID"],
                "is_interval": r.get("IS_INTERVAL", ""),
                "is_fund_of_fund": r.get("IS_FUND_OF_FUND", ""),
                "monthly_avg_net_assets": r.get("MONTHLY_AVG_NET_ASSETS", ""),
                "daily_avg_net_assets": r.get("DAILY_AVG_NET_ASSETS", ""),
                "management_fee": r.get("MANAGEMENT_FEE", ""),
                "net_operating_expenses": r.get("NET_OPERATING_EXPENSES", ""),
                "nav_per_share": r.get("NAV_PER_SHARE", ""),
                "has_line_of_credit": r.get("HAS_LINE_OF_CREDIT", ""),
                "has_exp_limit": r.get("HAS_EXP_LIMIT", ""),
                "advisers": advisers.get(r["FUND_ID"], []),
            })
        for acc, meta in subs.items():
            cik = meta["cik"]
            cur = by_cik.get(cik)
            if cur and cur["filed"] >= meta["filed"]:
                continue
            rrow = reg.get(acc, {})
            by_cik[cik] = {
                "accession": acc, "filed": meta["filed"],
                "period": meta["period"],
                "registrant_name": rrow.get("REGISTRANT_NAME", ""),
                "investment_company_type": rrow.get("INVESTMENT_COMPANY_TYPE", ""),
                "total_series": rrow.get("TOTAL_SERIES", ""),
                "is_nav_error_corrected": rrow.get("IS_NAV_ERROR_CORRECTED", ""),
                "is_opinion_qualified": rrow.get("IS_ACCT_OPINION_QUALIFIED", ""),
                "is_material_weakness": rrow.get("IS_MATERIAL_WEAKNESS_NOTED", ""),
                "accountants": acct.get(acc, []),
                "funds": funds.get(acc, []),
            }
    ck.write_text(json.dumps(by_cik))
    print(f"N-CEN extract: {len(by_cik)} registrants (latest filing per CIK)")
    return by_cik


def xbrl_assets(cik: int) -> dict | None:
    """us-gaap Assets latest instant, via the single-concept companyconcept
    endpoint (cached) - full companyfacts payloads run to tens of MB for old
    REITs and would make the sweep take hours."""
    p = RAW / "companyconcept" / f"CIK{cik:010d}_Assets.json"
    p.parent.mkdir(exist_ok=True)
    if p.exists():
        d = json.loads(p.read_text())
        if d.get("_miss"):
            return None
    else:
        try:
            d = get("https://data.sec.gov/api/xbrl/companyconcept/"
                    f"CIK{cik:010d}/us-gaap/Assets.json")
        except Exception:  # noqa: BLE001 - 404 = no XBRL Assets fact
            p.write_text(json.dumps({"_miss": True}))
            return None
        p.write_text(json.dumps(d))
    try:
        units = d["units"]["USD"]
        best = max((u for u in units if u.get("end") and u.get("val") is not None),
                   key=lambda u: u["end"])
        return {"value": best["val"], "as_of": best["end"],
                "accn": best.get("accn", "")}
    except (KeyError, ValueError):
        return None


def num(s) -> float | None:
    """N-CEN numeric fields arrive as strings; never let one crash the build."""
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def name_hint(name: str) -> list[str]:
    low = name.lower()
    return sorted({tag for tok, tag in HINT_TOKENS.items() if tok in low})


def F(value, source: str, ref: str, as_of: str):
    """C3 field wrapper: no provenance, no ship."""
    return {"value": value, "source": source, "ref": ref, "as_of": as_of}


def main() -> None:
    uni = json.loads((OUT / "universe.json").read_text())
    ncen = load_ncen()
    roster = {}
    for pj in sorted((BASE / "data" / "products").glob("*.json")):
        pd = json.loads(pj.read_text())
        roster[str(int(pd["cik"]))] = pd["product_key"]

    today = date.today().isoformat()
    census: dict[str, dict] = {}
    n = len(uni["entities"])
    for i, (cik, ent) in enumerate(uni["entities"].items(), 1):
        if i % 200 == 0:
            print(f"  …{i}/{n}", flush=True)
        try:
            sub = submissions(cik)
        except Exception:  # noqa: BLE001 - dead CIK: keep enumeration facts only
            sub = None
        rec: dict = {
            "cik": int(cik),
            "name": ent["name"],
            "wrapper_class": ent["wrapper_class"],
            "all_signals": ent["all_signals"],
            "detection_evidence": ent["detection_evidence"],
            "listed": {**F(ent["listed"], "submissions",
                           "company_tickers.json + submissions exchanges "
                           "(OTC quotation excluded)", today),
                       **({"reason": "submissions unreachable at enumeration, listing unknown"}
                          if ent["listed"] is None else {})},
            "tickers": F(ent["tickers"], "submissions",
                         "SEC company_tickers.json", today),
            "name_hint": {"value": name_hint(ent["name"]),
                          "authoritative": False,
                          "note": NAME_HINT_NOTE},
            "promotion": {"status": "evaluated", "product_key": roster[cik]}
                         if cik in roster else {"status": "none"},
        }
        if ent.get("n23c3a"):
            rec["n23c3a_activity"] = F(ent["n23c3a"], "efts",
                                       "EFTS forms=N-23C3A year-split", today)
        if ent.get("sctoi"):
            rec["tender_activity"] = F(ent["sctoi"], "efts",
                                       "EFTS forms=SC TO-I year-split", today)
        if sub:
            recent = sub.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            accs = recent.get("accessionNumber", [])
            first = min(dates) if dates else None
            oldest = sub.get("filings", {}).get("files", [])
            if oldest:  # older filings live in sidecar files; earliest known
                first = min([first or "9999"] +
                            [f.get("filingFrom", "9999") for f in oldest])
            rec["entity_name_current"] = F(sub.get("name", ""), "submissions",
                                           f"CIK{int(cik):010d}.json", today)
            if first and first != "9999":
                rec["first_filing"] = F(first, "submissions",
                                        f"CIK{int(cik):010d}.json", today)
            latest_annual = None
            for f, d_, a in zip(forms, dates, accs):
                if f in ("10-K", "N-CSR") and (latest_annual is None
                                               or d_ > latest_annual["date"]):
                    latest_annual = {"form": f, "date": d_, "accession": a}
            if latest_annual:
                rec["latest_annual"] = F(latest_annual, "submissions",
                                         latest_annual["accession"], today)
            hist = Counter(forms)
            rec["filing_summary"] = F(dict(hist.most_common(8)), "submissions",
                                      f"CIK{int(cik):010d}.json", today)
            exch = [e for e in sub.get("exchanges", []) if e]
            if exch:
                rec["exchanges"] = F(sorted(set(exch)), "submissions",
                                     f"CIK{int(cik):010d}.json", today)
        # ---- N-CEN facts ('40-Act filers) ----
        nc = ncen.get(cik)
        if nc:
            ref = nc["accession"]
            as_of = nc["period"]
            rec["ncen"] = {
                "investment_company_type": F(nc["investment_company_type"],
                                             "ncen", ref, as_of),
                "total_series": F(nc["total_series"], "ncen", ref, as_of),
                "nav_error_corrected": F(nc["is_nav_error_corrected"],
                                         "ncen", ref, as_of),
                "opinion_qualified": F(nc["is_opinion_qualified"],
                                       "ncen", ref, as_of),
                "auditor": F("; ".join(a["name"] for a in nc["accountants"]),
                             "ncen", ref, as_of),
            }
            funds = nc.get("funds", [])
            if funds:
                f0 = max(funds, key=lambda f: num(f["monthly_avg_net_assets"])
                         or num(f["daily_avg_net_assets"]) or 0)
                assets = (num(f0["monthly_avg_net_assets"])
                          or num(f0["daily_avg_net_assets"]))
                rec["ncen"]["primary_fund"] = F(
                    {"fund_name": f0["fund_name"], "series_id": f0["series_id"],
                     "is_interval": f0["is_interval"],
                     "avg_net_assets": assets,
                     "management_fee": num(f0["management_fee"]),
                     "net_operating_expenses": num(
                         f0["net_operating_expenses"]),
                     "nav_per_share": num(f0["nav_per_share"]),
                     "advisers": [a["name"] for a in f0["advisers"]][:4]},
                    "ncen", ref, as_of)
                if assets:
                    rec["total_assets"] = F(
                        {"value": assets,
                         "basis": "N-CEN average net assets (largest series)"},
                        "ncen", ref, as_of)
                # C1 cross-check: self-classification vs filing behavior
                self_int = any(f["is_interval"] == "Y" for f in funds)
                behav_int = "n23c3a_activity" in rec
                rec["interval_crosscheck"] = F(
                    {"ncen_self_classified_interval": self_int,
                     "n23c3a_filing_behavior": behav_int,
                     "agreement": self_int == behav_int},
                    "ncen", ref, as_of)
        # ---- XBRL assets ('34-Act filers) ----
        if ent["wrapper_class"] in ("nontraded_reit", "bdc",
                                    "nontraded_34act_other") and sub:
            xa = xbrl_assets(int(cik))
            if xa:
                rec["total_assets"] = F(
                    {"value": xa["value"], "basis": "us-gaap:Assets (GAAP "
                     "total assets, latest instant)"},
                    "xbrl", xa["accn"] or
                    f"companyconcept/CIK{int(cik):010d}/us-gaap/Assets",
                    xa["as_of"])
            else:
                rec["total_assets"] = {"value": None, "source": "xbrl",
                                       "ref": "companyconcept",
                                       "as_of": today,
                                       "reason": "unavailable-structured: no "
                                       "us-gaap:Assets fact tagged"}
            rec["nav_per_share_structured"] = {
                "value": None, "source": "xbrl", "ref": "companyconcept",
                "as_of": today,
                "reason": "unavailable-structured: NAV/share is issuer-custom "
                          "XBRL tagging - not guessed at T1"}
        census[cik] = rec

    doc = {
        "what": CENSUS_WHAT,
        "tiers": {"T1": "structured filing data (this file)",
                  "T2": "AI-extracted, unverified (evaluated roster)",
                  "T3": "human-verified (evidence CSVs signed)"},
        "as_of": today,
        "counts_by_class": uni["counts_by_class"],
        "total": len(census),
        "entities": census,
    }
    # P2-11: share-class aware listing and the N-23C3A recency rule, applied
    # here so a rebuild reproduces the committed classification
    from reclassify_listed import apply as _reclassify
    _reclassify(doc, uni)
    (OUT / "census.json").write_text(json.dumps(doc, indent=1))
    promoted = sum(1 for r in census.values()
                   if r["promotion"]["status"] != "none")
    with_assets = sum(1 for r in census.values() if r.get("total_assets", {})
                      .get("value"))
    print(f"census.json: {len(census)} entities | promoted links {promoted} | "
          f"with structured assets {with_assets}")


if __name__ == "__main__":
    main()

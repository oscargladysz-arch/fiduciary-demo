"""
Census Phase 1 — universe enumeration from filing behavior (C2: wrapper
classification only, evidence-based; NO strategy claims at T1).

Sources:
  - EFTS full-text search (efts.sec.gov), empty-query + forms filter,
    YEAR-SPLIT (each year < the 10k window), checkpointed per (form, year):
    N-23C3A (intervals), N-54A (BDC elections), SC TO-I (tender candidates),
    N-2/486BPOS/486APOS (N-2 lineage). Hits carry ciks/display_names/
    file_date, so per-CIK filing counts and first/last dates (cadence
    evidence) fall out of the same pull.
  - browse-edgar company search SIC=6798 + type=10-K (REIT candidates).
  - SEC company_tickers.json as the listing oracle.

Classes (each record carries detection_evidence — the signals that fired):
  bdc / interval_23c3 / tender_cef / nontraded_reit / listed_cef
Precedence on overlap: bdc > interval_23c3 > tender_cef > nontraded_reit >
listed_cef. EFTS coverage is 2001+ — funds whose only relevant filings
predate 2001 are not seen (recorded in method_notes).

Run: python src/census/enumerate.py  -> data/census/universe.json + counts
"""
from __future__ import annotations

import json
import urllib.parse
from datetime import date

from edgar_api import (BASE, RAW, companies_by_query, company_tickers, get,
                       submissions)

OUT = BASE / "data" / "census"
THIS_YEAR = date.today().year

# Documentation strings written into data/census/universe.json (and copied
# into census.json with each record). sync_notes.py rewrites the data from
# these constants and validate_census.py checks that the two agree, so edit
# the text here only.
UNIVERSE_WHAT = ("T1 census candidate universe: wrapper classification from "
                 "filing behavior only (C2: no strategy claims). Each record "
                 "carries detection_evidence")
METHOD_NOTES = [
    "form filers enumerated via EFTS full-text search, empty query + "
    "forms filter, year-split 2001-present, checkpointed",
    "REIT candidates via browse-edgar company search SIC=6798 + "
    "type=10-K",
    "listing oracle: SEC company_tickers.json",
    "precedence on overlapping signals: bdc > interval_23c3 > "
    "tender_cef > nontraded_reit > listed_cef > unlisted_cef_other",
    "'listed' means a real exchange listing confirmed in SEC "
    "submissions. An OTC quotation alone does not count (non-traded "
    "vehicles can carry OTC tickers)",
    "unlisted_cef_other: N-2-family registrants that are neither "
    "exchange-listed nor show tender/interval filing behavior - the "
    "wrapper is real but its liquidity mechanism (if any) is not "
    "detectable from filing behavior",
    "EFTS coverage is 2001+. Funds whose only relevant filings "
    "predate 2001 are not seen",
    "roster reconciliation: an evaluated roster product whose "
    "wrapper has no distinguishing form signature (non-traded "
    "'34-Act reporting company) is added individually with its "
    "filing facts as evidence. That class CANNOT be enumerated "
    "universe-wide and its census count covers roster entries only",
]
# detection_evidence text composed from constants (the rest of each record's
# evidence list is built from its own filing facts)
N23C3A_EVIDENCE_NOTE = ("(form exists only for Rule 23c-3 funds. EFTS "
                        "coverage 2001+)")
UNLISTED_CEF_EVIDENCE = ("no exchange listing, no SC TO-I or N-23C3A "
                         "activity observed (EFTS coverage 2001+). Liquidity "
                         "mechanism, if any, not detectable from filing "
                         "behavior")


def n23c3a_evidence(count: int, first: str, last: str) -> str:
    """The single detection_evidence entry of an interval_23c3 record."""
    return (f"{count} Form N-23C3A filings, {first} to {last} "
            f"{N23C3A_EVIDENCE_NOTE}")


def constant_evidence(rec: dict) -> list[str] | None:
    """The detection_evidence a universe or census record must carry where
    part of it is composed from the constants above, or None for classes
    whose evidence is built from filing facts alone. sync_notes.py rewrites
    the data to this and validate_census.py checks against it."""
    ev = rec.get("detection_evidence") or []
    if rec.get("wrapper_class") == "interval_23c3":
        n = (rec.get("n23c3a")
             or rec.get("n23c3a_activity", {}).get("value") or {})
        if not n:
            return None
        return [n23c3a_evidence(n["count"], n["first"], n["last"])]
    if rec.get("wrapper_class") == "unlisted_cef_other":
        return ev[:1] + [UNLISTED_CEF_EVIDENCE]
    return None


def efts_form_filers(label: str, forms: str, y0: int = 2001) -> dict:
    """{cik: {name, count, first, last}} for all filings of `forms`,
    year-split and checkpointed per year."""
    ck = RAW / f"efts_{label}.json"
    state = json.loads(ck.read_text()) if ck.exists() else {"years": {},
                                                            "filers": {}}
    for year in range(y0, THIS_YEAR + 1):
        ykey = str(year)
        if state["years"].get(ykey) == "done":
            continue
        frm = 0
        total = None
        while True:
            q = urllib.parse.urlencode({
                "q": "", "forms": forms, "dateRange": "custom",
                "startdt": f"{year}-01-01", "enddt": f"{year}-12-31",
                "from": str(frm), "size": "100"})
            d = json.loads(get(f"https://efts.sec.gov/LATEST/search-index?{q}",
                               as_json=False))
            hits = d["hits"]["hits"]
            total = d["hits"]["total"]["value"]
            for h in hits:
                src = h["_source"]
                fdate = src.get("file_date", "")
                names = src.get("display_names", [])
                for i, cik in enumerate(src.get("ciks", [])):
                    cik = str(int(cik))
                    rec = state["filers"].setdefault(
                        cik, {"name": "", "count": 0, "first": fdate,
                              "last": fdate})
                    rec["count"] += 1
                    rec["first"] = min(rec["first"], fdate)
                    rec["last"] = max(rec["last"], fdate)
                    if i < len(names) and not rec["name"]:
                        rec["name"] = names[i].split("  (CIK")[0].strip()
            frm += 100
            if frm >= min(total, 9900) or not hits:
                break
        if total is not None and total > 9900:
            state["years"][ykey] = f"TRUNCATED at 9900 of {total}"
        else:
            state["years"][ykey] = "done"
        ck.write_text(json.dumps(state))
        print(f"  efts {label} {year}: total {total}, filers so far "
              f"{len(state['filers'])}", flush=True)
    trunc = {y: v for y, v in state["years"].items() if v != "done"}
    if trunc:
        print(f"  !! {label} truncated years: {trunc}")
    return state["filers"]


def formd_dark_universe() -> dict:
    """Count (not enumerate) private pooled funds filing Form D in the
    trailing 24 months — the universe a 401(k) fiduciary cannot see into.
    Month-split so elasticsearch's 10k total cap never bites; checkpointed."""
    ck = RAW / "formd_dark.json"
    if ck.exists():
        return json.loads(ck.read_text())
    import calendar
    end = date.today()
    y0, m0 = (end.year - 2, end.month + 1) if end.month < 12 \
        else (end.year - 1, 1)
    months, y, m = [], y0, m0
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    tot, capped = {"D": 0, "D/A": 0}, []
    for forms in ("D", "D/A"):
        for (y, m) in months:
            last = calendar.monthrange(y, m)[1]
            q = urllib.parse.urlencode({
                "q": '"Pooled Investment Fund"', "forms": forms,
                "dateRange": "custom", "startdt": f"{y}-{m:02d}-01",
                "enddt": f"{y}-{m:02d}-{last:02d}", "from": "0", "size": "1"})
            d = json.loads(get(
                f"https://efts.sec.gov/LATEST/search-index?{q}",
                as_json=False))
            t = d["hits"]["total"]
            tot[forms] += t["value"]
            if t.get("relation") == "gte":
                capped.append([forms, y, m])
    out = {
        "what": "Form D dark universe - private pooled funds raising in the "
                "trailing 24 months (funds a 401(k) fiduciary CANNOT see "
                "into: no NAV, no fee table, no structured data)",
        "query": "EFTS full-text search, phrase 'Pooled Investment Fund' "
                 "(Form D industry group), forms D and D/A, month-split",
        "window": f"{months[0][0]}-{months[0][1]:02d}-01..{end.isoformat()}",
        "formd_new_notices": tot["D"], "formd_amendments": tot["D/A"],
        "capped_months": capped, "as_of": end.isoformat(),
    }
    ck.write_text(json.dumps(out))
    return out


def main() -> None:
    print("enumerating (checkpointed, safe to interrupt/resume)…")
    intervals = efts_form_filers("n23c3a", "N-23C3A")
    bdc_elect = efts_form_filers("n54a", "N-54A")
    tenders = efts_form_filers("sctoi", "SC TO-I")
    n2family = efts_form_filers("n2fam", "N-2,486BPOS,486APOS")
    reit10k = companies_by_query("sic6798_10k", SIC="6798", type="10-K")
    listed = company_tickers()

    def exchange_listed(cik: str) -> tuple[bool, list[str]]:
        """True only for a real exchange listing. The tickers oracle alone
        is NOT enough: non-traded vehicles can carry OTC quotations (e.g.
        Blackstone REIT trades OTC as BSTT while remaining non-traded), so
        oracle hits are confirmed against submissions `exchanges`."""
        if int(cik) not in listed:
            return False, []
        try:
            ex = sorted({e for e in (submissions(cik).get("exchanges") or [])
                         if e and e.upper() != "OTC"})
        except Exception:  # noqa: BLE001 - unreachable: unknown, never guess
            print(f"  !! submissions unreachable for CIK {cik}: listing "
                  "unknown", flush=True)
            return None, []
        return bool(ex), ex

    universe: dict[str, dict] = {}

    def add(cik: str, name: str, klass: str, evidence: list[str],
            extra: dict | None = None):
        if cik in universe:
            universe[cik]["all_signals"].append(klass)
            return
        exch, ex_names = exchange_listed(cik)
        universe[cik] = {"cik": int(cik), "name": name,
                         "wrapper_class": klass,
                         "detection_evidence": evidence,
                         "all_signals": [klass],
                         "listed": bool(exch),
                         "exchanges": ex_names,
                         "tickers": listed.get(int(cik), []),
                         **(extra or {})}

    for cik, f in bdc_elect.items():
        add(cik, f["name"], "bdc",
            [f"Form N-54A (BDC election) filed {f['first']}"
             + (f" (+{f['count']-1} more)" if f["count"] > 1 else "")])
    for cik, f in intervals.items():
        add(cik, f["name"], "interval_23c3",
            [n23c3a_evidence(f["count"], f["first"], f["last"])],
            {"n23c3a": {"count": f["count"], "first": f["first"],
                        "last": f["last"]}})
    for cik, f in tenders.items():
        if cik in n2family:
            add(cik, f["name"], "tender_cef",
                [f"{f['count']} SC TO-I filings, {f['first']} to {f['last']}",
                 "N-2-family registration in history (excludes "
                 "operating-company self-tenders)"],
                {"sctoi": {"count": f["count"], "first": f["first"],
                           "last": f["last"]}})
    print(f"  classifying {len(reit10k)} SIC-6798 10-K filers (exchange "
          "check + names via submissions JSON, cached)…", flush=True)
    done_n = 0
    for cik, name in reit10k.items():
        exch, ex_names = exchange_listed(cik)
        if exch is False:  # unknown (submissions unreachable) → skip, not guess
            if not name:  # SIC-axis atom feeds carry no usable names
                name = (submissions(cik).get("name") or "").strip()
            add(cik, name, "nontraded_reit",
                ["10-K filer with SIC 6798 (browse-edgar company search)",
                 "no exchange listing in SEC submissions (OTC quotation "
                 "alone is not exchange listing)"])
        done_n += 1
        if done_n % 200 == 0:
            print(f"    …{done_n}/{len(reit10k)}", flush=True)
    for cik, f in n2family.items():
        exch, ex_names = exchange_listed(cik)
        if exch:
            add(cik, f["name"], "listed_cef",
                [f"N-2-family registrant ({f['count']} registration filings, "
                 f"{f['first']} to {f['last']})",
                 f"exchange listing in SEC submissions: {ex_names}"])
    for cik, f in n2family.items():
        if cik not in universe:  # neither listed nor tender nor interval
            add(cik, f["name"], "unlisted_cef_other",
                [f"N-2-family registrant ({f['count']} registration filings, "
                 f"{f['first']} to {f['last']})",
                 UNLISTED_CEF_EVIDENCE])

    # roster reconciliation: an R1-verified roster product whose wrapper has
    # no distinguishing form signature (e.g. a non-traded '34-Act reporting
    # conglomerate files 10-K like any operating company) is added with its
    # actual filing facts as evidence and the coverage limitation stated —
    # never silently, never universe-wide (we cannot enumerate that class).
    for pj in sorted((BASE / "data" / "products").glob("*.json")):
        pd = json.loads(pj.read_text())
        cik = str(int(pd["cik"]))
        if cik in universe:
            continue
        sub = submissions(cik)
        forms = sub.get("filings", {}).get("recent", {}).get("form", [])
        add(cik, sub.get("name", pd.get("fund_name", "")),
            "nontraded_34act_other",
            [f"registry wrapper: {pd.get('wrapper', 'unknown')} "
             f"(R1-verified roster entry {pd['product_key']})",
             f"SEC submissions: {len(forms)} recent filings incl. "
             f"{', '.join(sorted(set(forms))[:5])}",
             "added via roster reconciliation - this wrapper class has no "
             "distinguishing form signature, so the census cannot enumerate "
             "it universe-wide (limitation recorded in method_notes)"])
        print(f"  roster reconciliation: added {pd['product_key']} "
              f"(CIK {cik}) as nontraded_34act_other", flush=True)

    # fold tender/interval activity onto records classified earlier (e.g. a
    # BDC that also runs quarterly tenders keeps that evidence)
    for cik, f in tenders.items():
        if cik in universe and "sctoi" not in universe[cik]:
            universe[cik]["sctoi"] = {"count": f["count"], "first": f["first"],
                                      "last": f["last"]}
    for cik, f in intervals.items():
        if cik in universe and "n23c3a" not in universe[cik]:
            universe[cik]["n23c3a"] = {"count": f["count"],
                                       "first": f["first"], "last": f["last"]}

    counts: dict[str, int] = {}
    for rec in universe.values():
        counts[rec["wrapper_class"]] = counts.get(rec["wrapper_class"], 0) + 1

    doc = {
        "what": UNIVERSE_WHAT,
        "method_notes": METHOD_NOTES,
        "as_of": date.today().isoformat(),
        "dark_universe": formd_dark_universe(),
        "counts_by_class": dict(sorted(counts.items())),
        "total": len(universe),
        "entities": {c: universe[c] for c in sorted(universe, key=int)},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "universe.json").write_text(json.dumps(doc, indent=1))

    print("\n=== UNIVERSE COUNT TABLE (real counts, no padding) ===")
    for k, v in sorted(counts.items()):
        print(f"  {k:<16} {v:>5}")
    print(f"  {'TOTAL':<16} {len(universe):>5}")
    print(f"raw sizes: N-23C3A filers {len(intervals)}, N-54A {len(bdc_elect)}, "
          f"SC TO-I {len(tenders)}, N-2 family {len(n2family)}, "
          f"SIC6798+10-K {len(reit10k)}")


if __name__ == "__main__":
    main()

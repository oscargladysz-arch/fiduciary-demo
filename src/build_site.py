"""
Tark static-site data bundle builder
====================================
Reads the canonical data layer (the SAME files the validator gates) and emits
site/data.js — a single window.TARK bundle — plus copies the decision-memo
docx artifacts into site/memos/. The site's HTML/JS never hard-codes a fact:
everything on screen comes from this generated bundle, so the data layer stays
the single source of truth.

Anonymization is machine-enforced here too: identity_private blocks are
stripped from every plan, and the build FAILS if any sponsor name from any
data/plans/*.json appears anywhere in the emitted bundle.

Run:  python src/build_site.py     -> site/data.js, site/memos/*.docx
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

from tark_benchmark import MIN_PRIMARY_SCORE, PRODUCT_PROFILES
from tark_data import (BASE, DATA, CELLS, FACTORS, load_evidence, load_plan,
                       load_products, load_series, load_series_manifest,
                       plan_keys, status_kind)
from tark_liquidity import LIQUIDITY_PROFILES, SCENARIO

SITE = BASE / "site"

RULE_CAPTION = ("Six-factor framework per DOL proposed rule, Fiduciary Duties in "
                "Selecting Designated Investment Alternatives — 91 FR 16088 "
                "(Mar 31, 2026), RIN 1210-AC38. Safe harbor attaches to a "
                "documented, objective, thorough, analytical process.")

# integrity stat, sourced from the independent cross-check pass; see the
# report for the cell-by-cell record (v9 adjudicated the 2 discrepancies)
CROSSCHECK = {"cells_checked": 44, "confirmed": 42, "corrected": 2,
              "unlocatable": 0,
              "source": "docs/crosscheck_report.md (independent re-location "
                        "pass, 2026-08-08; both discrepancies corrected in v9)"}


def evidence_counts(key: str) -> dict:
    c = {"extracted": 0, "verified": 0, "computed": 0, "partial": 0,
         "fetched": 0, "pending": 0, "na": 0}
    for row in load_evidence(key):
        k = status_kind(row["status"])
        if k == "n/a":
            c["na"] += 1
        elif k in c:
            c[k] += 1
        else:
            c["pending"] += 1
    seeded = c["extracted"] + c["verified"] + c["computed"]
    soft = c["partial"] + c["fetched"]
    applicable = seeded + soft + c["pending"]
    c["coverage_pct"] = round((seeded + soft) / applicable * 100) if applicable else 0
    return c


def daily_series(ticker: str, column: str = "adj_close") -> list:
    return [[d, round(v, 6)] for d, v in load_series(ticker, column)]


_MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}


def _with_period_ends(nav: dict) -> dict:
    """Derive an ISO period_end for each quarterly row from its printed
    period string, e.g. '... - December 31, 2025)'."""
    for row in nav["rows"]:
        m = re.search(r"-\s*(\w+) (\d+), (\d{4})\)", row["period"])
        if m:
            row["period_end"] = (f"{m.group(3)}-{_MONTHS[m.group(1)]:02d}-"
                                 f"{int(m.group(2)):02d}")
    return nav


def main() -> None:
    plans_raw = {k: load_plan(k) for k in plan_keys()}
    # distinctive sponsor tokens = every word of the private identity that is
    # not generic corporate/plan boilerplate (those words legitimately appear
    # in anonymized display labels, e.g. 'tire & rubber manufacturer')
    STOP = {"the", "inc", "inc.", "llc", "llp", "co", "co.", "company",
            "corporation", "corp", "corp.", "usa", "us", "group", "and", "of",
            "for", "plan", "trust", "savings", "profit", "sharing",
            "retirement", "employee", "employees", "bargaining", "unit",
            "restaurants", "tire", "rubber", "&", "(psrp)", "401(k)"}
    sponsor_names: set[str] = set()
    for p in plans_raw.values():
        ident = p.get("identity_private", {})
        for field in ("sponsor", "plan_name"):
            for w in str(ident.get(field, "")).split():
                w = w.strip(",.()").lower()
                if w and len(w) > 3 and w not in STOP and not w.startswith("401("):
                    sponsor_names.add(w)

    plans_pub = {}
    for k, p in plans_raw.items():
        pub = {kk: vv for kk, vv in p.items() if kk != "identity_private"}
        plans_pub[k] = pub

    benchmarks = {}
    for f in sorted((DATA / "benchmarks").glob("*_selection.json")):
        benchmarks[f.stem.replace("_selection", "")] = json.loads(f.read_text())

    liquidity = {}
    for f in sorted((DATA / "liquidity").glob("*__*_match.json")):
        liquidity[f.stem.replace("_match", "")] = json.loads(f.read_text())

    bundle = {
        "generated": date.today().isoformat(),
        "rule_caption": RULE_CAPTION,
        "factors": FACTORS,
        "cell_registry": CELLS,
        "products": load_products(),
        "evidence_counts": {k: evidence_counts(k) for k in load_products()},
        "plans": plans_pub,
        "plan_order": ["plan_tech_media"] + [k for k in sorted(plans_pub)
                                             if k != "plan_tech_media"],
        "benchmarks": benchmarks,
        "min_primary_score": MIN_PRIMARY_SCORE,
        "liquidity": liquidity,
        "liquidity_profiles": LIQUIDITY_PROFILES,
        "scenario_defaults": SCENARIO,
        "metrics": json.loads((DATA / "analytics" / "metrics.json").read_text()),
        "dxyz_nav": _with_period_ends(json.loads(
            (DATA / "analytics" / "dxyz_nav_quarterly.json").read_text())),
        "series_manifest": load_series_manifest(),
        "series": {
            "dxyz_daily": [[d, round(v, 4)] for d, v in load_series("dxyz", "close")],
            "cclfx": daily_series("cclfx"),
            "bkln": daily_series("bkln"),
            "psp": daily_series("psp"),
            "urth": daily_series("urth"),
        },
        "pme_profiles": {
            "cliffwater_cclfx": {"fund_series": "cclfx", "index_series": "bkln",
                                 "index_label": "BKLN (senior-loan proxy)",
                                 "granularity": "monthly"},
            "hl_paf": {"fy_returns": PRODUCT_PROFILES["hl_paf"]["fy_returns"],
                       "fy_window": list(PRODUCT_PROFILES["hl_paf"]["fy_window"]),
                       "index_series": "psp",
                       "index_label": "PSP (listed-PE proxy)",
                       "index_series_alt": "urth",
                       "index_label_alt": "URTH (MSCI World proxy)",
                       "granularity": "annual"},
        },
        "crosscheck": CROSSCHECK,
        "memos": sorted(p.stem.replace("_decision_memo", "")
                        for p in (DATA / "memos").glob("*_decision_memo.docx")),
    }

    payload = json.dumps(bundle, separators=(",", ":"))
    low = payload.lower()
    leaks = sorted(n for n in sponsor_names if n in low)
    if leaks:
        raise SystemExit(f"ANONYMIZATION FAILURE: sponsor token(s) {leaks} "
                         f"would enter site/data.js — build refused.")

    SITE.mkdir(exist_ok=True)
    (SITE / "data.js").write_text("window.TARK = " + payload + ";\n")

    memo_dir = SITE / "memos"
    memo_dir.mkdir(exist_ok=True)
    for m in (DATA / "memos").glob("*_decision_memo.docx"):
        shutil.copy2(m, memo_dir / m.name)

    print(f"site/data.js written ({len(payload):,} bytes), "
          f"{len(bundle['memos'])} memos copied, sponsor tokens screened: "
          f"{len(sponsor_names)}")


if __name__ == "__main__":
    main()

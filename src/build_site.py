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

# glossary: plain-language primary, term-of-art secondary. Rendered as chips
# with hover definitions wherever these terms appear in headline lines.
GLOSSARY = {
    "PME": "Did the fund beat simply buying an index with the same cash, at the same times? Above 1.0 = yes. (Kaplan-Schoar Public Market Equivalent)",
    "KS-PME": "Did the fund beat simply buying an index with the same cash, at the same times? Above 1.0 = yes. (Kaplan-Schoar Public Market Equivalent)",
    "Direct Alpha": "The fund's yearly edge over the index, as a percentage. Zero = index-like. (Gredil/Griffiths/Stucke annualized excess IRR)",
    "AFFE": "Fees of the funds this fund invests in, passed through to you on top of its own fees. (Acquired Fund Fees & Expenses)",
    "TER": "Everything the fund charges in a year as a percent of assets. (Total Expense Ratio)",
    "Rule 23c-3": "The SEC rule forcing an interval fund to offer buybacks on a fixed schedule - liquidity by law, not by choice.",
    "interval fund": "A fund legally committed to periodic buyback windows (SEC Rule 23c-3).",
    "tender offer": "The fund's board CHOOSES each buyback window - nothing legally requires the next one.",
    "DIA": "An investment option on a 401(k) menu that participants pick themselves. (Designated Investment Alternative)",
    "404(c)": "The ERISA section that shields plan sponsors when participants direct their own accounts - assumes daily menus.",
    "de-smoothing": "Un-flattering correction: appraisal prices understate risk; this statistically restores the hidden volatility. (Geltner AR(1) unsmoothing)",
    "high-water mark": "The manager earns performance fees only above the previous peak - no double-charging for recovered losses.",
    "hurdle": "Minimum return the fund must clear before performance fees start.",
    "catch-up": "After the hurdle, the manager temporarily takes ALL profit until they hold their full share.",
    "NAV": "What one share is worth by the fund's own books. (Net Asset Value)",
    "Transactional NAV": "The NAV at which the fund actually sells and buys back shares (can differ from GAAP NAV).",
    "premium/discount": "The gap between what the market pays and what the fund says a share is worth.",
    "K-1": "The partnership tax form - arrives late, complicates filing; retirement recordkeepers hate it. (Schedule K-1)",
    "1099": "The ordinary dividend tax form retirement plans handle automatically. (Form 1099-DIV/-B)",
    "RIC": "A fund taxed like a mutual fund: no fund-level tax, 1099s to investors. (Regulated Investment Company)",
    "REIT": "A tax structure for property funds: must pay out 90% of income; investors get 1099s. (Real Estate Investment Trust)",
    "QDIA": "The menu option your money lands in when you never choose. (Qualified Default Investment Alternative)",
    "DRIP": "Distributions automatically buy more shares unless you opt out. (Distribution Reinvestment Plan)",
    "proration": "When buyback requests exceed the cap, everyone gets only a slice - the rest waits for the next window.",
    "gating": "The fund limiting or suspending buybacks - the semi-liquid wrapper's stress behavior.",
    "Managed Assets": "A fee base that INCLUDES borrowed money - the fund earns fees on leverage.",
    "gross assets": "A fee base that INCLUDES assets bought with borrowings - fees on leverage.",
    "ASC 820": "The accounting rulebook for fair value: Level 1 = market prices, Level 3 = the fund's own models.",
    "Level 3": "Assets valued by the fund's own models and judgment - no market price exists. (ASC 820 fair-value hierarchy)",
    "NAV practical expedient": "Holdings valued at whatever the underlying fund reports - trusted, not re-derived.",
    "ITD": "Since the fund's first day. (Inception-to-date)",
    "ROC": "Distributions that are your own money coming back, not earnings. (Return of Capital)",
    "smoothing": "Appraisal-based prices react late and move little - reported volatility understates real risk.",
    "expense limitation": "The adviser's promise to absorb costs above a cap - often reclaimable for 3 years.",
    "PCAOB": "The audit regulator; registration means the auditor is inspected. (Public Company Accounting Oversight Board)",
    "N-23C3A": "The SEC form an interval fund files for EVERY buyback window - a public paper trail of kept promises.",
}

_FIG = re.compile(
    r"(\$[\d,]+(?:\.\d+)?(?:\s?(?:billion|million|B|M))?"      # money
    r"|\(?-?\d+(?:\.\d+)?\)?%(?:/yr)?"                          # percents
    r"|\b\d+\.\d{2,4}x?\b"                                      # ratios/PME
    r"|\b\d+(?:\.\d+)?x\b)")                                    # multiples


def cell_display(cell: dict) -> dict:
    """Numbers-first display derivation (display-only; full sourced text stays
    one disclosure away). Headline = first strong figure in the value with a
    few words of context; plain = first sentence, trimmed."""
    st = str(cell.get("status", "pending"))
    val = str(cell.get("value") or "")
    kind = status_kind(st)
    if kind == "n/a":
        reason = st.split(":", 1)[1].strip() if ":" in st else st[6:].strip(" -")
        return {"headline": "n/a", "plain": reason[:170]}
    if not val:
        return {"headline": "—", "plain": "Pending extraction."}
    first_sentence = re.split(r"(?<=[.;])\s+", val, maxsplit=1)[0][:180]
    m = _FIG.search(val)
    if m:
        s, e = m.span()
        pre = val[max(0, s - 34):s]
        pre = pre[pre.rfind(" ") + 1:] if " " in pre else pre
        post = val[e:e + 30]
        post = post[:post.find(" ", 18)] if post.find(" ", 18) > 0 else post
        headline = (pre + m.group(0) + post).strip(" ,;:-")
        headline = headline[:60]
    else:
        headline = {"partial": "partial", "computed": "computed",
                    "fetched": "series on disk"}.get(kind, "…")
    return {"headline": headline, "plain": first_sentence}


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

    products = load_products()
    display = {k: {cid: cell_display(c) for cid, c in p["cells"].items()}
               for k, p in products.items()}
    rollups = {}
    for k, p in products.items():
        by = {}
        for n, label in FACTORS.items():
            cells = [c for cid, c in p["cells"].items()
                     if cid.split(".")[0] == n]
            kinds = [status_kind(str(c.get("status", "pending"))) for c in cells]
            by[n] = {"label": label, "total": len(cells),
                     "evidenced": sum(kind in ("extracted", "verified",
                                               "partial", "fetched")
                                      for kind in kinds),
                     "computed": kinds.count("computed"),
                     "na": kinds.count("n/a")}
        rollups[k] = by

    ann_dir = DATA / "series_annual"
    series_annual = {}
    if ann_dir.exists():
        import csv as _csv
        for f in sorted(ann_dir.glob("*.csv")):
            with open(f, newline="") as fh:
                series_annual[f.stem] = list(_csv.DictReader(fh))
    monthly = {}
    mpath = DATA / "series_monthly" / "breit_nav.csv"
    if mpath.exists():
        import csv as _csv
        with open(mpath, newline="") as fh:
            monthly["breit_nav"] = [[r["date"], float(r["nav_per_share"])]
                                    for r in _csv.DictReader(fh)]
        monthly["breit_nav_manifest"] = json.loads(
            (DATA / "series_monthly" / "manifest.json").read_text())

    bundle = {
        "generated": date.today().isoformat(),
        "rule_caption": RULE_CAPTION,
        "factors": FACTORS,
        "cell_registry": CELLS,
        "products": products,
        "cell_display": display,
        "factor_rollups": rollups,
        "glossary": GLOSSARY,
        "taxonomy": json.loads((DATA / "analytics" / "taxonomy.json").read_text()),
        "supplement": json.loads((DATA / "analytics" / "supplement.json").read_text()),
        "series_annual": series_annual,
        "series_monthly": monthly,
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

"""
Tark data layer (M0)
====================
Single source of truth for the six-factor cell registry and all data access.
Every later module (M2 analytics, M3 benchmark engine, M4 UI, M5 memo
generator) imports from here and ONLY from here — no module re-declares
cell IDs, statuses, or file paths.

Data contract on disk:
    data/products/<key>.json           one file per product, all 54 cells present
    data/evidence/<key>_evidence.csv   same cells, same statuses (citations)
    data/plans/<key>.json              reference plans (real 5500 economics,
                                       anonymized display labels)
    data/series/<ticker>.csv           date,close daily series + series_manifest.json
    data/manifest.csv                  every EDGAR pull, reproducible

Usage:
    from tark_data import load_products, load_anchor_plan, cells_by_factor
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"

# ---------------------------------------------------------------- registry
FACTORS = {
    "1": "Performance",
    "2": "Fees",
    "3": "Liquidity",
    "4": "Valuation",
    "5": "Performance Benchmarks",
    "6": "Complexity",
}

CELLS = {
    "1.1": "Net total return series", "1.2": "Trailing & calendar-year returns",
    "1.3": "Gross vs net spread", "1.4": "Distribution history & composition",
    "1.5": "Underlying sleeve/GP performance", "1.6": "Volatility & max drawdown",
    "1.7": "De-smoothed volatility", "1.8": "Risk-adjusted metrics (PME etc)",
    "1.9": "Stress-window performance", "1.10": "Market price & premium/discount",
    "1.11": "Track record & manager tenure",
    "2.1": "Management fee (rate AND base)", "2.2": "Incentive fee terms",
    "2.3": "Total expense ratio & waivers", "2.4": "AFFE",
    "2.5": "Underlying GP economics", "2.6": "Loads & servicing fees",
    "2.7": "Early repurchase fee", "2.8": "CIT fee schedule",
    "2.9": "Fee peer percentile", "2.10": "Value justification",
    "3.1": "Wrapper liquidity terms", "3.2": "Repurchase mechanics",
    "3.3": "Repurchase history", "3.4": "Portfolio liquidity profile",
    "3.5": "TDF/CIT liquidity sleeve", "3.6": "Fund leverage & facilities",
    "3.7": "Plan participant liquidity demand", "3.8": "Redemption stress test",
    "3.9": "Product-to-plan liquidity match",
    "4.1": "Valuation policy & NAV frequency", "4.2": "Fair-value hierarchy (L1/2/3)",
    "4.3": "Independent valuation agent", "4.4": "Methodology by asset type",
    "4.5": "Auditor & opinion", "4.6": "NAV restatement history",
    "4.7": "Premium/discount check", "4.8": "Smoothing diagnostics",
    "4.9": "CIT unit valuation",
    "5.1": "Self-declared benchmark", "5.2": "Public index series",
    "5.3": "Alt asset-class indices", "5.4": "Peer universe & returns",
    "5.5": "PME / Direct Alpha inputs", "5.6": "Benchmark suitability memo",
    "5.7": "Case-law tracker",
    "6.1": "Structure map", "6.2": "Strategy & instrument complexity",
    "6.3": "Conflicts & affiliated transactions", "6.4": "Tax reporting (1099 vs K-1)",
    "6.5": "Service-provider web", "6.6": "Plan operational fit",
    "6.7": "Participant communicability", "6.8": "Fiduciary capacity self-assessment",
}

# status vocabulary is prefix-based: the wild data legitimately contains
# refinements like "pending-verify" and "fetched-series, extraction pending"
STATUS_PREFIXES = ("pending", "partial", "extracted", "verified", "computed", "fetched", "n/a")

SERIES_COLUMNS = ["date", "close", "adj_close"]

EVIDENCE_COLUMNS = [
    "cell_id", "element", "value", "source_doc", "source_section", "quote",
    "local_file", "date_pulled", "extracted_by", "verified_by", "status",
]


def factor_of(cell_id: str) -> str:
    """'3.4' -> 'Liquidity'"""
    return FACTORS[cell_id.split(".")[0]]


def status_kind(status: str) -> str:
    """Collapse a wild status string to its prefix kind, e.g. 'extracted'."""
    for p in STATUS_PREFIXES:
        if status.startswith(p):
            return p
    return "unknown"


# ---------------------------------------------------------------- loaders
def product_keys() -> list[str]:
    return sorted(p.stem for p in (DATA / "products").glob("*.json"))


def load_product(key: str) -> dict:
    return json.loads((DATA / "products" / f"{key}.json").read_text())


def load_products() -> dict[str, dict]:
    return {k: load_product(k) for k in product_keys()}


def get_cell(product: dict, cell_id: str) -> dict:
    return product["cells"][cell_id]


def cells_by_factor(product: dict) -> dict[str, list[tuple[str, dict]]]:
    """Factor label -> [(cell_id, cell), ...] in registry order."""
    out: dict[str, list[tuple[str, dict]]] = {v: [] for v in FACTORS.values()}
    for cid in CELLS:
        out[factor_of(cid)].append((cid, product["cells"][cid]))
    return out


ANCHOR_PLAN_KEY = "plan_tech_media"


def plan_keys() -> list[str]:
    return sorted(p.stem for p in (DATA / "plans").glob("*.json"))


def load_plan(key: str) -> dict:
    return json.loads((DATA / "plans" / f"{key}.json").read_text())


def load_plans() -> dict[str, dict]:
    return {k: load_plan(k) for k in plan_keys()}


def load_anchor_plan() -> dict:
    """Backward-compatible alias: the original anchor plan."""
    return load_plan(ANCHOR_PLAN_KEY)


def load_evidence(key: str) -> list[dict]:
    with open(DATA / "evidence" / f"{key}_evidence.csv", newline="") as fh:
        return list(csv.DictReader(fh))


def series_tickers() -> list[str]:
    return sorted(p.stem for p in (DATA / "series").glob("*.csv"))


def load_series(ticker: str, column: str = "adj_close") -> list[tuple[str, float]]:
    """[(iso_date, value), ...] ascending. column: 'adj_close' (total-return
    proxy, default) or 'close' (raw price/NAV)."""
    with open(DATA / "series" / f"{ticker}.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [(r["date"], float(r[column])) for r in rows]


def load_series_manifest() -> dict:
    return json.loads((DATA / "series" / "series_manifest.json").read_text())


def load_manifest() -> list[dict]:
    with open(DATA / "manifest.csv", newline="") as fh:
        return list(csv.DictReader(fh))


# ------------------------------------------------------------- validation
def validate_product(key: str) -> list[str]:
    """Return a list of error strings (empty = clean)."""
    errs: list[str] = []
    try:
        p = load_product(key)
    except Exception as e:  # noqa: BLE001 - report, don't crash the sweep
        return [f"{key}: cannot load JSON ({e})"]

    for req in ("product_key", "fund_name", "cik", "wrapper", "cells"):
        if req not in p:
            errs.append(f"{key}: missing top-level key '{req}'")
    if p.get("product_key") != key:
        errs.append(f"{key}: product_key mismatch ('{p.get('product_key')}')")

    cells = p.get("cells", {})
    missing = sorted(set(CELLS) - set(cells))
    extra = sorted(set(cells) - set(CELLS))
    if missing:
        errs.append(f"{key}: missing cells {missing}")
    if extra:
        errs.append(f"{key}: unknown cells {extra}")

    for cid, cell in cells.items():
        if cid not in CELLS:
            continue
        if cell.get("element") != CELLS[cid]:
            errs.append(f"{key}:{cid}: element label drift ('{cell.get('element')}')")
        st = cell.get("status", "")
        if status_kind(st) == "unknown":
            errs.append(f"{key}:{cid}: unknown status '{st}'")
        if status_kind(st) in ("extracted", "verified", "computed") and not cell.get("value"):
            errs.append(f"{key}:{cid}: status '{st}' but no value")
        if status_kind(st) in ("extracted", "verified", "computed") and not cell.get("source"):
            errs.append(f"{key}:{cid}: status '{st}' but no source")
        if status_kind(st) in ("extracted", "verified", "computed") and not str(cell.get("extracted_by", "")).strip():
            errs.append(f"{key}:{cid}: status '{st}' but empty extracted_by "
                        f"(provenance is part of the record)")

    # evidence CSV cross-check
    try:
        ev = load_evidence(key)
    except Exception as e:  # noqa: BLE001
        errs.append(f"{key}: cannot load evidence CSV ({e})")
        return errs
    if ev and list(ev[0].keys()) != EVIDENCE_COLUMNS:
        errs.append(f"{key}: evidence CSV columns differ from contract")
    ev_ids = [r["cell_id"] for r in ev]
    if sorted(ev_ids) != sorted(CELLS):
        errs.append(f"{key}: evidence CSV cell set differs from registry "
                    f"({len(ev_ids)} rows)")
    for r in ev:
        cid = r["cell_id"]
        if cid in cells and r["status"] != cells[cid].get("status"):
            errs.append(f"{key}:{cid}: status drift JSON='{cells[cid].get('status')}' "
                        f"CSV='{r['status']}'")
    return errs


def validate_plan(key: str) -> list[str]:
    errs: list[str] = []
    try:
        a = load_plan(key)
    except Exception as e:  # noqa: BLE001
        return [f"{key}: cannot load ({e})"]
    for req in ("display_label", "identity_private", "participants",
                "financials", "derived", "source"):
        if req not in a:
            errs.append(f"{key}: missing '{req}'")
    fin, part, der = a.get("financials", {}), a.get("participants", {}), a.get("derived", {})
    net = fin.get("net_assets_eoy")
    bal = part.get("with_account_balances")
    if not (isinstance(net, (int, float)) and net > 0):
        errs.append(f"{key}: net_assets_eoy not a positive number")
    # integrity: recompute derived figures from primitives
    if net and bal:
        recomputed = round(net / bal)
        if abs(recomputed - (der.get("avg_balance_per_account") or 0)) > 1:
            errs.append(f"{key}: avg_balance drift (stored "
                        f"{der.get('avg_balance_per_account')}, recomputed {recomputed})")
    adm = fin.get("tot_admin_expenses")
    if net and adm:
        recomputed = round(adm / net * 100, 3)
        if abs(recomputed - (der.get("admin_expense_ratio_pct") or 0)) > 0.001:
            errs.append(f"{key}: admin_expense_ratio drift")
    return errs


def validate_series() -> list[str]:
    errs: list[str] = []
    try:
        man = load_series_manifest()
    except Exception as e:  # noqa: BLE001
        return [f"series: cannot load manifest ({e})"]
    declared = {m["ticker"].lower() for m in man.get("series", [])}
    on_disk = set(series_tickers())
    if declared != on_disk:
        errs.append(f"series: manifest/disk mismatch ({declared} vs {on_disk})")
    for t in on_disk:
        try:
            with open(DATA / "series" / f"{t}.csv", newline="") as fh:
                hdr = next(csv.reader(fh))
            if hdr != SERIES_COLUMNS:
                errs.append(f"series {t}: columns {hdr} != contract {SERIES_COLUMNS}")
                continue
            s_close = load_series(t, "close")
            s_adj = load_series(t, "adj_close")
        except Exception as e:  # noqa: BLE001
            errs.append(f"series {t}: cannot parse ({e})")
            continue
        if len(s_close) < 50:
            errs.append(f"series {t}: suspiciously short ({len(s_close)} rows)")
        dates = [d for d, _ in s_close]
        if dates != sorted(dates):
            errs.append(f"series {t}: dates not ascending")
        if any(c <= 0 for _, c in s_close) or any(a <= 0 for _, a in s_adj):
            errs.append(f"series {t}: non-positive values present")
    return errs


def validate_all() -> dict[str, list[str]]:
    report = {k: validate_product(k) for k in product_keys()}
    for pk in plan_keys():
        report[f"plan:{pk}"] = validate_plan(pk)
    report["series"] = validate_series()
    return report

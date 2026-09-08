"""
The JSON views a job writes for the workspace (R3-P4-4): the same record
files the public demo is built from, sliced per product and plan, each
with a schema name so the ApiAdapter and the StaticAdapter of R3-P1 read
one shape. Every figure is the record's own, nothing is computed here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _read(p: Path):
    return json.loads(p.read_text()) if p.exists() else None


def write_views(data: Path, key: str, plan_key: str, out: Path, report_path: Path | None = None) -> list[Path]:
    from tark_data import coverage_summary, load_product
    from tark_display import cell_display, facts_by_cell
    out.mkdir(parents=True, exist_ok=True)
    product = load_product(key)
    facts = _read(data / "facts" / f"{key}.json") or {}
    fbc = facts_by_cell(facts.get("facts", {}))
    reg = (_read(data / "registry.json") or {}).get("products", {}).get(key, {})
    # the record's own cell beside the copy layer's rendering of it
    cells = {cid: {**c, "display": cell_display(c, cid, fbc.get(cid))} for cid, c in product["cells"].items()}
    written = []

    def put(name: str, body: dict) -> None:
        p = out / f"{name}.json"
        p.write_text(json.dumps(body, indent=1, ensure_ascii=False, default=str))
        written.append(p)

    put("record", {"schema": "tark.record.v1", "product_key": key, "fund_name": product["fund_name"], "cik": product["cik"],
                   "wrapper": product.get("wrapper", ""), "coverage": coverage_summary(key), "cells": cells,
                   "registry": {k: reg.get(k) for k in ("cohort", "strategy", "asset_class", "wrapper_type", "pricing_class",
                                                        "as_of", "depth", "default_entry")},
                   "human_verification": "pending"})
    sel = _read(data / "benchmarks" / f"{key}_selection.json")
    put("selection", {"schema": "tark.selection.v1", "product_key": key, "selection": sel})
    match = _read(data / "liquidity" / f"{plan_key}__{key}_match.json")
    put("liquidity", {"schema": "tark.liquidity.v1", "product_key": key, "plan_key": plan_key, "match": match})
    cid = reg.get("cohort", "")
    cohort = _read(data / "cohorts" / f"{cid}.json") if cid else None
    put("cohort", {"schema": "tark.cohort.v1", "product_key": key, "cohort_id": cid, "cohort": cohort})
    put("facts", {"schema": "tark.facts.v1", "product_key": key, "facts": facts})
    report = _read(report_path) if report_path else None
    put("report", {"schema": "tark.ingest_report.v1", "product_key": key, "report": report})
    return written

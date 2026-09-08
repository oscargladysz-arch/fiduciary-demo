"""
The view shapes, in one place (R3-P1 data access, R3-P4-4).

One product's record can be read three ways: as a JSON chunk the static
demo fetches, as a file the worker writes into a job's storage prefix, and
as an answer the workspace API returns. Every one of them is built here, so
the rebuilt frontend's adapter reads one shape whichever server it has and
a change of shape cannot land on one path and miss the other two.

Every figure is the record's own. Nothing is computed here: the functions
read the record's files and the copy layer, and arrange them.

    from tark_views import record_view, index_view, VIEW_NAMES
    record_view("hl_paf")                      -> {"schema": "tark.record.v1", ...}
    liquidity_view("plan_tech_media", "hl_paf")

The schema name on every view is the contract. When a shape changes, its
version changes with it, and the gates that read it change in the same
commit.
"""
from __future__ import annotations

import json
from pathlib import Path

from tark_data import (CELLS, DATA, FACTORS, RULE, RULE_CITATION, coverage_summary,
                       coverage_totals, load_plan, load_product, load_products, plan_keys,
                       product_keys)
from tark_display import (BASE_LABEL, WRAPPER_LABEL, cell_display, facts_by_cell,
                          plan_demand_sentence)

# the per-product views, in the order a reader meets them
VIEW_NAMES = ("record", "selection", "liquidity", "cohort", "facts", "documents")
SCHEMA = {
    "index": "tark.index.v1",
    "screener": "tark.screener.v1",
    "record": "tark.record.v1",
    "selection": "tark.selection.v1",
    "liquidity": "tark.liquidity.v1",
    "cohort": "tark.cohort.v1",
    "facts": "tark.facts.v1",
    "documents": "tark.documents.v1",
    "report": "tark.ingest_report.v1",
    "manifest": "tark.chunks.v1",
}
PENDING = "pending"          # what every surface says about human verification


def _read(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def _registry() -> dict:
    return json.loads((DATA / "registry.json").read_text())


def registry_entry(key: str) -> dict:
    return _registry()["products"].get(key, {})


def _facts_doc(key: str) -> dict:
    return _read(DATA / "facts" / f"{key}.json") or {}


# ------------------------------------------------------------------ record
def record_view(key: str) -> dict:
    """The 55 cells with the copy layer's rendering beside each one, the
    coverage arithmetic, and the registry fields a reader is shown."""
    product = load_product(key)
    fbc = facts_by_cell(_facts_doc(key).get("facts", {}))
    reg = registry_entry(key)
    cells = {cid: {**c, "display": cell_display(c, cid, fbc.get(cid))}
             for cid, c in product["cells"].items()}
    return {
        "schema": SCHEMA["record"],
        "product_key": key,
        "fund_name": product["fund_name"],
        "cik": product["cik"],
        "wrapper": product.get("wrapper", ""),
        "wrapper_label": WRAPPER_LABEL.get(reg.get("wrapper_type", ""), product.get("wrapper", "")),
        "coverage": coverage_summary(key),
        "cells": cells,
        "registry": {k: reg.get(k) for k in ("cohort", "strategy", "asset_class", "sub_strategy",
                                             "wrapper_type", "pricing_class", "nav_cadence", "as_of",
                                             "depth", "default_entry")},
        "human_verification": PENDING,
    }


def selection_view(key: str) -> dict:
    return {"schema": SCHEMA["selection"], "product_key": key,
            "selection": _read(DATA / "benchmarks" / f"{key}_selection.json")}


def liquidity_view(plan_key: str, key: str) -> dict:
    return {"schema": SCHEMA["liquidity"], "product_key": key, "plan_key": plan_key,
            "match": _read(DATA / "liquidity" / f"{plan_key}__{key}_match.json")}


def cohort_view(key: str) -> dict:
    cid = registry_entry(key).get("cohort", "")
    return {"schema": SCHEMA["cohort"], "product_key": key, "cohort_id": cid,
            "cohort": _read(DATA / "cohorts" / f"{cid}.json") if cid else None}


def facts_view(key: str) -> dict:
    return {"schema": SCHEMA["facts"], "product_key": key, "facts": _facts_doc(key)}


def documents_view(plan_key: str, key: str, record_name: str = "", attachment: str = "") -> dict:
    """What a reader may download for this plan and product. The names are
    the writer's own, so the caller passes them rather than guessing."""
    return {"schema": SCHEMA["documents"], "product_key": key, "plan_key": plan_key,
            "record": record_name, "attachment": attachment or None,
            "human_verification": PENDING}


def report_view(key: str, report: dict | None) -> dict:
    return {"schema": SCHEMA["report"], "product_key": key, "report": report}


def product_view(name: str, key: str, plan_key: str = "", **kw) -> dict:
    """One product view by name, so a route or a writer can loop the names."""
    if name == "record":
        return record_view(key)
    if name == "selection":
        return selection_view(key)
    if name == "cohort":
        return cohort_view(key)
    if name == "facts":
        return facts_view(key)
    if name == "liquidity":
        if not plan_key:
            raise KeyError("the liquidity view is per plan and needs a plan key")
        return liquidity_view(plan_key, key)
    if name == "documents":
        if not plan_key:
            raise KeyError("the documents view is per plan and needs a plan key")
        return documents_view(plan_key, key, **kw)
    raise KeyError(f"no view named {name!r}")


# ------------------------------------------------------------------- index
def index_view() -> dict:
    """What every route needs before it knows which product it is showing:
    the roster, the plans, the labels, and the counts that must be on the
    first paint (rule 20)."""
    reg = _registry()
    products = []
    for key in sorted(product_keys()):
        p = load_product(key)
        r = reg["products"].get(key, {})
        cov = coverage_summary(key)
        products.append({
            "key": key, "fund_name": p["fund_name"], "cik": p["cik"],
            "wrapper_type": r.get("wrapper_type", ""),
            "wrapper_label": WRAPPER_LABEL.get(r.get("wrapper_type", ""), p.get("wrapper", "")),
            "cohort": r.get("cohort", ""), "strategy": r.get("strategy", ""),
            "depth": r.get("depth", ""), "as_of": r.get("as_of", ""),
            "coverage": {k: cov[k] for k in ("evidenced", "computed", "soft", "na", "verified",
                                             "resolved", "resolvable")},
            "cited": sorted(cid for cid, c in p["cells"].items() if c.get("source")),
        })
    plans = []
    for pk in plan_keys():
        pl = load_plan(pk)
        plans.append({"key": pk, "label": pl["display_label"], "plan_year": pl.get("plan_year", ""),
                      "demand_sentence": plan_demand_sentence(pl)})
    cohorts = {cid: {"label": c.get("label", ""), "members": list(c.get("members", []))}
               for cid, c in reg.get("cohorts", {}).items()}
    return {
        "schema": SCHEMA["index"],
        "products": products,
        "plans": plans,
        "cohorts": cohorts,
        "cells": {cid: {"label": label, "factor": cid.split(".")[0]} for cid, label in CELLS.items()},
        "factors": dict(FACTORS),
        "labels": {"wrapper": dict(WRAPPER_LABEL), "base": dict(BASE_LABEL)},
        "coverage_totals": coverage_totals(),
        "rule": {"citation": RULE_CITATION, "paragraphs": RULE.get("paragraphs", ""),
                 "title": RULE.get("title", "")},
        "human_verification": PENDING,
    }


def screener_view() -> dict:
    """The one view that paints every product at once. It carries the typed
    facts its columns show and, per product, the cells that have a source,
    so every citation button is on the first paint (rule 20) without the
    537 sourced strings the drawer opens one product at a time."""
    products = {}
    for key in sorted(load_products()):
        p = load_product(key)
        products[key] = {
            "fund_name": p["fund_name"],
            "facts": _facts_doc(key).get("facts", {}),
            "cited": sorted(cid for cid, c in p["cells"].items() if c.get("source")),
        }
    return {"schema": SCHEMA["screener"], "products": products, "human_verification": PENDING}

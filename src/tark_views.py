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
from tark_data import authority, load_evidence, rule_ref, status_kind
from tark_display import (BASE_LABEL, WRAPPER_LABEL, cell_display, display_copy,
                          display_path_free, facts_by_cell, plan_demand_sentence)

# the per-product views, in the order a reader meets them
VIEW_NAMES = ("record", "selection", "liquidity", "cohort", "facts", "series", "documents")
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
    "series": "tark.series.v1",
    "plans": "tark.plans.v1",
    "funnel": "tark.funnel.v1",
    "coverage": "tark.coverage.v1",
    "verification": "tark.verification.v1",
    "authority": "tark.authority.v1",
    "evidence": "tark.evidence.v1",
    "cohorts": "tark.cohorts.v1",
    "lab": "tark.lab.v1",
    "census": "tark.census.v1",
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
def citations(key: str) -> dict:
    """Per cell: the accession the ledger names and the filings it resolves
    to on EDGAR, so the citation drawer links rather than prints a number.
    Every link comes from the manifest through `data/citations/`, never from
    a string a view built (rule 15)."""
    doc = _read(DATA / "citations" / f"{key}.json") or {}
    acc_by_cell = {r["cell_id"]: r.get("accession", "") for r in load_evidence(key)}
    out: dict = {}
    for cid in set(acc_by_cell) | set(doc.get("cells", {})):
        acc = acc_by_cell.get(cid, "")
        links = []
        for ref in doc.get("cells", {}).get(cid, []):
            if ref["match"] in ("exact", "form_only"):
                links.append({"form": ref.get("form", ""), "filing_date": ref.get("filing_date", ""),
                              "accession": ref["accession"], "url": ref["url"]})
            elif ref["match"] in ("range", "set"):
                links.extend({"form": ref.get("form", ""), "filing_date": f["filing_date"],
                              "accession": f["accession"], "url": f["url"]} for f in ref["filings"])
        out[cid] = {
            # a set pointer is said in words, never as a bare ledger token
            "accession": (f"{acc.split(',')[0]} filings, each linked under EDGAR"
                          if acc.startswith("multiple (") else acc),
            "edgar": links,
        }
    return out


def factor_rollup(key: str) -> dict:
    """The six factors with the record's one coverage arithmetic (R3-P2-8),
    so a factor tile never recomputes it in the browser."""
    cells = load_product(key)["cells"]
    out = {}
    for n, label in FACTORS.items():
        kinds = [status_kind(str(c.get("status", "pending")))
                 for cid, c in cells.items() if cid.split(".")[0] == n]
        out[n] = {"label": label, "total": len(kinds),
                  "evidenced": sum(k in ("structured", "extracted", "verified") for k in kinds),
                  "computed": kinds.count("computed"),
                  "soft": sum(k in ("partial", "fetched") for k in kinds),
                  "na": kinds.count("n/a")}
    return out


def record_view(key: str) -> dict:
    """The 55 cells with the copy layer's rendering beside each one, the
    citation the drawer opens, the factor rollup, the coverage arithmetic,
    and the registry fields a reader is shown."""
    product = load_product(key)
    fbc = facts_by_cell(_facts_doc(key).get("facts", {}))
    reg = registry_entry(key)
    cite = citations(key)
    auth = authority()
    cells = {}
    for cid, c in product["cells"].items():
        # a repository path inside the record renders as a reader label
        cell = {**c,
                "source": display_path_free(c.get("source", "")),
                "section": display_copy(c.get("section", "")),
                "display": cell_display(c, cid, fbc.get(cid)),
                "rule": {k: v for k, v in rule_ref(cid, auth).items() if k != "basis"}}
        cell.update(cite.get(cid, {"accession": "", "edgar": []}))
        cells[cid] = cell
    return {
        "schema": SCHEMA["record"],
        "product_key": key,
        "fund_name": product["fund_name"],
        "cik": product["cik"],
        "wrapper": product.get("wrapper", ""),
        "wrapper_label": WRAPPER_LABEL.get(reg.get("wrapper_type", ""), product.get("wrapper", "")),
        "coverage": coverage_summary(key),
        "factors": factor_rollup(key),
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
    if name == "series":
        return series_view(key, **kw)
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


# ------------------------------------------------------- per product, series
def series_view(key: str, *, annual=None, monthly=None, quarterly=None,
                daily=None, sources=None, supplement=None) -> dict:
    """Everything one product's charts draw, in one chunk the record and the
    lab fetch on demand. The caller passes the series it holds, because the
    static demo and a workspace hold different ones, and the shape is the
    same either way."""
    return {"schema": SCHEMA["series"], "product_key": key,
            "annual": annual or [], "monthly": monthly or [],
            "quarterly": quarterly or [], "daily": daily or None,
            "sources": sources or {}, "supplement": supplement or {}}


# ----------------------------------------------------------- demo-global views
# These arrange what the demo build already computes. They take their inputs
# rather than reading them, so the one view builder keeps no dependency on
# the static-site builder and the workspace can serve the same shapes.
def plans_view(plans: dict, order: list) -> dict:
    """The four reference plans as a reader meets them. Identity never
    reaches this shape: the caller strips it (rule 5) and the anonymization
    screen runs over the written chunk."""
    return {"schema": SCHEMA["plans"], "plans": plans, "order": list(order),
            "human_verification": PENDING}


def funnel_view(census: dict, crosscheck: dict, verification: dict) -> dict:
    """The dark universe down to the signed record, one step per row, each
    number live from the layer under it."""
    totals = coverage_totals()
    counts = totals["counts"]
    steps = [
        {"id": "dark", "label": "Registered wrappers on file",
         "value": census.get("total"), "note": census.get("dark_universe", {}).get("sentence", "")},
        {"id": "evaluated", "label": "Products evaluated in full",
         "value": len(product_keys()), "note": "Every cell of the six-factor record is attempted."},
        {"id": "resolved", "label": "Cells resolved",
         "value": counts.get("resolved"), "note": "Structured, extracted, computed or answered not applicable."},
        {"id": "evidenced", "label": "Cells with a filing behind them",
         "value": counts.get("evidenced"), "note": "A document, a section and a quote on record."},
        {"id": "verified", "label": "Cells signed by a person",
         "value": counts.get("verified"), "note": "Human verification is offered to design partners."},
    ]
    return {"schema": SCHEMA["funnel"], "steps": steps,
            "counts_by_class": census.get("counts_by_class", {}),
            "method_notes": census.get("method_notes", []),
            "as_of": census.get("as_of", ""),
            "totals": totals, "crosscheck": crosscheck,
            "verified_by_product": verification.get("verified", {}),
            "human_verification": PENDING}


def coverage_view(crosscheck: dict) -> dict:
    """The record's totals and every product's counts, on the one arithmetic
    the record itself uses, with the resolvable rule stated rather than
    implied."""
    per = {}
    for key in sorted(product_keys()):
        per[key] = {"fund_name": load_product(key)["fund_name"],
                    "coverage": coverage_summary(key),
                    "factors": factor_rollup(key)}
    return {"schema": SCHEMA["coverage"], "totals": coverage_totals(),
            "products": per, "crosscheck": crosscheck,
            "human_verification": PENDING}


def verification_view(queue: dict) -> dict:
    """The queue in its written order, the tier titles verbatim, and the live
    signed count. Nothing here can set a cell: the gate admits a human
    signature and nothing else (rule 16)."""
    rows = []
    for item in queue.get("queue", []):
        key, cid = item["product"], item["cell"]
        cell = load_product(key)["cells"].get(cid, {})
        rows.append({"product_key": key, "fund_name": load_product(key)["fund_name"],
                     "cell": cid, "tier": item.get("tier"),
                     "element": cell.get("element", ""), "status": cell.get("status", ""),
                     "source": display_path_free(cell.get("source", "")),
                     "section": display_copy(cell.get("section", "")),
                     "verified_by": cell.get("verified_by", "")})
    counts = coverage_totals()["counts"]
    return {"schema": SCHEMA["verification"], "rows": rows,
            "tiers": queue.get("tiers", {}),
            "verified": queue.get("verified", {}), "verifiable": queue.get("verifiable", {}),
            "signed": counts.get("verified", 0), "total": counts.get("total", 0),
            "human_verification": PENDING}


def authority_view(auth: dict) -> dict:
    """The rule's own paragraphs, verbatim, with the per cell mapping. Opened
    from the authority panel, so it never rides the first paint."""
    return {"schema": SCHEMA["authority"], "rule": dict(RULE), "citation": RULE_CITATION,
            "authority": auth,
            "cells": {cid: rule_ref(cid, auth) for cid in CELLS}}


def evidence_view() -> dict:
    """One row per cell that carries a quote, which is what evidence search
    reads. The value and the quote are the searchable text, and every row
    names the document it came from."""
    rows = []
    for key in sorted(product_keys()):
        p = load_product(key)
        for cid, c in p["cells"].items():
            if not (c.get("quote") or c.get("source")):
                continue
            rows.append({"product_key": key, "fund_name": p["fund_name"], "cell": cid,
                         "element": c.get("element", ""), "value": display_copy(c.get("value", "")),
                         "status": c.get("status", ""),
                         "source": display_path_free(c.get("source", "")),
                         "section": display_copy(c.get("section", "")),
                         "quote": c.get("quote", "")})
    return {"schema": SCHEMA["evidence"], "rows": rows, "human_verification": PENDING}


def exclusion_log() -> list:
    """The considered-and-excluded list as rows. The log is written as prose
    with a name and a reason on each line, and a surface should show two
    fields rather than reprint the markup (the reason a cohort has the
    members it has is a fact a committee asks about)."""
    path = DATA / "roster_decisions.md"
    if not path.exists():
        return []
    text = path.read_text()
    if "## Considered and excluded" not in text:
        return []
    body = text.split("## Considered and excluded", 1)[1].split("\n## ", 1)[0]
    rows, name, reason = [], "", []

    def flush():
        if name:
            rows.append({"name": name, "reason": " ".join(" ".join(reason).split())})

    for line in body.splitlines():
        s = line.strip()
        if s.startswith("- **"):
            flush()
            head, _, rest = s[2:].partition("\u2014")
            name, reason = head.replace("**", "").strip(), [rest.strip()]
        elif name and s and not s.startswith("#"):
            reason.append(s)
        elif not s:
            flush()
            name, reason = "", []
    flush()
    # the log's own separator is not a surface character: the split above
    # turns it into two fields, so a reader sees a name and a reason
    return [{**r, "reason": r["reason"].replace("\u2014", ", ").replace(";", ".")} for r in rows]


def cohorts_view(cohorts: dict, caveats: dict, exclusions: list) -> dict:
    """Every cohort at once, with the caveat matrix and the exclusion log
    already parsed into rows, so no surface renders raw markup."""
    return {"schema": SCHEMA["cohorts"], "cohorts": cohorts, "caveats": caveats,
            "exclusions": exclusions,
            "members": {cid: list(c.get("members", []))
                        for cid, c in _registry().get("cohorts", {}).items()},
            "human_verification": PENDING}


def lab_view(swap: dict, profiles: dict, library: dict, sources: dict) -> dict:
    """What the analysis lab needs to grade any product against any proxy in
    the library, which is the same scorer the selection used."""
    return {"schema": SCHEMA["lab"], "matrix": swap, "profiles": profiles,
            "library": library, "sources": sources, "human_verification": PENDING}


def census_view(doc: dict) -> dict:
    """The universe index as JSON. The detail shards and the text sidecar
    keep their own files, because 3,599 entities with their provenance do
    not belong on a first paint."""
    return {"schema": SCHEMA["census"], **doc}

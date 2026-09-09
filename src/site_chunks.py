"""
The record as JSON chunks the rebuilt frontend fetches (R3-P1 data access).

`src/build_site.py` writes these beside the legacy bundle. Every chunk is a
view from `src/tark_views.py`, which is the same builder the workspace API
and the job runner use, so the static demo and a partner's workspace serve
one shape and the adapter that reads them does not know which it has.

Layout under site/data/, and the API route that answers the same shape:

    index.json                          /api/reference/index.json
    screener.json                       (static only: the demo's 16 products)
    product/<key>/record.json           /api/records/<id>/record.json
    product/<key>/selection.json        /api/records/<id>/selection.json
    product/<key>/cohort.json           /api/records/<id>/cohort.json
    product/<key>/facts.json            /api/records/<id>/facts.json
    product/<key>/series.json           /api/records/<id>/series.json
    product/<key>/liquidity/<plan>.json /api/records/<id>/liquidity.json
    product/<key>/documents/<plan>.json /api/documents/<id>
    manifest.json                       (the chunk list and the shapes)

Static only, because they describe the demo's own reference set rather than
one record: plans.json, funnel.json, coverage.json, verification.json,
authority.json, evidence.json, cohorts.json, lab.json, and the universe as
census/index.json with 64 detail shards and a text sidecar.

Chunks are written whole on every build, and the folder is emptied first, so
a product that leaves the record cannot leave a chunk behind.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from tark_anon import leaks
from tark_data import load_products, plan_keys
from tark_views import (SCHEMA, authority_view, census_view, cohorts_view, coverage_view, daily_view,
                        evidence_view, funnel_view, index_view, lab_view, plans_view,
                        product_view, screener_view, series_view, verification_view)

CHUNK_DIR = "data"          # under site/


def _write(path: Path, payload: dict) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False, sort_keys=True)
    bad = leaks(text)
    if bad:
        raise SystemExit(f"ANONYMIZATION FAILURE: token(s) {bad} would enter "
                         f"{path.name}. Build refused.")
    path.write_text(text + "\n")
    return len(text)


def write_chunks(site: Path, record_name=None, attachment: str = "", demo: dict | None = None) -> dict:
    """Every chunk, plus the manifest that lists them. record_name(plan, key)
    gives the document's file name, so the writer stays the one place that
    names a document. `demo` carries what only the public build computes (the
    universe, the queue, the lab matrix and the held series): the shapes are
    the view builder's, the inputs are the caller's."""
    d = demo or {}
    out = site / CHUNK_DIR
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    files: dict[str, int] = {}
    files["index.json"] = _write(out / "index.json", index_view())
    files["screener.json"] = _write(out / "screener.json", screener_view())
    plans = plan_keys()
    for key in sorted(load_products()):
        base = out / "product" / key
        for name in ("record", "selection", "cohort", "facts"):
            files[f"product/{key}/{name}.json"] = _write(base / f"{name}.json", product_view(name, key))
        files[f"product/{key}/series.json"] = _write(
            base / "series.json", series_view(key, **(d.get("series") or {}).get(key, {})))
        for plan in plans:
            files[f"product/{key}/liquidity/{plan}.json"] = _write(
                base / "liquidity" / f"{plan}.json", product_view("liquidity", key, plan))
            files[f"product/{key}/documents/{plan}.json"] = _write(
                base / "documents" / f"{plan}.json",
                product_view("documents", key, plan,
                             record_name=record_name(plan, key) if record_name else "",
                             attachment=attachment))

    # the routes that are not per product
    census = d.get("census") or {}
    crosscheck = d.get("crosscheck") or {}
    queue = d.get("verification") or {}
    globals_ = {
        "plans.json": plans_view(d.get("plans") or {}, d.get("plan_order") or []),
        "funnel.json": funnel_view(census, crosscheck, queue),
        "coverage.json": coverage_view(crosscheck),
        "verification.json": verification_view(queue),
        "authority.json": authority_view(d.get("authority") or {}),
        "evidence.json": evidence_view(),
        "cohorts.json": cohorts_view(d.get("cohorts") or {}, d.get("caveats") or {},
                                     d.get("exclusions") or []),
        "lab.json": lab_view(d.get("swap_matrix") or {}, d.get("pme_profiles") or {},
                             d.get("proxy_library") or {}, d.get("series_sources") or {}),
    }
    for name, payload in globals_.items():
        files[name] = _write(out / name, payload)

    # every held daily series as its own chunk: a chart asks for the one it
    # draws, and no page carries eleven series it will not use
    sources = d.get("series_sources") or {}
    for name, points in (d.get("daily_series") or {}).items():
        files[f"daily/{name}.json"] = _write(out / "daily" / f"{name}.json",
                                             daily_view(name, points, sources.get(name)))

    # the universe: an index a filter reads, detail shards an entity opens,
    # and the text sidecar a name search needs
    if census:
        files["census/index.json"] = _write(out / "census" / "index.json", census_view(census))
        for n, shard in (d.get("census_shards") or {}).items():
            files[f"census/d/{n}.json"] = _write(out / "census" / "d" / f"{n}.json", shard)
        if d.get("census_search") is not None:
            files["census/search.json"] = _write(out / "census" / "search.json", d["census_search"])

    manifest = {"schema": SCHEMA["manifest"], "shapes": dict(SCHEMA),
                "products": sorted(load_products()), "plans": list(plans),
                "files": {k: files[k] for k in sorted(files)}}
    total = _write(out / "manifest.json", manifest)
    return {"files": len(files) + 1, "bytes": sum(files.values()) + total,
            "index_bytes": files["index.json"], "screener_bytes": files["screener.json"]}

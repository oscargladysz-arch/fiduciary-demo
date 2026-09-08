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
    product/<key>/liquidity/<plan>.json /api/records/<id>/liquidity.json
    product/<key>/documents/<plan>.json /api/documents/<id>
    manifest.json                       (the chunk list and the shapes)

Chunks are written whole on every build, and the folder is emptied first, so
a product that leaves the record cannot leave a chunk behind.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from tark_anon import leaks
from tark_data import load_products, plan_keys
from tark_views import SCHEMA, index_view, product_view, screener_view

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


def write_chunks(site: Path, record_name=None, attachment: str = "") -> dict:
    """Every chunk, plus the manifest that lists them. record_name(plan, key)
    gives the document's file name, so the writer stays the one place that
    names a document."""
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
        for plan in plans:
            files[f"product/{key}/liquidity/{plan}.json"] = _write(
                base / "liquidity" / f"{plan}.json", product_view("liquidity", key, plan))
            files[f"product/{key}/documents/{plan}.json"] = _write(
                base / "documents" / f"{plan}.json",
                product_view("documents", key, plan,
                             record_name=record_name(plan, key) if record_name else "",
                             attachment=attachment))
    manifest = {"schema": SCHEMA["manifest"], "shapes": dict(SCHEMA),
                "products": sorted(load_products()), "plans": list(plans),
                "files": {k: files[k] for k in sorted(files)}}
    total = _write(out / "manifest.json", manifest)
    return {"files": len(files) + 1, "bytes": sum(files.values()) + total,
            "index_bytes": files["index.json"], "screener_bytes": files["screener.json"]}

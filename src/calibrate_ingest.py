"""
Calibrate the ingest extractor against an evaluated product
    python src/calibrate_ingest.py <key> [--model ID] [--only 2.1,2.3] [--out DIR]

Runs the extraction contract on a product whose filings are on disk and
whose cells were already extracted by a person or an earlier agent pass,
in a scratch copy where the target cells are reset to pending, and compares
each outcome with the committed cell:
  located        the model's quote appears verbatim in the cited document
  same_document  the model cited the same form and filing date the record cites
  figures        the figures (percentages, dollar amounts, dates, counts)
                 in the model's value, and the share of the committed
                 cell's figures the model reproduced
  status         extracted-unverified, partial or pending against the record's
Writes data/ingest/calibration_<key>.json. Nothing in the repository's
record changes: the run happens in the scratch copy. Needs the filings in
data/raw/<key>/ (data/raw is not in git) and a key in the environment.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

FIGURE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\$?\d[\d,]*(?:\.\d+)?%?")   # dates first, then numbers
FORM_DATE = re.compile(r"\b([0-9A-Z][0-9A-Z-]*(?:/A)?)\b[^0-9]{0,40}(\d{4}-\d{2}-\d{2})")


def figures(text: str) -> set[str]:
    return {m.group(0).replace(",", "").rstrip(".") for m in FIGURE.finditer(text or "")}


def form_and_date(source: str) -> tuple[str, str] | None:
    m = FORM_DATE.search(source or "")
    return (m.group(1), m.group(2)) if m else None


def compare(committed: dict, produced: dict | None, outcome_status: str, reason: str) -> dict:
    """One cell's calibration row from the committed cell and the outcome."""
    row = {"committed_status": committed.get("status", ""), "outcome_status": outcome_status, "reason": reason}
    if produced is None:
        row.update({"located": False, "same_document": None, "figures_committed": sorted(figures(committed.get("value", ""))),
                    "figures_produced": [], "figure_recall": None})
        return row
    fc, fp = figures(committed.get("value", "")), figures(produced.get("value", ""))
    row.update({
        "located": outcome_status == "extracted-unverified",
        "same_document": (form_and_date(committed.get("source", "")) == form_and_date(produced.get("source", "")))
        if form_and_date(committed.get("source", "")) and form_and_date(produced.get("source", "")) else None,
        "figures_committed": sorted(fc), "figures_produced": sorted(fp),
        "figure_recall": (len(fc & fp) / len(fc)) if fc else None,
        "value_produced": produced.get("value", ""), "quote_produced": produced.get("quote", ""),
    })
    return row


def summarize(rows: dict) -> dict:
    n = len(rows)
    located = sum(1 for r in rows.values() if r.get("located"))
    same_doc = [r["same_document"] for r in rows.values() if r.get("same_document") is not None]
    recall = [r["figure_recall"] for r in rows.values() if r.get("figure_recall") is not None]
    return {"cells": n, "located": located,
            "located_share": round(located / n, 3) if n else None,
            "same_document_share": round(sum(same_doc) / len(same_doc), 3) if same_doc else None,
            "mean_figure_recall": round(sum(recall) / len(recall), 3) if recall else None,
            "partial": sum(1 for r in rows.values() if str(r["outcome_status"]).startswith("partial")),
            "pending": sum(1 for r in rows.values() if r["outcome_status"] == "pending extraction")}


def calibrate(client, key: str, model: str, only: set[str] | None = None,
              scratch: Path | None = None, today: str | None = None) -> dict:
    """Run the extractor in a scratch copy of data/ with the target cells reset,
    then compare. The client is any object with messages.parse (a mock in tests)."""
    from tark_data import DATA as LIVE
    scratch = scratch or Path(tempfile.mkdtemp(prefix="tark_calib_"))
    if not (scratch / "data").exists():
        shutil.copytree(LIVE, scratch / "data", ignore=shutil.ignore_patterns("census", "memos"))
    os.environ["TARK_DATA_DIR"] = str(scratch / "data")
    import importlib
    import tark_data
    importlib.reload(tark_data)
    import ingest
    importlib.reload(ingest)
    from tark_data import CELLS, EVIDENCE_COLUMNS, load_evidence, load_product, status_kind
    import csv
    product = load_product(key)
    committed = json.loads(json.dumps(product["cells"]))
    targets = [c for c in ingest.extractable_cells() if (not only or c in only)
               and status_kind(str(committed[c].get("status", ""))) in ("extracted", "partial")]
    for c in targets:
        product["cells"][c] = {"element": CELLS[c], "value": "", "status": "pending extraction", "source": "",
                               "section": "", "quote": "", "extracted_by": "", "verified_by": ""}
    (tark_data.DATA / "products" / f"{key}.json").write_text(json.dumps(product, indent=2, ensure_ascii=False) + "\n")
    rows = load_evidence(key)
    for r in rows:
        if r["cell_id"] in targets:
            r.update({"value": "", "source_doc": "", "source_section": "", "quote": "", "extracted_by": "",
                      "verified_by": "", "status": "pending extraction"})
    with open(tark_data.DATA / "evidence" / f"{key}_evidence.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=EVIDENCE_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    docs, skipped = ingest.documents_for(key)
    for s in skipped:
        print(f"  [skipped] {s['document']}: {s['reason']}")
    if not docs:
        raise SystemExit(f"no filing text on disk for {key} (data/raw/{key}/ is empty here)")
    outcomes = ingest.run_extraction(client, key, docs, set(targets), model, today)
    result = {}
    for o in outcomes:
        if o.cid in targets:
            result[o.cid] = compare(committed[o.cid], o.record, o.status, o.reason)
            result[o.cid]["usd"] = round(o.usd, 6)
            result[o.cid]["tokens"] = o.tokens
    report = {"product": key, "model": model, "documents": [d.label for d in docs],
              "targets": targets, "summary": summarize(result), "cells": result,
              "cost": outcomes.cost.as_dict(), "estimate": outcomes.estimate, "stopped": outcomes.stopped}
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("--model", default=os.environ.get("TARK_INGEST_MODEL", "claude-opus-5"))
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=str(BASE / "data" / "ingest"))
    a = ap.parse_args()
    import anthropic
    report = calibrate(anthropic.Anthropic(), a.key, a.model, {c for c in a.only.split(",") if c} or None)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"calibration_{a.key}.json"
    path.write_text(json.dumps(report, indent=2))
    s = report["summary"]
    print(f"{a.key}: {s['cells']} cells, located {s['located']} ({s['located_share']}), same document "
          f"{s['same_document_share']}, mean figure recall {s['mean_figure_recall']}, partial {s['partial']}, "
          f"pending {s['pending']} -> {path}")
    c = report["cost"]
    print(f"cost: {c['calls']} calls, ${c['usd']:.2f} (an estimate at the configured price list), "
          f"{c['input_tokens']:,} in / {c['cache_read_input_tokens']:,} cache read / {c['output_tokens']:,} out")
    return 0


if __name__ == "__main__":
    sys.exit(main())

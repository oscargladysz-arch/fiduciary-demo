"""
The pipeline child (R3-P4-6): runs inside the public checkout with
TARK_DATA_DIR already bound to the job's data root, and prints one JSON
line per event on stdout for the parent (worker.run_job) to relay to the
jobs row. Nothing here talks to Supabase or holds a key.

    python -m worker.pipeline --workdir W --cik N --key K --plan-key P
        [--mock] [--skip-fetch] [--budget-usd B] [--spent-before-usd S]
        [--time-budget-s T] [--as-of DATE]

Steps: registry entry, filings (fetched, or the synthetic fixture under
--mock), the ingest (run_product), the producers, the documents, the views,
and a manifest of every output with its hash. The exit code is the ingest's
(0 done, 1 refused or invalid, 2 stopped, 3 estimate over budget).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def emit(**ev) -> None:
    sys.stdout.write(json.dumps(ev, default=str) + "\n")
    sys.stdout.flush()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------- registry entry
CENSUS_TO_WRAPPER = {"interval_23c3": "interval_23c3", "tender_cef": "tender_offer", "bdc": "nontraded_bdc",
                     "nontraded_reit": "nontraded_reit", "listed_cef": "listed_cef",
                     "unlisted_cef_other": "tender_offer", "nontraded_34act_other": "nontraded_llc"}


def default_registry_entry(key: str, wrapper_class: str, listed: bool, as_of: str, registry: dict) -> dict:
    """A registry entry with no person's judgment in it: the wrapper from the
    census class, the document sets the reference products of that wrapper
    use, and every judged field set to the words that say it is pending.
    The record it produces carries the 55 cells and says the cohort, the
    strategy and the benchmark wait for a person."""
    wrapper = CENSUS_TO_WRAPPER.get(wrapper_class, "tender_offer")
    filings: dict[str, list[str]] = {}
    for p in registry["products"].values():
        if p.get("wrapper_type") == wrapper:
            for ds, forms in (p.get("filings") or {}).items():
                filings.setdefault(ds, [])
                for f in forms:
                    if f not in filings[ds]:
                        filings[ds].append(f)
    if not filings:
        filings = {"prospectus": ["486BPOS", "424B3", "N-2"], "annual_report": ["N-CSR", "10-K"]}
    pending = "pending a person's judgment (default entry from the census)"
    src = "default entry derived from the census wrapper class for a workspace job, pending a person's judgment"
    return {
        "cohort": f"uncohorted_{key}", "strategy": "not_judged", "asset_class": "not_judged",
        "sub_strategy": "not_judged", "wrapper_type": wrapper, "pricing_class": "MARKET" if listed else "NAV",
        "nav_cadence": "not read", "leverage_regime": pending, "held_returns": {"kind": "none"},
        "advisers": ["not read"], "adviser_keys": [], "declared_benchmarks": [], "source_cells": [],
        "as_of": as_of, "depth": "cohort", "membership_rationale": pending,
        "declared_none_reason": "cell 5.1 is read by the ingest, the declared benchmark is typed by a person after it",
        "filings": filings, "price_nav_decoupled": bool(listed), "default_entry": True,
        "sources": {f: src for f in ("asset_class", "sub_strategy", "pricing_class", "leverage_regime", "nav_cadence",
                                     "as_of", "depth", "membership_rationale", "filings", "strategy", "wrapper_type",
                                     "held_returns", "advisers", "declared_benchmarks")},
    }


def install_registry_entry(data: Path, key: str, entry: dict) -> None:
    rp = data / "registry.json"
    reg = json.loads(rp.read_text())
    reg["products"][key] = entry
    cid = entry["cohort"]
    if cid not in reg["cohorts"]:
        reg["cohorts"][cid] = {"label": "Uncohorted, pending a person's cohort decision", "members": [key]}
    elif key not in reg["cohorts"][cid]["members"]:
        reg["cohorts"][cid]["members"].append(key)
    rp.write_text(json.dumps(reg, indent=1))


def install_plan(data: Path, plan: dict) -> str:
    """The workspace plan under its own key beside the reference plans."""
    p = data / "plans" / f"{plan['plan_key']}.json"
    p.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    return plan["plan_key"]


def mock_filing(data: Path, key: str, cik: str) -> None:
    """Under --mock with no filing on disk: the synthetic fixture as the held
    filing, with its manifest row, labeled synthetic in the row itself."""
    from mock_model import FILING_PATH
    raw = data / "raw" / key
    raw.mkdir(parents=True, exist_ok=True)
    name = "486BPOS_2026-05-01_synthetic.htm"
    shutil.copy(FILING_PATH, raw / name)
    mp = data / "manifest.csv"
    rows = list(csv.DictReader(open(mp, newline=""))) if mp.exists() else []
    cols = ["product", "fund_name", "cik", "doc_set", "form", "filing_date", "accession", "primary_document", "url",
            "local_path", "pulled_at_utc"]
    acc = f"{int(cik):010d}-26-000001"
    if not any(r["product"] == key for r in rows):
        rows.append({"product": key, "fund_name": "synthetic filing for a mocked job", "cik": cik, "doc_set": "prospectus",
                     "form": "486BPOS", "filing_date": "2026-05-01", "accession": acc, "primary_document": "synthetic.htm",
                     "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/synthetic.htm",
                     "local_path": f"data/raw/{key}/{name}", "pulled_at_utc": "2026-09-08T00:00:00+00:00"})
        with open(mp, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--cik", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--plan-key", required=True)
    ap.add_argument("--mock", action="store_true", help="the mocked model and the synthetic filing, no network, no key")
    ap.add_argument("--skip-fetch", action="store_true")
    ap.add_argument("--budget-usd", type=float, default=None)
    ap.add_argument("--spent-before-usd", type=float, default=0.0)
    ap.add_argument("--time-budget-s", type=float, default=None)
    ap.add_argument("--as-of", default=date.today().isoformat())
    a = ap.parse_args()
    workdir = Path(a.workdir).resolve()
    data = workdir / "data"
    if os.environ.get("TARK_DATA_DIR", "") != str(data):
        emit(event="error", reason="the data root is not bound to the job's data folder")
        return 1
    os.environ.setdefault("TARK_AS_OF", a.as_of)
    import ingest  # bound to TARK_DATA_DIR
    from tark_data import validate_product

    emit(event="step", step="preparing the record", detail="the job's copy of the record, the plan and the registry entry")
    key, cik = a.key, str(int(a.cik))
    if not (data / "products" / f"{key}.json").exists() and (data / "census" / "census.json").exists():
        pass  # promote.scaffold runs inside run_product when the file is absent
    reg = json.loads((data / "registry.json").read_text())
    if key not in reg["products"]:
        cen = json.loads((data / "census" / "census.json").read_text())["entities"].get(cik, {}) if (data / "census" / "census.json").exists() else {}
        listed = bool(((cen.get("listed_common") or cen.get("listed") or {}) or {}).get("value"))
        entry_path = workdir / "registry_entry.json"
        entry = json.loads(entry_path.read_text()) if entry_path.exists() else default_registry_entry(
            key, cen.get("wrapper_class", ""), listed, a.as_of, reg)
        install_registry_entry(data, key, entry)
        emit(event="step", step="preparing the record",
             detail="registry entry " + ("from the person's file" if entry_path.exists() else "by default from the census, pending a person's judgment"))
    if a.mock:
        emit(event="step", step="fetching filings", detail="mocked job: the synthetic filing stands in for the fund's filings")
        # the scaffold needs the census, the mocked filing needs the product key on the manifest
        if not (data / "products" / f"{key}.json").exists():
            import promote
            cen_path = data / "census" / "census.json"
            cen_all = json.loads(cen_path.read_text())["entities"] if cen_path.exists() else {}
            try:
                promote.scaffold(cik, key, submissions_fn=lambda c: {"name": (cen_all.get(cik) or {}).get("name", f"CIK {cik}"),
                                                                     "formerNames": []})
            except promote.ScaffoldRefused as e:
                emit(event="error", reason=str(e))
                return 1
        mock_filing(data, key, cik)
    elif not a.skip_fetch:
        emit(event="step", step="fetching filings", detail="the registry's document sets from EDGAR")

    def on_progress(ev: dict) -> None:
        if ev["event"] == "run_start":
            emit(event="step", step="extracting cells", detail=f"estimate ${ev['estimate']['usd']:.2f} of ${ev['budget_usd']:.2f} budget, {ev['calls_planned']} calls planned",
                 estimate=ev["estimate"])
        elif ev["event"] == "cell_start":
            emit(event="step", step=f"extracting cell {ev['index']} of {ev['total']}", detail=f"cell {ev['cell']}, ${ev['usd_so_far']:.2f} so far")
        elif ev["event"] == "cell_done":
            emit(event="cell", cell=ev["cell"], status=ev["status"], reason=ev["reason"], tokens=ev["tokens"], usd=ev["usd"])
        elif ev["event"] == "run_end":
            emit(event="cost", cost=ev["cost"], stopped=ev["stopped"])

    client = None
    if a.mock:
        from mock_model import MockClient, canned_answers
        docs, _ = ingest.documents_for(key)
        label = docs[0].label if docs else ""
        answers, usage, default = canned_answers(label)
        client = MockClient(answers, usage, default)
    try:
        res = ingest.run_product(cik, workdir, on_progress=on_progress, model_client=client, key=key,
                                 skip_fetch=a.mock or a.skip_fetch, budget_usd=a.budget_usd,
                                 spent_before_usd=a.spent_before_usd, time_budget_s=a.time_budget_s, today=a.as_of)
    except ingest.Refusal as r:
        emit(event="error", reason=r.reason, commands=r.commands)
        return 1
    emit(event="ingest", summary=res.summary(), stopped=res.stopped, cost=res.cost.as_dict(), estimate=res.estimate,
         validate_errors=res.validate_errors, written=res.written, documents=res.documents,
         skipped_documents=res.skipped_documents, report=str(res.report_path))
    if res.validate_errors:
        emit(event="error", reason="the record did not validate after the extraction: " + res.validate_errors[0])
        return 1
    if res.stopped:
        emit(event="error", reason=res.stopped["detail"], stopped=res.stopped)
        return 3 if res.stopped["reason"] == "estimate over budget" else 2

    emit(event="step", step="computing benchmark and liquidity", detail="facts, liquidity matches, cohorts, the benchmark selection, computed cells")
    import produce
    produce.run(data_dir=str(data), as_of=a.as_of)
    errs = validate_product(key)
    if errs:
        emit(event="error", reason="the record did not validate after the producers: " + errs[0])
        return 1

    emit(event="step", step="writing documents", detail="the Investment Selection Record and its attachment")
    out = workdir / "out"
    docs_dir = out / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    import tark_memo
    record_path = tark_memo.build_record(key, a.plan_key, docs_dir)
    att = tark_memo.build_attachment(docs_dir)
    from tark_anon import docx_texts, leaks
    prose, prov = docx_texts(record_path)
    hits = leaks(prose + "\n" + prov)
    if hits:
        emit(event="error", reason="the document carried a reference sponsor token and was withheld")
        return 1

    emit(event="step", step="writing views", detail="the JSON views the workspace serves")
    from worker.views import write_views
    view_files = write_views(data, key, a.plan_key, out / "views", res.report_path)
    artifacts = out / "artifacts"
    artifacts.mkdir(exist_ok=True)
    for src_p in (data / "products" / f"{key}.json", data / "evidence" / f"{key}_evidence.csv", data / "facts" / f"{key}.json",
                  data / "benchmarks" / f"{key}_selection.json", data / "liquidity" / f"{a.plan_key}__{key}_match.json",
                  data / "manifest.csv", res.report_path):
        if src_p.exists():
            shutil.copy(src_p, artifacts / src_p.name)
    manifest = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rel = str(p.relative_to(out))
            kind = ("selection_record" if p == record_path else "attachment" if att and p == att
                    else "view" if rel.startswith("views/") else "ingest_report" if p.name.endswith("_report.json") else "artifact")
            manifest.append({"path": rel, "kind": kind, "size_bytes": p.stat().st_size, "sha256": sha256(p)})
    record_hash = hashlib.sha256(json.dumps([(m["path"], m["sha256"]) for m in manifest], sort_keys=True).encode()).hexdigest()
    (out / "manifest.json").write_text(json.dumps({"schema": "tark.job_output.v1", "product_key": key, "plan_key": a.plan_key,
                                                   "cik": cik, "as_of": a.as_of, "record_hash": record_hash,
                                                   "files": manifest}, indent=1))
    emit(event="done", record_hash=record_hash, files=len(manifest), views=[str(v.name) for v in view_files],
         record=str(record_path.relative_to(out)), attachment=str(att.relative_to(out)) if att else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Worker gate (R3-P4-6, offline)
===============================
A mocked-model job end to end against the fake Supabase and the pipeline in
this checkout: the claim, the budget check against the spend ledger, the
working copy of the record with the workspace plan and a default registry
entry, the pipeline child with the synthetic filing and the mock client,
every progress step relayed to the jobs row in order, the outputs uploaded
under the workspace prefix, the records, documents and spend rows with
hashes, the job marked done with its cost. Then the paths that must not
create a record: a job that is not queued, a spent budget, a pipeline that
refuses. No network, no key, no real model (decision 8.17).

Run: python worker/test_worker.py   (exit 0 = all pass)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "src"))

from app.supabase import Supabase  # noqa: E402
from app.testing import FakeSupabase  # noqa: E402
from worker.pipeline import CENSUS_TO_WRAPPER, default_registry_entry  # noqa: E402
from worker.run_job import STEP_ORDER, run_job  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" : {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


fake = FakeSupabase()
sb = Supabase("https://project.supabase.test", fake.service_key, transport=fake.transport)
alice = fake.seed_user("alice@example.test")
ws = fake.seed_workspace("Workspace A", alice)

import plan_intake  # noqa: E402
FORM = {"display_label": "US regional clinic 403(b) plan (~$400M, OH)", "anonymization_label": "US regional clinic 403(b) plan (~$400M, OH)",
        "plan_year": "2024-01-01 to 2024-12-31", "net_assets_eoy": 400_000_000, "net_assets_boy": 360_000_000,
        "tot_admin_expenses": 800_000, "with_account_balances": 5000, "active_eoy": 4200,
        "separated_deferred_vested": 700, "retired_receiving": 30, "pension_benefit_codes": "2E2G2J2K", "pulled": "2026-09-08"}
plan_obj = plan_intake.scaffold(dict(FORM))
plan_obj["plan_key"] = "ws_" + plan_obj["plan_key"][:28]
plan = sb.insert("plans", {"workspace_id": ws, "intake": plan_obj, "source_note": "intake by the adviser"})
product = sb.insert("products", {"workspace_id": ws, "cik": "1467631", "name": "ACAP Strategic Fund", "wrapper": "interval_23c3",
                                 "product_key": "cik_1467631"})
job = sb.insert("jobs", {"workspace_id": ws, "product_id": product["id"], "plan_id": plan["id"], "state": "queued",
                         "progress_step": "queued", "pipeline_commit": "local"})

# ---------------- the default registry entry: the wrapper's document sets, every judged field pending
reg = json.loads((BASE / "data" / "registry.json").read_text())
entry = default_registry_entry("cik_1467631", "interval_23c3", False, "2026-09-08", reg)
check("registry: the default entry takes the interval wrapper's document sets from the reference products and says every judgment is pending",
      entry["wrapper_type"] == "interval_23c3" and "486BPOS" in entry["filings"]["prospectus"] and "N-CSR" in entry["filings"]["annual_report"]
      and entry["cohort"] == "uncohorted_cik_1467631" and entry["default_entry"] is True and "pending" in entry["membership_rationale"]
      and entry["held_returns"] == {"kind": "none"} and entry["pricing_class"] == "NAV"
      and all(v in ("interval_23c3", "tender_offer", "nontraded_bdc", "nontraded_reit", "listed_cef", "nontraded_llc")
              for v in CENSUS_TO_WRAPPER.values()))

# ---------------- the mocked job, end to end
logs = []
wd = Path(tempfile.mkdtemp(prefix="tark_worker_test_"))
res = run_job(job["id"], "mock", runner="laptop", sb=sb, pipeline_dir=BASE, workdir=wd, budget_usd=50.0, log=logs.append)
row = sb.select("jobs", filters={"id": job["id"]})[0]
steps = [p[2]["progress_step"] for p in fake.patches if p[0] == "jobs" and "progress_step" in p[2]]
check("job: claimed by the laptop runner, run to done, with the cost and the file count on the row",
      res.claimed and res.state == "done" and row["state"] == "done" and row["runner"] == "laptop" and row["attempts"] == 1
      and row["claimed_at"] and row["finished_at"] and row["progress_step"] == "done" and row["cost_usd"] > 0
      and row["tokens_out"] > 0 and res.documents > 0 and res.record_id, f"{res.state} {res.reason} {row.get('failure_reason')} {logs[-6:]}")
_order = []
for s_ in steps:
    if s_ in STEP_ORDER and (not _order or _order[-1] != s_):
        _order.append(s_)
_cells = [s for s in steps if re.match(r"extracting cell \d+ of \d+", s)]
check("progress: the steps reach the row in the documented order with one row update per cell",
      _order == [s for s in STEP_ORDER if s in _order]
      and _order[:2] == ["preparing the record", "fetching filings"] and "computing benchmark and liquidity" in _order
      and "writing documents" in _order and "uploading" in _order and _order[-1] == "done"
      and len(_cells) == 32 and _cells[0] == "extracting cell 1 of 32", str(_order) + str(len(_cells)))
recs = sb.select("records", filters={"job_id": job["id"]})
docs = sb.select("documents", filters={"record_id": recs[0]["id"]}) if recs else []
kinds = {d["kind"] for d in docs}
check("records: one records row with the output hash under the workspace prefix, and one documents row per uploaded file with its hash and size",
      len(recs) == 1 and recs[0]["artifacts_prefix"] == f"{ws}/{job['id']}" and re.fullmatch(r"[0-9a-f]{64}", recs[0]["record_hash"])
      and len(docs) == res.documents and kinds >= {"selection_record", "attachment", "view", "ingest_report", "artifact"}
      and all(re.fullmatch(r"[0-9a-f]{64}", d["sha256"]) and d["size_bytes"] > 0 and d["storage_path"].startswith(f"{ws}/{job['id']}/")
              for d in docs), str(kinds))
_bad_hash = []
for d in docs:
    data = fake.objects.get(f"workspace/{d['storage_path']}")
    if data is None or hashlib.sha256(data).hexdigest() != d["sha256"] or len(data) != d["size_bytes"]:
        _bad_hash.append(d["storage_path"])
check("storage: every documents row's object is in the bucket under the workspace prefix with the recorded hash and size",
      not _bad_hash and f"workspace/{ws}/{job['id']}/manifest.json" in fake.objects, str(_bad_hash[:3]))
views = {d["storage_path"].rsplit("/", 1)[-1] for d in docs if d["kind"] == "view"}
check("views: record, selection, liquidity, cohort, facts and report views were written for the workspace",
      views == {"record.json", "selection.json", "liquidity.json", "cohort.json", "facts.json", "report.json"}, str(views))
rec_view = json.loads(fake.objects[f"workspace/{ws}/{job['id']}/views/record.json"])
check("views: the record view carries the 55 cells, the coverage, the pending verification and the default registry marker",
      rec_view["schema"] == "tark.record.v1" and len(rec_view["cells"]) == 55 and rec_view["human_verification"] == "pending"
      and rec_view["registry"]["default_entry"] is True and "resolved" in rec_view["coverage"]["headline"]
      and rec_view["cells"]["2.1"]["status"].startswith("extracted-unverified"), str(rec_view.get("coverage"))[:200])
liq_view = json.loads(fake.objects[f"workspace/{ws}/{job['id']}/views/liquidity.json"])
check("views: the liquidity view is for the workspace plan and says what the untyped facts allow",
      liq_view["plan_key"] == plan_obj["plan_key"] and liq_view["match"] is not None and "verdict" in liq_view["match"])
docx_path = next(d["storage_path"] for d in docs if d["kind"] == "selection_record")
from tark_anon import docx_texts, leaks  # noqa: E402
_tmp_docx = wd / "check.docx"
_tmp_docx.write_bytes(fake.objects[f"workspace/{docx_path}"])
prose, prov = docx_texts(_tmp_docx)
check("documents: the Investment Selection Record for the workspace plan opens, names the fund and the plan label, says pending, and carries no reference sponsor token",
      "ACAP Strategic Fund" in prose and FORM["display_label"] in prose and "pending" in prose.lower() and not leaks(prose + prov)
      and docx_path.endswith(f"{plan_obj['plan_key']}__cik_1467631_selection_record.docx"), docx_path)
spend = sb.select("spend", filters={"job_id": job["id"]})
check("spend: one ledger row equal to the job's cost, an estimate at the price list, and the total the budget guard reads",
      len(spend) == 1 and abs(float(spend[0]["cost_usd"]) - float(row["cost_usd"])) < 1e-9 and "estimate" in spend[0]["note"]
      and abs(float(sb.rpc("spend_total")) - float(row["cost_usd"])) < 1e-9)
audits = [a["event"] for a in fake.tables["audit_log"]]
check("audit: the claim and the completion are logged with no user", audits.count("job_claimed") == 1 and audits.count("job_done") == 1
      and all(a["user_id"] is None for a in fake.tables["audit_log"] if a["event"].startswith("job_")))
check("secrets: no log line carries the service key",
      not any(fake.service_key in ln for ln in logs) and not any("SUPABASE_SERVICE_KEY" in ev.get("detail", "") for ev in res.events if isinstance(ev, dict)))
check("isolation: the checkout's own record, census and manifest are untouched by the job",
      not (BASE / "data" / "raw").exists() and not (BASE / "data" / "products" / "cik_1467631.json").exists()
      and json.loads((BASE / "data" / "census" / "census.json").read_text())["entities"]["1467631"]["promotion"] == {"status": "none"}
      and "cik_1467631" not in (BASE / "data" / "manifest.csv").read_text())

# ---------------- idempotent: a done job is not run again
res2 = run_job(job["id"], "mock", runner="laptop", sb=sb, pipeline_dir=BASE, budget_usd=50.0, log=logs.append)
check("idempotent: running a done job again claims nothing, writes nothing and says why",
      not res2.claimed and res2.state == "skipped" and "done" in res2.reason and len(sb.select("records", filters={"job_id": job["id"]})) == 1
      and len(fake.tables["spend"]) == 1)
check("idempotent: an unknown job id is skipped with the reason", not run_job(str(uuid.uuid4()), "mock", sb=sb, pipeline_dir=BASE, log=logs.append).claimed)

# ---------------- the budget guard: spent at or over the total refuses before any call and creates no record
plan2 = sb.insert("plans", {"workspace_id": ws, "intake": {**plan_obj, "plan_key": "ws_plan_two"}, "source_note": ""})
job2 = sb.insert("jobs", {"workspace_id": ws, "product_id": product["id"], "plan_id": plan2["id"], "state": "queued", "progress_step": "queued"})
res3 = run_job(job2["id"], "mock", runner="actions", sb=sb, pipeline_dir=BASE, budget_usd=float(row["cost_usd"]), log=logs.append)
row2 = sb.select("jobs", filters={"id": job2["id"]})[0]
check("budget: with the ledger at the budget the job fails before the pipeline starts, in words, with no record and no spend row",
      res3.claimed and res3.state == "failed" and "budget is spent" in res3.reason and "Oscar" in res3.reason
      and row2["state"] == "failed" and row2["failure_reason"] == res3.reason and row2["runner"] == "actions"
      and sb.select("records", filters={"job_id": job2["id"]}) == [] and len(fake.tables["spend"]) == 1, res3.reason)

# ---------------- a pipeline that refuses: a CIK the census does not hold
bad = sb.insert("products", {"workspace_id": ws, "cik": "12", "name": "nobody", "wrapper": "", "product_key": "cik_12"})
job3 = sb.insert("jobs", {"workspace_id": ws, "product_id": bad["id"], "plan_id": plan["id"], "state": "queued", "progress_step": "queued"})
res4 = run_job(job3["id"], "mock", runner="laptop", sb=sb, pipeline_dir=BASE, budget_usd=50.0, log=logs.append)
row3 = sb.select("jobs", filters={"id": job3["id"]})[0]
check("refusal: a pipeline refusal marks the job failed with the pipeline's own sentence, no record, no census promotion",
      res4.claimed and res4.state == "failed" and row3["state"] == "failed" and row3["failure_reason"]
      and "census" in row3["failure_reason"] and sb.select("records", filters={"job_id": job3["id"]}) == [], row3["failure_reason"])
check("copy: every failure reason is a sentence with no semicolon or em dash",
      all(";" not in r["failure_reason"] and "—" not in r["failure_reason"] for r in fake.tables["jobs"]))

# ---------------- the tenancy test generator reads the schema
sys.path.insert(0, str(BASE / "tests" / "tenancy"))
from test_tenancy import tenant_tables  # noqa: E402
check("tenancy: the generator finds every tenant-scoped table in the schema, so a new table cannot skip the test",
      set(tenant_tables(BASE / "db" / "001_schema.sql")) == {"workspace_members", "plans", "products", "jobs", "records",
                                                              "documents", "audit_log", "spend"})

shutil.rmtree(wd, ignore_errors=True)
print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nWorker gate passes.")
sys.exit(1 if FAILS else 0)

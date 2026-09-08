"""
run_job (R3-P4-6): the one entry both runners call.

    python -m worker.run_job <job_id> [--runner actions|laptop] [--mock]
                             [--pipeline-dir DIR] [--keep-workdir]

Claims the job (queued to running by a conditional update), checks the
budget of rule 23 against the spend ledger, builds a job working directory
with a copy of the public record, the workspace plan and the registry entry,
runs the pipeline as a child process inside the pinned public checkout
(worker.pipeline), relays every progress event to the jobs row, uploads the
outputs under the workspace prefix, writes the records, documents and spend
rows with hashes, and marks the job done or failed with a reason in plain
words. Re-running a job that is not queued does nothing. A failed job never
creates a record and never marks a census entity evaluated (the census the
child touched is the job's own copy, discarded with the working directory).

Env (the worker's own, never the API's): SUPABASE_URL, SUPABASE_SERVICE_KEY,
ANTHROPIC_API_KEY (real runs), TARK_SEC_CONTACT (fetch), TARK_BUDGET_USD
(default 50, a total), TARK_TIME_BUDGET_S, TARK_PIPELINE_DIR.
model_client: None for the real model, or the mock ("mock", or any object
whose class is named MockClient) for a mocked job.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from app.settings import redact  # noqa: E402
from app.supabase import Supabase, SupabaseError  # noqa: E402

BUCKET = "workspace"
DEFAULT_BUDGET_USD = 50.0
STEP_ORDER = ("queued", "preparing the record", "fetching filings", "extracting cells", "computing benchmark and liquidity",
              "writing documents", "writing views", "uploading", "done", "failed")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class JobResult:
    job_id: str
    claimed: bool
    state: str                       # done | failed | skipped
    reason: str = ""
    record_id: str | None = None
    documents: int = 0
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    events: list = field(default_factory=list)
    workdir: str = ""


def is_mock(model_client) -> bool:
    return model_client == "mock" or type(model_client).__name__ == "MockClient"


def service_client(sb: Supabase | None) -> Supabase:
    if sb is not None:
        return sb
    url, key = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_KEY must be in the worker's environment")
    return Supabase(url, key)


def run_job(job_id: str, model_client=None, *, runner: str = "actions", sb: Supabase | None = None,
            pipeline_dir: str | Path | None = None, workdir: str | Path | None = None,
            budget_usd: float | None = None, time_budget_s: float | None = None,
            python: str = sys.executable, keep_workdir: bool = False, log=print) -> JobResult:
    sb = service_client(sb)
    pipeline = Path(pipeline_dir or os.environ.get("TARK_PIPELINE_DIR") or ROOT).resolve()
    budget = float(os.environ.get("TARK_BUDGET_USD", DEFAULT_BUDGET_USD)) if budget_usd is None else float(budget_usd)
    if time_budget_s is None and os.environ.get("TARK_TIME_BUDGET_S", "").strip():
        time_budget_s = float(os.environ["TARK_TIME_BUDGET_S"])
    mock = is_mock(model_client)
    res = JobResult(job_id=job_id, claimed=False, state="skipped")

    def say(line: str) -> None:
        log(redact(f"[job {job_id[:8]}] {line}"))

    rows = sb.select("jobs", filters={"id": job_id})
    if not rows:
        res.reason = "no job with that id"
        say(res.reason)
        return res
    job = rows[0]
    claimed = sb.update("jobs", {"id": job_id, "state": "queued"},
                        {"state": "running", "runner": runner, "claimed_at": now_iso(), "started_at": now_iso(),
                         "attempts": int(job.get("attempts") or 0) + 1, "progress_step": "preparing the record",
                         "progress_detail": f"claimed by the {runner} runner"})
    if not claimed:
        res.reason = f"the job is {job['state']}, nothing to do"
        say(res.reason)
        return res
    res.claimed = True
    ws = job["workspace_id"]
    sb.insert("audit_log", {"workspace_id": ws, "user_id": None, "event": "job_claimed",
                            "detail": {"job_id": job_id, "runner": runner}})

    def progress(step: str, detail: str = "", **more) -> None:
        sb.update("jobs", {"id": job_id}, {"progress_step": step[:120], "progress_detail": detail[:400], **more})

    def fail(reason: str, cost: dict | None = None) -> JobResult:
        cost = cost or {}
        patch = {"state": "failed", "finished_at": now_iso(), "progress_step": "failed", "failure_reason": reason[:400],
                 "progress_detail": reason[:400]}
        if cost:
            patch.update({"tokens_in": int(cost.get("input_tokens", 0)) + int(cost.get("cache_read_input_tokens", 0))
                          + int(cost.get("cache_creation_input_tokens", 0)), "tokens_out": int(cost.get("output_tokens", 0)),
                          "cost_usd": float(cost.get("usd", 0.0))})
            if float(cost.get("usd", 0.0)) > 0:
                sb.insert("spend", {"workspace_id": ws, "job_id": job_id, "cost_usd": float(cost["usd"]),
                                    "note": "a failed run, the model was called"})
        sb.update("jobs", {"id": job_id}, patch)
        sb.insert("audit_log", {"workspace_id": ws, "user_id": None, "event": "job_failed",
                                "detail": {"job_id": job_id, "reason": reason[:200]}})
        res.state, res.reason, res.cost_usd = "failed", reason, float(cost.get("usd", 0.0))
        say("failed: " + reason)
        return res

    try:
        product = sb.select("products", filters={"id": job["product_id"]})[0]
        plan = sb.select("plans", filters={"id": job["plan_id"]})[0]
    except (IndexError, SupabaseError):
        return fail("the job's product or plan is no longer in the workspace")
    spent = float(sb.rpc("spend_total") or 0.0)
    if spent >= budget:
        return fail(f"the model budget is spent: ${spent:.2f} of ${budget:.2f} across every run so far, raising it is Oscar's action in the environment")

    wd = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="tark_job_"))
    res.workdir = str(wd)
    try:
        sys.path.insert(0, str(pipeline / "src"))
        from ingest import dry_run_copy  # the pinned checkout's own copy helper
        data = wd / "data"
        if not data.exists():
            dry_run_copy(pipeline / "data", data, product["product_key"], product["cik"])
        plan_obj = plan["intake"]
        (data / "plans").mkdir(exist_ok=True)
        (data / "plans" / f"{plan_obj['plan_key']}.json").write_text(json.dumps(plan_obj, indent=2, ensure_ascii=False) + "\n")
        if product.get("registry_entry"):
            (wd / "registry_entry.json").write_text(json.dumps(product["registry_entry"], indent=1))
        env = {k: v for k, v in os.environ.items() if k not in ("SUPABASE_SERVICE_KEY", "SUPABASE_URL", "TARK_DISPATCH_TOKEN")}
        env.update({"TARK_DATA_DIR": str(data), "TARK_AS_OF": date.today().isoformat(), "PYTHONPATH": str(pipeline),
                    "TARK_BUDGET_USD": str(budget)})
        cmd = [python, "-m", "worker.pipeline", "--workdir", str(wd), "--cik", product["cik"], "--key", product["product_key"],
               "--plan-key", plan_obj["plan_key"], "--spent-before-usd", str(spent), "--budget-usd", str(budget),
               "--as-of", env["TARK_AS_OF"]]
        if mock:
            cmd.append("--mock")
        if time_budget_s is not None:
            cmd += ["--time-budget-s", str(time_budget_s)]
        say(f"pipeline at {pipeline} ({'mocked model' if mock else 'real model'}), budget ${budget:.2f}, ${spent:.2f} spent before")
        t0 = time.monotonic()
        proc = subprocess.Popen(cmd, cwd=str(pipeline), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        cost, last_error, done_ev = {}, "", None
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            res.events.append(ev)
            kind = ev.get("event")
            if kind == "step":
                progress(ev["step"], ev.get("detail", ""))
                say(f"{ev['step']}: {ev.get('detail', '')}")
            elif kind == "cost":
                cost = ev.get("cost") or {}
                progress("extracting cells", f"{cost.get('calls', 0)} calls, ${float(cost.get('usd', 0)):.2f}",
                         tokens_in=int(cost.get("input_tokens", 0)) + int(cost.get("cache_read_input_tokens", 0))
                         + int(cost.get("cache_creation_input_tokens", 0)),
                         tokens_out=int(cost.get("output_tokens", 0)), cost_usd=float(cost.get("usd", 0.0)))
            elif kind == "ingest":
                cost = ev.get("cost") or cost
            elif kind == "error":
                last_error = ev.get("reason", "the pipeline stopped without a reason")
            elif kind == "done":
                done_ev = ev
            if time_budget_s is not None and time.monotonic() - t0 > time_budget_s + 900:
                proc.kill()
                last_error = "the job ran past the wall-time budget and was stopped"
                break
        proc.wait()
        stderr_tail = (proc.stderr.read() if proc.stderr else "")[-2000:]
        if proc.returncode != 0 or done_ev is None:
            reason = last_error or f"the pipeline exited with code {proc.returncode}"
            if stderr_tail:
                say("child stderr tail: " + stderr_tail.replace("\n", " | ")[-600:])
            return fail(reason, cost)

        progress("uploading", "documents, views and artifacts to the workspace storage")
        out = wd / "out"
        manifest = json.loads((out / "manifest.json").read_text())
        prefix = f"{ws}/{job_id}"
        uploaded = []
        for f in manifest["files"]:
            p = out / f["path"]
            ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            sb.upload(BUCKET, f"{prefix}/{f['path']}", p.read_bytes(), content_type=ctype)
            uploaded.append(f)
        sb.upload(BUCKET, f"{prefix}/manifest.json", (out / "manifest.json").read_bytes(), content_type="application/json")
        rec = sb.insert("records", {"workspace_id": ws, "product_id": product["id"], "plan_id": plan["id"], "job_id": job_id,
                                    "version": 1, "artifacts_prefix": prefix, "record_hash": manifest["record_hash"]})
        for f in uploaded:
            sb.insert("documents", {"workspace_id": ws, "record_id": rec["id"], "kind": f["kind"],
                                    "storage_path": f"{prefix}/{f['path']}", "size_bytes": f["size_bytes"], "sha256": f["sha256"]})
        usd = float(cost.get("usd", 0.0))
        if usd > 0 or cost:
            sb.insert("spend", {"workspace_id": ws, "job_id": job_id, "cost_usd": usd,
                                "note": f"{cost.get('calls', 0)} calls at the configured price list, an estimate"})
        tokens_in = int(cost.get("input_tokens", 0)) + int(cost.get("cache_read_input_tokens", 0)) + int(cost.get("cache_creation_input_tokens", 0))
        sb.update("jobs", {"id": job_id}, {"state": "done", "finished_at": now_iso(), "progress_step": "done",
                                           "progress_detail": f"{len(uploaded)} files, record {manifest['record_hash'][:12]}",
                                           "tokens_in": tokens_in, "tokens_out": int(cost.get("output_tokens", 0)),
                                           "cost_usd": usd})
        sb.insert("audit_log", {"workspace_id": ws, "user_id": None, "event": "job_done",
                                "detail": {"job_id": job_id, "record_id": rec["id"], "files": len(uploaded), "cost_usd": usd}})
        res.state, res.record_id, res.documents = "done", rec["id"], len(uploaded)
        res.cost_usd, res.tokens_in, res.tokens_out = usd, tokens_in, int(cost.get("output_tokens", 0))
        say(f"done: {len(uploaded)} files, ${usd:.2f}")
        return res
    except SupabaseError as e:
        return fail(f"the workspace storage or database refused a write ({e.status}), the job can be requeued")
    except Exception as e:  # noqa: BLE001  (the reason reaches the row in words, the class reaches the private log)
        say(f"unexpected {type(e).__name__}: {str(e)[:200]}")
        return fail(f"the runner hit an unexpected {type(e).__name__}, the job can be requeued")
    finally:
        if not keep_workdir and not workdir:
            shutil.rmtree(wd, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("job_id")
    ap.add_argument("--runner", default=os.environ.get("TARK_RUNNER", "laptop"), choices=["actions", "laptop"])
    ap.add_argument("--mock", action="store_true", help="the mocked model and the synthetic filing (a rehearsal, no key)")
    ap.add_argument("--pipeline-dir", default=None)
    ap.add_argument("--keep-workdir", action="store_true")
    ap.add_argument("--budget-usd", type=float, default=None)
    ap.add_argument("--time-budget-s", type=float, default=None)
    a = ap.parse_args()
    r = run_job(a.job_id, "mock" if a.mock else None, runner=a.runner, pipeline_dir=a.pipeline_dir,
                keep_workdir=a.keep_workdir, budget_usd=a.budget_usd, time_budget_s=a.time_budget_s)
    print(f"{r.state}: {r.reason or (str(r.documents) + ' files, $' + format(r.cost_usd, '.2f'))}")
    return 0 if r.state == "done" else (2 if r.state == "skipped" else 1)


if __name__ == "__main__":
    sys.exit(main())

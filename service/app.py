"""
Tark evaluation service: one endpoint, no job state
====================================================
    uvicorn service.app:app --port 8787
    export TARK_SERVICE_URL=http://127.0.0.1:8787   # before python src/build_site.py

POST /evaluate {"cik": "1467631", "key": "acap_strategic"}
  Runs src/ingest.py synchronously for that fund and answers with what
  happened: refused (with the reason and the exact commands to run by
  hand), completed or failed (with the exit code, the last lines of output
  and the report path), or timed out. There is no queue, no job id and no
  progress state: the service never reports a state it cannot back.
Env: TARK_SERVICE_TIMEOUT (seconds, default 1800), TARK_SERVICE_ORIGINS
(comma-separated CORS origins, default *), plus everything src/ingest.py
reads (ANTHROPIC_API_KEY or an ant auth profile, TARK_INGEST_MODEL).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))
from tark_data import DATA  # noqa: E402

app = FastAPI(title="Tark evaluation service", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware,
                   allow_origins=[o.strip() for o in os.environ.get("TARK_SERVICE_ORIGINS", "*").split(",")],
                   allow_methods=["POST"], allow_headers=["content-type"])
KEY_RE = re.compile(r"[a-z0-9_]{2,32}")


class EvaluateRequest(BaseModel):
    cik: str
    key: str


def commands(cik: str, key: str) -> list[str]:
    return [f"python src/promote.py {cik} --key {key}",
            f"# write the data/registry.json entry for {key} and add it to its cohort's members list",
            f"python src/fetch_edgar.py {key}",
            f"python src/ingest.py {cik} --key {key} --skip-fetch",
            "python src/produce.py && python src/build_site.py && bash hooks/pre-commit"]


def refusal(reason: str, cik: str, key: str) -> dict:
    return {"status": "refused", "reason": reason, "commands": commands(cik, key)}


@app.post("/evaluate")
def evaluate(req: EvaluateRequest) -> dict:
    cik, key = req.cik.strip().lstrip("0") or "0", req.key.strip()
    if not cik.isdigit():
        return refusal("cik must be digits", cik, key)
    if not KEY_RE.fullmatch(key):
        return refusal("key must match [a-z0-9_]{2,32}", cik, key)
    census_path = DATA / "census" / "census.json"
    if not census_path.exists():
        return refusal("census not on disk (data/census/census.json)", cik, key)
    rec = json.loads(census_path.read_text())["entities"].get(cik)
    if rec is None:
        return refusal(f"CIK {cik} is not in the census universe, only what the census can see is evaluated", cik, key)
    if rec.get("promotion", {}).get("status") not in (None, "none"):
        return refusal(f"CIK {cik} is already evaluated as {rec['promotion'].get('product_key')}", cik, key)
    reg_path = DATA / "registry.json"
    reg = json.loads(reg_path.read_text())["products"] if reg_path.exists() else {}
    if key not in reg:
        return refusal(f"data/registry.json has no entry for {key}: the cohort, strategy and wrapper are a "
                       "person's judgments and come first", cik, key)
    cmd = [sys.executable, str(BASE / "src" / "ingest.py"), cik, "--key", key]
    timeout = int(os.environ.get("TARK_SERVICE_TIMEOUT", "1800"))
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=BASE)
    except subprocess.TimeoutExpired:
        return {"status": "timed out", "reason": f"ingest did not finish within {timeout} s",
                "commands": commands(cik, key)}
    tail = (r.stdout + r.stderr).splitlines()[-40:]
    report = DATA / "ingest" / f"{key}_report.json"
    return {"status": "completed" if r.returncode == 0 else "failed", "exit_code": r.returncode,
            "output_tail": tail, "report": str(report.relative_to(BASE)) if report.exists() else None,
            "commands": commands(cik, key)}

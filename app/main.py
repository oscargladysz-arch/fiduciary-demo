"""
The workspace API (R3-P4-4). One FastAPI application, no secrets in the
request path, every read and write forwarded to Supabase with the caller's
own token so row-level security decides (rule 22).

    uvicorn app.main:app --port 8000
    TARK_ADAPTER=api npm run build   (the same bundle, the ApiAdapter)

Routes: /api/health, /api/me, /api/plans, /api/products, /api/jobs,
/api/jobs/<id>, /api/records/<id>/<view>.json, /api/documents/<id>,
/api/reference/... Every error is one plain sentence.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from .auth import AuthError, Claims, Verifier, bearer
from .settings import Settings, load_settings, redact
from .supabase import Supabase, SupabaseError

BASE = Path(__file__).resolve().parents[1]
if str(BASE / "src") not in sys.path:
    sys.path.insert(0, str(BASE / "src"))

VIEWS = ("record", "selection", "liquidity", "cohort", "facts", "documents", "report")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
KEY_RE = re.compile(r"^[a-z0-9_]{2,32}$")
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",  # copy-exempt: a CSP header value, not prose
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",  # copy-exempt: an HSTS header value, not prose
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cache-Control": "no-store",
    "Content-Disposition": "attachment; filename=api.json",  # copy-exempt: a header value, a JSON answer is never rendered as a page
}
MAX_BODY_BYTES = 262_144        # an intake is a few kilobytes, nothing here needs more
BODY_METHODS = ("POST", "PUT", "PATCH")
HEALTH_DB_CACHE_S = 60          # the keep-alive calls this every ten minutes
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def refuse(status: int, sentence: str) -> HTTPException:
    return HTTPException(status_code=status, detail=sentence)


class PlanIn(BaseModel):
    workspace_id: str = Field(pattern=UUID_PATTERN)
    intake: dict = Field(default_factory=dict)     # the intake form fields of src/plan_intake.py
    source_note: str = Field(default="", max_length=2000)


class ProductIn(BaseModel):
    workspace_id: str = Field(pattern=UUID_PATTERN)
    cik: str = Field(default="", max_length=12)
    census_id: str = Field(default="", max_length=12)


class JobIn(BaseModel):
    product_id: str = Field(pattern=UUID_PATTERN)
    plan_id: str = Field(pattern=UUID_PATTERN)


# the intake form's field names as words, so a refusal reads as a sentence
# (rule 11) and never as a key
FIELD_LABELS = {
    "display_label": "the plan label", "anonymization_label": "the anonymization confirmation",
    "plan_year": "the plan year", "net_assets_eoy": "net assets at year end", "net_assets_boy": "net assets at year start",
    "tot_admin_expenses": "administrative expenses", "tot_expenses": "total expenses",
    "with_account_balances": "accounts with balances", "active_eoy": "active participants at year end",
    "separated_deferred_vested": "separated participants with balances", "retired_receiving": "retirees receiving benefits",
    "pension_benefit_codes": "the pension benefit codes", "plan_key": "the plan key", "pulled": "the intake date",
}


def as_sentence(text: str) -> str:
    for k in sorted(FIELD_LABELS, key=len, reverse=True):
        text = text.replace(k, FIELD_LABELS[k])
    return text


class Reference:
    """The 16 reference products and the four anonymized plans, read once
    from the public record, served read-only."""

    def __init__(self, data_dir: Path):
        self.data = data_dir
        self._census = None
        self._index = None

    def census_entity(self, cik: str) -> dict | None:
        if self._census is None:
            p = self.data / "census" / "census.json"
            self._census = json.loads(p.read_text())["entities"] if p.exists() else {}
        return self._census.get(str(int(cik))) if cik.isdigit() else None

    def index(self) -> dict:
        if self._index is None:
            reg = json.loads((self.data / "registry.json").read_text())["products"]
            products = []
            for key in sorted(reg):
                pj = self.data / "products" / f"{key}.json"
                if pj.exists():
                    d = json.loads(pj.read_text())
                    products.append({"key": key, "name": d["fund_name"], "cik": d["cik"], "wrapper": d.get("wrapper", "")})
            plans = []
            for pp in sorted((self.data / "plans").glob("*.json")):
                d = json.loads(pp.read_text())
                plans.append({"key": d["plan_key"], "label": d.get("display_label", ""), "plan_year": d.get("plan_year", "")})
            self._index = {"schema": "tark.reference.v1", "products": products, "plans": plans}
        return self._index

    def view(self, key: str, view: str, plan_key: str = "") -> dict | None:
        if not KEY_RE.match(key) or view not in VIEWS:
            return None
        if view == "record":
            p = self.data / "products" / f"{key}.json"
        elif view == "selection":
            p = self.data / "benchmarks" / f"{key}_selection.json"
        elif view == "facts":
            p = self.data / "facts" / f"{key}.json"
        elif view == "liquidity":
            if not KEY_RE.match(plan_key or ""):
                return None
            p = self.data / "liquidity" / f"{plan_key}__{key}_match.json"
        elif view == "cohort":
            reg = json.loads((self.data / "registry.json").read_text())
            cid = (reg["products"].get(key) or {}).get("cohort", "")
            p = self.data / "cohorts" / f"{cid}.json"
        else:
            return None
        if not p.exists():
            return None
        return json.loads(p.read_text())


def create_app(settings: Settings | None = None, *, verifier: Verifier | None = None,
               transport: httpx.BaseTransport | None = None, github_transport: httpx.BaseTransport | None = None,
               reference: Reference | None = None) -> FastAPI:
    s = settings or load_settings()
    app = FastAPI(title="Tark workspace", docs_url=None, redoc_url=None, openapi_url=None)
    ver = verifier or Verifier(s.supabase_url, s.supabase_jwt_secret, transport=transport)
    ref = reference or Reference(Path(s.reference_dir) if s.reference_dir else BASE / "data")
    app.state.settings = s
    app.state.log = []                      # the last lines, every one redacted
    app.state.health_db = None              # (when, answer) for the unauthenticated database check
    if s.app_origin:
        app.add_middleware(CORSMiddleware, allow_origins=[s.app_origin], allow_methods=["GET", "POST"],
                           allow_headers=["authorization", "content-type"], max_age=600)

    def log(line: str) -> None:
        app.state.log.append(redact(line))
        del app.state.log[:-200]

    def too_large() -> JSONResponse:
        return JSONResponse({"detail": "the request body is larger than anything this workspace accepts"},
                            status_code=413, headers=SECURITY_HEADERS)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            return too_large()
        if request.method in BODY_METHODS and not (length and length.isdigit()):
            # a body that declares no length cannot be measured before it is
            # read, so this API does not take one. Every client of it sends a
            # JSON object, which declares its length.
            return JSONResponse({"detail": "the request must declare the length of its body"},
                                status_code=411, headers=SECURITY_HEADERS)
        try:
            response = await call_next(request)
        except Exception as e:  # noqa: BLE001  (never a stack trace to a client, never a secret in the log)
            log(f"{request.method} {request.url.path} failed: {type(e).__name__}")
            response = JSONResponse({"detail": "the request could not be completed, the failure is logged by its kind"},
                                    status_code=500)
        for k, v in SECURITY_HEADERS.items():
            response.headers[k] = v
        return response

    @app.exception_handler(RequestValidationError)
    async def body_error(request: Request, e: RequestValidationError):
        log(f"{request.method} {request.url.path} malformed body")
        return JSONResponse({"detail": "the request is missing a field or carries a value of the wrong shape"},
                            status_code=422, headers=SECURITY_HEADERS)

    @app.exception_handler(SupabaseError)
    async def supabase_error(request: Request, e: SupabaseError):
        log(f"{request.method} {request.url.path} supabase {e.status}")
        if e.status in (401, 403):
            return JSONResponse({"detail": "the workspace refused the request, sign in to a workspace you belong to"},
                                status_code=403, headers=SECURITY_HEADERS)
        if e.status == 409:
            sentence = ("a job for this product and plan is already queued or running" if "jobs_one_active" in e.message
                        else "that fund is already in this workspace" if "products" in e.message
                        else "the workspace already holds that row")
            return JSONResponse({"detail": sentence}, status_code=409, headers=SECURITY_HEADERS)
        return JSONResponse({"detail": "the workspace could not complete the request, try again in a moment"},
                            status_code=502, headers=SECURITY_HEADERS)

    def claims(authorization: str | None = Header(default=None)) -> Claims:
        try:
            return ver.verify(bearer(authorization))
        except AuthError as e:
            raise refuse(401, str(e)) from None

    def db(c: Claims) -> Supabase:
        return Supabase(s.supabase_url, s.supabase_anon_key, token=c.token, transport=transport)

    def audit(sb: Supabase, c: Claims, workspace_id: str | None, event: str, detail: dict | None = None) -> None:
        try:
            sb.insert("audit_log", {"workspace_id": workspace_id, "user_id": c.user_id, "event": event,
                                    "detail": detail or {}})
        except SupabaseError as e:  # an audit failure is logged, it never hides the user's result
            log(f"audit {event} failed {e.status}")

    def one(sb: Supabase, table: str, row_id: str, what: str) -> dict:
        if not UUID_RE.fullmatch(row_id or ""):
            raise refuse(404, f"no {what} with that id is in your workspace")
        rows = sb.select(table, filters={"id": row_id})
        if not rows:
            raise refuse(404, f"no {what} with that id is in your workspace")
        return rows[0]

    # ------------------------------------------------------------ health
    @app.get("/api/health")
    def health(db_check: str = ""):
        out = {"status": "ok", "time": now_iso(), "pipeline_commit": s.pipeline_commit[:12]}
        if db_check and s.ready:
            # the answer is cached for a minute: this route takes no token, so
            # it must not turn one request into one database query
            cached = app.state.health_db
            if cached and time.monotonic() - cached[0] < HEALTH_DB_CACHE_S:
                out["database"] = cached[1]
                return out
            try:
                Supabase(s.supabase_url, s.supabase_anon_key, transport=transport).rpc("ping")
                out["database"] = "ok"
            except (SupabaseError, httpx.HTTPError):
                out["database"] = "unreachable"
            app.state.health_db = (time.monotonic(), out["database"])
        return out

    # ---------------------------------------------------------------- me
    @app.get("/api/me")
    def me(c: Claims = Depends(claims)):
        sb = db(c)
        members = sb.select("workspace_members", filters={"user_id": c.user_id})
        ws_ids = [m["workspace_id"] for m in members]
        workspaces = sb.select("workspaces", filters={"id": "in.(" + ",".join(ws_ids) + ")"}) if ws_ids else []
        audit(sb, c, ws_ids[0] if ws_ids else None, "login")
        return {"user_id": c.user_id, "email": c.email, "workspaces": workspaces,
                "human_verification": "pending"}

    # -------------------------------------------------------------- plans
    @app.get("/api/plans")
    def plans(c: Claims = Depends(claims)):
        return {"plans": db(c).select("plans", order="created_at.desc")}

    @app.post("/api/plans", status_code=201)
    def create_plan(body: PlanIn, c: Claims = Depends(claims)):
        import plan_intake  # the same validator the command line runs, so the workspace refuses what the record cannot hold
        try:
            plan = plan_intake.scaffold(dict(body.intake))
        except SystemExit as e:
            raise refuse(422, as_sentence(getattr(e, "message", "") or "the intake could not be scaffolded")) from None
        if not plan["plan_key"].startswith("ws_"):
            plan["plan_key"] = "ws_" + plan["plan_key"][:28]
        sb = db(c)
        row = sb.insert("plans", {"workspace_id": body.workspace_id, "intake": plan, "source_note": body.source_note})
        audit(sb, c, body.workspace_id, "plan_created", {"plan_id": row.get("id")})
        return row

    # ----------------------------------------------------------- products
    @app.get("/api/products")
    def products(c: Claims = Depends(claims)):
        return {"products": db(c).select("products", order="created_at.desc")}

    @app.post("/api/products", status_code=201)
    def create_product(body: ProductIn, c: Claims = Depends(claims)):
        cik = (body.cik or body.census_id or "").strip().lstrip("0") or ""
        if not re.fullmatch(r"[0-9]{1,10}", cik):
            raise refuse(422, "a fund is submitted by its CIK, the number the SEC assigns to the registrant")
        ent = ref.census_entity(cik)
        if ent is None:
            raise refuse(422, "that CIK is not in the census of registered funds, only what the census can see is evaluated")
        promoted = (ent.get("promotion") or {}).get("product_key")
        if promoted:
            raise refuse(409, f"that fund is one of the reference products, open it under the references as {promoted}")
        name = (ent.get("entity_name_current") or {}).get("value") or ent.get("name") or ""
        sb = db(c)
        row = sb.insert("products", {"workspace_id": body.workspace_id, "cik": cik, "name": name,
                                     "wrapper": ent.get("wrapper_class", ""), "product_key": f"cik_{cik}"})
        audit(sb, c, body.workspace_id, "product_created", {"product_id": row.get("id"), "cik": cik})
        return row

    # --------------------------------------------------------------- jobs
    @app.get("/api/jobs")
    def jobs(c: Claims = Depends(claims)):
        return {"jobs": db(c).select("jobs", order="created_at.desc")}

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str, c: Claims = Depends(claims)):
        return one(db(c), "jobs", job_id, "job")

    @app.post("/api/jobs", status_code=201)
    def create_job(body: JobIn, c: Claims = Depends(claims)):
        sb = db(c)
        product = one(sb, "products", body.product_id, "product")
        plan = one(sb, "plans", body.plan_id, "plan")
        if plan["workspace_id"] != product["workspace_id"]:
            raise refuse(422, "the plan and the product belong to different workspaces")
        row = sb.insert("jobs", {"workspace_id": product["workspace_id"], "product_id": product["id"],
                                 "plan_id": plan["id"], "state": "queued", "progress_step": "queued",
                                 "pipeline_commit": s.pipeline_commit})
        audit(sb, c, product["workspace_id"], "job_created", {"job_id": row.get("id")})
        dispatched, note = dispatch(row.get("id", ""))
        row["dispatched"] = dispatched
        row["dispatch_note"] = note
        return row

    def dispatch(job_id: str) -> tuple[bool, str]:
        """Wake the worker in the private repository (R3-P4-4). The token
        can only dispatch that workflow. A failure leaves the job queued
        for the laptop runner and says so."""
        if not (s.dispatch_repo and s.dispatch_token):
            return False, "no worker is connected, the job waits for a runner"
        try:
            with httpx.Client(base_url="https://api.github.com", transport=github_transport, timeout=15.0) as gh:
                r = gh.post(f"/repos/{s.dispatch_repo}/dispatches",
                            headers={"Authorization": f"Bearer {s.dispatch_token}",
                                     "Accept": "application/vnd.github+json"},
                            json={"event_type": s.dispatch_event,
                                  "client_payload": {"job_id": job_id, "pipeline_commit": s.pipeline_commit}})
            if r.status_code in (204, 200):
                return True, "the worker was asked to start"
            log(f"dispatch {job_id} refused {r.status_code}")
            return False, "the worker could not be started, the job waits for a runner"
        except httpx.HTTPError as e:
            log(f"dispatch {job_id} failed {type(e).__name__}")
            return False, "the worker could not be reached, the job waits for a runner"

    # ------------------------------------------------------------ records
    @app.get("/api/records/{record_id}/{view}.json")
    def record_view(record_id: str, view: str, c: Claims = Depends(claims)):
        if view not in VIEWS:
            raise refuse(404, "that view does not exist, the views are record, selection, liquidity, cohort, facts, documents and report")
        sb = db(c)
        rec = one(sb, "records", record_id, "record")
        try:
            data = sb.download("workspace", f"{rec['artifacts_prefix']}/views/{view}.json")
        except SupabaseError as e:
            if e.status == 404:
                raise refuse(404, "that view was not written for this record") from None
            raise
        return Response(content=data, media_type="application/json")

    # ---------------------------------------------------------- documents
    @app.get("/api/documents/{document_id}")
    def document(document_id: str, redirect: str = "", c: Claims = Depends(claims)):
        sb = db(c)
        doc = one(sb, "documents", document_id, "document")
        filename = doc["storage_path"].rsplit("/", 1)[-1]
        url = sb.signed_url("workspace", doc["storage_path"], s.signed_url_seconds, download_name=filename)
        audit(sb, c, doc["workspace_id"], "download", {"document_id": doc["id"], "kind": doc["kind"]})
        if redirect:
            return RedirectResponse(url, status_code=302)
        return {"url": url, "expires_in": s.signed_url_seconds, "filename": filename, "kind": doc["kind"],
                "sha256": doc["sha256"], "size_bytes": doc["size_bytes"]}

    # ---------------------------------------------------------- reference
    @app.get("/api/reference/index.json")
    def reference_index(c: Claims = Depends(claims)):
        return ref.index()

    @app.get("/api/reference/{key}/{view}.json")
    def reference_view(key: str, view: str, plan: str = "", c: Claims = Depends(claims)):
        data = ref.view(key, view, plan)
        if data is None:
            raise refuse(404, "that reference view does not exist")
        return data

    return app


app = create_app()

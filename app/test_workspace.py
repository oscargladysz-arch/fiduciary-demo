"""
Workspace API gate (R3-P4-4, offline)
======================================
Drives app/main.py through Starlette's TestClient against the fake
Supabase in app/testing.py: no network, no key, no real project. Asserts
what rule 22 and R3-P4-4 promise: every route but health rejects a missing,
malformed, expired or foreign token, a member sees only their workspace's
rows and objects, a plan is validated by the same intake code as the
command line, a product comes from the census, a job is one per product
and plan pair and wakes the worker through repository_dispatch with a
plain note when it cannot, a record's views and a document's signed URL
come through storage under the user's token, the references are read-only,
every response carries the security headers, CORS is one origin, every
error is a plain sentence the copy layer allows, and no log line or
response carries a secret.

Run: python app/test_workspace.py   (exit 0 = all pass)
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "src"))

import httpx  # noqa: E402
import jwt  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from app.auth import AuthError, Verifier  # noqa: E402
from app.main import Reference, SECURITY_HEADERS, VIEWS, create_app  # noqa: E402
from app.settings import Settings, redact  # noqa: E402
from app.supabase import Supabase, SupabaseError  # noqa: E402
from app.admin import delete_workspace, requeue  # noqa: E402
from app.settings import load_settings  # noqa: E402
from app.testing import ISSUER, FakeSupabase, make_token  # noqa: E402
from tark_display import prose_hits  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" : {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


SECRET = "test-jwt-secret-" + uuid.uuid4().hex
DISPATCH_TOKEN = "github_pat_test_" + uuid.uuid4().hex
fake = FakeSupabase()
alice = fake.seed_user("alice@example.test")
bob = fake.seed_user("bob@example.test")
ws_a = fake.seed_workspace("Workspace A", alice)
ws_b = fake.seed_workspace("Workspace B", bob)
tok_a = make_token(SECRET, alice, "alice@example.test")
tok_b = make_token(SECRET, bob, "bob@example.test")
dispatches = []


def github(request: httpx.Request) -> httpx.Response:
    dispatches.append((request.url.path, request.headers.get("authorization", ""), json.loads(request.content)))
    return httpx.Response(204)


settings = Settings(supabase_url="https://project.supabase.test", supabase_anon_key=fake.anon_key,
                    supabase_jwt_secret=SECRET, app_origin="https://tark-app.example.test",
                    dispatch_repo="owner/tark-workspace", dispatch_token=DISPATCH_TOKEN,
                    pipeline_commit="abc1234def5678", signed_url_seconds=120, reference_dir=str(BASE / "data"))
app = create_app(settings, transport=fake.transport, github_transport=httpx.MockTransport(github),
                 reference=Reference(BASE / "data"))
tc = TestClient(app, raise_server_exceptions=False)


def hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except SystemExit:
        return True


# ---------------- health and headers
r = tc.get("/api/health")
check("health: answers without a token, names the pipeline commit and no secret",
      r.status_code == 200 and r.json()["status"] == "ok" and r.json()["pipeline_commit"] == "abc1234def56"
      and SECRET not in r.text and DISPATCH_TOKEN not in r.text)
r2 = tc.get("/api/health?db_check=1")
check("health: the database check runs the ping function with the anon key only",
      r2.json().get("database") == "ok" and ("POST", "/rest/v1/rpc/ping") in fake.requests)
_pings = fake.requests.count(("POST", "/rest/v1/rpc/ping"))
for _ in range(5):
    tc.get("/api/health?db_check=1")
check("health: the unauthenticated database check answers from a short cache, so a flood of calls is not a flood of queries",
      fake.requests.count(("POST", "/rest/v1/rpc/ping")) == _pings
      and tc.get("/api/health?db_check=1").json()["database"] == "ok")
check("headers: every response carries the security headers and no-store",
      all(r.headers.get(k) == v for k, v in SECURITY_HEADERS.items()))
routes = sorted({rt.path for rt in app.routes if getattr(rt, "methods", None)})
check("routes: exactly the R3-P4-4 surface, no docs pages",
      routes == sorted(["/api/health", "/api/me", "/api/plans", "/api/products", "/api/jobs", "/api/jobs/{job_id}",
                        "/api/records/{record_id}/{view}.json", "/api/documents/{document_id}",
                        "/api/reference/index.json", "/api/reference/{key}/{view}.json"])
      and app.docs_url is None and app.openapi_url is None, str(routes))

# ---------------- tokens: missing, malformed, expired, wrong secret, wrong audience
protected = [("GET", "/api/me"), ("GET", "/api/plans"), ("POST", "/api/plans"), ("GET", "/api/products"),
             ("POST", "/api/products"), ("GET", "/api/jobs"), ("POST", "/api/jobs"), ("GET", f"/api/jobs/{uuid.uuid4()}"),
             ("GET", f"/api/records/{uuid.uuid4()}/record.json"), ("GET", f"/api/documents/{uuid.uuid4()}"),
             ("GET", "/api/reference/index.json"), ("GET", "/api/reference/hl_paf/record.json")]
bad_tokens = {"missing": None, "malformed": "not.a.jwt.at.all", "expired": make_token(SECRET, alice, ttl_s=-10),
              "wrong secret": make_token("another-secret-" + uuid.uuid4().hex, alice),
              "wrong audience": jwt.encode({"sub": alice, "aud": "anon", "exp": int(time.time()) + 60, "iss": ISSUER}, SECRET, algorithm="HS256"),
              "wrong issuer": make_token(SECRET, alice, issuer="https://another-project.supabase.test/auth/v1"),
              "no expiry": jwt.encode({"sub": alice, "aud": "authenticated", "iss": ISSUER}, SECRET, algorithm="HS256")}
_bad = []
for method, path in protected:
    for kind, tok in bad_tokens.items():
        h = hdr(tok) if tok else {}
        rr = tc.request(method, path, headers=h, json={} if method == "POST" else None)
        if rr.status_code != 401 or "detail" not in rr.json():
            _bad.append(f"{method} {path} {kind}: {rr.status_code}")
check("tokens: every protected route answers 401 with a sentence to a missing, malformed, expired, foreign, misaudienced, misissued or unexpiring token",
      not _bad, "; ".join(_bad[:3]))  # copy-exempt: a joiner in a console detail
check("tokens: an expired token is named as expired, never echoed",
      "expired" in tc.get("/api/me", headers=hdr(bad_tokens["expired"])).json()["detail"]
      and bad_tokens["expired"] not in tc.get("/api/me", headers=hdr(bad_tokens["expired"])).text)

# JWKS path: an ES256 token verified by kid, a rotated key refetched
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
priv = ec.generate_private_key(ec.SECP256R1())
jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(priv.public_key()))
jwk.update({"kid": "key-1", "alg": "ES256", "use": "sig"})
fake.jwks = {"keys": [jwk]}
ver = Verifier("https://project.supabase.test", "", transport=fake.transport, refresh_window_s=0)
es_tok = make_token("", alice, "alice@example.test", alg="ES256", key=priv, kid="key-1")
c = ver.verify(es_tok)
check("jwks: an ES256 token signed by a published key verifies by kid, the claims carry the user",
      c.user_id == alice and c.email == "alice@example.test" and not c.expired)
priv2 = ec.generate_private_key(ec.SECP256R1())
try:
    ver.verify(make_token("", alice, alg="ES256", key=priv2, kid="key-2"))
    rotated = False
except AuthError as e:
    rotated = "signing key" in str(e) and fake.requests.count(("GET", "/auth/v1/.well-known/jwks.json")) >= 2
check("jwks: with the window open, an unknown kid refetches the key set once and is refused when it is still unknown",
      rotated)
_ver_window = Verifier("https://project.supabase.test", "", transport=fake.transport)
_ver_window.verify(es_tok)          # one fetch, the key set is now cached
_n_before = fake.requests.count(("GET", "/auth/v1/.well-known/jwks.json"))
for _k in ("key-3", "key-4", "key-5"):
    try:
        _ver_window.verify(make_token("", alice, alg="ES256", key=priv2, kid=_k))
    except AuthError:
        pass
check("jwks: a run of unknown kids inside the refresh window fetches the key set no more than once",
      fake.requests.count(("GET", "/auth/v1/.well-known/jwks.json")) - _n_before <= 1,
      str(fake.requests.count(("GET", "/auth/v1/.well-known/jwks.json")) - _n_before))
# a project that publishes no keys (it signs with a secret): a sender whose
# token merely claims an asymmetric algorithm must not cost one fetch each
_empty = FakeSupabase(jwks={"keys": []})
_ver2 = Verifier("https://project.supabase.test", "", transport=_empty.transport)
for _ in range(6):
    try:
        _ver2.verify(make_token("", alice, alg="ES256", key=priv, kid="key-1"))
    except AuthError:
        pass
check("jwks: on a project that publishes no keys, a run of asymmetric tokens still costs at most one fetch",
      _empty.requests.count(("GET", "/auth/v1/.well-known/jwks.json")) == 1,
      str(_empty.requests.count(("GET", "/auth/v1/.well-known/jwks.json"))))
try:
    Verifier("https://project.supabase.test", "", transport=fake.transport).verify(tok_a)
    hs_without = False
except AuthError as e:
    hs_without = "secret" in str(e)
check("hs256: without the project secret an HS256 token is refused, never trusted", hs_without)

# ---------------- me, audit login
r = tc.get("/api/me", headers=hdr(tok_a))
check("me: the user's workspaces only, human verification pending, a login audit row under the user's token",
      r.status_code == 200 and [w["id"] for w in r.json()["workspaces"]] == [ws_a]
      and r.json()["human_verification"] == "pending"
      and any(a["event"] == "login" and a["user_id"] == alice and a["workspace_id"] == ws_a for a in fake.tables["audit_log"]))

check("headers: every JSON answer is marked as an attachment, so no browser renders it as a page",
      r.headers.get("content-disposition", "").startswith("attachment"))
check("settings: a Supabase URL or an app origin that is not https is refused at load",
      (lambda: (_raises(lambda: load_settings({"SUPABASE_URL": "http://x", "SUPABASE_ANON_KEY": "k"}))
                and _raises(lambda: load_settings({"SUPABASE_URL": "https://x", "SUPABASE_ANON_KEY": "k", "TARK_APP_ORIGIN": "http://y"}))
                and load_settings({"SUPABASE_URL": "https://x", "SUPABASE_ANON_KEY": "k", "TARK_SIGNED_URL_SECONDS": "99999"}).signed_url_seconds == 3600))())

# ---------------- plans through the intake validator
INTAKE = {"display_label": "US regional clinic 403(b) plan (~$400M, OH)",
          "anonymization_label": "US regional clinic 403(b) plan (~$400M, OH)",
          "plan_year": "2024-01-01 to 2024-12-31", "net_assets_eoy": 400_000_000, "net_assets_boy": 360_000_000,
          "tot_admin_expenses": 800_000, "with_account_balances": 5000, "active_eoy": 4200,
          "separated_deferred_vested": 700, "retired_receiving": 30, "pension_benefit_codes": "2E2G2J2K",
          "pulled": "2026-09-08"}
r = tc.post("/api/plans", headers=hdr(tok_a), json={"workspace_id": ws_a, "intake": INTAKE, "source_note": "intake by the adviser"})
plan_a = r.json()
check("plans: a valid intake is scaffolded by the same code as the command line, stored under a workspace key, audited",
      r.status_code == 201 and plan_a["workspace_id"] == ws_a and plan_a["intake"]["plan_key"].startswith("ws_")
      and plan_a["intake"]["display_label"] == INTAKE["display_label"]
      and "identity_private" not in plan_a["intake"]
      and any(a["event"] == "plan_created" for a in fake.tables["audit_log"]), r.text[:200])
r = tc.post("/api/plans", headers=hdr(tok_a), json={"workspace_id": ws_a, "intake": {**INTAKE, "display_label": "Acme Corp LLC 401(k)",
                                                                                      "anonymization_label": "Acme Corp LLC 401(k)"}})
check("plans: a label that looks like a sponsor name is refused with the intake's own sentence",
      r.status_code == 422 and "sponsor" in r.json()["detail"], r.text[:200])
r = tc.post("/api/plans", headers=hdr(tok_a), json={"workspace_id": ws_b, "intake": INTAKE})
check("plans: a member of A cannot write a plan into B, the policy refuses and the API says so in one sentence",
      r.status_code == 403 and r.json()["detail"].endswith("you belong to"), r.text[:200])
r = tc.post("/api/plans", headers=hdr(tok_a), json={"workspace_id": "not-a-uuid", "intake": INTAKE})
r_big = tc.post("/api/plans", headers={**hdr(tok_a), "Content-Length": "300001"}, content=b"{}")
check("bodies: a malformed body is refused in one sentence and a body over the cap is refused before it is read",
      r.status_code == 422 and r.json()["detail"].startswith("the request is missing") and r_big.status_code == 413
      and "larger" in r_big.json()["detail"], f"{r.status_code} {r_big.status_code}")
# a body that declares no length cannot be measured before it is read: httpx
# sends an iterator chunked, and this API refuses that rather than read it
r_chunk = tc.post("/api/plans", headers=hdr(tok_a), content=iter([b"x" * 70_000 for _ in range(5)]))
r_chunk_small = tc.post("/api/plans", headers=hdr(tok_a),
                        content=iter([json.dumps({"workspace_id": ws_a, "intake": INTAKE}).encode()]))
check("bodies: a body that declares no length is refused whatever its size, and a declared body under the cap is served",
      r_chunk.status_code == 411 and r_chunk_small.status_code == 411
      and "declare the length" in r_chunk.json()["detail"]
      and tc.get("/api/plans", headers=hdr(tok_a)).status_code == 200,
      f"{r_chunk.status_code} {r_chunk_small.status_code}")
check("plans: listing under A's token shows A's plan and none of B's",
      [p["id"] for p in tc.get("/api/plans", headers=hdr(tok_a)).json()["plans"]] == [plan_a["id"]]
      and tc.get("/api/plans", headers=hdr(tok_b)).json()["plans"] == [])

# ---------------- products from the census
r = tc.post("/api/products", headers=hdr(tok_a), json={"workspace_id": ws_a, "cik": "0001467631"})
prod_a = r.json()
check("products: a census CIK becomes a product with the census name and wrapper and a derived key",
      r.status_code == 201 and prod_a["cik"] == "1467631" and prod_a["name"] == "ACAP Strategic Fund"
      and prod_a["wrapper"] == "interval_23c3" and prod_a["product_key"] == "cik_1467631", r.text[:200])
r = tc.post("/api/products", headers=hdr(tok_a), json={"workspace_id": ws_a, "cik": "12"})
check("products: a CIK outside the census is refused with the reason", r.status_code == 422 and "census" in r.json()["detail"])
r = tc.post("/api/products", headers=hdr(tok_a), json={"workspace_id": ws_a, "cik": "1735964"})
check("products: a reference product is refused by its key and pointed at the references",
      r.status_code == 409 and "cliffwater_cclfx" in r.json()["detail"])
r = tc.post("/api/products", headers=hdr(tok_a), json={"workspace_id": ws_a, "cik": "x"})
check("products: a non-numeric submission is refused in one sentence", r.status_code == 422 and "CIK" in r.json()["detail"])
r = tc.post("/api/products", headers=hdr(tok_a), json={"workspace_id": ws_a, "cik": "0001467631"})
check("products: the same fund twice in one workspace is refused with its own sentence, not the job sentence",
      r.status_code == 409 and "already in this workspace" in r.json()["detail"], r.text[:200])

# ---------------- jobs: one per pair, dispatched, foreign rows invisible
r = tc.post("/api/jobs", headers=hdr(tok_a), json={"product_id": prod_a["id"], "plan_id": plan_a["id"]})
job_a = r.json()
check("jobs: a job is created queued with the pinned pipeline commit and the worker is dispatched with only the job id and the commit",
      r.status_code == 201 and job_a["state"] == "queued" and job_a["pipeline_commit"] == "abc1234def5678"
      and job_a["dispatched"] is True and len(dispatches) == 1
      and dispatches[0][0] == "/repos/owner/tark-workspace/dispatches"
      and dispatches[0][2] == {"event_type": "run_job", "client_payload": {"job_id": job_a["id"], "pipeline_commit": "abc1234def5678"}}
      and dispatches[0][1] == f"Bearer {DISPATCH_TOKEN}", r.text[:300])
r = tc.post("/api/jobs", headers=hdr(tok_a), json={"product_id": prod_a["id"], "plan_id": plan_a["id"]})
check("jobs: a second job for the same product and plan while one is queued is refused in one sentence",
      r.status_code == 409 and "already queued or running" in r.json()["detail"])
r = tc.post("/api/jobs", headers=hdr(tok_b), json={"product_id": prod_a["id"], "plan_id": plan_a["id"]})
check("jobs: B cannot create a job on A's product, the product is not in B's workspace",
      r.status_code == 404 and "workspace" in r.json()["detail"])
check("jobs: A reads the job, B receives not found for the same id, nobody sees a queue or progress it cannot back",
      tc.get(f"/api/jobs/{job_a['id']}", headers=hdr(tok_a)).json()["id"] == job_a["id"]
      and tc.get(f"/api/jobs/{job_a['id']}", headers=hdr(tok_b)).status_code == 404
      and tc.get("/api/jobs", headers=hdr(tok_b)).json()["jobs"] == [])
check("jobs: a malformed id is not found, never an error",
      tc.get("/api/jobs/not-an-id", headers=hdr(tok_a)).status_code == 404)
# the direct PostgREST path, the one the policies alone must hold (ASVS 4.1.2)
_plan_b = fake.tables["plans"].append({"id": str(uuid.uuid4()), "workspace_id": ws_b, "intake": {"plan_key": "ws_b"}, "source_note": "",
                                       "created_at": "2026-09-08T00:00:00+00:00"}) or fake.tables["plans"][-1]
_as_a = Supabase("https://project.supabase.test", fake.anon_key, token=tok_a, transport=fake.transport)
try:
    _as_a.insert("jobs", {"workspace_id": ws_a, "product_id": prod_a["id"], "plan_id": _plan_b["id"], "state": "queued",
                          "progress_step": "queued"})
    _direct = False
except SupabaseError as e:
    _direct = e.status == 401
try:
    _as_a.insert("jobs", {"workspace_id": ws_a, "product_id": prod_a["id"], "plan_id": plan_a["id"], "state": "queued",
                          "progress_step": "queued", "attempts": 3})
    _pinned = False
except SupabaseError as e:
    _pinned = e.status == 401
try:
    _as_a.insert("audit_log", {"workspace_id": ws_a, "user_id": alice, "event": "job_done", "detail": {}})
    _forged = False
except SupabaseError as e:
    _forged = e.status == 401
check("policies: through the database directly, a member cannot queue a job on another workspace's plan, cannot set the worker's columns, "
      "and cannot write a worker event into the audit trail", _direct and _pinned and _forged)

# dispatch failure leaves the job queued with a plain note
def github_down(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("no route")


app2 = create_app(settings, transport=fake.transport, github_transport=httpx.MockTransport(github_down),
                  reference=Reference(BASE / "data"))
tc2 = TestClient(app2, raise_server_exceptions=False)
r = tc2.post("/api/plans", headers=hdr(tok_a), json={"workspace_id": ws_a, "intake": {**INTAKE, "display_label": "US regional clinic 403(b) plan (~$410M, OH)",
                                                                                       "anonymization_label": "US regional clinic 403(b) plan (~$410M, OH)"}})
plan_a2 = r.json()
r = tc2.post("/api/jobs", headers=hdr(tok_a), json={"product_id": prod_a["id"], "plan_id": plan_a2["id"]})
check("jobs: when the worker cannot be reached the job stays queued for a runner and the answer says so",
      r.status_code == 201 and r.json()["dispatched"] is False and "waits for a runner" in r.json()["dispatch_note"]
      and DISPATCH_TOKEN not in json.dumps(app2.state.log) and any("dispatch" in ln for ln in app2.state.log), r.text[:200])

# ---------------- records and documents through storage under the user's token
prefix = f"{ws_a}/{job_a['id']}"
fake.objects[f"workspace/{prefix}/views/record.json"] = json.dumps({"schema": "tark.record.v1", "product_key": "cik_1467631"}).encode()
fake.objects[f"workspace/{prefix}/documents/record.docx"] = b"PK\x03\x04 synthetic bytes"
rec = {"id": str(uuid.uuid4()), "workspace_id": ws_a, "product_id": prod_a["id"], "plan_id": plan_a["id"], "job_id": job_a["id"],
       "version": 1, "artifacts_prefix": prefix, "record_hash": "0" * 64, "created_at": "2026-09-08T00:00:00+00:00"}
fake.tables["records"].append(rec)
doc = {"id": str(uuid.uuid4()), "workspace_id": ws_a, "record_id": rec["id"], "kind": "selection_record",
       "storage_path": f"{prefix}/documents/record.docx", "size_bytes": 22, "sha256": "1" * 64, "created_at": "2026-09-08T00:00:00+00:00"}
fake.tables["documents"].append(doc)
r = tc.get(f"/api/records/{rec['id']}/record.json", headers=hdr(tok_a))
check("records: a view is read from storage under the user's token and served as JSON",
      r.status_code == 200 and r.json()["product_key"] == "cik_1467631")
check("records: a view that was not written and a view that does not exist are each not found in one sentence",
      tc.get(f"/api/records/{rec['id']}/facts.json", headers=hdr(tok_a)).status_code == 404
      and "views are" in tc.get(f"/api/records/{rec['id']}/nope.json", headers=hdr(tok_a)).json()["detail"])
check("records: B cannot read A's record by id",
      tc.get(f"/api/records/{rec['id']}/record.json", headers=hdr(tok_b)).status_code == 404)
check("ids: an id with a trailing newline is not the id it trails, on every id-addressed route",
      tc.get(f"/api/records/{rec['id']}%0A/record.json", headers=hdr(tok_a)).status_code == 404
      and tc.get(f"/api/documents/{doc['id']}%0A", headers=hdr(tok_a)).status_code == 404
      and tc.get(f"/api/jobs/{job_a['id']}%0A", headers=hdr(tok_a)).status_code == 404)
r = tc.get(f"/api/documents/{doc['id']}", headers=hdr(tok_a))
check("documents: a signed URL with the expiry and the filename, audited as a download, never the service key",
      r.status_code == 200 and r.json()["expires_in"] == 120 and r.json()["filename"] == "record.docx"
      and "token=fake-signature" in r.json()["url"] and r.json()["url"].startswith("https://project.supabase.test/storage/v1/")
      and any(a["event"] == "download" and a["detail"]["document_id"] == doc["id"] for a in fake.tables["audit_log"])
      and fake.service_key not in r.text, r.text[:200])
r = tc.get(f"/api/documents/{doc['id']}?redirect=1", headers=hdr(tok_a), follow_redirects=False)
check("documents: the redirect form sends the browser to the signed URL", r.status_code == 302 and "fake-signature" in r.headers["location"])
check("documents: B cannot sign A's document", tc.get(f"/api/documents/{doc['id']}", headers=hdr(tok_b)).status_code == 404)
# the admin's removal path and the requeue guard (ASVS 8.3.2, the review's observation on requeue)
_admin = Supabase("https://project.supabase.test", fake.service_key, transport=fake.transport)
_job_running = {**job_a, "id": str(uuid.uuid4()), "state": "running", "plan_id": plan_a["id"], "product_id": prod_a["id"]}
fake.tables["jobs"].append(_job_running)
_req_failed = _raises(lambda: requeue(_admin, _job_running["id"]))
_req_ok = requeue(_admin, _job_running["id"], include_running=True)["state"] == "queued"
_ws_c = fake.seed_workspace("Workspace C", bob)
fake.objects[f"workspace/{_ws_c}/x/views/record.json"] = b"{}"
fake.tables["plans"].append({"id": str(uuid.uuid4()), "workspace_id": _ws_c, "intake": {}, "source_note": "", "created_at": "2026-09-08T00:00:00+00:00"})
_res = delete_workspace(_admin, "Workspace C")
_ws_d = fake.seed_workspace("Workspace D", bob)
for _i in range(1500):
    fake.objects[f"workspace/{_ws_d}/artifacts/{_i:05d}.json"] = b"{}"
fake.tables["plans"].append({"id": str(uuid.uuid4()), "workspace_id": _ws_d, "intake": {}, "source_note": "",
                             "created_at": "2026-09-08T00:00:00+00:00"})
_res_d = delete_workspace(_admin_for_paging := Supabase("https://project.supabase.test", fake.service_key, transport=fake.transport),
                          "Workspace D")
check("admin: delete-workspace pages the listing, so a workspace with more objects than one page keeps none of them",
      _res_d["objects_removed"] == 1500 and not any(k.startswith(f"workspace/{_ws_d}/") for k in fake.objects)
      and not any(p["workspace_id"] == _ws_d for p in fake.tables["plans"]), str(_res_d))
check("admin: a running job is requeued only with the flag, and delete-workspace removes the storage prefix and every row of the workspace and nothing else",
      _req_failed and _req_ok and _res["objects_removed"] == 1 and _res["rows_removed"] == 1
      and not any(k.startswith(f"workspace/{_ws_c}/") for k in fake.objects)
      and not any(p["workspace_id"] == _ws_c for p in fake.tables["plans"])
      and any(p["workspace_id"] == ws_a for p in fake.tables["plans"])
      and f"workspace/{prefix}/views/record.json" in fake.objects, str(_res))

# ---------------- references, read-only, the public record
r = tc.get("/api/reference/index.json", headers=hdr(tok_a))
check("reference: the index lists the 16 products and the four anonymized plans with no sponsor identity",
      r.status_code == 200 and len(r.json()["products"]) == 16 and len(r.json()["plans"]) == 4
      and "identity_private" not in r.text and all(KEY in ("plans", "products", "schema") for KEY in r.json()))
r = tc.get("/api/reference/hl_paf/record.json", headers=hdr(tok_a))
r_liq = tc.get("/api/reference/hl_paf/liquidity.json?plan=plan_tech_media", headers=hdr(tok_a))
check("reference: a product's record, selection, liquidity for a plan and cohort read from the record files",
      r.status_code == 200 and r.json()["product_key"] == "hl_paf" and len(r.json()["cells"]) == 55
      and tc.get("/api/reference/hl_paf/selection.json", headers=hdr(tok_a)).json().get("record_hash")
      and r_liq.status_code == 200 and "verdict" in r_liq.json()
      and tc.get("/api/reference/hl_paf/cohort.json", headers=hdr(tok_a)).status_code == 200)
check("reference: an unknown key, a path-like key and a missing plan are each not found",
      tc.get("/api/reference/nobody/record.json", headers=hdr(tok_a)).status_code == 404
      and tc.get("/api/reference/..%2Fregistry/record.json", headers=hdr(tok_a)).status_code in (404, 422)
      and tc.get("/api/reference/hl_paf/liquidity.json", headers=hdr(tok_a)).status_code == 404)

# ---------------- CORS one origin, errors as sentences, no secrets anywhere
r = tc.options("/api/me", headers={"Origin": "https://tark-app.example.test", "Access-Control-Request-Method": "GET",
                                   "Access-Control-Request-Headers": "authorization"})
r_other = tc.options("/api/me", headers={"Origin": "https://evil.example.test", "Access-Control-Request-Method": "GET"})
check("cors: the app's origin is allowed with GET and POST, any other origin receives no allow-origin header",
      r.headers.get("access-control-allow-origin") == "https://tark-app.example.test"
      and "access-control-allow-origin" not in r_other.headers)
details = []
for rr in (tc.get("/api/me"), tc.post("/api/plans", headers=hdr(tok_a), json={"workspace_id": ws_a, "intake": {}}),
           tc.post("/api/products", headers=hdr(tok_a), json={"workspace_id": ws_a, "cik": "12"}),
           tc.get("/api/jobs/nope", headers=hdr(tok_a)), tc.get(f"/api/records/{rec['id']}/nope.json", headers=hdr(tok_a)),
           tc.post("/api/jobs", headers=hdr(tok_a), json={"product_id": prod_a["id"], "plan_id": plan_a["id"]})):
    d = rr.json().get("detail")
    details.append(d if isinstance(d, str) else json.dumps(d))
_hits = [(d[:40], prose_hits(d)) for d in details if isinstance(d, str) and prose_hits(d)]
check("copy: every error detail is one plain sentence that passes the allowlist rules, no path, key, ticket or developer word",
      all(isinstance(d, str) and d and ";" not in d and "—" not in d for d in details) and not _hits, str(_hits[:2]))
leak = [ln for ln in app.state.log + app2.state.log if SECRET in ln or DISPATCH_TOKEN in ln or fake.service_key in ln]
check("secrets: no log line carries the JWT secret, the dispatch token or the service key, and redact masks each",
      not leak and redact(f"x {DISPATCH_TOKEN} y", {"TARK_DISPATCH_TOKEN": DISPATCH_TOKEN}) == "x <TARK_DISPATCH_TOKEN> y")
def _refused(sb, table):
    try:
        sb.select(table)
        return False
    except SupabaseError as e:
        return e.status == 401



_anon_ok = all(_refused(Supabase("https://project.supabase.test", fake.anon_key, transport=fake.transport), t) for t in fake.tables)
check("anon: the anon key alone reads nothing from any table through the client", _anon_ok)


print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nWorkspace API gate passes.")
sys.exit(1 if FAILS else 0)

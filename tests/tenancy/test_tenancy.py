"""
Tenancy tests (R3-P4-3), run from the outside against a Supabase project.
The laptop session runs them against a throwaway project or the real one
with test workspaces that are deleted after. Generated from the schema:
every table in db/001_schema.sql that carries workspace_id is tested, so a
new table cannot skip the test.

    SUPABASE_URL=... SUPABASE_ANON_KEY=... SUPABASE_SERVICE_KEY=... TARK_API_URL=... \
        python tests/tenancy/test_tenancy.py

What it asserts:
  1. a user of workspace A, holding only A's token, requests every tenant
     table's rows of workspace B by workspace id and by row id and receives
     nothing, and every storage path under B's prefix and receives nothing
  2. the anon key alone reads nothing from any table and no object
  3. every API route rejects a missing token and an expired token
  4. a signed download URL stops working after it expires
The users, workspaces and rows it creates carry the tag tark-tenancy-test
and are deleted at the end (also with --cleanup).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import httpx

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))

TABLE_RE = re.compile(r"create table if not exists public\.(\w+)\s*\((.*?)\n\);", re.S)


def tenant_tables(schema_path: Path) -> list[str]:
    """Every table whose columns carry workspace_id, in schema order."""
    text = schema_path.read_text()
    return [name for name, body in TABLE_RE.findall(text) if re.search(r"^\s*workspace_id\s", body, re.M)]


API_ROUTES = [("GET", "/api/me"), ("GET", "/api/plans"), ("POST", "/api/plans"), ("GET", "/api/products"),
              ("POST", "/api/products"), ("GET", "/api/jobs"), ("POST", "/api/jobs"), ("GET", "/api/jobs/x"),
              ("GET", "/api/records/x/record.json"), ("GET", "/api/documents/x"), ("GET", "/api/reference/index.json")]


def main() -> int:
    from app.supabase import Supabase, SupabaseError
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleanup", action="store_true", help="delete tagged test rows and users and exit")
    a = ap.parse_args()
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    anon = os.environ.get("SUPABASE_ANON_KEY", "")
    service = os.environ.get("SUPABASE_SERVICE_KEY", "")
    api = os.environ.get("TARK_API_URL", "").rstrip("/")
    if not (url and anon and service):
        print("SUPABASE_URL, SUPABASE_ANON_KEY and SUPABASE_SERVICE_KEY are required (the laptop session's environment)")
        return 2
    fails: list[str] = []

    def check(name, cond, detail=""):
        print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" : {detail}" if detail and not cond else ""))
        if not cond:
            fails.append(name)

    admin = Supabase(url, service)
    tables = tenant_tables(BASE / "db" / "001_schema.sql")
    tag = "tark-tenancy-test"

    def cleanup():
        for ws in admin.select("workspaces", filters={"name": f"like.{tag}%"}):
            admin._request("DELETE", "/rest/v1/workspaces", params={"id": f"eq.{ws['id']}"})
        with httpx.Client(base_url=url, headers={"apikey": service, "Authorization": f"Bearer {service}"}, timeout=30) as c:
            users = c.get("/auth/v1/admin/users", params={"per_page": "200"}).json().get("users", [])
            for u in users:
                if (u.get("email") or "").startswith(tag):
                    c.delete(f"/auth/v1/admin/users/{u['id']}")

    if a.cleanup:
        cleanup()
        print("cleaned")
        return 0

    # two users with passwords, two workspaces, one row per tenant table in B
    pw = uuid.uuid4().hex + "Aa1!"
    tokens, users = {}, {}
    with httpx.Client(base_url=url, headers={"apikey": service, "Authorization": f"Bearer {service}"}, timeout=30) as c:
        for who in ("a", "b"):
            email = f"{tag}-{who}-{uuid.uuid4().hex[:8]}@example.test"
            u = c.post("/auth/v1/admin/users", json={"email": email, "password": pw, "email_confirm": True}).json()
            users[who] = u["id"]
    # sign in through the public token endpoint, the way the app does
    with httpx.Client(base_url=url, headers={"apikey": service, "Authorization": f"Bearer {service}"}, timeout=30) as c:
        listing = c.get("/auth/v1/admin/users", params={"per_page": "200"}).json().get("users", [])
    emails = {u["id"]: u["email"] for u in listing}
    with httpx.Client(base_url=url, headers={"apikey": anon}, timeout=30) as c:
        for who in ("a", "b"):
            r = c.post("/auth/v1/token", params={"grant_type": "password"}, json={"email": emails[users[who]], "password": pw})
            tokens[who] = r.json()["access_token"]
    ws = {}
    for who in ("a", "b"):
        ws[who] = admin.insert("workspaces", {"name": f"{tag} {who}"})["id"]
        admin.insert("workspace_members", {"workspace_id": ws[who], "user_id": users[who]})
    plan_b = admin.insert("plans", {"workspace_id": ws["b"], "intake": {"plan_key": "ws_tenancy"}, "source_note": tag})
    prod_b = admin.insert("products", {"workspace_id": ws["b"], "cik": "1", "name": tag, "product_key": "cik_1"})
    job_b = admin.insert("jobs", {"workspace_id": ws["b"], "product_id": prod_b["id"], "plan_id": plan_b["id"]})
    rec_b = admin.insert("records", {"workspace_id": ws["b"], "product_id": prod_b["id"], "plan_id": plan_b["id"], "job_id": job_b["id"],
                                     "artifacts_prefix": f"{ws['b']}/{job_b['id']}", "record_hash": "0" * 64})
    path_b = f"{ws['b']}/{job_b['id']}/views/record.json"
    admin.upload("workspace", path_b, json.dumps({"tag": tag}).encode(), "application/json")
    doc_b = admin.insert("documents", {"workspace_id": ws["b"], "record_id": rec_b["id"], "kind": "view", "storage_path": path_b,
                                       "size_bytes": 10, "sha256": "0" * 64})
    admin.insert("audit_log", {"workspace_id": ws["b"], "user_id": users["b"], "event": "login"})
    admin.insert("spend", {"workspace_id": ws["b"], "job_id": job_b["id"], "cost_usd": 0.01})
    rows_b = {"plans": plan_b, "products": prod_b, "jobs": job_b, "records": rec_b, "documents": doc_b}

    as_a = Supabase(url, anon, token=tokens["a"])
    for t in tables:
        by_ws = as_a.select(t, filters={"workspace_id": ws["b"]})
        by_id = as_a.select(t, filters={"id": rows_b[t]["id"]}) if t in rows_b else []
        check(f"tenancy: A reads nothing of B from {t} by workspace id and by row id", by_ws == [] and by_id == [])
    try:
        as_a.download("workspace", path_b)
        got = True
    except SupabaseError:
        got = False
    check("tenancy: A reads no object under B's storage prefix", not got)
    try:
        as_a.signed_url("workspace", path_b, 60)
        signed = True
    except SupabaseError:
        signed = False
    check("tenancy: A cannot sign a URL under B's prefix", not signed)
    as_anon = Supabase(url, anon)
    anon_reads = []
    for t in tables + ["workspaces", "workspace_members"]:
        try:
            anon_reads.append((t, as_anon.select(t)))
        except SupabaseError:
            pass
    check("anon: the anon key alone reads nothing from any table", all(rows == [] for _, rows in anon_reads), str(anon_reads[:2]))
    try:
        as_anon.download("workspace", path_b)
        anon_obj = True
    except SupabaseError:
        anon_obj = False
    check("anon: the anon key reads no object", not anon_obj)
    if api:
        expired = os.environ.get("TARK_EXPIRED_TOKEN", "")
        with httpx.Client(base_url=api, timeout=30) as c:
            bad = []
            for m, p in API_ROUTES:
                r = c.request(m, p, json={} if m == "POST" else None)
                if r.status_code != 401:
                    bad.append(f"{m} {p} missing {r.status_code}")
                if expired:
                    r = c.request(m, p, headers={"Authorization": f"Bearer {expired}"}, json={} if m == "POST" else None)
                    if r.status_code != 401:
                        bad.append(f"{m} {p} expired {r.status_code}")
            check("api: every route rejects a missing token" + (" and an expired token" if expired else " (set TARK_EXPIRED_TOKEN for the expired case)"),
                  not bad, str(bad[:3]))
    else:
        print("[SKIP] api routes: TARK_API_URL not set")
    as_b = Supabase(url, anon, token=tokens["b"])
    signed_url = as_b.signed_url("workspace", path_b, 2)
    ok_now = httpx.get(signed_url, timeout=30).status_code == 200
    time.sleep(4)
    ok_later = httpx.get(signed_url, timeout=30).status_code == 200
    check("storage: a signed download URL works before its expiry and not after", ok_now and not ok_later)
    cleanup()
    print(f"\n{len(fails)} failure(s)." if fails else "\nTenancy tests pass.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

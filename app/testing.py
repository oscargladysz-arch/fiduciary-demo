"""
A fake Supabase for the offline gates: PostgREST, Storage and Auth admin
over an httpx.MockTransport, in memory, with the row-level policies of
db/002_policies.sql and db/003_storage.sql emulated from the bearer token.
The real policies are tested from the outside in tests/tenancy (R3-P4-3,
the laptop session). This fake exists so the API and the worker run end to
end with no network and no key.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote

import httpx
import jwt

TENANT_TABLES = ("plans", "products", "jobs", "records", "documents", "audit_log", "spend")
USER_INSERT = {"plans", "products", "jobs", "audit_log"}
DEFAULTS = {
    "jobs": {"state": "queued", "progress_step": "queued", "progress_detail": "", "runner": "", "pipeline_commit": "",
             "attempts": 0, "claimed_at": None, "started_at": None, "finished_at": None, "failure_reason": "",
             "tokens_in": 0, "tokens_out": 0, "cost_usd": 0},
    "plans": {"source_note": ""},
    "products": {"name": "", "wrapper": "", "registry_entry": None},
    "records": {"version": 1},
    "audit_log": {"detail": {}, "workspace_id": None},
    "spend": {"note": ""},
}
_AUTO = 0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_token(secret: str, user_id: str, email: str = "", ttl_s: int = 3600, alg: str = "HS256", key=None,
               kid: str | None = None) -> str:
    payload = {"sub": user_id, "email": email, "role": "authenticated", "aud": "authenticated",
               "exp": int(time.time()) + ttl_s, "iat": int(time.time())}
    headers = {"kid": kid} if kid else None
    return jwt.encode(payload, key if key is not None else secret, algorithm=alg, headers=headers)


class FakeSupabase:
    """In-memory tables and objects. handler() is the transport."""

    def __init__(self, service_key: str = "service-key-for-tests-only", anon_key: str = "anon-key-for-tests-only",
                 jwks: dict | None = None):
        self.service_key = service_key
        self.anon_key = anon_key
        self.jwks = jwks or {"keys": []}
        self.tables: dict[str, list[dict]] = {t: [] for t in ("workspaces", "workspace_members") + TENANT_TABLES}
        self.objects: dict[str, bytes] = {}
        self.users: dict[str, dict] = {}
        self.requests: list[tuple[str, str]] = []
        self.patches: list[tuple[str, dict, dict]] = []
        self.transport = httpx.MockTransport(self.handler)

    # ------------------------------------------------------------ helpers
    def seed_user(self, email: str) -> str:
        uid = str(uuid.uuid4())
        self.users[uid] = {"id": uid, "email": email}
        return uid

    def seed_workspace(self, name: str, *user_ids: str) -> str:
        ws = {"id": str(uuid.uuid4()), "name": name, "created_at": now_iso()}
        self.tables["workspaces"].append(ws)
        for u in user_ids:
            self.tables["workspace_members"].append({"workspace_id": ws["id"], "user_id": u, "created_at": now_iso()})
        return ws["id"]

    def memberships(self, user_id: str) -> set[str]:
        return {m["workspace_id"] for m in self.tables["workspace_members"] if m["user_id"] == user_id}

    def _who(self, request: httpx.Request) -> tuple[str, str | None]:
        """('service', None) | ('anon', None) | ('user', user_id)."""
        auth = request.headers.get("authorization", "")
        token = auth.split(" ", 1)[1] if " " in auth else ""
        if token == self.service_key:
            return "service", None
        if not token or token == self.anon_key:
            return "anon", None
        try:
            payload = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
        except jwt.PyJWTError:
            return "anon", None
        if int(payload.get("exp") or 0) <= int(time.time()):
            return "anon", None
        return "user", payload.get("sub")

    @staticmethod
    def _json(status: int, body) -> httpx.Response:
        return httpx.Response(status, json=body)

    def _visible(self, table: str, who: str, uid: str | None) -> list[dict]:
        rows = self.tables[table]
        if who == "service":
            return rows
        if who == "anon":
            return []
        ws = self.memberships(uid)
        if table == "workspaces":
            return [r for r in rows if r["id"] in ws]
        if table == "workspace_members":
            return [r for r in rows if r["user_id"] == uid]
        return [r for r in rows if r.get("workspace_id") in ws]

    @staticmethod
    def _match(row: dict, filters: dict) -> bool:
        for col, spec in filters.items():
            op, _, val = spec.partition(".")
            v = row.get(col)
            if op == "eq" and str(v) != val:
                return False
            if op == "neq" and str(v) == val:
                return False
            if op == "in":
                if str(v) not in [x.strip() for x in val.strip("()").split(",") if x.strip()]:
                    return False
            if op == "is" and val == "null" and v is not None:
                return False
        return True

    # ------------------------------------------------------------ handler
    def handler(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        self.requests.append((request.method, path))
        who, uid = self._who(request)
        if path == "/auth/v1/.well-known/jwks.json":
            return self._json(200, self.jwks)
        if path.startswith("/rest/v1/rpc/"):
            fn = path.rsplit("/", 1)[-1]
            if fn == "ping":
                return self._json(200, "ok")
            if fn == "spend_total":
                if who != "service":
                    return self._json(401, {"message": "permission denied for function spend_total"})
                return self._json(200, sum(float(r["cost_usd"]) for r in self.tables["spend"]))
            return self._json(404, {"message": "no such function"})
        if path.startswith("/rest/v1/"):
            return self._rest(request, path[len("/rest/v1/"):], who, uid)
        if path.startswith("/storage/v1/"):
            return self._storage(request, path[len("/storage/v1/"):], who, uid)
        if path == "/auth/v1/invite":
            if who != "service":
                return self._json(401, {"msg": "invite requires the service role"})
            email = json.loads(request.content)["email"]
            u = next((u for u in self.users.values() if u["email"] == email), None)
            if u is None:
                u = {"id": self.seed_user(email), "email": email}
            return self._json(200, {"id": u["id"], "email": email, "invited_at": now_iso()})
        if path == "/auth/v1/user":
            if who != "user":
                return self._json(401, {"msg": "invalid token"})
            return self._json(200, {"id": uid, "email": self.users.get(uid, {}).get("email", "")})
        return self._json(404, {"message": f"no route {path}"})

    def _rest(self, request: httpx.Request, table: str, who: str, uid: str | None) -> httpx.Response:
        global _AUTO
        if table not in self.tables:
            return self._json(404, {"message": f"relation {table} does not exist"})
        q = {k: v[0] for k, v in parse_qs(request.url.query.decode()).items()}
        filters = {k: v for k, v in q.items() if k not in ("select", "order", "limit", "offset")}
        if request.method == "GET":
            if who == "anon":
                return self._json(401, {"message": "permission denied"})
            rows = [r for r in self._visible(table, who, uid) if self._match(r, filters)]
            if "order" in q:
                col, _, direction = q["order"].partition(".")
                rows = sorted(rows, key=lambda r: str(r.get(col) or ""), reverse=direction == "desc")
            if "limit" in q:
                rows = rows[: int(q["limit"])]
            return self._json(200, rows)
        if request.method == "POST":
            body = json.loads(request.content)
            rows = body if isinstance(body, list) else [body]
            out = []
            for row in rows:
                row = {**DEFAULTS.get(table, {}), **row}
                if who == "anon" or (who == "user" and table not in USER_INSERT):
                    return self._json(401, {"message": "new row violates row-level security policy"})
                if who == "user":
                    ws = row.get("workspace_id")
                    if table == "audit_log":
                        if row.get("user_id") != uid or (ws is not None and ws not in self.memberships(uid)):
                            return self._json(401, {"message": "new row violates row-level security policy"})
                    elif ws not in self.memberships(uid):
                        return self._json(401, {"message": "new row violates row-level security policy"})
                    if table == "jobs" and (row.get("state") != "queued" or row.get("runner") or row.get("cost_usd")):
                        return self._json(401, {"message": "new row violates row-level security policy"})
                if table == "jobs" and any(r["product_id"] == row["product_id"] and r["plan_id"] == row["plan_id"]
                                           and r["state"] in ("queued", "running") for r in self.tables["jobs"]):
                    return self._json(409, {"message": "duplicate key value violates unique constraint jobs_one_active_per_pair"})
                if table == "documents" and any(r["storage_path"] == row["storage_path"] for r in self.tables["documents"]):
                    return self._json(409, {"message": "duplicate key value violates unique constraint documents_storage_path_key"})
                if table in ("audit_log", "spend"):
                    _AUTO += 1
                    row.setdefault("id", _AUTO)
                elif table != "workspace_members":
                    row.setdefault("id", str(uuid.uuid4()))
                row.setdefault("created_at", now_iso())
                if table == "jobs":
                    row.setdefault("updated_at", row["created_at"])
                self.tables[table].append(row)
                out.append(row)
            return self._json(201, out)
        if request.method == "PATCH":
            if who != "service":
                return self._json(401, {"message": "permission denied for table " + table})
            patch = json.loads(request.content)
            self.patches.append((table, dict(filters), patch))
            updated = []
            for r in self.tables[table]:
                if self._match(r, filters):
                    r.update(patch)
                    if table == "jobs":
                        r["updated_at"] = now_iso()
                    updated.append(r)
            return self._json(200, updated)
        return self._json(405, {"message": "method not allowed"})

    def _storage(self, request: httpx.Request, rest: str, who: str, uid: str | None) -> httpx.Response:
        m = re.match(r"object/(sign|list)/([^/]+)(?:/(.*))?$", rest) or re.match(r"object/([^/]+)/(.*)$", rest)
        if not m:
            return self._json(404, {"message": "no such storage route"})
        if m.re.pattern.startswith("object/(sign|list)"):
            action, bucket, path = m.group(1), m.group(2), m.group(3) or ""
        else:
            action, bucket, path = "object", m.group(1), m.group(2)
        key = f"{bucket}/{path}"

        def allowed(p: str) -> bool:
            if who == "service":
                return True
            if who != "user":
                return False
            first = p.split("/", 1)[0]
            return first in self.memberships(uid)

        if action == "object" and request.method == "POST":
            if who != "service":
                return self._json(403, {"message": "new row violates row-level security policy"})
            self.objects[key] = request.content
            return self._json(200, {"Key": key})
        if action == "object" and request.method == "GET":
            if not allowed(path):
                return self._json(403 if who == "user" else 401, {"message": "Object not found"})
            if key not in self.objects:
                return self._json(404, {"message": "Object not found"})
            return httpx.Response(200, content=self.objects[key])
        if action == "sign":
            if not allowed(path) or key not in self.objects:
                return self._json(404 if key not in self.objects else 403, {"message": "Object not found"})
            exp = json.loads(request.content)["expiresIn"]
            return self._json(200, {"signedURL": f"/object/sign/{bucket}/{path}?token=fake-signature&expires={int(time.time()) + exp}"})
        if action == "object" and request.method == "DELETE":
            if who != "service":
                return self._json(403, {"message": "permission denied"})
            prefixes = json.loads(request.content).get("prefixes", [])
            gone = [k for k in list(self.objects) if any(k == f"{bucket}/{p}" for p in prefixes)]
            for k in gone:
                del self.objects[k]
            return self._json(200, [{"name": k.split("/", 1)[1]} for k in gone])
        if action == "list":
            prefix = json.loads(request.content).get("prefix", "")
            items = [{"name": k.split("/", 1)[1], "size": len(v)} for k, v in self.objects.items()
                     if k.startswith(f"{bucket}/{prefix}") and allowed(k.split("/", 1)[1])]
            return self._json(200, items)
        return self._json(405, {"message": "method not allowed"})

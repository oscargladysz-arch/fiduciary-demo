"""
A thin client for Supabase's REST surfaces (PostgREST, Storage, Auth
admin) over httpx. No SDK, so every request is visible and the tests run it
against a fake transport with no network.

Two callers, two keys:
  - the API forwards the user's own JWT (with the anon key as apikey), so
    row-level security decides what the request may read or write
  - the worker and the admin CLI use the service key, from their own
    environments only, never in the API's request path (rule 22)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx


class SupabaseError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message


@dataclass
class Supabase:
    url: str
    apikey: str                      # the anon key (API) or the service key (worker, admin)
    token: str | None = None         # the user's JWT when acting for a user, else the apikey
    transport: httpx.BaseTransport | None = None
    timeout: float = 30.0

    def _headers(self, extra: dict | None = None) -> dict:
        h = {"apikey": self.apikey, "Authorization": f"Bearer {self.token or self.apikey}"}
        if extra:
            h.update(extra)
        return h

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.url, transport=self.transport, timeout=self.timeout)

    def _request(self, method: str, path: str, *, params: dict | None = None, json_body: Any = None,
                 content: bytes | None = None, headers: dict | None = None) -> httpx.Response:
        with self._client() as c:
            r = c.request(method, path, params=params, json=json_body, content=content, headers=self._headers(headers))
        if r.status_code >= 400:
            try:
                msg = r.json()
                msg = msg.get("message") or msg.get("msg") or msg.get("error") or json.dumps(msg)
            except ValueError:
                msg = r.text[:200]
            raise SupabaseError(r.status_code, str(msg))
        return r

    # ------------------------------------------------------------ PostgREST
    def select(self, table: str, *, filters: dict | None = None, columns: str = "*", order: str | None = None,
               limit: int | None = None) -> list[dict]:
        params = {"select": columns, **_filters(filters)}
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(limit)
        return self._request("GET", f"/rest/v1/{table}", params=params).json()

    def insert(self, table: str, row: dict) -> dict:
        r = self._request("POST", f"/rest/v1/{table}", json_body=row,
                          headers={"Prefer": "return=representation"})
        rows = r.json()
        return rows[0] if isinstance(rows, list) and rows else rows

    def update(self, table: str, filters: dict, patch: dict) -> list[dict]:
        """Rows updated (the conditional claim reads the count)."""
        r = self._request("PATCH", f"/rest/v1/{table}", params=_filters(filters), json_body=patch,
                          headers={"Prefer": "return=representation"})
        return r.json()

    def delete(self, table: str, filters: dict) -> list[dict]:
        """Rows deleted. Refuses an empty filter: never a whole table."""
        if not filters:
            raise ValueError("delete needs a filter")
        r = self._request("DELETE", f"/rest/v1/{table}", params=_filters(filters),
                          headers={"Prefer": "return=representation"})
        return r.json()

    def rpc(self, fn: str, args: dict | None = None) -> Any:
        return self._request("POST", f"/rest/v1/rpc/{fn}", json_body=args or {}).json()

    # -------------------------------------------------------------- Storage
    def upload(self, bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream",
               upsert: bool = True) -> dict:
        r = self._request("POST", f"/storage/v1/object/{bucket}/{path}", content=data,
                          headers={"Content-Type": content_type, "x-upsert": "true" if upsert else "false"})
        return r.json()

    def signed_url(self, bucket: str, path: str, expires_in: int, download_name: str | None = None) -> str:
        r = self._request("POST", f"/storage/v1/object/sign/{bucket}/{path}", json_body={"expiresIn": expires_in})
        signed = r.json()["signedURL"]
        url = f"{self.url}/storage/v1{signed}"
        if download_name:
            url += ("&" if "?" in url else "?") + "download=" + httpx.QueryParams({"d": download_name})["d"]
        return url

    def list_objects(self, bucket: str, prefix: str, limit: int = 1000, offset: int = 0) -> list[dict]:
        r = self._request("POST", f"/storage/v1/object/list/{bucket}",
                          json_body={"prefix": prefix, "limit": limit, "offset": offset})
        return r.json()

    def list_all_objects(self, bucket: str, prefix: str, page: int = 1000, max_pages: int = 1000) -> list[dict]:
        """Every object under the prefix, one page at a time. The caller that
        deletes needs all of them, and a listing that stops at the first page
        would leave objects behind with no row that names them."""
        out: list[dict] = []
        for _ in range(max_pages):
            page_rows = self.list_objects(bucket, prefix, limit=page, offset=len(out))
            if not page_rows:
                break
            out.extend(page_rows)
            if len(page_rows) < page:
                break
        return out

    def delete_objects(self, bucket: str, paths: list[str]) -> list[dict]:
        return self._request("DELETE", f"/storage/v1/object/{bucket}", json_body={"prefixes": paths}).json()

    def download(self, bucket: str, path: str) -> bytes:
        return self._request("GET", f"/storage/v1/object/{bucket}/{path}").content

    # ---------------------------------------------------------- Auth admin
    def invite(self, email: str, redirect_to: str | None = None) -> dict:
        body = {"email": email}
        if redirect_to:
            body["redirect_to"] = redirect_to  # copy-exempt: an API field name
        return self._request("POST", "/auth/v1/invite", json_body=body).json()

    def user_of_token(self) -> dict:
        """The user behind self.token, from Supabase Auth itself (the
        verifier's fallback when no signing key is configured)."""
        return self._request("GET", "/auth/v1/user").json()


_OPS = {"eq", "neq", "gt", "gte", "lt", "lte", "in", "is", "like", "ilike", "cs", "cd", "not"}


def _filters(filters: dict | None) -> dict:
    """PostgREST filters: a value already carrying an operator ('in.(a,b)',
    'is.null') passes through, anything else is an equality."""
    out = {}
    for k, v in (filters or {}).items():
        sv = str(v)
        out[k] = sv if sv.split(".", 1)[0] in _OPS and "." in sv else f"eq.{sv}"
    return out

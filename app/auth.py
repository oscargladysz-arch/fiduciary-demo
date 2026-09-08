"""
Who is calling: the Supabase JWT on every request (rule 22, no auth code of
our own). The token is verified, never issued here:
  - projects with JWT signing keys publish a JWKS at
    <url>/auth/v1/.well-known/jwks.json (ES256 or RS256): verified by kid
  - legacy projects sign with the project's JWT secret (HS256):
    verified with SUPABASE_JWT_SECRET
The audience must be 'authenticated' and the token unexpired. The verified
claims travel with the request. The same token is then forwarded to
Supabase so row-level security applies to every read and write.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
import jwt

ASYMMETRIC = ("ES256", "RS256", "ES384", "RS384", "EdDSA")


class AuthError(Exception):
    """Refused: the reason in one plain sentence (never the token)."""


@dataclass(frozen=True)
class Claims:
    user_id: str
    email: str
    role: str
    expires_at: int
    token: str

    @property
    def expired(self) -> bool:
        return self.expires_at <= int(time.time())


class Verifier:
    def __init__(self, supabase_url: str, jwt_secret: str = "", transport: httpx.BaseTransport | None = None,
                 jwks_ttl_s: int = 600):
        self.url = supabase_url.rstrip("/")
        self.secret = jwt_secret
        self.transport = transport
        self.ttl = jwks_ttl_s
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched = 0.0

    def _jwks(self, force: bool = False) -> dict[str, jwt.PyJWK]:
        if force or not self._keys or time.time() - self._fetched > self.ttl:
            with httpx.Client(base_url=self.url, transport=self.transport, timeout=10.0) as c:
                r = c.get("/auth/v1/.well-known/jwks.json")
            r.raise_for_status()
            self._keys = {k["kid"]: jwt.PyJWK(k) for k in r.json().get("keys", []) if k.get("kid")}
            self._fetched = time.time()
        return self._keys

    def verify(self, token: str) -> Claims:
        if not token or token.count(".") != 2:
            raise AuthError("a bearer token is required")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise AuthError("the token could not be read") from None
        alg = header.get("alg", "")
        try:
            if alg in ASYMMETRIC:
                kid = header.get("kid", "")
                keys = self._jwks()
                if kid not in keys:
                    keys = self._jwks(force=True)
                if kid not in keys:
                    raise AuthError("the token's signing key is not one the project publishes")
                payload = jwt.decode(token, keys[kid].key, algorithms=[alg], audience="authenticated")
            elif alg == "HS256":
                if not self.secret:
                    raise AuthError("the project signs with a secret this API was not given")
                payload = jwt.decode(token, self.secret, algorithms=["HS256"], audience="authenticated")
            else:
                raise AuthError("the token's algorithm is not one Supabase issues")
        except jwt.ExpiredSignatureError:
            raise AuthError("the session has expired, sign in again") from None
        except jwt.PyJWTError:
            raise AuthError("the token is not valid for this project") from None
        sub = payload.get("sub") or ""
        if not sub:
            raise AuthError("the token names no user")
        return Claims(user_id=sub, email=payload.get("email") or "", role=payload.get("role") or "",
                      expires_at=int(payload.get("exp") or 0), token=token)


def bearer(authorization: str | None) -> str:
    if not authorization:
        return ""
    scheme, _, rest = authorization.partition(" ")
    return rest.strip() if scheme.lower() == "bearer" else ""

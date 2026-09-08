"""Environment for the API. Every value comes from the environment (rule 8).
Nothing here is a secret the request path could leak: the anon key is
public by Supabase's design, the JWT secret and the dispatch token are read
once and never logged or returned."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_anon_key: str
    supabase_jwt_secret: str = ""           # HS256 projects. Empty on projects with signing keys (JWKS)
    app_origin: str = ""                    # the one CORS origin (the static app's host)
    dispatch_repo: str = ""                 # owner/tark-workspace, the private repository
    dispatch_token: str = ""                # fine-grained token that can only dispatch that workflow
    dispatch_event: str = "run_job"
    pipeline_commit: str = ""               # the public pipeline commit a job pins (Render sets RENDER_GIT_COMMIT)
    signed_url_seconds: int = 300
    reference_dir: str = ""                 # the checkout's data/ for the 16 references (read-only)
    extra: dict = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)


def load_settings(env: dict | None = None) -> Settings:
    e = os.environ if env is None else env
    url = (e.get("SUPABASE_URL") or "").rstrip("/")
    if url and not url.startswith("https://"):
        raise SystemExit("SUPABASE_URL must be an https URL")
    origin = (e.get("TARK_APP_ORIGIN") or "").rstrip("/")
    if origin and not origin.startswith("https://"):
        raise SystemExit("TARK_APP_ORIGIN must be an https origin")
    return Settings(
        supabase_url=url,
        supabase_anon_key=e.get("SUPABASE_ANON_KEY") or "",
        supabase_jwt_secret=e.get("SUPABASE_JWT_SECRET") or "",
        app_origin=origin,
        dispatch_repo=e.get("TARK_DISPATCH_REPO") or "",
        dispatch_token=e.get("TARK_DISPATCH_TOKEN") or "",
        dispatch_event=e.get("TARK_DISPATCH_EVENT") or "run_job",
        pipeline_commit=e.get("TARK_PIPELINE_COMMIT") or e.get("RENDER_GIT_COMMIT") or "",
        signed_url_seconds=min(max(int(e.get("TARK_SIGNED_URL_SECONDS") or 300), 30), 3600),
        reference_dir=e.get("TARK_REFERENCE_DIR") or "",
    )


SECRET_NAMES = ("SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_KEY", "TARK_DISPATCH_TOKEN", "ANTHROPIC_API_KEY",
                "DATABASE_URL", "TARK_SEC_CONTACT")


def redact(text: str, env: dict | None = None) -> str:
    """A log line with every secret value replaced, so no log ever carries one (rule 8)."""
    e = os.environ if env is None else env
    out = text
    for name in SECRET_NAMES:
        v = e.get(name) or ""
        if len(v) >= 8 and v in out:
            out = out.replace(v, f"<{name}>")
    return out

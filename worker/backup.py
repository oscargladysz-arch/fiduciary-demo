"""
Nightly backup (R3-P4-7): pg_dump of the schema and data plus a listing of
the storage bucket, uploaded under backups/<date>/ with 30-day retention.
Runs in the private repository's backup workflow with DATABASE_URL,
SUPABASE_URL and SUPABASE_SERVICE_KEY from its secrets.

    python -m worker.backup [--keep-days 30] [--out DIR]
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import redact  # noqa: E402
from app.supabase import Supabase  # noqa: E402

BUCKET = "workspace"


def dump(database_url: str, out: Path) -> Path:
    tool = shutil.which("pg_dump")
    if tool is None:
        raise SystemExit("pg_dump is not installed here (postgresql-client)")
    r = subprocess.run([tool, "--no-owner", "--no-privileges", "--schema=public", database_url],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("pg_dump failed: " + redact(r.stderr[-400:]))
    path = out / "db.sql.gz"
    with gzip.open(path, "wt") as fh:
        fh.write(r.stdout)
    return path


def prune(sb: Supabase, keep_days: int, today: date | None = None) -> list[str]:
    today = today or date.today()
    cutoff = today - timedelta(days=keep_days)
    old = []
    for it in sb.list_objects(BUCKET, "backups/"):
        name = it.get("name", "")
        day = name.split("/")[0] if "/" in name else name
        try:
            if date.fromisoformat(day) < cutoff:
                old.append(f"backups/{name}")
        except ValueError:
            continue
    if old:
        sb.delete_objects(BUCKET, old)
    return old


def run(sb: Supabase, database_url: str, out: Path, keep_days: int = 30, today: date | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    today = today or date.today()
    stamp = today.isoformat()
    db = dump(database_url, out)
    listing = sb.list_objects(BUCKET, "")
    lst = out / "storage_listing.json"
    lst.write_text(json.dumps({"taken_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "objects": listing}, indent=1))
    sb.upload(BUCKET, f"backups/{stamp}/db.sql.gz", db.read_bytes(), "application/gzip")
    sb.upload(BUCKET, f"backups/{stamp}/storage_listing.json", lst.read_bytes(), "application/json")
    pruned = prune(sb, keep_days, today)
    return {"date": stamp, "dump_bytes": db.stat().st_size, "objects_listed": len(listing), "pruned": pruned}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-days", type=int, default=30)
    ap.add_argument("--out", default="backup_out")
    a = ap.parse_args()
    url, key, db = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_KEY", ""), os.environ.get("DATABASE_URL", "")
    if not (url and key and db):
        raise SystemExit("SUPABASE_URL, SUPABASE_SERVICE_KEY and DATABASE_URL are required")
    res = run(Supabase(url, key), db, Path(a.out), a.keep_days)
    print(json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())

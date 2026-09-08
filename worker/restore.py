"""
Restore test (R3-P4-7): a backup restored into a local Postgres, then a row
count per table, so the runbook can say the backup restores.

    python -m worker.restore <date> --target postgresql://localhost/tark_restore
Downloads backups/<date>/db.sql.gz from the bucket with the service key,
runs it through psql against the target, and prints the counts.
"""
from __future__ import annotations

import argparse
import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import redact  # noqa: E402
from app.supabase import Supabase  # noqa: E402

TABLES = ("workspaces", "workspace_members", "plans", "products", "jobs", "records", "documents", "audit_log", "spend")


def restore(sql: str, target: str) -> dict[str, int]:
    psql = shutil.which("psql")
    if psql is None:
        raise SystemExit("psql is not installed here (postgresql-client)")
    r = subprocess.run([psql, "-v", "ON_ERROR_STOP=1", target], input=sql, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("psql failed: " + redact(r.stderr[-400:]))
    counts = {}
    for t in TABLES:
        r = subprocess.run([psql, "-tA", target, "-c", f"select count(*) from public.{t}"], capture_output=True, text=True)
        counts[t] = int((r.stdout or "0").strip() or 0) if r.returncode == 0 else -1
    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--target", required=True, help="a local Postgres URL, never the production database")
    a = ap.parse_args()
    if "supabase" in a.target:
        raise SystemExit("the restore target must be a local database, never the project")
    url, key = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_KEY", "")
    sb = Supabase(url, key)
    blob = sb.download("workspace", f"backups/{a.date}/db.sql.gz")
    sql = gzip.decompress(blob).decode()
    counts = restore(sql, a.target)
    for t, n in counts.items():
        print(f"{t:<20} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

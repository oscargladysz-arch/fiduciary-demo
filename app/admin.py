"""
The admin command line (R3-P4-2): Oscar's actions with the service key from
his own environment, never the API's. Every action is one row-level write
the policies would refuse a user.

    python -m app.admin workspace "<name>"                 create a workspace
    python -m app.admin invite <email> <workspace>         invite through Supabase Auth and record the membership
    python -m app.admin set-registry <product_id> <entry.json>   a person's registry judgment for a product's jobs
    python -m app.admin requeue <job_id>                   a failed or stuck job back to queued
    python -m app.admin jobs [<workspace>]                 list jobs with state, runner and cost
    python -m app.admin budget                             the spend total against TARK_BUDGET_USD

Env: SUPABASE_URL, SUPABASE_SERVICE_KEY, TARK_BUDGET_USD (default 50),
TARK_INVITE_REDIRECT (the app's login page).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.supabase import Supabase, SupabaseError  # noqa: E402

UUID_LEN = 36


def client(sb: Supabase | None = None) -> Supabase:
    if sb is not None:
        return sb
    url, key = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_KEY must be in your environment (the service key never leaves it)")
    return Supabase(url, key)


def workspace_id(sb: Supabase, name_or_id: str) -> str:
    if len(name_or_id) == UUID_LEN and name_or_id.count("-") == 4:
        return name_or_id
    rows = sb.select("workspaces", filters={"name": name_or_id})
    if not rows:
        raise SystemExit(f"no workspace named {name_or_id!r}")
    return rows[0]["id"]


def create_workspace(sb: Supabase, name: str) -> dict:
    return sb.insert("workspaces", {"name": name})


def invite(sb: Supabase, email: str, workspace: str, redirect_to: str | None = None) -> dict:
    ws = workspace_id(sb, workspace)
    user = sb.invite(email, redirect_to=redirect_to)
    uid = user["id"]
    if not sb.select("workspace_members", filters={"workspace_id": ws, "user_id": uid}):
        sb.insert("workspace_members", {"workspace_id": ws, "user_id": uid})
    sb.insert("audit_log", {"workspace_id": ws, "user_id": None, "event": "invite", "detail": {"user_id": uid}})
    return {"user_id": uid, "workspace_id": ws, "email": email}


def set_registry(sb: Supabase, product_id: str, entry: dict) -> dict:
    for f in ("cohort", "strategy", "asset_class", "wrapper_type", "pricing_class", "filings", "sources"):
        if f not in entry:
            raise SystemExit(f"the registry entry needs {f} (every judged field with its source, see data/registry.json)")
    rows = sb.update("products", {"id": product_id}, {"registry_entry": entry})
    if not rows:
        raise SystemExit("no product with that id")
    return rows[0]


def requeue(sb: Supabase, job_id: str) -> dict:
    rows = sb.update("jobs", {"id": job_id, "state": "in.(failed,running)"},
                     {"state": "queued", "runner": "", "progress_step": "queued", "progress_detail": "requeued by the admin",
                      "failure_reason": "", "claimed_at": None, "started_at": None, "finished_at": None})
    if not rows:
        raise SystemExit("no failed or running job with that id")
    return rows[0]


def budget(sb: Supabase, budget_usd: float | None = None) -> dict:
    total = float(sb.rpc("spend_total") or 0.0)
    cap = float(os.environ.get("TARK_BUDGET_USD", 50)) if budget_usd is None else budget_usd
    return {"spent_usd": round(total, 4), "budget_usd": cap, "remaining_usd": round(max(cap - total, 0.0), 4),
            "note": "spent is the sum of every job's estimate at the configured price list, raising the budget is Oscar's action in the environment"}


def main(argv: list[str] | None = None, sb: Supabase | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("workspace")
    p.add_argument("name")
    p = sub.add_parser("invite")
    p.add_argument("email")
    p.add_argument("workspace")
    p = sub.add_parser("set-registry")
    p.add_argument("product_id")
    p.add_argument("entry_json")
    p = sub.add_parser("requeue")
    p.add_argument("job_id")
    p = sub.add_parser("jobs")
    p.add_argument("workspace", nargs="?", default="")
    sub.add_parser("budget")
    a = ap.parse_args(argv)
    sb = client(sb)
    try:
        if a.cmd == "workspace":
            print(json.dumps(create_workspace(sb, a.name)))
        elif a.cmd == "invite":
            print(json.dumps(invite(sb, a.email, a.workspace, os.environ.get("TARK_INVITE_REDIRECT") or None)))
        elif a.cmd == "set-registry":
            print(json.dumps({"product_id": set_registry(sb, a.product_id, json.loads(Path(a.entry_json).read_text()))["id"]}))
        elif a.cmd == "requeue":
            print(json.dumps({k: requeue(sb, a.job_id)[k] for k in ("id", "state")}))
        elif a.cmd == "jobs":
            filters = {"workspace_id": workspace_id(sb, a.workspace)} if a.workspace else None
            for j in sb.select("jobs", filters=filters, order="created_at.desc", limit=50):
                print(f"{j['id']}  {j['state']:<8} {j['runner'] or '-':<8} ${float(j['cost_usd']):.2f}  {j['progress_step']}  {j['failure_reason'][:60]}")
        elif a.cmd == "budget":
            print(json.dumps(budget(sb)))
    except SupabaseError as e:
        print(f"refused by the workspace database: {e.message}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

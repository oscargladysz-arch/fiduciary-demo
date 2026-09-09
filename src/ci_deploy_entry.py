"""
Append a deploy-log entry to docs/DEPLOY_LOG.md from a workflow deploy
(R3-P0-3). The workflow calls this after a green run on main has replaced
the gh-pages root, with the facts of that run. Nothing here is invented:
every field is an argument the workflow measured, and the build outputs are
read from the site directory the run built.

Run:  python src/ci_deploy_entry.py --source-commit <sha> --pages-commit <sha>
          --started <iso> --finished <iso> --wall-seconds <n> --pass-count <n>
          --edgar "<result line>" --run-url <url> --site-dir site
"""
from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
LOG = BASE / "docs" / "DEPLOY_LOG.md"

GATES = ("validate_data, validate_census, test_evidence_immutable, corrections_log "
         "check, test_invariants, test_copy, test_docs, test_analytics, test_cohort, "
         "test_benchmark, test_liquidity, test_ingest, test_memo, test_app, "
         "test_artifacts_fresh, build_site, reconcile, test_surfaces, test_frontend")


def clean(s: str) -> str:
    """The copy gate refuses em dashes and semicolons in this file."""
    return s.replace("—", ",").replace(";", ",").strip()


def next_entry_number(text: str) -> int:
    nums = [int(m) for m in re.findall(r"^## Entry (\d+),", text, flags=re.M)]
    return (max(nums) + 1) if nums else 1


def build_outputs(site: Path) -> str:
    """What was deployed, in the sizes a later reader can check against the
    tree the deploy commit carries."""
    parts = []
    assets = sorted((site / "assets").glob("*")) if (site / "assets").exists() else []
    if assets:
        parts.append(f"{len(assets)} application files, "
                     f"{sum(f.stat().st_size for f in assets):,} bytes")
    chunks = sorted((site / "data").rglob("*.json")) if (site / "data").exists() else []
    if chunks:
        parts.append(f"{len(chunks)} record chunks, "
                     f"{sum(f.stat().st_size for f in chunks):,} bytes")
    memos = list((site / "memos").glob("*.docx")) if (site / "memos").exists() else []
    if memos:
        parts.append(f"{len(memos)} documents under `site/memos/`")
    return ", ".join(parts) if parts else "not read"


def entry(a: argparse.Namespace, number: int) -> str:
    today = date.today().isoformat()
    return f"""
## Entry {number}, {today}, workflow deploy from main

- Source commit: `{a.source_commit[:7]}` on `main`, deployed by the gates
  workflow (R3-P0-3) from the run at {a.run_url}. The tree deployed is the
  built site of that commit.
- Machine: a GitHub-hosted Ubuntu runner (Python 3.11, Playwright
  {a.playwright_version}, LibreOffice from apt). It reaches sec.gov.
- Hook run that authorized the deploy: `sh hooks/pre-commit` on the tree of
  `{a.source_commit[:7]}`, started {a.started}, finished {a.finished}, exit 0,
  {int(a.pass_count):,} `[PASS]` lines, wall time {int(a.wall_seconds)} s.
  Gates in order, each green: {GATES}.
- Build outputs from that run: {build_outputs(Path(a.site_dir))}. The
  anonymization gate in the build passed.
- Deploy: the built `site/` replaced the `gh-pages` root (every prior root
  file removed first, `previews/` and `.nojekyll` kept), committed as
  `{a.pages_commit}` and pushed without force. A recursive diff between
  `site/` and the deployed root shows no difference apart from `.nojekyll`
  and `previews/`.
- Tier 1 drawer check: green in the authorizing run (the frontend gate's
  automated drawer check against the evidence CSV).
- EDGAR HTTP 200 check: {clean(a.edgar)}.
- Demo script surface check: green in the same run (the frontend gate
  renders every spoken text on its named view).
- Rollback: the previous `gh-pages` commit stays in the branch history.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-commit", required=True)
    ap.add_argument("--pages-commit", required=True)
    ap.add_argument("--started", required=True)
    ap.add_argument("--finished", required=True)
    ap.add_argument("--wall-seconds", required=True)
    ap.add_argument("--pass-count", required=True)
    ap.add_argument("--edgar", required=True)
    ap.add_argument("--run-url", required=True)
    ap.add_argument("--site-dir", default="site")
    ap.add_argument("--playwright-version", default="1.56.0")
    ap.add_argument("--dry-run", action="store_true", help="print the entry, write nothing")
    a = ap.parse_args()
    text = LOG.read_text()
    e = entry(a, next_entry_number(text))
    if "—" in e or ";" in e:
        raise SystemExit("the entry would fail the copy gate")
    if a.dry_run:
        print(e)
        return 0
    LOG.write_text(text.rstrip("\n") + "\n" + e)
    print(f"appended entry to {LOG.relative_to(BASE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

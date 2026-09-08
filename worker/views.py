"""
The JSON views a job writes for the workspace (R3-P4-4).

Every shape comes from src/tark_views.py, the one builder the static site
build and the workspace API also use, so a partner's record and a reference
product are read through the same adapter without a branch. Nothing is
computed here: this writes what the job's own record already says.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def write_views(data: Path, key: str, plan_key: str, out: Path, report_path: Path | None = None) -> list[Path]:
    """The views for one product and one plan, into out/. `data` is the job's
    data root, which the pipeline already bound before importing anything."""
    import tark_views
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def put(name: str, body: dict) -> None:
        p = out / f"{name}.json"
        p.write_text(json.dumps(body, indent=1, ensure_ascii=False, default=str))
        written.append(p)

    put("record", tark_views.record_view(key))
    put("selection", tark_views.selection_view(key))
    put("liquidity", tark_views.liquidity_view(plan_key, key))
    put("cohort", tark_views.cohort_view(key))
    put("facts", tark_views.facts_view(key))
    report = json.loads(report_path.read_text()) if report_path and report_path.exists() else None
    put("report", tark_views.report_view(key, report))
    return written

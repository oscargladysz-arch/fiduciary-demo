"""
Freshness gate: committed artifacts equal a fresh producer run
===============================================================
Copies data/ to a scratch directory, runs src/produce.py there with the
record's as-of date, and compares the regenerated artifacts with the
committed ones. Any drift between the record and its derived artifacts fails
the gate. The gate never writes into the repository.

Compared (normalized: keys named "generated" dropped, docx by extracted
text): liquidity, facts, cohorts, benchmark selections, memos.
The supplement joins the set in P0-3, once fee_percentile reads typed facts
instead of a regex over cell prose.

Run: python src/test_artifacts_fresh.py   (exit 0 = fresh)
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import produce  # noqa: E402
from tark_anon import docx_text  # noqa: E402
from tark_data import DATA, record_as_of  # noqa: E402

ARTIFACTS = [
    "liquidity/*.json",
    "facts/*.json",
    "cohorts/*.json",
    "benchmarks/*_selection.json",
    "memos/*.docx",
]
SKIP_STEPS = {"supplement"}   # joins in P0-3 (see module docstring)
DROP_KEYS = {"generated"}


def norm(obj):
    if isinstance(obj, dict):
        return {k: norm(v) for k, v in obj.items() if k not in DROP_KEYS}
    if isinstance(obj, list):
        return [norm(v) for v in obj]
    return obj


def load(path: Path):
    if path.suffix == ".json":
        return norm(json.loads(path.read_text()))
    if path.suffix == ".docx":
        return docx_text(path)
    return path.read_bytes()


def first_diff(a, b, path="") -> str:
    if type(a) is not type(b):
        return f"{path}: type {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                return f"{path}.{k}: missing in committed"
            if k not in b:
                return f"{path}.{k}: missing in fresh run"
            d = first_diff(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return ""
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return ""
    if isinstance(a, str) and a != b:
        i = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        return f"{path}: text differs at char {i}: {a[max(0,i-30):i+40]!r} vs {b[max(0,i-30):i+40]!r}"
    if a != b:
        return f"{path}: {a!r} vs {b!r}"
    return ""


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="tark_fresh_"))
    scratch = tmp / "data"
    shutil.copytree(DATA, scratch, ignore=shutil.ignore_patterns("raw"))
    try:
        produce.run(data_dir=str(scratch), as_of=record_as_of(),
                    skip=SKIP_STEPS)
    except SystemExit as e:
        print(f"[FAIL] producer chain failed in the scratch run: {e}")
        return 1
    fails = 0
    for pattern in ARTIFACTS:
        committed = {p.name: p for p in sorted(DATA.glob(pattern))}
        fresh = {p.name: p for p in sorted(scratch.glob(pattern))}
        for name in sorted(set(committed) | set(fresh)):
            if name not in fresh:
                print(f"[FAIL] {pattern}: {name} committed but not produced")
                fails += 1
                continue
            if name not in committed:
                print(f"[FAIL] {pattern}: {name} produced but not committed")
                fails += 1
                continue
            d = first_diff(load(committed[name]), load(fresh[name]))
            if d:
                print(f"[FAIL] {pattern}: {name} is stale: {d}")
                fails += 1
        print(f"[{'FAIL' if fails else 'ok'}]   {pattern}: {len(committed)} files")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{fails} stale artifact(s)." if fails
          else "\nAll artifacts are fresh: committed files equal a reproducible producer run.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

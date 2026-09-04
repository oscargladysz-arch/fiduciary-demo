"""
Producer chain: the only way artifacts are regenerated
=======================================================
Runs every artifact producer in a fixed order with a fixed as-of date, so a
run is reproducible and src/test_artifacts_fresh.py can diff a fresh run
against the committed files.

Order (each step reads what the earlier ones wrote):
  1 liquidity         tark_liquidity.py     data/liquidity/*.json
  2 facts             build_facts.py        data/facts/*.json (cell-derived)
  3 cohorts           tark_cohort.py        data/cohorts/*.json
  4 benchmark         run_benchmark.py      data/benchmarks/*_selection.json
  5 facts-engine      build_facts.py        engine fields from step 4
  6 supplement        run_supplement.py     data/analytics/supplement.json
  7 computed-cells    write_computed_cells.py
  8 memos             tark_memo.py          data/memos/*.docx

Run:  python src/produce.py [--data-dir DIR] [--as-of YYYY-MM-DD]
                            [--skip step,...] [--only step,...] [--verbose]
Env:  TARK_DATA_DIR and TARK_AS_OF are honoured by every step.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent

STEPS = [
    ("liquidity", "tark_liquidity.py"),
    ("facts", "build_facts.py"),
    ("cohorts", "tark_cohort.py"),
    ("benchmark", "run_benchmark.py"),
    ("facts-engine", "build_facts.py"),
    ("supplement", "run_supplement.py"),      # fee_percentile reads the facts
    ("computed-cells", "write_computed_cells.py"),
    ("memos", "tark_memo.py"),
]


def run(data_dir: str | None = None, as_of: str | None = None,
        skip: set[str] | None = None, only: set[str] | None = None,
        verbose: bool = False) -> list[str]:
    env = dict(os.environ)
    if data_dir:
        env["TARK_DATA_DIR"] = str(Path(data_dir).resolve())
    if as_of:
        env["TARK_AS_OF"] = as_of
    ran: list[str] = []
    for name, script in STEPS:
        if skip and name in skip:
            continue
        if only and name not in only:
            continue
        path = SRC / script
        if not path.exists():
            if verbose:
                print(f"[produce] {name:<15} skipped ({script} not present yet)")
            continue
        r = subprocess.run([sys.executable, str(path)], env=env,
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.stdout.write(r.stdout)
            sys.stderr.write(r.stderr)
            raise SystemExit(f"[produce] step '{name}' ({script}) failed "
                             f"with exit {r.returncode}")
        ran.append(name)
        if verbose:
            last = (r.stdout.strip().splitlines() or [""])[-1]
            print(f"[produce] {name:<15} ok  {last[:90]}")
    return ran


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir")
    ap.add_argument("--as-of")
    ap.add_argument("--skip", default="", help="comma-separated step names")
    ap.add_argument("--only", default="", help="comma-separated step names")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    skip = {s for s in a.skip.split(",") if s}
    only = {s for s in a.only.split(",") if s}
    ran = run(a.data_dir, a.as_of, skip, only, a.verbose or True)
    print(f"[produce] done: {', '.join(ran)}")


if __name__ == "__main__":
    main()

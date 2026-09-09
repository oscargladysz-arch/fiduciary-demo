"""
Assemble the deployable site (R3-P1)
=====================================
Two producers write two halves of one folder. `src/build_site.py` writes the
record into `site/` as JSON chunks and writes the generated documents into
`site/memos/`. The web build writes the application into `site_next/`. What
gets deployed is both halves in one folder, and this is the only place that
puts them together, so a deploy cannot be assembled a second way by hand.

The application's own files are replaced whole on every run, because their
names carry a content hash and yesterday's bundle is not part of today's
build. The record's folders are never touched: this script refuses to run if
the application half would overwrite one of them.

Run:  python src/assemble_site.py        -> site/ holds the deployable tree
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
APP = BASE / "site_next"          # the web build
SITE = BASE / "site"              # the deployable tree

# what the record owns. The application may not write any of these, and this
# script never deletes them.
RECORD_DIRS = ("data", "memos", "census")


def assemble(app: Path = APP, site: Path = SITE) -> dict:
    if not app.exists() or not (app / "index.html").exists():
        raise SystemExit(
            f"{app.name} holds no built application (no index.html). "
            "Run the web build first: npm --prefix web run build")
    if not site.exists():
        raise SystemExit(f"{site.name} does not exist. Run python src/build_site.py first.")

    clash = sorted(p.name for p in app.iterdir() if p.name in RECORD_DIRS)
    if clash:
        raise SystemExit(
            f"the built application carries {clash}, which is the record's own. "
            "Assembly refused rather than overwriting the record.")

    # the application's previous files go, because their names carry a content
    # hash: keeping them would deploy two builds at once
    copied, removed = [], []
    for entry in sorted(site.iterdir()):
        if entry.name in RECORD_DIRS or entry.name.startswith("."):
            continue
        if entry.name in {p.name for p in app.iterdir()} or entry.name == "assets":
            removed.append(entry.name)
            shutil.rmtree(entry) if entry.is_dir() else entry.unlink()

    for entry in sorted(app.iterdir()):
        target = site / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)
        copied.append(entry.name)

    missing = [d for d in RECORD_DIRS if not (site / d).exists()]
    return {"copied": copied, "removed": removed, "record_missing": missing}


def main() -> None:
    out = assemble()
    print(f"site/ assembled: {len(out['copied'])} entries from the application "
          f"({', '.join(out['copied'])}), {len(out['removed'])} replaced")
    if out["record_missing"]:
        print(f"the record's folders are not all present: {out['record_missing']}. "
              "Run python src/build_site.py.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()

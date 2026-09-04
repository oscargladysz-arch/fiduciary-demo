"""
Sync the documentation strings in data/census/{universe,census}.json with the
constants in the census modules.
    python src/census/sync_notes.py

The census build needs its raw checkpoint (gitignored) and the network, so a
copy edit to a constant in enumerate.py or build_census.py cannot always be
carried into the committed data by rebuilding. This script imports those
constants (never a copy of the text) and rewrites only the fields that hold
them: 'what' in both files, method_notes in universe.json, name_hint.note on
every census record, and the detection_evidence text composed from constants
(interval_23c3 and unlisted_cef_other records, both files). Every other byte
stays as it is: json load, replace, dump with the files' own indent=1 and key
order. The script refuses to write a file that does not already round-trip
byte for byte, because a rewrite would then touch every line.

validate_census.py checks the same fields and never writes. This is the one
script that fixes drift.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_census  # noqa: E402
import enumerate as census_enum  # noqa: E402  (the module, not the builtin)

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "data" / "census"


def set_field(obj: dict, key: str, value) -> int:
    """Replace obj[key] when it differs. Returns 1 on change, else 0."""
    if obj.get(key) == value:
        return 0
    obj[key] = value
    return 1


def sync_evidence(entities: dict) -> int:
    n = 0
    for rec in entities.values():
        exp = census_enum.constant_evidence(rec)
        if exp is not None:
            n += set_field(rec, "detection_evidence", exp)
    return n


def sync_universe(doc: dict) -> dict[str, int]:
    return {
        "what": set_field(doc, "what", census_enum.UNIVERSE_WHAT),
        "method_notes": set_field(doc, "method_notes",
                                  census_enum.METHOD_NOTES),
        "detection_evidence": sync_evidence(doc["entities"]),
    }


def sync_census(doc: dict) -> dict[str, int]:
    notes = 0
    for rec in doc["entities"].values():
        if "name_hint" in rec:
            notes += set_field(rec["name_hint"], "note",
                               build_census.NAME_HINT_NOTE)
    return {
        "what": set_field(doc, "what", build_census.CENSUS_WHAT),
        "name_hint.note": notes,
        "detection_evidence": sync_evidence(doc["entities"]),
    }


def sync_file(path: Path, apply) -> dict[str, int]:
    raw = path.read_text()
    doc = json.loads(raw)
    if json.dumps(doc, indent=1) != raw:
        sys.exit(f"[FAIL] {path.name}: not a byte-exact json.dumps(indent=1) "
                 "file, refusing to rewrite it")
    changed = apply(doc)
    if sum(changed.values()):
        path.write_text(json.dumps(doc, indent=1))
    return changed


def main() -> int:
    for name, apply in (("universe.json", sync_universe),
                        ("census.json", sync_census)):
        changed = sync_file(OUT / name, apply)
        summary = ", ".join(f"{k} {v}" for k, v in changed.items())
        print(f"{name}: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

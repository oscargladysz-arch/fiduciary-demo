"""
P2-10: accession column and laptop-path purge
    python src/purge_paths.py

For every evidence row: the accession column is filled from the offline
resolver (data/citations): the one resolved accession, or "multiple (N),
data/citations/<key>.json" for a set or range, or empty when no filing
reference resolves. local_file that points at a laptop path becomes the
manifest local_path of the resolved filing when there is exactly one, and
empty otherwise (data/raw is not in git, the manifest is the ledger). The
series manifest notes lose their laptop paths too. Idempotent, and every
changed protected cell is covered by the two wildcard allowlist rows with
their reasons (docs/crosscheck_report.md).
"""
from __future__ import annotations

import csv
import json
import re

from tark_data import DATA, EVIDENCE_COLUMNS, LAPTOP_RE, load_evidence, product_keys

RESOLVED_ONE = ("exact", "form_only", "accession_in_text")


def accession_for(refs: list[dict], key: str) -> tuple[str, str | None]:
    """(accession column value, manifest local_path or None)."""
    ones = [r for r in refs if r["match"] in RESOLVED_ONE]
    many = [r for r in refs if r["match"] in ("range", "set")]
    if len(ones) == 1 and not many:
        return ones[0]["accession"], ones[0].get("local_path")
    total = len(ones) + sum(len(r["filings"]) for r in many)
    if total:
        return f"multiple ({total}), data/citations/{key}.json", None
    return "", None


def main() -> None:
    changed = 0
    for key in product_keys():
        cp = DATA / "citations" / f"{key}.json"
        cits = json.loads(cp.read_text())["cells"] if cp.exists() else {}
        rows = load_evidence(key)
        for r in rows:
            acc, local = accession_for(cits.get(r["cell_id"], []), key)
            before = (r.get("accession", ""), r.get("local_file", ""))
            r["accession"] = acc
            if LAPTOP_RE.search(r.get("local_file") or ""):
                r["local_file"] = local or ""
            changed += (r["accession"], r["local_file"]) != before
        with open(DATA / "evidence" / f"{key}_evidence.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=EVIDENCE_COLUMNS)
            w.writeheader()
            w.writerows(rows)
    sp = DATA / "series_annual" / "manifest.json"
    text = sp.read_text()
    new = re.sub(r"(?:/private/tmp|/Users|/tmp/claude)[^\s;,)\"]*", "(a local path, not in the repository)", text)
    if new != text:
        sp.write_text(new)
        changed += 1
    print(f"purge: {changed} evidence rows or notes changed")


if __name__ == "__main__":
    main()

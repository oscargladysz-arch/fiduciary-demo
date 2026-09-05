"""
Anonymization tokens: one source of truth
==========================================
The four reference plans are anonymized on every surface. The build refuses
to emit a bundle that leaks a sponsor token, and every test suite checks the
same list. Before this module, the build derived 5 tokens while two test
files listed 4 and never screened EINs or Form 5500 ack ids.

Tokens come from data/plans/*.json identity_private (sponsor, plan_name,
ein, ack_id). When P3-3 moves identities out of the public repo, this module
is the only place that changes.
"""
from __future__ import annotations

from pathlib import Path

from tark_data import load_plan, plan_keys

# generic corporate and plan words that legitimately appear in anonymized
# display labels (for example "tire & rubber manufacturer")
STOP = {"the", "inc", "inc.", "llc", "llp", "co", "co.", "company",
        "corporation", "corp", "corp.", "usa", "us", "group", "and", "of",
        "for", "plan", "trust", "savings", "profit", "sharing",
        "retirement", "employee", "employees", "bargaining", "unit",
        "restaurants", "tire", "rubber", "&", "(psrp)", "401(k)"}


def forbidden_tokens() -> list[str]:
    toks: set[str] = set()
    for k in plan_keys():
        ident = load_plan(k).get("identity_private", {}) or {}
        for field in ("sponsor", "plan_name"):
            for w in str(ident.get(field, "")).split():
                w = w.strip(",.()").lower()
                if w and len(w) > 3 and w not in STOP and not w.startswith("401("):
                    toks.add(w)
        for field in ("ein", "ack_id"):
            v = str(ident.get(field, "")).strip().lower()
            if v:
                toks.add(v)
    return sorted(toks)


def leaks(text: str) -> list[str]:
    """Tokens present in text (lowercased substring match)."""
    low = text.lower()
    return [t for t in forbidden_tokens() if t in low]


def docx_text(path: Path | str) -> str:
    """Plain text of a .docx: paragraphs plus every table cell."""
    from docx import Document
    d = Document(str(path))
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                parts.append(c.text)
    return "\n".join(parts)


if __name__ == "__main__":
    print(len(forbidden_tokens()), "forbidden tokens")

"""
Offline accession resolver (P1-D preparation, the first half of P2-10).
    python src/resolve_citations.py

For every evidence row whose source_doc names a filing (a form token and,
usually, a filed date), find the row in data/manifest.csv for the same
product with that form and filing date. Writes data/citations/<product>.json
(per cell: the references found, each resolved to accession, EDGAR URL and
local path, or left unresolved with the reason) and data/citations/summary.json.

Never invents an accession: a reference resolves only to a manifest row of
the same product and form, on the filed date when one is written, or to
the single held filing of that form when no date is written (flagged as
matched by form only). Anything else stays unresolved with the reason.
The online half (EDGAR submissions JSON for filings not in the manifest)
runs where sec.gov is reachable (P2-10).
"""
import csv
import json
import re
from collections import Counter
from pathlib import Path

from tark_data import DATA, load_evidence, load_products, product_keys

FORM_RE = re.compile(r"\b(N-CSRS|N-CSR|10-K/A|10-K|10-Q|424B3|424B5|486BPOS|486BXT|N-2/A|N-2-A|N-2|"
                     r"SC TO-I|N-23C3A|NPORT-P|8-K|N-CEN|DEF 14A|POS 8C|N-PX)\b")
FORM_ALIAS = {"N-2-A": "N-2/A"}
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
FILED_RE = re.compile(r"filed\s+(\d{4}-\d{2}-\d{2})")
# a range of filings of one form: "2024-09-06 through 2026-05-28", "2024-10-07..2026-07-02"
RANGE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*(?:through|to|\.\.|-)\s*(\d{4}-\d{2}-\d{2})")
# every date after a workflow verb is a workflow date (searched, pulled), not a filing date
WORKFLOW_RE = re.compile(r"\b(?:searched|searches|pulled|accessed|retrieved|run on)\b")
# a plural right after the form with no date cites the set of held filings of that form
SET_RE = re.compile(r"\s+(?:filings|notices)\b")
ACC_RE = re.compile(r"\b(\d{10}-\d{2}-\d{6})\b")
SPLIT_RE = re.compile(r";|\s\+\s")
RESOLVED = ("exact", "range", "set", "form_only")


def manifest() -> list[dict]:
    with open(DATA / "manifest.csv", newline="") as fh:
        return list(csv.DictReader(fh))


ALL_HELD_RE = re.compile(r"\ball\b[^.;]{0,40}\bfilings\b", re.I)


def references(source_doc: str) -> list[dict]:
    """The filing references written in one source_doc string. Each form
    token owns the text up to the next form token, so a compound citation
    ("N-CSR 2026-03-06, 486BPOS 2026-04-29") yields one reference per form
    with its own dates."""
    refs = []
    for frag in SPLIT_RE.split(source_doc or ""):
        toks = list(FORM_RE.finditer(frag))
        if not toks:
            if ALL_HELD_RE.search(frag) and not DATE_RE.search(WORKFLOW_RE.split(frag)[0]):
                # "all four on-disk filings": the set of every filing held for the product
                refs.append({"text": frag.strip(" ,;()"), "form": "*", "filed": [], "dates": [],
                             "range": None, "set": True, "accessions": []})
            continue
        prev = 0
        for i, m in enumerate(toks):
            end = toks[i + 1].start() if i + 1 < len(toks) else len(frag)
            seg = frag[prev:end]
            prev = end
            wf = WORKFLOW_RE.search(seg)
            clean = seg[:wf.start()] if wf else seg
            rng = RANGE_RE.search(clean)
            refs.append({"text": seg.strip(" ,;()"),
                         "form": FORM_ALIAS.get(m.group(1), m.group(1)),
                         "filed": FILED_RE.findall(clean),
                         "dates": DATE_RE.findall(clean),
                         "range": [rng.group(1), rng.group(2)] if rng else None,
                         "set": bool(SET_RE.match(frag, m.end())) and not DATE_RE.search(clean),
                         "accessions": ACC_RE.findall(seg)})
    return refs


def _row(r: dict) -> dict:
    return {"filing_date": r["filing_date"], "accession": r["accession"],
            "url": r["url"], "local_path": r["local_path"]}


def resolve(product: str, cik: str, ref: dict, rows: list[dict]) -> dict:
    form = ref["form"]
    out = {"text": ref["text"], "form": form}
    held = [r for r in rows if r["product"] == product and (form == "*" or r["form"] == form)]
    if ref["accessions"]:
        # R2-P0-1 (rule 15): the manifest wins. A filing of this form held on
        # the written date resolves the reference, and a number written in the
        # text that disagrees with it is flagged for the validator, never
        # used. A written number that matches no manifest row for the product
        # resolves nothing and gets no URL (the July placeholder accession
        # reached the live drawer as a 404 this way).
        acc = ref["accessions"][0]
        dated = [r for r in held if r["filing_date"] in (ref["filed"] or ref["dates"])]
        if len(dated) == 1 and dated[0]["accession"] != acc:
            return {**out, "match": "exact", **_row(dated[0]), "text_accession": acc,
                    "conflict": (f"the citation writes accession {acc} but the manifest's {form} "
                                 f"filed {dated[0]['filing_date']} is {dated[0]['accession']}. "
                                 "A validator error, not a resolution")}
        same = [r for r in rows if r["product"] == product and r["accession"] == acc]
        if same:
            return {**out, "match": "exact", **_row(same[0])}
        return {**out, "match": "unresolved", "text_accession": acc,
                "reason": (f"accession {acc} is written in the citation but is not a manifest row "
                           "for this product. No URL is built from an accession the manifest does "
                           "not hold")}
    if not held:
        return {**out, "match": "unresolved",
                "reason": f"no {form} filing for this product in data/manifest.csv"}
    if ref["range"]:
        lo, hi = ref["range"]
        inside = sorted((r for r in held if lo <= r["filing_date"] <= hi), key=lambda r: r["filing_date"])
        if inside:
            return {**out, "match": "range", "filings": [_row(r) for r in inside],
                    "reason": f"{len(inside)} {form} filings held between {lo} and {hi}"}
        return {**out, "match": "unresolved",
                "reason": f"no {form} filing held between {lo} and {hi}"}
    if ref["set"]:
        return {**out, "match": "set", "filings": [_row(r) for r in sorted(held, key=lambda r: r["filing_date"])],
                "reason": (f"cited as all filings held for the product, {len(held)} held" if form == "*"
                           else f"cited as the set of {form} filings, {len(held)} held")}
    dates = ref["filed"] or ref["dates"]
    hit = [r for r in held if r["filing_date"] in dates]
    if len(hit) == 1:
        return {**out, "match": "exact", **_row(hit[0])}
    if len(hit) > 1:
        return {**out, "match": "ambiguous",
                "reason": f"{len(hit)} {form} filings held on the written date(s)",
                "candidates": [_row(r) for r in hit]}
    if not dates and len(held) == 1:
        return {**out, "match": "form_only", **_row(held[0]),
                "reason": f"no date written, the only {form} filing held for this product"}
    if not dates:
        return {**out, "match": "ambiguous",
                "reason": f"no date written and {len(held)} {form} filings held",
                "candidates": [_row(r) for r in held]}
    return {**out, "match": "unresolved",
            "reason": f"{form} held on {', '.join(sorted(r['filing_date'] for r in held))}, "
                      f"not on the written date(s) {', '.join(dates)}"}


def run() -> dict:
    rows = manifest()
    ciks = {k: p["cik"] for k, p in load_products().items()}
    out_dir = DATA / "citations"
    out_dir.mkdir(exist_ok=True)
    totals: Counter = Counter()
    unresolved: list[dict] = []
    conflicts: list[dict] = []
    for key in product_keys():
        cells = {}
        for ev in load_evidence(key):
            refs = references(ev.get("source_doc", ""))
            if not refs:
                continue
            res = [resolve(key, ciks[key], r, rows) for r in refs]
            cells[ev["cell_id"]] = res
            for r in res:
                totals[r["match"]] += 1
                if r["match"] in ("unresolved", "ambiguous"):
                    unresolved.append({"product": key, "cell": ev["cell_id"], **r})
                if r.get("conflict"):
                    conflicts.append({"product": key, "cell": ev["cell_id"], **r})
        doc = {"product": key,
               "what": ("filing references in the evidence CSV resolved against data/manifest.csv, "
                        "offline. exact: form and filed date (or written accession) match one held "
                        "filing. range: every held filing of that form between the two written "
                        "dates. set: every held filing of that form when the citation names them "
                        "as a plural with no date. form_only: no date written, one such filing held. "
                        "An accession written in the citation resolves only when the manifest holds "
                        "it for this product, and one that disagrees with the manifest's filing on "
                        "the written date is a conflict for the validator. ambiguous and unresolved: "
                        "stated reason, no accession invented"),
               "cells": cells,
               "counts": dict(Counter(r["match"] for res in cells.values() for r in res))}
        (out_dir / f"{key}.json").write_text(json.dumps(doc, indent=2))
    summary = {"what": "offline accession resolution over every evidence row that names a filing",
               "references": sum(totals.values()), "counts": dict(totals),
               "unresolved": unresolved, "conflicts": conflicts}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    s = run()
    print(f"references {s['references']}: " + ", ".join(f"{k} {v}" for k, v in sorted(s["counts"].items())))
    for u in s["unresolved"][:12]:
        print(f"  {u['product']:18s} {u['cell']:5s} {u['match']:11s} {u['reason'][:80]}")
    for c in s.get("conflicts", []):
        print(f"  CONFLICT {c['product']:18s} {c['cell']:5s} {c['conflict'][:90]}")

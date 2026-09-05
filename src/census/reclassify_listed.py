"""
Share-class aware listing and the N-23C3A recency rule (P2-11)
    python src/census/reclassify_listed.py

The submissions oracle says whether SOME class of an entity trades on an
exchange. That is not the same as the common shares being listed, and an
interval fund that stopped filing N-23C3A years ago while its shares trade
on the NYSE is a listed closed-end fund today, not an interval fund. Rules,
applied offline to data/census/census.json and universe.json together:
  - every record gets `listed_common` and `listed_other_classes`. Where the
    submissions signal is unambiguous (not an interval fund, or an interval
    fund with no exchange listing) listed_common carries the signal and
    other classes are null with the reason that the census does not
    enumerate share classes.
  - an interval_23c3 record that is exchange-listed and whose last N-23C3A
    is more than RECENCY_MONTHS before the census as-of is reclassified to
    listed_cef, with the rule and the dates appended to its detection
    evidence. Reversible on a fresh N-23C3A.
  - an interval_23c3 record that is exchange-listed and still files
    N-23C3A keeps its class, and `listed` and `listed_common` become null
    with the reason: offline, the census cannot tell which share class is
    listed.
  - counts_by_class are recomputed in both files.
Idempotent. build_census.py calls apply() on a rebuild so the committed
state is reproducible.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
OUT = BASE / "data" / "census"
RECENCY_MONTHS = 24
NO_CLASSES = "the census does not enumerate share classes, only the entity's exchange status"
AMBIGUOUS = ("exchange-listed per SEC submissions while N-23C3A activity continues to {last}, and "
             "offline the census cannot tell which share class is listed")
RULE_TAG = "N-23C3A recency rule"


def months_before(as_of: str, months: int) -> str:
    y, m, d = (int(x) for x in as_of.split("-"))
    m -= months
    while m <= 0:
        m += 12
        y -= 1
    return f"{y:04d}-{m:02d}-{d:02d}"


def last_n23c3a(rec: dict) -> str | None:
    n = rec.get("n23c3a") or (rec.get("n23c3a_activity") or {}).get("value") or {}
    return n.get("last")


def _f(value, ref: str, as_of: str, reason: str | None = None) -> dict:
    out = {"value": value, "source": "submissions", "ref": ref, "as_of": as_of}
    if value is None:
        out["reason"] = reason or "unknown"
    return out


def apply(census: dict, universe: dict, months: int = RECENCY_MONTHS) -> dict:
    """Mutates both documents. Returns a summary."""
    as_of = census["as_of"]
    cutoff = months_before(as_of, months)
    reclassified, ambiguous = [], []
    cents, uents = census["entities"], universe["entities"]
    for cik, rec in cents.items():
        urec = uents.get(cik)
        signal = (rec.get("listed") or {}).get("value")
        as_of_rec = (rec.get("listed") or {}).get("as_of", as_of)
        ref = "company_tickers.json + submissions exchanges (OTC quotation excluded), common shares taken as the listed class"
        last = last_n23c3a(rec)
        if rec.get("wrapper_class") == "interval_23c3" and signal is True and last:
            if last < cutoff:
                note = (f"Reclassified by the {RULE_TAG}: last N-23C3A {last}, more than {months} months "
                        f"before the census as-of {as_of}, and the shares are exchange-listed per SEC "
                        "submissions, so the interval era ended and the fund is classed as a listed "
                        "closed-end fund. Reversible on a fresh N-23C3A.")
                for r in (rec, urec):
                    if r is None:
                        continue
                    r["wrapper_class"] = "listed_cef"
                    if not any(RULE_TAG in e for e in r["detection_evidence"]):
                        r["detection_evidence"] = list(r["detection_evidence"]) + [note]
                reclassified.append(cik)
                rec["listed_common"] = _f(True, ref, as_of_rec)
            else:
                reason = AMBIGUOUS.format(last=last)
                rec["listed"] = _f(None, rec["listed"]["ref"], as_of_rec, reason)
                rec["listed_common"] = _f(None, ref, as_of_rec, reason)
                if urec is not None:
                    urec["listed"] = None
                    urec["listed_reason"] = reason
                ambiguous.append(cik)
        elif signal is None:
            reason = (rec.get("listed") or {}).get("reason") or "listing unknown at enumeration"
            rec["listed_common"] = _f(None, ref, as_of_rec, reason)
        else:
            rec["listed_common"] = _f(bool(signal), ref, as_of_rec)
        rec["listed_other_classes"] = _f(None, ref, as_of_rec, NO_CLASSES)
        if urec is not None:
            urec["listed_common"] = rec["listed_common"]["value"]
            urec["listed_other_classes"] = None
            if rec["listed_common"]["value"] is None:
                urec["listed_common_reason"] = rec["listed_common"]["reason"]
    for doc in (census, universe):
        counts: dict[str, int] = {}
        for r in doc["entities"].values():
            counts[r["wrapper_class"]] = counts.get(r["wrapper_class"], 0) + 1
        doc["counts_by_class"] = dict(sorted(counts.items()))
    return {"cutoff": cutoff, "reclassified": reclassified, "ambiguous": ambiguous}


def main() -> None:
    cp, up = OUT / "census.json", OUT / "universe.json"
    census, universe = json.loads(cp.read_text()), json.loads(up.read_text())
    s = apply(census, universe)
    cp.write_text(json.dumps(census, indent=1))
    up.write_text(json.dumps(universe, indent=1))
    print(f"recency cutoff {s['cutoff']}: reclassified to listed_cef {s['reclassified']}, "
          f"listing left null {s['ambiguous']}, counts {census['counts_by_class']}")


if __name__ == "__main__":
    main()

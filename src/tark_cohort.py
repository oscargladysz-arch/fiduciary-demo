"""
Tark cohort engine (peer-comparison layer)
==========================================
Cohort membership is an ARGUED judgment (rationales live in the facts layer;
exclusions in data/roster_decisions.md). This module computes what a cohort
can honestly support:

  - cohort_stats(field): median/min/max over the members' structured facts,
    with n = count of members that HAVE the fact (nulls stay visible)
  - percentile_of / placement_line: R4-governed language — the word
    "percentile" is BANNED below n=4; small cohorts get
    "above/below cohort median (n=3)" phrasing, generated here and only here
  - composite returns at the cohort's honest granularity, equal-weight,
    refused entirely where members' pricing bases are heterogeneous
  - the comparability caveat block, assembled from data/cohorts/
    caveat_matrix.json (data, not prose-in-code)

Run:  python src/tark_cohort.py   -> data/cohorts/<id>.json
"""
from __future__ import annotations

import csv
import json
from statistics import median

from tark_data import DATA

# membership lives here (rationales in facts; exclusions in roster_decisions)
# cohorts from the one registry: label, ordered members and fallback note per
# cohort. Every member's own `cohort` field agrees (validate_registry).
def _cohorts_from_registry() -> dict:
    reg = json.loads((DATA / "registry.json").read_text())
    out = {}
    for cid, meta in reg["cohorts"].items():
        members = list(meta["members"])
        out[cid] = {"label": meta["label"], "members": members,
                    "wrapper_types": {k: reg["products"][k]["wrapper_type"] for k in members}}
        if meta.get("fallback_note"):
            out[cid]["fallback_note"] = meta["fallback_note"]
    return out


COHORTS = _cohorts_from_registry()

# fields the cohort stats layer summarizes (from structured facts)
STAT_FIELDS = ["mgmt_fee_pct", "expense_ratio_pct", "repurchase_cap_pct",
               "repurchase_cadence_per_year", "track_record_years",
               "net_assets_usd"]


def load_facts(key: str) -> dict:
    return json.loads((DATA / "facts" / f"{key}.json").read_text())["facts"]


def cohort_members(cohort_id: str) -> list[str]:
    return COHORTS[cohort_id]["members"]


def cohort_of(product_key: str) -> str | None:
    for cid, c in COHORTS.items():
        if product_key in c["members"]:
            return cid
    return None


def cohort_stats(cohort_id: str, field: str,
                 facts_by_key: dict[str, dict]) -> dict:
    values = {}
    missing = {}
    for k in cohort_members(cohort_id):
        f = facts_by_key[k].get(field, {})
        if f.get("value") is not None:
            values[k] = f["value"]
        else:
            missing[k] = f.get("reason", "no value")
    vs = sorted(values.values())
    return {
        "field": field, "n": len(vs),
        "median": round(median(vs), 4) if vs else None,
        "min": vs[0] if vs else None, "max": vs[-1] if vs else None,
        "values": values, "missing": missing,
    }


def percentile_of(product_key: str, cohort_id: str, field: str,
                  facts_by_key: dict[str, dict]) -> dict | None:
    """R4: percentile language only at n >= 4; below that, median-relative
    phrasing. Ties share one mid-rank percentile ((below + 0.5 * ties) / n),
    and a value equal to the median is the 50th percentile by definition, so
    no member can read as both "10th percentile" and "at the median" (the
    2026-08 record printed that contradiction in 10 cells). Returns
    {'phrase', 'n', ...} or None if the product lacks the fact."""
    st = cohort_stats(cohort_id, field, facts_by_key)
    if product_key not in st["values"]:
        return None
    v = st["values"][product_key]
    n = st["n"]
    med = st["median"]
    rel = "at" if v == med else "above" if v > med else "below"
    if n < 2:
        return {"phrase": f"only member with this fact (n={n})", "n": n,
                "value": v, "median": med}
    if n >= 4:
        values = list(st["values"].values())
        below = sum(1 for x in values if x < v)
        ties = sum(1 for x in values if x == v)
        pct = 50 if v == med else int((below + 0.5 * ties) / n * 100 + 0.5)
        return {"phrase": f"{pct}th percentile of cohort (n={n}), {rel} the "
                          f"median of {med:g}",
                "n": n, "percentile": pct, "value": v, "median": med,
                "ties": ties}
    return {"phrase": f"{rel} the cohort median of {med:g} (n={n}, too small "
                      f"for percentile language)",
            "n": n, "value": v, "median": med}


def _registry() -> dict:
    return json.loads((DATA / "registry.json").read_text())["products"]


def member_values(cohort_id: str, attr: str) -> tuple[dict[str, str], str]:
    """{member: value} for one comparability attribute, and where it came
    from. Typed per product (data/registry.json) when every member has the
    attribute typed, otherwise the wrapper-type attribute for every member,
    never a mix of the two vocabularies."""
    wts = COHORTS[cohort_id]["wrapper_types"]
    reg = _registry()
    typed = {k: (reg.get(k) or {}).get(attr) for k in wts}
    if typed and all(v is not None for v in typed.values()):
        return typed, "typed per product"
    attrs = json.loads((DATA / "cohorts" / "caveat_matrix.json").read_text())["wrapper_attributes"]
    return {k: attrs[w][attr] for k, w in wts.items()}, "by wrapper type"


def caveat_block(cohort_id: str) -> list[str]:
    """Comparability caveats that the members' own values support. A caveat
    fires only when the values differ across members. A wrapper-generic
    caveat that the typed facts contradict (five NAV-priced members, one
    pricing caveat) is not written."""
    matrix = json.loads((DATA / "cohorts" / "caveat_matrix.json").read_text())
    out = []
    for rule in matrix["pair_caveats"]:
        attr = rule["attrs"][0]
        values, basis = member_values(cohort_id, attr)
        if len(set(values.values())) > 1:
            detail = ", ".join(f"{k}: {v}" for k, v in sorted(values.items()))
            out.append(f"{rule['caveat']} [{basis}: {detail}]")
    fb = COHORTS[cohort_id].get("fallback_note")
    if fb:
        out.append(fb)
    return out


def _annual_returns(key: str) -> dict[str, float]:
    """{year: decimal return} from data/series_annual/<key>.csv."""
    p = DATA / "series_annual" / f"{key}.csv"
    if not p.exists():
        return {}
    out = {}
    with open(p, newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("total_return_pct"):
                out[r["fy_end"][:4]] = float(r["total_return_pct"]) / 100
    return out


def composite(cohort_id: str) -> dict:
    """Equal-weight annual composite — or an explicit refusal where members'
    pricing bases are heterogeneous (averaging premiums against appraisals
    would fabricate a series)."""
    wts = COHORTS[cohort_id]["wrapper_types"]
    values, _ = member_values(cohort_id, "pricing_class")
    bases = set(values.values())
    if len(bases) > 1:
        return {"refused": True,
                "reason": "members' pricing bases are heterogeneous (market "
                          "price vs NAV). An equal-weight composite would "
                          "average premium/discount dynamics against "
                          "appraisal NAVs, so it is refused, not fudged"}
    members = cohort_members(cohort_id)
    per = {k: _annual_returns(k) for k in members}
    years = sorted({y for m in per.values() for y in m})
    rows = []
    for y in years:
        have = {k: per[k][y] for k in members if y in per[k]}
        if len(have) >= 2:
            rows.append({"year": y,
                         "composite_return_pct": round(
                             sum(have.values()) / len(have) * 100, 2),
                         "n": len(have), "members": sorted(have)})
    return {"refused": False, "granularity": "annual (fiscal years as filed, with "
            "year-end months that differ across members and are disclosed per row)",
            "weighting": "equal-weight across members reporting that year",
            "rows": rows}


def build_cohorts() -> None:
    facts_by_key = {}
    for cid, c in COHORTS.items():
        for k in c["members"]:
            if k not in facts_by_key:
                facts_by_key[k] = load_facts(k)
    out_dir = DATA / "cohorts"
    out_dir.mkdir(exist_ok=True)
    for cid, c in COHORTS.items():
        doc = {
            "cohort_id": cid, "label": c["label"],
            "members": {k: {
                "wrapper_type": c["wrapper_types"][k],
                "depth": json.loads((DATA / "facts" / f"{k}.json")
                                    .read_text()).get("depth", "cohort"),
                "membership_rationale": json.loads(
                    (DATA / "facts" / f"{k}.json").read_text()).get(
                        "membership_rationale", ""),
            } for k in c["members"]},
            "n": len(c["members"]),
            "stats": {f: cohort_stats(cid, f, facts_by_key)
                      for f in STAT_FIELDS},
            "composite": composite(cid),
            "caveats": caveat_block(cid),
            "exclusion_log": "data/roster_decisions.md",
        }
        (out_dir / f"{cid}.json").write_text(json.dumps(doc, indent=2))
        comp = doc["composite"]
        print(f"{cid}: n={doc['n']}, composite="
              f"{'REFUSED' if comp.get('refused') else str(len(comp.get('rows', []))) + ' yrs'}, "
              f"caveats={len(doc['caveats'])}")


if __name__ == "__main__":
    build_cohorts()

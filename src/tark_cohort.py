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


def composite(cohort_id: str) -> dict:
    """The cohort's one member table (tark_periods): every period any member
    reports with each member's return and n, and an equal-weight composite
    return only where every member reports the period on the same basis.
    Refused entirely where members' pricing bases are heterogeneous or where
    members report on different year ends (rule 14). The engine's Slot G
    reads the same member table, leave-one-out."""
    from tark_periods import period_table
    members = cohort_members(cohort_id)
    values, _ = member_values(cohort_id, "pricing_class")
    if len(set(values.values())) > 1:
        return {"refused": True,
                "reason": "members' pricing bases are heterogeneous (market "
                          "price vs NAV). An equal-weight composite would "
                          "average premium/discount dynamics against "
                          "appraisal NAVs, so it is refused, not fudged",
                "rows": [], "member_source": {}}
    tbl = period_table(members)
    per = tbl["per_member"]
    kinds = {m: per[m]["period_kind"] for m in members}
    months = {m: per[m]["fy_end_month"] for m in members}
    rows = []
    for r in tbl["rows"]:
        have = [m for m in members if r["returns"][m] is not None]
        full = len(have) == len(members)
        rows.append({"period": r["period"], "label": r["label"], "period_kind": r["period_kind"],
                     "n": r["n"], "members": sorted(have), "returns": r["returns"],
                     "composite_return_pct": (round(sum(r["returns"][m] for m in have) / len(have), 2)
                                              if full and r["period_kind"] != "mixed" else None)})
    aligned = (len(set(kinds.values())) == 1 and "none" not in kinds.values()
               and len(set(months.values())) == 1)
    out = {"refused": False, "rows": rows,
           "member_source": {m: per[m]["source"] for m in members},
           "member_period_kind": kinds,
           "granularity": ("calendar years, identical start and end dates for every member"
                           if aligned and kinds[members[0]] == "calendar_year" else
                           "fiscal years to the same month for every member"
                           if aligned else "mixed year ends: no common period, composite returns not formed"),
           "weighting": "equal-weight, only over periods every member reports on the same basis"}
    if not aligned:
        out["composite_refused_reason"] = (
            "members report on different year ends (" + ", ".join(
                f"{m}: {'calendar years' if kinds[m] == 'calendar_year' else 'fiscal years to month ' + str(months[m]) if kinds[m] == 'fiscal_year' else 'no period returns'}"
                for m in members) + "), so no equal-weight composite return is formed. The table shows each member's own periods with n")
    return out


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

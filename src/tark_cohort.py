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
COHORTS = {
    "private_credit": {
        "label": "Private credit (interval fund + non-traded BDC)",
        "members": ["cliffwater_cclfx", "bcred", "pflex"],
        "wrapper_types": {"cliffwater_cclfx": "interval_23c3",
                          "bcred": "nontraded_bdc", "pflex": "interval_23c3"},
    },
    "evergreen_pe": {
        "label": "Evergreen private equity ('40-Act funds + '34-Act conglomerate)",
        "members": ["hl_paf", "stepstone_spm", "kkr_kpec", "ares_pmf",
                    "amg_pantheon"],
        "wrapper_types": {"hl_paf": "tender_offer", "stepstone_spm": "tender_offer",
                          "kkr_kpec": "nontraded_llc", "ares_pmf": "tender_offer",
                          "amg_pantheon": "tender_offer"},
        "fallback_note": "kkr_kpec joins under the authorized fallback: its "
                         "structural twins are Reg D vehicles with no public "
                         "filings (data/roster_decisions.md - 'The kkr_kpec "
                         "ruling'). Cross-wrapper caveats apply.",
    },
    "nontraded_reit": {
        "label": "Non-traded NAV REITs",
        "members": ["breit", "sreit", "jll_ipt"],
        "wrapper_types": {"breit": "nontraded_reit", "sreit": "nontraded_reit",
                          "jll_ipt": "nontraded_reit"},
    },
    "venture": {
        "label": "Pre-IPO / venture growth (listed CEF + listed BDC + interval fund)",
        "members": ["dxyz", "ssss", "arkvx"],
        "wrapper_types": {"dxyz": "listed_cef", "ssss": "listed_bdc",
                          "arkvx": "interval_23c3"},
    },
}

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
    phrasing. Returns {'phrase', 'n', ...} or None if the product lacks the
    fact."""
    st = cohort_stats(cohort_id, field, facts_by_key)
    if product_key not in st["values"]:
        return None
    v = st["values"][product_key]
    n = st["n"]
    if n < 2:
        return {"phrase": f"only member with this fact (n={n})", "n": n,
                "value": v, "median": st["median"]}
    if n >= 4:
        below = sum(1 for x in st["values"].values() if x < v)
        pct = round((below + 0.5) / n * 100)
        rel = ("at" if v == st["median"] else
               "above" if v > st["median"] else "below")
        return {"phrase": f"{pct}th percentile of cohort (n={n}), {rel} the "
                          f"median of {st['median']:g}",
                "n": n, "percentile": pct, "value": v, "median": st["median"]}
    rel = ("at" if v == st["median"] else
           "above" if v > st["median"] else "below")
    return {"phrase": f"{rel} the cohort median of {st['median']:g} (n={n} — "
                      f"too small for percentile language)",
            "n": n, "value": v, "median": st["median"]}


def caveat_block(cohort_id: str) -> list[str]:
    matrix = json.loads((DATA / "cohorts" / "caveat_matrix.json").read_text())
    attrs = matrix["wrapper_attributes"]
    wts = COHORTS[cohort_id]["wrapper_types"]
    out = []
    for rule in matrix["pair_caveats"]:
        attr = rule["attrs"][0]
        distinct = {attrs[w][attr] for w in wts.values()}
        if len(distinct) > 1:
            detail = "; ".join(f"{k}: {attrs[w][attr]}"
                               for k, w in sorted(wts.items()))
            out.append(f"{rule['caveat']} [{detail}]")
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
    matrix = json.loads((DATA / "cohorts" / "caveat_matrix.json").read_text())
    attrs = matrix["wrapper_attributes"]
    wts = COHORTS[cohort_id]["wrapper_types"]
    bases = {attrs[w]["pricing_class"] for w in wts.values()}
    if len(bases) > 1:
        return {"refused": True,
                "reason": "members' pricing bases are heterogeneous (market "
                          "price vs NAV); an equal-weight composite would "
                          "average premium/discount dynamics against "
                          "appraisal NAVs - refused, not fudged"}
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
    return {"refused": False, "granularity": "annual (fiscal years as filed; "
            "year-end months differ across members and are disclosed per row)",
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

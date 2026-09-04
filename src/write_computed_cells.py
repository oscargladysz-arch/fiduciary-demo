"""
Engine-derived cells: one writer, owned cells only
===================================================
Several cells restate the pipeline's own outputs as evidence (status
`computed`). Until now no committed script produced that prose, so it went
stale (cell 5.4 still described the roster of the first build). This module is the
only writer of those cells.

Guard rails:
- OWNED lists the cells this writer may touch. It refuses any target whose
  current status kind is not `computed`, `n/a` or `pending`. T2 evidence is
  never overwritten.
- Each owned cell is a machine sentence built from the artifact it cites,
  plus an optional analyst note carried verbatim from data/notes/<key>.json,
  so judgment written by a person is not lost in regeneration.
- extracted_by names this script and the record as-of date (never the wall
  clock, never a git sha: the freshness gate must reproduce the file
  byte-for-byte on any commit).
- Idempotent: a second run with the same inputs changes nothing.
- Writes the product JSON and the evidence CSV together.

Run: python src/write_computed_cells.py [--only 5.4,2.9] [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from tark_data import (CELLS, DATA, EVIDENCE_COLUMNS, load_evidence,
                       load_product, product_keys, record_as_of, status_kind)

WRITABLE_KINDS = ("computed", "n/a", "pending")


def analyst_note(key: str, cid: str) -> str:
    p = DATA / "notes" / f"{key}.json"
    if not p.exists():
        return ""
    return str(json.loads(p.read_text()).get("cells", {}).get(cid, "")).strip()


def _cohort_for(key: str) -> tuple[str | None, dict | None]:
    fp = DATA / "facts" / f"{key}.json"
    if not fp.exists():
        return None, None
    cid = json.loads(fp.read_text()).get("cohort_id")
    cp = DATA / "cohorts" / f"{cid}.json" if cid else None
    if not cp or not cp.exists():
        return cid, None
    return cid, json.loads(cp.read_text())


# --------------------------------------------------------------- producers
def cell_5_4(key: str) -> dict | None:
    """Peer universe and returns, from the cohort artifact."""
    cid, co = _cohort_for(key)
    if not co:
        return None
    members = list(co["members"].keys())
    comp = co.get("composite") or {}
    if comp.get("refused"):
        comp_txt = f"Composite REFUSED: {comp.get('reason', '').rstrip('.')}."
    else:
        rows = comp.get("rows", [])
        years = ", ".join(f"{r['year']} (n={r['n']})" for r in rows)
        comp_txt = ("Equal-weight annual composite on printed fiscal-year returns "
                    "for years with 2 or more reporting members: "
                    + (years if years else "none, no year has 2 reporting members")
                    + ".")
    wrappers = sorted({m["wrapper_type"] for m in co["members"].values()})
    n_cav = len(co.get("caveats") or [])
    text = (f"Peer cohort {cid} (n={co['n']}: {', '.join(members)}). {comp_txt} "
            f"Wrapper types in the cohort: {', '.join(wrappers)}. "
            f"Cross-wrapper differences are disclosed in the cohort caveat block "
            f"({n_cav} caveat{'s' if n_cav != 1 else ''}). Membership rationales are "
            f"in data/facts, exclusions in data/roster_decisions.md.")
    note = analyst_note(key, "5.4")
    if note:
        text += f" Analyst note: {note}"
    return {"value": text, "source": f"data/cohorts/{cid}.json",
            "section": "members, composite and caveats blocks", "quote": ""}


def cell_2_9(key: str) -> dict | None:
    """Fee peer percentile: cohort placement on three typed facts, phrased by
    tark_cohort.percentile_of (the R4 phrasing law lives there and only
    there)."""
    import tark_cohort
    cid, co = _cohort_for(key)
    if not co:
        return None
    members = list(co["members"].keys())
    facts_by_key = {m: tark_cohort.load_facts(m) for m in members
                    if (DATA / "facts" / f"{m}.json").exists()}
    parts = []
    for label, field in (("mgmt fee", "mgmt_fee_pct"),
                         ("expense ratio (bases differ, see notes)", "expense_ratio_pct"),
                         ("repurchase cap", "repurchase_cap_pct")):
        pl = tark_cohort.percentile_of(key, cid, field, facts_by_key)
        parts.append(f"{label}: {pl['phrase'] if pl else 'fact unavailable for this member'}")
    text = (f"Cohort placement ({cid}, R4 phrasing): " + " | ".join(parts)
            + f". Stats and per-member values in data/cohorts/{cid}.json, "
              f"membership rationales in data/facts.")
    note = analyst_note(key, "2.9")
    if note:
        text += f" Analyst note: {note}"
    return {"value": text, "source": f"data/cohorts/{cid}.json",
            "section": "stats block (R4 phrasing by tark_cohort.percentile_of)",
            "quote": ""}


def cell_5_6(key: str) -> dict | None:
    """Benchmark suitability: the selection artifact restated as one cell.
    Every figure is the engine's own output, nothing is extracted here."""
    sp = DATA / "benchmarks" / f"{key}_selection.json"
    if not sp.exists():
        return None
    sel = json.loads(sp.read_text())
    ma = sel.get("max_attainable")
    ma_txt = (f"Max attainable on held data {ma}/12." if ma is not None
              else "No candidate is eligible, so no maximum is attainable on held data.")
    parts = [f"Benchmark suitability (rubric {sel.get('rubric_version', 'v2')}, engine output)."]
    if sel.get("escalation"):
        parts.append(f"ESCALATED: {sel['escalation'].rstrip('.')}.")
    else:
        pr = sel["primary"]
        comp = pr.get("comparison") or {}
        line = f"Primary {pr['candidate']} ({pr['lane']} lane) scored {pr['score']}/{pr['max']}"
        if comp:
            line += (f" with a {comp['kind']} comparison over {comp['window']}: "
                     f"KS-PME {comp['ks_pme']}, Direct Alpha {comp['direct_alpha_pct']}%/yr")
            if comp.get("low_confidence"):
                line += f" ({comp['low_confidence']})"
        else:
            note = pr.get("comparison_note") or sel.get("comparison_note") or "not computable on held data"
            line += f", comparison not computable ({note.rstrip('.')})"
        parts.append(line + ".")
        sec = sel.get("secondary")
        parts.append(f"Secondary {sec['candidate']} scored {sec['score']}/{sec['max']}." if sec
                     else f"No eligible secondary ({sel.get('secondary_note') or 'none'}).")
    parts.append(ma_txt)
    decl = sel.get("declared_benchmarks") or []
    if decl:
        parts.append("Fund-declared benchmark(s) (cell 5.1): "
                     + ", ".join(f"{d['name']}: {d['status']}" for d in decl) + ".")
    elif sel.get("declared_none_reason"):
        parts.append(f"Declared benchmark: none ({sel['declared_none_reason']}).")
    parts.append(f"Rejected: {len(sel.get('rejected', []))} candidates, each with its reason in "
                 "the ledger. Methodology: docs/benchmark_methodology.md.")
    text = " ".join(parts)
    note = analyst_note(key, "5.6")
    if note:
        text += f" Analyst note: {note}"
    return {"value": text, "source": f"data/benchmarks/{key}_selection.json",
            "section": "primary, secondary, escalation, max_attainable, declared_benchmarks, rejected",
            "quote": ""}


def _selection(key: str) -> dict | None:
    sp = DATA / "benchmarks" / f"{key}_selection.json"
    return json.loads(sp.read_text()) if sp.exists() else None


def _matches(key: str) -> list[tuple[str, str, dict]]:
    """(plan_key, plan label, match) for every reference plan, in plan order."""
    from tark_data import load_plan, plan_keys
    out = []
    for pl in plan_keys():
        mp = DATA / "liquidity" / f"{pl}__{key}_match.json"
        if mp.exists():
            out.append((pl, load_plan(pl)["display_label"], json.loads(mp.read_text())))
    return out


def _signed(x: float) -> str:
    return f"{x:+g}"


def cell_1_8(key: str) -> dict | None:
    """Risk-adjusted metrics: the primary comparison of the selection artifact."""
    sel = _selection(key)
    if not sel:
        return None
    src = f"data/benchmarks/{key}_selection.json"
    if sel.get("escalation"):
        text = ("No KS-PME or Direct Alpha computable: " + sel["escalation"].rstrip(".")
                + ". The escalation is documented in the selection artifact.")
        return {"value": text, "source": src, "section": "escalation", "quote": ""}
    pr = sel["primary"]
    comp = pr.get("comparison") or {}
    if not comp:
        return None
    parts = [f"KS-PME {comp['ks_pme']} and Direct Alpha {_signed(comp['direct_alpha_pct'])}%/yr vs "
             f"{pr['candidate']} over {comp['window']} ({comp['kind']} comparison"
             + (f", {comp['window_note']}" if comp.get("window_note") else "") + ")."]
    parts.append(f"Fund growth {comp['fund_growth_x']}x vs benchmark {comp['index_growth_x']}x on "
                 "two-point flows (one contribution at the window start, one valuation at the end).")
    parts.append("The fund lagged the benchmark over this window." if comp["ks_pme"] < 1
                 else "The fund led the benchmark over this window.")
    if comp.get("low_confidence"):
        lc = comp["low_confidence"]
        parts.append(lc[0].upper() + lc[1:].rstrip(".") + ".")
    if comp.get("alignment_note"):
        parts.append(comp["alignment_note"].rstrip(".") + ".")
    sec = sel.get("secondary")
    sc = (sec or {}).get("comparison") or {}
    if sc:
        parts.append(f"Secondary {sec['candidate']}: KS-PME {sc['ks_pme']}, Direct Alpha "
                     f"{_signed(sc['direct_alpha_pct'])}%/yr over {sc['window']}.")
    for slot in (comp, sc):
        if slot.get("ks_pme_monthly_schedule") is not None:
            parts.append(f"ILLUSTRATIVE monthly-schedule KS-PME {slot['ks_pme_monthly_schedule']} "
                         f"({slot['schedule_contributions']} equal contributions), the two-point figure is primary.")
            break
    parts.append("Window-sensitive: PME and alpha on appraisal-lagged NAVs move with the window "
                 "(methodology section 3).")
    text = " ".join(parts)
    note = analyst_note(key, "1.8")
    if note:
        text += f" Analyst note: {note}"
    return {"value": text, "source": src, "section": "primary.comparison, secondary.comparison", "quote": ""}


def cell_1_9(key: str) -> dict | None:
    """Stress-window performance from the supplement's stress_windows block."""
    sp = DATA / "analytics" / "supplement.json"
    if not sp.exists():
        return None
    sw = (json.loads(sp.read_text()).get("stress_windows") or {}).get(key)
    if not sw:
        return None
    src = "data/analytics/supplement.json"
    if "cy2022_rate_shock" in sw or "covid_feb_apr_2020" in sw:
        parts = [f"Computed stress-window performance from {sw.get('series', 'the held series')} "
                 "(adjusted close, distributions reinvested)."]
        labels = (("cy2022_rate_shock", "CY2022 rate shock"), ("covid_feb_apr_2020", "COVID (Feb to Apr 2020)"))
        for k2, label in labels:
            w = sw.get(k2)
            if w:
                parts.append(f"{label}: total return {w['return_pct']}%, max drawdown {w['max_drawdown_pct']}%.")
        if sw.get("worst_peak_to_trough_full_history_pct") is not None:
            parts.append(f"Worst full-history peak-to-trough {sw['worst_peak_to_trough_full_history_pct']}%.")
        return {"value": " ".join(parts), "source": src, "section": f"stress_windows.{key}", "quote": ""}
    parts = [f"Stress observation from printed fiscal-year returns ({sw.get('series', 'data/series_annual')})."]
    fy = sw.get("fy_spanning_2022_shock")
    if fy:
        parts.append(f"The fiscal year spanning the 2022 public-market drawdown (FY ending {fy['fy_end']}) "
                     f"printed a total return of {fy['return_pct']}%.")
    wf = sw.get("worst_disclosed_fy")
    if wf:
        parts.append(f"Worst disclosed fiscal year: FY ending {wf['fy_end']} at {wf['return_pct']}%.")
    if sw.get("note"):
        parts.append(sw["note"][0].upper() + sw["note"][1:].rstrip(".") + ".")
    parts.append("CAVEAT: annual appraisal-based figures cannot show intra-year drawdowns, so this is "
                 "a floor on the stress the wrapper absorbed, not a measure of it.")
    return {"value": " ".join(parts), "source": src, "section": f"stress_windows.{key}", "quote": ""}


def cell_3_8(key: str) -> dict | None:
    """ILLUSTRATIVE redemption stress test across the four reference plans."""
    ms = _matches(key)
    if not ms:
        return None
    src = f"data/liquidity/{ms[0][0]}__{key}_match.json"
    section = "stressed_scenario and scenario across the four plan match files"
    first = ms[0][2]
    if first["wrapper_facts"].get("exchange"):
        return {"value": ("Redemption stress test not applicable: the wrapper is exchange-traded with "
                          "continuous dealing, so there is no wrapper capacity to stress. Exit is at the "
                          "market price, whose premium or discount to NAV is the relevant risk (cell 1.10)."),
                "source": src, "section": section, "quote": ""}
    sc, ss = first["scenario"], first["stressed_scenario"]
    parts = [f"ILLUSTRATIVE redemption stress test (computed for all four reference plans): "
             f"{ss['assumptions']}, default sliders allocation {sc['allocation_pct_of_plan']:g}% of plan, "
             f"tail turnover {sc['tail_annual_turnover_pct']:g}%/yr, active turnover "
             f"{sc['active_annual_turnover_pct']:g}%/yr."]
    for _, label, m in ms:
        s2 = m["stressed_scenario"]
        cap = s2.get("annual_wrapper_capacity_pct")
        parts.append(f"{label}: stressed demand {s2['demand_pct_of_position']}% of the position vs "
                     f"{cap:g}% annual wrapper capacity, {s2['outcome'].rstrip('.')}.")
    parts.append("Proration assumption: an oversubscribed offer is filled pro rata and the unfilled "
                 "remainder waits for the next window.")
    return {"value": " ".join(parts), "source": src, "section": section, "quote": ""}


def cell_3_9(key: str) -> dict | None:
    """Product-to-plan liquidity match: structural verdict plus per-plan scenario verdicts."""
    ms = _matches(key)
    if not ms:
        return None
    first = ms[0][2]
    src = f"data/liquidity/{ms[0][0]}__{key}_match.json"
    verdict = first["verdict"].upper()
    missing = first.get("missing_facts") or []
    head = (f"Structural liquidity verdict {verdict} (typed facts, cells 3.1, 3.3, 2.7, plan-independent"
            + (", facts missing: " + ", ".join(missing) if missing else "") + ").")
    per_plan = ", ".join(f"{label}: {(m.get('scenario_verdict') or 'not computable')}" for _, label, m in ms)
    parts = [head, f"Scenario verdicts (ILLUSTRATIVE, default sliders) by reference plan: {per_plan}."]
    for r in first.get("structural_reasons") or []:
        parts.append(r.rstrip(".") + ".")
    parts.append("Per-plan reasons, capacity and stressed outcomes are in the liquidity match artifacts "
                 "and on the Liquidity view.")
    return {"value": " ".join(parts), "source": src,
            "section": "verdict, scenario_verdict, missing_facts, structural_reasons across the four plan match files",
            "quote": ""}


def cell_5_3(key: str) -> dict | None:
    """Every benchmark candidate the engine scored, with its outcome."""
    sel = _selection(key)
    if not sel:
        return None
    src = f"data/benchmarks/{key}_selection.json"
    parts = [f"Benchmark candidates evaluated by the engine (rubric {sel.get('rubric_version', 'v2')}, "
             "threshold 7 of 12, strategy gate below 2 of 3 ineligible)."]
    if sel.get("escalation"):
        parts.append("ESCALATED: " + sel["escalation"].rstrip(".") + ".")
    else:
        pr = sel["primary"]
        parts.append(f"PRIMARY {pr['candidate']} {pr['score']}/{pr['max']} ({pr['lane']} lane).")
        sec = sel.get("secondary")
        parts.append(f"SECONDARY {sec['candidate']} {sec['score']}/{sec['max']} ({sec['lane']} lane)."
                     if sec else f"No eligible secondary ({sel.get('secondary_note') or 'none'}).")
    for r in sel.get("rejected", []):
        parts.append(f"REJECTED {r['candidate']} {r['score']}/{r['max']} ({r['lane']} lane): "
                     + r["rejection"].rstrip(".") + ".")
    decl = sel.get("declared_benchmarks") or []
    if decl:
        parts.append("Fund-declared (cell 5.1): " + ", ".join(f"{d['name']} ({d['status']})" for d in decl) + ".")
    elif sel.get("declared_none_reason"):
        parts.append(f"Fund-declared benchmark: none ({sel['declared_none_reason']}).")
    return {"value": " ".join(parts), "source": src,
            "section": "primary, secondary, rejected, declared_benchmarks", "quote": ""}


def cell_5_5(key: str) -> dict | None:
    """PME inputs of the primary comparison, stated as the formula."""
    sel = _selection(key)
    if not sel:
        return None
    src = f"data/benchmarks/{key}_selection.json"
    if sel.get("escalation"):
        return {"value": "No PME inputs constructible: " + sel["escalation"].rstrip(".") + ".",
                "source": src, "section": "escalation", "quote": ""}
    pr = sel["primary"]
    comp = pr.get("comparison") or {}
    if not comp:
        return None
    parts = [f"PME inputs (computed, primary comparison vs {pr['candidate']}): window {comp['window']} "
             f"({comp['kind']} comparison" + (f", {comp['window_note']}" if comp.get("window_note") else "") + ")."]
    parts.append(f"Fund growth {comp['fund_growth_x']}x vs benchmark growth {comp['index_growth_x']}x, "
                 "flows = one contribution of 1 at the window start and the terminal growth at the end, "
                 f"benchmark series {pr.get('series_id')}.")
    parts.append(f"KS-PME {comp['ks_pme']} = fund growth / benchmark growth. Direct Alpha "
                 f"{_signed(comp['direct_alpha_pct'])}%/yr is the annualized form of the same two flows "
                 f"(fund {comp['fund_ann_pct']}%/yr vs benchmark {comp['index_ann_pct']}%/yr).")
    if comp.get("alignment_note"):
        parts.append(comp["alignment_note"].rstrip(".") + ".")
    if comp.get("ks_pme_monthly_schedule") is not None:
        parts.append(f"ILLUSTRATIVE monthly-schedule KS-PME {comp['ks_pme_monthly_schedule']} "
                     f"({comp['schedule_contributions']} equal contributions at the window start and each "
                     "month-end inside it, valued at the window end).")
    return {"value": " ".join(parts), "source": src, "section": "primary.comparison", "quote": ""}


OWNED = {
    "1.8": cell_1_8,
    "1.9": cell_1_9,
    "2.9": cell_2_9,
    "3.8": cell_3_8,
    "3.9": cell_3_9,
    "5.3": cell_5_3,
    "5.4": cell_5_4,
    "5.5": cell_5_5,
    "5.6": cell_5_6,
}
# these six restate engine outputs that already exist as computed cells. The
# writer regenerates them where they are computed and never turns an n/a,
# pending or evidence row into a computed one (coverage totals do not move).
REGENERATE_ONLY = {"1.8", "1.9", "3.8", "3.9", "5.3", "5.5"}


# ------------------------------------------------------------------ writer
def write_cell(key: str, cid: str, new: dict, as_of: str,
               product: dict, ev_rows: list[dict]) -> bool:
    cell = product["cells"][cid]
    kind = status_kind(str(cell.get("status", "pending")))
    if kind not in WRITABLE_KINDS:
        raise SystemExit(f"refusing to overwrite {key} {cid}: status kind "
                         f"'{kind}' is evidence, not an engine output")
    record = {
        "element": CELLS[cid],
        "value": new["value"],
        "status": "computed",
        "source": new["source"],
        "section": new.get("section", ""),
        "quote": new.get("quote", ""),
        "extracted_by": f"src/write_computed_cells.py (as-of {as_of})",
        "verified_by": "",
    }
    changed = any(cell.get(k) != v for k, v in record.items())
    product["cells"][cid] = record
    for r in ev_rows:
        if r["cell_id"] == cid:
            row = {"cell_id": cid, "element": CELLS[cid], "value": new["value"],
                   "source_doc": new["source"],
                   "source_section": new.get("section", ""),
                   "quote": new.get("quote", ""), "local_file": "",
                   "date_pulled": as_of,
                   "extracted_by": record["extracted_by"], "verified_by": "",
                   "status": "computed"}
            changed = changed or any(r.get(k) != v for k, v in row.items())
            r.update(row)
    return changed


def run(only: set[str] | None = None, dry_run: bool = False) -> int:
    as_of = record_as_of()
    total = 0
    for key in product_keys():
        product = load_product(key)
        ev_rows = load_evidence(key)
        touched = []
        for cid, producer in OWNED.items():
            if only and cid not in only:
                continue
            kind = status_kind(str(product["cells"][cid].get("status", "pending")))
            if kind not in WRITABLE_KINDS or (cid in REGENERATE_ONLY and kind != "computed"):
                continue        # evidence, or a documented n/a, is left as it is
            new = producer(key)
            if new is None:
                continue
            if write_cell(key, cid, new, as_of, product, ev_rows):
                touched.append(cid)
        if touched and not dry_run:
            (DATA / "products" / f"{key}.json").write_text(
                json.dumps(product, indent=2, ensure_ascii=False) + "\n")
            with open(DATA / "evidence" / f"{key}_evidence.csv", "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=EVIDENCE_COLUMNS)
                w.writeheader()
                w.writerows(ev_rows)
        total += len(touched)
        print(f"{key:<18} {'would write' if dry_run else 'wrote'} "
              f"{', '.join(touched) if touched else 'nothing (unchanged)'}")
    return total


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="comma-separated cell ids")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    only = {c for c in a.only.split(",") if c}
    n = run(only or None, a.dry_run)
    print(f"{n} owned cell(s) {'would change' if a.dry_run else 'changed'}")


if __name__ == "__main__":
    main()

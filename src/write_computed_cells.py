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
from tark_benchmark_common import (BY_DESCRIPTOR_SENTENCE, MIN_PRIMARY_SCORE, RUBRIC_MAX,
                                   STRATEGY_GATE_MIN, TIE_SENTENCE, x_of_n)
from tark_display import (COMPUTED_WRITER_LABEL, RUBRIC_LABEL, WRAPPER_LABEL, cohort_label,
                          lane_label)


def _fund_short(key: str) -> str:
    return load_product(key)["fund_name"].split(" (")[0]

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
    members = [_fund_short(m) for m in co["members"].keys()]
    comp = co.get("composite") or {}
    if comp.get("refused"):
        comp_txt = f"Composite REFUSED: {comp.get('reason', '').rstrip('.')}."
    elif comp.get("composite_refused_reason"):
        comp_txt = ("No composite return is formed: " + comp["composite_refused_reason"].rstrip(".")
                    + ". Periods on record, n = members reporting: "
                    + ", ".join(f"{r['label']} (n={r['n']})" for r in comp.get("rows", [])) + ".")
    else:
        rows = comp.get("rows", [])
        full = [r for r in rows if r.get("composite_return_pct") is not None]
        comp_txt = (f"Member table on {comp.get('granularity', 'aligned periods')}, {comp.get('weighting', '')}: "
                    + (", ".join(f"{r['label']} (n={r['n']}, composite {r['composite_return_pct']:g}%)" for r in full)
                       if full else "no period is reported by every member")
                    + ". The fund's own leave-one-out comparison is cell 1.12.")
    wrappers = sorted({WRAPPER_LABEL.get(m["wrapper_type"], m["wrapper_type"]) for m in co["members"].values()})
    n_cav = len(co.get("caveats") or [])
    text = (f"Peer cohort: {cohort_label(cid)} (n={co['n']}: {', '.join(members)}). {comp_txt} "
            f"Wrapper types in the cohort: {', '.join(wrappers)}. "
            f"Cross-wrapper differences are disclosed in the cohort caveat block "
            f"({n_cav} caveat{'s' if n_cav != 1 else ''}). Membership rationales and "
            "exclusions are in the roster decisions record.")
    note = analyst_note(key, "5.4")
    if note:
        text += f" Analyst note: {note}"
    return {"value": text, "source": f"cohort artifact ({cohort_label(cid)})",
            "section": "members, composite and caveats", "quote": ""}


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
    text = (f"Cohort placement ({cohort_label(cid)}): " + " | ".join(parts)
            + ". Statistics and per-member values are in the cohort artifact, membership "
              "rationales in the typed facts.")
    note = analyst_note(key, "2.9")
    if note:
        text += f" Analyst note: {note}"
    return {"value": text, "source": f"cohort artifact ({cohort_label(cid)})",
            "section": "statistics (mid-rank percentile phrasing)",
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


def _lane_a_sentences(sel: dict) -> list[str]:
    """One sentence per declared benchmark or SEC-required comparator (cell
    5.1), typed, with its own computed comparison where the index has a
    held series (R2-P1-5)."""
    out = []
    for d in sel.get("declared") or []:
        head = f"{d['type_label'][0].upper()}{d['type_label'][1:]} {d['name']} (cell 5.1): {d['status']}"
        c = d.get("comparison")
        if c and c["kind"] == "series":
            head += (f". Fund vs {d['name']}: KS-PME {c['ks_pme']} and Direct Alpha {_signed(c['direct_alpha_pct'])}%/yr "
                     f"over {c['window']}, fund return source: {c['fund_return_source']}")
        elif c:
            head += (f". Fund vs {d['name']}: relative wealth ratio {c['relative_wealth_ratio']} over {c['window']}, "
                     f"fund return source: {c['fund_return_source']}")
        elif d.get("comparison_note"):
            head += f". No comparison: {d['comparison_note'].rstrip('.')}"
        out.append(head + ".")
    if not out and sel.get("declared_none_reason"):
        out.append(f"Declared benchmark: none ({sel['declared_none_reason'].rstrip('.')}).")
    return out


def _series_sentence(label: str, cand: str, c: dict) -> str:
    return (f"{label} {cand}: KS-PME {c['ks_pme']} and Direct Alpha {_signed(c['direct_alpha_pct'])}%/yr "
            f"over {c['window']} (series comparison" + (f", {c['window_note']}" if c.get("window_note") else "")
            + f"), fund growth {c['fund_growth_x']}x vs proxy growth {c['index_growth_x']}x on two-point flows "
            "(one contribution at the window start, one valuation at the end), fund return source: "
            f"{c['fund_return_source']}. "
            + ("The fund lagged the public proxy over this window." if c["ks_pme"] < 1
               else "The fund led the public proxy over this window."))


def _ratio_sentence(label: str, cand: str, c: dict) -> str:
    return (f"{label} {cand}: relative wealth ratio {c['relative_wealth_ratio']} over {c['window']} "
            f"({c['window_note']}), fund growth {c['fund_growth_x']}x / comparator growth {c['index_growth_x']}x "
            f"on two-point flows, annualized excess return {_signed(c['excess_return_pct'])}%/yr, fund return "
            f"source: {c['fund_return_source']}. {c['not_pme_note']} Alignment: {c['alignment_note'].rstrip('.')}.")


def cell_1_8(key: str) -> dict | None:
    """Risk-adjusted metrics: Slot K's comparison named for its comparator,
    the reference comparison when Slot K has no number, and every Lane A
    comparison (decision 7.1, rule 12)."""
    sel = _selection(key)
    if not sel:
        return None
    src = f"benchmark selection artifact ({_fund_short(key)})"
    sk = sel["slot_k"]
    parts: list[str] = []
    lows: list[str] = []
    sched: str | None = None
    if sk.get("escalation"):
        parts.append("No KS-PME or Direct Alpha computable for the meaningful-benchmark slot: "
                     + sk["escalation"].rstrip(".") + ".")
    else:
        s = sk["selected"]
        c = s.get("comparison")
        if c and c["kind"] == "series":
            parts.append(_series_sentence(f"{sk['label']},", s["candidate"], c))
        elif c:
            parts.append(_ratio_sentence(f"{sk['label']},", s["candidate"], c))
        elif s.get("by_descriptor"):
            parts.append(f"{sk['label']}, {s['candidate']} scored {x_of_n(s['score'], s['max'])}. {BY_DESCRIPTOR_SENTENCE}")
        else:
            parts.append(f"{sk['label']}, {s['candidate']} scored {x_of_n(s['score'], s['max'])}: no comparison computed "
                         f"({(s.get('comparison_note') or 'not computable on held data').rstrip('.')}).")
        if c and c.get("low_confidence"):
            lows.append(c["low_confidence"])
        if c and c.get("ks_pme_monthly_schedule") is not None:
            sched = (f"ILLUSTRATIVE monthly-schedule KS-PME {c['ks_pme_monthly_schedule']} vs {s['candidate']} "
                     f"({c['schedule_contributions']} equal contributions), the two-point figure is primary.")
    ref = sel.get("reference_comparison")
    if ref:
        c = ref["comparison"]
        parts.append(_series_sentence("Reference comparison on the highest-ranked held public market series, "
                                      "not the meaningful benchmark,", ref["candidate"], c))
        if c.get("low_confidence"):
            lows.append(c["low_confidence"])
        if sched is None and c.get("ks_pme_monthly_schedule") is not None:
            sched = (f"ILLUSTRATIVE monthly-schedule KS-PME {c['ks_pme_monthly_schedule']} vs {ref['candidate']} "
                     f"({c['schedule_contributions']} equal contributions), the two-point figure is primary.")
    parts.extend(_lane_a_sentences(sel))
    for lc in lows:
        parts.append(lc[0].upper() + lc[1:].rstrip(".") + ".")
    if sched:
        parts.append(sched)
    parts.append(f"Return basis for every comparison: {sel['basis']['label'].rstrip('.')}.")
    parts.append("The peer comparison (paragraphs (g) and (h)) is cell 1.12, never a PME. Window-sensitive: "
                 "every figure on appraisal-lagged NAVs moves with the window (methodology section 3).")
    text = " ".join(parts)
    note = analyst_note(key, "1.8")
    if note:
        text += f" Analyst note: {note}"
    return {"value": text, "source": src, "section": "meaningful benchmark, reference and declared comparisons",
            "quote": ""}


def cell_1_12(key: str) -> dict | None:
    """Peer comparison (paragraphs (g) and (h)): the cohort side by side over
    identical periods with n per period, the leave-one-out composite ratio
    where it is aligned, the refusal where it is not, and the survivorship
    and heterogeneity sentences. Never a benchmark, never a PME."""
    sel = _selection(key)
    if not sel or not sel.get("slot_g"):
        return None
    g = sel["slot_g"]
    comp = g["composite"]
    src = f"benchmark selection artifact ({_fund_short(key)})"
    parts = [f"{g['label']}: {g['cohort_label']}, peers {', '.join(g['member_names'])}, fund return basis "
             f"{sel['basis']['label'].rstrip('.')}."]
    if comp["status"] == "computed":
        parts.append(f"Equal-weight peer composite over {comp['window']} (n={comp['n']} peers in every period, "
                     f"identical start and end dates): relative wealth ratio {comp['relative_wealth_ratio']} = "
                     f"fund growth {comp['fund_growth_x']}x / composite growth {comp['index_growth_x']}x, "
                     f"annualized excess return {_signed(comp['excess_return_pct'])}%/yr "
                     f"(fund {comp['fund_ann_pct']}%/yr vs composite {comp['index_ann_pct']}%/yr).")
        parts.append(comp["not_pme_note"])
        parts.append("Alignment: " + comp["alignment_note"].rstrip(".") + ".")
        if comp.get("low_confidence"):
            parts.append(comp["low_confidence"][0].upper() + comp["low_confidence"][1:].rstrip(".") + ".")
    else:
        parts.append("Composite REFUSED: " + comp["reason"].rstrip(".") + ".")
    # the side-by-side table: member names once, in order, then one row per
    # period with the values in that order (n = members reporting)
    order = list(g["table"][0]["returns"].keys()) if g["table"] else []
    rows = []
    for r in g["table"]:
        cells = " / ".join(f"{r['returns'].get(m):g}%" if r["returns"].get(m) is not None else "n/a" for m in order)
        rows.append(f"{r['label']} (n={r['n']}): {cells}")
    parts.append("Side by side, every period any member reports, columns in this order: " + ", ".join(order)
                 + ". n = members reporting. " + " | ".join(rows) + ".")
    parts.append(g["survivorship_note"])
    parts.append(g["heterogeneity_note"])
    return {"value": " ".join(parts), "source": src,
            "section": "peer comparison: member table, composite or refusal, survivorship, heterogeneity",
            "quote": ""}


def cell_5_3(key: str) -> dict | None:
    """Every Slot K candidate the engine scored, with its outcome, and the
    typed Lane A record."""
    sel = _selection(key)
    if not sel:
        return None
    src = f"benchmark selection artifact ({_fund_short(key)})"
    sk = sel["slot_k"]
    parts = [f"Candidates evaluated for the meaningful-benchmark slot, paragraph (k) ({RUBRIC_LABEL}, "
             f"threshold {x_of_n(MIN_PRIMARY_SCORE, RUBRIC_MAX)}, strategy gate below {x_of_n(STRATEGY_GATE_MIN, 3)} "
             "ineligible, an index published by the fund's own adviser ineligible)."]
    if sk.get("escalation"):
        parts.append("ESCALATED: " + sk["escalation"].rstrip(".") + ".")
    else:
        s = sk["selected"]
        parts.append(f"SELECTED {s['candidate']} {x_of_n(s['score'], s['max'])} ({lane_label(s['lane'])}"
                     + (", series held" if s.get("held") else ", cited, series not in the record") + ")."
                     + (f" {BY_DESCRIPTOR_SENTENCE}" if s.get("by_descriptor") else ""))
    for r in sel.get("rejected", []):
        tag = "TIED" if r.get("tied") else "REJECTED"
        parts.append(f"{tag} {r['candidate']} {x_of_n(r['score'], r['max'])} ({lane_label(r['lane'])}): "
                     + r["rejection"].rstrip(".") + ".")
    parts.extend(_lane_a_sentences(sel))
    parts.append("The peer cohort is not a candidate here: it is the paragraph (g) and (h) comparison in cell 1.12.")
    return {"value": " ".join(parts), "source": src,
            "section": "selected, tied, rejected and declared candidates", "quote": ""}


def cell_5_5(key: str) -> dict | None:
    """PME inputs of the public-series comparison stated as the formula, and
    the appraisal-based comparisons stated as ratios, never as a PME."""
    sel = _selection(key)
    if not sel:
        return None
    src = f"benchmark selection artifact ({_fund_short(key)})"
    sk = sel["slot_k"]
    parts = []
    series = None
    if not sk.get("escalation") and (sk["selected"].get("comparison") or {}).get("kind") == "series":
        series = ("meaningful benchmark", sk["selected"]["candidate"], sk["selected"]["comparison"])
    elif sel.get("reference_comparison"):
        ref = sel["reference_comparison"]
        series = ("reference comparison, not the meaningful benchmark", ref["candidate"], ref["comparison"])
    if series:
        lab, cand, c = series
        parts.append(f"PME inputs (computed, public market series {cand}, {lab}): window {c['window']} "
                     f"(series comparison" + (f", {c['window_note']}" if c.get("window_note") else "") + ").")
        parts.append(f"Fund growth {c['fund_growth_x']}x vs proxy growth {c['index_growth_x']}x, flows = one "
                     "contribution of 1 at the window start and the terminal growth at the end, fund return "
                     f"source: {c['fund_return_source']}.")
        parts.append(f"KS-PME {c['ks_pme']} = fund growth / proxy growth. Direct Alpha "
                     f"{_signed(c['direct_alpha_pct'])}%/yr is the annualized form of the same two flows "
                     f"(fund {c['fund_ann_pct']}%/yr vs proxy {c['index_ann_pct']}%/yr).")
        if c.get("ks_pme_monthly_schedule") is not None:
            parts.append(f"ILLUSTRATIVE monthly-schedule KS-PME {c['ks_pme_monthly_schedule']} "
                         f"({c['schedule_contributions']} equal contributions at the window start and each "
                         "month-end inside it, valued at the window end).")
    else:
        parts.append("No public market series comparison is computable on held data, so no PME inputs exist "
                     "for this product" + (": " + sk["escalation"].rstrip(".") if sk.get("escalation") else "") + ".")
    if not sk.get("escalation"):
        s = sk["selected"]
        c = s.get("comparison") or {}
        if c.get("kind") == "published_index":
            parts.append(f"Meaningful benchmark inputs ({s['candidate']}): relative wealth ratio "
                         f"{c['relative_wealth_ratio']} = fund growth {c['fund_growth_x']}x / index growth "
                         f"{c['index_growth_x']}x over {c['window']}, fund return source: {c['fund_return_source']}. "
                         f"{c['not_pme_note']}")
        elif not c and s.get("by_descriptor"):
            parts.append(f"Meaningful benchmark {s['candidate']}: no inputs. {BY_DESCRIPTOR_SENTENCE}")
        elif not c:
            parts.append(f"Meaningful benchmark {s['candidate']}: no inputs, "
                         f"{(s.get('comparison_note') or 'not computable').rstrip('.')}.")
    g = (sel.get("slot_g") or {}).get("composite") or {}
    if g.get("status") == "computed":
        parts.append(f"Peer comparison inputs (cell 1.12, {g['candidate']}): relative wealth ratio "
                     f"{g['relative_wealth_ratio']} = fund growth {g['fund_growth_x']}x / peer composite growth "
                     f"{g['index_growth_x']}x over {g['window']}, fund return source: {g['fund_return_source']}. "
                     f"{g['not_pme_note']}")
    elif g:
        parts.append("Peer comparison inputs: composite refused (" + g["reason"].rstrip(".") + "), see cell 1.12.")
    return {"value": " ".join(parts), "source": src,
            "section": "meaningful benchmark, reference and peer comparison inputs", "quote": ""}


def _cand_name(sel: dict, cid: str) -> str:
    for r in sel.get("rejected", []):
        if r["id"] == cid:
            return r["candidate"]
    return cid


def cell_5_6(key: str) -> dict | None:
    """Benchmark suitability: the selection artifact restated as one cell.
    Every figure is the engine's own output, nothing is extracted here."""
    sel = _selection(key)
    if not sel:
        return None
    sk = sel["slot_k"]
    ma = sk.get("max_attainable")
    ma_txt = (f"Max attainable by an eligible candidate on held data {x_of_n(ma, RUBRIC_MAX)}." if ma is not None
              else "No candidate is eligible, so no maximum is attainable on held data.")
    parts = [f"Benchmark suitability ({RUBRIC_LABEL})."]
    if sk.get("escalation"):
        parts.append(f"ESCALATED: {sk['escalation'].rstrip('.')}.")
    else:
        s = sk["selected"]
        comp = s.get("comparison") or {}
        line = f"{sk['label']}: {s['candidate']} ({lane_label(s['lane'])}) scored {x_of_n(s['score'], s['max'])}"
        if comp and comp["kind"] == "series":
            line += (f" with a {comp['statistic']} over {comp['window']}: "
                     f"KS-PME {comp['ks_pme']}, Direct Alpha {comp['direct_alpha_pct']}%/yr")
        elif comp:
            line += (f" with a {comp['statistic']} over {comp['window']}: relative wealth ratio "
                     f"{comp['relative_wealth_ratio']}, annualized excess return {comp['excess_return_pct']}%/yr")
        elif s.get("by_descriptor"):
            line += f". {BY_DESCRIPTOR_SENTENCE.rstrip('.')}"
        else:
            line += f", no comparison computed ({(s.get('comparison_note') or 'not computable on held data').rstrip('.')})"
        if comp and comp.get("low_confidence"):
            line += f" ({comp['low_confidence']})"
        parts.append(line + ".")
        if sk.get("ties"):
            parts.append(f"{TIE_SENTENCE} Tied with: " + ", ".join(_cand_name(sel, i) for i in sk["ties"]) + ".")
    ref = sel.get("reference_comparison")
    if ref:
        c = ref["comparison"]
        parts.append(f"Reference comparison (not the meaningful benchmark): {ref['candidate']}, KS-PME {c['ks_pme']} "
                     f"over {c['window']}, fund return source: {c['fund_return_source']}.")
    parts.append(ma_txt)
    parts.extend(_lane_a_sentences(sel))
    g = (sel.get("slot_g") or {}).get("composite") or {}
    if g.get("status") == "computed":
        parts.append(f"Peer comparison (cell 1.12): relative wealth ratio {g['relative_wealth_ratio']} vs the "
                     f"equal-weight peer composite over {g['window']} (n={g['n']}), not a benchmark.")
    elif g:
        parts.append("Peer comparison (cell 1.12): composite refused, " + g["reason"].rstrip(".") + ".")
    parts.append(f"Not selected: {len(sel.get('rejected', []))} candidates, each with its reason in "
                 "the ledger. The scoring rules are in the benchmark methodology document.")
    if sel.get("record_hash"):
        parts.append(f"Selection recorded {sel['recorded_at'][:10]}, record {sel['record_hash'][:8]} "
                     f"(rubric {sel.get('rubric_version')}, full hash in the selection record).")
    text = " ".join(parts)
    note = analyst_note(key, "5.6")
    if note:
        text += f" Analyst note: {note}"
    return {"value": text, "source": f"benchmark selection artifact ({_fund_short(key)})",
            "section": "meaningful benchmark, reference, maximum attainable, declared benchmarks, peer comparison",
            "quote": ""}


def _supplement() -> dict:
    sp = DATA / "analytics" / "supplement.json"
    return json.loads(sp.read_text()) if sp.exists() else {}


def _diag(key: str) -> dict | None:
    return (_supplement().get("series_diagnostics") or {}).get(key)


def _breit_diag(key: str) -> dict | None:
    return _supplement().get("breit_monthly_diagnostics") if key == "breit" else None


def _pct(x) -> str:
    return f"{x:g}%"


def cell_1_6(key: str) -> dict | None:
    """Volatility and max drawdown from the analytics supplement's series
    diagnostics (daily series products) or the printed monthly NAV path
    (breit). Every figure is the supplement's, nothing is typed here."""
    d = _diag(key)
    if d:
        market = "market price" in d["basis"]
        text = (f"Computed from the held daily series {d['ticker']} ({d['basis']}), {d['window']}: annualized "
                f"volatility {_pct(d['ann_vol_observed_pct'])} on {d['monthly_obs']} monthly returns"
                + (f" and {_pct(d['ann_vol_daily_pct'])} on daily returns" if market else "")
                + f", max drawdown {_pct(d['max_drawdown_pct'])} on the daily series (peak {d['drawdown_peak']} to "
                f"trough {d['drawdown_trough']}). "
                + ("A market-price series: the drawdown and the volatility include premium and discount swings "
                   "and are not a measure of the portfolio."
                   if market else
                   "An appraisal-based NAV series: the volatility understates the risk of the holdings, see the "
                   "de-smoothed figure in cell 1.7."))
        return {"value": text, "source": "analytics supplement artifact (series diagnostics)",
                "section": "series diagnostics for this product", "quote": ""}
    b = _breit_diag(key)
    if b:
        text = (f"Computed from the fund's own printed monthly NAV path (Class I, {b['window']}, "
                f"n={b['monthly_obs']} monthly returns): annualized NAV-path volatility {_pct(b['nav_path_ann_vol_pct'])}, "
                f"NAV-path max drawdown {_pct(b['nav_path_max_drawdown_pct'])}. {b['basis'][0].upper()}{b['basis'][1:]}. "
                f"{b['drawdown_note'][0].upper()}{b['drawdown_note'][1:]}.")
        return {"value": text, "source": "analytics supplement artifact (monthly NAV diagnostics)",
                "section": "monthly NAV diagnostics for this product", "quote": ""}
    return None


def cell_1_7(key: str) -> dict | None:
    """De-smoothed volatility (Geltner AR1) from the same diagnostics."""
    d = _diag(key)
    if d:
        rho = d["lag1_autocorr_rho"]
        read = ("no lag-1 smoothing is measurable" if abs(rho) < 0.05 else
                "mild lag-1 smoothing" if rho < 0.2 else
                "moderate lag-1 smoothing" if rho < 0.4 else "heavy lag-1 smoothing")
        text = (f"De-smoothed (Geltner AR1) annualized volatility {_pct(d['ann_vol_desmoothed_pct'])} vs "
                f"{_pct(d['ann_vol_observed_pct'])} observed (lag-1 autocorrelation rho {rho:g}, n={d['monthly_obs']} "
                f"monthly returns of the held daily series {d['ticker']}, {d['basis']}). Reading: {read}"
                + (", the de-smoothed figure is the better estimate of the holdings' volatility" if rho >= 0.05 else "")
                + ". The method and its limits are in the methodology's window-sensitivity section.")
        return {"value": text, "source": "analytics supplement artifact (series diagnostics)",
                "section": "series diagnostics for this product", "quote": ""}
    b = _breit_diag(key)
    if b:
        text = (f"De-smoothed (Geltner AR1) annualized NAV-path volatility {_pct(b['desmoothed_ann_vol_pct'])} vs "
                f"{_pct(b['nav_path_ann_vol_pct'])} observed (lag-1 autocorrelation rho {b['lag1_autocorr_rho']:g}, "
                f"n={b['monthly_obs']}, printed monthly NAV path {b['window']}). The appraisal process compresses "
                f"reported volatility by about {b['desmoothed_ann_vol_pct'] / b['nav_path_ann_vol_pct']:.1f}x. "
                f"{b['basis'][0].upper()}{b['basis'][1:]}.")
        return {"value": text, "source": "analytics supplement artifact (monthly NAV diagnostics)",
                "section": "monthly NAV diagnostics for this product", "quote": ""}
    return None


def cell_4_8(key: str) -> dict | None:
    """Smoothing diagnostics: the lag-1 autocorrelation of this product's
    series beside every other measured product's, from the same artifact."""
    sup = _supplement()
    diags = sup.get("series_diagnostics") or {}
    d = diags.get(key)
    b = _breit_diag(key)
    if not d and not b:
        return None
    others = []
    for k2, d2 in sorted(diags.items()):
        if k2 != key and "market price" not in d2["basis"]:
            others.append(f"{_fund_short(k2)} {d2['lag1_autocorr_rho']:g}")
    bm = sup.get("breit_monthly_diagnostics")
    if bm and key != "breit":
        others.append(f"{_fund_short('breit')} {bm['lag1_autocorr_rho']:g} (printed monthly NAV path)")
    if d:
        market = "market price" in d["basis"]
        head = (f"Smoothing diagnostics: lag-1 autocorrelation rho {d['lag1_autocorr_rho']:g} on n={d['monthly_obs']} monthly "
                f"returns of {d['ticker']} ({d['basis']}), observed annualized volatility "
                f"{_pct(d['ann_vol_observed_pct'])} vs de-smoothed {_pct(d['ann_vol_desmoothed_pct'])}.")
        if market:
            head += (" A market price is not an appraisal: the autocorrelation here describes the traded price, "
                     "so the appraisal-smoothing reading does not apply.")
    else:
        head = (f"Smoothing diagnostics on the printed monthly NAV path: lag-1 autocorrelation rho "
                f"{b['lag1_autocorr_rho']:g} (n={b['monthly_obs']}), observed {_pct(b['nav_path_ann_vol_pct'])} vs "
                f"de-smoothed {_pct(b['desmoothed_ann_vol_pct'])}, heavy smoothing consistent with monthly appraisal "
                "marks.")
    text = head + (" Other measured NAV series in the record, same statistic: " + ", ".join(others) + "."
                   if others else "")
    return {"value": text, "source": "analytics supplement artifact (series diagnostics)",
            "section": "lag-1 autocorrelation across the measured series", "quote": ""}


def cell_1_10(key: str) -> dict | None:
    """Market price history and premium from the held close series and the
    supplement's premium block (market-priced products only)."""
    sup = _supplement()
    d = _diag(key)
    if not d or "market price" not in d["basis"]:
        return None
    from tark_data import load_series
    prem = sup.get(f"{key}_premium") or {}
    s = load_series(d["ticker"].lower(), "close")
    first, last = s[0][1], s[-1][1]
    peak_d, peak_v = max(s, key=lambda x: x[1])
    text = (f"Full trading-life price series on record ({len(s)} sessions, {s[0][0]} to {s[-1][0]}, {d['ticker']} daily "
            f"close): first ${first:.2f}, peak ${peak_v:.2f} on {peak_d}, last ${last:.2f}, cumulative "
            f"{(last / first - 1) * 100:+.1f}%.")
    if prem:
        nav = prem.get("latest_filed_nav") or prem.get("latest_printed_nav")
        pv = prem.get("premium_pct_vs_latest_filed_nav", prem.get("premium_pct_vs_latest_printed_nav"))
        if nav is not None and pv is not None:
            text += (f" Premium or discount to the latest filed NAV (${nav:.2f}): {pv:+g}% at the {prem['last_close_date']} "
                     f"close. {prem.get('note', '').rstrip('.')}.")
    text += " A market price benchmarks the premium, not the portfolio (cells 4.7 and 5.6)."
    return {"value": text, "source": "held daily series and analytics supplement artifact (premium block)",
            "section": "price history and premium to NAV", "quote": ""}


def cell_4_7(key: str) -> dict | None:
    """Premium or discount check from the supplement's premium block."""
    prem = _supplement().get(f"{key}_premium")
    if not prem:
        return None
    if key == "dxyz":
        lo, hi = prem["filed_premium_range_pct"]
        text = (f"Premium vs the latest FILED quarterly NAV (${prem['latest_filed_nav']:.2f}): "
                f"{prem['premium_pct_vs_latest_filed_nav']:+g}% at the {prem['last_close_date']} close "
                f"(${prem['last_close']:.2f}). Filed premium range since listing: {lo:g}% to {hi:g}%. "
                f"{prem['note'][0].upper()}{prem['note'][1:].rstrip('.')}.")
    else:
        qs = prem.get("premium_pct_at_each_printed_quarter") or []
        text = (f"Premium or discount vs the printed quarterly NAV: {prem['premium_pct_vs_latest_printed_nav']:+g}% at the "
                f"{prem['last_close_date']} close (${prem['last_close']:.2f} vs NAV ${prem['latest_printed_nav']:.2f} at "
                f"{prem['latest_nav_date']}). Across the {len(qs)} printed quarters the price stood between "
                f"{min(qs):g}% and {max(qs):g}% of NAV, at a discount in {sum(1 for q in qs if q < 0)} of them. "
                f"{prem['note'][0].upper()}{prem['note'][1:].rstrip('.')}.")
    return {"value": text, "source": "analytics supplement artifact (premium block)",
            "section": "premium and discount to NAV", "quote": ""}


def cell_3_7(key: str) -> dict | None:
    """Plan participant liquidity demand is a property of each reference
    plan, never of the product. The record's cell says so and names where
    the per-plan figures live. The memo for a plan prints that plan's own
    counts from its file (R2-P1-13, audit item 30), so no plan's numbers
    sit in another plan's document."""
    from tark_data import plan_keys
    n = len(plan_keys())
    text = (f"Plan participant liquidity demand is computed per reference plan from the plan's own Form 5500 record "
            f"(participants with account balances, separated participants with balances as the near-term liquidity "
            f"tail, active participants, retirees in pay status, and the filed outflow proxy from Schedule H "
            f"totals), for each of the {n} reference plans. The figures appear in the decision memo and the "
            "Liquidity view for the plan being evaluated. This product record holds no plan's counts, so a "
            "memo for one plan never carries another plan's numbers.")
    return {"value": text, "source": "plan records on file (Form 5500), read per plan by the liquidity match",
            "section": "participant counts and filed outflow proxy, per plan", "quote": ""}


def cell_1_9(key: str) -> dict | None:
    """Stress-window performance from the supplement's stress_windows block."""
    sp = DATA / "analytics" / "supplement.json"
    if not sp.exists():
        return None
    sw = (json.loads(sp.read_text()).get("stress_windows") or {}).get(key)
    if not sw:
        return None
    src = "analytics supplement artifact (stress windows)"
    if "cy2022_rate_shock" in sw or "covid_feb_apr_2020" in sw:
        parts = ["Computed stress-window performance from the held daily series "
                 "(adjusted close, distributions reinvested)."]
        labels = (("cy2022_rate_shock", "CY2022 rate shock"), ("covid_feb_apr_2020", "COVID (Feb to Apr 2020)"))
        for k2, label in labels:
            w = sw.get(k2)
            if w:
                parts.append(f"{label}: total return {w['return_pct']}%, max drawdown {w['max_drawdown_pct']}%.")
        if sw.get("worst_peak_to_trough_full_history_pct") is not None:
            parts.append(f"Worst full-history peak-to-trough {sw['worst_peak_to_trough_full_history_pct']}%.")
        return {"value": " ".join(parts), "source": src, "section": "stress windows for this product", "quote": ""}
    parts = ["Stress observation from the printed fiscal-year returns on record."]
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
    return {"value": " ".join(parts), "source": src, "section": "stress windows for this product", "quote": ""}


def cell_3_8(key: str) -> dict | None:
    """ILLUSTRATIVE redemption stress test across the four reference plans."""
    ms = _matches(key)
    if not ms:
        return None
    src = f"liquidity match artifacts ({_fund_short(key)}, four reference plans)"
    section = "stressed scenario and scenario across the four plan match files"
    first = ms[0][2]
    if first["wrapper_facts"].get("exchange"):
        return {"value": ("Redemption stress test not applicable: the wrapper is exchange-traded with "
                          "continuous dealing, so there is no wrapper capacity to stress. Exit is at the "
                          "market price, whose premium or discount to NAV is the relevant risk (cell 1.10)."),
                "source": src, "section": section, "quote": ""}
    sc, ss = first["scenario"], first["stressed_scenario"]
    parts = [f"ILLUSTRATIVE redemption stress test (computed for all four reference plans): "
             f"base demand is each plan's filed outflow proxy (Schedule H, total expenses less "
             f"administrative expenses over beginning net assets), stressed demand is "
             f"{ss['assumptions']}, default sliders allocation {sc['allocation_pct_of_plan']:g}% of plan, "
             f"tail turnover {sc['tail_annual_turnover_pct']:g}%/yr, active turnover "
             f"{sc['active_annual_turnover_pct']:g}%/yr."]
    for _, label, m in ms:
        s2, sc2 = m["stressed_scenario"], m["scenario"]
        cap = s2.get("annual_wrapper_capacity_pct")
        cap_words = "an annual wrapper capacity not computable (3.1)" if cap is None else f"{cap:g}% annual wrapper capacity"
        filed = sc2.get("filed_outflow_proxy_pct")
        filed_words = ("no filed outflow proxy in the plan record" if filed is None
                       else f"filed outflow proxy {filed:.1f}% of the position per year")
        stressed_words = ("stressed demand not computable" if s2.get("demand_pct_of_position") is None
                          else f"stressed demand {s2['demand_pct_of_position']}%")
        parts.append(f"{label}: {filed_words}, slider assumption {sc2['slider_assumption_pct']}%, "
                     f"{stressed_words} vs {cap_words}, {s2['outcome'].rstrip('.')}.")
    parts.append("Proration assumption: an oversubscribed offer is filled pro rata and the unfilled "
                 "remainder waits for the next window.")
    return {"value": " ".join(parts), "source": src, "section": section, "quote": ""}


def cell_3_9(key: str) -> dict | None:
    """Product-to-plan liquidity match: structural verdict plus per-plan scenario verdicts."""
    ms = _matches(key)
    if not ms:
        return None
    first = ms[0][2]
    src = f"liquidity match artifacts ({_fund_short(key)}, four reference plans)"
    verdict = first["verdict"].upper()
    missing = first.get("missing_facts") or []
    head = (f"Structural liquidity verdict {verdict} (typed facts, cells 3.1, 3.3, 2.7, plan-independent"
            + (", facts missing: " + ", ".join(missing) if missing else "") + ").")
    per_plan = ", ".join(f"{label}: {(m.get('scenario_verdict') or 'not computable')}" for _, label, m in ms)
    parts = [head, f"Scenario verdicts (ILLUSTRATIVE, default sliders) by reference plan: {per_plan}. "
                   "Base demand is each plan's filed outflow proxy (Schedule H), the sliders set the stress."]
    for r in first.get("structural_reasons") or []:
        parts.append(r.rstrip(".") + ".")
    parts.append("Per-plan reasons, capacity and stressed outcomes are in the liquidity match artifacts "
                 "and on the Liquidity view.")
    return {"value": " ".join(parts), "source": src,
            "section": "verdict, scenario verdict, missing facts and structural reasons across the four plan match files",
            "quote": ""}


OWNED = {
    "1.6": cell_1_6,
    "1.7": cell_1_7,
    "1.8": cell_1_8,
    "1.9": cell_1_9,
    "1.10": cell_1_10,
    "1.12": cell_1_12,
    "2.9": cell_2_9,
    "3.7": cell_3_7,
    "3.8": cell_3_8,
    "3.9": cell_3_9,
    "4.7": cell_4_7,
    "4.8": cell_4_8,
    "5.3": cell_5_3,
    "5.4": cell_5_4,
    "5.5": cell_5_5,
    "5.6": cell_5_6,
}
# these six restate engine outputs that already exist as computed cells. The
# writer regenerates them where they are computed and never turns an n/a,
# pending or evidence row into a computed one (coverage totals do not move).
# Cell 1.12 (R2-P1-A) is born here: the writer fills its pending row. Cell
# 3.7 (R2-P1-13) is owned for every product: its documented n/a rows said
# the same thing the computed sentence now says (plan-side, per plan).
REGENERATE_ONLY = {"1.6", "1.7", "1.8", "1.9", "1.10", "3.8", "3.9", "4.7", "4.8", "5.3", "5.5"}


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
        "extracted_by": f"{COMPUTED_WRITER_LABEL} (as-of {as_of})",
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

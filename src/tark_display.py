"""
Display derivations shared by the site build and the memo writer
==================================================================
Typed-fact headlines and label vocabularies. Display only: the full sourced
text of every cell stays one disclosure away, and no figure is ever
extracted from prose by regex. build_site.py ships cell_display per cell in
the bundle, tark_memo.py writes the same headlines into the findings table,
so the site and the memo can never disagree on a headline.
"""
from __future__ import annotations

import re

from tark_data import status_kind

# display vocabularies for typed facts (the JS keeps the same maps; P2-1
# folds both into the registry)
BASE_LABEL = {
    "net_assets": "net assets", "nav": "NAV", "aggregate_nav": "aggregate NAV",
    "managed_assets": "managed assets (leverage-inclusive)",
    "gross_incl_borrowings": "gross assets incl. borrowings",
    "outstanding_shares": "outstanding shares",
    "lesser_of_dual_base": "the lesser of two bases",
}
WRAPPER_LABEL = {
    "interval_23c3": "interval fund (Rule 23c-3)", "tender_offer": "tender-offer fund",
    "nontraded_bdc": "non-traded BDC", "nontraded_reit": "non-traded REIT",
    "nontraded_llc": "non-traded LLC ('34 Act)", "listed_cef": "listed closed-end fund",
    "listed_bdc": "listed BDC",
}


def _pct(v) -> str:
    return f"{v:g}%"


def fmt_incentive(v: dict | None) -> str:
    if not v:
        return ""
    if not v.get("present"):
        return "none"
    parts = []
    if v.get("rate_pct") is not None:
        parts.append(_pct(v["rate_pct"]))
    if v.get("hurdle_pct") is not None:
        parts.append(f"{_pct(v['hurdle_pct'])} hurdle")
    return " / ".join(parts) if parts else "present, rate not typed (see 2.2)"


def fmt_early(v: dict | None) -> str:
    if not v:
        return ""
    if not v.get("present"):
        return "none"
    rate = _pct(v["rate_pct"]) if v.get("rate_pct") is not None else \
        "fee present, rate not typed (see 2.7)"
    return f"{rate} {v['window']}" if v.get("window") else rate


def _money(x) -> str:
    if x >= 1e9:
        return f"${x / 1e9:.1f}B"
    if x >= 1e6:
        return f"${x / 1e6:.1f}M"
    return f"${round(x):,}"


def facts_by_cell(facts: dict) -> dict[str, dict]:
    """{cell_id: {field: fact}} for facts whose value is not null."""
    out: dict[str, dict] = {}
    for field, f in (facts or {}).items():
        if f.get("value") is not None:
            out.setdefault(f["source_cell"], {})[field] = f
    return out


def typed_headline(cid: str, fx: dict) -> str | None:
    """Headline from the typed facts that cite this cell, or None when no
    fact does. Never a regex over the prose."""
    if not fx:
        return None
    g = lambda f: fx.get(f, {}).get("value")  # noqa: E731
    if cid == "2.1" and g("mgmt_fee_pct") is not None:
        base = BASE_LABEL.get(g("mgmt_fee_base"), g("mgmt_fee_base") or "a base not typed")
        return f"{g('mgmt_fee_pct'):.2f}% on {base}"
    if cid == "2.2" and "incentive_fee" in fx:
        return "incentive fee: " + fmt_incentive(g("incentive_fee"))
    if cid == "2.3" and g("expense_ratio_pct") is not None:
        return f"{g('expense_ratio_pct'):.2f}% net expense ratio"
    if cid == "2.4" and "affe" in fx:
        v = g("affe")
        if not v.get("present"):
            return "no AFFE line"
        return f"AFFE {v['rate_pct']:.2f}%" if v.get("rate_pct") is not None \
            else "AFFE line present, rate not typed"
    if cid == "2.7" and "early_repurchase" in fx:
        return "early repurchase fee: " + fmt_early(g("early_repurchase"))
    if cid == "3.1":
        parts = []
        if g("repurchase_cadence_per_year") is not None:
            parts.append(f"{g('repurchase_cadence_per_year')}x per year")
        if g("repurchase_cap_pct") is not None:
            base = BASE_LABEL.get(g("repurchase_cap_base"), g("repurchase_cap_base") or "")
            parts.append(f"{g('repurchase_cap_pct'):g}% cap" + (f" on {base}" if base else ""))
        if parts:
            return ", ".join(parts)
        if g("wrapper_type"):
            return WRAPPER_LABEL.get(g("wrapper_type"), g("wrapper_type"))
    if cid == "3.3" and "gate_history" in fx:
        return "gating history: yes, prorated under stress" if g("gate_history") \
            else "no gating identified in the filings on record"
    if g("net_assets_usd") is not None:
        return f"{_money(g('net_assets_usd'))} net assets"
    if cid == "4.5" and g("auditor"):
        return g("auditor") + (" (Big 4)" if g("big4") else "")
    if cid == "6.4" and g("tax_form"):
        return {"1099": "Form 1099", "K-1": "Schedule K-1"}.get(g("tax_form"), g("tax_form"))
    if cid == "1.11" and g("inception"):
        yrs = g("track_record_years")
        return f"inception {g('inception')}" + (f", {yrs:g} years" if yrs is not None else "")
    if cid == "6.1" and g("wrapper_type"):
        return WRAPPER_LABEL.get(g("wrapper_type"), g("wrapper_type"))
    if cid == "1.8" and g("pme_primary") is not None:
        da = g("direct_alpha_primary")
        return f"KS-PME {g('pme_primary'):.2f}" + (f", Direct Alpha {da:.2f}%/yr" if da is not None else "")
    if cid == "5.3" and g("primary_benchmark_id"):
        sc = g("selection_score")
        return f"{g('primary_benchmark_id')} selected" + (f", {sc}/12" if sc is not None else "")
    if cid == "3.9" and isinstance(g("liquidity_verdict_by_plan"), dict):
        vs = sorted(set(g("liquidity_verdict_by_plan").values()))
        return ("verdict " + vs[0] + " under all plans") if len(vs) == 1 \
            else "verdict varies by plan: " + ", ".join(vs)
    field, f = next(iter(fx.items()))
    v = f["value"]
    return f"{field.replace('_', ' ')}: {v if not isinstance(v, float) else f'{v:g}'}"


def cell_display(cell: dict, cid: str = "", fx: dict | None = None) -> dict:
    """Display derivation (display-only; the full sourced text stays one
    disclosure away). headline = the typed fact that cites the cell when one
    exists, otherwise the first complete sentence of the value (cut at a word
    boundary when long). No figure is ever extracted from prose by regex:
    that produced headlines that read the opposite of the finding."""
    st = str(cell.get("status", "pending"))
    val = str(cell.get("value") or "")
    kind = status_kind(st)
    if kind == "n/a":
        reason = st.split(":", 1)[1].strip() if ":" in st else st[6:].strip(" -")
        return {"headline": "n/a", "plain": reason[:170]}
    if not val:
        return {"headline": "—", "plain": "Pending extraction."}
    first_sentence = re.split(r"(?<=[.!?])\s+", val, maxsplit=1)[0]
    plain = first_sentence[:180]
    typed = typed_headline(cid, fx or {})
    if typed:
        return {"headline": typed, "plain": plain, "typed": True}
    if len(first_sentence) <= 140:
        headline = first_sentence
    else:
        cut = first_sentence[:137]
        headline = cut[: cut.rfind(" ")].rstrip(" ,;:") + "…" if " " in cut else cut + "…"
    return {"headline": headline, "plain": plain, "typed": False}

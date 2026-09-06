"""
Tark — Fiduciary Evaluation Demo (M4, Increment 5)
===================================================
Four views: the anchor plan, the candidate roster, the six-factor evaluation,
and the benchmark selection with its rejection log. Every number on screen is
real-and-cited or labeled illustrative; the plan sponsor is anonymized on all
surfaces by project rule (enforced by src/test_app.py).

Run:  streamlit run app.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))          # app.py lives at repo root;
                                               # the modules live in src/
import json                                    # noqa: E402

import streamlit as st                         # noqa: E402

from tark_data import (coverage_summary, DATA, FACTORS, RULE, RULE_CITATION,  # noqa: E402
                       authority, cells_by_factor, load_evidence, load_plan,
                       load_products, plan_keys, status_kind)

st.set_page_config(page_title="Tark: Fiduciary Evaluation Demo",
                   layout="wide")

RULE_CAPTION = (f"Six factors per DOL proposed rule {RULE_CITATION}, paragraphs "
                f"{RULE['paragraphs']}. Verbatim text: {authority()['status']}.")

CHIP = {
    "verified": ":green[● verified]",
    "extracted": ":green[● extracted-unverified]",
    "partial": ":orange[● partial]",
    "fetched": ":blue[● series fetched]",
    "computed": ":violet[● computed (pipeline)]",
    "pending": ":gray[○ pending]",
    "n/a": ":gray[– n/a]",
}

PRODUCTS = load_products()
PLANS = {k: load_plan(k) for k in plan_keys()}


def product_label(key: str) -> str:
    return PRODUCTS[key]["fund_name"]


def coverage_line(key: str) -> str:
    """The one coverage formula (tark_data.coverage_summary), per kind."""
    return coverage_summary(key)["headline"]


# ------------------------------------------------------------------ sidebar
st.sidebar.title("Tark")
st.sidebar.caption("Benchmark selection & six-factor evaluation (demo build)")
view = st.sidebar.radio(
    "View",
    ["Reference Plan", "Candidate Roster", "Six-Factor Evaluation",
     "Benchmark Selection", "Liquidity Match"],
    key="nav",
)
_plan_order = ["plan_tech_media"] + [k for k in PLANS if k != "plan_tech_media"]
plan_key = st.sidebar.selectbox(
    "Plan", _plan_order, format_func=lambda k: PLANS[k]["display_label"],
    key="plan",
)
product_key = st.sidebar.selectbox(
    "Product", list(PRODUCTS), format_func=product_label, key="product",
)
ANCHOR = PLANS[plan_key]
st.sidebar.caption(RULE_CAPTION)
st.sidebar.caption("All figures real and cited, or labeled illustrative. "
                   "Plan sponsor anonymized on all surfaces.")


# --------------------------------------------------------------- anchor view
def render_anchor():
    st.title("Reference Plan")
    st.subheader(ANCHOR["display_label"])
    if ANCHOR.get("archetype"):
        st.caption(f"Archetype: {ANCHOR['archetype']} · plan year "
                   f"{ANCHOR.get('plan_year', '?')}")
    fin, part, der = ANCHOR["financials"], ANCHOR["participants"], ANCHOR["derived"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net assets (EOY)", f"${fin['net_assets_eoy'] / 1e6:,.1f}M",
              delta=f"{der['yoy_net_asset_growth_pct']}% YoY")
    c2.metric("Accounts with balances", f"{int(part['with_account_balances']):,}")
    c3.metric("Average balance", f"${der['avg_balance_per_account']:,}")
    c4.metric("Admin expense ratio", f"{der['admin_expense_ratio_pct']}%")

    c5, c6, c7 = st.columns(3)
    c5.metric("Active participants", f"{int(part['active_eoy']):,}")
    c6.metric("Separated, balances retained",
              f"{int(part['separated_deferred_vested']):,}")
    c7.metric("Retirees in pay status", f"{int(part['retired_receiving']):,}")

    tail_pct = part["separated_deferred_vested"] / part["with_account_balances"] * 100
    st.info(f"**Liquidity tail:** {int(part['separated_deferred_vested']):,} "
            f"separated participants still hold balances, "
            f"{tail_pct:.0f}% of all accounts. This cohort, not the active base, "
            f"is the plan's near-term liquidity demand and drives the "
            f"product-to-plan match (cell 3.9).")

    st.markdown(f"**Plan type:** {ANCHOR['plan_characteristics']['codes_decoded']}")
    st.caption(ANCHOR["plan_characteristics"]["note"])
    st.caption(f"Source: {ANCHOR['source']['publisher']}, plan year "
               f"{ANCHOR['plan_year']}, pulled {ANCHOR['source']['pulled']}. "
               f"{ANCHOR['anonymization_rule']}")


# --------------------------------------------------------------- roster view
def render_roster():
    st.title("Candidate Roster")
    st.caption(f"{len(PRODUCTS)} real products across "
               f"{len({p.get('wrapper') for p in PRODUCTS.values()})} wrapper "
               "strings. Every cell is traceable to a public filing via "
               "data/evidence/.")
    rows = []
    for k, p in PRODUCTS.items():
        rows.append({
            "key": k,
            "fund": p["fund_name"],
            "wrapper": p["wrapper"],
            "CIK": p["cik"],
            "evidence coverage": coverage_line(k),
            "note": p.get("note", p.get("identity_note", "")),
        })
    st.dataframe(rows, width="stretch", hide_index=True)
    st.caption("Coverage per status kind from the record's one coverage formula, "
               "the same one the static site uses.")


# ----------------------------------------------------------- evaluation view
def render_evaluation():
    p = PRODUCTS[product_key]
    st.title("Six-Factor Evaluation")
    st.subheader(p["fund_name"])
    st.caption(f"{p['wrapper']} · CIK {p['cik']} · evidence coverage "
               f"{coverage_line(product_key)}")

    tabs = st.tabs([f"{n} · {label}" for n, label in FACTORS.items()])
    grouped = cells_by_factor(p)
    for tab, (n, label) in zip(tabs, FACTORS.items()):
        with tab:
            for cid, cell in grouped[label]:
                kind = status_kind(cell.get("status", "pending"))
                chip = CHIP.get(kind, cell.get("status", ""))
                st.markdown(f"**{cid} · {cell['element']}** {chip}")
                if cell.get("value"):
                    st.markdown(cell["value"])
                    if cell.get("source"):
                        with st.expander("Source"):
                            st.markdown(
                                f"**Document:** {cell.get('source', '')}  \n"
                                f"**Section:** {cell.get('section', '')}  \n"
                                f"**Quote:** {cell.get('quote', '')}  \n"
                                f"**Extracted:** {cell.get('extracted_by', '')} · "
                                f"**Verified:** {cell.get('verified_by', '') or 'pending'}")
                elif kind == "n/a":
                    st.caption(f"Not applicable: {cell['status'][6:]}")
                else:
                    st.caption("Pending extraction. Pointer in "
                               f"data/evidence/{product_key}_evidence.csv")
                st.divider()


# ------------------------------------------------------------ benchmark view
def render_benchmark():
    p = PRODUCTS[product_key]
    st.title("Benchmark Selection")
    st.subheader(p["fund_name"])
    sel_path = DATA / "benchmarks" / f"{product_key}_selection.json"
    if not sel_path.exists():
        st.warning("Engine profile pending for this product: extraction depth "
                   "first (see Increment 1 pointers in the evidence CSV).")
        return
    sel = json.loads(sel_path.read_text())
    st.caption(f"Strategy: {sel['strategy']} · engine inputs from cells "
               f"{', '.join(sel['source_cells'])} · {sel.get('rubric', 'rubric not recorded')}"
               + (f" · max attainable on held data {sel['max_attainable']}/12"
                  if sel.get("max_attainable") is not None else ""))

    sk = sel["slot_k"]
    if sk.get("escalation"):
        st.error(sk["escalation"])

    slots = []
    if sk.get("selected"):
        slots.append((sk["label"], sk["selected"], "the benchmark"))
    if sel.get("reference_comparison"):
        ref = sel["reference_comparison"]
        slots.append(("Reference comparison, not the meaningful benchmark", ref, "the public series"))
    g = sel.get("slot_g")
    if g:
        slots.append((g["label"], {"candidate": g["composite"].get("candidate") or g["cohort_label"],
                                   "score": None, "comparison": g["composite"] if g["composite"]["status"] == "computed" else None,
                                   "comparison_note": g["composite"].get("reason"),
                                   "reasons": [g["survivorship_note"], g["heterogeneity_note"]]}, "the peer composite"))
    for badge, s, comparator in slots:
        st.markdown(f"### {badge}: {s['candidate']}" + (f" ({s['score']}/{s.get('max', 12)})" if s.get("score") is not None else ""))
        comp = s.get("comparison")
        if comp:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Fund (ann.)", f"{comp['fund_ann_pct']}%/yr")
            c2.metric(f"{comparator[0].upper()}{comparator[1:]} (ann.)", f"{comp['index_ann_pct']}%/yr")
            if comp.get("kind") != "series":
                c3.metric("Relative wealth ratio", f"{comp['relative_wealth_ratio']}")
                c4.metric("Excess return", f"{comp['excess_return_pct']}%/yr")
            else:
                c3.metric("KS-PME", f"{comp['ks_pme']}")
                c4.metric("Direct Alpha", f"{comp['direct_alpha_pct']}%/yr")
            st.caption(f"Window {comp['window']}"
                       f"{(' (' + comp['window_note'] + ')') if comp.get('window_note') else ''}"
                       f". Figures on appraisal-lagged NAVs are window-sensitive and can be "
                       f"smoothing-flattered (disclosed per methodology).")
        elif s.get("comparison_note"):
            st.caption(f"No comparison computed: {s['comparison_note']}")
        with st.expander("Scoring rationale"):
            for r in s.get("reasons") or []:
                st.markdown(f"- {r}")

    st.markdown("### Rejection log")
    st.caption("Every candidate not selected, with its true reason: the other "
               "half of a defensible record.")
    st.dataframe(
        [{"candidate": r["candidate"], "lane": r["lane"],
          "score": f"{r['score']}/{r['max']}", "reason": r["rejection"]}
         for r in sel["rejected"]],
        width="stretch", hide_index=True)

    memo = ROOT / "site" / "memos" / f"{plan_key}__{product_key}_decision_memo.docx"
    if memo.exists():
        st.download_button("Download decision memo (.docx)", memo.read_bytes(),
                           file_name=memo.name, key="memo_dl")
    else:
        st.caption("The decision memo for this plan and product has not been built yet.")


def render_liquidity():
    p = PRODUCTS[product_key]
    st.title("Product-to-Plan Liquidity Match")
    st.subheader(p["fund_name"])
    mp = DATA / "liquidity" / f"{plan_key}__{product_key}_match.json"
    if not mp.exists():
        st.warning("Match pending for this plan x product.")
        return
    m = json.loads(mp.read_text())
    st.caption(f"Plan: {m['plan_display_label']} - liquidity tail "
               f"{m['plan_inputs']['tail_share_pct']}% of accounts "
               f"({int(m['plan_inputs']['separated_with_balances']):,} separated "
               f"participants with balances).")
    v = m["verdict"]
    box = (st.success if v.startswith("aligned")
           else st.error if v in ("misaligned", "conditional-weak") else st.warning)
    box(f"Structural verdict (typed facts, cells 3.1, 3.3, 2.7): {v.upper()}")
    if m.get("scenario_verdict"):
        st.info(f"Scenario verdict (ILLUSTRATIVE, this plan): {m['scenario_verdict'].upper()}")
    for r in m["reasons"]:
        st.markdown(f"- {r}")
    st.markdown("#### Scenario (ILLUSTRATIVE - adjustable parameters, not facts)")
    sc = m["scenario"]
    st.dataframe([{"parameter": k, "value": str(val)} for k, val in sc.items()],
                 width="stretch", hide_index=True)
    st.caption("Wrapper facts cited to cell(s) "
               + str(m["wrapper_facts"]["source_cell"])
               + " · citations: " + ", ".join(m["citations"]))


VIEWS = {
    "Reference Plan": render_anchor,
    "Candidate Roster": render_roster,
    "Six-Factor Evaluation": render_evaluation,
    "Benchmark Selection": render_benchmark,
    "Liquidity Match": render_liquidity,
}
VIEWS[view]()

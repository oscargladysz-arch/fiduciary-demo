"""
Tark decision memo generator (M5)
=================================
Renders one Word decision memo per plan and product from the evaluated data:
regulatory basis, six-factor findings, benchmark selection with the FULL
rejection log (or the escalation, for the fail case), the product-to-plan
liquidity match for that plan, and a provenance appendix. The memo is the
artifact a fiduciary files; the rejection log is half its legal value.

The build (src/build_site.py) generates every memo into site/memos/, so a
memo can never be stale against the record. The docx bytes are
deterministic (fixed zip timestamps): the same record yields the same file.

Run:  python src/tark_memo.py [--out DIR]   -> DIR/<plan>__<product>_decision_memo.docx
Anonymization: only the plan's display label ever appears (test-enforced).
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

import csv

from tark_data import (ADVISOR_COMPLETED, ADVISOR_NOT_EVIDENCE, ADVISOR_STATED_CELLS, CELLS,
                       DATA, FACTOR_PARAS, FACTORS, RULE, RULE_CITATION, authority,
                       cells_by_factor, coverage_summary, load_advisor, load_plan,
                       load_products, plan_keys, record_as_of, rule_ref, status_kind)
from tark_benchmark_common import BY_DESCRIPTOR_SENTENCE, TIE_SENTENCE, x_of_n
from tark_display import (WRAPPER_LABEL, _money as money, display_path_free, facts_by_cell,
                          display_copy, fact_label, plan_demand_sentence, reconciliation_sentence,
                          typed_headline)

SITE_MEMOS = Path(__file__).resolve().parents[1] / "site" / "memos"

RULE_PARAS = [
    ("This memo documents an evaluation of the product below as a candidate designated "
     "investment alternative for the plan named above, structured on the six factors of "
     "the proposed rule, paragraphs (g) to (l) of proposed 29 CFR 2550.404a-6: performance "
     "(g), fees and expenses (h), liquidity (i), valuation (j), performance benchmarks (k), "
     "complexity (l). The regulation is cited, not paraphrased. This memo and its underlying "
     "evidence files are the record of the evaluation."),
    ("The benchmark section documents the selection AND the rejections: every candidate "
     "considered, its score, and the true reason it was or was not chosen. Case law is "
     "addressed in its own section below, from cell 5.7 only."),
]

# cells the adopting committee completes for its own plan (P2-6 makes them
# advisor-stated with signer and date). Listed in the Recommendation so the
# memo never implies the record decided them.
COMMITTEE_CELLS = ("6.6", "6.8", "3.7", "2.8", "3.5", "4.9")


KIND_LABEL = {"extracted": "extracted-unverified", "verified": "verified",
              "computed": "computed", "partial": "partial", "structured": "structured"}
EVIDENCED = tuple(KIND_LABEL)


# the abbreviation-aware splitter is shared with the site (R2-P0-4)
from tark_display import ends_at_abbreviation, first_sentence  # noqa: E402,F401


def _findings(product: dict, factor_label: str, fbc: dict, overrides: dict | None = None) -> list[str]:
    """One paragraph per line: the typed facts for the factor's cells, then
    the complete first sentence of every evidenced cell, then the cells
    marked not applicable with their reasons. Nothing is truncated. An
    override replaces the record's sentence for a cell whose content is a
    property of the plan the memo is for (3.7, 3.8, 3.9), so the memo for
    one plan never prints another plan's numbers (R2-P1-13)."""
    typed, lines, na = [], [], []
    overrides = overrides or {}
    for cid, cell in cells_by_factor(product)[factor_label]:
        st = str(cell.get("status", "pending"))
        kind = status_kind(st)
        v = (cell.get("value") or "").strip()
        if cid in overrides and kind in EVIDENCED:
            th = typed_headline(cid, fbc.get(cid, {}))
            if th:
                typed.append(f"{cid} {th}")
            lines.append(f"{cid} {cell['element']} ({KIND_LABEL[kind]}, this plan): {overrides[cid]}")
            continue
        if kind in EVIDENCED and v:
            th = typed_headline(cid, fbc.get(cid, {}))
            if th:
                typed.append(f"{cid} {th}")
            lines.append(f"{cid} {cell['element']} ({KIND_LABEL[kind]}): {first_sentence(display_copy(v))}")
        elif kind == "n/a":
            reason = st.split(":", 1)[1].strip() if ":" in st else st[3:].strip(" -")
            na.append(f"{cid} {reason}")
    out = []
    if typed:
        out.append("Facts on record: " + ". ".join(typed) + ".")
    out.extend(lines)
    if na:
        out.append("Not applicable: " + ". ".join(na) + ".")
    return out or ["No cell evaluated for this factor."]


def _fill(cell, lines: list[str]) -> None:
    """One paragraph per line inside a table cell (no newline joins)."""
    cell.paragraphs[0].text = lines[0]
    for line in lines[1:]:
        cell.add_paragraph(line)


def cell_title(cid: str) -> str:
    c = CELLS[cid]
    return c if isinstance(c, str) else c.get("title", cid)


def _fact_value(fdoc: dict, field: str):
    f = (fdoc.get("facts") or {}).get(field) or {}
    return f.get("value"), f.get("source_cell", ""), f.get("null_reason") or ""


def _liquidity_section(doc: Document, m: dict | None, fdoc: dict, plan: dict, heading: bool = True) -> None:
    if heading:
        doc.add_heading("Product-to-plan liquidity match", level=1)
    if m is None:
        doc.add_paragraph("No liquidity match record exists for this plan and product.")
        return
    doc.add_paragraph(f"Plan: {plan['display_label']}. {m['layers']}")
    doc.add_heading("Structural verdict (dealing terms on record, plan-independent)", level=2)
    doc.add_paragraph(m["verdict"].upper())
    for r in m["structural_reasons"]:
        doc.add_paragraph(r, style="List Bullet")
    wf = m["wrapper_facts"]
    t = doc.add_table(rows=1, cols=3)
    t.style = "Table Grid"
    h = t.rows[0].cells
    h[0].text, h[1].text, h[2].text = "Wrapper fact", "Value", "Cell"
    rows = [("Wrapper", "wrapper_type", WRAPPER_LABEL.get(wf.get("kind"), wf.get("kind"))),
            ("Dealing terms", "dealing_cadence", wf.get("dealing_label")),
            ("Repurchase caps", "repurchase_caps", wf.get("caps_label")),
            ("Annual capacity (binding cap)", "repurchase_caps",
             None if wf.get("annual_capacity_pct") is None else f"{wf['annual_capacity_pct']:g}% of the position per year"),
            ("Gating history", "gate_history",
             None if wf.get("gate_history") is None else ("yes, prorated under stress" if wf["gate_history"] else "none identified in the filings on record")),
            ("Repurchase program status", "repurchase_program_status",
             None if wf.get("program_status") is None
             else wf["program_status"] + (f" as of {wf['program_status_as_of']}" if wf.get("program_status_as_of") else "")),
            ("Early repurchase fee", "early_repurchase", wf.get("early_fee")),
            ("Fund net assets (for the dollar capacity)", "net_assets_usd",
             None if wf.get("net_assets_usd") is None
             else ("approx. " if wf.get("net_assets_approx") else "") + money(wf["net_assets_usd"]))]
    for label, field, shown in rows:
        _, src, null_reason = _fact_value(fdoc, field)
        c = t.add_row().cells
        c[0].text = label
        if shown is None:
            reason = wf.get("null_reasons", {}).get(field) or null_reason or "not on record"
            c[1].text = f"not on record: {reason}"
        else:
            c[1].text = str(shown)
        c[2].text = src or ""
    for row in t.rows:
        row.cells[0].width, row.cells[1].width, row.cells[2].width = Inches(1.7), Inches(4.0), Inches(0.8)

    doc.add_heading("Scenario (ILLUSTRATIVE, this plan)", level=2)
    sc, pi, ss = m["scenario"], m["plan_inputs"], m["stressed_scenario"]
    fo = m.get("filed_outflow") or {}
    cap = sc.get("annual_wrapper_capacity_pct")
    cap_text = ("not applicable (exchange-traded)" if wf.get("exchange")
                else "not computable (3.1)" if cap is None else f"{cap:g}%")
    filed = sc.get("filed_outflow_proxy_pct")
    doc.add_paragraph(
        f"Plan inputs (Form 5500): net assets {money(pi['net_assets'])}, liquidity tail "
        f"{pi['tail_share_pct']}% of accounts ({int(pi['separated_with_balances']):,} "
        "separated participants with balances)"
        + (f", filed outflow proxy {filed:.1f}% of beginning net assets per year "
           f"({fo.get('source', 'the plan record')}: {fo.get('what', '')})."
           if filed is not None else ", no filed outflow proxy in the plan record."))
    if filed is not None:
        doc.add_paragraph(
            f"Base demand (filed outflow proxy applied to a {sc['allocation_pct_of_plan']:g}% "
            f"allocation = {money(sc['plan_allocation_usd'])}): "
            f"{money(sc['filed_annual_demand_usd'])}/yr = {filed:.1f}% of the position per year "
            f"vs annual wrapper capacity {cap_text}.")
    doc.add_paragraph(
        "Slider assumption (adjustable on the Liquidity view, not a fact): tail turnover "
        f"{sc['tail_annual_turnover_pct']:g}%/yr, active turnover "
        f"{sc['active_annual_turnover_pct']:g}%/yr, {sc['slider_assumption_pct']}% of the "
        f"position per year = {money(sc['slider_annual_demand_usd'])}/yr, shown beside the "
        "filed rate, not blended with it.")
    if ss.get("demand_pct_of_position") is not None:
        doc.add_paragraph(
            f"Stressed ({ss['assumptions']}): demand {money(ss['annual_demand_usd'])}/yr = "
            f"{ss['demand_pct_of_position']}% of the position. {ss['outcome']}.")
    else:
        doc.add_paragraph(f"Stressed ({ss['assumptions']}): {ss['outcome']}.")
    fc = sc.get("fund_capacity") or {}
    if fc.get("available"):
        doc.add_paragraph(
            f"Fund capacity in dollars: {money(fc['annual_capacity_usd'])} per year "
            f"({cap:g}% of {'approx. ' if fc.get('net_assets_approx') else ''}"
            f"{money(fc['fund_net_assets_usd'])} net assets, cell {fc.get('net_assets_cell')}). "
            f"The plan's demand at the filed rate is {money(fc['plan_annual_demand_usd'])} per "
            f"year, {fc['plan_share_of_fund_capacity_pct']:.2f}% of that capacity, a claim "
            "shared with every other holder.")
    elif fc.get("reason") and not wf.get("exchange"):
        doc.add_paragraph(f"Fund capacity in dollars: not computable, {fc['reason']}.")
    doc.add_paragraph("Scenario verdict (ILLUSTRATIVE, this plan): "
                      f"{(m.get('scenario_verdict') or 'not computable').upper()}.")
    for r in m["scenario_reasons"]:
        doc.add_paragraph(r, style="List Bullet")
    doc.add_paragraph("Cited: " + ", ".join(
        f"cell {c}" if c[:1].isdigit() else c for c in m["citations"]) + ".")


def _flags(sel: dict | None, m: dict | None, fdoc: dict) -> list[str]:
    """Flags raised by the record. Each restates a typed value or a verdict
    already in the artifacts, with its source. None is a new judgment."""
    out = []
    if sel:
        sk = sel.get("slot_k") or {}
        if sk.get("escalation"):
            out.append("Benchmark: " + sk["escalation"] + " (benchmark selection)")
        elif sk.get("selected") and not sk["selected"].get("comparison"):
            out.append("Benchmark: the meaningful benchmark carries no computed comparison "
                       f"({(sk['selected'].get('comparison_note') or 'not computable').rstrip('.')}) (benchmark selection)")
        comp = ((sk.get("selected") or {}).get("comparison")
                or (sel.get("reference_comparison") or {}).get("comparison") or {})
        if comp.get("low_confidence"):
            out.append("Benchmark: " + comp["low_confidence"] + " (benchmark comparison)")
        g = ((sel.get("slot_g") or {}).get("composite") or {})
        if g.get("status") == "refused":
            out.append("Peer comparison: composite refused, " + g["reason"].rstrip(".") + " (cell 1.12)")
    if m:
        wf = m["wrapper_facts"]
        if wf.get("program_status") == "suspended":
            out.append("Liquidity: repurchase program suspended (cells 3.1, 3.3)")
        if wf.get("gate_history"):
            out.append("Liquidity: gating precedent, repurchases prorated under stress (cell 3.3)")
        if m.get("missing_facts"):
            out.append("Liquidity: structural verdict partial, facts missing: "
                       + ", ".join(fact_label(n) for n in m["missing_facts"]) + " (cells 3.1, 3.3)")
        if m.get("scenario_verdict") in ("misaligned", "conditional-weak"):
            out.append(f"Liquidity: ILLUSTRATIVE scenario verdict {m['scenario_verdict']} "
                       "under this plan (the filed outflow proxy or the stressed demand above "
                       "wrapper capacity)")
    tax, src, _ = _fact_value(fdoc, "tax_form")
    if tax == "K-1":
        out.append(f"Tax reporting: Schedule K-1 (cell {src})")
    return out


def _advisor_section(doc: Document, key: str, plan_key: str, plan: dict) -> dict:
    """The fiduciary's own stated cells for this plan, or none. Returns the entries."""
    adv = load_advisor(plan_key, key) or {}
    entries = adv.get("cells") or {}
    doc.add_heading("Advisor-stated inputs (this plan)", level=1)
    doc.add_paragraph(ADVISOR_NOT_EVIDENCE)
    if not entries:
        doc.add_paragraph(f"None stated for {plan['display_label']}. The six committee cells "
                          "(" + ", ".join(f"{c} {cell_title(c)}" for c in ADVISOR_STATED_CELLS)
                          + ") remain open.")
        return entries
    t = doc.add_table(rows=1, cols=4)
    t.style = "Table Grid"
    h = t.rows[0].cells
    h[0].text, h[1].text, h[2].text, h[3].text = "Cell", "Statement", "Signer", "Date"
    for cid in ADVISOR_STATED_CELLS:
        e = entries.get(cid)
        if e:
            r = t.add_row().cells
            r[0].text, r[1].text, r[2].text, r[3].text = f"{cid} {cell_title(cid)}", e["value"], e["signer"], e["date"]
    return entries


def committee_cell_state(cid: str, product: dict, stated: dict) -> str:
    """stated, not applicable with the record's reason, or open (R3-P2-17b)."""
    if cid in stated:
        return "stated"
    st = str((product.get("cells", {}).get(cid) or {}).get("status", ""))
    if status_kind(st) == "n/a":
        reason = st.split(":", 1)[1].strip() if ":" in st else st[3:].strip(" -")
        return "not applicable" + (f": {reason.rstrip('.')}" if reason else "")
    return "open"


def _recommendation_section(doc: Document, sel: dict | None, m: dict | None,
                            fdoc: dict, plan: dict, stated: dict | None = None,
                            product: dict | None = None) -> None:
    doc.add_heading("Recommendation", level=1)
    if m:
        doc.add_paragraph(
            f"Structural liquidity verdict: {m['verdict'].upper()} (dealing terms on record, plan-independent). "
            f"Scenario verdict under {plan['display_label']} (ILLUSTRATIVE): "
            f"{(m.get('scenario_verdict') or 'not computable').upper()}.")
    if sel is None:
        doc.add_paragraph("Benchmark: no selection record for this product.")
    elif (sel.get("slot_k") or {}).get("escalation"):
        doc.add_paragraph("Benchmark: escalated. " + sel["slot_k"]["escalation"])
    else:
        pr = sel["slot_k"]["selected"]
        doc.add_paragraph(f"Meaningful benchmark (paragraph (k)): {pr['candidate']} at {pr['score']}/{pr['max']}"
                          + ("" if pr.get("held") else ", cited, series not in the record") + ". "
                          + _peer_line(sel))
    flags = _flags(sel, m, fdoc)
    doc.add_paragraph("Flags raised by the record (each restates a recorded value or verdict "
                      "already in the record, with its source):")
    if flags:
        for f in flags:
            doc.add_paragraph(f, style="List Bullet")
    else:
        doc.add_paragraph("none", style="List Bullet")
    stated = stated or {}
    doc.add_paragraph(
        "This memo does not decide. The fiduciary makes the decision on this record. "
        "The committee-completed cells stay the committee's to complete for its own plan "
        "before it does: " + ", ".join(f"{c} {cell_title(c)} ({committee_cell_state(c, product or {}, stated)})"
                                       for c in COMMITTEE_CELLS) + ".")


def _scope_section(doc: Document) -> None:
    doc.add_heading("Scope", level=1)
    # the one gate for "is the verbatim text in this build": the file with its
    # hashed manifest row, never a bare glob of the folder
    verbatim = authority()["status"] == "fetched"
    doc.add_paragraph(
        "This memo records the evaluation of one product as a candidate designated "
        f"investment alternative for one plan, on the record as of {record_as_of()}. "
        "It is a selection record. It is not a monitoring record, and nothing in it "
        "states a monitoring cadence or a later review.")
    doc.add_paragraph(
        "Every figure in it is a cited cell, a figure read from a cited cell, or a "
        "computation from cited series. Every scenario figure is labeled ILLUSTRATIVE. "
        "Cells marked extracted-unverified were extracted by an agent and not yet "
        "verified by a person. "
        + ("Verbatim regulatory text is in this record and quoted where cited."
           if verbatim else
           "Verbatim regulatory text is not in this record: the regulation is cited by "
           "Federal Register citation and RIN, not paraphrased."))



def _case_law_section(doc: Document, product: dict) -> None:
    doc.add_heading("Case law", level=1)
    c = product["cells"]["5.7"]
    st = str(c.get("status", "pending"))
    kind = status_kind(st)
    v = (c.get("value") or "").strip()
    if kind in EVIDENCED and v:
        doc.add_paragraph(f"Cell 5.7 ({KIND_LABEL[kind]}): {display_copy(v)}")
        src = display_copy(c.get("source") or c.get("source_doc") or "")
        if src:
            doc.add_paragraph(f"Source: {src}" + (f". Extracted: {c['extracted_by']}" if c.get("extracted_by") else ""))
    else:
        reason = st.split(":", 1)[1].strip() if ":" in st else st
        doc.add_paragraph(f"Cell 5.7 ({cell_title('5.7')}) is {st.split(' ')[0]} for this product"
                          + (f": {v}" if v else f": {reason}")
                          + " This memo makes no case-law statement beyond that cell.")


RESOLVED_KINDS = ("structured", "extracted", "verified", "computed")
KIND_ORDER = (("structured", "structured"), ("extracted", "extracted-unverified"),
              ("verified", "verified"), ("computed", "computed"), ("partial", "partial"),
              ("fetched", "fetched"), ("na", "n/a"), ("pending", "pending"))
RESOLVED_ONE = ("exact", "form_only")


def _citation_lines(refs: list[dict]) -> list[str]:
    """One paragraph per resolved filing, or the reason it is not on record."""
    lines = []
    for r in refs:
        if r["match"] in RESOLVED_ONE:
            tag = {"form_only": " (matched by form only: the single such filing held)"
                   }.get(r["match"], "")
            lines.append(f"{r['form']} {r.get('filing_date', '')} accession {r['accession']} "
                         f"{r['url']}{tag}".replace("  ", " "))
        elif r["match"] in ("range", "set"):
            lines.append(f"{r['form']}, {r['reason']}:")
            lines.extend(f"{f['filing_date']} accession {f['accession']} {f['url']}"
                         for f in r["filings"])
        else:
            lines.append(f"{r.get('form', '')} accession not on record: {r['reason']}".strip())
    return lines


def _provenance_section(doc: Document, key: str, product: dict, plan: dict) -> None:
    doc.add_heading("Provenance", level=1)
    cov = coverage_summary(key)
    doc.add_paragraph(
        "Cell status for this product, from the record's one coverage formula: "
        + ", ".join(f"{label} {cov[k]}" for k, label in KIND_ORDER)
        + f". {cov['headline']}.")
    # the same set the coverage headline counts as resolved (R3-P2-17a):
    # structured, extracted, verified and computed. Partial and fetched cells
    # are soft and are said to be so, never folded into either count
    ev = [(cid, c) for cid, c in product["cells"].items()
          if status_kind(c.get("status", "")) in RESOLVED_KINDS]
    n = len(ev)
    assert n == cov["resolved"], (n, cov["resolved"])
    have = {f: sum(1 for _, c in ev if (c.get(f) or "").strip())
            for f in ("source", "section", "quote", "extracted_by")}
    doc.add_paragraph(
        f"Of the {n} resolved cells (structured, extracted-unverified, verified and computed), "
        f"{have['source']} carry a source document, "
        f"{have['section']} a section, {have['quote']} a verbatim quote (computed cells "
        f"carry their computation and inputs instead of a quote) and {have['extracted_by']} "
        f"an extractor. {cov['soft']} cells are partial or fetched and are not counted as "
        "resolved. "
        + ("Verified cells have been independently re-checked by a person."
           if cov["verified"] > 0 else
           "No cell is verified: no cell has been independently re-checked by a person, "
           "and the verifier column is empty on every row.")
        + " Cells marked extracted-unverified were extracted by an agent from the cited "
        "document."
        + (" Cells marked structured come directly from machine-readable regulatory "
           "datasets with the dataset cited." if cov.get("structured", 0) > 0 else ""))

    doc.add_heading("Sources cited", level=2)
    cpath = DATA / "citations" / f"{key}.json"
    cit = json.loads(cpath.read_text())["cells"] if cpath.exists() else {}
    doc.add_paragraph(
        "Each evidenced cell's source document as written in the evidence ledger, with "
        "the SEC accession and EDGAR URL resolved against the filing manifest. "
        "Where no filing reference resolves, the row says accession not on record.")
    t = doc.add_table(rows=1, cols=3)
    t.style = "Table Grid"
    h = t.rows[0].cells
    h[0].text, h[1].text, h[2].text = "Cell", "Source as written", "Accession and EDGAR URL"
    for cid, c in ev:
        lines = _citation_lines(cit.get(cid, []))
        if not lines:
            lines = ["accession not on record: no filing reference in the source field"]
        row = t.add_row().cells
        row[0].text = cid
        row[1].text = display_copy(c.get("source") or "")
        _fill(row[2], lines)
    for row in t.rows:
        row.cells[0].width, row.cells[1].width, row.cells[2].width = Inches(0.5), Inches(2.4), Inches(3.6)

    with open(DATA / "manifest.csv", newline="") as fh:
        held = sum(1 for r in csv.DictReader(fh) if r["product"] == key)
    doc.add_paragraph(
        f"Data sources: SEC EDGAR filings ({held} held for this product in the filing manifest, "
        "every row with its accession) and DOL EBSA Form 5500 data for the plan, shown under "
        "its anonymized label.")


def _set_letter(doc: Document) -> None:
    s = doc.sections[0]
    s.page_width, s.page_height = Inches(8.5), Inches(11)
    for m in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(s, m, Inches(1))


def _save(doc: Document, path: Path) -> None:
    """Save with fixed zip entry timestamps so identical content gives
    identical bytes (python-docx stamps the wall clock on every entry)."""
    buf = io.BytesIO()
    doc.save(buf)
    src = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            zi = zipfile.ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = info.external_attr
            dst.writestr(zi, src.read(info.filename))
    path.write_bytes(out.getvalue())


def memo_name(plan_key: str, key: str) -> str:
    return f"{plan_key}__{key}_decision_memo.docx"



def _peer_line(sel: dict) -> str:
    g = ((sel.get("slot_g") or {}).get("composite") or {})
    if g.get("status") == "computed":
        return (f"Peer comparison (paragraphs (g) and (h)): relative wealth ratio {g['relative_wealth_ratio']} vs the "
                f"equal-weight peer composite over {g['window']} (n={g['n']}), not a benchmark and not a PME.")
    if g:
        return "Peer comparison (paragraphs (g) and (h)): composite refused, " + g["reason"].rstrip(".") + "."
    return "Peer comparison (paragraphs (g) and (h)): no cohort on record."


def _comparison_paragraphs(doc: Document, comp: dict, comparator: str,
                           fdoc: dict | None = None) -> None:
    """The comparison named for its comparator (rule 12): KS-PME and Direct
    Alpha against a public market series, a relative wealth ratio against
    an appraisal-based comparator, each with its window and fund source."""
    lc = (f" {comp['low_confidence'][0].upper()}{comp['low_confidence'][1:]}."
          if comp.get("low_confidence") else "")
    filed = ((fdoc or {}).get("facts") or {}).get("filed_since_inception_return_pct") or {}
    if comp.get("kind") == "series" and filed.get("value") is not None:
        lc += " " + reconciliation_sentence(filed["value"], filed.get("note", ""), comp)
    if comp.get("kind") == "series":
        doc.add_paragraph(
            f"Window {comp['window']}"
            f"{(' (' + comp['window_note'] + ')') if comp.get('window_note') else ''}"
            f": fund {comp['fund_ann_pct']}%/yr ({comp['fund_return_source']}) "
            f"vs {comparator} {comp['index_ann_pct']}%/yr, "
            f"KS-PME {comp['ks_pme']}, Direct Alpha {comp['direct_alpha_pct']}%/yr. Disclosure: PME and "
            "alpha computed on appraisal-lagged NAVs are window-sensitive and can be smoothing-flattered. "
            "Conclusions should be read with the methodology's window-sensitivity analysis." + lc)
        doc.add_paragraph(
            "Two-point comparison: one contribution at the window start and one valuation at the end. "
            "Direct Alpha is the annualized form of the same two flows."
            + (f" ILLUSTRATIVE monthly-schedule KS-PME {comp['ks_pme_monthly_schedule']} "
               f"({comp['schedule_contributions']} equal contributions at the window start and each "
               "month-end inside it, valued at the window end). The two-point figure is primary."
               if comp.get("ks_pme_monthly_schedule") is not None else ""))
    else:
        doc.add_paragraph(
            f"Window {comp['window']} ({comp.get('window_note') or str(comp.get('window_years')) + ' period(s), n=' + str(comp.get('n'))}): fund {comp['fund_ann_pct']}%/yr "
            f"({comp['fund_return_source']}) vs {comparator} {comp['index_ann_pct']}%/yr, "
            f"relative wealth ratio {comp['relative_wealth_ratio']}, annualized excess return "
            f"{comp['excess_return_pct']}%/yr. {comp['not_pme_note']} Disclosure: ratios on "
            "appraisal-lagged NAVs are window-sensitive and can be smoothing-flattered." + lc)
        doc.add_paragraph("Alignment: " + comp["alignment_note"].rstrip(".") + ".")
        doc.add_paragraph(
            "Two-point comparison: one contribution at the window start and one valuation at the end, "
            "on identical period boundaries. The ratio is fund growth divided by the comparator's growth "
            "over the same periods.")


def _benchmark_section(doc: Document, sel: dict, fdoc: dict | None = None) -> None:
    """Slot K, the reference comparison, the Lane A record, Slot G with its
    table, then the ledger (decision 7.1)."""
    sk = sel["slot_k"]
    doc.add_paragraph(f"Return basis for every comparison in this section: {sel['basis']['label'].rstrip('.')}.")
    if sk.get("escalation"):
        doc.add_heading("ESCALATION: no meaningful benchmark constructible", level=2)
        doc.add_paragraph(sk["escalation"])
        # no legal conclusion (R2-P0-9, audit round 2 item 29): the memo
        # states what the record holds and does not decide
        doc.add_paragraph(
            "No meaningful benchmark could be constructed from the data held. "
            "The record cannot support the paragraph (k) comparison until one "
            "is identified. This memo does not decide.")
    else:
        s = sk["selected"]
        doc.add_heading(f"{sk['label']}: {s['candidate']} (score {x_of_n(s['score'], s['max'])})", level=2)
        comp = s.get("comparison")
        if comp:
            _comparison_paragraphs(doc, comp, "the benchmark", fdoc)
        elif s.get("by_descriptor"):
            doc.add_paragraph(f"{BY_DESCRIPTOR_SENTENCE} The candidate is selected on its own descriptors. "
                              "No number is substituted.")
        else:
            doc.add_paragraph("Comparison not computed: "
                              f"{(s.get('comparison_note') or 'not computable on held data').rstrip('.')}. "
                              "The candidate is selected on its own descriptors. No number is substituted.")
        if sk.get("ties"):
            doc.add_paragraph(f"{TIE_SENTENCE} Tied with " + ", ".join(
                next((r["candidate"] for r in sel["rejected"] if r["id"] == t), t) for t in sk["ties"]) + ".")
        if sel.get("record_hash"):
            doc.add_paragraph(f"Selection recorded {sel['recorded_at'][:10]}, record {sel['record_hash'][:8]}. "
                              f"Rubric {sel.get('rubric_version')}. The full record hash is "
                              f"{sel['record_hash']}.")
        for r in s["reasons"]:
            doc.add_paragraph(r, style="List Bullet")
    ref = sel.get("reference_comparison")
    if ref:
        doc.add_heading(f"Reference comparison, not the meaningful benchmark: {ref['candidate']}", level=2)
        doc.add_paragraph(ref["note"][0].upper() + ref["note"][1:].rstrip(".") + ".")
        _comparison_paragraphs(doc, ref["comparison"], "the public series")
    # the fund's own declared benchmark or SEC-required comparator (cell
    # 5.1), typed, with its comparison whenever the index has a held series
    # (R2-P1-5, R2-P1-15)
    doc.add_heading("Declared benchmark and SEC-required comparators (cell 5.1)", level=2)
    decl = sel.get("declared") or []
    if not decl:
        doc.add_paragraph("The fund declares no benchmark: "
                          + (sel.get("declared_none_reason") or "cell 5.1").rstrip(".") + ".")
    for d in decl:
        doc.add_paragraph(f"{d['type_label'][0].upper()}{d['type_label'][1:]}: {d['name']}, {d['status']}. "
                          "The declaration itself earns no points.")
        if d.get("comparison"):
            _comparison_paragraphs(doc, d["comparison"], d["name"])
        elif d.get("comparison_note"):
            doc.add_paragraph(f"No comparison: {d['comparison_note'].rstrip('.')}.")
    if not any(d["type"] == "declared" for d in decl) and decl and sel.get("declared_none_reason"):
        doc.add_paragraph("Declared benchmark: none. " + sel["declared_none_reason"].rstrip(".") + ".")
    # Slot G
    g = sel.get("slot_g")
    if g:
        comp = g["composite"]
        doc.add_heading(f"{g['label']}: {g['cohort_label']}", level=2)
        doc.add_paragraph("Peers: " + ", ".join(g["member_names"]) + ". This is the history of similar "
                          "investments, not the benchmark, and it is never a public market equivalent.")
        if comp["status"] == "computed":
            _comparison_paragraphs(doc, comp, "the peer composite")
        else:
            doc.add_paragraph("Composite refused: " + comp["reason"].rstrip(".") + ". The side-by-side table "
                              "is shown without a ratio.")
        t = doc.add_table(rows=1, cols=2 + len(g["member_names"]) + 1)
        t.style = "Table Grid"
        h = t.rows[0].cells
        h[0].text, h[1].text = "Period", "n"
        cols = [FUND_SHORT_OF(sel["product"])] + g["member_names"]
        for i, name in enumerate(cols):
            h[2 + i].text = name
        for r in g["table"]:
            c = t.add_row().cells
            c[0].text, c[1].text = r["label"], str(r["n"])
            for i, name in enumerate(cols):
                v = r["returns"].get(name)
                c[2 + i].text = "n/a" if v is None else f"{v:g}%"
        doc.add_paragraph(g["survivorship_note"])
        doc.add_paragraph(g["heterogeneity_note"])
    doc.add_heading("Rejection log (candidates considered and not selected)", level=2)
    rt = doc.add_table(rows=1, cols=3)
    rt.style = "Table Grid"
    h = rt.rows[0].cells
    h[0].text, h[1].text, h[2].text = "Candidate", "Score", "Reason and criteria"
    for r in sel["rejected"]:
        c = rt.add_row().cells
        c[0].text = r["candidate"]
        c[1].text = x_of_n(r["score"], r["max"])
        # the criteria ride with the reason so a reader sees whether a
        # candidate lost on fit or on data absence (audit round 2 item 14)
        c[2].text = r["rejection"] + " Criteria: " + ", ".join(r["reasons"]) + "."
    for row in rt.rows:
        row.cells[0].width = Inches(2.0)
        row.cells[1].width = Inches(0.7)
        row.cells[2].width = Inches(3.8)


def FUND_SHORT_OF(key: str) -> str:
    return load_products()[key]["fund_name"].split(" (")[0]



def plan_findings(plan: dict, m: dict | None) -> dict[str, str]:
    """The plan-specific sentences for cells 3.7, 3.8 and 3.9, built from the
    memo's own plan record and its own match file. Counts and rates are the
    plan's; nothing comes from the product record."""
    out: dict[str, str] = {}
    part = plan.get("participants") or {}
    wab = part.get("with_account_balances")
    sep = part.get("separated_deferred_vested")
    act = part.get("active_eoy")
    ret = part.get("retired_receiving")
    del sep, act, ret
    if wab:
        out["3.7"] = plan_demand_sentence(plan)
    if m:
        ss = m.get("stressed_scenario") or {}
        sc = m.get("scenario") or {}
        cap = ss.get("annual_wrapper_capacity_pct")
        if (m.get("wrapper_facts") or {}).get("exchange"):
            out["3.8"] = ("Redemption stress test not applicable: the wrapper is exchange-traded with continuous "
                          "dealing, so there is no wrapper capacity to stress.")
        elif ss:
            out["3.8"] = (f"ILLUSTRATIVE redemption stress test for this plan: filed outflow proxy "
                          f"{sc.get('filed_outflow_proxy_pct', 'n/a')}% of the position, slider assumption "
                          f"{sc.get('slider_assumption_pct', 'n/a')}%, stressed demand {ss.get('demand_pct_of_position')}% "
                          f"vs {cap:g}% annual wrapper capacity, {str(ss.get('outcome', '')).rstrip('.')}. "
                          "Source: this plan's liquidity match.")
        out["3.9"] = (f"Structural liquidity verdict {str(m.get('verdict', '')).upper()} (dealing terms on record, plan-independent). "
                      f"Scenario verdict under this plan (ILLUSTRATIVE): "
                      f"{str(m.get('scenario_verdict') or 'not computable').upper()}. Source: this plan's liquidity match.")
    return out


def build_memo(key: str, plan_key: str, out_dir: Path | None = None) -> Path:
    products = load_products()
    p = products[key]
    anchor = load_plan(plan_key)
    sel_path = DATA / "benchmarks" / f"{key}_selection.json"
    sel = json.loads(sel_path.read_text()) if sel_path.exists() else None

    doc = Document()
    _set_letter(doc)
    doc.styles["Normal"].font.size = Pt(10.5)

    doc.add_heading("Designated Investment Alternative Evaluation: "
                    "Decision Memo", level=0)
    sub = doc.add_paragraph()
    sub.add_run(f"Plan: {anchor['display_label']}\n").bold = True
    sub.add_run(f"Product: {p['fund_name']} ({p['wrapper']}, CIK {p['cik']})\n")
    sub.add_run(f"Date: {record_as_of()}    Status: DRAFT (demo "
                "build). Cells marked extracted-unverified pend independent "
                "verification.")

    doc.add_heading("Regulatory basis", level=1)
    auth = authority()
    doc.add_paragraph(f"{RULE['issuer']}, proposed rule {RULE_CITATION}. Federal Register "
                      f"document {RULE['fr_document']}, {RULE['fr_url']}. Docket {RULE['docket']}, "
                      f"{RULE['docket_url']}.")
    for para in RULE_PARAS:
        doc.add_paragraph(para)
    doc.add_paragraph("Factor mapping basis: " + rule_ref("1.1", auth)["basis"] + ". "
                      + ("The rule paragraph under each letter follows verbatim and the full text of "
                         "paragraphs (g) to (l), examples included, is the appendix at the end of this memo."
                         if auth["status"] == "fetched" else auth["note"])
                      + " Cells " + " and ".join(ADVISOR_COMPLETED)
                      + " are advisor-completed under paragraph (l).")
    if auth["status"] == "fetched":
        # the first paragraph under each letter is the rule text itself, the
        # rest are the Department's examples: quote the rule text here
        for letter in "ghijkl":
            paras = (auth.get("paragraphs") or {}).get(letter) or []
            if paras:
                doc.add_paragraph(paras[0], style="Intense Quote")
        doc.add_paragraph(f"Source: Federal Register document {RULE['fr_document']}, fetched "
                          f"{auth.get('fetched_at', 'on the date in the authority manifest')}, "
                          f"content hash {auth.get('sha256', '')[:16]}. Nothing in the quoted text is Tark's.")

    facts_path = DATA / "facts" / f"{key}.json"
    fdoc = json.loads(facts_path.read_text()) if facts_path.exists() else {}
    fbc = facts_by_cell(fdoc.get("facts", {}))

    _mp = DATA / "liquidity" / f"{plan_key}__{key}_match.json"
    _plan_lines = plan_findings(anchor, json.loads(_mp.read_text()) if _mp.exists() else None)
    doc.add_heading("Six-factor findings", level=1)
    doc.add_paragraph(
        "Per factor: the facts on record the computations read (each cites its cell), "
        "then the complete first sentence of every evidenced cell with its "
        "status, then the cells marked not applicable with the reason. The "
        "full sourced text, quote and document of every cell is in "
        "the evidence ledger and on the Evaluation view.")
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text = "Factor", "Findings (cell, status, first sentence)"
    for n, label in FACTORS.items():
        row = table.add_row().cells
        row[0].text = f"{n}. {label} ({FACTOR_PARAS[n]})"
        _fill(row[1], _findings(p, label, fbc, _plan_lines))
    for row in table.rows:
        row.cells[0].width, row.cells[1].width = Inches(1.2), Inches(5.3)

    doc.add_heading("Benchmark selection and justification", level=1)
    if sel is None:
        doc.add_paragraph("Selection pending for this product: "
                          "extraction depth required before selection.")
    else:
        _benchmark_section(doc, sel, fdoc)

    # ---- product-to-plan liquidity match for THIS plan ----
    mp = DATA / "liquidity" / f"{plan_key}__{key}_match.json"
    m = json.loads(mp.read_text()) if mp.exists() else None
    _liquidity_section(doc, m, fdoc, anchor)

    # ---- cohort placement + exclusion log (peer-comparison layer) ----
    if fdoc:
        cid = fdoc.get("cohort_id")
        cpath = DATA / "cohorts" / f"{cid}.json"
        if cid and cpath.exists():
            co = json.loads(cpath.read_text())
            doc.add_heading("Peer cohort placement", level=1)
            doc.add_paragraph(
                f"Evidence depth tier: {fdoc.get('depth', 'cohort').upper()}. "
                f"Cohort: {co['label']} (n={co['n']}). Membership rationale: "
                f"{display_copy(fdoc.get('membership_rationale', ''))}")
            v29 = p["cells"]["2.9"].get("value")
            if v29:
                doc.add_paragraph(display_copy(v29))
            comp = co.get("composite", {})
            if comp.get("refused"):
                doc.add_paragraph("Cohort composite: REFUSED, "
                                  + comp.get("reason", ""))
            elif comp.get("composite_refused_reason"):
                doc.add_paragraph("Cohort composite return: not formed, "
                                  + comp["composite_refused_reason"].rstrip(".") + ".")
            for cv in co.get("caveats", []):
                doc.add_paragraph(f"Caveat: {display_copy(cv)}", style="List Bullet")
            doc.add_paragraph(
                "Cohort exclusion log: every candidate considered and not "
                "admitted is recorded with its reason in the roster decisions "
                "record (shown on the Cohorts view). Membership is an "
                "argued judgment, not a tag.")

    stated = _advisor_section(doc, key, plan_key, anchor)
    _recommendation_section(doc, sel, m, fdoc, anchor, stated, p)
    _scope_section(doc)
    _case_law_section(doc, p)

    _provenance_section(doc, key, p, anchor)

    if auth["status"] == "fetched":
        doc.add_heading("Appendix: verbatim regulatory text", level=1)
        doc.add_paragraph(auth["note"] + f". Federal Register document {RULE['fr_document']}, fetched "
                          f"{auth.get('fetched_at', 'on the date in the authority manifest')}, content hash "
                          f"{auth.get('sha256', '')}. Runs of whitespace inside a paragraph are collapsed to "
                          "one space. Every paragraph below is the Federal Register text unchanged.")
        for letter, paras in auth["paragraphs"].items():
            doc.add_heading(f"Paragraph ({letter})", level=2)
            for t in paras:
                doc.add_paragraph(t)

    sig = doc.add_paragraph()
    sig.add_run("\nPrepared by: ______________________    "
                "Reviewed by: ______________________    "
                "Date: ____________")
    sig.alignment = WD_ALIGN_PARAGRAPH.LEFT

    out = out_dir or SITE_MEMOS
    out.mkdir(parents=True, exist_ok=True)
    path = out / memo_name(plan_key, key)
    _save(doc, path)
    return path


def write_all(out_dir: Path | None = None) -> list[Path]:
    """Every plan x product memo, stale docx files in out_dir removed first."""
    out = out_dir or SITE_MEMOS
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*_decision_memo.docx"):
        stale.unlink()
    return [build_memo(key, plan_key, out)
            for plan_key in plan_keys() for key in load_products()]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    paths = write_all(Path(a.out) if a.out else None)
    print(f"wrote {len(paths)} memos to {paths[0].parent}")

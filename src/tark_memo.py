"""
Tark Investment Selection Record (R3-P2-13 to R3-P2-17, decision 8.6 and 8.33).

One Word document per plan and product, site/memos/<plan>__<product>_selection_record.docx,
replaces the decision memo and the committee packet. Its first page is the
decision summary and the signature block. Every figure in it is a cited cell,
a figure read from a cited cell, or a computation from cited series, printed
through the copy layer (tark_display.display_copy). The verbatim text of
paragraphs (g) to (l) is Attachment A, one file written once and cited by its
content hash. The record does not decide: the fiduciary decides on it.

Layout (R3-P2-16): letter page, one-inch margins, every table on a fixed
grid whose columns sum to the text width, the header row repeated and no
row split across pages, headings kept with the next paragraph, a running
header and a footer with the page count, core properties set from the
record's as-of date, never the wall clock, so identical content gives
identical bytes.

Run:  python src/tark_memo.py [--out DIR]
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

import csv

from tark_data import (ADVISOR_COMPLETED, ADVISOR_NOT_EVIDENCE, ADVISOR_STATED_CELLS, CELLS,
                       DATA, FACTOR_PARAS, FACTORS, RULE, RULE_CITATION, authority,
                       cells_by_factor, coverage_summary, load_advisor, load_plan,
                       load_products, plan_keys, record_as_of, rule_ref, status_kind)
from tark_benchmark_common import (BY_DESCRIPTOR_SENTENCE, CRITERIA, CRITERION_DEFINITION, CRITERION_LABEL,
                                   CRITERION_MAX, METRIC_DEFINITION, MIN_PRIMARY_SCORE, RUBRIC_LABEL, RUBRIC_MAX,
                                   STRATEGY_GATE_MIN, TIE_SENTENCE, x_of_n)
from tark_display import (BASE_LABEL, WRAPPER_LABEL, _money as money, display_copy, display_path_free,
                          fact_label, facts_by_cell, fmt_early, fmt_incentive, lane_label,
                          plan_demand_sentence, reconciliation_sentence, typed_headline)

SITE_MEMOS = Path(__file__).resolve().parents[1] / "site" / "memos"
TEXT_WIDTH_IN = 6.5          # letter page, one-inch margins
TWIPS_PER_INCH = 1440
DOCUMENT_TITLE = "Investment Selection Record"

RULE_PARAS = [
    ("This record documents an evaluation of the product below as a candidate designated "
     "investment alternative for the plan named above, structured on the six factors of "
     "the proposed rule, paragraphs (g) to (l) of proposed 29 CFR 2550.404a-6: performance "
     "(g), fees and expenses (h), liquidity (i), valuation (j), performance benchmarks (k), "
     "complexity (l). The regulation is cited, not paraphrased. This record and its underlying "
     "evidence files are the record of the evaluation."),
    ("The benchmark section documents the selection AND the rejections: every candidate "
     "considered, its score, and the true reason it was or was not chosen. Case law is "
     "addressed in its own section below, from cell 5.7 only."),
]

# cells the adopting committee completes for its own plan (P2-6 makes them
# advisor-stated with signer and date). Listed in the recommendation so the
# record never implies it decided them.
COMMITTEE_CELLS = ("6.6", "6.8", "3.7", "2.8", "3.5", "4.9")
# the fee and terms cells the record tabulates on their own (the packet's Exhibit C)
FEE_CELLS = ("2.1", "2.2", "2.3", "2.4", "2.6", "2.7", "6.4")

KIND_LABEL = {"extracted": "extracted-unverified", "verified": "verified",
              "computed": "computed", "partial": "partial", "structured": "structured"}
EVIDENCED = tuple(KIND_LABEL)
RESOLVED_KINDS = ("structured", "extracted", "verified", "computed")
KIND_ORDER = (("structured", "structured"), ("extracted", "extracted-unverified"),
              ("verified", "verified"), ("computed", "computed"), ("partial", "partial"),
              ("fetched", "fetched"), ("na", "n/a"), ("pending", "pending"))
RESOLVED_ONE = ("exact", "form_only")

# the abbreviation-aware splitter is shared with the site (R2-P0-4)
from tark_display import ends_at_abbreviation, first_sentence  # noqa: E402,F401


# ------------------------------------------------------------ the copy layer in Word
def P(doc, text: str, style: str | None = None, keep: bool = False, verbatim: bool = False):
    """One paragraph through the copy layer. A verbatim paragraph (the rule's
    own words) is never rewritten."""
    t = text if verbatim else display_copy(text)
    p = doc.add_paragraph(t, style=style) if style else doc.add_paragraph(t)
    if keep:
        p.paragraph_format.keep_with_next = True
    return p


def H(doc, text: str, level: int):
    h = doc.add_heading(display_copy(text), level=level)
    h.paragraph_format.keep_with_next = True
    return h


def _fill(cell, lines: list[str], verbatim: bool = False) -> None:
    """One paragraph per line inside a table cell (no newline joins), each
    through the copy layer unless the lines are provenance set verbatim (an
    accession, a URL)."""
    cp = (lambda t: t) if verbatim else display_copy
    cell.paragraphs[0].text = cp(lines[0])
    for line in lines[1:]:
        cell.add_paragraph(cp(line))


def _set(cell, text: str, verbatim: bool = False) -> None:
    cell.text = text if verbatim else display_copy(str(text))


# ------------------------------------------------------------ layout (R3-P2-16)
def _table(doc, headers: list[str], widths_in: list[float]):
    """A table on a fixed grid: the columns sum to the text width, the
    header row repeats on every page, no row splits across pages. Rows are
    added by the caller, then _finish_table sets every width."""
    assert abs(sum(widths_in) - TEXT_WIDTH_IN) < 1e-6, widths_in
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.autofit = False
    tblPr = t._tbl.tblPr
    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = OxmlElement("w:tblW")
        tblPr.append(tblW)
    tblW.set(qn("w:type"), "dxa")
    tblW.set(qn("w:w"), str(int(TEXT_WIDTH_IN * TWIPS_PER_INCH)))
    for i, h in enumerate(headers):
        _set(t.rows[0].cells[i], h)
    t._tark_widths = widths_in
    return t


def _finish_table(t) -> None:
    widths = t._tark_widths
    for i, w in enumerate(widths):
        t.columns[i].width = Inches(w)
    for r, row in enumerate(t.rows):
        trPr = row._tr.get_or_add_trPr()
        if r == 0:
            hdr = OxmlElement("w:tblHeader")
            trPr.append(hdr)
        cant = OxmlElement("w:cantSplit")
        trPr.append(cant)
        for i, w in enumerate(widths):
            if i < len(row.cells):
                row.cells[i].width = Inches(w)


def _field(paragraph, instr: str, placeholder: str) -> None:
    """A Word field (PAGE, NUMPAGES, TOC) as begin, instruction, separate,
    placeholder result, end. Word refreshes it on open."""
    r = paragraph.add_run()
    fld = OxmlElement("w:fldChar")
    fld.set(qn("w:fldCharType"), "begin")
    r._r.append(fld)
    r = paragraph.add_run()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = instr
    r._r.append(it)
    r = paragraph.add_run()
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    r._r.append(sep)
    paragraph.add_run(placeholder)
    r = paragraph.add_run()
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    r._r.append(end)


def _page_setup(doc, title: str, subtitle: str) -> None:
    """Letter page, one-inch margins, a running header and a footer with the
    page count, the record's as-of date and the DRAFT mark."""
    s = doc.sections[0]
    s.page_width, s.page_height = Inches(8.5), Inches(11)
    for m in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(s, m, Inches(1))
    hp = s.header.paragraphs[0]
    hp.text = display_copy(f"{title}. {subtitle}")
    hp.style = doc.styles["Header"]
    fp = s.footer.paragraphs[0]
    fp.style = doc.styles["Footer"]
    fp.add_run("Page ")
    _field(fp, "PAGE", "1")
    fp.add_run(" of ")
    _field(fp, "NUMPAGES", "1")
    fp.add_run(display_copy(f". Record as of {record_as_of()}. DRAFT."))
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER


def _core_properties(doc, title: str, subject: str, keywords: str) -> None:
    """Document properties from the record, never from the wall clock, so the
    bytes reproduce."""
    cp = doc.core_properties
    stamp = datetime.strptime(record_as_of(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    cp.title = title
    cp.subject = subject
    cp.author = "Tark"
    cp.last_modified_by = "Tark"
    cp.keywords = keywords
    cp.category = DOCUMENT_TITLE
    cp.comments = "Generated from the record. The fiduciary decides on it."
    cp.created = stamp
    cp.modified = stamp
    cp.revision = 1


def _toc(doc) -> None:
    """A table of contents field over headings 1 and 2. Word refreshes it on
    open (updateFields), so the placeholder is what a plain text export shows."""
    p = doc.add_paragraph()
    _field(p, 'TOC \\o "1-2" \\h \\z \\u', "Table of contents: updated when the document is opened in Word.")
    settings = doc.settings.element
    uf = OxmlElement("w:updateFields")
    uf.set(qn("w:val"), "true")
    settings.append(uf)


def _keep_tables_with_lead(doc) -> None:
    """The paragraph before every table stays on the table's page."""
    body = doc.element.body
    prev = None
    for child in body.iterchildren():
        if child.tag == qn("w:tbl") and prev is not None and prev.tag == qn("w:p"):
            pPr = prev.get_or_add_pPr()
            if pPr.find(qn("w:keepNext")) is None:
                pPr.append(OxmlElement("w:keepNext"))
        prev = child


def _save(doc, path: Path) -> None:
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


def _set_letter(doc) -> None:   # kept for the tests that import it
    s = doc.sections[0]
    s.page_width, s.page_height = Inches(8.5), Inches(11)
    for m in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(s, m, Inches(1))


# ------------------------------------------------------------ names
def record_name(plan_key: str, key: str) -> str:
    return f"{plan_key}__{key}_selection_record.docx"


memo_name = record_name     # the older name, still imported by the gates


def attachment_name(auth: dict | None = None) -> str | None:
    a = auth or authority()
    if a.get("status") != "fetched" or not a.get("sha256"):
        return None
    return f"attachment_a_rule_text_{a['sha256'][:12]}.docx"


def cell_title(cid: str) -> str:
    c = CELLS[cid]
    return c if isinstance(c, str) else c.get("title", cid)


def FUND_SHORT_OF(key: str) -> str:
    return load_products()[key]["fund_name"].split(" (")[0]


def _fact_value(fdoc: dict, field: str):
    f = (fdoc.get("facts") or {}).get(field) or {}
    return f.get("value"), f.get("source_cell", ""), f.get("null_reason") or ""


# ------------------------------------------------------------ the six factors
def _findings(product: dict, factor_label: str, fbc: dict, overrides: dict | None = None) -> list[str]:
    """One paragraph per line: the facts on record for the factor's cells,
    then the complete first sentence of every evidenced cell, then the cells
    marked not applicable with their reasons. Nothing is truncated. An
    override replaces the record's sentence for a cell whose content is a
    property of the plan the record is for (3.7, 3.8, 3.9), so the record
    for one plan never prints another plan's numbers (R2-P1-13)."""
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
        # a headline that ends with a period (an auditor's name) never doubles it
        out.append("Facts on record: " + ". ".join(t.rstrip(".") for t in typed) + ".")
    out.extend(lines)
    if na:
        out.append("Not applicable: " + ". ".join(n.rstrip(".") for n in na) + ".")
    return out or ["No cell evaluated for this factor."]


def factor_lead(n: str, fdoc: dict, reg: dict, sel: dict | None, m: dict | None) -> str:
    """One generated sentence per factor from the facts on record (R3-P2-14),
    each clause naming its cell. A clause whose fact is not on record is
    left out, never filled in."""
    fx = fdoc.get("facts") or {}

    def val(field):
        return (fx.get(field) or {}).get("value")

    def cell(field):
        return (fx.get(field) or {}).get("source_cell", "")

    parts: list[str] = []
    if n == "1":
        if val("inception") and val("track_record_years") is not None:
            parts.append(f"the record holds {val('track_record_years'):g} years of history since "
                         f"{val('inception')} (cell {cell('inception')})")
        if val("net_assets_usd") is not None:
            approx = "approx. " if (fx.get("net_assets_usd") or {}).get("approx") else ""
            parts.append(f"net assets of {approx}{money(val('net_assets_usd'))} (cell {cell('net_assets_usd')})")
        if val("pme_public_proxy") is not None and val("pme_public_proxy_name"):
            parts.append(f"a KS-PME of {val('pme_public_proxy')} against {val('pme_public_proxy_name')} "
                         f"(cell {cell('pme_public_proxy')})")
        if val("peer_relative_wealth_ratio") is not None:
            parts.append(f"a relative wealth ratio of {val('peer_relative_wealth_ratio')} against the peer "
                         f"composite (cell {cell('peer_relative_wealth_ratio')})")
        head = "On performance (g), "
        tail = "no return series is on record for a public market comparison"
    elif n == "2":
        if val("mgmt_fee_pct") is not None:
            base = BASE_LABEL.get(val("mgmt_fee_base"), val("mgmt_fee_base") or "a base not on record")
            parts.append(f"the management fee is {val('mgmt_fee_pct'):.2f}% on {base} (cell {cell('mgmt_fee_pct')})")
        if val("incentive_fee") is not None:
            parts.append(f"the incentive fee is {fmt_incentive(val('incentive_fee'))} (cell {cell('incentive_fee')})")
        if val("expense_ratio_pct") is not None:
            basis = (fx.get("expense_ratio_pct") or {}).get("basis") or ""
            parts.append(f"the expense ratio is {val('expense_ratio_pct'):.2f}%"
                         + (f" ({basis})" if basis else "") + f" (cell {cell('expense_ratio_pct')})")
        if val("early_repurchase") is not None:
            parts.append(f"the early repurchase fee is {fmt_early(val('early_repurchase'))} (cell {cell('early_repurchase')})")
        head = "On fees and expenses (h), "
        tail = "no fee figure is on record"
    elif n == "3":
        wf = (m or {}).get("wrapper_facts") or {}
        if wf.get("dealing_label"):
            parts.append(f"the wrapper deals by {wf['dealing_label']}")
        if wf.get("program_status"):
            parts.append(f"the repurchase program is {wf['program_status']}"
                         + (f" as of {wf['program_status_as_of']}" if wf.get("program_status_as_of") else "")
                         + " (cell 3.1)")
        if wf.get("gate_history") is not None:
            parts.append(("requests have been prorated under stress before" if wf["gate_history"]
                          else "no proration is identified in the filings on record") + " (cell 3.3)")
        if m and m.get("scenario", {}).get("filed_outflow_proxy_pct") is not None:
            parts.append(f"the plan's filed outflow proxy is {m['scenario']['filed_outflow_proxy_pct']:.1f}% "
                         "of the position per year (the plan record)")
        if m:
            parts.append(f"the structural verdict is {m['verdict']} with the scenario verdict "
                         f"{m.get('scenario_verdict') or 'not computable'} under this plan (ILLUSTRATIVE, cell 3.9)")
        head = "On liquidity (i), "
        tail = "no dealing terms are on record"
    elif n == "4":
        if reg.get("pricing_class"):
            parts.append("the holder transacts at " + ("NAV" if reg["pricing_class"] == "NAV" else "the market price")
                         + (f" struck {reg['nav_cadence']}" if reg.get("nav_cadence") else "")
                         + " (the registry descriptors)")
        if val("auditor"):
            parts.append(f"the auditor is {val('auditor')}" + (" (Big 4)" if val("big4") else "")
                         + f" (cell {cell('auditor')})")
        head = "On valuation (j), "
        tail = "no valuation fact is on record"
    elif n == "5":
        sk = (sel or {}).get("slot_k") or {}
        if sk.get("escalation"):
            parts.append("no meaningful benchmark could be constructed from the data held (cell 5.6)")
        elif sk.get("selected"):
            s = sk["selected"]
            comp = s.get("comparison") or {}
            parts.append(f"the meaningful benchmark is {s['candidate']}, scored {x_of_n(s['score'], s['max'])} (cell 5.3)")
            if comp.get("kind") == "series":
                parts.append(f"KS-PME {comp['ks_pme']} and Direct Alpha {comp['direct_alpha_pct']}%/yr over "
                             f"{comp['window']} (cell 1.8)")
            elif comp:
                parts.append(f"a relative wealth ratio of {comp['relative_wealth_ratio']} over {comp['window']} (cell 1.8)")
            elif s.get("by_descriptor"):
                parts.append(BY_DESCRIPTOR_SENTENCE.rstrip(".").lower()[0] + BY_DESCRIPTOR_SENTENCE.rstrip(".")[1:])
        head = "On performance benchmarks (k), "
        tail = "no selection is on record"
    else:
        if val("wrapper_type"):
            parts.append(f"the wrapper is {WRAPPER_LABEL.get(val('wrapper_type'), val('wrapper_type'))} "
                         f"(cell {cell('wrapper_type')})")
        if val("tax_form"):
            parts.append("tax reporting is " + {"1099": "Form 1099", "K-1": "Schedule K-1"}.get(val("tax_form"), val("tax_form"))
                         + f" (cell {cell('tax_form')})")
        parts.append("cells " + " and ".join(ADVISOR_COMPLETED) + " are advisor-completed under paragraph (l)")
        head = "On complexity (l), "
        tail = "no complexity fact is on record"
    if not parts:
        return head + tail + "."
    if len(parts) == 1:
        return head + parts[0] + "."
    return head + ", ".join(parts[:-1]) + " and " + parts[-1] + "."


def plan_findings(plan: dict, m: dict | None) -> dict[str, str]:
    """The plan-specific sentences for cells 3.7, 3.8 and 3.9, built from the
    record's own plan record and its own match file. Counts and rates are
    the plan's; nothing comes from the product record."""
    out: dict[str, str] = {}
    part = plan.get("participants") or {}
    if part.get("with_account_balances"):
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


# ------------------------------------------------------------ liquidity
def _liquidity_section(doc, m: dict | None, fdoc: dict, plan: dict, heading: bool = True) -> None:
    if heading:
        H(doc, "Product-to-plan liquidity match", 1)
    if m is None:
        P(doc, "No liquidity match record exists for this plan and product.")
        return
    P(doc, f"Plan: {plan['display_label']}. {m['layers']}")
    H(doc, "Structural verdict (dealing terms on record, plan-independent)", 2)
    P(doc, m["verdict"].upper())
    for r in m["structural_reasons"]:
        P(doc, r, style="List Bullet")
    wf = m["wrapper_facts"]
    t = _table(doc, ["Wrapper fact", "Value", "Cell"], [1.7, 4.0, 0.8])
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
        _set(c[0], label)
        if shown is None:
            reason = wf.get("null_reasons", {}).get(field) or null_reason or "not on record"
            _set(c[1], f"not on record: {reason}")
        else:
            _set(c[1], str(shown))
        _set(c[2], src or "")
    _finish_table(t)

    H(doc, "Scenario (ILLUSTRATIVE, this plan)", 2)
    sc, pi, ss = m["scenario"], m["plan_inputs"], m["stressed_scenario"]
    fo = m.get("filed_outflow") or {}
    cap = sc.get("annual_wrapper_capacity_pct")
    cap_text = ("not applicable (exchange-traded)" if wf.get("exchange")
                else "not computable (3.1)" if cap is None else f"{cap:g}%")
    filed = sc.get("filed_outflow_proxy_pct")
    P(doc, f"Plan inputs (Form 5500): net assets {money(pi['net_assets'])}, liquidity tail "
           f"{pi['tail_share_pct']}% of accounts ({int(pi['separated_with_balances']):,} "
           "separated participants with balances)"
           + (f", filed outflow proxy {filed:.1f}% of beginning net assets per year "
              f"({fo.get('source', 'the plan record')}: {fo.get('what', '')})."
              if filed is not None else ", no filed outflow proxy in the plan record."))
    if filed is not None:
        P(doc, f"Base demand (filed outflow proxy applied to a {sc['allocation_pct_of_plan']:g}% "
               f"allocation = {money(sc['plan_allocation_usd'])}): "
               f"{money(sc['filed_annual_demand_usd'])}/yr = {filed:.1f}% of the position per year "
               f"vs annual wrapper capacity {cap_text}.")
    P(doc, "Slider assumption (adjustable on the Liquidity view, not a fact): tail turnover "
           f"{sc['tail_annual_turnover_pct']:g}%/yr, active turnover "
           f"{sc['active_annual_turnover_pct']:g}%/yr, {sc['slider_assumption_pct']}% of the "
           f"position per year = {money(sc['slider_annual_demand_usd'])}/yr, shown beside the "
           "filed rate, not blended with it.")
    if ss.get("demand_pct_of_position") is not None:
        P(doc, f"Stressed ({ss['assumptions']}): demand {money(ss['annual_demand_usd'])}/yr = "
               f"{ss['demand_pct_of_position']}% of the position. {ss['outcome']}.")
    else:
        P(doc, f"Stressed ({ss['assumptions']}): {ss['outcome']}.")
    fc = sc.get("fund_capacity") or {}
    if fc.get("available"):
        P(doc, f"Fund capacity in dollars: {money(fc['annual_capacity_usd'])} per year "
               f"({cap:g}% of {'approx. ' if fc.get('net_assets_approx') else ''}"
               f"{money(fc['fund_net_assets_usd'])} net assets, cell {fc.get('net_assets_cell')}). "
               f"The plan's demand at the filed rate is {money(fc['plan_annual_demand_usd'])} per "
               f"year, {fc['plan_share_of_fund_capacity_pct']:.2f}% of that capacity, a claim "
               "shared with every other holder.")
    elif fc.get("reason") and not wf.get("exchange"):
        P(doc, f"Fund capacity in dollars: not computable, {fc['reason']}.")
    P(doc, "Scenario verdict (ILLUSTRATIVE, this plan): "
           f"{(m.get('scenario_verdict') or 'not computable').upper()}.")
    for r in m["scenario_reasons"]:
        P(doc, r, style="List Bullet")
    P(doc, "Cited: " + ", ".join(f"cell {c}" if c[:1].isdigit() else c for c in m["citations"]) + ".")


# ------------------------------------------------------------ flags, adviser inputs, recommendation
def _flags(sel: dict | None, m: dict | None, fdoc: dict) -> list[str]:
    """Flags raised by the record. Each restates a recorded value or a
    verdict already in the record, with its source. None is a new judgment."""
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


def _advisor_section(doc, key: str, plan_key: str, plan: dict) -> dict:
    """Advisor-stated inputs for this plan and product: cells the fiduciary
    completes, signed and dated. Inputs, not evidence."""
    H(doc, "Advisor-stated inputs (this plan)", 1)
    P(doc, ADVISOR_NOT_EVIDENCE)
    entries = (load_advisor(plan_key, key) or {}).get("cells") or {}
    if not entries:
        P(doc, f"None stated for {plan['display_label']}. The six committee cells ("
               + ", ".join(f"{c} {cell_title(c)}" for c in ADVISOR_STATED_CELLS) + ") remain open.")
        return entries
    t = _table(doc, ["Cell", "Statement", "Signer", "Date"], [1.2, 3.3, 1.2, 0.8])
    for cid in ADVISOR_STATED_CELLS:
        e = entries.get(cid)
        if e:
            r = t.add_row().cells
            _set(r[0], f"{cid} {cell_title(cid)}")
            _set(r[1], e["value"])
            _set(r[2], e["signer"])
            _set(r[3], e["date"])
    _finish_table(t)
    return entries


def committee_cell_state(cid: str, product: dict, stated: dict) -> str:
    """stated, not applicable with the record's reason, or open (R3-P2-17b)."""
    if cid in stated:
        return "stated"
    if cid in ADVISOR_COMPLETED:
        return "open"     # advisor-completed by design, never not applicable
    st = str((product.get("cells", {}).get(cid) or {}).get("status", ""))
    if status_kind(st) == "n/a":
        reason = st.split(":", 1)[1].strip() if ":" in st else st[3:].strip(" -")
        return "not applicable" + (f": {reason.rstrip('.')}" if reason else "")
    return "open"


def _peer_line(sel: dict) -> str:
    g = ((sel.get("slot_g") or {}).get("composite") or {})
    if g.get("status") == "computed":
        return (f"Peer comparison (paragraphs (g) and (h)): relative wealth ratio {g['relative_wealth_ratio']} vs the "
                f"equal-weight peer composite over {g['window']} (n={g['n']}), not a benchmark and not a PME.")
    if g:
        return f"Peer comparison (paragraphs (g) and (h)): composite refused, {g['reason'].rstrip('.')}."
    return "Peer comparison (paragraphs (g) and (h)): no cohort on record."


def _stat_line(comp: dict) -> str:
    """The comparison's statistic named for its comparator (rule 12)."""
    if comp.get("kind") != "series":
        return (f"relative wealth ratio {comp['relative_wealth_ratio']}, annualized "
                f"excess return {comp['excess_return_pct']}%/yr (not a public market equivalent)")
    return f"KS-PME {comp['ks_pme']}, Direct Alpha {comp['direct_alpha_pct']}%/yr"


def _summary_section(doc, key: str, product: dict, plan: dict, sel: dict | None, m: dict | None,
                     fdoc: dict, stated: dict) -> None:
    """Page one: both verdicts, the benchmark state, the peer ratio, the
    flags, the coverage and signed counts, the adviser inputs count, the
    recommendation and the sentence that the record does not decide, then the
    signature block."""
    H(doc, "Decision summary", 1)
    if m:
        P(doc, f"Structural liquidity verdict: {m['verdict'].upper()} (dealing terms on record, plan-independent). "
               f"Scenario verdict under {plan['display_label']} (ILLUSTRATIVE): "
               f"{(m.get('scenario_verdict') or 'not computable').upper()}.")
    else:
        P(doc, "Structural liquidity verdict: no liquidity match record for this plan and product.")
    if sel is None:
        P(doc, "Benchmark: no selection record for this product.")
    elif (sel.get("slot_k") or {}).get("escalation"):
        P(doc, "Benchmark: escalated. " + sel["slot_k"]["escalation"])
        P(doc, _peer_line(sel))
    else:
        pr = sel["slot_k"]["selected"]
        comp = pr.get("comparison") or {}
        line = f"Meaningful benchmark (paragraph (k)): {pr['candidate']} at {x_of_n(pr['score'], pr['max'])}"
        if comp:
            line += f", {_stat_line(comp)} over {comp['window']}"
        elif pr.get("by_descriptor"):
            line += f", cited, series not in the record. {BY_DESCRIPTOR_SENTENCE.rstrip('.')}"
        else:
            line += f", no comparison computed ({(pr.get('comparison_note') or 'not computable').rstrip('.')})"
        P(doc, line + ". " + _peer_line(sel))
        ref = sel.get("reference_comparison")
        if ref:
            P(doc, f"Reference comparison, not the meaningful benchmark: {ref['candidate']}, "
                   f"{_stat_line(ref['comparison'])} over {ref['comparison']['window']}.")
    cov = coverage_summary(key)
    P(doc, f"Evidence coverage: {cov['headline']}. Verified by a person: {cov['verified']}. "
           f"Advisor-stated inputs for this plan: {len(stated)} of {len(ADVISOR_STATED_CELLS)}.")
    H(doc, "Recommendation", 2)
    flags = _flags(sel, m, fdoc)
    P(doc, "Flags raised by the record (each restates a recorded value or verdict "
           "already in the record, with its source):", keep=True)
    for f in flags or ["none"]:
        P(doc, f, style="List Bullet")
    P(doc, "This record does not decide. The fiduciary makes the decision on this record. "
           "The committee-completed cells stay the committee's to complete for its own plan "
           "before it does: " + ", ".join(f"{c} {cell_title(c)} ({committee_cell_state(c, product, stated)})"
                                          for c in COMMITTEE_CELLS) + ".")
    H(doc, "Committee action and signatures", 2)
    P(doc, "The committee records its action on this product for this plan and signs below. "
           "A signature adopts the record as read, it does not verify a cell: verification is "
           "the separate signed act on the evidence ledger.", keep=True)
    t = _table(doc, ["Role", "Name and title", "Signature", "Date"], [1.6, 2.4, 1.6, 0.9])
    r = t.add_row().cells
    _set(r[0], "Committee action")
    merged = r[1].merge(r[3])
    _set(merged, "Select    Decline    Defer    (mark one)")
    for role in ("Adopting fiduciary", "Adviser", "Committee secretary"):
        r = t.add_row().cells
        _set(r[0], role)
    _finish_table(t)
    P(doc, f"Record as of {record_as_of()}. Status: DRAFT until signed.")


# ------------------------------------------------------------ regulatory basis, scope, case law
def _regulatory_basis(doc, auth: dict) -> None:
    H(doc, "Regulatory basis", 1)
    P(doc, f"{RULE['issuer']}, proposed rule {RULE_CITATION}. Federal Register "
           f"document {RULE['fr_document']}, {RULE['fr_url']}. Docket {RULE['docket']}, "
           f"{RULE['docket_url']}.")
    for para in RULE_PARAS:
        P(doc, para)
    P(doc, "Factor mapping basis: " + rule_ref("1.1", auth)["basis"] + ". "
           + (("The rule paragraph under each letter follows verbatim. The full text of "
               "paragraphs (g) to (l), examples included, is Attachment A, one document shared by "
               f"every record and named by its content hash, {auth.get('sha256', '')}.")
              if auth["status"] == "fetched" else auth["note"])
           + " Cells " + " and ".join(ADVISOR_COMPLETED)
           + " are advisor-completed under paragraph (l).")
    if auth["status"] == "fetched":
        # the first paragraph under each letter is the rule text itself, the
        # rest are the Department's examples: quote the rule text here
        for letter in "ghijkl":
            paras = (auth.get("paragraphs") or {}).get(letter) or []
            if paras:
                P(doc, paras[0], style="Intense Quote", verbatim=True)
        P(doc, f"Source: Federal Register document {RULE['fr_document']}, fetched "
               f"{auth.get('fetched_at', 'on the date in the authority manifest')}, "
               f"content hash {auth.get('sha256', '')[:16]}. Nothing in the quoted text is Tark's.")


def _scope_section(doc) -> None:
    H(doc, "Scope", 2)
    # the one gate for "is the verbatim text in the record": the file with its
    # hashed manifest row, never a bare glob of the folder
    verbatim = authority()["status"] == "fetched"
    P(doc, "This record covers the evaluation of one product as a candidate designated "
           f"investment alternative for one plan, on the record as of {record_as_of()}. "
           "It is a selection record. It is not a monitoring record, and nothing in it "
           "states a monitoring cadence or a later review.")
    P(doc, "Every figure in it is a cited cell, a figure read from a cited cell, or a "
           "computation from cited series. Every scenario figure is labeled ILLUSTRATIVE. "
           "Cells marked extracted-unverified were extracted by an agent and not yet "
           "verified by a person. "
           + ("Verbatim regulatory text is in this record and quoted where cited."
              if verbatim else
              "Verbatim regulatory text is not in this record: the regulation is cited by "
              "Federal Register citation and RIN, not paraphrased."))


def _case_law_section(doc, product: dict) -> None:
    H(doc, "Case law", 2)
    c = product["cells"]["5.7"]
    st = str(c.get("status", "pending"))
    kind = status_kind(st)
    v = (c.get("value") or "").strip()
    if kind in EVIDENCED and v:
        P(doc, f"Cell 5.7 ({KIND_LABEL[kind]}): {display_copy(v)}")
        src = display_copy(c.get("source") or c.get("source_doc") or "")
        if src:
            P(doc, f"Source: {src}" + (f". Extracted: {c['extracted_by']}" if c.get("extracted_by") else ""))
    else:
        reason = st.split(":", 1)[1].strip() if ":" in st else st
        P(doc, f"Cell 5.7 ({cell_title('5.7')}) is {st.split(' ')[0]} for this product"
               + (f": {v}" if v else f": {reason}")
               + " This record makes no case-law statement beyond that cell.")


# ------------------------------------------------------------ benchmark selection
def _comparison_paragraphs(doc, comp: dict, comparator: str, fdoc: dict | None = None) -> None:
    """The comparison named for its comparator (rule 12): KS-PME and Direct
    Alpha against a public market series, a relative wealth ratio against
    an appraisal-based comparator, each with its window and fund source."""
    lc = (f" {comp['low_confidence'][0].upper()}{comp['low_confidence'][1:]}."
          if comp.get("low_confidence") else "")
    filed = ((fdoc or {}).get("facts") or {}).get("filed_since_inception_return_pct") or {}
    if comp.get("kind") == "series" and filed.get("value") is not None:
        lc += " " + reconciliation_sentence(filed["value"], filed.get("note", ""), comp)
    if comp.get("kind") == "series":
        P(doc, f"Window {comp['window']}"
               f"{(' (' + comp['window_note'] + ')') if comp.get('window_note') else ''}"
               f": fund {comp['fund_ann_pct']}%/yr ({comp['fund_return_source']}) "
               f"vs {comparator} {comp['index_ann_pct']}%/yr, "
               f"KS-PME {comp['ks_pme']}, Direct Alpha {comp['direct_alpha_pct']}%/yr. Disclosure: PME and "
               "alpha computed on appraisal-lagged NAVs are window-sensitive and can be smoothing-flattered. "
               "Conclusions should be read with the methodology's window-sensitivity analysis." + lc)
        P(doc, "Two-point comparison: one contribution at the window start and one valuation at the end. "
               "Direct Alpha is the annualized form of the same two flows."
               + (f" ILLUSTRATIVE monthly-schedule KS-PME {comp['ks_pme_monthly_schedule']} "
                  f"({comp['schedule_contributions']} equal contributions at the window start and each "
                  "month-end inside it, valued at the window end). The two-point figure is primary."
                  if comp.get("ks_pme_monthly_schedule") is not None else ""))
    else:
        note = comp.get("window_note") or f"{comp.get('window_years')} periods, n={comp.get('n')}"
        P(doc, f"Window {comp['window']} ({note}): fund {comp['fund_ann_pct']}%/yr "
               f"({comp['fund_return_source']}) vs {comparator} {comp['index_ann_pct']}%/yr, "
               f"relative wealth ratio {comp['relative_wealth_ratio']}, annualized excess return "
               f"{comp['excess_return_pct']}%/yr. {comp['not_pme_note']} Disclosure: ratios on "
               "appraisal-lagged NAVs are window-sensitive and can be smoothing-flattered." + lc)
        P(doc, "Alignment: " + comp["alignment_note"].rstrip(".") + ".")
        P(doc, "Two-point comparison: one contribution at the window start and one valuation at the end, "
               "on identical period boundaries. The ratio is fund growth divided by the comparator's growth "
               "over the same periods.")


def _ledger_table(doc, sel: dict) -> None:
    """Every candidate on one ledger: the selected slot, the reference, each
    declared comparator, the peer slot, then each rejection."""
    sk = sel["slot_k"]
    P(doc, f"{RUBRIC_LABEL}, threshold {x_of_n(MIN_PRIMARY_SCORE, RUBRIC_MAX)}, strategy gate "
           f"{x_of_n(STRATEGY_GATE_MIN, CRITERION_MAX['strategy_match'])}, affiliated providers ineligible. "
           + (f"Max attainable by an eligible candidate on held data {x_of_n(sk['max_attainable'], RUBRIC_MAX)}."
              if sk.get("max_attainable") is not None else "No candidate is eligible on held data."), keep=True)
    t = _table(doc, ["Slot", "Candidate", "Lane", "Score", "Outcome"], [1.1, 1.9, 1.1, 0.6, 1.8])
    s2 = sk.get("selected")
    if s2:
        r = t.add_row().cells
        comp = s2.get("comparison") or {}
        _set(r[0], sk["label"]); _set(r[1], s2["candidate"]); _set(r[2], lane_label(s2.get("lane", "")))
        _set(r[3], x_of_n(s2["score"], s2["max"]))
        _set(r[4], (f"{_stat_line(comp)}, {comp['window']}" if comp
                    else f"selected. {BY_DESCRIPTOR_SENTENCE}" if s2.get("by_descriptor")
                    else "selected, no comparison computed: " + (s2.get("comparison_note") or "not computable")))
    elif sk.get("escalation"):
        r = t.add_row().cells
        _set(r[0], sk["label"]); _set(r[1], "none"); _set(r[2], ""); _set(r[3], "")
        _set(r[4], "escalated: " + sk["escalation"])
    ref = sel.get("reference_comparison")
    if ref:
        r = t.add_row().cells
        _set(r[0], "Reference comparison, not the meaningful benchmark"); _set(r[1], ref["candidate"])
        _set(r[2], lane_label(ref.get("lane", "B"))); _set(r[3], x_of_n(ref["score"], ref["max"]) if ref.get("score") is not None else "")
        _set(r[4], f"{_stat_line(ref['comparison'])}, {ref['comparison']['window']}")
    for d in sel.get("declared") or []:
        r = t.add_row().cells
        _set(r[0], d["type_label"][0].upper() + d["type_label"][1:]); _set(r[1], d["name"]); _set(r[2], lane_label("A"))
        _set(r[3], ""); _set(r[4], d["status"] + (f", {_stat_line(d['comparison'])}" if d.get("comparison") else ""))
    g = sel.get("slot_g")
    if g:
        comp = g["composite"]
        r = t.add_row().cells
        _set(r[0], g["label"]); _set(r[1], g["cohort_label"]); _set(r[2], "peer cohort"); _set(r[3], "not scored")
        _set(r[4], _stat_line(comp) + f", {comp['window']}" if comp.get("status") == "computed"
             else "composite refused: " + comp.get("reason", ""))
    for rj in sel.get("rejected") or []:
        r = t.add_row().cells
        _set(r[0], "rejected"); _set(r[1], rj["candidate"]); _set(r[2], lane_label(rj.get("lane", "")))
        _set(r[3], x_of_n(rj["score"], rj["max"]) if rj.get("score") is not None else "")
        _set(r[4], rj["rejection"])
    _finish_table(t)


def _rubric_table(doc) -> None:
    """The rubric defined once: each criterion, its points and its definition,
    then the three metrics defined once."""
    P(doc, f"The rubric's criteria, {RUBRIC_MAX} points in all:", keep=True)
    t = _table(doc, ["Criterion", "Points", "Definition"], [1.8, 0.7, 4.0])
    for c in CRITERIA:
        r = t.add_row().cells
        _set(r[0], CRITERION_LABEL[c]); _set(r[1], str(CRITERION_MAX[c])); _set(r[2], CRITERION_DEFINITION[c])
    _finish_table(t)
    P(doc, "Metrics, each defined once: " + " ".join(f"{k}: {v}" for k, v in METRIC_DEFINITION.items()))


def _benchmark_section(doc, sel: dict, fdoc: dict | None = None) -> None:
    """The ledger and the rubric first, then Slot K, the reference comparison,
    the Lane A record, Slot G with its table, and the rejection log with
    every reason (decision 7.1)."""
    sk = sel["slot_k"]
    P(doc, f"Return basis for every comparison in this section: {sel['basis']['label'].rstrip('.')}.")
    H(doc, "Ledger: every candidate and its outcome", 2)
    _ledger_table(doc, sel)
    _rubric_table(doc)
    if sk.get("escalation"):
        H(doc, "ESCALATION: no meaningful benchmark constructible", 2)
        P(doc, sk["escalation"])
        # no legal conclusion (R2-P0-9, audit round 2 item 29): the record
        # states what it holds and does not decide
        P(doc, "No meaningful benchmark could be constructed from the data held. "
               "The record cannot support the paragraph (k) comparison until one "
               "is identified. This record does not decide.")
    else:
        s = sk["selected"]
        H(doc, f"{sk['label']}: {s['candidate']} (score {x_of_n(s['score'], s['max'])})", 2)
        comp = s.get("comparison")
        if comp:
            _comparison_paragraphs(doc, comp, "the benchmark", fdoc)
        elif s.get("by_descriptor"):
            P(doc, f"{BY_DESCRIPTOR_SENTENCE} The candidate is selected on its own descriptors. "
                   "No number is substituted.")
        else:
            P(doc, "Comparison not computed: "
                   f"{(s.get('comparison_note') or 'not computable on held data').rstrip('.')}. "
                   "The candidate is selected on its own descriptors. No number is substituted.")
        if sk.get("ties"):
            P(doc, f"{TIE_SENTENCE} Tied with " + ", ".join(
                next((r["candidate"] for r in sel["rejected"] if r["id"] == t), t) for t in sk["ties"]) + ".")
        if sel.get("record_hash"):
            P(doc, f"Selection recorded {sel['recorded_at'][:10]}, record {sel['record_hash'][:8]}. "
                   f"Rubric {sel.get('rubric_version')}. The full record hash is "
                   f"{sel['record_hash']}.")
        for r in s["reasons"]:
            P(doc, r, style="List Bullet")
    ref = sel.get("reference_comparison")
    if ref:
        H(doc, f"Reference comparison, not the meaningful benchmark: {ref['candidate']}", 2)
        P(doc, ref["note"][0].upper() + ref["note"][1:].rstrip(".") + ".")
        _comparison_paragraphs(doc, ref["comparison"], "the public series")
    # the fund's own declared benchmark or SEC-required comparator (cell
    # 5.1), typed, with its comparison whenever the index has a held series
    # (R2-P1-5, R2-P1-15)
    H(doc, "Declared benchmark and SEC-required comparators (cell 5.1)", 2)
    decl = sel.get("declared") or []
    if not decl:
        P(doc, "The fund declares no benchmark: "
               + (sel.get("declared_none_reason") or "cell 5.1").rstrip(".") + ".")
    for d in decl:
        P(doc, f"{d['type_label'][0].upper()}{d['type_label'][1:]}: {d['name']}, {d['status']}. "
               "The declaration itself earns no points.")
        if d.get("comparison"):
            _comparison_paragraphs(doc, d["comparison"], d["name"])
        elif d.get("comparison_note"):
            P(doc, f"No comparison: {d['comparison_note'].rstrip('.')}.")
    if not any(d["type"] == "declared" for d in decl) and decl and sel.get("declared_none_reason"):
        P(doc, "Declared benchmark: none. " + sel["declared_none_reason"].rstrip(".") + ".")
    # Slot G
    g = sel.get("slot_g")
    if g:
        comp = g["composite"]
        H(doc, f"{g['label']}: {g['cohort_label']}", 2)
        P(doc, "Peers: " + ", ".join(g["member_names"]) + ". This is the history of similar "
               "investments, not the benchmark, and it is never a public market equivalent.")
        if comp["status"] == "computed":
            _comparison_paragraphs(doc, comp, "the peer composite")
        else:
            P(doc, "Composite refused: " + comp["reason"].rstrip(".") + ". The side-by-side table "
                   "is shown without a ratio.")
        cols = [FUND_SHORT_OF(sel["product"])] + g["member_names"]
        n_cols = 2 + len(cols)
        first = [0.9, 0.4]
        rest = round((TEXT_WIDTH_IN - sum(first)) / len(cols), 4)
        widths = first + [rest] * len(cols)
        widths[-1] = round(TEXT_WIDTH_IN - sum(widths[:-1]), 4)
        t = _table(doc, ["Period", "n"] + cols, widths)
        assert len(t.columns) == n_cols
        for r in g["table"]:
            c = t.add_row().cells
            _set(c[0], r["label"]); _set(c[1], str(r["n"]))
            for i, name in enumerate(cols):
                v = r["returns"].get(name)
                _set(c[2 + i], "n/a" if v is None else f"{v:g}%")
        _finish_table(t)
        P(doc, g["survivorship_note"])
        P(doc, g["heterogeneity_note"])
    H(doc, "Rejection log (candidates considered and not selected)", 2)
    rt = _table(doc, ["Candidate", "Score", "Reason and criteria"], [2.0, 0.7, 3.8])
    for r in sel["rejected"]:
        c = rt.add_row().cells
        _set(c[0], r["candidate"])
        _set(c[1], x_of_n(r["score"], r["max"]) if r.get("score") is not None else "not scored")
        # the criteria ride with the reason so a reader sees whether a
        # candidate lost on fit or on data absence (audit round 2 item 14)
        _set(c[2], r["rejection"].rstrip(".") + ". Criteria: " + ", ".join(r["reasons"]) + ".")
    _finish_table(rt)


# ------------------------------------------------------------ fees on record
def _fee_table(doc, product: dict, fbc: dict) -> None:
    H(doc, "Fees and terms on record", 2)
    P(doc, "Each line is the fact read from the cell, or the cell's status word when none is "
           "on record. Full text and provenance are in the evidence ledger.", keep=True)
    t = _table(doc, ["Cell", "Headline", "Status"], [2.0, 2.5, 2.0])
    for cid in FEE_CELLS:
        c = product["cells"][cid]
        r = t.add_row().cells
        _set(r[0], f"{cid} {cell_title(cid)}")
        # never a status word where a headline belongs (audit round 2 item 34)
        _set(r[1], typed_headline(cid, fbc.get(cid, {})) or (
            "not applicable, the record states why" if status_kind(c.get("status", "")) == "n/a"
            else "no fact on record for this cell"))
        _set(r[2], str(c.get("status", "")))
    _finish_table(t)


# ------------------------------------------------------------ provenance grouped by filing
def _citation_lines(refs: list[dict]) -> list[str]:
    """One line per resolved filing, or the reason it is not on record."""
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


def _provenance_section(doc, key: str, product: dict, plan: dict) -> None:
    H(doc, "Provenance", 1)
    cov = coverage_summary(key)
    P(doc, "Cell status for this product, from the record's one coverage formula: "
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
    P(doc, f"Of the {n} resolved cells (structured, extracted-unverified, verified and computed), "
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

    H(doc, "Sources cited, by filing", 2)
    cpath = DATA / "citations" / f"{key}.json"
    cit = json.loads(cpath.read_text())["cells"] if cpath.exists() else {}
    P(doc, "Every filing an evidenced cell cites, resolved against the filing manifest by "
           "accession, with the cells that cite it. A cell whose reference does not resolve "
           "is listed after the table with the reason. The source as written in the evidence "
           "ledger stays on the ledger row.", keep=True)
    evid = [(cid, c) for cid, c in product["cells"].items()
            if status_kind(c.get("status", "")) in EVIDENCED and (c.get("value") or "").strip()]
    by_filing: dict[tuple[str, str, str, str], list[str]] = {}
    unresolved: list[str] = []
    for cid, c in evid:
        refs = cit.get(cid, [])
        if not refs:
            unresolved.append(f"{cid}: accession not on record: no filing reference in the source field")
            continue
        for r in refs:
            if r["match"] in RESOLVED_ONE:
                k = (r["form"], r.get("filing_date", ""), r["accession"], r["url"])
                by_filing.setdefault(k, []).append(cid + (" (matched by form only)" if r["match"] == "form_only" else ""))
            elif r["match"] in ("range", "set"):
                for f in r["filings"]:
                    k = (r["form"], f["filing_date"], f["accession"], f["url"])
                    by_filing.setdefault(k, []).append(f"{cid} ({r['reason']})")
            else:
                unresolved.append(f"{cid}: {r.get('form', '')} accession not on record: {r['reason']}".replace(":  ", ": "))
    t = _table(doc, ["Filing", "Accession and EDGAR URL", "Cells citing it"], [1.3, 3.4, 1.8])
    for (form, date, acc, url), cids in sorted(by_filing.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        r = t.add_row().cells
        _set(r[0], f"{form} {date}".strip())
        _fill(r[1], [f"accession {acc}", url], verbatim=True)
        _set(r[2], ", ".join(dict.fromkeys(cids)))
    _finish_table(t)
    if unresolved:
        P(doc, "Cells whose reference does not resolve to a manifest row:", keep=True)
        for u in unresolved:
            P(doc, u, style="List Bullet")
    P(doc, f"Plan record: DOL Form 5500 and Schedule H for plan year {plan.get('plan_year', 'on file')}, "
           "shown under the plan's anonymized label.")
    with open(DATA / "manifest.csv", newline="") as fh:
        held = sum(1 for r in csv.DictReader(fh) if r["product"] == key)
    P(doc, f"Data sources: SEC EDGAR filings ({held} held for this product in the filing manifest, "
           "every row with its accession) and DOL EBSA Form 5500 data for the plan, shown under "
           "its anonymized label.")


# ------------------------------------------------------------ the attachment
def build_attachment(out_dir: Path | None = None) -> Path | None:
    """Attachment A: the verbatim text of paragraphs (g) to (l), one file
    written once and cited by its content hash. Nothing in it is Tark's and
    nothing in it goes through the copy layer."""
    auth = authority()
    name = attachment_name(auth)
    if not name:
        return None
    doc = Document()
    doc.styles["Normal"].font.size = Pt(10.5)
    _page_setup(doc, "Attachment A", f"verbatim text of proposed 29 CFR 2550.404a-6 paragraphs (g) to (l)")
    _core_properties(doc, "Attachment A: verbatim regulatory text", RULE_CITATION, "regulation, verbatim")
    doc.add_heading("Attachment A: verbatim text of proposed 29 CFR 2550.404a-6, paragraphs (g) to (l)", level=0)
    P(doc, f"{RULE['issuer']}, proposed rule {RULE_CITATION}. Federal Register document "
           f"{RULE['fr_document']}, {RULE['fr_url']}. Fetched {auth.get('fetched_at', 'on the date in the authority manifest')}. "
           f"Content hash (SHA-256 of the fetched text) {auth.get('sha256', '')}. Runs of whitespace inside a "
           "paragraph are collapsed to one space. Every paragraph below is the Federal Register text unchanged. "
           "Nothing in it is Tark's.")
    for letter, paras in auth["paragraphs"].items():
        H(doc, f"Paragraph ({letter})", 1)
        for t in paras:
            P(doc, t, verbatim=True)
    out = out_dir or SITE_MEMOS
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    _save(doc, path)
    return path


# ------------------------------------------------------------ the record
def build_record(key: str, plan_key: str, out_dir: Path | None = None) -> Path:
    products = load_products()
    p = products[key]
    anchor = load_plan(plan_key)
    sel_path = DATA / "benchmarks" / f"{key}_selection.json"
    sel = json.loads(sel_path.read_text()) if sel_path.exists() else None
    facts_path = DATA / "facts" / f"{key}.json"
    fdoc = json.loads(facts_path.read_text()) if facts_path.exists() else {}
    fbc = facts_by_cell(fdoc.get("facts", {}))
    mp = DATA / "liquidity" / f"{plan_key}__{key}_match.json"
    m = json.loads(mp.read_text()) if mp.exists() else None
    reg = json.loads((DATA / "registry.json").read_text())["products"].get(key, {})
    auth = authority()
    stated = (load_advisor(plan_key, key) or {}).get("cells") or {}

    doc = Document()
    doc.styles["Normal"].font.size = Pt(10.5)
    _page_setup(doc, DOCUMENT_TITLE, f"{anchor['display_label']}. {p['fund_name']}")
    _core_properties(doc, f"{DOCUMENT_TITLE}: {p['fund_name']} for {anchor['display_label']}",
                     f"{RULE_CITATION}, paragraphs (g) to (l)", f"{key}, {plan_key}, {record_as_of()}")

    doc.add_heading(DOCUMENT_TITLE, level=0)
    sub = doc.add_paragraph()
    sub.add_run(display_copy(f"Plan: {anchor['display_label']}")).bold = True
    sub.add_run(display_copy(f". Product: {p['fund_name']} ({p['wrapper']}, CIK {p['cik']}). "))
    sub.add_run(display_copy(f"Date: {record_as_of()}. Status: DRAFT until the committee signs page one. "
                             "Cells marked extracted-unverified pend independent verification."))

    _summary_section(doc, key, p, anchor, sel, m, fdoc, stated)
    _toc(doc)
    _regulatory_basis(doc, auth)

    _plan_lines = plan_findings(anchor, m)
    H(doc, "Six-factor findings", 1)
    P(doc, "Per factor: one sentence generated from the facts on record (each clause names its cell), "
           "then the facts on record the computations read, then the complete first sentence of "
           "every evidenced cell with its status, then the cells marked not applicable with the "
           "reason. The full sourced text, quote and document of every cell is in the evidence "
           "ledger and on the Evaluation view.", keep=True)
    table = _table(doc, ["Factor", "Findings (cell, status, first sentence)"], [1.2, 5.3])
    for n, label in FACTORS.items():
        row = table.add_row().cells
        _set(row[0], f"{n}. {label} ({FACTOR_PARAS[n]})")
        _fill(row[1], [factor_lead(n, fdoc, reg, sel, m)] + _findings(p, label, fbc, _plan_lines))
    _finish_table(table)
    _fee_table(doc, p, fbc)

    H(doc, "Benchmark selection and justification", 1)
    if sel is None:
        P(doc, "Selection pending for this product: extraction depth required before selection.")
    else:
        _benchmark_section(doc, sel, fdoc)

    _liquidity_section(doc, m, fdoc, anchor)

    if fdoc:
        cid = fdoc.get("cohort_id")
        cpath = DATA / "cohorts" / f"{cid}.json"
        if cid and cpath.exists():
            co = json.loads(cpath.read_text())
            H(doc, "Peer cohort placement", 1)
            P(doc, f"Evidence depth tier: {fdoc.get('depth', 'cohort').upper()}. "
                   f"Cohort: {co['label']} (n={co['n']}). Membership rationale: "
                   f"{display_copy(fdoc.get('membership_rationale', ''))}")
            v29 = p["cells"]["2.9"].get("value")
            if v29:
                P(doc, v29)
            comp = co.get("composite", {})
            if comp.get("refused"):
                P(doc, "Cohort composite: REFUSED, " + comp.get("reason", ""))
            elif comp.get("composite_refused_reason"):
                P(doc, "Cohort composite return: not formed, " + comp["composite_refused_reason"].rstrip(".") + ".")
            for cv in co.get("caveats", []):
                P(doc, f"Caveat: {cv}", style="List Bullet")
            P(doc, "Cohort exclusion log: every candidate considered and not admitted is recorded with "
                   "its reason in the roster decisions record (shown on the Cohorts view). Membership is "
                   "an argued judgment, not a tag.")

    _advisor_section(doc, key, plan_key, anchor)
    H(doc, "Scope and case law", 1)
    _scope_section(doc)
    _case_law_section(doc, p)
    _provenance_section(doc, key, p, anchor)

    H(doc, "Attachments", 1)
    att = attachment_name(auth)
    if att:
        P(doc, "Attachment A: the verbatim text of proposed 29 CFR 2550.404a-6 paragraphs (g) to (l), "
               "examples included, one document shared by every record and named by the first twelve "
               f"characters of its content hash, {auth.get('sha256', '')}.")
    else:
        P(doc, "No attachment: the verbatim regulatory text is not yet in the record.")

    for para in doc.paragraphs:
        if para.style.name.startswith("Heading") or para.style.name == "Title":
            para.paragraph_format.keep_with_next = True
    _keep_tables_with_lead(doc)

    out = out_dir or SITE_MEMOS
    out.mkdir(parents=True, exist_ok=True)
    path = out / record_name(plan_key, key)
    _save(doc, path)
    return path


build_memo = build_record    # the older name, still imported by the gates


STALE_PATTERNS = ("*_decision_memo.docx", "*_committee_packet.docx", "*_selection_record.docx",
                  "attachment_a_*.docx")


def write_all(out_dir: Path | None = None) -> list[Path]:
    """Every plan x product record, stale documents in out_dir removed first.
    The attachment is written once beside them (attachment_path)."""
    out = out_dir or SITE_MEMOS
    out.mkdir(parents=True, exist_ok=True)
    for pat in STALE_PATTERNS:
        for stale in out.glob(pat):
            stale.unlink()
    build_attachment(out)
    return [build_record(key, plan_key, out)
            for plan_key in plan_keys() for key in load_products()]


def attachment_path(out_dir: Path | None = None) -> Path | None:
    name = attachment_name()
    if not name:
        return None
    path = (out_dir or SITE_MEMOS) / name
    return path if path.exists() else None


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    paths = write_all(Path(a.out) if a.out else None)
    print(f"wrote {len(paths)} records to {paths[0].parent}")

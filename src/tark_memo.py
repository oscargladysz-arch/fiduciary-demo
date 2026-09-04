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

from tark_data import (CELLS, DATA, FACTORS, cells_by_factor, coverage_summary,
                       load_plan, load_products, plan_keys, record_as_of, status_kind)
from tark_display import _money as money, facts_by_cell, typed_headline

SITE_MEMOS = Path(__file__).resolve().parents[1] / "site" / "memos"

RULE = ("DOL proposed rule, Fiduciary Duties in Selecting Designated "
        "Investment Alternatives, 91 FR 16088 (Mar. 31, 2026), RIN 1210-AC38")

RULE_PARAS = [
    ("This memo documents an evaluation of the product below as a potential "
     "designated investment alternative (DIA) for the plan, structured on the "
     "six factors of the proposed rule: performance, fees and expenses, "
     "liquidity, valuation, performance benchmarks, and complexity. The "
     "proposed safe harbor attaches to a documented, objective, thorough and "
     "analytical process. This memo and its underlying evidence files "
     "constitute that record."),
    ("On benchmarks, the proposal requires comparison against a meaningful "
     "benchmark and acknowledges that no single benchmark is meaningful for "
     "every DIA. Where none exists, the history of a similar type of "
     "investment may serve. The benchmark section below therefore documents "
     "the selection AND the rejections: every candidate considered, its "
     "score, and the true reason it was or was not chosen. Case law is "
     "addressed in its own section below, from cell 5.7 only."),
]

# cells the adopting committee completes for its own plan (P2-6 makes them
# advisor-stated with signer and date). Listed in the Recommendation so the
# memo never implies the record decided them.
COMMITTEE_CELLS = ("6.6", "6.8", "3.7", "2.8", "3.5", "4.9")


KIND_LABEL = {"extracted": "extracted-unverified", "verified": "verified",
              "computed": "computed", "partial": "partial", "structured": "structured"}
EVIDENCED = tuple(KIND_LABEL)


def first_sentence(value: str) -> str:
    """The complete first sentence of a cell value, never cut mid-word."""
    return re.split(r"(?<=[.!?])\s+", value.strip(), maxsplit=1)[0]


def _findings(product: dict, factor_label: str, fbc: dict) -> list[str]:
    """One paragraph per line: the typed facts for the factor's cells, then
    the complete first sentence of every evidenced cell, then the cells
    marked not applicable with their reasons. Nothing is truncated."""
    typed, lines, na = [], [], []
    for cid, cell in cells_by_factor(product)[factor_label]:
        st = str(cell.get("status", "pending"))
        kind = status_kind(st)
        v = (cell.get("value") or "").strip()
        if kind in EVIDENCED and v:
            th = typed_headline(cid, fbc.get(cid, {}))
            if th:
                typed.append(f"{cid} {th}")
            lines.append(f"{cid} {cell['element']} ({KIND_LABEL[kind]}): {first_sentence(v)}")
        elif kind == "n/a":
            reason = st.split(":", 1)[1].strip() if ":" in st else st[3:].strip(" -")
            na.append(f"{cid} {reason}")
    out = []
    if typed:
        out.append("Typed facts: " + ". ".join(typed) + ".")
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


def _liquidity_section(doc: Document, m: dict | None, fdoc: dict, plan: dict) -> None:
    doc.add_heading("Product-to-plan liquidity match", level=1)
    if m is None:
        doc.add_paragraph("No match file for this plan and product in data/liquidity/.")
        return
    doc.add_paragraph(f"Plan: {plan['display_label']}. {m['layers']}")
    doc.add_heading("Structural verdict (typed facts, plan-independent)", level=2)
    doc.add_paragraph(m["verdict"].upper())
    for r in m["structural_reasons"]:
        doc.add_paragraph(r, style="List Bullet")
    wf = m["wrapper_facts"]
    t = doc.add_table(rows=1, cols=3)
    t.style = "Table Grid"
    h = t.rows[0].cells
    h[0].text, h[1].text, h[2].text = "Wrapper fact", "Value", "Cell"
    rows = [("Wrapper", "wrapper_type", wf.get("kind")),
            ("Dealing cadence per year", "repurchase_cadence_per_year", wf.get("cadence_per_year")),
            ("Repurchase cap", "repurchase_cap_pct",
             None if wf.get("cap_pct") is None else f"{wf['cap_pct']:g}% of {wf.get('cap_base') or 'a base not typed'}"),
            ("Gating history", "gate_history",
             None if wf.get("gate_history") is None else ("yes, prorated under stress" if wf["gate_history"] else "none identified in the filings on record")),
            ("Repurchase program status", "repurchase_program_status", wf.get("program_status")),
            ("Early repurchase fee", "early_repurchase", wf.get("early_fee"))]
    for label, field, shown in rows:
        _, src, null_reason = _fact_value(fdoc, field)
        c = t.add_row().cells
        c[0].text = label
        if shown is None:
            reason = wf.get("null_reasons", {}).get(field) or null_reason or "not typed"
            c[1].text = f"not typed: {reason}"
        else:
            c[1].text = str(shown)
        c[2].text = src or ""
    for row in t.rows:
        row.cells[0].width, row.cells[1].width, row.cells[2].width = Inches(1.7), Inches(4.0), Inches(0.8)

    doc.add_heading("Scenario (ILLUSTRATIVE, this plan)", level=2)
    sc, pi, ss = m["scenario"], m["plan_inputs"], m["stressed_scenario"]
    cap = sc.get("annual_wrapper_capacity_pct")
    cap_text = "not applicable (exchange-traded)" if cap is None else f"{cap:g}%"
    doc.add_paragraph(
        f"Plan inputs (Form 5500): net assets {money(pi['net_assets'])}, liquidity tail "
        f"{pi['tail_share_pct']}% of accounts ({int(pi['separated_with_balances']):,} "
        "separated participants with balances).")
    doc.add_paragraph(
        "Parameters (adjustable on the site, not facts): allocation "
        f"{sc['allocation_pct_of_plan']:g}% of plan = {money(sc['plan_allocation_usd'])}, "
        f"tail turnover {sc['tail_annual_turnover_pct']:g}%/yr, active turnover "
        f"{sc['active_annual_turnover_pct']:g}%/yr. Base demand "
        f"{money(sc['annual_demand_usd'])}/yr = {sc['demand_pct_of_position']}% of the "
        f"position vs annual wrapper capacity {cap_text}.")
    doc.add_paragraph(
        f"Stressed ({ss['assumptions']}): demand {money(ss['annual_demand_usd'])}/yr = "
        f"{ss['demand_pct_of_position']}% of the position. {ss['outcome']}.")
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
        if sel.get("escalation"):
            out.append("Benchmark: " + sel["escalation"] + " (benchmark selection)")
        elif sel.get("primary") and not sel.get("secondary"):
            out.append("Benchmark: no eligible secondary benchmark "
                       f"({sel.get('secondary_note') or 'none'}) (benchmark selection)")
        comp = (sel.get("primary") or {}).get("comparison") or {}
        if comp.get("low_confidence"):
            out.append("Benchmark: " + comp["low_confidence"] + " (benchmark comparison)")
    if m:
        wf = m["wrapper_facts"]
        if wf.get("program_status") == "suspended":
            out.append("Liquidity: repurchase program suspended (cells 3.1, 3.3)")
        if wf.get("gate_history"):
            out.append("Liquidity: gating precedent, repurchases prorated under stress (cell 3.3)")
        if m.get("missing_facts"):
            out.append("Liquidity: structural verdict partial, facts missing: "
                       + ", ".join(m["missing_facts"]) + " (cells 3.1, 3.3)")
        if m.get("scenario_verdict") in ("misaligned", "conditional-weak"):
            out.append(f"Liquidity: ILLUSTRATIVE scenario verdict {m['scenario_verdict']} "
                       "under this plan (base or stressed demand above wrapper capacity)")
    tax, src, _ = _fact_value(fdoc, "tax_form")
    if tax == "K-1":
        out.append(f"Tax reporting: Schedule K-1 (cell {src})")
    return out


def _recommendation_section(doc: Document, sel: dict | None, m: dict | None,
                            fdoc: dict, plan: dict) -> None:
    doc.add_heading("Recommendation", level=1)
    if m:
        doc.add_paragraph(
            f"Structural liquidity verdict: {m['verdict'].upper()} (typed facts, plan-independent). "
            f"Scenario verdict under {plan['display_label']} (ILLUSTRATIVE): "
            f"{(m.get('scenario_verdict') or 'not computable').upper()}.")
    if sel is None:
        doc.add_paragraph("Benchmark: no selection artifact for this product.")
    elif sel.get("escalation"):
        doc.add_paragraph("Benchmark: escalated. " + sel["escalation"])
    else:
        pr = sel["primary"]
        doc.add_paragraph(f"Benchmark: {pr['candidate']} selected as primary at {pr['score']}/{pr['max']}"
                          + (f", secondary {sel['secondary']['candidate']} at "
                             f"{sel['secondary']['score']}/{sel['secondary']['max']}."
                             if sel.get("secondary") else ". No eligible secondary."))
    flags = _flags(sel, m, fdoc)
    doc.add_paragraph("Flags raised by the record (each restates a typed value or verdict "
                      "already in the artifacts, with its source):")
    if flags:
        for f in flags:
            doc.add_paragraph(f, style="List Bullet")
    else:
        doc.add_paragraph("none", style="List Bullet")
    doc.add_paragraph(
        "This memo does not decide. The fiduciary makes the decision on this record. "
        "The committee-completed cells stay the committee's to complete for its own plan "
        "before it does: " + ", ".join(f"{c} {cell_title(c)}" for c in COMMITTEE_CELLS) + ".")


def _scope_section(doc: Document) -> None:
    doc.add_heading("Scope", level=1)
    authority = sorted((DATA / "authority").glob("*.md")) if (DATA / "authority").exists() else []
    doc.add_paragraph(
        "This memo records the evaluation of one product as a candidate designated "
        f"investment alternative for one plan, on the record as of {record_as_of()}. "
        "It is a selection record. It is not a monitoring record, and nothing in it "
        "states a monitoring cadence or a later review.")
    doc.add_paragraph(
        "Every figure in it is a cited cell, a typed projection of a cited cell, or a "
        "computation from cited series. Every scenario figure is labeled ILLUSTRATIVE. "
        "Cells marked extracted-unverified were extracted by an agent and not yet "
        "verified by a person. "
        + ("Verbatim regulatory text is in data/authority/ and quoted where cited."
           if authority else
           "Verbatim regulatory text is not in this build: the regulation is cited by "
           "Federal Register citation and RIN, not paraphrased."))


def _case_law_section(doc: Document, product: dict) -> None:
    doc.add_heading("Case law", level=1)
    c = product["cells"]["5.7"]
    st = str(c.get("status", "pending"))
    kind = status_kind(st)
    v = (c.get("value") or "").strip()
    if kind in EVIDENCED and v:
        doc.add_paragraph(f"Cell 5.7 ({KIND_LABEL[kind]}): {v}")
        src = c.get("source") or c.get("source_doc") or ""
        if src:
            doc.add_paragraph(f"Source: {src}" + (f". Extracted: {c['extracted_by']}" if c.get("extracted_by") else ""))
    else:
        reason = st.split(":", 1)[1].strip() if ":" in st else st
        doc.add_paragraph(f"Cell 5.7 ({cell_title('5.7')}) is {st.split(' ')[0]} for this product"
                          + (f": {v}" if v else f": {reason}")
                          + " This memo makes no case-law statement beyond that cell.")


KIND_ORDER = (("structured", "structured"), ("extracted", "extracted-unverified"),
              ("verified", "verified"), ("computed", "computed"), ("partial", "partial"),
              ("fetched", "fetched"), ("na", "n/a"), ("pending", "pending"))
RESOLVED_ONE = ("exact", "form_only", "accession_in_text")


def _citation_lines(refs: list[dict]) -> list[str]:
    """One paragraph per resolved filing, or the reason it is not on record."""
    lines = []
    for r in refs:
        if r["match"] in RESOLVED_ONE:
            tag = {"form_only": " (matched by form only: the single such filing held)",
                   "accession_in_text": " (accession written in the citation, EDGAR folder URL)"
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
    ev = [(cid, c) for cid, c in product["cells"].items()
          if status_kind(c.get("status", "")) in EVIDENCED and (c.get("value") or "").strip()]
    n = len(ev)
    have = {f: sum(1 for _, c in ev if (c.get(f) or "").strip())
            for f in ("source", "section", "quote", "extracted_by")}
    doc.add_paragraph(
        f"Of the {n} evidenced cells, {have['source']} carry a source document, "
        f"{have['section']} a section, {have['quote']} a verbatim quote (computed cells "
        f"carry their computation and inputs instead of a quote) and {have['extracted_by']} "
        "an extractor. "
        + ("Verified cells have been independently re-checked by a person."
           if cov["verified"] > 0 else
           "No cell is verified: no cell has been independently re-checked by a person, "
           "and verified_by is empty on every row.")
        + " Cells marked extracted-unverified were extracted by an agent from the cited "
        "document. Cells marked structured come directly from machine-readable regulatory "
        "datasets with the dataset cited.")

    doc.add_heading("Sources cited", level=2)
    cpath = DATA / "citations" / f"{key}.json"
    cit = json.loads(cpath.read_text())["cells"] if cpath.exists() else {}
    doc.add_paragraph(
        "Each evidenced cell's source document as written in the evidence ledger, with "
        "the SEC accession and EDGAR URL resolved offline against data/manifest.csv. "
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
        row[1].text = c.get("source") or ""
        _fill(row[2], lines)
    for row in t.rows:
        row.cells[0].width, row.cells[1].width, row.cells[2].width = Inches(0.5), Inches(2.4), Inches(3.6)

    with open(DATA / "manifest.csv", newline="") as fh:
        held = sum(1 for r in csv.DictReader(fh) if r["product"] == key)
    doc.add_paragraph(
        f"Data sources: SEC EDGAR filings ({held} held for this product in data/manifest.csv, "
        "every row with its accession) and DOL EBSA Form 5500 data for the plan. "
        f"{plan['anonymization_rule']}")


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
    doc.add_paragraph(RULE)
    for para in RULE_PARAS:
        doc.add_paragraph(para)

    facts_path = DATA / "facts" / f"{key}.json"
    fdoc = json.loads(facts_path.read_text()) if facts_path.exists() else {}
    fbc = facts_by_cell(fdoc.get("facts", {}))

    doc.add_heading("Six-factor findings", level=1)
    doc.add_paragraph(
        "Per factor: the typed facts the engines read (each cites its cell), "
        "then the complete first sentence of every evidenced cell with its "
        "status, then the cells marked not applicable with the reason. The "
        "full sourced text, quote and document of every cell is in "
        "data/evidence/ and on the site's Evaluation view.")
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text = "Factor", "Findings (cell, status, first sentence)"
    for n, label in FACTORS.items():
        row = table.add_row().cells
        row[0].text = f"{n}. {label}"
        _fill(row[1], _findings(p, label, fbc))
    for row in table.rows:
        row.cells[0].width, row.cells[1].width = Inches(1.2), Inches(5.3)

    doc.add_heading("Benchmark selection and justification", level=1)
    if sel is None:
        doc.add_paragraph("Engine profile pending for this product: "
                          "extraction depth required before selection.")
    else:
        if sel.get("escalation"):
            doc.add_heading("ESCALATION: no meaningful benchmark "
                            "constructible", level=2)
            doc.add_paragraph(sel["escalation"])
            doc.add_paragraph(
                "Under the proposal's own terms, a benchmark that is not "
                "meaningful cannot support the comparison. Proceeding without "
                "one documented here would undercut the safe harbor. "
                "Recommended action: do not proceed pending the data steps "
                "above. Retain this memo as the record of the determination.")
        for slot, badge in (("primary", "Primary"), ("secondary", "Secondary")):
            s = sel.get(slot)
            if not s:
                continue
            doc.add_heading(f"{badge}: {s['candidate']} (score "
                            f"{s['score']}/{s['max']})", level=2)
            comp = s.get("comparison")
            if not comp and s.get("comparison_note"):
                doc.add_paragraph("Comparison not computable on held data: "
                                  f"{s['comparison_note']}. The candidate is scored on "
                                  "its own descriptors.")
            if comp:
                doc.add_paragraph(
                    f"Window {comp['window']}"
                    f"{(' (' + comp['window_note'] + ')') if comp.get('window_note') else ''}"
                    f": fund {comp['fund_ann_pct']}%/yr "
                    f"vs benchmark {comp['index_ann_pct']}%/yr, "
                    f"KS-PME {comp['ks_pme']}, Direct Alpha "
                    f"{comp['direct_alpha_pct']}%/yr. Disclosure: PME and "
                    "alpha computed on appraisal-lagged NAVs are "
                    "window-sensitive and can be smoothing-flattered. "
                    "Conclusions should be read with the methodology's "
                    "window-sensitivity analysis."
                    + (f" {comp['low_confidence'][0].upper()}{comp['low_confidence'][1:]}."
                       if comp.get("low_confidence") else ""))
                doc.add_paragraph(
                    "Two-point comparison: one contribution at the window start "
                    "and one valuation at the end. Direct Alpha is the "
                    "annualized form of the same two flows."
                    + (f" ILLUSTRATIVE monthly-schedule KS-PME "
                       f"{comp['ks_pme_monthly_schedule']} "
                       f"({comp['schedule_contributions']} equal contributions "
                       "at the window start and each month-end inside it, "
                       "valued at the window end). The two-point figure is "
                       "primary."
                       if comp.get("ks_pme_monthly_schedule") is not None else ""))
            for r in s["reasons"]:
                doc.add_paragraph(r, style="List Bullet")

        doc.add_heading("Rejection log (candidates considered and not "
                        "selected)", level=2)
        rt = doc.add_table(rows=1, cols=3)
        rt.style = "Table Grid"
        h = rt.rows[0].cells
        h[0].text, h[1].text, h[2].text = "Candidate", "Score", "Reason"
        for r in sel["rejected"]:
            c = rt.add_row().cells
            c[0].text = r["candidate"]
            c[1].text = f"{r['score']}/{r['max']}"
            c[2].text = r["rejection"]
        for row in rt.rows:
            row.cells[0].width = Inches(2.4)
            row.cells[1].width = Inches(0.8)
            row.cells[2].width = Inches(3.3)

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
                f"{fdoc.get('membership_rationale', '')}")
            v29 = p["cells"]["2.9"].get("value")
            if v29:
                doc.add_paragraph(str(v29))
            comp = co.get("composite", {})
            if comp.get("refused"):
                doc.add_paragraph("Cohort composite: REFUSED, "
                                  + comp.get("reason", ""))
            for cv in co.get("caveats", []):
                doc.add_paragraph(f"Caveat: {cv}", style="List Bullet")
            doc.add_paragraph(
                "Cohort exclusion log: every candidate considered and not "
                "admitted is recorded with its reason in "
                "data/roster_decisions.md (rendered on the site's Cohorts "
                "view). Membership is an argued judgment, not a tag.")

    _recommendation_section(doc, sel, m, fdoc, anchor)
    _scope_section(doc)
    _case_law_section(doc, p)

    _provenance_section(doc, key, p, anchor)

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
    for stale in out.glob("*.docx"):
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

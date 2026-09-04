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
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt

from tark_data import (DATA, FACTORS, cells_by_factor, load_plan, load_products,
                       plan_keys, record_as_of, status_kind)

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
     "score, and the true reason it was or was not chosen. Note: the pleading "
     "standard for benchmark-based claims is before the Supreme Court in "
     "Anderson v. Intel (argument expected October Term 2026). This memo's "
     "approach is designed to be defensible under either outcome."),
]


def _cell_lines(product: dict, factor_label: str, limit: int = 4) -> str:
    picks = []
    for cid, cell in cells_by_factor(product)[factor_label]:
        if status_kind(cell.get("status", "")) in ("extracted", "verified",
                                                   "computed", "partial",
                                                   "structured"):
            v = (cell.get("value") or "").strip()
            if v:
                picks.append(f"{cid}: {v[:220]}")
        if len(picks) >= limit:
            break
    return "\n".join(picks) if picks else "No cells evaluated yet. Pending extraction."


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

    doc.add_heading("Six-factor findings (summary)", level=1)
    table = doc.add_table(rows=1, cols=2)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text = "Factor", "Key findings (cell: value)"
    for n, label in FACTORS.items():
        row = table.add_row().cells
        row[0].text = f"{n}. {label}"
        row[1].text = _cell_lines(p, label)
    for row in table.rows:
        row.cells[0].width, row.cells[1].width = Inches(1.4), Inches(5.1)

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
    if mp.exists():
        m = json.loads(mp.read_text())
        doc.add_heading("Product-to-plan liquidity match", level=1)
        doc.add_paragraph(
            f"Plan: {anchor['display_label']}. Structural verdict (typed facts, "
            f"cells 3.1, 3.3, 2.7, plan-independent): {m['verdict'].upper()}. "
            "Scenario verdict (ILLUSTRATIVE, this plan): "
            f"{(m.get('scenario_verdict') or 'not computable').upper()}.")
        for r in m["reasons"]:
            doc.add_paragraph(r, style="List Bullet")

    # ---- cohort placement + exclusion log (peer-comparison layer) ----
    facts_path = DATA / "facts" / f"{key}.json"
    if facts_path.exists():
        fdoc = json.loads(facts_path.read_text())
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

    doc.add_heading("Provenance", level=1)
    counts: dict[str, int] = {}
    for cell in p["cells"].values():
        counts[status_kind(cell.get("status", ""))] = \
            counts.get(status_kind(cell.get("status", "")), 0) + 1
    doc.add_paragraph(
        "Every populated cell carries its source document, section, quote, "
        "extractor and verifier in data/evidence/. Current cell status for "
        "this product: "
        + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())) + ". "
        "Cells marked extracted-unverified or computed await independent "
        "verification. Verified cells have been independently re-checked. "
        "Cells marked structured come directly from machine-readable "
        "regulatory data (N-CEN structured datasets, XBRL company facts) "
        "with the source dataset cited. No model judgment is involved.")
    doc.add_paragraph(f"Data sources include SEC EDGAR filings (see "
                      f"data/manifest.csv) and DOL EBSA Form 5500 bulk data. "
                      f"{anchor['anonymization_rule']}")

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

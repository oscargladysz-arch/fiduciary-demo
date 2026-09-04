"""
Ingest gate: the extraction contract, offline
==============================================
Drives src/ingest.py against a scratch copy of the data layer with a mock
client and a synthetic filing (no network, no key). Asserts the contract:
a verbatim quote makes extracted-unverified, a quote the document does not
contain downgrades to partial with the reason, not found leaves the cell
pending, evidence and structured cells are never overwritten, nothing is
ever verified, the JSON and the CSV agree, and the source string resolves
through the offline citation resolver.

Run: python src/test_ingest.py   (exit 0 = all pass)
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

SCRATCH = Path(tempfile.mkdtemp(prefix="tark_ingest_"))
os.environ["TARK_DATA_DIR"] = str(SCRATCH / "data")
shutil.copytree(BASE / "data", SCRATCH / "data",
                ignore=shutil.ignore_patterns("raw", "census", "memos", "citations", "liquidity",
                                              "benchmarks", "cohorts", "facts", "analytics", "series*"))

import ingest  # noqa: E402
from ingest import (CellExtraction, FilingText, Outcome, doc_label, extractable_cells,  # noqa: E402
                    filing_text, normalize, run_extraction, verify)
from resolve_citations import references  # noqa: E402
from tark_data import CELLS, DATA, EVIDENCE_COLUMNS, load_evidence, load_product, status_kind  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" : {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


# ---------------- a synthetic fund: scaffold, one filing, one manifest row
KEY, CIK = "zz_synthetic", "9999999"
FILING = """<html><body>
<div><b>PROSPECTUS</b></div>
<p>The Fund pays the Adviser a management fee at an annual rate of 1.25% of the Fund&rsquo;s average daily Managed Assets.</p>
<table><tr><td>Acquired Fund Fees and Expenses</td><td>0.42%</td></tr></table>
<hr style="page-break-after:always">
<p>The Fund does not charge an early repurchase fee.</p>
<p>The Fund will make quarterly repurchase offers for 5% of its outstanding Shares.</p>
<hr style="page-break-before: always">
<p>Shareholders receive Form 1099-DIV. The Fund has elected to be treated as a RIC.</p>
</body></html>"""
raw_dir = SCRATCH / "data" / "raw" / KEY
raw_dir.mkdir(parents=True)
(raw_dir / "486BPOS_2026-05-01_synthetic.htm").write_text(FILING)
row = {"product": KEY, "fund_name": "Synthetic Interval Fund", "cik": CIK, "doc_set": "prospectus",
       "form": "486BPOS", "filing_date": "2026-05-01", "accession": "0009999999-26-000001",
       "primary_document": "synthetic.htm",
       "url": "https://www.sec.gov/Archives/edgar/data/9999999/000999999926000001/synthetic.htm",
       "local_path": f"data/raw/{KEY}/486BPOS_2026-05-01_synthetic.htm", "pulled_at_utc": "2026-09-04T00:00:00+00:00"}
from promote import blank_cell  # noqa: E402
cells = {cid: blank_cell(el) for cid, el in CELLS.items()}
cells["4.5"] = {"element": CELLS["4.5"], "value": "Auditor (N-CEN structured): Example LLP.", "status": "structured",
                "source": "N-CEN 0009999999-26-000009 (structured dataset)", "section": "PUBLIC_ACCOUNTANT",
                "quote": "PUB_ACCOUNTANT_NAME=Example LLP", "extracted_by": "census pipeline", "verified_by": ""}
cells["2.3"] = {"element": CELLS["2.3"], "value": "Total annual expenses 2.10% (Class I).", "status": "extracted-unverified",
                "source": "486BPOS filed 2026-05-01", "section": "fee table", "quote": "2.10%",
                "extracted_by": "a person", "verified_by": ""}
(DATA / "products" / f"{KEY}.json").write_text(json.dumps(
    {"product_key": KEY, "fund_name": "Synthetic Interval Fund", "cik": CIK, "wrapper": "interval fund (Rule 23c-3)",
     "depth": "cohort", "cells": cells}, indent=1))
with open(DATA / "evidence" / f"{KEY}_evidence.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=EVIDENCE_COLUMNS)
    w.writeheader()
    for cid, c in cells.items():
        w.writerow({"cell_id": cid, "element": c["element"], "value": c["value"], "source_doc": c["source"],
                    "source_section": c["section"], "quote": c["quote"], "local_file": "", "date_pulled": "",
                    "extracted_by": c["extracted_by"], "verified_by": "", "status": c["status"]})

# ---------------- filing text with page anchors
doc = filing_text(raw_dir / "486BPOS_2026-05-01_synthetic.htm", doc_label(row))
check("filing text: three pages split on page-break styles", len(doc.pages) == 3, str(len(doc.pages)))
check("filing text: entities decoded and the quote located on page 1",
      doc.page_of("management fee at an annual rate of 1.25% of the Fund's average daily Managed Assets") == 1)
check("filing text: a page-two passage is found on page 2",
      doc.page_of("quarterly repurchase offers for 5% of its outstanding Shares") == 2)
check("document label parses through the citation resolver as form and filed date",
      references(doc.label) and references(doc.label)[0]["form"] == "486BPOS"
      and references(doc.label)[0]["filed"] == ["2026-05-01"]
      and references(doc.label)[0]["accessions"] == ["0009999999-26-000001"])

# ---------------- the contract: extractable cells exclude what the model may not write
ex_cells = extractable_cells()
check("contract: no engine-owned, advisor or census cell is extractable",
      not set(ex_cells) & set(ingest.ENGINE_OWNED + ingest.ADVISOR_CELLS + ingest.CENSUS_CELLS))
check("contract: every extractable cell has an instruction and preferred document sets",
      all(ingest.CELL_CONTRACT[c][0] and ingest.CELL_CONTRACT[c][1] for c in ex_cells))
check("contract: instructions carry no semicolon or em dash",
      all(";" not in ingest.CELL_CONTRACT[c][0] and "—" not in ingest.CELL_CONTRACT[c][0] for c in ex_cells)
      and ";" not in ingest.SYSTEM)


# ---------------- a mock client with canned answers, one deliberate lie
CANNED = {
    "2.1": CellExtraction(found=True,
                          value="Management fee 1.25% per year on average daily Managed Assets (a leverage-inclusive base).",
                          quote="management fee at an annual rate of 1.25% of the Fund's average daily Managed Assets",
                          source_doc=doc.label, section="Management fee", not_found_reason=""),
    "2.4": CellExtraction(found=True, value="AFFE line present at 0.42%.",
                          quote="Acquired Fund Fees and Expenses 0.42%", source_doc=doc.label,
                          section="fee table", not_found_reason=""),
    "2.7": CellExtraction(found=True, value="No early repurchase fee.",
                          quote="The Fund does not charge an early repurchase fee.", source_doc=doc.label,
                          section="Repurchases", not_found_reason=""),
    # the lie: a figure the document does not contain
    "3.1": CellExtraction(found=True, value="Quarterly repurchase offers for 25% of outstanding Shares.",
                          quote="quarterly repurchase offers for 25% of its outstanding Shares",
                          source_doc=doc.label, section="Repurchases", not_found_reason=""),
    "6.4": CellExtraction(found=True, value="Form 1099-DIV, RIC status.",
                          quote="Shareholders receive Form 1099-DIV. The Fund has elected to be treated as a RIC.",
                          source_doc="a document that is not on record", section="Taxes", not_found_reason=""),
}
calls = []


class _Resp:
    def __init__(self, parsed):
        self.parsed_output = parsed
        self.stop_reason = "end_turn"


class _Messages:
    def parse(self, **kw):
        calls.append(kw)
        cid = kw["messages"][0]["content"][1]["text"].split(",")[0].replace("Cell ", "")
        return _Resp(CANNED.get(cid, CellExtraction(found=False, value="", quote="", source_doc="",
                                                    section="", not_found_reason=f"no passage for {cid}")))


class MockClient:
    messages = _Messages()


outcomes = run_extraction(MockClient(), KEY, [doc], model="mock-model", today="2026-09-04")
by = {o.cid: o for o in outcomes}
prod = load_product(KEY)

check("verbatim quote: 2.1 written as extracted-unverified with the page in the source",
      prod["cells"]["2.1"]["status"] == "extracted-unverified" and "page 1" in prod["cells"]["2.1"]["source"]
      and prod["cells"]["2.1"]["value"].startswith("Management fee 1.25%"))
check("quote across a table row (cells joined by spaces) still verifies: 2.4 extracted-unverified",
      prod["cells"]["2.4"]["status"] == "extracted-unverified")
check("page anchor: 2.7 located on page 2", "page 2" in prod["cells"]["2.7"]["source"])
check("the lie: 3.1 downgraded to partial with the reason, value kept for a human",
      prod["cells"]["3.1"]["status"].startswith("partial - quote not located verbatim")
      and "25%" in prod["cells"]["3.1"]["value"] and by["3.1"].reason)
check("unknown document: 6.4 downgraded to partial, cited document not among the held filings",
      prod["cells"]["6.4"]["status"].startswith("partial - cited document not among the held filings"))
check("not found: 1.1 stays pending with the reason in the report only",
      prod["cells"]["1.1"]["status"] == "pending extraction" and by["1.1"].record is None
      and "no passage" in by["1.1"].reason)
check("evidence cell 2.3 and structured cell 4.5 were not sent to the model and are unchanged",
      prod["cells"]["2.3"]["extracted_by"] == "a person" and prod["cells"]["4.5"]["status"] == "structured"
      and not any("Cell 2.3," in c["messages"][0]["content"][1]["text"]
                  or "Cell 4.5," in c["messages"][0]["content"][1]["text"] for c in calls))
check("nothing is verified: every written cell has empty verified_by and no verified status",
      all(c["verified_by"] == "" and not str(c["status"]).startswith("verified") for c in prod["cells"].values()))
csv_rows = {r["cell_id"]: r for r in load_evidence(KEY)}
check("JSON and CSV agree on value, source, quote, status and extractor for every written cell",
      all(csv_rows[o.cid]["value"] == prod["cells"][o.cid]["value"]
          and csv_rows[o.cid]["source_doc"] == prod["cells"][o.cid]["source"]
          and csv_rows[o.cid]["quote"] == prod["cells"][o.cid]["quote"]
          and csv_rows[o.cid]["status"] == prod["cells"][o.cid]["status"]
          and csv_rows[o.cid]["extracted_by"] == prod["cells"][o.cid]["extracted_by"]
          for o in outcomes if o.record))
check("extractor names the script, the model and the date, never a person",
      all(o.record["extracted_by"].startswith("src/ingest.py (mock-model, 2026-09-04)") for o in outcomes if o.record))
check("the documents ride as a cached prefix and the system prompt forbids inference",
      all(c["messages"][0]["content"][0].get("cache_control") == {"type": "ephemeral"} for c in calls)
      and "never infer" in calls[0]["system"].lower())
check("every call requested the structured CellExtraction output",
      all(c["output_format"] is CellExtraction for c in calls))
rep = json.loads((DATA / "ingest" / f"{KEY}_report.json").read_text())
check("report lists every contract cell with status and reason",
      {o["cell"] for o in rep["outcomes"]} == set(ex_cells) and all("status" in o for o in rep["outcomes"]))
check("the scratch run never touched the repository's data",
      not (BASE / "data" / "products" / f"{KEY}.json").exists() and not (BASE / "data" / "ingest").exists()
      or not (BASE / "data" / "ingest" / f"{KEY}_report.json").exists())

# ---------------- a second run is refused where a cell became evidence
try:
    run_extraction(MockClient(), KEY, [doc], only={"2.1"}, model="mock-model", today="2026-09-04")
    second_ok = True
except SystemExit:
    second_ok = False
prod2 = load_product(KEY)
check("second run: an extracted cell is kept, not re-extracted or overwritten",
      second_ok and prod2["cells"]["2.1"] == prod["cells"]["2.1"])

shutil.rmtree(SCRATCH, ignore_errors=True)
print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll ingest checks pass.")
sys.exit(1 if FAILS else 0)

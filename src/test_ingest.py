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
      all(o.record["extracted_by"].startswith("Tark ingest (mock-model, 2026-09-04)") for o in outcomes if o.record))
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

# ---------------- calibration harness: committed cells vs the mock's outcomes
from calibrate_ingest import compare, figures, form_and_date, summarize  # noqa: E402
check("calibration: figures are read from both sides the same way",
      figures("1.25% of Managed Assets, $5,000 minimum, 2026-05-01") == {"1.25%", "$5000", "2026-05-01"})
check("calibration: form and filed date parse from a source string",
      form_and_date("486BPOS filed 2026-05-01 (accession 0009999999-26-000001), fee table, page 1") == ("486BPOS", "2026-05-01"))
truth = {"2.1": {"value": "Management fee 1.25% on Managed Assets.", "source": "486BPOS filed 2026-05-01", "status": "extracted-unverified"},
         "3.1": {"value": "Quarterly offers for 5% of outstanding Shares.", "source": "486BPOS filed 2026-05-01", "status": "extracted-unverified"},
         "1.1": {"value": "Net total return 7.1% FY2025.", "source": "N-CSR filed 2026-06-01", "status": "extracted-unverified"}}
rows = {c: compare(truth[c], by[c].record, by[c].status, by[c].reason) for c in truth}
check("calibration: a located cell with the committed figure scores recall 1 and same document",
      rows["2.1"]["located"] and rows["2.1"]["figure_recall"] == 1.0 and rows["2.1"]["same_document"] is True)
check("calibration: the lie scores as not located with figure recall 0",
      not rows["3.1"]["located"] and rows["3.1"]["figure_recall"] == 0.0)
check("calibration: a pending cell scores as not located with no document comparison",
      not rows["1.1"]["located"] and rows["1.1"]["same_document"] is None)
summ = summarize(rows)
check("calibration: the summary counts cells, located, partial and pending",
      summ["cells"] == 3 and summ["located"] == 1 and summ["partial"] == 1 and summ["pending"] == 1)

# ---------------- advisor-stated files (P2-6): validator and the not-evidence rule
from tark_data import validate_advisor, validate_product, ADVISOR_STATED_CELLS  # noqa: E402
adv_dir = DATA / "advisor"
adv_dir.mkdir(exist_ok=True)
good = {"plan": "plan_tech_media", "product": KEY, "not_evidence": "input, not evidence",
        "cells": {"6.6": {"value": "Recordkeeper confirmed NSCC order handling for quarterly windows.",
                          "signer": "A. Person, plan committee chair", "date": "2026-09-04",
                          "status": "advisor-stated - A. Person, plan committee chair, 2026-09-04"}}}
(adv_dir / f"plan_tech_media__{KEY}.json").write_text(json.dumps(good))
check("advisor: a signed, dated statement on an advisor cell validates", validate_advisor() == [])
bad = json.loads(json.dumps(good))
bad["cells"]["6.6"]["signer"] = ""
bad["cells"]["2.1"] = dict(good["cells"]["6.6"])
bad["cells"]["2.1"]["date"] = "Sept 4"
(adv_dir / f"plan_tech_media__{KEY}.json").write_text(json.dumps(bad))
errs = validate_advisor()
check("advisor: missing signer, a non-advisor cell and a non-ISO date are each refused",
      any("no signer" in e for e in errs) and any("2.1 is not an advisor-stated cell" in e for e in errs)
      and any("date is not ISO" in e for e in errs))
(adv_dir / f"plan_tech_media__{KEY}.json").write_text(json.dumps(good))
(adv_dir / f"plan_nowhere__{KEY}.json").write_text(json.dumps({**good, "plan": "plan_nowhere"}))
check("advisor: an unknown plan is refused", any("unknown plan or product" in e for e in validate_advisor()))
(adv_dir / f"plan_nowhere__{KEY}.json").unlink()
# the not-evidence rule: the status may never enter an evidence cell
prod_adv = load_product(KEY)
prod_adv["cells"]["6.6"] = {**prod_adv["cells"]["6.6"], "status": "advisor-stated - someone, 2026-09-04",
                            "value": "x", "source": "s", "extracted_by": "e"}
(DATA / "products" / f"{KEY}.json").write_text(json.dumps(prod_adv))
check("advisor: an advisor-stated status inside an evidence cell is refused by validate_product",
      any("advisor-stated is not an evidence status" in e for e in validate_product(KEY)))
check("advisor: the six cells are exactly the committee cells",
      set(ADVISOR_STATED_CELLS) == {"6.6", "6.8", "3.7", "2.8", "3.5", "4.9"})

# ---------------- verify_cell (P2-7): every refusal, the dry run, never a write
import verify_cell  # noqa: E402
def refused(*a, **kw):
    try:
        verify_cell.apply(*a, **kw)
        return False
    except SystemExit:
        return True
before = (DATA / "products" / f"{KEY}.json").read_text()
check("verify: an empty signer is refused", refused(KEY, "2.1", "", "2026-09-04"))
check("verify: a non-ISO date is refused", refused(KEY, "2.1", "A. Person, chair", "Sept 4 2026"))
check("verify: a signer naming a model, script or agent is refused",
      refused(KEY, "2.1", "Claude Code", "2026-09-04") and refused(KEY, "2.1", "ingest.py run", "2026-09-04"))
check("verify: a partial cell cannot be verified", refused(KEY, "3.1", "A. Person, chair", "2026-09-04"))
check("verify: a pending cell cannot be verified", refused(KEY, "1.1", "A. Person, chair", "2026-09-04"))
check("verify: a structured cell cannot be verified", refused(KEY, "4.5", "A. Person, chair", "2026-09-04"))
row = verify_cell.apply(KEY, "2.1", "A. Person, committee chair", "2026-09-04", dry_run=True)
after = (DATA / "products" / f"{KEY}.json").read_text()
check("verify: the dry run shows the signed row and writes nothing",
      row["status"] == "verified - A. Person, committee chair, 2026-09-04"
      and row["verified_by"] == "A. Person, committee chair, 2026-09-04"
      and row["value"] == prod["cells"]["2.1"]["value"] and row["quote"] == prod["cells"]["2.1"]["quote"]
      and before == after and load_product(KEY)["cells"]["2.1"]["status"] == "extracted-unverified")
check("verify: no verified row exists in the scratch record after the tests",
      all(not str(c["status"]).startswith("verified") for c in load_product(KEY)["cells"].values()))

# ---------------- plan intake (P2-8): anonymized label required, derived recomputed
import plan_intake  # noqa: E402
from tark_data import validate_plan  # noqa: E402
FORM = {"display_label": "US regional hospital 403(b) plan (~$400M, OH)",
        "anonymization_label": "US regional hospital 403(b) plan (~$400M, OH)",
        "plan_year": "2024-01-01 to 2024-12-31", "net_assets_eoy": 400_000_000, "net_assets_boy": 360_000_000,
        "tot_admin_expenses": 800_000, "with_account_balances": 5000, "active_eoy": 4200,
        "separated_deferred_vested": 700, "retired_receiving": 30, "pension_benefit_codes": "2E2G2J2K",
        "derived": {"avg_balance_per_account": 1}}
def intake_refused(form):
    try:
        plan_intake.intake(form)
        return False
    except SystemExit:
        return True
check("intake: a label that looks like a sponsor is refused",
      intake_refused({**FORM, "display_label": "Acme Widgets Inc. 401(k)", "anonymization_label": "Acme Widgets Inc. 401(k)"}))
check("intake: an EIN in the label is refused",
      intake_refused({**FORM, "display_label": "plan 12-3456789", "anonymization_label": "plan 12-3456789"}))
check("intake: without the anonymization confirmation it is refused",
      intake_refused({k: v for k, v in FORM.items() if k != "anonymization_label"}))
check("intake: missing benefit codes are refused", intake_refused({**FORM, "pension_benefit_codes": ""}))
check("intake: separated above accounts is refused", intake_refused({**FORM, "separated_deferred_vested": 6000}))
out = plan_intake.intake(FORM)
newp = json.loads(out.read_text())
check("intake: the plan file validates like a reference plan and stores no identity block",
      validate_plan(newp["plan_key"]) == [] and "identity_private" not in newp
      and newp["anonymization_label"] == newp["display_label"])
check("intake: derived figures are recomputed from the primitives, the form's own are ignored",
      newp["derived"]["avg_balance_per_account"] == 80000 and newp["derived"]["admin_expense_ratio_pct"] == 0.2
      and newp["derived"]["yoy_net_asset_growth_pct"] == 11.1)
check("intake: Schedule H lines left empty are null with a reason, never zero",
      newp["schedule_h"]["benefit_payments_2e"]["value"] is None and newp["schedule_h"]["benefit_payments_2e"]["reason"])
check("intake: the same key twice is refused", intake_refused(FORM))
check("intake: a labeled plan reads as fully participant-directed from its codes",
      __import__("tark_liquidity").plan_direction(newp) == "total")
out.unlink()

# ---------------- the service: one endpoint, honest refusals, no job state
(SCRATCH / "data" / "census").mkdir(exist_ok=True)
shutil.copy(BASE / "data" / "census" / "census.json", SCRATCH / "data" / "census" / "census.json")
sys.path.insert(0, str(BASE))
from starlette.testclient import TestClient  # noqa: E402
from service.app import app  # noqa: E402
tc = TestClient(app)
routes = [r.path for r in app.routes if getattr(r, "methods", None)]
check("service: exactly one endpoint, POST /evaluate, no docs pages",
      routes == ["/evaluate"] and app.docs_url is None and app.openapi_url is None)
r1 = tc.post("/evaluate", json={"cik": "1", "key": "nobody"}).json()
check("service: a CIK outside the census is refused with the reason and the commands",
      r1["status"] == "refused" and "census" in r1["reason"] and any("promote.py" in c for c in r1["commands"]))
r2 = tc.post("/evaluate", json={"cik": "1467631", "key": "acap_strategic"}).json()
check("service: a census CIK without a registry entry is refused, the registry comes first",
      r2["status"] == "refused" and "registry" in r2["reason"] and "python src/ingest.py 1467631 --key acap_strategic --skip-fetch" in r2["commands"])
r3 = tc.post("/evaluate", json={"cik": "1735964", "key": "cliffwater_cclfx"}).json()
check("service: an already evaluated CIK is refused by name",
      r3["status"] == "refused" and "already evaluated as cliffwater_cclfx" in r3["reason"])
r4 = tc.post("/evaluate", json={"cik": "1467631", "key": "Bad Key!"}).json()
check("service: a malformed key is refused", r4["status"] == "refused" and "key must match" in r4["reason"])
check("service: no answer carries a job id, queue or progress field",
      all(not (set(r) & {"job_id", "job", "queued", "progress", "state"}) for r in (r1, r2, r3, r4)))

# ---------------- source documents (R2-P1-14, R2-P1-16): the authority text
# path and the case-law path, on this scratch copy. Runs here so the hook's
# gate count is unchanged while the checks are enforced.
import test_sources  # noqa: E402
test_sources.run(check)

shutil.rmtree(SCRATCH, ignore_errors=True)
print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll ingest checks pass.")
sys.exit(1 if FAILS else 0)

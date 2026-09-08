"""
Ingest gate: the extraction contract, offline
==============================================
Drives src/ingest.py against a scratch copy of the data layer with a mock
client and a synthetic filing (no network, no key). Asserts the contract:
a verbatim quote makes extracted-unverified, a quote the document does not
contain downgrades to partial with the reason, not found leaves the cell
pending, evidence and structured cells are never overwritten, nothing is
ever verified, the JSON and the CSV agree, and the source string resolves
through the offline citation resolver. Then the hardened loop (R3-P3-3):
token and dollar accounting at a configured price list, the cost estimate
before the first call, the progress callback, a write after every cell that
survives an interrupt, one retry at reduced context, the time and cost stops,
per-cell page retrieval under a small context cap, inline XBRL and hidden
blocks stripped, the PDF splitter, exhibits on one accession, promote and the
fetcher as library calls under the data root with a faked network, and
run_product as the one entry the worker calls. The model client is always the
mock in src/mock_model.py (decision 8.17).

Run: python src/test_ingest.py   (exit 0 = all pass)
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
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
from mock_model import (IXBRL_PATH, FILING_PATH, PDFTEXT_PATH, FakeClock, MockClient,  # noqa: E402
                        canned_answers, context_error)
FILING = FILING_PATH.read_text()
raw_dir = SCRATCH / "data" / "raw" / KEY
raw_dir.mkdir(parents=True)
(raw_dir / "486BPOS_2026-05-01_synthetic.htm").write_text(FILING)
# the price list for the mock model, in USD per million tokens: the run
# refuses an unpriced model before any call (every dollar figure is an
# estimate at this list)
PRICES = {"input": 5.0, "output": 25.0, "cache_write": 6.25, "cache_read": 0.5}
os.environ["TARK_PRICES_JSON"] = json.dumps({"mock-model": PRICES})
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


# ---------------- the mock client: canned answers from the fixture, one deliberate lie
answers, usage_by, default_usage = canned_answers(doc.label)
client = MockClient(answers, usage_by, default_usage)
calls = client.calls
events = []
outcomes = run_extraction(client, KEY, [doc], model="mock-model", today="2026-09-04", on_progress=events.append)
by = {o.cid: o for o in outcomes}
prod = load_product(KEY)

check("verbatim quote: 2.1 written as extracted-unverified with the page in the source",
      prod["cells"]["2.1"]["status"] == "extracted-unverified" and "page 1" in prod["cells"]["2.1"]["source"]
      and prod["cells"]["2.1"]["value"].startswith("Management fee 1.25%"))
check("quote across a table row (cells joined by spaces) still verifies: 2.4 extracted-unverified",
      prod["cells"]["2.4"]["status"] == "extracted-unverified")
check("page anchor: 2.7 located on page 2", "page 2" in prod["cells"]["2.7"]["source"])
_ev = {r["cell_id"]: r for r in load_evidence(KEY)}
check("ledger: every row the ingest wrote from a held filing carries the filing's record path and accession (audit item 41)",
      all(_ev[c]["local_file"] == f"data/raw/{KEY}/486BPOS_2026-05-01_synthetic.htm"
          and _ev[c]["accession"] == "0009999999-26-000001" for c in ("2.1", "2.4", "2.7")))
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
    run_extraction(MockClient(answers, usage_by, default_usage), KEY, [doc], only={"2.1"}, model="mock-model",
                   today="2026-09-04")
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


# ---------------- R3-P3-3: the hardened loop, against the same mock
from ingest import (ReaderMissing, Refusal, documents_for, dry_run_copy, filing_from_row,  # noqa: E402
                    pdf_pages, run_product, split_form_feeds, usd_of)
from promote import blank_cell as _blank  # noqa: E402
from tark_data import validate_product  # noqa: E402

_cell_of = client.messages.cell_of
_exp_usd = sum(usd_of(usage_by.get(_cell_of(c)) or default_usage, PRICES) for c in calls)
_exp_out = sum((usage_by.get(_cell_of(c)) or default_usage)["output_tokens"] for c in calls)
check("accounting: the run's calls, tokens and dollars are the sum of what every response reported, at the price list",
      outcomes.cost.calls == len(calls) and outcomes.cost.output_tokens == _exp_out
      and abs(outcomes.cost.usd - _exp_usd) < 1e-9 and rep["cost"]["calls"] == len(calls)
      and abs(rep["cost"]["usd"] - round(_exp_usd, 6)) < 1e-9 and rep["cost"]["model"] == "mock-model",
      f"{outcomes.cost.as_dict()} vs {_exp_usd}")
check("accounting: the per-cell rows carry tokens, dollars, seconds, attempts and the pages sent",
      all({"tokens", "usd", "seconds", "attempts", "pages_sent"} <= set(o) for o in rep["outcomes"])
      and by["2.1"].tokens == usage_by["2.1"] and abs(by["2.1"].usd - usd_of(usage_by["2.1"], PRICES)) < 1e-12
      and by["2.1"].attempts == 1)
check("estimate: computed before the first call from the client's own token count, labeled an estimate, in the report",
      events[0]["event"] == "run_start" and events[0]["estimate"]["method"] == "count_tokens"
      and events[0]["estimate"]["usd"] > 0 and "estimate" in events[0]["estimate"]["note"]
      and rep["estimate"] == events[0]["estimate"] and client.count_calls >= 1
      and events[0]["estimate"]["calls"] == len(calls), str(events[0].get("estimate")))
_kinds = [e["event"] for e in events]
check("progress: run_start, then cell_start and cell_done for every contract cell, then run_end, each with the documented keys",
      _kinds[0] == "run_start" and _kinds[-1] == "run_end" and _kinds[1:-1] == ["cell_start", "cell_done"] * len(ex_cells)
      and all({"cell", "index", "total", "elapsed_s", "usd_so_far"} <= set(e) for e in events if e["event"] == "cell_start")
      and all({"cell", "status", "reason", "tokens", "usd", "seconds", "attempts", "usd_so_far"} <= set(e)
              for e in events if e["event"] == "cell_done")
      and events[-1]["cost"]["calls"] == len(calls) and events[-1]["stopped"] is None
      and events[-1]["written"] == outcomes.written, str(_kinds[:4]))
check("progress: a kept evidence cell is reported as kept, never sent",
      any(e["event"] == "cell_done" and e["cell"] == "2.3" and e["reason"] == "kept: extracted cell" for e in events))
_r = run_extraction(MockClient(answers, usage_by, default_usage), KEY, [doc], only={"1.1"}, model="mock-model",
                    today="2026-09-04", on_progress=lambda e: 1 / 0)
check("progress: a callback that raises is recorded in the report and never aborts the run",
      _r.stopped is None and len(_r.callback_errors) == 4 and all("ZeroDivisionError" in x for x in _r.callback_errors)
      and json.loads(_r.report_path.read_text())["callback_errors"] == _r.callback_errors)
check("writes: no temporary file is left beside the product JSON, the ledger or the report",
      not list((DATA / "products").glob("*.tmp")) and not list((DATA / "evidence").glob("*.tmp"))
      and not list((DATA / "ingest").glob("*.tmp")))
check("context: the whole corpus fits the cap, so every call carries one identical cached prefix and no page selection",
      rep["context"]["whole_corpus"] and len({c["messages"][0]["content"][0]["text"] for c in calls}) == 1
      and all(o["pages_sent"] == "all" for o in rep["outcomes"] if o["attempts"]))
check("report: the progress block says the run finished, the stop is null, the documents carry kind, pages and accession",
      rep["progress"] == {"done": len(ex_cells), "total": len(ex_cells), "final": True} and rep["stopped"] is None
      and rep["documents"][0]["kind"] == "html" and rep["documents"][0]["pages"] == 3)
try:
    run_extraction(MockClient(answers, usage_by, default_usage), KEY, [doc], only={"1.1"}, model="unpriced-model")
    unpriced = False
except Refusal as e:
    unpriced = "no price list for model unpriced-model" in str(e)
check("prices: a model without a price list is refused before any call, with the override named", unpriced)


def reset_cells(key, keep=("2.3", "4.5")):
    """Every cell back to pending except the evidence ones, in the JSON and the ledger."""
    pr = load_product(key)
    for cid in pr["cells"]:
        if cid not in keep:
            pr["cells"][cid] = _blank(CELLS[cid])
    (DATA / "products" / f"{key}.json").write_text(json.dumps(pr, indent=2))
    rws = load_evidence(key)
    for r_ in rws:
        if r_["cell_id"] not in keep:
            r_.update({"value": "", "source_doc": "", "source_section": "", "quote": "", "local_file": "",
                       "accession": "", "date_pulled": "", "extracted_by": "", "verified_by": "",
                       "status": "pending extraction"})
    with open(DATA / "evidence" / f"{key}_evidence.csv", "w", newline="") as fh:
        w_ = csv.DictWriter(fh, fieldnames=EVIDENCE_COLUMNS)
        w_.writeheader()
        w_.writerows(rws)


# retry at reduced context, an error that is not retried, the loop kept
reset_cells(KEY)
c2 = MockClient(answers, usage_by, default_usage,
                fail={"2.1": [context_error()], "2.4": [context_error(), context_error()],
                      "2.7": [RuntimeError("connection dropped")]})
out2 = run_extraction(c2, KEY, [doc], model="mock-model", today="2026-09-04")
b2 = {o.cid: o for o in out2}
_calls21 = [c for c in c2.calls if _cell_of(c) == "2.1"]
check("retry: a request-too-large error is retried once at half the context with the pages ranked for the cell, and the cell is extracted",
      b2["2.1"].status == "extracted-unverified" and b2["2.1"].attempts == 2 and b2["2.1"].pages_sent
      and len(_calls21) == 2 and _calls21[0]["messages"][0]["content"][0]["text"] != _calls21[1]["messages"][0]["content"][0]["text"]
      and load_product(KEY)["cells"]["2.1"]["status"] == "extracted-unverified", str(b2["2.1"]))
check("retry: a second failure leaves the cell pending with the error named, and the loop goes on",
      b2["2.4"].status == "pending extraction" and b2["2.4"].reason.startswith("extraction error: BadRequestError")
      and b2["2.4"].attempts == 2 and b2["3.1"].status.startswith("partial"), b2["2.4"].reason)
check("retry: any other error is recorded after one attempt, not retried, and the cell stays pending with nothing written",
      b2["2.7"].status == "pending extraction" and b2["2.7"].reason == "extraction error: RuntimeError: connection dropped"
      and b2["2.7"].attempts == 1 and load_product(KEY)["cells"]["2.7"]["status"] == "pending extraction"
      and json.loads(out2.report_path.read_text())["outcomes"][ex_cells.index("2.7")]["reason"].startswith("extraction error"))

# a write after every cell: an interrupt on cell 3.1 loses nothing before it
reset_cells(KEY)
c3 = MockClient(answers, usage_by, default_usage, fail={"3.1": [KeyboardInterrupt()]})
try:
    run_extraction(c3, KEY, [doc], model="mock-model", today="2026-09-04")
    crashed = False
except KeyboardInterrupt:
    crashed = True
p3 = load_product(KEY)
rep3 = json.loads((DATA / "ingest" / f"{KEY}_report.json").read_text())
ev3 = {r["cell_id"]: r for r in load_evidence(KEY)}
check("writes after every cell: an interrupt on cell 3.1 leaves 2.1, 2.4 and 2.7 on disk in the JSON and the ledger, and the report says how far the run got",
      crashed and p3["cells"]["2.1"]["status"] == "extracted-unverified" and p3["cells"]["2.7"]["status"] == "extracted-unverified"
      and ev3["2.1"]["status"] == "extracted-unverified" and ev3["2.4"]["accession"] == "0009999999-26-000001"
      and p3["cells"]["3.1"]["status"] == "pending extraction"
      and rep3["progress"] == {"done": ex_cells.index("3.1"), "total": len(ex_cells), "final": False}
      and rep3["cost"]["calls"] == len(c3.calls) - 1, str(rep3["progress"]))

# the wall-time budget with a clock the mock advances
reset_cells(KEY)
clk = FakeClock()
c4 = MockClient(answers, usage_by, default_usage, clock=clk, latency_s=10.0)
out4 = run_extraction(c4, KEY, [doc], model="mock-model", today="2026-09-04", time_budget_s=25.0, clock=clk)
_stopped4 = [o for o in out4 if o.reason.startswith("stopped: the wall-time budget of 25 s ran out after 3 calls")]
check("time budget: with 10 s per call and a 25 s budget the run makes three calls, leaves the rest pending with the reason, and the report says time",
      out4.cost.calls == 3 and out4.stopped["reason"] == "time" and out4.stopped["after_cells"] == 3
      and len(_stopped4) == len(ex_cells) - 3 - 1 and out4.cost.wall_seconds == 30.0
      and json.loads(out4.report_path.read_text())["stopped"]["reason"] == "time"
      and all(o.status == "pending extraction" and o.record is None for o in _stopped4),
      f"{out4.cost.calls} calls, {out4.stopped}, {len(_stopped4)} stopped")

# the cost budget: the estimate passes, the first measured call does not
reset_cells(KEY)
big = {**default_usage, "output_tokens": 50_000}    # $1.25 per call at the list
c5 = MockClient(answers, {}, big)
out5 = run_extraction(c5, KEY, [doc], model="mock-model", today="2026-09-04", budget_usd=1.0)
check("cost budget: the estimate is under the budget, the first call's reported cost is over it, so the run stops after one call and says budget",
      out5.estimate["usd"] < 1.0 and out5.cost.calls == 1 and out5.stopped["reason"] == "budget"
      and out5.stopped["after_cells"] == 1 and abs(out5.cost.usd - usd_of(big, PRICES)) < 1e-9
      and sum(1 for o in out5 if o.reason.startswith("stopped: the running cost estimate reached the budget of $1.00")) == len(ex_cells) - 2,
      f"estimate {out5.estimate['usd']}, calls {out5.cost.calls}, {out5.stopped}")
reset_cells(KEY)
c5b = MockClient(answers, usage_by, default_usage)
out5b = run_extraction(c5b, KEY, [doc], model="mock-model", today="2026-09-04", budget_usd=1.0, spent_before_usd=0.5)
check("cost budget: an estimate that, with what earlier runs spent, exceeds the budget is refused before any call, and the report says so",
      c5b.calls == [] and out5b.stopped["reason"] == "estimate over budget" and out5b.cost.calls == 0
      and all(o.reason.startswith("stopped: the cost estimate") for o in out5b if o.cid != "2.3")
      and json.loads(out5b.report_path.read_text())["spent_before_usd"] == 0.5, str(out5b.stopped))

# per-cell page retrieval under a small context cap
reset_cells(KEY)
c6 = MockClient(answers, usage_by, default_usage)
out6 = run_extraction(c6, KEY, [doc], only={"3.1", "6.4"}, model="mock-model", today="2026-09-04", context_tokens=60)
b6 = {o.cid: o for o in out6}
_blk = {_cell_of(c): c["messages"][0]["content"][0]["text"] for c in c6.calls}
check("retrieval: under a cap the corpus does not fit, each cell receives the pages its terms rank first, with the true page anchors",
      b6["3.1"].pages_sent == {doc.label: [2]} and b6["6.4"].pages_sent == {doc.label: [3]}
      and "quarterly repurchase offers" in _blk["3.1"] and "Form 1099-DIV" not in _blk["3.1"]
      and "[page 2]" in _blk["3.1"] and "(pages 2 of 3)" in _blk["3.1"]
      and "Form 1099-DIV" in _blk["6.4"] and "Managed Assets" not in _blk["6.4"]
      and not json.loads(out6.report_path.read_text())["context"]["whole_corpus"]
      and out6.estimate["whole_corpus"] is False,
      f"{b6['3.1'].pages_sent} {b6['6.4'].pages_sent}")
check("retrieval: the verify step still scans the whole document, so the lie in 3.1 is still caught on the pages that were not sent",
      b6["3.1"].status.startswith("partial - quote not located verbatim"))

# inline XBRL: the header block and every hidden block never reach the text
ix = filing_text(IXBRL_PATH, "IXBRL synthetic")
check("iXBRL: the ix:header block and every display:none block are stripped, the visible facts and inline tags stay, pages still split",
      len(ix.pages) == 2 and ix.page_of("management fee of 1.00% of net assets") == 1
      and ix.page_of("1,234,567 total assets") == 2 and ix.page_of("Visible after the hidden block") == 2
      and all(t not in ix.text for t in ("HIDDEN CONTEXT", "99.99%", "77.77%", "66.66%")), ix.text[:200])

# PDF: the splitter always, the binary when it is installed here
_pp = split_form_feeds(PDFTEXT_PATH.read_text())
check("PDF: pdftotext output splits into pages on the form feed, the empty tail dropped",
      len(_pp) == 3 and _pp[0].startswith("SYNTHETIC PDFTOTEXT OUTPUT") and "0.90%" in _pp[0] and _pp[2] == "Page three text.")


def minimal_pdf(text: str) -> bytes:
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out = b"%PDF-1.4\n"
    offsets = []
    for n, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


if shutil.which("pdftotext"):
    _pdf = SCRATCH / "synthetic.pdf"
    _pdf.write_bytes(minimal_pdf("Synthetic PDF page one. Fee 0.80% of net assets."))
    _pages = pdf_pages(_pdf)
    check("PDF: a one-page PDF reads through pdftotext into one page with its text",
          len(_pages) == 1 and "0.80%" in _pages[0], str(_pages)[:120])
else:
    _fake = raw_dir / "N-2_2026-01-01_exhibit.pdf"
    _fake.write_bytes(b"%PDF-1.4 not a document")
    try:
        pdf_pages(_fake)
        _missing = False
    except ReaderMissing as e:
        _missing = "pdftotext" in str(e) and "poppler-utils" in str(e)
    check("PDF: without pdftotext the reader refuses by name instead of reading the bytes as text", _missing)
    print("[SKIP] PDF through pdftotext: the binary is not installed here (CI installs poppler-utils)")
    _fake.unlink()

# exhibits: two documents on one accession, labels that name the document
row_ex = {**row, "primary_document": "ex99-1.htm", "local_path": f"data/raw/{KEY}/486BPOS_2026-05-01_ex99-1.htm"}
(raw_dir / "486BPOS_2026-05-01_ex99-1.htm").write_text(
    "<html><body><p>Exhibit text: an early repurchase fee of 2.00% applies within one year.</p></body></html>")
label_a, label_b = doc_label(row, [row, row_ex]), doc_label(row_ex, [row, row_ex])
check("exhibits: two documents on one accession get labels that name the document, both still parse through the citation resolver, a lone document keeps the old label",
      label_a.endswith(", document synthetic.htm)") and label_b.endswith(", document ex99-1.htm)")
      and references(label_a)[0]["accessions"] == ["0009999999-26-000001"] and references(label_b)[0]["form"] == "486BPOS"
      and references(label_b)[0]["filed"] == ["2026-05-01"] and doc_label(row) == doc.label, label_b)
fx = filing_from_row(row_ex, [row, row_ex])
check("manifest: a document built from its manifest row carries the row's accession, record path, document set and form, so the ledger never re-parses a label",
      fx is not None and fx.accession == "0009999999-26-000001" and fx.local_path == row_ex["local_path"]
      and fx.doc_set == "prospectus" and fx.form == "486BPOS" and fx.label == label_b and fx.kind == "html")
reset_cells(KEY)
c8 = MockClient({"2.7": CellExtraction(found=True, value="Early repurchase fee 2.00% within one year.",
                                       quote="an early repurchase fee of 2.00% applies within one year",
                                       source_doc=label_b, section="Exhibit", not_found_reason="")}, {}, default_usage)
out8 = run_extraction(c8, KEY, [filing_from_row(row, [row, row_ex]), fx], only={"2.7"}, model="mock-model", today="2026-09-04")
_ev8 = {r["cell_id"]: r for r in load_evidence(KEY)}
check("exhibits: a quote located in the exhibit writes the exhibit's own path and the shared accession into the ledger",
      out8[0].status == "extracted-unverified" and _ev8["2.7"]["local_file"] == row_ex["local_path"]
      and _ev8["2.7"]["accession"] == "0009999999-26-000001" and label_b in _ev8["2.7"]["source_doc"])

# promote and the fetcher as library calls under the data root, the network faked
KEY2, CIK2 = "zz_synth_two", "9999998"
(SCRATCH / "data" / "census").mkdir(exist_ok=True)
shutil.copy(BASE / "data" / "census" / "census.json", SCRATCH / "data" / "census" / "census.json")
import promote  # noqa: E402
import fetch_edgar  # noqa: E402
check("data root: promote, the fetcher and the census cache all bind under TARK_DATA_DIR, never the repository",
      promote.CENSUS == SCRATCH / "data" / "census" / "census.json" and fetch_edgar.MANIFEST == SCRATCH / "data" / "manifest.csv"
      and fetch_edgar.RAW_DIR == SCRATCH / "data" / "raw"
      and sys.modules["edgar_api"].RAW == SCRATCH / "data" / "census" / "raw")
_cen = json.loads(promote.CENSUS.read_text())
_cen["entities"][CIK2] = {"name": "Synthetic Two Fund", "wrapper_class": "interval_23c3", "detection_evidence": ["synthetic"],
                          "listed": {"value": False}, "exchanges": {"value": []}, "promotion": {"status": "none"},
                          "ncen": {"investment_company_type": {"ref": "0009999998-26-000009", "as_of": "2025-12-31"},
                                   "auditor": {"value": "Example Two LLP"}, "opinion_qualified": {"value": "N"},
                                   "nav_error_corrected": {"value": "N"}}}
promote.CENSUS.write_text(json.dumps(_cen))
_subs_fn = lambda cik: {"name": "Synthetic Two Fund", "formerNames": [{"name": "Old Synthetic Fund"}]}  # noqa: E731
sc = promote.scaffold(CIK2, KEY2, submissions_fn=_subs_fn)
check("scaffold: promote as a library writes the product JSON, the ledger and the census promotion under the data root, prefills the census cells and returns the worklist and identity",
      sc["product_path"] == DATA / "products" / f"{KEY2}.json" and sc["product_path"].exists()
      and (DATA / "evidence" / f"{KEY2}_evidence.csv").exists()
      and set(sc["prefilled"]) == {"4.5", "4.6", "1.10"} and "2.1" in sc["worklist"]
      and json.loads(promote.CENSUS.read_text())["entities"][CIK2]["promotion"] == {"status": "evaluated", "product_key": KEY2}
      and sc["identity"]["former_names"] == ["Old Synthetic Fund"] and not sc["name_drift"]
      and validate_product(KEY2) == [] and not (BASE / "data" / "products" / f"{KEY2}.json").exists(), str(sc)[:300])
try:
    promote.scaffold(CIK2, KEY2, submissions_fn=_subs_fn)
    refused2 = False
except promote.ScaffoldRefused as e:
    refused2 = "already promoted" in str(e)
try:
    promote.scaffold("1", "zz_nobody", submissions_fn=_subs_fn)
    refused3 = False
except promote.ScaffoldRefused as e:
    refused3 = "not in the census universe" in str(e)
check("scaffold: a promoted CIK and a CIK outside the census are refused by name, nothing written", refused2 and refused3
      and not (DATA / "products" / "zz_nobody.json").exists())

_regp = DATA / "registry.json"
_reg_before = _regp.read_text()
_reg = json.loads(_reg_before)
_reg["products"][KEY2] = {"filings": {"prospectus": ["486BPOS"], "annual_report": ["N-CSR"]},
                          "exhibits": {"N-CSR": ["ex99*"]}, "sources": {"filings": "synthetic", "exhibits": "synthetic"}}
_regp.write_text(json.dumps(_reg))
_SUBS = {"filings": {"recent": {"form": ["N-CSR", "486BPOS", "N-23C3A"], "filingDate": ["2026-06-01", "2026-05-01", "2026-04-01"],
                                "accessionNumber": ["0009999998-26-000002", "0009999998-26-000001", "0009999998-26-000003"],
                                "primaryDocument": ["ncsr.htm", "synthetic2.htm", "n23c3a.htm"]}}}
_INDEX = {"directory": {"item": [{"name": "ncsr.htm"}, {"name": "ex99-1.htm"}, {"name": "ex99-2.pdf"},
                                 {"name": "0009999998-26-000002-index.htm"}, {"name": "FilingSummary.xml"}, {"name": "index.json"}]}}
_gets = []


def _fake_get(url, as_json=False):
    _gets.append(url)
    if url.endswith("index.json"):
        return _INDEX
    name = url.rsplit("/", 1)[-1]
    if name == "synthetic2.htm":
        return FILING.encode()
    return f"<html><body><p>Synthetic document {name}: the Fund's total annual expenses are 2.34%.</p></body></html>".encode()


fetch_edgar.polite_get = _fake_get
fetch_edgar.load_submissions = lambda cik: _SUBS
rows2 = fetch_edgar.fetch_product(KEY2)
_man2 = [r for r in fetch_edgar.read_manifest() if r["product"] == KEY2]
check("fetch: the fetcher reads the registry's document sets and named exhibits, saves every document under the data root's raw folder, "
      "records one manifest row per document with a record-relative path, and returns the product's rows",
      len(rows2) == 4 and rows2 == _man2
      and {r["primary_document"] for r in rows2} == {"synthetic2.htm", "ncsr.htm", "ex99-1.htm", "ex99-2.pdf"}
      and all(r["local_path"].startswith(f"data/raw/{KEY2}/") and (SCRATCH / r["local_path"]).is_file() for r in rows2)
      and sum(1 for r in rows2 if r["accession"] == "0009999998-26-000002") == 3
      and all(r["url"].startswith("https://www.sec.gov/Archives/edgar/data/9999998/") for r in rows2)
      and not (BASE / "data" / "raw").exists() and any(u.endswith("/000999999826000002/index.json") for u in _gets)
      and not any(u.endswith("/000999999826000001/index.json") for u in _gets),
      f"{len(rows2)} rows, {[r['primary_document'] for r in rows2]}")
check("fetch: a second run is idempotent, no download repeats and no manifest row duplicates",
      (lambda n: fetch_edgar.fetch_product(KEY2) == rows2 and len(_gets) == n)(len(_gets)))
docs2, skipped2 = documents_for(KEY2)
check("documents: every held document reads to text with its accession and path, the PDF exhibit is skipped with the reason, the exhibit labels name the document",
      len(docs2) == 3 and len(skipped2) == 1 and "ex99-2.pdf" in skipped2[0]["document"]
      and ("pdftotext" in skipped2[0]["reason"])
      and sum(1 for d in docs2 if ", document " in d.label) == 2
      and all(d.accession and d.local_path.startswith(f"data/raw/{KEY2}/") for d in docs2), str(skipped2))

# run_product: the one call the worker makes
_lab2 = next(d.label for d in docs2 if d.form == "486BPOS")
answers2, usage2, default2 = canned_answers(_lab2)
c7 = MockClient(answers2, usage2, default2)
_pev = []
res = run_product(CIK2, SCRATCH, on_progress=_pev.append, model_client=c7, skip_fetch=True, today="2026-09-04")
_p2 = load_product(KEY2)
check("run_product: resolves the key from the CIK, reads the held filings, runs the loop, validates, and returns the result with the report on disk",
      res.product == KEY2 and res.cik == CIK2 and res.ok and len(res.outcomes) == len(ex_cells) and res.report_path.exists()
      and res.cost.calls == len(c7.calls) and "2.1" in res.written and res.validate_errors == []
      and len(res.documents) == 3 and len(res.skipped_documents) == 1 and _pev[0]["event"] == "run_start"
      and _pev[-1]["event"] == "run_end" and res.stopped is None
      and _p2["cells"]["2.1"]["status"] == "extracted-unverified" and _p2["cells"]["4.5"]["status"] == "structured"
      and res.summary().startswith(f"{KEY2}: 3 documents, "), res.summary())
_refusals = {}
for _name, _kw in (("unknown cik", dict(cik="1234", key=None)), ("no registry entry", dict(cik=CIK2, key="zz_nowhere")),
                   ("wrong workdir", dict(cik=CIK2, key=KEY2, workdir=SCRATCH / "elsewhere"))):
    try:
        run_product(_kw["cik"], _kw.get("workdir", SCRATCH), model_client=c7, key=_kw["key"], skip_fetch=True)
        _refusals[_name] = None
    except Refusal as e:
        _refusals[_name] = e
check("run_product: an unknown CIK, a key without a registry entry and a workdir that is not the bound data root are each refused with the reason and the hand commands, no call made",
      "no product key for CIK 1234" in str(_refusals["unknown cik"]) and any("promote.py" in c for c in _refusals["unknown cik"].commands)
      and "no entry for zz_nowhere" in str(_refusals["no registry entry"])
      and "data root bound at import" in str(_refusals["wrong workdir"]) and len(c7.calls) == res.cost.calls,
      str({k: str(v)[:60] for k, v in _refusals.items()}))
check("run_product: a second run keeps every extracted cell and sends nothing that is already evidence",
      (lambda r2: r2.ok and r2.cost.calls == len(c7.calls) - res.cost.calls
       and all(o.reason.startswith("kept: extracted") for o in r2.outcomes if o.cid in ("2.1", "2.4", "2.7")))(
          run_product(CIK2, SCRATCH, model_client=c7, skip_fetch=True, today="2026-09-04")))

# the dry-run copy and the library import from the repository root
_dd = SCRATCH / "dry"
dry_run_copy(DATA, _dd / "data", KEY2, CIK2)
check("dry run: the copy carries the record, the census and this product's raw filings only, so a run against it reaches extraction without the repository",
      (_dd / "data" / "raw" / KEY2).is_dir() and not (_dd / "data" / "raw" / KEY).exists()
      and (_dd / "data" / "census" / "census.json").exists() and (_dd / "data" / "products" / f"{KEY2}.json").exists()
      and (_dd / "data" / "manifest.csv").exists() and not (_dd / "data" / "memos").exists())
_imp = subprocess.run([sys.executable, "-c", "import src.ingest as m, src.mock_model as mm; print(m.run_product.__name__, m.DATA, mm.MockClient.__name__)"],
                      cwd=BASE, capture_output=True, text=True, env={**os.environ, "TARK_DATA_DIR": str(SCRATCH / "data")})
check("library: src.ingest and src.mock_model import from the repository root with TARK_DATA_DIR bound",
      _imp.returncode == 0 and "run_product" in _imp.stdout and str(SCRATCH / "data") in _imp.stdout, _imp.stderr[-300:])
_cli = subprocess.run([sys.executable, str(BASE / "src" / "ingest.py"), "1", "--key", "zz_nowhere", "--skip-fetch"],
                      cwd=BASE, capture_output=True, text=True, env={**os.environ, "TARK_DATA_DIR": str(SCRATCH / "data")})
check("command line: a refusal prints the reason and the hand commands and exits 1 before any client is built",
      _cli.returncode == 1 and "refused: data/registry.json has no entry for zz_nowhere" in _cli.stdout
      and "python src/promote.py 1 --key zz_nowhere" in _cli.stdout, _cli.stdout[-300:] + _cli.stderr[-300:])
_regp.write_text(_reg_before)
# the synthetic product back to the state of the first run, for the blocks below
reset_cells(KEY)
run_extraction(MockClient(answers, usage_by, default_usage), KEY, [doc], model="mock-model", today="2026-09-04")
check("state: the synthetic product is back to the first run's outcome for the later blocks",
      load_product(KEY)["cells"]["2.1"] == prod["cells"]["2.1"])

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
SYN_DOC = str(raw_dir / "486BPOS_2026-05-01_synthetic.htm")
row = verify_cell.apply(KEY, "2.1", "A. Person, committee chair", "2026-09-04", dry_run=True, document=SYN_DOC)
after = (DATA / "products" / f"{KEY}.json").read_text()
check("verify: the dry run shows the signed row and writes nothing",
      row["status"] == "verified - A. Person, committee chair, 2026-09-04"
      and row["verified_by"] == "A. Person, committee chair, 2026-09-04"
      and row["value"] == prod["cells"]["2.1"]["value"] and row["quote"] == prod["cells"]["2.1"]["quote"]
      and before == after and load_product(KEY)["cells"]["2.1"]["status"] == "extracted-unverified")
check("verify: no verified row exists in the scratch record after the dry runs",
      all(not str(c["status"]).startswith("verified") for c in load_product(KEY)["cells"].values()))

# ---------------- verify_cell (R2-P2-1): the quote against the document, the marker, the gate
from verify_cell import cited_documents, quote_in_text, verified_row_problems  # noqa: E402
import corrections_log  # noqa: E402
check("verify: the signer filter is word-bounded, Talbot and Cabot are people, a bot or a model is not",
      not verify_cell.NOT_A_PERSON.search("R. Talbot, trustee") and not verify_cell.NOT_A_PERSON.search("J. Cabot, CIO")
      and bool(verify_cell.NOT_A_PERSON.search("Claude Code")) and bool(verify_cell.NOT_A_PERSON.search("the bot")))
_txt = "the fund pays a management fee at an annual rate of 1.25% of the fund's average daily managed assets"
check("verify: an ellipsis quote is matched fragment by fragment, in order, never out of order",
      quote_in_text("management fee at an annual rate ... Managed Assets", _txt)[0]
      and not quote_in_text("Managed Assets ... management fee at an annual rate", _txt)[0]
      and quote_in_text("1.25% of the Fund\u2019s average", _txt)[0])
check("verify: the ledger's local file resolves the document, so the dry run needs no --document",
      [d["path"] for d in cited_documents(KEY, "2.1")] == [f"data/raw/{KEY}/486BPOS_2026-05-01_synthetic.htm"]
      and verify_cell.apply(KEY, "2.1", "A. Person, chair", "2026-09-04", dry_run=True)["status"].startswith("verified"))
_rows0 = load_evidence(KEY)
for _r in _rows0:
    if _r["cell_id"] == "2.1":
        _r["local_file"], _r["accession"] = "", ""
with open(DATA / "evidence" / f"{KEY}_evidence.csv", "w", newline="") as fh:
    _w = csv.DictWriter(fh, fieldnames=EVIDENCE_COLUMNS)
    _w.writeheader()
    _w.writerows(_rows0)
check("verify: a row that cites no document the record resolves is refused without --document or --fetch",
      cited_documents(KEY, "2.1") == [] and refused(KEY, "2.1", "A. Person, chair", "2026-09-04"))
(SCRATCH / "no_quote.htm").write_text("<html><body><p>A filing that never states the fee.</p></body></html>")
check("verify: a document that does not contain the quote refuses the signature",
      refused(KEY, "2.1", "A. Person, chair", "2026-09-04", document=str(SCRATCH / "no_quote.htm")))
check("verify: a document path that does not exist refuses the signature",
      refused(KEY, "2.1", "A. Person, chair", "2026-09-04", document=str(SCRATCH / "missing.htm")))
scratch_report = SCRATCH / "crosscheck_report.md"
shutil.copy(BASE / "docs" / "crosscheck_report.md", scratch_report)
real_report_before = (BASE / "docs" / "crosscheck_report.md").read_bytes()
signed = verify_cell.apply(KEY, "2.1", "R. Talbot, trustee", "2026-09-05", dry_run=False, document=SYN_DOC, report=scratch_report)
ev21 = next(r for r in load_evidence(KEY) if r["cell_id"] == "2.1")
allow_scratch = corrections_log.allow_rows(scratch_report.read_text())
marker_rows = [a for a in allow_scratch if a["product"] == KEY and a["cell"] == "2.1"
               and a["reason"].startswith("verified by R. Talbot, trustee on 2026-09-05")]
check("verify: a real signature writes the JSON and the CSV together and two allowlist rows with the marker reason",
      load_product(KEY)["cells"]["2.1"]["status"] == "verified - R. Talbot, trustee, 2026-09-05"
      and ev21["status"] == signed["status"] and ev21["verified_by"] == "R. Talbot, trustee, 2026-09-05"
      and sorted(a["column"] for a in marker_rows) == ["status", "verified_by"]
      and "quote found in" in marker_rows[0]["reason"])
check("verify: the repository's own report is untouched by the scratch signature",
      (BASE / "docs" / "crosscheck_report.md").read_bytes() == real_report_before)
check("verify: the gate accepts the signed scratch row",
      verified_row_problems([KEY], allow=allow_scratch) == [])
check("verify: the gate refuses the same row without the allowlist marker",
      any("allowlist" in p for p in verified_row_problems([KEY], allow=[])))
_p = load_product(KEY)
_p["cells"]["2.4"]["verified_by"] = "someone, 2026-09-05"
(DATA / "products" / f"{KEY}.json").write_text(json.dumps(_p, indent=1))
_rows = load_evidence(KEY)
for _r in _rows:
    if _r["cell_id"] == "2.4":
        _r["verified_by"] = "someone, 2026-09-05"
    if _r["cell_id"] == "2.7":
        _r["status"], _r["verified_by"] = "verified - ingest.py run, 2026-09-05", "ingest.py run, 2026-09-05"
with open(DATA / "evidence" / f"{KEY}_evidence.csv", "w", newline="") as fh:
    _w = csv.DictWriter(fh, fieldnames=EVIDENCE_COLUMNS)
    _w.writeheader()
    _w.writerows(_rows)
_probs = verified_row_problems([KEY], allow=allow_scratch)
check("verify: the gate refuses a signature without a verified status, a script signer, and a CSV the JSON does not carry",
      any("not verified" in p and "2.4" in p for p in _probs)
      and any("not a person" in p and "2.7" in p for p in _probs)
      and any("disagree" in p and "2.7" in p for p in _probs))

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
from tark_anon import forbidden_tokens  # noqa: E402
check("intake: a label naming a reference sponsor's token is refused, without the token being printed",
      intake_refused({**FORM, "display_label": f"plan of {forbidden_tokens()[0]} employees",
                      "anonymization_label": f"plan of {forbidden_tokens()[0]} employees"}))
_co = plan_intake.intake({**FORM, "display_label": "US consulting company 401(k) plan (~$50M, CO)",
                          "anonymization_label": "US consulting company 401(k) plan (~$50M, CO)"})
check("intake: a description with the words company and CO is a description, not a sponsor, and is accepted",
      _co.exists() and json.loads(_co.read_text())["display_label"].endswith("CO)"))
_co.unlink()
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
# R3-P2-10: the plan an advisor enters passes the surfaces gate on every shape
# the hook ships or writes: the bundle's plan object, the liquidity match, the
# decision memo and the committee packet. The scratch record gains the facts
# the match reads. A second intake carries the Schedule H totals so the
# computed proxy's copy of the provenance is covered too.
import test_surfaces  # noqa: E402
import tark_liquidity  # noqa: E402
import tark_memo  # noqa: E402
from tark_anon import docx_text, leaks  # noqa: E402
shutil.copytree(BASE / "data" / "facts", SCRATCH / "data" / "facts", dirs_exist_ok=True)
FORM_TOTALS = {**FORM, "display_label": "US regional clinic 403(b) plan (~$400M, OH)",
               "anonymization_label": "US regional clinic 403(b) plan (~$400M, OH)", "tot_expenses": 30_000_000}
out2 = plan_intake.intake(FORM_TOTALS)
newp2 = json.loads(out2.read_text())
_ship_bad = []
for np_ in (newp, newp2):
    # the filter build_site applies to a plan before it ships (identity never,
    # the internal rule sentence never, the maintainer's index of the file never)
    pub = {k: v for k, v in np_.items() if k not in ("identity_private", "anonymization_rule", "dictionary_cells")}
    test_surfaces.HITS["bundle"].clear()
    test_surfaces.walk_strings(pub, "plans", "plans", [0])
    if test_surfaces.HITS["bundle"] or leaks(json.dumps(pub)):
        _ship_bad.append(f"{np_['plan_key']}: {test_surfaces.HITS['bundle'][:2]}")
    if not (pub["source"]["note"].startswith("plan intake, ") and pub["source"]["pulled"]
            and pub["source"]["note"].endswith(pub["source"]["pulled"] + ", figures as the advisor supplied them")):
        _ship_bad.append(f"{np_['plan_key']}: provenance {pub['source']}")
check("intake: the shipped plan object carries no developer string, path or script name and no sponsor token, and its "
      "provenance reads 'plan intake, <date>'", not _ship_bad, "; ".join(_ship_bad[:2]))
check("intake: the computed filed outflow proxy copies the same display-safe provenance",
      newp2["schedule_h"]["filed_outflow_proxy"]["value"] == 8.11
      and newp2["schedule_h"]["filed_outflow_proxy"]["source"]["note"].startswith("plan intake, "))
(SCRATCH / "data" / "liquidity").mkdir(exist_ok=True)
_doc_bad = []
for np_ in (newp, newp2):
    m = tark_liquidity.run_match("hl_paf", np_["plan_key"])
    (SCRATCH / "data" / "liquidity" / f"{np_['plan_key']}__hl_paf_match.json").write_text(json.dumps(m))
    mtext = json.dumps(m)
    if test_surfaces.ANY.search(mtext) or leaks(mtext):
        _doc_bad.append(f"{np_['plan_key']} match: {test_surfaces.ANY.search(mtext)}")
    for builder, label in ((tark_memo.build_record, "record"),):
        path = builder("hl_paf", np_["plan_key"], out_dir=SCRATCH / "out")
        text = docx_text(path)
        test_surfaces.HITS["documents"].clear()
        test_surfaces.scan(text, "documents", f"docx {path.name}")
        if test_surfaces.HITS["documents"] or leaks(text):
            _doc_bad.append(f"{np_['plan_key']} {label}: {test_surfaces.HITS['documents'][:2]}")
        if np_["display_label"].lower() not in text.lower():
            _doc_bad.append(f"{np_['plan_key']} {label}: the plan label is missing")
check("intake: the liquidity match and the Investment Selection Record for an intake plan carry no forbidden "
      "string and no sponsor token, and name the plan by its anonymized label", not _doc_bad, "; ".join(_doc_bad[:3]))
check("intake: without the Schedule H totals the scenario has no verdict and says so, with them it has one",
      json.loads((SCRATCH / "data" / "liquidity" / f"{newp['plan_key']}__hl_paf_match.json").read_text())["scenario_verdict"] is None
      and json.loads((SCRATCH / "data" / "liquidity" / f"{newp2['plan_key']}__hl_paf_match.json").read_text())["scenario_verdict"] is not None)
out2.unlink()
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

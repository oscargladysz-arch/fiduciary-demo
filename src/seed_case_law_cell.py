"""
Cell 5.7 (case-law tracker): one partial row, sixteen products
==============================================================
The tracker is cross-product, so every product carries the same row. The
row states only what the docket listing and web-search snippets support and
says so in its status. It is never `extracted`: the source documents were
not fetched in this build (supremecourt.gov, congress.gov and scotusblog.com
are blocked from the build container). A person with access replaces the
snippet quote with the document quote and the status with extracted.

Run: python src/seed_case_law_cell.py
Refuses to overwrite a 5.7 row whose status kind is extracted or verified.
"""
from __future__ import annotations

import csv
import json

from tark_data import (CELLS, DATA, EVIDENCE_COLUMNS, load_evidence, load_product,
                       product_keys, status_kind)

ACCESSED = "2026-09-04"
VALUE = (
    "Anderson v. Intel Corp. Investment Policy Committee, No. 25-498 (U.S.). Certiorari "
    "granted 2026-01-16 per the Supreme Court docket listing. Question presented, per the "
    "docket as relayed in search-result snippets: whether, for claims predicated on fund "
    "underperformance, pleading that an ERISA fiduciary breached the duty of prudence "
    "requires alleging a meaningful benchmark. The Ninth Circuit had required plaintiffs to "
    "identify a comparable alternative giving a sound basis for comparison, a meaningful "
    "benchmark. Argument is listed for the October 2026 term and had not been held as of "
    f"{ACCESSED}. No holding exists yet, and this cell draws no consequence for the "
    "evaluation. Status partial: assembled from the docket listing and search snippets, not "
    "from the source documents, which this build could not fetch."
)
SOURCE = (
    "Supreme Court docket 25-498, "
    "https://www.supremecourt.gov/docket/docketfiles/html/public/25-498.html (grant date). "
    "SCOTUSblog case page, "
    "https://www.scotusblog.com/cases/anderson-v-intel-corp-investment-policy-comm/ and CRS "
    "Legal Sidebar LSB11396, https://www.congress.gov/crs-product/LSB11396 (question "
    f"presented, argument term). Accessed {ACCESSED} through web-search snippets only."
)
SECTION = "docket listing and search-result snippets (question presented, argument scheduling)"
QUOTE = (
    "search snippet, not the source document: \"whether, for claims predicated on fund "
    "underperformance, pleading that an ERISA fiduciary failed to use the requisite 'care, "
    "skill, prudence, or diligence' under the circumstances and thus breached ERISA's duty of "
    "prudence when investing plan assets requires alleging a 'meaningful benchmark'\" and "
    "\"The case is scheduled for argument before the Supreme Court of the United States during "
    "the court's October 2026-2027 term.\""
)
STATUS = ("partial - search snippets and docket listing only, source documents not fetched "
          "in this build")
EXTRACTED_BY = f"Claude Code (WebSearch snippet, {ACCESSED})"


def main() -> None:
    for key in product_keys():
        product = load_product(key)
        cell = product["cells"]["5.7"]
        if status_kind(str(cell.get("status", ""))) in ("extracted", "verified"):
            raise SystemExit(f"refusing to overwrite {key} 5.7: status is evidence")
        product["cells"]["5.7"] = {
            "element": CELLS["5.7"], "value": VALUE, "status": STATUS, "source": SOURCE,
            "section": SECTION, "quote": QUOTE, "extracted_by": EXTRACTED_BY, "verified_by": "",
        }
        rows = load_evidence(key)
        for r in rows:
            if r["cell_id"] == "5.7":
                r.update({"element": CELLS["5.7"], "value": VALUE, "source_doc": SOURCE,
                          "source_section": SECTION, "quote": QUOTE, "local_file": "",
                          "date_pulled": ACCESSED, "extracted_by": EXTRACTED_BY,
                          "verified_by": "", "status": STATUS})
        (DATA / "products" / f"{key}.json").write_text(
            json.dumps(product, indent=2, ensure_ascii=False) + "\n")
        with open(DATA / "evidence" / f"{key}_evidence.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=EVIDENCE_COLUMNS)
            w.writeheader()
            w.writerows(rows)
        print(f"{key:<18} 5.7 written (partial)")


if __name__ == "__main__":
    main()

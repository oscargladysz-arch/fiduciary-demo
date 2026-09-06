"""
Source-document checks: the authority text path and the case-law path, offline
==============================================================================
Runs the authority writer and parser on a synthetic Federal Register XML
fixture (src/fixtures/authority_fr_synthetic.xml) and asserts a byte-for-byte
round trip of every paragraph, the nested roman items included. Runs the
one-off timing strip and the case-law fetcher (fake network, synthetic
documents) against a scratch copy of the record, applies cell 5.7 from the
saved documents, and asserts every refusal. Nothing here touches the
repository's data, and no fixture text can reach a build.

    python src/test_sources.py            standalone, on its own scratch copy
It also runs inside python src/test_ingest.py (the hook's ingest gate), so
the hook's gate count is unchanged while the checks are enforced.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
FIXTURES = BASE / "src" / "fixtures"
BAD_COPY = re.compile("[—;]")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run(check) -> None:
    """Every check through the caller's check(name, cond, detail)."""
    sys.path.insert(0, str(BASE / "src"))
    import fetch_authority as fa  # noqa: E402
    import fetch_caselaw as fc  # noqa: E402
    import strip_caselaw_timing as strip  # noqa: E402
    from tark_data import (AUTHORITY_FILE, AUTHORITY_MANIFEST, AUTHORITY_MANIFEST_COLUMNS,  # noqa: E402
                           DATA, NOT_FETCHED_SENTENCE, authority, load_evidence, load_product,
                           parse_authority, product_keys, status_kind, validate_product)

    # ------------------------------------------------ A. the authority text path
    xml = (FIXTURES / "authority_fr_synthetic.xml").read_bytes()
    paras = fa.select(fa.section_paragraphs(xml), fa.PARAS)
    counts = {k: len(v) for k, v in paras.items()}
    check("authority: the fixture yields paragraphs (g) to (l) with every sub-paragraph "
          "(9, 5, 3, 4, 9, 3), decoy sections and the preamble excluded",
          counts == {"g": 9, "h": 5, "i": 3, "j": 4, "k": 9, "l": 3}
          and not any("Decoy" in p or "preamble" in p.lower() for v in paras.values() for p in v),
          str(counts))
    check("authority: nested (i) and (ii) stay inside (g), (h) and (j), the (v) item stays inside (k), "
          "and the real (i) opens after (h)",
          paras["g"][3].startswith("(i) Fixture roman item (g)(2)(i)")
          and paras["h"][3].startswith("(i) Fixture roman item (h)(2)(i)")
          and paras["h"][4].startswith("(ii) Fixture roman item (h)(2)(ii)")
          and paras["i"][0].startswith("(i) Fixture heading (i).")
          and paras["j"][2].startswith("(i) Fixture roman item (j)(1)(i)")
          and paras["k"][6].startswith("(v) Fixture roman item (k)(1)(v)"))
    check("authority: a paragraph wrapped over three lines in the XML is one line, whitespace collapsed",
          all("\n" not in p and "  " not in p for v in paras.values() for p in v)
          and paras["g"][0].endswith("so the writer must join it into one line."))
    check("authority: italic markup is flattened and the section symbol and curly quotes survive",
          paras["g"][0].startswith("(g) Fixture heading (g). This synthetic")
          and "§ 0.0" in paras["g"][1] and "“curly quotes”" in paras["g"][1])

    out_dir = Path(tempfile.mkdtemp(prefix="tark_authority_out_"))   # outside the repository
    meta = {"citation": fa.CITATION, "publication_date": "2026-03-31",
            "regulation_id_numbers": [fa.RIN], "docket_ids": ["EBSA-2026-0166"],
            "full_text_xml_url": "file://fixture", "html_url": ""}
    try:
        path, row = fa.write(out_dir, out_dir / "raw", meta, xml, paras, "2026-09-06T00:00:00+00:00")
        wrote_ok = True
    except Exception as e:  # noqa: BLE001
        path, row, wrote_ok = None, {}, False
        print("   writer raised:", repr(e))
    check("authority: --out outside the repository writes without crashing and records an absolute path",
          wrote_ok and path.exists() and Path(row["local_path"]).is_absolute()
          and (out_dir / "raw" / f"{fa.DOC}.xml").read_bytes() == xml)
    if wrote_ok:
        import csv
        with (out_dir / AUTHORITY_MANIFEST).open(newline="") as fh:
            rdr = csv.DictReader(fh)
            mrows = list(rdr)
            cols = rdr.fieldnames
        check("authority: the manifest row has the authority columns, the content hash of the file "
              "as written, the source hash and the paragraph count",
              cols == AUTHORITY_MANIFEST_COLUMNS and len(mrows) == 1
              and mrows[0]["content_sha256"] == _sha(path)
              and mrows[0]["source_sha256"] == hashlib.sha256(xml).hexdigest()
              and mrows[0]["paragraph_count"] == "33" and mrows[0]["section"] == fa.SECTION)
        parsed = parse_authority(path.read_text(encoding="utf-8"))
        total_in = sum(len(p) for v in paras.values() for p in v)
        total_out = sum(len(p) for v in parsed.values() for p in v)
        check(f"authority: round trip is byte for byte, every paragraph of every letter "
              f"({total_out} of {total_in} characters, 33 paragraphs)",
              parsed == paras and total_out == total_in and list(parsed) == fa.PARAS)
        check("authority: the round trip carries the nested (i) items, not only the labels",
              parsed["g"][3] == paras["g"][3] and parsed["h"][3] == paras["h"][3]
              and parsed["k"][6] == paras["k"][6] and len(parsed["g"][3]) > 60)
        # the same fixture through the command line, twice: one manifest row
        cli = subprocess.run([sys.executable, str(BASE / "src" / "fetch_authority.py"),
                              "--xml", str(FIXTURES / "authority_fr_synthetic.xml"), "--out", str(out_dir)],
                             capture_output=True, text=True)
        cli2 = subprocess.run([sys.executable, str(BASE / "src" / "fetch_authority.py"),
                               "--xml", str(FIXTURES / "authority_fr_synthetic.xml"), "--out", str(out_dir)],
                              capture_output=True, text=True)
        with (out_dir / AUTHORITY_MANIFEST).open(newline="") as fh:
            mrows2 = list(csv.DictReader(fh))
        check("authority: the command line run on the fixture exits 0 twice and keeps one manifest row",
              cli.returncode == 0 and cli2.returncode == 0 and len(mrows2) == 1
              and "33 paragraphs" in cli.stdout, cli.stderr[-300:])
        noout = subprocess.run([sys.executable, str(BASE / "src" / "fetch_authority.py"),
                                "--xml", str(FIXTURES / "authority_fr_synthetic.xml")],
                               capture_output=True, text=True)
        check("authority: --xml without --out is refused, a fixture run never writes into the record",
              noout.returncode != 0 and not (DATA / "authority").exists())
    legacy = "# head\n\n## (g)\n\n> (g) first para,\nwrapped on a second line.\n>\n> (1) second.\n\n## (h)\n\n> (h) third.\n"
    check("authority: an older file with a wrapped paragraph still reads whole",
          parse_authority(legacy) == {"g": ["(g) first para, wrapped on a second line.", "(1) second."],
                                      "h": ["(h) third."]})

    # the build admits the text only with the file AND its hashed manifest row
    if wrote_ok:
        adir = DATA / "authority"
        adir.mkdir(parents=True, exist_ok=True)
        target = adir / AUTHORITY_FILE
        shutil.copy(path, target)
        a1 = authority()
        shutil.copy(out_dir / AUTHORITY_MANIFEST, adir / AUTHORITY_MANIFEST)
        a2 = authority()
        target.write_text(target.read_text(encoding="utf-8") + "x\n", encoding="utf-8")
        a3 = authority()
        check("authority: the file alone is not fetched, the file with its hashed row is fetched "
              "with six letters, and a changed file falls back to not fetched",
              a1["status"] == "not fetched" and a1["note"] == NOT_FETCHED_SENTENCE and a1["paragraphs"] is None
              and a2["status"] == "fetched" and a2["paragraphs"] == paras and a2["sha256"] == _sha(path)
              and a3["status"] == "not fetched" and a3["note"] == NOT_FETCHED_SENTENCE)
        shutil.rmtree(adir, ignore_errors=True)
        check("authority: the fixture text is gone from the scratch record after the check",
              not adir.exists() and authority()["status"] == "not fetched")
    shutil.rmtree(out_dir, ignore_errors=True)

    # ---------------------------------------- B. the one-off timing strip (scratch)
    # the record no longer carries the sentence (the strip ran in R2-P1-14),
    # so the scratch copy gets a SYNTHETIC one, labeled as such, appended to
    # every partial 5.7 value and quoted in its quote column, and the strip
    # must remove exactly that
    keys = [k for k in product_keys() if status_kind(load_product(k)["cells"]["5.7"].get("status", "")) == "partial"]
    _synthetic = "Argument is listed for a synthetic test term and this sentence is a test fixture."
    import csv as _csv
    from tark_data import EVIDENCE_COLUMNS as _COLS
    for k in keys:
        pj = DATA / "products" / f"{k}.json"
        doc = json.loads(pj.read_text())
        c = doc["cells"]["5.7"]
        # appended at the end: the value's own first sentence carries an
        # abbreviation ("v."), so a split on ". " would land inside it
        c["value"] = c["value"].rstrip() + " " + _synthetic
        c["quote"] = c["quote"].rstrip() + ' and "synthetic fixture text that speaks of an argument"'
        pj.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
        evp = DATA / "evidence" / f"{k}_evidence.csv"
        rows = list(_csv.DictReader(evp.open(newline="")))
        for r in rows:
            if r["cell_id"] == "5.7":
                r["value"], r["quote"] = c["value"], c["quote"]
        with evp.open("w", newline="") as fh:
            w = _csv.DictWriter(fh, fieldnames=_COLS)
            w.writeheader()
            w.writerows(rows)
    before = {k: (DATA / "products" / f"{k}.json").read_bytes() for k in keys}
    dry = strip.run(write=False)
    check(f"strip: the dry run names every partial 5.7 ({len(keys)} products) and writes nothing",
          [r["key"] for r in dry] == keys and all((DATA / "products" / f"{k}.json").read_bytes() == before[k] for k in keys))
    done = strip.run(write=True)
    ok_all = bool(done)
    for rec in done:
        k = rec["key"]
        p = load_product(k)["cells"]["5.7"]
        ev = {r["cell_id"]: r for r in load_evidence(k)}["5.7"]
        removed = rec["removed_sentence"]
        ok = (status_kind(p["status"]) == "partial" and p["status"] == ev["status"]
              and p["value"] == rec["new_value"] == ev["value"]
              and not re.search(r"\bargument\b", p["value"], re.I)
              and re.search(r"\bargument\b", removed, re.I) and re.search(r"\bterm\b", removed, re.I)
              and rec["old_value"] == rec["old_value"][:rec["old_value"].index(removed)] + removed
              + rec["old_value"][rec["old_value"].index(removed) + len(removed):]
              and rec["new_value"] == (rec["old_value"].replace(removed, "", 1)).rstrip()
              and rec["new_value"][:40] == rec["old_value"][:40]
              and p["quote"] == ev["quote"] and not re.search(r"\bargument\b", p["quote"], re.I)
              and p["quote"].count('"') == 2 and p["source"] == ev["source_doc"]
              and p["extracted_by"] == ev["extracted_by"] and ev["verified_by"] == "")
        if not ok:
            print("   strip mismatch:", k)
        ok_all = ok_all and ok
    check("strip: every product keeps status partial, loses exactly the one sentence that speaks of an "
          "argument and a term and the matching quote snippet, keeps the rest byte for byte, "
          "and the JSON and the CSV agree", ok_all)
    check("strip: a second run finds nothing to strip", strip.run(write=False) == [])
    check("strip: the scratch record still validates", all(validate_product(k) == [] for k in keys))

    # ---------------------------------------------- C. the case-law path (scratch)
    docket_url = "https://example.invalid/docket/00-0000.html"
    qp_url = "https://example.invalid/qp/00-00000qp.txt"
    opinion_url = "https://example.invalid/opinions/00-00000.txt"
    docket_html = (FIXTURES / "caselaw_docket_synthetic.html").read_bytes()
    pages = {docket_url: docket_html,
             qp_url: (FIXTURES / "caselaw_qp_synthetic.txt").read_bytes(),
             opinion_url: (FIXTURES / "caselaw_opinion_synthetic.txt").read_bytes(),
             "https://example.invalid/opinions/wrong.txt": b"A text that names no case number at all."}

    def fake_get(url: str) -> bytes:
        if url not in pages:
            raise AssertionError(f"unexpected fetch {url}")
        return pages[url]

    def refused(fn, *a, **kw) -> str | None:
        try:
            fn(*a, **kw)
            return None
        except SystemExit as e:
            return str(e)

    msg = refused(fc.fetch, "99-9999", docket_url, opinion_url, None, getter=fake_get)
    check("caselaw: a page that does not name the docket number saves nothing",
          msg and "does not name docket" in msg and not fc.manifest_path().exists()
          and not list(fc.raw_dir().glob("*")) if fc.raw_dir().exists() else bool(msg))
    check("caselaw: apply refuses while the manifest is absent",
          (refused(fc.apply, False) or "").startswith("the case-law manifest is absent"))
    rows = fc.fetch("00-0000", docket_url, "https://example.invalid/opinions/wrong.txt", None,
                    getter=fake_get, fetched_at="2001-05-01T00:00:00+00:00")
    check("caselaw: an opinion that lacks the lower-court case number the docket page states is not recorded",
          [r["document"] for r in rows] == [fc.DOC_DOCKET, fc.DOC_QP]
          and not (fc.raw_dir() / "ca9_opinion.txt").exists())
    rows = fc.fetch("00-0000", docket_url, opinion_url, None, getter=fake_get,
                    fetched_at="2001-05-01T00:00:00+00:00")
    import csv
    with fc.manifest_path().open(newline="") as fh:
        rdr = csv.DictReader(fh)
        mrows = list(rdr)
        mcols = rdr.fieldnames
    check("caselaw: the fetch saves the docket page, the questions presented document found through the "
          "page's own /qp/ link, and the opinion, one manifest row each with URL, fetch time and hashes",
          mcols == fc.MANIFEST_COLUMNS and [r["document"] for r in mrows] == [fc.DOC_DOCKET, fc.DOC_QP, fc.DOC_OPINION]
          and {r["url"] for r in mrows} == {docket_url, qp_url, opinion_url}
          and all(r["fetched_at_utc"] == "2001-05-01T00:00:00+00:00" for r in mrows)
          and all(_sha(fc.resolve_local(r["local_path"])) == r["sha256"]
                  and _sha(fc.resolve_local(r["text_path"])) == r["text_sha256"] for r in mrows))
    check("caselaw: the manifest note says the reporter citation comes from the brief, not the document",
          "per the task brief, not read from the document" in mrows[2]["note"])

    fields = fc.docket_fields(fc.html_text(docket_html))
    check("caselaw: the docket page parser reads the title block and every dated row, scripts dropped",
          fields["title"].startswith("Synthetic Petitioner") and fields["docketed"] == "January 2, 2001"
          and fields["case_numbers"] == "(00-00000)" and fields["decision_date"] == "June 1, 2000"
          and len(fields["entries"]) == 6 and fields["entries"][4] == ("Mar 19 2001", "Petition GRANTED.")
          and "ignored by the text extractor" not in fc.html_text(docket_html))

    before = {k: (DATA / "products" / f"{k}.json").read_bytes() for k in product_keys()}
    # the ingest gate's scratch carries a synthetic product it deliberately
    # leaves invalid, so only the products that validated before must after
    clean_before = {k for k in product_keys() if validate_product(k) == []}
    would = fc.apply(write=False)
    check("caselaw: the apply dry run names every product and writes nothing",
          would == product_keys()
          and all((DATA / "products" / f"{k}.json").read_bytes() == before[k] for k in product_keys()))
    wrote = fc.apply(write=True)
    cell = fc.new_cell()
    qp = cell["quote"]
    ok_all = wrote == product_keys()
    for k in product_keys():
        p = load_product(k)["cells"]["5.7"]
        ev = {r["cell_id"]: r for r in load_evidence(k)}["5.7"]
        ok = (p["status"] == "extracted-unverified" == ev["status"] and p["value"] == ev["value"] == cell["value"]
              and p["quote"] == ev["quote"] == qp and p["source"] == ev["source_doc"]
              and ev["verified_by"] == "" and p["verified_by"] == "" and ev["accession"] == ""
              and ev["local_file"] == mrows[0]["local_path"] and ev["date_pulled"] == "2001-05-01"
              and (k not in clean_before or validate_product(k) == []))
        if not ok:
            print("   apply mismatch:", k, validate_product(k)[:3])
        ok_all = ok_all and ok
    check("caselaw: apply writes the same extracted-unverified row into every product JSON and CSV, "
          "nothing verified, and the scratch record validates", ok_all)
    v = cell["value"]
    check("caselaw: the question presented is quoted verbatim with its wrapping collapsed, and is the quote column",
          qp.startswith("Whether this synthetic fixture question") and qp.endswith("single spaces?")
          and "\n" not in qp and f'"{qp}"' in v)
    check("caselaw: the cell states the title, the docketed date, the petition and grant entries with their "
          "dates, the entry count and the lower-court block, all as the page states them",
          v.startswith("Synthetic Petitioner, et al., Petitioners v. Synthetic Respondent Committee, et al., No. 00-0000, "
                       "Supreme Court of the United States, as the docket page states.")
          and "Docketed January 2, 2001 per the docket page." in v
          and "Jan 02 2001, Petition for a writ of certiorari filed. (Response due February 5, 2001)" in v
          and "Mar 19 2001, Petition GRANTED." in v
          and "lists 6 entries from Jan 02 2001 to Apr 30 2001" in v
          and "Synthetic Court of Appeals for the Zeroth Circuit, case number (00-00000), decision date June 1, 2000. "
              "The opinion is held in the record with its content hash." in v
          and v.endswith("This cell draws no consequence for the evaluation."))
    check("caselaw: no argument sentence when the docket page lists no argument entry, and the absence of "
          "a decision entry is stated as of the fetch date",
          not re.search(r"\bargu", v, re.I)
          and "As of the fetch date 2001-05-01 the docket page lists no entry recording a decision of the Court." in v)
    check("caselaw: no em dash, no semicolon, no repository path and no script name in any written field",
          all(not BAD_COPY.search(cell[f]) and "data/" not in cell[f] and ".py" not in cell[f]
              for f in ("value", "source", "section", "quote", "extracted_by")))
    check("caselaw: the source names both documents with their URLs and fetch dates and the manifest",
          docket_url in cell["source"] and qp_url in cell["source"] and opinion_url in cell["source"]
          and "fetched 2001-05-01" in cell["source"] and "case-law manifest" in cell["source"])
    check("caselaw: a second apply changes nothing", fc.apply(write=False) == [])

    # the argument and decision sentences appear only when the page lists such entries
    with_arg = docket_html.replace(
        b"</table>\n</body>",
        b"  <tr><td>Oct 01 2001</td><td>SET FOR ARGUMENT on Monday, November 5, 2001.</td></tr>\n"
        b"  <tr><td>Nov 05 2001</td><td>Argued. For petitioners: a fixture advocate.</td></tr>\n"
        b"  <tr><td>Mar 03 2002</td><td>Adjudged to be AFFIRMED. Fixture entry.</td></tr>\n</table>\n</body>")
    pages[docket_url] = with_arg
    fc.fetch("00-0000", docket_url, opinion_url, None, getter=fake_get, fetched_at="2002-04-01T00:00:00+00:00")
    v2 = fc.new_cell()["value"]
    check("caselaw: an argument entry the page lists is stated with its date, and a decision entry replaces "
          "the no-decision sentence",
          "Argument entries the docket page states: Oct 01 2001, SET FOR ARGUMENT on Monday, November 5, 2001. "
          "Nov 05 2001, Argued. For petitioners: a fixture advocate." in v2
          and "Mar 03 2002, Adjudged to be AFFIRMED. Fixture entry." in v2
          and "lists no entry recording a decision" not in v2 and "lists 9 entries" in v2)
    pages[docket_url] = docket_html
    fc.fetch("00-0000", docket_url, opinion_url, None, getter=fake_get, fetched_at="2001-05-01T00:00:00+00:00")

    # refusals: an absent file, a changed file, a verified row
    qp_text_path = fc.resolve_local(mrows[1]["text_path"])
    saved = qp_text_path.read_bytes()
    qp_text_path.unlink()
    m1 = refused(fc.apply, False) or ""
    qp_text_path.write_bytes(saved + b"\n")
    m2 = refused(fc.apply, False) or ""
    qp_text_path.write_bytes(saved)
    check("caselaw: apply refuses when a listed file is absent or no longer matches its manifest hash",
          "is absent" in m1 and "does not match its manifest hash" in m2 and fc.apply(write=False) == [])
    k0 = product_keys()[0]
    prod0 = load_product(k0)
    kept = json.dumps(prod0, indent=2, ensure_ascii=False) + "\n"
    prod0["cells"]["5.7"]["status"] = "verified - a person, 2001-06-01"
    (DATA / "products" / f"{k0}.json").write_text(json.dumps(prod0, indent=2, ensure_ascii=False) + "\n")
    m3 = refused(fc.apply, True) or ""
    (DATA / "products" / f"{k0}.json").write_text(kept)
    check("caselaw: apply refuses to overwrite a verified row", "it is verified" in m3)
    # a page without a questions presented link: the fetch says so and apply refuses
    no_link = docket_html.replace(b'<a href="/qp/00-00000qp.txt">Questions Presented</a>', b"")
    pages[docket_url] = no_link
    shutil.rmtree(fc.manifest_path().parent, ignore_errors=True)
    rows = fc.fetch("00-0000", docket_url, None, None, getter=fake_get, fetched_at="2001-05-01T00:00:00+00:00")
    m4 = refused(fc.apply, False) or ""
    check("caselaw: without a questions presented link the fetch records the docket page only and apply refuses",
          [r["document"] for r in rows] == [fc.DOC_DOCKET] and "no manifest row for" in m4)
    check("caselaw: no fixture sentence names a real party, court or date",
          all("Synthetic" in fields[f] or f == "docketed" for f in ("title", "lower_ct")))


def main() -> int:
    scratch = Path(tempfile.mkdtemp(prefix="tark_sources_"))
    os.environ["TARK_DATA_DIR"] = str(scratch / "data")
    (scratch / "data").mkdir()
    for name in ("products", "evidence"):
        shutil.copytree(BASE / "data" / name, scratch / "data" / name)
    for name in ("manifest.csv", "as_of.json", "registry.json"):
        shutil.copy(BASE / "data" / name, scratch / "data" / name)
    fails: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" : {detail}" if detail and not cond else ""))
        if not cond:
            fails.append(name)

    run(check)
    shutil.rmtree(scratch, ignore_errors=True)
    print(f"\n{len(fails)} failure(s)." if fails else "\nAll source-document checks pass.")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

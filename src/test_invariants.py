"""
Invariants of the record and its surfaces (grows with every phase)
==================================================================
Each check is a property the audit found violated or a rule the brief makes
non-negotiable. Run: python src/test_invariants.py   (exit 0 = all hold)
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tark_data import (BASE, DATA, coverage_summary, coverage_totals,  # noqa: E402
                       load_evidence, product_keys)

FAILS: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}{(' : ' + extra) if extra and not cond else ''}")
    if not cond:
        FAILS.append(name)


# 1. verified is human-only: this remediation never sets it
verified_rows = 0
signed = 0
for key in product_keys():
    for r in load_evidence(key):
        if r["status"].startswith("verified"):
            verified_rows += 1
        if r["verified_by"].strip():
            signed += 1
check("no cell is verified and no verified_by is signed in this pull request",
      verified_rows == 0 and signed == 0, f"verified={verified_rows} signed={signed}")

# 2. one coverage formula: build_site and app.py call tark_data.coverage_summary
bs = (BASE / "src" / "build_site.py").read_text()
ap = (BASE / "app.py").read_text()
check("build_site.evidence_counts delegates to coverage_summary",
      "return coverage_summary(key)" in bs)
check("app.py uses coverage_summary and has no local coverage formula",
      "coverage_summary(" in ap and "def coverage_pct" not in ap)
tot = coverage_totals()["counts"]
# P1-23 moved 16 cells 5.6 from n/a to computed and 16 cells 5.7 from n/a to
# partial (32 fewer n/a). R2-P1-A added cell 1.12 (the peer comparison) to
# all 16 products as a computed cell owned by the writer: 161 to 177.
# R2-P1-13 owns cell 3.7 for all 16: its ten documented n/a rows (plan-side,
# per plan) became the writer's computed sentence: 177 to 187, n/a 205 to
# 195. The pin is a snapshot of the record, not a target.
check("record totals per kind (recomputed): extracted 406, n/a 195, computed 187, "
      "partial 75, fetched 16, structured 1, verified 0, pending 0",
      (tot["extracted"], tot["na"], tot["computed"], tot["partial"], tot["fetched"],
       tot["structured"], tot["verified"], tot["pending"]) == (406, 195, 187, 75, 16, 1, 0, 0),
      str(tot))
c = coverage_summary("cion_ares")
check("cion_ares: structured counts as resolved (structured 1, pending 0)",
      c["structured"] == 1 and c["pending"] == 0)

# 3. no product-count "six" copy on any surface or in the record
SIX = re.compile(r"six (real )?products|six-product|six rows|six hundred|six wrappers", re.I)
hits = []
for pattern in ("site/js/*.js", "site/index.html", "app.py", "data/products/*.json",
                "data/evidence/*.csv", "data/analytics/*.json", "data/roster_decisions.md"):
    for f in BASE.glob(pattern):
        for i, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
            if SIX.search(line):
                hits.append(f"{f.relative_to(BASE)}:{i}")
check("no product-count 'six' string in site/, app.py or data/", not hits, "; ".join(hits[:5]))

# 4. every non-raw data/ path a cell cites exists (raw paths are checked
#    against the manifest by the validator, as warnings until P2-10)
from tark_data import data_paths_in, load_product  # noqa: E402
dangling = []
for key in product_keys():
    for cid, cell in load_product(key)["cells"].items():
        for field in ("value", "source", "section", "quote"):
            for pth in data_paths_in(str(cell.get(field) or "")):
                if not pth.startswith("data/raw/") and not (BASE / pth).exists():
                    dangling.append(f"{key}:{cid}:{pth}")
check("every non-raw data/ path cited by a cell exists", not dangling, "; ".join(dangling[:5]))

# 5. the frozen taxonomy file is gone (the build computes it)
check("data/analytics/taxonomy.json no longer exists",
      not (DATA / "analytics" / "taxonomy.json").exists())

# accessions (P1-D prep, tightened in R2-P0-1, rule 15): a resolved reference
# points at a manifest row of the same product and form with the manifest's
# own URL, that URL is built from the product's CIK and that accession, no
# reference resolves from a number written in the citation text, and no
# written number disagrees with the manifest
import csv as _csv  # noqa: E402
import json as _json  # noqa: E402
_man = list(_csv.DictReader(open(BASE / "data" / "manifest.csv", newline="")))
_by_acc = {(r["product"], r["accession"]): r for r in _man}
_held = {}
for _r in _man:
    _held.setdefault(_r["product"], set()).add(_r["accession"])
_ciks = {k: load_product(k)["cik"] for k in product_keys()}


def _built_from(url: str, product: str, acc: str) -> bool:
    return f"/edgar/data/{int(_ciks[product])}/{acc.replace('-', '')}/" in url


_bad, _n_res, _n_all, _conflicts, _retired = [], 0, 0, [], []
for _p in sorted((BASE / "data" / "citations").glob("*.json")):
    if _p.name == "summary.json":
        continue
    _doc = _json.loads(_p.read_text())
    _prod = _doc["product"]
    for _cid, _refs in _doc["cells"].items():
        for _r in _refs:
            _n_all += 1
            if _r.get("conflict"):
                _conflicts.append(f"{_prod} {_cid}: {_r['conflict'][:70]}")
            if _r["match"] == "accession_in_text":
                _retired.append(f"{_prod} {_cid}")
            if _r["match"] in ("exact", "form_only"):
                _n_res += 1
                _m = _by_acc.get((_prod, _r["accession"]))
                if not _m or _m["form"] != _r["form"] or _m["url"] != _r["url"] \
                        or not _built_from(_r["url"], _prod, _r["accession"]):
                    _bad.append(f"{_prod} {_cid}: {_r.get('accession')}")
            elif _r["match"] in ("range", "set"):
                _n_res += 1
                for _f in _r["filings"]:
                    _m = _by_acc.get((_prod, _f["accession"]))
                    if not _m or (_r["form"] != "*" and _m["form"] != _r["form"]) or _m["url"] != _f["url"] \
                            or not _built_from(_f["url"], _prod, _f["accession"]):
                        _bad.append(f"{_prod} {_cid}: range {_f['accession']}")
            else:
                if not _r.get("reason"):
                    _bad.append(f"{_prod} {_cid}: {_r['match']} without a reason")
                if _r.get("url") or _r.get("accession"):
                    _bad.append(f"{_prod} {_cid}: {_r['match']} yet carries a URL or an accession")
_summary = _json.loads((BASE / "data" / "citations" / "summary.json").read_text())
check("citations: every resolved reference is the same product's manifest row with its URL built from "
      f"the CIK and that accession, every other one carries a reason and no URL ({_n_res} of {_n_all} resolved)",
      not _bad, "; ".join(_bad[:5]))
check("citations: no reference resolves from a number written in the text and no written accession "
      "disagrees with the manifest (rule 15)", not _conflicts and not _retired,
      "; ".join((_conflicts + _retired)[:5]))
check("citations: the summary counts equal the per-product files",
      _summary["references"] == _n_all and sum(_summary["counts"].values()) == _n_all)
# every single accession in every evidence row, in the accession column and
# written in the citation text, is a manifest row for that product
from tark_data import ACCESSION_RE as _ACC  # noqa: E402
_acc_bad = []
for _k in product_keys():
    for _row in load_evidence(_k):
        _a = (_row.get("accession") or "").strip()
        if _a and not _a.startswith("multiple (") and _a not in _held.get(_k, set()):
            _acc_bad.append(f"{_k} {_row['cell_id']}: column {_a}")
        for _w in _ACC.findall(_row.get("source_doc") or ""):
            if _w not in _held.get(_k, set()):
                _acc_bad.append(f"{_k} {_row['cell_id']}: text {_w}")
check("evidence: every accession in the accession column and every accession written in a citation "
      "is a manifest row for that product", not _acc_bad, "; ".join(_acc_bad[:5]))

# engine-owned cells restate their artifacts, never an older run
import re as _re  # noqa: E402
from tark_data import load_products as _lp, status_kind as _sk  # noqa: E402
_bad18, _bad39 = [], []
for _k, _p in _lp().items():
    _c18 = _p["cells"]["1.8"]
    _sp = BASE / "data" / "benchmarks" / f"{_k}_selection.json"
    if _sk(_c18["status"]) == "computed" and _sp.exists():
        _sel = _json.loads(_sp.read_text())
        # Slot K's own statistic, else the reference comparison's (decision 7.21)
        _comp = (((_sel.get("slot_k") or {}).get("selected") or {}).get("comparison")
                 or (_sel.get("reference_comparison") or {}).get("comparison") or {})
        if _comp.get("kind") == "published_index":
            _m = _re.search(r"relative wealth ratio ([0-9.]+)", _c18["value"])
            _want = _comp["relative_wealth_ratio"]
        else:
            _m = _re.search(r"KS-PME ([0-9.]+)", _c18["value"])
            _want = _comp.get("ks_pme")
        if _comp and (not _m or float(_m.group(1)) != _want):
            _bad18.append(f"{_k}: cell {_m.group(1) if _m else None} vs artifact {_want}")
        _g = ((_sel.get("slot_g") or {}).get("composite") or {})
        _c112 = _p["cells"]["1.12"]["value"]
        if _g.get("status") == "computed" and f"relative wealth ratio {_g['relative_wealth_ratio']}" not in _c112:
            _bad18.append(f"{_k}: cell 1.12 lacks the peer ratio {_g['relative_wealth_ratio']}")
        if _g.get("status") == "refused" and "REFUSED" not in _c112:
            _bad18.append(f"{_k}: cell 1.12 does not state the refusal")
    _fx = _json.loads((BASE / "data" / "facts" / f"{_k}.json").read_text())["facts"]
    _sv = (_fx.get("liquidity_structural_verdict") or {}).get("value")
    if _sv and not _p["cells"]["3.9"]["value"].startswith(f"Structural liquidity verdict {_sv.upper()}"):
        _bad39.append(_k)
check("cell 1.8 states the meaningful benchmark's statistic (or the reference comparison's) and cell 1.12 the "
      "peer ratio or its refusal, for every product with one", not _bad18,
      "; ".join(_bad18[:4]))
check("cell 3.9 opens with the typed structural verdict for every product", not _bad39, "; ".join(_bad39))

# the authority parser reads what fetch_authority.py writes, letter by letter,
# byte for byte: the synthetic fixture (33 paragraphs, nested roman items)
# goes through the writer into a scratch directory and back
import tempfile as _tempfile  # noqa: E402
import fetch_authority as _fa  # noqa: E402
from tark_data import (AUTHORITY_FILE as _AF, parse_authority as _pa,  # noqa: E402
                       rule_ref as _rr, authority as _auth)
_fx = (BASE / "src" / "fixtures" / "authority_fr_synthetic.xml").read_bytes()
_paras = _fa.select(_fa.section_paragraphs(_fx), _fa.PARAS)
_tmp = Path(_tempfile.mkdtemp(prefix="tark_auth_inv_"))
_meta = {"citation": _fa.CITATION, "publication_date": "2026-03-31", "regulation_id_numbers": [_fa.RIN],
         "docket_ids": ["EBSA-2026-0166"], "full_text_xml_url": "file://fixture", "html_url": ""}
_path, _row = _fa.write(_tmp, _tmp / "raw", _meta, _fx, _paras, "2026-09-06T00:00:00+00:00")
check("parse_authority: the writer's file parses back to every paragraph of every letter byte for byte "
      "(fixture: 33 paragraphs, nested (i) items inside (g), (h) and (j))",
      _pa(_path.read_text(encoding="utf-8")) == _paras and sum(len(v) for v in _paras.values()) == 33
      and _paras["h"][3].startswith("(i) ") and _paras["i"][0].startswith("(i) Fixture heading (i)"))
import shutil as _shutil  # noqa: E402
_shutil.rmtree(_tmp, ignore_errors=True)
_a = _auth()
_afile = DATA / "authority" / _AF
check("authority: a file in data/authority is in the build only with its hashed manifest row "
      "(a half-fetched state fails here)", not _afile.exists() or _a["status"] == "fetched",
      "file present, manifest row missing or its content hash differs")
check("rule_ref: paragraph letter follows the factor and the basis names the verbatim state",
      _rr("3.4", _a)["para"] == "(i)" and _rr("6.6", _a)["advisor_completed"]
      and not _rr("6.5", _a)["advisor_completed"]
      and (("verbatim text in " in _rr("1.1", _a)["basis"]) == (_a["status"] == "fetched")))

# P2-10: no laptop path anywhere under data/ (evidence, facts, notes, manifests)
_lap = _re.compile(r"/private/tmp/|/Users/|/tmp/claude")
_lap_hits = [str(_f.relative_to(BASE)) for _f in (BASE / "data").rglob("*")
             if _f.is_file() and _f.suffix in (".csv", ".json", ".md") and _lap.search(_f.read_text(errors="ignore"))]
check("no laptop path anywhere under data/", not _lap_hits, "; ".join(_lap_hits[:5]))

# data/roster_decisions.md claims to be validator-enforced: every product key
# in the record must be named in it
from tark_data import product_keys as _product_keys  # noqa: E402
_roster_md = (BASE / "data" / "roster_decisions.md").read_text()
_missing = [k for k in _product_keys() if k not in _roster_md]
check("data/roster_decisions.md names every product key in the record",
      not _missing, ", ".join(_missing))

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll invariants hold.")
sys.exit(1 if FAILS else 0)

"""Memo regression checks (M5). Run: python src/test_memo.py"""
import sys
from pathlib import Path
from docx import Document

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))
from tark_anon import forbidden_tokens  # noqa: E402
FORBIDDEN = forbidden_tokens()
FAILS = []
def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond: FAILS.append(name)

def text_of(p):
    d = Document(p)
    parts = [para.text for para in d.paragraphs]
    for t in d.tables:
        for r in t.rows:
            for c in r.cells: parts.append(c.text)
    return "\n".join(parts).lower()

import tempfile  # noqa: E402
from tark_memo import memo_name, write_all  # noqa: E402
from tark_data import load_plan, load_products, plan_keys  # noqa: E402

# the writer runs here, into a scratch directory: the test never depends on
# a committed docx and never writes into the repository
OUT = Path(tempfile.mkdtemp(prefix="tark_memos_"))
written = write_all(OUT)
check(f"writer produced one memo per plan x product ({len(plan_keys())} x {len(load_products())})",
      len(written) == len(plan_keys()) * len(load_products())
      and all(p.exists() and p.stat().st_size > 5000 for p in written))
# deterministic bytes: the same record gives the same file
again = write_all(Path(tempfile.mkdtemp(prefix="tark_memos2_")))
check("memo bytes are deterministic across two runs",
      all(a.read_bytes() == b.read_bytes() for a, b in zip(written, again)))
# the plan shapes the memo: same product, two plans, both labels present and different
_pt = text_of(OUT / memo_name("plan_tech_media", "cliffwater_cclfx"))
_pc = text_of(OUT / memo_name("plan_consulting_alumni", "cliffwater_cclfx"))
check("memo carries its own plan label (tech plan)",
      load_plan("plan_tech_media")["display_label"].lower() in _pt)
check("memo carries its own plan label (consulting plan)",
      load_plan("plan_consulting_alumni")["display_label"].lower() in _pc
      and load_plan("plan_tech_media")["display_label"].lower() not in _pc)
check("liquidity match section is plan-specific (consulting memo carries the thin-headroom flag)",
      "thin headroom" in _pc and "product-to-plan liquidity match" in _pt)

import re  # noqa: E402
from tark_data import status_kind  # noqa: E402
from tark_display import facts_by_cell, typed_headline  # noqa: E402
from tark_memo import EVIDENCED, first_sentence  # noqa: E402
import json  # noqa: E402

def squash(t):
    return re.sub(r"\s+", " ", t).strip().lower()

# P1-20: the findings table carries the COMPLETE first sentence of every
# evidenced cell (no 220-character cut, no mid-word ending) and the typed
# facts the engines read, per factor
prods = load_products()
missing, typed_missing, cut = [], [], []
for k, prod in prods.items():
    t = squash(text_of(OUT / memo_name("plan_tech_media", k)))
    if "…" in t:
        cut.append(k)
    fbc = facts_by_cell(json.loads((BASE / "data" / "facts" / f"{k}.json").read_text()).get("facts", {}))
    for cid, cell in prod["cells"].items():
        v = (cell.get("value") or "").strip()
        if status_kind(cell.get("status", "")) in EVIDENCED and v:
            if squash(first_sentence(v)) not in t:
                missing.append(f"{k} {cid}")
            th = typed_headline(cid, fbc.get(cid, {}))
            if th and squash(th) not in t:
                typed_missing.append(f"{k} {cid}")
check("findings: complete first sentence of every evidenced cell, all 16 products",
      not missing)
if missing:
    print("   missing:", "; ".join(missing[:8]))
check("findings: every typed-fact headline the site shows is in the memo", not typed_missing)
if typed_missing:
    print("   missing:", "; ".join(typed_missing[:8]))
check("findings: no ellipsis cut anywhere in the memos", not cut)

# P1-21: the four sections, in every plan x product memo
SECTIONS = ("product-to-plan liquidity match", "structural verdict (typed facts, plan-independent)",
            "scenario (illustrative, this plan)", "recommendation", "scope", "case law",
            "the fiduciary makes the decision on this record", "flags raised by the record")
sec_missing, verdict_missing = [], []
matches = {}
for pl in plan_keys():
    for k in prods:
        t = squash(text_of(OUT / memo_name(pl, k)))
        for sname in SECTIONS:
            if sname not in t:
                sec_missing.append(f"{pl} {k}: {sname}")
        mm = json.loads((BASE / "data" / "liquidity" / f"{pl}__{k}_match.json").read_text())
        matches[(pl, k)] = mm
        want = (f"structural liquidity verdict: {mm['verdict']}".lower(),
                f"(illustrative): {(mm.get('scenario_verdict') or 'not computable')}".lower())
        if not all(w in t for w in want):
            verdict_missing.append(f"{pl} {k}")
check("sections: liquidity match, recommendation, scope, case law in all 64 memos", not sec_missing)
if sec_missing:
    print("   missing:", "; ".join(sec_missing[:6]))
check("recommendation states the match file's structural and scenario verdicts, all 64", not verdict_missing)
if verdict_missing:
    print("   missing:", "; ".join(verdict_missing[:6]))
# the scenario layer is plan-specific: some product's scenario verdict differs
# between two plans and each memo carries its own
diff = [k for k in prods if matches[("plan_tech_media", k)]["scenario_verdict"]
        != matches[("plan_consulting_alumni", k)]["scenario_verdict"]]
check("scenario verdict differs between plans for at least one product", bool(diff))
if diff:
    k = diff[0]
    tt = squash(text_of(OUT / memo_name("plan_tech_media", k)))
    tc = squash(text_of(OUT / memo_name("plan_consulting_alumni", k)))
    check(f"{k}: each plan's memo carries its own scenario verdict",
          f"(illustrative): {matches[('plan_tech_media', k)]['scenario_verdict']}" in tt
          and f"(illustrative): {matches[('plan_consulting_alumni', k)]['scenario_verdict']}" in tc)
_sre = squash(text_of(OUT / memo_name("plan_tech_media", "sreit")))
check("sreit: suspended program is a flag and the structural verdict is MISALIGNED",
      "repurchase program suspended" in _sre and "structural liquidity verdict: misaligned" in _sre)
_dx = squash(text_of(OUT / memo_name("plan_tech_media", "dxyz")))
check("dxyz: recommendation carries the benchmark escalation",
      "benchmark: escalated" in _dx)
check("no memo carries the unsourced case-law sentence",
      all("argument expected october term" not in squash(text_of(OUT / memo_name(pl, k)))
          for pl in plan_keys() for k in prods))

# P1-22: provenance with true counts, the verified sentence only when true,
# every resolved accession in the memo, unresolved rows say so
from tark_data import coverage_summary  # noqa: E402
acc_missing, cov_missing, false_verified = [], [], []
not_on_record = 0
for k in prods:
    t = squash(text_of(OUT / memo_name("plan_tech_media", k)))
    cov = coverage_summary(k)
    if squash(cov["headline"]) not in t:
        cov_missing.append(k)
    if cov["verified"] == 0 and ("verified cells have been independently re-checked" in t
                                 or "no cell is verified" not in t):
        false_verified.append(k)
    cit = json.loads((BASE / "data" / "citations" / f"{k}.json").read_text())["cells"]
    for cid, refs in cit.items():
        if status_kind(prods[k]["cells"][cid].get("status", "")) not in EVIDENCED:
            continue
        for r in refs:
            accs = [r["accession"]] if r["match"] in ("exact", "form_only", "accession_in_text") \
                else [f["accession"] for f in r.get("filings", [])]
            for a in accs:
                if a.lower() not in t or r.get("url", r.get("filings", [{}])[0].get("url", "")).lower() not in t:
                    acc_missing.append(f"{k} {cid} {a}")
    not_on_record += t.count("accession not on record")
check("provenance: the coverage headline from the one formula is in every memo", not cov_missing)
check("provenance: the verified sentence is never written while verified is 0", not false_verified)
check("provenance: every resolved accession and URL for an evidenced cell is in the memo", not acc_missing)
if acc_missing:
    print("   missing:", "; ".join(acc_missing[:6]))
check("provenance: cells without a resolvable filing say accession not on record", not_on_record > 0)

keys = ["breit","cliffwater_cclfx","dxyz","hl_paf","kkr_kpec","stepstone_spm"]
texts = {}
for k in keys:
    p = OUT / memo_name("plan_tech_media", k)
    check(f"{k}: memo exists", p.exists())
    if p.exists():
        texts[k] = text_of(p)
        check(f"{k}: anonymization holds",
              not any(t in texts[k] for t in FORBIDDEN))
        check(f"{k}: rule cited", "91 fr 16088" in texts[k])
check("cclfx: PME + CDLI rejection in memo",
      "ks-pme 1.2532" in texts["cliffwater_cclfx"] and "cliffwater direct lending index" in texts["cliffwater_cclfx"])
check("dxyz: escalation variant", "escalation" in texts["dxyz"] and "no meaningful benchmark" in texts["dxyz"])
check("kpec: K-1 finding in memo", "schedule k-1" in texts["kkr_kpec"])
check("paf: window-sensitivity disclosure", "window-sensitive" in texts["hl_paf"])
print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll memo checks pass.")
sys.exit(1 if FAILS else 0)

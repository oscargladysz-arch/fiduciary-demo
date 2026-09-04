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

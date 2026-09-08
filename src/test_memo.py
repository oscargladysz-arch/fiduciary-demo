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
_TEXTS = {}
def memo_text(pl, k):
    """docx text parsed once per memo and cached (64 memos, many checks)."""
    if (pl, k) not in _TEXTS:
        _TEXTS[(pl, k)] = text_of(OUT / memo_name(pl, k))
    return _TEXTS[(pl, k)]
check(f"writer produced one memo per plan x product ({len(plan_keys())} x {len(load_products())})",
      len(written) == len(plan_keys()) * len(load_products())
      and all(p.exists() and p.stat().st_size > 5000 for p in written))
# deterministic bytes: the same record gives the same file
again = write_all(Path(tempfile.mkdtemp(prefix="tark_memos2_")))
check("memo bytes are deterministic across two runs",
      all(a.read_bytes() == b.read_bytes() for a, b in zip(written, again)))
# the plan shapes the memo: same product, two plans, both labels present and different
_pt = memo_text("plan_tech_media", "cliffwater_cclfx")
_pc = memo_text("plan_consulting_alumni", "cliffwater_cclfx")
check("memo carries its own plan label (tech plan)",
      load_plan("plan_tech_media")["display_label"].lower() in _pt)
check("memo carries its own plan label (consulting plan)",
      load_plan("plan_consulting_alumni")["display_label"].lower() in _pc
      and load_plan("plan_tech_media")["display_label"].lower() not in _pc)
check("liquidity match section is plan-specific (consulting memo carries the thin-headroom flag)",
      "thin headroom" in _pc and "product-to-plan liquidity match" in _pt)

import re  # noqa: E402
from tark_data import status_kind  # noqa: E402
from tark_display import display_path_free, facts_by_cell, typed_headline  # noqa: E402
from tark_memo import EVIDENCED, cell_title, first_sentence  # noqa: E402
import json  # noqa: E402

def squash(t):
    return re.sub(r"\s+", " ", t).strip().lower()

# P1-20: the findings table carries the COMPLETE first sentence of every
# evidenced cell (no 220-character cut, no mid-word ending) and the typed
# facts the engines read, per factor
prods = load_products()
missing, typed_missing, cut = [], [], []
for k, prod in prods.items():
    t = squash(memo_text("plan_tech_media", k))
    if "…" in t:
        cut.append(k)
    fbc = facts_by_cell(json.loads((BASE / "data" / "facts" / f"{k}.json").read_text()).get("facts", {}))
    for cid, cell in prod["cells"].items():
        v = (cell.get("value") or "").strip()
        if status_kind(cell.get("status", "")) in EVIDENCED and v:
            # 3.7, 3.8 and 3.9 print the memo's own plan's sentence instead of
            # the record's plan-independent one (R2-P1-13), checked below
            if cid not in ("3.7", "3.8", "3.9") and squash(first_sentence(display_path_free(v))) not in t:
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

# R2-P0-4: the abbreviation-aware splitter (audit round 2 item 4). The old
# "period then whitespace" splitter cut the case caption at "v." on all 16
# products (cell 5.7) and "Stephen L." on hl_paf 1.11. The regression set is every cell where the two
# splitters differ today, and the audit's named examples must be inside it.
from tark_display import ends_at_abbreviation  # noqa: E402
_naive = lambda v: re.split(r"(?<=[.!?])\s+", v.strip(), maxsplit=1)[0]  # noqa: E731
_reg = {(k, cid) for k, prod in prods.items() for cid, c in prod["cells"].items()
        if (c.get("value") or "").strip() and status_kind(c.get("status", "")) != "n/a"
        and _naive(c["value"]) != first_sentence(c["value"])}
_named = {(k, "5.7") for k in prods} | {("cliffwater_cclfx", "1.11"), ("amg_pantheon", "3.2"),
                                        ("cliffwater_cclfx", "3.2"), ("bcred", "4.6"), ("jll_ipt", "4.6"),
                                        ("bcred", "6.2"), ("cion_ares", "6.5"), ("jll_ipt", "6.5"),
                                        ("dxyz", "6.3"), ("breit", "2.7"), ("arkvx", "6.5")}
check(f"splitter: the audit's abbreviation cuts (the caption's v. on all 16, Stephen L., p.m., Supplement No., U.S., "
      f"Inc., Mr., i.e., St.) are in the regression set of {len(_reg)} cells where the old splitter cut short",
      _named <= _reg)
if not _named <= _reg:
    print("   missing:", sorted(_named - _reg))
_unit = {"Doe v. Roe Corp. Investment Committee, No. 00-000. Next.":
         "Doe v. Roe Corp. Investment Committee, No. 00-000.",
         "Portfolio manager Stephen L. Nesbitt since inception. Next.": "Portfolio manager Stephen L. Nesbitt since inception.",
         "Tenders due 11:59 p.m. ET 2026-08-28. Next.": "Tenders due 11:59 p.m. ET 2026-08-28.",
         "STRATEGY: U.S. middle-market loans (incl. unitranche). Next.": "STRATEGY: U.S. middle-market loans (incl. unitranche).",
         "Adviser ARK Investment Management LLC (St. Petersburg, FL). Next.": "Adviser ARK Investment Management LLC (St. Petersburg, FL).",
         "At the median of 5. Next sentence.": "At the median of 5."}
check("splitter: unit cases (v., initial, p.m., U.S., incl., parenthesis, a number is a sentence end)",
      all(first_sentence(k) == v for k, v in _unit.items()))
_abbr_rows = []
for pl in plan_keys():
    for k in prods:
        _d = Document(OUT / memo_name(pl, k))
        for _t in _d.tables:
            for _row in _t.rows:
                for _c in _row.cells:
                    for _para in _c.paragraphs:
                        _txt = _para.text.strip()
                        if re.match(r"^\d+\.\d+ .*\((?:extracted-unverified|computed|partial|verified|structured)\): ",
                                    _txt) and ends_at_abbreviation(_txt):
                            _abbr_rows.append(f"{pl} {k}: {_txt[-40:]}")
check("findings: no row in any of the 64 memos ends at an abbreviation (v., L., U.S., p.m., No., Inc.)",
      not _abbr_rows)
if _abbr_rows:
    print("   rows:", "; ".join(_abbr_rows[:6]))

# P1-21: the four sections, in every plan x product memo
SECTIONS = ("product-to-plan liquidity match", "structural verdict (typed facts, plan-independent)",
            "scenario (illustrative, this plan)", "recommendation", "scope", "case law",
            "the fiduciary makes the decision on this record", "flags raised by the record")
sec_missing, verdict_missing = [], []
matches = {}
for pl in plan_keys():
    for k in prods:
        t = squash(memo_text(pl, k))
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
    tt = squash(memo_text("plan_tech_media", k))
    tc = squash(memo_text("plan_consulting_alumni", k))
    check(f"{k}: each plan's memo carries its own scenario verdict",
          f"(illustrative): {matches[('plan_tech_media', k)]['scenario_verdict']}" in tt
          and f"(illustrative): {matches[('plan_consulting_alumni', k)]['scenario_verdict']}" in tc)
_sre = squash(memo_text("plan_tech_media", "sreit"))
check("sreit: suspended program is a flag and the structural verdict is MISALIGNED",
      "repurchase program suspended" in _sre and "structural liquidity verdict: misaligned" in _sre)
_dx = squash(memo_text("plan_tech_media", "dxyz"))
check("dxyz: recommendation carries the benchmark escalation",
      "benchmark: escalated" in _dx)
check("no memo carries the unsourced case-law sentence",
      all("argument expected october term" not in squash(memo_text(pl, k))
          for pl in plan_keys() for k in prods))

# P1-22: provenance with true counts, the verified sentence only when true,
# every resolved accession in the memo, unresolved rows say so
from tark_data import coverage_summary  # noqa: E402
acc_missing, cov_missing, false_verified = [], [], []
not_on_record = 0
for k in prods:
    t = squash(memo_text("plan_tech_media", k))
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
            accs = [r["accession"]] if r["match"] in ("exact", "form_only") \
                else [f["accession"] for f in r.get("filings", [])]
            for a in accs:
                if a.lower() not in t or r.get("url", r.get("filings", [{}])[0].get("url", "")).lower() not in t:
                    acc_missing.append(f"{k} {cid} {a}")
    not_on_record += t.count("accession not on record")
check("provenance: the coverage headline from the one formula is in every memo", not cov_missing)
# R3-P2-17a: the provenance counts the same set the headline counts as resolved
_t_sreit = squash(memo_text("plan_tech_media", "sreit"))
_cov_sreit = coverage_summary("sreit")
check("provenance: the resolved count in the prose is the headline's resolved count and the soft cells are named as "
      "not resolved (sreit)",
      f"of the {_cov_sreit['resolved']} resolved cells (structured, extracted-unverified, verified and computed)" in _t_sreit
      and f"{_cov_sreit['soft']} cells are partial or fetched and are not counted as resolved" in _t_sreit
      and "of the 41 evidenced cells" not in _t_sreit)
# R3-P2-17b: a committee cell that is n/a for the product is not called open
_na_bad = []
for k in prods:
    t = squash(memo_text("plan_tech_media", k))
    for cid in ("2.8", "3.5", "4.9"):
        st = str(prods[k]["cells"][cid].get("status", ""))
        if status_kind(st) == "n/a" and f"{cid} {cell_title(cid).lower()} (open)" in t:
            _na_bad.append(f"{k} {cid}")
        if status_kind(st) == "n/a" and f"{cid} {cell_title(cid).lower()} (not applicable" not in t:
            _na_bad.append(f"{k} {cid} missing")
check("recommendation: a committee cell the record marks n/a for the product is listed as not applicable with the "
      "reason, never as open", not _na_bad)
if _na_bad:
    print("   n/a committee cells called open:", "; ".join(_na_bad[:4]))
check("provenance: the verified sentence is never written while verified is 0", not false_verified)
check("provenance: every resolved accession and URL for an evidenced cell is in the memo", not acc_missing)
if acc_missing:
    print("   missing:", "; ".join(acc_missing[:6]))
check("provenance: cells without a resolvable filing say accession not on record", not_on_record > 0)

# P1-23, R2-P1-14: case law comes from cell 5.7 alone. The memo carries the
# cell under its status kind and the cell's own first sentence, states no
# holding of the Court, and the cell is never verified. No case-law text is
# written here: the record is the only source.
from tark_memo import KIND_LABEL as _KL  # noqa: E402
cl_bad = []
for pl in plan_keys():
    for k in prods:
        t = squash(memo_text(pl, k))
        c57 = prods[k]["cells"]["5.7"]
        kind = status_kind(c57["status"])
        lead = squash(first_sentence(display_path_free(c57["value"])).lower())
        if not (f"cell 5.7 ({_KL[kind]})" in t and lead in t
                and "the court held" not in t and "holding of the court" not in t):
            cl_bad.append(f"{pl} {k}")
check("case law: every memo carries cell 5.7 under its status kind with the cell's own first sentence "
      "and states no holding of the Court", not cl_bad)
if cl_bad:
    print("   bad:", "; ".join(cl_bad[:4]))
check("cell 5.7 is partial or extracted-unverified for every product, never verified, and identical across products",
      all(status_kind(p_["cells"]["5.7"]["status"]) in ("partial", "extracted") for p_ in prods.values())
      and len({p_["cells"]["5.7"]["value"] for p_ in prods.values()}) == 1)
check("cell 5.6 is computed for every product with a selection artifact",
      all(status_kind(p_["cells"]["5.6"]["status"]) == "computed" for p_ in prods.values()))

# P1-24: no memo prints a caveat the typed facts contradict
_reg = json.loads((BASE / "data" / "registry.json").read_text())["products"]
_cav_bad = []
for k, prod in prods.items():
    fx = json.loads((BASE / "data" / "facts" / f"{k}.json").read_text())
    cid = fx.get("cohort_id")
    if not cid:
        continue
    members = list(json.loads((BASE / "data" / "cohorts" / f"{cid}.json").read_text())["members"])
    t = squash(memo_text("plan_tech_media", k))
    for label, attr in (("pricing-basis mix", "pricing_class"), ("nav-cadence mix", "nav_cadence"),
                        ("leverage-regime mix", "leverage_regime")):
        if label in t and len({_reg[m][attr] for m in members}) < 2:
            _cav_bad.append(f"{k}: {label}")
check("no memo caveat contradicts the members' typed values", not _cav_bad)
if _cav_bad:
    print("   bad:", "; ".join(_cav_bad[:6]))

# P1-26: the regulatory basis cites and maps, never paraphrases
from tark_data import RULE, authority  # noqa: E402
_rb_bad = []
for pl in plan_keys():
    for k in prods:
        t = memo_text(pl, k)
        if not (RULE["fr_url"].lower() in t and RULE["docket"].lower() in t
                and "paragraphs (g) to (l)" in t and "factor mapping basis:" in t
                and "1. performance (g)" in t and "6. complexity (l)" in t
                and "advisor-completed under paragraph (l)" in t):
            _rb_bad.append(f"{pl} {k}: regulatory basis incomplete")
        if "safe harbor attaches" in t or "the proposal requires comparison" in t:
            _rb_bad.append(f"{pl} {k}: paraphrase of the regulation")
        # R2-P0-9: no legal conclusion and, while the rule text is not in the
        # build, no sentence that states what the rule requires
        for phrase in ("undercut", "do not proceed", "cannot support the safe harbor",
                       "satisfies the safe harbor", "would defeat the safe harbor",
                       "recommended action:", "under the proposal's own terms"):
            if phrase in t:
                _rb_bad.append(f"{pl} {k}: legal conclusion phrase {phrase!r}")
        if authority()["status"] != "fetched":
            for rx in (r"\bthe (?:rule|proposal|regulation|safe harbor) (?:requires|mandates|demands|obliges|calls for)\b",
                       r"\brequired by the (?:rule|proposal|regulation)\b",
                       r"\bto (?:qualify for|earn|keep|preserve) the safe harbor\b"):
                if re.search(rx, t):
                    _rb_bad.append(f"{pl} {k}: states what the rule requires while the text is not in the build ({rx})")
        if authority()["status"] != "fetched" and "not yet in this build" not in t:
            _rb_bad.append(f"{pl} {k}: verbatim-text status missing")
check("regulatory basis: citation, links, paragraph mapping and basis in all 64, no paraphrase, no legal "
      "conclusion, no statement of what the rule requires while its text is absent", not _rb_bad)
if _rb_bad:
    print("   bad:", "; ".join(_rb_bad[:4]))

# P2-6: advisor-stated inputs are a section of their own, never evidence
from tark_data import advisor_entries  # noqa: E402
_adv_bad = []
for pl in plan_keys():
    for k in prods:
        t = memo_text(pl, k)
        stated = bool((advisor_entries().get(f"{pl}__{k}") or {}).get("cells"))
        if "advisor-stated inputs (this plan)" not in t or "it is not evidence" not in t:
            _adv_bad.append(f"{pl} {k}: section missing")
        if not stated and "none stated for" not in t:
            _adv_bad.append(f"{pl} {k}: no advisor file yet the memo does not say none stated")
        if not stated and "(stated)" in t:
            _adv_bad.append(f"{pl} {k}: a committee cell marked stated without an advisor file")
check("advisor-stated section in all 64 memos, honest about what is stated", not _adv_bad)
if _adv_bad:
    print("   bad:", "; ".join(_adv_bad[:4]))

# P2-9: committee packets, one per plan and product, from the same artifacts
from tark_packet import packet_name, write_all_packets  # noqa: E402
POUT = Path(tempfile.mkdtemp(prefix="tark_packets_"))
pk = write_all_packets(POUT)
check("packets: one per plan x product, deterministic bytes",
      len(pk) == len(plan_keys()) * len(prods)
      and all(a.read_bytes() == b.read_bytes() for a, b in zip(pk, write_all_packets(Path(tempfile.mkdtemp(prefix="tark_packets2_"))))))
_pk_bad = []
for pl in plan_keys():
    for k in prods:
        t = squash(text_of(POUT / packet_name(pl, k)))
        mm = matches[(pl, k)]
        if any(tok in t for tok in FORBIDDEN):
            _pk_bad.append(f"{pl} {k}: sponsor token")
        if f"plan: {load_plan(pl)['display_label'].lower()}" not in t or "committee packet" not in t:
            _pk_bad.append(f"{pl} {k}: header")
        if (f"structural liquidity verdict: {mm['verdict']}" not in t
                or f"(illustrative, default sliders): {(mm.get('scenario_verdict') or 'not computable')}" not in t):
            _pk_bad.append(f"{pl} {k}: verdicts")
        if not all(x in t for x in ("exhibit a. benchmark selection", "exhibit c. fees and terms",
                                    "exhibit d. peer cohort placement", "verified by a person: 0",
                                    "this packet does not decide")):
            _pk_bad.append(f"{pl} {k}: exhibits")
        if "verified cells have been independently" in t:
            _pk_bad.append(f"{pl} {k}: verified sentence")
        if any(ph in t for ph in ("undercut", "do not proceed", "cannot support the safe harbor",
                                  "satisfies the safe harbor", "recommended action:")):
            _pk_bad.append(f"{pl} {k}: legal conclusion phrase")
check("packets: anonymized, own plan, both verdicts from the match file, exhibits, no decision, all 64", not _pk_bad)
if _pk_bad:
    print("   bad:", "; ".join(_pk_bad[:5]))

# R2-P1-13 and R2-P1-15: no plan in another plan's document. Every memo and
# every packet (64 each) is read for another plan's label, another plan's
# participant counts (any count of 1,000 or more, comma-formatted, from the
# plan records) and another plan's match file name. The memo's own 3.7 line
# carries its own plan's counts. No packet headline cell is a status word.
# The structured sentence appears only where the product has a structured cell.
from docx import Document as _Doc  # noqa: E402
_plans = {pl: load_plan(pl) for pl in plan_keys()}
def _counts(pl):
    # the counts the 3.7 line prints: accounts, the separated tail, active,
    # retirees (a total-at-start figure is not printed anywhere)
    part = _plans[pl].get("participants") or {}
    return {f"{part[f]:,.0f}" for f in ("with_account_balances", "separated_deferred_vested", "active_eoy", "retired_receiving")
            if isinstance(part.get(f), (int, float)) and part[f] >= 1000}
_leak_bad, _own_bad, _head_bad, _struct_bad = [], [], [], []
_STATUS_WORDS = {"extracted", "extracted-unverified", "computed", "partial", "structured", "verified", "pending", "n/a"}
for pl in plan_keys():
    others = [o for o in plan_keys() if o != pl]
    for k in prods:
        for kind, path in (("memo", OUT / memo_name(pl, k)), ("packet", POUT / packet_name(pl, k))):
            t_raw = text_of(path)
            t = squash(t_raw)
            for o in others:
                if _plans[o]["display_label"].lower() in t:
                    _leak_bad.append(f"{pl} {k} {kind}: label of {o}")
                for c in _counts(o) - _counts(pl):
                    if c in t_raw:
                        _leak_bad.append(f"{pl} {k} {kind}: count {c} of {o}")
                if f"{o}__" in t:
                    _leak_bad.append(f"{pl} {k} {kind}: match file of {o}")
            if kind == "memo":
                own = _counts(pl)
                if not all(c in t_raw for c in own):
                    _own_bad.append(f"{pl} {k}: own counts missing from the 3.7 line")
                if "3.7 plan participant liquidity demand (computed, this plan)" not in t:
                    _own_bad.append(f"{pl} {k}: 3.7 not marked as this plan's")
                has_struct = any(status_kind(c_.get("status", "")) == "structured" for c_ in prods[k]["cells"].values())
                if ("cells marked structured" in t) != has_struct:
                    _struct_bad.append(f"{pl} {k}: structured sentence {'present' if not has_struct else 'absent'}")
            else:
                d = _Doc(str(path))
                for tb in d.tables:
                    if tb.rows[0].cells[1].text.strip().lower() == "typed headline":
                        for r in tb.rows[1:]:
                            if r.cells[1].text.strip().lower() in _STATUS_WORDS:
                                _head_bad.append(f"{pl} {k}: {r.cells[0].text[:8]} headline is a status word")
check("no memo or packet carries another plan's label, participant counts or match file (64 memos, 64 packets)",
      not _leak_bad)
if _leak_bad:
    print("   bad:", "; ".join(_leak_bad[:6]))
check("every memo's 3.7 line carries its own plan's counts and is marked as this plan's", not _own_bad)
if _own_bad:
    print("   bad:", "; ".join(_own_bad[:4]))
check("no packet prints a status word where a typed headline belongs", not _head_bad)
if _head_bad:
    print("   bad:", "; ".join(_head_bad[:4]))
check("the structured-cells sentence appears only where the product has a structured cell", not _struct_bad)
if _struct_bad:
    print("   bad:", "; ".join(_struct_bad[:4]))
check("packet: Exhibit B is not an empty heading (the liquidity section sits directly under it)",
      all("exhibit b. liquidity match for this plan product-to-plan liquidity match" not in squash(text_of(POUT / packet_name(pl, k)))
          and "exhibit b. liquidity match for this plan plan:" in squash(text_of(POUT / packet_name(pl, k)))
          for pl in plan_keys() for k in prods if matches.get((pl, k))))

keys = ["breit","cliffwater_cclfx","dxyz","hl_paf","kkr_kpec","stepstone_spm"]
texts = {}
for k in keys:
    p = OUT / memo_name("plan_tech_media", k)
    check(f"{k}: memo exists", p.exists())
    if p.exists():
        texts[k] = memo_text("plan_tech_media", k)

# P1-25: the record-wide invariants hold in every one of the 64 memos
from tark_data import record_as_of  # noqa: E402
_labels = {pl: load_plan(pl)["display_label"].lower() for pl in plan_keys()}
_inv_bad = []
for pl in plan_keys():
    for k in prods:
        t = memo_text(pl, k)
        leak = next((tok for tok in FORBIDDEN if tok in t), None)
        if leak:
            _inv_bad.append(f"{pl} {k}: sponsor token")
        if "91 fr 16088" not in t or "rin 1210-ac38" not in t:
            _inv_bad.append(f"{pl} {k}: rule citation missing")
        # the header and the recommendation name this memo's own plan (other
        # plans may appear inside cell 3.9, which states verdicts per plan)
        if f"plan: {_labels[pl]}" not in t or f"scenario verdict under {_labels[pl]}" not in t:
            _inv_bad.append(f"{pl} {k}: own plan label missing from header or recommendation")
        if f"date: {record_as_of()}" not in t:
            _inv_bad.append(f"{pl} {k}: memo date is not the record as-of")
        if "verified cells have been independently re-checked" in t:
            _inv_bad.append(f"{pl} {k}: verified sentence while verified is 0")
        if "\u2026" in t:      # the writer's former cut marker, never a quoted ellipsis
            _inv_bad.append(f"{pl} {k}: ellipsis cut")
        if "illustrative" not in t or "the fiduciary makes the decision on this record" not in t:
            _inv_bad.append(f"{pl} {k}: scenario label or decision sentence missing")
check("all 64 memos: anonymized, rule cited with RIN, own plan label only, record as-of date, "
      "no verified sentence, no ellipsis cut, ILLUSTRATIVE label and decision sentence", not _inv_bad)
if _inv_bad:
    print("   bad:", "; ".join(_inv_bad[:8]))
check("memo count equals plans x products", len(_TEXTS) == len(plan_keys()) * len(prods))
check("cclfx: PME + CDLI rejection in memo",
      "ks-pme 1.2532" in texts["cliffwater_cclfx"] and "cliffwater direct lending index" in texts["cliffwater_cclfx"])
check("dxyz: escalation variant", "escalation" in texts["dxyz"] and "no meaningful benchmark" in texts["dxyz"])
check("kpec: K-1 finding in memo", "schedule k-1" in texts["kkr_kpec"])
check("paf: window-sensitivity disclosure", "window-sensitive" in texts["hl_paf"])
print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll memo checks pass.")
sys.exit(1 if FAILS else 0)

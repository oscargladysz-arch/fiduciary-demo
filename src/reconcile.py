"""
Reconcile gate: one number, every surface
==========================================
    python src/reconcile.py

For every product, the figures a committee reads must agree wherever they
appear: the typed facts (screener and compare read them), the cell headline
the Evaluation and Fee views print, the benchmark selection artifact and
the card that renders it, the engine-owned cells 1.8, 1.12 and 3.9, the
liquidity match files, and the memo for the reference plan. Checked:
expense ratio, management fee rate and base, KS-PME and Direct Alpha of the
primary comparison, and the structural liquidity verdict. Reads the record,
the built bundle (site/data.js) and the built memos (site/memos/), so it
runs after build_site.py in the hook. Nothing is written.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tark_anon import docx_text  # noqa: E402
from tark_data import BASE, DATA, load_products  # noqa: E402
from tark_display import BASE_LABEL, facts_by_cell, typed_headline  # noqa: E402
from tark_memo import memo_name  # noqa: E402

SITE = BASE / "site"
FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" : {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def bundle() -> dict:
    raw = (SITE / "data.js").read_text()
    return json.loads(raw[len("window.TARK = "):].rstrip().rstrip(";"))


def squash(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip().lower()


def main() -> int:
    B = bundle()
    prods = load_products()
    bad: dict[str, list[str]] = {"expense": [], "mgmt": [], "pme": [], "verdict": [], "scenario": []}
    plans = sorted(p.stem for p in (DATA / "plans").glob("*.json"))
    liq_text = (SITE / "series.js").read_text()
    m_liq = re.search(r"^window\.TARK_LIQ = (.*);$", liq_text, re.M)
    bundle_liq = json.loads(m_liq.group(1)) if m_liq else {}
    n_memos = 0
    for k in prods:
        fx = json.loads((DATA / "facts" / f"{k}.json").read_text())["facts"]
        bfx = B["facts"][k]
        fbc = facts_by_cell(fx)
        memos = {pl: squash(docx_text(SITE / "memos" / memo_name(pl, k))) for pl in plans}
        n_memos += len(memos)
        memo = memos["plan_tech_media"]
        # ---- expense ratio: facts, bundle facts, the cell 2.3 headline, the memo typed line
        er = (fx.get("expense_ratio_pct") or {}).get("value")
        if bfx["expense_ratio_pct"]["value"] != er:
            bad["expense"].append(f"{k}: bundle facts {bfx['expense_ratio_pct']['value']} vs record {er}")
        if er is not None:
            # the headline lives on the cell the fact cites (2.3 for most products,
            # another fee cell where the 2.3 prose is partial and the ratio was
            # typed from a different line)
            cid = str(fx["expense_ratio_pct"]["source_cell"]).split(",")[0].strip()
            head = typed_headline(cid, fbc.get(cid, {}))
            disp = B["cell_display"][k][cid]["headline"]
            if not (head and head == disp and f"{er:.2f}%" in head and squash(f"{cid} {head}") in memo):
                bad["expense"].append(f"{k}: {cid} headline {disp!r} vs facts {er} or memo")
        # ---- management fee rate and base
        mf, mb = (fx.get("mgmt_fee_pct") or {}).get("value"), (fx.get("mgmt_fee_base") or {}).get("value")
        if bfx["mgmt_fee_pct"]["value"] != mf or bfx["mgmt_fee_base"]["value"] != mb:
            bad["mgmt"].append(f"{k}: bundle mgmt fee differs from record")
        if mf is not None:
            cid = str(fx["mgmt_fee_pct"]["source_cell"]).split(",")[0].strip()
            head = typed_headline(cid, fbc.get(cid, {}))
            disp = B["cell_display"][k][cid]["headline"]
            base_label = BASE_LABEL.get(mb, mb or "a base not typed")
            if not (head == disp and f"{mf:.2f}%" in head and base_label in head and squash(f"{cid} {head}") in memo):
                bad["mgmt"].append(f"{k}: {cid} headline {disp!r} vs facts {mf} on {mb} or memo")
        # ---- every computed comparison, named for its comparator (rule 12):
        # KS-PME and Direct Alpha against a public market series, a relative
        # wealth ratio against an appraisal-based comparator. Slot K, the
        # reference comparison and Slot G must agree across the artifact, the
        # bundle card, cells 1.8 and 1.12, the typed facts and every memo, and
        # no sentence about Slot G may carry a PME name (decision 7.1).
        sel = json.loads((DATA / "benchmarks" / f"{k}_selection.json").read_text())
        bsel = B["benchmarks"].get(k) or {}
        c18 = prods[k]["cells"]["1.8"]["value"]
        c112 = prods[k]["cells"]["1.12"]["value"]
        c55 = prods[k]["cells"]["5.5"]["value"]
        c56 = prods[k]["cells"]["5.6"]["value"]
        sk = sel["slot_k"]
        slots = []
        if sk.get("selected"):
            slots.append(("slot_k", sk["selected"], (bsel.get("slot_k") or {}).get("selected") or {}))
        if sel.get("reference_comparison"):
            slots.append(("reference", sel["reference_comparison"], bsel.get("reference_comparison") or {}))
        pme_fact = (fx.get("pme_public_proxy") or {}).get("value")
        pme_expected = None
        for slot, s, bs in slots:
            comp = s.get("comparison") or {}
            if not comp:
                continue
            bcomp = bs.get("comparison") or {}
            cand = re.escape(s["candidate"])
            if comp["kind"] == "series":
                ks, da = comp["ks_pme"], comp["direct_alpha_pct"]
                if pme_expected is None:
                    pme_expected = ks
                if not (bcomp.get("ks_pme") == ks and bcomp.get("direct_alpha_pct") == da
                        and bcomp.get("statistic", "").startswith("KS-PME")):
                    bad["pme"].append(f"{k} {slot}: bundle card {bcomp.get('ks_pme')} vs artifact {ks}")
                m = re.search(cand + r": KS-PME ([0-9.]+) and Direct Alpha ([+-]?[0-9.]+)%/yr", c18)
                if not (m and float(m.group(1)) == ks and float(m.group(2)) == da):
                    bad["pme"].append(f"{k} {slot}: cell 1.8 {m.groups() if m else None} vs artifact {ks} {da}")
                if not all(f"ks-pme {ks}" in mt and f"direct alpha {da}%/yr" in mt.replace("+", "")
                           for mt in memos.values()):
                    bad["pme"].append(f"{k} {slot}: a memo lacks KS-PME {ks} or Direct Alpha {da}")
                if comp["fund_return_source"].lower() not in c18.lower() \
                        or not all(comp["fund_return_source"].lower() in mt for mt in memos.values()):
                    bad["pme"].append(f"{k} {slot}: fund return source not named in cell 1.8 or a memo")
                if slot == "reference":
                    if "reference comparison" not in c18.lower() or "not the meaningful benchmark" not in c18.lower():
                        bad["pme"].append(f"{k}: cell 1.8 does not name the reference comparison as such")
                    if not all("not the meaningful benchmark" in mt for mt in memos.values()):
                        bad["pme"].append(f"{k}: a memo does not name the reference comparison as such")
            else:
                rr = comp["relative_wealth_ratio"]
                if not (bcomp.get("relative_wealth_ratio") == rr and "ks_pme" not in bcomp
                        and bcomp.get("statistic", "").startswith("relative wealth ratio")):
                    bad["pme"].append(f"{k} {slot}: bundle card ratio {bcomp.get('relative_wealth_ratio')} vs artifact {rr}")
                m = re.search(cand + r": relative wealth ratio ([0-9.]+)", c18)
                if not (m and float(m.group(1)) == rr):
                    bad["pme"].append(f"{k} {slot}: cell 1.8 lacks relative wealth ratio {rr}")
                if (fx.get("slot_k_relative_wealth_ratio") or {}).get("value") != rr:
                    bad["pme"].append(f"{k}: facts slot_k_relative_wealth_ratio vs artifact {rr}")
        if pme_fact != pme_expected:
            bad["pme"].append(f"{k}: facts pme_public_proxy {pme_fact} vs artifact {pme_expected}")
        # ---- Slot G: the peer comparison, never a PME, agrees everywhere
        g = ((sel.get("slot_g") or {}).get("composite") or {})
        bg = (((bsel.get("slot_g") or {}).get("composite")) or {})
        peer_fact = (fx.get("peer_relative_wealth_ratio") or {}).get("value")
        if g.get("status") == "computed":
            rr = g["relative_wealth_ratio"]
            if not (bg.get("relative_wealth_ratio") == rr and "ks_pme" not in bg
                    and bg.get("statistic", "").startswith("relative wealth ratio")):
                bad["pme"].append(f"{k} slot_g: bundle {bg.get('relative_wealth_ratio')} vs artifact {rr}")
            if f"relative wealth ratio {rr}" not in c112 or g["alignment_note"][:60] not in c112:
                bad["pme"].append(f"{k}: cell 1.12 lacks relative wealth ratio {rr} or the alignment note")
            if not all(f"relative wealth ratio {rr}" in mt and g["alignment_note"].lower()[:60] in mt
                       for mt in memos.values()):
                bad["pme"].append(f"{k} slot_g: a memo lacks relative wealth ratio {rr} or the alignment note")
            if peer_fact != rr:
                bad["pme"].append(f"{k}: facts peer_relative_wealth_ratio {peer_fact} vs artifact {rr}")
        else:
            if peer_fact is not None:
                bad["pme"].append(f"{k}: facts peer_relative_wealth_ratio {peer_fact} but the composite is refused")
            if g and ("REFUSED" not in c112 or g["reason"][:40] not in c112):
                bad["pme"].append(f"{k}: cell 1.12 does not carry the refusal reason")
            if g and not all("composite refused" in mt for mt in memos.values()):
                bad["pme"].append(f"{k}: a memo lacks the peer composite refusal")
        # the naming rule (rule 12): no sentence about the peer composite or a
        # published appraisal index carries a PME name, in any cell or memo
        peer_words = ("peer composite", "peer comparison", "paragraphs (g) and (h)")
        for cid, text in (("1.8", c18), ("1.12", c112), ("5.5", c55), ("5.6", c56)):
            for sent in re.split(r"(?<=[.!?])\s+", text):
                low = sent.lower()
                if any(w in low for w in peer_words) and re.search(r"KS-PME|Direct Alpha|\bPME\b", sent) \
                        and "never a pme" not in low and "not a public market equivalent" not in low \
                        and "never a public market equivalent" not in low:
                    bad["pme"].append(f"{k} cell {cid}: a peer-comparison sentence carries a PME name")
        for pl, mt in memos.items():
            if re.search(r"ks-pme [0-9.]+ ?(?:vs|against)? ?(?:the )?peer", mt) or \
                    re.search(r"peer composite[^.]{0,80}ks-pme", mt):
                bad["pme"].append(f"{k} {pl}: memo names a PME against the peer composite")
        # ---- structural liquidity verdict: facts, bundle, cell 3.9, four match files, memo
        sv = (fx.get("liquidity_structural_verdict") or {}).get("value")
        if sv:
            if bfx["liquidity_structural_verdict"]["value"] != sv:
                bad["verdict"].append(f"{k}: bundle verdict differs")
            if not prods[k]["cells"]["3.9"]["value"].startswith(f"Structural liquidity verdict {sv.upper()}"):
                bad["verdict"].append(f"{k}: cell 3.9 does not open with {sv}")
            for mp in sorted((DATA / "liquidity").glob(f"*__{k}_match.json")):
                if json.loads(mp.read_text())["verdict"] != sv:
                    bad["verdict"].append(f"{k}: {mp.name} verdict differs")
            for pl, mt in memos.items():
                if f"structural liquidity verdict: {sv}" not in mt:
                    bad["verdict"].append(f"{k}: {pl} memo lacks the structural verdict {sv}")
            head39 = B["cell_display"][k]["3.9"]["headline"]
            if head39 != f"structural verdict {sv}, plan-independent":
                bad["verdict"].append(f"{k}: 3.9 headline {head39!r} is not the structural verdict alone")
        # ---- ILLUSTRATIVE scenario verdict, per plan: facts, match file, bundle, cell 3.9 text, memo
        by_plan = (fx.get("liquidity_verdict_by_plan") or {}).get("value") or {}
        c39 = prods[k]["cells"]["3.9"]["value"]
        for pl in plans:
            mp = DATA / "liquidity" / f"{pl}__{k}_match.json"
            if not mp.exists():
                continue
            mdoc = json.loads(mp.read_text())
            scv = mdoc.get("scenario_verdict")
            shown = scv or "not computable"
            label = json.loads((DATA / "plans" / f"{pl}.json").read_text())["display_label"]
            if by_plan and by_plan.get(pl) != scv:
                bad["scenario"].append(f"{k} {pl}: facts {by_plan.get(pl)} vs match {scv}")
            if bundle_liq and (bundle_liq.get(f"{pl}__{k}") or {}).get("scenario_verdict") != scv:
                bad["scenario"].append(f"{k} {pl}: bundle match differs")
            if f"{label}: {shown}" not in c39 or "ILLUSTRATIVE" not in c39.split("Scenario verdicts")[1][:20]:
                bad["scenario"].append(f"{k} {pl}: cell 3.9 lacks the labeled scenario verdict {shown}")
            if f"scenario verdict under {label.lower()} (illustrative): {shown}" not in memos[pl]:
                bad["scenario"].append(f"{k} {pl}: memo lacks the ILLUSTRATIVE scenario verdict {shown} for its own plan")
    check("expense ratio agrees across facts, bundle, cell 2.3 headline and memo, all 16", not bad["expense"],
          "; ".join(bad["expense"][:4]))
    check("management fee rate and base agree across facts, bundle, cell 2.1 headline and memo, all 16",
          not bad["mgmt"], "; ".join(bad["mgmt"][:4]))
    check("every comparison is named for its comparator (KS-PME vs a public proxy, relative wealth ratio vs an "
          "appraisal-based comparator) and Slot K, the reference comparison and Slot G agree across artifact, "
          "bundle card, cells 1.8 and 1.12, facts and all memos, with the fund return source named",
          not bad["pme"], "; ".join(bad["pme"][:6]))
    check(f"structural liquidity verdict agrees across facts, bundle, cell 3.9 headline, four match files and "
          f"all {n_memos} memos", not bad["verdict"], "; ".join(bad["verdict"][:4]))
    check("ILLUSTRATIVE scenario verdict agrees per plan across facts, match file, bundle, cell 3.9 text and "
          f"the plan's memo, always under its label ({n_memos} memos)", not bad["scenario"],
          "; ".join(bad["scenario"][:4]))
    # R2-P0-1 (rule 15): every EDGAR URL the drawer can link is the manifest's
    # own URL for that product and accession, built from the product's CIK
    import csv
    man = {(r["product"], r["accession"]): r["url"]
           for r in csv.DictReader(open(DATA / "manifest.csv", newline=""))}
    ev_text = (SITE / "series.js").read_text()
    m = re.search(r"^window\.TARK_EVIDENCE = (.*);$", ev_text, re.M)
    evidence = json.loads(m.group(1)) if m else {}
    bad_url, n_url = [], 0
    for k, cells in evidence.items():
        cik = int(prods[k]["cik"])
        for cid, cell in cells.items():
            for f in cell.get("edgar") or []:
                n_url += 1
                folder = f"/edgar/data/{cik}/{f['accession'].replace('-', '')}/"
                if man.get((k, f["accession"])) != f["url"] or folder not in f["url"]:
                    bad_url.append(f"{k} {cid}: {f['url']}")
            acc = (cell.get("accession") or "").strip()
            if acc and not acc.startswith("multiple (") and (k, acc) not in man:
                bad_url.append(f"{k} {cid}: accession {acc} not in the manifest")
    check(f"bundle: every EDGAR URL in the citation drawer is the manifest URL for that product and accession, "
          f"built from the CIK ({n_url} links)", bool(evidence) and not bad_url, "; ".join(bad_url[:4]))
    # R2-P0-4: no site headline or plain line stops at an abbreviation
    from tark_display import ends_at_abbreviation
    # a typed-fact headline is a fact, not a split sentence: an auditor named
    # "Cohen & Company, Ltd." is complete
    bad_head = [f"{k} {cid}: {d.get('headline', '')[-30:]!r}" for k, cells in B["cell_display"].items()
                for cid, d in cells.items()
                if (not d.get("typed") and ends_at_abbreviation(d.get("headline")))
                or ends_at_abbreviation(d.get("plain"))]
    check("headlines: no site headline or plain line ends at an abbreviation (v., L., U.S., p.m., No.)",
          not bad_head, "; ".join(bad_head[:4]))
    print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll surfaces reconcile.")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

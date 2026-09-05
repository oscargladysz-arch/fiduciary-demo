"""
Reconcile gate: one number, every surface
==========================================
    python src/reconcile.py

For every product, the figures a committee reads must agree wherever they
appear: the typed facts (screener and compare read them), the cell headline
the Evaluation and Fee views print, the benchmark selection artifact and
the card that renders it, the engine-owned cells 1.8 and 3.9, the
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
    bad: dict[str, list[str]] = {"expense": [], "mgmt": [], "pme": [], "verdict": []}
    for k in prods:
        fx = json.loads((DATA / "facts" / f"{k}.json").read_text())["facts"]
        bfx = B["facts"][k]
        fbc = facts_by_cell(fx)
        memo = squash(docx_text(SITE / "memos" / memo_name("plan_tech_media", k)))
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
        # ---- KS-PME and Direct Alpha of the primary comparison
        sel = json.loads((DATA / "benchmarks" / f"{k}_selection.json").read_text())
        comp = ((sel.get("primary") or {}).get("comparison") or {})
        bsel = B["benchmarks"].get(k) or {}
        bcomp = ((bsel.get("primary") or {}).get("comparison") or {})
        if comp:
            ks, da = comp["ks_pme"], comp["direct_alpha_pct"]
            c18 = prods[k]["cells"]["1.8"]["value"]
            m = re.search(r"KS-PME ([0-9.]+) and Direct Alpha ([+-]?[0-9.]+)%/yr", c18)
            if not (bcomp.get("ks_pme") == ks and bcomp.get("direct_alpha_pct") == da):
                bad["pme"].append(f"{k}: bundle benchmark card {bcomp.get('ks_pme')} vs artifact {ks}")
            if not (m and float(m.group(1)) == ks and float(m.group(2)) == da):
                bad["pme"].append(f"{k}: cell 1.8 {m.groups() if m else None} vs artifact {ks} {da}")
            if not (f"ks-pme {ks}" in memo and f"direct alpha {da}%/yr" in memo.replace("+", "")):
                bad["pme"].append(f"{k}: memo lacks KS-PME {ks} or Direct Alpha {da}")
            pme_fact = (fx.get("pme_primary") or {}).get("value")
            if pme_fact != ks:
                bad["pme"].append(f"{k}: facts pme_primary {pme_fact} vs artifact {ks}")
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
            if f"structural liquidity verdict: {sv}" not in memo:
                bad["verdict"].append(f"{k}: memo lacks the structural verdict {sv}")
    check("expense ratio agrees across facts, bundle, cell 2.3 headline and memo, all 16", not bad["expense"],
          "; ".join(bad["expense"][:4]))
    check("management fee rate and base agree across facts, bundle, cell 2.1 headline and memo, all 16",
          not bad["mgmt"], "; ".join(bad["mgmt"][:4]))
    check("KS-PME and Direct Alpha agree across artifact, bundle card, cell 1.8, facts and memo",
          not bad["pme"], "; ".join(bad["pme"][:4]))
    check("structural liquidity verdict agrees across facts, bundle, cell 3.9, four match files and memo",
          not bad["verdict"], "; ".join(bad["verdict"][:4]))
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

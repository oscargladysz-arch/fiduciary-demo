"""
Corrections log: every changed published number, generated not hand-written
=============================================================================
Compares the published numbers in the working tree against a git base ref
(default origin/main) and maintains two machine-managed blocks inside
docs/crosscheck_report.md:

  Corrections 2026-09   one row per (product, field) whose value changed:
                        old, new, cause, surfaces, date
  Evidence allowlist    T2 evidence rows that were deliberately edited, with
                        the reason (read by src/test_evidence_immutable.py)

Watched numbers: benchmark selections (slots, scores, comparison figures,
escalation), typed facts, liquidity verdicts per plan, fee_percentile bars,
the engine-owned cells (1.6, 1.7, 1.8, 1.9, 1.10, 1.12, 2.9, 3.7, 3.8, 3.9, 4.7, 4.8,
5.3, 5.4, 5.5, 5.6, 5.7),
and the accession column of every evidence row.

Commands:
  python src/corrections_log.py diff  [--base REF]
  python src/corrections_log.py write --cause "P0-3: ..." [--base REF]
  python src/corrections_log.py check [--base REF]      (gate: exit 1 if a
                                       changed number has no log row)
  python src/corrections_log.py allow --product K --cell 3.7 --column source \
                                      --reason "..."
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tark_data import BASE, DATA, record_as_of  # noqa: E402

REPORT = BASE / "docs" / "crosscheck_report.md"
CORR_BEGIN = "<!-- tark:corrections-2026-09:begin -->"
CORR_END = "<!-- tark:corrections-2026-09:end -->"
ALLOW_BEGIN = "<!-- tark:evidence-allowlist:begin -->"
ALLOW_END = "<!-- tark:evidence-allowlist:end -->"
OWNED_CELLS = ("1.6", "1.7", "1.8", "1.9", "1.10", "1.12", "2.9", "3.7", "3.8", "3.9",
               "4.7", "4.8", "5.3", "5.4", "5.5", "5.6", "5.7")
SURFACES = {
    "selection": "benchmark card, screener PME column, cell 1.8, memo",
    "facts": "screener, compare, fee matrix, memo findings",
    "liquidity": "liquidity view, screener verdict column, memo",
    "fee_percentile": "fee matrix bar chart",
    "cell": "evaluation cell, source drawer, memo",
    "evidence": "citation drawer EDGAR link, memo provenance table, packet provenance",
}


# ------------------------------------------------------------ tree access
def git_show(ref: str, rel: str) -> str | None:
    r = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=BASE,
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def git_ls(ref: str, prefix: str) -> list[str]:
    """Direct children of prefix at ref (not recursive: the frozen
    data/benchmarks/v1_snapshot/ must never shadow the live artifacts)."""
    r = subprocess.run(["git", "ls-tree", "--name-only", ref, prefix.rstrip("/") + "/"],
                       cwd=BASE, capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l]


class Tree:
    """Uniform read access to the working tree or a git ref."""
    def __init__(self, ref: str | None):
        self.ref = ref

    def files(self, prefix: str, suffix: str) -> list[str]:
        if self.ref is None:
            base = BASE / prefix
            return sorted(str(p.relative_to(BASE)) for p in base.glob(f"*{suffix}"))
        return sorted(f for f in git_ls(self.ref, prefix) if f.endswith(suffix))

    def text(self, rel: str) -> str | None:
        if self.ref is None:
            p = BASE / rel
            return p.read_text() if p.exists() else None
        return git_show(self.ref, rel)

    def json(self, rel: str):
        t = self.text(rel)
        return json.loads(t) if t else None


# ---------------------------------------------------------- watched values
def canon(v) -> str:
    if isinstance(v, float):
        return repr(round(v, 6))
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True, separators=(",", ":"))
    return str(v)


def collect(tree: Tree) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for rel in tree.files("data/benchmarks", "_selection.json"):
        key = Path(rel).name.replace("_selection.json", "")
        sel = tree.json(rel) or {}
        FIELDS = ("window", "ks_pme", "direct_alpha_pct", "relative_wealth_ratio",
                  "excess_return_pct", "statistic", "fund_return_source", "fund_ann_pct",
                  "index_ann_pct", "fund_growth_x", "index_growth_x",
                  "ks_pme_monthly_schedule")
        # v3 artifacts (slot_k, slot_g, reference and declared comparisons) and
        # the v2 shape they replaced (primary, secondary) are both read, so a
        # diff across the architecture change lists every moved number
        slots: dict[str, dict | None] = {}
        if "slot_k" in sel:
            sk = sel["slot_k"] or {}
            slots["slot_k"] = sk.get("selected")
            slots["reference"] = sel.get("reference_comparison")
            g = ((sel.get("slot_g") or {}).get("composite") or {})
            slots["slot_g"] = {"id": g.get("candidate"), "score": None, "comparison": g} if g else None
            for d in sel.get("declared") or []:
                slots[f"declared.{d['candidate_id']}"] = {"id": d["candidate_id"], "score": None,
                                                          "comparison": d.get("comparison"),
                                                          "type": d.get("type")}
            out[(key, "selection.escalation")] = canon(bool(sk.get("escalation")))
        else:
            slots["primary"] = sel.get("primary")
            slots["secondary"] = sel.get("secondary")
            out[(key, "selection.escalation")] = canon(bool(sel.get("escalation")))
        for slot, s in slots.items():
            out[(key, f"selection.{slot}.id")] = canon(s["id"] if s else None)
            out[(key, f"selection.{slot}.score")] = canon(s.get("score") if s else None)
            if s and s.get("type"):
                out[(key, f"selection.{slot}.type")] = canon(s["type"])
            comp = (s or {}).get("comparison") or {}
            for f in FIELDS:
                out[(key, f"selection.{slot}.{f}")] = canon(comp.get(f))
        out[(key, "selection.rejected")] = canon(
            sorted(f"{r['id']}:{r['score']}" for r in sel.get("rejected", [])))
    for rel in tree.files("data/facts", ".json"):
        key = Path(rel).stem
        for field, f in (tree.json(rel) or {}).get("facts", {}).items():
            out[(key, f"facts.{field}")] = canon(f.get("value"))
    for rel in tree.files("data/liquidity", "_match.json"):
        name = Path(rel).name.replace("_match.json", "")
        if "__" not in name:
            continue
        plan, key = name.split("__", 1)
        doc = tree.json(rel) or {}
        out[(key, f"liquidity.{plan}.verdict")] = canon(doc.get("verdict"))
        out[(key, f"liquidity.{plan}.scenario_verdict")] = canon(doc.get("scenario_verdict"))
    sup = tree.json("data/analytics/supplement.json") or {}
    for e in (sup.get("fee_percentile") or {}).get("entries", []):
        out[(e["product"], "fee_percentile.ter_pct")] = canon(e.get("ter_pct"))
    for rel in tree.files("data/products", ".json"):
        key = Path(rel).stem
        cells = (tree.json(rel) or {}).get("cells", {})
        for cid in OWNED_CELLS:
            c = cells.get(cid) or {}
            out[(key, f"cell.{cid}.value")] = canon(c.get("value"))
            out[(key, f"cell.{cid}.status")] = canon(c.get("status"))
    # the accession behind every citation is a published identifier (the
    # drawer links it): a change is logged like any number (R2-P0-1)
    for rel in tree.files("data/evidence", "_evidence.csv"):
        key = Path(rel).name.replace("_evidence.csv", "")
        for r in csv.DictReader(io.StringIO(tree.text(rel) or "")):
            acc = (r.get("accession") or "").strip()
            if acc:
                out[(key, f"evidence.{r['cell_id']}.accession")] = acc
    return out


def diffs(base_ref: str, head_ref: str | None = None) -> list[tuple[str, str, str, str]]:
    """Changed watched values between base_ref and head_ref (the working
    tree when head_ref is None)."""
    old, new = collect(Tree(base_ref)), collect(Tree(head_ref))
    rows = []
    for k in sorted(set(old) | set(new)):
        o, n = old.get(k, "<absent>"), new.get(k, "<absent>")
        if o != n:
            rows.append((k[0], k[1], o, n))
    return rows


# ------------------------------------------------------------- the report
def _block(text: str, begin: str, end: str) -> tuple[int, int]:
    i, j = text.find(begin), text.find(end)
    if i < 0 or j < 0:
        raise SystemExit(f"{REPORT} lacks the block {begin} .. {end}")
    return i + len(begin), j


def corr_rows(text: str) -> list[dict]:
    i, j = _block(text, CORR_BEGIN, CORR_END)
    rows = []
    for line in text[i:j].splitlines():
        if line.startswith("|") and not line.startswith("| product") and "---" not in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 8:
                rows.append(dict(zip(["product", "field", "old", "new", "new_sha",
                                      "cause", "surfaces", "date"], cells)))
    return rows


def allow_rows(text: str | None = None) -> list[dict]:
    text = text if text is not None else REPORT.read_text()
    i, j = _block(text, ALLOW_BEGIN, ALLOW_END)
    rows = []
    for line in text[i:j].splitlines():
        if line.startswith("|") and not line.startswith("| product") and "---" not in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 5:
                rows.append(dict(zip(["product", "cell", "column", "reason", "date"], cells)))
    return rows


def sha8(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:8]


def short(s: str, n: int = 60) -> str:
    s = s.replace("|", "/").replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


def surfaces_for(field: str) -> str:
    return SURFACES[field.split(".")[0]]


def cmd_diff(a) -> int:
    rows = diffs(a.base, a.head)
    for p, f, o, n in rows:
        print(f"{p:<18} {f:<40} {short(o, 40):<42} -> {short(n, 40)}")
    print(f"\n{len(rows)} changed value(s) vs {a.base}")
    return 0


def cmd_write(a) -> int:
    text = REPORT.read_text()
    have = {(r["product"], r["field"], r["new_sha"]) for r in corr_rows(text)}
    added = []
    import re as _re
    only = _re.compile(a.only) if getattr(a, "only", None) else None
    for p, f, o, n in diffs(a.base, a.head):
        if (p, f, sha8(n)) in have:
            continue
        # --only narrows one write to the fields a task changed, so each
        # row carries the cause of the task that moved it
        if only and not only.search(f):
            continue
        added.append(f"| {p} | {f} | {short(o)} | {short(n)} | {sha8(n)} | "
                     f"{a.cause} | {surfaces_for(f)} | {record_as_of()} |")
    if not added:
        print("nothing new to log")
        return 0
    i, j = _block(text, CORR_BEGIN, CORR_END)
    body = text[i:j].rstrip("\n")
    text = text[:i] + body + "\n" + "\n".join(added) + "\n" + text[j:]
    REPORT.write_text(text)
    print(f"logged {len(added)} correction row(s) under '{a.cause}'")
    return 0


def cmd_check(a) -> int:
    text = REPORT.read_text()
    have = {(r["product"], r["field"], r["new_sha"]) for r in corr_rows(text)}
    missing = [(p, f, o, n) for p, f, o, n in diffs(a.base)
               if (p, f, sha8(n)) not in have]
    for p, f, o, n in missing:
        print(f"[FAIL] unlogged change: {p} {f}: {short(o, 40)} -> {short(n, 40)}")
    if missing:
        print(f"\n{len(missing)} changed published number(s) have no row under "
              f"'Corrections 2026-09' in {REPORT.relative_to(BASE)}. Run: "
              f"python src/corrections_log.py write --cause '<task id>: <cause>'")
        return 1
    print(f"[ok]   corrections log: every changed published number vs {a.base} is logged")
    return 0


def add_allow_row(product: str, cell: str, column: str, reason: str, report: Path | None = None) -> bool:
    """One row in the report's evidence allowlist block. A row is keyed by
    product, cell, column and reason, so a second reason for the same
    column is a second row. Returns False when the row is already there."""
    path = report or REPORT
    text = path.read_text()
    i, j = _block(text, ALLOW_BEGIN, ALLOW_END)
    row = f"| {product} | {cell} | {column} | {reason} | {record_as_of()} |"
    if row.split("|")[1:5] in [r.split("|")[1:5] for r in text[i:j].splitlines()]:
        return False
    body = text[i:j].rstrip("\n")
    path.write_text(text[:i] + body + "\n" + row + "\n" + text[j:])
    return True


def cmd_allow(a) -> int:
    if add_allow_row(a.product, a.cell, a.column, a.reason):
        print("allowlisted", a.product, a.cell, a.column)
    else:
        print("already allowlisted")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("diff", "write", "check"):
        s = sub.add_parser(name)
        s.add_argument("--base", default="origin/main")
        if name in ("diff", "write"):
            # --head logs the state at a past commit, so a change a later
            # commit built on can still be attributed to the task that made it
            s.add_argument("--head", default=None)
        if name == "write":
            s.add_argument("--cause", required=True)
            s.add_argument("--only", default=None,
                           help="regex over the field name: log only the matching changed values")
    s = sub.add_parser("allow")
    for f in ("product", "cell", "column", "reason"):
        s.add_argument(f"--{f}", required=True)
    a = ap.parse_args()
    return {"diff": cmd_diff, "write": cmd_write, "check": cmd_check,
            "allow": cmd_allow}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

"""Docs gate: the runbook and the queue agree with the hook, the record and
the app. Run: python src/test_docs.py

Every number a document states about the build is derived here from its
source of truth (hooks/pre-commit, data/, site/js/main.js), so a stale
document fails the commit instead of reaching a meeting.
"""
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))
from tark_data import load_product, product_keys  # noqa: E402

FAILS: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}"
          f"{(': ' + extra) if extra and not cond else ''}")
    if not cond:
        FAILS.append(name)


hook = (BASE / "hooks" / "pre-commit").read_text()
gate_stems = [m.split("/")[-1] for m in
              re.findall(r"^python src/([\w/]+)\.py", hook, re.M)]
# markdown wraps sentences, so every phrase search runs on whitespace-
# normalized text
runbook = re.sub(r"\s+", " ", (BASE / "docs" / "INVESTOR_DEMO.md").read_text())

# ---- gates: one count, equal to the hook, every gate named in hook order
counts = re.findall(r"runs (\d+) gates", runbook)
check("runbook states the gate count exactly once", len(counts) == 1)
check("runbook gate count equals the hook",
      bool(counts) and int(counts[0]) == len(gate_stems),
      f"{counts} vs {len(gate_stems)}")
head = "## What is enforced by machines"
sect = runbook[runbook.index(head) + len(head):]
sect = sect.split(" ## ")[0]
pos = [sect.find(f"`{s}`") for s in gate_stems]
check("runbook names every gate, in hook order",
      all(p >= 0 for p in pos) and pos == sorted(pos),
      ", ".join(s for s, p in zip(gate_stems, pos) if p < 0) or "order")
check("hook runs the copy gate and this gate",
      "test_copy" in gate_stems and "test_docs" in gate_stems)

# ---- roster and views
m = re.search(r"\*\*Roster:\*\* (\d+) products", runbook)
check("runbook roster count equals the record",
      bool(m) and int(m.group(1)) == len(product_keys()),
      f"{m and m.group(1)} vs {len(product_keys())}")
main_js = (BASE / "site" / "js" / "main.js").read_text()
default_view = re.search(r'\bview: "(\w+)"', main_js).group(1)
views = re.findall(r'^\s*\["(\w+)", "([^"]+)", view\w+, "\w+"\]', main_js, re.M)
labels = dict(views)
check("runbook lands on the app's default view",
      f"**{labels[default_view]}**" in runbook, labels[default_view])
m = re.search(r"all (\d+) views", runbook)
check("runbook view count equals main.js",
      bool(m) and int(m.group(1)) == len(views),
      f"{m and m.group(1)} vs {len(views)}")

# ---- census numbers the runbook says out loud (validator-enforced T1)
census = json.loads((BASE / "data" / "census" / "census.json").read_text())
uni = json.loads((BASE / "data" / "census" / "universe.json").read_text())
check("runbook universe total equals the census",
      f"{census['total']:,} registered wrappers" in runbook)
PHRASE = {"interval_23c3": "{n} interval", "tender_cef": "{n} tender CEF",
          "bdc": "{n} BDC", "nontraded_reit": "{n} non-traded REIT",
          "listed_cef": "{n} listed CEF",
          "unlisted_cef_other": "{n} unlisted CEF other",
          "nontraded_34act_other": "{n} reconciled '34-Act"}
for cls, n in census["counts_by_class"].items():
    check(f"runbook class count for {cls} equals the census",
          PHRASE[cls].format(n=f"{n:,}") in runbook)
dark_n = next(v for v in uni["dark_universe"].values() if isinstance(v, int))
check("runbook dark-universe count equals universe.json",
      f"{dark_n:,} Form D pooled funds" in runbook)
check("runbook states the census as-of date", census["as_of"] in runbook)
check("runbook labels the universe counts validator-enforced, not human-verified",
      "validator-enforced T1 counts, not human-verified" in runbook)

# ---- no memorized record percentages in the runbook
check("runbook carries no record coverage percentages",
      not re.search(r"\d+% (evidenced|computed|documented)", runbook))

# ---- deleted files and the README
# the operational documents must not point a reader at a deleted file; the
# audit, the decisions log and the build reports record the deletion itself
LIVING = ["README.md", "docs/INVESTOR_DEMO.md", "docs/demo_script.md",
          "docs/verification_queue.md"]
for name in ("hook_snapshot.txt", "README_SPIKE.md", "src/seed_case_law_cell.py"):
    check(f"{name} is gone", not (BASE / name).exists())
    refs = [d for d in LIVING if name in (BASE / d).read_text()]
    check(f"no operational document references {name}", not refs, ", ".join(refs))
readme = (BASE / "README.md").read_text()
check("README names the decisions log and the audit",
      "DECISIONS_2026-09.md" in readme and "GAP_ANALYSIS_2026-09-03.md" in readme)

# ---- the verification queue names what the record has at structured
queue = (BASE / "docs" / "verification_queue.md").read_text()
structured = [(k, cid) for k in product_keys()
              for cid, c in load_product(k)["cells"].items()
              if str(c.get("status", "")).startswith("structured")]
for k, cid in structured:
    check(f"queue names the structured cell {k} {cid}", f"{k} {cid}" in queue)
m = re.search(r"record carries (\d+) `structured` cell", queue)
check("queue states the structured count the record has",
      bool(m) and int(m.group(1)) == len(structured),
      f"{m and m.group(1)} vs {len(structured)}")

# ---- the demo script version is one number, named the same everywhere
script = (BASE / "docs" / "demo_script.md").read_text()
sv = re.search(r"Demo Script v(\d+)", script)
qv = re.search(r"demo_script\.md` \(v(\d+)\)", queue)
rv = re.search(r"demo_script\.md` \(v(\d+),", runbook)
check("verification queue Tier 1 is derived from the current demo script version",
      bool(sv and qv) and sv.group(1) == qv.group(1),
      f"script v{sv and sv.group(1)} vs queue v{qv and qv.group(1)}")
check("runbook names the current demo script version",
      bool(sv and rv) and sv.group(1) == rv.group(1),
      f"script v{sv and sv.group(1)} vs runbook v{rv and rv.group(1)}")
check("demo script carries a surface-check block for the frontend gate",
      "## Surface checks" in script and script.count("\n- ") >= 20)
check("deploy log exists and names the pre-deploy EDGAR URL check",
      (BASE / "docs" / "DEPLOY_LOG.md").exists()
      and "check_edgar_urls.py" in (BASE / "docs" / "DEPLOY_LOG.md").read_text())

# ---- superseded claims stay marked
br4 = (BASE / "docs" / "BUILD_REPORT_4.md").read_text()
check("BUILD_REPORT_4 Lane C claim is marked superseded",
      "Lane C fed" in br4 and "Superseded (2026-09)" in br4)

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nDocs agree with the hook, the record and the app.")
sys.exit(1 if FAILS else 0)

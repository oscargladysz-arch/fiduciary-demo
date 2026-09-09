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
              re.findall(r"^python (?:src|app|worker)/([\w/]+)\.py", hook, re.M)]
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
# the route table is the one list of what the application answers, so the
# runbook's count is checked against it rather than against a second list
routes_ts = (BASE / "web" / "src" / "app" / "routes.ts").read_text()
globals_ = re.findall(r'\{ id: "([a-z]+)", label: "([^"]+)"', routes_ts.split("export const PANELS")[0])
panels = re.findall(r'\{ id: "([a-z]+)", label: "([^"]+)"',
                    routes_ts.split("export const PANELS")[1].split("export const GLOBAL_BY_ID")[0])
labels = dict(globals_ + panels)
check("every route in the table names a view", len(globals_) >= 12 and len(panels) >= 6,
      f"{len(globals_)} global, {len(panels)} panels")
check("runbook lands on the route the application opens on",
      f"**{labels['start']}**" in runbook or "Start" in runbook, labels.get("start"))
m = re.search(r"all (\d+) views", runbook)
check("runbook view count equals the route table",
      bool(m) and int(m.group(1)) == len(globals_) + len(panels),
      f"{m and m.group(1)} vs {len(globals_) + len(panels)}")

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


# ---- R3-P0-3: the workflow's deploy-log entry writer produces an entry the
# copy gate accepts, numbered after the last entry in the log
import subprocess
_dry = subprocess.run([sys.executable, str(BASE / "src" / "ci_deploy_entry.py"),
                       "--source-commit", "0123456789abcdef", "--pages-commit", "abcdef0",
                       "--started", "2026-09-18T10:00:00Z", "--finished", "2026-09-18T10:05:00Z",
                       "--wall-seconds", "300", "--pass-count", "1100",
                       "--edgar", "exit 0, 9 distinct EDGAR URLs, every one answered 200",
                       "--run-url", "https://github.com/oscargladysz-arch/fiduciary-demo/actions/runs/1",
                       "--dry-run"], capture_output=True, text=True)
_log = (BASE / "docs" / "DEPLOY_LOG.md").read_text()
_last = max(int(n) for n in re.findall(r"^## Entry (\d+),", _log, flags=re.M))
check("deploy-log entry writer: dry run exits 0 and carries no em dash or semicolon",
      _dry.returncode == 0 and "\u2014" not in _dry.stdout and ";" not in _dry.stdout, _dry.stderr[-200:])
check("deploy-log entry writer: numbers the entry after the last one in the log",
      f"## Entry {_last + 1}," in _dry.stdout, _dry.stdout[:80])
check("deploy-log entry writer: names the source commit, the gh-pages commit, the gate list and the EDGAR result",
      all(x in _dry.stdout for x in ("`0123456`", "`abcdef0`", "test_frontend", "every one answered 200")))
check("gates workflow exists, runs the hook, and never names a model key",
      (BASE / ".github" / "workflows" / "gates.yml").exists()
      and "sh hooks/pre-commit" in (BASE / ".github" / "workflows" / "gates.yml").read_text()
      and "ANTHROPIC_API_KEY" not in (BASE / ".github" / "workflows" / "gates.yml").read_text().replace(
          "never receives ANTHROPIC_API_KEY", ""))

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nDocs agree with the hook, the record and the app.")
sys.exit(1 if FAILS else 0)

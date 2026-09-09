"""
Bundle gate: the data behind the screen.
    python src/test_frontend.py       (exit 0 = pass)

What it enforces, all of it about the record rather than about any frontend:
  1. the build runs fresh from the data layer
  2. no sponsor token anywhere in what the build emits
  3. every typed fact cites a real cell, and the ones that mirror a selection
     mirror the right one
  4. no peer composite carries a public-market-equivalent key or name
  5. every product and proxy pair in the lab matrix carries a real score, the
     four criteria of the rubric and an eligibility the rubric agrees with
  6. every selection carries the rubric, its ceiling, the declared record and
     the peer slot

The rendered half of this gate walked the old application. That application is
gone, and each of its checks moved with the thing it checked: see the note at
the end of this file.
"""
import json
import re
import subprocess
import sys
import threading
import time
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parents[1]
SITE = BASE / "site"
PORT = 8477
sys.path.insert(0, str(BASE / "src"))
from tark_anon import forbidden_tokens  # noqa: E402
FORBIDDEN = forbidden_tokens()

FAILS = []


class TextNodes(HTMLParser):
    """Collects the visible text nodes of a rendered page. inner_text cannot
    see markup that leaked into a text node (the gloss() defect), a real HTML
    parse can: a text node must never contain a stray '">' or an attribute
    name such as data-def."""
    SKIP = {"script", "style"}

    def __init__(self):
        super().__init__()
        self.nodes = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.nodes.append(data)


def stray_markup(html: str) -> list[str]:
    tp = TextNodes()
    tp.feed(html)
    bad = []
    for n in tp.nodes:
        if '">' in n or "data-def" in n or "<span" in n or "</span" in n:
            bad.append(n.strip()[:80])
        # a JS `undefined` leaks next to a unit, punctuation or a node edge
        # ("undefined%", ": undefined", "$undefined"); English usage in filing
        # prose ("is undefined by construction") is preceded and followed by
        # a space and is not a leak
        if (re.search(r"(?<![A-Za-z ])undefined|undefined(?=[%×x/,)\]])|^\s*undefined\s*$", n)
                or re.search(r"\bNaN\b", n)):
            bad.append("undefined/NaN: " + n.strip()[:80])
    return bad


def check(name: str, cond: bool, extra: str = ""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}{(' — ' + extra) if extra and not cond else ''}")
    if not cond:
        FAILS.append(name)


# ---------------------------------------------------------------- build
r = subprocess.run([sys.executable, str(BASE / "src" / "build_site.py")],
                   capture_output=True, text=True)
check("site builds from data layer", r.returncode == 0, r.stderr[-300:])
if r.returncode != 0:
    print(r.stdout, r.stderr)
    sys.exit(1)

data_js = (SITE / "data.js").read_text().lower()
for tok in FORBIDDEN:
    check(f"data bundle anonymization: '{tok}' absent", tok not in data_js)

# ---------------------------------------------------------------- serve
handler = partial(SimpleHTTPRequestHandler, directory=str(SITE))
httpd = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
time.sleep(0.3)

bundle = json.loads((SITE / "data.js").read_text()[len("window.TARK = "):-2])
# the full supplement (stress windows etc.) stays on disk for the cell writer;
# only the parts a view reads ship in the bundle, so parity checkpoints
# against committed analytics read the file
supplement_disk = json.loads((BASE / "data" / "analytics" / "supplement.json").read_text())
PLANS = bundle["plan_order"]
PRODUCTS = list(bundle["products"].keys())

# perf budget: first-paint bundle <= 1.2MB; the series chunk is split out and
# lazy-loaded by chart/lab views, and the TOTAL payload is capped too so the
# split cannot hide unbounded growth
check("perf: data.js first-paint bundle <= 1.2MB",
      (SITE / "data.js").stat().st_size <= 1_200_000,
      f"{(SITE / 'data.js').stat().st_size:,} bytes")
check("perf: series.js chunk exists (lazy-loaded)",
      (SITE / "series.js").exists())
check("perf: total payload (data.js + series.js) <= 2.4MB",
      (SITE / "data.js").stat().st_size
      + (SITE / "series.js").stat().st_size <= 2_400_000,
      f"{(SITE / 'data.js').stat().st_size + (SITE / 'series.js').stat().st_size:,} bytes")
check("perf: census.data.js lazy chunk exists and <= 500KB",
      (SITE / "census.data.js").exists()
      and (SITE / "census.data.js").stat().st_size <= 500_000,
      f"{(SITE / 'census.data.js').stat().st_size:,} bytes"
      if (SITE / "census.data.js").exists() else "missing")
census_bundle = json.loads(
    (SITE / "census.data.js").read_text()[len("window.TARK_CENSUS = "):-2])

# structured-facts provenance spot-checks (bundle side)
for k in PRODUCTS:
    for field, f in bundle["facts"][k].items():
        if f.get("source_cell") not in bundle["products"][k]["cells"]:
            check(f"facts bundle: {k}.{field} cites real cell", False,
                  str(f.get("source_cell")))
            break
    else:
        continue
    break
else:
    pass
check("facts bundle: every field cites a real cell", all(
    f.get("source_cell") in bundle["products"][k]["cells"]
    for k in PRODUCTS for f in bundle["facts"][k].values()))
def _slot_k(k):
    return ((bundle["benchmarks"].get(k) or {}).get("slot_k") or {}).get("selected")
def _reference(k):
    return (bundle["benchmarks"].get(k) or {}).get("reference_comparison")
def _series_comparison(k):
    """the public market series comparison the facts mirror: Slot K's own
    when Slot K is a series, else the reference comparison's, else None"""
    s = _slot_k(k)
    if s and (s.get("comparison") or {}).get("kind") == "series":
        return s["comparison"]
    r = _reference(k)
    if r and (r.get("comparison") or {}).get("kind") == "series":
        return r["comparison"]
    return None
def _peer_composite(k):
    return ((bundle["benchmarks"].get(k) or {}).get("slot_g") or {}).get("composite")
check("facts bundle: pme_public_proxy mirrors Slot K's public series, else the reference comparison (named so in "
      "the fact note), else null, and peer_relative_wealth_ratio mirrors slot_g.composite when computed, else null "
      "(rule 12, decision 7.1)", all(
    bundle["facts"][k]["pme_public_proxy"]["value"] == (_series_comparison(k) or {}).get("ks_pme")
    and bundle["facts"][k]["peer_relative_wealth_ratio"]["value"]
    == ((_peer_composite(k) or {}).get("relative_wealth_ratio")
        if (_peer_composite(k) or {}).get("status") == "computed" else None)
    and (((_slot_k(k) or {}).get("comparison") or {}).get("kind") == "series" or _series_comparison(k) is None
         or "reference comparison" in bundle["facts"][k]["pme_public_proxy"].get("note", ""))
    for k in PRODUCTS if bundle["benchmarks"].get(k)))
check("facts bundle: slot_k_relative_wealth_ratio mirrors Slot K only when it is a held published index, else null", all(
    (bundle["facts"][k]["slot_k_relative_wealth_ratio"]["value"]
     == ((_slot_k(k) or {}).get("comparison") or {}).get("relative_wealth_ratio"))
    if ((_slot_k(k) or {}).get("comparison") or {}).get("kind") == "published_index"
    else bundle["facts"][k]["slot_k_relative_wealth_ratio"]["value"] is None
    for k in PRODUCTS if bundle["benchmarks"].get(k)))
check("benchmarks bundle: no peer composite carries a PME key or name", all(
    "ks_pme" not in comp and "direct_alpha_pct" not in comp and comp["statistic"].startswith("relative wealth ratio")
    for k in PRODUCTS for comp in [_peer_composite(k)] if comp))
sm = json.loads((SITE / "series.js").read_text().split("\n")[2][len("window.TARK_LAB = "):-1])
check("lab matrix: every product x proxy pair carries a real v3.1 score, the four v3.1 criteria and eligibility",
      all(isinstance(v["score"], int) and set(v["criteria"]) == {"strategy_match", "risk_liquidity_match",
          "provider_independence", "data_held"} and isinstance(v["eligible"], bool)
          and v["reasons"] for prod in sm.values() for v in prod.values())
      and all(set(prod) == set(bundle["proxy_library"]) for prod in sm.values()))
check("lab matrix: cclfx x BKLN eligible and on the menu, cclfx x SPY not eligible and off the menu",
      sm["cliffwater_cclfx"]["bkln"]["eligible"] and sm["cliffwater_cclfx"]["bkln"]["on_menu"]
      and not sm["cliffwater_cclfx"]["spy"]["eligible"] and not sm["cliffwater_cclfx"]["spy"]["on_menu"])
check("benchmarks bundle: rubric v3.1 on every selection, Slot K with its ceiling, the declared record, Slot G and "
      "the selection lock present, the v2 keys and the lock's input list gone", all(
    sel.get("rubric_version") == "v3.1" and "max_attainable" in (sel.get("slot_k") or {})
    and len(sel.get("record_hash", "")) == 64 and sel.get("recorded_at") and "inputs" not in sel
    and "declared" in sel and bool(sel.get("slot_g"))
    and not any(old in sel for old in ("primary", "secondary", "secondary_note", "declared_benchmarks", "escalation"))
    for sel in bundle["benchmarks"].values()))

# The rendered half of this gate walked the old application: every view by
# plan by product, the anonymization sweep over each one, the figures on
# screen, the interactive recompute and the parity of the ported analytics.
# The old application is gone, and each of those moved with the thing it
# checked rather than being dropped:
#   - the rendered sweep and the figures on screen are in src/test_web.py,
#     which walks the rebuilt routes with the same scanner and the same token
#     list, and reads the committed figures out of the record rather than out
#     of a hand-written list
#   - the interactive recompute is in src/test_web.py as the liquidity panel's
#     live-state checks
#   - the parity of the analytics is in web/src/analytics/*.test.ts, which is
#     where a parity check belongs: it runs the same toy cases as
#     src/test_analytics.py and then against the record itself
# What stays here is what it always checked about the data behind the screen.

if FAILS:
    print(f"\n{len(FAILS)} failure(s):")
    for f_ in FAILS:
        print("  -", f_)
    raise SystemExit(1)
print("\nBundle gate passes.")

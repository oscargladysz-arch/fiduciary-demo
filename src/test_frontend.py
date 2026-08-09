"""
Frontend gate — Playwright (Python) e2e + JS/Python parity suite.
Ports every assertion class of src/test_app.py to the static site and adds
the interactive-feature checks. Run: python src/test_frontend.py (exit 0 = pass).

What it enforces:
  1. site builds fresh from the data layer (build_site.py) and boots clean
  2. every view x plan x product renders without JS exceptions
  3. anonymization sweep: NO sponsor token in data.js or any rendered view
  4. DXYZ escalation, CCLFX CDLI rejection, key real numbers on screen
  5. ILLUSTRATIVE label wherever scenario math shows
  6. interactive recompute: moved sliders change the numbers on screen
  7. JS<->Python parity: the ported analytics pass the SAME toy cases as
     src/test_analytics.py, and the browser reproduces the committed engine
     numbers (KS-PME/Direct Alpha) and all 24 bundled liquidity scenarios
"""
import json
import subprocess
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parents[1]
SITE = BASE / "site"
PORT = 8477
FORBIDDEN = ["spotify", "darden", "mckinsey", "goodyear"]

FAILS = []


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
PLANS = bundle["plan_order"]
PRODUCTS = list(bundle["products"].keys())
VIEWS = ["plans", "roster", "evaluation", "benchmarks", "fees", "liquidity",
         "pme", "dxyz", "desmooth", "coverage"]

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")

    check("app boots without exception", not errors, "; ".join(errors[:2]))
    check("boot view renders content",
          len(page.locator("#view").inner_text()) > 200)

    # ---------- 2+3. every view x plan x product renders, anonymized ----------
    combos_bad = []
    leak_bad = []
    for view in VIEWS:
        for plan in PLANS:
            for product in PRODUCTS:
                n_err = len(errors)
                text = page.evaluate(
                    """([v, pl, pr]) => {
                         window.tarkSetState({view: v, plan: pl, product: pr});
                         return document.getElementById('view').innerText;
                       }""", [view, plan, product])
                if len(errors) > n_err or len(text.strip()) < 40:
                    combos_bad.append(f"{view}/{plan}/{product}")
                low = text.lower()
                if any(t in low for t in FORBIDDEN):
                    leak_bad.append(f"{view}/{plan}/{product}")
    check(f"all {len(VIEWS) * len(PLANS) * len(PRODUCTS)} view x plan x product "
          f"combos render", not combos_bad, "; ".join(combos_bad[:5]))
    check("anonymization holds across every rendered combo", not leak_bad,
          "; ".join(leak_bad[:5]))

    def view_text(view, plan="plan_tech_media", product="hl_paf"):
        return page.evaluate(
            """([v, pl, pr]) => {
                 window.tarkSetState({view: v, plan: pl, product: pr});
                 return document.getElementById('view').innerText;
               }""", [view, plan, product])

    # ---------- 4. key real numbers + the two hero states ----------
    t = view_text("plans")
    check("plans: net assets $565.8M rendered", "565.8" in t)
    check("plans: avg balance $110,515 rendered", "110,515" in t)
    check("plans: liquidity tail 1,847 rendered", "1,847" in t)
    t = view_text("benchmarks", product="cliffwater_cclfx")
    check("benchmark cclfx: KS-PME 1.2519 on screen", "1.2519" in t)
    check("benchmark cclfx: CDLI sits in rejection log",
          "Cliffwater Direct Lending Index" in t)
    check("benchmark cclfx: independence rejection is truthful",
          "provider_independence 0/2" in t or "fund's own" in t)
    t = view_text("benchmarks", product="dxyz")
    check("benchmark dxyz: escalation banner shown",
          "NO MEANINGFUL BENCHMARK" in t)
    t = view_text("evaluation", product="hl_paf")
    check("evaluation hl_paf: Managed Assets fee-base trap on screen",
          "managed assets" in t.lower())
    t = view_text("evaluation", product="breit")
    check("evaluation breit: 2%/5% repurchase caps on screen",
          "2% of aggregate NAV" in t or "2% of our aggregate NAV" in t)
    t = view_text("fees")
    check("fee matrix: leverage-inclusive base flagged",
          "MANAGED ASSETS" in t and "GROSS assets" in t)
    check("fee matrix: K-1 vs 1099 row present",
          "Schedule K-1" in t and "Form 1099" in t)

    # ---------- 5. liquidity verdicts + ILLUSTRATIVE labels everywhere ----------
    t = view_text("liquidity", product="cliffwater_cclfx")
    check("liquidity cclfx: CONDITIONAL verdict", "CONDITIONAL" in t)
    check("liquidity cclfx: structural gap named", "STRUCTURAL GAP" in t)
    t = view_text("liquidity", product="breit")
    check("liquidity breit: CONDITIONAL-WEAK on gating precedent",
          "CONDITIONAL-WEAK" in t and "prorated" in t)
    t = view_text("liquidity", product="dxyz")
    check("liquidity dxyz: aligned-mechanical with premium caveat",
          "ALIGNED-MECHANICAL" in t and "premium" in t)
    t = view_text("liquidity", plan="plan_consulting_alumni",
                  product="cliffwater_cclfx")
    check("plan switch changes liquidity: consulting tail 58.2%", "58.2" in t)
    check("plan switch changes liquidity: partial-direction language",
          "PARTIALLY participant-directed" in t)
    check("plan switch changes liquidity: thin headroom fires",
          "THIN HEADROOM" in t)
    t = view_text("liquidity", plan="plan_restaurant_hourly",
                  product="cliffwater_cclfx")
    check("plan switch changes liquidity: restaurant tail 28.2%", "28.2" in t)
    ill_missing = [f"{pl}/{pr}" for pl in PLANS for pr in PRODUCTS
                   if "ILLUSTRATIVE" not in view_text("liquidity", pl, pr)]
    check("ILLUSTRATIVE label visible for all 24 liquidity combos",
          not ill_missing, "; ".join(ill_missing[:4]))

    # ---------- 6. interactive recompute sanity ----------
    view_text("pme", product="cliffwater_cclfx")
    ks0 = page.locator("#pme_ks").inner_text()
    check("pme default reproduces committed KS-PME",
          abs(float(ks0) -
              bundle["benchmarks"]["cliffwater_cclfx"]["primary"]["comparison"]["ks_pme"]) < 1e-4)
    da0 = page.locator("#pme_da").inner_text()
    check("pme default reproduces committed Direct Alpha",
          abs(float(da0.rstrip("%")) -
              bundle["benchmarks"]["cliffwater_cclfx"]["primary"]["comparison"]["direct_alpha_pct"]) < 0.01)
    page.evaluate("""() => { const s = document.getElementById('winstart');
        s.value = String(Math.floor(+s.max / 2)); s.dispatchEvent(new Event('input')); }""")
    ks1 = page.locator("#pme_ks").inner_text()
    check("pme window slider changes KS-PME", ks1 != ks0, f"{ks0} -> {ks1}")
    check("pme honest caption visible",
          "window-sensitive" in page.locator("#view").inner_text())

    view_text("pme", product="hl_paf")
    check("pme hl_paf default reproduces committed 1.9565",
          abs(float(page.locator("#pme_ks").inner_text()) - 1.9565) < 1e-4)

    view_text("liquidity", product="cliffwater_cclfx")
    d0 = page.locator("#o_dpct").inner_text()
    page.evaluate("""() => { const s = document.getElementById('s_tail');
        s.value = '45'; s.dispatchEvent(new Event('input')); }""")
    d1 = page.locator("#o_dpct").inner_text()
    check("liquidity slider changes demand", d0 != d1, f"{d0} -> {d1}")

    # ---------- 7. JS<->Python parity: same toy cases as test_analytics ----------
    toys = page.evaluate("""() => {
      const M = window.TarkMath;
      const idxUp = [["2020-01-01", 100], ["2021-01-01", 150]];
      const idxFlat = [["2020-01-01", 100], ["2021-01-01", 100]];
      const track = [["2020-01-01", -100], ["2021-01-01", 150]];
      const beat = [["2020-01-01", -100], ["2021-01-01", 180]];
      const mixed = [["2020-01-01", -100], ["2020-07-01", 30], ["2021-01-01", 90]];
      const trueSer = [0.02, -0.01, 0.03, 0.015, -0.005, 0.02, 0.01, 0.025];
      const rho = 0.4;
      const obs = [trueSer[0]];
      for (let t = 1; t < trueSer.length; t++)
        obs.push((1 - rho) * trueSer[t] + rho * obs[t - 1]);
      const [rec] = M.desmoothGeltner(obs, rho);
      return {
        pr0: M.periodReturns([100, 110, 99])[0],
        pr1: M.periodReturns([100, 110, 99])[1],
        mdd: M.maxDrawdown([100, 120, 60, 90]),
        cg: M.cumulativeGrowth([0.10, -0.10]),
        me: JSON.stringify(M.monthEndPoints([["2024-01-05", 1], ["2024-01-31", 2],
                                             ["2024-02-10", 3], ["2024-02-28", 4]])),
        xirr: M.xirr([["2020-01-01", -100], ["2021-01-01", 110]]),
        pmeTrack: M.ksPme(track, idxUp),
        daTrack: M.directAlpha(track, idxUp),
        pmeBeat: M.ksPme(beat, idxUp),
        daBeat: M.directAlpha(beat, idxUp),
        pmeFlat: M.ksPme(mixed, idxFlat),
        rec0: rec[0], recN: rec[rec.length - 1],
      };
    }""")
    check("parity: period_returns up", abs(toys["pr0"] - 0.10) < 1e-12)
    check("parity: period_returns down", abs(toys["pr1"] - -0.10) < 1e-12)
    check("parity: max_drawdown 120->60", abs(toys["mdd"] - -0.5) < 1e-12)
    check("parity: cumulative growth", abs(toys["cg"] - 0.99) < 1e-12)
    check("parity: month_end picks last of month",
          json.loads(toys["me"]) == [["2024-01-31", 2], ["2024-02-28", 4]])
    check("parity: xirr one-year 10%", abs(toys["xirr"] - 0.10) < 3e-3)
    check("parity: PME = 1 when fund tracks index",
          abs(toys["pmeTrack"] - 1.0) < 1e-12)
    check("parity: Direct Alpha = 0 when fund tracks index",
          abs(toys["daTrack"]) < 3e-3)
    check("parity: PME = 1.2 on outperformance",
          abs(toys["pmeBeat"] - 1.2) < 1e-12)
    check("parity: Direct Alpha > 0.10 on outperformance", toys["daBeat"] > 0.10)
    check("parity: PME flat-index = simple multiple",
          abs(toys["pmeFlat"] - 1.2) < 1e-12)
    check("parity: AR(1) round-trip recovers true series",
          abs(toys["rec0"] - -0.01) < 1e-12 and abs(toys["recN"] - 0.025) < 1e-12)

    # liquidity scenario parity vs all 24 bundled matches (default params)
    mism = page.evaluate("""() => {
      const out = [];
      for (const [k, m] of Object.entries(window.TARK.liquidity)) {
        const sc = m.scenario;
        const got = window.TarkLiquidity.computeScenario(
          m.plan_inputs, m.wrapper_facts, sc);
        if (Math.abs(got.demand_pct_of_position - sc.demand_pct_of_position) > 0.05 ||
            Math.abs(got.plan_allocation_usd - sc.plan_allocation_usd) > 1)
          out.push(k);
      }
      return out;
    }""")
    check("parity: JS scenario matches all 24 bundled liquidity scenarios",
          not mism, "; ".join(mism[:4]))

    # ---------- 8. citation drawer + memo artifacts ----------
    view_text("evaluation", product="hl_paf")
    page.locator("[data-cite]").first.click()
    check("citation drawer opens with verbatim quote",
          page.locator("#drawer").get_attribute("class").find("open") >= 0
          and len(page.locator("#drawer .dbody").inner_text()) > 60)

    import urllib.request
    memo_bad = []
    for k in bundle["memos"]:
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{PORT}/memos/{k}_decision_memo.docx") as resp:
                if resp.status != 200 or int(resp.headers["Content-Length"]) < 5000:
                    memo_bad.append(k)
        except Exception:  # noqa: BLE001
            memo_bad.append(k)
    check("all decision memos served", not memo_bad, "; ".join(memo_bad))

    check("no page errors across the whole run", not errors,
          "; ".join(errors[:3]))
    browser.close()

httpd.shutdown()
print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll frontend tests pass.")
sys.exit(1 if FAILS else 0)

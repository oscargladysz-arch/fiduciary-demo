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
VIEWS = ["screener", "compare", "search", "packet", "plans", "roster",
         "evaluation", "benchmarks", "fees", "liquidity", "pme", "dxyz",
         "desmooth", "coverage", "verification"]

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
check("facts bundle: pme_primary mirrors selection artifact", all(
    bundle["facts"][k]["pme_primary"]["value"] ==
    (bundle["benchmarks"][k].get("primary") or {}).get("comparison", {}).get("ks_pme")
    for k in PRODUCTS if bundle["benchmarks"].get(k, {}).get("primary")))

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")

    check("app boots without exception", not errors, "; ".join(errors[:2]))
    check("boot view renders content",
          len(page.locator("#view").inner_text()) > 200)
    check("boot does NOT load the series chunk (lazy split)",
          page.evaluate("() => !window.TARK.series"))
    # preload the series chunk for the rest of the suite so view renders stay
    # synchronous (runtime lazy-load behavior is exercised by the boot check)
    page.evaluate("""() => new Promise((res) => {
        const s = document.createElement('script');
        s.src = 'series.js';
        s.onload = () => { window.TARK.series = window.TARK_SERIES; res(true); };
        document.head.append(s);
      })""")

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
                         document.querySelectorAll('#view details').forEach(
                           (d) => { d.open = true; });
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
        # open every disclosure so hidden prose is included in the sweep —
        # anonymization and content checks must cover collapsed details too
        return page.evaluate(
            """([v, pl, pr]) => {
                 window.tarkSetState({view: v, plan: pl, product: pr});
                 document.querySelectorAll('#view details').forEach(
                   (d) => { d.open = true; });
                 return document.getElementById('view').innerText;
               }""", [view, plan, product])

    # ---------- 4. key real numbers + the two hero states ----------
    t = view_text("plans")
    check("plans: net assets $565.8M rendered", "565.8" in t)
    check("plans: avg balance $110,515 rendered", "110,515" in t)
    check("plans: liquidity tail 1,847 rendered", "1,847" in t)
    t = view_text("benchmarks", product="cliffwater_cclfx")
    check("benchmark cclfx: KS-PME 1.2532 on screen", "1.2532" in t)
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
    # every combo WITH a liquidity match must show ILLUSTRATIVE; combos whose
    # profile has not landed (cohort-tier, cell 3.1 pending) must say so
    # honestly instead — both states are asserted, neither is skipped
    ill_missing, pend_missing = [], []
    for pl in PLANS:
        for pr in PRODUCTS:
            t = view_text("liquidity", pl, pr)
            if f"{pl}__{pr}" in bundle["liquidity"]:
                if "ILLUSTRATIVE" not in t:
                    ill_missing.append(f"{pl}/{pr}")
            elif "pending" not in t.lower():
                pend_missing.append(f"{pl}/{pr}")
    check("ILLUSTRATIVE label visible for every matched liquidity combo",
          not ill_missing, "; ".join(ill_missing[:4]))
    check("matchless combos state the pending profile honestly",
          not pend_missing, "; ".join(pend_missing[:4]))

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
    d0 = page.locator("#o_reason").inner_text()
    page.evaluate("""() => { const s = document.getElementById('s_tail');
        s.value = '45'; s.dispatchEvent(new Event('input')); }""")
    d1 = page.locator("#o_reason").inner_text()
    check("liquidity slider changes demand", d0 != d1, f"{d0} -> {d1}")
    check("liquidity capacity-vs-demand visual renders",
          page.locator("#capchart svg rect").count() >= 2)
    check("liquidity stress block present",
          "Stressed demand" in page.locator("#view").inner_text())

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

    # ---------- 7b. design-pass additions ----------
    t = view_text("benchmarks", product="kkr_kpec")
    check("kkr_kpec selection exists with PSP primary",
          "Listed private equity investable proxy" in t and "0.8964" in t)
    t = view_text("benchmarks", product="breit")
    check("breit selection exists with VNQ primary",
          "Listed REIT investable proxy" in t and "0.9073" in t)
    check("breit ODCE secondary with honest data caveat",
          "ODCE" in t)
    t = view_text("desmooth", product="breit")
    check("breit de-smoothing from printed monthly NAV (rho 0.483)",
          "0.483" in t)
    check("de-smoothing availability honesty renders for annual-tier",
          "cannot run" in t.lower() or "Where this diagnostic" in t)
    t = view_text("evaluation", product="hl_paf")
    check("factor rollup strip renders", page.locator(".rollup a").count() == 6)
    check("glossary chips present",
          page.locator("#view .term").count() >= 1)
    check("evaluation product chart renders (tier-driven)",
          page.locator("#prodchart svg").count() == 1)
    t = view_text("coverage")
    check("taxonomy line on screen", "0 unresolved" in t)
    check("coverage rings render (one per roster product)",
          page.locator("#prodrings .ring").count() == len(PRODUCTS))
    check("taxonomy donut renders", page.locator("#taxdonut svg").count() == 1)
    t = view_text("fees")
    check("fee bar chart renders", page.locator("#feechart svg").count() == 1)
    t = view_text("benchmarks", product="dxyz")
    check("escalation renders as formal notice",
          page.locator(".notice .notice-head").count() == 1)

    # ---------- 7c. workbench: screener / compare / lab / palette / URLs ----------
    page.evaluate("""() => window.tarkSetState({view: 'screener', f_tax: 'K-1'})""")
    krows = page.evaluate("""() =>
      [...document.querySelectorAll('table.screener tbody tr')]
        .map(r => r.innerText.split('\\t')[0])""")
    check("screener: tax_form=K-1 filter returns exactly kkr_kpec",
          len(krows) == 1 and "KKR" in krows[0], str(krows))
    page.evaluate("""() => window.tarkSetState({f_tax: '', f_base: 'managed_assets'})""")
    mrows = page.evaluate("""() =>
      document.querySelectorAll('table.screener tbody tr').length""")
    # the cohort roster changed this answer honestly: ares_pmf shares the
    # Managed Assets base with hl_paf (both 1.40% leverage-inclusive)
    check("screener: fee-base=managed_assets returns exactly hl_paf + ares_pmf",
          mrows == 2)
    page.evaluate("""() => window.tarkSetState({f_base: '', f_vonly: '1'})""")
    check("screener: verified-only renders the honest progress line",
          "verification in progress" in page.locator("#view").inner_text())
    page.evaluate("""() => window.tarkSetState({f_vonly: ''})""")

    t = view_text("compare")
    page.evaluate("""() => window.tarkSetState({view: 'compare', compare: 'hl_paf,breit'})""")
    check("compare: renders side-by-side with material differences",
          page.evaluate("""() => document.querySelectorAll('td.diff').length""") > 5)
    check("compare: fee-base trap flagged red",
          page.evaluate("""() => document.querySelectorAll('td.trap').length""") >= 1)
    check("compare: URL carries only keys/ids",
          page.evaluate("""() => decodeURIComponent(location.hash)""")
          .count("compare=hl_paf,breit") == 1)

    # URL round-trip: encode -> reload -> identical view
    page.goto(f"http://127.0.0.1:{PORT}/#view=compare&compare=hl_paf,breit"
              f"&plan=plan_consulting_alumni", wait_until="networkidle")
    rt = page.locator("#view").inner_text()
    check("URL round-trip: compare view restored after reload",
          "Comparison" in rt and "HL PAF" in rt and "BREIT" in rt)
    page.goto(f"http://127.0.0.1:{PORT}/#view=pme&product=cliffwater_cclfx"
              f"&proxy=spy", wait_until="networkidle")
    check("URL round-trip: lab proxy restored; off-menu verdict shown",
          "Off the engine's menu" in page.locator("#verdictcard").inner_text())
    # sponsor sweep over generated URLs
    url_now = page.evaluate("() => location.href").lower()
    check("URL contains no sponsor token",
          not any(tok in url_now for tok in FORBIDDEN))
    page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")

    # benchmark swap: engine verdict beside user choice; recompute differs
    view_text("pme", product="cliffwater_cclfx")
    ks_bkln = page.locator("#pme_ks").inner_text()
    page.evaluate("""() => window.tarkSetState({proxy: 'spy'})""")
    ks_spy = page.locator("#pme_ks").inner_text()
    check("benchmark swap changes the number", ks_bkln != ks_spy,
          f"{ks_bkln} vs {ks_spy}")
    check("swap lab: USER-CONFIGURED label visible",
          "USER-CONFIGURED" in page.locator("#view").inner_text())
    page.evaluate("""() => window.tarkSetState({proxy: ''})""")
    view_text("pme", product="breit")
    check("breit lab: annual-tier PME vs VNQ reproduces engine 0.9073",
          abs(float(page.locator("#pme_ks").inner_text()) - 0.9073) < 1e-4)
    check("breit lab: annual granularity honestly labeled",
          "fiscal" in page.locator("#pmenote").inner_text().lower())
    view_text("pme", product="dxyz")
    check("dxyz lab: price-series warning shown",
          "Price-series warning" in page.locator("#view").inner_text())

    # rho override
    page.evaluate("""() => window.tarkSetState({view: 'desmooth', product: 'breit', rho: ''})""")
    v0 = page.locator("#view").inner_text()
    page.evaluate("""() => window.tarkSetState({rho: '0.20'})""")
    v1 = page.locator("#view").inner_text()
    check("rho override recomputes and is labeled USER OVERRIDE",
          "USER OVERRIDE" in v1 and v0 != v1)
    page.evaluate("""() => window.tarkSetState({rho: ''})""")

    # palette entries
    pal = page.evaluate("""() => ({
      cmp: window.tarkPalette.entries('compare hl_paf breit')[0].label,
      cell: (window.tarkPalette.entries('2.7 kkr').find(x => x.kind === 'cell') || {}).label || 'MISS',
      view: (window.tarkPalette.entries('screener').find(x => x.kind === 'view') || {}).label || 'MISS',
    })""")
    check("palette: compare command", "Compare" in pal["cmp"])
    check("palette: cell jump entry", "2.7" in pal["cell"] and "KKR" in pal["cell"])
    check("palette: view jump entry", pal["view"] == "Screener")

    # verification view mirrors the queue
    view_text("verification")
    qrows = page.evaluate("""() =>
      document.querySelectorAll('table.grid tbody tr').length""")
    check("verification view renders the full queue",
          qrows == len(bundle["verification_queue"]["queue"]))

    # ---------- 7d. parity: new math toys + committed real-data checkpoints ----------
    wb = page.evaluate("""() => {
      const M = window.TarkMath;
      const cal = M.calendarYearReturns([["2023-01-31", 100], ["2023-12-29", 110],
        ["2024-06-28", 120], ["2024-12-31", 99]]);
      const eps = M.drawdownEpisodes([["d1", 100], ["d2", 120], ["d3", 60],
        ["d4", 90], ["d5", 130], ["d6", 110]], 3);
      const rr = M.rollingReturns([0.10, -0.10, 0.10], 2);
      // committed real-data checkpoints
      const T = window.TARK;
      const bre = T.series_monthly.breit_nav.filter(([d]) => d <= "2025-12-31");
      const dd = M.maxDrawdown(bre.map(([, v]) => v));
      const cc22 = T.series.cclfx.filter(([d]) => d >= "2022-01-01" && d <= "2022-12-31");
      const ccRet = cc22[cc22.length - 1][1] / cc22[0][1] - 1;
      return {
        cal2023: cal[0][1], cal2024: cal[1][1],
        dd0: eps[0].depth, dd0peak: eps[0].peak_date, dd1rec: eps[1].recovery_date,
        rr0: rr[0],
        beta2: M.beta([0.02, -0.04, 0.06], [0.01, -0.02, 0.03]),
        breitDD: dd * 100, cclfx22: ccRet * 100,
      };
    }""")
    check("parity: calendar 2023 +10%", abs(wb["cal2023"] - 0.10) < 1e-12)
    check("parity: calendar 2024 -10%", abs(wb["cal2024"] - -0.10) < 1e-12)
    check("parity: deepest drawdown -50% at d2", abs(wb["dd0"] - -0.5) < 1e-12
          and wb["dd0peak"] == "d2")
    check("parity: unrecovered episode is null", wb["dd1rec"] is None)
    check("parity: rolling window compound", abs(wb["rr0"] - -0.01) < 1e-12)
    check("parity: beta of 2x = 2", abs(wb["beta2"] - 2.0) < 1e-12)
    check("checkpoint: breit NAV-path max drawdown matches committed -7.93",
          abs(wb["breitDD"] -
              bundle["supplement"]["breit_monthly_diagnostics"]["nav_path_max_drawdown_pct"]) < 0.01,
          str(wb["breitDD"]))
    check("checkpoint: cclfx CY2022 return matches committed supplement value",
          abs(wb["cclfx22"] -
              bundle["supplement"]["stress_windows"]["cliffwater_cclfx"]["cy2022_rate_shock"]["return_pct"]) < 0.01,
          str(wb["cclfx22"]))

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

    # ---------- cohort layer (C4) ----------
    t = view_text("cohorts")
    check("cohort page renders with caveats + rationale + exclusion log",
          "Comparability caveats" in t and "Membership rationales" in t
          and "Exclusion log" in t)
    check("cohort range bars render",
          page.locator(".rangerow").count() >= 3)
    t = page.evaluate("""() => { window.tarkSetState({view: 'cohorts',
        cohort: 'venture'}); return document.getElementById('view').innerText; }""")
    check("venture cohort shows the composite REFUSAL honestly",
          "composite refused" in t.lower()
          and "refused, not fudged" in t.lower().replace("\n", " "))
    t = page.evaluate("""() => { window.tarkSetState({view: 'cohorts',
        cohort: 'evergreen_pe'}); return document.getElementById('view').innerText; }""")
    check("evergreen cohort carries the kkr fallback note",
          "authorized fallback" in t)
    # R4 phrasing law over the BUNDLE: no ordinal-percentile language for
    # members of n<4 cohorts (evergreen n=5 members may use it)
    import re as _re
    small_cohorts = [c for c, d in bundle["cohorts"].items() if d["n"] < 4]
    r4_bad = []
    for k, meta in bundle["facts_meta"].items():
        if meta.get("cohort_id") in small_cohorts:
            v29 = str(bundle["products"][k]["cells"]["2.9"].get("value") or "")
            if _re.search(r"\d+(st|nd|rd|th) percentile", v29):
                r4_bad.append(k)
    check("R4: no ordinal percentile phrasing in n<4 cohort placements",
          not r4_bad, "; ".join(r4_bad))
    check("R4: evergreen (n=5) placements DO use percentile language",
          _re.search(r"\d+(st|nd|rd|th) percentile",
                     str(bundle["products"]["hl_paf"]["cells"]["2.9"]["value"])) is not None)
    # screener cohort filter correctness
    page.evaluate("""() => window.tarkSetState({view: 'screener',
        f_cohort: 'private_credit', f_base: '', f_tax: ''})""")
    pc_rows = page.evaluate("""() =>
        document.querySelectorAll('table.screener tbody tr').length""")
    check("screener: cohort filter private_credit returns exactly 3", pc_rows == 3)
    page.evaluate("""() => window.tarkSetState({f_cohort: '', f_depth: 'cohort'})""")
    d_rows = page.evaluate("""() =>
        document.querySelectorAll('table.screener tbody tr').length""")
    check("screener: depth=cohort returns exactly the 8 cohort-tier products",
          d_rows == 8, str(d_rows))
    page.evaluate("""() => window.tarkSetState({f_depth: ''})""")
    # DXYZ/NSLR exhibit
    view_text("dxyz")
    check("premium-pattern exhibit renders (NSLR panel + chart)",
          page.locator("#nslrpanel svg").count() == 1
          and "DISCOUNT" in page.locator("#nslrpanel").inner_text())
    # compare peer-suggest + cross-wrapper caveats
    page.evaluate("""() => window.tarkSetState({view: 'compare',
        compare: 'cliffwater_cclfx,bcred'})""")
    t = page.locator("#view").inner_text()
    check("cross-wrapper comparison surfaces caveats automatically",
          "Cross-wrapper comparison" in t and "LEVERAGE-REGIME MIX" in t)

    check("no page errors across the whole run", not errors,
          "; ".join(errors[:3]))
    browser.close()

httpd.shutdown()
print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll frontend tests pass.")
sys.exit(1 if FAILS else 0)

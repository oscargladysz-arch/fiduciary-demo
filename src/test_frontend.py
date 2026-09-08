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
     numbers (KS-PME/Direct Alpha) and every bundled liquidity scenario
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
VIEWS = ["screener", "compare", "search", "packet", "plans", "roster",
         "evaluation", "benchmarks", "cohorts", "fees", "liquidity", "pme",
         "dxyz", "desmooth", "coverage", "verification"]
# census views ignore plan/product context — swept once each (renders +
# anonymization), not across the full combo grid
CENSUS_VIEWS = ["census", "funnel"]
# the two lists together must be every view main.js registers, so a new
# view cannot ship unswept
APP_VIEW_IDS = re.findall(r'^\s*\["(\w+)", "[^"]+", view\w+, "\w+"\]',
                          (SITE / "js" / "main.js").read_text(), re.M)
check("sweep covers every view registered in main.js",
      bool(APP_VIEW_IDS) and set(VIEWS) | set(CENSUS_VIEWS) == set(APP_VIEW_IDS),
      f"registered {len(APP_VIEW_IDS)}, missing "
      f"{sorted(set(APP_VIEW_IDS) - set(VIEWS) - set(CENSUS_VIEWS))}")

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

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    # record every bundle key a view actually reads: window.TARK and the
    # lazy chunks are wrapped in a Proxy the moment the bundle scripts assign
    # them (before any module captures a reference). A key is dead only if
    # the whole sweep never reads it.
    page.add_init_script("""
      // the set survives the share-link reloads later in the sweep: it is
      // parked in sessionStorage on pagehide and reloaded on init
      let prior = [];
      try { prior = JSON.parse(sessionStorage.getItem('__tarkReads') || '[]'); } catch (e) {}
      window.__tarkReads = new Set(prior);
      window.addEventListener('pagehide', () => {
        try { sessionStorage.setItem('__tarkReads', JSON.stringify([...window.__tarkReads])); } catch (e) {}
      });
      const NESTED = new Set(['supplement', 'metrics', 'series_monthly', 'series_quarterly',
                              'series', 'liquidity', 'daily_series']);
      const wrap = (obj, prefix) => new Proxy(obj, {
        get(t, k, r) {
          const v = Reflect.get(t, k, r);
          if (typeof k === 'string') {
            window.__tarkReads.add(prefix + k);
            if (!prefix && NESTED.has(k) && v && typeof v === 'object') return wrap(v, k + '.');
          }
          return v;
        },
        has(t, k) { if (typeof k === 'string') window.__tarkReads.add(prefix + k); return Reflect.has(t, k); },
        ownKeys(t) { for (const k of Object.keys(t)) window.__tarkReads.add(prefix + k); return Reflect.ownKeys(t); },
      });
      for (const name of ['TARK', 'TARK_SERIES', 'TARK_LIQ', 'TARK_LAB', 'TARK_EVIDENCE', 'TARK_CENSUS']) {
        let store;
        Object.defineProperty(window, name, {
          configurable: true,
          get() { return store; },
          set(v) { store = (v && typeof v === 'object')
            ? wrap(v, name === 'TARK' ? '' : name === 'TARK_SERIES' ? 'series.'
                                        : name === 'TARK_LIQ' ? 'liquidity.'
                                        : name === 'TARK_LAB' ? 'lab.'
                                        : name === 'TARK_EVIDENCE' ? 'evidence.' : 'census.')
            : v; },
        });
      }
    """)
    page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")

    check("app boots without exception", not errors, "; ".join(errors[:2]))
    check("boot view renders content",
          len(page.locator("#view").inner_text()) > 200)
    check("boot does NOT load the series chunk (lazy split)",
          page.evaluate("() => !window.TARK.series"))
    check("boot does NOT load the census chunk (lazy split)",
          page.evaluate("() => !window.TARK_CENSUS"))
    # preload both lazy chunks for the rest of the suite so view renders stay
    # synchronous (runtime lazy-load behavior is exercised by the boot checks)
    page.evaluate("""() => new Promise((res) => {
        const s = document.createElement('script');
        s.src = 'series.js';
        s.onload = () => { window.tarkMergeLazy(); res(true); };
        document.head.append(s);
      })""")
    page.evaluate("""() => new Promise((res) => {
        const s = document.createElement('script');
        s.src = 'census.data.js';
        s.onload = () => res(true);
        document.head.append(s);
      })""")

    # ---------- 2+3. every view x plan x product renders, anonymized ----------
    combos_bad = []
    leak_bad = []
    markup_bad = []
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
                # a real HTML parse of the whole page: no text node may carry
                # leaked markup, undefined or NaN (inner_text cannot see this)
                stray = stray_markup(page.content())
                if stray:
                    markup_bad.append(f"{view}/{plan}/{product}: {stray[0]}")
    check(f"all {len(VIEWS) * len(PLANS) * len(PRODUCTS)} view x plan x product "
          f"combos render", not combos_bad, "; ".join(combos_bad[:5]))
    check("anonymization holds across every rendered combo", not leak_bad,
          "; ".join(leak_bad[:5]))
    check("no text node carries leaked markup, undefined or NaN across every "
          "rendered combo (HTML parse of page.content())", not markup_bad,
          "; ".join(markup_bad[:3]))
    for view in CENSUS_VIEWS:
        n_err = len(errors)
        text = page.evaluate(
            """(v) => { window.tarkSetState({view: v});
                 return document.getElementById('view').innerText; }""", view)
        low = text.lower()
        check(f"census view '{view}' renders without exception",
              len(errors) == n_err and len(text.strip()) > 200)
        check(f"census view '{view}' anonymization sweep",
              not any(tok in low for tok in FORBIDDEN))
        check(f"census view '{view}' has no leaked markup in text nodes",
              not stray_markup(page.content()))

    # ---------- gloss(): text is preserved, definitions are exact ----------
    # textContent(gloss(s)) must equal s for every glossary entry, every
    # definition, every wrapper string, every cell title and every headline;
    # each data-def must be a glossary definition verbatim.
    gloss_bad = page.evaluate(
        """() => {
             const T = window.TARK, out = [];
             const defs = new Set(Object.values(T.glossary));
             const inputs = [...Object.keys(T.glossary), ...Object.values(T.glossary)];
             for (const p of Object.values(T.products)) {
               inputs.push(p.wrapper);
               for (const s of Object.values(T.cell_labels)) inputs.push(s);
             }
             for (const d of Object.values(T.cell_display))
               for (const x of Object.values(d)) inputs.push(x.headline);
             const div = document.createElement('div');
             for (const s of inputs) {
               div.innerHTML = window.TarkGloss(s);
               if (div.textContent !== s) out.push('text changed: ' + s);
               for (const el of div.querySelectorAll('[data-def]'))
                 if (!defs.has(el.dataset.def)) out.push('bad def on: ' + s);
               if (div.querySelector('[data-def] [data-def]')) out.push('nested: ' + s);
             }
             return {n: inputs.length, bad: out.slice(0, 5)};
           }""")
    check(f"gloss preserves text and emits exact definitions over "
          f"{gloss_bad['n']} strings", not gloss_bad["bad"],
          "; ".join(gloss_bad["bad"]))
    chips_bad = page.evaluate(
        """() => {
             const T = window.TARK, bad = [];
             window.tarkSetState({view: 'roster', plan: T.plan_order[0], product: 'hl_paf'});
             const chips = [...document.querySelectorAll('#rostercards .chip.wrapper')]
               .map((c) => c.textContent);
             const want = Object.values(T.products).map((p) => p.wrapper);
             want.forEach((w, i) => { if (chips[i] !== w) bad.push('roster: ' + w); });
             for (const [k, p] of Object.entries(T.products)) {
               window.tarkSetState({view: 'evaluation', plan: T.plan_order[0], product: k});
               const sub = document.querySelector('#view .viewhead .sub').textContent;
               if (!sub.includes(p.wrapper)) bad.push('evaluation: ' + k);
             }
             return bad;
           }""")
    check("wrapper chip text equals the product's wrapper string on Roster "
          "and Evaluation for all products", not chips_bad, "; ".join(chips_bad[:3]))

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
    # R2-P0-6: the composite card is named a relative wealth ratio and never a PME,
    # the public-proxy card keeps KS-PME, each names its fund return source
    # stat labels render uppercase through CSS and inner_text follows, so the
    # label tokens are compared case-folded and the PME names case-sensitively
    _g_card = page.locator('[data-slot="g"]').first
    _g_text = _g_card.inner_text()
    _g_low = _g_text.lower()
    _g_src = bundle["benchmarks"]["cliffwater_cclfx"]["slot_g"]["composite"]["fund_return_source"]
    check("benchmark cclfx: the Slot G card reads relative wealth ratio vs peer composite, names its fund return "
          "source and the alignment note, says never a benchmark and never a PME, and carries no other PME or "
          "benchmark name",
          "relative wealth ratio vs peer composite" in _g_low and _g_src.lower() in _g_low
          and "Alignment:" in _g_text and "Never a benchmark and never a PME." in _g_text
          and _g_card.locator('[data-stat-kind="composite"]').count() == 1
          and "KS-PME" not in _g_text and "Direct Alpha" not in _g_text
          and "pme" not in _g_low.replace("public market equivalent", "").replace("never a pme", "")
          and "benchmark" not in _g_low.replace("never a benchmark", ""))
    _k_card = page.locator('[data-slot="k"]').first
    _k_text = _k_card.inner_text()
    check("benchmark cclfx: the Slot K card carries the series statrow, keeps KS-PME, names the Yahoo adjusted "
          "close source and shows no reference block (Slot K has its own number)",
          _k_card.locator('[data-stat-kind="series"]').count() == 1 and "KS-PME" in _k_text
          and "yahoo adjusted close" in _k_text.lower() and _k_card.locator('[data-reference="true"]').count() == 0)
    _scr = view_text("screener")
    check("screener: the PME column is split into KS-PME vs reference proxy and peer relative wealth ratio, and the "
          "by-descriptor sentence prints for every product whose Slot K has no number (decision 8.5)",
          "KS-PME vs reference proxy" in _scr and "Peer relative wealth ratio" in _scr
          and page.locator("#view [data-by-descriptor]").count()
          == sum(1 for k in PRODUCTS if (bundle["facts"][k].get("slot_k_by_descriptor") or {}).get("value") is True))
    tl = t.lower()   # stat labels render uppercase (CSS), inner_text follows
    check("benchmark cclfx: monthly-schedule row labeled ILLUSTRATIVE, two-point stated primary",
          "monthly schedule" in tl and "illustrative" in tl and "two-point figure is primary" in tl
          and "direct alpha is the annualized form of the same two flows" in tl)
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
    # ---------- P0-4: the labs never substitute another product ----------
    labs_bad = page.evaluate(
        """() => {
             const T = window.TARK, bad = [];
             const menu = {};
             for (const sel of Object.values(T.benchmarks)) {
               for (const c of [sel.slot_k && sel.slot_k.selected, sel.reference_comparison, ...(sel.rejected || [])].filter(Boolean)) menu[c.id] = c;
             }
             for (const [k, p] of Object.entries(T.products)) {
               window.tarkSetState({view: 'pme', plan: T.plan_order[0], product: k, proxy: '', win: ''});
               const sub = document.querySelector('#view .viewhead .sub')?.textContent || '';
               const empty = document.querySelector('[data-lab-empty]');
               if (T.pme_profiles[k]) {
                 if (empty || !sub.includes(p.fund_name)) bad.push(`pme ${k}: profile exists but lab did not open on it`);
                 const sel = T.benchmarks[k];
                 // the lab opens on its default proxy series; compare with the
                 // slot (Slot K's selection or the reference comparison) that carries that series
                 const slot = sel && [sel.slot_k && sel.slot_k.selected, sel.reference_comparison].find((x) => x && x.comparison
                   && x.comparison.kind === 'series' && x.series_id === T.pme_profiles[k].default_proxy);
                 const comp = slot && slot.comparison;
                 if (comp) {
                   const shown = parseFloat(document.querySelector('#pme_ks').textContent);
                   if (Math.abs(shown - comp.ks_pme) > 1e-4) bad.push(`pme ${k}: lab KS-PME ${shown} vs artifact ${comp.ks_pme}`);
                   const sched = document.querySelector('#pme_sched').textContent;
                   if (comp.ks_pme_monthly_schedule != null) {
                     if (Math.abs(parseFloat(sched) - comp.ks_pme_monthly_schedule) > 1e-4) bad.push(`pme ${k}: lab schedule ${sched} vs artifact ${comp.ks_pme_monthly_schedule}`);
                   } else if (!sched.includes('n/a')) bad.push(`pme ${k}: annual tier shows a schedule figure`);
                 }
               } else if (!empty || empty.dataset.labEmpty !== k || !empty.textContent.includes(p.fund_name)) {
                 bad.push(`pme ${k}: no profile and no empty state naming it`);
               }
               window.tarkSetState({view: 'desmooth', plan: T.plan_order[0], product: k, rho: ''});
               const e2 = document.querySelector('[data-lab-empty]');
               const sub2 = document.querySelector('#view .viewhead .sub')?.textContent || '';
               const has = (T.daily_series && T.daily_series[k]) || k === 'breit';
               if (has && (e2 || !document.querySelector('#dschart'))) bad.push(`desmooth ${k}: series exists but lab did not open`);
               if (!has && (!e2 || e2.dataset.labEmpty !== k)) bad.push(`desmooth ${k}: no series and no empty state naming it`);
             }
             return bad;
           }""")
    check("labs: every product either opens on its own data (KS-PME equals the "
          "selection artifact) or shows an empty state naming it",
          not labs_bad, "; ".join(labs_bad[:4]))

    # ---------- P0-3: Fee Matrix is the typed facts layer ----------
    fees_bad = page.evaluate(
        """() => {
             const T = window.TARK, bad = [];
             window.tarkSetState({view: 'fees', plan: T.plan_order[0], product: 'hl_paf'});
             const items = JSON.parse(document.querySelector('#feechart').dataset.items);
             const rects = document.querySelectorAll('#feechart rect').length;
             for (const it of items) {
               const f = T.facts[it.product].expense_ratio_pct;
               const want = f && f.value !== null ? Math.round(f.value * 100) / 100 : null;
               const got = it.value === null ? null : Math.round(it.value * 100) / 100;
               if (want !== got) bad.push(`bar ${it.product}: ${got} vs fact ${want}`);
             }
             if (rects !== items.filter((i) => i.value !== null).length) bad.push('rect count');
             const FIELD = {'2.1': 'mgmt_fee_pct', '2.2': 'incentive_fee', '2.3': 'expense_ratio_pct',
                            '2.4': 'affe', '2.7': 'early_repurchase', '6.4': 'tax_form'};
             for (const el of document.querySelectorAll('[data-fee-chip]')) {
               const cid = el.dataset.feeChip, k = el.dataset.product, txt = el.textContent;
               const cell = T.products[k].cells[cid];
               const fact = FIELD[cid] ? T.facts[k][FIELD[cid]] : null;
               const isNA = String(cell.status || '').startsWith('n/a');
               const nullFact = !fact || fact.value === null;
               if ((isNA || nullFact) && txt.includes('%')) bad.push(`chip ${k} ${cid} shows a percentage: ${txt}`);
               if (isNA && txt !== 'n/a') bad.push(`chip ${k} ${cid} n/a cell reads ${txt}`);
               if (fact && fact.value && fact.value.present === false && txt !== 'none') bad.push(`chip ${k} ${cid} absence reads ${txt}`);
               if (cid === '2.3' && fact && fact.value !== null && !txt.startsWith(fact.value.toFixed(2) + '%')) bad.push(`chip ${k} 2.3 ${txt}`);
             }
             return bad;
           }""")
    check("fee matrix: every bar equals facts.expense_ratio_pct to 2 dp or is "
          "absent, and no chip shows a percentage for a null fact or an n/a cell",
          not fees_bad, "; ".join(fees_bad[:4]))
    # cell headlines: typed fact first, never a regex figure
    hl_bad = page.evaluate(
        """() => {
             const T = window.TARK, bad = [];
             for (const [k, cells] of Object.entries(T.cell_display)) {
               const cited = {};
               for (const [f, x] of Object.entries(T.facts[k])) if (x.value !== null) (cited[x.source_cell] ||= []).push(f);
               for (const [cid, d] of Object.entries(cells)) {
                 if (cited[cid] && !d.typed && !String(T.products[k].cells[cid].status).startsWith('n/a')) bad.push(`${k} ${cid} has a typed fact but a prose headline`);
               }
             }
             return bad;
           }""")
    check("cell headlines are typed-fact-first wherever a fact cites the cell",
          not hl_bad, "; ".join(hl_bad[:4]))

    t = view_text("fees")
    check("fee matrix: leverage-inclusive base flagged",
          "MANAGED ASSETS" in t and "GROSS assets" in t)
    check("fee matrix: K-1 vs 1099 row present",
          "Schedule K-1" in t and "Form 1099" in t)

    # ---------- 5. liquidity verdicts + ILLUSTRATIVE labels everywhere ----------
    t = view_text("liquidity", product="cliffwater_cclfx")
    # CONDITIONAL -> PARTIAL (P1-16/17): the record does not establish whether
    # CCLFX has ever prorated (cell 3.3 holds N-23C3A notifications, not
    # results), so gate_history is null and the structural verdict says so
    check("liquidity cclfx: PARTIAL structural verdict, the missing fact named",
          "STRUCTURAL VERDICT: PARTIAL" in t.upper() and "Facts missing" in t and "gate_history" in t)
    check("liquidity cclfx: structural gap named", "STRUCTURAL GAP" in t)
    check("liquidity cclfx: scenario verdict banner labeled ILLUSTRATIVE",
          "SCENARIO VERDICT" in t.upper() and "ILLUSTRATIVE" in t)
    t = view_text("liquidity", product="sreit")
    check("liquidity sreit: MISALIGNED on the suspended program, capacity 0%",
          "MISALIGNED" in t and "suspended" in t and "0%" in t and "far inside" not in t)
    check("liquidity sreit: the fund's net assets are typed from cell 3.4 and printed as approximate",
          "approx. $8.3B (3.4)" in t)
    # R3-P2-7 (b): the program status precedes the cadence on every surface
    t = view_text("screener")
    check("screener: sreit's dealing column reads suspended, not monthly",
          "suspended" in page.locator('tr[data-key="sreit"]').first.inner_text()
          and "monthly" not in page.locator('tr[data-key="sreit"]').first.inner_text())
    t = view_text("evaluation", product="sreit")
    check("evaluation sreit: the cell 3.1 headline reads suspended before any cadence word",
          "repurchases suspended since the April 29, 2026 amendment" in t)
    # R3-P2-11: cell 3.7 shows the selected plan's own demand sentence
    t_tech = view_text("evaluation", plan="plan_tech_media", product="hl_paf")
    s_tech = page.locator('[data-plan-cell="3.7"]').inner_text()
    t_cons = view_text("evaluation", plan="plan_consulting_alumni", product="hl_paf")
    s_cons = page.locator('[data-plan-cell="3.7"]').inner_text()
    check("evaluation: cell 3.7 leads with the selected plan's own demand sentence and it changes with the plan",
          s_tech == bundle["plans"]["plan_tech_media"]["demand_sentence"]
          and s_cons == bundle["plans"]["plan_consulting_alumni"]["demand_sentence"] and s_tech != s_cons
          and s_tech in t_tech and s_tech not in t_cons)
    # R3-P2-8: the rollup tiles count on the record's one arithmetic
    t = view_text("evaluation", product="sreit")
    roll = bundle["factor_rollups"]["sreit"]
    check("evaluation: the factor rollups count evidenced as T1 plus T2 plus T3, name the soft cells, and sum to the "
          "coverage headline's resolved count",
          sum(r["evidenced"] + r["computed"] for r in roll.values()) == bundle["evidence_counts"]["sreit"]["resolved"]
          and sum(r["soft"] for r in roll.values()) == bundle["evidence_counts"]["sreit"]["soft"]
          and any(f"{r['soft']} partial" in t for r in roll.values() if r["soft"]))
    check("coverage: resolved is structured plus extracted plus verified plus computed for every product, and the "
          "headline prints the four counts side by side with the signed count last",
          all(c["resolved"] == c["structured"] + c["extracted"] + c["verified"] + c["computed"]
              and c["headline"].endswith(f"{c['verified']} verified by a person")
              and f"{c['evidenced']} evidenced, {c['computed']} computed, {c['soft']} partial, {c['na']} n/a" in c["headline"]
              for c in bundle["evidence_counts"].values()))
    # R3-P2-17d: the filed since-inception return beside the series figure
    t = view_text("benchmarks", product="cliffwater_cclfx")
    check("cclfx card: the reconciliation names the filed 9.34% since inception and the series' 7.89%/yr with why they differ",
          page.locator("[data-reconciliation]").count() == 1 and "9.34%" in t and "7.89%/yr" in t
          and "differ by end date" in t and bundle["reconciliation"]["cliffwater_cclfx"] in t)
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
    # liquidity matches ride the lazy series chunk now (perf split) — read
    # them from series.js line 2 for the assertion set
    liq_line = (SITE / "series.js").read_text().splitlines()[1]
    bundle_liq = json.loads(liq_line[len("window.TARK_LIQ = "):-1])
    ill_missing, pend_missing = [], []
    for pl in PLANS:
        for pr in PRODUCTS:
            t = view_text("liquidity", pl, pr)
            if f"{pl}__{pr}" in bundle_liq:
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
    # the lab opens on BKLN: Slot K's own series for cclfx (v3), or the
    # reference comparison wherever Slot K is a cited index without a number
    cclfx_sel = bundle["benchmarks"]["cliffwater_cclfx"]
    bkln_slot = next(x for x in (cclfx_sel["slot_k"].get("selected"), cclfx_sel.get("reference_comparison"))
                     if x and x.get("series_id") == "bkln" and (x.get("comparison") or {}).get("kind") == "series")
    check("pme default reproduces committed KS-PME (BKLN slot)",
          abs(float(ks0) - bkln_slot["comparison"]["ks_pme"]) < 1e-4)
    da0 = page.locator("#pme_da").inner_text()
    check("pme default reproduces committed Direct Alpha (BKLN slot)",
          abs(float(da0.rstrip("%")) - bkln_slot["comparison"]["direct_alpha_pct"]) < 0.01)
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
    s0 = page.locator("#o_stressed").inner_text()
    v0 = page.locator("#o_verdict").inner_text()
    f0 = page.locator("#o_filed").inner_text()
    page.evaluate("""() => { const s = document.getElementById('s_tail');
        s.value = '45'; s.dispatchEvent(new Event('input')); }""")
    d1 = page.locator("#o_reason").inner_text()
    check("liquidity slider changes demand", d0 != d1, f"{d0} -> {d1}")
    check("liquidity capacity-vs-demand visual renders",
          page.locator("#capchart svg rect").count() >= 2)
    check("liquidity stress block present",
          "Stressed demand" in page.locator("#view").inner_text())
    # R2-P1-10: the turnover slider moves the slider assumption and the
    # stressed demand, never the filed outflow proxy, and the live verdict
    # follows the stressed rung
    check("liquidity: the tail slider moves the stressed demand and leaves the filed outflow proxy where the filing put it",
          page.locator("#o_stressed").inner_text() != s0 and page.locator("#o_filed").inner_text() == f0
          and f0.endswith("%"), f"stressed {s0} -> {page.locator('#o_stressed').inner_text()}, filed {f0}")
    check("liquidity: the capacity chart draws the filed outflow proxy, the slider assumption and the stressed demand",
          page.locator("#capchart svg rect").count() >= 3
          and all(x in page.locator("#capchart").inner_text() for x in ("Filed outflow proxy", "Slider assumption", "Stressed demand")))
    check("liquidity: filed outflow proxy and slider assumption are both printed and labeled on the view",
          all(x in page.locator("#view").inner_text() for x in ("Filed outflow proxy", "Slider assumption", "not blended")))
    del v0
    # R2-P1-11: the allocation slider exists exactly where the fund's dollar
    # capacity is computable (fund net assets typed), moves the dollar figures
    # and the plan's share of that capacity, and moves no percent-of-position
    # figure. Elsewhere one sentence says why it is absent.
    alloc_bad = []
    for pr in PRODUCTS:
        t = view_text("liquidity", plan="plan_tech_media", product=pr)
        mm = bundle_liq.get(f"plan_tech_media__{pr}")
        if not mm:
            continue
        has = page.locator("#s_alloc").count() == 1
        want = bool(mm["scenario"]["fund_capacity"]["available"])
        if has != want:
            alloc_bad.append(f"{pr}: slider {has} vs fund capacity {want}")
        if not want and "No allocation slider for this fund" not in t:
            alloc_bad.append(f"{pr}: no sentence for the missing slider")
        if want and ("Fund capacity in dollars" not in t or "of that capacity" not in t):
            alloc_bad.append(f"{pr}: dollar capacity not printed")
    check("liquidity: the allocation slider exists exactly where the fund's dollar capacity is computable, with the "
          "dollar figures printed, and one sentence explains its absence elsewhere", not alloc_bad, "; ".join(alloc_bad[:4]))
    view_text("liquidity", plan="plan_tech_media", product="hl_paf")
    fund0 = page.locator('[data-bullet="fund"]').inner_text()
    pct0 = (page.locator("#o_filed").inner_text(), page.locator("#o_slider").inner_text(),
            page.locator("#o_stressed").inner_text(), page.locator("#o_verdict").inner_text())
    page.evaluate("""() => { const s = document.getElementById('s_alloc');
        s.value = '10'; s.dispatchEvent(new Event('input')); }""")
    fund1 = page.locator('[data-bullet="fund"]').inner_text()
    pct1 = (page.locator("#o_filed").inner_text(), page.locator("#o_slider").inner_text(),
            page.locator("#o_stressed").inner_text(), page.locator("#o_verdict").inner_text())
    check("liquidity hl_paf: moving the allocation slider changes the plan's dollar demand and share of the fund's "
          "capacity and moves no percent-of-position figure or verdict",
          fund0 != fund1 and "of that capacity" in fund1 and pct0 == pct1, f"{fund0[:60]} -> {fund1[:60]}")

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

    # liquidity scenario parity vs every bundled match (default params)
    # R2-P1-10 and R2-P1-11: every figure the JS recomputes live (the filed
    # base, the slider assumption, the stress increment and the stressed
    # demand, in percent and in dollars, the fund's dollar capacity and the
    # plan's share of it) equals the Python figure in every bundled match
    mism = page.evaluate("""() => {
      const out = [];
      const near = (a, b, tol) => (a === null || a === undefined)
        ? (b === null || b === undefined) : (b !== null && b !== undefined && Math.abs(a - b) <= tol);
      for (const [k, m] of Object.entries(window.TARK.liquidity)) {
        const sc = m.scenario, ss = m.stressed_scenario, fc = sc.fund_capacity;
        const got = window.TarkLiquidity.computeScenario(
          m.plan_inputs, m.wrapper_facts, sc, ss.multiples);
        const bad = [];
        if (!near(got.plan_allocation_usd, sc.plan_allocation_usd, 1)) bad.push("alloc");
        if (!near(got.filed_outflow_proxy_pct, sc.filed_outflow_proxy_pct, 1e-9)) bad.push("filed");
        if (!near(got.filed_annual_demand_usd, sc.filed_annual_demand_usd, 1)) bad.push("filed_usd");
        if (!near(got.slider_assumption_pct, sc.slider_assumption_pct, 0.05)) bad.push("slider");
        if (!near(got.slider_annual_demand_usd, sc.slider_annual_demand_usd, 1)) bad.push("slider_usd");
        if (!near(got.stress_increment_pct, ss.stress_increment_pct, 0.05)) bad.push("increment");
        if (!near(got.stressed_pct, ss.demand_pct_of_position, 0.05)) bad.push("stressed");
        if (!near(got.stressed_annual_demand_usd, ss.annual_demand_usd, 1)) bad.push("stressed_usd");
        if (got.annual_wrapper_capacity_pct !== sc.annual_wrapper_capacity_pct) bad.push("capacity");
        if (got.fund_capacity.available !== fc.available) bad.push("fund_available");
        if (fc.available && (!near(got.fund_capacity.annual_capacity_usd, fc.annual_capacity_usd, 1)
            || !near(got.fund_capacity.plan_annual_demand_usd, fc.plan_annual_demand_usd, 1)
            || !near(got.fund_capacity.plan_share_of_fund_capacity_pct, fc.plan_share_of_fund_capacity_pct, 0.011)))
          bad.push("fund_dollars");
        if (bad.length) out.push(`${k}: ${bad.join(",")}`);
      }
      return out;
    }""")
    check(f"parity: JS scenario matches all {len(bundle_liq)} bundled liquidity scenarios (filed base, slider assumption, "
          "stress increment, stressed demand, dollars, fund capacity and share)", not mism, "; ".join(mism[:4]))
    vmism = page.evaluate("""() => {
      const T = window.TARK, L = window.TarkLiquidity, out = [];
      for (const [k, m] of Object.entries(T.liquidity)) {
        const sc = L.computeScenario(m.plan_inputs, m.wrapper_facts, m.scenario, m.stressed_scenario.multiples);
        const sp = L.stressedDemandPct(m.plan_inputs, m.scenario, m.stressed_scenario.multiples);
        const v = L.scenarioVerdict(sc, sp, m.wrapper_facts.exchange);
        if (v !== m.scenario_verdict) out.push(`${k}: js ${v} vs ${m.scenario_verdict}`);
      }
      return out;
    }""")
    check(f"parity: JS scenario verdict matches all {len(bundle_liq)} bundled matches",
          not vmism, "; ".join(vmism[:4]))
    # R3-P1-10 and R3-P2-7: at the default sliders the bullets the view
    # rebuilds live and the drivers line are the record's own sentences,
    # word for word, for every bundled match
    smism = page.evaluate("""() => {
      const T = window.TARK, L = window.TarkLiquidity, out = [];
      for (const [k, m] of Object.entries(T.liquidity)) {
        const sc = L.computeScenario(m.plan_inputs, m.wrapper_facts, m.scenario, m.stressed_scenario.multiples);
        const v = L.scenarioVerdict(sc, sc._stressed_exact, m.wrapper_facts.exchange);
        const d = L.scenarioDrivers(sc, sc._stressed_exact, m.wrapper_facts, v);
        if (d.sentence !== m.scenario.drivers.sentence || d.rung !== m.scenario.drivers.rung) out.push(`${k}: drivers`);
        const bullets = L.scenarioBullets(m, sc, m.scenario, m.wrapper_facts, v).map((b) => b.text);
        if (JSON.stringify(bullets) !== JSON.stringify(m.scenario_reasons)) {
          const i = bullets.findIndex((b, j) => b !== m.scenario_reasons[j]);
          out.push(`${k}: bullet ${i}: ${String(bullets[i]).slice(0, 80)} | ${String(m.scenario_reasons[i]).slice(0, 80)}`);
        }
      }
      return out;
    }""")
    check(f"parity: at the default sliders the live bullets and the drivers line equal the record's sentences for all "
          f"{len(bundle_liq)} matches, word for word", not smism, "; ".join(smism[:3]))
    view_text("liquidity", plan="plan_consulting_alumni", product="hl_paf")
    drv0 = page.locator("[data-drivers]").inner_text()
    verdict_bullet0 = page.locator('[data-bullet="verdict"]').inner_text()
    page.evaluate("""() => { const s = document.getElementById('s_tail');
        s.value = '45'; s.dispatchEvent(new Event('input')); }""")
    drv1 = page.locator("[data-drivers]").inner_text()
    verdict_bullet1 = page.locator('[data-bullet="verdict"]').inner_text()
    check("liquidity: the drivers line and the verdict bullet move with the sliders from the one live state (hl_paf under "
          "the consulting plan: no rung at the defaults, the stress rung at tail turnover 45)",
          "No rung fired" in drv0 and "Stress rung" in drv1 and "No rung fired" in verdict_bullet0
          and "Stress rung" in verdict_bullet1 and "conditional-weak" in verdict_bullet1
          and page.locator("#o_verdict").inner_text() == "CONDITIONAL-WEAK", f"{drv0[:60]} -> {drv1[:60]}")
    check("liquidity: the program status row prints the typed status and the date it was read at",
          "active as of 2026-03-31 (3.1)" in page.locator("#view").inner_text())
    check("scenario verdict varies with the plan for at least one product (bundled)",
          any(bundle_liq[f"plan_tech_media__{pr}"]["scenario_verdict"]
              != bundle_liq[f"plan_consulting_alumni__{pr}"]["scenario_verdict"] for pr in PRODUCTS))

    # every proxy the lab offers selects and computes (cclfx has the longest
    # daily NAV series); this is also what marks each proxy series as read
    proxy_bad = []
    for pid in bundle["proxy_library"]:
        n_err = len(errors)
        page.evaluate("(p) => window.tarkSetState({view: 'pme', "
                      "product: 'cliffwater_cclfx', proxy: p, win: ''})", pid)
        sel = page.evaluate("() => (document.querySelector("
                            "'#view input[type=radio]:checked') || {}).value")
        t = page.locator("#view").inner_text()
        if (sel != pid or "KS-PME" not in t or len(errors) != n_err
                or stray_markup(page.content())):
            proxy_bad.append(f"{pid}: selected={sel}")
    check(f"lab: every offered proxy ({len(bundle['proxy_library'])}) selects "
          "and computes a KS-PME on cclfx", not proxy_bad, "; ".join(proxy_bad))
    page.evaluate("() => window.tarkSetState({proxy: '', win: ''})")

    # ---------- P1-4: every Yahoo series is labeled from series_sources ----------
    label_bad = []
    for k, d in bundle["daily_series"].items():
        want = bundle["series_sources"][d["series"]]["label"]
        for view in ("pme", "desmooth"):
            page.evaluate("(a) => window.tarkSetState({view: a[0], product: a[1], proxy: '', win: '', rho: ''})", [view, k])
            txt = page.evaluate("() => document.getElementById('view').textContent")
            if want not in txt:
                label_bad.append(f"{view}/{k}: missing '{want}'")
    page.evaluate("() => window.tarkSetState({view: 'evaluation', product: 'cliffwater_cclfx'})")
    if bundle["series_sources"]["cclfx"]["label"] not in page.evaluate("() => document.getElementById('view').textContent"):
        label_bad.append("evaluation/cliffwater_cclfx: mini-chart label missing")
    check("every chart of a held Yahoo series prints its series_sources label "
          "(lab, de-smoothing, evaluation)", not label_bad, "; ".join(label_bad[:4]))
    check("market-price series are labeled as market price, never as NAV",
          all(bundle["series_sources"][d["series"]]["label"] == "Yahoo daily close (market price)"
              for d in bundle["daily_series"].values() if d["price_series"]))

    # ---------- 7b. design-pass additions ----------
    def _committed_reference(k):
        """the committed artifact, its public-series slot, and whether that
        slot is the reference comparison (Slot K cited, not held) or Slot K"""
        art = json.loads((BASE / "data" / "benchmarks" / f"{k}_selection.json").read_text())
        s = (art.get("slot_k") or {}).get("selected")
        if s and (s.get("comparison") or {}).get("kind") == "series":
            return art, s, False
        return art, art.get("reference_comparison"), True
    _art, _slot, _is_ref = _committed_reference("kkr_kpec")
    t = view_text("benchmarks", product="kkr_kpec")
    check("kkr_kpec: Cambridge PE is the cited Slot K, PSP renders as the reference comparison with the committed KS-PME",
          _is_ref and "Cambridge" in _art["slot_k"]["selected"]["candidate"]
          and "Listed private equity investable proxy" in t and str(_slot["comparison"]["ks_pme"]) in t
          and "Reference comparison, not the meaningful benchmark" in t
          and page.locator('[data-slot="k"] [data-reference="true"] [data-stat-kind="series"]').count() == 1)
    _art, _slot, _is_ref = _committed_reference("breit")
    _breit_ks = _slot["comparison"]["ks_pme"]
    t = view_text("benchmarks", product="breit")
    # the window starts 2022-12-31, a Saturday: the index anchor is the level
    # on or before that date (2022-12-30), the same anchor the PME uses
    check("breit: NFI-ODCE is the cited Slot K, VNQ renders as the reference comparison with the committed KS-PME",
          _is_ref and "ODCE" in _art["slot_k"]["selected"]["candidate"]
          and "Listed REIT investable proxy" in t and str(_breit_ks) in t
          and "Reference comparison, not the meaningful benchmark" in t
          and page.locator('[data-slot="k"] [data-reference="true"] [data-stat-kind="series"]').count() == 1)
    t_s = view_text("benchmarks", product="sreit")
    check("sreit: one-year comparison window labeled low confidence on the card",
          "low confidence" in t_s.lower() and "shorter than 3 years" in t_s)
    t_c = view_text("benchmarks", product="cliffwater_cclfx")
    check("cclfx: no low-confidence label on its windows", "low confidence" not in t_c.lower())
    check("breit: the cited Slot K holds the slot by descriptor and prints the decided sentence (decision 8.5)",
          "ODCE" in t and bundle["by_descriptor_sentence"] in t and "No comparison computed on held data" not in t)
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
    # the taxonomy line is per status kind (T1 / T2 / T3 named), computed
    # from the live record; "0 unresolved" used to count n/a as resolved
    tax = bundle["taxonomy"]
    rec = {k: 0 for k in ("structured", "extracted", "verified", "computed",
                          "partial", "fetched", "na", "pending")}
    for k in PRODUCTS:
        for cell in bundle["products"][k]["cells"].values():
            st = str(cell.get("status", "pending"))
            kind = next((p for p in ("pending", "partial", "extracted", "verified",
                                     "structured", "computed", "fetched", "n/a")
                         if st.startswith(p)), "pending")
            rec["na" if kind == "n/a" else kind] += 1
    check("taxonomy counts equal the record recomputed from the bundle",
          tax["counts"] == rec and tax["total"] == sum(rec.values()),
          f"{tax['counts']} vs {rec}")
    check("taxonomy line names the tiers and pending on screen",
          "(T1)" in t and "(T2)" in t and "(T3)" in t and "pending" in t)
    check("taxonomy: cion_ares structured=1 and pending=0 (the CION 98% defect)",
          bundle["evidence_counts"]["cion_ares"]["structured"] == 1
          and bundle["evidence_counts"]["cion_ares"]["pending"] == 0)
    check("crosscheck tile reads from the report header and names an agent pass",
          "re-located by an agent pass" in t and "Human verification: 0" in t)
    check("coverage rings render (one per-kind donut per roster product)",
          page.locator("#prodrings svg").count() == len(PRODUCTS))
    check("taxonomy donut renders", page.locator("#taxdonut svg").count() == 1)
    t = view_text("fees")
    check("fee bar chart renders", page.locator("#feechart svg").count() == 1)
    t = view_text("benchmarks", product="dxyz")
    check("escalation renders as formal notice",
          page.locator(".notice .notice-head").count() == 1)

    # ---------- v3 surface law over every product's Benchmark Selection
    slot_bad = []
    for pr in PRODUCTS:
        tt = view_text("benchmarks", product=pr)
        raw = page.evaluate("() => document.getElementById('view').textContent")
        sel = bundle["benchmarks"][pr]
        if page.locator('[data-slot="k"]').count() != 1 or page.locator('[data-slot="g"]').count() != 1:
            slot_bad.append(f"{pr}: slot cards")
        if "PRIMARY" in tt or "SECONDARY" in tt:
            slot_bad.append(f"{pr}: rank word on screen")
        leaked = [k2 for k2 in PRODUCTS if re.search(rf"(?<![A-Za-z0-9_]){re.escape(k2)}(?![A-Za-z0-9_])", raw)]
        if leaked:
            slot_bad.append(f"{pr}: bare key {leaked[0]}")
        tied = [r for r in sel["rejected"] if r.get("tied") is True]
        chips = page.locator("[data-tied-chip]")
        if chips.count() != len(tied) or any(chips.nth(i).inner_text() != "TIED" for i in range(len(tied))):
            slot_bad.append(f"{pr}: TIED chip count")
        if bool(tied) != bool(sel["slot_k"].get("ties")):
            slot_bad.append(f"{pr}: ledger ties and slot_k.ties disagree")
        if tied and (bundle["tie_sentence"] not in tt or any(r["candidate"] not in tt for r in tied)):
            slot_bad.append(f"{pr}: tie sentence")
        if picked_k_pre := (sel["slot_k"].get("selected") or {}):
            if picked_k_pre.get("by_descriptor") and (page.locator('[data-slot="k"] [data-by-descriptor]').count() != 1
                                                       or bundle["by_descriptor_sentence"] not in tt):
                slot_bad.append(f"{pr}: by-descriptor sentence")
            if not picked_k_pre.get("by_descriptor") and page.locator('[data-slot="k"] [data-by-descriptor]').count():
                slot_bad.append(f"{pr}: by-descriptor sentence where Slot K has a number")
        if sel.get("record_hash") and (page.locator('[data-slot="k"] [data-lock]').count() != 1
                                       or sel["record_hash"][:8] not in tt or "Selection recorded" not in tt):
            slot_bad.append(f"{pr}: selection lock line")
        if "/10" in tt or "/12" in tt:
            slot_bad.append(f"{pr}: a slash score survives")
        picked_k = sel["slot_k"].get("selected") or {}
        if sel.get("reference_comparison") and not picked_k.get("comparison"):
            if (page.locator('[data-slot="k"] [data-reference="true"]').count() != 1
                    or "Reference comparison, not the meaningful benchmark" not in tt
                    or sel["reference_comparison"]["candidate"] not in tt):
                slot_bad.append(f"{pr}: reference block")
        elif page.locator('[data-reference="true"]').count():
            slot_bad.append(f"{pr}: reference block where Slot K has its own comparison")
        if picked_k and picked_k["candidate"] not in page.locator('[data-slot="k"]').inner_text():
            slot_bad.append(f"{pr}: Slot K candidate")
        if sel["slot_k"].get("escalation") and sel["slot_k"]["escalation"].split(".")[0] not in page.locator('[data-slot="k"]').inner_text():
            slot_bad.append(f"{pr}: escalation sentence missing from the Slot K card")
        g = sel["slot_g"]
        g_text = page.locator('[data-slot="g"]').inner_text()
        if g["cohort_label"] not in g_text or any(n not in g_text for n in g["member_names"]):
            slot_bad.append(f"{pr}: Slot G cohort or peer names")
        if page.locator('[data-slot="g"] [data-peer-table] tbody tr').count() != max(1, len(g["table"])):
            slot_bad.append(f"{pr}: Slot G table rows")
        if (g["composite"].get("status") == "computed") != (page.locator('[data-slot="g"] [data-stat-kind="composite"]').count() == 1):
            slot_bad.append(f"{pr}: Slot G composite block")
        if g["composite"].get("status") != "computed" and f"Composite refused: {g['composite'].get('reason')}" not in g_text:
            slot_bad.append(f"{pr}: Slot G refusal reason")
        if "The declaration itself earns no points." not in tt or "Return basis for every comparison:" not in tt \
                or sel["basis"]["label"] not in tt:
            slot_bad.append(f"{pr}: declared strip or basis line")
        if any(d["name"] not in tt or d["status"] not in tt for d in sel["declared"]):
            slot_bad.append(f"{pr}: declared entry")
        if sel.get("declared_none_reason") and f"The fund declares no benchmark ({sel['declared_none_reason']})." not in tt:
            slot_bad.append(f"{pr}: declared-none reason")
    check("benchmarks: every product shows one Slot K and one Slot G card, prints no PRIMARY or SECONDARY and no "
          "bare product key, marks every tied ledger row TIED beside the tie sentence, shows the reference block "
          "only where Slot K has no number, and prints the declared record and the return basis",
          not slot_bad and any(r.get("tied") is True
                               for s in bundle["benchmarks"].values() for r in s["rejected"]),
          "; ".join(slot_bad[:6]))

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
    # the roster changed this answer honestly twice: ares_pmf (cohort
    # build) and cion_ares (census promotion) share the leverage-inclusive
    # Managed Assets base with hl_paf
    check("screener: fee-base=managed_assets returns hl_paf + ares_pmf + cion_ares",
          mrows == 3, str(mrows))
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
    vtext = page.locator("#verdictcard").inner_text()
    check("URL round-trip: lab proxy restored; off-menu proxy graded by the real scorer",
          "not on the engine's menu" in vtext and "Not eligible" in vtext
          and "strategy gate" in vtext)
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
    check("breit lab: annual-tier PME vs VNQ reproduces the committed reference KS-PME",
          abs(float(page.locator("#pme_ks").inner_text()) - _breit_ks) < 1e-4)
    check("breit lab: the verdict card names the meaningful benchmark and says the lab opens on the reference",
          "Engine's meaningful benchmark for this product" in page.locator("#verdictcard").inner_text()
          and "The lab opens on the reference comparison, not the meaningful benchmark"
          in page.locator("#verdictcard").inner_text()
          and page.locator("[data-lab-peer]").count() == 1
          and "never a proxy" in page.locator("[data-lab-peer]").inner_text())
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

    # ---------- census (T1 universe) ----------
    # earlier share-link round-trips reloaded the page, wiping the preloaded
    # lazy chunks — re-inject them so census renders are synchronous again
    page.evaluate("""() => new Promise((res) => {
        if (window.TARK_CENSUS) return res(true);
        const s = document.createElement('script');
        s.src = 'census.data.js';
        s.onload = () => res(true);
        document.head.append(s);
      })""")
    t = view_text("census")
    check("census: universe total on screen",
          f"{census_bundle['total']:,}" in t)
    check("census: tier legend on the screener surface",
          "T1 structured filing data" in t and "T3 verified" in t)
    n_int = census_bundle["counts_by_class"]["interval_23c3"]
    page.evaluate("""() => window.tarkSetState({view: 'census',
      c_class: 'interval_23c3'})""")
    t = page.locator("#view").inner_text()
    check("census: interval filter shows the real class count",
          f"{n_int:,} of" in t or f"{n_int} of" in t)
    check("census: the surface states the census as-of date",
          census_bundle["as_of"] in t)
    # entity detail: the on-interaction shard fetch path (cclfx, CIK 1735964)
    n_err = len(errors)
    page.evaluate("() => window.tarkSetState({view: 'census', c_cik: '1735964'})")
    page.wait_for_selector("#view [data-back]", timeout=15000)
    t = page.locator("#view").inner_text()
    check("census entity: detail shard renders the entity with its CIK",
          "CIK 1735964" in t and len(errors) == n_err)
    check("census entity: per-field provenance rows are on screen",
          page.locator("#view table.grid td.cap").count() > 0)
    check("census entity: no leaked markup in text nodes",
          not stray_markup(page.content()))
    check("census entity: anonymization sweep",
          not any(tok in t.lower() for tok in FORBIDDEN))
    page.evaluate("() => window.tarkSetState({view: 'census', c_cik: ''})")
    # an unevaluated entity (P2-5): copyable command, honest service state
    page.evaluate("() => window.tarkSetState({view: 'census', c_cik: '1467631'})")
    page.wait_for_selector("#view [data-back]", timeout=15000)
    t = page.locator("#view").inner_text()
    check("census entity (unevaluated): an evaluation request naming this CIK is copyable, no command line",
          "Evaluate CIK 1467631" in t and page.locator("[data-copycmd]").count() == 1
          and page.locator("[data-cmd]").inner_text().startswith("Evaluate CIK 1467631")
          and "python" not in t and "src/" not in t)
    check("census entity (unevaluated): no service connected to this build, no button, no job state",
          (bundle.get("service_url") is None) == ("No evaluation service is connected" in t)
          and page.locator("[data-evaluate]").count() == (0 if bundle.get("service_url") is None else 1)
          and not any(w in t.lower() for w in ("queued", "job id", "in progress")))
    page.evaluate("() => window.tarkSetState({view: 'census', c_cik: ''})")
    # index rows are compact arrays; the field order ships in the chunk as
    # row_fields and the screener decodes with it (one source)
    RF = [f.split("(")[0] for f in census_bundle["row_fields"]]
    check("census: row_fields names every index column",
          RF == ["nm", "cls_code", "flags", "assets_usd", "latest_annual_date",
                 "tender_count", "tender_last", "hint_mask", "promo_key"])
    CODE = {v: k for k, v in census_bundle["cls_codes"].items()}
    def crow(cik):
        r = dict(zip(RF, census_bundle["entities"][cik]))
        return {"nm": r["nm"], "cls": census_bundle["cls_codes"][r["cls_code"]],
                "flags": r["flags"], "ta": r["assets_usd"], "promo": r["promo_key"]}
    # cclfx: present, interval-flagged (self+behavior agree), promoted —
    # and the link round-trips
    cclfx = crow("1735964")
    check("census: cclfx is in the universe, interval class, promoted",
          cclfx["cls"] == "interval_23c3"
          and cclfx["promo"] == "cliffwater_cclfx"
          and bool(cclfx["flags"] & 8))  # crosscheck agreement bit
    page.evaluate("""() => window.tarkSetState({c_cik: '1735964'})""")
    page.wait_for_timeout(600)  # detail shard fetch
    t = page.locator("#view").inner_text()
    check("census: cclfx detail shows evaluated tier + evidence",
          "evaluated roster" in t and "Detection evidence" in t)
    page.evaluate("""() => document.querySelector('[data-goproduct]').click()""")
    check("census: promotion link lands on the evaluation record",
          page.evaluate("() => decodeURIComponent(location.hash)")
          .find("view=evaluation") >= 0
          and page.evaluate("() => decodeURIComponent(location.hash)")
          .find("product=cliffwater_cclfx") >= 0)
    # the two census promotions link both ways
    for cik, key in (("1812554", "ocic"), ("1678124", "cion_ares")):
        e = crow(cik)
        check(f"census: promotion {key} linked in the universe index",
              e["promo"] == key and bool(e["flags"] & 16))
    # known non-traded REITs classified correctly (OTC quotation != listed)
    for cik, nm in (("1662972", "breit"), ("1711929", "sreit")):
        e = crow(cik)
        check(f"census: {nm} is nontraded_reit and NOT exchange-listed",
              e["cls"] == "nontraded_reit" and not (e["flags"] & 1))
    # P2-11: the N-23C3A recency rule and share-class aware listing
    for cik, nm in (("65433", "MXF"), ("917100", "IFN"), ("1517767", "CCIF"), ("1523289", "DMA")):
        e = crow(cik)
        check(f"census: {nm} reclassified to listed_cef by the recency rule, listed common shares",
              e["cls"] == "listed_cef" and bool(e["flags"] & 1))
    for cik, nm in (("1551047", "TIPLX"), ("1644771", "RSF")):
        e = crow(cik)
        check(f"census: {nm} stays interval_23c3 with the listing flag off (class listed is unknown)",
              e["cls"] == "interval_23c3" and not (e["flags"] & 1))
    page.evaluate("() => window.tarkSetState({view: 'census', c_cik: '65433'})")
    page.wait_for_selector("#view [data-back]", timeout=15000)
    check("census entity: the reclassified fund shows the rule and its dates in its evidence",
          "N-23C3A recency rule" in page.locator("#view").inner_text())
    page.evaluate("() => window.tarkSetState({view: 'census', c_cik: '1644771'})")
    page.wait_for_selector("#view [data-back]", timeout=15000)
    check("census entity: the still-active listed interval fund shows the listing signal row with its reason",
          "Listing signal (submissions)" in page.locator("#view").inner_text()
          and page.locator("#view [title*='which share class is listed']").count() >= 1)
    page.evaluate("() => window.tarkSetState({view: 'census', c_cik: ''})")
    # C2: name hints are badged and never filter by default
    unfiltered = page.evaluate("""() => {
      window.tarkSetState({view: 'census', c_cik: '', c_class: '', c_hint: ''});
      return document.querySelectorAll('tr[data-cik]').length; }""")
    hint_ok = page.evaluate("""() =>
      [...document.querySelectorAll('.chip.hint')].every(
        (c) => (c.title || '').includes('not a strategy claim'))""")
    check("census C2: every hint chip carries the not-a-strategy-claim badge",
          bool(hint_ok))
    check("census C2: default view applies no hint filter",
          unfiltered == 400)  # top-400 slice of the full universe, unfiltered
    # URL round-trip with census params (IDs/enums only) — detail shard
    # fetch is async, so wait for the rendered heading
    page.goto(f"http://127.0.0.1:{PORT}/#view=census&c_class=nontraded_reit"
              "&c_cik=1662972", wait_until="networkidle")
    page.wait_for_timeout(900)
    t = page.locator("#view").inner_text()
    check("census: shared entity link round-trips to the detail page",
          "Blackstone Real Estate Income Trust" in t
          and "Detection evidence" in t)
    check("census: promoted detail offers the evaluation record",
          "evaluated roster" in t)
    # detail shards + search sidecar exist and are honest sizes
    shard_dir = SITE / "census" / "d"
    check("census: 64 detail shards on disk",
          len(list(shard_dir.glob("*.json"))) == census_bundle["shards"])
    check("census: search sidecar exists (lazy, memory-only filters)",
          (SITE / "census" / "search.json").exists())
    page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")
    page.evaluate("""() => new Promise((res) => {
        const s = document.createElement('script');
        s.src = 'series.js';
        s.onload = () => { window.tarkMergeLazy(); res(true); };
        document.head.append(s);
      })""")
    page.evaluate("""() => new Promise((res) => {
        const s = document.createElement('script');
        s.src = 'census.data.js';
        s.onload = () => res(true);
        document.head.append(s);
      })""")
    # funnel: true counts, no padding
    t = view_text("funnel")
    dk = census_bundle["dark_universe"]["formd_new_notices"]
    check("funnel: dark-universe Form D count on screen",
          f"{dk:,}" in t)
    check("funnel: universe total and evaluated count are the real numbers",
          f"{census_bundle['total']:,}" in t
          and f"{len(PRODUCTS)}" in t)
    nprom = sum(1 for r in census_bundle["entities"].values() if r[8])
    check("census: promoted links equal the roster size",
          nprom == len(PRODUCTS), f"{nprom} vs {len(PRODUCTS)}")

    # verification view mirrors the queue
    view_text("verification")
    # queue rows carry data-q. Each now has a verify row beneath it (P2-7),
    # so the count reads the queue rows themselves, not every table row.
    qrows = page.evaluate("""() =>
      document.querySelectorAll('table.grid tbody tr[data-q]').length""")
    check("verification view renders the full queue",
          qrows == len(bundle["verification_queue"]["queue"]))
    vq = bundle["verification_queue"]
    tier1 = [f"{it['product']}:{it['cell']}" for it in vq["queue"] if it["tier"] == 1]
    check("verification queue: the parser found Tier 1 rows and their heading",
          len(tier1) >= 5 and "spoken aloud" in vq["tiers"].get("1", ""))
    shown = page.evaluate("""() => [...document.querySelectorAll('table.grid tbody tr[data-q]')]
      .map(r => r.dataset.q)""")
    check("verification view: Tier 1 rows come first, in document order",
          shown[:len(tier1)] == tier1, f"{shown[:3]} vs {tier1[:3]}")
    nbadge = page.evaluate("() => document.querySelectorAll('[data-tier1-badge]').length")
    check("verification view: every Tier 1 row carries the spoken-aloud badge, no other row does",
          nbadge == len(tier1), f"{nbadge} vs {len(tier1)}")
    vt = page.locator("#view").inner_text()
    check("verification view: tier headings repeat the queue document's words",
          all(vq["tiers"][k] in vt for k in vq["tiers"])
          and vt.index("Tier 1") < vt.index("Tier 2") < vt.index("Tier 3"))

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
              supplement_disk["stress_windows"]["cliffwater_cclfx"]["cy2022_rate_shock"]["return_pct"]) < 0.01,
          str(wb["cclfx22"]))

    # ---------- 8. citation drawer + memo artifacts ----------
    view_text("evaluation", product="hl_paf")
    page.locator("[data-cite]").first.click()
    check("citation drawer opens with verbatim quote",
          page.locator("#drawer").get_attribute("class").find("open") >= 0
          and len(page.locator("#drawer .dbody").inner_text()) > 60)
    # P2-10: the drawer links the resolved EDGAR filing for cclfx 2.3 (an exact match)
    page.evaluate("() => { document.getElementById('drawer').classList.remove('open'); }")
    view_text("evaluation", product="cliffwater_cclfx")
    page.locator('[data-cite][data-cid="2.3"]').first.click()
    edgar_href = page.locator("#drawer [data-edgar] a").first.get_attribute("href")
    cit23 = json.loads((BASE / "data" / "citations" / "cliffwater_cclfx.json").read_text())["cells"]["2.3"][0]
    check("citation drawer: EDGAR link is the manifest URL of the resolved filing, accession shown",
          edgar_href == cit23["url"] and cit23["accession"] in page.locator("#drawer [data-edgar]").inner_text())
    page.evaluate("() => { document.getElementById('drawer').classList.remove('open'); }")

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
    packet_bad = []
    for k in bundle["packets"]:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/memos/{k}_committee_packet.docx") as resp:
                if resp.status != 200 or int(resp.headers["Content-Length"]) < 5000:
                    packet_bad.append(k)
        except Exception:  # noqa: BLE001
            packet_bad.append(k)
    check("all committee packets served, one per plan x product",
          not packet_bad and len(bundle["packets"]) == len(bundle["plan_order"]) * len(bundle["products"]))
    view_text("packet", product="cliffwater_cclfx", plan="plan_consulting_alumni")
    check("packet view: the committee packet link follows the selected plan",
          page.locator("#packetlink").get_attribute("href")
          == "memos/plan_consulting_alumni__cliffwater_cclfx_committee_packet.docx")
    printed = page.evaluate("""() => new Promise((res) => {
        window.print = () => res(document.body.className);
        document.querySelector('[data-print-pins]').click();
      })""")
    check("packet view: printing covers the pinned exhibits only (print class on during the dialog, off after)",
          "print-pins" in printed and "print-pins" not in page.evaluate("() => document.body.className"))
    check("one memo per plan x product in the bundle",
          len(bundle["memos"]) == len(bundle["plan_order"]) * len(bundle["products"])
          and all(f"{pl}__{pk}" in bundle["memos"]
                  for pl in bundle["plan_order"] for pk in bundle["products"]))
    view_text("benchmarks", product="cliffwater_cclfx", plan="plan_tech_media")
    href_tech = page.locator("#memolink").get_attribute("href")
    view_text("benchmarks", product="cliffwater_cclfx", plan="plan_consulting_alumni")
    href_cons = page.locator("#memolink").get_attribute("href")
    check("benchmark memo link follows the selected plan",
          href_tech == "memos/plan_tech_media__cliffwater_cclfx_decision_memo.docx"
          and href_cons == "memos/plan_consulting_alumni__cliffwater_cclfx_decision_memo.docx",
          f"{href_tech} / {href_cons}")

    # ---------- P2-8: plan intake form emits the intake file, refuses a sponsor-like label
    view_text("plans")
    pf = page.locator("[data-plan-form]")
    pf.evaluate("(d) => { d.open = true; }")
    pf.locator("[data-plan-make]").click()
    check("plan intake: an empty form produces nothing and says why",
          "required" in pf.locator("[data-plan-msg]").inner_text() and pf.locator("[data-plan-patch]").is_hidden())
    pf.locator('[data-f="display_label"]').fill("Acme Widgets Inc. 401(k)")
    pf.locator("[data-plan-make]").click()
    check("plan intake: a sponsor-like label is refused before anything else",
          "sponsor name" in pf.locator("[data-plan-msg]").inner_text())
    pf.locator('[data-f="display_label"]').fill("US regional hospital 403(b) plan (~$400M, OH)")
    for f, v in (("net_assets_eoy", "400000000"), ("with_account_balances", "5000"), ("active_eoy", "4200"),
                 ("separated_deferred_vested", "700"), ("pension_benefit_codes", "2e2g2j2k")):
        pf.locator(f'[data-f="{f}"]').fill(v)
    pf.locator("[data-plan-make]").click()
    check("plan intake: without the anonymization confirmation nothing is produced",
          "confirm" in pf.locator("[data-plan-msg]").inner_text() and pf.locator("[data-plan-patch]").is_hidden())
    pf.locator('[data-f="anonymization_label"]').check()
    pf.locator("[data-plan-make]").click()
    try:
        intake_doc = json.loads(pf.locator("[data-plan-patch]").inner_text())
    except Exception:  # noqa: BLE001
        intake_doc = {}
    check("plan intake: the file carries the label, the confirmation, the codes upper-cased and a derived preview",
          intake_doc.get("anonymization_label") == "US regional hospital 403(b) plan (~$400M, OH)"
          and intake_doc.get("pension_benefit_codes") == "2E2G2J2K"
          and intake_doc.get("derived_preview", {}).get("avg_balance_per_account") == 80000
          and "identity_private" not in intake_doc)
    # R2-P2-2: the file is offered as a named download whose bytes are the
    # text on screen, with a copy button, and the site still writes nothing
    _dl = pf.locator("a[data-download]")
    _blob_text = page.evaluate("async (u) => (await fetch(u)).text()", _dl.get_attribute("href"))
    check("plan intake: the intake file downloads under a plan_intake name with the same bytes as the text shown",
          _dl.get_attribute("download") == "plan_intake_us_regional_hospital_403_b_plan_400m_oh.json"
          and _dl.get_attribute("href").startswith("blob:") and _blob_text == pf.locator("[data-plan-patch]").inner_text()
          and pf.locator("[data-copy]").count() == 1)
    pf.locator('[data-f="display_label"]').fill("US consulting company 401(k) plan (~$50M, CO)")
    pf.locator("[data-plan-make]").click()
    check("plan intake: a description with the words company and CO is accepted (audit item 39)",
          not pf.locator("[data-plan-patch]").is_hidden()
          and json.loads(pf.locator("[data-plan-patch]").inner_text()).get("display_label", "").endswith("CO)"))
    pf.locator('[data-f="display_label"]').fill("")
    pf.locator("[data-plan-make]").click()
    check("plan intake: a refused form hides the previous file and its download",
          pf.locator("[data-plan-patch]").is_hidden() and pf.locator("[data-file-actions]").is_hidden())

    # ---------- P2-7: verification view, quote beside value, command from signer and date
    view_text("verification")
    order = page.evaluate("() => [...document.querySelectorAll('tr[data-q]')].map((r) => r.dataset.q)")
    check("verification: queue order is the document's order, unchanged by the forms",
          order == [f"{it['product']}:{it['cell']}" for it in bundle["verification_queue"]["queue"]])
    check("verification: every queue row has a verify form with the value and the quote side by side",
          page.locator("[data-verify-form]").count() == len(order)
          and page.locator("[data-verify-form] .sidebyside").count() == len(order))
    vf = page.locator("[data-verify-form]").first
    vf.evaluate("(d) => { d.open = true; }")
    vf.locator("[data-verify-make]").click()
    check("verification: no signer or date produces nothing and says why",
          "both required" in vf.locator("[data-verify-msg]").inner_text()
          and vf.locator("[data-verify-cmd]").is_hidden())
    vf.locator('[data-f="signer"]').fill("A. Person, committee chair")
    vf.locator('[data-f="date"]').fill("2026-09-04")
    vf.locator("[data-verify-make]").click()
    _req = json.loads(vf.locator("[data-verify-cmd]").inner_text())
    check("verification: the signature request is offered as a named file download with a copy button",
          vf.locator("a[data-download]").get_attribute("download") == f"verify_{order[0].replace(':', '_')}.json"
          and vf.locator("a[data-download]").get_attribute("href").startswith("blob:")
          and vf.locator("[data-copy]").count() == 1)
    check("verification: the signature request names the product, cell, signer and date, no command line, "
          "nothing is written by the site",
          _req.get("signature_request") == "verify"
          and f"{_req.get('product')}:{_req.get('cell')}" == order[0]
          and _req.get("signer") == "A. Person, committee chair" and _req.get("date") == "2026-09-04"
          and "writes nothing" in vf.locator("[data-verify-msg]").inner_text())

    # ---------- P1-26: authority panel and rule references ----------
    page.evaluate("() => { document.querySelector('details.authority').open = true; }")
    auth_t = page.locator("details.authority").inner_text()
    check("authority panel: title, citation, RIN, section, six paragraph letters",
          all(x in auth_t for x in ("Fiduciary Duties in Selecting Designated Investment Alternatives",
                                    "91 FR 16088", "RIN 1210-AC38", "2550.404a-6"))
          and all(f"paragraph ({c})" in auth_t for c in "ghijkl"))
    check("authority panel: Federal Register link and docket",
          page.locator("#fr_link").get_attribute("href") == bundle["rule"]["fr_url"]
          and bundle["rule"]["docket"] in auth_t)
    check("authority panel: verbatim status is the build's, never text from memory",
          page.locator("#auth_status").inner_text() == bundle["rule"]["authority"]["status"]
          and (bundle["rule"]["authority"]["status"] == "fetched" or "not yet in this build" in auth_t))
    check("authority panel: scope sentence (selection, not monitoring) and advisor-completed cells",
          "Monitoring is not documented here" in auth_t and "6.6 and 6.8" in auth_t)
    # once the text is fetched, the panel quotes the rule paragraph under
    # every letter byte for byte from the hashed record, the lead in view
    # and the Department's examples folded, and the first-paint bundle
    # carries none of it (the paragraphs ride the lazy chunk)
    from tark_data import authority as _authority
    _auth = _authority()
    if _auth["status"] == "fetched":
        page.wait_for_selector("[data-authority-lead='(k)']", timeout=15000)
        auth_t = page.locator("details.authority").inner_text()
        _leads = {c: page.locator(f"[data-authority-lead='({c})']").inner_text() for c in "ghijkl"}
        check("authority panel: every lead paragraph (g) to (l) is the fetched record's text verbatim",
              all(_leads[c] == _auth["paragraphs"][c][0] for c in "ghijkl"))
        _folded = page.locator("details.authority details.authmore").count()
        check("authority panel: the examples under each letter are folded, none dropped",
              _folded == sum(1 for c in "ghijkl" if len(_auth["paragraphs"][c]) > 1)
              and all(f"{len(_auth['paragraphs'][c]) - 1} further paragraph" in auth_t.lower()
                      or len(_auth["paragraphs"][c]) < 2
                      for c in "ghijkl")
              and "paragraphs" not in bundle["rule"]["authority"])
    else:
        check("authority panel: nothing quoted when the text is not fetched",
              page.locator("[data-authority-lead]").count() == 0)
    ev_t = view_text("evaluation", product="hl_paf")
    check("evaluation: every factor shows its rule paragraph and the build's basis sentence",
          all(f"rule paragraph ({c})" in ev_t for c in "ghijkl")
          and ev_t.count(f"Basis: {bundle['rule']['mapping_basis']}") == 6)
    # ---------- P2-6: advisor-stated cells, form emits a patch, nothing is faked
    n_forms = page.locator("[data-advisor-form]").count()
    n_stated = page.locator("[data-advisor-stated]").count()
    check("evaluation: every committee cell shows either a statement or a form, six in all",
          n_forms + n_stated == 6 and page.locator("[data-advisor-count]").inner_text()
          == f"advisor-stated for this plan: {n_stated} of 6")
    if n_forms:
        form = page.locator("[data-advisor-form]").first
        form.evaluate("(d) => { d.open = true; }")     # view_text may have toggled it already
        form.locator("[data-advisor-make]").click()
        check("advisor form: an empty form produces nothing and says why",
              "all required" in form.locator("[data-advisor-msg]").inner_text()
              and form.locator("[data-advisor-patch]").is_hidden())
        form.locator('[data-f="value"]').fill("Recordkeeper confirmed quarterly window handling.")
        form.locator('[data-f="signer"]').fill("A. Person, committee chair")
        form.locator('[data-f="date"]').fill("2026-09-04")
        form.locator("[data-advisor-make]").click()
        patch_text = form.locator("[data-advisor-patch]").inner_text()
        cid = form.get_attribute("data-advisor-form")
        try:
            patch = json.loads(patch_text)
        except Exception:  # noqa: BLE001
            patch = {}
        check("advisor form: the output is valid JSON for this plan and product, signed and dated, no comment line",
              patch_text.startswith("{")
              and patch.get("plan") == "plan_tech_media" and patch.get("product") == "hl_paf"
              and patch.get("cells", {}).get(cid, {}).get("signer") == "A. Person, committee chair"
              and patch["cells"][cid]["status"].startswith("advisor-stated - A. Person")
              and "not evidence" in patch.get("not_evidence", ""))
        check("advisor form: the statement is offered as a named file download with a copy button",
              form.locator("a[data-download]").get_attribute("download") == "advisor_plan_tech_media__hl_paf.json"
              and form.locator("a[data-download]").get_attribute("href").startswith("blob:")
              and form.locator("[data-copy]").count() == 1)
    check("evaluation: cells 6.6 and 6.8 carry the advisor-completed chip, no other cell does",
          page.locator("[data-advisor-completed]").count() == 2
          and all("paragraph (l)" in page.locator("[data-advisor-completed]").nth(i).inner_text()
                  for i in range(2)))

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
    _evc = bundle["cohorts"]["evergreen_pe"]["composite"]
    check("evergreen private equity cohort (R3-P2-5): the composite is formed over the four March-year-end members, "
          "the December member is excluded by name with its reason on screen, and no product key prints",
          page.locator("#compchart svg").count() == 1 and page.locator("[data-composite-note]").count() == 1
          and "KKR Private Equity Conglomerate LLC" in t and "calendar years" in t
          and _evc.get("composite_members") and len(_evc["composite_members"]) == 4
          and [e["member"] for e in _evc["excluded_members"]] == ["KKR Private Equity Conglomerate LLC"]
          and "kkr_kpec" not in t)
    page.evaluate("() => window.tarkSetState({view: 'cohorts', cohort: 'private_credit'})")
    page.wait_for_selector("#compchart svg", timeout=5000)
    _pc_rows = bundle["cohorts"]["private_credit"]["composite"]["rows"]
    _formed = [r for r in _pc_rows if r["composite_return_pct"] is not None]
    check("private credit cohort: the calendar-year composite chart renders one marker per formed composite "
          "return and the note says where a composite exists",
          bool(_formed) and len(_formed) < len(_pc_rows)
          and page.locator("#compchart svg circle[r='3.4']").count() == len(_formed)
          and "composite return exists only where every member reports the period"
          in page.locator("#view").inner_text())
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
    # census promotions grew private_credit 3 -> 5 (cion_ares, ocic)
    check("screener: cohort filter private_credit returns exactly 5",
          pc_rows == 5, str(pc_rows))
    page.evaluate("""() => window.tarkSetState({f_cohort: '', f_depth: 'cohort'})""")
    d_rows = page.evaluate("""() =>
        document.querySelectorAll('table.screener tbody tr').length""")
    check("screener: depth=cohort returns the 10 cohort-tier products "
          "(8 cohort build + 2 census promotions)",
          d_rows == 10, str(d_rows))
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

    # ---------- dead bundle keys: emitted but never read by any view ----------
    reads = set(page.evaluate("() => [...window.__tarkReads]"))
    series_bundle = json.loads((SITE / "series.js").read_text().split("\n")[0]
                               [len("window.TARK_SERIES = "):-1])
    lab_bundle = json.loads((SITE / "series.js").read_text().split("\n")[2]
                            [len("window.TARK_LAB = "):-1])
    evidence_bundle = json.loads((SITE / "series.js").read_text().split("\n")[3]
                                 [len("window.TARK_EVIDENCE = "):-1])
    emitted = set()
    for k in bundle:
        if k in ("series", "liquidity", "swap_matrix"):
            continue          # placeholders merged from the lazy chunk
        emitted.add(k)
        if isinstance(bundle[k], dict) and k in ("supplement", "metrics", "series_monthly",
                                                  "series_quarterly"):
            emitted |= {f"{k}.{kk}" for kk in bundle[k]}
    emitted |= {f"series.{k}" for k in series_bundle}
    emitted |= {f"lab.{k}" for k in lab_bundle}
    emitted |= {f"evidence.{k}" for k in evidence_bundle}
    emitted |= {f"census.{k}" for k in census_bundle}
    dead = sorted(emitted - reads)
    check("bundle has no key that no view reads (runtime Proxy over the whole sweep)",
          not dead, "; ".join(dead[:8]))

    check("no page errors across the whole run", not errors,
          "; ".join(errors[:3]))
    # ---------- VERIFY 6: the ten Tier 1 cells, drawer against the evidence CSV
    import csv as _csv
    tier1 = [it for it in bundle["verification_queue"]["queue"] if it["tier"] == 1]
    t1_bad = []
    for it in tier1:
        rows = {r["cell_id"]: r for r in _csv.DictReader(open(BASE / "data" / "evidence" / f"{it['product']}_evidence.csv", newline=""))}
        r = rows[it["cell"]]
        view_text("evaluation", product=it["product"])
        page.locator(f'[data-cite][data-cid="{it["cell"]}"]').first.click()
        body = page.locator("#drawer .dbody").inner_text()
        page.evaluate("() => { document.getElementById('drawer').classList.remove('open'); }")
        norm = lambda t: re.sub(r"\s+", " ", t).strip()
        if not (norm(r["source_doc"]) in norm(body) and norm(r["quote"]) in norm(body)
                and (not r.get("accession") or r["accession"].startswith("multiple") or r["accession"] in norm(body))):
            t1_bad.append(f"{it['product']} {it['cell']}")
    check(f"Tier 1 manual check, automated: drawer document, quote and accession equal the CSV for all {len(tier1)} cells "
          "(EDGAR HTTP status cannot be checked from this container)", bool(tier1) and not t1_bad, "; ".join(t1_bad))

    # ---------- VERIFY 7: the demo script speaks only what is on screen (R2-P0-10)
    # docs/demo_script.md ends with a "## Surface checks" block, one line per
    # spoken text: view | product | plan | text. Every text must render on
    # that view under that plan (case-folded: stat labels render uppercase).
    # A drawer row names the cell in the plan column and reads the citation
    # drawer of that cell on the Evaluation view.
    _script = (BASE / "docs" / "demo_script.md").read_text()
    check("demo script: the title carries a version and the queue's Tier 1 names the same one",
          bool(re.search(r"Demo Script v(\d+)", _script))
          and re.search(r"Demo Script v(\d+)", _script).group(1)
          == (re.search(r"demo_script\.md` \(v(\d+)\)", (BASE / "docs" / "verification_queue.md").read_text()) or re.match(r"(x)", "x")).group(1))
    _blk = _script.split("## Surface checks", 1)
    _rows = []
    if len(_blk) == 2:
        for _line in _blk[1].splitlines():
            _mm = re.match(r"-\s+(\w+)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|\s*(.+?)\s*$", _line.strip())
            if _mm:
                _rows.append(_mm.groups())
    _fold = lambda t: re.sub(r"\s+", " ", t).strip().lower()  # noqa: E731
    _miss = []
    for _view, _product, _plan, _token in _rows:
        if _view == "drawer":
            view_text("evaluation", product=_product)
            page.locator(f'[data-cite][data-cid="{_plan}"]').first.click()
            _body = page.locator("#drawer .dbody").inner_text()
            page.evaluate("() => { document.getElementById('drawer').classList.remove('open'); }")
        else:
            _body = view_text(_view, plan=_plan, product=("hl_paf" if _product == "-" else _product))
        if _fold(_token) not in _fold(_body):
            _miss.append(f"{_view}/{_product}/{_plan}: {_token}")
    check(f"demo script: all {len(_rows)} surface-check texts render on the named view under the named plan",
          len(_rows) >= 20 and not _miss, "; ".join(_miss[:6]))
    # decision 7.27: the peer ratio may be spoken, but only as the labeled
    # peer comparison, never as a benchmark or a PME, and only the number the
    # artifact holds. Every ratio-shaped number in the spoken part must sit
    # in a sentence that names the peer comparison, that sentence must not
    # call it a benchmark or a PME, and the value must be Slot G's ratio for
    # cliffwater_cclfx (the one product whose peer ratio the script speaks).
    _spoken = _script.split("## Numbers this script speaks")[0]
    _g = (bundle["benchmarks"]["cliffwater_cclfx"].get("slot_g") or {}).get("composite") or {}
    _ratio_ok = True
    _why = []
    for _m in re.finditer(r"relative wealth ratio (?:of )?(\d\.\d{2,4})", _spoken):
        _sent = _spoken[max(0, _m.start() - 400):_m.end() + 250]
        _sent = re.split(r"(?<=[.!?])\s+", _sent[:400 + _m.end() - _m.start()])[-1] + re.split(r"(?<=[.!?])\s+", _sent[400 + _m.end() - _m.start():])[0]
        _low = _sent.lower()
        if "peer comparison" not in _low and "paragraphs (g) and (h)" not in _low:
            _ratio_ok, _why = False, _why + ["ratio spoken outside the labeled peer comparison"]
        if re.search(r"\bpme\b|ks-pme|benchmark", _low.replace("not a benchmark", "").replace("not a pme", "")):
            _ratio_ok, _why = False, _why + ["ratio sentence names a benchmark or a PME"]
        if _g.get("status") != "computed" or float(_m.group(1)) != _g.get("relative_wealth_ratio"):
            _ratio_ok, _why = False, _why + [f"spoken {_m.group(1)} vs artifact {_g.get('relative_wealth_ratio')}"]
    check("demo script: any peer ratio spoken is labeled as the peer comparison, never a benchmark or a PME, and "
          "equals Slot G's ratio (decision 7.27)", _ratio_ok, "; ".join(_why[:3]))
    check("demo script: no v2 composite ratio survives (0.97xx) and every KS-PME spoken carries the Yahoo caveat "
          "nearby", not re.search(r"\b0\.97\d\d\b", _spoken)
          and all("yahoo adjusted close" in _spoken[max(0, m.start() - 500):m.end() + 500].lower()
                  or "filed fiscal-year returns" in _spoken[max(0, m.start() - 500):m.end() + 500].lower()
                  for m in re.finditer(r"KS-PME \d\.\d{4}", _spoken)))

    # ---------- R3-P0-2: the three Tuesday fixes, each in a fresh browser context
    # (1) a fresh load of the Screener and of the Comparison renders a citation
    # button on every fact cell whose cell has a source, before the lazy chunk
    # carries the drawer detail, and the count equals the count after the chunk
    def _expected_cite_count(pg):
        return pg.evaluate("""() => {
            const T = window.TARK; let n = 0;
            for (const b of document.querySelectorAll('#view [data-cite]')) {
              const { key, cid } = b.dataset;
              if ((T.products[key].cited || '').split(',').includes(cid)) n += 1;
            }
            return [document.querySelectorAll('#view [data-cite]').length, n];
        }""")
    _fresh = browser.new_context()
    _fp = _fresh.new_page(); _ferr = []
    _fp.on("pageerror", lambda e: _ferr.append(str(e)))
    _fp.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")
    _chunk_before = _fp.evaluate("() => !!window.TARK.series")
    _total, _cited = _expected_cite_count(_fp)
    _rows_without = _fp.evaluate("""() => [...document.querySelectorAll('#view table.screener tbody tr')]
        .filter((tr) => !tr.querySelector('[data-cite]')).length""")
    check("R3-P0-2 (1): a fresh Screener load renders a citation button on every cited fact cell "
          "(no lazy chunk loaded yet, every button names a cited cell, no product row without one)",
          not _chunk_before and _total > 0 and _total == _cited and _rows_without == 0 and not _ferr,
          f"chunk loaded before render={_chunk_before}, buttons={_total}, cited={_cited}, "
          f"rows without a button={_rows_without}, errors={_ferr[:1]}")
    _fp.locator("#view [data-cite]").first.click()
    _fp.wait_for_timeout(600)
    _drawer_doc = _fp.evaluate("() => document.getElementById('drawer').classList.contains('open') "
                               "? (document.querySelector('#drawer .dbody .v') || {}).innerText || '' : ''")
    check("R3-P0-2 (1): clicking a citation on the fresh load opens the drawer with the document name "
          "after the chunk arrives", bool(_drawer_doc.strip()) and _fp.evaluate("() => !!window.TARK.series"),
          _drawer_doc[:60])
    _fp.evaluate("() => window.tarkSetState({view: 'screener'})")
    _fp.wait_for_timeout(200)
    _after = _expected_cite_count(_fp)
    check("R3-P0-2 (1): the Screener's citation count is the same before and after the lazy chunk",
          _after[0] == _total, f"{_total} before, {_after[0]} after")
    # the first-paint list is exactly the set of cells whose drawer detail
    # carries a source, product by product, once the chunk is merged
    _list_vs_chunk = _fp.evaluate("""() => {
        const T = window.TARK; const bad = [];
        for (const [k, p] of Object.entries(T.products)) {
          const listed = (p.cited || '').split(',').filter(Boolean).sort().join(',');
          const sourced = Object.entries(p.cells).filter(([, c]) => c.source).map(([cid]) => cid).sort().join(',');
          if (listed !== sourced) bad.push(k);
        }
        return bad;
    }""")
    check("R3-P0-2 (1): the first-paint cited list equals the set of cells with a source in the chunk, "
          "all 16 products", not _list_vs_chunk, ", ".join(_list_vs_chunk))
    _cp = browser.new_context().new_page()
    _cp.goto(f"http://127.0.0.1:{PORT}/#view=compare&plan=plan_tech_media&product=hl_paf"
             f"&compare=hl_paf,cliffwater_cclfx", wait_until="networkidle")
    _ct, _cc = _expected_cite_count(_cp)
    check("R3-P0-2 (1): a fresh Comparison load renders its citation buttons before the lazy chunk",
          not _cp.evaluate("() => !!window.TARK.series") and _ct > 0 and _ct == _cc,
          f"buttons={_ct}, cited={_cc}")
    _cp.context.close()
    _fresh.close()

    # (2) the browser Back button: three navigations by real clicks on the nav,
    # then three Backs, return to the landing route with the site still open,
    # Forward works, and a filter change adds no history entry
    _bc = browser.new_context(); _bp = _bc.new_page(); _berr = []
    _bp.on("pageerror", lambda e: _berr.append(str(e)))
    _bp.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")
    _landing = _bp.evaluate("() => location.hash")
    _h1s = []
    for _v in ("roster", "plans", "coverage"):
        _bp.click(f"button.navitem[data-view={_v}]")
        _bp.wait_for_timeout(150)
    _h1s.append(_bp.locator("#view h1").first.inner_text())
    for _ in range(3):
        _bp.go_back()
        _bp.wait_for_timeout(250)
        _h1s.append(_bp.locator("#view h1").first.inner_text())
    _on_site = _bp.url.startswith(f"http://127.0.0.1:{PORT}/")
    check("R3-P0-2 (2): three navigations then three Backs return to the landing route with the site open",
          _on_site and _bp.evaluate("() => location.hash") == _landing
          and _h1s == ["Coverage & Provenance", "Reference Plans", "Candidate Roster", "Screener"]
          and not _berr, f"on site={_on_site}, hash={_bp.evaluate('() => location.hash')}, h1s={_h1s}, {_berr[:1]}")
    _bp.go_forward()
    _bp.wait_for_timeout(250)
    check("R3-P0-2 (2): Forward re-renders the next route",
          _bp.locator("#view h1").first.inner_text() == "Candidate Roster")
    _bp.go_back(); _bp.wait_for_timeout(250)
    _len0 = _bp.evaluate("() => history.length")
    _bp.select_option("select[data-f=f_tax]", "K-1"); _bp.wait_for_timeout(150)
    _bp.select_option("select[data-f=f_tax]", "1099"); _bp.wait_for_timeout(150)
    check("R3-P0-2 (2): a filter change replaces the history entry instead of pushing one",
          _bp.evaluate("() => history.length") == _len0
          and "f_tax=1099" in _bp.evaluate("() => location.hash"))
    _bp.evaluate("() => window.tarkSetState({product: 'cliffwater_cclfx', view: 'evaluation'})")
    _bp.wait_for_timeout(300)
    _bp.go_back(); _bp.wait_for_timeout(250)
    check("R3-P0-2 (2): a product change pushes an entry and Back restores the previous product and view",
          _bp.evaluate("() => location.hash").startswith("#view=screener&plan=plan_tech_media&product=hl_paf"))
    _bc.close()

    # (3) every coverage ring on the Roster and on Coverage has a nonzero
    # rendered size (they rendered at 0 by 0 before, 37 invisible rings)
    _sizes = {}
    for _v in ("roster", "coverage"):
        page.evaluate(f"() => window.tarkSetState({{view: '{_v}', plan: 'plan_tech_media', product: 'hl_paf'}})")
        page.wait_for_timeout(300)
        _sizes[_v] = page.evaluate("() => [...document.querySelectorAll('#view svg[data-donut]')].map("
                                   "(s) => { const r = s.getBoundingClientRect(); return [r.width, r.height]; })")
    check("R3-P0-2 (3): every donut on the Roster (16) and Coverage (17) has a nonzero rendered size",
          len(_sizes["roster"]) == 16 and len(_sizes["coverage"]) == 17
          and all(w >= 48 and h >= 48 for v in _sizes.values() for w, h in v),
          f"roster={len(_sizes['roster'])} coverage={len(_sizes['coverage'])} "
          f"min={min((min(w, h) for v in _sizes.values() for w, h in v), default=None)}")

    # ---------- VERIFY 5: mobile (390 px) and print renders of Roster, Evaluation, Benchmarks
    mobile = browser.new_page(viewport={"width": 390, "height": 844})
    m_err = []
    mobile.on("pageerror", lambda e: m_err.append(str(e)))
    mobile.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")
    mobile.evaluate("""() => new Promise((res) => { const s = document.createElement('script'); s.src = 'series.js';
        s.onload = () => { window.tarkMergeLazy(); res(true); }; document.head.append(s); })""")
    overflow = []
    for v in ("roster", "evaluation", "benchmarks"):
        mobile.evaluate(f"() => window.tarkSetState({{view: '{v}', plan: 'plan_tech_media', product: 'hl_paf'}})")
        mobile.wait_for_timeout(200)
        w = mobile.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")
        if w[0] > w[1] + 2:
            overflow.append(f"{v}: {w[0]}px wide in a {w[1]}px viewport")
    check("mobile 390 px: Roster, Evaluation and Benchmarks render without horizontal overflow or errors",
          not overflow and not m_err, "; ".join(overflow + m_err[:2]))
    mobile.emulate_media(media="print")
    p_err = []
    for v in ("roster", "evaluation", "benchmarks"):
        mobile.evaluate(f"() => window.tarkSetState({{view: '{v}', plan: 'plan_tech_media', product: 'hl_paf'}})")
        mobile.wait_for_timeout(200)
        if len(mobile.locator("#view").inner_text()) < 200:
            p_err.append(v)
    check("print media: the same three views still render their content", not p_err and not m_err, "; ".join(p_err))
    mobile.close()

    browser.close()

httpd.shutdown()
print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll frontend tests pass.")
sys.exit(1 if FAILS else 0)

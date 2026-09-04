/* Tark shell: nav, context chips, hash router, drawer, palette, density.
 * URL state is KEYS/IDS/NUMBERS ONLY — every value is validated against a
 * whitelist on read, so a shared link can never carry free text (leak-proof
 * by construction). Search queries and pins live in memory/localStorage. */
import { viewPlans, viewRoster, viewEvaluation, viewBenchmarks, viewPme,
         viewLiquidity, viewFees, viewDxyz, viewDesmooth, viewCoverage,
         esc } from "./views.js";
import { viewScreener, viewCompare, viewVerification, viewSearch, viewPacket,
         viewCohorts, initPalette } from "./workbench.js";
import { viewCensus, viewFunnel } from "./census.js";

const T = window.TARK;

const VIEWS = [
  ["census", "Universe", viewCensus, "universe"],
  ["funnel", "The Funnel", viewFunnel, "universe"],
  ["screener", "Screener", viewScreener, "workbench"],
  ["compare", "Comparison", viewCompare, "workbench"],
  ["search", "Evidence Search", viewSearch, "workbench"],
  ["packet", "Packet", viewPacket, "workbench"],
  ["plans", "Reference Plans", viewPlans, "context"],
  ["roster", "Candidate Roster", viewRoster, "context"],
  ["evaluation", "Six-Factor Evaluation", viewEvaluation, "record"],
  ["benchmarks", "Benchmark Selection", viewBenchmarks, "record"],
  ["cohorts", "Cohorts", viewCohorts, "record"],
  ["fees", "Fee Matrix", viewFees, "record"],
  ["liquidity", "Liquidity Match", viewLiquidity, "record"],
  ["pme", "Analysis Lab", viewPme, "analytics"],
  ["dxyz", "DXYZ Price vs NAV", viewDxyz, "analytics"],
  ["desmooth", "De-smoothing Lab", viewDesmooth, "analytics"],
  ["coverage", "Coverage & Provenance", viewCoverage, "integrity"],
  ["verification", "Verification", viewVerification, "integrity"],
];
const GROUPS = { universe: "Universe (T1)", workbench: "Workbench", context: "Context",
  record: "The Record", analytics: "Interactive Analytics",
  integrity: "Integrity" };

/* ---- URL state: whitelisted keys, validated values ---- */
const state = {
  view: "screener", plan: T.plan_order[0], product: "hl_paf",
  compare: "", proxy: "", win: "", rho: "", density: "comfortable",
  f_wrapper: "", f_base: "", f_tax: "", f_gate: "", f_big4: "",
  f_verdict: "", f_vonly: "", pme_min: "", pme_max: "",
  sort: "", dir: "", cols: "",
  c_class: "", c_listed: "", c_interval: "", c_tender: "", c_eval: "",
  c_amin: "", c_amax: "", c_hint: "", c_cik: "",
};
const VALID = {
  view: (v) => VIEWS.some(([id]) => id === v),
  plan: (v) => !!T.plans[v],
  product: (v) => !!T.products[v],
  compare: (v) => v.split(",").every((k) => !k || T.products[k]),
  proxy: (v) => !v || !!T.proxy_library[v],
  win: (v) => !v || /^\d{1,3}$/.test(v),
  rho: (v) => !v || /^0?\.\d{1,2}$|^0$/.test(v),
  density: (v) => ["comfortable", "compact"].includes(v),
  cohort: (v) => !v || !!T.cohorts[v],
  f_cohort: (v) => !v || !!T.cohorts[v],
  f_depth: (v) => !v || ["full", "cohort"].includes(v),
  f_wrapper: (v) => !v || ["tender_offer", "interval_23c3", "listed_cef",
    "nontraded_reit", "nontraded_llc", "nontraded_bdc", "listed_bdc"].includes(v),
  f_base: (v) => !v || ["net_assets", "managed_assets", "gross_incl_borrowings",
    "nav", "outstanding_shares", "aggregate_nav",
    "lesser_of_dual_base"].includes(v),
  f_tax: (v) => !v || ["1099", "K-1"].includes(v),
  f_gate: (v) => !v || ["yes", "no"].includes(v),
  f_big4: (v) => !v || ["yes", "no"].includes(v),
  f_verdict: (v) => !v || ["aligned-mechanical", "conditional",
    "conditional-weak"].includes(v),
  f_vonly: (v) => !v || v === "1",
  pme_min: (v) => !v || /^\d{0,2}(\.\d{1,4})?$/.test(v),
  pme_max: (v) => !v || /^\d{0,2}(\.\d{1,4})?$/.test(v),
  sort: (v) => !v || /^[a-z0-9_]{1,16}$/.test(v),
  dir: (v) => !v || ["asc", "desc"].includes(v),
  cols: (v) => !v || /^[a-z0-9.]{1,200}$/.test(v),
  /* census filters: enums + numbers only; text search never enters the URL */
  c_class: (v) => !v || ["bdc", "interval_23c3", "tender_cef",
    "nontraded_reit", "listed_cef", "unlisted_cef_other",
    "nontraded_34act_other"].includes(v),
  c_listed: (v) => !v || ["yes", "no"].includes(v),
  c_interval: (v) => !v || v === "1",
  c_tender: (v) => !v || ["24m", "60m", "ever"].includes(v),
  c_eval: (v) => !v || ["yes", "no"].includes(v),
  c_amin: (v) => !v || /^\d{1,7}$/.test(v),
  c_amax: (v) => !v || /^\d{1,7}$/.test(v),
  c_hint: (v) => !v || /^[a-z-]{1,20}\?$/.test(v),
  c_cik: (v) => !v || /^\d{1,10}$/.test(v),
};

function readHash() {
  const h = new URLSearchParams(location.hash.replace(/^#\??/, ""));
  for (const [k, validate] of Object.entries(VALID)) {
    const v = h.get(k);
    if (v !== null && validate(v)) state[k] = v;
  }
}

function writeHash() {
  const h = new URLSearchParams();
  for (const k of Object.keys(VALID)) {
    if (state[k] && !(k === "density" && state[k] === "comfortable")) {
      h.set(k, state[k]);
    }
  }
  history.replaceState(null, "", "#" + h.toString());
}

export function setState(patch) {
  Object.assign(state, patch);
  writeHash();
  render();
}
window.tarkSetState = setState; // for tests + palette

function buildNav() {
  const nav = document.getElementById("navitems");
  nav.innerHTML = "";
  let lastGroup = null;
  for (const [id, label, , group] of VIEWS) {
    if (group !== lastGroup) {
      const g = document.createElement("div");
      g.className = "navgroup";
      g.textContent = GROUPS[group];
      nav.append(g);
      lastGroup = group;
    }
    const b = document.createElement("button");
    b.className = "navitem" + (state.view === id ? " active" : "");
    b.dataset.view = id;
    b.textContent = label;
    b.addEventListener("click", () => setState({ view: id }));
    nav.append(b);
  }
}

function buildTopbar() {
  const bar = document.getElementById("topbar");
  bar.innerHTML = `
    <span class="ctxchip"><label>Plan</label>
      <select id="planpick">${T.plan_order.map((k) =>
        `<option value="${k}" ${k === state.plan ? "selected" : ""}>${esc(T.plans[k].display_label)}</option>`).join("")}
      </select></span>
    <span class="ctxchip"><label>Product</label>
      <select id="prodpick">${Object.keys(T.products).map((k) =>
        `<option value="${k}" ${k === state.product ? "selected" : ""}>${esc(T.products[k].fund_name)}</option>`).join("")}
      </select></span>
    <button class="copylink" data-copylink title="Copy a shareable link (IDs only, no free text can enter the URL)">copy link</button>
    <button class="copylink" id="densitybtn">${state.density === "compact" ? "comfortable" : "compact"} density</button>
    <button class="copylink" id="palettebtn"><kbd>⌘K</kbd> palette</button>
    <span class="spacer"></span>
    <details class="authority"><summary>Authority</summary>
      ${esc(T.rule_caption)}</details>`;
  bar.querySelector("#planpick").addEventListener("change",
    (e) => setState({ plan: e.target.value }));
  bar.querySelector("#prodpick").addEventListener("change",
    (e) => setState({ product: e.target.value }));
  bar.querySelector("#densitybtn").addEventListener("click", () => setState(
    { density: state.density === "compact" ? "comfortable" : "compact" }));
  bar.querySelector("#palettebtn").addEventListener("click",
    () => window.tarkPalette.open());
}

/* the price/NAV series chunk is lazy-loaded (perf budget): chart/lab views
 * wait for series.js; screener/compare/plans first-paint stays light */
const SERIES_VIEWS = new Set(["evaluation", "pme", "dxyz", "desmooth",
                              "liquidity"]);
let seriesLoading = false;
function ensureSeries() {
  const root = document.getElementById("view");
  root.innerHTML = `<div class="nochart"><div class="k">Loading series</div>
    Loading the price/NAV series chunk, split from the core bundle so the
    screener and comparison views paint instantly.</div>`;
  if (!seriesLoading) {
    seriesLoading = true;
    const s = document.createElement("script");
    s.src = "series.js";
    s.onload = () => {
      window.TARK.series = window.TARK_SERIES;
      window.TARK.liquidity = window.TARK_LIQ;
      window.TARK.swap_matrix = window.TARK_LAB;   // lab verdict matrix
      render();
    };
    document.head.append(s);
  }
}

/* the census chunk (T1 universe, ~1.3k entities) is lazy-loaded the same
 * way — the universe views wait for census.js.data; nothing else pays */
const CENSUS_VIEWS = new Set(["census", "funnel"]);
let censusLoading = false;
function ensureCensus() {
  const root = document.getElementById("view");
  root.innerHTML = `<div class="nochart"><div class="k">Loading the universe</div>
    Loading the census chunk. The full T1 universe is split from the core
    bundle so the evaluated-roster views paint instantly.</div>`;
  if (!censusLoading) {
    censusLoading = true;
    const s = document.createElement("script");
    s.src = "census.data.js";
    s.onload = () => render();
    document.head.append(s);
  }
}

function render() {
  document.body.dataset.density = state.density;
  buildNav();
  buildTopbar();
  if (SERIES_VIEWS.has(state.view) && !window.TARK.series) {
    ensureSeries();
    return;
  }
  if (CENSUS_VIEWS.has(state.view) && !window.TARK_CENSUS) {
    ensureCensus();
    return;
  }
  const root = document.getElementById("view");
  const entry = VIEWS.find(([id]) => id === state.view);
  root.innerHTML = "";
  entry[2](root, state, setState);
  document.getElementById("drawer").classList.remove("open");
  window.scrollTo(0, 0);
}

/* copy-link affordance (event delegation — buttons exist across views) */
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-copylink]");
  if (!b) return;
  navigator.clipboard?.writeText(location.href).then(() => {
    const old = b.textContent;
    b.textContent = "copied ✓";
    setTimeout(() => { b.textContent = old; }, 1200);
  });
});

document.getElementById("drawerclose").addEventListener("click",
  () => document.getElementById("drawer").classList.remove("open"));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") document.getElementById("drawer").classList.remove("open");
});

/* same-document hash navigation (pasted share-links, back/forward) must
 * re-read state and re-render — the URL is the source of truth */
window.addEventListener("hashchange", () => {
  readHash();
  render();
});

readHash();
writeHash();
initPalette(setState, VIEWS.map(([id, label]) => [id, label]));
render();

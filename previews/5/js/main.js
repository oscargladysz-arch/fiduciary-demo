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
/* R3-P0-2: the browser Back button is a site affordance. A change of view,
 * plan, product, cohort or census entity pushes a history entry, everything
 * else (filters, sort, columns, window, density, sliders) replaces it, and
 * Back or Forward re-renders the route the URL names. */
const DEFAULTS = { ...state, cohort: "", f_cohort: "", f_depth: "" };
const NAV_KEYS = ["view", "plan", "product", "cohort", "c_cik"];
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
  f_wrapper: (v) => !v || v in T.wrapper_labels,
  f_base: (v) => !v || v in T.base_labels,
  f_tax: (v) => !v || ["1099", "K-1"].includes(v),
  f_gate: (v) => !v || ["yes", "no"].includes(v),
  f_big4: (v) => !v || ["yes", "no"].includes(v),
  f_verdict: (v) => !v || ["aligned-mechanical", "conditional",
    "conditional-weak", "misaligned", "partial"].includes(v),
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

function currentHash() {
  const h = new URLSearchParams();
  for (const k of Object.keys(VALID)) {
    if (state[k] && !(k === "density" && state[k] === "comfortable")) {
      h.set(k, state[k]);
    }
  }
  return "#" + h.toString();
}

let renderedHash = "";
function writeHash(push = false) {
  const next = currentHash();
  if (push && next !== location.hash) history.pushState(null, "", next);
  else history.replaceState(null, "", next);
  renderedHash = next;
}

export function setState(patch) {
  const push = NAV_KEYS.some((k) => k in patch && String(patch[k]) !== String(state[k]));
  Object.assign(state, patch);
  writeHash(push);
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

/* the rule, its identifiers with links, the six factors with their paragraph
 * letters and, when fetched into the build, the verbatim paragraph text.
 * Nothing here paraphrases the regulation: absent the fetched file, the panel
 * says so. */
function authorityPanel() {
  const r = T.rule, a = r.authority;
  const factors = Object.entries(T.factors).map(([n, label]) => {
    const letter = T.rule_refs[`${n}.1`].para;
    const paras = a.paragraphs && a.paragraphs[letter.replace(/[()]/g, "")];
    // the first paragraph under a letter is the rule text, the rest are the
    // Department's examples and definitions: the rule text is always in
    // view, the rest one click away, every word the Federal Register's
    const body = paras
      ? `<blockquote class="verbatim" data-authority-lead="${esc(letter)}">${esc(paras[0])}</blockquote>`
        + (paras.length > 1
          ? `<details class="authmore"><summary>${paras.length - 1} further paragraph${paras.length > 2 ? "s" : ""} under ${esc(letter)}, verbatim</summary>`
            + paras.slice(1).map((t) => `<blockquote class="verbatim">${esc(t)}</blockquote>`).join("") + `</details>`
          : "")
      : a.status === "fetched"
        ? `<div class="cap" data-authority-pending>paragraph ${esc(letter)}: loading the verbatim text.</div>`
        : `<div class="cap">paragraph ${esc(letter)}: ${esc(a.note)}</div>`;
    return `<div class="authfactor"><b>${n} · ${esc(label)}</b> <span class="cap">paragraph ${esc(letter)}</span>${body}</div>`;
  }).join("");
  return `<div class="authbody">
    <div><b>${esc(r.title)}</b>, ${esc(r.issuer)}. ${esc(r.citation)}, ${esc(r.rin)}, ${esc(r.section)}, paragraphs ${esc(r.paragraphs)}.</div>
    <div class="cap">Federal Register document <a href="${esc(r.fr_url)}" target="_blank" rel="noopener" id="fr_link">${esc(r.fr_document)}</a>
      · docket <a href="${esc(r.docket_url)}" target="_blank" rel="noopener">${esc(r.docket)}</a>
      · verbatim text: <span id="auth_status">${esc(a.status)}</span></div>
    <div class="cap">Scope of this build: the selection of a designated investment alternative, documented per product and per plan. Monitoring is not documented here. Cells 6.6 and 6.8 are advisor-completed under paragraph (l).</div>
    ${factors}
    <div class="cap">Factor mapping basis: ${esc(r.mapping_basis)}.</div>
  </div>`;
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
    <details class="authority"><summary>Authority</summary>${authorityPanel()}</details>`;
  const auth = bar.querySelector("details.authority");
  auth.addEventListener("toggle", () => {
    if (!auth.open || !T.rule.authority || T.rule.authority.status !== "fetched") return;
    if (T.rule.authority.paragraphs) return;
    loadSeriesChunk(() => {
      const d = document.querySelector("details.authority");
      if (d) { d.innerHTML = `<summary>Authority</summary>${authorityPanel()}`; d.open = true; }
    });
  });
  bar.querySelector("#planpick").addEventListener("change",
    (e) => setState({ plan: e.target.value }));
  bar.querySelector("#prodpick").addEventListener("change",
    (e) => setState({ product: e.target.value }));
  bar.querySelector("#densitybtn").addEventListener("click", () => setState(
    { density: state.density === "compact" ? "comfortable" : "compact" }));
  bar.querySelector("#palettebtn").addEventListener("click",
    () => window.tarkPalette.open());
}

/* the lazy chunk (series.js) carries the price/NAV series, the liquidity
 * matches, the lab matrix and the citation-drawer detail of every cell
 * (source, section, quote, extractor). Chart, lab and evidence views wait
 * for it; the screener, compare, plans, roster and benchmark first paint
 * stays light. */
const SERIES_VIEWS = new Set(["evaluation", "pme", "dxyz", "desmooth",
                              "liquidity", "cohorts", "search", "packet",
                              "verification", "fees"]);
window.tarkLoadSeries = (then) => loadSeriesChunk(then);
window.tarkMergeLazy = function () {
  // the chunk ships each series as a first date, day offsets and values:
  // expand back to [[date, value], ...] once, so every chart and lab reads
  // the same array the engine read
  const expand = (s) => {
    if (Array.isArray(s)) return s;
    const base = Date.UTC(+s.base.slice(0, 4), +s.base.slice(5, 7) - 1, +s.base.slice(8, 10));
    return s.d.map((off, i) => [new Date(base + off * 86400000).toISOString().slice(0, 10), s.v[i]]);
  };
  const series = {};
  for (const [k, s] of Object.entries(window.TARK_SERIES || {})) series[k] = expand(s);
  window.TARK.series = series;
  // the chunk carries each product's wrapper facts once and the stress
  // assumption sentence once: give every match its copy back
  const shared = window.TARK_LIQ_SHARED || { wrapper_facts: {}, stress_assumptions: "" };
  for (const m of Object.values(window.TARK_LIQ || {})) {
    if (!m.wrapper_facts) m.wrapper_facts = shared.wrapper_facts[m.product];
    if (m.stressed_scenario && m.stressed_scenario.assumptions === undefined) {
      m.stressed_scenario.assumptions = shared.stress_assumptions;
    }
  }
  window.TARK.liquidity = window.TARK_LIQ;
  window.TARK.swap_matrix = window.TARK_LAB;   // lab verdict matrix
  // the verbatim rule paragraphs, keyed by letter, when the text is in the build
  if (window.TARK.rule && window.TARK.rule.authority) {
    window.TARK.rule.authority.paragraphs = window.TARK_AUTHORITY || null;
  }
  const ev = window.TARK_EVIDENCE || {};
  for (const k of Object.keys(ev)) {
    for (const cid of Object.keys(ev[k])) Object.assign(window.TARK.products[k].cells[cid], ev[k][cid]);
  }
};
let seriesLoading = false;
const seriesWaiters = [];
/* one script element for the chunk however many callers ask: the series
 * views and the Authority panel both wait on the same load */
function loadSeriesChunk(then) {
  if (window.TARK.series) { then(); return; }
  seriesWaiters.push(then);
  if (seriesLoading) return;
  seriesLoading = true;
  const s = document.createElement("script");
  s.src = "series.js";
  s.onload = () => {
    window.tarkMergeLazy();
    while (seriesWaiters.length) seriesWaiters.shift()();
  };
  document.head.append(s);
}
function ensureSeries() {
  const root = document.getElementById("view");
  root.innerHTML = `<div class="nochart"><div class="k">Loading series</div>
    Loading the price/NAV series chunk, split from the core bundle so the
    screener and comparison views paint instantly.</div>`;
  loadSeriesChunk(render);
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

/* same-document navigation (Back, Forward, a pasted share-link) re-reads
 * the whole state from the URL, defaults first, so a key the URL no longer
 * carries does not survive from the previous route. popstate and
 * hashchange both fire on a fragment navigation: the second is a no-op. */
function routeFromUrl() {
  if (location.hash === renderedHash) return;
  Object.assign(state, DEFAULTS);
  readHash();
  renderedHash = location.hash;
  render();
}
window.addEventListener("popstate", routeFromUrl);
window.addEventListener("hashchange", routeFromUrl);

readHash();
writeHash();
initPalette(setState, VIEWS.map(([id, label]) => [id, label]));
render();

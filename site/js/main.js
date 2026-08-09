/* Tark shell: nav, context chips (plan + product), hash router, drawer. */
import { viewPlans, viewRoster, viewEvaluation, viewBenchmarks, viewPme,
         viewLiquidity, viewFees, viewDxyz, viewDesmooth, viewCoverage,
         esc } from "./views.js";

const T = window.TARK;

const VIEWS = [
  ["plans", "Reference Plans", viewPlans, "context"],
  ["roster", "Candidate Roster", viewRoster, "context"],
  ["evaluation", "Six-Factor Evaluation", viewEvaluation, "record"],
  ["benchmarks", "Benchmark Selection", viewBenchmarks, "record"],
  ["fees", "Fee Matrix", viewFees, "record"],
  ["liquidity", "Liquidity Match", viewLiquidity, "record"],
  ["pme", "PME Window Explorer", viewPme, "analytics"],
  ["dxyz", "DXYZ Price vs NAV", viewDxyz, "analytics"],
  ["desmooth", "De-smoothing (CCLFX)", viewDesmooth, "analytics"],
  ["coverage", "Coverage & Provenance", viewCoverage, "integrity"],
];
const GROUPS = { context: "Context", record: "The Record",
  analytics: "Interactive Analytics", integrity: "Integrity" };

const state = {
  view: "plans",
  plan: T.plan_order[0],
  product: "hl_paf",
};

function readHash() {
  const h = new URLSearchParams(location.hash.replace(/^#\??/, ""));
  if (h.get("view") && VIEWS.some(([id]) => id === h.get("view"))) state.view = h.get("view");
  if (h.get("plan") && T.plans[h.get("plan")]) state.plan = h.get("plan");
  if (h.get("product") && T.products[h.get("product")]) state.product = h.get("product");
}

function writeHash() {
  const h = new URLSearchParams({ view: state.view, plan: state.plan,
    product: state.product });
  history.replaceState(null, "", "#" + h.toString());
}

export function setState(patch) {
  Object.assign(state, patch);
  writeHash();
  render();
}
window.tarkSetState = setState; // for tests

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
    <span class="spacer"></span>
    <span class="cap" style="max-width:460px">${esc(T.rule_caption)}</span>`;
  bar.querySelector("#planpick").addEventListener("change",
    (e) => setState({ plan: e.target.value }));
  bar.querySelector("#prodpick").addEventListener("change",
    (e) => setState({ product: e.target.value }));
}

function render() {
  buildNav();
  buildTopbar();
  const root = document.getElementById("view");
  const entry = VIEWS.find(([id]) => id === state.view);
  root.innerHTML = "";
  entry[2](root, state, setState);
  document.getElementById("drawer").classList.remove("open");
  window.scrollTo(0, 0);
}

document.getElementById("drawerclose").addEventListener("click",
  () => document.getElementById("drawer").classList.remove("open"));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") document.getElementById("drawer").classList.remove("open");
});

readHash();
writeHash();
render();

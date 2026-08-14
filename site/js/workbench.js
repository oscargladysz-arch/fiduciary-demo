/* Tark workbench — screener, comparison, verification, search, packet,
 * command palette, pins. Everything reads window.TARK; structured facts carry
 * source_cell provenance and honest nulls. URL state is keys/IDs only —
 * free text (search queries) never enters the hash. */

import { esc, chip, statusKind, money, stat, citeBtn, gloss } from "./views.js";

const T = window.TARK;
const PRODUCTS = Object.keys(T.products);

/* ------------------------------------------------------------- helpers */
export function fact(key, field) {
  return T.facts[key]?.[field] ?? { value: null, reason: "field unmapped" };
}

function shortName(key) {
  return T.products[key].fund_name.split(" (")[0]
    .replace("Blackstone Real Estate Income Trust", "BREIT")
    .replace("KKR Private Equity Conglomerate LLC", "KKR K-PEC")
    .replace("Hamilton Lane Private Assets Fund", "HL PAF")
    .replace("Cliffwater Corporate Lending Fund", "Cliffwater CCLFX")
    .replace("StepStone Private Markets", "StepStone SPRIM")
    .replace("Destiny Tech100 Inc", "Destiny DXYZ");
}

const WRAPPER_LABEL = {
  tender_offer: "tender-offer", interval_23c3: "interval (23c-3)",
  listed_cef: "listed CEF", nontraded_reit: "non-traded REIT",
  nontraded_llc: "non-traded LLC", nontraded_bdc: "non-traded BDC",
  listed_bdc: "listed BDC",
};
const BASE_LABEL = {
  net_assets: "net assets", managed_assets: "MANAGED assets",
  gross_incl_borrowings: "GROSS incl. borrowings", nav: "NAV",
  outstanding_shares: "outstanding shares", aggregate_nav: "aggregate NAV",
  lesser_of_dual_base: "LESSER-OF dual base",
};

/* render a fact into a table cell: value or honest gap; provenance click */
function factCell(key, f, fmt = (v) => esc(String(v)), trapWhen = null) {
  if (!f || f.value === null || f.value === undefined) {
    return `<td class="gap"><span class="why" title="${esc(f?.reason || "unmapped")}">—</span>
      ${f?.source_cell ? citeBtn(key, f.source_cell) : ""}</td>`;
  }
  const trap = trapWhen && trapWhen(f.value);
  return `<td class="${trap ? "trap" : ""}"><span class="cellval">${fmt(f.value)}</span>
    ${f.note ? `<span class="why cap" title="${esc(f.note)}"> ◦</span>` : ""}
    ${citeBtn(key, f.source_cell)}</td>`;
}

/* =============================================================== SCREENER */
const COLS = [
  ["wrapper", "Wrapper", (k) => factCell(k, fact(k, "wrapper_type"),
      (v) => esc(WRAPPER_LABEL[v] || v))],
  ["fee", "Mgmt fee", (k) => factCell(k, fact(k, "mgmt_fee_pct"),
      (v) => v.toFixed(2) + "%")],
  ["base", "Fee base", (k) => factCell(k, fact(k, "mgmt_fee_base"),
      (v) => esc(BASE_LABEL[v] || v),
      (v) => v === "managed_assets" || v === "gross_incl_borrowings")],
  ["incentive", "Incentive", (k) => {
    const f = fact(k, "incentive_fee");
    if (f.value === null) return factCell(k, f);
    return factCell(k, { ...f, value: f.value.present
      ? `${f.value.rate_pct}%${f.value.hurdle_pct ? ` / ${f.value.hurdle_pct}% hurdle` : ""}`
      : "none" });
  }],
  ["ter", "Expense ratio", (k) => factCell(k, fact(k, "expense_ratio_pct"),
      (v) => v.toFixed(2) + "%")],
  ["early", "Early fee", (k) => {
    const f = fact(k, "early_repurchase");
    if (f.value === null) return factCell(k, f);
    return factCell(k, { ...f, value: f.value.present
      ? `${f.value.rate_pct}% ${f.value.window}` : "none" });
  }],
  ["cadence", "Dealing/yr", (k) => factCell(k, fact(k, "repurchase_cadence_per_year"))],
  ["cap", "Cap", (k) => factCell(k, fact(k, "repurchase_cap_pct"),
      (v) => v + "%")],
  ["gate", "Gate history", (k) => factCell(k, fact(k, "gate_history"),
      (v) => v ? "YES" : "none identified", (v) => v === true)],
  ["tax", "Tax form", (k) => factCell(k, fact(k, "tax_form"), esc,
      (v) => v === "K-1")],
  ["big4", "Big-4 audit", (k) => factCell(k, fact(k, "big4"),
      (v) => v ? "yes" : "no")],
  ["pme", "KS-PME", (k) => factCell(k, fact(k, "pme_primary"),
      (v) => v.toFixed(4))],
  ["alpha", "Direct Alpha", (k) => factCell(k, fact(k, "direct_alpha_primary"),
      (v) => v.toFixed(2) + "%/yr")],
  ["score", "Engine score", (k) => factCell(k, fact(k, "selection_score"),
      (v) => v + "/12")],
  ["verdict", "Liquidity verdict", (k, state) => {
    const f = fact(k, "liquidity_verdict_by_plan");
    if (!f.value) return factCell(k, f);
    const v = f.value[state.plan];
    return factCell(k, { ...f, value: v }, esc,
      (x) => x === "conditional-weak");
  }],
  ["track", "Track record", (k) => factCell(k, fact(k, "track_record_years"),
      (v) => v + " yrs")],
  ["aum", "Net assets", (k) => factCell(k, fact(k, "net_assets_usd"),
      (v) => money(v))],
];
const SORT_VAL = {
  fee: (k) => fact(k, "mgmt_fee_pct").value,
  ter: (k) => fact(k, "expense_ratio_pct").value,
  pme: (k) => fact(k, "pme_primary").value,
  alpha: (k) => fact(k, "direct_alpha_primary").value,
  score: (k) => fact(k, "selection_score").value,
  track: (k) => fact(k, "track_record_years").value,
  aum: (k) => fact(k, "net_assets_usd").value,
  cadence: (k) => fact(k, "repurchase_cadence_per_year").value,
  cap: (k) => fact(k, "repurchase_cap_pct").value,
};

function verifiedFactCounts() {
  let verified = 0; let total = 0;
  for (const k of PRODUCTS) {
    for (const f of Object.values(T.facts[k])) {
      if (f.value === null) continue;
      total++;
      if (statusKind(String(f.status || "")) === "verified") verified++;
    }
  }
  return { verified, total };
}

export function viewScreener(root, state, setState) {
  const F = state; // filters live in state (all enum/number keys)
  const sel = (id, label, opts) => `<span class="lbl">${label}</span>
    <select data-f="${id}"><option value="">any</option>
      ${opts.map((o) => `<option value="${o}" ${F[id] === o ? "selected" : ""}>${esc(o)}</option>`).join("")}
    </select>`;

  let rows = PRODUCTS.filter((k) => {
    if (F.f_cohort && T.facts_meta[k]?.cohort_id !== F.f_cohort) return false;
    if (F.f_depth && T.facts_meta[k]?.depth !== F.f_depth) return false;
    if (F.f_wrapper && fact(k, "wrapper_type").value !== F.f_wrapper) return false;
    if (F.f_base && fact(k, "mgmt_fee_base").value !== F.f_base) return false;
    if (F.f_tax && fact(k, "tax_form").value !== F.f_tax) return false;
    if (F.f_gate === "yes" && fact(k, "gate_history").value !== true) return false;
    if (F.f_gate === "no" && fact(k, "gate_history").value !== false) return false;
    if (F.f_big4 === "yes" && fact(k, "big4").value !== true) return false;
    if (F.f_big4 === "no" && fact(k, "big4").value !== false) return false;
    if (F.f_verdict && fact(k, "liquidity_verdict_by_plan").value?.[state.plan]
        !== F.f_verdict) return false;
    if (F.pme_min && !(fact(k, "pme_primary").value >= +F.pme_min)) return false;
    if (F.pme_max && !(fact(k, "pme_primary").value <= +F.pme_max)) return false;
    return true;
  });
  if (F.f_vonly === "1") rows = rows.filter((k) =>
    Object.values(T.facts[k]).some((f) =>
      statusKind(String(f.status || "")) === "verified"));

  const sortId = SORT_VAL[F.sort] ? F.sort : null;
  if (sortId) {
    const dir = F.dir === "desc" ? -1 : 1;
    rows.sort((a, b) => {
      const av = SORT_VAL[sortId](a); const bv = SORT_VAL[sortId](b);
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      return (av - bv) * dir;
    });
  }

  const visCols = F.cols ? COLS.filter(([id]) => F.cols.split(".").includes(id))
    : COLS;
  const vc = verifiedFactCounts();

  root.innerHTML = `
    <div class="viewhead"><h1>Screener</h1>
      <div class="sub">Typed projections of evidenced cells — every value click-through
        to its citation; gaps are honest, not blank.</div></div>
    <div class="filterbar">
      ${sel("f_cohort", "cohort", Object.keys(T.cohorts))}
      ${sel("f_depth", "depth", ["full", "cohort"])}
      ${sel("f_wrapper", "wrapper", Object.keys(WRAPPER_LABEL))}
      ${sel("f_base", "fee base", Object.keys(BASE_LABEL).filter((b) => PRODUCTS.some((k) => fact(k, "mgmt_fee_base").value === b)))}
      ${sel("f_tax", "tax", ["1099", "K-1"])}
      ${sel("f_gate", "gate hist", ["yes", "no"])}
      ${sel("f_big4", "big-4", ["yes", "no"])}
      ${sel("f_verdict", "verdict", ["aligned-mechanical", "conditional", "conditional-weak"])}
      <span class="lbl">PME ≥</span><input type="number" step="0.05" style="width:70px" data-f="pme_min" value="${esc(F.pme_min || "")}">
      <span class="lbl">≤</span><input type="number" step="0.05" style="width:70px" data-f="pme_max" value="${esc(F.pme_max || "")}">
      <label class="lbl" style="cursor:pointer"><input type="checkbox" data-f="f_vonly" ${F.f_vonly === "1" ? "checked" : ""}> verified only</label>
      <details style="font-size:11px"><summary class="lbl" style="cursor:pointer">columns</summary>
        <div style="position:absolute;z-index:30;background:var(--panel);border:1px solid var(--line);padding:8px 12px;border-radius:3px">
        ${COLS.map(([id, label]) => `<label style="display:block"><input type="checkbox" data-col="${id}"
          ${!F.cols || F.cols.split(".").includes(id) ? "checked" : ""}> ${esc(label)}</label>`).join("")}</div></details>
      <button class="copylink" data-copylink>copy link</button>
    </div>
    ${F.f_vonly === "1" ? `<div class="banner amber vonly-banner">
      Independent human verification in progress: <b>${vc.verified} of ${vc.total}</b>
      typed facts verified. This filter will fill up as the verification pass
      (docs/verification_queue.md) lands in the evidence CSVs — showing
      ${rows.length} product(s) with any verified fact today is the honest state.</div>` : ""}
    <div class="tablewrap"><table class="grid screener">
      <thead><tr><th>Product</th>
        ${visCols.map(([id, label]) => `<th class="${SORT_VAL[id] ? "sortable" : ""}" data-sort="${id}">${esc(label)}${F.sort === id ? (F.dir === "desc" ? " ↓" : " ↑") : ""}</th>`).join("")}
      </tr></thead>
      <tbody>${rows.map((k) => `<tr>
        <td><a href="#" data-goto-prod="${k}" style="font-weight:600">${esc(shortName(k))}</a></td>
        ${visCols.map(([, , render]) => render(k, state)).join("")}
      </tr>`).join("")}</tbody></table></div>
    <p class="cap" style="margin-top:8px">${rows.length} of ${PRODUCTS.length}
      products match. Six rows today; the grid, filters and URL state are built
      for six hundred. Facts layer: data/facts/*.json — zero new facts, every
      field carries its source cell (validator-enforced).</p>`;

  root.querySelectorAll("[data-f]").forEach((el) => el.addEventListener("change", () => {
    const patch = {};
    if (el.type === "checkbox") patch[el.dataset.f] = el.checked ? "1" : "";
    else patch[el.dataset.f] = el.value;
    setState(patch);
  }));
  root.querySelectorAll("[data-col]").forEach((el) => el.addEventListener("change", () => {
    const on = [...root.querySelectorAll("[data-col]")].filter((c) => c.checked)
      .map((c) => c.dataset.col);
    setState({ cols: on.length === COLS.length ? "" : on.join(".") });
  }));
  root.querySelectorAll("[data-sort]").forEach((th) => th.addEventListener("click", () => {
    if (!SORT_VAL[th.dataset.sort]) return;
    setState(state.sort === th.dataset.sort
      ? { dir: state.dir === "desc" ? "asc" : "desc" }
      : { sort: th.dataset.sort, dir: "asc" });
  }));
  root.querySelectorAll("[data-goto-prod]").forEach((a) => a.addEventListener("click",
    (e) => { e.preventDefault(); setState({ view: "evaluation", product: a.dataset.gotoProd }); }));
}

/* ============================================================= COMPARISON */
const CMP_ROWS = [
  ["Wrapper", "wrapper_type", (v) => WRAPPER_LABEL[v] || v, null],
  ["Management fee", "mgmt_fee_pct", (v) => v.toFixed(2) + "%", null],
  ["Fee base", "mgmt_fee_base", (v) => BASE_LABEL[v] || v,
    (v) => v === "managed_assets" || v === "gross_incl_borrowings"],
  ["Incentive fee", "incentive_fee",
    (v) => v.present ? `${v.rate_pct}%${v.hurdle_pct ? ` / ${v.hurdle_pct}% hurdle` : ""}` : "none", null],
  ["Expense ratio", "expense_ratio_pct", (v) => v.toFixed(2) + "%", null],
  ["Early repurchase", "early_repurchase",
    (v) => v.present ? `${v.rate_pct}% if ${v.window}` : "none", null],
  ["Dealing cadence", "repurchase_cadence_per_year", (v) => v + "×/yr", null],
  ["Repurchase cap", "repurchase_cap_pct", (v) => v + "%", null],
  ["Gate history", "gate_history", (v) => v ? "YES — prorated under stress" : "none identified",
    (v) => v === true],
  ["Tax form", "tax_form", (v) => v, (v) => v === "K-1"],
  ["Auditor", "auditor", (v) => v, null],
  ["Big-4", "big4", (v) => v ? "yes" : "no", null],
  ["Primary benchmark", "primary_benchmark_id", (v) => v.toUpperCase(), null],
  ["Engine score", "selection_score", (v) => v + "/12", null],
  ["KS-PME (primary)", "pme_primary", (v) => v.toFixed(4), (v) => v < 1],
  ["Direct Alpha", "direct_alpha_primary", (v) => v.toFixed(2) + "%/yr", (v) => v < 0],
  ["Track record", "track_record_years", (v) => v + " yrs", null],
  ["Net assets", "net_assets_usd", (v) => money(v), null],
];

export function viewCompare(root, state, setState) {
  const picked = (state.compare || "").split(",").filter((k) => PRODUCTS.includes(k));
  const keys = picked.length >= 2 ? picked.slice(0, 4) : [];

  const picker = `<div class="comparepick">${PRODUCTS.map((k) => `
    <label class="${picked.includes(k) ? "on" : ""}">
      <input type="checkbox" data-cmp="${k}" ${picked.includes(k) ? "checked" : ""}
        style="display:none">${esc(shortName(k))}</label>`).join("")}
    <button class="copylink" data-copylink>copy link</button>
    <span class="lbl" style="margin-left:10px">peer-suggest:</span>
    ${Object.keys(T.cohorts).map((c) =>
      `<button class="citebtn" data-cmpcohort="${c}">vs ${esc(c)}</button>`).join(" ")}
  </div>`;

  // cross-wrapper caveats surface automatically when a comparison spans
  // wrapper types (assembled from the caveat matrix — data, not prose)
  const crossCaveats = (() => {
    if (keys.length < 2) return "";
    const attrs = T.caveat_matrix.wrapper_attributes;
    const wts = keys.map((k) => fact(k, "wrapper_type").value).filter(Boolean);
    const out = [];
    for (const rule of T.caveat_matrix.pair_caveats) {
      const a = rule.attrs[0];
      if (new Set(wts.map((w) => attrs[w]?.[a])).size > 1) out.push(rule.caveat);
    }
    return out.length ? `<div class="banner amber"><b>Cross-wrapper comparison —
      caveats apply:</b><ul style="margin:6px 0 0 18px">${out.map((c) =>
      `<li style="margin-bottom:3px">${esc(c)}</li>`).join("")}</ul></div>` : "";
  })();

  if (!keys.length) {
    root.innerHTML = `<div class="viewhead"><h1>Comparison</h1>
      <div class="sub">Pick 2–4 products — synchronized side-by-side with
        material differences highlighted and every value one click from its
        citation.</div></div>${picker}`;
    wireCompare(root, picked, setState);
    return;
  }

  const diffClass = (vals, trap) => {
    const rendered = vals.map((v) => JSON.stringify(v?.value ?? null));
    const allSame = rendered.every((r) => r === rendered[0]);
    return (v) => {
      if (trap && v?.value !== null && v?.value !== undefined && trap(v.value)) return "trap";
      return allSame ? "" : "diff";
    };
  };

  const body = CMP_ROWS.map(([label, field, fmt, trap]) => {
    const vals = keys.map((k) => fact(k, field));
    const cls = diffClass(vals, trap);
    return `<tr><td style="font-weight:600">${gloss(label)}</td>
      ${keys.map((k, i) => {
        const f = vals[i];
        if (f.value === null || f.value === undefined) {
          return `<td class="gap"><span class="why" title="${esc(f.reason || "")}">—</span>
            ${f.source_cell ? citeBtn(k, f.source_cell) : ""}</td>`;
        }
        return `<td class="${cls(f)}"><span class="cellval">${esc(fmt(f.value))}</span>
          ${citeBtn(k, f.source_cell)} ${chip(f.status)}</td>`;
      }).join("")}</tr>`;
  }).join("");

  const verdictRow = `<tr><td style="font-weight:600">Liquidity verdict
      <div class="cap">${esc(T.plans[state.plan].display_label)}</div></td>
    ${keys.map((k) => {
      const v = fact(k, "liquidity_verdict_by_plan").value?.[state.plan];
      return `<td class="${v === "conditional-weak" ? "trap" : ""}">
        <span class="cellval">${esc((v || "—").toUpperCase())}</span>
        <a href="#" class="cap" data-goto-liq="${k}">full match →</a></td>`;
    }).join("")}</tr>`;

  const benchRow = `<tr><td style="font-weight:600">Rejection ledger</td>
    ${keys.map((k) => `<td><a href="#" data-goto-bench="${k}">
      ${T.benchmarks[k]?.rejected?.length ?? 0} rejections on record →</a></td>`).join("")}</tr>`;

  root.innerHTML = `
    <div class="viewhead"><h1>Comparison</h1>
      <div class="sub">Material differences highlighted amber; fee-base traps,
        K-1, gating and sub-1.0 PME flagged red. Every value cites its cell.</div></div>
    ${picker}
    ${crossCaveats}
    <div class="tablewrap"><table class="grid compare">
      <thead><tr><th style="min-width:170px">Fact</th>
        ${keys.map((k) => `<th class="prodcol">${esc(shortName(k))}</th>`).join("")}</tr></thead>
      <tbody>${body}${verdictRow}${benchRow}</tbody></table></div>
    <p class="cap" style="margin-top:8px">Facts: typed projections with
      source-cell provenance (data/facts). Status chips mirror the evidence
      record — nothing here is human-verified yet.</p>`;
  wireCompare(root, picked, setState);
  root.querySelectorAll("[data-goto-liq]").forEach((a) => a.addEventListener("click",
    (e) => { e.preventDefault(); setState({ view: "liquidity", product: a.dataset.gotoLiq }); }));
  root.querySelectorAll("[data-goto-bench]").forEach((a) => a.addEventListener("click",
    (e) => { e.preventDefault(); setState({ view: "benchmarks", product: a.dataset.gotoBench }); }));
}

function wireCompare(root, picked, setState) {
  root.querySelectorAll("[data-cmp]").forEach((cb) => cb.addEventListener("change", () => {
    let next = picked.filter((k) => k !== cb.dataset.cmp);
    if (cb.checked) next = [...next, cb.dataset.cmp];
    setState({ compare: next.slice(-4).join(",") });
  }));
  root.querySelectorAll("[data-cmpcohort]").forEach((b) =>
    b.addEventListener("click", () => setState({
      compare: Object.keys(T.cohorts[b.dataset.cmpcohort].members)
        .slice(0, 4).join(","),
    })));
}

/* =========================================================== VERIFICATION */
export function viewVerification(root, state, setState) {
  const q = T.verification_queue;
  const totV = Object.values(q.verified).reduce((a, b) => a + b, 0);
  const totA = Object.values(q.verifiable).reduce((a, b) => a + b, 0);
  root.innerHTML = `
    <div class="viewhead"><h1>Verification</h1>
      <div class="sub">The human pass, made product-native: the evidence CSVs are
        the interface; this surface tracks progress live from the statuses.</div></div>
    <div class="statrow">
      ${stat("Cells verified", `${totV}`, `of ${totA} at extracted-unverified/verified`)}
      ${stat("Progress", `${totA ? Math.round(totV / totA * 100) : 0}%`)}
      ${stat("Queue source", `<span style="font-size:13px">docs/verification_queue.md</span>`)}
    </div>
    <div class="cardgrid g3" style="margin:14px 0">
      ${Object.keys(T.products).map((k) => {
        const v = q.verified[k]; const a = q.verifiable[k];
        return `<div class="card"><h3 style="font-size:13px">${esc(shortName(k))}</h3>
          <div class="covbar" style="margin:8px 0"><div class="seg extracted"
            style="width:${a ? v / a * 100 : 0}%"></div></div>
          <div class="cap num">${v} / ${a} verified</div></div>`;
      }).join("")}
    </div>
    <h2 style="margin-bottom:6px">Queue (demo-load-bearing first)</h2>
    <div class="tablewrap"><table class="grid"><thead><tr>
      <th>#</th><th>Product</th><th>Cell</th><th>Element</th><th>Status</th><th></th>
    </tr></thead><tbody>
      ${q.queue.map((it, i) => {
        const cell = T.products[it.product].cells[it.cell];
        return `<tr><td class="num">${i + 1}</td>
          <td>${esc(shortName(it.product))}</td>
          <td class="num">${esc(it.cell)}</td>
          <td>${esc(cell.element)}</td>
          <td>${chip(cell.status)}</td>
          <td>${citeBtn(it.product, it.cell)}
            <a href="#" data-goto-cell="${it.product}">open →</a></td></tr>`;
      }).join("")}
    </tbody></table></div>
    <p class="cap footer-rule">Verification flips a row to 'verified' + signs
      verified_by in data/evidence/*.csv AND the product JSON — humans only;
      the build can never do this.</p>`;
  root.querySelectorAll("[data-goto-cell]").forEach((a) => a.addEventListener("click",
    (e) => { e.preventDefault(); setState({ view: "evaluation", product: a.dataset.gotoCell }); }));
}

/* ================================================================ SEARCH */
let searchQuery = ""; // in-memory only — free text NEVER enters the URL

export function viewSearch(root, state, setState) {
  root.innerHTML = `
    <div class="viewhead"><h1>Evidence Search</h1>
      <div class="sub">Full-text over every cell value and verbatim quote.
        Queries stay local — never in the URL (leak-proof links by construction).</div></div>
    <input id="searchbox" type="search" placeholder="e.g. 'managed assets', 'prorated', 'Loss Recovery'"
      style="width:100%;max-width:620px;padding:11px 14px;font:500 14px var(--text);
             border:1px solid var(--line);border-radius:3px" value="${esc(searchQuery)}">
    <div id="searchresults" style="margin-top:14px"></div>`;
  const box = root.querySelector("#searchbox");
  const out = root.querySelector("#searchresults");
  function run() {
    searchQuery = box.value;
    const q = box.value.trim().toLowerCase();
    if (q.length < 2) { out.innerHTML = `<p class="cap">Type at least 2 characters.</p>`; return; }
    const hits = [];
    for (const k of PRODUCTS) {
      for (const [cid, cell] of Object.entries(T.products[k].cells)) {
        const hay = `${cell.value || ""} ${cell.quote || ""} ${cell.element}`.toLowerCase();
        const at = hay.indexOf(q);
        if (at >= 0) {
          hits.push({ k, cid, cell,
            ctx: (cell.value || cell.quote || "").slice(Math.max(0, at - 60), at + 90) });
          if (hits.length >= 60) break;
        }
      }
    }
    out.innerHTML = hits.length ? `<div class="tablewrap"><table class="grid"><thead>
      <tr><th>Product</th><th>Cell</th><th>Element</th><th>Match</th><th>Status</th><th></th></tr></thead>
      <tbody>${hits.map((h) => `<tr>
        <td>${esc(shortName(h.k))}</td><td class="num">${h.cid}</td>
        <td>${esc(h.cell.element)}</td>
        <td class="cap">…${esc(h.ctx)}…</td>
        <td>${chip(h.cell.status)}</td>
        <td>${citeBtn(h.k, h.cid)}</td></tr>`).join("")}</tbody></table></div>
      <p class="cap" style="margin-top:6px">${hits.length} match(es)${hits.length >= 60 ? " (capped at 60)" : ""}.</p>`
      : `<p class="cap">No matches.</p>`;
  }
  box.addEventListener("input", run);
  box.focus();
  if (searchQuery) run();
}

/* ================================================================== PINS */
const PINS_KEY = "tark_pins";
export function getPins() {
  try { return JSON.parse(localStorage.getItem(PINS_KEY) || "[]"); }
  catch { return []; }
}
export function setPins(pins) {
  localStorage.setItem(PINS_KEY, JSON.stringify(pins));
}
export function pinCurrent(label) {
  const pins = getPins();
  pins.push({ label, hash: location.hash, at: pins.length });
  setPins(pins);
}
window.addEventListener("click", (e) => {
  const b = e.target.closest("[data-pin-cell]");
  if (b) {
    const { key, cid } = b.dataset;
    const pins = getPins();
    pins.push({ label: `${shortName(key)} · ${cid} ${T.products[key].cells[cid].element}`,
      hash: `#view=evaluation&plan=plan_tech_media&product=${key}`,
      cell: { key, cid } });
    setPins(pins);
    b.classList.add("on");
  }
});

export function viewPacket(root, state, setState) {
  const pins = getPins();
  root.innerHTML = `
    <div class="viewhead"><h1>Packet</h1>
      <div class="sub">Your pinned figures and views — reorder, then print to a
        clean packet (the per-product decision memos remain the docx artifacts;
        this packet is a browser-side print composition, nothing is uploaded
        anywhere).</div></div>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      <button class="btn ghost" id="pinview">Pin current selections as a view</button>
      <button class="btn" onclick="window.print()">Print packet</button>
      ${T.memos.includes(state.product) ? `<a class="btn ghost"
        href="memos/${state.product}_decision_memo.docx" download>Decision memo (docx) ↓</a>` : ""}
    </div>
    <div id="pinlist">${pins.length ? "" : `<p class="cap">Nothing pinned yet —
      use the ⌖ buttons on evaluation cells, or 'Pin current selections'.</p>`}</div>`;
  const list = root.querySelector("#pinlist");
  pins.forEach((p, i) => {
    const row = document.createElement("div");
    row.className = "packetitem";
    let live = "";
    if (p.cell) {
      const cell = T.products[p.cell.key].cells[p.cell.cid];
      const disp = T.cell_display[p.cell.key][p.cell.cid];
      live = `<div><div class="headline" style="margin:0">${esc(disp.headline)}</div>
        <div class="cap">${esc(disp.plain)}</div>
        <div class="cap">${esc(cell.source || "")} ${chip(cell.status)}</div></div>`;
    }
    row.innerHTML = `<b style="min-width:230px">${esc(p.label)}</b>${live}
      <span class="mv">
        <button class="copylink" data-open="${i}">open</button>
        <button class="copylink" data-up="${i}">↑</button>
        <button class="copylink" data-del="${i}">remove</button></span>`;
    list.append(row);
  });
  root.querySelector("#pinview").addEventListener("click", () => {
    pinCurrent(`view · ${state.view} · ${shortName(state.product)} · ${state.plan}`);
    setState({});
  });
  list.querySelectorAll("[data-open]").forEach((b) => b.addEventListener("click", () => {
    location.hash = pins[+b.dataset.open].hash.replace(/^#/, "");
    location.reload();
  }));
  list.querySelectorAll("[data-up]").forEach((b) => b.addEventListener("click", () => {
    const i = +b.dataset.up;
    if (i > 0) { const t = pins[i - 1]; pins[i - 1] = pins[i]; pins[i] = t; setPins(pins); setState({}); }
  }));
  list.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", () => {
    pins.splice(+b.dataset.del, 1); setPins(pins); setState({});
  }));
}

/* ================================================================ PALETTE */
export function initPalette(setState, VIEWS) {
  const el = document.createElement("div");
  el.id = "palette";
  el.innerHTML = `<div class="box">
    <input placeholder="Jump to view, product, plan, cell (e.g. '2.1 hl_paf'), or 'compare a b'…" aria-label="Command palette">
    <div class="results"></div>
    <div class="hint"><kbd>↑↓</kbd> navigate · <kbd>↵</kbd> go · <kbd>esc</kbd> close ·
      try: <i>screener</i>, <i>compare hl_paf breit</i>, <i>2.7 kkr</i>, <i>density compact</i></div>
  </div>`;
  document.body.append(el);
  const input = el.querySelector("input");
  const results = el.querySelector(".results");
  let items = [];
  let selIdx = 0;

  function entries(q) {
    const out = [];
    const ql = q.toLowerCase().trim();
    // command: compare <keys>
    const cmpKeys = PRODUCTS.filter((k) => ql.includes(k.split("_")[0]) || ql.includes(k));
    if (ql.startsWith("compare") && cmpKeys.length >= 2) {
      out.push({ kind: "command", label: `Compare ${cmpKeys.map(shortName).join(" vs ")}`,
        run: () => setState({ view: "compare", compare: cmpKeys.slice(0, 4).join(",") }) });
    }
    if (ql.startsWith("density")) {
      for (const d of ["comfortable", "compact"]) {
        if (`density ${d}`.includes(ql)) out.push({ kind: "command",
          label: `Density: ${d}`, run: () => setState({ density: d }) });
      }
    }
    // command: cohort <id> — jump to a cohort page
    for (const c of Object.keys(T.cohorts)) {
      if (ql && (`cohort ${c}`.includes(ql) || c.includes(ql.replace(/^cohort\s*/, "")))
          && ql.length >= 3) {
        out.push({ kind: "command", label: `Cohort: ${T.cohorts[c].label}`,
          run: () => setState({ view: "cohorts", cohort: c }) });
      }
    }
    // cell id + product ("2.1 hl_paf" or "hl 2.1")
    const cellM = ql.match(/(\d+\.\d+)/);
    if (cellM) {
      const cid = cellM[1];
      for (const k of PRODUCTS) {
        if (T.cell_registry[cid] && (ql.includes(k.split("_")[0]) || ql.includes(k))) {
          out.push({ kind: "cell", label: `${cid} ${T.cell_registry[cid]} — ${shortName(k)}`,
            run: () => { setState({ view: "evaluation", product: k });
              setTimeout(() => document.getElementById(`f${cid.split(".")[0]}`)
                ?.scrollIntoView({ block: "start" }), 60); } });
        }
      }
    }
    for (const [id, label] of VIEWS) {
      if (label.toLowerCase().includes(ql) || id.includes(ql)) {
        out.push({ kind: "view", label, run: () => setState({ view: id }) });
      }
    }
    for (const k of PRODUCTS) {
      if (k.includes(ql) || shortName(k).toLowerCase().includes(ql)
          || T.products[k].fund_name.toLowerCase().includes(ql)) {
        out.push({ kind: "product", label: shortName(k),
          run: () => setState({ product: k }) });
      }
    }
    for (const pk of T.plan_order) {
      if (pk.includes(ql) || T.plans[pk].display_label.toLowerCase().includes(ql)) {
        out.push({ kind: "plan", label: T.plans[pk].display_label,
          run: () => setState({ plan: pk }) });
      }
    }
    out.push({ kind: "search", label: `Search evidence for “${q}”`,
      run: () => { searchQuery = q; setState({ view: "search" }); } });
    return out.slice(0, 12);
  }

  function render() {
    results.innerHTML = items.map((it, i) => `<div class="pitem ${i === selIdx ? "sel" : ""}"
        data-i="${i}"><span class="kind">${it.kind}</span>${esc(it.label)}</div>`).join("");
    results.querySelectorAll(".pitem").forEach((d) => d.addEventListener("click",
      () => { items[+d.dataset.i].run(); close(); }));
  }
  function open() { el.classList.add("open"); input.value = ""; items = entries("");
    selIdx = 0; render(); input.focus(); }
  function close() { el.classList.remove("open"); }

  input.addEventListener("input", () => { items = entries(input.value); selIdx = 0; render(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { selIdx = Math.min(selIdx + 1, items.length - 1); render(); e.preventDefault(); }
    if (e.key === "ArrowUp") { selIdx = Math.max(selIdx - 1, 0); render(); e.preventDefault(); }
    if (e.key === "Enter" && items[selIdx]) { items[selIdx].run(); close(); }
    if (e.key === "Escape") close();
  });
  el.addEventListener("click", (e) => { if (e.target === el) close(); });
  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); open(); }
  });
  window.tarkPalette = { open, close, entries }; // for tests
}

/* ============================================================== COHORTS */
export function viewCohorts(root, state, setState) {
  const cid = T.cohorts[state.cohort] ? state.cohort : "private_credit";
  const C = T.cohorts[cid];
  const members = Object.keys(C.members);

  const FIELD_ROWS = [
    ["mgmt_fee_pct", "Mgmt fee %"], ["mgmt_fee_base", "Fee base"],
    ["incentive_fee", "Incentive"], ["expense_ratio_pct", "Expense ratio %"],
    ["early_repurchase", "Early repurchase"],
    ["repurchase_cadence_per_year", "Cadence /yr"],
    ["repurchase_cap_pct", "Cap %"], ["gate_history", "Gate history"],
    ["tax_form", "Tax form"], ["big4", "Big-4 audit"],
    ["track_record_years", "Track record (yrs)"],
    ["pme_primary", "KS-PME (primary)"],
  ];
  const cell = (k, field) => {
    const f = fact(k, field);
    if (!f) return `<td class="cap">—</td>`;
    if (f.value === null || f.value === undefined) {
      const rsn = String(f.reason || "no value");
      return `<td><span class="cap" title="${esc(rsn)}">n/a — ${esc(rsn.length > 46 ? rsn.slice(0, 46) + "…" : rsn)}</span></td>`;
    }
    let v = f.value;
    if (typeof v === "object") {
      v = v.present === false ? "none" :
          `${v.present ? "yes" : ""}${v.rate_pct != null ? " " + v.rate_pct + "%" : ""}${v.hurdle_pct != null ? " / " + v.hurdle_pct + "% hurdle" : ""}${v.window ? " " + v.window : ""}`;
    }
    if (typeof v === "boolean") v = v ? "yes" : "no";
    return `<td class="num">${esc(String(v))} <button class="citebtn" data-cite data-key="${k}" data-cid="${esc(f.source_cell)}">src</button></td>`;
  };

  // range bars per stat field
  const rangeBar = (field, label) => {
    const st = C.stats[field];
    if (!st || st.n === 0) return "";
    const lo = st.min, hi = st.max, span = (hi - lo) || 1;
    const marks = Object.entries(st.values).map(([k, v]) =>
      `<div class="rmark" style="left:${((v - lo) / span * 100).toFixed(1)}%"
            title="${esc(T.products[k].fund_name)}: ${v}">
         <span>${esc(k.split("_")[0])}</span></div>`).join("");
    const missing = Object.keys(st.missing || {}).length;
    return `<div class="rangerow"><div class="rlabel">${esc(label)}
        <span class="cap">n=${st.n}${missing ? ` · ${missing} n/a` : ""} · median ${st.median}</span></div>
      <div class="rtrack"><div class="rmed" style="left:${((st.median - lo) / span * 100).toFixed(1)}%"></div>${marks}</div>
      <div class="rminmax"><span>${st.min}</span><span>${st.max}</span></div></div>`;
  };

  const comp = C.composite;
  const exclusions = T.roster_decisions_md.split("## Considered and excluded")[1]?.split("##")[0] || "";

  root.innerHTML = `
    <div class="viewhead"><h1>Cohort: ${esc(C.label)}</h1>
      <div class="sub">n=${C.n} · membership is an argued judgment — every
        rationale below, every exclusion logged. Cohorts:
        ${Object.keys(T.cohorts).map((c) =>
          `<a href="#" data-cohort="${c}" style="margin-right:9px;${c === cid ? "font-weight:700" : ""}">${esc(c)}</a>`).join("")}</div></div>
    ${(C.caveats || []).length ? `<div class="banner amber"><b>Comparability caveats
      (assembled from the wrapper matrix):</b><ul style="margin:6px 0 0 18px">
      ${C.caveats.map((c) => `<li style="margin-bottom:4px">${esc(c)}</li>`).join("")}</ul></div>` : ""}
    <div class="tablewrap"><table class="grid">
      <thead><tr><th>Fact</th>${members.map((k) => `<th>
        ${esc(T.products[k].fund_name.split(" (")[0].slice(0, 26))}<br>
        <span class="chip ${C.members[k].depth === "full" ? "extracted" : "wrapper"}">${C.members[k].depth} depth</span>
      </th>`).join("")}</tr></thead>
      <tbody>${FIELD_ROWS.map(([f, label]) => `<tr>
        <td style="font-weight:600">${esc(label)}</td>
        ${members.map((k) => cell(k, f)).join("")}</tr>`).join("")}</tbody>
    </table></div>
    <h2 style="margin:18px 0 6px">Ranges</h2>
    <div class="card">${["mgmt_fee_pct", "expense_ratio_pct", "repurchase_cap_pct",
                         "track_record_years"].map((f) =>
      rangeBar(f, (FIELD_ROWS.find(([id]) => id === f) || [f, f])[1])).join("")}</div>
    <h2 style="margin:18px 0 6px">Composite</h2>
    ${comp.refused ? `<div class="nochart"><div class="k">Composite refused</div>
        ${esc(comp.reason)}</div>`
      : `<div class="chartbox"><div id="compchart"></div>
         <div class="chartnote">${esc(comp.granularity)} · ${esc(comp.weighting)}.
           Per-row membership shown in the tooltip; rows require ≥2 reporting members.</div></div>`}
    <h2 style="margin:18px 0 6px">Membership rationales</h2>
    ${members.map((k) => `<div class="cellrow"><div class="head">
        <span class="el">${esc(T.products[k].fund_name)}</span>
        <span class="chip wrapper">${esc(C.members[k].wrapper_type)}</span></div>
      <div class="plain">${esc(C.members[k].membership_rationale)}</div></div>`).join("")}
    <h2 style="margin:18px 0 6px">Exclusion log</h2>
    <div class="cap" style="margin-bottom:6px">Every candidate considered and not
      admitted, with its reason (data/roster_decisions.md).</div>
    <div class="cellrow"><div class="plain" style="white-space:pre-wrap">${esc(exclusions.trim())}</div></div>`;

  root.querySelectorAll("[data-cohort]").forEach((a) => a.addEventListener("click",
    (e) => { e.preventDefault(); setState({ view: "cohorts", cohort: a.dataset.cohort }); }));
  if (!comp.refused && comp.rows.length) {
    import("./charts.js").then(({ lineChart }) => {
      const box = root.querySelector("#compchart");
      if (!box) return;
      lineChart(box, {
        series: [{ points: comp.rows.map((r) => [`${r.year}-12-31`, r.composite_return_pct]),
          label: `equal-weight composite (${cid})`, color: "#593380", width: 2, markers: true }],
        height: 220, includeZero: true, yFormat: (v) => v.toFixed(0) + "%",
      });
    });
  }
}

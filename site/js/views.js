/* Tark views — every renderer reads ONLY window.TARK (generated from the
 * canonical data layer by src/build_site.py). No fact is hard-coded here.
 * Numbers first: each cell leads with its focal figure (cell_display,
 * derived at build time); the full sourced text sits behind a disclosure.
 * Charts are TIER-DRIVEN from the bundle: daily series, printed monthly
 * series, filing-annual series — and where a chart is impossible, the
 * documented reason renders in its place. */

import { annVol, beta, calendarYearReturns, desmoothGeltner, directAlpha,
         drawdownEpisodes, effectiveWindow, fiscalYearBounds, ksPme,
         lag1Autocorr, levelOn, monthlyScheduleFlows,
         monthEndPoints, periodReturns, rollingReturns,
         rollingVol } from "./analytics.js";
import { computeScenario, scenarioReason } from "./liquidity.js";
import { lineChart, barChart, donut } from "./charts.js";

const T = window.TARK;

/* ------------------------------------------------------------ utilities */
export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const STATUS_PREFIXES = ["pending", "partial", "extracted", "verified",
  "structured", "computed", "fetched", "n/a"];
export function statusKind(status) {
  for (const p of STATUS_PREFIXES) if (String(status).startsWith(p)) return p;
  return "unknown";
}

const CHIP_LABEL = {
  structured: "structured filing data (T1)",
  verified: "verified", extracted: "extracted · unverified",
  computed: "computed", partial: "partial", fetched: "series fetched",
  pending: "pending", "n/a": "n/a",
};
export function chip(status) {
  const k = statusKind(status);
  const cls = k === "n/a" ? "na" : k;
  return `<span class="chip ${cls}">${CHIP_LABEL[k] || esc(status)}</span>`;
}

export function money(x, digits = 1) {
  if (x >= 1e9) return `$${(x / 1e9).toFixed(digits)}B`;
  if (x >= 1e6) return `$${(x / 1e6).toFixed(digits)}M`;
  return `$${Math.round(x).toLocaleString()}`;
}

export function stat(k, v, small = "") {
  return `<div class="stat"><div class="k">${esc(k)}</div>
    <div class="v">${v}${small ? ` <small>${esc(small)}</small>` : ""}</div></div>`;
}

/* glossary chips: wrap known terms (longest first) in short display strings.
 * Plain-language definition on hover; never applied to long prose.
 * Terms are matched on the PLAIN string and the output is assembled from
 * escaped text segments, so emitted markup is never re-scanned. Before this,
 * a term occurring inside another term's definition was re-glossed inside
 * the data-def attribute, which broke the attribute and printed raw markup
 * on the Roster and Evaluation wrapper chips. */
const TERMS = Object.keys(T.glossary).sort((a, b) => b.length - a.length);
const escRe = (t) => t.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
export function gloss(s) {
  const src = String(s ?? "");
  const taken = new Array(src.length).fill(false);
  const hits = [];
  for (const t of TERMS) {
    const re = new RegExp(`(?<!\\w)(${escRe(t)})(?!\\w)`, "g");
    let m;
    while ((m = re.exec(src))) {
      const a = m.index, b = a + m[0].length;
      let free = true;
      for (let i = a; i < b; i++) if (taken[i]) { free = false; break; }
      if (!free) continue;
      for (let i = a; i < b; i++) taken[i] = true;
      hits.push([a, b, t]);
      break;                       // first free occurrence of each term only
    }
  }
  hits.sort((x, y) => x[0] - y[0]);
  let out = "", pos = 0;
  for (const [a, b, t] of hits) {
    out += esc(src.slice(pos, a));
    out += `<span class="term" tabindex="0" data-def="${esc(T.glossary[t])}">`
         + `${esc(src.slice(a, b))}</span>`;
    pos = b;
  }
  return out + esc(src.slice(pos));
}
window.TarkGloss = gloss;   // test seam: textContent(gloss(s)) must equal s

/* coverage: per status kind, never one merged number. structured is T1,
 * extracted is T2, verified is T3; n/a stays visible as its own segment. */
export const KINDS = [
  ["structured", "structured (T1)", "#2456a6"],
  ["extracted", "extracted-unverified (T2)", "#256e46"],
  ["verified", "verified (T3)", "#b8860b"],
  ["computed", "computed", "#14636d"],
  ["partial", "partial", "#c98a1a"],
  ["fetched", "series fetched", "#e0b45a"],
  ["na", "documented n/a", "#d8d3dd"],
  ["pending", "pending", "#9d2f26"],
];
export function kindSegments(c) {
  return KINDS.filter(([k]) => (c[k] || 0) > 0)
    .map(([k, label, color]) => ({ label, value: c[k], color }));
}
export function kindLine(c) {
  return KINDS.filter(([k]) => (c[k] || 0) > 0)
    .map(([k, label]) => `${c[k]} ${label}`).join(" · ");
}
export function kindLegend() {
  return KINDS.map(([, label, color]) =>
    `<span><span class="sw" style="background:${color}"></span>${label}</span>`).join("");
}
export function kindDonut(c, size = 64) {
  const box = document.createElement("div");
  donut(box, { size, segments: kindSegments(c), center: `${c.verified || 0}`,
    centerSub: "T3" });
  box.title = c.headline || "";
  return box;
}

/* typed-fact formatters: print only the fields the fact carries. A fee
 * whose rate is unknown says so instead of printing "undefined%". */
export function fmtIncentive(v) {
  if (!v) return "";
  if (!v.present) return "none";
  const parts = [];
  if (v.rate_pct != null) parts.push(`${v.rate_pct}%`);
  if (v.hurdle_pct != null) parts.push(`${v.hurdle_pct}% hurdle`);
  return parts.length ? parts.join(" / ") : "present, rate not typed (see 2.2)";
}
export function fmtEarly(v) {
  if (!v) return "";
  if (!v.present) return "none";
  const rate = v.rate_pct != null ? `${v.rate_pct}%` : "fee present, rate not typed (see 2.7)";
  return v.window ? `${rate} ${v.window}` : rate;
}

/* citation drawer */
export function openCite(rec, title) {
  const d = document.getElementById("drawer");
  d.querySelector(".dtitle").textContent = title || "Source";
  d.querySelector(".dbody").innerHTML = `
    ${rec.status ? `<div class="f">${chip(rec.status)}</div>` : ""}
    <div class="f"><div class="k">Document</div>
      <div class="v">${esc(rec.source || "—")}</div></div>
    <div class="f"><div class="k">Section</div>
      <div class="v">${esc(rec.section || "—")}</div></div>
    ${rec.quote ? `<div class="f"><div class="k">Verbatim quote</div>
      <div class="quote">“${esc(rec.quote)}”</div></div>` : ""}
    <div class="f"><div class="k">Extracted by</div>
      <div class="v">${esc(rec.extracted_by || "—")}</div></div>
    <div class="f"><div class="k">Human verification</div>
      <div class="v">${rec.verified_by ? esc(rec.verified_by)
        : "pending: a human verifies rows in data/evidence/*.csv and flips status to verified"}</div></div>`;
  d.classList.add("open");
}
window.addEventListener("click", (e) => {
  const b = e.target.closest("[data-cite]");
  if (b) {
    const { key, cid } = b.dataset;
    const cell = T.products[key].cells[cid];
    openCite(cell, `${cid} · ${cell.element} (${T.products[key].fund_name})`);
  }
});

export function citeBtn(key, cid) {
  const cell = T.products[key]?.cells?.[cid];
  if (!cell || !cell.source) return "";
  return `<button class="citebtn" data-cite data-key="${esc(key)}" data-cid="${esc(cid)}">source</button>`;
}

const short = (s, n = 170) => {
  s = String(s ?? "");
  return s.length > n ? esc(s.slice(0, n).trimEnd()) + "…" : esc(s);
};

/* --------------------------------------------------- tier-driven charts */
// series labels come from the bundle's series_sources (one source, from
// data/series/series_manifest.json), never typed here
const DAILY = { cliffwater_cclfx: { series: "cclfx", col: "adj", label: `CCLFX ${T.series_sources.cclfx.label}` },
                dxyz: { series: "dxyz_daily", label: `DXYZ ${T.series_sources.dxyz_daily.label}` } };

export function productChart(container, key) {
  // pick the finest tier the data supports; label the cadence honestly
  if (DAILY[key]) {
    const pts = T.series[DAILY[key].series];
    lineChart(container, {
      series: [{ points: pts, label: DAILY[key].label, color: "#593380", width: 1.5 }],
      height: 260, yFormat: (v) => "$" + v.toFixed(0),
      logY: key === "dxyz",
    });
    return `daily series, ${pts.length.toLocaleString()} observations (${esc(pts[0][0])} → ${esc(pts[pts.length - 1][0])})`;
  }
  if (key === "breit" && T.series_monthly.breit_nav) {
    const pts = T.series_monthly.breit_nav;
    lineChart(container, {
      series: [{ points: pts, label: "Monthly NAV per share, Class I, as PRINTED in the 10-K/10-Q",
        color: "#593380", width: 1.8, markers: true }],
      height: 260, yFormat: (v) => "$" + v.toFixed(1),
    });
    return "monthly disclosure cadence: the fund's own printed NAV table (NAV path, distributions excluded)";
  }
  const ann = T.series_annual[key];
  if (ann && ann.length) {
    const nav = ann.filter((r) => r.nav_per_share)
      .map((r) => [r.fy_end, +r.nav_per_share]);
    lineChart(container, {
      series: [{ points: nav, label: "NAV per share at fiscal year-end (primary class, as filed)",
        color: "#593380", width: 1.8, markers: true }],
      height: 240, yFormat: (v) => "$" + v.toFixed(0),
    });
    return "annual disclosure cadence: non-traded wrapper with no public daily series, fiscal-year figures as filed";
  }
  container.innerHTML = `<div class="nochart"><div class="k">No chartable public series</div>
    This wrapper publishes no public return series at any charted cadence.</div>`;
  return null;
}

/* ============================================================== PLANS */
export function viewPlans(root, state, setState) {
  const cards = T.plan_order.map((k) => {
    const p = T.plans[k];
    const f = p.financials; const pt = p.participants; const d = p.derived;
    const tail = (pt.separated_deferred_vested / pt.with_account_balances * 100);
    return `<div class="card selectable ${state.plan === k ? "selected" : ""}"
                 data-plan="${k}">
      <h3>${esc(p.display_label)}</h3>
      <div class="cap">${esc(p.archetype || "")}</div>
      <div class="statrow">
        ${stat("Net assets", money(f.net_assets_eoy))}
        ${stat("Accounts", Math.round(pt.with_account_balances).toLocaleString())}
        ${stat("Avg balance", "$" + d.avg_balance_per_account.toLocaleString())}
        ${stat("Liquidity tail", tail.toFixed(1) + "%",
               `${Math.round(pt.separated_deferred_vested).toLocaleString()} separated w/ balances`)}
      </div>
      <details><summary class="cap" style="cursor:pointer">Plan characteristics & source</summary>
        <div class="cap" style="margin-top:6px">${esc(p.plan_characteristics.codes_decoded)}</div>
        <div class="cap" style="margin-top:4px">Plan year ${esc(p.plan_year)} ·
          ${esc(p.source.publisher)} · pulled ${esc(p.source.pulled)}</div></details>
    </div>`;
  }).join("");
  root.innerHTML = `
    <div class="viewhead"><h1>Reference Plans</h1>
      <div class="sub">Four real 401(k) plans from public Form 5500 filings. The
        selected plan drives every liquidity verdict.</div></div>
    <div class="cardgrid g2">${cards}</div>
    <p class="cap footer-rule">${esc(T.plans[state.plan].anonymization_rule)}</p>`;
  root.querySelectorAll("[data-plan]").forEach((c) =>
    c.addEventListener("click", () => setState({ plan: c.dataset.plan })));
}

/* ============================================================== ROSTER */
export function viewRoster(root, state, setState) {
  root.innerHTML = `
    <div class="viewhead"><h1>Candidate Roster</h1>
      <div class="sub">${Object.keys(T.products).length} real products across
        ${new Set(Object.values(T.facts).map((f) => f.wrapper_type?.value).filter(Boolean)).size}
        wrapper types. Every figure is traceable to a public filing.</div></div>
    <div class="cardgrid g2" id="rostercards"></div>`;
  const grid = root.querySelector("#rostercards");
  for (const [k, p] of Object.entries(T.products)) {
    const c = T.evidence_counts[k];
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div style="display:flex; gap:16px; align-items:flex-start">
        <div data-ring></div>
        <div style="flex:1; min-width:0">
          <h3>${esc(p.fund_name)}</h3>
          <div style="margin:5px 0"><span class="chip wrapper">${gloss(p.wrapper)}</span>
            <span class="cap"> CIK ${esc(p.cik)}</span></div>
          <div class="cap">${kindLine(c)}</div>
        </div>
      </div>
      <div style="margin-top:12px; display:flex; gap:8px; flex-wrap:wrap">
        <button class="btn ghost" data-goto="evaluation" data-key="${k}">Six-factor record</button>
        <button class="btn ghost" data-goto="benchmarks" data-key="${k}">Benchmark</button>
        ${T.memos.includes(k) ? `<a class="btn ghost" href="memos/${k}_decision_memo.docx" download>Memo ↓</a>` : ""}
      </div>`;
    card.querySelector("[data-ring]").append(kindDonut(c, 64));
    grid.append(card);
  }
  root.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click",
    () => setState({ view: b.dataset.goto, product: b.dataset.key })));
}

/* ========================================================== EVALUATION */
export function viewEvaluation(root, state) {
  const key = state.product;
  const p = T.products[key];
  const c = T.evidence_counts[key];
  const roll = T.factor_rollups[key];

  const rollupHtml = Object.entries(T.factors).map(([n, label]) => {
    const r = roll[n];
    return `<a href="#f${n}" data-anchor="f${n}">
      <div class="fnum">${r.evidenced + r.computed}<span style="font-size:11px;color:var(--ink-3)">/${r.total - r.na}</span></div>
      <div class="fname">${n} · ${esc(label)}</div>
      <div class="fmeta">${r.evidenced} evidenced · ${r.computed} computed${r.na ? ` · ${r.na} n/a` : ""}</div>
    </a>`;
  }).join("");

  const blocks = Object.entries(T.factors).map(([n, label]) => {
    const rows = Object.keys(T.cell_registry)
      .filter((cid) => cid.split(".")[0] === n)
      .map((cid) => {
        const cell = p.cells[cid];
        const disp = T.cell_display[key][cid];
        const k = statusKind(cell.status || "pending");
        let body;
        if (k === "n/a") {
          body = `<div class="muted">not applicable / not public-sourceable:
            ${esc(disp.plain)}</div>`;
        } else if (!cell.value) {
          body = `<div class="muted">pending: pointer in data/evidence/${esc(key)}_evidence.csv</div>`;
        } else {
          body = `<div class="headline">${gloss(disp.headline)}</div>
            <div class="plain">${esc(disp.plain)}</div>
            <details class="src"><summary>Full text & provenance</summary>
              <div class="fulltext">${esc(cell.value)}</div></details>`;
        }
        return `<div class="cellrow">
          <div class="head"><span class="cid num">${cid}</span>
            <span class="el">${gloss(cell.element)}</span>
            ${chip(cell.status || "pending")} ${citeBtn(key, cid)}
            <button class="pinbtn" data-pin-cell data-key="${key}" data-cid="${cid}"
              title="pin to packet">⌖</button></div>
          ${body}</div>`;
      }).join("");
    return `<div class="factorblock" id="f${n}"><h2>${n} · ${esc(label)}</h2>${rows}</div>`;
  }).join("");

  root.innerHTML = `
    <div class="viewhead"><h1>Six-Factor Evaluation</h1>
      <div class="sub">${esc(p.fund_name)}, ${gloss(p.wrapper)} · coverage
        <b class="num">${esc(c.headline)}</b>
        ${T.facts_meta && T.facts_meta[key] ? `
          · <span class="chip ${T.facts_meta[key].depth === "full" ? "extracted" : "wrapper"}">${T.facts_meta[key].depth} depth</span>
          · <a href="#" onclick="window.tarkSetState({view:'cohorts',cohort:'${esc(T.facts_meta[key].cohort_id)}'});return false">view cohort: ${esc(T.facts_meta[key].cohort_id)}</a>` : ""}
      </div></div>
    <div class="chartbox" style="margin-bottom:4px"><div id="prodchart"></div>
      <div class="chartnote" id="prodchartnote"></div></div>
    <div class="rollup">${rollupHtml}</div>
    ${blocks}`;
  const note = productChart(root.querySelector("#prodchart"), key);
  if (note) root.querySelector("#prodchartnote").textContent = note;
  root.querySelectorAll("[data-anchor]").forEach((a) =>
    a.addEventListener("click", (e) => {
      e.preventDefault();
      document.getElementById(a.dataset.anchor)?.scrollIntoView(
        { behavior: "smooth", block: "start" });
    }));
}

/* ========================================================== BENCHMARKS */
export function viewBenchmarks(root, state, setState) {
  const key = state.product;
  const p = T.products[key];
  const sel = T.benchmarks[key];
  if (!sel) {
    root.innerHTML = `<div class="viewhead"><h1>Benchmark Selection</h1>
      <div class="sub">${esc(p.fund_name)}</div></div>
      <div class="nochart"><div class="k">No selection artifact</div>
      No engine profile exists for this product yet.</div>`;
    return;
  }
  const slotCard = (slot, badge) => {
    const s = sel[slot];
    if (!s) return "";
    const comp = s.comparison;
    return `<div class="card">
      <div class="cap" style="letter-spacing:.14em;font-weight:600;color:var(--plum-700)">${badge}</div>
      <h3>${esc(s.candidate)}</h3>
      <div class="num" style="font-size:15px;margin-top:2px">${s.score}/${s.max}</div>
      <div class="scorebar"><div class="fill" style="width:${s.score / s.max * 100}%"></div></div>
      ${comp ? `<div class="statrow">
        ${stat("KS-PME", comp.ks_pme)}
        ${stat("Direct Alpha", `${comp.direct_alpha_pct}%<small>/yr</small>`)}
        ${stat("Fund", `${comp.fund_ann_pct}%<small>/yr</small>`)}
        ${stat("Benchmark", `${comp.index_ann_pct}%<small>/yr</small>`)}
        ${comp.ks_pme_monthly_schedule != null
          ? stat("KS-PME, monthly schedule", `${comp.ks_pme_monthly_schedule} <span class="chip illustrative">ILLUSTRATIVE</span>`)
          : ""}
      </div>
      <div class="cap">Two-point comparison: one contribution at the window start, one
        valuation at the end. ${gloss("Direct Alpha")} is the annualized form of the same
        two flows.${comp.ks_pme_monthly_schedule != null
          ? ` The monthly-schedule figure is ${esc(comp.schedule_note)}` : ""}
        ${gloss("KS-PME")} and ${gloss("Direct Alpha")} on
        appraisal-lagged NAVs are window-sensitive, disclosed, and explorable:
        <a href="#" data-goto="pme">move the window yourself →</a>
        <span class="num">(${esc(comp.window)}${comp.window_note ? `, ${esc(comp.window_note)}` : ""})</span>
        ${comp.low_confidence ? ` <span class="chip illustrative">${esc(comp.low_confidence)}</span>` : ""}
        ${comp.alignment_note ? ` <span>Lane C composite, ${esc(comp.alignment_note)}.</span>` : ""}</div>`
      : s.comparison_note ? `<div class="cap">Comparison not computable on held data: ${esc(s.comparison_note)}.${
          s.comparison_note.includes("proxy series")
            ? " Refetch the proxy series over a longer window (src/fetch_series.py) to compute it."
            : " The candidate is scored on its own descriptors. A comparison needs a fund return series the filings do not print."}</div>` : ""}
      <details style="margin-top:10px"><summary class="cap" style="cursor:pointer">Scoring rationale</summary>
        <ul style="margin:8px 0 0 18px; font-size:12.5px">
          ${s.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul></details>
    </div>`;
  };

  const rejRows = sel.rejected.map((r, i) => `<tr>
      <td class="entryno">${String(i + 1).padStart(2, "0")}</td>
      <td>${esc(r.candidate)}</td><td class="num">${esc(r.lane)}</td>
      <td class="num">${r.score}/${r.max}</td>
      <td>${esc(r.rejection)}
        <div class="cap" style="margin-top:5px">${r.reasons.map(esc).join(" · ")}</div>
      </td></tr>`).join("");

  root.innerHTML = `
    <div class="viewhead"><h1>Benchmark Selection</h1>
      <div class="sub">${esc(p.fund_name)} · ${esc(sel.strategy)} · lanes A, B and C,
        rubric v2 (12 points, strategy gate below 2), threshold ${T.min_primary_score}/12,
        max attainable on held data ${sel.max_attainable == null ? "none eligible" : `${sel.max_attainable}/12`},
        and every rejection on the record.</div></div>
    <div class="cap" style="margin:6px 0 10px">${sel.declared_benchmarks && sel.declared_benchmarks.length
      ? `Fund declares (cell 5.1): ${sel.declared_benchmarks.map((d) => `<b>${esc(d.name)}</b>, ${esc(d.status)}`).join(" · ")}.
         The declaration itself earns no points.`
      : `Fund declares no benchmark (${esc(sel.declared_none_reason || "cell 5.1")}), so the engine constructs one.`}</div>
    ${sel.escalation ? `<div class="notice">
        <div class="notice-head">Formal escalation: no benchmark assigned</div>
        <div class="notice-body"><b>${esc(sel.escalation.split(".")[0])}.</b>
          ${esc(sel.escalation.split(".").slice(1).join(".").trim())}
          ${key === "dxyz" ? `<div style="margin-top:10px">
            <a class="btn" href="#" data-goto="dxyz">See the premium decomposition →</a></div>` : ""}
        </div></div>` : ""}
    <div class="cardgrid g2">${slotCard("primary", "PRIMARY")}${slotCard("secondary", "SECONDARY")}${sel.primary && !sel.secondary
      ? `<div class="card"><div class="cap" style="letter-spacing:.14em;font-weight:600;color:var(--plum-700)">SECONDARY</div>
         <p class="cap">${esc(sel.secondary_note || "no eligible secondary")}.</p></div>` : ""}</div>
    <h2 style="margin:22px 0 6px">Rejection ledger</h2>
    <div class="cap" style="margin-bottom:8px">Every candidate not selected, with
      its true reason and full rubric rationale: the other half of a defensible
      record.</div>
    <div class="tablewrap"><table class="grid ledger" id="rejtable">
      <thead><tr><th>#</th><th class="sortable" data-col="1">Candidate</th>
        <th class="sortable" data-col="2">Lane</th>
        <th class="sortable" data-col="3">Score</th><th>Reason as logged</th></tr></thead>
      <tbody>${rejRows}</tbody></table></div>
    ${T.memos.includes(key) ? `<div style="margin-top:16px">
      <a class="btn" href="memos/${key}_decision_memo.docx" download>Download decision memo (.docx)</a></div>` : ""}`;

  root.querySelectorAll("[data-goto]").forEach((a) => a.addEventListener("click",
    (e) => { e.preventDefault(); setState({ view: a.dataset.goto }); }));
  const table = root.querySelector("#rejtable");
  table.querySelectorAll("th.sortable").forEach((th) => th.addEventListener("click", () => {
    const col = +th.dataset.col;
    const tb = table.querySelector("tbody");
    const rows = [...tb.rows];
    const dir = th.dataset.dir === "asc" ? -1 : 1;
    th.dataset.dir = dir === 1 ? "asc" : "desc";
    rows.sort((a, b) => {
      const av = a.cells[col].textContent; const bv = b.cells[col].textContent;
      const an = parseFloat(av); const bn = parseFloat(bv);
      return (Number.isNaN(an) || Number.isNaN(bn))
        ? av.localeCompare(bv) * dir : (an - bn) * dir;
    });
    rows.forEach((r) => tb.append(r));
  }));
}

/* ============================================================== PME LAB */
function labEmptyState(root, title, selected, available, what, setState, view, attr) {
  const p = T.products[selected];
  root.innerHTML = `
    <div class="viewhead"><h1>${title}</h1>
      <div class="sub">${esc(p.fund_name)}</div></div>
    <div class="banner amber" data-lab-empty="${esc(selected)}">
      <b>No ${what} on record for ${esc(p.fund_name)}.</b>
      The lab never substitutes another product. It is available for:
      ${available.map((k) => `<a href="#" ${attr}="${k}" style="margin-left:8px">${esc(T.products[k].fund_name.split(" (")[0])}</a>`).join("")}
    </div>
    <div class="cap">Why: ${esc(T.cell_display[selected]["5.2"]?.plain || T.cell_display[selected]["1.1"]?.plain || "no series cell on record")}</div>`;
  root.querySelectorAll(`[${attr}]`).forEach((a) => a.addEventListener("click",
    (e) => { e.preventDefault(); setState({ view, product: a.getAttribute(attr), proxy: "", rho: "" }); }));
}

export function viewPme(root, state, setState) {
  const prods = Object.keys(T.pme_profiles);
  if (!prods.includes(state.product)) {
    labEmptyState(root, "Analysis Lab: benchmark swap", state.product, prods,
      "return series the lab can recompute", setState, "pme", "data-labprod");
    return;
  }
  const key = state.product;
  const prof = T.pme_profiles[key];
  const p = T.products[key];
  const proxyId = T.proxy_library[state.proxy] ? state.proxy : prof.default_proxy;
  const verdict = T.swap_matrix[key][proxyId];

  const isAnnual = prof.granularity === "annual";
  const hasFy = !!prof.fy_returns;
  const fundDaily = prof.fund_series ? T.series[prof.fund_series] : null;

  root.innerHTML = `
    <div class="viewhead"><h1>Analysis Lab: benchmark swap</h1>
      <div class="sub">${esc(p.fund_name)}: recompute PME / Direct Alpha against ANY
        proxy and window, and the engine grades your choice beside the result.
        Customization plus judgment, never instead of it.</div></div>
    ${prof.price_series_warning ? `<div class="banner red"><b>Price-series warning:</b>
      ${esc(prof.price_series_warning)}.</div>` : ""}
    <div class="banner amber"><span class="chip illustrative">USER-CONFIGURED ANALYSIS</span>
      Results below reflect YOUR proxy/window choice, not the engine's selection.
      Appraisal-lagged NAVs are window-sensitive. The standing methodology
      disclosure applies to every recomputation on this screen.</div>
    <div class="cardgrid g2">
      <div class="card">
        <div class="cap" style="margin-bottom:6px">Product:
          ${prods.map((k) => `<a href="#" data-labprod="${k}"
            style="margin-right:8px;${k === key ? "font-weight:700" : ""}">${esc(T.products[k].fund_name.split(" (")[0])}</a>`).join("")}</div>
        <div class="cap">Proxy:
          ${Object.entries(T.proxy_library).map(([id, label]) =>
            `<label style="margin-right:10px"><input type="radio" name="proxy" value="${id}"
              ${id === proxyId ? "checked" : ""}> ${esc(id.toUpperCase())}</label>`).join("")}
          <button class="copylink" data-copylink style="float:right">copy link</button></div>
        <div class="sliderrow"><label id="winlabel">Window start</label>
          <input type="range" id="winstart" min="0" max="1" value="0" step="1">
          <span class="out num" id="winout"></span></div>
        <div class="statrow">
          ${stat("KS-PME", `<span id="pme_ks"></span>`)}
          ${stat("Direct Alpha", `<span id="pme_da"></span><small>/yr</small>`)}
          ${stat("Fund growth", `<span id="pme_fg"></span>×`)}
          ${stat("Proxy growth", `<span id="pme_ig"></span>×`)}
          ${stat("Window", `<span id="pme_win" style="font-size:12px"></span>`)}
          ${stat("KS-PME, monthly schedule", `<span id="pme_sched"></span> <span class="chip illustrative">ILLUSTRATIVE</span>`)}
        </div>
        <div class="chartbox" style="border:0;padding:6px 0 0"><div id="pmechart"></div></div>
        <div class="chartnote" id="pmenote"></div>
      </div>
      <div class="card" id="verdictcard">
        <h3>The engine's judgment of your choice</h3>
        <div id="verdictbody"></div>
      </div>
    </div>
    <h2 style="margin:18px 0 6px">Analysis tables <span class="cap">(vs selected proxy, Python-first math, parity-tested)</span></h2>
    <div class="cardgrid g2" id="tables"></div>`;

  root.querySelectorAll("[data-labprod]").forEach((a) => a.addEventListener("click",
    (e) => { e.preventDefault(); setState({ view: "pme", product: a.dataset.labprod, proxy: "" }); }));
  root.querySelectorAll('input[name="proxy"]').forEach((r) =>
    r.addEventListener("change", () => setState({ proxy: r.value })));

  // --- engine verdict panel (always beside the user's choice) ---
  const sel = T.benchmarks[key];
  const vb = root.querySelector("#verdictbody");
  if (verdict.score !== null && verdict.score !== undefined) {
    vb.innerHTML = `
      <div class="num" style="font-size:22px;font-weight:600;color:var(--plum-900)">
        ${verdict.score}/${verdict.max}</div>
      <div class="scorebar"><div class="fill" style="width:${verdict.score / verdict.max * 100}%"></div></div>
      <ul style="margin:10px 0 0 18px;font-size:12px">
        ${verdict.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
      <div class="cap" style="margin-top:10px">${sel && sel.primary
        ? `Engine's actual selection for this product: <b>${esc(sel.primary.candidate)}</b>
           (${sel.primary.score}/12). Rejection ledger: <a href="#" data-goto-bench>view →</a>`
        : `Engine outcome for this product: FORMAL ESCALATION, no benchmark assigned.
           <a href="#" data-goto-bench>see the notice →</a>`}</div>`;
  } else {
    vb.innerHTML = `<div class="banner amber" style="margin:0">
      <b>Off the engine's menu.</b> ${esc(verdict.verdict)}</div>
      <div class="cap" style="margin-top:8px">${sel && sel.primary
        ? `Engine's actual selection: <b>${esc(sel.primary.candidate)}</b> (${sel.primary.score}/12).`
        : "Engine outcome: FORMAL ESCALATION, no benchmark assigned."}
        <a href="#" data-goto-bench>rubric & ledger →</a></div>`;
  }
  root.querySelectorAll("[data-goto-bench]").forEach((a) => a.addEventListener("click",
    (e) => { e.preventDefault(); setState({ view: "benchmarks" }); }));

  // --- window machinery per tier: every window lives inside the selected
  // proxy's coverage (same clipping rule as tark_benchmark.comparison_stats)
  const slider = root.querySelector("#winstart");
  const idxAll = T.series[proxyId];
  const idx0 = idxAll[0][0];
  const idx1 = idxAll[idxAll.length - 1][0];
  let starts; let fyFirst = 0; let fyLast = -1; let fyEnd = null; let clipNote = "";
  let notComputable = "";
  if (hasFy) {
    const bounds = fiscalYearBounds(prof.fy_window, prof.fy_returns.length);
    const kept = bounds.map((b, i) => [b, i]).filter(([b]) => b[0] >= idx0 && b[1] <= idx1);
    if (!kept.length) {
      notComputable = `no whole fiscal year of ${prof.fy_window[0]} to ${prof.fy_window[1]} lies inside the proxy series (${idx0} to ${idx1})`;
    } else {
      fyFirst = kept[0][1]; fyLast = kept[kept.length - 1][1]; fyEnd = kept[kept.length - 1][0][1];
      starts = kept.map(([b]) => b[0]);
      if (kept.length < bounds.length) {
        clipNote = `clipped: proxy series begins ${idx0}, ${bounds.length - kept.length} fiscal year(s) outside it dropped`;
      }
    }
  } else if (isAnnual) {
    starts = [prof.fy_window[0]];
    if (prof.fy_window[0] < idx0 || prof.fy_window[1] > idx1) {
      notComputable = `the single disclosed figure covers ${prof.fy_window[0]} to ${prof.fy_window[1]} and cannot be clipped to the proxy series (${idx0} to ${idx1})`;
    }
    slider.disabled = true;
    root.querySelector("#winlabel").textContent =
      "Window fixed: single disclosed ITD figure";
  } else {
    const me = monthEndPoints(fundDaily).map(([d]) => d);
    const all = [fundDaily[0][0], ...me.slice(0, me.length - 13)];
    starts = all.filter((d) => d >= idx0);
    if (starts.length !== all.length) {
      const firstIn = fundDaily.find(([d]) => d >= idx0)[0];
      if (!starts.includes(firstIn)) starts.unshift(firstIn);
      clipNote = `clipped: proxy series begins ${idx0}`;
    }
  }
  if (notComputable) {
    root.querySelector("#pmenote").textContent =
      `Comparison not computable on held data: ${notComputable}. Refetch the proxy series over a longer window (src/fetch_series.py) to compute it.`;
    slider.disabled = true;
    return;
  }
  slider.max = String(starts.length - 1);
  const wi = Math.min(parseInt(state.win || "0", 10) || 0, starts.length - 1);
  slider.value = String(wi);

  function recompute() {
    const i = +slider.value;
    const d0 = starts[i];
    const idxDaily = T.series[proxyId];
    let d1; let fGrowth; let fundPts;
    if (hasFy) {
      d1 = fyEnd;
      const rets = prof.fy_returns.slice(fyFirst + i, fyLast + 1);
      fGrowth = rets.reduce((g, r) => g * (1 + r), 1);
      let acc = 1;
      fundPts = [[d0, 1]];
      rets.forEach((r, j) => { acc *= 1 + r;
        fundPts.push([`${+d0.slice(0, 4) + j + 1}${d0.slice(4)}`, acc]); });
    } else if (isAnnual) {
      d1 = prof.fy_window[1];
      fGrowth = (1 + prof.aatr) ** prof.aatr_years;
      fundPts = [[d0, 1], [d1, fGrowth]];
    } else {
      const fundLast = fundDaily[fundDaily.length - 1][0];
      d1 = fundLast <= idx1 ? fundLast : idx1;
      if (fundLast > idx1 && !clipNote.includes("ends")) clipNote += `${clipNote ? ", " : "clipped: "}proxy series ends ${idx1}`;
      const win = fundDaily.filter(([d]) => d >= d0 && d <= d1);
      const me = monthEndPoints(win);
      fGrowth = win[win.length - 1][1] / win[0][1];
      let acc = 1;
      fundPts = [[me[0][0], 1]];
      periodReturns(me.map(([, v]) => v)).forEach((r, j) => {
        acc *= 1 + r; fundPts.push([me[j + 1][0], acc]); });
    }
    const flows = [[d0, -1.0], [d1, fGrowth]];
    // one anchor: PME, alpha and the displayed growth all read the proxy
    // level on or before each flow date from the full series (a window
    // that starts on a non-trading day must not shift the anchor)
    const idx = idxDaily.filter(([d]) => d >= d0 && d <= d1);
    const ks = ksPme(flows, idxDaily);
    const da = directAlpha(flows, idxDaily);
    const iGrowth = levelOn(idxDaily, d1) / levelOn(idxDaily, d0);
    const idxMe = monthEndPoints(idx);
    let acc = 1;
    const idxPts = [[idxMe[0][0], 1]];
    periodReturns(idxMe.map(([, v]) => v)).forEach((r, j) => {
      acc *= 1 + r; idxPts.push([idxMe[j + 1][0], acc]); });

    root.querySelector("#pme_ks").textContent = ks.toFixed(4);
    root.querySelector("#pme_da").textContent =
      da === null ? "n/a" : `${(da * 100).toFixed(2)}%`;
    root.querySelector("#pme_fg").textContent = fGrowth.toFixed(4);
    root.querySelector("#pme_sched").textContent = (!hasFy && !isAnnual)
      ? ksPme(monthlyScheduleFlows(fundDaily, d0, d1), idxDaily).toFixed(4)
      : "n/a on annual data";
    root.querySelector("#pme_ig").textContent = iGrowth.toFixed(4);
    root.querySelector("#pme_win").textContent = `${d0} → ${d1}${clipNote ? ` (${clipNote})` : ""}`;
    root.querySelector("#winout").textContent = d0;
    lineChart(root.querySelector("#pmechart"), {
      series: [
        { points: fundPts, label: `${T.products[key].fund_name.split(" (")[0]}, ${fundDaily
            ? T.series_sources[prof.fund_series].label
            : hasFy ? "disclosed fiscal-year returns" : "single disclosed ITD figure"} (growth of 1.0)`,
          color: "#593380", width: 2 },
        { points: idxPts, label: `${proxyId.toUpperCase()}, ${T.series_sources[proxyId].label} (growth of 1.0)`,
          color: "#92600d", width: 1.6, dash: "5,4" },
      ],
      height: 280, yFormat: (v) => v.toFixed(2) + "×",
    });
    root.querySelector("#pmenote").textContent =
      (hasFy ? "Fund line compounds disclosed fiscal-year returns (fiscal-step windows: annual is the honest granularity). "
        : isAnnual ? "Single disclosed ITD figure: window fixed to the disclosure period. "
        : "Fund growth daily-anchored. Lines month-end sampled for drawing. ")
      + "Same code path as the Python engine (parity-tested).";
    renderTables();
  }

  // --- analysis tables: calendar years, drawdowns, rolling 12m ---
  function renderTables() {
    const box = root.querySelector("#tables");
    const idxDaily = T.series[proxyId];
    const idxMe = monthEndPoints(idxDaily);
    const idxCal = calendarYearReturns(idxMe);
    const pct = (x) => (x * 100).toFixed(1) + "%";

    let fundCal = null; let fundLabel = ""; let ddHtml = ""; let rollHtml = "";
    if (fundDaily) {
      const me = monthEndPoints(fundDaily);
      fundCal = calendarYearReturns(me);
      fundLabel = T.series_sources[prof.fund_series].label + (prof.price_series_warning ? " (premium-driven!)" : "");
      const eps = drawdownEpisodes(me, 3);
      ddHtml = `<div class="card"><h3>Drawdowns: top ${eps.length} episodes</h3>
        <table class="grid" style="margin-top:6px"><thead><tr><th>Peak</th><th>Trough</th>
          <th>Depth</th><th>Recovered</th></tr></thead><tbody>
        ${eps.map((e) => `<tr><td class="num">${e.peak_date}</td>
          <td class="num">${e.trough_date}</td>
          <td class="num" style="color:var(--alarm)">${pct(e.depth)}</td>
          <td class="num">${e.recovery_date || "not yet"}</td></tr>`).join("")}
        </tbody></table>
        <div class="cap" style="margin-top:6px">${prof.price_series_warning
          ? "Price series: episodes are PREMIUM collapses, not portfolio losses."
          : "Month-end sampled. Appraisal smoothing understates true depth (see De-smoothing Lab)."}</div></div>`;
      const rets = periodReturns(me.map(([, v]) => v));
      if (rets.length >= 13) {
        const rr = rollingReturns(rets, 12);
        const rv = rollingVol(rets, 12, 12);
        const dates = me.slice(13).map(([d]) => d);
        rollHtml = `<div class="card"><h3>Rolling 12-month</h3>
          <div id="rollchart"></div>
          <div class="cap">Latest: return ${pct(rr[rr.length - 1])}, vol ${pct(rv[rv.length - 1])}.
            β vs ${proxyId.toUpperCase()} over common months:
            <b class="num">${beta(rets, periodReturns(idxMe.filter(([d]) => d >= me[0][0]).map(([, v]) => v))).toFixed(2)}</b></div></div>`;
        setTimeout(() => {
          const el = root.querySelector("#rollchart");
          if (el) lineChart(el, { series: [
            { points: dates.map((d, j) => [d, rr[j] * 100]), label: "rolling 12m return (%)", color: "#593380", width: 1.6 },
            { points: dates.map((d, j) => [d, rv[j] * 100]), label: "rolling 12m vol (%)", color: "#14636d", width: 1.3, dash: "4,3" },
          ], height: 220, includeZero: true, yFormat: (v) => v.toFixed(0) + "%" });
        }, 0);
      }
    } else if (key === "breit" && T.series_monthly.breit_nav) {
      const pts = T.series_monthly.breit_nav.filter(([d]) => d <= "2025-12-31");
      fundCal = calendarYearReturns(pts);
      fundLabel = "NAV path (distributions EXCLUDED, understates total return)";
      const eps = drawdownEpisodes(pts, 3);
      ddHtml = `<div class="card"><h3>NAV-path drawdowns</h3>
        <table class="grid" style="margin-top:6px"><thead><tr><th>Peak</th><th>Trough</th>
          <th>Depth</th><th>Recovered</th></tr></thead><tbody>
        ${eps.map((e) => `<tr><td class="num">${e.peak_date}</td>
          <td class="num">${e.trough_date}</td>
          <td class="num" style="color:var(--alarm)">${pct(e.depth)}</td>
          <td class="num">${e.recovery_date || "not yet"}</td></tr>`).join("")}
        </tbody></table>
        <div class="cap" style="margin-top:6px">Printed monthly NAV path, Class I,
          distributions excluded. Total-return drawdowns are smaller.</div></div>`;
    } else {
      const ann = T.series_annual[key] || [];
      const withTr = ann.filter((r) => r.total_return_pct);
      fundCal = withTr.map((r) => [r.fy_end.slice(0, 4) + " (FY)", +r.total_return_pct / 100]);
      fundLabel = "fiscal-year total returns as filed";
      ddHtml = `<div class="nochart"><div class="k">Drawdown / rolling tables unavailable</div>
        Annual disclosure cadence: intra-year drawdowns and rolling 12-month
        stats require a monthly-or-finer public series, which this wrapper does
        not publish (see cells 1.6/1.7).</div>`;
    }

    box.innerHTML = `
      <div class="card"><h3>Calendar-year returns</h3>
        <table class="grid" style="margin-top:6px"><thead><tr><th>Year</th>
          <th>${esc(T.products[key].fund_name.split(" (")[0])} <span class="cap">(${esc(fundLabel)})</span></th>
          <th>${proxyId.toUpperCase()}</th></tr></thead><tbody>
        ${fundCal.map(([y, r]) => {
          const iy = idxCal.find(([yy]) => yy === String(y).slice(0, 4));
          return `<tr><td class="num">${esc(String(y))}</td>
            <td class="num">${pct(r)}</td>
            <td class="num">${iy ? pct(iy[1]) : "—"}</td></tr>`;
        }).join("")}</tbody></table>
        <div class="cap" style="margin-top:6px">First covered year may be partial
          (series start mid-year). Proxy years from daily adj close.</div></div>
      ${ddHtml}${rollHtml}`;
  }

  slider.addEventListener("input", recompute);          // live while dragging
  slider.addEventListener("change", () => setState({ win: slider.value }));
  recompute();
}

/* ============================================================ LIQUIDITY */
export function viewLiquidity(root, state) {
  const key = state.product;
  const plan = state.plan;
  const m = T.liquidity[`${plan}__${key}`];
  const p = T.products[key];
  if (!m) {
    root.innerHTML = `<h1>Liquidity Match</h1><div class="nochart">
      Match pending for this plan × product.</div>`;
    return;
  }
  const bannerCls = m.verdict.startsWith("aligned") ? "green"
    : m.verdict === "conditional-weak" ? "red" : "amber";
  const sc = m.scenario;
  const profile = m.wrapper_facts;
  const stress = m.stressed_scenario;

  root.innerHTML = `
    <div class="viewhead"><h1>Liquidity Match</h1>
      <div class="sub">${esc(p.fund_name)} × ${esc(m.plan_display_label)}. Tail
        ${m.plan_inputs.tail_share_pct}% of accounts
        (${Math.round(m.plan_inputs.separated_with_balances).toLocaleString()}
        separated), plan direction: ${esc(m.plan_direction)}.</div></div>
    <div class="banner ${bannerCls}"><h3>Verdict: ${esc(m.verdict.toUpperCase())}</h3></div>
    <ul style="margin:0 0 16px 18px; font-size:13.5px" id="reasons">
      ${m.reasons.map((r) => `<li style="margin-bottom:6px">${esc(r)}</li>`).join("")}</ul>
    <div class="cardgrid g2">
      <div class="card">
        <h3>Capacity vs demand <span class="chip illustrative">ILLUSTRATIVE</span></h3>
        <div class="cap">Wrapper capacity is a filed fact (cells ${esc(String(profile.source_cell))}).
          The demand model is an adjustable scenario, never presented as fact.</div>
        <div class="sliderrow"><label>Plan allocation to product</label>
          <input type="range" id="s_alloc" min="1" max="10" step="0.5"
            value="${sc.allocation_pct_of_plan}"><span class="out" id="o_alloc"></span></div>
        <div class="sliderrow"><label>Tail annual turnover</label>
          <input type="range" id="s_tail" min="5" max="50" step="1"
            value="${sc.tail_annual_turnover_pct}"><span class="out" id="o_tail"></span></div>
        <div class="sliderrow"><label>Active annual turnover</label>
          <input type="range" id="s_act" min="1" max="15" step="0.5"
            value="${sc.active_annual_turnover_pct}"><span class="out" id="o_act"></span></div>
        <div id="capchart" style="margin-top:8px"></div>
        <div class="cap" id="o_reason" style="margin-top:6px"></div>
      </div>
      <div class="card"><h3>Wrapper facts</h3>
        <table class="grid" style="border:0;margin-top:8px">
          <tr><td>Kind</td><td class="num">${gloss(profile.kind.replace(/_/g, " "))}</td></tr>
          <tr><td>Dealing cadence</td><td class="num">${profile.cadence_per_year}×/year</td></tr>
          <tr><td>Cap</td><td class="num">${profile.cap_pct === null ? "—" : profile.cap_pct + "%"} of ${esc(profile.cap_base)}</td></tr>
          <tr><td>Exchange-listed</td><td class="num">${profile.exchange ? "yes" : "no"}</td></tr>
          <tr><td>Gating history</td><td class="num">${profile.gate_history ? "YES (3.3)" : "none identified"}</td></tr>
          <tr><td>Early repurchase</td><td>${esc(profile.early_fee)}</td></tr>
        </table>
        <h3 style="margin-top:14px">Stress test <span class="chip illustrative">ILLUSTRATIVE</span></h3>
        <div class="cap">${esc(stress.assumptions)}</div>
        <div class="statrow" style="margin:8px 0">
          ${stat("Stressed demand", `<span class="num">${stress.demand_pct_of_position}%</span><small>/yr of position</small>`)}
        </div>
        <div class="cap"><b>${esc(stress.outcome)}</b></div>
        <div class="cap" style="margin-top:8px">Citations: ${m.citations.map(esc).join(" · ")}</div>
      </div>
    </div>`;

  // ---- named scenarios (localStorage only; nothing leaves the browser) ----
  const SCN_KEY = "tark_scenarios";
  const loadScn = () => { try { return JSON.parse(localStorage.getItem(SCN_KEY) || "{}"); } catch { return {}; } };
  const scnPanel = document.createElement("div");
  scnPanel.className = "card";
  scnPanel.style.marginTop = "14px";
  root.querySelector(".cardgrid").after(scnPanel);
  function renderScenarios() {
    const scns = loadScn();
    const names = Object.keys(scns).slice(0, 12);
    const cur = {
      allocation_pct_of_plan: +root.querySelector("#s_alloc").value,
      tail_annual_turnover_pct: +root.querySelector("#s_tail").value,
      active_annual_turnover_pct: +root.querySelector("#s_act").value,
    };
    scnPanel.innerHTML = `<h3>Saved scenarios
        <span class="chip illustrative">ILLUSTRATIVE</span></h3>
      <div class="cap">Named parameter sets live in YOUR browser (localStorage).
        Compare up to three against the current sliders, per the selected
        plan × product.</div>
      <div style="display:flex;gap:8px;margin:8px 0;flex-wrap:wrap">
        <input id="scnname" placeholder="scenario name" maxlength="24"
          style="border:1px solid var(--line);border-radius:3px;padding:5px 9px;font:500 12px var(--text)">
        <button class="copylink" id="scnsave">save current sliders</button>
        ${names.map((n) => `<label class="comparepick" style="margin:0">
          <span class="${(window._scnSel || []).includes(n) ? "on" : ""}"
            style="border:1px solid var(--line);border-radius:999px;padding:3px 10px;font-size:12px;cursor:pointer"
            data-scn="${esc(n)}">${esc(n)} ×</span></label>`).join("")}
      </div>
      <div id="scncompare"></div>`;
    scnPanel.querySelector("#scnsave").addEventListener("click", () => {
      const name = (scnPanel.querySelector("#scnname").value || "").trim().slice(0, 24);
      if (!name) return;
      const all = loadScn(); all[name] = cur;
      localStorage.setItem(SCN_KEY, JSON.stringify(all));
      window._scnSel = [...(window._scnSel || []), name].slice(-3);
      renderScenarios();
    });
    scnPanel.querySelectorAll("[data-scn]").forEach((el) => el.addEventListener("click", (ev) => {
      const n = el.dataset.scn;
      if (ev.altKey) { const all = loadScn(); delete all[n];
        localStorage.setItem(SCN_KEY, JSON.stringify(all));
      } else {
        window._scnSel = (window._scnSel || []).includes(n)
          ? window._scnSel.filter((x) => x !== n)
          : [...(window._scnSel || []), n].slice(-3);
      }
      renderScenarios();
    }));
    const chosen = (window._scnSel || []).filter((n) => scns[n]).slice(0, 3);
    const out = scnPanel.querySelector("#scncompare");
    if (!chosen.length) { out.innerHTML = `<p class="cap">Select saved scenarios to compare (alt-click removes).</p>`; return; }
    const cols = [["current sliders", cur], ...chosen.map((n) => [n, scns[n]])];
    out.innerHTML = `<div class="tablewrap"><table class="grid"><thead><tr>
      <th>Parameter</th>${cols.map(([n]) => `<th>${esc(n)}</th>`).join("")}</tr></thead><tbody>
      ${[["Allocation %", "allocation_pct_of_plan"], ["Tail turnover %", "tail_annual_turnover_pct"],
         ["Active turnover %", "active_annual_turnover_pct"]].map(([lbl, f]) =>
        `<tr><td>${lbl}</td>${cols.map(([, prm]) => `<td class="num">${prm[f]}</td>`).join("")}</tr>`).join("")}
      <tr><td style="font-weight:600">Demand %/yr of position</td>
        ${cols.map(([, prm]) => {
          const o = computeScenario(m.plan_inputs, profile, prm);
          return `<td class="num" style="font-weight:600">${o.demand_pct_of_position.toFixed(1)}%
            ${o.thin_headroom ? '<span class="chip trap">thin</span>' : ""}</td>`;
        }).join("")}</tr>
      <tr><td>Annual demand</td>
        ${cols.map(([, prm]) => `<td class="num">${money(computeScenario(m.plan_inputs, profile, prm).annual_demand_usd)}</td>`).join("")}</tr>
    </tbody></table></div>
    <div class="cap" style="margin-top:4px">All columns ILLUSTRATIVE: parameter
      choices, not facts. Wrapper capacity ${profile.exchange ? "is market depth (listed)" :
      (profile.cadence_per_year * profile.cap_pct).toFixed(0) + "%/yr (filed)"}.</div>`;
  }

  const els = ["alloc", "tail", "act"].map((s) => root.querySelector("#s_" + s));
  function update() {
    const params = {
      allocation_pct_of_plan: +els[0].value,
      tail_annual_turnover_pct: +els[1].value,
      active_annual_turnover_pct: +els[2].value,
    };
    root.querySelector("#o_alloc").textContent = params.allocation_pct_of_plan.toFixed(1) + "%";
    root.querySelector("#o_tail").textContent = params.tail_annual_turnover_pct.toFixed(0) + "%";
    root.querySelector("#o_act").textContent = params.active_annual_turnover_pct.toFixed(1) + "%";
    const out = computeScenario(m.plan_inputs, profile, params);
    const stressOut = computeScenario(m.plan_inputs, profile, {
      ...params,
      tail_annual_turnover_pct: params.tail_annual_turnover_pct * 2,
      active_annual_turnover_pct: params.active_annual_turnover_pct * 1.5,
    });
    const cap = out.annual_wrapper_capacity_pct;
    barChart(root.querySelector("#capchart"), {
      items: [
        { label: "Wrapper capacity (filed)", value: cap,
          color: "#593380", note: "daily (exchange-listed)" },
        { label: "Scenario demand (illustrative)",
          value: out.demand_pct_of_position, color: "#92600d" },
        { label: "Stressed demand (illustrative)",
          value: stressOut.demand_pct_of_position, color: "#9d2f26" },
      ],
      format: (v) => v.toFixed(0) + "%",
      max: Math.max(cap || 0, stressOut.demand_pct_of_position) * 1.15 || 30,
    });
    const r = scenarioReason(out);
    root.querySelector("#o_reason").innerHTML =
      `<span class="num">${money(out.plan_allocation_usd)}</span> position ·
       <span class="num">${money(out.annual_demand_usd)}</span>/yr demand. ` +
      esc(r ? r : "Exchange-listed: capacity is market depth, not a fund cap.") +
      ` <b>[ILLUSTRATIVE]</b>`;
  }
  els.forEach((e) => e.addEventListener("input", () => { update(); renderScenarios(); }));
  update();
  renderScenarios();
}

/* ================================================================ FEES */
export function viewFees(root) {
  const rows = [
    ["2.1", "Management fee (rate AND base)"], ["2.2", "Incentive fee"],
    ["2.3", "Total expense ratio"], ["2.4", "AFFE"],
    ["2.6", "Loads & servicing"], ["2.7", "Early repurchase"],
    ["6.4", "Tax reporting (K-1 vs 1099)"],
  ];
  const keys = Object.keys(T.products);
  const BASES = { net_assets: "net assets", nav: "NAV", aggregate_nav: "aggregate NAV",
    managed_assets: "MANAGED ASSETS (leverage-inclusive)",
    gross_incl_borrowings: "GROSS assets incl. borrowings",
    outstanding_shares: "outstanding shares", lesser_of_dual_base: "the lesser of two bases" };
  const TRAP_BASES = new Set(["managed_assets", "gross_incl_borrowings"]);
  const fact = (k, f) => (T.facts[k] || {})[f] || null;
  const val = (k, f) => fact(k, f)?.value ?? null;

  // the headline chip for each row comes from the TYPED facts layer. An
  // absence says "none", an n/a cell says "n/a", and a null fact shows the
  // cell's status word. No number is ever read out of the prose here.
  const typedChip = (cid, k) => {
    const kind = statusKind((T.products[k].cells[cid] || {}).status || "pending");
    if (kind === "n/a") return { text: "n/a", badge: "" };
    if (cid === "2.1") {
      const pct = val(k, "mgmt_fee_pct"), base = val(k, "mgmt_fee_base");
      if (pct === null) return { text: kind, badge: "" };
      const badge = base ? `<span class="chip ${TRAP_BASES.has(base) ? "trap" : "okbase"}">base: ${esc(BASES[base] || base)}</span>` : "";
      return { text: `${pct.toFixed(2)}% on ${BASES[base] || base || "a base not typed"}`, badge };
    }
    if (cid === "2.2") { const v = val(k, "incentive_fee"); return { text: v === null ? kind : fmtIncentive(v), badge: "" }; }
    if (cid === "2.3") { const v = val(k, "expense_ratio_pct"); return { text: v === null ? kind : `${v.toFixed(2)}% net expense ratio`, badge: "" }; }
    if (cid === "2.4") {
      const v = val(k, "affe");
      if (v === null) return { text: kind, badge: "" };
      if (!v.present) return { text: "none", badge: "" };
      return { text: v.rate_pct != null ? `AFFE ${v.rate_pct.toFixed(2)}%` : "AFFE line present, rate not typed", badge: "" };
    }
    if (cid === "2.7") { const v = val(k, "early_repurchase"); return { text: v === null ? kind : fmtEarly(v), badge: "" }; }
    if (cid === "6.4") {
      const v = val(k, "tax_form");
      if (v === null) return { text: kind, badge: "" };
      return { text: v === "K-1" ? "Schedule K-1" : `Form ${v}`,
        badge: `<span class="chip ${v === "K-1" ? "trap" : "extracted"}">${v === "K-1" ? "Schedule K-1" : "Form 1099"}</span>` };
    }
    return { text: kind, badge: "" };     // 2.6: no typed fact, status word only
  };

  const body = rows.map(([cid, label]) => {
    const tds = keys.map((k) => {
      const cell = T.products[k].cells[cid];
      const disp = T.cell_display[k][cid];
      const kind = statusKind(cell.status || "pending");
      const { text, badge } = typedChip(cid, k);
      const support = cell.value && kind !== "n/a"
        ? `<span style="font-size:11.5px;color:var(--ink-2)">${short(disp.plain, 120)}</span>`
        : `<span class="cap">${kind === "n/a" ? esc(disp.plain).slice(0, 110) : "pending"}</span>`;
      return `<td>${badge ? badge + "<br>" : ""}
        <div class="headline" data-fee-chip="${cid}" data-product="${esc(k)}" style="font-size:14px;margin:3px 0 1px">${esc(text)}</div>
        ${support}<div style="margin-top:5px">${chip(cell.status || "pending")} ${citeBtn(k, cid)}</div></td>`;
    }).join("");
    return `<tr><td style="font-weight:600; white-space:nowrap">${cid}<br>
      <span class="cap">${gloss(label)}</span></td>${tds}</tr>`;
  }).join("");

  // bars: the typed net expense ratio, or an explicit absence with its reason
  const items = keys.map((k) => {
    const f = fact(k, "expense_ratio_pct");
    return { product: k, label: T.products[k].fund_name.split(" (")[0],
      value: f && f.value !== null ? f.value : null,
      color: f && f.value !== null ? "#593380" : "#837b8e",
      note: f && f.value !== null ? "" : `no comparable net expense ratio line: ${f?.reason || "not typed"}` };
  });
  const missing = items.filter((i) => i.value === null).map((i) => i.label);

  root.innerHTML = `
    <div class="viewhead"><h1>Fee Matrix</h1>
      <div class="sub">The headline rate is never the story. The BASE is.</div></div>
    <div class="chartbox" style="margin-bottom:14px">
      <h3 style="margin-bottom:4px">Net expense ratio, typed from cell 2.3, where one exists</h3>
      <div id="feechart"></div>
      <div class="chartnote">Each bar is the typed fact facts.expense_ratio_pct
        (bases differ by wrapper and are quoted in the fact's note, click source
        on row 2.3). No comparable line for ${missing.length ? esc(missing.join(", ")) : "none"}:
        their burden is fee plus performance participation (2.1/2.2), flagged in
        the matrix below. Universe = this roster.</div></div>
    <div class="tablewrap"><table class="grid">
      <thead><tr><th style="min-width:120px">Cell</th>
        ${keys.map((k) => `<th style="min-width:210px">${esc(T.products[k].fund_name)}</th>`).join("")}
      </tr></thead><tbody>${body}</tbody></table></div>
    <p class="cap" style="margin-top:10px">Headline chips are the typed facts
      layer (data/facts, each field cites its cell). An absence reads "none".
      Click source for document, section and verbatim quote.</p>`;

  const box = root.querySelector("#feechart");
  box.dataset.items = JSON.stringify(items.map((i) => ({ product: i.product, value: i.value })));
  barChart(box, { items, format: (v) => v.toFixed(2) + "%" });
}

/* ========================================================== DXYZ CHART */
function nslrPanel(root) {
  // the venture cohort's second market-priced member: DXYZ's premium has a
  // MIRROR — NSLR's persistent discount. Pattern, not anecdote.
  const sp = T.supplement.ssss_premium;
  const px = T.series.nslr_daily;
  const qnav = (T.series_quarterly || {}).ssss || [];
  if (!sp || !px || !qnav.length) return;
  const box = root.querySelector("#nslrpanel");
  if (!box) return;
  box.innerHTML = `
    <h2 style="margin:20px 0 6px">The pattern, not the anecdote: NSLR (fka
      SuRo/SSSS), the cohort's other market-priced member</h2>
    <div class="statrow">
      ${stat("Premium/(discount) now", sp.premium_pct_vs_latest_printed_nav + "%",
             `close ${sp.last_close_date} vs printed NAV ${sp.latest_nav_date}`)}
      ${stat("Across 16 printed quarters",
             `${Math.min(...sp.premium_pct_at_each_printed_quarter)}% – ${Math.max(...sp.premium_pct_at_each_printed_quarter)}%`)}
    </div>
    <div class="chartbox"><div id="nslrchart"></div>
      <div class="chartnote">DXYZ trades at a PREMIUM to NAV, NSLR at a
        persistent DISCOUNT. Two listed venture vehicles, two opposite gaps,
        one conclusion: the market price is not the portfolio. This is why the
        engine escalates BOTH rather than benchmarking either price
        (data/analytics/supplement.json ssss_premium and both selection
        artifacts).</div></div>`;
  lineChart(box.querySelector("#nslrchart"), {
    series: [
      { points: px, label: "NSLR market price (daily close)", color: "#593380", width: 1.3 },
      { points: qnav, label: "NAV per share (quarterly, printed)",
        color: "#9d2f26", markersOnly: true, markers: true },
    ],
    height: 280, yFormat: (v) => "$" + v.toFixed(0),
  });
}

export function viewDxyz(root) {
  const nav = T.dxyz_nav;
  const px = T.series.dxyz_daily;
  const closes = px.map(([, v]) => v);
  const peak = Math.max(...closes);
  const peakDate = px[closes.indexOf(peak)][0];
  const troughAfterPeak = px.filter(([d]) => d > peakDate)
    .reduce((min, [d, v]) => (v < min[1] ? [d, v] : min), ["", Infinity]);
  const dd = (troughAfterPeak[1] / peak - 1) * 100;
  const navPts = nav.rows.filter((r) => r.period_end && r.nav_per_share)
    .map((r) => [r.period_end, r.nav_per_share]);
  const latest = nav.rows[nav.rows.length - 1];
  const dp = T.supplement.dxyz_premium;

  root.innerHTML = `
    <div class="viewhead"><h1>DXYZ: Price vs NAV</h1>
      <div class="sub">The market price is a premium series, not a portfolio
        series, which is WHY the engine refused a benchmark.</div></div>
    <div class="statrow">
      ${stat("Peak close", "$" + peak.toFixed(2), peakDate)}
      ${stat("Drawdown from peak", dd.toFixed(1) + "%", "computed from price series")}
      ${stat("Latest filed NAV/share", "$" + latest.nav_per_share.toFixed(2), latest.period_end)}
      ${stat("Premium now", dp.premium_pct_vs_latest_filed_nav + "%",
             `close ${dp.last_close_date} vs latest filed NAV`)}
      ${stat("Filed premium range", `${dp.filed_premium_range_pct[0]}% – ${dp.filed_premium_range_pct[1]}%`,
             "fund's own prospectus table")}
    </div>
    <div class="chartbox"><div id="dxyzchart"></div>
      <div class="chartnote">Price: daily close (${px.length} obs). Red points:
        the fund's own quarterly filed NAV per share. Log scale: the vertical
        gap IS the ${gloss("premium/discount")}.</div></div>
    <h2 style="margin:18px 0 8px">Quarterly premium/(discount), as filed</h2>
    <div class="tablewrap"><table class="grid"><thead><tr>
      <th>Period</th><th>NAV/share</th><th>Price high</th><th>Price low</th>
      <th>Premium at high</th><th>Premium at low</th></tr></thead><tbody>
      ${nav.rows.map((r) => `<tr><td>${esc(r.period)}</td>
        <td class="num">$${r.nav_per_share?.toFixed(2) ?? "—"}</td>
        <td class="num">$${r.price_high?.toFixed(2) ?? "—"}</td>
        <td class="num">$${r.price_low?.toFixed(2) ?? "—"}</td>
        <td class="num">${r.premium_pct_at_high ?? "—"}%</td>
        <td class="num">${r.premium_pct_at_low ?? "—"}%</td></tr>`).join("")}
    </tbody></table></div>
    <div id="nslrpanel"></div>`;

  lineChart(root.querySelector("#dxyzchart"), {
    series: [
      { points: px, label: "Market price (daily close)", color: "#593380", width: 1.4 },
      { points: navPts, label: "NAV per share (quarterly, filed)",
        color: "#9d2f26", markersOnly: true, markers: true },
    ],
    annotations: [
      { x: peakDate, y: peak, text: `peak $${peak.toFixed(2)}`, color: "#9d2f26" },
      { x: troughAfterPeak[0], y: troughAfterPeak[1],
        text: `${dd.toFixed(1)}% from peak`, color: "#9d2f26", dy: 16 },
    ],
    height: 340, logY: true, yFormat: (v) => "$" + v.toFixed(0),
  });
  nslrPanel(root);
}

/* ======================================================== DE-SMOOTHING */
export function viewDesmooth(root, state) {
  // data-driven roster: every daily series in the bundle (from the engine
  // profiles) plus the printed monthly NAV path where one exists
  const AVAILABLE = {};
  for (const [k, d] of Object.entries(T.daily_series || {})) {
    if (!T.series[d.series]) continue;
    AVAILABLE[k] = () => {
      const me = monthEndPoints(T.series[d.series]);
      const m = k === "cliffwater_cclfx" && T.metrics?.cclfx?.full_history;
      return { rets: periodReturns(me.map(([, v]) => v)),
               dates: me.map(([d]) => d),
               basis: `monthly returns from ${d.label}`,
               price: d.price_series,
               committed: m
                 ? `pipeline: rho ${m.lag1_autocorr_rho}, observed ${m.ann_vol_observed_pct}% → de-smoothed ${m.ann_vol_desmoothed_pct}% (data/analytics/metrics.json)`
                 : "no committed pipeline diagnostic for this series yet (live recompute only)" };
    };
  }
  if (T.series_monthly?.breit_nav) {
    AVAILABLE.breit = () => {
      const pts = T.series_monthly.breit_nav.filter(([d]) => d <= "2025-12-31");
      const bd = T.supplement.breit_monthly_diagnostics;
      return { rets: periodReturns(pts.map(([, v]) => v)),
               dates: pts.map(([d]) => d),
               basis: "monthly NAV path as PRINTED in the 10-K (distributions excluded, appraisal-process diagnostic)",
               price: false,
               committed: `pipeline: rho ${bd.lag1_autocorr_rho}, observed ${bd.nav_path_ann_vol_pct}% → de-smoothed ${bd.desmoothed_ann_vol_pct}% (data/analytics/supplement.json)` };
    };
  }
  const UNAVAILABLE_REASON = (k) =>
    T.cell_display[k]["4.8"]?.plain || "no monthly-or-finer public series";

  if (!AVAILABLE[state.product]) {
    labEmptyState(root, "De-smoothing Lab", state.product, Object.keys(AVAILABLE),
      "monthly-or-finer series", (st) => window.tarkSetState(st), "desmooth", "data-dsprod");
    return;
  }
  const key = state.product;
  const data = AVAILABLE[key]();
  const rhoEst = lag1Autocorr(data.rets);
  const rhoOverride = state.rho !== "" && state.rho !== undefined
    && !Number.isNaN(parseFloat(state.rho))
    ? Math.min(0.9, Math.max(0, parseFloat(state.rho))) : null;
  const rhoUsed = rhoOverride ?? rhoEst;
  const [rec, rho] = desmoothGeltner(data.rets, rhoUsed);
  const volObs = annVol(data.rets, 12) * 100;
  const volDes = annVol(rec, 12) * 100;
  const obsPts = data.rets.map((r, i) => [data.dates[i + 1], r * 100]);
  const desPts = rec.map((r, i) => [data.dates[i + 2], r * 100]);

  const others = Object.keys(T.products)
    .filter((k) => !AVAILABLE[k])
    .map((k) => `<div class="nochart" style="margin-top:8px">
      <div class="k">${esc(T.products[k].fund_name)}</div>
      ${esc(UNAVAILABLE_REASON(k))}</div>`).join("");

  root.innerHTML = `
    ${data.price ? `<div class="banner red"><b>Market-price series.</b> De-smoothing
      corrects appraisal lag. Exchange prices carry no appraisal lag, so the
      correction below is shown for contrast only, not as a risk estimate.</div>` : ""}
    <div class="viewhead"><h1>De-smoothing Lab</h1>
      <div class="sub">Appraisal NAVs autocorrelate, and ${gloss("de-smoothing")}
        restores the volatility the pricing process hides. Available wherever a
        monthly-or-finer public series exists, currently
        ${Object.keys(AVAILABLE).map((k) =>
          `<a href="#" data-dsprod="${k}" style="${k === key ? "font-weight:700" : ""}">${esc(T.products[k].fund_name)}</a>`).join(" · ")}.</div></div>
    <div class="statrow">
      ${stat("ρ in use", rho.toFixed(3), rhoOverride !== null
        ? `USER OVERRIDE (estimated ρ is ${rhoEst.toFixed(3)})`
        : `estimated from n=${data.rets.length} monthly returns`)}
      ${stat("Observed ann. vol", volObs.toFixed(2) + "%")}
      ${stat("De-smoothed ann. vol", volDes.toFixed(2) + "%")}
      ${stat("Understatement", (volDes / volObs).toFixed(1) + "×", "risk hidden by smoothing")}
    </div>
    <div class="card" style="margin-bottom:12px">
      <div class="sliderrow"><label>ρ override
        ${rhoOverride !== null ? '<span class="chip illustrative">USER-CONFIGURED</span>' : ""}</label>
        <input type="range" id="rhoslider" min="0" max="0.9" step="0.01"
          value="${rhoUsed.toFixed(2)}" list="rhoticks">
        <span class="out num">${rhoUsed.toFixed(2)}</span></div>
      <datalist id="rhoticks"><option value="${rhoEst.toFixed(2)}" label="estimated"></option></datalist>
      <div class="cap">Estimated ρ (${rhoEst.toFixed(3)}) is marked on the track.
        Dragging recomputes the correction under YOUR assumption (labeled
        user-configured, never the record).
        ${rhoOverride !== null ? '<a href="#" id="rhoreset">reset to estimated</a>' : ""}
        <b>What de-smoothing can and cannot detect:</b> it corrects serial
        correlation from appraisal lag. It cannot reveal risks the appraisals
        never mark: stale-pricing bias, gating, or premium collapse.</div>
    </div>
    <div class="chartbox"><div id="dschart"></div>
      <div class="chartnote">${esc(data.basis)}. r*_t = (r_t − ρ·r_{t−1}) / (1 − ρ),
        recomputed live with the parity-tested port. Committed record:
        ${esc(data.committed)}.</div></div>
    <h2 style="margin:18px 0 4px">Where this diagnostic cannot run</h2>
    <div class="cap">Availability honesty: the reason renders where the chart
      would be.</div>
    ${others}`;

  root.querySelectorAll("[data-dsprod]").forEach((a) => a.addEventListener("click",
    (e) => { e.preventDefault();
             window.tarkSetState({ view: "desmooth", product: a.dataset.dsprod, rho: "" }); }));
  root.querySelector("#rhoslider").addEventListener("change", (e) =>
    window.tarkSetState({ rho: e.target.value }));
  root.querySelector("#rhoreset")?.addEventListener("click", (e) => {
    e.preventDefault(); window.tarkSetState({ rho: "" }); });

  lineChart(root.querySelector("#dschart"), {
    series: [
      { points: obsPts, label: "Observed monthly return (%)", color: "#593380", width: 1.5 },
      { points: desPts, label: "De-smoothed (Geltner AR1) (%)", color: "#92600d",
        width: 1.2, dash: "4,3" },
    ],
    height: 300, includeZero: true, yFormat: (v) => v.toFixed(1) + "%",
  });
}

/* ============================================================ COVERAGE */
export function viewCoverage(root) {
  const keys = Object.keys(T.products);
  const tax = T.taxonomy;
  const cc = T.crosscheck;

  root.innerHTML = `
    <div class="viewhead"><h1>Coverage & Provenance</h1>
      <div class="sub">${esc(tax.line)}</div></div>
    <div class="cardgrid g3" style="margin-bottom:14px">
      <div class="card" style="display:flex;gap:16px;align-items:center">
        <div id="taxdonut"></div>
        <div><h3>The record, whole</h3>
          <div class="cap">${Object.values(T.products).reduce((a, p) => a + Object.keys(p.cells).length, 0)}
            cells across ${Object.keys(T.products).length} products. Every cell is
            evidenced, computed, or carries a documented reason it cannot be
            public-sourced.</div></div></div>
      <div class="card"><h3 class="num" style="font-size:28px;color:var(--ok)">${cc.confirmed}/${cc.cells_checked}</h3>
        <div class="cap">${esc(cc.tile)} Source: ${esc(cc.source)}. An agent
          re-check is a machine re-check, not human verification.</div></div>
      <div class="card"><h3 class="num" style="font-size:28px;color:var(--plum-700)">${tax.counts.verified}</h3>
        <div class="cap">cells human-verified so far (T3). The verification
          interface is data/evidence/*.csv, and nothing is marked verified until
          a human signs the row. Honesty is load-bearing.</div></div>
    </div>
    <div class="cardgrid g3" id="prodrings"></div>
    <div class="legend" style="margin-top:10px">${kindLegend()}</div>
    <p class="cap footer-rule">Bundle generated ${esc(T.generated)} from the same
      data layer the validator gates. Every number on every surface is
      real-and-cited or labeled ILLUSTRATIVE.</p>`;

  donut(root.querySelector("#taxdonut"), {
    size: 150,
    segments: kindSegments(tax.counts),
    center: `${tax.counts.verified}`,
    centerSub: "human-verified (T3)",
  });

  const grid = root.querySelector("#prodrings");
  for (const k of keys) {
    const c = T.evidence_counts[k];
    const card = document.createElement("div");
    card.className = "card";
    card.style.display = "flex";
    card.style.gap = "14px";
    card.style.alignItems = "center";
    card.innerHTML = `<div data-r></div><div>
      <h3 style="font-size:13.5px">${esc(T.products[k].fund_name)}</h3>
      <div class="cap">${kindLine(c)}</div></div>`;
    card.querySelector("[data-r]").append(kindDonut(c, 72));
    grid.append(card);
  }
}

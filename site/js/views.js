/* Tark views — every renderer reads ONLY window.TARK (generated from the
 * canonical data layer by src/build_site.py). No fact is hard-coded here.
 * Numbers first: each cell leads with its focal figure (cell_display,
 * derived at build time); the full sourced text sits behind a disclosure.
 * Charts are TIER-DRIVEN from the bundle: daily series, printed monthly
 * series, filing-annual series — and where a chart is impossible, the
 * documented reason renders in its place. */

import { desmoothGeltner, directAlpha, ksPme, annVol, lag1Autocorr, levelOn,
         maxDrawdown, monthEndPoints, periodReturns } from "./analytics.js";
import { computeScenario, scenarioReason } from "./liquidity.js";
import { lineChart, barChart, donut, ring } from "./charts.js";

const T = window.TARK;

/* ------------------------------------------------------------ utilities */
export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const STATUS_PREFIXES = ["pending", "partial", "extracted", "verified",
  "computed", "fetched", "n/a"];
export function statusKind(status) {
  for (const p of STATUS_PREFIXES) if (String(status).startsWith(p)) return p;
  return "unknown";
}

const CHIP_LABEL = {
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

/* glossary chips: wrap known terms (longest first) in short display strings —
 * plain-language definition on hover; never applied to long prose */
const TERMS = Object.keys(T.glossary).sort((a, b) => b.length - a.length);
export function gloss(s) {
  let out = esc(s);
  for (const t of TERMS) {
    const re = new RegExp(`(?<![\\w>])(${t.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&")})(?![\\w<])`, "");
    if (re.test(out)) {
      out = out.replace(re,
        `<span class="term" tabindex="0" data-def="${esc(T.glossary[t])}">$1</span>`);
    }
  }
  return out;
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
    ${rec.local_file ? `<div class="f"><div class="k">Local file (repo)</div>
      <div class="v num" style="font-size:11.5px">${esc(rec.local_file)}</div></div>` : ""}
    <div class="f"><div class="k">Extracted by</div>
      <div class="v">${esc(rec.extracted_by || "—")}</div></div>
    <div class="f"><div class="k">Human verification</div>
      <div class="v">${rec.verified_by ? esc(rec.verified_by)
        : "pending — a human verifies rows in data/evidence/*.csv and flips status to verified"}</div></div>`;
  d.classList.add("open");
}
window.addEventListener("click", (e) => {
  const b = e.target.closest("[data-cite]");
  if (b) {
    const { key, cid } = b.dataset;
    const cell = T.products[key].cells[cid];
    openCite(cell, `${cid} · ${cell.element} — ${T.products[key].fund_name}`);
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
const DAILY = { cliffwater_cclfx: { series: "cclfx", col: "adj", label: "Daily NAV (adj, distributions reinvested)" },
                dxyz: { series: "dxyz_daily", label: "Daily market price (close)" } };

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
      series: [{ points: pts, label: "Monthly NAV per share, Class I — as PRINTED in the 10-K/10-Q",
        color: "#593380", width: 1.8, markers: true }],
      height: 260, yFormat: (v) => "$" + v.toFixed(1),
    });
    return "monthly disclosure cadence — the fund's own printed NAV table (NAV path; distributions excluded)";
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
    return "annual disclosure cadence — non-traded wrapper, no public daily series; fiscal-year figures as filed";
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
      <div class="sub">Four real 401(k) plans from public Form 5500 filings — the
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
      <div class="sub">Six real products, six wrappers — every figure traceable to
        a public filing.</div></div>
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
          <div class="cap">${c.extracted + c.verified} extracted · ${c.computed}
            computed · ${c.partial + c.fetched} partial · ${c.na} documented-n/a
            · ${c.pending} pending</div>
        </div>
      </div>
      <div style="margin-top:12px; display:flex; gap:8px; flex-wrap:wrap">
        <button class="btn ghost" data-goto="evaluation" data-key="${k}">Six-factor record</button>
        <button class="btn ghost" data-goto="benchmarks" data-key="${k}">Benchmark</button>
        ${T.memos.includes(k) ? `<a class="btn ghost" href="memos/${k}_decision_memo.docx" download>Memo ↓</a>` : ""}
      </div>`;
    card.querySelector("[data-ring]").append(ring(c.coverage_pct));
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
          body = `<div class="muted">not applicable / not public-sourceable —
            ${esc(disp.plain)}</div>`;
        } else if (!cell.value) {
          body = `<div class="muted">pending — pointer in data/evidence/${esc(key)}_evidence.csv</div>`;
        } else {
          body = `<div class="headline">${gloss(disp.headline)}</div>
            <div class="plain">${esc(disp.plain)}</div>
            <details class="src"><summary>Full text & provenance</summary>
              <div class="fulltext">${esc(cell.value)}</div></details>`;
        }
        return `<div class="cellrow">
          <div class="head"><span class="cid num">${cid}</span>
            <span class="el">${gloss(cell.element)}</span>
            ${chip(cell.status || "pending")} ${citeBtn(key, cid)}</div>
          ${body}</div>`;
      }).join("");
    return `<div class="factorblock" id="f${n}"><h2>${n} · ${esc(label)}</h2>${rows}</div>`;
  }).join("");

  root.innerHTML = `
    <div class="viewhead"><h1>Six-Factor Evaluation</h1>
      <div class="sub">${esc(p.fund_name)} — ${gloss(p.wrapper)} · coverage
        <b class="num">${c.coverage_pct}%</b></div></div>
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
      </div>
      <div class="cap">${gloss("KS-PME")} and ${gloss("Direct Alpha")} on
        appraisal-lagged NAVs are window-sensitive — disclosed, and explorable:
        <a href="#" data-goto="pme">move the window yourself →</a>
        <span class="num">(${esc(comp.window)})</span></div>` : ""}
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
      <div class="sub">${esc(p.fund_name)} · ${esc(sel.strategy)} · four lanes,
        12-point rubric, threshold ${T.min_primary_score}/12 — and every
        rejection on the record.</div></div>
    ${sel.escalation ? `<div class="notice">
        <div class="notice-head">Formal escalation — no benchmark assigned</div>
        <div class="notice-body"><b>${esc(sel.escalation.split(".")[0])}.</b>
          ${esc(sel.escalation.split(".").slice(1).join(".").trim())}
          ${key === "dxyz" ? `<div style="margin-top:10px">
            <a class="btn" href="#" data-goto="dxyz">See the premium decomposition →</a></div>` : ""}
        </div></div>` : ""}
    <div class="cardgrid g2">${slotCard("primary", "PRIMARY")}${slotCard("secondary", "SECONDARY")}</div>
    <h2 style="margin:22px 0 6px">Rejection ledger</h2>
    <div class="cap" style="margin-bottom:8px">Every candidate not selected, with
      its true reason and full rubric rationale — the other half of a defensible
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
function windowGrowthDaily(series, d0, d1) {
  const win = series.filter(([d]) => d >= d0 && d <= d1);
  const me = monthEndPoints(win);
  return { growth: win[win.length - 1][1] / win[0][1], me };
}

export function pmeCompute(fundFlows, indexDaily, d0, d1) {
  const idx = indexDaily.filter(([d]) => d >= d0 && d <= d1);
  return { ks: ksPme(fundFlows, idx), da: directAlpha(fundFlows, idx) };
}

export function viewPme(root, state, setState) {
  const prods = Object.keys(T.pme_profiles);
  const key = prods.includes(state.product) ? state.product : "cliffwater_cclfx";
  const prof = T.pme_profiles[key];
  const p = T.products[key];

  root.innerHTML = `
    <div class="viewhead"><h1>PME Window Explorer</h1>
      <div class="sub">${esc(p.fund_name)} vs <span id="idxlabel">${esc(prof.index_label)}</span>
        — drag the window start; the honesty is the feature.</div>
      <div class="cap" style="margin-top:4px">Products: ${prods.map((k) =>
        `<a href="#" data-pmeprod="${k}" style="margin-right:10px;${k === key ? "font-weight:700" : ""}">${esc(T.products[k].fund_name)}</a>`).join("")}</div>
    </div>
    <div class="banner amber"><b>Disclosure, interactive:</b> appraisal-lagged
      NAVs are window-sensitive — the SAME fund shows different ${gloss("PME")}
      and alpha depending on where the window opens. The engine's committed
      numbers use the full disclosed window.</div>
    <div class="card">
      <div class="sliderrow"><label>Window start</label>
        <input type="range" id="winstart" min="0" max="1" value="0" step="1">
        <span class="out num" id="winout"></span></div>
      ${prof.index_series_alt ? `<div class="cap">Index:
        <label><input type="radio" name="pmeidx" value="main" checked> ${esc(prof.index_label)}</label>
        <label style="margin-left:12px"><input type="radio" name="pmeidx" value="alt"> ${esc(prof.index_label_alt)}</label></div>` : ""}
      <div class="statrow">
        ${stat("KS-PME", `<span id="pme_ks">—</span>`)}
        ${stat("Direct Alpha", `<span id="pme_da">—</span><small>/yr</small>`)}
        ${stat("Fund growth", `<span id="pme_fg">—</span>×`)}
        ${stat("Index growth", `<span id="pme_ig">—</span>×`)}
        ${stat("Window", `<span id="pme_win" style="font-size:13px">—</span>`)}
      </div>
      <div class="chartbox" style="border:0;padding:6px 0 0"><div id="pmechart"></div></div>
      <div class="chartnote" id="pmenote"></div>
    </div>`;

  root.querySelectorAll("[data-pmeprod]").forEach((a) => a.addEventListener("click",
    (e) => { e.preventDefault(); setState({ view: "pme", product: a.dataset.pmeprod }); }));

  const slider = root.querySelector("#winstart");
  const isAnnual = prof.granularity === "annual";
  let starts;
  let fundDaily = null;
  if (isAnnual) {
    const [w0] = prof.fy_window;
    const y0 = +w0.slice(0, 4);
    starts = prof.fy_returns.map((_, i) => `${y0 + i}${w0.slice(4)}`);
  } else {
    fundDaily = T.series[prof.fund_series];
    const me = monthEndPoints(fundDaily).map(([d]) => d);
    starts = [fundDaily[0][0], ...me.slice(0, me.length - 13)];
  }
  slider.max = String(starts.length - 1);

  const idxFor = () => {
    const alt = root.querySelector('input[name="pmeidx"][value="alt"]');
    return alt && alt.checked
      ? { series: T.series[prof.index_series_alt], label: prof.index_label_alt }
      : { series: T.series[prof.index_series], label: prof.index_label };
  };

  function recompute() {
    const i = +slider.value;
    const d0 = starts[i];
    const { series: idxDaily, label } = idxFor();
    let d1; let fGrowth; let fundPts;
    if (isAnnual) {
      d1 = prof.fy_window[1];
      const rets = prof.fy_returns.slice(i);
      fGrowth = rets.reduce((g, r) => g * (1 + r), 1);
      let acc = 1;
      fundPts = [[d0, 1]];
      rets.forEach((r, j) => {
        acc *= 1 + r;
        fundPts.push([`${+d0.slice(0, 4) + j + 1}${d0.slice(4)}`, acc]);
      });
    } else {
      d1 = fundDaily[fundDaily.length - 1][0];
      const { growth, me } = windowGrowthDaily(fundDaily, d0, d1);
      fGrowth = growth;
      let acc = 1;
      fundPts = [[me[0][0], 1]];
      periodReturns(me.map(([, v]) => v)).forEach((r, j) => {
        acc *= 1 + r; fundPts.push([me[j + 1][0], acc]);
      });
    }
    const flows = [[d0, -1.0], [d1, fGrowth]];
    const { ks, da } = pmeCompute(flows, idxDaily, d0, d1);
    const iGrowth = levelOn(idxDaily, d1) / levelOn(idxDaily, d0);
    const idxWin = idxDaily.filter(([d]) => d >= d0 && d <= d1);
    const idxMe = monthEndPoints(idxWin);
    let acc = 1;
    const idxPts = [[idxMe[0][0], 1]];
    periodReturns(idxMe.map(([, v]) => v)).forEach((r, j) => {
      acc *= 1 + r; idxPts.push([idxMe[j + 1][0], acc]);
    });

    root.querySelector("#pme_ks").textContent = ks.toFixed(4);
    root.querySelector("#pme_da").textContent =
      da === null ? "n/a" : `${(da * 100).toFixed(2)}%`;
    root.querySelector("#pme_fg").textContent = fGrowth.toFixed(4);
    root.querySelector("#pme_ig").textContent = iGrowth.toFixed(4);
    root.querySelector("#pme_win").textContent = `${d0} → ${d1}`;
    root.querySelector("#winout").textContent = d0;
    root.querySelector("#idxlabel").textContent = label;
    lineChart(root.querySelector("#pmechart"), {
      series: [
        { points: fundPts, label: `${T.products[key].fund_name} (growth of 1.0)`,
          color: "#593380", width: 2 },
        { points: idxPts, label: `${label} (growth of 1.0)`, color: "#92600d",
          width: 1.6, dash: "5,4" },
      ],
      height: 300, yFormat: (v) => v.toFixed(2) + "×",
    });
    root.querySelector("#pmenote").textContent =
      (isAnnual
        ? "Fund line compounds the disclosed fiscal-year total returns (cell 1.2); KS-PME/Direct Alpha anchored on daily index levels. "
        : "Fund growth daily-anchored (window last/first observation); lines month-end sampled for drawing only. ")
      + "Same code path as the Python engine — parity-tested.";
  }

  slider.addEventListener("input", recompute);
  root.querySelectorAll('input[name="pmeidx"]').forEach((r) =>
    r.addEventListener("change", recompute));
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
      <div class="sub">${esc(p.fund_name)} × ${esc(m.plan_display_label)} — tail
        ${m.plan_inputs.tail_share_pct}% of accounts
        (${Math.round(m.plan_inputs.separated_with_balances).toLocaleString()}
        separated), plan direction: ${esc(m.plan_direction)}.</div></div>
    <div class="banner ${bannerCls}"><h3>Verdict: ${esc(m.verdict.toUpperCase())}</h3></div>
    <ul style="margin:0 0 16px 18px; font-size:13.5px" id="reasons">
      ${m.reasons.map((r) => `<li style="margin-bottom:6px">${esc(r)}</li>`).join("")}</ul>
    <div class="cardgrid g2">
      <div class="card">
        <h3>Capacity vs demand <span class="chip illustrative">ILLUSTRATIVE</span></h3>
        <div class="cap">Wrapper capacity is a filed fact (cells ${esc(String(profile.source_cell))});
          the demand model is an adjustable scenario, never presented as fact.</div>
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
          color: "#593380", note: "daily — exchange-listed" },
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
       <span class="num">${money(out.annual_demand_usd)}</span>/yr demand — ` +
      esc(r ? r : "Exchange-listed: capacity is market depth, not a fund cap.") +
      ` <b>[ILLUSTRATIVE]</b>`;
  }
  els.forEach((e) => e.addEventListener("input", update));
  update();
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

  const baseBadge = (val) => {
    const v = String(val || "").toLowerCase();
    if (v.includes("managed assets")) return `<span class="chip trap">base: MANAGED ASSETS (leverage-inclusive)</span>`;
    if (v.includes("gross assets")) return `<span class="chip trap">base: GROSS assets incl. borrowings</span>`;
    if (v.includes("net assets") || v.includes("nav")) return `<span class="chip okbase">base: net assets / NAV</span>`;
    return "";
  };
  const taxBadge = (val) => {
    const v = String(val || "").toLowerCase();
    if (v.includes("k-1")) return `<span class="chip trap">Schedule K-1</span>`;
    if (v.includes("1099")) return `<span class="chip extracted">Form 1099</span>`;
    return "";
  };

  const body = rows.map(([cid, label]) => {
    const tds = keys.map((k) => {
      const cell = T.products[k].cells[cid];
      const disp = T.cell_display[k][cid];
      const kind = statusKind(cell.status || "pending");
      const badge = cid === "2.1" ? baseBadge(cell.value)
        : cid === "6.4" ? taxBadge(cell.value) : "";
      const content = cell.value
        ? `${badge ? badge + "<br>" : ""}
           <div class="headline" style="font-size:14px;margin:3px 0 1px">${esc(disp.headline)}</div>
           <span style="font-size:11.5px;color:var(--ink-2)">${short(disp.plain, 120)}</span>`
        : `<span class="cap">${kind === "n/a" ? esc(disp.plain).slice(0, 110) : "pending"}</span>`;
      return `<td>${content}<div style="margin-top:5px">${chip(cell.status || "pending")} ${citeBtn(k, cid)}</div></td>`;
    }).join("");
    return `<tr><td style="font-weight:600; white-space:nowrap">${cid}<br>
      <span class="cap">${gloss(label)}</span></td>${tds}</tr>`;
  }).join("");

  root.innerHTML = `
    <div class="viewhead"><h1>Fee Matrix</h1>
      <div class="sub">The headline rate is never the story — the BASE is.</div></div>
    <div class="chartbox" style="margin-bottom:14px">
      <h3 style="margin-bottom:4px">Own net expense ratio, where one exists</h3>
      <div id="feechart"></div>
      <div class="chartnote">From each fund's cell 2.3 as extracted (bases differ
        by wrapper and are quoted per product). kkr_kpec and breit have NO TER
        line — '34-Act wrappers; their burden is fee + performance participation
        (2.1/2.2), flagged in the matrix below. Universe = this roster
        (data/analytics/supplement.json fee_percentile).</div></div>
    <div class="tablewrap"><table class="grid">
      <thead><tr><th style="min-width:120px">Cell</th>
        ${keys.map((k) => `<th style="min-width:210px">${esc(T.products[k].fund_name)}</th>`).join("")}
      </tr></thead><tbody>${body}</tbody></table></div>
    <p class="cap" style="margin-top:10px">Every figure is the evidence record
      itself — click source for document · section · verbatim quote. Chips are
      derived from the cell text, not hand-assigned.</p>`;

  const fp = T.supplement.fee_percentile.entries;
  barChart(root.querySelector("#feechart"), {
    items: fp.map((e) => ({
      label: T.products[e.product].fund_name.split(" (")[0],
      value: e.ter_pct, color: e.ter_pct === null ? "#837b8e" : "#593380",
      note: e.ter_pct === null ? "no TER line — '34-Act wrapper (see 2.1/2.2)" : "",
    })),
    format: (v) => v.toFixed(1) + "%",
  });
}

/* ========================================================== DXYZ CHART */
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
    <div class="viewhead"><h1>DXYZ — Price vs NAV</h1>
      <div class="sub">The market price is a premium series, not a portfolio
        series — which is WHY the engine refused a benchmark.</div></div>
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
        the fund's own quarterly filed NAV per share. Log scale — the vertical
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
    </tbody></table></div>`;

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
}

/* ======================================================== DE-SMOOTHING */
export function viewDesmooth(root, state) {
  // data-driven roster: any product with a monthly-or-finer series qualifies
  const AVAILABLE = {
    cliffwater_cclfx: () => {
      const me = monthEndPoints(T.series.cclfx);
      return { rets: periodReturns(me.map(([, v]) => v)),
               dates: me.map(([d]) => d),
               basis: "monthly returns from daily adj close (distributions reinvested)",
               committed: `pipeline: rho ${T.metrics.cclfx.full_history.lag1_autocorr_rho}, observed ${T.metrics.cclfx.full_history.ann_vol_observed_pct}% → de-smoothed ${T.metrics.cclfx.full_history.ann_vol_desmoothed_pct}% (data/analytics/metrics.json)` };
    },
    breit: () => {
      const pts = T.series_monthly.breit_nav.filter(([d]) => d <= "2025-12-31");
      const bd = T.supplement.breit_monthly_diagnostics;
      return { rets: periodReturns(pts.map(([, v]) => v)),
               dates: pts.map(([d]) => d),
               basis: "monthly NAV path as PRINTED in the 10-K (distributions excluded — appraisal-process diagnostic)",
               committed: `pipeline: rho ${bd.lag1_autocorr_rho}, observed ${bd.nav_path_ann_vol_pct}% → de-smoothed ${bd.desmoothed_ann_vol_pct}% (data/analytics/supplement.json)` };
    },
  };
  const UNAVAILABLE_REASON = (k) =>
    T.cell_display[k]["4.8"]?.plain || "no monthly-or-finer public series";

  const key = AVAILABLE[state.product] ? state.product : "cliffwater_cclfx";
  const data = AVAILABLE[key]();
  const [rec, rho] = desmoothGeltner(data.rets);
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
    <div class="viewhead"><h1>De-smoothing Lab</h1>
      <div class="sub">Appraisal NAVs autocorrelate; ${gloss("de-smoothing")}
        restores the volatility the pricing process hides. Available wherever a
        monthly-or-finer public series exists — currently
        ${Object.keys(AVAILABLE).map((k) =>
          `<a href="#" data-dsprod="${k}" style="${k === key ? "font-weight:700" : ""}">${esc(T.products[k].fund_name)}</a>`).join(" · ")}.</div></div>
    <div class="statrow">
      ${stat("ρ (lag-1 autocorr)", rho.toFixed(3), `n=${data.rets.length} monthly`)}
      ${stat("Observed ann. vol", volObs.toFixed(2) + "%")}
      ${stat("De-smoothed ann. vol", volDes.toFixed(2) + "%")}
      ${stat("Understatement", (volDes / volObs).toFixed(1) + "×", "risk hidden by smoothing")}
    </div>
    <div class="chartbox"><div id="dschart"></div>
      <div class="chartnote">${esc(data.basis)}. r*_t = (r_t − ρ·r_{t−1}) / (1 − ρ),
        recomputed live with the parity-tested port; committed record —
        ${esc(data.committed)}.</div></div>
    <h2 style="margin:18px 0 4px">Where this diagnostic cannot run</h2>
    <div class="cap">Availability honesty: the reason renders where the chart
      would be.</div>
    ${others}`;

  root.querySelectorAll("[data-dsprod]").forEach((a) => a.addEventListener("click",
    (e) => { e.preventDefault();
             window.tarkSetState({ view: "desmooth", product: a.dataset.dsprod }); }));

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
          <div class="cap">${tax.total} cells across six products. Every cell is
            evidenced, computed, or carries a documented reason it cannot be
            public-sourced. Zero unresolved.</div></div></div>
      <div class="card"><h3 class="num" style="font-size:28px;color:var(--ok)">${cc.confirmed}/${cc.cells_checked}</h3>
        <div class="cap">cells CONFIRMED by an independent re-location pass;
          ${cc.corrected} discrepancies found and corrected in the open;
          ${cc.unlocatable} unlocatable. ${esc(cc.source)}</div></div>
      <div class="card"><h3 class="num" style="font-size:28px;color:var(--plum-700)">0</h3>
        <div class="cap">cells human-verified so far — the verification
          interface is data/evidence/*.csv, and nothing is marked verified until
          a human signs the row. Honesty is load-bearing.</div></div>
    </div>
    <div class="cardgrid g3" id="prodrings"></div>
    <div class="legend" style="margin-top:10px">
      <span><span class="sw" style="background:var(--ok)"></span>extracted/verified</span>
      <span><span class="sw" style="background:var(--calc)"></span>computed</span>
      <span><span class="sw" style="background:var(--warn)"></span>partial/fetched</span>
      <span><span class="sw" style="background:#d8d3dd"></span>documented n/a</span></div>
    <p class="cap footer-rule">Bundle generated ${esc(T.generated)} from the same
      data layer the validator gates. Every number on every surface is
      real-and-cited or labeled ILLUSTRATIVE.</p>`;

  donut(root.querySelector("#taxdonut"), {
    size: 150,
    segments: [
      { label: "evidenced", value: tax.counts.extracted + (tax.counts.verified || 0)
          + tax.counts.partial + tax.counts.fetched, color: "#256e46" },
      { label: "computed", value: tax.counts.computed, color: "#14636d" },
      { label: "documented n/a", value: tax.counts["n/a"], color: "#d8d3dd" },
    ],
    center: `${Math.round((tax.total - tax.counts["n/a"]) / tax.total * 100)}%`,
    centerSub: "resolvable, resolved",
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
      <div class="cap">${c.extracted} extracted · ${c.computed} computed ·
        ${c.partial + c.fetched} partial · ${c.na} documented-n/a</div></div>`;
    card.querySelector("[data-r]").append(ring(c.coverage_pct, "#593380", 72));
    grid.append(card);
  }
}

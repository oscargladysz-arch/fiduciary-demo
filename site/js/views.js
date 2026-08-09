/* Tark views — every renderer reads ONLY window.TARK (generated from the
 * canonical data layer by src/build_site.py). No fact is hard-coded here:
 * numbers on screen are bundle values or live recomputations of them, and
 * every citation panel is the cell's own provenance record. */

import { cumulativeGrowth, desmoothGeltner, directAlpha, ksPme, annVol,
         monthEndPoints, periodReturns, stdev } from "./analytics.js";
import { computeScenario, scenarioReason } from "./liquidity.js";
import { lineChart } from "./charts.js";

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
  computed: "computed (pipeline)", partial: "partial", fetched: "series fetched",
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
        : "pending — a human (CF2) verifies rows in data/evidence/*.csv and flips status to verified"}</div></div>`;
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
  return `<button class="citebtn" data-cite data-key="${esc(key)}" data-cid="${esc(cid)}">cite</button>`;
}

const short = (s, n = 170) => {
  s = String(s ?? "");
  return s.length > n ? esc(s.slice(0, n).trimEnd()) + "…" : esc(s);
};

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
        ${stat("Net assets (EOY)", money(f.net_assets_eoy))}
        ${stat("Accounts", Math.round(pt.with_account_balances).toLocaleString())}
        ${stat("Avg balance", "$" + d.avg_balance_per_account.toLocaleString())}
        ${stat("Liquidity tail", tail.toFixed(1) + "%",
               `${Math.round(pt.separated_deferred_vested).toLocaleString()} separated w/ balances`)}
      </div>
      <div class="cap">${esc(p.plan_characteristics.codes_decoded)}</div>
      <div class="cap" style="margin-top:6px">Plan year ${esc(p.plan_year)} ·
        ${esc(p.source.publisher)} · pulled ${esc(p.source.pulled)}</div>
    </div>`;
  }).join("");
  root.innerHTML = `
    <div class="viewhead"><h1>Reference Plans</h1>
      <div class="sub">Four real 401(k) plans from public DOL Form 5500 filings —
        anonymized display labels by project rule; the selected plan drives the
        Liquidity Match view.</div></div>
    <div class="cardgrid g2">${cards}</div>
    <p class="cap footer-rule">${esc(T.plans[state.plan].anonymization_rule)}</p>`;
  root.querySelectorAll("[data-plan]").forEach((c) =>
    c.addEventListener("click", () => setState({ plan: c.dataset.plan })));
}

/* ============================================================== ROSTER */
export function viewRoster(root, state, setState) {
  const cards = Object.entries(T.products).map(([k, p]) => {
    const c = T.evidence_counts[k];
    const seeded = c.extracted + c.verified + c.computed;
    const applicable = seeded + c.partial + c.fetched + c.pending;
    const segs = [
      ["extracted", (c.extracted + c.verified) / applicable * 100],
      ["computed", c.computed / applicable * 100],
      ["partial", (c.partial + c.fetched) / applicable * 100],
    ].map(([cls, w]) => `<div class="seg ${cls}" style="width:${w}%"></div>`).join("");
    return `<div class="card">
      <h3>${esc(p.fund_name)}</h3>
      <div style="margin:6px 0 8px"><span class="chip wrapper">${esc(p.wrapper)}</span>
        <span class="cap"> CIK ${esc(p.cik)}</span></div>
      <div class="covbar">${segs}</div>
      <div class="cap" style="margin-top:5px">evidence coverage
        <b class="num">${c.coverage_pct}%</b> ·
        ${seeded} seeded · ${c.partial + c.fetched} partial ·
        ${c.pending} pending · ${c.na} n/a</div>
      ${p.identity_note || p.note ? `<div class="cap" style="margin-top:8px">${short(p.identity_note || p.note, 150)}</div>` : ""}
      <div style="margin-top:12px; display:flex; gap:8px">
        <button class="btn ghost" data-goto="evaluation" data-key="${k}">Six-factor record</button>
        <button class="btn ghost" data-goto="benchmarks" data-key="${k}">Benchmark</button>
        ${T.memos.includes(k) ? `<a class="btn ghost" href="memos/${k}_decision_memo.docx" download>Memo ↓</a>` : ""}
      </div>
    </div>`;
  }).join("");
  root.innerHTML = `
    <div class="viewhead"><h1>Candidate Roster</h1>
      <div class="sub">Six real products, six wrappers — every cell traceable to a
        public filing via data/evidence/. Coverage counts seeded + partial cells
        over all applicable cells.</div></div>
    <div class="cardgrid g2">${cards}</div>`;
  root.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click",
    () => setState({ view: b.dataset.goto, product: b.dataset.key })));
}

/* ========================================================== EVALUATION */
export function viewEvaluation(root, state) {
  const key = state.product;
  const p = T.products[key];
  const c = T.evidence_counts[key];
  const blocks = Object.entries(T.factors).map(([n, label]) => {
    const rows = Object.keys(T.cell_registry)
      .filter((cid) => cid.split(".")[0] === n)
      .map((cid) => {
        const cell = p.cells[cid];
        const k = statusKind(cell.status || "pending");
        let body = "";
        if (cell.value) {
          body = `<div class="val">${esc(cell.value)}</div>`;
        } else if (k === "n/a") {
          body = `<div class="muted">Not applicable — ${esc(String(cell.status).slice(6))}</div>`;
        } else {
          body = `<div class="muted">Pending extraction — pointer in
            data/evidence/${esc(key)}_evidence.csv</div>`;
        }
        return `<div class="cellrow">
          <div class="head"><span class="cid num">${cid}</span>
            <span class="el">${esc(cell.element)}</span>
            ${chip(cell.status || "pending")} ${citeBtn(key, cid)}</div>
          ${body}</div>`;
      }).join("");
    return `<div class="factorblock"><h2>${n} · ${esc(label)}</h2>${rows}</div>`;
  }).join("");
  root.innerHTML = `
    <div class="viewhead"><h1>Six-Factor Evaluation</h1>
      <div class="sub">${esc(p.fund_name)} — ${esc(p.wrapper)} · CIK ${esc(p.cik)}
        · evidence coverage <b class="num">${c.coverage_pct}%</b></div>
      <div class="cap" style="margin-top:4px">${esc(T.rule_caption)}</div></div>
    ${blocks}`;
}

/* ========================================================== BENCHMARKS */
export function viewBenchmarks(root, state, setState) {
  const key = state.product;
  const p = T.products[key];
  const sel = T.benchmarks[key];
  if (!sel) {
    root.innerHTML = `<div class="viewhead"><h1>Benchmark Selection</h1>
      <div class="sub">${esc(p.fund_name)}</div></div>
      <div class="banner amber"><h3>Engine profile pending</h3>
      No selection has been generated for this product yet (10-K wrappers
      ${esc(key)} — extraction depth first; see the evidence CSV pointers).</div>`;
    return;
  }
  const slotCard = (slot, badge) => {
    const s = sel[slot];
    if (!s) return "";
    const comp = s.comparison;
    return `<div class="card">
      <div class="cap" style="letter-spacing:.1em;font-weight:700">${badge}</div>
      <h3>${esc(s.candidate)}</h3>
      <div class="num" style="font-size:15px;margin-top:2px">${s.score}/${s.max}</div>
      <div class="scorebar"><div class="fill" style="width:${s.score / s.max * 100}%"></div></div>
      ${comp ? `<div class="statrow">
        ${stat("Fund (ann.)", `${comp.fund_ann_pct}%<small>/yr</small>`)}
        ${stat("Benchmark (ann.)", `${comp.index_ann_pct}%<small>/yr</small>`)}
        ${stat("KS-PME", comp.ks_pme)}
        ${stat("Direct Alpha", `${comp.direct_alpha_pct}%<small>/yr</small>`)}
      </div>
      <div class="cap">Window ${esc(comp.window)}. PME and alpha on appraisal-lagged
        NAVs are window-sensitive and can be smoothing-flattered — disclosed per
        methodology §3. <a href="#" data-goto="pme">Explore window sensitivity →</a></div>` : ""}
      <details style="margin-top:10px"><summary class="cap" style="cursor:pointer">Scoring rationale</summary>
        <ul style="margin:8px 0 0 18px; font-size:12.5px">
          ${s.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul></details>
    </div>`;
  };

  const rejRows = sel.rejected.map((r) => `<tr>
      <td>${esc(r.candidate)}</td><td class="num">${esc(r.lane)}</td>
      <td class="num">${r.score}/${r.max}</td>
      <td>${esc(r.rejection)}
        <div class="cap" style="margin-top:5px">${r.reasons.map(esc).join(" · ")}</div>
      </td></tr>`).join("");

  root.innerHTML = `
    <div class="viewhead"><h1>Benchmark Selection</h1>
      <div class="sub">${esc(p.fund_name)} · strategy: ${esc(sel.strategy)} ·
        engine inputs from cells ${sel.source_cells.map(esc).join(", ")}</div>
      <div class="cap" style="margin-top:4px">Rubric: strategy match 3 ·
        risk/liquidity 3 · investability 2 · data quality 2 · provider
        independence 2 — primary threshold ${T.min_primary_score}/12.</div></div>
    ${sel.escalation ? `<div class="banner red"><h3>ESCALATION</h3>
        ${esc(sel.escalation)}
        ${key === "dxyz" ? `<div style="margin-top:8px">
          <a class="btn" href="#" data-goto="dxyz">See the premium/discount decomposition →</a></div>` : ""}
      </div>` : ""}
    <div class="cardgrid g2">${slotCard("primary", "PRIMARY")}${slotCard("secondary", "SECONDARY")}</div>
    <h2 style="margin:20px 0 8px">Rejection log</h2>
    <div class="cap" style="margin-bottom:8px">Every candidate not selected, with
      its true reason — the other half of a defensible record.</div>
    <div class="tablewrap"><table class="grid" id="rejtable">
      <thead><tr><th class="sortable" data-col="0">Candidate</th>
        <th class="sortable" data-col="1">Lane</th>
        <th class="sortable" data-col="2">Score</th><th>Reason</th></tr></thead>
      <tbody>${rejRows}</tbody></table></div>
    ${T.memos.includes(key) ? `<div style="margin-top:16px">
      <a class="btn" href="memos/${key}_decision_memo.docx" download>Download decision memo (.docx)</a></div>` : ""}`;

  root.querySelectorAll("[data-goto]").forEach((a) => a.addEventListener("click",
    (e) => { e.preventDefault(); setState({ view: a.dataset.goto }); }));
  // sortable rejection log
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

/* ============================================================ helpers for PME */
function windowGrowthMonthly(series, d0, d1) {
  const win = series.filter(([d]) => d >= d0 && d <= d1);
  const me = monthEndPoints(win);
  return { growth: cumulativeGrowth(periodReturns(me.map(([, v]) => v))), me };
}

export function pmeCompute(fundFlows, indexDaily, d0, d1) {
  const idx = indexDaily.filter(([d]) => d >= d0 && d <= d1);
  return {
    ks: ksPme(fundFlows, idx),
    da: directAlpha(fundFlows, idx),
  };
}

/* ============================================================== PME LAB */
export function viewPme(root, state, setState) {
  const prods = Object.keys(T.pme_profiles);
  const key = prods.includes(state.product) ? state.product : "cliffwater_cclfx";
  const prof = T.pme_profiles[key];
  const p = T.products[key];

  root.innerHTML = `
    <div class="viewhead"><h1>PME Window-Sensitivity Explorer</h1>
      <div class="sub">${esc(p.fund_name)} vs <span id="idxlabel">${esc(prof.index_label)}</span>
        — move the comparison-window start and watch KS-PME and Direct Alpha move.</div>
      <div class="cap" style="margin-top:4px">Products: ${prods.map((k) =>
        `<a href="#" data-pmeprod="${k}" style="margin-right:10px;${k === key ? "font-weight:700" : ""}">${esc(T.products[k].fund_name)}</a>`).join("")}</div>
    </div>
    <div class="banner amber"><b>Honest caption:</b> appraisal-lagged NAVs are
      window-sensitive — the SAME fund shows different PME and alpha depending on
      where the window opens (a window opening at a public-market peak flatters
      the fund; smoothing lets lagged NAVs sail through drawdowns). This explorer
      is the methodology's §3 disclosure made interactive; the engine's committed
      numbers use the full disclosed window.</div>
    <div class="card">
      <div class="sliderrow"><label id="winlabel">Window start</label>
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
    // fiscal-year boundaries only — honest granularity for an annual series;
    // each start leaves at least one full fiscal year in the window
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
      fGrowth = cumulativeGrowth(rets);
      let acc = 1;
      fundPts = [[d0, 1]];
      rets.forEach((r, j) => {
        acc *= 1 + r;
        fundPts.push([`${+d0.slice(0, 4) + j + 1}${d0.slice(4)}`, acc]);
      });
    } else {
      d1 = fundDaily[fundDaily.length - 1][0];
      const { growth, me } = windowGrowthMonthly(fundDaily, d0, d1);
      fGrowth = growth;
      let acc = 1;
      fundPts = [[me[0][0], 1]];
      periodReturns(me.map(([, v]) => v)).forEach((r, j) => {
        acc *= 1 + r; fundPts.push([me[j + 1][0], acc]);
      });
    }
    const flows = [[d0, -1.0], [d1, fGrowth]];
    const { ks, da } = pmeCompute(flows, idxDaily, d0, d1);
    const idxWin = idxDaily.filter(([d]) => d >= d0 && d <= d1);
    const idxMe = monthEndPoints(idxWin);
    const iGrowth = cumulativeGrowth(periodReturns(idxMe.map(([, v]) => v)));
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
          color: "#1f4e5f", width: 2 },
        { points: idxPts, label: `${label} (growth of 1.0)`, color: "#b06e1c",
          width: 1.6, dash: "5,4" },
      ],
      height: 300, yFormat: (v) => v.toFixed(2) + "×",
    });
    root.querySelector("#pmenote").textContent =
      (isAnnual
        ? "Fund line compounds the disclosed fiscal-year total returns (cell 1.2); index from the bundled daily series, month-end sampled. "
        : "Fund and index lines are month-end sampled from bundled daily series (adj close, distributions reinvested). ")
      + "Same KS-PME / Direct Alpha code path as the Python engine (parity-tested).";
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
    root.innerHTML = `<h1>Liquidity Match</h1><div class="banner amber">
      Match pending for this plan × product.</div>`;
    return;
  }
  const bannerCls = m.verdict.startsWith("aligned") ? "green"
    : m.verdict === "conditional-weak" ? "red" : "amber";
  const sc = m.scenario;
  const profile = m.wrapper_facts;

  root.innerHTML = `
    <div class="viewhead"><h1>Product-to-Plan Liquidity Match</h1>
      <div class="sub">${esc(p.fund_name)} × ${esc(m.plan_display_label)}</div>
      <div class="cap" style="margin-top:4px">Plan liquidity tail
        ${m.plan_inputs.tail_share_pct}% of accounts
        (${Math.round(m.plan_inputs.separated_with_balances).toLocaleString()}
        separated participants with balances) · plan direction: ${esc(m.plan_direction)}
        (from the plan's own Form 5500 codes).</div></div>
    <div class="banner ${bannerCls}"><h3>Verdict: ${esc(m.verdict.toUpperCase())}</h3></div>
    <ul style="margin:0 0 16px 18px; font-size:13.5px" id="reasons">
      ${m.reasons.map((r) => `<li style="margin-bottom:6px">${esc(r)}</li>`).join("")}</ul>
    <div class="cardgrid g2">
      <div class="card"><h3>Wrapper facts <span class="cap">(cells ${esc(String(profile.source_cell))})</span></h3>
        <table class="grid" style="border:0;margin-top:8px">
          <tr><td>Kind</td><td class="num">${esc(profile.kind)}</td></tr>
          <tr><td>Dealing cadence</td><td class="num">${profile.cadence_per_year}×/year</td></tr>
          <tr><td>Cap</td><td class="num">${profile.cap_pct === null ? "—" : profile.cap_pct + "%"} of ${esc(profile.cap_base)}</td></tr>
          <tr><td>Exchange-listed</td><td class="num">${profile.exchange ? "yes" : "no"}</td></tr>
          <tr><td>Gating history</td><td class="num">${profile.gate_history ? "YES (3.3)" : "none identified"}</td></tr>
          <tr><td>Early repurchase</td><td>${esc(profile.early_fee)}</td></tr>
        </table>
        <div class="cap" style="margin-top:8px">Citations: ${m.citations.map(esc).join(" · ")}</div>
      </div>
      <div class="card">
        <h3>Scenario <span class="chip illustrative">ILLUSTRATIVE</span></h3>
        <div class="cap">Adjustable parameters, not facts. Demand model: plan
          allocates X% of assets; annual liquidity demand = separated-tail
          turnover + active turnover on the position.</div>
        <div class="sliderrow"><label>Plan allocation to product</label>
          <input type="range" id="s_alloc" min="1" max="10" step="0.5"
            value="${sc.allocation_pct_of_plan}"><span class="out" id="o_alloc"></span></div>
        <div class="sliderrow"><label>Tail annual turnover</label>
          <input type="range" id="s_tail" min="5" max="50" step="1"
            value="${sc.tail_annual_turnover_pct}"><span class="out" id="o_tail"></span></div>
        <div class="sliderrow"><label>Active annual turnover</label>
          <input type="range" id="s_act" min="1" max="15" step="0.5"
            value="${sc.active_annual_turnover_pct}"><span class="out" id="o_act"></span></div>
        <div class="statrow">
          ${stat("Position", `<span id="o_pos">—</span>`)}
          ${stat("Annual demand", `<span id="o_dem">—</span>`)}
          ${stat("Demand % of position", `<span id="o_dpct">—</span>`)}
          ${stat("Wrapper capacity", `<span id="o_cap">—</span>`)}
        </div>
        <div class="cap" id="o_reason" style="margin-top:4px"></div>
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
    root.querySelector("#o_pos").textContent = money(out.plan_allocation_usd);
    root.querySelector("#o_dem").textContent = money(out.annual_demand_usd);
    root.querySelector("#o_dpct").textContent = out.demand_pct_of_position.toFixed(1) + "%/yr";
    root.querySelector("#o_cap").textContent = out.annual_wrapper_capacity_pct === null
      ? "daily (exchange)" : out.annual_wrapper_capacity_pct.toFixed(0) + "%/yr";
    const r = scenarioReason(out);
    root.querySelector("#o_reason").textContent = r
      ? r + " [ILLUSTRATIVE scenario output]"
      : "Exchange-listed: capacity is market depth, not a fund cap. [ILLUSTRATIVE]";
  }
  els.forEach((e) => e.addEventListener("input", update));
  update();
}

/* ================================================================ FEES */
export function viewFees(root) {
  const rows = [
    ["2.1", "Management fee (rate AND base)"],
    ["2.2", "Incentive fee"],
    ["2.3", "Total expense ratio"],
    ["2.4", "AFFE"],
    ["2.6", "Loads & servicing"],
    ["2.7", "Early repurchase"],
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
      const kind = statusKind(cell.status || "pending");
      const badge = cid === "2.1" ? baseBadge(cell.value)
        : cid === "6.4" ? taxBadge(cell.value) : "";
      const content = cell.value
        ? `${badge ? badge + "<br>" : ""}<span style="font-size:12px">${short(cell.value, 210)}</span>`
        : `<span class="cap">${kind === "n/a" ? "n/a" : "pending"}</span>`;
      return `<td>${content}<div style="margin-top:5px">${chip(cell.status || "pending")} ${citeBtn(k, cid)}</div></td>`;
    }).join("");
    return `<tr><td style="font-weight:650; white-space:nowrap">${cid}<br>
      <span class="cap">${esc(label)}</span></td>${tds}</tr>`;
  }).join("");

  root.innerHTML = `
    <div class="viewhead"><h1>Fee Comparison Matrix</h1>
      <div class="sub">All six products side by side — the headline rate is never
        the story; the BASE is. Red chips flag leverage-inclusive fee bases and
        K-1 tax reporting (recordkeeper-hostile).</div></div>
    <div class="tablewrap"><table class="grid">
      <thead><tr><th style="min-width:120px">Cell</th>
        ${keys.map((k) => `<th style="min-width:220px">${esc(T.products[k].fund_name)}</th>`).join("")}
      </tr></thead><tbody>${body}</tbody></table></div>
    <p class="cap" style="margin-top:10px">Every cell text is the evidence record
      itself (click cite for document · section · verbatim quote). Chips are
      derived from the cell text, not hand-assigned.</p>`;
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

  root.innerHTML = `
    <div class="viewhead"><h1>DXYZ — Price vs NAV</h1>
      <div class="sub">${esc(T.products.dxyz.fund_name)} — the fail case drawn:
        the market price is a premium series, not a portfolio series. This is WHY
        the benchmark engine refused a comparator (escalation, cell 5.x) —
        benchmarking the price benchmarks the premium.</div></div>
    <div class="statrow">
      ${stat("Peak close", "$" + peak.toFixed(2), peakDate + " (price series)")}
      ${stat("Drawdown from peak", dd.toFixed(1) + "%", "to " + troughAfterPeak[0] + " (computed)")}
      ${stat("Latest quarterly NAV/share", "$" + latest.nav_per_share.toFixed(2), latest.period_end + " (filed)")}
      ${stat("Premium at quarter high / low", `${latest.premium_pct_at_high}% / ${latest.premium_pct_at_low}%`, "as printed")}
    </div>
    <div class="chartbox"><div id="dxyzchart"></div>
      <div class="chartnote">Price: daily close, Yahoo Finance series (data/series/dxyz.csv,
        ${px.length} rows, cell 1.10 exhibit). NAV points: the fund's own quarterly
        NAV-per-share disclosure (${esc(nav.source)} — status ${esc(nav.status)}).
        Log scale; the vertical gap between the two lines IS the premium.</div></div>
    <h2 style="margin:18px 0 8px">Quarterly premium/(discount) as filed</h2>
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
    <p class="cap" style="margin-top:8px">${esc(nav.what)} — quote: “${esc(nav.quote)}”.</p>`;

  lineChart(root.querySelector("#dxyzchart"), {
    series: [
      { points: px, label: "Market price (daily close)", color: "#1f4e5f", width: 1.4 },
      { points: navPts, label: "NAV per share (quarterly, filed)",
        color: "#a4322b", markersOnly: true, markers: true },
    ],
    annotations: [
      { x: peakDate, y: peak, text: `peak $${peak.toFixed(2)}`, color: "#a4322b" },
      { x: troughAfterPeak[0], y: troughAfterPeak[1],
        text: `${dd.toFixed(1)}% from peak`, color: "#a4322b", dy: 16 },
    ],
    height: 340, logY: true, yFormat: (v) => "$" + v.toFixed(0),
  });
}

/* ======================================================== DE-SMOOTHING */
export function viewDesmooth(root) {
  const met = T.metrics.cclfx.full_history;
  const daily = T.series.cclfx;
  const me = monthEndPoints(daily);
  const rets = periodReturns(me.map(([, v]) => v));
  const [rec, rho] = desmoothGeltner(rets);
  const volObs = annVol(rets, 12) * 100;
  const volDes = annVol(rec, 12) * 100;

  const obsPts = rets.map((r, i) => [me[i + 1][0], r * 100]);
  const desPts = rec.map((r, i) => [me[i + 2][0], r * 100]);

  root.innerHTML = `
    <div class="viewhead"><h1>De-smoothing — CCLFX</h1>
      <div class="sub">${esc(T.products.cliffwater_cclfx.fund_name)} — appraisal-based
        NAVs autocorrelate; Geltner AR(1) unsmoothing recovers the volatility the
        smoothing hides. Cell 1.7 / 4.8 evidence, drawn.</div></div>
    <div class="statrow">
      ${stat("Lag-1 autocorrelation ρ", rho.toFixed(3), "estimated from monthly series")}
      ${stat("Observed ann. vol", volObs.toFixed(2) + "%")}
      ${stat("De-smoothed ann. vol", volDes.toFixed(2) + "%")}
      ${stat("Committed pipeline values", `${T.metrics.cclfx.full_history.lag1_autocorr_rho} / ${met.ann_vol_observed_pct}% / ${met.ann_vol_desmoothed_pct}%`,
             "data/analytics/metrics.json (computed, cited)")}
    </div>
    <div class="chartbox"><div id="dschart"></div>
      <div class="chartnote">Monthly returns from daily adj-close month-ends
        (window ${esc(met.window)}, ${rets.length} obs). De-smoothed series:
        r*_t = (r_t − ρ·r_{t−1}) / (1 − ρ). Recomputed live in the browser with
        the SAME ported code that passes the Python suite's toy cases; the
        committed pipeline numbers above are the cited record.</div></div>
    <div class="banner navy" style="margin-top:14px">Why it matters: the fund's
      disclosed stdev (${T.metrics.cclfx.fund_disclosed_at_2026_03_31.si_ann_stdev_pct}%,
      ${esc(T.metrics.cclfx.fund_disclosed_at_2026_03_31.source)}) understates
      participant-experienced risk if NAVs are appraisal-lagged. The de-smoothed
      number is the honest comparator input — and it is still low, which is
      itself informative about this asset class's pricing process.</div>`;

  lineChart(root.querySelector("#dschart"), {
    series: [
      { points: obsPts, label: "Observed monthly return (%)", color: "#1f4e5f", width: 1.5 },
      { points: desPts, label: "De-smoothed (Geltner AR1) (%)", color: "#b06e1c",
        width: 1.2, dash: "4,3" },
    ],
    height: 300, includeZero: true, yFormat: (v) => v.toFixed(1) + "%",
  });
}

/* ============================================================ COVERAGE */
export function viewCoverage(root) {
  const keys = Object.keys(T.products);
  let agg = { seeded: 0, soft: 0, pending: 0, verified: 0, computed: 0, extracted: 0 };
  const rows = keys.map((k) => {
    const c = T.evidence_counts[k];
    const seeded = c.extracted + c.verified + c.computed;
    const applicable = seeded + c.partial + c.fetched + c.pending;
    agg.seeded += seeded; agg.soft += c.partial + c.fetched;
    agg.pending += c.pending; agg.verified += c.verified;
    agg.computed += c.computed; agg.extracted += c.extracted;
    const segs = [
      ["extracted", (c.extracted + c.verified) / applicable * 100],
      ["computed", c.computed / applicable * 100],
      ["partial", (c.partial + c.fetched) / applicable * 100],
    ].map(([cls, w]) => `<div class="seg ${cls}" style="width:${w}%"></div>`).join("");
    return `<tr><td>${esc(T.products[k].fund_name)}</td>
      <td style="min-width:220px"><div class="covbar">${segs}</div></td>
      <td class="num">${c.coverage_pct}%</td>
      <td class="num">${c.extracted}</td><td class="num">${c.verified}</td>
      <td class="num">${c.computed}</td><td class="num">${c.partial + c.fetched}</td>
      <td class="num">${c.pending}</td><td class="num">${c.na}</td></tr>`;
  }).join("");
  const total = agg.seeded + agg.soft + agg.pending;
  const cc = T.crosscheck;

  root.innerHTML = `
    <div class="viewhead"><h1>Coverage & Provenance</h1>
      <div class="sub">The record's honesty, quantified: what is extracted, what is
        computed, what is still pending — and the independent cross-check stats.</div></div>
    <div class="statrow">
      ${stat("Overall coverage", Math.round((agg.seeded + agg.soft) / total * 100) + "%", `${agg.seeded} seeded + ${agg.soft} partial of ${total} applicable cells`)}
      ${stat("Extracted (cited)", agg.extracted)}
      ${stat("Computed (pipeline)", agg.computed)}
      ${stat("Human-verified", agg.verified, "verification interface: data/evidence/*.csv (CF2 pass pending)")}
    </div>
    <div class="cardgrid g3" style="margin-bottom:16px">
      <div class="card"><h3 class="num" style="font-size:26px;color:var(--green)">${cc.confirmed}</h3>
        <div class="cap">cells CONFIRMED by an independent re-location pass
          (of ${cc.cells_checked} checked)</div></div>
      <div class="card"><h3 class="num" style="font-size:26px;color:var(--amber)">${cc.corrected}</h3>
        <div class="cap">discrepancies found by the cross-check — both CORRECTED
          in the record (that the process catches its own errors is the point)</div></div>
      <div class="card"><h3 class="num" style="font-size:26px;color:var(--navy)">${cc.unlocatable}</h3>
        <div class="cap">cells that could not be re-located — zero</div></div>
    </div>
    <p class="cap" style="margin-bottom:16px">Source: ${esc(cc.source)}.</p>
    <div class="tablewrap"><table class="grid"><thead><tr>
      <th>Product</th><th>Mix</th><th>Coverage</th><th>Extracted</th>
      <th>Verified</th><th>Computed</th><th>Partial</th><th>Pending</th><th>n/a</th>
    </tr></thead><tbody>${rows}</tbody></table></div>
    <div class="legend" style="margin-top:8px">
      <span><span class="sw" style="background:var(--green)"></span>extracted/verified</span>
      <span><span class="sw" style="background:var(--violet)"></span>computed</span>
      <span><span class="sw" style="background:var(--amber)"></span>partial/fetched</span></div>
    <p class="cap footer-rule">Every number on every surface is real-and-cited or
      labeled ILLUSTRATIVE. Statuses are never inflated: nothing here is marked
      verified until a human checks the row in data/evidence/*.csv and signs
      verified_by. Bundle generated ${esc(T.generated)} from the same data layer
      the validator gates.</p>`;
}

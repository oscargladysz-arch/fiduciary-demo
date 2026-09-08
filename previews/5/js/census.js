/* Tark census — the T1 universe layer. Views over the lazy census INDEX
 * chunk (window.TARK_CENSUS, ≤500KB) plus on-demand detail shards
 * (census/d/<cik % shards>.json — full per-field provenance, fetched on
 * interaction) and an auditor/adviser search sidecar (census/search.json,
 * fetched only when a text filter is used). Tier discipline: T1 =
 * structured filing data (machine-read, per-field provenance), T2 =
 * AI-extracted unverified, T3 = human-verified. C2: name hints are NEVER
 * strategy claims — badged, excluded from filters unless explicitly
 * switched on. URL state is enums/numbers only; adviser/auditor/name text
 * search stays in memory. */

import { esc, money } from "./views.js";

const T = window.TARK;
const C = () => window.TARK_CENSUS;

export const CLASS_LABEL = {
  bdc: "BDC", interval_23c3: "interval fund (23c-3)",
  tender_cef: "tender-offer CEF", nontraded_reit: "non-traded REIT",
  listed_cef: "listed CEF", unlisted_cef_other: "unlisted CEF (other)",
  nontraded_34act_other: "non-traded '34-Act (other)",
};
export const CLASS_ORDER = ["interval_23c3", "tender_cef", "bdc",
  "nontraded_reit", "listed_cef", "unlisted_cef_other",
  "nontraded_34act_other"];

/* index rows are compact arrays; their field order ships in the chunk as
 * row_fields (written by build_site.py) and is decoded here, so the wire
 * format has one source */
const FL = { listed: 1, ncen: 2, intervalSelf: 4, crossAgree: 8,
  evaluated: 16, structured: 32 };
let _rows = null;
function rows() {
  if (_rows) return _rows;
  const cc = C().cls_codes;
  const hints = C().hints;
  const ix = Object.fromEntries(
    C().row_fields.map((f, i) => [f.split("(")[0], i]));
  _rows = Object.entries(C().entities).map(([cik, r]) => ({
    cik, nm: r[ix.nm], cls: cc[r[ix.cls_code]], flags: r[ix.flags],
    ta: r[ix.assets_usd] || null, la: r[ix.latest_annual_date] || null,
    tc: r[ix.tender_count], tl: r[ix.tender_last] || null,
    hm: r[ix.hint_mask], promo: r[ix.promo_key] || null,
    hints: hints.filter((_, i) => r[ix.hint_mask] & (1 << i)),
  }));
  return _rows;
}

/* ---- the tier legend: rendered on EVERY census surface ---- */
export function tierLegend() {
  return `<div class="tierlegend">
    <span class="chip structured">T1 structured filing data</span>
    <span class="cap">machine-read from N-CEN / XBRL / submissions. No
      model judgment, every field carries {source, ref, as-of}</span>
    <span class="chip extracted">T2 extracted-unverified</span>
    <span class="cap">AI-extracted from filings, awaiting human check</span>
    <span class="chip verified">T3 verified</span>
    <span class="cap">independently re-checked by a human</span>
  </div>`;
}

/* a provenance-carrying field → cell text + hover provenance (C3) */
function pf(f, fmt = (v) => esc(String(v))) {
  if (!f || f.value === null || f.value === undefined) {
    return `<span class="why" title="${esc(f?.reason || "not in structured sources")}">—</span>`;
  }
  return `<span class="cellval" title="source: ${esc(f.source)} · ref: ${esc(f.ref)} · as of ${esc(f.as_of)}">${fmt(f.value)}</span>`;
}

function tenderRecent(e, months) {
  if (!e.tl) return false;
  const cut = new Date(); cut.setMonth(cut.getMonth() - months);
  return e.tl >= cut.toISOString().slice(0, 10);
}

/* in-memory text filters (NEVER in the URL — leak-proof links) */
const mem = { q: "", adviser: "", auditor: "" };
let _search = null; // cik -> "auditor | adviser | …" (lazy sidecar)
async function ensureSearch() {
  if (_search) return _search;
  const r = await fetch("census/search.json");
  _search = await r.json();
  return _search;
}

/* detail shards, cached */
const _shards = {};
async function entityDetail(cik) {
  const s = String(Number(cik) % C().shards);
  if (!_shards[s]) {
    const r = await fetch(`census/d/${s}.json`);
    _shards[s] = await r.json();
  }
  return _shards[s][cik];
}

export function viewCensus(root, state, setState) {
  if (state.c_cik && C().entities[state.c_cik]) {
    return viewCensusEntity(root, state, setState);
  }
  const F = state;
  const needSearch = mem.adviser || mem.auditor;
  if (needSearch && !_search) {
    root.innerHTML = `<div class="nochart"><div class="k">Loading search sidecar</div>
      Fetching the auditor/adviser sidecar (lazy: it only loads when a text
      filter is used, and the query never enters the URL).</div>`;
    ensureSearch().then(() => setState({}));
    return;
  }
  let out = rows().filter((e) => {
    if (F.c_class && e.cls !== F.c_class) return false;
    if (F.c_listed === "yes" && !(e.flags & FL.listed)) return false;
    if (F.c_listed === "no" && (e.flags & FL.listed)) return false;
    if (F.c_interval === "1" && !(e.flags & FL.intervalSelf)
        && e.cls !== "interval_23c3") return false;
    if (F.c_eval === "yes" && !e.promo) return false;
    if (F.c_eval === "no" && e.promo) return false;
    if (F.c_tender === "24m" && !tenderRecent(e, 24)) return false;
    if (F.c_tender === "60m" && !tenderRecent(e, 60)) return false;
    if (F.c_tender === "ever" && !e.tc) return false;
    if (F.c_amin && !(e.ta !== null && e.ta >= Number(F.c_amin) * 1e6)) return false;
    if (F.c_amax && !(e.ta !== null && e.ta <= Number(F.c_amax) * 1e6)) return false;
    if (F.c_hint && !e.hints.includes(F.c_hint)) return false;
    if (mem.q && !(e.nm || "").toLowerCase().includes(mem.q)) return false;
    if (mem.adviser && !(_search[e.cik] || "").includes(mem.adviser)) return false;
    if (mem.auditor && !(_search[e.cik] || "").includes(mem.auditor)) return false;
    return true;
  });
  out.sort((x, y) => (y.ta || 0) - (x.ta || 0)
    || (x.nm || "").localeCompare(y.nm || ""));

  const sel = (id, label, opts, labels = {}) => `<span class="lbl">${label}</span>
    <select data-cf="${id}"><option value="">any</option>
      ${opts.map((o) => `<option value="${o}" ${F[id] === o ? "selected" : ""}>${esc(labels[o] || o)}</option>`).join("")}
    </select>`;

  root.innerHTML = `
    <h1>Universe: <span class="cap">every registered alt wrapper the census can see</span></h1>
    ${tierLegend()}
    <p class="cap">${C().total.toLocaleString()} entities enumerated from filing
      behavior (EFTS form streams, SIC search, submissions listing check),
      census as of ${esc(C().as_of)}.
      This layer is <b>T1: structured filing data only</b>. Wrapper classes
      come from what each entity filed, never from what its name suggests.
      The ${Object.keys(T.products).length} evaluated products are the tiny
      lit patch: <button class="linklike" data-gofunnel>see the funnel</button>.</p>
    <div class="filterbar">
      ${sel("c_class", "Wrapper", CLASS_ORDER, CLASS_LABEL)}
      ${sel("c_listed", "Exchange-listed", ["yes", "no"])}
      ${sel("c_interval", "Interval", ["1"], { 1: "interval only" })}
      ${sel("c_tender", "Tender activity", ["24m", "60m", "ever"],
        { "24m": "last 24 months", "60m": "last 5 years", ever: "any (2001+)" })}
      ${sel("c_eval", "Evaluated (T2+)", ["yes", "no"])}
      <span class="lbl">Assets $M</span>
      <input data-cn="c_amin" size="6" inputmode="numeric" placeholder="min" value="${esc(F.c_amin)}">
      <input data-cn="c_amax" size="6" inputmode="numeric" placeholder="max" value="${esc(F.c_amax)}">
      <span class="lbl">Name <span class="cap">(memory-only)</span></span>
      <input data-cm="q" size="12" placeholder="contains…" value="${esc(mem.q)}">
      <span class="lbl">Adviser</span>
      <input data-cm="adviser" size="10" placeholder="N-CEN adviser" value="${esc(mem.adviser)}">
      <span class="lbl">Auditor</span>
      <input data-cm="auditor" size="10" placeholder="N-CEN auditor" value="${esc(mem.auditor)}">
      <details class="hintfilter"><summary>name-hint filter (off by default)</summary>
        <p class="cap">Hints are derived from the fund NAME only. They are
        <b>not strategy claims</b> and are excluded from filtering unless you
        opt in here.</p>
        ${sel("c_hint", "Hint", C().hints)}
      </details>
    </div>
    <p class="cap">${out.length.toLocaleString()} of ${rows().length.toLocaleString()} entities
      ${(mem.q || mem.adviser || mem.auditor) ? " · text filters active (kept out of the URL by design)" : ""}</p>
    <div class="tablewrap"><table class="grid">
      <thead><tr><th>Entity</th><th>Wrapper (from filing behavior)</th>
        <th>Listed</th><th>Structured assets</th>
        <th>Interval ✓</th><th>Latest annual</th><th>Tenders</th>
        <th>Tier</th></tr></thead>
      <tbody>
      ${out.slice(0, 400).map((e) => `<tr data-cik="${e.cik}">
        <td><b>${esc(e.nm || "(name pending)")}</b>
          ${e.hints.map((h) => `<span class="chip hint" title="derived from the name only, not a strategy claim">${esc(h)}</span>`).join("")}</td>
        <td>${esc(CLASS_LABEL[e.cls] || e.cls)}</td>
        <td>${(e.flags & FL.listed) ? "yes" : "no"}</td>
        <td>${e.ta ? `<span title="structured (T1): open the entity for source · ref · as-of">${money(e.ta)}</span>` : "—"}</td>
        <td>${(e.flags & FL.ncen)
          ? ((e.flags & FL.intervalSelf)
             ? ((e.flags & FL.crossAgree) ? "✓ self+behavior" : "self-only")
             : "—")
          : "—"}</td>
        <td>${e.la ? esc(e.la) : "—"}</td>
        <td>${e.tc ? `${e.tc}× → ${esc(e.tl)}` : "—"}</td>
        <td>${e.promo
          ? `<span class="chip extracted">T2 evaluated</span>`
          : `<span class="chip structured">T1</span>`}</td>
      </tr>`).join("")}
      </tbody></table></div>
    ${out.length > 400 ? `<p class="cap">Showing the 400 largest by structured assets. Narrow the filters to see the rest (all ${out.length.toLocaleString()} are loaded and filterable).</p>` : ""}`;

  root.querySelectorAll("[data-cf]").forEach((s) => s.addEventListener(
    "change", (e2) => setState({ [s.dataset.cf]: e2.target.value })));
  root.querySelectorAll("[data-cn]").forEach((i) => i.addEventListener(
    "change", (e2) => {
      setState({ [i.dataset.cn]: e2.target.value.replace(/[^0-9]/g, "") });
    }));
  root.querySelectorAll("[data-cm]").forEach((i) => i.addEventListener(
    "change", (e2) => { mem[i.dataset.cm] = e2.target.value.toLowerCase(); setState({}); }));
  root.querySelector("[data-gofunnel]").addEventListener("click",
    () => setState({ view: "funnel" }));
  root.querySelectorAll("tr[data-cik]").forEach((tr) => tr.addEventListener(
    "click", () => setState({ c_cik: tr.dataset.cik })));
}

/* ------------------------------------------------------ entity detail */
function provRow(label, f, fmt) {
  if (!f) return "";
  return `<tr><td class="k">${esc(label)}</td><td>${pf(f, fmt)}</td>
    <td class="cap">${esc(f.source || "")} · ${esc(f.ref || "")} · ${esc(f.as_of || "")}</td></tr>`;
}

export function viewCensusEntity(root, state, setState) {
  root.innerHTML = `<div class="nochart"><div class="k">Loading entity</div>
    Fetching this entity's detail shard (full per-field provenance, split
    from the index so the universe screener stays a light chunk).</div>`;
  entityDetail(state.c_cik).then((e) => {
    if (!e) {
      root.innerHTML = `<p>Entity not in the census detail shards.</p>`;
      return;
    }
    renderEntity(root, e, state, setState);
  });
}

/* a product key suggestion from the entity name: lowercase, letters, digits
 * and underscores, the ticker in parentheses dropped, 2 to 32 characters */
export function suggestKey(name) {
  const base = String(name || "").replace(/\(.*?\)/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 32);
  return base.length >= 2 ? base : `cik_${base}`;
}

function renderEntity(root, e, state, setState) {
  const nc = e.nc ? e.nc.value : null;
  const serviceUrl = T.service_url;      // null unless a service was connected at build time
  const cmd = `Evaluate CIK ${e.cik} (suggested record key ${suggestKey(e.nm)})`;
  root.innerHTML = `
    <p><button class="linklike" data-back>← back to the universe</button></p>
    <h1>${esc(e.nm || "(name pending)")} <span class="cap">CIK ${e.cik}</span></h1>
    ${tierLegend()}
    <div class="cardgrid g2">
      <div class="card"><h3>Wrapper: ${esc(CLASS_LABEL[e.cls] || e.cls)}</h3>
        <p class="cap">Classified from filing behavior, not from marketing or
        the name (C2). Detection evidence:</p>
        <ul>${(e.ev || []).map((x) => `<li class="cap">${esc(x)}</li>`).join("")}</ul>
        ${(e.sig || []).length > 1 ? `<p class="cap">All signals fired: ${e.sig.map(esc).join(", ")}</p>` : ""}
      </div>
      <div class="card"><h3>${e.promo ? "Evaluated (T2+)" : "Evaluate this fund"}</h3>
        ${e.promo ? `
          <p>This entity is on the evaluated roster as
            <b>${esc(T.products[e.promo]?.fund_name || e.promo)}</b>, with a full
            six-factor extraction and per-cell provenance.</p>
          <button class="primary" data-goproduct="${esc(e.promo)}">open the evaluation record</button>`
        : `
          <p class="cap">Everything above is T1 (structured filing data). A
          promotion step verifies identity against EDGAR (R1),
          fetches the fund's filings, scaffolds the 55-cell six-factor record,
          prefills what the census already answers (marked
          <span class="chip structured">structured filing data (T1)</span>),
          and emits the extraction worklist for the rest. Nothing here is
          extracted or verified until that work is actually done.</p>
          <p class="cap">The registry entry (cohort, strategy, wrapper, a person's
            judgments) comes first, then Tark runs the evaluation for this fund:</p>
          <pre class="cmd" data-cmd>${esc(cmd)}</pre>
          <button class="btn ghost" data-copycmd>copy request</button>
          ${serviceUrl
            ? `<button class="primary" data-evaluate>Evaluate this fund</button>
               <span class="cap">posts to ${esc(serviceUrl)}/evaluate and shows its answer as returned</span>`
            : `<span class="cap">No evaluation service is connected to this build, so the
               button is not shown. Send the request to Tark.</span>`}
          <div data-evalresult></div>`}
      </div>
    </div>
    <h2>Structured facts <span class="cap">(every row carries source · ref · as-of)</span></h2>
    <div class="tablewrap"><table class="grid">
      <thead><tr><th>Field</th><th>Value</th><th>Provenance</th></tr></thead>
      <tbody>
        ${provRow("Current entity name", e.enc)}
        ${provRow("Exchange-listed (common shares)", e.lif, (v) => v ? ((e.ex || []).join(", ") || "yes") : "no")}
        ${e.lsig ? provRow("Listing signal (submissions)", e.lsig) : ""}
        ${e.tk && e.tk.value && e.tk.value.length ? provRow("Tickers (SEC oracle, OTC quotation ≠ listing)", e.tk, (v) => v.map(esc).join(", ")) : ""}
        ${provRow("First filing on record", e.ff)}
        ${provRow("Latest annual report", e.la, (v) => `${esc(v.form)} filed ${esc(v.date)}`)}
        ${provRow("Total assets", e.ta, (v) => `${money(v.value)} <span class="cap">(${esc(v.basis)})</span>`)}
        ${e.nav ? provRow("NAV per share (structured)", e.nav) : ""}
        ${e.ic ? provRow("Interval cross-check", e.ic, (v) =>
          `N-CEN self-classified: ${v.ncen_self_classified_interval ? "yes" : "no"} · N-23C3A behavior: ${v.n23c3a_filing_behavior ? "yes" : "no"} · ${v.agreement ? "AGREE" : "DISAGREE"}`) : ""}
      </tbody></table></div>
    ${nc ? `
    <h2>N-CEN <span class="cap">(latest annual report, structured dataset)</span></h2>
    <div class="tablewrap"><table class="grid"><tbody>
      ${provRow("Investment company type", { ...e.nc, value: nc.ict })}
      ${provRow("Auditor", { ...e.nc, value: nc.auditor || null, reason: "no accountant row" })}
      ${provRow("NAV error corrected (period)", { ...e.nc, value: nc.nav_err })}
      ${provRow("Audit opinion qualified", { ...e.nc, value: nc.oq })}
      ${nc.pf ? provRow("Largest series", { ...e.nc, value: nc.pf }, (v) =>
        `${esc(v.fund_name)} · avg net assets ${v.avg_net_assets ? money(v.avg_net_assets) : "—"} ·
         mgmt fee ${v.management_fee !== null && v.management_fee !== undefined ? esc(String(v.management_fee)) + "%" : "—"} ·
         interval: ${esc(v.is_interval || "—")}
         ${v.advisers && v.advisers.length ? " · advisers: " + v.advisers.map(esc).join("; ") : ""}`) : ""}
    </tbody></table></div>` : ""}
    ${e.fs ? `
    <h2>Filing activity <span class="cap">(recent EDGAR stream, by form)</span></h2>
    <div class="filestrip">${Object.entries(e.fs.value).map(([f, n]) =>
      `<span class="chip plain">${esc(f)} × ${n}</span>`).join(" ")}
      <span class="cap" title="source: ${esc(e.fs.source)} · ${esc(e.fs.ref)}">· source: submissions JSON, as of ${esc(e.fs.as_of)}</span></div>` : ""}
    ${(e.hint || []).length ? `
    <p class="cap"><span class="chip hint">hint</span> Name suggests:
      ${e.hint.map(esc).join(", ")}. Derived from the NAME ONLY, never a
      strategy claim, never used in default filters (C2).</p>` : ""}`;

  root.querySelector("[data-back]").addEventListener("click",
    () => setState({ c_cik: "" }));
  const gp = root.querySelector("[data-goproduct]");
  if (gp) gp.addEventListener("click", () => setState(
    { view: "evaluation", product: gp.dataset.goproduct, c_cik: "" }));
  const cp = root.querySelector("[data-copycmd]");
  if (cp) cp.addEventListener("click", () => {
    navigator.clipboard?.writeText(cmd);
    cp.textContent = "copied";
  });
  const ev = root.querySelector("[data-evaluate]");
  if (ev) ev.addEventListener("click", async () => {
    const out = root.querySelector("[data-evalresult]");
    ev.disabled = true;
    out.innerHTML = `<p class="cap">Request sent. The service runs the ingest synchronously and
      answers when it is done or refused, so this can take a while.</p>`;
    try {
      const r = await fetch(`${serviceUrl}/evaluate`, { method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ cik: String(e.cik), key: suggestKey(e.nm) }) });
      const j = await r.json();
      out.innerHTML = `<p><b>Service answer:</b> ${esc(j.status || "no status")}
        ${j.reason ? `<span class="cap">${esc(j.reason)}</span>` : ""}
        ${j.exit_code !== undefined ? `<span class="cap">exit code ${esc(String(j.exit_code))}</span>` : ""}</p>
        ${j.output_tail ? `<pre class="cmd">${esc(j.output_tail.join("\n"))}</pre>` : ""}
        ${j.report ? `<p class="cap">report: ${esc(j.report)}</p>` : ""}
        ${j.commands ? `<pre class="cmd">${esc(j.commands.join("\n"))}</pre>` : ""}`;
    } catch (err) {
      out.innerHTML = `<p class="cap">Service unreachable: ${esc(String(err))}. Run the command.</p>`;
    }
    ev.disabled = false;
  });
}

/* ------------------------------------------------------------- funnel */
export function viewFunnel(root, state, setState) {
  const all = rows();
  const censused = all.filter((e) => e.flags & FL.structured).length;
  const evaluated = Object.keys(T.products).length;
  let cellsV = 0; let cellsT = 0;
  for (const p of Object.values(T.products)) {
    for (const c of Object.values(p.cells)) {
      cellsT++;
      if (String(c.status || "").startsWith("verified")) cellsV++;
    }
  }
  const dark = C().dark_universe;
  const bar = (n, base) => `<div class="funnelbar"><div class="fill" style="width:${Math.max(0.4, 100 * n / base)}%"></div></div>`;
  const counts = C().counts_by_class;
  const maxC = Math.max(...Object.values(counts));
  root.innerHTML = `
    <h1>The funnel: <span class="cap">what the census can see, honestly</span></h1>
    ${tierLegend()}
    <div class="cardgrid g2">
      <div class="card dark"><h3>${dark.formd_new_notices.toLocaleString()}</h3>
        <p>private pooled funds filed Form D in the trailing 24 months
        (${esc(dark.window)}): the <b>dark universe</b>. No NAV, no fee table,
        no structured data: a 401(k) fiduciary cannot see into these at all.
        <span class="cap">(+${dark.formd_amendments.toLocaleString()} amendments. EFTS phrase query on the Form D industry group)</span></p></div>
      <div class="card"><h3>${C().total.toLocaleString()}</h3>
        <p><b>registered wrappers enumerated</b>: the universe this census
        covers, classified from filing behavior alone.</p>${bar(C().total, C().total)}</div>
      <div class="card"><h3>${censused.toLocaleString()}</h3>
        <p><b>with structured facts (T1)</b>: N-CEN, XBRL, or an annual
        report on record.</p>${bar(censused, C().total)}</div>
      <div class="card"><h3>${evaluated}</h3>
        <p><b>evaluated (T2)</b>: full six-factor extraction with per-cell
        provenance, cohort placement, decision memo.</p>${bar(evaluated, C().total)}</div>
      <div class="card"><h3>${cellsV}</h3>
        <p><b>human-verified cells (T3)</b> of ${cellsT.toLocaleString()}
        evaluated cells, the only tier a human has signed.</p>${bar(cellsV, cellsT)}</div>
    </div>
    <h2>Universe by wrapper class <span class="cap">(from filing behavior: real counts, no padding)</span></h2>
    <div class="tablewrap"><table class="grid"><tbody>
      ${CLASS_ORDER.filter((k) => counts[k]).map((k) => `<tr>
        <td class="k">${esc(CLASS_LABEL[k])}</td>
        <td style="min-width:12rem">${bar(counts[k], maxC)}</td>
        <td><b>${counts[k].toLocaleString()}</b></td>
        <td><button class="linklike" data-class="${esc(k)}">browse</button></td></tr>`).join("")}
      <tr><td class="k">TOTAL</td><td></td><td><b>${C().total.toLocaleString()}</b></td><td></td></tr>
    </tbody></table></div>
    <h2>Method <span class="cap">(and its stated limits)</span></h2>
    <ul>${(C().method_notes || []).map((n) => `<li class="cap">${esc(n)}</li>`).join("")}</ul>`;
  root.querySelectorAll("[data-class]").forEach((b) => b.addEventListener(
    "click", () => setState({ view: "census", c_class: b.dataset.class })));
}

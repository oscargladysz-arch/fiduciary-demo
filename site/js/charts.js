/* Minimal hand-rolled SVG charts — no external libraries (self-contained
 * static deploy). Line charts with date x-axes, point markers, annotations. */

import { parseDate } from "./analytics.js";

const NS = "http://www.w3.org/2000/svg";

function el(tag, attrs = {}, text = null) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text !== null) e.textContent = text;
  return e;
}

function niceTicks(lo, hi, n = 5) {
  if (lo === hi) { lo -= 1; hi += 1; }
  const span = hi - lo;
  const step0 = span / n;
  const mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag)
    .find((s) => span / s <= n + 1) || mag * 10;
  const t0 = Math.ceil(lo / step) * step;
  const out = [];
  for (let t = t0; t <= hi + 1e-9; t += step) out.push(t);
  return out;
}

function logTicks(lo, hi) {
  // 1-2-5 series across the decades covered by [lo, hi]
  const out = [];
  for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) {
    for (const m of [1, 2, 5]) {
      const t = m * 10 ** e;
      if (t >= lo && t <= hi) out.push(t);
    }
  }
  return out;
}

/**
 * lineChart(container, {
 *   series: [{points: [[iso, y], ...], label, color, width, dash, markers}],
 *   annotations: [{x: iso, y, text, color}], yFormat, height, logY
 * })
 */
export function lineChart(container, cfg) {
  const W = 920;
  const H = cfg.height || 320;
  const M = { t: 16, r: 16, b: 34, l: 62 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });

  const all = cfg.series.flatMap((s) => s.points);
  if (!all.length) return;
  const xs = all.map(([d]) => parseDate(d));
  const ys = all.map(([, y]) => y);
  const x0 = Math.min(...xs); const x1 = Math.max(...xs);
  let y0 = Math.min(...ys); let y1 = Math.max(...ys);
  if (cfg.includeZero) y0 = Math.min(0, y0);
  if (cfg.logY) {
    const padF = (y1 / y0) ** 0.05 || 1.1;   // multiplicative pad keeps y0 > 0
    y0 /= padF; y1 *= padF;
  } else {
    const pad = (y1 - y0) * 0.06 || 1;
    y0 -= pad; y1 += pad;
  }

  const X = (d) => M.l + (parseDate(d) - x0) / (x1 - x0 || 1) * (W - M.l - M.r);
  const Y = cfg.logY
    ? (v) => M.t + (1 - (Math.log(v) - Math.log(y0)) /
        (Math.log(y1) - Math.log(y0))) * (H - M.t - M.b)
    : (v) => M.t + (1 - (v - y0) / (y1 - y0)) * (H - M.t - M.b);

  const fmt = cfg.yFormat || ((v) => v.toLocaleString());
  const ticks = cfg.logY ? logTicks(y0, y1) : niceTicks(y0, y1, 5);
  for (const t of ticks) {
    svg.append(el("line", { x1: M.l, x2: W - M.r, y1: Y(t), y2: Y(t),
      stroke: "#eceff1", "stroke-width": 1 }));
    svg.append(el("text", { x: M.l - 8, y: Y(t) + 4, "text-anchor": "end",
      "font-size": 11, fill: "#7b8794", "font-family": "ui-monospace, Menlo, monospace" }, fmt(t)));
  }
  // x ticks: ~6 date labels
  const nX = 6;
  for (let i = 0; i <= nX; i++) {
    const t = x0 + (x1 - x0) * i / nX;
    const d = new Date(t);
    const lab = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
    const px = M.l + (t - x0) / (x1 - x0 || 1) * (W - M.l - M.r);
    svg.append(el("text", { x: px, y: H - 10, "text-anchor": "middle",
      "font-size": 11, fill: "#7b8794", "font-family": "ui-monospace, Menlo, monospace" }, lab));
  }
  svg.append(el("line", { x1: M.l, x2: W - M.r, y1: H - M.b, y2: H - M.b,
    stroke: "#dee3e7" }));

  for (const s of cfg.series) {
    if (s.points.length > 1 && !s.markersOnly) {
      const dAttr = s.points.map(([d, y], i) =>
        `${i ? "L" : "M"}${X(d).toFixed(1)},${Y(y).toFixed(1)}`).join("");
      svg.append(el("path", { d: dAttr, fill: "none",
        stroke: s.color || "#1f4e5f", "stroke-width": s.width || 1.6,
        "stroke-dasharray": s.dash || "none" }));
    }
    if (s.markers || s.markersOnly) {
      for (const [d, y] of s.points) {
        svg.append(el("circle", { cx: X(d), cy: Y(y), r: 3.4,
          fill: s.color || "#1f4e5f", stroke: "#fff", "stroke-width": 1 }));
      }
    }
  }

  for (const a of cfg.annotations || []) {
    const ax = X(a.x); const ay = Y(a.y);
    svg.append(el("circle", { cx: ax, cy: ay, r: 4, fill: "none",
      stroke: a.color || "#a4322b", "stroke-width": 1.6 }));
    const anchor = ax > W * 0.72 ? "end" : "start";
    const dx = ax > W * 0.72 ? -8 : 8;
    svg.append(el("text", { x: ax + dx, y: ay + (a.dy || -8),
      "font-size": 11, "font-weight": 600, fill: a.color || "#a4322b",
      "text-anchor": anchor }, a.text));
  }

  container.innerHTML = "";
  container.append(svg);
  if (cfg.series.some((s) => s.label)) {
    const leg = document.createElement("div");
    leg.className = "legend";
    for (const s of cfg.series) {
      if (!s.label) continue;
      const item = document.createElement("span");
      const sw = document.createElement("span");
      sw.className = "sw";
      sw.style.background = s.color || "#1f4e5f";
      item.append(sw, s.label);
      leg.append(item);
    }
    container.append(leg);
  }
}

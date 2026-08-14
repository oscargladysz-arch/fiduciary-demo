/* Hand-rolled SVG charts — no external libraries (self-contained deploy).
 * Line charts (with hover tooltips), horizontal bars, donuts, rings.
 * Every chart is DATA-DRIVEN from the bundle; nothing here invents values. */

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
  const out = [];
  for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) {
    for (const m of [1, 2, 5]) {
      const t = m * 10 ** e;
      if (t >= lo && t <= hi) out.push(t);
    }
  }
  return out;
}

/* one shared tooltip node */
let tipEl = null;
function tip() {
  if (!tipEl) {
    tipEl = document.createElement("div");
    tipEl.className = "charttip";
    document.body.append(tipEl);
  }
  return tipEl;
}

/**
 * lineChart(container, { series: [{points [[iso,y]], label, color, width,
 *   dash, markers, markersOnly}], annotations, yFormat, height, logY,
 *   includeZero })  — hover shows nearest point per series.
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
    const padF = (y1 / y0) ** 0.05 || 1.1;
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
      stroke: "#eeeae4", "stroke-width": 1 }));
    svg.append(el("text", { x: M.l - 8, y: Y(t) + 4, "text-anchor": "end",
      "font-size": 11, fill: "#837b8e" }, fmt(t)));
  }
  const nX = 6;
  for (let i = 0; i <= nX; i++) {
    const t = x0 + (x1 - x0) * i / nX;
    const d = new Date(t);
    const lab = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
    const px = M.l + (t - x0) / (x1 - x0 || 1) * (W - M.l - M.r);
    svg.append(el("text", { x: px, y: H - 10, "text-anchor": "middle",
      "font-size": 11, fill: "#837b8e" }, lab));
  }
  svg.append(el("line", { x1: M.l, x2: W - M.r, y1: H - M.b, y2: H - M.b,
    stroke: "#e3ded7" }));

  for (const s of cfg.series) {
    if (s.points.length > 1 && !s.markersOnly) {
      const dAttr = s.points.map(([d, y], i) =>
        `${i ? "L" : "M"}${X(d).toFixed(1)},${Y(y).toFixed(1)}`).join("");
      svg.append(el("path", { d: dAttr, fill: "none",
        stroke: s.color || "#593380", "stroke-width": s.width || 1.6,
        "stroke-dasharray": s.dash || "none" }));
    }
    if (s.markers || s.markersOnly) {
      for (const [d, y] of s.points) {
        svg.append(el("circle", { cx: X(d), cy: Y(y), r: 3.4,
          fill: s.color || "#593380", stroke: "#fff", "stroke-width": 1 }));
      }
    }
  }

  for (const a of cfg.annotations || []) {
    const ax = X(a.x); const ay = Y(a.y);
    svg.append(el("circle", { cx: ax, cy: ay, r: 4, fill: "none",
      stroke: a.color || "#9d2f26", "stroke-width": 1.6 }));
    const anchor = ax > W * 0.72 ? "end" : "start";
    const dx = ax > W * 0.72 ? -8 : 8;
    svg.append(el("text", { x: ax + dx, y: ay + (a.dy || -8),
      "font-size": 11, "font-weight": 600, fill: a.color || "#9d2f26",
      "text-anchor": anchor }, a.text));
  }

  /* hover: nearest point per series, vertical guide, tooltip */
  const guide = el("line", { y1: M.t, y2: H - M.b, stroke: "#a685cc",
    "stroke-width": 1, "stroke-dasharray": "3,3", visibility: "hidden" });
  svg.append(guide);
  const dots = cfg.series.map((s) => {
    const c = el("circle", { r: 4, fill: s.color || "#593380",
      stroke: "#fff", "stroke-width": 1.4, visibility: "hidden" });
    svg.append(c);
    return c;
  });
  svg.addEventListener("mousemove", (ev) => {
    const rect = svg.getBoundingClientRect();
    const mx = (ev.clientX - rect.left) / rect.width * W;
    if (mx < M.l || mx > W - M.r) return;
    const tt = tip();
    const lines = [];
    let guideX = null;
    cfg.series.forEach((s, i) => {
      let best = null; let bd = Infinity;
      for (const [d, y] of s.points) {
        const dx = Math.abs(X(d) - mx);
        if (dx < bd) { bd = dx; best = [d, y]; }
      }
      if (best && bd < 60) {
        dots[i].setAttribute("cx", X(best[0]));
        dots[i].setAttribute("cy", Y(best[1]));
        dots[i].setAttribute("visibility", "visible");
        guideX = guideX ?? X(best[0]);
        lines.push(`${best[0]}  ${s.label ? s.label.split("(")[0].trim() + ": " : ""}${fmt(best[1])}`);
      } else {
        dots[i].setAttribute("visibility", "hidden");
      }
    });
    if (lines.length) {
      guide.setAttribute("x1", guideX);
      guide.setAttribute("x2", guideX);
      guide.setAttribute("visibility", "visible");
      tt.style.display = "block";
      tt.style.left = `${ev.clientX + 14}px`;
      tt.style.top = `${ev.clientY + 12}px`;
      tt.textContent = lines.join("  ·  ");
    }
  });
  svg.addEventListener("mouseleave", () => {
    tip().style.display = "none";
    guide.setAttribute("visibility", "hidden");
    dots.forEach((d) => d.setAttribute("visibility", "hidden"));
  });

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
      sw.style.background = s.color || "#593380";
      item.append(sw, s.label);
      leg.append(item);
    }
    container.append(leg);
  }
}

/**
 * barChart(container, {items: [{label, value, color, note}], format, max,
 *   height, markers: [{value, label, color}]}) — horizontal bars.
 */
export function barChart(container, cfg) {
  const W = 920;
  const rowH = 34;
  const M = { t: 8, r: 60, b: 24, l: 210 };
  const H = M.t + cfg.items.length * rowH + M.b;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });
  const max = cfg.max ?? Math.max(...cfg.items.map((i) => i.value || 0)) * 1.12;
  const X = (v) => M.l + v / (max || 1) * (W - M.l - M.r);
  const fmt = cfg.format || ((v) => String(v));

  for (const t of niceTicks(0, max, 5)) {
    svg.append(el("line", { x1: X(t), x2: X(t), y1: M.t, y2: H - M.b,
      stroke: "#eeeae4" }));
    svg.append(el("text", { x: X(t), y: H - 8, "text-anchor": "middle",
      "font-size": 10.5, fill: "#837b8e" }, fmt(t)));
  }
  cfg.items.forEach((it, i) => {
    const y = M.t + i * rowH;
    svg.append(el("text", { x: M.l - 10, y: y + rowH / 2 + 4,
      "text-anchor": "end", "font-size": 12, fill: "#262130",
      "font-weight": 500 }, it.label.slice(0, 30)));
    if (it.value === null || it.value === undefined) {
      svg.append(el("text", { x: M.l + 6, y: y + rowH / 2 + 4,
        "font-size": 11, fill: "#837b8e", "font-style": "italic" },
        it.note || "n/a"));
      return;
    }
    svg.append(el("rect", { x: M.l, y: y + 7, width: Math.max(2, X(it.value) - M.l),
      height: rowH - 14, fill: it.color || "#593380", rx: 2 }));
    svg.append(el("text", { x: X(it.value) + 6, y: y + rowH / 2 + 4,
      "font-size": 12, "font-weight": 600, fill: "#262130" }, fmt(it.value)));
  });
  for (const mk of cfg.markers || []) {
    svg.append(el("line", { x1: X(mk.value), x2: X(mk.value), y1: M.t,
      y2: H - M.b, stroke: mk.color || "#9d2f26", "stroke-width": 1.6,
      "stroke-dasharray": "5,3" }));
    svg.append(el("text", { x: X(mk.value), y: M.t + 10, "font-size": 10.5,
      "font-weight": 600, fill: mk.color || "#9d2f26",
      "text-anchor": "middle" }, mk.label));
  }
  container.innerHTML = "";
  container.append(svg);
}

/** donut(container, {segments: [{label, value, color}], size, center,
 *   centerSub}) */
export function donut(container, cfg) {
  const size = cfg.size || 180;
  const r = size / 2 - 12;
  const cx = size / 2; const cy = size / 2;
  const total = cfg.segments.reduce((a, s) => a + s.value, 0) || 1;
  const svg = el("svg", { viewBox: `0 0 ${size} ${size}`,
    style: `max-width:${size}px` });
  let a0 = -Math.PI / 2;
  for (const s of cfg.segments) {
    const frac = s.value / total;
    if (frac <= 0) continue;
    const a1 = a0 + frac * Math.PI * 2;
    const large = frac > 0.5 ? 1 : 0;
    const p = (a) => `${(cx + r * Math.cos(a)).toFixed(2)},${(cy + r * Math.sin(a)).toFixed(2)}`;
    if (frac >= 0.9999) {
      svg.append(el("circle", { cx, cy, r, fill: "none", stroke: s.color,
        "stroke-width": 20 }));
    } else {
      svg.append(el("path", {
        d: `M${p(a0)} A${r},${r} 0 ${large} 1 ${p(a1)}`,
        fill: "none", stroke: s.color, "stroke-width": 20 }));
    }
    a0 = a1;
  }
  if (cfg.center) {
    svg.append(el("text", { x: cx, y: cy + 1, "text-anchor": "middle",
      "font-size": size / 7.2, "font-weight": 600, fill: "#331d49" },
      cfg.center));
    if (cfg.centerSub) {
      svg.append(el("text", { x: cx, y: cy + size / 8.5, "text-anchor": "middle",
        "font-size": size / 16, fill: "#837b8e" }, cfg.centerSub));
    }
  }
  container.innerHTML = "";
  container.append(svg);
}

/** small coverage ring (returns an element) */
export function ring(pct, color = "#593380", size = 84) {
  const wrap = document.createElement("div");
  wrap.className = "ring";
  wrap.style.width = wrap.style.height = `${size}px`;
  const r = size / 2 - 6;
  const c = 2 * Math.PI * r;
  const svg = el("svg", { viewBox: `0 0 ${size} ${size}`,
    width: size, height: size });
  svg.append(el("circle", { cx: size / 2, cy: size / 2, r, fill: "none",
    stroke: "#eeeae4", "stroke-width": 8 }));
  svg.append(el("circle", { cx: size / 2, cy: size / 2, r, fill: "none",
    stroke: color, "stroke-width": 8,
    "stroke-dasharray": `${(pct / 100 * c).toFixed(1)} ${c.toFixed(1)}`,
    "stroke-linecap": "butt" }));
  const label = document.createElement("div");
  label.className = "pct";
  label.textContent = `${pct}%`;
  wrap.append(svg, label);
  return wrap;
}

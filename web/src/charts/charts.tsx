/* One chart module (R3-P1-7): responsive SVG whose text is rendered at token
 * sizes in CSS pixels regardless of container width (scales are computed per
 * container size, no fixed viewBox), axis labels never clipped, a table
 * alternative behind a toggle, tooltips reachable by keyboard focus on data
 * points and by tap, an accessible name and description, tabular figures,
 * colors from the tokens, a legend as part of the component. */
import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Button, Legend } from "../components/primitives";
import { fmtDateShort, fmtNum } from "../format/format";

const CHART_COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)", "var(--chart-6)"];
/* text sizes in CSS pixels: the token values, read once from the root so the
 * SVG never scales them */
function tokenPx(name: string, fallback: number): number {
  if (typeof window === "undefined") return fallback;
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : fallback;
}

export function useSize<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const ro = new ResizeObserver((es) => { for (const e of es) setW(Math.floor(e.contentRect.width)); });
    ro.observe(el); setW(Math.floor(el.getBoundingClientRect().width));
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

function niceTicks(min: number, max: number, count = 5): number[] {
  if (!(max > min)) return [min];
  const span = max - min;
  const step0 = span / Math.max(1, count - 1);
  const mag = 10 ** Math.floor(Math.log10(step0));
  const norm = step0 / mag;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;
  const start = Math.floor(min / step) * step;
  const out: number[] = [];
  for (let v = start; v <= max + step / 2; v += step) out.push(Math.round(v * 1e10) / 1e10);
  return out;
}

interface ChartFrameProps { title: string; description: string; legend?: { label: string; color: string }[]; table: ReactNode; children: (w: number) => ReactNode; height?: number; footer?: ReactNode }
export function ChartFrame({ title, description, legend, table, children, footer }: ChartFrameProps) {
  const [ref, w] = useSize<HTMLDivElement>();
  const [showTable, setShowTable] = useState(false);
  const id = useId();
  return (
    <figure style={{ margin: 0 }} aria-labelledby={`${id}-t`} aria-describedby={`${id}-d`}>
      <div className="row" style={{ marginBottom: "var(--s-2)" }}>
        <figcaption id={`${id}-t`} className="t-13 t-semibold" style={{ flex: 1 }}>{title}</figcaption>
        <Button variant="quiet" icon={showTable ? "chart" : "table"} onClick={() => setShowTable((s) => !s)} aria-pressed={showTable}>{showTable ? "Chart" : "Table"}</Button>
      </div>
      <p id={`${id}-d`} className="sr-only">{description}</p>
      {showTable ? table : <div ref={ref} style={{ width: "100%" }}>{w > 0 && children(w)}</div>}
      {legend && legend.length > 1 && <div style={{ marginTop: "var(--s-2)" }}><Legend items={legend.map((l) => ({ label: l.label, color: l.color }))} /></div>}
      {footer && <div className="t-12 t-3" style={{ marginTop: "var(--s-2)" }}>{footer}</div>}
    </figure>
  );
}

/* ------------------------------------------------------------ line chart */
export interface Point { x: string; y: number }
export interface Series { id: string; label: string; points: Point[]; color?: string; dashed?: boolean }
interface LineProps { title: string; description: string; series: Series[]; yFormat?: (v: number) => string; height?: number; logY?: boolean; markers?: { x: string; label: string }[]; footer?: ReactNode }
export function LineChart({ title, description, series, yFormat = (v) => fmtNum(v, 2), height = 240, logY, markers, footer }: LineProps) {
  const [focus, setFocus] = useState<{ s: number; i: number } | null>(null);
  const fs12 = tokenPx("--fs-12", 12);
  const legend = series.map((s, i) => ({ label: s.label, color: s.color || CHART_COLORS[i % CHART_COLORS.length] }));
  const table = (
    <div className="tblwrap"><table className="tbl"><caption>{title}</caption>
      <thead><tr><th scope="col">Date</th>{series.map((s) => <th key={s.id} scope="col" className="num">{s.label}</th>)}</tr></thead>
      <tbody>{(series[0]?.points || []).map((p, i) => <tr key={p.x}><td>{fmtDateShort(p.x)}</td>{series.map((s) => <td key={s.id} className="num">{s.points[i] ? yFormat(s.points[i].y) : ""}</td>)}</tr>)}</tbody>
    </table></div>
  );
  return (
    <ChartFrame title={title} description={description} legend={legend} table={table} footer={footer}>
      {(w) => {
        const all = series.flatMap((s) => s.points);
        if (!all.length) return <p className="t-3">No points</p>;
        const xs = all.map((p) => Date.parse(p.x)).filter((n) => !Number.isNaN(n));
        const ys = all.map((p) => (logY ? Math.log10(Math.max(p.y, 1e-9)) : p.y));
        const xmin = Math.min(...xs), xmax = Math.max(...xs);
        let ymin = Math.min(...ys), ymax = Math.max(...ys);
        if (ymin === ymax) { ymin -= 1; ymax += 1; }
        const ticks = niceTicks(ymin, ymax, 5);
        const yLabels = ticks.map((t) => yFormat(logY ? 10 ** t : t));
        const labelW = Math.max(...yLabels.map((l) => l.length)) * fs12 * 0.62 + 8;
        const M = { l: Math.ceil(labelW), r: 12, t: 12, b: fs12 * 2 + 6 };
        const iw = Math.max(40, w - M.l - M.r), ih = height - M.t - M.b;
        const X = (t: number) => M.l + ((t - xmin) / Math.max(1, xmax - xmin)) * iw;
        const Y = (v: number) => M.t + ih - ((v - ticks[0]) / Math.max(1e-9, ticks[ticks.length - 1] - ticks[0])) * ih;
        const xTickCount = Math.max(2, Math.min(6, Math.floor(iw / (fs12 * 7))));
        const xTicks = Array.from({ length: xTickCount }, (_, i) => xmin + ((xmax - xmin) * i) / (xTickCount - 1));
        const f = focus && series[focus.s]?.points[focus.i];
        return (
          <svg width={w} height={height} role="img" aria-label={title} style={{ display: "block", fontFamily: "var(--font-text)", fontVariantNumeric: "tabular-nums" }}>
            {ticks.map((t, i) => (
              <g key={i}>
                <line x1={M.l} x2={M.l + iw} y1={Y(t)} y2={Y(t)} stroke="var(--chart-grid)" />
                <text x={M.l - 6} y={Y(t)} fontSize={fs12} fill="var(--text-3)" textAnchor="end" dominantBaseline="middle">{yLabels[i]}</text>
              </g>
            ))}
            {xTicks.map((t, i) => (
              <text key={i} x={X(t)} y={height - 4} fontSize={fs12} fill="var(--text-3)"
                textAnchor={i === 0 ? "start" : i === xTicks.length - 1 ? "end" : "middle"}>{fmtDateShort(new Date(t))}</text>
            ))}
            {markers?.map((m, i) => { const t = Date.parse(m.x); return (
              <g key={i}><line x1={X(t)} x2={X(t)} y1={M.t} y2={M.t + ih} stroke="var(--chart-5)" strokeDasharray="4 3" />
                <text x={X(t) + 4} y={M.t + fs12} fontSize={fs12} fill="var(--chart-5)">{m.label}</text></g>); })}
            {series.map((s, si) => {
              const color = s.color || CHART_COLORS[si % CHART_COLORS.length];
              const pts = s.points.map((p) => [X(Date.parse(p.x)), Y(logY ? Math.log10(Math.max(p.y, 1e-9)) : p.y)] as const);
              const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${Math.round(x * 10) / 10},${Math.round(y * 10) / 10}`).join(" ");
              const step = Math.max(1, Math.ceil(pts.length / 60));
              return (
                <g key={s.id}>
                  <path d={d} fill="none" stroke={color} strokeWidth={1.5} strokeDasharray={s.dashed ? "5 3" : undefined} />
                  {pts.map(([x, y], i) => (i % step === 0 || i === pts.length - 1) && (
                    <g key={i}>
                      {focus?.s === si && focus.i === i && <circle cx={x} cy={y} r={4} fill={color} />}
                      {/* a 24 px hit target around each point: focusable by keyboard, tappable by touch */}
                      <circle cx={x} cy={y} r={12} fill="transparent" stroke="transparent" tabIndex={0} role="img"
                        aria-label={`${s.label}, ${fmtDateShort(s.points[i].x)}, ${yFormat(s.points[i].y)}`}
                        onFocus={() => setFocus({ s: si, i })} onBlur={() => setFocus(null)} onMouseEnter={() => setFocus({ s: si, i })} onMouseLeave={() => setFocus(null)}
                        onClick={() => setFocus({ s: si, i })} style={{ cursor: "pointer" }} />
                    </g>
                  ))}
                </g>
              );
            })}
            {f && focus && (() => {
              const x = X(Date.parse(f.x)), y = Y(logY ? Math.log10(Math.max(f.y, 1e-9)) : f.y);
              const text = `${fmtDateShort(f.x)}  ${yFormat(f.y)}`;
              const tw = text.length * fs12 * 0.62 + 12;
              const bx = Math.min(Math.max(M.l, x - tw / 2), M.l + iw - tw);
              const by = y - fs12 * 2.4 < M.t ? y + 10 : y - fs12 * 2.4;
              return (
                <g role="tooltip" aria-live="polite">
                  <rect x={bx} y={by} width={tw} height={fs12 * 1.8} rx={4} fill="var(--panel-raised)" stroke="var(--line-strong)" />
                  <text x={bx + 6} y={by + fs12 * 1.25} fontSize={fs12} fill="var(--text)">{text}</text>
                </g>
              );
            })()}
          </svg>
        );
      }}
    </ChartFrame>
  );
}

/* ------------------------------------------------------------ donut */
export interface Segment { label: string; value: number; color: string }
export function Donut({ title, segments, center, centerSub, size = 96 }: { title: string; segments: Segment[]; center?: string; centerSub?: string; size?: number }) {
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  const r = size / 2 - 10, cx = size / 2, cy = size / 2;
  const fs12 = tokenPx("--fs-12", 12), fs20 = tokenPx("--fs-20", 20);
  let a0 = -Math.PI / 2;
  const desc = segments.map((s) => `${s.label} ${s.value}`).join(", ");
  return (
    <div className="row-3">
      <svg width={size} height={size} role="img" aria-label={`${title}: ${desc}`} data-donut="" style={{ display: "block", flex: "none" }}>
        {segments.filter((s) => s.value > 0).map((s, i) => {
          const frac = s.value / total, a1 = a0 + frac * Math.PI * 2;
          const p = (a: number) => `${Math.round((cx + r * Math.cos(a)) * 100) / 100},${Math.round((cy + r * Math.sin(a)) * 100) / 100}`;
          const el = frac >= 0.9999
            ? <circle key={i} cx={cx} cy={cy} r={r} fill="none" stroke={s.color} strokeWidth={size / 8} />
            : <path key={i} d={`M${p(a0)} A${r},${r} 0 ${frac > 0.5 ? 1 : 0} 1 ${p(a1)}`} fill="none" stroke={s.color} strokeWidth={size / 8} />;
          a0 = a1;
          return el;
        })}
        {center && <text x={cx} y={cy + (centerSub ? 0 : fs20 / 3)} textAnchor="middle" fontSize={size >= 96 ? fs20 : fs12 * 1.2} fontWeight={600} fill="var(--text)" style={{ fontVariantNumeric: "tabular-nums" }}>{center}</text>}
        {centerSub && size >= 96 && <text x={cx} y={cy + fs12 * 1.3} textAnchor="middle" fontSize={fs12} fill="var(--text-3)">{centerSub}</text>}
      </svg>
      <Legend items={segments.map((s) => ({ label: `${s.value} ${s.label}`, color: s.color }))} label={title} />
    </div>
  );
}

/* ------------------------------------------------------------ bar chart */
export interface Bar { label: string; value: number | null; color?: string; note?: string }
export function BarChart({ title, description, bars, format = (v) => fmtNum(v, 2), footer }: { title: string; description: string; bars: Bar[]; format?: (v: number) => string; footer?: ReactNode }) {
  const fs12 = tokenPx("--fs-12", 12), fs13 = tokenPx("--fs-13", 13);
  const table = (
    <div className="tblwrap"><table className="tbl"><caption>{title}</caption>
      <thead><tr><th scope="col">Label</th><th scope="col" className="num">Value</th></tr></thead>
      <tbody>{bars.map((b) => <tr key={b.label}><td>{b.label}</td><td className="num">{b.value === null ? b.note || "" : format(b.value)}</td></tr>)}</tbody>
    </table></div>
  );
  return (
    <ChartFrame title={title} description={description} table={table} footer={footer}>
      {(w) => {
        const max = Math.max(...bars.map((b) => b.value ?? 0), 1e-9);
        const rowH = fs13 * 2.2, labelW = Math.min(w * 0.4, Math.max(...bars.map((b) => b.label.length)) * fs13 * 0.62 + 8);
        const valueW = Math.max(...bars.map((b) => (b.value === null ? (b.note || "").length : format(b.value).length))) * fs12 * 0.62 + 8;
        const iw = Math.max(20, w - labelW - valueW - 8);
        const h = bars.length * rowH;
        return (
          <svg width={w} height={h} role="img" aria-label={title} style={{ display: "block", fontFamily: "var(--font-text)", fontVariantNumeric: "tabular-nums" }}>
            {bars.map((b, i) => {
              const y = i * rowH;
              const bw = b.value === null ? 0 : (b.value / max) * iw;
              return (
                <g key={b.label} tabIndex={0} role="img" aria-label={`${b.label}, ${b.value === null ? b.note || "not available" : format(b.value)}`}>
                  {/* the whole row is the hit target */}
                  <rect x={0} y={y} width={w} height={rowH} fill="transparent" />
                  <text x={labelW - 8} y={y + rowH / 2} fontSize={fs13} fill="var(--text-2)" textAnchor="end" dominantBaseline="middle">{b.label}</text>
                  {b.value !== null && <rect x={labelW} y={y + rowH * 0.2} width={bw} height={rowH * 0.6} rx={2} fill={b.color || "var(--chart-1)"} />}
                  <text x={labelW + bw + 6} y={y + rowH / 2} fontSize={fs12} fill={b.value === null ? "var(--text-3)" : "var(--text)"} dominantBaseline="middle">{b.value === null ? b.note || "" : format(b.value)}</text>
                </g>
              );
            })}
          </svg>
        );
      }}
    </ChartFrame>
  );
}

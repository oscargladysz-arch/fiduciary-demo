/* The analytics, in TypeScript, mirroring src/tark_analytics.py exactly.
 *
 * This is the port the old frontend carried, moved across unchanged in
 * behavior and typed. The conventions are the Python module's and nothing
 * here may drift from them:
 *   - a return is a decimal simple return for one period
 *   - a flow is [date, amount] with a contribution negative and a
 *     distribution or a terminal value positive
 *   - an index series is [date, level], ascending
 *
 * Parity with the Python originals is a test (`math.test.ts`), which runs the
 * same toy cases as `src/test_analytics.py` and then checks the figures this
 * module produces against the ones the engine committed to the record. Two
 * implementations of one calculation disagree unless something checks them.
 */

export type Point = [string, number];
export type Flow = [string, number];

export function parseDate(d: string): number {
  return Date.UTC(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10));
}

export function yearFrac(d0: string, d1: string): number {
  return (parseDate(d1) - parseDate(d0)) / 86400000 / 365.25;
}

export function periodReturns(values: number[]): number[] {
  const out: number[] = [];
  for (let i = 1; i < values.length; i++) out.push(values[i] / values[i - 1] - 1);
  return out;
}

export function monthEndPoints(series: Point[]): Point[] {
  const by: Record<string, Point> = {};
  for (const [d, v] of series) by[d.slice(0, 7)] = [d, v];   // ascending overwrite
  return Object.keys(by).sort().map((k) => by[k]);
}

export function mean(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

export function stdev(xs: number[]): number {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  return Math.sqrt(xs.reduce((a, x) => a + (x - m) ** 2, 0) / (xs.length - 1));
}

export function cumulativeGrowth(returns: number[]): number {
  let g = 1;
  for (const r of returns) g *= 1 + r;
  return g;
}

export function annReturn(returns: number[], periodsPerYear: number): number {
  return cumulativeGrowth(returns) ** (periodsPerYear / returns.length) - 1;
}

export function annVol(returns: number[], periodsPerYear: number): number {
  return stdev(returns) * Math.sqrt(periodsPerYear);
}

export function maxDrawdown(values: number[]): number {
  let peak = values[0];
  let worst = 0;
  for (const v of values) {
    peak = Math.max(peak, v);
    worst = Math.min(worst, v / peak - 1);
  }
  return worst;
}

export function lag1Autocorr(returns: number[]): number {
  const a = returns.slice(1);
  const b = returns.slice(0, -1);
  const ma = mean(a);
  const mb = mean(b);
  let num = 0;
  for (let i = 0; i < a.length; i++) num += (a[i] - ma) * (b[i] - mb);
  const den = Math.sqrt(
    a.reduce((s, x) => s + (x - ma) ** 2, 0)
    * b.reduce((s, y) => s + (y - mb) ** 2, 0));
  return den ? num / den : 0;
}

/** Geltner unsmoothing: the reported series with the appraisal lag removed,
 *  and the lag it was removed at. */
export function desmoothGeltner(returns: number[], rho: number | null = null): [number[], number] {
  const r = rho === null ? lag1Autocorr(returns) : rho;
  const out: number[] = [];
  for (let t = 1; t < returns.length; t++) {
    out.push((returns[t] - r * returns[t - 1]) / (1 - r));
  }
  return [out, r];
}

export function xnpv(rate: number, flows: Flow[]): number {
  const t0 = flows[0][0];
  return flows.reduce((s, [d, amt]) => s + amt / (1 + rate) ** yearFrac(t0, d), 0);
}

export function xirr(flows: Flow[], lo = -0.9999, hi = 10.0, tol = 1e-8): number | null {
  let low = lo;
  let high = hi;
  let fLo = xnpv(low, flows);
  const fHi = xnpv(high, flows);
  if (fLo * fHi > 0) return null;
  for (let i = 0; i < 200; i++) {
    const mid = (low + high) / 2;
    const fMid = xnpv(mid, flows);
    if (Math.abs(fMid) < tol) return mid;
    if (fLo * fMid < 0) {
      high = mid;
    } else {
      low = mid;
      fLo = fMid;
    }
  }
  return (low + high) / 2;
}

/** The level on or before a date. A date before the series starts is refused
 *  rather than silently anchored at the first observation. */
export function levelOn(index: Point[], d: string): number {
  if (d < index[0][0]) throw new Error(`date ${d} is before the series starts (${index[0][0]})`);
  let lvl = index[0][1];
  for (const [di, vi] of index) {
    if (di <= d) lvl = vi;
    else break;
  }
  return lvl;
}

export interface Window { d0: string; d1: string; note: string }

/** A fund window clipped to what the index covers, and what was clipped. */
export function effectiveWindow(d0: string, d1: string, index: Point[]): Window {
  const i0 = index[0][0];
  const i1 = index[index.length - 1][0];
  const e0 = d0 > i0 ? d0 : i0;
  const e1 = d1 < i1 ? d1 : i1;
  if (e0 >= e1) throw new Error(`window ${d0} to ${d1} does not overlap the series (${i0} to ${i1})`);
  const parts: string[] = [];
  if (e0 !== d0) parts.push(`the comparison series begins ${i0}`);
  if (e1 !== d1) parts.push(`the comparison series ends ${i1}`);
  return { d0: e0, d1: e1, note: parts.length ? `clipped: ${parts.join(", ")}` : "" };
}

/** [start, end] per fiscal year, from a window and a count. */
export function fiscalYearBounds(fyWindow: string[], n: number): [string, string][] {
  const [w0, w1] = fyWindow;
  const y0 = +w0.slice(0, 4);
  const starts = Array.from({ length: n }, (_, i) => `${y0 + i}${w0.slice(4)}`);
  return starts.map((s, i) => [s, i + 1 < n ? starts[i + 1] : w1] as [string, string]);
}

/** Kaplan-Schoar public market equivalent. Only ever against a public market
 *  series: against an appraisal-based composite this ratio is not a public
 *  market equivalent and must not be called one. */
export function ksPme(flows: Flow[], index: Point[]): number {
  const T = flows[flows.length - 1][0];
  const iT = levelOn(index, T);
  let fvPos = 0;
  let fvNeg = 0;
  for (const [d, amt] of flows) {
    if (amt > 0) fvPos += (amt * iT) / levelOn(index, d);
    if (amt < 0) fvNeg += (-amt * iT) / levelOn(index, d);
  }
  return fvPos / fvNeg;
}

/** An illustrative flow schedule: one unit of cash at the window start and at
 *  each fund month end strictly inside it, valued once at the window end. */
export function monthlyScheduleFlows(fund: Point[], d0: string, d1: string): Flow[] {
  const win = fund.filter(([d]) => d >= d0 && d <= d1);
  const dates = [d0, ...monthEndPoints(win).map(([d]) => d).filter((d) => d > d0 && d < d1)];
  let units = 0;
  const flows: Flow[] = [];
  for (const d of dates) {
    units += 1 / levelOn(fund, d);
    flows.push([d, -1.0]);
  }
  flows.push([d1, units * levelOn(fund, d1)]);
  return flows;
}

/** The yearly edge over the index, as an annualized excess rate. */
export function directAlpha(flows: Flow[], index: Point[]): number | null {
  const T = flows[flows.length - 1][0];
  const iT = levelOn(index, T);
  const scaled: Flow[] = flows.map(([d, amt]) => [d, (amt * iT) / levelOn(index, d)]);
  return xirr(scaled);
}

/** A fund's fiscal-year returns as a flow schedule against an index: a unit in
 *  at each year's start, the compounded value out at the end. */
export function fiscalYearFlows(fyReturns: number[], fyWindow: string[]): Flow[] {
  const bounds = fiscalYearBounds(fyWindow, fyReturns.length);
  let acc = 1;
  for (const r of fyReturns) acc *= 1 + r;
  return [[bounds[0][0], -1], [bounds[bounds.length - 1][1], acc]];
}

export function calendarYearReturns(series: Point[]): [string, number][] {
  const lastByYear: Record<string, number> = {};
  for (const [d, v] of series) lastByYear[d.slice(0, 4)] = v;
  const years = Object.keys(lastByYear).sort();
  const out: [string, number][] = [];
  let prev = series[0][1];
  for (const y of years) {
    out.push([y, lastByYear[y] / prev - 1]);
    prev = lastByYear[y];
  }
  return out;
}

export interface Episode { peak_date: string; trough_date: string; depth: number; recovery_date: string | null }

export function drawdownEpisodes(series: Point[], topN = 3): Episode[] {
  const episodes: Episode[] = [];
  let i = 0;
  const n = series.length;
  while (i < n - 1) {
    const [peakD, peakV] = series[i];
    let j = i + 1;
    let troughD = peakD;
    let troughV = peakV;
    let recovery: string | null = null;
    while (j < n) {
      const [d, v] = series[j];
      if (v >= peakV) { recovery = d; break; }
      if (v < troughV) { troughD = d; troughV = v; }
      j++;
    }
    if (troughV < peakV) {
      episodes.push({ peak_date: peakD, trough_date: troughD, depth: troughV / peakV - 1, recovery_date: recovery });
    }
    i = j > i ? j : i + 1;
  }
  episodes.sort((a, b) => a.depth - b.depth);
  return episodes.slice(0, topN);
}

export function rollingReturns(returns: number[], window: number): number[] {
  const out: number[] = [];
  for (let i = window; i <= returns.length; i++) out.push(cumulativeGrowth(returns.slice(i - window, i)) - 1);
  return out;
}

export function rollingVol(returns: number[], window: number, periodsPerYear: number): number[] {
  const out: number[] = [];
  for (let i = window; i <= returns.length; i++) out.push(annVol(returns.slice(i - window, i), periodsPerYear));
  return out;
}

export function beta(fundReturns: number[], indexReturns: number[]): number {
  const n = Math.min(fundReturns.length, indexReturns.length);
  const f = fundReturns.slice(0, n);
  const x = indexReturns.slice(0, n);
  const mf = mean(f);
  const mx = mean(x);
  let cov = 0;
  let vr = 0;
  for (let i = 0; i < n; i++) {
    cov += (f[i] - mf) * (x[i] - mx);
    vr += (x[i] - mx) ** 2;
  }
  cov /= n - 1;
  vr /= n - 1;
  return vr ? cov / vr : 0;
}

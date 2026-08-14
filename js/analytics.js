/* Tark analytics — JavaScript port of src/tark_analytics.py.
 * Mirrors the Python semantics EXACTLY (same conventions, same algorithms):
 *   - returns are decimal per-period simple returns
 *   - flows are [dateISO, amount]: contributions NEGATIVE, distributions and
 *     terminal NAV POSITIVE
 *   - index series are [dateISO, level] ascending
 * Parity with the Python originals is enforced by tests/test_frontend.py,
 * which runs the SAME toy cases as src/test_analytics.py through this file.
 */

export function parseDate(d) {
  return Date.UTC(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10));
}

export function yearFrac(d0, d1) {
  return (parseDate(d1) - parseDate(d0)) / 86400000 / 365.25;
}

export function periodReturns(values) {
  const out = [];
  for (let i = 1; i < values.length; i++) out.push(values[i] / values[i - 1] - 1);
  return out;
}

export function monthEndPoints(series) {
  const by = {};
  for (const [d, v] of series) by[d.slice(0, 7)] = [d, v]; // ascending overwrite
  return Object.keys(by).sort().map((k) => by[k]);
}

export function mean(xs) {
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

export function stdev(xs) {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  return Math.sqrt(xs.reduce((a, x) => a + (x - m) ** 2, 0) / (xs.length - 1));
}

export function cumulativeGrowth(returns) {
  let g = 1;
  for (const r of returns) g *= 1 + r;
  return g;
}

export function annReturn(returns, periodsPerYear) {
  return cumulativeGrowth(returns) ** (periodsPerYear / returns.length) - 1;
}

export function annVol(returns, periodsPerYear) {
  return stdev(returns) * Math.sqrt(periodsPerYear);
}

export function maxDrawdown(values) {
  let peak = values[0];
  let worst = 0;
  for (const v of values) {
    peak = Math.max(peak, v);
    worst = Math.min(worst, v / peak - 1);
  }
  return worst;
}

export function lag1Autocorr(returns) {
  const a = returns.slice(1);
  const b = returns.slice(0, -1);
  const ma = mean(a);
  const mb = mean(b);
  let num = 0;
  for (let i = 0; i < a.length; i++) num += (a[i] - ma) * (b[i] - mb);
  const den = Math.sqrt(
    a.reduce((s, x) => s + (x - ma) ** 2, 0) *
    b.reduce((s, y) => s + (y - mb) ** 2, 0));
  return den ? num / den : 0;
}

export function desmoothGeltner(returns, rho = null) {
  if (rho === null) rho = lag1Autocorr(returns);
  const out = [];
  for (let t = 1; t < returns.length; t++) {
    out.push((returns[t] - rho * returns[t - 1]) / (1 - rho));
  }
  return [out, rho];
}

export function xnpv(rate, flows) {
  const t0 = flows[0][0];
  return flows.reduce(
    (s, [d, amt]) => s + amt / (1 + rate) ** yearFrac(t0, d), 0);
}

export function xirr(flows, lo = -0.9999, hi = 10.0, tol = 1e-8) {
  let fLo = xnpv(lo, flows);
  const fHi = xnpv(hi, flows);
  if (fLo * fHi > 0) return null;
  for (let i = 0; i < 200; i++) {
    const mid = (lo + hi) / 2;
    const fMid = xnpv(mid, flows);
    if (Math.abs(fMid) < tol) return mid;
    if (fLo * fMid < 0) {
      hi = mid;
    } else {
      lo = mid;
      fLo = fMid;
    }
  }
  return (lo + hi) / 2;
}

export function levelOn(index, d) {
  let lvl = index[0][1];
  for (const [di, vi] of index) {
    if (di <= d) lvl = vi;
    else break;
  }
  return lvl;
}

export function ksPme(flows, index) {
  const T = flows[flows.length - 1][0];
  const iT = levelOn(index, T);
  let fvPos = 0;
  let fvNeg = 0;
  for (const [d, amt] of flows) {
    if (amt > 0) fvPos += amt * iT / levelOn(index, d);
    if (amt < 0) fvNeg += -amt * iT / levelOn(index, d);
  }
  return fvPos / fvNeg;
}

export function directAlpha(flows, index) {
  const T = flows[flows.length - 1][0];
  const iT = levelOn(index, T);
  const scaled = flows.map(([d, amt]) => [d, amt * iT / levelOn(index, d)]);
  return xirr(scaled);
}

/* ---- workbench table math (ports of the Python originals; parity-tested
 * on the same toy cases plus committed real-data checkpoints) ---- */
export function calendarYearReturns(series) {
  const lastByYear = {};
  for (const [d, v] of series) lastByYear[d.slice(0, 4)] = v;
  const years = Object.keys(lastByYear).sort();
  const out = [];
  let prev = series[0][1];
  for (const y of years) {
    out.push([y, lastByYear[y] / prev - 1]);
    prev = lastByYear[y];
  }
  return out;
}

export function drawdownEpisodes(series, topN = 3) {
  const episodes = [];
  let i = 0;
  const n = series.length;
  while (i < n - 1) {
    const [peakD, peakV] = series[i];
    let j = i + 1;
    let troughD = peakD; let troughV = peakV;
    let recovery = null;
    while (j < n) {
      const [d, v] = series[j];
      if (v >= peakV) { recovery = d; break; }
      if (v < troughV) { troughD = d; troughV = v; }
      j++;
    }
    if (troughV < peakV) {
      episodes.push({ peak_date: peakD, trough_date: troughD,
        depth: troughV / peakV - 1, recovery_date: recovery });
    }
    i = j > i ? j : i + 1;
  }
  episodes.sort((a, b) => a.depth - b.depth);
  return episodes.slice(0, topN);
}

export function rollingReturns(returns, window) {
  const out = [];
  for (let i = window; i <= returns.length; i++) {
    out.push(cumulativeGrowth(returns.slice(i - window, i)) - 1);
  }
  return out;
}

export function rollingVol(returns, window, periodsPerYear) {
  const out = [];
  for (let i = window; i <= returns.length; i++) {
    out.push(annVol(returns.slice(i - window, i), periodsPerYear));
  }
  return out;
}

export function beta(fundReturns, indexReturns) {
  const n = Math.min(fundReturns.length, indexReturns.length);
  const f = fundReturns.slice(0, n); const x = indexReturns.slice(0, n);
  const mf = mean(f); const mx = mean(x);
  let cov = 0; let vr = 0;
  for (let i = 0; i < n; i++) {
    cov += (f[i] - mf) * (x[i] - mx);
    vr += (x[i] - mx) ** 2;
  }
  cov /= n - 1; vr /= n - 1;
  return vr ? cov / vr : 0;
}

// expose for Playwright parity tests (page.evaluate)
window.TarkMath = {
  parseDate, yearFrac, periodReturns, monthEndPoints, mean, stdev,
  cumulativeGrowth, annReturn, annVol, maxDrawdown, lag1Autocorr,
  desmoothGeltner, xnpv, xirr, levelOn, ksPme, directAlpha,
  calendarYearReturns, drawdownEpisodes, rollingReturns, rollingVol, beta,
};

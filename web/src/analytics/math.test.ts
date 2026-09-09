/* Parity: the analytics in the browser and the analytics in the engine are
 * the same calculation.
 *
 * The first half runs the same toy cases as `src/test_analytics.py`, so a
 * change to either implementation that moves a figure fails here. The second
 * half runs against the record: the selections the engine committed carry the
 * public market equivalent and the yearly edge it computed, and this module
 * recomputes them from the same inputs and compares.
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import {
  cumulativeGrowth, desmoothGeltner, directAlpha, effectiveWindow, fiscalYearBounds,
  ksPme, levelOn, maxDrawdown, monthEndPoints, monthlyScheduleFlows,
  periodReturns, xirr,
} from "./math";
import type { Flow, Point } from "./math";

const DATA = join(__dirname, "..", "..", "..", "site", "data");

const idxUp: Point[] = [["2020-01-01", 100], ["2021-01-01", 150]];
const idxFlat: Point[] = [["2020-01-01", 100], ["2021-01-01", 100]];
const track: Flow[] = [["2020-01-01", -100], ["2021-01-01", 150]];
const beat: Flow[] = [["2020-01-01", -100], ["2021-01-01", 180]];
const mixed: Flow[] = [["2020-01-01", -100], ["2020-07-01", 30], ["2021-01-01", 90]];

describe("the same toy cases the engine's own tests run", () => {
  it("takes a return per period", () => {
    expect(periodReturns([100, 110, 99])[0]).toBeCloseTo(0.1, 12);
    expect(periodReturns([100, 110, 99])[1]).toBeCloseTo(-0.1, 12);
  });

  it("measures the worst fall from a peak", () => {
    expect(maxDrawdown([100, 120, 60, 90])).toBeCloseTo(-0.5, 12);
  });

  it("compounds returns", () => {
    expect(cumulativeGrowth([0.1, -0.1])).toBeCloseTo(0.99, 12);
  });

  it("keeps the last observation of each month", () => {
    expect(monthEndPoints([["2024-01-05", 1], ["2024-01-31", 2], ["2024-02-10", 3], ["2024-02-28", 4]]))
      .toEqual([["2024-01-31", 2], ["2024-02-28", 4]]);
  });

  it("solves a one-year ten per cent return", () => {
    expect(xirr([["2020-01-01", -100], ["2021-01-01", 110]]) as number).toBeCloseTo(0.1, 3);
  });

  it("gives one and zero when the fund tracks the index", () => {
    expect(ksPme(track, idxUp)).toBeCloseTo(1.0, 12);
    expect(directAlpha(track, idxUp) as number).toBeCloseTo(0, 3);
  });

  it("gives the outperformance when the fund beats the index", () => {
    expect(ksPme(beat, idxUp)).toBeCloseTo(1.2, 12);
    expect(directAlpha(beat, idxUp) as number).toBeGreaterThan(0.1);
  });

  it("reduces to the simple multiple against a flat index", () => {
    expect(ksPme(mixed, idxFlat)).toBeCloseTo(1.2, 12);
  });

  it("recovers the true series from an appraisal-lagged one", () => {
    const trueSer = [0.02, -0.01, 0.03, 0.015, -0.005, 0.02, 0.01, 0.025];
    const rho = 0.4;
    const obs = [trueSer[0]];
    for (let t = 1; t < trueSer.length; t++) obs.push((1 - rho) * trueSer[t] + rho * obs[t - 1]);
    const [rec] = desmoothGeltner(obs, rho);
    expect(rec[0]).toBeCloseTo(-0.01, 12);
    expect(rec[rec.length - 1]).toBeCloseTo(0.025, 12);
  });

  it("refuses a level before the series starts rather than anchoring at the first one", () => {
    expect(() => levelOn(idxUp, "2019-06-30")).toThrow();
    expect(levelOn(idxUp, "2020-06-30")).toBe(100);
  });

  it("clips a window to what the series covers and says what it clipped", () => {
    const w = effectiveWindow("2019-01-01", "2022-01-01", idxUp);
    expect(w.d0).toBe("2020-01-01");
    expect(w.d1).toBe("2021-01-01");
    expect(w.note).toContain("begins");
    expect(effectiveWindow("2020-06-01", "2020-12-01", idxUp).note).toBe("");
  });

  it("splits a window into fiscal years the way the engine does", () => {
    expect(fiscalYearBounds(["2021-03-31", "2026-03-31"], 5)).toEqual([
      ["2021-03-31", "2022-03-31"], ["2022-03-31", "2023-03-31"], ["2023-03-31", "2024-03-31"],
      ["2024-03-31", "2025-03-31"], ["2025-03-31", "2026-03-31"],
    ]);
  });

  it("builds an illustrative schedule that buys at each month end and values once", () => {
    const fund: Point[] = [["2020-01-31", 10], ["2020-02-29", 11], ["2020-03-31", 12]];
    const flows = monthlyScheduleFlows(fund, "2020-01-31", "2020-03-31");
    expect(flows.filter(([, a]) => a < 0)).toHaveLength(2);
    expect(flows[flows.length - 1][0]).toBe("2020-03-31");
    expect(flows[flows.length - 1][1]).toBeCloseTo((1 / 10 + 1 / 11) * 12, 12);
  });
});

/* ------------------------------------------------- against the record itself */
interface Comparison {
  kind?: string; ks_pme?: number; direct_alpha_pct?: number; series_id?: string;
  window?: string; fund_return_source?: string;
}

function selections(): { key: string; selection: Record<string, unknown> }[] {
  const root = join(DATA, "product");
  if (!existsSync(root)) return [];
  const out: { key: string; selection: Record<string, unknown> }[] = [];
  for (const key of readdirSync(root)) {
    const file = join(root, key, "selection.json");
    if (!existsSync(file)) continue;
    const body = JSON.parse(readFileSync(file, "utf8"));
    if (body.selection) out.push({ key, selection: body.selection });
  }
  return out;
}

function daily(seriesId: string): Point[] | null {
  const file = join(DATA, "daily", `${seriesId}.json`);
  if (!existsSync(file)) return null;
  const body = JSON.parse(readFileSync(file, "utf8"));
  const p = body.points;
  if (!p || !p.base) return null;
  const base = Date.parse(`${p.base}T00:00:00Z`);
  const day = 24 * 60 * 60 * 1000;
  return p.d.map((offset: number, i: number) =>
    [new Date(base + offset * day).toISOString().slice(0, 10), p.v[i]] as Point);
}

describe("against the figures the engine committed", () => {
  const found = selections();

  it("finds the committed selections", () => {
    expect(found.length).toBeGreaterThan(0);
  });

  it("recomputes the public market equivalent the record carries, from the record's own inputs", () => {
    const lab = JSON.parse(readFileSync(join(DATA, "lab.json"), "utf8"));
    const checked: string[] = [];
    const wrong: string[] = [];
    const skipped: string[] = [];
    for (const { key, selection } of found) {
      const ref = selection.reference_comparison as
        { series_id?: string; comparison?: Comparison } | undefined;
      const slotK = (selection.slot_k || {}) as { selected?: { series_id?: string; comparison?: Comparison } };
      const picked = slotK.selected?.comparison ? slotK.selected : ref;
      const comp = picked?.comparison;
      const seriesId = picked?.series_id;
      const profile = lab.profiles?.[key];
      if (!comp || comp.kind !== "series" || typeof comp.ks_pme !== "number" || !seriesId) {
        skipped.push(`${key}: no series comparison on record`);
        continue;
      }
      const index = daily(seriesId);
      if (!index) { skipped.push(`${key}: the comparison series is not held`); continue; }
      if (!profile?.fy_returns || !profile?.fy_window) {
        skipped.push(`${key}: the return input is not fiscal-year returns`);
        continue;
      }
      // the engine clips a fund window to what the comparison series covers and
      // records the window it actually used: this reproduces that window rather
      // than assuming the fund's own, which is where the two would silently part
      const stated = (comp.window || "").split(" to ");
      if (stated.length !== 2) { skipped.push(`${key}: the comparison records no window`); continue; }
      const bounds = fiscalYearBounds(profile.fy_window, profile.fy_returns.length)
        .map((b, i) => ({ b, r: profile.fy_returns[i] }))
        .filter((x) => x.b[0] >= stated[0] && x.b[1] <= stated[1]);
      if (!bounds.length) { skipped.push(`${key}: no whole fiscal year inside the recorded window`); continue; }
      let acc = 1;
      for (const x of bounds) acc *= 1 + x.r;
      const flows: Flow[] = [[bounds[0].b[0], -1], [bounds[bounds.length - 1].b[1], acc]];
      const mine = ksPme(flows, index);
      checked.push(key);
      if (Math.abs(mine - comp.ks_pme) > 5e-3) wrong.push(`${key}: ${mine} vs ${comp.ks_pme}`);
    }
    // what could not be checked is named rather than passed over: a fund whose
    // return input is a held series or a single annualized figure is compared a
    // different way, and those are covered by the toy cases above
    expect({ wrong, checkedAtLeast: checked.length > 0 })
      .toEqual({ wrong: [], checkedAtLeast: true });
    expect(checked.length + skipped.length).toBe(found.length);
  });

  it("agrees with the engine on every daily series it holds", () => {
    const root = join(DATA, "daily");
    if (!existsSync(root)) return;
    for (const file of readdirSync(root)) {
      const points = daily(file.replace(".json", ""));
      expect(points).not.toBeNull();
      const p = points as Point[];
      expect(p.length).toBeGreaterThan(1);
      // ascending, and every level a positive number
      for (let i = 1; i < p.length; i++) expect(p[i][0] > p[i - 1][0]).toBe(true);
      expect(p.every(([, v]) => typeof v === "number" && v > 0)).toBe(true);
      // a level on or before a date the series covers is the series' own level
      expect(levelOn(p, p[p.length - 1][0])).toBe(p[p.length - 1][1]);
    }
  });
});

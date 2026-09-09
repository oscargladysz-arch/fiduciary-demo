/* Parity: what the browser computes and what the record holds are the same
 * figures.
 *
 * The liquidity panel recomputes as a reader moves an input, which means there
 * are now two implementations of one calculation, the engine that wrote the
 * record and the arithmetic the panel runs. Two implementations of one
 * calculation disagree unless something checks them, and the thing that checks
 * them is this file: it runs the panel's arithmetic against every committed
 * match at the record's own filed inputs and compares the result to the
 * figures the record carries.
 *
 * If this file fails, a figure on the screen and the same figure in the
 * document for that plan are different numbers. That is the failure it exists
 * to catch. */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { compute } from "./liquidity";
import type { Inputs, Match } from "./liquidity";

const CHUNKS = join(__dirname, "..", "..", "..", "site", "data", "product");

function everyMatch(): { name: string; match: Match }[] {
  const out: { name: string; match: Match }[] = [];
  for (const product of readdirSync(CHUNKS)) {
    const dir = join(CHUNKS, product, "liquidity");
    let files: string[] = [];
    try { files = readdirSync(dir); } catch { continue; }
    for (const file of files) {
      const body = JSON.parse(readFileSync(join(dir, file), "utf8"));
      if (body.match) out.push({ name: `${product} ${file.replace(".json", "")}`, match: body.match });
    }
  }
  return out;
}

/** The record's own filed inputs, which is where the panel starts. */
function filedInputs(m: Match): Inputs {
  const sc = m.scenario || {};
  const pi = m.plan_inputs || {};
  return {
    allocation: sc.allocation_pct_of_plan ?? 5,
    outflow: sc.filed_outflow_proxy_pct ?? pi.filed_outflow_proxy_pct ?? 0,
    tail: sc.tail_annual_turnover_pct ?? 0,
    active: sc.active_annual_turnover_pct ?? 0,
  };
}

const matches = everyMatch();

describe("the panel's arithmetic against the record", () => {
  it("finds every committed match", () => {
    expect(matches.length).toBeGreaterThan(0);
  });

  it("reproduces the position, the demand and the stressed demand the record carries", () => {
    const wrong: string[] = [];
    for (const { name, match } of matches) {
      const live = compute(filedInputs(match), match);
      const sc = match.scenario || {};
      const near = (a: number | null | undefined, b: number | null | undefined, tol: number) =>
        a === null || a === undefined || b === null || b === undefined || Math.abs(a - b) <= tol;
      if (typeof sc.plan_allocation_usd === "number" && !near(live.positionUsd, sc.plan_allocation_usd, 1)) {
        wrong.push(`${name}: position ${live.positionUsd} vs ${sc.plan_allocation_usd}`);
      }
      // the rate the record filed is the rate the panel starts from
      if (typeof sc.filed_outflow_proxy_pct === "number" && !near(live.filedPct, sc.filed_outflow_proxy_pct, 1e-9)) {
        wrong.push(`${name}: filed rate ${live.filedPct} vs ${sc.filed_outflow_proxy_pct}`);
      }
      // the turnover assumption is the two rates weighted by the tail share
      const pi = match.plan_inputs || {};
      if (typeof pi.tail_share === "number") {
        const inputs = filedInputs(match);
        const expected = inputs.tail * pi.tail_share + inputs.active * (1 - pi.tail_share);
        if (!near(live.turnoverPct, expected, 1e-9)) {
          wrong.push(`${name}: turnover ${live.turnoverPct} vs ${expected}`);
        }
      }
      // the stressed demand is the filed rate plus what the stress adds
      if (!near(live.stressedPct, live.filedPct + live.incrementPct, 1e-9)) {
        wrong.push(`${name}: stressed ${live.stressedPct} is not the filed rate plus the increment`);
      }
    }
    expect(wrong).toEqual([]);
  });

  it("reproduces the rung the record recorded, for every match", () => {
    const wrong: string[] = [];
    for (const { name, match } of matches) {
      const recorded = match.scenario?.drivers?.rung;
      if (!recorded) continue;
      const live = compute(filedInputs(match), match);
      if (live.rung !== recorded) wrong.push(`${name}: ${live.rung} vs ${recorded}`);
    }
    expect(wrong).toEqual([]);
  });

  it("puts every figure in dollars on the same position", () => {
    for (const { match } of matches) {
      const live = compute(filedInputs(match), match);
      if (live.positionUsd === null) continue;
      for (const [pct, usd] of [[live.filedPct, live.filedUsd],
        [live.turnoverPct, live.turnoverUsd], [live.stressedPct, live.stressedUsd]] as const) {
        expect(usd).not.toBeNull();
        expect(Math.abs((usd as number) - (live.positionUsd * pct) / 100)).toBeLessThan(1e-6);
      }
    }
  });
});

describe("the arithmetic itself", () => {
  const bare: Match = {
    plan_inputs: { net_assets: 1_000_000, tail_share: 0.5 },
    scenario: { annual_wrapper_capacity_pct: 20, allocation_pct_of_plan: 10,
      filed_outflow_proxy_pct: 8, tail_annual_turnover_pct: 20, active_annual_turnover_pct: 4 },
    stressed_scenario: { multiples: { tail_multiple: 2, active_multiple: 1.5 } },
    wrapper_facts: { cadence_per_year: 4, cap_pct: 5, annual_capacity_pct: 20 },
  };
  const inputs: Inputs = { allocation: 10, outflow: 8, tail: 20, active: 4 };

  it("takes the position from the allocation", () => {
    expect(compute(inputs, bare).positionUsd).toBe(100_000);
  });

  it("weights the turnover by the tail share", () => {
    // 20 * 0.5 + 4 * 0.5
    expect(compute(inputs, bare).turnoverPct).toBeCloseTo(12, 9);
  });

  it("adds only what the stress adds, never the whole stressed turnover", () => {
    // stressed turnover 20*2*0.5 + 4*1.5*0.5 = 23, increment 23 - 12 = 11
    const live = compute(inputs, bare);
    expect(live.incrementPct).toBeCloseTo(11, 9);
    expect(live.stressedPct).toBeCloseTo(19, 9);
  });

  it("reads the rung off the capacity rather than guessing it", () => {
    expect(compute(inputs, bare).rung).toBe("none");
    expect(compute({ ...inputs, outflow: 25 }, bare).rung).toBe("base");
    expect(compute({ ...inputs, tail: 40 }, bare).rung).toBe("stress");
  });

  it("says the capacity is unknown rather than assuming one", () => {
    const noCap: Match = { ...bare, scenario: { ...bare.scenario, annual_wrapper_capacity_pct: null },
      wrapper_facts: { ...bare.wrapper_facts, annual_capacity_pct: null, cap_pct: null } };
    const live = compute(inputs, noCap);
    expect(live.capacityPct).toBeNull();
    expect(live.rung).toBe("unknown");
  });

  it("treats an exchange-traded wrapper as its own rung", () => {
    const listed: Match = { ...bare, wrapper_facts: { ...bare.wrapper_facts, exchange: true } };
    expect(compute(inputs, listed).rung).toBe("exchange");
  });

  it("divides a yearly rate by the offers a year, and only when there are offers", () => {
    const live = compute(inputs, bare);
    expect(live.windows).toBe(4);
    expect(live.filedPerWindow).toBeCloseTo(2, 9);
    const noWindows: Match = { ...bare, wrapper_facts: { ...bare.wrapper_facts, cap_pct: null, cadence_per_year: 0 } };
    expect(compute(inputs, noWindows).filedPerWindow).toBeNull();
  });

  it("returns nothing rather than zero when the plan's net assets are not on record", () => {
    const noAssets: Match = { ...bare, plan_inputs: { tail_share: 0.5 } };
    const live = compute(inputs, noAssets);
    expect(live.positionUsd).toBeNull();
    expect(live.filedUsd).toBeNull();
  });
});

/* The liquidity arithmetic, on its own so it can be checked on its own.
 *
 * Every figure the liquidity panel shows is this function's output, and the
 * panel holds one state that feeds it. It lives here rather than inside the
 * view because the figures it produces have to agree with the engine that
 * wrote the record, and that agreement is a test rather than a screenshot:
 * the parity suite runs this function against every committed match at the
 * filed inputs and compares it to the figures the record carries.
 *
 * Nothing here reads the document, fetches anything, or formats anything. It
 * takes the positions a reader is holding and one match, and returns figures.
 */

/* The liquidity chunk carries its match as an open map, so the fields this
 * panel reads are named here rather than in the shared types. */
export interface FiledOutflow {
  formula?: string; inputs?: Record<string, number>; label?: string;
  plan_year?: string; rate_pct?: number; source?: string; what?: string;
}
export interface PlanInputs {
  filed_outflow_proxy_pct?: number; net_assets?: number; plan_year?: string;
  separated_with_balances?: number; tail_share?: number; tail_share_pct?: number;
}
export interface WindowFacts { cap_per_window_pct?: number; period?: string; windows_per_year?: number }
export interface Drivers {
  binding_cap?: { pct?: number; period?: string } | null;
  cadence_per_year?: number; rung?: string; sentence?: string; window?: WindowFacts | null;
}
export interface FundCapacity {
  available?: boolean; annual_capacity_usd?: number; fund_net_assets_usd?: number;
  net_assets_approx?: boolean; net_assets_cell?: string;
}
export interface Scenario {
  active_annual_turnover_pct?: number; allocation_pct_of_plan?: number;
  annual_wrapper_capacity_pct?: number | null; capacity_note?: string; drivers?: Drivers;
  filed_outflow_proxy_pct?: number; fund_capacity?: FundCapacity; plan_allocation_usd?: number;
  schedule_h_lines?: string[]; tail_annual_turnover_pct?: number;
}
export interface Stressed { multiples?: { active_multiple?: number; tail_multiple?: number }; outcome?: string }
export interface WrapperFacts {
  annual_capacity_pct?: number | null; cadence_per_year?: number; cap_base?: string;
  cap_pct?: number | null; cap_period?: string | null; caps_label?: string; dealing_label?: string;
  early_fee?: string; exchange?: boolean; gate_history?: boolean; net_assets_cell?: string;
  program_status?: string | null; program_status_as_of?: string | null;
}
export interface Match {
  citations?: string[]; filed_outflow?: FiledOutflow; layers?: string; missing_facts?: string[];
  missing_facts_labels?: string[]; plan_direction?: string; plan_display_label?: string;
  plan_inputs?: PlanInputs; scenario?: Scenario; scenario_verdict?: string; stressed_scenario?: Stressed;
  structural_reasons?: string[]; verdict?: string; wrapper_facts?: WrapperFacts;
  /* the sentences the document for this plan carries, unedited */
  scenario_reasons?: string[];
}

export interface Inputs { allocation: number; outflow: number; tail: number; active: number }
/* ------------------------------------------------------- the arithmetic */
export interface Live {
  positionUsd: number | null;
  filedPct: number; turnoverPct: number; stressedPct: number; incrementPct: number;
  filedUsd: number | null; turnoverUsd: number | null; stressedUsd: number | null;
  capacityPct: number | null; capacityUsd: number | null;
  windows: number | null; capPerWindowPct: number | null;
  filedPerWindow: number | null; turnoverPerWindow: number | null; stressedPerWindow: number | null;
  headroomPct: number | null; fundSharePct: number | null;
  rung: string;
}

export function compute(inputs: Inputs, m: Match): Live {
  const pi = m.plan_inputs || {};
  const sc = m.scenario || {};
  const wf = m.wrapper_facts || {};
  const mult = m.stressed_scenario?.multiples || {};
  const tailShare = typeof pi.tail_share === "number" ? pi.tail_share : 0;
  const tailMult = typeof mult.tail_multiple === "number" ? mult.tail_multiple : 1;
  const activeMult = typeof mult.active_multiple === "number" ? mult.active_multiple : 1;
  const netAssets = typeof pi.net_assets === "number" ? pi.net_assets : null;

  const positionUsd = netAssets === null ? null : (netAssets * inputs.allocation) / 100;
  const turnoverPct = inputs.tail * tailShare + inputs.active * (1 - tailShare);
  const stressedTurnover = inputs.tail * tailMult * tailShare + inputs.active * activeMult * (1 - tailShare);
  const incrementPct = stressedTurnover - turnoverPct;
  const stressedPct = inputs.outflow + incrementPct;

  const capacityPct = typeof sc.annual_wrapper_capacity_pct === "number" ? sc.annual_wrapper_capacity_pct
    : typeof wf.annual_capacity_pct === "number" ? wf.annual_capacity_pct : null;
  /* a wrapper can carry two caps, and the binding one decides the window: the
   * record names it, so it is read rather than picked here */
  const bound = sc.drivers?.window?.cap_per_window_pct ?? sc.drivers?.binding_cap?.pct;
  const capPerWindowPct = typeof bound === "number" ? bound
    : typeof wf.cap_pct === "number" ? wf.cap_pct : null;
  const perYear = sc.drivers?.window?.windows_per_year;
  const windows = typeof perYear === "number" ? perYear
    : typeof wf.cadence_per_year === "number" && capPerWindowPct !== null ? wf.cadence_per_year : null;

  const share = (pct: number) => (positionUsd === null ? null : (positionUsd * pct) / 100);
  const perWindow = (pct: number) => (windows && windows > 0 && capPerWindowPct !== null ? pct / windows : null);
  const fundCapacityUsd = m.scenario?.fund_capacity?.annual_capacity_usd;
  const filedUsd = share(inputs.outflow);

  return {
    positionUsd,
    filedPct: inputs.outflow, turnoverPct, stressedPct, incrementPct,
    filedUsd, turnoverUsd: share(turnoverPct), stressedUsd: share(stressedPct),
    capacityPct, capacityUsd: capacityPct === null ? null : share(capacityPct),
    windows, capPerWindowPct,
    filedPerWindow: perWindow(inputs.outflow),
    turnoverPerWindow: perWindow(turnoverPct),
    stressedPerWindow: perWindow(stressedPct),
    headroomPct: capacityPct === null ? null : capacityPct - stressedPct,
    fundSharePct: filedUsd !== null && typeof fundCapacityUsd === "number" && fundCapacityUsd > 0
      ? (filedUsd / fundCapacityUsd) * 100 : null,
    rung: wf.exchange ? "exchange"
      : capacityPct === null ? "unknown"
        : inputs.outflow > capacityPct ? "base"
          : stressedPct > capacityPct ? "stress" : "none",
  };
}

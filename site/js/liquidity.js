/* Tark liquidity scenario math, the JavaScript port of the SCENARIO layer of
 * src/tark_liquidity.py (v3, R2-P1-10 and R2-P1-11). The FACTS and VERDICT
 * layers come precomputed per (plan x product) in the data bundle
 * (data/liquidity/*.json). Only the ILLUSTRATIVE scenario recomputes live
 * when sliders move. The base demand is the plan's filed outflow proxy (read
 * from the match, never recomputed here). The sliders set the slider
 * assumption and the stress increment around that base. The allocation
 * moves dollars and the plan's share of the fund's dollar capacity, never
 * the percent-of-position ladder. Parity of the arithmetic with Python is
 * tested in src/test_frontend.py against every bundled match file.
 */

const THIN_HEADROOM_SHARE = 0.6;

function sliderDemandPct(tailShare, tailPct, activePct) {
  return tailShare * tailPct + (1 - tailShare) * activePct;
}

/** the plan's separated share of accounts, unrounded when the match ships it */
function tailShareOf(planInputs) {
  return (planInputs.tail_share === null || planInputs.tail_share === undefined)
    ? planInputs.tail_share_pct / 100 : planInputs.tail_share;
}

/** what the stress multiples add over the slider assumption itself */
export function stressIncrementPct(planInputs, params, multiples) {
  const tailShare = tailShareOf(planInputs);
  const base = sliderDemandPct(tailShare, params.tail_annual_turnover_pct,
    params.active_annual_turnover_pct);
  const stressed = sliderDemandPct(tailShare,
    params.tail_annual_turnover_pct * multiples.tail_multiple,
    params.active_annual_turnover_pct * multiples.active_multiple);
  return stressed - base;
}

/** stressed demand as a percent of the position: the filed outflow proxy
 * plus the sliders' stress increment (null when the plan has no filed rate) */
export function stressedDemandPct(planInputs, params, multiples) {
  const filed = planInputs.filed_outflow_proxy_pct;
  if (filed === null || filed === undefined) return null;
  return filed + stressIncrementPct(planInputs, params, multiples);
}

export function computeScenario(planInputs, profile, params, multiples) {
  // planInputs: {net_assets, tail_share_pct, filed_outflow_proxy_pct} from
  //             the match file (cited to the plan record)
  // profile: wrapper facts. annual_capacity_pct is the binding annual figure
  //          Python computed from the typed cap list (null when no cap is
  //          typed or the wrapper is exchange-listed). It is read, never
  //          recomputed here, so a null cap yields null and never 0.
  //          net_assets_usd (null when not typed) sizes the dollar capacity.
  // params: {allocation_pct_of_plan, tail_annual_turnover_pct,
  //          active_annual_turnover_pct}
  // multiples: the stress multiples shipped in the match file
  const tailShare = tailShareOf(planInputs);
  const alloc = planInputs.net_assets * params.allocation_pct_of_plan / 100;
  const filed = (planInputs.filed_outflow_proxy_pct === undefined)
    ? null : planInputs.filed_outflow_proxy_pct;
  const sliderPct = sliderDemandPct(tailShare, params.tail_annual_turnover_pct,
    params.active_annual_turnover_pct);
  const increment = stressIncrementPct(planInputs, params, multiples || { tail_multiple: 2, active_multiple: 1.5 });
  const stressedPct = filed === null ? null : filed + increment;
  const cap = profile.annual_capacity_pct;
  const capacityPct = (profile.exchange || cap === null || cap === undefined) ? null : cap;
  const na = profile.net_assets_usd;
  let fund = { available: false };
  if (!profile.exchange && na !== null && na !== undefined && capacityPct !== null
      && capacityPct > 0 && filed !== null) {
    const capUsd = capacityPct / 100 * na;
    const demandUsd = alloc * filed / 100;
    fund = {
      available: true,
      annual_capacity_usd: Math.round(capUsd),
      plan_annual_demand_usd: Math.round(demandUsd),
      plan_share_of_fund_capacity_pct: Math.round(demandUsd / capUsd * 10000) / 100,
    };
  }
  return {
    plan_allocation_usd: Math.round(alloc),
    filed_outflow_proxy_pct: filed,
    filed_annual_demand_usd: filed === null ? null : Math.round(alloc * filed / 100),
    slider_assumption_pct: Math.round(sliderPct * 10) / 10,
    slider_annual_demand_usd: Math.round(alloc * sliderPct / 100),
    stress_increment_pct: Math.round(increment * 10) / 10,
    stressed_pct: stressedPct === null ? null : Math.round(stressedPct * 10) / 10,
    stressed_annual_demand_usd: stressedPct === null ? null : Math.round(alloc * stressedPct / 100),
    annual_wrapper_capacity_pct: capacityPct,
    thin_headroom_filed: capacityPct !== null && capacityPct > 0 && filed !== null
      && filed > THIN_HEADROOM_SHARE * capacityPct,
    thin_headroom_slider: capacityPct !== null && capacityPct > 0
      && sliderPct > THIN_HEADROOM_SHARE * capacityPct,
    fund_capacity: fund,
    // the unrounded stressed figure, for the verdict ladder
    _stressed_exact: stressedPct,
  };
}

/** ILLUSTRATIVE scenario verdict, the same ladder as tark_liquidity.scenario_verdict:
 * the base rung reads the filed outflow proxy, the stress rung the stressed demand */
export function scenarioVerdict(sc, stressedPct, exchange) {
  if (exchange) return "aligned-mechanical";
  if (sc.annual_wrapper_capacity_pct === null) return null;
  if (sc.filed_outflow_proxy_pct === null || stressedPct === null) return null;
  if (sc.filed_outflow_proxy_pct > sc.annual_wrapper_capacity_pct) return "misaligned";
  if (stressedPct > sc.annual_wrapper_capacity_pct) return "conditional-weak";
  return "conditional";
}

function headroom(pct, cap, subject, baseClause) {
  if (cap === null) return "";
  if (cap === 0) return " EXCEEDS: repurchases are closed, so every request waits for the program to reopen.";
  if (pct <= THIN_HEADROOM_SHARE * cap) return " " + baseClause;
  return ` THIN HEADROOM: the ${subject} consumes over 60% of wrapper capacity, so ` +
    "proration in any oversubscribed window would push the shortfall into the next window.";
}

function vsCapacity(pct, cap) {
  if (cap === null) {
    return `${pct.toFixed(1)}% of the position per year, no annual wrapper capacity to ` +
      "compare against until the cap is typed (3.1)";
  }
  return `${pct.toFixed(1)}% of the position per year vs ${cap.toFixed(0)}% annual wrapper capacity`;
}

/** the two demand sentences the Python generator prints, live */
export function scenarioReason(sc) {
  const cap = sc.annual_wrapper_capacity_pct;
  const filed = sc.filed_outflow_proxy_pct;
  const filedLine = filed === null
    ? "Filed outflow proxy: not in the plan record, so the scenario has no base demand."
    : `Filed outflow proxy: ${vsCapacity(filed, cap)}.` +
      headroom(filed, cap, "filed rate", "Adequate headroom at the filed rate if offers are not prorated.");
  const sliderLine = `Slider assumption (illustrative): ${vsCapacity(sc.slider_assumption_pct, cap)}.` +
    headroom(sc.slider_assumption_pct, cap, "slider assumption", "Within 60% of wrapper capacity at these sliders.");
  return filedLine + " " + sliderLine;
}

window.TarkLiquidity = { computeScenario, scenarioReason, scenarioVerdict, stressedDemandPct, stressIncrementPct };

/* Tark liquidity scenario math — JavaScript port of the SCENARIO layer of
 * src/tark_liquidity.py. The FACTS and VERDICT layers come precomputed per
 * (plan x product) in the data bundle (data/liquidity/*.json); only the
 * ILLUSTRATIVE scenario recomputes live when sliders move. The wording of the
 * scenario reason mirrors the Python generator; parity of the arithmetic is
 * tested in tests/test_frontend.py against the bundled match files.
 */

export function computeScenario(planInputs, profile, params) {
  // planInputs: {net_assets, tail_share_pct} from the match file (cited)
  // profile: wrapper facts (cadence_per_year, cap_pct, exchange)
  // params: {allocation_pct_of_plan, tail_annual_turnover_pct,
  //          active_annual_turnover_pct}
  const tailShare = planInputs.tail_share_pct / 100;
  const alloc = planInputs.net_assets * params.allocation_pct_of_plan / 100;
  const tailDemand = alloc * tailShare * params.tail_annual_turnover_pct / 100;
  const activeDemand =
    alloc * (1 - tailShare) * params.active_annual_turnover_pct / 100;
  const demand = tailDemand + activeDemand;
  const demandPct = demand / alloc * 100;
  const capacityPct = profile.exchange
    ? null
    : profile.cadence_per_year * profile.cap_pct;
  return {
    plan_allocation_usd: Math.round(alloc),
    annual_demand_usd: Math.round(demand),
    demand_pct_of_position: Math.round(demandPct * 10) / 10,
    annual_wrapper_capacity_pct: capacityPct,
    thin_headroom: capacityPct !== null && demandPct > 0.6 * capacityPct,
  };
}

export function scenarioReason(sc) {
  if (sc.annual_wrapper_capacity_pct === null) return null;
  const head = `Scenario demand (illustrative): ${sc.demand_pct_of_position.toFixed(1)}% ` +
    `of the position per year vs ${sc.annual_wrapper_capacity_pct.toFixed(0)}% ` +
    `annual wrapper capacity — `;
  return head + (sc.thin_headroom
    ? "THIN HEADROOM: demand consumes over 60% of wrapper capacity; " +
      "proration in any oversubscribed quarter would push the shortfall " +
      "into the next window."
    : "adequate headroom at this allocation if offers are not prorated.");
}

window.TarkLiquidity = { computeScenario, scenarioReason };

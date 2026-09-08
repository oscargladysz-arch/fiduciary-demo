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
// the ladder's typed vocabulary, mirrored from src/tark_liquidity.py (R3-P2-7)
const PERIODS_PER_YEAR = { month: 12, quarter: 4, year: 1 };
const DEALING_NOUN = { daily: "daily repurchase requests", monthly: "monthly repurchases", quarterly: "quarterly offers" };
const RUNG_OF = { misaligned: "base", "conditional-weak": "stress", conditional: "none", "aligned-mechanical": "exchange" };
const PRORATION = "Proration assumption: an oversubscribed offer is filled pro rata and the unfilled remainder waits for the next window.";
const FILED_WORDS = "the plan's total expenses less administrative expenses over beginning net assets, applied to the position";
const isNum = (v) => v !== null && v !== undefined;

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
      "compare against until the cap is on record (3.1)";
  }
  return `${pct.toFixed(1)}% of the position per year vs ${cap.toFixed(0)}% annual wrapper capacity`;
}

/* The product facts behind the capacity, each with its cell: the mirror of
 * tark_liquidity._driver_facts. */
function driverFacts(d) {
  const cap = d.binding_cap;
  const parts = [];
  if (d.program_status === "suspended") {
    parts.push("repurchases suspended (3.1)");
  } else if (cap) {
    parts.push(`binding cap ${cap.pct}% per ${cap.period} on ${d.cap_base} (3.1)`);
    if (DEALING_NOUN[d.dealing_cadence]) parts.push(`${DEALING_NOUN[d.dealing_cadence]} (3.1)`);
  } else {
    parts.push("repurchase cap not on record (3.1)");
  }
  if (d.program_status === "active") {
    parts.push("program active" + (d.program_status_as_of ? ` as of ${d.program_status_as_of}` : "") + " (3.1)");
  } else if (!isNum(d.program_status)) {
    parts.push("program status not on record (3.1)");
  }
  parts.push(d.gate_history ? "prorated under stress before (3.3)"
    : d.gate_history === false ? "no proration identified (3.3)" : "gating history not on record (3.3)");
  return parts.join(", ");
}

/** the sentence naming the rung that fired and the facts it read, the
 * mirror of tark_liquidity.drivers_sentence (parity-tested word for word) */
export function driversSentence(d) {
  const c = d.compared;
  if (d.rung === "exchange") {
    return "No rung: the wrapper is exchange-listed, so both rates are selling rates against market depth and no fund cap applies (3.1).";
  }
  const facts = driverFacts(d);
  const cap = c.capacity_pct;
  if (d.rung === "not_computable") {
    const why = !isNum(c.filed_pct) ? "the plan record carries no filed outflow proxy"
      : "the annual wrapper capacity is not computable";
    return `No rung fired: ${why} (${facts}).`;
  }
  let head;
  if (d.rung === "base") {
    head = `Base rung: the filed outflow proxy ${c.filed_pct.toFixed(1)}% of the position per year ` +
      `exceeds the annual wrapper capacity ${cap.toFixed(0)}%`;
  } else if (d.rung === "stress") {
    head = `Stress rung: the filed outflow proxy ${c.filed_pct.toFixed(1)}% of the position per year ` +
      `stays within the annual wrapper capacity ${cap.toFixed(0)}% and the stressed demand ` +
      `${c.stressed_pct.toFixed(1)}% exceeds it`;
  } else {
    head = `No rung fired: the filed outflow proxy ${c.filed_pct.toFixed(1)}% and the stressed demand ` +
      `${c.stressed_pct.toFixed(1)}% of the position per year both stay within the annual ` +
      `wrapper capacity ${cap.toFixed(0)}%`;
  }
  const w = d.window;
  const per = w ? ` Per ${w.period}: filed ${w.filed_per_window_pct.toFixed(1)}% and stressed ` +
    `${w.stressed_per_window_pct.toFixed(1)}% of the position against the ${w.cap_per_window_pct}% cap.` : "";
  return `${head} (${facts}).${per}`;
}

/** what the ladder read and which rung fired, live: the mirror of
 * tark_liquidity.scenario_drivers over the same typed inputs
 * (profile.scenario_inputs) and the live figures */
export function scenarioDrivers(sc, stressedPct, profile, verdict) {
  const si = profile.scenario_inputs || {};
  const cap = si.binding_cap;
  const filed = sc.filed_outflow_proxy_pct;
  const capacity = sc.annual_wrapper_capacity_pct;
  const rung = profile.exchange ? "exchange" : (isNum(verdict) ? RUNG_OF[verdict] : "not_computable");
  let window = null;
  if (cap && !profile.exchange && capacity && isNum(filed) && isNum(stressedPct)) {
    const n = PERIODS_PER_YEAR[cap.period];
    window = { period: cap.period, windows_per_year: n, cap_per_window_pct: cap.pct,
      filed_per_window_pct: filed / n, stressed_per_window_pct: stressedPct / n };
  }
  const d = { rung, compared: { filed_pct: filed, stressed_pct: stressedPct, capacity_pct: capacity }, ...si, window };
  d.sentence = driversSentence(d);
  return d;
}

function money(x) {
  if (x >= 1e9) return `$${(x / 1e9).toFixed(1)}B`;
  if (x >= 1e6) return `$${(x / 1e6).toFixed(1)}M`;
  return `$${Math.round(x).toLocaleString("en-US")}`;
}

/** every scenario bullet from one live state (R3-P1-10): the mirror of the
 * scenario_reasons list run_match writes, so the view rebuilds the list on
 * every slider move and, at the default sliders, prints the record's own
 * sentences word for word. Each entry is {kind, text}. */
export function scenarioBullets(m, out, params, profile, verdict) {
  const sc = m.scenario;
  const pi = m.plan_inputs;
  const cap = out.annual_wrapper_capacity_pct;
  const filed = out.filed_outflow_proxy_pct;
  const tailPct = (tailShareOf(pi) * 100).toFixed(1);
  const sliderWords = `from tail turnover ${params.tail_annual_turnover_pct}%/yr on the ${tailPct}% of accounts ` +
    `that are separated and active turnover ${params.active_annual_turnover_pct}%/yr on the rest. Shown ` +
    "beside the filed rate, not blended with it";
  const sliderPct = out.slider_assumption_pct;
  const bullets = [{ kind: "capacity", text: `Capacity: ${sc.capacity_note}.` }];
  if (profile.exchange) {
    if (isNum(filed)) {
      bullets.push({ kind: "filed", text: `Filed outflow proxy (Schedule H, plan year ${pi.plan_year}): ${filed.toFixed(1)}% of the ` +
        `position per year, ${FILED_WORDS}. On an exchange this is a selling rate against market depth, not a claim on a fund cap.` });
    }
    bullets.push({ kind: "slider", text: `Slider assumption (illustrative): ${sliderPct.toFixed(1)}% of the position per year, ` +
      `${sliderWords}, and likewise a selling rate against market depth.` });
    return bullets;
  }
  if (!isNum(filed)) {
    bullets.push({ kind: "filed", text: "Filed outflow proxy: not in the plan record, so the scenario has no base demand and no " +
      "scenario verdict until the Schedule H totals are on record." });
  } else {
    bullets.push({ kind: "filed", text: `Filed outflow proxy (Schedule H, plan year ${pi.plan_year}): ${vsCapacity(filed, cap)}, ${FILED_WORDS}.` +
      headroom(filed, cap, "filed rate", "Adequate headroom at the filed rate if offers are not prorated.") });
  }
  bullets.push({ kind: "slider", text: `Slider assumption (illustrative): ${vsCapacity(sliderPct, cap)}, ${sliderWords}.` +
    headroom(sliderPct, cap, "slider assumption", "Within 60% of wrapper capacity at these turnover assumptions.") });
  const fc = out.fund_capacity;
  if (fc.available) {
    const approx = profile.net_assets_approx ? "approx. " : "";
    bullets.push({ kind: "fund", text: `Fund capacity in dollars: ${cap}% of ${approx}${money(profile.net_assets_usd)} ` +
      `net assets (cell ${profile.net_assets_cell}) is ${money(fc.annual_capacity_usd)} per year. At a ` +
      `${params.allocation_pct_of_plan}% allocation (${money(out.plan_allocation_usd)}) the plan's demand at the filed ` +
      `rate is ${money(fc.plan_annual_demand_usd)} per year, ${fc.plan_share_of_fund_capacity_pct.toFixed(2)}% of that ` +
      "capacity. The cap is shared by every holder, so this is the plan's own claim on it, not the fund's total " +
      "demand. The allocation moves these dollar figures and this share, never the percent-of-position ladder." });
  }
  const d = scenarioDrivers(out, out._stressed_exact, profile, verdict);
  bullets.push({ kind: "verdict", text: `Scenario verdict (ILLUSTRATIVE, this plan): ${isNum(verdict) ? verdict : "not computable"}. ` +
    `${d.sentence} ${PRORATION}` });
  for (const line of sc.schedule_h_lines || []) bullets.push({ kind: "schedule", text: line });
  return bullets;
}

window.TarkLiquidity = { computeScenario, scenarioVerdict, scenarioDrivers, driversSentence, scenarioBullets,
  stressedDemandPct, stressIncrementPct };

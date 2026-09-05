"""
Tark liquidity match, v2 (P1-16, P1-17). Two layers, never blurred.

structural_verdict, from typed facts only (data/facts/<product>.json,
cells 3.1, 3.3, 2.7, and the registry's pricing class):
  exchange-listed                         -> aligned-mechanical
  repurchase program suspended, or cap 0  -> misaligned
  a required fact not typed               -> partial (suspension wins)
  gating history                          -> conditional-weak
  otherwise                               -> conditional

scenario_verdict, ILLUSTRATIVE and per plan, from the demand model:
  base demand above annual capacity       -> misaligned
  stressed demand above annual capacity   -> conditional-weak
  otherwise                               -> conditional
  (exchange-listed: aligned-mechanical, capacity is market depth)

No hand-typed wrapper profile exists any more. Every input names its cell,
a null input names its reason, and the proration assumption is printed.
"""
import json

from tark_data import DATA, load_plan, load_products, plan_keys

ANCHOR_PLAN_KEY = "plan_tech_media"
REGISTRY = json.loads((DATA / "registry.json").read_text())["products"]

# ILLUSTRATIVE scenario defaults (sliders on the surface start here)
SCENARIO = {"allocation_pct_of_plan": 5.0, "tail_annual_turnover_pct": 20.0,
            "active_annual_turnover_pct": 5.0}
STRESS = {"tail_multiple": 2.0, "active_multiple": 1.5}
THIN_HEADROOM_SHARE = 0.6
REQUIRED = ("repurchase_cadence_per_year", "repurchase_cap_pct", "gate_history")
VERDICTS = ("aligned-mechanical", "conditional", "conditional-weak", "misaligned", "partial")


def load_facts(key: str) -> dict:
    return json.loads((DATA / "facts" / f"{key}.json").read_text())["facts"]


def early_fee_text(f) -> str:
    if f is None:
        return "not typed (2.7)"
    if not f.get("present"):
        return "none at fund level (2.7)"
    parts = []
    if f.get("rate_pct") is not None:
        parts.append(f"{f['rate_pct']:g}%")
    if f.get("window"):
        parts.append(f"if held {f['window']}")
    return (" ".join(parts) or "present, terms not typed") + " (2.7)"


def wrapper_facts(key: str) -> dict:
    """The typed inputs the verdict reads, each with its cell, plus the
    reason for every null."""
    fx = load_facts(key)
    g = lambda n: fx[n].get("value")   # noqa: E731
    names = REQUIRED + ("repurchase_cap_base", "repurchase_program_status",
                        "early_repurchase", "wrapper_type")
    return {
        "kind": g("wrapper_type"),
        "cadence_per_year": g("repurchase_cadence_per_year"),
        "cap_pct": g("repurchase_cap_pct"),
        "cap_base": (g("repurchase_cap_base") or "not typed").replace("_", " "),
        "exchange": REGISTRY[key]["pricing_class"] == "MARKET",
        "gate_history": g("gate_history"),
        "program_status": g("repurchase_program_status"),
        "early_fee": early_fee_text(g("early_repurchase")),
        "null_reasons": {n: fx[n].get("reason") for n in names
                         if g(n) is None and fx[n].get("reason")},
        "source_cell": ", ".join(sorted({fx[n]["source_cell"] for n in names})),
    }


def structural_verdict(wf: dict) -> tuple[str, list[str], list[str]]:
    """(verdict, reasons, missing facts) from typed facts alone."""
    if wf["exchange"]:
        return "aligned-mechanical", [
            "Daily exchange liquidity mechanically satisfies daily participant "
            "dealing (3.1).",
            "BUT price-vs-NAV decoupling means participants transact at the "
            "premium or discount, not at portfolio value. The liquidity is real, "
            "the price basis is not (1.10, 4.7)."], []
    if wf["program_status"] == "suspended" or wf["cap_pct"] == 0:
        return "misaligned", [
            "Repurchase program "
            + ("suspended" if wf["program_status"] == "suspended" else "capped at 0%")
            + " (cell 3.1): ordinary repurchase requests are not accepted, so "
            "participant liquidity depends on the program reopening. Capacity is 0%."
            + (" Gating precedent on top (3.3)." if wf["gate_history"] else "")], []
    missing = [n for n in REQUIRED if wf[
        {"repurchase_cadence_per_year": "cadence_per_year", "repurchase_cap_pct": "cap_pct",
         "gate_history": "gate_history"}[n]] is None]
    if missing:
        detail = "; ".join(f"{n} ({wf['null_reasons'].get(n, 'not typed')})" for n in missing)
        return "partial", [
            "Facts missing for a structural verdict: " + detail.replace("; ", ". ")
            + ". The verdict stays partial until they are typed from the filings."], missing
    if wf["gate_history"]:
        return "conditional-weak", [
            "Gating precedent: this issuer has prorated repurchases when requests "
            "exceeded caps (3.3). Capacity on paper has failed in stress before."], []
    return "conditional", [], []


def scenario_verdict(demand_pct: float, stressed_pct: float,
                     capacity_pct: float | None, exchange: bool) -> str | None:
    if exchange:
        return "aligned-mechanical"
    if capacity_pct is None:
        return None
    if demand_pct > capacity_pct:
        return "misaligned"
    if stressed_pct > capacity_pct:
        return "conditional-weak"
    return "conditional"


def schedule_h_lines(plan: dict) -> tuple[list[str], list[str]]:
    """(scenario lines, structural lines) from the plan's Schedule H block
    (P1-18). Filed figures are used when present, with the model named.
    Absent figures are said to be absent, with the plan file's reason."""
    fin = plan.get("financials", {})
    sh = plan.get("schedule_h") or {}
    boy = fin.get("net_assets_boy")
    scenario, structural = [], []
    bp = sh.get("benefit_payments_2e") or {}
    if isinstance(bp.get("value"), (int, float)) and boy:
        pct = bp["value"] / boy * 100
        scenario.append(f"Schedule H based demand (filed, line 2e): benefit payments were "
                        f"{pct:.1f}% of beginning net assets in plan year "
                        f"{plan.get('plan_year', '?')}. Model: the filed plan-level outflow "
                        f"rate applied to the position, {pct:.1f}% of the position per year, "
                        "shown beside the slider model above, not blended with it.")
    else:
        scenario.append("Schedule H benefit-payment lines are not yet in the plan record. "
                        "Demand uses the illustrative turnover sliders only.")
    pc = sh.get("participant_contributions_2a1b") or {}
    if isinstance(pc.get("value"), (int, float)) and boy:
        scenario.append(f"Participant contributions (Schedule H line 2a(1)(B)) were "
                        f"{pc['value'] / boy * 100:.1f}% of beginning net assets, an inflow "
                        "that offsets outflows at the plan level, not at the position level.")
    qd = sh.get("qdia_indicator") or {}
    if qd.get("value"):
        structural.append(f"Plan QDIA on file: {qd['value']} ({qd.get('source', 'source not recorded')}). "
                          "A product reaching participants through the QDIA sits inside a TDF "
                          "or managed-account sleeve (cell 3.5), not as a standalone DIA.")
    return scenario, structural


def plan_direction(plan: dict) -> str:
    codes = plan["plan_characteristics"].get("pension_benefit_codes", "")
    if "2G" in codes or "404(c)" in plan["plan_characteristics"].get("notes", ""):
        return "total"
    if "2H" in codes:
        return "partial"
    return "unknown"


def run_match(key: str, plan_key: str = ANCHOR_PLAN_KEY,
              scenario: dict | None = None) -> dict:
    wf = wrapper_facts(key)
    sc_in = {**SCENARIO, **(scenario or {})}
    a = load_plan(plan_key)
    part, fin = a["participants"], a["financials"]
    net = fin["net_assets_eoy"]
    tail_share = part["separated_deferred_vested"] / part["with_account_balances"]
    direction = plan_direction(a)

    alloc = net * sc_in["allocation_pct_of_plan"] / 100
    tail_demand = alloc * tail_share * sc_in["tail_annual_turnover_pct"] / 100
    active_demand = alloc * (1 - tail_share) * sc_in["active_annual_turnover_pct"] / 100
    demand = tail_demand + active_demand
    demand_pct = demand / alloc * 100
    s_tail = alloc * tail_share * (sc_in["tail_annual_turnover_pct"] * STRESS["tail_multiple"]) / 100
    s_active = alloc * (1 - tail_share) * (sc_in["active_annual_turnover_pct"] * STRESS["active_multiple"]) / 100
    s_demand = s_tail + s_active
    s_pct = s_demand / alloc * 100

    # ---- layer 1: structural, from typed facts ----
    verdict, s_reasons, missing = structural_verdict(wf)
    structural = list(s_reasons)
    if not wf["exchange"]:
        cad = wf["cadence_per_year"]
        dealing = (f"this wrapper deals {cad:g}x/year" if cad
                   else "this wrapper's dealing cadence is not typed (3.1)")
        if direction == "total":
            structural.insert(0, "STRUCTURAL GAP: a participant-directed 404(c) menu "
                                 "assumes daily pricing and daily participant liquidity, "
                                 f"whereas {dealing}. Direct DIA use requires a bridging "
                                 "structure: CIT sleeve, managed account, or TDF sleeve "
                                 "(cell 3.5).")
        elif direction == "partial":
            structural.insert(0, "STRUCTURAL GAP (narrowed): this plan is PARTIALLY "
                                 "participant-directed per its own Form 5500 codes (2H, no "
                                 "2G/404(c) code filed). A trustee-directed sleeve could "
                                 "hold this wrapper directly, and the daily-menu constraint "
                                 f"({dealing}) applies only to the participant-directed "
                                 "portion (cell 3.5).")
        else:
            structural.insert(0, "STRUCTURAL: plan direction codes do not show full "
                                 "participant direction, so DIA daily-menu framing may not "
                                 f"bind. {dealing[0].upper()}{dealing[1:]} (cell 3.5).")
        if wf["early_fee"] != "none at fund level (2.7)":
            structural.append(f"Early repurchase economics: {wf['early_fee']}. Relevant "
                              "to participant-level churn (2.7).")

    # ---- layer 2: ILLUSTRATIVE scenario, per plan ----
    if wf["exchange"]:
        capacity = None
        capacity_note = "daily on-exchange liquidity. Capacity is market depth, not a fund cap"
    elif wf["cadence_per_year"] is None or wf["cap_pct"] is None:
        capacity = None
        capacity_note = ("annual capacity not computable: "
                         + ", ".join(n for n in ("repurchase_cadence_per_year", "repurchase_cap_pct")
                                     if wf[{"repurchase_cadence_per_year": "cadence_per_year",
                                            "repurchase_cap_pct": "cap_pct"}[n]] is None)
                         + " not typed (3.1)")
    elif wf["cap_pct"] == 0:
        capacity = 0.0
        capacity_note = (f"repurchases closed (cell 3.1): {wf['cadence_per_year']:g}x per year "
                         f"at 0% of {wf['cap_base']}. Capacity is 0% until the program reopens")
    else:
        capacity = wf["cadence_per_year"] * wf["cap_pct"]
        capacity_note = (f"{wf['cadence_per_year']:g}x per year at {wf['cap_pct']:g}% of "
                         f"{wf['cap_base']}: at most {capacity:g}% of the position per year. "
                         "This is a FUND-level cap shared by every holder, so the plan's "
                         "position is served only while offers are not oversubscribed")
    scv = scenario_verdict(demand_pct, s_pct, capacity, wf["exchange"])
    scenario_reasons = [f"Capacity: {capacity_note}."]
    if capacity is not None:
        if capacity == 0:
            demand_line = (f"Scenario demand (illustrative): {demand_pct:.1f}% of the position "
                           "per year vs 0% annual wrapper capacity. EXCEEDS: repurchases are "
                           "closed, so every request waits for the program to reopen.")
        else:
            demand_line = (f"Scenario demand (illustrative): {demand_pct:.1f}% of the position "
                           f"per year vs {capacity:.0f}% annual wrapper capacity. "
                           + ("Adequate headroom at this allocation if offers are not prorated."
                              if demand_pct <= THIN_HEADROOM_SHARE * capacity else
                              "THIN HEADROOM: demand consumes over 60% of wrapper capacity, so "
                              "proration in any oversubscribed quarter would push the shortfall "
                              "into the next window."))
        scenario_reasons.append(demand_line)
    if wf["exchange"]:
        outcome = "daily exchange liquidity, so stress transmits to price, not to a fund gate"
    elif capacity is None:
        outcome = "not computable until the capacity facts are typed (3.1)"
    elif s_pct > capacity:
        outcome = ("EXCEEDS annual wrapper capacity. Unmet demand rolls into later windows "
                   "(gating-equivalent outcome)")
    else:
        outcome = (f"within wrapper capacity ({s_pct:.1f}% vs {capacity:.0f}%) IF offers are "
                   "not prorated" + (", but this issuer HAS prorated under stress (3.3)"
                                     if wf["gate_history"] else ""))
    stressed = {"illustrative": True,
                "assumptions": f"tail turnover x{STRESS['tail_multiple']:.0f}, active turnover "
                               f"x{STRESS['active_multiple']:.1f} vs base scenario",
                "multiples": dict(STRESS),
                "annual_demand_usd": round(s_demand),
                "demand_pct_of_position": round(s_pct, 1),
                "annual_wrapper_capacity_pct": capacity,
                "outcome": outcome}
    if scv and not wf["exchange"]:
        scenario_reasons.append(
            f"Scenario verdict (ILLUSTRATIVE, this plan): {scv}. It moves with the sliders "
            "and the plan. Proration assumption: an oversubscribed offer is filled pro rata "
            "and the unfilled remainder waits for the next window.")
    sh_scenario, sh_structural = schedule_h_lines(a)
    if not wf["exchange"]:
        scenario_reasons.extend(sh_scenario)
    structural.extend(sh_structural)

    return {
        "product": key, "plan": plan_key,
        "verdict": verdict,                       # structural, facts only
        "scenario_verdict": scv,                  # ILLUSTRATIVE, per plan
        "structural_reasons": structural,
        "scenario_reasons": scenario_reasons,
        "reasons": structural + scenario_reasons,
        "missing_facts": missing,
        "layers": ("verdict is structural (typed facts, cells 3.1, 3.3, 2.7, plan-independent). "
                   "scenario_verdict is ILLUSTRATIVE (demand model against the same capacity, "
                   "per plan)."),
        "stressed_scenario": stressed,
        "plan_display_label": a["display_label"],
        "plan_direction": direction,
        "wrapper_facts": wf,
        "scenario": {**sc_in, "illustrative": True,
                     "plan_allocation_usd": round(alloc),
                     "annual_demand_usd": round(demand),
                     "demand_pct_of_position": round(demand_pct, 1),
                     "annual_wrapper_capacity_pct": capacity},
        "plan_inputs": {"net_assets": net,
                        "tail_share_pct": round(tail_share * 100, 1),
                        "separated_with_balances": part["separated_deferred_vested"]},
        "citations": ["3.1", "3.3", "3.5", "3.7", "3.9", "2.7",
                      f"plan: {plan_key}.json (Form 5500, plan year {a.get('plan_year', '?')})"],
    }


if __name__ == "__main__":
    out = DATA / "liquidity"
    out.mkdir(exist_ok=True)
    for pk in plan_keys():
        for key in load_products():
            m = run_match(key, pk)
            (out / f"{pk}__{key}_match.json").write_text(json.dumps(m, indent=2))
            print(f"{pk:<26} {key:<18} {m['verdict']:<18} scenario {str(m['scenario_verdict']):<18} "
                  f"demand {m['scenario']['demand_pct_of_position']}%/yr")

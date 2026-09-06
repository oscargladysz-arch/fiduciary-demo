"""
Tark liquidity match, v3 (P1-16, P1-17, R2-P0-5, R2-P1-10, R2-P1-11). Two
layers, never blurred.

structural_verdict, from typed facts only (data/facts/<product>.json,
cells 3.1, 3.3, 2.7, and the registry's pricing class):
  exchange-listed                         -> aligned-mechanical
  repurchase program suspended, or cap 0  -> misaligned
  a required fact not typed               -> partial (suspension wins)
  gating history                          -> conditional-weak
  otherwise                               -> conditional

scenario_verdict, ILLUSTRATIVE and per plan. The BASE demand is the plan's
FILED outflow proxy: Schedule H total expenses less administrative expenses
over beginning net assets, typed in the plan record with its inputs, applied
to the plan's position. A plan whose filing shows low outflows gets low base
demand, whatever its participant mix. The sliders are the stress around that
base: the slider assumption (tail turnover on the separated share of
accounts, active turnover on the rest) is printed beside the filed rate and
never blended with it, and the stressed demand is the filed rate plus the
increment the sliders add under the stress multiples (tail x2, active x1.5
over the slider assumption itself).
  filed outflow proxy above annual capacity  -> misaligned
  stressed demand above annual capacity      -> conditional-weak
  otherwise                                  -> conditional
  (exchange-listed: aligned-mechanical, capacity is market depth)

Annual capacity is the BINDING figure over the typed cap list: the smallest
of pct * periods per year across every cap (breit: 2% per month and 5% per
quarter give 24 and 20, so 20 binds). It is never dealing cadence * cap,
because the dealing cadence and the cap period are separate facts (jll_ipt
takes repurchase requests daily under a quarterly cap).

The allocation moves dollars, never the percent-of-position ladder, which
does not depend on it. Where the fund's net assets are typed, the match
prints the fund's dollar capacity per year (binding cap * net assets), the
plan's dollar demand at the filed rate and the share of the fund's capacity
the plan alone would take. Where they are not typed, the match says so in
one sentence and the surface shows no allocation slider.

No hand-typed wrapper profile exists any more. Every input names its cell,
a null input names its reason, and the proration assumption is printed.
"""
import json

from tark_data import DATA, load_plan, load_product, load_products, plan_keys, status_kind
from tark_display import BASE_LABEL, SCHEDULE_H_ABSENT_SENTENCE, _money as money

ANCHOR_PLAN_KEY = "plan_tech_media"
REGISTRY = json.loads((DATA / "registry.json").read_text())["products"]

# ILLUSTRATIVE scenario defaults (sliders on the surface start here)
SCENARIO = {"allocation_pct_of_plan": 5.0, "tail_annual_turnover_pct": 20.0,
            "active_annual_turnover_pct": 5.0}
STRESS = {"tail_multiple": 2.0, "active_multiple": 1.5}
THIN_HEADROOM_SHARE = 0.6
FILED_LABEL = "filed outflow proxy"
SLIDER_LABEL = "slider assumption"
REQUIRED = ("repurchase_cadence_per_year", "repurchase_cap_pct", "gate_history")
# every typed fact the match reads. Their source cells are the match's
# citations (plus 3.5 and 3.7 where the product's cell is not n/a)
LIQUIDITY_FACTS = REQUIRED + ("repurchase_cap_base", "repurchase_program_status",
                              "early_repurchase", "dealing_cadence", "cap_period",
                              "repurchase_caps")
PLAN_SIDE_CELLS = ("3.5", "3.7")
VERDICTS = ("aligned-mechanical", "conditional", "conditional-weak", "misaligned", "partial")
PERIODS_PER_YEAR = {"month": 12, "quarter": 4, "year": 1}
PERIOD_ADJECTIVE = {"month": "monthly", "quarter": "quarterly", "year": "annual"}
DEALING_NOUN = {"daily": "daily repurchase requests", "monthly": "monthly repurchases",
                "quarterly": "quarterly offers"}
SCHEDULE_H_ABSENT = SCHEDULE_H_ABSENT_SENTENCE
PRORATION = ("Proration assumption: an oversubscribed offer is filled pro rata and the "
             "unfilled remainder waits for the next window.")
LADDER = ("Misaligned when the filed outflow proxy exceeds the annual wrapper capacity, "
          "conditional-weak when the stressed demand exceeds it, conditional otherwise. "
          "It moves with the plan's filing and the sliders.")


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


# ---------------------------------------------------------------- capacity
def binding_cap(caps) -> tuple[float | None, dict | None]:
    """(annual capacity in % of the position, the cap that binds) from a
    list of {pct, period} records. The binding figure is the smallest
    pct * periods per year. None when the list is empty or not typed."""
    if not caps:
        return None, None
    figs = [(c["pct"] * PERIODS_PER_YEAR[c["period"]], c) for c in caps
            if isinstance(c, dict) and isinstance(c.get("pct"), (int, float))
            and c.get("period") in PERIODS_PER_YEAR]
    if not figs:
        return None, None
    fig, cap = min(figs, key=lambda t: t[0])
    return float(fig), cap


def caps_phrase(caps) -> str:
    """'5% per quarter' or '2% per month and 5% per quarter'."""
    return " and ".join(f"{c['pct']:g}% per {c['period']}" for c in caps)


def capacity_from_facts(wf: dict) -> tuple[float | None, str]:
    """(annual capacity % of the position or None, the capacity note) from
    the typed cap list. A suspended program has 0% capacity whatever its
    caps say. A null cap list yields None, never 0."""
    if wf["exchange"]:
        return None, "daily on-exchange liquidity. Capacity is market depth, not a fund cap"
    caps = wf.get("caps")
    if wf.get("program_status") == "suspended":
        return 0.0, ("repurchases are suspended (cell 3.1): ordinary requests are not "
                     "accepted. Capacity is 0% until the program reopens")
    capacity, cap = binding_cap(caps)
    if capacity is None:
        reason = wf.get("null_reasons", {}).get("repurchase_caps")
        return None, ("annual capacity not computable: the repurchase cap is not typed (3.1)"
                      + (f", {reason}" if reason else ""))
    base = wf["cap_base"]
    if capacity == 0:
        return 0.0, (f"repurchases closed (cell 3.1): {caps_phrase(caps)} on {base}. "
                     "Capacity is 0% until the program reopens")
    if len(caps) > 1:
        head = (f"{caps_phrase(caps)} on {base}: the binding annual figure is "
                f"{capacity:g}% of the position per year (the "
                f"{PERIOD_ADJECTIVE[cap['period']]} cap)")
    else:
        head = (f"{caps_phrase(caps)} on {base}: at most {capacity:g}% of the "
                "position per year")
    return capacity, (head + ". This is a FUND-level cap shared by every holder, so the "
                      "plan's position is served only while offers are not oversubscribed")


# ------------------------------------------------------------ display text
def dealing_clause(wf: dict) -> str:
    """The clause the structural-gap sentence prints after 'whereas'. Reads
    the program status first, then the dealing cadence in words, never a
    per-year count."""
    if wf.get("program_status") == "suspended":
        return "repurchases are suspended (cell 3.1)"
    dc = wf.get("dealing_cadence")
    if dc not in ("daily", "monthly", "quarterly"):
        return "this wrapper's dealing cadence is not typed (3.1)"
    caps = wf.get("caps")
    if not caps:
        return f"this wrapper deals {dc}"
    cap_words = (f"caps of {caps_phrase(caps)}" if len(caps) > 1
                 else f"a {caps[0]['pct']:g}% cap per {caps[0]['period']}")
    if dc == "daily":
        return f"this wrapper deals daily but only within {cap_words} on {wf['cap_base']}"
    return f"this wrapper deals {dc} with {cap_words} on {wf['cap_base']}"


def dealing_label(wf: dict, since: str | None = None) -> str:
    """Display-ready dealing terms for the site and the memo."""
    if wf["exchange"]:
        return "daily on-exchange dealing, no fund-level cap (3.1)"
    if wf.get("program_status") == "suspended":
        return "repurchases suspended" + (f" since the {since}" if since else "") + " (3.1)"
    dc = wf.get("dealing_cadence")
    if dc not in DEALING_NOUN:
        return "dealing cadence not typed (3.1)"
    caps = wf.get("caps")
    if not caps:
        return DEALING_NOUN[dc]
    return (DEALING_NOUN[dc] + ", "
            + " and ".join(f"{c['pct']:g}% cap per {c['period']}" for c in caps)
            + f" on {wf['cap_base']}")


def caps_label(wf: dict) -> str:
    """Display-ready cap terms with the binding annual figure."""
    if wf["exchange"]:
        return "no fund-level cap, capacity is market depth"
    caps = wf.get("caps")
    capacity = wf.get("annual_capacity_pct")
    if not caps or capacity is None:
        return "repurchase cap not typed (3.1)"
    if wf.get("program_status") == "suspended":
        return f"{caps_phrase(caps)} for ordinary requests (suspended), 0% per year"
    if len(caps) > 1:
        return f"{caps_phrase(caps)}, binding {capacity:g}% per year"
    return f"{caps_phrase(caps)}, {capacity:g}% per year"


def wrapper_facts(key: str) -> dict:
    """The typed inputs the verdict reads, each with its cell, plus the
    reason for every null, the binding annual capacity, the fund's net
    assets (for the dollar capacity) and display labels."""
    fx = load_facts(key)
    g = lambda n: fx[n].get("value")   # noqa: E731
    names = LIQUIDITY_FACTS + ("wrapper_type",)
    raw_base = g("repurchase_cap_base")
    na = fx.get("net_assets_usd") or {}
    wf = {
        "kind": g("wrapper_type"),
        "cadence_per_year": g("repurchase_cadence_per_year"),
        "dealing_cadence": g("dealing_cadence"),
        "cap_pct": g("repurchase_cap_pct"),
        "cap_period": g("cap_period"),
        "caps": g("repurchase_caps"),
        "cap_base": ("not typed" if raw_base is None
                     else BASE_LABEL.get(raw_base, raw_base.replace("_", " "))),
        "exchange": REGISTRY[key]["pricing_class"] == "MARKET",
        "gate_history": g("gate_history"),
        "program_status": g("repurchase_program_status"),
        "early_fee": early_fee_text(g("early_repurchase")),
        # the fund's own size, read only for the dollar capacity (R2-P1-11)
        "net_assets_usd": na.get("value"),
        "net_assets_cell": na.get("source_cell"),
        "net_assets_approx": bool(na.get("approx")),
        "null_reasons": {n: fx[n].get("reason") for n in names + ("net_assets_usd",)
                         if n in fx and fx[n].get("value") is None and fx[n].get("reason")},
        "source_cell": ", ".join(sorted({fx[n]["source_cell"] for n in names})),
        "cells_read": sorted({fx[n]["source_cell"] for n in LIQUIDITY_FACTS}),
    }
    wf["annual_capacity_pct"] = capacity_from_facts(wf)[0]
    wf["dealing_label"] = dealing_label(wf, fx["repurchase_program_status"].get("since"))
    wf["caps_label"] = caps_label(wf)
    return wf


def citations(key: str, wf: dict, plan_key: str, plan: dict,
              extra_cells: tuple[str, ...] = ()) -> list[str]:
    """The cells the match actually read: the source cells of the typed
    facts, plus the plan-side cells 3.5 and 3.7, in both cases only where
    this product's cell is not n/a (a fact that is null against an n/a cell
    is a documented absence, not evidence read), plus the cell the fund's
    net assets came from when the dollar capacity was computed. Never 3.9,
    which is written from the match."""
    cells = load_product(key)["cells"]
    out = {c for c in set(wf["cells_read"]) | set(PLAN_SIDE_CELLS) | set(extra_cells)
           if c in cells and status_kind(str(cells[c].get("status", ""))) != "n/a"}
    out.discard("3.9")
    return sorted(out) + [f"plan: {plan_key}.json (Form 5500, plan year "
                          f"{plan.get('plan_year', '?')})"]


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


# ------------------------------------------------------- the demand model
def filed_outflow(plan: dict) -> dict | None:
    """The plan's filed outflow proxy as the match carries it: the rate, the
    formula, the three inputs and a reader-facing source. None when the plan
    record does not type it (an intake plan without the totals)."""
    fp = (plan.get("schedule_h") or {}).get("filed_outflow_proxy") or {}
    v = fp.get("value")
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return None
    py = fp.get("plan_year") or plan.get("plan_year") or "?"
    return {"label": FILED_LABEL,
            "rate_pct": float(v),
            "formula": fp.get("formula"),
            "inputs": {k: (rec or {}).get("value") for k, rec in (fp.get("inputs") or {}).items()},
            "plan_year": py,
            "source": f"Schedule H totals of the plan's Form 5500 for plan year {py}, from the plan record",
            "what": ("total expenses less administrative expenses over beginning net assets, "
                     "an upper bound on benefit payments while Schedule H line 2e is not in "
                     "the record")}


def slider_demand_pct(tail_share: float, tail_pct: float, active_pct: float) -> float:
    """The slider assumption: tail turnover on the separated share of
    accounts, active turnover on the rest, in % of the position per year."""
    return tail_share * tail_pct + (1 - tail_share) * active_pct


def stress_increment_pct(tail_share: float, tail_pct: float, active_pct: float,
                         multiples: dict | None = None) -> float:
    """What the stress multiples add over the slider assumption itself."""
    m = multiples or STRESS
    stressed = slider_demand_pct(tail_share, tail_pct * m["tail_multiple"],
                                 active_pct * m["active_multiple"])
    return stressed - slider_demand_pct(tail_share, tail_pct, active_pct)


def stressed_demand_pct(filed_rate: float | None, tail_share: float, tail_pct: float,
                        active_pct: float, multiples: dict | None = None) -> float | None:
    """The stressed demand: the filed outflow proxy plus the sliders' stress
    increment. None when the plan carries no filed rate."""
    if filed_rate is None:
        return None
    return filed_rate + stress_increment_pct(tail_share, tail_pct, active_pct, multiples)


def scenario_verdict(filed_pct: float | None, stressed_pct: float | None,
                     capacity_pct: float | None, exchange: bool) -> str | None:
    """The ILLUSTRATIVE ladder. The base rung reads the filed outflow proxy,
    the stress rung reads the stressed demand (filed plus the sliders'
    increment). None when either the capacity or the filed rate is absent."""
    if exchange:
        return "aligned-mechanical"
    if capacity_pct is None or filed_pct is None or stressed_pct is None:
        return None
    if filed_pct > capacity_pct:
        return "misaligned"
    if stressed_pct > capacity_pct:
        return "conditional-weak"
    return "conditional"


def fund_capacity(wf: dict, alloc_usd: float, filed_rate: float | None,
                  capacity_pct: float | None) -> dict:
    """The fund's own repurchase capacity in dollars per year and the plan's
    claim on it at the filed rate (R2-P1-11). Available only when the fund's
    net assets are typed, the wrapper has a computable non-zero cap and the
    plan carries a filed rate. Otherwise one sentence says why, and the
    surface shows no allocation slider."""
    na = wf.get("net_assets_usd")
    if wf["exchange"]:
        return {"available": False,
                "reason": ("an exchange-listed wrapper has no fund-level repurchase capacity "
                           "to share, exit is at the market price, so the allocation slider "
                           "is not shown")}
    if na is None:
        why = wf.get("null_reasons", {}).get("net_assets_usd", "no reason recorded")
        return {"available": False,
                "reason": (f"the fund's net assets are not typed in the record ({why}), so "
                           "the plan's dollar demand cannot be set against the fund's dollar "
                           "capacity and the allocation slider is not shown")}
    if capacity_pct is None:
        return {"available": False,
                "reason": ("the wrapper's annual capacity is not computable (3.1), so the "
                           "fund's dollar capacity is not either and the allocation slider "
                           "is not shown")}
    if capacity_pct == 0:
        return {"available": False,
                "reason": ("the wrapper's annual capacity is 0% while repurchases are "
                           "suspended, so the plan's share of it is undefined and the "
                           "allocation slider is not shown")}
    if filed_rate is None:
        return {"available": False,
                "reason": ("the plan record carries no filed outflow proxy, so the plan's "
                           "dollar demand at the filed rate cannot be computed and the "
                           "allocation slider is not shown")}
    cap_usd = capacity_pct / 100 * na
    demand_usd = alloc_usd * filed_rate / 100
    return {"available": True,
            "fund_net_assets_usd": na,
            "net_assets_cell": wf.get("net_assets_cell"),
            "net_assets_approx": bool(wf.get("net_assets_approx")),
            "annual_capacity_usd": round(cap_usd),
            "plan_annual_demand_usd": round(demand_usd),
            "plan_share_of_fund_capacity_pct": round(demand_usd / cap_usd * 100, 2),
            "basis": ("plan demand = allocation share * plan net assets * filed outflow proxy, "
                      "fund capacity = binding annual cap * fund net assets")}


def _vs_capacity(pct: float, capacity: float | None) -> str:
    if capacity is None:
        return (f"{pct:.1f}% of the position per year, no annual wrapper capacity to compare "
                "against until the cap is typed (3.1)")
    return f"{pct:.1f}% of the position per year vs {capacity:.0f}% annual wrapper capacity"


def _headroom(pct: float, capacity: float | None, subject: str, base_clause: str) -> str:
    if capacity is None:
        return ""
    if capacity == 0:
        return (" EXCEEDS: repurchases are closed, so every request waits for the program "
                "to reopen.")
    if pct <= THIN_HEADROOM_SHARE * capacity:
        return f" {base_clause}"
    return (f" THIN HEADROOM: the {subject} consumes over 60% of wrapper capacity, so "
            "proration in any oversubscribed window would push the shortfall into the "
            "next window.")


def schedule_h_lines(plan: dict) -> tuple[list[str], list[str]]:
    """(scenario lines, structural lines) from the plan's Schedule H block
    (P1-18). Filed figures are used when present, with the model named.
    Absent figures are said to be absent, and the filed outflow proxy is
    named as what stands in for line 2e."""
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
                        "shown beside the filed outflow proxy and the slider assumption above, "
                        "not blended with them.")
    else:
        scenario.append(SCHEDULE_H_ABSENT)
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
    fo = filed_outflow(a)
    filed_rate = fo["rate_pct"] if fo else None
    py = fo["plan_year"] if fo else a.get("plan_year", "?")
    tail, active = sc_in["tail_annual_turnover_pct"], sc_in["active_annual_turnover_pct"]

    alloc = net * sc_in["allocation_pct_of_plan"] / 100
    slider_pct = slider_demand_pct(tail_share, tail, active)
    increment = stress_increment_pct(tail_share, tail, active)
    stressed_pct = stressed_demand_pct(filed_rate, tail_share, tail, active)
    filed_demand = None if filed_rate is None else alloc * filed_rate / 100
    slider_demand = alloc * slider_pct / 100
    stressed_demand = None if stressed_pct is None else alloc * stressed_pct / 100

    # ---- layer 1: structural, from typed facts ----
    verdict, s_reasons, missing = structural_verdict(wf)
    structural = list(s_reasons)
    if not wf["exchange"]:
        dealing = dealing_clause(wf)
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
                                 "hold this wrapper directly (cell 3.5), and the daily-menu "
                                 "constraint applies only to the participant-directed "
                                 "portion, where the menu assumes daily liquidity whereas "
                                 f"{dealing}.")
        else:
            structural.insert(0, "STRUCTURAL: plan direction codes do not show full "
                                 "participant direction, so DIA daily-menu framing may not "
                                 f"bind (cell 3.5). Either way, {dealing}.")
        if wf["early_fee"] != "none at fund level (2.7)":
            structural.append(f"Early repurchase economics: {wf['early_fee']}. Relevant "
                              "to participant-level churn (2.7).")

    # ---- layer 2: ILLUSTRATIVE scenario, per plan ----
    capacity, capacity_note = capacity_from_facts(wf)
    scv = scenario_verdict(filed_rate, stressed_pct, capacity, wf["exchange"])
    fc = fund_capacity(wf, alloc, filed_rate, capacity)
    scenario_reasons = [f"Capacity: {capacity_note}."]
    filed_words = ("the plan's total expenses less administrative expenses over beginning "
                   "net assets, applied to the position")
    slider_words = (f"from tail turnover {tail:g}%/yr on the {tail_share * 100:.1f}% of accounts "
                    f"that are separated and active turnover {active:g}%/yr on the rest. Shown "
                    "beside the filed rate, not blended with it")
    if wf["exchange"]:
        if filed_rate is not None:
            scenario_reasons.append(
                f"Filed outflow proxy (Schedule H, plan year {py}): {filed_rate:.1f}% of the "
                f"position per year, {filed_words}. On an exchange this is a selling rate "
                "against market depth, not a claim on a fund cap.")
        scenario_reasons.append(
            f"Slider assumption (illustrative): {slider_pct:.1f}% of the position per year, "
            f"{slider_words}, and likewise a selling rate against market depth.")
    else:
        if filed_rate is None:
            scenario_reasons.append(
                "Filed outflow proxy: not in the plan record, so the scenario has no base "
                "demand and no scenario verdict until the Schedule H totals are typed.")
        else:
            scenario_reasons.append(
                f"Filed outflow proxy (Schedule H, plan year {py}): "
                f"{_vs_capacity(filed_rate, capacity)}, {filed_words}."
                + _headroom(filed_rate, capacity, "filed rate",
                            "Adequate headroom at the filed rate if offers are not prorated."))
        scenario_reasons.append(
            f"Slider assumption (illustrative): {_vs_capacity(slider_pct, capacity)}, "
            f"{slider_words}."
            + _headroom(slider_pct, capacity, "slider assumption",
                        "Within 60% of wrapper capacity at these sliders."))
        if fc["available"]:
            approx = "approx. " if fc["net_assets_approx"] else ""
            scenario_reasons.append(
                f"Fund capacity in dollars: {capacity:g}% of {approx}{money(fc['fund_net_assets_usd'])} "
                f"net assets (cell {fc['net_assets_cell']}) is {money(fc['annual_capacity_usd'])} per "
                f"year. At a {sc_in['allocation_pct_of_plan']:g}% allocation ({money(alloc)}) the "
                f"plan's demand at the filed rate is {money(fc['plan_annual_demand_usd'])} per year, "
                f"{fc['plan_share_of_fund_capacity_pct']:.2f}% of that capacity. The cap is shared "
                "by every holder, so this is the plan's own claim on it, not the fund's total "
                "demand. The allocation moves these dollar figures and this share, never the "
                "percent-of-position ladder.")
        # when the dollar capacity is not computable the one-sentence reason
        # rides fund_capacity.reason: the view prints it where the slider
        # would be and the memo prints it in the scenario section
    if wf["exchange"]:
        outcome = "daily exchange liquidity, so stress transmits to price, not to a fund gate"
    elif capacity is None:
        outcome = "not computable until the capacity facts are typed (3.1)"
    elif stressed_pct is None:
        outcome = "not computable: the plan record carries no filed outflow proxy"
    elif stressed_pct > capacity:
        outcome = (f"EXCEEDS annual wrapper capacity ({stressed_pct:.1f}% vs {capacity:.0f}%). "
                   "Unmet demand rolls into later windows (gating-equivalent outcome)")
    else:
        outcome = (f"within wrapper capacity ({stressed_pct:.1f}% vs {capacity:.0f}%) IF offers are "
                   "not prorated" + (", but this issuer HAS prorated under stress (3.3)"
                                     if wf["gate_history"] else ""))
    stressed = {"illustrative": True,
                "base": FILED_LABEL,
                "assumptions": ("the filed outflow proxy plus the increment the sliders add "
                                f"under stress (tail turnover x{STRESS['tail_multiple']:.0f}, "
                                f"active turnover x{STRESS['active_multiple']:.1f} over the "
                                "slider assumption)"),
                "multiples": dict(STRESS),
                "filed_outflow_proxy_pct": filed_rate,
                "slider_assumption_pct": round(slider_pct, 1),
                "stress_increment_pct": round(increment, 1),
                "annual_demand_usd": None if stressed_demand is None else round(stressed_demand),
                "demand_pct_of_position": None if stressed_pct is None else round(stressed_pct, 1),
                "annual_wrapper_capacity_pct": capacity,
                "outcome": outcome}
    if scv and not wf["exchange"]:
        scenario_reasons.append(
            f"Scenario verdict (ILLUSTRATIVE, this plan): {scv}. {LADDER} {PRORATION}")
    elif not wf["exchange"]:
        scenario_reasons.append(
            f"Scenario verdict (ILLUSTRATIVE, this plan): not computable. {LADDER} {PRORATION}")
    sh_scenario, sh_structural = schedule_h_lines(a)
    if not wf["exchange"]:
        scenario_reasons.extend(sh_scenario)
    structural.extend(sh_structural)
    extra = (fc["net_assets_cell"],) if fc["available"] and fc.get("net_assets_cell") else ()

    return {
        "product": key, "plan": plan_key,
        "verdict": verdict,                       # structural, facts only
        "scenario_verdict": scv,                  # ILLUSTRATIVE, per plan
        "structural_reasons": structural,
        "scenario_reasons": scenario_reasons,
        "reasons": structural + scenario_reasons,
        "missing_facts": missing,
        "layers": ("verdict is structural (typed facts, cells 3.1, 3.3, 2.7, plan-independent). "
                   "scenario_verdict is ILLUSTRATIVE (the plan's filed outflow proxy as the base "
                   "demand and the sliders as the stress, against the same capacity, per plan)."),
        "filed_outflow": fo,
        "stressed_scenario": stressed,
        "plan_display_label": a["display_label"],
        "plan_direction": direction,
        "wrapper_facts": wf,
        "scenario": {**sc_in, "illustrative": True,
                     "base": FILED_LABEL,
                     "plan_allocation_usd": round(alloc),
                     "filed_outflow_proxy_pct": filed_rate,
                     "filed_annual_demand_usd": None if filed_demand is None else round(filed_demand),
                     "slider_assumption_pct": round(slider_pct, 1),
                     "slider_annual_demand_usd": round(slider_demand),
                     # the base demand under its long-standing keys, so every
                     # reader of the record sees the filed figure there
                     "demand_pct_of_position": filed_rate,
                     "annual_demand_usd": None if filed_demand is None else round(filed_demand),
                     "annual_wrapper_capacity_pct": capacity,
                     "fund_capacity": fc},
        "plan_inputs": {"net_assets": net,
                        "tail_share_pct": round(tail_share * 100, 1),
                        # the unrounded share, so the JavaScript port reproduces
                        # the dollar figures to the dollar
                        "tail_share": tail_share,
                        "separated_with_balances": part["separated_deferred_vested"],
                        "filed_outflow_proxy_pct": filed_rate,
                        "plan_year": py},
        "citations": citations(key, wf, plan_key, a, extra),
    }


if __name__ == "__main__":
    out = DATA / "liquidity"
    out.mkdir(exist_ok=True)
    for pk in plan_keys():
        for key in load_products():
            m = run_match(key, pk)
            (out / f"{pk}__{key}_match.json").write_text(json.dumps(m, indent=2))
            print(f"{pk:<26} {key:<18} {m['verdict']:<18} scenario {str(m['scenario_verdict']):<18} "
                  f"filed {m['scenario']['filed_outflow_proxy_pct']}%/yr "
                  f"stressed {m['stressed_scenario']['demand_pct_of_position']}%/yr")

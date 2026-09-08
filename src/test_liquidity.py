"""
Liquidity match gate (v2). Run: python src/test_liquidity.py

The structural verdict comes from typed facts alone and never varies with
the plan. The scenario verdict is ILLUSTRATIVE and must vary with the plan
for at least one product. A required fact left null yields partial unless
the program is suspended. No capacity text says "far inside" a cap.
"""
import json
import sys
from pathlib import Path

import tark_liquidity
from tark_liquidity import (FILED_LABEL, PERIODS_PER_YEAR, PRORATION, REQUIRED, RUNG_OF, SCHEDULE_H_ABSENT,
                            THIN_HEADROOM_SHARE, VERDICTS, binding_cap, capacity_from_facts, drivers_sentence,
                            load_facts, run_match, scenario_drivers, scenario_verdict, schedule_h_lines,
                            slider_demand_pct, stress_increment_pct, stressed_demand_pct, structural_verdict,
                            wrapper_facts)
from tark_data import DATA, _norm_words, load_plan, load_product, load_products, plan_keys, status_kind

FAILS: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}{(': ' + extra) if extra and not cond else ''}")
    if not cond:
        FAILS.append(name)


PLANS = plan_keys()
PRODUCTS = load_products()

# ---- structural ladder on synthetic typed facts
base = {"kind": "interval_23c3", "cadence_per_year": 4, "cap_pct": 5.0, "cap_base": "nav",
        "exchange": False, "gate_history": False, "program_status": None,
        "early_fee": "none at fund level (2.7)", "null_reasons": {}, "source_cell": "3.1"}
check("exchange-listed is aligned-mechanical", structural_verdict({**base, "exchange": True})[0] == "aligned-mechanical")
check("suspended program is misaligned", structural_verdict({**base, "program_status": "suspended"})[0] == "misaligned")
check("cap 0 is misaligned", structural_verdict({**base, "cap_pct": 0.0})[0] == "misaligned")
check("gating history is conditional-weak", structural_verdict({**base, "gate_history": True})[0] == "conditional-weak")
check("all facts typed and clean is conditional", structural_verdict(base)[0] == "conditional")
v, reasons, missing = structural_verdict({**base, "gate_history": None,
                                          "null_reasons": {"gate_history": "3.3 not extracted"}})
check("a null required fact yields partial and names it",
      v == "partial" and missing == ["gate_history"] and "3.3 not extracted" in reasons[0])
check("suspension takes precedence over a null fact",
      structural_verdict({**base, "program_status": "suspended", "gate_history": None})[0] == "misaligned")

# ---- scenario ladder (R2-P1-10: the base rung reads the filed outflow
# proxy, the stress rung reads the filed proxy plus the sliders' increment)
check("scenario: filed demand above capacity is misaligned", scenario_verdict(25.0, 30.0, 20.0, False) == "misaligned")
check("scenario: stressed demand above capacity is conditional-weak", scenario_verdict(10.0, 25.0, 20.0, False) == "conditional-weak")
check("scenario: within capacity under stress is conditional", scenario_verdict(5.0, 9.0, 20.0, False) == "conditional")
check("scenario: exchange-listed is aligned-mechanical", scenario_verdict(50.0, 90.0, None, True) == "aligned-mechanical")
check("scenario: capacity not computable yields no scenario verdict", scenario_verdict(5.0, 9.0, None, False) is None)
check("scenario: a filed rate above capacity is misaligned however low the sliders sit",
      scenario_verdict(25.0, 25.5, 20.0, False) == "misaligned")
check("scenario: no filed rate yields no scenario verdict", scenario_verdict(None, None, 20.0, False) is None)
check("stress arithmetic: filed 6.5, tail share 0.5, sliders 20/5 at x2/x1.5 gives 6.5 + (0.5 * 20 + 0.5 * 2.5) = 17.75",
      abs(stress_increment_pct(0.5, 20.0, 5.0) - 11.25) < 1e-9
      and abs(stressed_demand_pct(6.5, 0.5, 20.0, 5.0) - 17.75) < 1e-9
      and abs(slider_demand_pct(0.5, 20.0, 5.0) - 12.5) < 1e-9)

# ---- the record: every product under every plan
matches = {(pk, k): run_match(k, pk) for pk in PLANS for k in PRODUCTS}
check("every match carries a structural verdict from the allowed set and a layers note",
      all(m["verdict"] in VERDICTS and "structural" in m["layers"] for m in matches.values()))
check("structural verdict never varies with the plan",
      all(len({matches[(pk, k)]["verdict"] for pk in PLANS}) == 1 for k in PRODUCTS))
check("sreit is structurally misaligned under all four plans",
      all(matches[(pk, "sreit")]["verdict"] == "misaligned" for pk in PLANS))
check("breit is conditional-weak on its gating history",
      matches[("plan_tech_media", "breit")]["verdict"] == "conditional-weak")
check("dxyz and ssss are aligned-mechanical with the price caveat",
      all(matches[("plan_tech_media", k)]["verdict"] == "aligned-mechanical"
          and any("premium" in r for r in matches[("plan_tech_media", k)]["reasons"]) for k in ("dxyz", "ssss")))
partials = sorted(k for k in PRODUCTS if matches[("plan_tech_media", k)]["verdict"] == "partial")
check("partial verdicts name the missing fact and its reason",
      all(matches[("plan_tech_media", k)]["missing_facts"] and
          "Facts missing" in matches[("plan_tech_media", k)]["reasons"][1 if matches[("plan_tech_media", k)]["reasons"][0].startswith("STRUCTURAL") else 0]
          for k in partials), ", ".join(partials))
check("the scenario verdict differs between plan_tech_media and plan_consulting_alumni for at least one product",
      any(matches[("plan_tech_media", k)]["scenario_verdict"] != matches[("plan_consulting_alumni", k)]["scenario_verdict"]
          for k in PRODUCTS),
      "; ".join(f"{k}: {matches[('plan_tech_media', k)]['scenario_verdict']}" for k in PRODUCTS))
check("no capacity text says a position is far inside a cap",
      not any("far inside" in r for m in matches.values() for r in m["reasons"]))
check("a closed program has 0% capacity and the scenario says so",
      all(matches[(pk, "sreit")]["scenario"]["annual_wrapper_capacity_pct"] == 0
          and matches[(pk, "sreit")]["scenario_verdict"] == "misaligned"
          and any("closed" in r for r in matches[(pk, "sreit")]["reasons"]) for pk in PLANS))
check("every scenario reason block labels itself illustrative",
      all(any("illustrative" in r.lower() for r in m["scenario_reasons"]) or m["wrapper_facts"]["exchange"]
          for m in matches.values()))

# ---- P1-18: Schedule H fields are used when present, named absent otherwise
present = {"plan_year": "2024", "financials": {"net_assets_boy": 400_000_000.0},
           "schedule_h": {"benefit_payments_2e": {"value": 32_000_000.0, "source": "line 2e"},
                          "participant_contributions_2a1b": {"value": 20_000_000.0, "source": "line 2a(1)(B)"},
                          "qdia_indicator": {"value": "target-date series", "source": "plan document"}}}
sc_lines, st_lines = schedule_h_lines(present)
check("schedule H present: filed outflow rate printed with the model named",
      any("Schedule H based demand (filed, line 2e): benefit payments were 8.0%" in x and "Model:" in x for x in sc_lines))
check("schedule H present: contributions printed as a plan-level inflow",
      any("5.0% of beginning net assets" in x and "plan level" in x for x in sc_lines))
check("schedule H present: QDIA named in the structural reasons",
      any("Plan QDIA on file: target-date series" in x and "cell 3.5" in x for x in st_lines))
absent_lines, _ = schedule_h_lines({"financials": {"net_assets_boy": 1.0}, "schedule_h": {
    "benefit_payments_2e": {"value": None, "reason": "not typed in the test"}}})
# R2-P0-5: the absent sentence is fixed wording (no environment excuse, no
# file name), so the plan file's reason is no longer echoed into the match.
# R2-P1-10: it names the filed outflow proxy as what stands in for line 2e
# and the sliders as the stress, never as the base
check("schedule H absent: the match says line 2e is not yet in the plan record, names the filed outflow proxy as "
      "what stands in for it and the turnover assumptions as the stress",
      any(x == SCHEDULE_H_ABSENT and "line 2e is not yet in the plan record" in x
          and "filed outflow proxy" in x and "stands in for it" in x and "assumptions are the stress" in x
          for x in absent_lines)
      and "not typed in the test" not in " ".join(absent_lines))
check("today's four plans carry Schedule H as null-with-reason and every non-exchange match says so",
      all(any(r == SCHEDULE_H_ABSENT for r in m["scenario_reasons"])
          for m in matches.values() if not m["wrapper_facts"]["exchange"]))
check("no match or plan reason names a blocked host, a bulk file or the build container",
      not any(w in json.dumps(m) for m in matches.values()
              for w in ("askebsa", "bulk file", "build container", ".csv")))

# ---- R2-P0-5: reason strings read the facts they cite
cap_profile = {"kind": "interval_23c3", "exchange": False, "program_status": None, "cap_base": "NAV",
               "caps": [{"pct": 5.0, "period": "quarter"}], "null_reasons": {}}
check("binding figure: 2% per month and 5% per quarter binds at 20",
      binding_cap([{"pct": 2.0, "period": "month"}, {"pct": 5.0, "period": "quarter"}])[0] == 20.0
      and binding_cap([{"pct": 2.0, "period": "month"}, {"pct": 5.0, "period": "quarter"}])[1]["period"] == "quarter")
check("binding figure: 3% per month and 15% per quarter binds at 36",
      binding_cap([{"pct": 3.0, "period": "month"}, {"pct": 15.0, "period": "quarter"}])[0] == 36.0)
check("binding figure: a single 5% quarterly cap is 20", binding_cap([{"pct": 5.0, "period": "quarter"}])[0] == 20.0)
null_cap, null_note = capacity_from_facts({**cap_profile, "caps": None,
                                           "null_reasons": {"repurchase_caps": "cap not printed"}})
check("a null cap list on a non-exchange wrapper yields capacity None, not 0, and no scenario verdict",
      null_cap is None and "not computable" in null_note and "cap not printed" in null_note
      and scenario_verdict(5.0, 9.0, null_cap, False) is None)
check("a suspended program has 0% capacity whatever its caps say",
      capacity_from_facts({**cap_profile, "program_status": "suspended"})[0] == 0.0)
check("every non-exchange match's capacity equals the binding figure over its typed caps",
      all(m["scenario"]["annual_wrapper_capacity_pct"] == m["wrapper_facts"]["annual_capacity_pct"]
          and (m["wrapper_facts"]["program_status"] == "suspended"
               or m["wrapper_facts"]["annual_capacity_pct"] == binding_cap(m["wrapper_facts"]["caps"])[0])
          for m in matches.values() if not m["wrapper_facts"]["exchange"]))
sreit_reasons = [r for pk in PLANS for r in matches[(pk, "sreit")]["structural_reasons"]]
check("sreit: structural reasons say repurchases are suspended and never print a dealing count",
      any("repurchases are suspended" in r for r in sreit_reasons)
      and not any("deals" in r or "x/year" in r or "x per year" in r for r in sreit_reasons))
check("sreit: the dealing label names the suspension and its amendment",
      matches[("plan_tech_media", "sreit")]["wrapper_facts"]["dealing_label"]
      == "repurchases suspended since the April 29, 2026 amendment (3.1)")
jll = matches[("plan_tech_media", "jll_ipt")]
check("jll_ipt: reasons say daily dealing under a quarterly cap and never a per-year count",
      any("deals daily" in r and "cap per quarter" in r for r in jll["structural_reasons"])
      and not any("x/year" in r or "x per year" in r for r in jll["reasons"]))
check("jll_ipt: dealing cadence is daily, cap period is a quarter, annual capacity is 20",
      jll["wrapper_facts"]["dealing_cadence"] == "daily" and jll["wrapper_facts"]["cap_period"] == "quarter"
      and jll["scenario"]["annual_wrapper_capacity_pct"] == 20.0
      and jll["wrapper_facts"]["dealing_label"] == "daily repurchase requests, 5% cap per quarter on NAV")
br = matches[("plan_consulting_alumni", "breit")]
br_cap_note = next(r for r in br["scenario_reasons"] if r.startswith("Capacity:"))
check("breit: annual capacity is the binding 20, not 12 * 2 = 24",
      br["scenario"]["annual_wrapper_capacity_pct"] == 20.0
      and br["wrapper_facts"]["caps"] == [{"pct": 2.0, "period": "month"}, {"pct": 5.0, "period": "quarter"}])
check("breit: the capacity note names both caps and the one that binds",
      "2% per month and 5% per quarter" in br_cap_note and "binding annual figure is 20%" in br_cap_note
      and "quarterly cap" in br_cap_note)
check("breit: the structural gap sentence prints both caps in words, no per-year count",
      any("deals monthly" in r and "2% per month and 5% per quarter" in r for r in br["structural_reasons"])
      and not any("x/year" in r for r in br["reasons"]))
check("breit under plan_consulting_alumni: 13.7% demand against 20% capacity is THIN HEADROOM",
      any("THIN HEADROOM" in r for r in br["scenario_reasons"]))
check("breit under plan_consulting_alumni: the THIN HEADROOM sentence belongs to the 13.7% slider assumption, "
      "and the 6.5% filed outflow proxy line says adequate headroom at the filed rate",
      any(r.startswith("Slider assumption (illustrative): 13.7% of the position per year vs 20% annual wrapper capacity")
          and "THIN HEADROOM: the slider assumption" in r for r in br["scenario_reasons"])
      and any(r.startswith("Filed outflow proxy (Schedule H, plan year 2024-01-01 to 2024-12-31): 6.5% of the position "
                           "per year vs 20% annual wrapper capacity")
              and "Adequate headroom at the filed rate" in r for r in br["scenario_reasons"]))
check("breit: the caps label names both caps and the binding annual figure",
      br["wrapper_facts"]["caps_label"] == "2% per month and 5% per quarter, binding 20% per year")
check("every match carries the display labels for the site and the memo",
      all(m["wrapper_facts"].get("dealing_label") and m["wrapper_facts"].get("caps_label")
          and "annual_capacity_pct" in m["wrapper_facts"] for m in matches.values()))
check("no reason string prints a dealing count as Nx/year",
      not any("x/year" in r or "x per year" in r for m in matches.values() for r in m["reasons"]))
bad_cites = []
for (pk, k), m in matches.items():
    cells = load_product(k)["cells"]
    for c in m["citations"]:
        if not c[:1].isdigit():
            continue
        if c == "3.9":
            bad_cites.append(f"{k}: cites 3.9")
        elif c not in cells or status_kind(str(cells[c].get("status", ""))) == "n/a":
            bad_cites.append(f"{k}: cites {c} ({cells.get(c, {}).get('status')})")
check("no match cites cell 3.9 or a cell whose status is n/a for that product", not bad_cites,
      "; ".join(sorted(set(bad_cites))[:6]))
check("every match cites cell 3.1 and the plan, and 2.7 wherever the product's 2.7 is not n/a",
      all("3.1" in m["citations"] and any(c.startswith("the plan record on file (Form 5500") for c in m["citations"])
          and (("2.7" in m["citations"])
               == (status_kind(str(load_product(k)["cells"]["2.7"].get("status", ""))) != "n/a"))
          for (pk, k), m in matches.items()))
check("cell 3.7 is cited exactly where the product's cell is not n/a",
      all(("3.7" in m["citations"]) == (status_kind(str(load_product(k)["cells"]["3.7"].get("status", ""))) != "n/a")
          for (pk, k), m in matches.items()))
check("the dealing cadence and the cap period are typed for every non-exchange product",
      all(m["wrapper_facts"]["dealing_cadence"] in ("daily", "monthly", "quarterly")
          and m["wrapper_facts"]["cap_period"] in ("month", "quarter", "year")
          and m["wrapper_facts"]["caps"] for m in matches.values() if not m["wrapper_facts"]["exchange"]))

# ---- committed artifacts equal a fresh run's verdicts, and the wrapper facts name cells
drift = []
for (pk, k), m in matches.items():
    p = DATA / "liquidity" / f"{pk}__{k}_match.json"
    if not p.exists():
        drift.append(f"{pk}/{k}: missing"); continue
    d = json.loads(p.read_text())
    if (d["verdict"], d["scenario_verdict"]) != (m["verdict"], m["scenario_verdict"]):
        drift.append(f"{pk}/{k}: committed {d['verdict']}/{d['scenario_verdict']} vs {m['verdict']}/{m['scenario_verdict']}")
check("committed match files carry the verdicts a fresh run produces", not drift, "; ".join(drift[:4]))
check("wrapper facts cite cells and carry a reason for every null",
      all(wrapper_facts(k)["source_cell"] and
          all(wrapper_facts(k)["null_reasons"].get(n) for n in REQUIRED
              if wrapper_facts(k)[{"repurchase_cadence_per_year": "cadence_per_year",
                                   "repurchase_cap_pct": "cap_pct", "gate_history": "gate_history"}[n]] is None)
          for k in PRODUCTS))

# ---- R2-P1-10: the base demand is the plan's filed outflow proxy, the sliders are the stress
plans_doc = {pk: load_plan(pk) for pk in PLANS}
proxy = {pk: (plans_doc[pk].get("schedule_h") or {}).get("filed_outflow_proxy") or {} for pk in PLANS}
check("every plan file types a filed outflow proxy with its formula, its three inputs, its plan year and its source",
      all(isinstance(proxy[pk].get("value"), (int, float)) and proxy[pk].get("formula") and proxy[pk].get("source")
          and proxy[pk].get("plan_year")
          and set(proxy[pk].get("inputs") or {}) == {"tot_expenses", "tot_admin_expenses", "net_assets_boy"}
          for pk in PLANS))
check("the filed outflow proxy is (total expenses - administrative expenses) / beginning net assets * 100, recomputed here",
      all(proxy[pk].get("value") == round((plans_doc[pk]["financials"]["tot_expenses"]
                                           - plans_doc[pk]["financials"]["tot_admin_expenses"])
                                          / plans_doc[pk]["financials"]["net_assets_boy"] * 100, 2)
          and all((proxy[pk]["inputs"][n] or {}).get("value") == plans_doc[pk]["financials"][n]
                  for n in ("tot_expenses", "tot_admin_expenses", "net_assets_boy"))
          for pk in PLANS))
check("the four filed rates in the match files equal the plan files' proxy values, in every match and in every block",
      all(m["scenario"]["filed_outflow_proxy_pct"] == proxy[pk]["value"]
          and m["plan_inputs"]["filed_outflow_proxy_pct"] == proxy[pk]["value"]
          and m["filed_outflow"]["rate_pct"] == proxy[pk]["value"]
          and m["stressed_scenario"]["filed_outflow_proxy_pct"] == proxy[pk]["value"]
          for (pk, k), m in matches.items()))
check("the four plans' filed rates are distinct, so the ranking they give the scenario layer is theirs, not the sliders'",
      len({proxy[pk]["value"] for pk in PLANS}) == len(PLANS))
check("the base demand of every match is the filed outflow proxy applied to the position, in percent and in dollars",
      all(m["scenario"]["base"] == FILED_LABEL
          and m["scenario"]["demand_pct_of_position"] == m["scenario"]["filed_outflow_proxy_pct"]
          and abs(m["scenario"]["filed_annual_demand_usd"]
                  - m["scenario"]["plan_allocation_usd"] * m["scenario"]["filed_outflow_proxy_pct"] / 100) <= 1
          and m["scenario"]["annual_demand_usd"] == m["scenario"]["filed_annual_demand_usd"]
          for m in matches.values()))
check("the slider assumption is tail turnover on the separated share of accounts and active turnover on the rest",
      all(abs(m["scenario"]["slider_assumption_pct"]
              - slider_demand_pct(m["plan_inputs"]["tail_share_pct"] / 100, m["scenario"]["tail_annual_turnover_pct"],
                                  m["scenario"]["active_annual_turnover_pct"])) < 0.06
          for m in matches.values()))
check("the stressed demand is the filed outflow proxy plus the sliders' stress increment, never the slider model alone",
      all(m["stressed_scenario"]["base"] == FILED_LABEL
          and abs(m["stressed_scenario"]["demand_pct_of_position"]
                  - (m["scenario"]["filed_outflow_proxy_pct"] + m["stressed_scenario"]["stress_increment_pct"])) < 0.11
          and abs(m["stressed_scenario"]["stress_increment_pct"]
                  - stress_increment_pct(m["plan_inputs"]["tail_share_pct"] / 100, m["scenario"]["tail_annual_turnover_pct"],
                                         m["scenario"]["active_annual_turnover_pct"], m["stressed_scenario"]["multiples"])) < 0.06
          for m in matches.values()))
check("every match's scenario verdict is the ladder on the filed rate and the stressed demand it carries",
      all(m["scenario_verdict"] == scenario_verdict(m["scenario"]["filed_outflow_proxy_pct"],
                                                    m["scenario"]["filed_outflow_proxy_pct"]
                                                    + m["stressed_scenario"]["stress_increment_pct"]
                                                    if m["stressed_scenario"]["stress_increment_pct"] is not None else None,
                                                    m["scenario"]["annual_wrapper_capacity_pct"], m["wrapper_facts"]["exchange"])
          for m in matches.values()))
# the brief's test: the plan whose filing shows the lowest outflow rate is
# never the only plan flagged conditional-weak for a product, unless its own
# filed rate is already in thin headroom against that wrapper (the filed
# rates then say so). Under the slider-only model the lowest-filed plan was
# the only weak one for 13 products (audit item 24).
lowest = min(PLANS, key=lambda pk: proxy[pk]["value"])
offenders = []
for k in PRODUCTS:
    weak = [pk for pk in PLANS if matches[(pk, k)]["scenario_verdict"] == "conditional-weak"]
    cap = matches[(lowest, k)]["scenario"]["annual_wrapper_capacity_pct"]
    if weak == [lowest] and not (cap and proxy[lowest]["value"] > THIN_HEADROOM_SHARE * cap):
        offenders.append(k)
check(f"the plan with the lowest filed outflow rate ({lowest}) is not the only plan flagged conditional-weak for any "
      "product unless its filed rate says so", not offenders, ", ".join(offenders))
check("the scenario verdict still differs between plans for at least one product, now on the filings",
      any(len({matches[(pk, k)]["scenario_verdict"] for pk in PLANS}) > 1 for k in PRODUCTS))
_hl_c = matches[("plan_consulting_alumni", "hl_paf")]
_hl_c45 = run_match("hl_paf", "plan_consulting_alumni", {"tail_annual_turnover_pct": 45.0})
check("the turnover sliders move the stressed demand and can move the verdict (hl_paf under the consulting plan: "
      "tail turnover 45 pushes the stressed demand past 20% and the verdict to conditional-weak)",
      _hl_c["scenario_verdict"] == "conditional" and _hl_c45["scenario_verdict"] == "conditional-weak"
      and _hl_c45["stressed_scenario"]["demand_pct_of_position"] > 20
      and _hl_c45["scenario"]["filed_outflow_proxy_pct"] == _hl_c["scenario"]["filed_outflow_proxy_pct"])
check("every non-exchange match prints the filed outflow proxy and the slider assumption as separate labeled lines "
      "carrying their own numbers, the slider line saying it is not blended with the filed rate",
      all(any(r.startswith("Filed outflow proxy (Schedule H, plan year ")
              and f"{m['scenario']['filed_outflow_proxy_pct']:.1f}% of the position per year" in r
              for r in m["scenario_reasons"])
          and any(r.startswith("Slider assumption (illustrative): ")
                  and f"{m['scenario']['slider_assumption_pct']:.1f}% of the position per year" in r
                  and "not blended with it" in r for r in m["scenario_reasons"])
          for m in matches.values() if not m["wrapper_facts"]["exchange"]))
# ---- R3-P2-7: the scenario verdict names the rung that fired and the product facts it read
def _verdict_line(m):
    return next(r for r in m["scenario_reasons"] if r.startswith("Scenario verdict (ILLUSTRATIVE, this plan): "))
check("the verdict sentence names the fired rung, the filed and stressed figures, the capacity and the proration assumption",
      all(f": {m['scenario_verdict']}. " in _verdict_line(m)
          and m["scenario"]["drivers"]["sentence"] in _verdict_line(m) and PRORATION in _verdict_line(m)
          and f"{m['scenario']['filed_outflow_proxy_pct']:.1f}%" in _verdict_line(m)
          and (m["scenario_verdict"] == "misaligned"
               or f"{m['stressed_scenario']['demand_pct_of_position']:.1f}%" in _verdict_line(m))
          and f"{m['scenario']['annual_wrapper_capacity_pct']:.0f}%" in _verdict_line(m)
          for m in matches.values() if not m["wrapper_facts"]["exchange"]))
check("every match's drivers record names the rung of its verdict, the binding cap, the cadence, the program status "
      "and the gating history from the typed inputs, and the sentence is the record's own",
      all(d["rung"] == RUNG_OF[m["scenario_verdict"]]
          and d["binding_cap"] == binding_cap(m["wrapper_facts"]["caps"])[1]
          and d["dealing_cadence"] == m["wrapper_facts"]["dealing_cadence"]
          and d["program_status"] == m["wrapper_facts"]["program_status"]
          and d["gate_history"] == m["wrapper_facts"]["gate_history"]
          and d["sentence"] == drivers_sentence(d)
          and d["compared"]["capacity_pct"] == m["scenario"]["annual_wrapper_capacity_pct"]
          for m in matches.values() for d in [m["scenario"]["drivers"]]))
check("the per-window figures restate the annual test over the binding cap's own window and never change the rung",
      all(abs(w["stressed_per_window_pct"] * w["windows_per_year"] - d["compared"]["stressed_pct"]) < 1e-9
          and w["windows_per_year"] == PERIODS_PER_YEAR[w["period"]] and w["cap_per_window_pct"] == d["binding_cap"]["pct"]
          and ((w["stressed_per_window_pct"] > w["cap_per_window_pct"]) == (d["compared"]["stressed_pct"] > d["compared"]["capacity_pct"]))
          for m in matches.values() for d in [m["scenario"]["drivers"]] for w in [d["window"]] if w))
check("no per-window figure is printed against a 0% cap, an uncomputable capacity or an exchange",
      all(m["scenario"]["drivers"]["window"] is None for m in matches.values()
          if not m["scenario"]["annual_wrapper_capacity_pct"]))
check("the drivers sentence prints every fact it read with its cell: the rung word, the cap, the cadence noun, the "
      "program status with its as-of date, the gating history (hl_paf under the tech plan)",
      all(x in matches[("plan_tech_media", "hl_paf")]["scenario"]["drivers"]["sentence"]
          for x in ("Stress rung", "binding cap 5% per quarter on net assets (3.1)", "quarterly offers (3.1)",
                    "program active as of 2026-03-31 (3.1)", "gating history not on record (3.3)", "Per quarter: filed 2.9% and stressed 5.1%")))
check("sreit's sentence names the base rung, the suspension and the proration precedent, and prints no window against the 0% cap",
      "Base rung" in matches[("plan_tech_media", "sreit")]["scenario"]["drivers"]["sentence"]
      and "repurchases suspended (3.1)" in matches[("plan_tech_media", "sreit")]["scenario"]["drivers"]["sentence"]
      and "prorated under stress before (3.3)" in matches[("plan_tech_media", "sreit")]["scenario"]["drivers"]["sentence"]
      and "Per month" not in matches[("plan_tech_media", "sreit")]["scenario"]["drivers"]["sentence"])
check("an exchange-listed match records the exchange rung and no capacity",
      all(m["scenario"]["drivers"]["rung"] == "exchange" and m["scenario"]["drivers"]["window"] is None
          for m in matches.values() if m["wrapper_facts"]["exchange"]))
# the property: the product's own cap moves its verdict and nothing else's.
# hl_paf under the tech plan sits on the stress rung at 5% per quarter; at 10%
# per quarter the same plan demand fits and the rung is none, while every
# other product's match is byte for byte what the record holds
_real_load = tark_liquidity.load_facts
def _wider_cap(key):
    fx = json.loads(json.dumps(_real_load(key)))
    if key == "hl_paf":
        fx["repurchase_caps"]["value"] = [{"pct": 10.0, "period": "quarter"}]
        fx["repurchase_cap_pct"]["value"] = 10.0
    return fx
tark_liquidity.load_facts = _wider_cap
try:
    _hl_wide = run_match("hl_paf", "plan_tech_media")
    _others_wide = {k: run_match(k, "plan_tech_media") for k in PRODUCTS if k != "hl_paf"}
finally:
    tark_liquidity.load_facts = _real_load
check("perturbing one product's cap moves only that product's verdict: hl_paf at 10% per quarter drops from the stress rung "
      "to none under the tech plan (capacity 40%), the drivers say so, and the other 15 matches are unchanged",
      matches[("plan_tech_media", "hl_paf")]["scenario_verdict"] == "conditional-weak"
      and _hl_wide["scenario_verdict"] == "conditional" and _hl_wide["scenario"]["annual_wrapper_capacity_pct"] == 40.0
      and _hl_wide["scenario"]["drivers"]["rung"] == "none"
      and "binding cap 10% per quarter" in _hl_wide["scenario"]["drivers"]["sentence"]
      and all(_others_wide[k] == matches[("plan_tech_media", k)] for k in _others_wide))
check("the same perturbation leaves the plan-side figures where the filing put them (filed and stressed demand unchanged)",
      _hl_wide["scenario"]["filed_outflow_proxy_pct"] == matches[("plan_tech_media", "hl_paf")]["scenario"]["filed_outflow_proxy_pct"]
      and _hl_wide["stressed_scenario"]["demand_pct_of_position"] == matches[("plan_tech_media", "hl_paf")]["stressed_scenario"]["demand_pct_of_position"])
# the program status is typed for every product that has a program (R3-P2-7)
check("repurchase program status is typed for every non-exchange product ('active' or 'suspended') with the date it was "
      "read at, and null with the reason only for the two exchange-listed wrappers",
      all((load_facts(k)["repurchase_program_status"]["value"] in ("active", "suspended")
           and load_facts(k)["repurchase_program_status"].get("as_of"))
          if not matches[("plan_tech_media", k)]["wrapper_facts"]["exchange"]
          else (load_facts(k)["repurchase_program_status"]["value"] is None
                and "exchange-listed" in load_facts(k)["repurchase_program_status"]["reason"])
          for k in PRODUCTS))
check("every match's scenario inputs carry the program status and its as-of date the facts carry",
      all(m["wrapper_facts"]["scenario_inputs"]["program_status"] == load_facts(m["product"])["repurchase_program_status"]["value"]
          and m["wrapper_facts"]["scenario_inputs"]["program_status_as_of"] == load_facts(m["product"])["repurchase_program_status"].get("as_of")
          for m in matches.values()))
check("the two slider-independent pieces of the bullets ride the scenario typed: the capacity note and the Schedule H lines",
      all(f"Capacity: {m['scenario']['capacity_note']}." == m["scenario_reasons"][0]
          and (m["scenario"]["schedule_h_lines"] == [] if m["wrapper_facts"]["exchange"]
               else m["scenario_reasons"][-len(m["scenario"]["schedule_h_lines"]):] == m["scenario"]["schedule_h_lines"])
          for m in matches.values()))
check("the stressed outcome prints the stressed figure it compares, never the slider figure",
      all(f"{m['stressed_scenario']['demand_pct_of_position']:.1f}%" in m["stressed_scenario"]["outcome"]
          for m in matches.values()
          if not m["wrapper_facts"]["exchange"] and m["scenario"]["annual_wrapper_capacity_pct"] is not None))
check("no reason string calls the slider figure the scenario demand or the base",
      not any("Scenario demand (illustrative)" in r or "sliders only" in r for m in matches.values() for r in m["reasons"]))
check("exchange-listed matches print both rates as selling rates against market depth, not against a fund cap",
      all(any(r.startswith("Filed outflow proxy") and "market depth" in r for r in m["scenario_reasons"])
          and any(r.startswith("Slider assumption") and "market depth" in r for r in m["scenario_reasons"])
          for m in matches.values() if m["wrapper_facts"]["exchange"]))

# ---- R2-P1-11: the allocation moves dollars against the fund's own dollar capacity, or is removed
na_typed = {k: load_facts(k)["net_assets_usd"].get("value") is not None for k in PRODUCTS}
check("the fund's dollar capacity is computed exactly where the fund's net assets are typed, the wrapper is not "
      "exchange-listed and its annual cap is computable and above 0",
      all(m["scenario"]["fund_capacity"]["available"]
          == (na_typed[k] and not m["wrapper_facts"]["exchange"]
              and (m["scenario"]["annual_wrapper_capacity_pct"] or 0) > 0)
          for (pk, k), m in matches.items()))
_with = sorted(k for k in PRODUCTS if matches[("plan_tech_media", k)]["scenario"]["fund_capacity"]["available"])
check("today six products carry the allocation slider (fund net assets typed with a source cell)",
      _with == ["cion_ares", "hl_paf", "kkr_kpec", "ocic", "pflex", "stepstone_spm"], ", ".join(_with))
check("where available: fund capacity = binding annual cap * fund net assets, plan demand = allocation share * plan net "
      "assets * filed rate, share = demand / capacity, and the net assets cell is cited",
      all(abs(fc["annual_capacity_usd"] - m["scenario"]["annual_wrapper_capacity_pct"] / 100 * fc["fund_net_assets_usd"]) <= 1
          and abs(fc["plan_annual_demand_usd"] - m["plan_inputs"]["net_assets"] * m["scenario"]["allocation_pct_of_plan"] / 100
                  * m["scenario"]["filed_outflow_proxy_pct"] / 100) <= 1
          and abs(fc["plan_share_of_fund_capacity_pct"] - fc["plan_annual_demand_usd"] / fc["annual_capacity_usd"] * 100) < 0.011
          and fc["net_assets_cell"] in m["citations"]
          and any(r.startswith("Fund capacity in dollars: ") and f"{fc['plan_share_of_fund_capacity_pct']:.2f}% of that capacity" in r
                  and "shared by every holder" in r for r in m["scenario_reasons"])
          for m in matches.values() for fc in [m["scenario"]["fund_capacity"]] if fc["available"]))
_hl_t = matches[("plan_tech_media", "hl_paf")]
_hl_t10 = run_match("hl_paf", "plan_tech_media", {"allocation_pct_of_plan": 10.0})
check("hl_paf: doubling the allocation doubles the plan's dollar demand and its share of the fund's capacity, and moves "
      "no percent-of-position figure and no verdict",
      abs(_hl_t10["scenario"]["fund_capacity"]["plan_share_of_fund_capacity_pct"]
          - 2 * _hl_t["scenario"]["fund_capacity"]["plan_share_of_fund_capacity_pct"]) < 0.02
      and _hl_t10["scenario"]["fund_capacity"]["plan_annual_demand_usd"] > 1.99 * _hl_t["scenario"]["fund_capacity"]["plan_annual_demand_usd"]
      and (_hl_t10["scenario"]["filed_outflow_proxy_pct"], _hl_t10["scenario"]["slider_assumption_pct"],
           _hl_t10["stressed_scenario"]["demand_pct_of_position"], _hl_t10["scenario_verdict"])
      == (_hl_t["scenario"]["filed_outflow_proxy_pct"], _hl_t["scenario"]["slider_assumption_pct"],
          _hl_t["stressed_scenario"]["demand_pct_of_position"], _hl_t["scenario_verdict"]))
check("where the fund's dollar capacity is not computable, the match carries one reason sentence that names the "
      "missing allocation slider, prints no dollar share and no dollar line",
      all((fc["reason"] and "allocation slider is not shown" in fc["reason"]
           and not any(r.startswith("Fund capacity in dollars") for r in m["scenario_reasons"])
           and "plan_share_of_fund_capacity_pct" not in fc)
          for m in matches.values() for fc in [m["scenario"]["fund_capacity"]] if not fc["available"]))
check("the reason for a missing slider names the cause (net assets not on record, exchange-listed, or a 0% or unknown cap)",
      all(("net assets are not on record" in fc["reason"] or "exchange-listed" in fc["reason"]
           or "0% while repurchases are suspended" in fc["reason"] or "not computable (3.1)" in fc["reason"])
          for m in matches.values() for fc in [m["scenario"]["fund_capacity"]] if not fc["available"]))

# ---- R2-P1-12: gate_history is typed by one rule and every judgment quotes its cell
GATE_BY_RULE = {"bcred": True, "breit": True, "sreit": True,
                "pflex": False, "jll_ipt": False, "cion_ares": False, "ssss": False, "dxyz": False,
                "hl_paf": None, "cliffwater_cclfx": None, "ocic": None, "stepstone_spm": None,
                "ares_pmf": None, "kkr_kpec": None, "arkvx": None, "amg_pantheon": None}
check("gate_history by the rule: True where a filing states proration, False where it states full fills or no right "
      "to gate, null where tendered-versus-accepted amounts are not printed (all 16)",
      all(load_facts(k)["gate_history"]["value"] is GATE_BY_RULE[k] for k in PRODUCTS))
check("every gate_history fact carries an evidence phrase found verbatim in its cited cell (case-insensitive, "
      "whitespace-normalized), null facts included",
      all(_norm_words(load_facts(k)["gate_history"].get("evidence_phrase"))
          and _norm_words(load_facts(k)["gate_history"]["evidence_phrase"])
          in _norm_words(load_product(k)["cells"][load_facts(k)["gate_history"]["source_cell"]].get("value"))
          for k in PRODUCTS))
check("every typed dealing cadence, cap period, program status and big4 flag carries an evidence phrase found in its cell",
      all(_norm_words(f.get("evidence_phrase"))
          and _norm_words(f["evidence_phrase"]) in _norm_words(load_product(k)["cells"][f["source_cell"]].get("value"))
          for k in PRODUCTS for n, f in load_facts(k).items()
          if n in ("dealing_cadence", "cap_period", "repurchase_program_status", "big4") and f.get("value") is not None))
check("a null gate_history yields the partial structural verdict, and bcred's printed Q2-2026 proration yields conditional-weak",
      all(matches[("plan_tech_media", k)]["verdict"] == "partial" for k in ("ares_pmf", "kkr_kpec", "arkvx", "amg_pantheon")
          if matches[("plan_tech_media", k)]["wrapper_facts"]["program_status"] != "suspended")
      and matches[("plan_tech_media", "bcred")]["verdict"] == "conditional-weak")
# the validator refuses a phrase that is not in the cell: a scratch copy of the
# record with one phrase corrupted must fail validate_facts on that fact
import os  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
_tmp = Path(tempfile.mkdtemp(prefix="tark_phrase_"))
for _sub in ("products", "facts", "plans"):
    shutil.copytree(DATA / _sub, _tmp / _sub)
for _f in DATA.glob("*.json"):
    shutil.copy(_f, _tmp / _f.name)
for _f in DATA.glob("*.csv"):
    shutil.copy(_f, _tmp / _f.name)
_fp = _tmp / "facts" / "breit.json"
_doc = json.loads(_fp.read_text())
_doc["facts"]["gate_history"]["evidence_phrase"] = "words the cell does not contain"
_fp.write_text(json.dumps(_doc))
_r = subprocess.run([sys.executable, "-c",
                     "from tark_data import validate_facts; import json; print(json.dumps(validate_facts()))"],
                    env={**os.environ, "TARK_DATA_DIR": str(_tmp)}, capture_output=True, text=True,
                    cwd=str(Path(__file__).resolve().parent))
_errs = json.loads(_r.stdout.strip().splitlines()[-1]) if _r.returncode == 0 and _r.stdout.strip() else [f"validator crashed: {_r.stderr[-300:]}"]
check("validate_facts fails when an evidence phrase is absent from the cell (breit gate_history corrupted in a scratch copy)",
      any("breit:gate_history" in e and "evidence_phrase" in e for e in _errs), "; ".join(_errs[:3]))
shutil.rmtree(_tmp, ignore_errors=True)

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll liquidity tests pass.")
sys.exit(1 if FAILS else 0)

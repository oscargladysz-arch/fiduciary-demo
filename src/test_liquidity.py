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

from tark_liquidity import (REQUIRED, VERDICTS, run_match, scenario_verdict,
                            schedule_h_lines, structural_verdict, wrapper_facts)
from tark_data import DATA, load_products, plan_keys

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

# ---- scenario ladder
check("scenario: base demand above capacity is misaligned", scenario_verdict(25.0, 30.0, 20.0, False) == "misaligned")
check("scenario: stressed demand above capacity is conditional-weak", scenario_verdict(10.0, 25.0, 20.0, False) == "conditional-weak")
check("scenario: within capacity under stress is conditional", scenario_verdict(5.0, 9.0, 20.0, False) == "conditional")
check("scenario: exchange-listed is aligned-mechanical", scenario_verdict(50.0, 90.0, None, True) == "aligned-mechanical")
check("scenario: capacity not computable yields no scenario verdict", scenario_verdict(5.0, 9.0, None, False) is None)

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
check("schedule H absent: the match says so with the plan file's reason and uses the sliders only",
      any("not typed in the test" in x and "sliders only" in x for x in absent_lines))
check("today's four plans carry Schedule H as null-with-reason and every non-exchange match says so",
      all(any("Schedule H benefit payments (line 2e)" in r and "sliders only" in r for r in m["scenario_reasons"])
          for m in matches.values() if not m["wrapper_facts"]["exchange"]))

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

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll liquidity tests pass.")
sys.exit(1 if FAILS else 0)

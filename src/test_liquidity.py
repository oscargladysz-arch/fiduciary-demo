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

from tark_liquidity import (REQUIRED, SCHEDULE_H_ABSENT, VERDICTS, binding_cap,
                            capacity_from_facts, run_match, scenario_verdict,
                            schedule_h_lines, structural_verdict, wrapper_facts)
from tark_data import DATA, load_product, load_products, plan_keys, status_kind

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
# R2-P0-5: the absent sentence is fixed wording (no environment excuse, no
# file name), so the plan file's reason is no longer echoed into the match
check("schedule H absent: the match says the lines are not yet in the plan record and uses the sliders only",
      any(x == SCHEDULE_H_ABSENT and "sliders only" in x for x in absent_lines)
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
      all("3.1" in m["citations"] and any(c.startswith("plan: ") for c in m["citations"])
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

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll liquidity tests pass.")
sys.exit(1 if FAILS else 0)

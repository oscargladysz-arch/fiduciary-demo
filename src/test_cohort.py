"""
Unit tests for the cohort engine — R4 phrasing law, stats/percentile math on
toy cohorts, composite arithmetic by hand, caveat-block assembly.
Run: python src/test_cohort.py   (exit 0 = all pass)
"""
import sys

import tark_cohort as tc

FAILS = []


def check(name, cond):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        FAILS.append(name)


# ---- toy cohort injected around the module's data structures ----
tc.COHORTS["_toy3"] = {
    "label": "toy n=3", "members": ["a", "b", "c"],
    "wrapper_types": {"a": "interval_23c3", "b": "interval_23c3",
                      "c": "interval_23c3"},
}
tc.COHORTS["_toy5"] = {
    "label": "toy n=5", "members": ["a", "b", "c", "d", "e"],
    "wrapper_types": {k: "interval_23c3" for k in "abcde"},
}
FACTS3 = {k: {"fee": {"value": v}} for k, v in
          {"a": 1.0, "b": 2.0, "c": 4.0}.items()}
FACTS5 = {k: {"fee": {"value": v}} for k, v in
          {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0, "e": 5.0}.items()}
FACTS_GAP = {"a": {"fee": {"value": 1.0}},
             "b": {"fee": {"value": None, "reason": "cell partial"}},
             "c": {"fee": {"value": 3.0}}}

# ---- stats ----
st = tc.cohort_stats("_toy3", "fee", FACTS3)
check("stats median n=3", st["median"] == 2.0 and st["n"] == 3)
check("stats min/max", st["min"] == 1.0 and st["max"] == 4.0)
stg = tc.cohort_stats("_toy3", "fee", FACTS_GAP)
check("stats: nulls stay visible with reasons",
      stg["n"] == 2 and stg["missing"]["b"] == "cell partial")

# ---- R4 phrasing law ----
p3 = tc.percentile_of("c", "_toy3", "fee", FACTS3)
check("n=3: 'percentile' word BANNED", "percentile" not in p3["phrase"]
      or "too small for percentile" in p3["phrase"])
check("n=3: median-relative phrasing",
      "above the cohort median" in p3["phrase"] and "n=3" in p3["phrase"])
p5 = tc.percentile_of("e", "_toy5", "fee", FACTS5)
check("n=5: percentile allowed", "percentile" in p5["phrase"])
check("n=5: top value = 90th percentile ((4+0.5)/5)", p5["percentile"] == 90)
p5m = tc.percentile_of("c", "_toy5", "fee", FACTS5)
check("n=5: median member at 50th", p5m["percentile"] == 50)
pn = tc.percentile_of("b", "_toy3", "fee", FACTS_GAP)
check("null-fact member gets None placement",
      tc.percentile_of("b", "_toy3", "fee", FACTS_GAP) is None
      or pn is None)

# ---- caveat assembly ----
cv_same = tc.caveat_block("_toy3")
check("homogeneous cohort: no wrapper caveats", cv_same == [])
tc.COHORTS["_toymix"] = {
    "label": "mix", "members": ["a", "b"],
    "wrapper_types": {"a": "interval_23c3", "b": "listed_bdc"},
}
cv_mix = tc.caveat_block("_toymix")
check("mixed cohort: pricing-basis caveat fires",
      any("PRICING-BASIS MIX" in c for c in cv_mix))
check("mixed cohort: leverage-regime caveat fires",
      any("LEVERAGE-REGIME MIX" in c for c in cv_mix))

# ---- composite: refusal law + arithmetic ----
comp_mix = tc.composite("_toymix")
check("heterogeneous pricing basis: composite REFUSED",
      comp_mix["refused"] is True and "refused" in comp_mix["reason"])

# arithmetic on injected annual returns: monkeypatch _annual_returns
_orig = tc._annual_returns
tc._annual_returns = lambda k: {"a": {"2024": 0.10, "2025": 0.20},
                                "b": {"2024": 0.20, "2025": 0.00},
                                "c": {"2025": 0.40}}.get(k, {})
comp = tc.composite("_toy3")
tc._annual_returns = _orig
rows = {r["year"]: r for r in comp["rows"]}
check("composite 2024 = mean(10,20) = 15.0, n=2",
      rows["2024"]["composite_return_pct"] == 15.0 and rows["2024"]["n"] == 2)
check("composite 2025 = mean(20,0,40) = 20.0, n=3",
      rows["2025"]["composite_return_pct"] == 20.0 and rows["2025"]["n"] == 3)
check("composite discloses weighting", "equal-weight" in comp["weighting"])

# cleanup injected cohorts
for k in ("_toy3", "_toy5", "_toymix"):
    del tc.COHORTS[k]

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll cohort tests pass.")
sys.exit(1 if FAILS else 0)

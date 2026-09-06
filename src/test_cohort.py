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
# ---- ties share one rank; "at the median" is always the 50th ----
FACTS_TIE = {k: {"cap": {"value": 5.0}} for k in "abcde"}
tc.COHORTS["_tie5"] = {"label": "tie", "members": list("abcde"),
                       "wrapper_types": {k: "interval_23c3" for k in "abcde"}}
tie = [tc.percentile_of(k, "_tie5", "cap", FACTS_TIE) for k in "abcde"]
check("five-way tie: every member is the 50th percentile",
      all(t["percentile"] == 50 for t in tie))
check("five-way tie: every member reads 'at the median'",
      all("at the median" in t["phrase"] for t in tie))
check("no member is both a non-50th percentile and 'at the median'",
      not any(("at the median" in t["phrase"]) and t["percentile"] != 50 for t in tie))
FACTS_ASYM = {"a": {"fee": {"value": 1.0}}, "b": {"fee": {"value": 1.25}},
              "c": {"fee": {"value": 1.25}}, "d": {"fee": {"value": 1.5}},
              "e": {"fee": {"value": 1.75}}}
tc.COHORTS["_asym5"] = {"label": "asym", "members": list("abcde"),
                        "wrapper_types": {k: "interval_23c3" for k in "abcde"}}
pb = tc.percentile_of("b", "_asym5", "fee", FACTS_ASYM)
pd = tc.percentile_of("d", "_asym5", "fee", FACTS_ASYM)
check("asymmetric tie at the median reads 50th, at the median",
      pb["percentile"] == 50 and "at the median" in pb["phrase"])
check("member above a tied median: mid-rank (3 below + 0.5) / 5 = 70th, above",
      pd["percentile"] == 70 and "above the median" in pd["phrase"])
check("phrases carry no em dash or semicolon",
      all(("\u2014" not in t["phrase"]) and (";" not in t["phrase"]) for t in tie + [pb, pd, p3]))

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

# ---- P1-24: no committed caveat contradicts a typed fact ----
import json as _json  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
_BASE = _Path(__file__).resolve().parents[1]
_reg = _json.loads((_BASE / "data" / "registry.json").read_text())["products"]
_RULES = (("PRICING-BASIS MIX", "pricing_class"), ("LEVERAGE-REGIME MIX", "leverage_regime"),
          ("NAV-CADENCE MIX", "nav_cadence"))
_bad = []
for _cp in sorted((_BASE / "data" / "cohorts").glob("*.json")):
    if _cp.name == "caveat_matrix.json":
        continue
    _co = _json.loads(_cp.read_text())
    _members = list(_co["members"])
    for _label, _attr in _RULES:
        _vals = {_reg[m][_attr] for m in _members}
        _present = any(_label in c for c in _co["caveats"])
        if _present != (len(_vals) > 1):
            _bad.append(f"{_cp.stem}: {_label} {'written' if _present else 'absent'} "
                        f"while typed values are {sorted(_vals)}")
    if any(";" in c for c in _co["caveats"]):
        _bad.append(f"{_cp.stem}: semicolon in a caveat")
check("committed caveats: each fires exactly when the members' typed values differ, no semicolons",
      not _bad)
if _bad:
    print("   ", " | ".join(_bad[:4]))
_ev = _json.loads((_BASE / "data" / "cohorts" / "evergreen_pe.json").read_text())["caveats"]
check("evergreen_pe: no pricing-basis caveat over five NAV-priced members",
      not any("PRICING-BASIS" in c for c in _ev))
check("evergreen_pe: leverage-regime caveat stays (kkr_kpec has no 1940-Act limit)",
      any("LEVERAGE-REGIME" in c for c in _ev))
_vals, _basis = tc.member_values("evergreen_pe", "pricing_class")
check("member_values reads typed per-product values for a real cohort",
      _basis == "typed per product" and set(_vals.values()) == {"NAV"})
_vals, _basis = tc.member_values("_toymix", "pricing_class")
check("member_values falls back to wrapper attributes for members outside the registry",
      _basis == "by wrapper type" and set(_vals.values()) == {"NAV", "MARKET"})

# ---- composite: refusal law + arithmetic ----
comp_mix = tc.composite("_toymix")
check("heterogeneous pricing basis: composite REFUSED",
      comp_mix["refused"] is True and "refused" in comp_mix["reason"])

# arithmetic on injected period returns: monkeypatch the shared member table
# (tark_periods) the composite reads. Members a and b report calendar 2024
# and 2025, c reports 2025 only, so 2025 is the one period every member
# reports and the only one with a composite return (rule 14).
import tark_periods as _tp
_orig = _tp.member_period_returns
def _fake(key, reg=None):
    per = {"a": {"2024": 0.10, "2025": 0.20}, "b": {"2024": 0.20, "2025": 0.00}, "c": {"2025": 0.40}}.get(key, {})
    return {"period_kind": "calendar_year", "basis": "fy_returns", "source": "test", "fy_end_month": "12",
            "periods": {f"{y}-12-31": {"start": f"{int(y) - 1}-12-31", "end": f"{y}-12-31", "return": r, "label": y}
                        for y, r in per.items()}}
_tp.member_period_returns = _fake
comp = tc.composite("_toy3")
_tp.member_period_returns = _orig
rows = {r["label"]: r for r in comp["rows"]}
check("composite 2024: two of three members report, n=2, no composite return is formed",
      rows["2024"]["n"] == 2 and rows["2024"]["composite_return_pct"] is None
      and rows["2024"]["returns"] == {"a": 10.0, "b": 20.0, "c": None})
check("composite 2025 = mean(20,0,40) = 20.0, n=3, every member reports",
      rows["2025"]["composite_return_pct"] == 20.0 and rows["2025"]["n"] == 3)
check("composite discloses weighting and the calendar-year granularity",
      "equal-weight" in comp["weighting"] and "calendar years" in comp["granularity"])

# cleanup injected cohorts
for k in ("_toy3", "_toy5", "_toymix"):
    del tc.COHORTS[k]

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll cohort tests pass.")
sys.exit(1 if FAILS else 0)

"""
Unit tests for the M3 benchmark engine.
Run: python src/test_benchmark.py   (exit 0 = all pass)
"""
import sys

from tark_benchmark import (MIN_PRIMARY_SCORE, PRODUCT_PROFILES, STRATEGY_MENU,
                            run_selection, score_candidate)

FAILS = []


def check_true(name: str, cond: bool):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        FAILS.append(name)


# --- rubric mechanics on synthetic candidates ---
prof = {"strategy": "x"}
perfect = {"id": "p", "name": "perfect", "lane": "B", "series": "spy",
           "provider": "indep", "independent": True, "data": "daily",
           "strategy_match": 3, "match_note": "exact"}
s = score_candidate(prof, perfect)
# strategy 3 + risk 1 (daily proxy) + invest 2 + data 2 + indep 2 = 10
check_true("perfect candidate arithmetic = 10", s["score"] == 10)

affiliated = dict(perfect, id="a", independent=False,
                  provider="the fund's own adviser")
sa = score_candidate(prof, affiliated)
check_true("affiliated provider loses exactly the 2 independence points",
           s["score"] - sa["score"] == 2)
check_true("independence zero is reasoned in the log",
           any("manufacturer-owned" in r for r in sa["reasons"]))

paid = dict(perfect, id="q", series=None, data="quarterly-paid")
sq = score_candidate(prof, paid)
check_true("unlicensed paid index cannot outscore computable proxy",
           sq["score"] < s["score"])
check_true("paid-data rejection reason names the missing license",
           any("licensed data not held" in r for r in sq["reasons"]))

# --- selection behavior on real profiles ---
sel_c = run_selection("cliffwater_cclfx")
check_true("CCLFX selects a primary", sel_c["primary"] is not None)
check_true("CCLFX primary is independent BKLN lane, not adviser-owned CDLI",
           sel_c["primary"]["id"] in ("bkln", "pme_bkln"))
check_true("CDLI appears in rejected with independence reasoning",
           any(r["id"] == "cdli" and any("manufacturer-owned" in x for x in r["reasons"])
               for r in sel_c["rejected"]))
check_true("CCLFX primary carries computed comparison stats",
           sel_c["primary"]["comparison"] is not None
           and sel_c["primary"]["comparison"]["ks_pme"] > 0)

sel_d = run_selection("dxyz")
check_true("DXYZ returns NO primary (the fail case)", sel_d["primary"] is None)
check_true("DXYZ escalates with a reasoned message",
           sel_d["escalation"] is not None and "NO MEANINGFUL BENCHMARK"
           in sel_d["escalation"])
check_true("DXYZ rejection log gives the premium-decoupling reason on every row",
           all("premium" in r["rejection"] for r in sel_d["rejected"]))

# --- rejection-log completeness: every candidate is accounted for ---
for key in PRODUCT_PROFILES:
    sel = run_selection(key)
    menu = STRATEGY_MENU[PRODUCT_PROFILES[key]["strategy"]]
    accounted = len(sel["rejected"]) + (1 if sel["primary"] else 0) \
        + (1 if sel["secondary"] else 0)
    check_true(f"{key}: every candidate selected or rejected-with-reason "
               f"({accounted}/{len(menu)})", accounted == len(menu))
    check_true(f"{key}: every rejection carries a reason string",
               all(r.get("rejection") for r in sel["rejected"]))

# --- rejection-reason TRUTHFULNESS: no false statements in the audit log ---
for key in PRODUCT_PROFILES:
    sel = run_selection(key)
    for r in sel["rejected"]:
        if r["score"] >= MIN_PRIMARY_SCORE and not PRODUCT_PROFILES[key].get("price_nav_decoupled"):
            check_true(f"{key}/{r['id']}: above-threshold rejection says 'outranked', "
                       f"never 'below threshold'",
                       "outranked" in r["rejection"] and "below" not in r["rejection"])
        if r["score"] < MIN_PRIMARY_SCORE and not PRODUCT_PROFILES[key].get("price_nav_decoupled"):
            check_true(f"{key}/{r['id']}: below-threshold rejection states the threshold",
                       "below primary threshold" in r["rejection"])

check_true("threshold constant sane", 0 < MIN_PRIMARY_SCORE <= 12)

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll benchmark engine tests pass.")
sys.exit(1 if FAILS else 0)

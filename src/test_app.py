"""
UI tests for app.py via Streamlit's AppTest — including the anonymization
gate: the anchor plan sponsor's name must appear NOWHERE in any rendered view.
Run: python src/test_app.py   (exit 0 = all pass)
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
VIEWS = ["Reference Plan", "Candidate Roster", "Six-Factor Evaluation",
         "Benchmark Selection", "Liquidity Match"]
PRODUCTS = ["breit", "cliffwater_cclfx", "dxyz", "hl_paf", "kkr_kpec",
            "stepstone_spm"]
PLANS = ["plan_tech_media", "plan_restaurant_hourly", "plan_consulting_alumni",
         "plan_manufacturer_union"]
# the anonymization rule, lowercased: NO reference-plan sponsor name, ever
FORBIDDEN = ["spotify", "darden", "mckinsey", "goodyear"]

FAILS = []


def check_true(name: str, cond: bool):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")
    if not cond:
        FAILS.append(name)


def widget(at, kind: str, key: str):
    return next(w for w in getattr(at, kind) if w.key == key)


def collect_text(at) -> str:
    parts = []
    for kind in ("title", "header", "subheader", "markdown", "caption",
                 "error", "warning", "info", "success"):
        for el in getattr(at, kind, []):
            parts.append(str(getattr(el, "value", "")))
    for m in getattr(at, "metric", []):
        parts.append(f"{m.label} {m.value} {getattr(m, 'delta', '')}")
    for df in getattr(at, "dataframe", []):
        try:
            parts.append(df.value.to_string())
        except Exception:  # noqa: BLE001
            pass
    for ex in getattr(at, "expander", []):
        try:
            for el in ex.markdown:
                parts.append(str(el.value))
        except Exception:  # noqa: BLE001
            pass
    return " \n ".join(parts)


def leaked(text: str) -> str | None:
    low = text.lower()
    return next((name for name in FORBIDDEN if name in low), None)


def run_view(view: str, product: str, plan: str = "plan_tech_media"
             ) -> tuple[AppTest, str]:
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    widget(at, "radio", "nav").set_value(view)
    widget(at, "selectbox", "plan").set_value(plan)
    widget(at, "selectbox", "product").set_value(product)
    at.run()
    return at, collect_text(at)


# 1. app boots clean
at0 = AppTest.from_file(APP, default_timeout=30)
at0.run()
check_true("app boots without exception", not at0.exception)

# 2. every view x product combination renders without exception,
#    and NEVER leaks any sponsor name (anchor plan)
for view in VIEWS:
    for product in PRODUCTS:
        at, text = run_view(view, product)
        check_true(f"{view} / {product}: renders clean", not at.exception)
        check_true(f"{view} / {product}: anonymization holds",
                   leaked(text) is None)

# 2b. every plan renders the plan-sensitive views clean + anonymized,
#     and the plan switcher visibly changes the liquidity output
for plan in PLANS:
    for view in ("Reference Plan", "Liquidity Match"):
        at, text = run_view(view, "cliffwater_cclfx", plan)
        check_true(f"{view} / {plan}: renders clean", not at.exception)
        check_true(f"{view} / {plan}: anonymization holds", leaked(text) is None)
_, lt_rest = run_view("Liquidity Match", "cliffwater_cclfx",
                      "plan_restaurant_hourly")
check_true("liquidity switches with plan: restaurant tail 28.2%",
           "28.2" in lt_rest)
_, lt_cons = run_view("Liquidity Match", "cliffwater_cclfx",
                      "plan_consulting_alumni")
check_true("liquidity switches with plan: consulting tail 58.2%",
           "58.2" in lt_cons)
check_true("consulting plan: partial-direction structural language",
           "PARTIALLY participant-directed" in lt_cons)
check_true("consulting plan: thin-headroom flag fires",
           "THIN HEADROOM" in lt_cons)

# 3. anchor plan shows the real (anonymized) economics
_, anchor_text = run_view("Reference Plan", "hl_paf")
check_true("anchor: net assets $565.8M rendered", "565.8" in anchor_text)
check_true("anchor: avg balance $110,515 rendered", "110,515" in anchor_text)
check_true("anchor: liquidity tail called out", "1,847" in anchor_text)

# 4. benchmark view: CCLFX numbers reproduce; DXYZ escalates
_, cclfx_text = run_view("Benchmark Selection", "cliffwater_cclfx")
check_true("benchmark cclfx: KS-PME 1.2532 on screen", "1.2532" in cclfx_text)
check_true("benchmark cclfx: CDLI sits in rejection log", "CDLI" in cclfx_text)
_, dxyz_text = run_view("Benchmark Selection", "dxyz")
check_true("benchmark dxyz: escalation banner shown",
           "NO MEANINGFUL BENCHMARK" in dxyz_text)

# 5. evaluation view: seeded evidence surfaces with provenance
_, ev_text = run_view("Six-Factor Evaluation", "hl_paf")
check_true("evaluation hl_paf: Managed Assets fee-base trap on screen",
           "Managed Assets".lower() in ev_text.lower())
_, ev2 = run_view("Six-Factor Evaluation", "breit")
check_true("evaluation breit: 2%/5% repurchase caps on screen",
           "2% of aggregate NAV" in ev2)

# 6. liquidity match view: verdicts, structural gap, illustrative labeling
_, lc = run_view("Liquidity Match", "cliffwater_cclfx")
check_true("liquidity cclfx: CONDITIONAL verdict", "CONDITIONAL" in lc)
check_true("liquidity cclfx: structural gap named", "STRUCTURAL GAP" in lc)
check_true("liquidity cclfx: scenario labeled ILLUSTRATIVE", "ILLUSTRATIVE" in lc)
_, lb = run_view("Liquidity Match", "breit")
check_true("liquidity breit: CONDITIONAL-WEAK on gating precedent",
           "CONDITIONAL-WEAK" in lb and "prorated" in lb)
_, ld = run_view("Liquidity Match", "dxyz")
check_true("liquidity dxyz: aligned-mechanical with premium caveat",
           "ALIGNED-MECHANICAL" in ld and "premium" in ld)

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll app tests pass.")
sys.exit(1 if FAILS else 0)

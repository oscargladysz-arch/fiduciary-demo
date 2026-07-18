"""
UI tests for app.py via Streamlit's AppTest — including the anonymization
gate: the anchor plan sponsor's name must appear NOWHERE in any rendered view.
Run: python src/test_app.py   (exit 0 = all pass)
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
VIEWS = ["Anchor Plan", "Candidate Roster", "Six-Factor Evaluation",
         "Benchmark Selection"]
PRODUCTS = ["breit", "cliffwater_cclfx", "dxyz", "hl_paf", "kkr_kpec",
            "stepstone_spm"]
FORBIDDEN = "spotify"   # the anonymization rule, lowercased

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


def run_view(view: str, product: str) -> tuple[AppTest, str]:
    at = AppTest.from_file(APP, default_timeout=30)
    at.run()
    widget(at, "radio", "nav").set_value(view)
    widget(at, "selectbox", "product").set_value(product)
    at.run()
    return at, collect_text(at)


# 1. app boots clean
at0 = AppTest.from_file(APP, default_timeout=30)
at0.run()
check_true("app boots without exception", not at0.exception)

# 2. every view x product combination renders without exception,
#    and NEVER leaks the sponsor name
for view in VIEWS:
    for product in PRODUCTS:
        at, text = run_view(view, product)
        check_true(f"{view} / {product}: renders clean", not at.exception)
        check_true(f"{view} / {product}: anonymization holds",
                   FORBIDDEN not in text.lower())

# 3. anchor plan shows the real (anonymized) economics
_, anchor_text = run_view("Anchor Plan", "hl_paf")
check_true("anchor: net assets $565.8M rendered", "565.8" in anchor_text)
check_true("anchor: avg balance $110,515 rendered", "110,515" in anchor_text)
check_true("anchor: liquidity tail called out", "1,847" in anchor_text)

# 4. benchmark view: CCLFX numbers reproduce; DXYZ escalates
_, cclfx_text = run_view("Benchmark Selection", "cliffwater_cclfx")
check_true("benchmark cclfx: KS-PME 1.2519 on screen", "1.2519" in cclfx_text)
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

print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nAll app tests pass.")
sys.exit(1 if FAILS else 0)

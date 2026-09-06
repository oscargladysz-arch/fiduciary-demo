"""Constants and small helpers shared by the benchmark engine and the period
module (kept apart so neither imports the other's data)."""
from __future__ import annotations

LOW_CONFIDENCE_YEARS = 3.0   # a comparison window shorter than this is labeled


def low_confidence(window_years: float, unit: str = "year") -> str | None:
    """The label a short window carries on the card and in the memo (P1-14),
    or None at or above LOW_CONFIDENCE_YEARS."""
    if window_years >= LOW_CONFIDENCE_YEARS:
        return None
    n = round(window_years, 2)
    shown = f"{int(n)}" if float(n).is_integer() else f"{n}"
    return f"low confidence: {shown}-{unit} window, shorter than {int(LOW_CONFIDENCE_YEARS)} years"

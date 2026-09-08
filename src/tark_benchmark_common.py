"""Constants and small helpers shared by the benchmark engine, the period
module, the display layer and the writers (kept apart so none of them
imports the engine's data)."""
from __future__ import annotations

import hashlib
import json
import math

LOW_CONFIDENCE_YEARS = 3.0   # a comparison window shorter than this is labeled

# ---- rubric v3.1 (R3-P2-1, R3-P2-2): four criteria, the threshold and the
# gate stated as fractions and printed as "x of N" everywhere
RUBRIC_VERSION = "v3.1"
CRITERIA = ("strategy_match", "risk_liquidity_match", "provider_independence", "data_held")
CRITERION_MAX = {"strategy_match": 3, "risk_liquidity_match": 3, "provider_independence": 2, "data_held": 2}
CRITERION_LABEL = {"strategy_match": "Strategy match",
                   "risk_liquidity_match": "Risk and liquidity match",
                   "provider_independence": "Provider independence",
                   "data_held": "Data held"}
CRITERION_DEFINITION = {
    "strategy_match": "how closely the candidate's asset class and sub-strategy match the fund's, "
                      "3 for the same sub-strategy, 2 for the same asset class, 1 for an adjacent one",
    "risk_liquidity_match": "whether the candidate's liquidity process matches the fund's typed dealing "
                            "terms (cadence, caps, gating, program status), 3 for a like-for-like process",
    "provider_independence": "2 unless the registry's affiliation map ties the candidate's publisher to "
                             "one of the fund's advisers, in which case 0 and the candidate is ineligible",
    "data_held": "2 when the candidate's series is in the record, 0 when it is only cited",
}
RUBRIC_MAX = sum(CRITERION_MAX.values())            # 10
MIN_PRIMARY_FRACTION = 0.6                           # six tenths of the maximum
MIN_PRIMARY_SCORE = math.ceil(RUBRIC_MAX * MIN_PRIMARY_FRACTION)   # 6 of 10
STRATEGY_GATE_MIN = 2                                # of 3: below it a candidate is ineligible
STRATEGY_GATE_FRACTION = STRATEGY_GATE_MIN / CRITERION_MAX["strategy_match"]
RUBRIC_LABEL = f"Tark benchmark rubric, {RUBRIC_MAX} points"


def x_of_n(x, n) -> str:
    """The one way a score prints on every surface: "8 of 10"."""
    return f"{x} of {n}"


TIE_SENTENCE = ("Tied on score. Ordered by strategy match, then risk and liquidity match, "
                "then data held, then name.")
# decision 8.5: a cited published index with no held series holds Slot K and
# every surface prints this one sentence until its series is held
BY_DESCRIPTOR_SENTENCE = "Meaningful benchmark by descriptor. No comparison until its series is held."


def low_confidence(window_years: float, unit: str = "year") -> str | None:
    """The label a short window carries on the card and in the memo (P1-14),
    or None at or above LOW_CONFIDENCE_YEARS."""
    if window_years >= LOW_CONFIDENCE_YEARS:
        return None
    n = round(window_years, 2)
    shown = f"{int(n)}" if float(n).is_integer() else f"{n}"
    return f"low confidence: {shown}-{unit} window, shorter than {int(LOW_CONFIDENCE_YEARS)} years"


# ---- the selection lock (R3-P2-19)
def canonical_json(doc) -> str:
    """One canonical serialization: sorted keys, no whitespace, unicode kept."""
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def record_hash(doc: dict) -> str:
    """SHA-256 over the canonical JSON of the selection without its hash field."""
    body = {k: v for k, v in doc.items() if k != "record_hash"}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def sha256_file(path) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()

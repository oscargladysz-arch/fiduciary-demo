"""
Tark benchmark engine, architecture v3 (R2-P1-A, decisions 7.1 and 7.21).

Every product carries two named comparisons that answer different
paragraphs of the rule:

  Slot K, "Meaningful benchmark (paragraph (k))": the fund's declared
  benchmark (Lane A), exchange-traded strategy proxies (Lane B) and
  published strategy indices (Lane P) scored by the 12-point rubric v3 from
  typed descriptors. A candidate with a public market price series gets a
  PME (KS-PME, Direct Alpha). A candidate with a published appraisal-based
  series gets a relative wealth ratio and an excess return on aligned
  periods. A candidate that is cited but not held gets no number and says
  so. An index published by the fund's own adviser is never Slot K.

  Slot G, "Peer comparison (paragraphs (g) and (h))": the cohort, members
  side by side over identical periods with n per period, an equal-weight
  leave-one-out composite only where every peer reports the period, a
  relative wealth ratio for the fund against it, a survivorship sentence
  and a heterogeneity sentence. Never a benchmark, never a PME (rule 12).

Rubric v3 (12 points): strategy_match 0 to 3 (gate below 2),
risk_liquidity_match 0 to 3 from the facts layer, provider_independence
0 or 2 from the affiliation map (0 is ineligible), data_held 0 or 2 (the
one possession criterion), pricing_basis_match 0 to 2. Threshold 7. Ties
are printed as ties. docs/benchmark_methodology.md is the specification.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from tark_analytics import (_level_on, cumulative_growth, direct_alpha,
                            effective_window, ks_pme, monthly_schedule_flows,
                            year_frac)
from tark_benchmark_common import (BY_DESCRIPTOR_SENTENCE, CRITERIA, CRITERION_LABEL, CRITERION_MAX,  # noqa: F401
                                   LOW_CONFIDENCE_YEARS, MIN_PRIMARY_FRACTION, MIN_PRIMARY_SCORE, RUBRIC_MAX,
                                   RUBRIC_VERSION, STRATEGY_GATE_MIN, TIE_SENTENCE, canonical_json, low_confidence,
                                   record_hash, sha256_file, x_of_n)
from tark_data import DATA, load_products, load_series
from tark_display import (RUBRIC_LABEL, asset_label, candidate_short, cohort_label,
                          strategy_label, sub_label)
from tark_periods import (aligned_composite, calendar_years_from_series,
                          member_period_returns)

SLOT_K_LABEL = "Meaningful benchmark (paragraph (k))"
SLOT_G_LABEL = "Peer comparison (paragraphs (g) and (h))"
# rubric v3.1 (R3-P2-1, R3-P2-2): four criteria, the threshold and the gate
# as fractions of their maxima, printed as "x of N" on every surface
RUBRIC_CAPTION = (f"{RUBRIC_LABEL}: strategy match 3 (gate below {STRATEGY_GATE_MIN}), risk and liquidity "
                  "match 3, provider independence 2 (an affiliated provider is ineligible), data held 2, "
                  f"threshold {x_of_n(MIN_PRIMARY_SCORE, RUBRIC_MAX)}")
NOT_PME_NOTE = ("Not a public market equivalent: the comparator is appraisal-based and cannot "
                "be bought, so the statistic is a relative wealth ratio.")
YAHOO_SOURCE = "Yahoo adjusted close, approximates NAV total return"
# the same series for an exchange-traded fund is a market price, not NAV (R3-P2-4)
MARKET_SOURCE = "Yahoo adjusted close, a market price with distributions reinvested, not NAV"
# fund short names for anything a surface prints (never a product key)
FUND_SHORT = {k: p["fund_name"].split(" (")[0] for k, p in load_products().items()}

_REGISTRY_DOC = json.loads((DATA / "registry.json").read_text())
REGISTRY = _REGISTRY_DOC["products"]
COHORTS = _REGISTRY_DOC["cohorts"]
# provider entity -> adviser entity keys (R2-P0-2). A candidate is affiliated
# with a fund only when this map says so. Never a string match.
AFFILIATIONS: dict[str, dict] = (_REGISTRY_DOC.get("affiliations") or {}).get("providers", {})
# return inputs live in the registry (P2-1). Exposed for the site build and tests.
RETURN_INPUTS = {k: r["return_inputs"] for k, r in REGISTRY.items() if r.get("return_inputs")}
DECLARED_TYPES = ("declared", "sec_required_comparator")
DECLARED_TYPE_LABEL = {"declared": "declared benchmark",
                       "sec_required_comparator": "SEC-required comparator"}


def _facts(key: str) -> dict:
    fp = DATA / "facts" / f"{key}.json"
    if not fp.exists():
        return {}
    return {f: v.get("value") for f, v in json.loads(fp.read_text()).get("facts", {}).items()}


def _profile(key: str, reg: dict) -> dict:
    held = reg["held_returns"]
    fx = _facts(key)
    prof = {"key": key, "strategy": reg["strategy"], "series": held.get("series"),
            "granularity": ("daily" if held["kind"] == "series" and reg["pricing_class"] == "MARKET"
                            else "monthly" if held["kind"] == "series" else "annual"),
            "price_nav_decoupled": reg["price_nav_decoupled"],
            "source_cells": reg["source_cells"],
            **{k: reg[k] for k in ("asset_class", "sub_strategy", "pricing_class",
                                   "leverage_regime", "adviser_keys", "advisers",
                                   "declared_benchmarks", "cohort", "wrapper_type")},
            # the liquidity terms the risk criterion reads (R2-P1-4): the
            # facts layer, cells 3.1 and 3.3, never the held return file
            "dealing_cadence": fx.get("dealing_cadence"),
            "cap_period": fx.get("cap_period"),
            "repurchase_caps": fx.get("repurchase_caps") or [],
            "gate_history": fx.get("gate_history"),
            "repurchase_program_status": fx.get("repurchase_program_status")}
    prof["declared_none_reason"] = reg.get("declared_none_reason")
    inp = (reg.get("return_inputs") or {}).get("profile", {})
    prof.update(inp)
    prof["held_kind"] = held["kind"]
    if held["kind"] == "none":
        prof["no_returns_reason"] = held.get("reason", "no return input on record")
    return prof


ALL_PRODUCTS: dict[str, dict] = {key: _profile(key, reg) for key, reg in REGISTRY.items()}
PRODUCT_PROFILES: dict[str, dict] = ALL_PRODUCTS


def basis_of(key: str) -> dict:
    """The one return basis the product uses in every slot (R2-P1-6)."""
    prof = ALL_PRODUCTS[key]
    if prof["held_kind"] == "series":
        src = MARKET_SOURCE if prof.get("pricing_class") == "MARKET" else YAHOO_SOURCE
        return {"kind": "series", "label": f"{src} ({prof['series'].upper()})"}
    if prof["held_kind"] == "fy_returns":
        per = member_period_returns(key, REGISTRY)
        return {"kind": "fy_returns", "label": per["source"] or "filed fiscal-year returns"}
    if prof["held_kind"] in ("aatr", "aatr_5yr"):
        return {"kind": prof["held_kind"], "label": "disclosed annualized figure (cell 1.2)"}
    return {"kind": "none", "label": "no computable return series on record: " + prof["no_returns_reason"]}


# ----------------------------------------------------------- candidates
# asset_class families: a public version of an asset class scores 2
FAMILY = {"private_credit": "credit", "public_credit": "credit",
          "private_equity": "private_equity", "listed_private_equity": "private_equity",
          "real_estate": "real_estate", "listed_real_estate": "real_estate",
          "venture": "venture", "public_equity": "public_equity"}
# private NAV-class indices of an asset class count as a sub-strategy match
PRIVATE_INDEX_SUBS = {"private_index"}
# liquidity classes a candidate can carry (typed, not inferred from data held):
#   daily_market          an exchange-traded proxy or a market-priced index
#   appraisal_index       an appraisal-based index of assets or funds with no
#                         dealing mechanism of its own
#   appraisal_fund_index  an appraisal-based index whose constituents are
#                         funds dealt at NAV on a periodic cycle
LIQUIDITY_CLASS_LABEL = {"daily_market": "daily market series",
                         "appraisal_index": "appraisal-based index without a dealing mechanism",
                         "appraisal_fund_index": "appraisal-based index of periodically dealt funds"}

CANDIDATES: dict[str, dict] = {
    "bkln": {"name": "Senior loan investable proxy (BKLN, for Morningstar LSTA class)",
             "asset_class": "public_credit", "sub_strategy": "syndicated_loans",
             "listed": True, "pricing_class": "MARKET", "liquidity_class": "daily_market",
             "series": "bkln", "data": "daily", "lane": "B",
             "provider": "Invesco / Morningstar LSTA class", "provider_key": "invesco morningstar"},
    "lsta": {"name": "Morningstar LSTA US Leveraged Loan Index",
             "asset_class": "public_credit", "sub_strategy": "syndicated_loans",
             "listed": False, "pricing_class": "MARKET", "liquidity_class": "daily_market",
             "series": None, "data": "cited", "lane": "P",
             "provider": "Morningstar / LSTA", "provider_key": "morningstar lsta"},
    "cdli": {"name": "Cliffwater Direct Lending Index (CDLI)",
             "asset_class": "private_credit", "sub_strategy": "direct_lending",
             "listed": False, "pricing_class": "NAV", "liquidity_class": "appraisal_index",
             "series": None, "data": "cited", "lane": "P", "published_id": "idx_cdli",
             "provider": "Cliffwater", "provider_key": "cliffwater"},
    "csll": {"name": "Credit Suisse Leveraged Loan Index (CSLLI)",
             "asset_class": "public_credit", "sub_strategy": "leveraged_loans",
             "listed": False, "pricing_class": "MARKET", "liquidity_class": "daily_market",
             "series": None, "data": "cited", "lane": "P",
             "provider": "Credit Suisse (UBS)", "provider_key": "credit suisse ubs"},
    "bbg_agg": {"name": "Bloomberg US Aggregate Bond Index",
                "asset_class": "public_credit", "sub_strategy": "core_bonds",
                "listed": False, "pricing_class": "MARKET", "liquidity_class": "daily_market",
                "series": None, "data": "cited", "lane": "A",
                "provider": "Bloomberg", "provider_key": "bloomberg"},
    "ice_bofa_hy": {"name": "ICE BofA US High Yield Index",
                    "asset_class": "public_credit", "sub_strategy": "high_yield",
                    "listed": False, "pricing_class": "MARKET", "liquidity_class": "daily_market",
                    "series": None, "data": "cited", "lane": "A",
                    "provider": "ICE Data Indices", "provider_key": "ice bofa"},
    "psp": {"name": "Listed private equity investable proxy (PSP)",
            "asset_class": "listed_private_equity", "sub_strategy": "listed_private_equity",
            "listed": True, "pricing_class": "MARKET", "liquidity_class": "daily_market",
            "series": "psp", "data": "daily", "lane": "B",
            "provider": "Invesco / Red Rocks", "provider_key": "invesco red rocks"},
    "urth": {"name": "MSCI World investable proxy (URTH)",
             "asset_class": "public_equity", "sub_strategy": "global_equity",
             "listed": True, "pricing_class": "MARKET", "liquidity_class": "daily_market",
             "series": "urth", "data": "daily", "lane": "B",
             "provider": "iShares / MSCI", "provider_key": "ishares blackrock msci"},
    "spy": {"name": "S&P 500 investable proxy (SPY)",
            "asset_class": "public_equity", "sub_strategy": "us_large_cap",
            "listed": True, "pricing_class": "MARKET", "liquidity_class": "daily_market",
            "series": "spy", "data": "daily", "lane": "B",
            "provider": "SPDR / S&P DJI", "provider_key": "spdr state street s&p dow jones"},
    "nasdaq_comp": {"name": "NASDAQ Composite Index",
                    "asset_class": "public_equity", "sub_strategy": "nasdaq_composite",
                    "listed": False, "pricing_class": "MARKET", "liquidity_class": "daily_market",
                    "series": None, "data": "cited", "lane": "A",
                    "provider": "Nasdaq", "provider_key": "nasdaq"},
    "cambridge_pe": {"name": "Cambridge Associates US PE benchmark",
                     "asset_class": "private_equity", "sub_strategy": "private_index",
                     "listed": False, "pricing_class": "NAV", "liquidity_class": "appraisal_index",
                     "series": None, "data": "licensed", "lane": "P",
                     "provider": "Cambridge Associates", "provider_key": "cambridge associates"},
    "vnq": {"name": "Listed REIT investable proxy (VNQ)",
            "asset_class": "listed_real_estate", "sub_strategy": "listed_reits",
            "listed": True, "pricing_class": "MARKET", "liquidity_class": "daily_market",
            "series": "vnq", "data": "daily", "lane": "B",
            "provider": "Vanguard / MSCI US REIT", "provider_key": "vanguard msci"},
    "odce": {"name": "NCREIF Fund Index - ODCE (private core RE)",
             "asset_class": "real_estate", "sub_strategy": "private_index",
             "listed": False, "pricing_class": "NAV", "liquidity_class": "appraisal_fund_index",
             "series": None, "data": "cited", "lane": "P", "published_id": "idx_odce",
             "provider": "NCREIF", "provider_key": "ncreif"},
}
# the same series under the per-strategy ids the ledger has always used
for alias, base in (("psp_v", "psp"), ("psp_k", "psp"), ("urth_k", "urth"),
                    ("cambridge_pe_k", "cambridge_pe")):
    CANDIDATES[alias] = {**CANDIDATES[base], "alias_of": base}


def published_series_path(cand: dict) -> Path | None:
    """data/series_quarterly/<published_id>.csv when the published headline
    series has been acquired (R2-P1-1), else None."""
    pid = cand.get("published_id")
    if not pid:
        return None
    p = DATA / "series_quarterly" / f"{pid}.csv"
    return p if p.exists() else None


def _with_holding(cand: dict) -> dict:
    """The candidate with its data status read from what is on disk: a held
    daily series, a held published series, or cited/licensed."""
    out = dict(cand)
    if out.get("series"):
        out["data"] = "daily"
    elif published_series_path(out):
        out["data"] = "published"
    out["held"] = out["data"] in ("daily", "published")
    return out


# Lane B and Lane P ids per strategy (Lane A is added per product)
STRATEGY_MENU_IDS = {
    "private_credit": ["bkln", "cdli", "lsta", "csll"],
    "private_equity_evergreen": ["urth", "psp", "cambridge_pe"],
    "preipo_venture": ["spy", "psp_v"],
    "pe_conglomerate": ["psp_k", "urth_k", "cambridge_pe_k"],
    "nontraded_reit": ["vnq", "odce"],
}
STRATEGY_MENU: dict[str, list[dict]] = {
    strat: [_with_holding({**CANDIDATES[c], "id": c}) for c in ids]
    for strat, ids in STRATEGY_MENU_IDS.items()}


def declared_entries(key: str) -> list[dict]:
    """The registry's typed Lane A entries: {name, candidate, type}. An entry
    without a type is 'declared' (the pre-v3 form)."""
    out = []
    for d in ALL_PRODUCTS[key]["declared_benchmarks"]:
        t = d.get("type") or "declared"
        if t not in DECLARED_TYPES:
            raise ValueError(f"{key}: declared benchmark type {t!r} is not one of {DECLARED_TYPES}")
        out.append({**d, "type": t})
    return out


def menu_for(key: str) -> list[dict]:
    """The full candidate menu for one product: Lane B and P for its strategy
    plus every declared or SEC-required comparator (Lane A) not already
    present. A menu candidate that is also declared is tagged Lane A."""
    prof = ALL_PRODUCTS[key]
    out: list[dict] = []
    # a strategy nobody has judged yet (a workspace job's default registry
    # entry) has no menu: the selection escalates instead of guessing
    for cid in STRATEGY_MENU_IDS.get(prof["strategy"], ()):
        out.append(_with_holding({**CANDIDATES[cid], "id": cid}))
    decl = declared_entries(key)
    declared_ids = {d["candidate"]: d["type"] for d in decl}
    for cand in out:
        base = cand.get("alias_of") or cand["id"]
        if base in declared_ids:
            cand["lane"] = "A"
            cand["declared_type"] = declared_ids[base]
    present = {c["id"] for c in out} | {c.get("alias_of") for c in out}
    for d in decl:
        if d["candidate"] not in present:
            out.append(_with_holding({**CANDIDATES[d["candidate"]], "id": d["candidate"], "lane": "A",
                                      "declared_type": d["type"]}))
    return out


# ---------------------------------------------------------------- scoring
def strategy_match(prof: dict, cand: dict) -> tuple[int, str]:
    pac, psub = prof["asset_class"], prof["sub_strategy"]
    cac, csub = cand["asset_class"], cand["sub_strategy"]
    if cac == pac and (csub == psub or csub in PRIVATE_INDEX_SUBS):
        return 3, (f"same asset class and sub-strategy ({asset_label(pac)} / {sub_label(psub)})"
                   if csub == psub else
                   f"a {sub_label(csub)} of {asset_label(pac)} for a {sub_label(psub)} fund")
    if FAMILY.get(cac) == FAMILY.get(pac):
        return 2, (f"same asset class, different sub-strategy ({sub_label(csub)} vs "
                   f"{sub_label(psub)})" if cac == pac else
                   f"the public-market version of the asset class ({sub_label(csub)} "
                   f"for {sub_label(psub)})")
    if (FAMILY.get(pac) in ("private_equity", "venture") and cac == "public_equity") or \
            (pac == "venture" and cac == "listed_private_equity"):
        return 1, (f"adjacent asset class sharing the dominant risk ({sub_label(csub)} "
                   f"for {sub_label(psub)})")
    return 0, f"unrelated asset class ({asset_label(cac)} for {asset_label(pac)})"


def fund_liquidity_terms(prof: dict) -> str:
    """The fund's dealing terms as the facts layer types them (cells 3.1 and
    3.3), printed inside the risk criterion's reason."""
    dc = prof.get("dealing_cadence")
    if prof.get("repurchase_program_status") == "suspended":
        return "repurchases suspended (ordinary requests not accepted, capacity 0%)"
    if dc == "exchange":
        base = "exchange-traded, continuous dealing at the market price"
    else:
        caps = prof.get("repurchase_caps") or []
        cap_txt = (" under " + " and ".join(f"{c['pct']:g}% cap per {c['period']}" for c in caps)
                   if caps else " with no cap on record")
        base = f"{dc or 'periodic'} dealing at NAV{cap_txt}"
    if prof.get("gate_history") is True:
        base += ", requests prorated in the filings on record"
    return base


def risk_liquidity_match(prof: dict, cand: dict) -> tuple[int, str]:
    """0 to 3 from the fund's typed dealing terms (cells 3.1 and 3.3: dealing
    cadence, caps, gating history, program status) against the candidate's
    typed liquidity class (R3-P2-1). Never reads the held return file. Every
    input that fires is named in the reason, and a perturbation of any of
    them moves the score for at least one candidate class:
      3  an appraisal-based index against a NAV fund whose filings disclose
         no proration and no suspension, or a daily market series against
         an exchange-traded fund whose price tracks NAV
      2  an appraisal-based index against a NAV fund that has prorated
         requests or suspended repurchases (the index has no such gate)
      1  a daily market series against a semi-liquid NAV fund
      0  the fund's price is decoupled from NAV, or an appraisal index for a
         market-priced fund"""
    terms = fund_liquidity_terms(prof)
    if prof.get("price_nav_decoupled"):
        return 0, ("fund price is premium-driven and decoupled from NAV, no candidate matches that "
                   f"risk process (fund terms: {terms})")
    lc = cand.get("liquidity_class")
    exchange = prof.get("dealing_cadence") == "exchange" or prof["pricing_class"] == "MARKET"
    if lc == "daily_market":
        if exchange:
            return 3, f"daily market series for an exchange-traded fund whose price tracks NAV ({terms})"
        return 1, (f"daily-liquid market series against a semi-liquid NAV fund ({terms}): volatility "
                   "and liquidity regimes differ, the PME construct exists for exactly this comparison")
    if exchange:
        return 0, f"appraisal-based index for a market-priced fund ({terms}): no like-for-like process"
    suspended = prof.get("repurchase_program_status") == "suspended"
    gated = prof.get("gate_history") is True
    what = ("appraisal-based index of periodically dealt funds" if lc == "appraisal_fund_index"
            else "appraisal-based index without a dealing mechanism of its own")
    if suspended:
        return 2, (f"{what} against a NAV fund whose repurchases are suspended ({terms}): the index "
                   "carries no such closure, so the liquidity process is one step apart")
    if gated:
        return 2, (f"{what} against a NAV fund that has prorated requests ({terms}): the index carries "
                   "no gate, so the liquidity process is one step apart")
    gate_note = ("no proration and no suspension disclosed in the filings on record"
                 if prof.get("gate_history") is None else "every request filled in full per the filings")
    return 3, (f"{what} against a periodically dealt NAV fund with {gate_note} ({terms}): the pricing "
               "process and the liquidity process both match")


def provider_independence(prof: dict, cand: dict) -> tuple[int, str]:
    """0 or 2. 0 when the registry's affiliation map ties the candidate's
    provider entity to one of the fund's adviser entities, and 0 makes the
    candidate ineligible for Slot K. Affiliation is a fact read from the
    map, never a string match (R2-P0-2)."""
    affiliated = {a.strip() for a in (AFFILIATIONS.get(cand["provider_key"]) or {}).get("adviser_keys", [])}
    hits = [a.strip() for a in prof["adviser_keys"] if a.strip() in affiliated]
    if hits:
        return 0, (f"index published by the fund's own adviser ({', '.join(prof['advisers'])}) per the "
                   "registry affiliation map. A manufacturer-owned yardstick is not an independent "
                   "comparator and is ineligible for the meaningful-benchmark slot")
    return 2, (f"provider unaffiliated with the fund ({cand['provider']}): the registry affiliation "
               "map ties it to none of the fund's advisers")


def data_held(cand: dict) -> tuple[int, str]:
    """The one possession criterion (decision 7.21): 2 when the candidate's
    series is in the record, public or published, else 0."""
    if cand.get("data") == "daily":
        return 2, "daily public market series held (exchange-traded proxy, Yahoo adjusted close)"
    if cand.get("data") == "published":
        return 2, "published headline series held in the record"
    if cand.get("data") == "licensed":
        return 0, "licensed series not held (no subscription): the candidate is cited, not computed"
    return 0, "cited, series not in the record: no comparison can be computed yet"


def score_candidate(prof: dict, cand: dict) -> dict:
    """Score one candidate for one product from typed descriptors. Every
    criterion returns its points and the reason that fired."""
    cand = _with_holding(cand) if "held" not in cand else cand
    s_match, s_why = strategy_match(prof, cand)
    r_match, r_why = risk_liquidity_match(prof, cand)
    ind, p_why = provider_independence(prof, cand)
    dh, d_why = data_held(cand)
    crit = {"strategy_match": s_match, "risk_liquidity_match": r_match,
            "provider_independence": ind, "data_held": dh}
    whys = {"strategy_match": s_why, "risk_liquidity_match": r_why,
            "provider_independence": p_why, "data_held": d_why}
    # reasons print the criterion's display name, never its key (rule 11)
    reasons = [f"{CRITERION_LABEL[c]} {x_of_n(crit[c], CRITERION_MAX[c])}: {whys[c]}" for c in CRITERIA]
    total = sum(crit.values())
    return {"candidate": cand["name"], "id": cand["id"], "lane": cand["lane"],
            "declared_type": cand.get("declared_type"),
            "score": total, "max": RUBRIC_MAX,
            "criteria": crit,
            "held": bool(cand.get("held")),
            "comparator_kind": ("public market series" if cand["pricing_class"] == "MARKET"
                                else "appraisal-based published series"),
            "series_id": cand.get("series") or (cand.get("published_id") if cand.get("data") == "published"
                                                 else f"cited:{cand['id']}"),
            "reasons": reasons}


def eligible(s: dict, decoupled: bool) -> bool:
    """The one eligibility rule for Slot K: not price-decoupled, past the
    strategy gate, an unaffiliated provider, at or above the threshold."""
    c = s["criteria"]
    return (not decoupled and c["strategy_match"] >= STRATEGY_GATE_MIN
            and c["provider_independence"] == 2 and s["score"] >= MIN_PRIMARY_SCORE)


# ------------------------------------------------------------ comparison
class WindowNotComputable(ValueError):
    """The fund's return input cannot be compared on the held candidate data."""


def fiscal_year_bounds(fy_window, n: int) -> list[tuple[str, str]]:
    """[(start, end)] for n consecutive fiscal years: each start steps the
    year of the window start, the last end is the window end. Same rule as
    fiscalYearBounds in site/js/analytics.js."""
    w0, w1 = fy_window
    y0 = int(w0[:4])
    starts = [f"{y0 + i}{w0[4:]}" for i in range(n)]
    return [(st, starts[i + 1] if i + 1 < n else w1) for i, st in enumerate(starts)]


def _fund_source(profile: dict) -> str:
    if profile.get("series"):
        return MARKET_SOURCE if profile.get("pricing_class") == "MARKET" else YAHOO_SOURCE
    if profile.get("fy_returns"):
        per = member_period_returns(profile["key"], REGISTRY) if profile.get("key") in REGISTRY else {}
        return per.get("source") or "filed fiscal-year returns"
    return "disclosed annualized figure (cell 1.2)"


def comparison_stats(profile: dict, cand: dict) -> dict | None:
    """Fund-vs-candidate growth, PME and Direct Alpha over the EFFECTIVE
    window against a held PUBLIC MARKET series: the fund's window clipped
    to the proxy's coverage (both sides for a daily series, whole fiscal
    years for an annual list). A single disclosed annualized figure cannot
    be clipped: outside coverage it raises WindowNotComputable. One anchor:
    fund growth, index growth and the PME flows all read the level on or
    before each window date from the full series. Annualized figures use
    the actual/365.25 day count of the effective window. An appraisal-based
    published series is routed to published_index_comparison instead."""
    if cand.get("data") == "published" or (cand.get("published_id") and not cand.get("series")):
        return published_index_comparison(profile, cand)
    if not cand.get("series"):
        return None
    index = load_series(cand["series"], "adj_close")
    i0, i1 = index[0][0], index[-1][0]
    years = None
    schedule: dict = {}
    if profile.get("series"):
        fund = load_series(profile["series"], "adj_close")
        fund_window = (fund[0][0], fund[-1][0])
        d0, d1, note = effective_window(fund_window[0], fund_window[1], index)
        f_growth = _level_on(fund, d1) / _level_on(fund, d0)
        sched = monthly_schedule_flows(fund, d0, d1)
        schedule = {
            "ks_pme_monthly_schedule": round(ks_pme(sched, index), 4),
            "schedule_contributions": len(sched) - 1,
            "schedule_note": (f"ILLUSTRATIVE: {len(sched) - 1} equal contributions, "
                              "at the window start and each month-end inside it, "
                              "valued at the window end. The two-point figure "
                              "is primary."),
        }
    elif profile.get("fy_returns"):
        bounds = fiscal_year_bounds(profile["fy_window"], len(profile["fy_returns"]))
        fund_window = (profile["fy_window"][0], profile["fy_window"][1])
        kept = [(r, b) for r, b in zip(profile["fy_returns"], bounds)
                if i0 <= b[0] and b[1] <= i1]
        if not kept:
            raise WindowNotComputable(
                f"no whole fiscal year of {fund_window[0]} to {fund_window[1]} "
                f"lies inside the proxy series ({i0} to {i1})")
        d0, d1 = kept[0][1][0], kept[-1][1][1]
        f_growth = cumulative_growth([r for r, _ in kept])
        note = ""
        dropped = len(bounds) - len(kept)
        if dropped:
            parts = []
            if d0 != bounds[0][0]:
                parts.append(f"proxy series begins {i0}")
            if d1 != bounds[-1][1]:
                parts.append(f"proxy series ends {i1}")
            note = (f"clipped: {', '.join(parts)}, {dropped} fiscal year(s) "
                    f"outside it dropped")
    elif profile.get("aatr_5yr") or profile.get("aatr"):
        d0, d1 = profile["fy_window"]
        fund_window = (d0, d1)
        if d0 < i0 or d1 > i1:
            raise WindowNotComputable(
                f"the single disclosed figure covers {d0} to {d1} and cannot be "
                f"clipped to the proxy series (proxy series begins {i0}, ends {i1})")
        note = ""
        if profile.get("aatr_5yr"):
            f_growth = (1 + profile["aatr_5yr"]) ** 5
            years = 5
        else:
            f_growth = (1 + profile["aatr"]) ** profile["aatr_years"]
            years = profile["aatr_years"]
    else:
        return None
    i_growth = _level_on(index, d1) / _level_on(index, d0)
    if years is None:
        years = year_frac(d0, d1)
    flows = [(d0, -1.0), (d1, f_growth)]
    return {
        "kind": "series",
        "statistic": "KS-PME vs public market proxy",
        "comparator_kind": "public market series (exchange-traded proxy, Yahoo adjusted close)",
        "fund_return_source": _fund_source(profile),
        "window": f"{d0} to {d1}",
        "window_note": note,
        "fund_window": f"{fund_window[0]} to {fund_window[1]}",
        "window_years": round(year_frac(d0, d1), 2),
        "fund_growth_x": round(f_growth, 4),
        "index_growth_x": round(i_growth, 4),
        "ks_pme": round(ks_pme(flows, index), 4),
        "direct_alpha_pct": round((direct_alpha(flows, index) or 0) * 100, 2),
        "fund_ann_pct": round((f_growth ** (1 / years) - 1) * 100, 2),
        "index_ann_pct": round((i_growth ** (1 / years) - 1) * 100, 2),
        "low_confidence": low_confidence(year_frac(d0, d1)),
        **schedule,
    }


def load_published_series(cand: dict) -> list[tuple[str, float]]:
    """[(quarter_end, decimal return)] from the acquired headline file
    (columns period_end, total_return_pct), ascending."""
    p = published_series_path(cand)
    if not p:
        return []
    with open(p, newline="") as fh:
        rows = [(r["period_end"], float(r["total_return_pct"]) / 100)
                for r in csv.DictReader(fh) if r.get("total_return_pct")]
    return sorted(rows)


def _quarters_from_series(series: list[tuple[str, float]]) -> dict[str, float]:
    """{quarter_end: return} for complete calendar quarters of a daily
    series: the last observation of the quarter over the last observation
    of the prior quarter, both within the quarter's final week."""
    ends = {"03": "31", "06": "30", "09": "30", "12": "31"}
    last: dict[str, tuple[str, float]] = {}
    for d, v in series:
        q = f"{d[:4]}-{ends.get(d[5:7], '')}" if d[5:7] in ends else None
        key = f"{d[:4]}-{d[5:7]}"
        last[key] = (d, v)
    out: dict[str, float] = {}
    qkeys = [k for k in sorted(last) if k[5:] in ends]
    for a, b in zip(qkeys, qkeys[1:]):
        da, va = last[a]
        db, vb = last[b]
        ya, ma = int(a[:4]), int(a[5:])
        yb, mb = int(b[:4]), int(b[5:])
        if (yb * 12 + mb) - (ya * 12 + ma) != 3:
            continue
        if da[8:] < "24" or db[8:] < "24":
            continue
        out[f"{b}-{ends[b[5:]]}"] = vb / va - 1
    return out


def published_index_comparison(profile: dict, cand: dict) -> dict | None:
    """Fund against a held appraisal-based published series over identical
    periods: calendar quarters where the fund has a daily series, else the
    fund's own filed years compounded from the index's quarters (a March
    fiscal year is four quarter-ends). Relative wealth ratio and excess
    return, never a PME (rule 12)."""
    idx = dict(load_published_series(cand))
    if not idx:
        return None
    key = profile.get("key")
    if profile.get("series"):
        fund_q = _quarters_from_series(load_series(profile["series"], "adj_close"))
        common = sorted(q for q in fund_q if q in idx)
        unit, ppy = "calendar-quarter", 4
        fund_rets = {q: fund_q[q] for q in common}
        idx_rets = {q: idx[q] for q in common}
        labels = {q: q for q in common}
    else:
        per = member_period_returns(key, REGISTRY) if key in REGISTRY else {"periods": {}}
        unit, ppy = ("calendar-year" if per.get("period_kind") == "calendar_year" else "fiscal-year"), 1
        fund_rets, idx_rets, labels = {}, {}, {}
        for pid, p in sorted(per["periods"].items()):
            # the four quarter-ends inside the period must all be published
            y1, m1 = int(pid[:4]), int(pid[5:7])
            qs = []
            for back in (9, 6, 3, 0):
                mm = m1 - back
                yy = y1
                while mm <= 0:
                    mm += 12
                    yy -= 1
                dd = {3: "31", 6: "30", 9: "30", 12: "31"}.get(mm)
                if dd is None:
                    qs = []
                    break
                qs.append(f"{yy}-{mm:02d}-{dd}")
            if qs and all(q in idx for q in qs):
                fund_rets[pid] = p["return"]
                idx_rets[pid] = cumulative_growth([idx[q] for q in qs]) - 1
                labels[pid] = p["label"]
        common = sorted(fund_rets)
    if not common:
        raise WindowNotComputable("no period is reported by both the fund and the published series "
                                  "with identical start and end dates")
    # the longest consecutive run
    def step(a: str, b: str) -> bool:
        ya, ma = int(a[:4]), int(a[5:7])
        yb, mb = int(b[:4]), int(b[5:7])
        return (yb * 12 + mb) - (ya * 12 + ma) == (3 if ppy == 4 else 12)
    best: list[str] = []
    cur: list[str] = []
    for pid in common:
        if cur and not step(cur[-1], pid):
            cur = []
        cur.append(pid)
        if len(cur) >= len(best):
            best = list(cur)
    fg = cumulative_growth([fund_rets[p] for p in best])
    ig = cumulative_growth([idx_rets[p] for p in best])
    yrs = len(best) / ppy
    ratio = fg / ig
    return {
        "kind": "published_index",
        "statistic": "relative wealth ratio vs published strategy index",
        "comparator_kind": "appraisal-based published series held in the record",
        "fund_return_source": _fund_source(profile),
        "not_pme_note": NOT_PME_NOTE,
        "window": f"{labels[best[0]]} to {labels[best[-1]]}",
        "window_note": f"{len(best)} {unit} period(s) with identical start and end dates",
        "window_years": round(yrs, 2),
        "periods": best,
        "fund_growth_x": round(fg, 4), "index_growth_x": round(ig, 4),
        "relative_wealth_ratio": round(ratio, 4),
        "excess_return_pct": round((ratio ** (1 / yrs) - 1) * 100, 2),
        "fund_ann_pct": round((fg ** (1 / yrs) - 1) * 100, 2),
        "index_ann_pct": round((ig ** (1 / yrs) - 1) * 100, 2),
        "alignment_note": (f"{len(best)} {unit} period(s) aligned on identical start and end dates, "
                           "the published series is appraisal-based and the fund's NAV is too"),
        "low_confidence": low_confidence(yrs, unit if ppy == 1 else "year"),
    }


def _comparison_for(profile: dict, cand: dict) -> tuple[dict | None, str | None]:
    """(comparison, note) for one held candidate and this fund's one basis."""
    if profile.get("held_kind") == "none":
        return None, "no computable fund return series on record: " + profile["no_returns_reason"]
    if not cand.get("held"):
        return None, "cited, series not in the record: no comparison computed"
    try:
        return comparison_stats(profile, cand), None
    except WindowNotComputable as e:
        return None, str(e)


# ------------------------------------------------------------ escalation
def escalation_text(profile: dict, scored: list[dict], decoupled: bool) -> str:
    """Generated from the strategy and the candidates actually scored
    (R2-P1-7). Never a fixed sentence."""
    strat = strategy_label(profile["strategy"])
    if decoupled:
        return (f"NO MEANINGFUL BENCHMARK CONSTRUCTIBLE for this {strat} fund: its price is "
                "premium-driven and decoupled from NAV, so every candidate benchmarks the premium, "
                "not the portfolio. Required next: a NAV series from the filings and a premium to "
                "NAV decomposition before any comparator is defensible.")
    parts = []
    gate_fails = threshold_fails = affiliated = 0
    for s in scored:
        c = s["criteria"]
        if c["strategy_match"] < STRATEGY_GATE_MIN:
            why = f"fails the strategy gate (strategy match {x_of_n(c['strategy_match'], 3)})"
            gate_fails += 1
        elif c["provider_independence"] == 0:
            why = "affiliated provider"
            affiliated += 1
        elif s["score"] < MIN_PRIMARY_SCORE:
            why = "below the threshold"
            threshold_fails += 1
        else:
            why = "eligible"
        parts.append(f"{candidate_short(s['id'])} {x_of_n(s['score'], RUBRIC_MAX)} ({why})")
    exact = [s for s in scored if s["criteria"]["strategy_match"] == 3]
    if exact:
        need = ("a held series for " + " or ".join(candidate_short(s["id"]) for s in exact)
                + ", the strategy-exact candidates already on the menu")
    else:
        need = f"a published {strat} strategy index with a series the record can hold"
    clauses = []
    if gate_fails:
        clauses.append(f"fails the strategy gate (strategy match below {x_of_n(STRATEGY_GATE_MIN, 3)})")
    if threshold_fails:
        clauses.append(f"scores below the threshold ({x_of_n(MIN_PRIMARY_SCORE, RUBRIC_MAX)})")
    if affiliated:
        clauses.append("is published by an affiliated provider")
    why_all = (" or ".join(clauses) if clauses else "is ineligible")
    return (f"NO MEANINGFUL BENCHMARK CONSTRUCTIBLE from the candidates scored for this {strat} fund. "
            f"Every candidate either {why_all}. "
            "Scored: " + ", ".join(parts) + f". Required next: {need}.")


# ---------------------------------------------------------------- Slot G
def slot_g(key: str) -> dict | None:
    prof = ALL_PRODUCTS[key]
    cid = prof.get("cohort")
    if not cid or cid not in COHORTS:
        return None
    peers = [m for m in COHORTS[cid]["members"] if m != key]
    comp = aligned_composite(key, peers, REGISTRY, FUND_SHORT)
    wrappers = sorted({REGISTRY[m]["wrapper_type"] for m in peers + [key]})
    regimes = sorted({REGISTRY[m]["leverage_regime"] for m in peers + [key]})
    from tark_display import WRAPPER_LABEL
    hetero = ("Members span " + (f"{len(wrappers)} wrapper types ({', '.join(WRAPPER_LABEL.get(w, w) for w in wrappers)})"
                                if len(wrappers) > 1 else f"one wrapper type ({WRAPPER_LABEL.get(wrappers[0], wrappers[0])})")
              + " and " + (f"{len(regimes)} leverage regimes ({', '.join(regimes)})" if len(regimes) > 1
                           else f"one leverage regime ({regimes[0]})")
              + ". Fee bases, leverage and exit rights are not like-for-like, so the comparison is a "
              "history of similar investments, not a like-for-like index.")
    surv = (f"The cohort is the roster's {len(peers) + 1} surviving, still-filing products. Funds that "
            "closed, merged, or stopped filing are not in it, so any composite carries survivorship "
            "bias in the fund's favor. Membership rationales and exclusions are in the roster record.")
    table = [{"period": r["period"], "label": r["label"], "period_kind": r["period_kind"], "n": r["n"],
              "returns": {FUND_SHORT.get(m, m): v for m, v in r["returns"].items()}}
             for r in comp["table"]]
    out = {"label": SLOT_G_LABEL, "cohort": cid, "cohort_label": cohort_label(cid),
           "members": peers, "member_names": [FUND_SHORT.get(m, m) for m in peers],
           "member_source": {FUND_SHORT.get(m, m): s for m, s in comp["member_source"].items()},
           "member_period_kind": {FUND_SHORT.get(m, m): k for m, k in comp["member_period_kind"].items()},
           "table": table, "survivorship_note": surv, "heterogeneity_note": hetero,
           "composite": {k: v for k, v in comp.items()
                         if k not in ("table", "member_source", "member_period_kind", "members")}}
    out["composite"]["candidate"] = (f"Peer composite, {cohort_label(cid)} without {FUND_SHORT.get(key, key)}")
    out["composite"]["kind"] = "composite"
    if out["composite"]["status"] == "computed":
        out["composite"]["window_note"] = (f"{out['composite']['window_years']} "
                                           f"{'calendar' if out['composite']['period_kind'] == 'calendar_year' else 'fiscal'}-year "
                                           f"period(s), n={out['composite']['n']} peers in every period")
    return out


# ---------------------------------------------------------------- select
def _sort_key(s: dict):
    c = s["criteria"]
    return (-s["score"], -c["strategy_match"], -c["risk_liquidity_match"], -c["data_held"],
            s["candidate"].lower())


def run_selection(product_key: str) -> dict:
    profile = PRODUCT_PROFILES[product_key]
    menu = menu_for(product_key)
    by_id = {c["id"]: c for c in menu}
    scored = sorted((score_candidate(profile, c) for c in menu), key=_sort_key)
    decoupled = bool(profile.get("price_nav_decoupled"))
    elig = [s for s in scored if eligible(s, decoupled)]
    selected = elig[0] if elig else None

    rejected = []
    for s in scored:
        if s is selected:
            continue
        c = s["criteria"]
        tied = False
        if decoupled:
            why = ("fund price is premium/discount-driven and decoupled from NAV. "
                   "Benchmarking the price benchmarks the premium, not the portfolio")
        elif c["strategy_match"] < STRATEGY_GATE_MIN:
            why = (f"rejected: strategy gate (score {x_of_n(s['score'], s['max'])} but "
                   f"strategy match {x_of_n(c['strategy_match'], 3)})")
        elif c["provider_independence"] == 0:
            why = (f"rejected: affiliated provider (score {x_of_n(s['score'], s['max'])}), an index published "
                   "by the fund's own adviser is ineligible for the meaningful-benchmark slot")
        elif s["score"] < MIN_PRIMARY_SCORE:
            why = (f"score {x_of_n(s['score'], s['max'])} below the threshold "
                   f"{x_of_n(MIN_PRIMARY_SCORE, s['max'])}")
        elif selected and s["score"] == selected["score"]:
            tied = True
            why = (f"{TIE_SENTENCE} Score {x_of_n(s['score'], s['max'])}, "
                   f"{candidate_short(selected['id'])} selected.")
        else:
            why = (f"ranked below the selected candidate: {x_of_n(s['score'], s['max'])} vs "
                   f"{x_of_n(selected['score'], selected['max'])} for {candidate_short(selected['id'])}")
        rejected.append({**s, "rejection": why, "tied": tied})

    # ---- Slot K
    slot_k = {"label": SLOT_K_LABEL, "selected": None, "escalation": None,
              "max_attainable": max((s["score"] for s in elig), default=None),
              "ties": [s["id"] for s in elig[1:] if selected and s["score"] == selected["score"]]}
    if selected:
        cand = by_id[selected["id"]]
        if cand.get("held"):
            comp, note = _comparison_for(profile, cand)
            by_descriptor = False
        else:
            # decision 8.5: a cited index with no held series holds the slot
            # and every surface prints one sentence until its series is held
            comp, note, by_descriptor = None, BY_DESCRIPTOR_SENTENCE, True
        slot_k["selected"] = {**selected, "comparison": comp, "comparison_note": note,
                              "by_descriptor": by_descriptor}
    else:
        slot_k["escalation"] = escalation_text(profile, scored, decoupled)

    # ---- reference comparison on the highest-ranked held public market
    # series when Slot K carries no number (decision 7.21): named as a
    # reference, never as the benchmark. The loop continues past a candidate
    # whose comparison is not computable (R3-P2-6) and records why.
    reference = None
    reference_skipped: list[dict] = []
    if not (selected and slot_k["selected"]["comparison"]) and not decoupled:
        for s in scored:
            c = s["criteria"]
            cand = by_id[s["id"]]
            if (s["held"] and cand["pricing_class"] == "MARKET" and c["strategy_match"] >= STRATEGY_GATE_MIN
                    and c["provider_independence"] == 2):
                comp, note = _comparison_for(profile, cand)
                if comp:
                    reference = {"candidate": s["candidate"], "id": s["id"], "score": s["score"],
                                 "max": s["max"], "series_id": s["series_id"], "lane": s["lane"],
                                 "held": True, "comparison": comp,
                                 "note": ("reference comparison on the highest-ranked held public "
                                          "market series: not the meaningful benchmark")}
                    break
                reference_skipped.append({"id": s["id"], "candidate": s["candidate"], "note": note})

    # ---- Lane A record: every declared or SEC-required comparator, typed,
    # with its own comparison whenever its series is held (R2-P1-5)
    declared_out = []
    for d in declared_entries(product_key):
        s = next((x for x in scored if x["id"] == d["candidate"]
                  or CANDIDATES.get(x["id"], {}).get("alias_of") == d["candidate"]), None)
        cand = by_id.get(s["id"]) if s else None
        held = bool(cand and cand.get("held"))
        if s is None:
            status = "not scored"
        elif selected and s is selected:
            status = f"{'held' if held else 'cited, not held'}, scored {x_of_n(s['score'], RUBRIC_MAX)}, selected for Slot K"
        elif decoupled:
            status = f"{'held' if held else 'cited, not held'}, scored {x_of_n(s['score'], RUBRIC_MAX)}, fund price decoupled from NAV"
        elif s["criteria"]["strategy_match"] < STRATEGY_GATE_MIN:
            status = (f"{'held' if held else 'cited, not held'}, scored {x_of_n(s['score'], RUBRIC_MAX)}, "
                      f"fails the strategy gate (strategy match {x_of_n(s['criteria']['strategy_match'], 3)})")
        elif s["score"] < MIN_PRIMARY_SCORE:
            status = f"{'held' if held else 'cited, not held'}, scored {x_of_n(s['score'], RUBRIC_MAX)}, below the threshold"
        elif selected and s["score"] == selected["score"]:
            status = f"{'held' if held else 'cited, not held'}, scored {x_of_n(s['score'], RUBRIC_MAX)}, tied"
        else:
            status = f"{'held' if held else 'cited, not held'}, scored {x_of_n(s['score'], RUBRIC_MAX)}, ranked below the selection"
        if cand is None:
            comp, note = None, "not scored"
        elif decoupled:
            # R3-P2-4: no PME on a price series decoupled from NAV, it would
            # benchmark the premium, not the portfolio (cells 1.10 and 4.7)
            comp, note = None, ("fund price is premium-driven and decoupled from NAV: no comparison on a "
                                "market-price series, it would benchmark the premium, not the portfolio")
        else:
            comp, note = _comparison_for(profile, cand)
        declared_out.append({"name": d["name"], "candidate_id": d["candidate"], "cell": "5.1",
                             "type": d["type"], "type_label": DECLARED_TYPE_LABEL[d["type"]],
                             "held": held, "status": status,
                             "comparison": comp, "comparison_note": note})
    has_declared = any(d["type"] == "declared" for d in declared_out)

    doc = {
        "product": product_key,
        "strategy": profile["strategy"],
        "cohort": profile.get("cohort"),
        "source_cells": profile["source_cells"],
        "rubric_version": RUBRIC_VERSION,
        "rubric": RUBRIC_CAPTION,
        "threshold": {"min_score": MIN_PRIMARY_SCORE, "max": RUBRIC_MAX, "fraction": MIN_PRIMARY_FRACTION,
                      "strategy_gate_min": STRATEGY_GATE_MIN, "strategy_gate_max": CRITERION_MAX["strategy_match"]},
        "basis": basis_of(product_key),
        "slot_k": slot_k,
        "slot_g": slot_g(product_key),
        "reference_comparison": reference,
        "reference_skipped": reference_skipped,
        "declared": declared_out,
        "declared_none_reason": profile.get("declared_none_reason") if not has_declared else None,
        "rejected": rejected,
        # the selection lock (R3-P2-19): when, under which rubric, from which
        # inputs, and a hash over the whole record
        "recorded_at": recorded_at(),
        "inputs": selection_inputs(product_key, [by_id[s["id"]] for s in scored]),
    }
    doc["record_hash"] = record_hash(doc)
    return doc


# ---------------------------------------------------------- the lock
def recorded_at() -> str:
    """The record's as-of instant, midnight UTC of the as-of date. Artifacts
    never carry a wall clock (they must reproduce byte for byte in the
    freshness gate), so a re-record on a later day bumps data/as_of.json."""
    from tark_data import record_as_of
    return f"{record_as_of()}T00:00:00Z"


# the typed facts the rubric reads for the risk criterion (R3-P2-1)
RISK_FACT_FIELDS = ("dealing_cadence", "cap_period", "repurchase_caps", "gate_history",
                    "repurchase_program_status")
# the cells those facts and the strategy descriptors come from
LOCK_CELLS = ("3.1", "3.3", "5.1")


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(DATA.parent))
    except ValueError:
        return str(p)


def selection_inputs(key: str, cands: list[dict]) -> dict:
    """Every input the selection was computed from, each with a hash the
    lock gate recomputes: the filings by accession (the record holds no
    filing bytes, so the accession is the lock), the series files by
    content hash, the descriptors by a hash of the exact values read."""
    from tark_data import load_evidence
    prof = ALL_PRODUCTS[key]
    cells = sorted(set(prof["source_cells"]) | set(LOCK_CELLS))
    manifest = {}
    with open(DATA / "manifest.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["product"] == key:
                manifest[r["accession"]] = {"form": r["form"], "filing_date": r["filing_date"]}
    accessions = []
    seen = set()
    for r in load_evidence(key):
        acc = (r.get("accession") or "").strip()
        if r["cell_id"] not in cells or not acc or acc.startswith("multiple") or acc in seen:
            continue
        seen.add(acc)
        m = manifest.get(acc, {})
        accessions.append({"accession": acc, "cell": r["cell_id"], "form": m.get("form", ""),
                           "filing_date": m.get("filing_date", "")})
    series = []
    paths = []
    if prof.get("series"):
        paths.append(DATA / "series" / f"{prof['series']}.csv")
    if prof.get("held_kind") == "fy_returns":
        paths.append(DATA / "series_annual" / f"{key}.csv")
    for c in cands:
        if c.get("series"):
            paths.append(DATA / "series" / f"{c['series']}.csv")
        pp = published_series_path(c)
        if pp:
            paths.append(pp)
    for p in sorted({p for p in paths if p.exists()}, key=str):
        series.append({"path": _rel(p), "sha256": sha256_file(p)})
    reg = REGISTRY[key]
    facts_read = {f: prof.get(f) for f in RISK_FACT_FIELDS}
    descriptors = {
        "registry": {"path": "data/registry.json", "product": key,
                     "sha256": hashlib.sha256(canonical_json(reg).encode("utf-8")).hexdigest()},
        "facts": {"path": f"data/facts/{key}.json", "fields": list(RISK_FACT_FIELDS),
                  "sha256": hashlib.sha256(canonical_json(facts_read).encode("utf-8")).hexdigest()},
        "candidates": {"count": len(cands),
                       "sha256": hashlib.sha256(canonical_json(sorted(cands, key=lambda c: c["id"])).encode("utf-8")).hexdigest()},
    }
    return {"cells": cells, "accessions": accessions, "series": series, "descriptors": descriptors,
            "note": ("filings are locked by accession, the record holds no filing bytes. Series and "
                     "descriptors are locked by content hash. The record hash covers this whole document.")}

"""
Display derivations shared by the site build and the memo writer
==================================================================
Typed-fact headlines and label vocabularies. Display only: the full sourced
text of every cell stays one disclosure away, and no figure is ever
extracted from prose by regex. build_site.py ships cell_display per cell in
the bundle, tark_memo.py writes the same headlines into the findings table,
so the site and the memo can never disagree on a headline.
"""
from __future__ import annotations

import re

from tark_data import NOT_FETCHED_SENTENCE, status_kind  # noqa: F401 (re-exported)

# display vocabularies for typed facts (the JS keeps the same maps; P2-1
# folds both into the registry)
BASE_LABEL = {
    "net_assets": "net assets", "nav": "NAV", "aggregate_nav": "aggregate NAV",
    "managed_assets": "managed assets (leverage-inclusive)",
    "gross_incl_borrowings": "gross assets incl. borrowings",
    "outstanding_shares": "outstanding shares",
    "lesser_of_dual_base": "the lesser of two bases",
}
WRAPPER_LABEL = {
    "interval_23c3": "interval fund (Rule 23c-3)", "tender_offer": "tender-offer fund",
    "nontraded_bdc": "non-traded BDC", "nontraded_reit": "non-traded REIT",
    "nontraded_llc": "non-traded LLC ('34 Act)", "listed_cef": "listed closed-end fund",
    "listed_bdc": "listed BDC",
}


def _pct(v) -> str:
    return f"{v:g}%"


def fmt_incentive(v: dict | None) -> str:
    if not v:
        return ""
    if not v.get("present"):
        return "none"
    parts = []
    if v.get("rate_pct") is not None:
        parts.append(_pct(v["rate_pct"]))
    if v.get("hurdle_pct") is not None:
        parts.append(f"{_pct(v['hurdle_pct'])} hurdle")
    return " / ".join(parts) if parts else "present, rate not typed (see 2.2)"


def fmt_early(v: dict | None) -> str:
    if not v:
        return ""
    if not v.get("present"):
        return "none"
    rate = _pct(v["rate_pct"]) if v.get("rate_pct") is not None else \
        "fee present, rate not typed (see 2.7)"
    return f"{rate} {v['window']}" if v.get("window") else rate


def _money(x) -> str:
    if x >= 1e9:
        return f"${x / 1e9:.1f}B"
    if x >= 1e6:
        return f"${x / 1e6:.1f}M"
    return f"${round(x):,}"


def facts_by_cell(facts: dict) -> dict[str, dict]:
    """{cell_id: {field: fact}} for facts whose value is not null."""
    out: dict[str, dict] = {}
    for field, f in (facts or {}).items():
        if f.get("value") is not None:
            out.setdefault(f["source_cell"], {})[field] = f
    return out


def typed_headline(cid: str, fx: dict) -> str | None:
    """Headline from the typed facts that cite this cell, or None when no
    fact does. Never a regex over the prose."""
    if not fx:
        return None
    g = lambda f: fx.get(f, {}).get("value")  # noqa: E731
    if cid == "2.1" and g("mgmt_fee_pct") is not None:
        base = BASE_LABEL.get(g("mgmt_fee_base"), g("mgmt_fee_base") or "a base not typed")
        return f"{g('mgmt_fee_pct'):.2f}% on {base}"
    if cid == "2.2" and "incentive_fee" in fx:
        return "incentive fee: " + fmt_incentive(g("incentive_fee"))
    if g("expense_ratio_pct") is not None:
        # the headline says what the record holds (R2-P0-8): the fact's typed
        # basis clause. "net" appears only when the basis says net.
        basis = (fx.get("expense_ratio_pct", {}).get("basis") or "").strip()
        if not basis:
            note = (fx.get("expense_ratio_pct", {}).get("note") or "").split(". ")[0].split(", ")[0].strip()
            basis = note[:80] if note else "basis not typed"
        return f"{g('expense_ratio_pct'):.2f}% expense ratio, {basis}"
    if cid == "2.4" and "affe" in fx:
        v = g("affe")
        if not v.get("present"):
            return "no AFFE line"
        return f"AFFE {v['rate_pct']:.2f}%" if v.get("rate_pct") is not None \
            else "AFFE line present, rate not typed"
    if cid == "2.7" and "early_repurchase" in fx:
        return "early repurchase fee: " + fmt_early(g("early_repurchase"))
    if cid == "3.1":
        # dealing cadence and cap period are two facts (R2-P0-5): jll_ipt deals
        # daily under a quarterly cap, breit has a monthly and a quarterly cap
        parts = []
        dc = g("dealing_cadence")
        if dc:
            parts.append({"daily": "daily dealing", "monthly": "monthly dealing",
                          "quarterly": "quarterly dealing", "exchange": "on-exchange dealing"}.get(dc, dc))
        elif g("repurchase_cadence_per_year") is not None:
            parts.append(f"{g('repurchase_cadence_per_year')}x per year")
        base = BASE_LABEL.get(g("repurchase_cap_base"), g("repurchase_cap_base") or "")
        caps = g("repurchase_caps")
        if caps:
            parts.append(" and ".join(f"{c['pct']:g}% cap per {c['period']}" for c in caps)
                         + (f" on {base}" if base else ""))
        elif g("repurchase_cap_pct") is not None:
            parts.append(f"{g('repurchase_cap_pct'):g}% cap" + (f" on {base}" if base else ""))
        if parts:
            return ", ".join(parts)
        if g("wrapper_type"):
            return WRAPPER_LABEL.get(g("wrapper_type"), g("wrapper_type"))
    if cid == "3.3" and "gate_history" in fx:
        return "gating history: yes, prorated under stress" if g("gate_history") \
            else "no gating identified in the filings on record"
    if g("net_assets_usd") is not None:
        return f"{_money(g('net_assets_usd'))} net assets"
    if cid == "4.5" and g("auditor"):
        return g("auditor") + (" (Big 4)" if g("big4") else "")
    if cid == "6.4" and g("tax_form"):
        return {"1099": "Form 1099", "K-1": "Schedule K-1"}.get(g("tax_form"), g("tax_form"))
    if cid == "1.11" and g("inception"):
        yrs = g("track_record_years")
        return f"inception {g('inception')}" + (f", {yrs:g} years" if yrs is not None else "")
    if cid == "6.1" and g("wrapper_type"):
        return WRAPPER_LABEL.get(g("wrapper_type"), g("wrapper_type"))
    if cid == "1.8" and (g("pme_public_proxy") is not None or g("peer_relative_wealth_ratio") is not None):
        parts = []
        if g("pme_public_proxy") is not None:
            parts.append(f"KS-PME {g('pme_public_proxy'):.2f} vs {g('pme_public_proxy_name') or 'public proxy'}")
        if g("peer_relative_wealth_ratio") is not None:
            parts.append(f"peer relative wealth ratio {g('peer_relative_wealth_ratio'):.2f}")
        return ", ".join(parts)
    if cid == "5.3" and g("primary_benchmark_id"):
        sc = g("selection_score")
        return (f"{candidate_short(g('primary_benchmark_id'))} selected"
                + (f", {sc}/12" if sc is not None else ""))
    if cid == "3.9" and g("liquidity_structural_verdict"):
        # the headline is the structural layer only (typed facts, plan-
        # independent). The per-plan scenario verdicts are ILLUSTRATIVE and
        # appear in the cell text under that label, never in a headline (R2-P0-7)
        return f"structural verdict {g('liquidity_structural_verdict')}, plan-independent"
    field, f = next(iter(fx.items()))
    v = f["value"]
    return f"{field.replace('_', ' ')}: {v if not isinstance(v, float) else f'{v:g}'}"


# Abbreviations a period does not end a sentence after (R2-P0-4, audit round
# 2 item 4). Lower-cased. Single initials ("Stephen L.") and dotted acronyms
# ("U.S.", "p.m.", "i.e.", "L.L.C.") are matched by shape, and a period inside
# an open parenthesis or bracket never ends the sentence.
SENTENCE_ABBREVIATIONS = {
    "v.", "vs.", "mr.", "ms.", "mrs.", "dr.", "jr.", "sr.", "no.", "nos.", "inc.", "corp.",
    "co.", "ltd.", "l.p.", "llc.", "llp.", "p.m.", "a.m.", "incl.", "excl.", "approx.",
    "i.e.", "e.g.", "st.", "ste.", "u.s.", "et al.", "al.", "cf.", "sec.", "para.", "fig.",
    "vol.", "ch.", "art.", "reg.", "fed.", "del.", "n.a.", "s.a.", "inc", "mgmt.", "avg.",
    "est.", "dept.", "assoc.", "bros.", "mt.", "ft.", "jan.", "feb.", "mar.", "apr.", "jun.",
    "jul.", "aug.", "sep.", "sept.", "oct.", "nov.", "dec.",
}
_INITIAL = re.compile(r"^[A-Z]\.$")
_DOTTED = re.compile(r"^(?:[A-Za-z]\.){2,}$")


def first_sentence(text) -> str:
    """The complete first sentence of a value: the text up to the first
    sentence-ending punctuation followed by whitespace that is not an
    abbreviation, an initial, a dotted acronym, or inside parentheses."""
    s = str(text or "").strip()
    depth = 0
    for i, ch in enumerate(s):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif ch in ".!?" and depth == 0 and i + 1 < len(s) and s[i + 1].isspace():
            start = s.rfind(" ", 0, i) + 1
            tok = s[start:i + 1]
            low = tok.lower()
            if (low in SENTENCE_ABBREVIATIONS or _INITIAL.match(tok) or _DOTTED.match(tok)
                    or s[max(0, start - 3):i + 1].lower() == "et al."):
                continue
            return s[:i + 1]
    return s


def ends_at_abbreviation(text) -> bool:
    """True when a headline or findings row stops at an abbreviation."""
    s = str(text or "").rstrip()
    if not s or s.endswith("…"):
        return False    # a marked cut is not a sentence end
    tok = s.rsplit(" ", 1)[-1]
    low = tok.lower()
    return low in SENTENCE_ABBREVIATIONS or bool(_INITIAL.match(tok)) or bool(_DOTTED.match(tok))


def cell_display(cell: dict, cid: str = "", fx: dict | None = None) -> dict:
    """Display derivation (display-only; the full sourced text stays one
    disclosure away). headline = the typed fact that cites the cell when one
    exists, otherwise the first complete sentence of the value (cut at a word
    boundary when long). No figure is ever extracted from prose by regex:
    that produced headlines that read the opposite of the finding."""
    st = str(cell.get("status", "pending"))
    val = display_path_free(cell.get("value") or "")
    kind = status_kind(st)
    if kind == "n/a":
        reason = st.split(":", 1)[1].strip() if ":" in st else st[6:].strip(" -")
        return {"headline": "n/a", "plain": reason[:170]}
    if not val:
        return {"headline": "—", "plain": "Pending extraction."}
    sentence = first_sentence(val)
    # a long plain line is cut at a word boundary and marked, never left
    # looking like a sentence that stops at an abbreviation
    plain = sentence if len(sentence) <= 180 else sentence[:177].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"
    typed = typed_headline(cid, fx or {})
    if typed:
        return {"headline": typed, "plain": plain, "typed": True}
    if len(sentence) <= 140:
        headline = sentence
    else:
        cut = sentence[:137]
        headline = cut[: cut.rfind(" ")].rstrip(" ,;:") + "…" if " " in cut else cut + "…"
    return {"headline": headline, "plain": plain, "typed": False}


# ------------------------------------------------------------ R2-P0-3 maps
# Internal keys never reach a surface bare: every strategy, cohort, lane and
# candidate id renders through one of these maps (rule 11 of the round-2
# brief). The site build ships them in the bundle so the JS uses the same
# words as the memo and the packet.
STRATEGY_LABEL = {
    "private_credit": "private credit",
    "private_equity_evergreen": "evergreen private equity",
    "pe_conglomerate": "private equity conglomerate",
    "nontraded_reit": "non-traded real estate",
    "preipo_venture": "pre-IPO and venture",
}
COHORT_LABEL = {
    "private_credit": "private credit cohort",
    "evergreen_pe": "evergreen private equity cohort",
    "nontraded_reit": "non-traded real estate cohort",
    "venture": "pre-IPO and venture cohort",
}
LANE_LABEL = {
    "A": "fund-declared benchmark",
    "B": "third-party index or investable proxy",
    "C": "peer composite constructed by the evaluator",
}
ASSET_CLASS_LABEL = {
    "private_credit": "private credit", "public_credit": "public credit",
    "private_equity": "private equity", "listed_private_equity": "listed private equity",
    "real_estate": "real estate", "listed_real_estate": "listed real estate",
    "venture": "venture", "public_equity": "public equity",
}
SUB_STRATEGY_LABEL = {
    "direct_lending": "direct lending", "multi_sector_credit": "multi-sector credit",
    "diversified_credit": "diversified credit", "syndicated_loans": "syndicated loans",
    "leveraged_loans": "leveraged loans", "evergreen_pe": "evergreen private equity",
    "pe_conglomerate": "private equity conglomerate", "listed_private_equity": "listed private equity",
    "global_equity": "global equity", "us_large_cap": "US large cap",
    "nasdaq_composite": "NASDAQ Composite", "private_index": "private-market index",
    "core_plus_nontraded_re": "core-plus non-traded real estate",
    "core_nontraded_re": "core non-traded real estate", "listed_reits": "listed REITs",
    "pre_ipo_listed_cef": "pre-IPO holdings in a listed closed-end fund",
    "late_stage_listed_bdc": "late-stage growth in a listed BDC",
    "venture_interval": "venture and growth in an interval fund",
}
# short display names for benchmark candidate ids (the long names live in
# the engine's CANDIDATES table and on the composite candidate itself)
CANDIDATE_SHORT = {
    "bkln": "BKLN", "cdli": "CDLI", "csll": "CSLLI", "psp": "PSP", "psp_k": "PSP", "psp_v": "PSP",
    "urth": "URTH", "urth_k": "URTH", "spy": "SPY", "nasdaq_comp": "NASDAQ Composite",
    "cambridge_pe": "Cambridge PE benchmark", "cambridge_pe_k": "Cambridge PE benchmark",
    "cambridge_re": "Cambridge RE benchmark", "vnq": "VNQ", "odce": "NFI-ODCE",
    "peer_credit": "private credit peer composite", "peer_evergreen": "evergreen PE peer composite",
    "peer_kpec": "evergreen PE peer composite", "peer_reit": "non-traded REIT peer composite",
    "peer_venture": "venture peer composite",
}
RUBRIC_LABEL = "Tark benchmark rubric, 12 points"
COMPUTED_WRITER_LABEL = "Tark computed-cells writer"
SCHEDULE_H_ABSENT_SENTENCE = ("Schedule H benefit-payment lines are not yet in the plan record. "
                              "Demand uses the illustrative turnover sliders only.")


def strategy_label(key: str) -> str:
    return STRATEGY_LABEL.get(key, key.replace("_", " "))


def cohort_label(key: str) -> str:
    return COHORT_LABEL.get(key, key.replace("_", " "))


def lane_label(letter: str) -> str:
    return LANE_LABEL.get(letter, letter)


def asset_label(key: str) -> str:
    return ASSET_CLASS_LABEL.get(key, key.replace("_", " "))


def sub_label(key: str) -> str:
    return SUB_STRATEGY_LABEL.get(key, key.replace("_", " "))


def candidate_short(cid: str) -> str:
    return CANDIDATE_SHORT.get(cid, cid.replace("_", " "))


# Strings that must never appear on a surface or in a generated document:
# developer instructions, environment excuses, file paths, script names and
# internal identifiers (round-2 brief rule 11 and task R2-P0-3). Every entry
# is a case-insensitive regular expression. src/test_surfaces.py scans the
# built bundle, every rendered view and every generated docx with this list.
# Grow it, never prune it to get a build green.
SURFACE_FORBIDDEN = [
    r"\bsrc/",                      # a repository path
    r"\.py\b",                      # a script name
    r"\bpython ",                   # a command
    r"\brun (?:python|src/|\S+\.py|the (?:hook|fetcher|script|command|build|validator))",
    r"fetch_authority", r"askebsa\.dol\.gov is blocked", r"build container", r"not in the repository",
    r"machine that reaches", r"data/advisor", r"validate_data", r"project display rule",
    r"rubric v2", r"engine output", r"data/raw/", r"data/[a-z_]+/[A-Za-z0-9_.\-]+\.(?:json|csv|md)",
    r"R4 phrasing", r"anonymization_rule",
    # bare registry keys (strategies, cohorts, candidate ids)
    r"\bpeer_evergreen\b", r"\bpeer_credit\b", r"\bpeer_kpec\b", r"\bpeer_reit\b", r"\bpeer_venture\b",
    r"\bprivate_credit\b", r"\bprivate_equity_evergreen\b", r"\bpreipo_venture\b",
    r"\bpe_conglomerate\b", r"\bnontraded_reit\b", r"\bevergreen_pe\b",
    r"\bcambridge_pe_k\b", r"\bpsp_k\b", r"\bpsp_v\b", r"\burth_k\b",
]


# Repository paths inside cell text stay in the record (the validator checks
# that every cited path exists) and render as reader labels on every surface
# and in every document (R2-P0-3). Order matters: specific before generic.
_PATH_LABELS = [
    (re.compile(r"data/analytics/supplement\.json(?:\s*\(stress_windows\.[a-z_]+\))?"), "the analytics supplement artifact (stress windows)"),
    (re.compile(r"data/analytics/metrics\.json"), "the analytics metrics artifact"),
    (re.compile(r"data/cohorts/([a-z_]+)\.json"), lambda m: f"the cohort artifact ({cohort_label(m.group(1))})"),
    (re.compile(r"data/liquidity/[A-Za-z0-9_.\-]*"), "the liquidity match artifacts"),
    (re.compile(r"data/benchmarks/[A-Za-z0-9_.\-]*"), "the benchmark selection artifact"),
    (re.compile(r"data/manifest\.csv"), "the filing manifest"),
    # no plan label here: cell 3.7 still cites one plan's record in every
    # product (audit item 30, owned per plan in R2-P1-13), and naming it would
    # leak that plan into the other plans' memos
    (re.compile(r"data/plans/([a-z_]+)\.json"), "the plan record on file"),
    (re.compile(r"data/raw/[A-Za-z0-9_.\-]*/?"), "the fund's raw filings on disk"),
    (re.compile(r"data/series/series_manifest\.json"), "the held price-series manifest"),
    (re.compile(r"data/series/([a-z0-9_]+)\.csv"), lambda m: f"the held daily series {m.group(1).upper()} (Yahoo adjusted close)"),
    (re.compile(r"data/series/"), "the held daily series"),
    (re.compile(r"data/series_annual(?:/[A-Za-z0-9_.\-]*)?"), "the filed fiscal-year returns on record"),
    (re.compile(r"data/series_monthly/[A-Za-z0-9_.\-]*"), "the monthly NAV series on record"),
    (re.compile(r"data/series_quarterly/manifest\.json"), "the quarterly NAV series manifest"),
    (re.compile(r"data/series_quarterly(?:/[A-Za-z0-9_.\-]*)?"), "the quarterly NAV series on record"),
    (re.compile(r"data/citations/[A-Za-z0-9_.\-]*"), "the citations record"),
    (re.compile(r"data/facts(?:/[A-Za-z0-9_.\-]*)?"), "the typed facts"),
    (re.compile(r"data/roster_decisions\.md"), "the roster decisions record"),
    (re.compile(r"data/evidence(?:/[A-Za-z0-9_.\-*]*)?"), "the evidence ledger"),
    (re.compile(r"data/[A-Za-z0-9_./\-]*"), "the record"),
    (re.compile(r"stress_windows\.[a-z_]+"), "stress windows"),
]


def _plan_label(plan_key: str) -> str:
    from tark_data import load_plan
    try:
        return load_plan(plan_key)["display_label"]
    except Exception:  # noqa: BLE001 - a plan that no longer exists keeps its key out of the surface
        return "a reference plan"


def display_path_free(text) -> str:
    """The same text with every repository path replaced by a reader label."""
    s = str(text or "")
    if "data/" not in s and "stress_windows" not in s:
        return s
    for rx, rep in _PATH_LABELS:
        s = rx.sub(rep, s)
    return s

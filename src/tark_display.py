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
from decimal import ROUND_HALF_UP, Decimal

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
    return " / ".join(parts) if parts else "present, rate not on record (see 2.2)"


def fmt_early(v: dict | None) -> str:
    if not v:
        return ""
    if not v.get("present"):
        return "none"
    rate = _pct(v["rate_pct"]) if v.get("rate_pct") is not None else \
        "fee present, rate not on record (see 2.7)"
    return f"{rate} {v['window']}" if v.get("window") else rate


def _fixed1(v: float) -> str:
    """One decimal, an exact binary tie rounded up, the rule the site's
    JavaScript toFixed applies, so the memo and the site print one figure."""
    return str(Decimal(v).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _money(x) -> str:
    if x >= 1e9:
        return f"${_fixed1(x / 1e9)}B"
    if x >= 1e6:
        return f"${_fixed1(x / 1e6)}M"
    return f"${round(x):,}"


def plan_demand_sentence(plan: dict) -> str | None:
    """Cell 3.7 for one plan (R3-P2-11): the plan's own participant counts
    and filed outflow proxy, from its record. One builder for the memo and
    the site, so the two never drift. None when the plan carries no counts."""
    part = plan.get("participants") or {}
    wab = part.get("with_account_balances")
    if not wab:
        return None
    sep = part.get("separated_deferred_vested") or 0
    act = part.get("active_eoy") or 0
    ret = part.get("retired_receiving") or 0
    fo = ((plan.get("schedule_h") or {}).get("filed_outflow_proxy") or {})
    tail = f"{sep:,.0f} separated participants with balances = {sep / wab * 100:.1f}% of {wab:,.0f} accounts"
    return (f"Plan-side demand profile for this plan (Form 5500, plan year {plan.get('plan_year', 'on file')}): "
            f"{tail} (the near-term liquidity tail), {act:,.0f} active, {ret:,.0f} retirees in pay status"
            + (f", filed outflow proxy {fo['value']:g}% of beginning net assets (Schedule H totals)."
               if fo.get("value") is not None else "."))


def reconciliation_sentence(filed_pct: float, note: str, comp: dict) -> str:
    """The filed since-inception return beside the held series' annualized
    return, with why the two differ (R3-P2-17d). Neither is restated and
    the comparison uses the series. One builder for the cells, the memo
    and the site."""
    return (f"Reconciliation: the filed since-inception annualized return is {filed_pct:g}% "
            f"({note}, cell 1.2) and the held series annualizes to {comp['fund_ann_pct']}%/yr over "
            f"{comp['window']}. The two differ by end date, by the adjusted-close reinvestment "
            "convention against the fund's own total-return calculation, and by share class. "
            "Neither is restated and the comparison uses the series.")


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
        base = BASE_LABEL.get(g("mgmt_fee_base"), g("mgmt_fee_base") or "a base not on record")
        return f"{g('mgmt_fee_pct'):.2f}% on {base}"
    if cid == "2.2" and "incentive_fee" in fx:
        return "incentive fee: " + fmt_incentive(g("incentive_fee"))
    if g("expense_ratio_pct") is not None:
        # the headline says what the record holds (R2-P0-8): the fact's typed
        # basis clause. "net" appears only when the basis says net.
        basis = (fx.get("expense_ratio_pct", {}).get("basis") or "").strip()
        if not basis:
            note = (fx.get("expense_ratio_pct", {}).get("note") or "").split(". ")[0].split(", ")[0].strip()
            basis = note[:80] if note else "basis not on record"
        return f"{g('expense_ratio_pct'):.2f}% expense ratio, {basis}"
    if cid == "2.4" and "affe" in fx:
        v = g("affe")
        if not v.get("present"):
            return "no AFFE line"
        return f"AFFE {v['rate_pct']:.2f}%" if v.get("rate_pct") is not None \
            else "AFFE line present, rate not on record"
    if cid == "2.7" and "early_repurchase" in fx:
        return "early repurchase fee: " + fmt_early(g("early_repurchase"))
    if cid == "3.1":
        # the program status precedes the cadence (R3-P2-7): a suspended
        # plan's cadence is not a dealing term a holder can use
        if g("repurchase_program_status") == "suspended":
            since = fx["repurchase_program_status"].get("since")
            dc = g("dealing_cadence")
            return ("repurchases suspended" + (f" since the {since}" if since else "")
                    + (f", the {dc} plan is closed to ordinary requests" if dc in ("daily", "monthly", "quarterly")
                       else ", the plan is closed to ordinary requests"))
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
    if cid == "1.12" and "peer_relative_wealth_ratio" in fx:
        v = g("peer_relative_wealth_ratio")
        return (f"peer relative wealth ratio {v:.2f}, not a benchmark" if v is not None
                else "peer composite refused, table only")
    if cid == "1.8" and (g("pme_public_proxy") is not None or g("slot_k_relative_wealth_ratio") is not None):
        # the meaningful-benchmark slot's own statistic first, the reference
        # comparison named as such when Slot K carries no number (decision 7.21)
        parts = []
        if g("slot_k_relative_wealth_ratio") is not None:
            parts.append(f"relative wealth ratio {g('slot_k_relative_wealth_ratio'):.2f} vs the published index")
        if g("pme_public_proxy") is not None:
            note = (fx.get("pme_public_proxy", {}).get("note") or "")
            ref = "reference comparison" in note
            parts.append(f"KS-PME {g('pme_public_proxy'):.2f} vs {g('pme_public_proxy_name') or 'public proxy'}"
                         + (" (reference, not the benchmark)" if ref else ""))
        return ", ".join(parts)
    if cid == "5.3" and g("primary_benchmark_id"):
        sc = g("selection_score")
        by_desc = g("slot_k_by_descriptor") is True
        return (f"{candidate_short(g('primary_benchmark_id'))} selected"
                + (" by descriptor" if by_desc else "")
                + (f", {x_of_n(sc, RUBRIC_MAX)}" if sc is not None else ""))
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


# A leading word that only repeats the status the chip already carries. The
# headline says what the row found, never what tier it sits in (R3-P1-10).
_STATUS_LEAD = re.compile(
    r"^(PARTIAL|ABSENCE DOCUMENTED|DOCUMENTED ABSENCE|STRUCTURED SERIES FETCHED|"
    r"SCOPE LIMIT|COMPUTED|FETCHED|N/A)\b\s*[:\u2014-]?\s*")
# Acronyms that are the word, not shouting.
_KEEP_CAPS = {"NAV", "AFFE", "TER", "PME", "ROC", "ITD", "GAAP", "REIT", "RIC", "BDC",
              "IRR", "SEC", "ERISA", "QDIA", "DIA", "DRIP", "PCAOB", "ASC", "LLC", "US",
              "UK", "OP", "JV", "ID", "FFO", "K-1", "N-2", "N-CSR"}


def _unshout(label: str) -> str:
    """A leading all-capitals label reads as a label, not as shouting. Known
    acronyms keep their capitals."""
    words = label.split()
    if not words or not all(w.isupper() for w in words if w.isalpha()):
        return label
    out = [words[0] if words[0] in _KEEP_CAPS else words[0].capitalize()]
    out += [w if w in _KEEP_CAPS else w.lower() for w in words[1:]]
    return " ".join(out)


def headline_copy(sentence: str, limit: int = 140) -> str:
    """A headline: the finding, in one line, with no status word in front of
    it and no trailing ellipsis. A sentence too long for the line is cut at
    its last clause boundary and closed, because a headline that trails off
    tells a reader nothing (R3-P1-10)."""
    s = _STATUS_LEAD.sub("", sentence).strip()
    head, sep, rest = s.partition(":")
    if sep and len(head) <= 40 and head.isupper():
        s = _unshout(head) + ":" + rest
    # a headline that is one shouted word is the word, not the shout
    bare = s.rstrip(".!? ")
    if bare and bare.isupper() and len(bare.split()) <= 3 and bare not in _KEEP_CAPS:
        s = _unshout(bare) + s[len(bare):]
    if len(s) <= limit:
        return s
    # candidate cuts, outside brackets only, so a headline never stops inside
    # a parenthesis it never closes
    depth, breaks, words = 0, [], []
    for i, ch in enumerate(s[:limit]):
        if ch in "([":
            if depth == 0:
                breaks.append(i)
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif depth == 0 and ch == " ":
            words.append(i)
            if i and s[i - 1] in ",;:":
                breaks.append(i - 1)
    # a headline must not stop at an abbreviation, an initial or a dotted
    # acronym, which would read as a sentence that ended there, and it must
    # not stop inside a bracket it never closes: walk the boundaries back
    # until the closing word is a word
    for cut in sorted({*breaks, *words, limit}, reverse=True):
        head = _balanced(s[:cut]).rstrip(" ,;:(")
        if len(head) >= limit // 4 and not ends_at_abbreviation(head + "."):
            return head + "."
    # nothing in the line closes cleanly: the record's own first words, marked
    return _balanced(s[:limit]).rstrip(" ,;:(") + "\u2026"


def _balanced(s: str) -> str:
    """The text up to the last bracket it leaves open, so a cut line never
    shows half a parenthesis."""
    stack = []
    for i, ch in enumerate(s):
        if ch in "([":
            stack.append(i)
        elif ch in ")]" and stack:
            stack.pop()
    return s[:stack[0]] if stack else s


def cell_display(cell: dict, cid: str = "", fx: dict | None = None) -> dict:
    """Display derivation (display-only; the full sourced text stays one
    disclosure away). headline = the typed fact that cites the cell when one
    exists, otherwise the first complete sentence of the value (cut at a word
    boundary when long). No figure is ever extracted from prose by regex:
    that produced headlines that read the opposite of the finding."""
    st = str(cell.get("status", "pending"))
    val = display_copy(cell.get("value") or "")
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
    # no "typed" key when false: the views read a missing key as false and
    # the bundle saves 880 copies of the flag
    return {"headline": headline_copy(sentence), "plain": plain}


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
    "A": "fund-declared benchmark or SEC-required comparator",
    "B": "exchange-traded strategy proxy",
    "P": "published strategy index",
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
    "bkln": "BKLN", "cdli": "CDLI", "csll": "CSLLI", "lsta": "Morningstar LSTA Leveraged Loan",
    "bbg_agg": "Bloomberg US Aggregate", "ice_bofa_hy": "ICE BofA US High Yield",
    "psp": "PSP", "psp_k": "PSP", "psp_v": "PSP",
    "urth": "URTH", "urth_k": "URTH", "spy": "SPY", "nasdaq_comp": "NASDAQ Composite",
    "cambridge_pe": "Cambridge PE benchmark", "cambridge_pe_k": "Cambridge PE benchmark",
    "vnq": "VNQ", "odce": "NFI-ODCE",
}
SLOT_LABELS = {"slot_k": "Meaningful benchmark (paragraph (k))",
               "slot_g": "Peer comparison (paragraphs (g) and (h))"}
from tark_benchmark_common import RUBRIC_LABEL, RUBRIC_MAX, x_of_n  # noqa: E402,F401
COMPUTED_WRITER_LABEL = "Tark computed cells"
SCHEDULE_H_ABSENT_SENTENCE = ("Schedule H benefit-payment line 2e is not yet in the plan record. "
                              "The filed outflow proxy (total expenses less administrative "
                              "expenses over beginning net assets) stands in for it as the base "
                              "demand, and the turnover assumptions are the stress around it.")


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


# The allowlist gate's second family (R3-P2-12, design system section 6).
# Reader prose, meaning every bundle string a view prints, every rendered
# view and every document paragraph, may not carry an internal token: a
# snake_case key, a repository path or file name, a ticket reference, a
# developer word, or "slider" outside the name of the figure the control
# sets ("slider assumption") and the control's own label ("allocation
# slider"). A field set in code style for provenance (a cited file name, an
# accession column, a form's JSON) is exempt from this family and never from
# SURFACE_FORBIDDEN. URLs are stripped before the rules run. Each entry is
# (name, case-insensitive regular expression). Grow it, never prune it.
PROSE_RULES = [
    ("snake_case token", r"(?<![A-Za-z0-9_/.\-])[a-z][a-z0-9]*_[a-z0-9_]+(?![A-Za-z0-9_])"),
    ("repository path or file name",
     r"(?<![\w/])(?:data|docs|src|site|web)/[A-Za-z0-9_./\-]+"
     r"|(?<![\w/.\-])[A-Za-z0-9_\-]{2,}\.(?:py|json|csv|md|js|htm|html|txt)\b"),
    ("ticket reference", r"\bR[0-9]-P[0-9]-[0-9]+\b|\bR[0-9]-P[0-9]\b|\bP[0-9]-[0-9]+\b"),
    ("developer word", r"\b(?:engine|artifacts?|typed|the writer|the build|this build|the site)\b"),
    ("slider outside its label", r"(?<!allocation )\bsliders?\b(?! assumption\b)"),
]
PROSE_URL = re.compile(r"https?://\S+")


def prose_hits(text: str) -> list[tuple[str, str]]:
    """(rule name, matched text) for every PROSE_RULES hit in one string."""
    t = PROSE_URL.sub(" ", text or "")
    out = []
    for name, rx in _PROSE_COMPILED:
        for m in rx.finditer(t):
            out.append((name, m.group(0)))
    return out


_PROSE_COMPILED = [(n, re.compile(p, re.IGNORECASE)) for n, p in PROSE_RULES]

# Internal keys that reach reader prose from inside the record (a product
# key in a cell's own text, a fact field name, a wrapper or base enum, a
# series column) render as their words on every surface and in every
# document (R3-P2-12). A verbatim quote is never rewritten.
FACT_LABEL = {
    "gate_history": "gating history",
    "repurchase_cadence_per_year": "dealing cadence",
    "repurchase_cap_pct": "repurchase cap",
    "repurchase_program_status": "program status",
    "repurchase_caps": "repurchase caps",
    "net_assets_usd": "net assets",
    "adj_close": "adjusted close",
    "index_proxy": "public market proxy",
    "series_manifest": "the series manifest",
    # the N-CEN structured dataset's own field names, cited in cells 4.5 and 4.6
    "PUB_ACCOUNTANT_NAME": "the accountant-name field",
    "IS_ACCT_OPINION_QUALIFIED": "the opinion-qualified flag",
    "IS_NAV_ERROR_CORRECTED": "the NAV-error-corrected flag",
}


def fact_label(field: str) -> str:
    return FACT_LABEL.get(field, field.replace("_", " "))


_KEY_LABELS: list[tuple[re.Pattern, str]] | None = None


def _key_labels() -> list[tuple[re.Pattern, str]]:
    global _KEY_LABELS
    if _KEY_LABELS is None:
        from tark_data import load_products
        pairs: list[tuple[str, str]] = []
        for key, p in load_products().items():
            pairs.append((key, p["fund_name"].split(" (")[0]))
        pairs += [(k, v) for k, v in WRAPPER_LABEL.items()]
        pairs += [(k, v) for k, v in BASE_LABEL.items() if "_" in k]
        pairs += list(FACT_LABEL.items())
        # longest key first so a key that contains another is replaced whole
        pairs.sort(key=lambda kv: -len(kv[0]))
        _KEY_LABELS = [(re.compile(r"(?<![A-Za-z0-9_])" + re.escape(k) + r"(?![A-Za-z0-9_])"), v)
                       for k, v in pairs if "_" in k]
    return _KEY_LABELS


_EM_DASH = re.compile(r"\s*\u2014\s*")
_SEMICOLON = re.compile(r";\s*")
_DOUBLE_PERIOD = re.compile(r"(?<!\.)\.\.(?!\.)")
_SPACED_HYPHEN = re.compile(r"(?<=[A-Za-z)\.%']) - (?=[A-Za-z(\'])")
_PERIODS = re.compile(r"\bperiod\(s\)")


def punctuate(text: str) -> str:
    """The copy rule on punctuation (R3-P2-17): no em dash and no semicolon
    in reader prose (each becomes a comma), no double period, no spaced
    hyphen between words (a comma), and "periods" for "period(s)". URLs are
    left alone. Applied to record text on every surface and in every
    document, never to a verbatim quote."""
    parts = re.split(r"(https?://\S+)", text)
    for i in range(0, len(parts), 2):
        t = parts[i]
        t = _EM_DASH.sub(", ", t)
        t = _SEMICOLON.sub(", ", t)
        t = _DOUBLE_PERIOD.sub(".", t)
        t = _SPACED_HYPHEN.sub(", ", t)
        t = _PERIODS.sub("periods", t)
        # typographic marks: an apostrophe between letters, a possessive after
        # a plural, a clipped decade, and a pair of double quotes
        t = _APOSTROPHE.sub("\u2019", t)
        t = _CLIPPED.sub("\u2019", t)
        t = _OPEN_SQ.sub("\u2018", t)
        t = _DQUOTES.sub("\u201c\\1\u201d", t)
        parts[i] = t
    return "".join(parts)


def display_copy_deep(obj, skip=("quote",)):
    """The copy rule over a whole view.

    A string with whitespace in it is prose a reader will read, and it goes
    through `display_copy` in full. A string without whitespace is an address,
    not prose: a product key, a plan key, a cell id, a schema name, a file
    name, an accession, a hash, a URL. Rewriting one of those would break the
    thing that points at it, so an address is only screened for a repository
    path, which becomes its reader label.

    The values under a key named in `skip` are exempt entirely: a verbatim
    quote from a filing and the rule's own paragraphs are somebody else's
    words, and editing them would make the record wrong (rule 2).
    """
    if isinstance(obj, dict):
        return {k: (v if k in skip else display_copy_deep(v, skip)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [display_copy_deep(v, skip) for v in obj]
    if not isinstance(obj, str):
        return obj
    return display_copy(obj) if any(c.isspace() for c in obj) else display_path_free(obj)


_APOSTROPHE = re.compile(r"(?<=[A-Za-z])'(?=[A-Za-z])")
# An opening quote takes the left mark and a closing quote after a word takes
# the right one. A clipped year is deliberately left alone: it is written the
# same way in the wrapper labels the selection record hashes, and curling it
# here would change four record fingerprints for a typographic nicety.
_CLIPPED = re.compile(r"(?<=[A-Za-z])'(?=[\s.,;:)\]]|$)")
_OPEN_SQ = re.compile(r"(?<=[\s(\[])'(?=[A-Za-z])")
_DQUOTES = re.compile(r'"([^"\n]{1,200})"')


def display_copy(text) -> str:
    """Reader copy of a record string: repository paths become their labels,
    internal keys become their words and the punctuation rule applies. A URL
    inside the string is left exactly as written. Used for cell values,
    sources and sections, never for a verbatim quote."""
    if not isinstance(text, str):
        return text
    parts = re.split(r"(https?://\S+)", text)
    for i in range(0, len(parts), 2):
        out = display_path_free(parts[i])
        for rx, label in _key_labels():
            out = rx.sub(label, out)
        parts[i] = punctuate(out)
    return "".join(parts)


# Repository paths inside cell text stay in the record (the validator checks
# that every cited path exists) and render as reader labels on every surface
# and in every document (R2-P0-3). Order matters: specific before generic.
_PATH_LABELS = [
    (re.compile(r"data/analytics/supplement\.json(?:\s*\(stress_windows\.[a-z_]+\))?"), "the analytics supplement (stress windows)"),
    (re.compile(r"data/analytics/metrics\.json"), "the analytics metrics"),
    (re.compile(r"data/cohorts/([a-z_]+)\.json"), lambda m: f"the cohort record ({cohort_label(m.group(1))})"),
    (re.compile(r"data/liquidity/[A-Za-z0-9_.\-]*"), "the liquidity match records"),
    (re.compile(r"data/benchmarks/[A-Za-z0-9_.\-]*"), "the benchmark selection record"),
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
    (re.compile(r"data/facts(?:/[A-Za-z0-9_.\-]*)?"), "the facts on record"),
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


# A local copy of a filing carries the form in its file name. The surface says
# the form, which is what a reader recognises and what the rest of the record
# already calls it, never the file.
_FILING_FORMS = {
    "486bpos": "486BPOS", "486apos": "486APOS", "ncsr": "N-CSR", "ncsrs": "N-CSRS",
    "sctoi": "SC TO-I", "sctot": "SC TO-T", "424b3": "424B3", "424b5": "424B5",
    "424b2": "424B2", "10k": "10-K", "10q": "10-Q", "8k": "8-K", "ncen": "N-CEN",
    "nport": "N-PORT", "n2": "N-2", "n23c3a": "N-23C3A", "def14a": "DEF 14A",
    "s1": "S-1", "s11": "S-11", "497": "497", "40417g": "40-17G", "nq": "N-Q",
}
_LOCAL_FILING = re.compile(r"(?<![\w/.-])[a-z][a-z0-9]*_([a-z0-9]+)\.(?:txt|htm|html|pdf)\b")
# a published dataset a reader could go and look at, named for what it is
_DATASETS = [
    (re.compile(r"(?<![\w/.-])company_tickers\.json\b"), "the SEC company ticker file"),
]


def _filing_label(m: re.Match) -> str:
    return _FILING_FORMS.get(m.group(1), "a filing on file")


def display_path_free(text) -> str:
    """The same text with every repository path and every local filing copy
    replaced by a reader label. A URL is left exactly as written."""
    s = str(text or "")
    parts = re.split(r"(https?://\S+)", s)
    for i in range(0, len(parts), 2):
        seg = parts[i]
        if "data/" in seg or "stress_windows" in seg:
            for rx, rep in _PATH_LABELS:
                seg = rx.sub(rep, seg)
        seg = _LOCAL_FILING.sub(_filing_label, seg)
        for rx, label in _DATASETS:
            seg = rx.sub(label, seg)
        parts[i] = seg
    return "".join(parts)


# The glossary: plain language first, the term of art in the parenthesis.
# Rendered as a keyboard-reachable definition wherever a term appears.
GLOSSARY = {
    "PME": "Did the fund beat simply buying an index with the same cash, at the same times? Above 1.0 = yes. (Kaplan-Schoar Public Market Equivalent)",
    "KS-PME": "Did the fund beat simply buying an index with the same cash, at the same times? Above 1.0 = yes. (Kaplan-Schoar Public Market Equivalent)",
    "Direct Alpha": "The fund's yearly edge over the index, as a percentage. Zero = index-like. (Gredil/Griffiths/Stucke annualized excess IRR)",
    "relative wealth ratio": "The fund's cumulative growth divided by the comparator's over identical periods. Above 1.0 = the fund grew more. Not a PME: the comparator is appraisal-based and cannot be bought.",
    "meaningful benchmark": "The paragraph (k) comparison: the highest-scoring independent public index, exchange-traded proxy or published strategy index for the fund's strategy. A PME only when the comparator is a public market series.",
    "peer comparison": "The paragraph (g) and (h) comparison: the cohort side by side over identical periods with n per period, and an equal-weight composite only where every peer reports the period. Never the benchmark, never a PME.",
    "AFFE": "Fees of the funds this fund invests in, passed through to you on top of its own fees. (Acquired Fund Fees & Expenses)",
    "TER": "Everything the fund charges in a year as a percent of assets. (Total Expense Ratio)",
    "Rule 23c-3": "The SEC rule forcing an interval fund to offer buybacks on a fixed schedule - liquidity by law, not by choice.",
    "interval fund": "A fund legally committed to periodic buyback windows (SEC Rule 23c-3).",
    "tender offer": "The fund's board CHOOSES each buyback window - nothing legally requires the next one.",
    "DIA": "An investment option on a 401(k) menu that participants pick themselves. (Designated Investment Alternative)",
    "404(c)": "The ERISA section that shields plan sponsors when participants direct their own accounts - assumes daily menus.",
    "de-smoothing": "Un-flattering correction: appraisal prices understate risk. This statistically restores the hidden volatility. (Geltner AR(1) unsmoothing)",
    "high-water mark": "The manager earns performance fees only above the previous peak - no double-charging for recovered losses.",
    "hurdle": "Minimum return the fund must clear before performance fees start.",
    "catch-up": "After the hurdle, the manager temporarily takes ALL profit until they hold their full share.",
    "NAV": "What one share is worth by the fund's own books. (Net Asset Value)",
    "Transactional NAV": "The NAV at which the fund actually sells and buys back shares (can differ from GAAP NAV).",
    "premium/discount": "The gap between what the market pays and what the fund says a share is worth.",
    "K-1": "The partnership tax form: arrives late, complicates filing. Retirement recordkeepers hate it. (Schedule K-1)",
    "1099": "The ordinary dividend tax form retirement plans handle automatically. (Form 1099-DIV/-B)",
    "RIC": "A fund taxed like a mutual fund: no fund-level tax, 1099s to investors. (Regulated Investment Company)",
    "REIT": "A tax structure for property funds: must pay out 90% of income. Investors get 1099s. (Real Estate Investment Trust)",
    "QDIA": "The menu option your money lands in when you never choose. (Qualified Default Investment Alternative)",
    "DRIP": "Distributions automatically buy more shares unless you opt out. (Distribution Reinvestment Plan)",
    "proration": "When buyback requests exceed the cap, everyone gets only a slice - the rest waits for the next window.",
    "gating": "The fund limiting or suspending buybacks - the semi-liquid wrapper's stress behavior.",
    "Managed Assets": "A fee base that INCLUDES borrowed money - the fund earns fees on leverage.",
    "gross assets": "A fee base that INCLUDES assets bought with borrowings - fees on leverage.",
    "ASC 820": "The accounting rulebook for fair value: Level 1 = market prices, Level 3 = the fund's own models.",
    "Level 3": "Assets valued by the fund's own models and judgment - no market price exists. (ASC 820 fair-value hierarchy)",
    "NAV practical expedient": "Holdings valued at whatever the underlying fund reports - trusted, not re-derived.",
    "ITD": "Since the fund's first day. (Inception-to-date)",
    "ROC": "Distributions that are your own money coming back, not earnings. (Return of Capital)",
    "smoothing": "Appraisal-based prices react late and move little - reported volatility understates real risk.",
    "expense limitation": "The adviser's promise to absorb costs above a cap - often reclaimable for 3 years.",
    "PCAOB": "The audit regulator. Registration means the auditor is inspected. (Public Company Accounting Oversight Board)",
    "N-23C3A": "The SEC form an interval fund files for EVERY buyback window - a public paper trail of kept promises.",
}

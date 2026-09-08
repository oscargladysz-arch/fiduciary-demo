"""
Tark static-site data bundle builder
====================================
Reads the canonical data layer (the SAME files the validator gates) and emits
site/data.js — a single window.TARK bundle — plus generates the decision-memo
docx artifacts (one per plan and product) into site/memos/. The site's HTML/JS never hard-codes a fact:
everything on screen comes from this generated bundle, so the data layer stays
the single source of truth.

Anonymization is machine-enforced here too: identity_private blocks are
stripped from every plan, and the build FAILS if any sponsor name from any
data/plans/*.json appears anywhere in the emitted bundle.

Run:  python src/build_site.py     -> site/data.js, site/memos/*.docx
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path

from tark_benchmark import MIN_PRIMARY_SCORE, PRODUCT_PROFILES
from tark_benchmark_common import (BY_DESCRIPTOR_SENTENCE as _BY_DESCRIPTOR_SENTENCE, RUBRIC_MAX as _RUBRIC_MAX,
                                   STRATEGY_GATE_MIN as _STRATEGY_GATE_MIN, TIE_SENTENCE as _TIE_SENTENCE)
from tark_display import (SLOT_LABELS, BASE_LABEL, CANDIDATE_SHORT, LANE_LABEL, RUBRIC_LABEL, STRATEGY_LABEL,
                          WRAPPER_LABEL, cell_display, display_path_free, facts_by_cell,
                          plan_demand_sentence, reconciliation_sentence)
from tark_memo import write_all
from tark_packet import write_all_packets
from tark_data import (ADVISOR_NOT_EVIDENCE, ADVISOR_STATED_CELLS, BASE, DATA, CELLS, FACTORS,
                       RULE, advisor_entries, authority,
                       coverage_summary, rule_ref,
                       coverage_totals, load_evidence, load_plan,
                       load_product, load_products, load_series,
                       load_series_manifest, plan_keys, product_keys,
                       status_kind)
from tark_anon import docx_text, forbidden_tokens, leaks

SITE = BASE / "site"


# glossary: plain-language primary, term-of-art secondary. Rendered as chips
# with hover definitions wherever these terms appear in headline lines.
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

def _path_free(obj):
    """Every string inside a shipped structure with repository paths rendered
    as reader labels (R2-P0-3)."""
    if isinstance(obj, dict):
        return {k: _path_free(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_path_free(v) for v in obj]
    return display_path_free(obj) if isinstance(obj, str) else obj


def evidence_counts(key: str) -> dict:
    """Per-kind coverage for one product: the shared formula in tark_data."""
    return coverage_summary(key)


def crosscheck_summary() -> dict:
    """The cross-check tile is read from the machine-readable header of
    docs/crosscheck_report.md, never a literal. The human-verified count is
    live from the record. An agent pass is described as an agent pass."""
    text = (BASE / "docs" / "crosscheck_report.md").read_text()
    m = re.search(r"<!-- tark:crosscheck\n(.*?)-->", text, re.S)
    if not m:
        raise SystemExit("docs/crosscheck_report.md lacks the tark:crosscheck header")
    kv = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()
    ints = {k: int(kv[k]) for k in ("cells_checked", "confirmed", "corrected",
                                    "unlocatable", "products")}
    verified = coverage_totals()["counts"]["verified"]
    return {**ints, "date": kv["date"], "run_by": kv["run_by"],
            "human_verified": verified,
            "tile": (f"{ints['cells_checked']} cells re-located by an agent pass "
                     f"({ints['products']} products, {kv['date']}), "
                     f"{ints['confirmed']} confirmed, {ints['corrected']} corrected. "
                     f"Human verification: {verified}."),
            "source": "docs/crosscheck_report.md"}



ADJ_LABEL = "Yahoo adjusted close (approximates NAV total return)"
CLOSE_LABEL = "Yahoo daily close (market price)"


def series_sources() -> dict:
    """Per held series: provider, role, coverage and the label every chart
    prints beside it, from data/series/series_manifest.json (one source).
    `<ticker>` is the adjusted close, `<ticker>_daily` the raw close."""
    man = load_series_manifest()
    out: dict = {}
    for m in man.get("series", []):
        t = m["ticker"].lower()
        base = {"ticker": m["ticker"], "source": m["source"], "role": m["role"],
                "first": m["first"], "last": m["last"], "pulled": m.get("pulled")}
        out[t] = {**base, "column": "adj_close", "label": ADJ_LABEL}
        out[f"{t}_daily"] = {**base, "column": "close", "label": CLOSE_LABEL}
    return out


def daily_series(ticker: str, column: str = "adj_close") -> list:
    return [[d, round(v, 6)] for d, v in load_series(ticker, column)]


_MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}


def _with_period_ends(nav: dict) -> dict:
    """Derive an ISO period_end for each quarterly row from its printed
    period string, e.g. '... - December 31, 2025)'."""
    for row in nav["rows"]:
        m = re.search(r"-\s*(\w+) (\d+), (\d{4})\)", row["period"])
        if m:
            row["period_end"] = (f"{m.group(3)}-{_MONTHS[m.group(1)]:02d}-"
                                 f"{int(m.group(2)):02d}")
    return nav


# the investable proxy library the swap lab can recompute against — every
# entry has a committed daily series on disk
PROXY_LIBRARY = {
    "bkln": "BKLN: senior loans (Invesco / Morningstar LSTA class)",
    "psp": "PSP: listed private equity (Invesco / Red Rocks)",
    "urth": "URTH: MSCI World (iShares)",
    "spy": "SPY: S&P 500 (SPDR)",
    "vnq": "VNQ: listed REITs (Vanguard / MSCI US REIT)",
}


STRATEGY_DEFAULT_PROXY = {
    "private_credit": "bkln", "private_equity_evergreen": "psp",
    "pe_conglomerate": "psp", "nontraded_reit": "vnq", "preipo_venture": "psp",
}
PRICE_SERIES_WARNING = ("MARKET-PRICE series. Any PME here benchmarks the premium, "
                        "not the portfolio. The engine formally escalated instead "
                        "of selecting (5.6)")


def daily_series_map() -> dict:
    """product -> the daily series the labs may recompute on, derived from the
    engine profiles (never a second hand-typed roster). Market-priced
    products point at their close series and carry the warning."""
    from tark_benchmark import PRODUCT_PROFILES as PP
    out = {}
    for key, prof in PP.items():
        t = prof.get("series")
        if not t:
            continue
        price = bool(prof.get("price_nav_decoupled"))
        out[key] = {"series": f"{t}_daily" if price else t,
                    "ticker": t.upper(),
                    "column": "close" if price else "adj_close",
                    "price_series": price,
                    "label": f"{t.upper()} {series_sources()[f'{t}_daily' if price else t]['label']}"}
    return out


def _cohort_bundle(doc: dict) -> dict:
    """The cohort artifact for the bundle: the composite rows keep label,
    period, n, members and the composite return (the chart and the n table),
    the per-member returns stay in the record and on the Slot G card."""
    comp = dict(doc.get("composite") or {})
    if comp.get("rows"):
        comp["rows"] = [{k: v for k, v in r.items() if k != "returns"} for r in comp["rows"]]
    return {**doc, "composite": comp}


def compact_series(series: list) -> dict:
    """Transport encoding of a daily series: the first date, day offsets from
    it and the values. main.js expands it back to [[date, value], ...] the
    moment the chunk loads, so every consumer sees the same array as before
    and the lab's parity with the engine is unchanged."""
    from datetime import date
    base = date.fromisoformat(series[0][0])
    return {"base": series[0][0],
            "d": [(date.fromisoformat(d) - base).days for d, _ in series],
            "v": [v for _, v in series]}


def pme_profiles() -> dict:
    """Analysis Lab profiles for EVERY product with a recomputable return
    input: a daily series, a fiscal-year return list, or a disclosed
    annualized figure. Inputs come from the engine profiles and the
    registry's return inputs (the same inputs the selection used). The default
    proxy is the series of the engine's own primary selection, so the lab
    opens on the engine's comparison and the user swaps from there."""
    from tark_benchmark import PRODUCT_PROFILES as PP, RETURN_INPUTS as pi, menu_for
    daily = daily_series_map()
    out = {}
    for key, prof in PP.items():
        merged = {**prof, **pi.get(key, {}).get("profile", {})}
        strategy = merged["strategy"]
        proxy = STRATEGY_DEFAULT_PROXY[strategy]
        sel_path = DATA / "benchmarks" / f"{key}_selection.json"
        slot_g = None
        if sel_path.exists():
            sel = json.loads(sel_path.read_text())
            # the lab opens on the engine's own comparison (R2-P1-8): Slot K's
            # series when it is held, else the reference public series
            picked = (sel.get("slot_k") or {}).get("selected")
            if not (picked and picked.get("comparison")):
                picked = sel.get("reference_comparison")
            if picked and picked.get("series_id") in PROXY_LIBRARY:
                proxy = picked["series_id"]
            slot_g = sel.get("slot_g")
        entry: dict = {"default_proxy": proxy}
        # Slot G is read by the lab from the benchmarks bundle (one copy)
        if key in daily:
            entry.update({"fund_series": daily[key]["series"], "granularity": "monthly"})
            if daily[key]["price_series"]:
                entry["price_series_warning"] = PRICE_SERIES_WARNING
        elif merged.get("fy_returns"):
            entry.update({"fy_returns": list(merged["fy_returns"]),
                          "fy_window": list(merged["fy_window"]),
                          "granularity": "annual"})
        elif merged.get("aatr_5yr"):
            entry.update({"aatr": merged["aatr_5yr"], "aatr_years": 5,
                          "fy_window": list(merged["fy_window"]),
                          "granularity": "annual"})
        elif merged.get("aatr"):
            entry.update({"aatr": merged["aatr"], "aatr_years": merged["aatr_years"],
                          "fy_window": list(merged["fy_window"]),
                          "granularity": "annual"})
        else:
            continue   # no recomputable input on record: the lab shows why
        out[key] = entry
    return out


def swap_matrix() -> dict:
    """Rubric v2 verdict for every (product x proxy-library) pair the lab
    can select, on the engine's menu or not. Every pair goes through the
    same scorer from typed descriptors. The verdict says whether the pair
    would be eligible (passes the strategy gate and the threshold) and
    whether it sits on the engine's menu for the product, so the lab grades
    any choice instead of declaring some choices ungradeable."""
    from tark_benchmark import (CANDIDATES, MIN_PRIMARY_SCORE, PRODUCT_PROFILES, STRATEGY_GATE_MIN,
                                eligible as _eligible, menu_for, score_candidate, x_of_n)
    out: dict = {}
    for key, prof in PRODUCT_PROFILES.items():
        if prof.get("held_kind") == "none":
            continue          # no return input, no lab, nothing to grade
        menu = menu_for(key)
        by_series: dict = {}
        for proxy in PROXY_LIBRARY:
            on_menu = next((c for c in menu if c.get("series") == proxy), None)
            cand = {**CANDIDATES[proxy], "id": proxy}
            if on_menu:
                cand["lane"] = on_menu["lane"]
            s = score_candidate(prof, cand)
            sm = s["criteria"]["strategy_match"]
            decoupled = bool(prof.get("price_nav_decoupled"))
            gate = sm >= STRATEGY_GATE_MIN
            independent = s["criteria"]["provider_independence"] == 2
            # one eligibility rule, the engine's own (R3-P2-2)
            eligible = _eligible(s, decoupled)
            if decoupled:
                verdict = ("not eligible: the fund's price is decoupled from its NAV, so no "
                           "proxy benchmarks the portfolio")
            elif not gate:
                verdict = f"not eligible: fails the strategy gate (strategy match {x_of_n(sm, 3)})"
            elif not independent:
                verdict = "not eligible: the provider is affiliated with the fund's adviser"
            elif s["score"] < MIN_PRIMARY_SCORE:
                verdict = (f"not eligible: {x_of_n(s['score'], s['max'])} is below the "
                           f"{x_of_n(MIN_PRIMARY_SCORE, s['max'])} threshold")
            else:
                verdict = (f"eligible under the {RUBRIC_LABEL}: {x_of_n(s['score'], s['max'])} passes the "
                           "strategy gate and the threshold")
            by_series[proxy] = {"score": s["score"], "max": s["max"],
                                "criteria": s["criteria"], "reasons": s["reasons"],
                                "candidate": cand["name"], "on_menu": bool(on_menu),
                                "eligible": eligible, "verdict": verdict}
        out[key] = by_series
    return out


def parse_verification_queue() -> dict:
    """Parse docs/verification_queue.md into an ordered queue of (product,
    cell) refs plus live verified counts from the record itself. Each ref
    carries the tier it sits under ("### Tier N <title>" headings; rows
    outside a tier heading carry tier null) and the tier titles ship
    verbatim so the surface repeats the document's words."""
    qp = BASE / "docs" / "verification_queue.md"
    queue: list[dict] = []
    tiers: dict[str, str] = {}
    tier = None
    seen = set()

    def add(product: str, cell: str) -> None:
        if product in product_keys() and (product, cell) not in seen:
            seen.add((product, cell))
            queue.append({"product": product, "cell": cell, "tier": tier})

    if qp.exists():
        for line in qp.read_text().splitlines():
            s = line.strip()
            th = re.match(r"#{2,3}\s+Tier\s+(\d+)\s*[—:-]\s*(.+)$", s)
            if th:
                tier = int(th.group(1))
                tiers[str(tier)] = th.group(2).strip()
                continue
            if s.startswith("#"):
                tier = None
                continue
            m = re.match(r"-\s+([a-z_]+)\s+(\d+\.\d+)\s+—", s)
            if m:
                add(m.group(1), m.group(2))
            else:
                for mm in re.finditer(
                        r"([a-z_]+)\s+(\d+\.\d+)(?=\s*[/—-])", s):
                    add(mm.group(1), mm.group(2))
    verified = {k: sum(1 for c in load_product(k)["cells"].values()
                       if str(c.get("status", "")).startswith("verified"))
                for k in product_keys()}
    verifiable = {k: sum(1 for c in load_product(k)["cells"].values()
                         if status_kind(str(c.get("status", ""))) in
                         ("extracted", "verified"))
                  for k in product_keys()}
    return {"queue": queue, "tiers": tiers, "verified": verified,
            "verifiable": verifiable, "source": "docs/verification_queue.md"}


def census_chunk() -> str:
    """site/census.data.js — the lazy T1 universe chunk. Compact keys, every
    field keeps its {source, ref, as_of} provenance (C3). Budget: <=500KB."""
    census = json.loads((DATA / "census" / "census.json").read_text())
    uni = json.loads((DATA / "census" / "universe.json").read_text())

    def slim(rec: dict) -> dict:
        e: dict = {"cik": rec["cik"],
                   "nm": (rec.get("entity_name_current", {}).get("value")
                          or rec["name"]),
                   "cls": rec["wrapper_class"], "sig": rec["all_signals"],
                   "ev": rec["detection_evidence"]}
        if rec.get("listed_common"):
            e["lif"] = rec["listed_common"]        # exchange status of the common shares (P2-11)
        if (rec.get("listed") or {}).get("value") is None and rec.get("listed"):
            e["lsig"] = rec["listed"]              # the raw signal, null with its reason
        ex = (rec.get("exchanges", {}) or {}).get("value") or []
        if ex:
            e["ex"] = [x for x in ex if x and x.upper() != "OTC"]
        if (rec.get("tickers", {}) or {}).get("value"):
            e["tk"] = rec["tickers"]
        for src, dst in (("first_filing", "ff"), ("latest_annual", "la"),
                         ("filing_summary", "fs"), ("total_assets", "ta"),
                         ("nav_per_share_structured", "nav"),
                         ("interval_crosscheck", "ic"),
                         ("entity_name_current", "enc")):
            if src in rec:
                e[dst] = rec[src]
        if "fs" in e and isinstance(e["fs"].get("value"), dict):
            top = sorted(e["fs"]["value"].items(), key=lambda kv: -kv[1])[:6]
            e["fs"] = {**e["fs"], "value": dict(top)}
        nc = rec.get("ncen")
        if nc:
            ref = nc["investment_company_type"]["ref"]
            as_of = nc["investment_company_type"]["as_of"]
            val = {"ict": nc["investment_company_type"]["value"],
                   "auditor": nc["auditor"]["value"],
                   "nav_err": nc["nav_error_corrected"]["value"],
                   "oq": nc["opinion_qualified"]["value"]}
            if "primary_fund" in nc:
                pfv = dict(nc["primary_fund"]["value"])
                pfv["advisers"] = (pfv.get("advisers") or [])[:3]
                val["pf"] = pfv
            e["nc"] = {"value": val, "source": "ncen", "ref": ref,
                       "as_of": as_of}
        if (rec.get("tender_activity", {}) or {}).get("value"):
            e["toi"] = rec["tender_activity"]["value"]
        hint = (rec.get("name_hint", {}) or {}).get("value") or []
        if hint:
            e["hint"] = hint
        if rec["promotion"]["status"] != "none":
            e["promo"] = rec["promotion"]["product_key"]
        return e

    # ---- 3,599 entities cannot fit one <=500KB chunk with provenance, so
    # the census ships in three honest pieces:
    #   census.data.js       light INDEX (screener fields only), <=500KB hard
    #   census/d/<k>.json    64 detail shards - the full slim records with
    #                        per-field provenance, fetched on interaction
    #   census/search.json   auditor/adviser sidecar, fetched only when a
    #                        text filter is used (never in the URL)
    CLS_CODE = {"bdc": "b", "interval_23c3": "i", "tender_cef": "t",
                "nontraded_reit": "r", "listed_cef": "l",
                "unlisted_cef_other": "u", "nontraded_34act_other": "o"}
    N_SHARDS = 64
    hints_all = sorted({h for r in census["entities"].values()
                        for h in ((r.get("name_hint", {}) or {})
                                  .get("value") or [])})
    hint_bit = {h: 1 << i for i, h in enumerate(hints_all)}

    ddir = SITE / "census" / "d"
    ddir.mkdir(parents=True, exist_ok=True)
    shards: dict[int, dict] = {i: {} for i in range(N_SHARDS)}
    index: dict[str, list] = {}
    search: dict[str, str] = {}
    for cik, rec in census["entities"].items():
        s = slim(rec)
        shards[int(cik) % N_SHARDS][cik] = s
        nc = rec.get("ncen")
        flags = 0
        if (rec.get("listed_common", {}) or {}).get("value") is True:
            flags |= 1
        if nc:
            flags |= 2
            pf = (nc.get("primary_fund", {}) or {}).get("value") or {}
            if pf.get("is_interval") == "Y":
                flags |= 4
            icx = (rec.get("interval_crosscheck", {}) or {}).get("value") or {}
            if icx.get("agreement"):
                flags |= 8
        if rec["promotion"]["status"] != "none":
            flags |= 16
        if nc or "total_assets" in rec or "latest_annual" in rec:
            flags |= 32
        ta = (rec.get("total_assets", {}) or {}).get("value") or {}
        la = (rec.get("latest_annual", {}) or {}).get("value") or {}
        toi = (rec.get("tender_activity", {}) or {}).get("value") or {}
        hm = 0
        for h in (rec.get("name_hint", {}) or {}).get("value") or []:
            hm |= hint_bit[h]
        row = [s["nm"], CLS_CODE[rec["wrapper_class"]], flags,
               ta.get("value") or 0, la.get("date") or "",
               toi.get("count") or 0, toi.get("last") or "", hm,
               rec["promotion"].get("product_key") or ""]
        index[cik] = row
        if nc:
            terms = [nc["auditor"]["value"] or ""]
            pf = (nc.get("primary_fund", {}) or {}).get("value") or {}
            terms += pf.get("advisers") or []
            joined = " | ".join(t for t in terms if t).lower()
            if joined:
                search[cik] = joined

    for i, sh in shards.items():
        (ddir / f"{i}.json").write_text(json.dumps(sh, separators=(",", ":")))
    (SITE / "census" / "search.json").write_text(
        json.dumps(search, separators=(",", ":")))

    # "what" and "tiers" stay in data/census/census.json as file-level
    # documentation; no view reads them, so they do not ship
    doc = {
        "as_of": census["as_of"],
        "counts_by_class": census["counts_by_class"],
        "total": census["total"],
        "dark_universe": uni["dark_universe"],
        "method_notes": uni["method_notes"],
        "cls_codes": {v: k for k, v in CLS_CODE.items()},
        "hints": hints_all,
        "shards": N_SHARDS,
        "row_fields": ["nm", "cls_code", "flags(1=listed common,2=ncen,4=interval-"
                       "self,8=crosscheck-agree,16=evaluated,32=structured-"
                       "facts)", "assets_usd", "latest_annual_date",
                       "tender_count", "tender_last", "hint_mask",
                       "promo_key"],
        "entities": index,
    }
    payload = json.dumps(doc, separators=(",", ":"))
    if len(payload) > 500_000:
        raise SystemExit(f"census chunk {len(payload):,}B exceeds the 500KB "
                         "lazy-chunk budget. Trim the transform, do not "
                         "ship a bloated first-class page.")
    return payload


def main() -> None:
    plans_raw = {k: load_plan(k) for k in plan_keys()}
    # forbidden tokens (sponsor, plan name, EIN, ack id) come from ONE module
    # shared with every test suite: src/tark_anon.py
    sponsor_names = set(forbidden_tokens())

    plans_pub = {}
    for k, p in plans_raw.items():
        # identity never ships, and the internal anonymization rule string is
        # not a surface sentence (R2-P0-3)
        pub = {kk: vv for kk, vv in p.items() if kk not in ("identity_private", "anonymization_rule")}
        # cell 3.7 for this plan, one sentence shared with the memo (R3-P2-11)
        pub["demand_sentence"] = plan_demand_sentence(p)
        plans_pub[k] = pub

    benchmarks = {}
    for f in sorted((DATA / "benchmarks").glob("*_selection.json")):
        sel = json.loads(f.read_text())
        # the bundle copy drops what no view reads (the composite's per-period
        # rows duplicate the table, the per-member basis and kind maps are in
        # the record for the memo): the record file keeps everything
        g = sel.get("slot_g") or {}
        if g:
            g.pop("member_period_kind", None)
            g.pop("member_source", None)
            (g.get("composite") or {}).pop("rows", None)
            (g.get("composite") or {}).pop("periods", None)
            # the side-by-side table ships its column names once and each
            # row's values in that order (the record keeps the keyed form)
            if g.get("table"):
                cols = list(g["table"][0]["returns"].keys())
                g["columns"] = cols
                for r in g["table"]:
                    r["values"] = [r["returns"].get(c) for c in cols]
                    r.pop("returns", None)
                    r.pop("period_kind", None)
        # the rubric caption ships once (rubric_caption) and the per-criterion
        # integers are printed through the reasons, which every card carries
        sel.pop("rubric", None)
        # the lock's input list names series files: it stays in the record,
        # the card prints the recorded date and the record hash (R3-P2-19)
        sel.pop("inputs", None)
        sel.pop("threshold", None)
        sel.pop("reference_skipped", None)
        for x in [sel["slot_k"].get("selected")] + sel.get("rejected", []):
            if x:
                x.pop("criteria", None)
                x.pop("comparator_kind", None)
        benchmarks[f.stem.replace("_selection", "")] = sel

    liquidity = {}
    # what every match repeats verbatim rides the chunk once and is
    # re-attached to each match by main.js on load (tarkMergeLazy): the
    # wrapper facts are plan-independent (the same object under all four
    # plans) and the stress-assumption sentence is one constant. The
    # record's "reasons" list (structural_reasons + scenario_reasons
    # verbatim), the memo-only "layers" note, the filed_outflow block (its
    # rate and plan year ride plan_inputs, its words ride scenario_reasons)
    # and the fund_capacity basis note are not read by any view. None of
    # this changes a figure or a sentence a view prints.
    liquidity_shared = {"wrapper_facts": {}, "stress_assumptions": None}
    for f in sorted((DATA / "liquidity").glob("*__*_match.json")):
        mdoc = json.loads(f.read_text())
        for drop in ("reasons", "layers", "filed_outflow"):
            mdoc.pop(drop, None)
        wf = mdoc.pop("wrapper_facts")
        prev = liquidity_shared["wrapper_facts"].setdefault(mdoc["product"], wf)
        if prev != wf:
            raise SystemExit(f"{f.name}: wrapper facts differ across plans, the bundle cannot share them")
        sa = mdoc["stressed_scenario"].pop("assumptions", None)
        if liquidity_shared["stress_assumptions"] not in (None, sa):
            raise SystemExit(f"{f.name}: stress assumptions differ across matches")
        liquidity_shared["stress_assumptions"] = sa
        (mdoc.get("scenario", {}).get("fund_capacity") or {}).pop("basis", None)
        liquidity[f.stem.replace("_match", "")] = mdoc

    products = load_products()
    facts = {}
    for f in sorted((DATA / "facts").glob("*.json")):
        facts[f.stem] = json.loads(f.read_text())["facts"]
        # the evidence phrase is the gate's input, not a view's: it stays in
        # the record and off the first paint
        for fact in facts[f.stem].values():
            fact.pop("evidence_phrase", None)
    display = {}
    for k, p in products.items():
        fbc = facts_by_cell(facts.get(k, {}))
        display[k] = {cid: cell_display(c, cid, fbc.get(cid))
                      for cid, c in p["cells"].items()}
    rollups = {}
    for k, p in products.items():
        by = {}
        for n, label in FACTORS.items():
            cells = [c for cid, c in p["cells"].items()
                     if cid.split(".")[0] == n]
            kinds = [status_kind(str(c.get("status", "pending"))) for c in cells]
            # the factor's counts on the record's one arithmetic (R3-P2-8):
            # evidenced is T1 plus T2 plus T3, soft is partial plus fetched
            by[n] = {"label": label, "total": len(cells),
                     "evidenced": sum(kind in ("structured", "extracted", "verified")
                                      for kind in kinds),
                     "computed": kinds.count("computed"),
                     "soft": sum(kind in ("partial", "fetched") for kind in kinds),
                     "na": kinds.count("n/a")}
        rollups[k] = by

    ann_dir = DATA / "series_annual"
    series_annual = {}
    if ann_dir.exists():
        import csv as _csv
        for f in sorted(ann_dir.glob("*.csv")):
            with open(f, newline="") as fh:
                series_annual[f.stem] = list(_csv.DictReader(fh))
    monthly = {}
    mpath = DATA / "series_monthly" / "breit_nav.csv"
    if mpath.exists():
        import csv as _csv
        with open(mpath, newline="") as fh:
            monthly["breit_nav"] = [[r["date"], float(r["nav_per_share"])]
                                    for r in _csv.DictReader(fh)]

    metrics = json.loads((DATA / "analytics" / "metrics.json").read_text())
    supplement = json.loads((DATA / "analytics" / "supplement.json").read_text())

    # first paint ships element, value, status and verifier per cell. The
    # citation-drawer detail (source, section, quote, extractor) rides in the
    # lazy chunk as TARK_EVIDENCE and is merged into products on load.
    # the element label rides once per cell id in cell_labels, not per product
    FIRST_PAINT_FIELDS = ("value", "status", "verified_by")
    DETAIL_FIELDS = ("source", "section", "quote", "extracted_by")
    # repository paths inside the record render as reader labels (R2-P0-3)
    evidence_detail = {k: {cid: {f: display_path_free(c.get(f, "")) for f in DETAIL_FIELDS}
                           for cid, c in p["cells"].items()}
                       for k, p in products.items()}
    # the accession column and the resolved EDGAR filings per cell (P2-10)
    for k in products:
        acc_by_cell = {r["cell_id"]: r.get("accession", "") for r in load_evidence(k)}
        cp = DATA / "citations" / f"{k}.json"
        cits = json.loads(cp.read_text())["cells"] if cp.exists() else {}
        for cid, cell in evidence_detail[k].items():
            acc = acc_by_cell.get(cid, "")
            # the ledger's set pointer names the citations file, the drawer says it in words
            cell["accession"] = (f"{acc.split(',')[0]} filings, each linked under EDGAR"
                                 if acc.startswith("multiple (") else acc)
            edgar = []
            for ref in cits.get(cid, []):
                if ref["match"] in ("exact", "form_only"):
                    edgar.append({"form": ref.get("form", ""), "filing_date": ref.get("filing_date", ""),
                                  "accession": ref["accession"], "url": ref["url"]})
                elif ref["match"] in ("range", "set"):
                    edgar.extend({"form": ref.get("form", ""), "filing_date": f["filing_date"],
                                  "accession": f["accession"], "url": f["url"]} for f in ref["filings"])
            cell["edgar"] = edgar
    # R3-P0-2: the citation button must render on a fresh load of the
    # Screener and Compare, before the lazy chunk carries the drawer detail,
    # so the first paint names which cells have a source (ids only, one
    # short string per product, to stay under the bundle's size pin)
    cited_cells = {k: ",".join(cid for cid, c in p["cells"].items() if c.get("source"))
                   for k, p in products.items()}
    # the verifier rides the first paint only when a person has signed the
    # row (an empty string on 880 cells is 14 KB of nothing)
    products = {k: {**p, "cited": cited_cells[k],
                    "cells": {cid: {f: (display_path_free(c.get(f, "")) if f == "value" else c.get(f, ""))
                                    for f in FIRST_PAINT_FIELDS
                                    if not (f == "verified_by" and not c.get(f))}
                              for cid, c in p["cells"].items()}}
                for k, p in products.items()}
    _reg = json.loads((DATA / "registry.json").read_text())["products"]
    descriptors = {k: {a: _reg[k].get(a) for a in ("wrapper_type", "pricing_class",
                                                    "nav_cadence", "leverage_regime")}
                   for k in products}
    # the filed since-inception return beside the series figure, one sentence
    # per product where the fact is typed and the selected slot is a series
    # comparison (R3-P2-17d), the same sentence cells 1.8 and 5.5 carry
    reconciliation = {}
    for k, sel in benchmarks.items():
        f = (facts.get(k) or {}).get("filed_since_inception_return_pct") or {}
        comp = ((sel.get("slot_k") or {}).get("selected") or {}).get("comparison") or {}
        if f.get("value") is not None and comp.get("kind") == "series":
            reconciliation[k] = reconciliation_sentence(f["value"], f.get("note", ""), comp)
    bundle = {
        "generated": date.today().isoformat(),
        "facts": facts,
        "reconciliation": reconciliation,
        # the rule record once, the mapping basis once, per cell only what differs
        # advisor-stated inputs per plan and product (P2-6), inputs not evidence
        "advisor": advisor_entries(),
        "advisor_cells": list(ADVISOR_STATED_CELLS),
        "advisor_not_evidence": ADVISOR_NOT_EVIDENCE,
        # an evaluation service, when one is connected at build time (P2-5)
        "service_url": (os.environ.get("TARK_SERVICE_URL") or "").rstrip("/") or None,
        # the verbatim paragraphs (about 60 KB) ride the lazy chunk as
        # TARK_AUTHORITY and are merged back on load, so the first-paint
        # bundle carries the status, the hash and the note only
        "rule": {**RULE, "authority": {k: v for k, v in authority().items() if k != "paragraphs"},
                 "mapping_basis": rule_ref("1.1", authority())["basis"]},
        "rule_refs": {cid: {k: v for k, v in rule_ref(cid, authority()).items() if k != "basis"}
                      for cid in CELLS},
        "factors": FACTORS,
        "cell_registry": CELLS,
        "products": products,
        "descriptors": descriptors,   # typed comparability attributes per product (registry)
        "wrapper_labels": WRAPPER_LABEL,   # one vocabulary, shared with the memo (tark_display)
        "base_labels": BASE_LABEL,
        # internal keys never render bare (R2-P0-3): the JS prints these labels
        "strategy_labels": STRATEGY_LABEL,
        "lane_labels": LANE_LABEL,
        "candidate_short": CANDIDATE_SHORT,
        "rubric_label": RUBRIC_LABEL,
        "slot_labels": SLOT_LABELS,
        # one label per cell id: the bundle's product cells carry no element
        # string, the views read this map (55 entries instead of 880 copies)
        "cell_labels": dict(CELLS),
        "cell_display": display,
        "factor_rollups": rollups,
        "glossary": GLOSSARY,
        "taxonomy": coverage_totals(),   # live, per kind, never a frozen file
        "supplement": _path_free({k: supplement[k] for k in ("dxyz_premium",
                                                             "ssss_premium",
                                                             "breit_monthly_diagnostics")}),
        "series_annual": series_annual,
        "series_monthly": monthly,
        "evidence_counts": {k: evidence_counts(k) for k in load_products()},
        "plans": plans_pub,
        "plan_order": ["plan_tech_media"] + [k for k in sorted(plans_pub)
                                             if k != "plan_tech_media"],
        "benchmarks": benchmarks,
        "min_primary_score": MIN_PRIMARY_SCORE,
        "rubric_max": _RUBRIC_MAX,
        "strategy_gate_min": _STRATEGY_GATE_MIN,
        "tie_sentence": _TIE_SENTENCE,
        "by_descriptor_sentence": _BY_DESCRIPTOR_SENTENCE,
        # per-plan liquidity match artifacts ride the lazy series chunk —
        # only the Liquidity view reads them; merged by ensureSeries()
        "liquidity": None,
        # only the parts a view reads ship (the rest stays on disk for the
        # cell writer); a runtime check in test_frontend fails on unread keys
        "metrics": {"cclfx": {"full_history": metrics["cclfx"]["full_history"]}},
        "series_sources": series_sources(),
        "dxyz_nav": _path_free(_with_period_ends(json.loads(
            (DATA / "analytics" / "dxyz_nav_quarterly.json").read_text()))),
        # series payload is SPLIT into site/series.js (lazy-loaded by the
        # chart/lab views) to keep the first-paint bundle inside the perf
        # budget; window.TARK.series is merged in by ensureSeries()
        "series": None,
        "cohorts": {p.stem: _cohort_bundle(json.loads(p.read_text()))
                    for p in sorted((DATA / "cohorts").glob("*.json"))
                    if p.stem != "caveat_matrix"},
        "facts_meta": {p.stem: {k: json.loads(p.read_text())[k]
                                for k in ("cohort_id", "depth",
                                          "membership_rationale")}
                       for p in sorted((DATA / "facts").glob("*.json"))},
        "series_quarterly": {p.stem.replace("_nav", ""): [
            [r["date"], float(r["nav_per_share"])]
            for r in __import__("csv").DictReader(open(p, newline=""))]
            for p in sorted((DATA / "series_quarterly").glob("*_nav.csv"))
            if p.stem == "ssss_nav"},   # the premium-pattern panel reads ssss only
        "caveat_matrix": json.loads(
            (DATA / "cohorts" / "caveat_matrix.json").read_text()),
        "roster_decisions_md": (DATA / "roster_decisions.md").read_text(),
        "pme_profiles": pme_profiles(),
        "daily_series": daily_series_map(),
        "proxy_library": PROXY_LIBRARY,
        "swap_matrix": None,      # lab matrix, merged from the lazy chunk (TARK_LAB)
        "verification_queue": parse_verification_queue(),
        "crosscheck": crosscheck_summary(),
        "memos": None,            # every plan x product memo, generated below
    }
    # the memos are generated by the build, never copied from a stale folder
    memo_dir = SITE / "memos"
    memo_paths = write_all(memo_dir)
    bundle["memos"] = sorted(m.stem.replace("_decision_memo", "") for m in memo_paths)
    # committee packets (P2-9), one per plan and product, same folder, same screen
    packet_paths = write_all_packets(memo_dir)
    bundle["packets"] = sorted(m.stem.replace("_committee_packet", "") for m in packet_paths)
    memo_paths = memo_paths + packet_paths

    series_payload = json.dumps({k: compact_series(v) for k, v in {
        "dxyz_daily": [[d, round(v, 4)] for d, v in load_series("dxyz", "close")],
        "cclfx": daily_series("cclfx"),
        "pflex": daily_series("pflex"),
        "arkvx": daily_series("arkvx"),
        "cadux": daily_series("cadux"),
        "nslr_daily": [[d, round(v, 4)] for d, v in load_series("nslr", "close")],
        "bkln": daily_series("bkln"),
        "psp": daily_series("psp"),
        "urth": daily_series("urth"),
        "spy": daily_series("spy"),
        "vnq": daily_series("vnq"),
    }.items()}, separators=(",", ":"))

    census_payload = census_chunk()
    payload = json.dumps(bundle, separators=(",", ":"))
    lab_payload = json.dumps(swap_matrix(), separators=(",", ":"))
    evidence_payload = json.dumps(evidence_detail, separators=(",", ":"))
    low = (payload + series_payload + census_payload + lab_payload + evidence_payload).lower()
    leaked = sorted(n for n in sponsor_names if n in low)
    if leaked:
        raise SystemExit(f"ANONYMIZATION FAILURE: sponsor token(s) {leaked} "
                         f"would enter site/data.js. Build refused.")
    # the memos ship from site/memos/: screen their text with the same list
    for m in sorted(memo_paths):
        bad = leaks(docx_text(m))
        if bad:
            raise SystemExit(f"ANONYMIZATION FAILURE: token(s) {bad} in "
                             f"{m.name}. Build refused.")

    SITE.mkdir(exist_ok=True)
    (SITE / "data.js").write_text("window.TARK = " + payload + ";\n")
    (SITE / "series.js").write_text(
        "window.TARK_SERIES = " + series_payload + ";\n"
        + "window.TARK_LIQ = "
        + json.dumps(liquidity, separators=(",", ":")) + ";\n"
        + "window.TARK_LAB = " + lab_payload + ";\n"
        + "window.TARK_EVIDENCE = " + evidence_payload + ";\n"
        # last, so the gates that read the chunk lines by position keep theirs
        + "window.TARK_LIQ_SHARED = "
        + json.dumps(liquidity_shared, separators=(",", ":")) + ";\n"
        + "window.TARK_AUTHORITY = "
        + json.dumps(authority().get("paragraphs") or {}, separators=(",", ":")) + ";\n")
    (SITE / "census.data.js").write_text("window.TARK_CENSUS = "
                                         + census_payload + ";\n")

    print(f"site/data.js written ({len(payload):,} bytes), census chunk "
          f"{len(census_payload):,} bytes, {len(bundle['memos'])} memos and "
          f"{len(bundle['packets'])} packets generated, sponsor tokens screened: {len(sponsor_names)}")


if __name__ == "__main__":
    main()

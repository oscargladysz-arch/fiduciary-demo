"""
Period returns per product, one basis each, aligned or refused (rule 14)
=========================================================================
Every peer comparison (Slot G, decision 7.1) and every cohort composite
reads member returns from this module, so one cohort has one member table
(audit round 2 item 20). A member's returns come from the one basis the
registry names for it (`held_returns.kind`, decision 7.21):

- a daily series: calendar years from the adjusted close, complete years
  only (an observation in the last week of December on both ends);
- filed fiscal-year returns whose year ends 12-31: calendar years;
- filed fiscal-year returns ending in another month: fiscal years, keyed
  by their end date, never averaged with calendar years;
- anything else (a single annualized figure, no returns): no periods.

A composite exists only over periods every peer reports, with at least
MIN_PEERS peers, all on the same period kind with identical start and end
dates. Otherwise it is refused with the reason, and the side-by-side table
still prints every member's periods with n per period.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from tark_data import DATA, load_series

MIN_PEERS = 3
_STUB = re.compile(r"stub|not annualized|commencement|partial", re.I)
YAHOO_SOURCE = "Yahoo adjusted close, approximates NAV total return"
MARKET_SOURCE = "Yahoo adjusted close, a market price with distributions reinvested, not NAV"
FILED_CY_SOURCE = "filed calendar-year returns (December fiscal year)"
FILED_FY_SOURCE = "filed fiscal-year returns"


def _registry() -> dict:
    return json.loads((DATA / "registry.json").read_text())["products"]


def _fy_end_month(fy_end: str) -> str:
    return fy_end[5:7]


def calendar_years_from_series(series: list[tuple[str, float]]) -> dict[str, dict]:
    """{'YYYY-12-31': {start, end, return, label}} for every complete
    calendar year: the last observation of the year over the last
    observation of the prior year, both dated on or after the 24th of
    December so a series that starts or ends mid-year contributes no
    partial year."""
    last: dict[str, tuple[str, float]] = {}
    for d, v in series:
        last[d[:4]] = (d, v)
    out: dict[str, dict] = {}
    for y in sorted(last):
        prev = str(int(y) - 1)
        if prev not in last:
            continue
        d0, v0 = last[prev]
        d1, v1 = last[y]
        if d0 < f"{prev}-12-24" or d1 < f"{y}-12-24":
            continue
        out[f"{y}-12-31"] = {"start": f"{prev}-12-31", "end": f"{y}-12-31",
                             "anchor_start": d0, "anchor_end": d1,
                             "return": v1 / v0 - 1, "label": y}
    return out


def filed_years(key: str) -> list[dict]:
    """Whole fiscal years from data/series_annual/<key>.csv (stubs and
    partial periods excluded), each with its end date and return."""
    p = DATA / "series_annual" / f"{key}.csv"
    if not p.exists():
        return []
    out = []
    with open(p, newline="") as fh:
        for r in csv.DictReader(fh):
            if not r.get("total_return_pct") or _STUB.search(r.get("note") or ""):
                continue
            out.append({"fy_end": r["fy_end"], "return": float(r["total_return_pct"]) / 100})
    return out


def member_period_returns(key: str, reg: dict | None = None) -> dict:
    """The member's period returns on its one basis. Returns
    {period_kind, basis, source, fy_end_month, periods: {id: {...}}}."""
    reg = reg or _registry()
    held = reg[key]["held_returns"]
    if held["kind"] == "series":
        series = load_series(held["series"], "adj_close")
        src = MARKET_SOURCE if reg[key].get("pricing_class") == "MARKET" else YAHOO_SOURCE
        return {"period_kind": "calendar_year", "basis": "series", "source": src,
                "fy_end_month": "12", "periods": calendar_years_from_series(series)}
    if held["kind"] == "fy_returns":
        rows = filed_years(key)
        if not rows:
            return {"period_kind": "none", "basis": "fy_returns", "source": FILED_FY_SOURCE,
                    "fy_end_month": None, "periods": {}}
        months = {_fy_end_month(r["fy_end"]) for r in rows}
        month = sorted(months)[-1]
        if months == {"12"}:
            periods = {r["fy_end"]: {"start": f"{int(r['fy_end'][:4]) - 1}-12-31", "end": r["fy_end"],
                                     "return": r["return"], "label": r["fy_end"][:4]} for r in rows}
            return {"period_kind": "calendar_year", "basis": "fy_returns", "source": FILED_CY_SOURCE,
                    "fy_end_month": "12", "periods": periods}
        periods = {r["fy_end"]: {"start": f"{int(r['fy_end'][:4]) - 1}{r['fy_end'][4:]}", "end": r["fy_end"],
                                 "return": r["return"],
                                 "label": f"FY{r['fy_end'][:4]} (year to {r['fy_end']})"}
                   for r in rows if _fy_end_month(r["fy_end"]) == month}
        return {"period_kind": "fiscal_year", "basis": "fy_returns", "source": FILED_FY_SOURCE,
                "fy_end_month": month, "periods": periods}
    return {"period_kind": "none", "basis": held["kind"], "source": None,
            "fy_end_month": None, "periods": {}}


def period_table(members: list[str], reg: dict | None = None) -> dict:
    """Every period any member reports, with each member's return (percent,
    None where absent) and n. Rows are ordered by period end."""
    reg = reg or _registry()
    per = {m: member_period_returns(m, reg) for m in members}
    ids = sorted({pid for m in per.values() for pid in m["periods"]})
    rows = []
    for pid in ids:
        rets = {m: (round(per[m]["periods"][pid]["return"] * 100, 2) if pid in per[m]["periods"] else None)
                for m in members}
        have = [m for m in members if rets[m] is not None]
        kinds = {per[m]["period_kind"] for m in have}
        rows.append({"period": pid, "label": next(per[m]["periods"][pid]["label"] for m in have),
                     "period_kind": kinds.pop() if len(kinds) == 1 else "mixed",
                     "returns": rets, "n": len(have)})
    return {"members": members, "per_member": per, "rows": rows}


def _pct(x: float) -> float:
    return round(x * 100, 2)


def aligned_composite(subject: str, peers: list[str], reg: dict | None = None,
                      fund_short: dict[str, str] | None = None) -> dict:
    """The subject against the equal-weight composite of its peers over the
    consecutive common periods, or a refusal with the reason. Never a PME:
    the statistic is a relative wealth ratio and an annualized excess
    return (rule 12)."""
    reg = reg or _registry()
    short = fund_short or {}
    name = lambda k: short.get(k, k)  # noqa: E731
    tbl = period_table(peers + [subject], reg)
    per = tbl["per_member"]
    base = {"members": peers, "n_peers": len(peers), "table": tbl["rows"],
            "member_source": {m: per[m]["source"] for m in peers + [subject]},
            "member_period_kind": {m: per[m]["period_kind"] for m in peers + [subject]},
            "weighting": "equal-weight across peers, only over periods every peer reports",
            "statistic": "relative wealth ratio vs peer composite",
            "not_pme_note": ("Not a public market equivalent: the peer composite is appraisal-based, "
                             "constructed by the evaluator and cannot be bought."),
            }
    if len(peers) < MIN_PEERS:
        return {**base, "status": "refused",
                "reason": (f"fewer than {MIN_PEERS} peers remain after leaving {name(subject)} out "
                           f"({len(peers)}: {', '.join(name(m) for m in peers)})")}
    classes = {reg[m]["pricing_class"] for m in peers + [subject]}
    if len(classes) > 1:
        return {**base, "status": "refused",
                "reason": ("members price on different bases (market price and appraisal NAV). An "
                           "equal-weight composite would average premium and discount dynamics "
                           "against appraisal NAVs, so it is refused, not fudged")}
    kinds = {m: per[m]["period_kind"] for m in peers + [subject]}
    if "none" in kinds.values():
        missing = [name(m) for m, k in kinds.items() if k == "none"]
        return {**base, "status": "refused",
                "reason": f"no period returns on record for {', '.join(missing)}"}
    months = {m: per[m]["fy_end_month"] for m in peers + [subject]}

    def basis_words(m: str) -> str:
        return ("calendar years" if kinds[m] == "calendar_year"
                else f"fiscal years to month {months[m]}")
    # R3-P2-5: the peers that report on the subject's own period basis
    # (same kind, same year-end month) form the composite. A peer on another
    # basis is excluded by name with the reason, and stays in the table.
    all_peers = list(peers)
    aligned = [m for m in peers if kinds[m] == kinds[subject] and months[m] == months[subject]]
    excluded = [{"member": name(m), "reason": (f"{name(m)} reports {basis_words(m)}. {name(subject)} and the "
                                                f"aligned peers report {basis_words(subject)}, so it is excluded "
                                                "from the composite and stays in the side-by-side table")}
                for m in peers if m not in aligned]
    base["excluded"] = excluded
    if len(aligned) < MIN_PEERS:
        others = ", ".join(f"{name(m)} ({basis_words(m)})" for m in peers if m not in aligned)
        return {**base, "status": "refused",
                "reason": (f"fewer than {MIN_PEERS} peers share {name(subject)}'s period basis "
                           f"({basis_words(subject)}): {len(aligned)} aligned"
                           + (f", the rest report on another basis ({others})" if others else "")
                           + ". A composite needs identical start and end dates for every member")}
    peers = aligned
    base["members"] = peers
    base["n_peers"] = len(peers)
    # common periods: every aligned peer reports it
    common = [pid for pid in sorted(per[peers[0]]["periods"]) if all(pid in per[m]["periods"] for m in peers)]
    run = [pid for pid in common if pid in per[subject]["periods"]]
    # the longest run of consecutive periods, latest first
    def consecutive(a: str, b: str) -> bool:
        return int(b[:4]) - int(a[:4]) == 1 and a[4:] == b[4:]
    best: list[str] = []
    cur: list[str] = []
    for pid in run:
        if cur and not consecutive(cur[-1], pid):
            cur = []
        cur.append(pid)
        if len(cur) >= len(best):
            best = list(cur)
    if not best:
        return {**base, "status": "refused",
                "reason": (f"no period is reported by {name(subject)} and every peer at once")}
    fund_rets = [per[subject]["periods"][pid]["return"] for pid in best]
    comp_rets = [sum(per[m]["periods"][pid]["return"] for m in peers) / len(peers) for pid in best]
    fg = 1.0
    for r in fund_rets:
        fg *= 1 + r
    cg = 1.0
    for r in comp_rets:
        cg *= 1 + r
    yrs = len(best)
    ratio = fg / cg
    kind = kinds[subject]
    unit = "calendar-year" if kind == "calendar_year" else "fiscal-year"
    labels = [per[subject]["periods"][pid]["label"] for pid in best]
    window = (f"{labels[0]} to {labels[-1]}" if kind == "calendar_year"
              else f"{labels[0].split(' ')[0]} to {labels[-1].split(' ')[0]} (years to {best[0][5:]})")
    align = (f"{yrs} {unit} period(s) with identical start and end dates for every member "
             f"({per[subject]['periods'][best[0]]['start']} to {per[subject]['periods'][best[-1]]['end']}), "
             f"n={len(peers)} peers in every period. Member return sources: "
             + "; ".join(f"{name(m)}: {per[m]['source']}" for m in peers)
             + (". Excluded from the composite: " + " ".join(e["reason"] for e in excluded) if excluded else "")
             + (f". {len(all_peers) - len(peers)} of {len(all_peers)} peers excluded" if excluded else ""))
    rows = [{"period": pid, "label": per[subject]["periods"][pid]["label"], "n": len(peers),
             "composite_return_pct": _pct(c), "fund_return_pct": _pct(f),
             "members": {name(m): _pct(per[m]["periods"][pid]["return"]) for m in peers}}
            for pid, c, f in zip(best, comp_rets, fund_rets)]
    from tark_benchmark_common import low_confidence
    return {**base, "status": "computed", "reason": None,
            "period_kind": kind, "window": window, "periods": best, "rows": rows,
            "window_years": yrs, "n": len(peers),
            "fund_growth_x": round(fg, 4), "index_growth_x": round(cg, 4),
            "relative_wealth_ratio": round(ratio, 4),
            "excess_return_pct": round((ratio ** (1 / yrs) - 1) * 100, 2),
            "fund_ann_pct": round((fg ** (1 / yrs) - 1) * 100, 2),
            "index_ann_pct": round((cg ** (1 / yrs) - 1) * 100, 2),
            "fund_return_source": per[subject]["source"],
            "alignment_note": align,
            "low_confidence": low_confidence(yrs, unit)}

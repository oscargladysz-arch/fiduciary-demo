"""
Tark data layer (M0)
====================
Single source of truth for the six-factor cell registry and all data access.
Every later module (M2 analytics, M3 benchmark engine, M4 UI, M5 memo
generator) imports from here and ONLY from here — no module re-declares
cell IDs, statuses, or file paths.

Data contract on disk:
    data/products/<key>.json           one file per product, all 54 cells present
    data/evidence/<key>_evidence.csv   same cells, same statuses (citations)
    data/plans/<key>.json              reference plans (real 5500 economics,
                                       anonymized display labels)
    data/series/<ticker>.csv           date,close daily series + series_manifest.json
    data/manifest.csv                  every EDGAR pull, reproducible

Usage:
    from tark_data import load_products, load_anchor_plan, cells_by_factor
"""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
# TARK_DATA_DIR lets the freshness gate run the whole producer chain into a
# scratch copy of the record and diff it against the committed artifacts.
DATA = Path(os.environ.get("TARK_DATA_DIR") or (BASE / "data")).resolve()


def record_as_of() -> str:
    """The record's as-of date, stamped on every machine-written artifact
    (memo date, computed cells, supplement). TARK_AS_OF overrides
    data/as_of.json. Never the wall clock: producers must be reproducible so
    the freshness gate can compare a fresh run against the committed files."""
    v = os.environ.get("TARK_AS_OF", "").strip()
    if v:
        return v
    p = DATA / "as_of.json"
    if p.exists():
        return json.loads(p.read_text())["record_as_of"]
    raise SystemExit("record as-of date missing: set TARK_AS_OF or add "
                     "data/as_of.json {\"record_as_of\": \"YYYY-MM-DD\"}")


def sec_user_agent() -> str:
    """Identified User-Agent for SEC and other fetchers. The contact comes
    from the environment, never from source. SEC fair-access policy requires
    a name and email, so the fetchers refuse to run without one."""
    contact = os.environ.get("TARK_SEC_CONTACT", "").strip()
    if not contact:
        raise SystemExit("TARK_SEC_CONTACT is not set. Export it as "
                         "'Your Name your@email' (SEC fair-access policy "
                         "requires an identified User-Agent).")
    return f"Tark research tool ({contact})"

# ---------------------------------------------------------------- registry
FACTORS = {
    "1": "Performance",
    "2": "Fees",
    "3": "Liquidity",
    "4": "Valuation",
    "5": "Performance Benchmarks",
    "6": "Complexity",
}

# The one rule record every surface reads. Identifiers are those recorded
# with their sources in docs/DECISIONS_2026-09.md (section 0). No sentence of
# the regulation is paraphrased here: verbatim paragraphs come only from
# data/authority/, written by src/fetch_authority.py from the Federal
# Register text, and every surface says when that file is absent.
RULE = {
    "title": "Fiduciary Duties in Selecting Designated Investment Alternatives",
    "issuer": "U.S. Department of Labor, Employee Benefits Security Administration",
    "citation": "91 FR 16088 (Mar. 31, 2026)",
    "rin": "RIN 1210-AC38",
    "section": "proposed 29 CFR 2550.404a-6",
    "paragraphs": "(g) to (l)",
    "fr_document": "2026-06178",
    "fr_url": ("https://www.federalregister.gov/documents/2026/03/31/2026-06178/"
               "fiduciary-duties-in-selecting-designated-investment-alternatives"),
    "docket": "EBSA-2026-0166",
    "docket_url": "https://www.regulations.gov/docket/EBSA-2026-0166",
}
RULE_CITATION = f"{RULE['title']}, {RULE['citation']}, {RULE['rin']}, {RULE['section']}"
# factor n maps to paragraph letter per the 2026-09-03 audit's check of the
# Federal Register text (audit section 3, item on rule mapping)
FACTOR_PARAS = {"1": "g", "2": "h", "3": "i", "4": "j", "5": "k", "6": "l"}
# cells the adopting fiduciary completes for its own plan rather than the
# record extracting them from filings
ADVISOR_COMPLETED = ("6.6", "6.8")
MAPPING_BASIS = ("factor order per the 2026-09-03 audit's check of 91 FR 16088, "
                 "paragraphs (g) to (l) of proposed 29 CFR 2550.404a-6")


def parse_authority(text: str) -> dict[str, list[str]]:
    """{letter: [verbatim paragraphs]} from the markdown src/fetch_authority.py
    writes: '## (g)' headings followed by '> ' blockquote lines."""
    out: dict[str, list[str]] = {}
    letter = None
    for line in text.splitlines():
        m = re.match(r"^## \(([a-z])\)\s*$", line)
        if m:
            letter = m.group(1)
            out[letter] = []
            continue
        if letter and line.startswith("> ") and line[2:].strip():
            out[letter].append(line[2:].strip())
    return out


def authority() -> dict:
    """The verbatim regulatory text when fetched into this build, else the
    not-fetched state. Never text from memory."""
    d = DATA / "authority"
    files = sorted(d.glob("*_proposed.md")) if d.exists() else []
    if not files:
        return {"status": "not fetched",
                "note": ("verbatim regulatory text not yet fetched into this build: run "
                         "python src/fetch_authority.py on a machine that reaches "
                         "federalregister.gov"),
                "file": None, "paragraphs": None}
    paras = parse_authority(files[0].read_text())
    return {"status": "fetched", "note": f"verbatim Federal Register text in {files[0].relative_to(BASE)}",
            "file": str(files[0].relative_to(BASE)), "paragraphs": paras}


def rule_ref(cid: str, auth: dict | None = None) -> dict:
    """Where a cell sits in the rule: paragraph letter, the basis for that
    mapping, and whether the adopting fiduciary completes the cell."""
    auth = auth or authority()
    letter = FACTOR_PARAS[cid.split(".")[0]]
    verbatim = auth["status"] == "fetched"
    return {"para": f"({letter})",
            "basis": MAPPING_BASIS + (", verbatim text in " + auth["file"] if verbatim
                                      else ", verbatim text not in this build"),
            "verbatim": verbatim,
            "advisor_completed": cid in ADVISOR_COMPLETED}


CELLS = {
    "1.1": "Net total return series", "1.2": "Trailing & calendar-year returns",
    "1.3": "Gross vs net spread", "1.4": "Distribution history & composition",
    "1.5": "Underlying sleeve/GP performance", "1.6": "Volatility & max drawdown",
    "1.7": "De-smoothed volatility", "1.8": "Risk-adjusted metrics (PME etc)",
    "1.9": "Stress-window performance", "1.10": "Market price & premium/discount",
    "1.11": "Track record & manager tenure",
    "2.1": "Management fee (rate AND base)", "2.2": "Incentive fee terms",
    "2.3": "Total expense ratio & waivers", "2.4": "AFFE",
    "2.5": "Underlying GP economics", "2.6": "Loads & servicing fees",
    "2.7": "Early repurchase fee", "2.8": "CIT fee schedule",
    "2.9": "Fee peer percentile", "2.10": "Value justification",
    "3.1": "Wrapper liquidity terms", "3.2": "Repurchase mechanics",
    "3.3": "Repurchase history", "3.4": "Portfolio liquidity profile",
    "3.5": "TDF/CIT liquidity sleeve", "3.6": "Fund leverage & facilities",
    "3.7": "Plan participant liquidity demand", "3.8": "Redemption stress test",
    "3.9": "Product-to-plan liquidity match",
    "4.1": "Valuation policy & NAV frequency", "4.2": "Fair-value hierarchy (L1/2/3)",
    "4.3": "Independent valuation agent", "4.4": "Methodology by asset type",
    "4.5": "Auditor & opinion", "4.6": "NAV restatement history",
    "4.7": "Premium/discount check", "4.8": "Smoothing diagnostics",
    "4.9": "CIT unit valuation",
    "5.1": "Self-declared benchmark", "5.2": "Public index series",
    "5.3": "Alt asset-class indices", "5.4": "Peer universe & returns",
    "5.5": "PME / Direct Alpha inputs", "5.6": "Benchmark suitability memo",
    "5.7": "Case-law tracker",
    "6.1": "Structure map", "6.2": "Strategy & instrument complexity",
    "6.3": "Conflicts & affiliated transactions", "6.4": "Tax reporting (1099 vs K-1)",
    "6.5": "Service-provider web", "6.6": "Plan operational fit",
    "6.7": "Participant communicability", "6.8": "Fiduciary capacity self-assessment",
}

# status vocabulary is prefix-based: the wild data legitimately contains
# refinements like "pending-verify" and "fetched-series, extraction pending"
STATUS_PREFIXES = ("pending", "partial", "extracted", "verified",
                   "structured", "computed", "fetched", "n/a")

SERIES_COLUMNS = ["date", "close", "adj_close"]

EVIDENCE_COLUMNS = [
    "cell_id", "element", "value", "source_doc", "source_section", "quote",
    "local_file", "date_pulled", "extracted_by", "verified_by", "status",
]


def factor_of(cell_id: str) -> str:
    """'3.4' -> 'Liquidity'"""
    return FACTORS[cell_id.split(".")[0]]


def status_kind(status: str) -> str:
    """Collapse a wild status string to its prefix kind, e.g. 'extracted'."""
    for p in STATUS_PREFIXES:
        if status.startswith(p):
            return p
    return "unknown"


# ---------------------------------------------------------------- loaders
def product_keys() -> list[str]:
    return sorted(p.stem for p in (DATA / "products").glob("*.json"))


def load_product(key: str) -> dict:
    return json.loads((DATA / "products" / f"{key}.json").read_text())


def load_products() -> dict[str, dict]:
    return {k: load_product(k) for k in product_keys()}


def get_cell(product: dict, cell_id: str) -> dict:
    return product["cells"][cell_id]


def cells_by_factor(product: dict) -> dict[str, list[tuple[str, dict]]]:
    """Factor label -> [(cell_id, cell), ...] in registry order."""
    out: dict[str, list[tuple[str, dict]]] = {v: [] for v in FACTORS.values()}
    for cid in CELLS:
        out[factor_of(cid)].append((cid, product["cells"][cid]))
    return out


ANCHOR_PLAN_KEY = "plan_tech_media"


def plan_keys() -> list[str]:
    return sorted(p.stem for p in (DATA / "plans").glob("*.json"))


def load_plan(key: str) -> dict:
    return json.loads((DATA / "plans" / f"{key}.json").read_text())


def load_plans() -> dict[str, dict]:
    return {k: load_plan(k) for k in plan_keys()}


def load_anchor_plan() -> dict:
    """Backward-compatible alias: the original anchor plan."""
    return load_plan(ANCHOR_PLAN_KEY)


def load_evidence(key: str) -> list[dict]:
    with open(DATA / "evidence" / f"{key}_evidence.csv", newline="") as fh:
        return list(csv.DictReader(fh))


def series_tickers() -> list[str]:
    return sorted(p.stem for p in (DATA / "series").glob("*.csv"))


def load_series(ticker: str, column: str = "adj_close") -> list[tuple[str, float]]:
    """[(iso_date, value), ...] ascending. column: 'adj_close' (total-return
    proxy, default) or 'close' (raw price/NAV)."""
    with open(DATA / "series" / f"{ticker}.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [(r["date"], float(r[column])) for r in rows]


def load_series_manifest() -> dict:
    return json.loads((DATA / "series" / "series_manifest.json").read_text())


def load_manifest() -> list[dict]:
    with open(DATA / "manifest.csv", newline="") as fh:
        return list(csv.DictReader(fh))


# ------------------------------------------------------------- validation
def validate_product(key: str) -> list[str]:
    """Return a list of error strings (empty = clean)."""
    errs: list[str] = []
    try:
        p = load_product(key)
    except Exception as e:  # noqa: BLE001 - report, don't crash the sweep
        return [f"{key}: cannot load JSON ({e})"]

    for req in ("product_key", "fund_name", "cik", "wrapper", "cells"):
        if req not in p:
            errs.append(f"{key}: missing top-level key '{req}'")
    if p.get("product_key") != key:
        errs.append(f"{key}: product_key mismatch ('{p.get('product_key')}')")
    # one type for the CIK everywhere: a digit string (the census keys its
    # entities by the same string, and a mixed int/str column breaks the
    # Streamlit roster table's Arrow conversion)
    cik = p.get("cik")
    if not (isinstance(cik, str) and cik.isdigit() and 1 <= len(cik) <= 10):
        errs.append(f"{key}: cik must be a string of digits, got {cik!r}")

    cells = p.get("cells", {})
    missing = sorted(set(CELLS) - set(cells))
    extra = sorted(set(cells) - set(CELLS))
    if missing:
        errs.append(f"{key}: missing cells {missing}")
    if extra:
        errs.append(f"{key}: unknown cells {extra}")

    for cid, cell in cells.items():
        if cid not in CELLS:
            continue
        if cell.get("element") != CELLS[cid]:
            errs.append(f"{key}:{cid}: element label drift ('{cell.get('element')}')")
        st = cell.get("status", "")
        if status_kind(st) == "unknown":
            errs.append(f"{key}:{cid}: unknown status '{st}'")
        if status_kind(st) in ("extracted", "verified", "computed",
                              "structured") and not cell.get("value"):
            errs.append(f"{key}:{cid}: status '{st}' but no value")
        if status_kind(st) in ("extracted", "verified", "computed",
                              "structured") and not cell.get("source"):
            errs.append(f"{key}:{cid}: status '{st}' but no source")
        if status_kind(st) in ("extracted", "verified", "computed",
                              "structured") and not str(cell.get("extracted_by", "")).strip():
            errs.append(f"{key}:{cid}: status '{st}' but empty extracted_by "
                        f"(provenance is part of the record)")

    # every data/ path a cell cites must resolve. Non-raw paths must exist in
    # the repo (hard error). data/raw/ is gitignored, so a raw path is checked
    # against data/manifest.csv local_path (a warning until P2-10 makes the
    # ledger complete). Paths may contain spaces (SEC primary documents such
    # as "SC TO-I_...") and may be directories.
    for cid, cell in cells.items():
        if cid not in CELLS:
            continue
        if status_kind(st) == "partial" and str(cell.get("value") or "").strip():
            if not str(cell.get("source") or "").strip():
                errs.append(f"{key}:{cid}: partial with a value but no source")
            if not str(cell.get("extracted_by") or "").strip():
                errs.append(f"{key}:{cid}: partial with a value but empty extracted_by")
        for field in ("value", "source", "section", "quote"):
            for pth in data_paths_in(str(cell.get(field) or "")):
                if pth.startswith("data/raw/"):
                    continue   # reported by data_path_warnings()
                if not (BASE / pth).exists():
                    errs.append(f"{key}:{cid}: {field} cites {pth}, which does "
                                f"not exist")

    # evidence CSV cross-check
    try:
        ev = load_evidence(key)
    except Exception as e:  # noqa: BLE001
        errs.append(f"{key}: cannot load evidence CSV ({e})")
        return errs
    if ev and list(ev[0].keys()) != EVIDENCE_COLUMNS:
        errs.append(f"{key}: evidence CSV columns differ from contract")
    ev_ids = [r["cell_id"] for r in ev]
    if sorted(ev_ids) != sorted(CELLS):
        errs.append(f"{key}: evidence CSV cell set differs from registry "
                    f"({len(ev_ids)} rows)")
    # the JSON cell and the CSV row are one record in two stores: every
    # field must agree, not only the status (33 extracted_by drifts shipped
    # before this check existed)
    FIELD_PAIRS = (("value", "value"), ("source", "source_doc"),
                   ("section", "source_section"), ("quote", "quote"),
                   ("extracted_by", "extracted_by"),
                   ("verified_by", "verified_by"))
    for r in ev:
        cid = r["cell_id"]
        if cid not in cells:
            continue
        c = cells[cid]
        if r["status"] != c.get("status"):
            errs.append(f"{key}:{cid}: status drift JSON='{c.get('status')}' "
                        f"CSV='{r['status']}'")
        for jf, cf in FIELD_PAIRS:
            if str(c.get(jf) or "").strip() != str(r.get(cf) or "").strip():
                errs.append(f"{key}:{cid}: {jf} differs between JSON and CSV")
    return errs


DATA_PATH_RE = re.compile(
    r"data/(?:[A-Za-z0-9_.\-]+/)*"                      # directories
    r"(?:[A-Za-z0-9_.\- ]*?\.(?:htm|html|csv|json|md|txt|pdf|xml)"  # a file
    r"|(?=[\s,;:)\]'\"]|$))")                             # or a bare directory


def data_paths_in(text: str) -> list[str]:
    """Every data/... path token in a prose or source string."""
    out = []
    for m in DATA_PATH_RE.finditer(text):
        tok = m.group(0).rstrip(".")
        if tok and tok != "data/":
            out.append(tok)
    return out


def data_path_warnings() -> list[str]:
    """Raw-filing citations that no manifest row covers. Warnings, not
    errors, until P2-10 completes the accession ledger."""
    man = {r["local_path"] for r in load_manifest()}
    dirs = {p.rsplit("/", 1)[0] + "/" for p in man}
    out = []
    for key in product_keys():
        for cid, cell in load_product(key)["cells"].items():
            for field in ("value", "source", "section", "quote"):
                for pth in data_paths_in(str(cell.get(field) or "")):
                    if not pth.startswith("data/raw/"):
                        continue
                    if pth in man or pth in dirs or any(pth.startswith(d) for d in dirs):
                        continue
                    out.append(f"{key}:{cid}: {field} cites {pth}, not in data/manifest.csv")
    return out


def validate_plan(key: str) -> list[str]:
    errs: list[str] = []
    try:
        a = load_plan(key)
    except Exception as e:  # noqa: BLE001
        return [f"{key}: cannot load ({e})"]
    for req in ("display_label", "identity_private", "participants",
                "financials", "derived", "source"):
        if req not in a:
            errs.append(f"{key}: missing '{req}'")
    fin, part, der = a.get("financials", {}), a.get("participants", {}), a.get("derived", {})
    net = fin.get("net_assets_eoy")
    bal = part.get("with_account_balances")
    if not (isinstance(net, (int, float)) and net > 0):
        errs.append(f"{key}: net_assets_eoy not a positive number")
    # integrity: recompute derived figures from primitives
    if net and bal:
        recomputed = round(net / bal)
        if abs(recomputed - (der.get("avg_balance_per_account") or 0)) > 1:
            errs.append(f"{key}: avg_balance drift (stored "
                        f"{der.get('avg_balance_per_account')}, recomputed {recomputed})")
    adm = fin.get("tot_admin_expenses")
    if net and adm:
        recomputed = round(adm / net * 100, 3)
        if abs(recomputed - (der.get("admin_expense_ratio_pct") or 0)) > 0.001:
            errs.append(f"{key}: admin_expense_ratio drift")
    # Schedule H fields (P1-18): present as records, null only with a reason,
    # a value only with a source
    sh = a.get("schedule_h")
    if not isinstance(sh, dict):
        errs.append(f"{key}: missing 'schedule_h' block")
    else:
        for fld in ("benefit_payments_2e", "participant_contributions_2a1b", "qdia_indicator"):
            rec = sh.get(fld)
            if not isinstance(rec, dict):
                errs.append(f"{key}: schedule_h.{fld} missing or not a record")
                continue
            if rec.get("value") is None and not rec.get("reason"):
                errs.append(f"{key}: schedule_h.{fld} is null without a reason")
            if rec.get("value") is not None and not rec.get("source"):
                errs.append(f"{key}: schedule_h.{fld} has a value without a source")
    return errs


def validate_series() -> list[str]:
    errs: list[str] = []
    try:
        man = load_series_manifest()
    except Exception as e:  # noqa: BLE001
        return [f"series: cannot load manifest ({e})"]
    declared = {m["ticker"].lower() for m in man.get("series", [])}
    on_disk = set(series_tickers())
    if declared != on_disk:
        errs.append(f"series: manifest/disk mismatch ({declared} vs {on_disk})")
    for t in on_disk:
        try:
            with open(DATA / "series" / f"{t}.csv", newline="") as fh:
                hdr = next(csv.reader(fh))
            if hdr != SERIES_COLUMNS:
                errs.append(f"series {t}: columns {hdr} != contract {SERIES_COLUMNS}")
                continue
            s_close = load_series(t, "close")
            s_adj = load_series(t, "adj_close")
        except Exception as e:  # noqa: BLE001
            errs.append(f"series {t}: cannot parse ({e})")
            continue
        if len(s_close) < 50:
            errs.append(f"series {t}: suspiciously short ({len(s_close)} rows)")
        dates = [d for d, _ in s_close]
        if dates != sorted(dates):
            errs.append(f"series {t}: dates not ascending")
        if any(c <= 0 for _, c in s_close) or any(a <= 0 for _, a in s_adj):
            errs.append(f"series {t}: non-positive values present")
    return errs


# ------------------------------------------------------------- coverage
COVERAGE_KINDS = ("structured", "extracted", "verified", "computed", "partial",
                  "fetched", "na", "pending")


def coverage_summary(key: str) -> dict:
    """The ONE coverage formula (coverage.py, build_site.py and app.py all
    call this). Counts per status kind, never one merged number: structured
    is T1, extracted is T2, verified is T3, computed is the pipeline's own
    output, partial and fetched are soft, n/a is documented-unavailable and
    stays in the denominator as its own segment. `resolvable` = cells that
    are not n/a; `resolved` = resolvable cells that carry content."""
    c = {k: 0 for k in COVERAGE_KINDS}
    for row in load_evidence(key):
        kind = status_kind(row["status"])
        kind = "na" if kind == "n/a" else kind
        c[kind if kind in c else "pending"] += 1
    total = sum(c.values())
    resolvable = total - c["na"]
    resolved = resolvable - c["pending"]
    c.update({
        "total": total, "resolvable": resolvable, "resolved": resolved,
        "resolved_pct": round(resolved / resolvable * 100) if resolvable else 0,
        "headline": (f"{resolved} of {resolvable} resolvable, {c['verified']} verified, "
                     f"{c['na']} n/a by wrapper"
                     + (f", {c['pending']} pending" if c["pending"] else "")),
    })
    return c


def coverage_totals() -> dict:
    """Record-wide per-kind counts plus the one-line taxonomy the Coverage
    view prints. Computed from the live record on every build."""
    tot = {k: 0 for k in COVERAGE_KINDS}
    for key in product_keys():
        c = coverage_summary(key)
        for k in COVERAGE_KINDS:
            tot[k] += c[k]
    total = sum(tot.values())
    na = tot["na"]
    resolvable = total - na
    resolved = resolvable - tot["pending"]
    line = (f"{resolved} of {resolvable} resolvable cells resolved · "
            f"{tot['structured']} structured (T1) · {tot['extracted']} "
            f"extracted-unverified (T2) · {tot['verified']} verified (T3) · "
            f"{tot['computed']} computed · {tot['partial'] + tot['fetched']} "
            f"partial · {na} documented n/a · {tot['pending']} pending")
    return {"counts": tot, "total": total, "resolvable": resolvable,
            "resolved": resolved, "line": line,
            "products": len(product_keys())}


# statuses a non-null structured fact may cite (invariant: the screener layer
# contains zero new facts — only typed projections of evidenced cells)
FACT_OK_STATUS = ("extracted", "verified", "computed", "fetched",
                  "structured")


def _num_forms(v) -> set[str]:
    if isinstance(v, float):
        return {f"{v}", f"{v:g}", f"{v:.1f}", f"{v:.2f}"}
    return {str(v), f"{v:,}"}


def validate_facts() -> list[str]:
    """Enforce the structured-facts contract: every field cites a real cell;
    non-null values only from extracted/verified/computed/fetched cells;
    numeric % fields (and large integers) must appear in the cited cell's own
    text unless flagged approx; nulls must carry a reason."""
    errs: list[str] = []
    fdir = DATA / "facts"
    if not fdir.exists():
        return ["facts: data/facts/ missing"]
    for key in product_keys():
        fp = fdir / f"{key}.json"
        if not fp.exists():
            errs.append(f"facts:{key}: file missing")
            continue
        doc = json.loads(fp.read_text())
        cells = load_product(key)["cells"]
        for field, f in doc.get("facts", {}).items():
            sc = f.get("source_cell")
            if sc not in cells:
                errs.append(f"facts:{key}:{field}: unknown source_cell '{sc}'")
                continue
            cell = cells[sc]
            if f.get("value") is None:
                if not f.get("reason"):
                    errs.append(f"facts:{key}:{field}: null without a reason")
                continue
            if status_kind(str(f.get("status", ""))) not in FACT_OK_STATUS:
                errs.append(f"facts:{key}:{field}: non-null value carries "
                            f"status '{f.get('status')}'")
            if (status_kind(str(cell.get("status", ""))) not in FACT_OK_STATUS
                    and f.get("status") != "computed"):
                errs.append(f"facts:{key}:{field}: cites cell {sc} whose "
                            f"status is '{cell.get('status')}'")
            if f.get("approx") or f.get("status") == "computed":
                continue
            text = str(cell.get("value") or "")
            checks = []
            v = f["value"]
            if isinstance(v, float):
                checks.append((field, v))
            elif isinstance(v, int) and not isinstance(v, bool) and v >= 1000:
                checks.append((field, v))
            elif isinstance(v, dict):
                checks += [(f"{field}.{k}", x) for k, x in v.items()
                           if isinstance(x, float)]
            for label, num in checks:
                if not any(s in text for s in _num_forms(num)):
                    errs.append(f"facts:{key}:{label}: value {num} not found "
                                f"in cell {sc} text (add approx flag only if "
                                f"the cell genuinely prints a rounded form)")
    return errs


def validate_all() -> dict[str, list[str]]:
    report = {k: validate_product(k) for k in product_keys()}
    for pk in plan_keys():
        report[f"plan:{pk}"] = validate_plan(pk)
    report["series"] = validate_series()
    report["facts"] = validate_facts()
    return report


def validate_warnings() -> dict[str, list[str]]:
    """Non-fatal findings the validator prints but does not fail on."""
    return {"raw paths vs manifest": data_path_warnings()}

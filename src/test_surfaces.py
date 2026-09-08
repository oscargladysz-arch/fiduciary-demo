"""
Surface gate: no developer string on any surface or in any document
====================================================================
    python src/test_surfaces.py      (exit 0 = every surface is clean)

Round-2 audit, items 3 and 6: developer instructions ("run python
src/fetch_authority.py on a machine that reaches federalregister.gov"),
environment excuses ("askebsa.dol.gov is blocked from the build container"),
file paths, script names and bare internal identifiers (peer_evergreen,
rubric v2, private_credit) were printed on committee-facing surfaces and
inside the generated Word documents. tark_display.SURFACE_FORBIDDEN is the
one list of such strings. This gate fails the build when any entry appears

  1. in any displayable string value of the built bundle (site/data.js,
     site/series.js, site/census.data.js),
  2. in the text or the tooltip attributes of any rendered view, including
     the interactive states a committee member reaches (entity detail,
     Authority panel, the three forms, the citation drawer), or
  3. in any generated .docx under site/memos/.

Reads the built site, writes nothing. Sits in the hook after reconcile.py,
so the build normally exists (it is built here when it does not).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from collections import Counter
from functools import partial
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tark_anon import docx_texts  # noqa: E402
from tark_data import FACT_ENUMS  # noqa: E402
from tark_display import PROSE_RULES, SURFACE_FORBIDDEN, prose_hits  # noqa: E402

BASE = Path(__file__).resolve().parents[1]
SITE = BASE / "site"
PORT = 8493
REF_PLAN = "plan_tech_media"
REF_PRODUCT = "hl_paf"

# every one of these must stay covered by some pattern in the list, so the
# list cannot be pruned to get a build green
REQUIRED_TOKENS = (
    "src/", ".py", "python ", "run ", "fetch_authority", "askebsa", "build container",
    "not in the repository", "machine that reaches", "data/advisor", "validate_data",
    "project display rule", "rubric v2", "engine output", "peer_evergreen",
    "private_credit", "private_equity_evergreen", "preipo_venture",
)

# bundle keys whose values are identifiers the JS maps to words before they
# reach a surface (never printed bare). The whole value under such a key is
# skipped, list or fact object included, because the key names its meaning.
IDENTIFIER_KEYS = {
    "id", "key", "product", "product_key", "plan", "plan_key", "strategy", "cohort",
    "cohort_id", "series", "series_id", "candidate_id", "provider_key", "members",
    "source_cells", "primary_benchmark_id", "sub_strategy", "asset_class", "wrapper_type",
    "pricing_class", "leverage_regime", "nav_cadence", "rubric_version", "lane", "local_path",
    "url", "fr_url", "docket_url", "file", "generated", "fund_series", "default_proxy",
    "proxy", "service_url", "ref", "status", "kind", "type", "declared_type", "published_id",
    "period", "periods", "period_kind", "member_period_kind", "ties", "cohort_label_id",
    "cls_codes",   # the census wire format's code-to-class table, decoded by the view
    # file stems the JS builds hrefs from, a series column and role the JS
    # maps to labels, the census row field names it decodes, the fact keys a
    # match lists (its labels ride beside them), the roster decisions
    # markdown the Cohorts view renders through its key-to-words map
    "memos", "attachment", "files", "column", "role", "row_fields", "missing_facts", "cells_read",
    "roster_decisions_md",
    # cohort member lists and statistic field names, the caveat matrix's
    # attribute keys, a cited local file, the plan order, the census entity rows
    "composite_members", "excluded_members", "field", "attrs", "local_file", "plan_order", "entities",
}
# a fact whose value is a closed vocabulary (the JS maps it to words): the
# value under these fields is a key, not prose
ENUM_VALUE_FIELDS = set(FACT_ENUMS) | {"wrapper_type", "mgmt_fee_base", "repurchase_cap_base", "tax_form",
                                       "pricing_class", "leverage_regime", "nav_cadence"}
# the rule names the second family must keep (grow, never prune)
REQUIRED_RULES = ("snake_case token", "repository path or file name", "ticket reference", "developer word",
                  "slider outside its label")

# views whose content does not depend on the selected product: rendered once
PRODUCT_INDEPENDENT = {"census", "funnel", "screener", "search", "plans", "roster",
                       "cohorts", "fees", "coverage", "verification"}
# the product-dependent views that also render for the reference product
# under every other plan (their text changes with the plan)
PLAN_SENSITIVE = ("plans", "liquidity", "packet", "evaluation")

PATTERNS = [(p, re.compile(p, re.IGNORECASE)) for p in SURFACE_FORBIDDEN]
# one alternation as a fast pre-filter, the per-pattern pass names the hit
ANY = re.compile("|".join(f"(?:{p})" for p in SURFACE_FORBIDDEN), re.IGNORECASE)

FAILS: list[str] = []
# family -> list of (pattern, location, excerpt)
HITS: dict[str, list[tuple[str, str, str]]] = {"bundle": [], "chunks": [], "views": [], "documents": []}


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}{(' : ' + extra) if extra and not cond else ''}")
    if not cond:
        FAILS.append(name)


def excerpt(text: str, start: int, end: int) -> str:
    lo, hi = max(0, start - 40), min(len(text), end + 40)
    return re.sub(r"\s+", " ", text[lo:hi]).strip()


def scan(text: str, family: str, location: str, prose: bool = True) -> None:
    """The forbidden-string list always, the prose rules (R3-P2-12) on
    reader prose. A code-styled provenance field passes prose=False."""
    if not text:
        return
    if ANY.search(text):
        for src, rx in PATTERNS:
            for m in rx.finditer(text):
                HITS[family].append((src, location, excerpt(text, m.start(), m.end())))
    if prose:
        for rule, hit in prose_hits(text):
            i = text.find(hit)
            HITS[family].append((f"prose: {rule}", location, excerpt(text, i, i + len(hit))))


# ------------------------------------------------------------ precondition
def ensure_built() -> None:
    needed = [SITE / "data.js", SITE / "series.js", SITE / "census.data.js"]
    if all(p.exists() for p in needed) and any((SITE / "memos").glob("*.docx")):
        return
    print("site not built, running build_site.py first")
    r = subprocess.run([sys.executable, str(BASE / "src" / "build_site.py")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-1500:], r.stderr[-1500:])
        check("site builds before the surface scan", False, "build_site.py failed")
        print("\n1 failure(s).")
        sys.exit(1)


# ------------------------------------------------------------ 0. the list
def check_required_tokens() -> None:
    missing = [t for t in REQUIRED_TOKENS if not any(t in p for p in SURFACE_FORBIDDEN)]
    check(f"forbidden list: SURFACE_FORBIDDEN still covers every required token "
          f"({len(SURFACE_FORBIDDEN)} patterns, {len(REQUIRED_TOKENS)} tokens)",
          bool(SURFACE_FORBIDDEN) and not missing, "uncovered: " + ", ".join(missing))
    names = [n for n, _ in PROSE_RULES]
    check(f"allowlist rules: the prose family keeps its {len(REQUIRED_RULES)} named rules ({len(PROSE_RULES)} rules)",
          all(r in names for r in REQUIRED_RULES), "missing: " + ", ".join(r for r in REQUIRED_RULES if r not in names))
    check("allowlist rules: the family fires on a key, a path, a ticket, a developer word and a bare slider, and not "
          "on the figure's own label or a URL",
          {r for r, _ in prose_hits("gate_history data/facts/x.json R2-P1-12 the engine sliders")}
          == set(REQUIRED_RULES)
          and not prose_hits("Slider assumption 10.4%, the allocation slider, https://www.sec.gov/Archives/edgar/data/1/x.htm"))


# ------------------------------------------------------------ 1. the bundle
def bundle_objects() -> dict[str, object]:
    """Every window.NAME = {...} object the three bundle files assign. The
    object is the text between the outermost braces of each assignment."""
    objs: dict[str, object] = {}
    raw = (SITE / "data.js").read_text()
    objs["TARK"] = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    for line in (SITE / "series.js").read_text().splitlines():
        m = re.match(r"^window\.(\w+) = (\{.*\})", line)
        if m:
            objs[m.group(1)] = json.loads(m.group(2))
    raw = (SITE / "census.data.js").read_text()
    m = re.match(r"^window\.(\w+) = (\{.*\})", raw, re.S)
    objs[m.group(1)] = json.loads(m.group(2))
    return objs


def scan_chunks() -> tuple[int, int]:
    """The JSON chunks the rebuilt frontend fetches (site/data/). They are a
    surface like any other: what a view paints comes out of them, so the same
    rules apply. Returns the number of files and of string values scanned."""
    out = SITE / "data"
    files = sorted(out.rglob("*.json")) if out.exists() else []
    count = [0]
    for f in files:
        walk_strings(json.loads(f.read_text()), "chunks", str(f.relative_to(out)), count)
    return len(files), count[0]


def walk_strings(node, key: str, path: str, count: list[int], parent: str = "") -> None:
    """Scan every string leaf except those under an identifier key. Dict keys
    themselves are never scanned, they are code, not copy. The value of a
    closed-vocabulary fact is a key the JS maps to words: the forbidden list
    runs over it, the prose rules do not."""
    if key in IDENTIFIER_KEYS:
        return
    if isinstance(node, dict):
        for k, v in node.items():
            walk_strings(v, k, f"{path}.{k}", count, key)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_strings(v, key, f"{path}[{i}]", count, parent)
    elif isinstance(node, str):
        count[0] += 1
        # the evidence ledger's source column and verbatim quote are provenance
        provenance = path.startswith("TARK_EVIDENCE") and key in ("source", "quote")
        scan(node, "bundle", path, prose=not (provenance or (key == "value" and parent in ENUM_VALUE_FIELDS)))


def scan_bundle() -> tuple[dict, int]:
    objs = bundle_objects()
    count = [0]
    for name, obj in objs.items():
        walk_strings(obj, name, name, count)
    return objs["TARK"], count[0]


# ------------------------------------------------------------ 2. the views
class SurfaceText(HTMLParser):
    """Every text node outside script and style plus the attribute values a
    reader meets on hover or in a form (title, placeholder, aria-label,
    data-def). Hidden elements count: a developer string must not hide in a
    tooltip, a closed details block or a hidden pre. Text inside a
    code-styled element (pre, code, a command or provenance block, a slider
    control's own row) is collected apart: the forbidden list runs over it,
    the prose rules do not (R3-P2-12)."""
    SKIP = {"script", "style"}
    ATTRS = {"title", "placeholder", "aria-label", "data-def"}
    CODE_TAGS = {"pre", "code"}
    CODE_CLASSES = ("cmd", "provenance", "sliderrow")
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param",
            "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.code_parts: list[str] = []
        self._skip = 0
        self._stack: list[bool] = []   # one entry per open element: is it code-styled

    def _in_code(self) -> bool:
        return any(self._stack)

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        cls = next((v or "" for k, v in attrs if k == "class"), "")
        code = tag in self.CODE_TAGS or any(c in cls.split() for c in self.CODE_CLASSES)
        if tag not in self.VOID:
            self._stack.append(code)
        for k, v in attrs:
            if k in self.ATTRS and v:
                (self.code_parts if (code or self._in_code()) else self.parts).append(v)

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag not in self.VOID and self._stack:
            self._stack.pop()

    def handle_data(self, data):
        if not self._skip and data.strip():
            (self.code_parts if self._in_code() else self.parts).append(data)


def surface_text(html: str) -> str:
    return surface_texts(html)[0]


def surface_texts(html: str) -> tuple[str, str]:
    """(reader prose, code-styled text) of one rendered page."""
    p = SurfaceText()
    p.feed(html)
    p.close()
    return "\n".join(p.parts), "\n".join(p.code_parts)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # the request log is noise in a gate
        pass


def serve() -> ThreadingHTTPServer:
    handler = partial(QuietHandler, directory=str(SITE))
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def scan_views(bundle: dict) -> tuple[int, list[str]]:
    from playwright.sync_api import sync_playwright

    main_js = (SITE / "js" / "main.js").read_text()
    view_ids = re.findall(r'^\s*\["(\w+)", "[^"]+", view\w+, "\w+"\]', main_js, re.M)
    check("views: the route registry in main.js was read", bool(view_ids))
    products = list(bundle["products"].keys())
    plans = list(bundle["plan_order"])
    other = "cliffwater_cclfx" if REF_PRODUCT != "cliffwater_cclfx" else products[0]

    states: list[tuple[str, str, str]] = []
    for v in view_ids:
        if v in PRODUCT_INDEPENDENT:
            states.append((v, REF_PRODUCT, REF_PLAN))
        else:
            states.extend((v, k, REF_PLAN) for k in products)
    for pl in plans:
        if pl != REF_PLAN:
            states.extend((v, REF_PRODUCT, pl) for v in PLAN_SENSITIVE)

    errors: list[str] = []
    rendered = [0]
    current = ["boot"]
    httpd = serve()
    time.sleep(0.2)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("pageerror", lambda e: errors.append(f"{current[0]}: {e}"))

        def render(view: str, product: str, plan: str) -> None:
            current[0] = f"view {view} product {product} plan {plan}"
            pair = f"&compare={product},{other if other != product else REF_PRODUCT}" \
                if view == "compare" else ""
            page.goto(f"http://127.0.0.1:{PORT}/#view={view}&plan={plan}&product={product}{pair}",
                      wait_until="networkidle")
            page.wait_for_timeout(150)

        def scan_page(view: str, product: str, plan: str) -> None:
            rendered[0] += 1
            prose, code = surface_texts(page.content())
            scan(prose, "views", f"view {view} product {product} plan {plan}")
            scan(code, "views", f"view {view} product {product} plan {plan} (code-styled)", prose=False)

        # the Authority panel lives in the top bar of every page: open it once
        # and scan (its text is in the DOM either way, open makes the intent plain)
        render(view_ids[0], REF_PRODUCT, REF_PLAN)
        page.evaluate("() => document.querySelectorAll('details.authority').forEach((d) => { d.open = true })")
        scan_page(f"{view_ids[0]}+authority-open", REF_PRODUCT, REF_PLAN)

        for view, product, plan in states:
            render(view, product, plan)
            scan_page(view, product, plan)

        # census entity detail for an unevaluated fund (the ingest command surface)
        render("census", REF_PRODUCT, REF_PLAN)
        page.evaluate("() => window.tarkSetState({view: 'census', c_cik: '1467631'})")
        page.wait_for_selector("#view [data-back]", timeout=15000)
        scan_page("census+entity-1467631", REF_PRODUCT, REF_PLAN)

        # advisor form on the evaluation view, filled and made
        render("evaluation", REF_PRODUCT, REF_PLAN)
        form = page.locator("[data-advisor-form]")
        if form.count():
            form = form.first
            form.evaluate("(d) => { d.open = true }")
            form.locator('[data-f="value"]').fill("Recordkeeper confirmed quarterly window handling.")
            form.locator('[data-f="signer"]').fill("A. Person, committee chair")
            form.locator('[data-f="date"]').fill("2026-09-04")
            form.locator("[data-advisor-make]").click()
            page.wait_for_timeout(100)
            scan_page("evaluation+advisor-form", REF_PRODUCT, REF_PLAN)
        else:
            check("views: an advisor form exists on the reference evaluation page", False)

        # citation drawer on the evaluation view, three cells in turn
        for cid in ("2.1", "5.4", "5.6"):
            btn = page.locator(f'[data-cite][data-cid="{cid}"]')
            if not btn.count():
                check(f"views: a citation button for cell {cid} exists on the reference evaluation page", False)
                continue
            btn.first.click()
            page.wait_for_timeout(100)
            scan_page(f"evaluation+drawer-{cid}", REF_PRODUCT, REF_PLAN)

        # plan intake form on the plans view, filled, confirmed and made
        render("plans", REF_PRODUCT, REF_PLAN)
        pf = page.locator("[data-plan-form]")
        if pf.count():
            pf = pf.first
            pf.evaluate("(d) => { d.open = true }")
            for f, v in (("display_label", "US regional hospital 403(b) plan (~$400M, OH)"),
                         ("plan_year", "2024-01-01 to 2024-12-31"), ("net_assets_eoy", "400000000"),
                         ("net_assets_boy", "380000000"), ("tot_admin_expenses", "300000"),
                         ("with_account_balances", "5000"), ("active_eoy", "3000"),
                         ("separated_deferred_vested", "1500"), ("retired_receiving", "100"),
                         ("pension_benefit_codes", "2E2G2J2K")):
                pf.locator(f'[data-f="{f}"]').fill(v)
            pf.locator('[data-f="anonymization_label"]').check()
            pf.locator("[data-plan-make]").click()
            page.wait_for_timeout(100)
            scan_page("plans+intake-form", REF_PRODUCT, REF_PLAN)
        else:
            check("views: the plan intake form exists on the plans page", False)

        # verification form, signed and made
        render("verification", REF_PRODUCT, REF_PLAN)
        vf = page.locator("[data-verify-form]")
        if vf.count():
            vf = vf.first
            vf.evaluate("(d) => { d.open = true }")
            vf.locator('[data-f="signer"]').fill("A. Person, committee chair")
            vf.locator('[data-f="date"]').fill("2026-09-04")
            vf.locator("[data-verify-make]").click()
            page.wait_for_timeout(100)
            scan_page("verification+verify-form", REF_PRODUCT, REF_PLAN)
        else:
            check("views: a verification form exists on the verification page", False)

        browser.close()
    httpd.shutdown()
    return rendered[0], errors


# ------------------------------------------------------------ 3. the documents
def scan_documents() -> int:
    docs = sorted((SITE / "memos").glob("*.docx"))
    for p in docs:
        prose, provenance = docx_texts(p)
        scan(prose, "documents", f"docx {p.name}")
        scan(provenance, "documents", f"docx {p.name} (provenance columns)", prose=False)
    return len(docs)


# ------------------------------------------------------------ report
def report(family: str, limit: int = 25) -> None:
    hits = HITS[family]
    if not hits:
        return
    per = Counter(src for src, _, _ in hits)
    distinct = {src: len({ex for s, _, ex in hits if s == src}) for src in per}
    print(f"\n  {family}: {len(hits)} hits, per pattern (distinct excerpts in parentheses):")
    for src, n in per.most_common():
        print(f"    /{src}/  {n} ({distinct[src]})")
    # the same excerpt recurs on many states (shell text, footers), so the
    # lines shown are distinct pattern x excerpt pairs with the first location
    seen: dict[tuple[str, str], tuple[str, int]] = {}
    for src, loc, ex in hits:
        k = (src, ex)
        if k in seen:
            seen[k] = (seen[k][0], seen[k][1] + 1)
        else:
            seen[k] = (loc, 1)
    print(f"  first {min(limit, len(seen))} of {len(seen)} distinct hits:")
    for (src, ex), (loc, n) in list(seen.items())[:limit]:
        more = f"  (+{n - 1} more)" if n > 1 else ""
        print(f"    {loc}: /{src}/ in \"{ex}\"{more}")


def main() -> int:
    t0 = time.time()
    check_required_tokens()
    ensure_built()

    bundle, n_strings = scan_bundle()
    check(f"bundle: no developer string, file path, script name, internal key, ticket, developer word or bare "
          f"slider in {n_strings} string values", not HITS["bundle"], f"{len(HITS['bundle'])} hits")

    n_states, errors = scan_views(bundle)
    check(f"views: none in {n_states} rendered states, no page error",
          not HITS["views"] and not errors,
          f"{len(HITS['views'])} hits, {len(errors)} page errors" + (f", first: {errors[0][:120]}" if errors else ""))

    n_chunks, n_chunk_strings = scan_chunks()
    check(f"chunks: none in {n_chunk_strings} string values of {n_chunks} JSON chunks the rebuilt frontend fetches",
          n_chunks > 0 and not HITS["chunks"], f"{len(HITS['chunks'])} hits")

    n_docs = scan_documents()
    check(f"documents: none in {n_docs} generated documents",
          n_docs > 0 and not HITS["documents"], f"{len(HITS['documents'])} hits")

    if FAILS:
        for family in ("bundle", "chunks", "views", "documents"):
            report(family)
        if errors:
            print(f"\n  page errors ({len(errors)}):")
            for e in errors[:10]:
                print("    " + e[:200])
    print(f"\n{len(FAILS)} failure(s) in {time.time() - t0:.1f}s." if FAILS
          else f"\nEvery surface and document is clean ({time.time() - t0:.1f}s).")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

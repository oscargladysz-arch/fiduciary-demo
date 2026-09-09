"""
Screenshot sweep for the static site (baseline and after sets).

Renders every view for a set of products under one plan and writes one PNG
per (product, view) into an output directory. Reused before and after the
remediation so the two sets are directly comparable.

Run:  python src/shots.py --out docs/screenshots/baseline_2026-09 \
          --products hl_paf,cion_ares,sreit,jll_ipt --plan plan_tech_media
Requires a built site (python src/build_site.py) and the Playwright Chromium
that ships with the environment.
"""
from __future__ import annotations

import argparse
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parents[1]
SITE = BASE / "site"

# the routes that do not depend on a product: shot once
GLOBAL_ROUTES = ["start", "universe", "funnel", "screener", "compare", "roster",
                 "plans", "search", "packet", "coverage", "verification", "design"]
# the panels under one fund: shot per product
PANELS = ["record", "benchmark", "liquidity", "cohort", "lab", "documents"]
VIEWS = GLOBAL_ROUTES + PANELS
PRODUCT_INDEPENDENT = set(GLOBAL_ROUTES)


def serve(port: int) -> ThreadingHTTPServer:
    handler = partial(SimpleHTTPRequestHandler, directory=str(SITE))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--products", required=True,
                    help="comma-separated product keys")
    ap.add_argument("--plan", default="plan_tech_media")
    ap.add_argument("--views", default=",".join(VIEWS))
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--port", type=int, default=8477)
    ap.add_argument("--compare-with", default="cliffwater_cclfx",
                    help="second product for the compare view")
    ap.add_argument("--format", choices=["png", "jpeg"], default="jpeg",
                    help="jpeg keeps a 72-image set under 10 MB in git")
    ap.add_argument("--quality", type=int, default=60,
                    help="jpeg quality (ignored for png)")
    ap.add_argument("--max-height", type=int, default=8000,
                    help="clip very tall pages (the census table) at this height")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    products = [p for p in args.products.split(",") if p]
    views = [v for v in args.views.split(",") if v]
    serve(args.port)
    n = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": args.width, "height": 800})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for pi, key in enumerate(products):
            for i, view in enumerate(views, 1):
                if pi > 0 and view in PRODUCT_INDEPENDENT:
                    continue
                other = args.compare_with if args.compare_with != key else products[0]
                path = f"/{view}" if view in PRODUCT_INDEPENDENT else f"/product/{key}/{view}"
                query = f"?plan={args.plan}"
                if view == "compare":
                    query += f"&compare={key}.{other}"
                url = f"http://127.0.0.1:{args.port}/#{path}{query}"
                page.goto(url, wait_until="networkidle")
                page.reload(wait_until="networkidle")   # a hash change is not a load
                page.wait_for_timeout(400)
                name = (f"{i:02d}_{view}" if view in PRODUCT_INDEPENDENT
                        else f"{key}__{i:02d}_{view}")
                path = out / f"{name}.{args.format}"
                kw = {"quality": args.quality} if args.format == "jpeg" else {}
                height = page.evaluate("document.documentElement.scrollHeight")
                if height > args.max_height:
                    kw["clip"] = {"x": 0, "y": 0, "width": args.width,
                                  "height": args.max_height}
                    kw["full_page"] = True
                else:
                    kw["full_page"] = True
                page.screenshot(path=str(path), type=args.format, **kw)
                n += 1
        browser.close()
    print(f"{n} screenshots written to {out}")
    if errors:
        print(f"{len(errors)} page errors during the sweep:")
        for e in errors[:10]:
            print("  ", e)


if __name__ == "__main__":
    main()

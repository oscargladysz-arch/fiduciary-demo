"""
Web gate (R3-P1-11): the rebuilt frontend under web/ against the Web
Interface Guidelines pinned in docs/design/web-interface-guidelines_*.md.

Run: python src/test_web.py [--routes design,start,...] [--out web_dist]
Exit 0 = pass. Builds web/ first unless --no-build.

What it enforces, all as properties, never as phrases:
  (c) token gate: no color, font-size, spacing, radius, shadow, border-width
      or duration literal in the built CSS or JS outside the tokens file
  (e) formatting gate: no toFixed(, no toLocaleString( without options, no
      "..." in strings rendered to users
  (a) guideline audit, Playwright, every route at 1440 and 390 px in both
      themes: every interactive element focusable with a visible focus ring,
      every form control labeled, every icon-only button named, every image
      and chart named, strict heading order, a working skip link, no text
      under 12 px, every text color pair at 4.5:1 (3:1 at 24 px and up), no
      transition: all, no horizontal body scroll, tap targets, the H1 within
      200 px on mobile, tables that scroll in their container with a sticky
      header, no title-only information, aria-live regions present, Back
      restores the previous route and scroll, a filter change preserves
      focus and scroll
  (b) axe-core on every route, zero serious or critical, report committed
      under docs/design/axe_<date>.json
  (f) performance budget: base JS and CSS gzipped, fonts preloaded,
      modulepreload for the route chunks, no synchronous data script
  (h) the build served under /previews/999/ loads every route
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import subprocess
import sys
import threading
import time
from datetime import date
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
WEB = BASE / "web"
FAILS: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    print(f"[{'PASS' if cond else 'FAIL'}] {name}{(' — ' + extra) if extra and not cond else ''}")
    if not cond:
        FAILS.append(name)


# ---------------------------------------------------------------- build
ap = argparse.ArgumentParser()
ap.add_argument("--routes", default="start,universe,funnel,screener,compare,roster,plans,"
                "search,packet,design,product/hl_paf/record,product/dxyz/record")
ap.add_argument("--out", default="site_next")
ap.add_argument("--no-build", action="store_true")
ap.add_argument("--port", type=int, default=8478)
ap.add_argument("--axe-out", default="")
args = ap.parse_args()
OUT = BASE / args.out
if not args.no_build:
    r = subprocess.run(["npx", "vite", "build"], cwd=WEB, capture_output=True, text=True,
                       env={**__import__("os").environ, "TARK_WEB_OUT": str(OUT)})
    check("web: vite build succeeds", r.returncode == 0, (r.stderr or r.stdout)[-400:])
    if r.returncode != 0:
        sys.exit(1)
    r = subprocess.run(["npx", "tsc", "--noEmit"], cwd=WEB, capture_output=True, text=True)
    check("web: typecheck is clean", r.returncode == 0, r.stdout[-400:])
    r = subprocess.run(["npx", "vitest", "run", "--reporter", "dot"], cwd=WEB, capture_output=True, text=True)
    check("web: the unit tests pass (the data adapter's chunk layout, its routes, its cache and its sentences)",
          r.returncode == 0, (r.stdout + r.stderr)[-500:])

css_files = sorted((OUT / "assets").glob("*.css"))
js_files = sorted((OUT / "assets").glob("*.js"))
check("web: built CSS and JS exist", bool(css_files) and bool(js_files))
css_all = "\n".join(f.read_text() for f in css_files)
js_all = "\n".join(f.read_text() for f in js_files)

# ---------------------------------------------------------------- (c) token gate
# the tokens file is the only place a literal may live. In the built CSS the
# token block is the :root / [data-theme] / @media(prefers-color-scheme)
# declarations of custom properties. Every other declaration must be var().
def strip_token_blocks(css: str) -> str:
    # remove custom property declarations (--x: value) anywhere: the gate
    # then asserts no literal survives in ordinary declarations
    css = re.sub(r"--[a-zA-Z0-9-]+\s*:[^;{}]*(;|(?=\}))", "", css)
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"url\((['\"]?)data:[^)]*\)", "url(data)", css)
    return css

rest = strip_token_blocks(css_all)
decls = re.findall(r"([a-zA-Z-]+)\s*:\s*([^;{}]+)[;}]", rest)
LITERAL = re.compile(r"(#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|\b\d*\.?\d+(px|rem|em|ms|s)\b)")
ALLOWED_PROPS = {"line-height", "flex", "z-index", "opacity", "font-weight", "grid-template-columns", "grid-column", "order",
                 "stroke-width", "transform", "width", "height", "max-width", "min-width", "top", "left", "right", "bottom", "inset",
                 "clip", "margin", "padding", "content", "font-family", "text-decoration-thickness", "text-underline-offset"}
ZEROISH = re.compile(r"^(0|1px|-1px|100%|auto|none|0 0|0 auto|inherit|initial|unset|max-content|min-content|100vh|100vw|calc\(.*\)|\d+fr|repeat\(.*\)|translate.*|rotate.*|rect\(.*\)|attr\(.*\)|[\"'].*[\"']|min\(.*\)|max\(.*\))$")
literal_hits = []
for prop, val in decls:
    v = val.strip()
    if "var(" in v and not LITERAL.search(re.sub(r"var\([^)]*\)", "", v)):
        continue
    if prop in ("line-height", "flex", "z-index", "opacity", "font-weight", "order", "grid-column", "stroke-width"):
        continue
    if ZEROISH.match(v):
        continue
    if LITERAL.search(v):
        # 0.15em underline offsets and 1px hairline widths are the two literals the base allows
        if prop in ("text-underline-offset", "text-decoration-thickness"):
            continue
        if prop in ("width", "height", "min-width", "max-width", "margin", "padding", "top", "left", "right", "bottom", "inset", "clip") and re.fullmatch(r"-?1px|0|100%|auto|1px 1px|-?1px -?1px|rect\(0, 0, 0, 0\)|rect\(0 0 0 0\)", v):
            continue
        literal_hits.append(f"{prop}: {v[:40]}")
check("tokens (c): no color, size, spacing, radius, shadow or duration literal in the built CSS outside custom properties",
      not literal_hits, f"{len(literal_hits)} hits: " + "; ".join(literal_hits[:8]))

# the JS: any hex color, any px number in a style string, any ms duration
js_user = js_all
# strip the vendored libraries (react, tanstack): only the application chunks are scanned
app_js = "\n".join(f.read_text() for f in js_files if not re.match(r"(react|table)-", f.name))
js_hex = re.findall(r"[\"'`]#[0-9a-fA-F]{6}\b", app_js)
js_px = re.findall(r"[\"'`:]\s*\d+px\b", app_js)
js_ms = re.findall(r"\b\d{2,4}ms\b", app_js)
check("tokens (c): no hex color, px size or ms duration literal in the application JS",
      not js_hex and not js_px and not js_ms, f"hex={js_hex[:4]} px={js_px[:4]} ms={js_ms[:4]}")

# ---------------------------------------------------------------- (e) formatting gate
check("formatting (e): no toFixed( in the application JS", "toFixed(" not in app_js)
bare_tls = [m for m in re.finditer(r"toLocaleString\(([^)]*)\)", app_js) if not m.group(1).strip()]
check("formatting (e): no toLocaleString( without options", not bare_tls)
strings = re.findall(r"[\"'`]([^\"'`\\]{4,200})[\"'`]", app_js)
three_dots = [s for s in strings if re.search(r"(?<=[A-Za-z\s\"'`])\.\.\.(?=[\"'`\s.)]|$)", s)]
check("formatting (e): no three-dot ellipsis in a string literal", not three_dots, "; ".join(three_dots[:3]))
# straight quotes in prose strings (a space on both sides of a double quote inside a string)
straight = [s for s in strings if re.search(r"\s\"[A-Za-z]", s) or re.search(r"[A-Za-z]'[a-z]\b", s)]
check("formatting (e): no straight quotes or apostrophes in prose strings", not straight, "; ".join(straight[:3]))

# ---------------------------------------------------------------- (f) performance budget
html = (OUT / "index.html").read_text()
entry_js = [f for f in js_files if re.match(r"index-", f.name)]
base_bytes = sum(len(gzip.compress(f.read_bytes())) for f in entry_js + css_files + [f for f in js_files if re.match(r"react-", f.name)])
check("performance (f): base JS and CSS under 120 KB gzipped", base_bytes <= 120_000, f"{base_bytes:,} bytes")
check("performance (f): fonts are preloaded", 'rel="preload"' in html and 'as="font"' in html)
check("performance (f): route chunks are preloaded with modulepreload", "modulepreload" in html)
check("performance (f): no synchronous data script", not re.search(r"<script src=\"[^\"]*data[^\"]*\.js\"", html))

# ------------------------------------------------- the rule set, statically
# What the audit cannot see from one rendered page: the stylesheet's own
# promises, and the anti-patterns that are absent rather than present.
faces = re.findall(r"@font-face\s*\{[^}]*\}", css_all)
check("guidelines: every font face declares font-display: swap",
      bool(faces) and all("font-display" in f and "swap" in f for f in faces),
      f"{len(faces)} faces, {sum('swap' not in f for f in faces)} without swap")
check("guidelines: the layout applies the safe-area insets",
      "env(safe-area-inset" in css_all)
check("guidelines: the tap highlight is set on purpose rather than left to the platform",
      "-webkit-tap-highlight-color" in css_all)
check("guidelines: the double-tap delay is removed on the controls",
      "touch-action" in css_all and "manipulation" in css_all)
_hover = [sel for sel in (".btn", ".link", ".navlink", ".tab")
          if not re.search(re.escape(sel) + r"[^{]*:hover", css_all)]
check("guidelines: every control has a hover state", not _hover, f"missing: {_hover}")
# removing the default ring is correct only when :focus-visible draws one back
_focus_none = bool(re.search(r":focus(?!-visible)[^{]*\{[^}]*outline\s*:\s*none", css_all))
_focus_visible_ring = bool(re.search(r":focus-visible[^{]*\{[^}]*outline\s*:(?!\s*none)", css_all))
check("guidelines: the focus ring is drawn on :focus-visible, and nothing removes it without drawing it back",
      _focus_visible_ring and (not _focus_none or _focus_visible_ring),
      f"outline:none on :focus {_focus_none}, ring on :focus-visible {_focus_visible_ring}")
check("guidelines: paste is never blocked", "onPaste" not in app_js and "preventDefault" in app_js)
check("guidelines: zoom is not disabled in the document",
      not re.search(r"user-scalable\s*=\s*no|maximum-scale\s*=\s*1(?!\d)", html))
check("guidelines: the theme reaches the browser chrome",
      'name="theme-color"' in html and "color-scheme" in css_all)
# a link to another host is a link a reader follows: what must not happen is
# the page FETCHING from another host, which is a stylesheet url() or a
# script or stylesheet tag in the document
_ext = sorted(set(re.findall(r"url\(\s*[\"']?(https?://[a-z0-9.-]+)", css_all))
              | set(re.findall(r"<(?:script|link)[^>]+(?:src|href)=\"(https?://[a-z0-9.-]+)", html)))
check("guidelines: the page fetches nothing from another host",
      not _ext, f"external hosts fetched: {_ext[:4]}")
check("guidelines: no image is rendered without its dimensions",
      not re.search(r"<img(?![^>]*\bwidth=)[^>]*>", html), "an img in the document has no width")

# ---------------------------------------------------------------- serve two ways: root and a preview subpath
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D401
        pass

root_dir = OUT
# the JSON chunks the build wrote, beside the application that fetches them:
# on the deployed site they sit at data/ under the same root
chunks_src = BASE / "site" / "data"
if chunks_src.exists():
    import shutil as _sh
    _sh.copytree(chunks_src, OUT / "data", dirs_exist_ok=True)
# the generated documents sit beside the application too, so a download link on
# the documents panel and in the packet resolves the same way at the site root
# and under a preview subpath
memos_src = BASE / "site" / "memos"
if memos_src.exists():
    import shutil as _sh2
    _sh2.copytree(memos_src, OUT / "memos", dirs_exist_ok=True)
sub_root = BASE / ".preview_root"
if sub_root.exists():
    import shutil
    shutil.rmtree(sub_root)
(sub_root / "previews").mkdir(parents=True)
import shutil
shutil.copytree(OUT, sub_root / "previews" / "999")
httpd = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Quiet, directory=str(root_dir)))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
httpd2 = ThreadingHTTPServer(("127.0.0.1", args.port + 1), partial(Quiet, directory=str(sub_root)))
threading.Thread(target=httpd2.serve_forever, daemon=True).start()
time.sleep(0.3)
ROOT = f"http://127.0.0.1:{args.port}/"
SUB = f"http://127.0.0.1:{args.port + 1}/previews/999/"
ROUTES = [r for r in args.routes.split(",") if r]

from playwright.sync_api import sync_playwright  # noqa: E402

AXE = (WEB / "node_modules" / "axe-core" / "axe.min.js").read_text()

AUDIT_JS = r"""
() => {
  const out = { fails: [], counts: {} };
  const add = (rule, detail) => { out.fails.push(rule + ': ' + detail); };
  const count = (k, n) => { out.counts[k] = (out.counts[k] || 0) + n; };
  const lum = (rgb) => { const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2]); };
  const parse = (s) => { const m = s && s.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(',').map((x) => parseFloat(x));
    return { rgb: p.slice(0, 3), a: p.length > 3 ? p[3] : 1 }; };
  const bgOf = (el) => { let e = el; while (e) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0.9) return c.rgb; e = e.parentElement; }
    const b = parse(getComputedStyle(document.body).backgroundColor); return b ? b.rgb : [255, 255, 255]; };
  const contrast = (a, b) => { const la = lum(a), lb = lum(b); return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05); };
  const visible = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const name = (el) => (el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.getAttribute('title') || (el.textContent || '').trim());

  // text under 12 px and contrast on every visible text node
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n; const seen = new Set();
  while ((n = walker.nextNode())) {
    if (!n.textContent.trim()) continue;
    const el = n.parentElement; if (!el || seen.has(el) || !visible(el)) continue; seen.add(el);
    if (el.closest('script, style, [aria-hidden="true"], .sr-only')) continue;
    const cs = getComputedStyle(el); const fs = parseFloat(cs.fontSize);
    count('textNodes', 1);
    if (fs < 12) add('text-size', el.tagName + '.' + el.className + ' at ' + fs + 'px "' + n.textContent.trim().slice(0, 30) + '"');
    const fg = parse(cs.color); if (!fg) continue;
    const bg = bgOf(el); const cr = contrast(fg.rgb, bg);
    const big = fs >= 24 || (fs >= 18.66 && parseInt(cs.fontWeight, 10) >= 700);
    const need = big ? 3 : 4.5;
    if (cr < need - 0.01) add('contrast', el.tagName + '.' + el.className + ' ' + cr.toFixed(2) + ' (' + cs.color + ' on rgb(' + bg.join(',') + ')) "' + n.textContent.trim().slice(0, 24) + '"');
  }
  // typography, in the rendered text rather than in a string literal: a source
  // string with an apostrophe in it ends the literal early, so a grep over the
  // built JS cannot see the apostrophe it is looking for. A verbatim quote from
  // a filing is exempt: it is the document's own text and is never edited.
  const QUOTED = 'blockquote, .quote, .provenance, code, pre, [data-verbatim]';
  for (const el of Array.from(document.body.querySelectorAll('*'))) {
    if (el.closest(QUOTED) || el.children.length) continue;
    const text = (el.textContent || '').trim();
    if (!text || text.length < 4) continue;
    if (/[A-Za-z]'[A-Za-z]/.test(text)) add('straight-apostrophe', text.slice(0, 60));
    else if (/\s"[A-Za-z]/.test(text)) add('straight-quote', text.slice(0, 60));
    else if (/[A-Za-z]\.\.\.(\s|$)/.test(text)) add('three-dot-ellipsis', text.slice(0, 60));
    else if (/\u2014/.test(text)) add('em-dash', text.slice(0, 60));
  }

  // interactive elements: focusable, named, hit targets, focus ring
  const inter = [...document.querySelectorAll('a[href], button, input, select, textarea, [role="button"], [tabindex]')].filter(visible);
  count('interactive', inter.length);
  const isMobile = innerWidth < 900;
  for (const el of inter) {
    if (el.tabIndex < 0 && !el.matches('[tabindex="-1"]')) add('focusable', el.tagName + ' not focusable');
    const r = el.getBoundingClientRect();
    const min = (isMobile && el.matches('.btn--primary')) ? 44 : 24;
    // a text link is governed by its line box (WCAG 2.5.8 exempts inline links); block-like links are not
    const inlineLink = el.matches('a') && !el.matches('.btn, .navlink, .card--link') && !el.querySelector('svg') && r.height < 28;
    // a focusable region (a tab panel, a scroll container) is a keyboard target, not a tap target
    if (el.matches('[role="tabpanel"], [role="region"]')) continue;
    if (!inlineLink && !el.matches('input[type="range"], input[type="checkbox"], input[type="radio"]') && (r.width < min - 0.5 || r.height < min - 0.5) && !el.closest('.check'))
      add('hit-target', el.tagName + '.' + el.className + ' ' + Math.round(r.width) + 'x' + Math.round(r.height));
    if (el.matches('button, a[href], [role="button"]') && !name(el)) add('name', el.tagName + '.' + el.className + ' has no accessible name');
    if (el.matches('input:not([type="hidden"]), select, textarea')) {
      const id = el.id; const lab = (id && document.querySelector('label[for="' + CSS.escape(id) + '"]')) || el.closest('label') || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby');
      if (!lab) add('label', el.tagName + '[name=' + el.name + '] has no label');
    }
    const cs = getComputedStyle(el);
    if (/\ball\b/.test(cs.transitionProperty) && cs.transitionDuration && cs.transitionDuration !== '0s') add('transition-all', el.tagName + '.' + el.className);
  }
  // icon-only buttons named, decorative icons hidden
  for (const svg of document.querySelectorAll('svg')) {
    if (!visible(svg)) continue;
    const inBtn = svg.closest('button, a');
    if (svg.getAttribute('aria-hidden') !== 'true' && !svg.getAttribute('aria-label') && !svg.getAttribute('role')) add('svg-name', 'svg without aria-hidden or a name');
    if (inBtn && !name(inBtn)) add('icon-button', 'icon-only control without a name');
  }
  for (const img of document.querySelectorAll('img')) if (!img.hasAttribute('alt')) add('img-alt', img.src.slice(-30));
  // headings strict order
  const hs = [...document.querySelectorAll('h1, h2, h3, h4, h5, h6')].filter(visible).map((h) => +h.tagName[1]);
  count('headings', hs.length);
  if (hs.filter((h) => h === 1).length !== 1) add('h1', 'expected one h1, found ' + hs.filter((h) => h === 1).length);
  for (let i = 1; i < hs.length; i++) if (hs[i] > hs[i - 1] + 1) add('heading-order', 'h' + hs[i - 1] + ' then h' + hs[i]);
  // skip link
  const skip = document.querySelector('a.skiplink, a[href="#main"]');
  if (!skip) add('skip-link', 'missing'); else if (!document.getElementById('main')) add('skip-link', 'target missing');
  // horizontal scroll
  if (document.documentElement.scrollWidth > innerWidth + 1) add('h-scroll', document.documentElement.scrollWidth + ' > ' + innerWidth);
  // H1 within 200 px on mobile
  const h1 = document.querySelector('h1');
  if (isMobile && h1) { const top = h1.getBoundingClientRect().top + scrollY; if (top > 200) add('h1-top', Math.round(top) + 'px'); }
  // tables scroll inside their wrapper with a sticky header
  for (const t of document.querySelectorAll('table')) {
    if (!visible(t)) continue;
    const wrap = t.closest('.tblwrap');
    if (!wrap) { add('table-wrap', 'table outside a scroll container'); continue; }
    const th = t.querySelector('thead th');
    if (th && getComputedStyle(th).position !== 'sticky') add('table-sticky', 'header not sticky');
    if (!t.querySelector('caption')) add('table-caption', 'no caption');
  }
  // title-only information
  for (const el of document.querySelectorAll('[title]')) {
    if (!visible(el) || el.matches('a, button, input, select, textarea, svg, abbr')) continue;
    if (!(el.textContent || '').trim() && !el.getAttribute('aria-label')) add('title-only', el.tagName + '.' + el.className);
  }
  // aria-live regions exist
  if (!document.querySelector('[aria-live]')) add('aria-live', 'no live region on the page');

  // tier language never blurs. Three things are checked, and the record's own
  // words about a fund's disclosures are not one of them: a cell that says a
  // manager's figures are unverified is the filing's finding, not a claim
  // about this record's tiers.
  //  - the term of art, human-verified, belongs beside a count or a pending state
  //  - a re-check by an agent is never called verification
  //  - a status chip carries a defined label, so it is the tier itself
  for (const el of Array.from(document.body.querySelectorAll('*'))) {
    if (el.children.length || el.closest(QUOTED) || el.closest('.chip, .legend')) continue;
    const text = (el.textContent || '').trim();
    if (/human[\s-]?verifi/i.test(text)
        && !/\d/.test(text) && !/pending|nobody|not yet|queue|signature|offered/i.test(text)) {
      add('tier-language', 'human-verified with no count and no pending state: ' + text.slice(0, 60));
    }
    if (/\bagent\b[^.]{0,60}\bverif/i.test(text) || /\bverif[^.]{0,60}\bagent\b/i.test(text)) {
      add('tier-language', 'an agent pass called verification: ' + text.slice(0, 60));
    }
  }
  // a control may never set a row verified: only a human signature does, and
  // it is made outside this page
  for (const el of document.querySelectorAll('button, [role="button"], input[type="submit"]')) {
    const n = ((el.getAttribute('aria-label') || el.textContent || '') + '').trim();
    if (/^(verify|mark verified|set verified|approve row)\b/i.test(n)) add('tier-language', 'a control offers to verify: ' + n.slice(0, 50));
  }

  // ---- the rest of the pinned rule set -----------------------------------
  // a native select paints itself in the platform's dark mode unless it is
  // told what to paint: both the background and the colour must be explicit
  for (const sel of document.querySelectorAll('select')) {
    if (!visible(sel)) continue;
    const cs = getComputedStyle(sel);
    const bg = parse(cs.backgroundColor);
    if (!bg || bg.a < 0.9) add('select-color', 'select without an explicit background');
    if (!parse(cs.color)) add('select-color', 'select without an explicit colour');
  }
  // a scrollable overlay must not chain its scroll to the page behind it
  for (const panel of document.querySelectorAll('[role="dialog"] > *, .drawer__panel, .sheet__panel, .palette')) {
    if (!visible(panel)) continue;
    const oy = getComputedStyle(panel).overscrollBehaviorY;
    if (oy !== 'contain' && oy !== 'none') add('overscroll', (panel.className || panel.tagName) + ' is ' + oy);
  }
  // autofocus: at most one, and never on a narrow viewport where it opens the
  // keyboard over the content a reader has not read yet
  const autos = [...document.querySelectorAll('[autofocus]')].filter(visible);
  if (autos.length > 1) add('autofocus', autos.length + ' elements claim the focus');
  if (isMobile && autos.length) add('autofocus', 'autofocus on a narrow viewport');
  // a control must be a control: nothing else may look clickable
  for (const el of document.querySelectorAll('div, span, li, p, section, article')) {
    if (!visible(el) || el.children.length) continue;
    if (getComputedStyle(el).cursor !== 'pointer') continue;
    if (el.closest('button, a[href], label, summary, [role="button"], [role="option"], [role="tab"]')) continue;
    add('click-target', el.tagName + '.' + el.className + ' looks clickable and is not a control');
  }
  // form fields carry what a browser needs to fill them and a person needs to
  // type into them
  for (const el of document.querySelectorAll('input, textarea')) {
    if (!visible(el) || el.matches('[type="checkbox"], [type="radio"], [type="range"], [type="hidden"]')) continue;
    if (!el.getAttribute('autocomplete')) add('autocomplete', (el.name || el.id || el.type) + ' has no autocomplete');
    if (el.matches('[type="number"]') || /^(numeric|decimal)$/.test(el.getAttribute('inputmode') || '')) {
      if (!el.getAttribute('inputmode')) add('inputmode', (el.name || el.id) + ' is numeric with no inputmode');
    }
    const ph = el.getAttribute('placeholder');
    if (ph && !/\u2026$/.test(ph)) add('placeholder', 'placeholder does not end with an ellipsis: ' + ph.slice(0, 30));
    if (el.matches('[type="email"], [type="url"], [name*="code"], [name*="key"]') && el.spellcheck)
      add('spellcheck', (el.name || el.id) + ' should not be spellchecked');
  }
  // an image without its dimensions moves the page when it loads
  for (const img of document.querySelectorAll('img')) {
    if (!img.getAttribute('width') || !img.getAttribute('height')) add('img-size', img.src.slice(-40));
  }
  // zoom is never disabled
  const vp = document.querySelector('meta[name="viewport"]');
  const vpc = vp ? vp.getAttribute('content') || '' : '';
  if (/user-scalable\s*=\s*no|maximum-scale\s*=\s*1(\D|$)/.test(vpc)) add('viewport-zoom', vpc);
  // the theme reaches the browser chrome and the native controls
  if (!document.querySelector('meta[name="theme-color"]')) add('theme-color', 'no theme-color meta');
  const rootScheme = getComputedStyle(document.documentElement).colorScheme;
  if (!rootScheme || rootScheme === 'normal') add('color-scheme', 'the root sets no colour scheme');
  // a long list is virtualized rather than put in the document whole
  for (const body of document.querySelectorAll('tbody')) {
    const rows = body.querySelectorAll('tr').length;
    if (rows > 60) add('virtualize', rows + ' rows rendered in one table');
  }
  // a tap must not wait for a second tap that is not coming
  for (const el of inter.slice(0, 40)) {
    const ta = getComputedStyle(el).touchAction;
    if (el.matches('.btn, .navlink, .tab, .link') && ta === 'auto')
      add('touch-action', (el.className || el.tagName) + ' leaves the double-tap delay in place');
  }
  // outline: none without a focus-visible style: test by focusing each control
  let ringMissing = 0;
  for (const el of inter.slice(0, 80)) {
    if (el.matches('[tabindex="-1"]')) continue;
    el.focus({ preventScroll: true });
    if (document.activeElement !== el) continue;
    const cs = getComputedStyle(el);
    const hasRing = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || (cs.boxShadow && cs.boxShadow !== 'none');
    if (!hasRing) { ringMissing++; if (ringMissing <= 3) add('focus-ring', el.tagName + '.' + el.className); }
  }
  if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
  return out;
}
"""

axe_reports = {}
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for theme in ("light", "dark"):
        for width, height in ((1440, 900), (390, 844)):
            ctx = browser.new_context(viewport={"width": width, "height": height}, color_scheme=theme)
            page = ctx.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            for route in ROUTES:
                page.goto(f"{ROOT}#/{route}", wait_until="networkidle")
                # a hash change is not a load: reload so every route is audited as a
                # reader meets it from a pasted link, with no focus, scroll or state
                # carried over from the route before it
                page.reload(wait_until="networkidle")
                page.wait_for_timeout(300)
                # the first Tab is read on the fresh route, before the audit focuses
                # anything: once a control has been focused and blurred the browser
                # keeps it as the sequential starting point, and Tab would continue
                # from there rather than from the top of the document
                page.keyboard.press("Tab")
                ring = page.evaluate("""() => { const el = document.activeElement; if (!el || el === document.body) return 'none';
                    const cs = getComputedStyle(el); return (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) ? 'ring' : 'no-ring'; }""")
                first_tab = page.evaluate("() => document.activeElement && document.activeElement.className")
                page.evaluate("() => document.activeElement && document.activeElement.blur()")
                res = page.evaluate(AUDIT_JS)
                label = f"{route} {theme} {width}px"
                fails = res["fails"]
                by_rule: dict[str, int] = {}
                for f in fails:
                    by_rule[f.split(":")[0]] = by_rule.get(f.split(":")[0], 0) + 1
                check(f"guideline audit (a) {label}: {res['counts'].get('textNodes', 0)} text nodes, {res['counts'].get('interactive', 0)} controls, "
                      f"{res['counts'].get('headings', 0)} headings, no violations",
                      not fails and not errors, f"{by_rule} e.g. " + "; ".join(fails[:4]) + (f" errors={errors[:1]}" if errors else ""))
                check(f"guideline audit (a) {label}: the first Tab lands on the skip link with a visible ring",
                      ring == "ring" and "skiplink" in str(first_tab), f"{ring} {first_tab}")
                # axe
                page.add_script_tag(content=AXE)
                axe = page.evaluate("""async () => { const r = await axe.run(document, { resultTypes: ['violations'] });
                    return r.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help,
                      targets: v.nodes.slice(0, 3).map((n) => n.target.join(' ')) })); }""")
                serious = [v for v in axe if v["impact"] in ("serious", "critical")]
                axe_reports[label] = axe
                check(f"axe-core (b) {label}: zero serious or critical findings ({len(axe)} total)", not serious,
                      "; ".join(f"{v['id']} ({v['impact']}, {v['nodes']}) {v['targets'][:1]}" for v in serious[:4]))
            ctx.close()
    # the plan intake: what a reader fills in becomes a file, and that file must
    # carry their figures and nothing about how it was made. The producer wrote
    # a note naming the tool into an earlier version, which the surfaces gate
    # then refused at build time.
    pv = browser.new_page(viewport={"width": 1440, "height": 900})
    pv.goto(f"{ROOT}#/plans", wait_until="networkidle")
    pv.wait_for_timeout(500)
    intake = pv.evaluate("""async () => {
      const form = document.querySelector('form');
      if (!form) return {found: false};
      const set = (el, v) => {
        const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement : HTMLInputElement;
        Object.getOwnPropertyDescriptor(proto.prototype, 'value').set.call(el, v);
        el.dispatchEvent(new Event('input', {bubbles: true}));
      };
      let i = 0;
      for (const el of form.querySelectorAll('input, textarea')) {
        if (el.type === 'checkbox' || el.type === 'radio') continue;
        const numeric = el.inputMode === 'numeric' || el.inputMode === 'decimal' || el.type === 'number';
        set(el, numeric ? String(1000 * ++i) : ('Reference profile ' + (++i)));
      }
      form.querySelector('button[type=submit]').click();
      await new Promise((r) => setTimeout(r, 500));
      const a = document.querySelector('a[download]');
      if (!a) return {found: true, produced: false,
                      live: (document.querySelector('[aria-live]') || {}).textContent};
      const text = await (await fetch(a.href)).text();
      return {found: true, produced: true, name: a.getAttribute('download'), text};
    }""")
    check("plan intake: a filled form produces a file for the reader to keep",
          intake.get("produced"), str(intake)[:200])
    _bad_intake = []
    if intake.get("produced"):
        low = intake["text"].lower()
        for token in ("src/", "data/", "docs/", ".py", "entered through", "generated by",
                      "plan_intake", "build_site", "claude"):
            if token in low:
                _bad_intake.append(token)
    check("plan intake: the file carries the reader's figures and nothing about how it was made",
          intake.get("produced") and not _bad_intake, f"tokens found: {_bad_intake}")
    pv.close()

    # the packet's own states: a page with nothing pinned is audited above, and
    # what a reader actually does with it is checked here. The old view printed
    # "2.1 undefined" for a pin, allowed the same row twice, and removed without
    # an undo.
    pk = browser.new_page(viewport={"width": 1440, "height": 900})
    pk.goto(f"{ROOT}#/start", wait_until="networkidle")
    pk.evaluate("""() => localStorage.setItem('tark.pins', JSON.stringify([
      {productKey: 'hl_paf', fundName: 'Hamilton Lane Private Assets Fund', cell: '2.1',
       element: 'Management fee rate and base'},
      {productKey: 'bcred', fundName: 'Blackstone Private Credit Fund', cell: '3.1',
       element: 'Repurchase cadence and cap'}]))""")
    pk.goto(f"{ROOT}#/packet", wait_until="networkidle")
    pk.wait_for_timeout(500)
    pk_text = pk.evaluate("() => document.getElementById('main').innerText")
    check("packet: a pinned row shows the element name of the row, not the cell id alone",
          "Management fee rate and base" in pk_text and "Repurchase cadence and cap" in pk_text
          and "undefined" not in pk_text, pk_text[:160])
    moves = pk.evaluate("""() => [...document.querySelectorAll('button')]
      .map((b) => b.getAttribute('aria-label') || b.textContent.trim())
      .filter((n) => /move (up|down)/i.test(n))""")
    check("packet: reorder is a pair of named buttons per row, each saying which row it moves",
          len(moves) >= 2 and all(any(ch.isdigit() for ch in m) for m in moves), str(moves[:3]))
    removed = pk.evaluate("""async () => {
      const btn = [...document.querySelectorAll('button')].find((b) =>
        /remove/i.test(b.getAttribute('aria-label') || b.textContent));
      if (!btn) return {found: false};
      btn.click();
      await new Promise((r) => setTimeout(r, 400));
      const toast = document.querySelector('.toast');
      const undo = toast && [...toast.querySelectorAll('button')].find((b) => /undo/i.test(b.textContent));
      const afterRemove = JSON.parse(localStorage.getItem('tark.pins') || '[]').length;
      if (undo) undo.click();
      await new Promise((r) => setTimeout(r, 300));
      return {found: true, hadUndo: !!undo, afterRemove,
              afterUndo: JSON.parse(localStorage.getItem('tark.pins') || '[]').length};
    }""")
    check("packet: removing a row offers an undo and the undo puts it back",
          removed.get("found") and removed.get("hadUndo") and removed.get("afterRemove") == 1
          and removed.get("afterUndo") == 2, str(removed))
    pk.evaluate("() => localStorage.removeItem('tark.pins')")
    pk.close()

    # Back restores the previous route and scroll, a filter change preserves focus and scroll: on the design route
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(f"{ROOT}#/design", wait_until="networkidle")
    page.wait_for_timeout(200)
    page.evaluate("() => window.scrollTo(0, 600)")
    page.wait_for_timeout(100)
    page.click("a.navlink[href='#/start']")
    page.wait_for_timeout(200)
    page.go_back()
    page.wait_for_timeout(400)
    back_ok = page.evaluate("() => [location.hash, Math.round(window.scrollY)]")
    check("navigation: Back returns to the previous route with its scroll position", back_ok[0] == "#/design" and abs(back_ok[1] - 600) < 50, str(back_ok))
    # a sort change (a replace) keeps focus and scroll
    btn = page.locator(".tbl .sortbtn").first
    btn.focus()
    page.wait_for_timeout(100)
    before = page.evaluate("() => Math.round(window.scrollY)")
    btn.press("Enter")
    page.wait_for_timeout(200)
    keep = page.evaluate("() => [document.activeElement && document.activeElement.className, Math.round(window.scrollY)]")
    check("navigation: a sort change preserves focus and scroll", keep[0] == "sortbtn" and abs(keep[1] - before) < 5, f"{keep} vs {before}")
    # keyboard: the palette opens with Ctrl K, Esc returns focus
    page.keyboard.press("Control+k")
    page.wait_for_timeout(200)
    check("keyboard: Ctrl K opens the palette with focus in the combobox", page.evaluate("() => document.activeElement && document.activeElement.getAttribute('role')") == "combobox")
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    check("keyboard: Esc closes the palette", page.locator("[role=combobox]").count() == 0)
    # drawer: opens with focus on close, Esc returns focus to the opener
    opener = page.locator("button[aria-label='Open the citation']").first
    opener.focus(); opener.press("Enter")
    page.wait_for_timeout(200)
    check("keyboard: the drawer takes focus and is a labeled dialog",
          page.evaluate("() => { const d = document.querySelector('[role=dialog]'); return !!d && d.contains(document.activeElement) && !!d.getAttribute('aria-labelledby'); }"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    check("keyboard: Esc closes the drawer and returns focus to the opener", page.evaluate("() => document.activeElement && document.activeElement.getAttribute('aria-label')") == "Open the citation")
    # theme toggle sets data-theme and the stored choice survives a reload
    page.locator(".topbar button[aria-label*='theme']").first.click()
    page.wait_for_timeout(100)
    t1 = page.evaluate("() => document.documentElement.dataset.theme")
    page.reload(wait_until="networkidle")
    t2 = page.evaluate("() => document.documentElement.dataset.theme")
    check("theme: the toggle sets data-theme and the choice survives a reload", t1 in ("dark", "light") and t1 == t2, f"{t1} {t2}")
    # reduced motion: durations collapse to zero
    ctx = browser.new_context(reduced_motion="reduce")
    p2 = ctx.new_page(); p2.goto(f"{ROOT}#/design", wait_until="networkidle")
    check("motion: prefers-reduced-motion collapses every duration to 0", p2.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--t-base').trim()") == "0ms")
    ctx.close()
    # (h) the preview subpath serves every route
    p3 = browser.new_page(viewport={"width": 1440, "height": 900})
    sub_err: list[str] = []
    p3.on("pageerror", lambda e: sub_err.append(str(e)))
    bad = []
    for route in ROUTES:
        p3.goto(f"{SUB}#/{route}", wait_until="networkidle")
        p3.wait_for_timeout(200)
        if p3.locator("h1").count() == 0:
            bad.append(route)
    check("preview subpath (h): the build served under /previews/999/ loads every route", not bad and not sub_err, f"{bad} {sub_err[:1]}")
    # (i) the chunks the data adapter reads resolve against the document, so
    # the same build finds them at the site root and under a preview subpath
    # the manifest drives the check, so a chunk added later cannot escape it
    read_chunks = """async () => {
      const base = new URL('data/', document.baseURI).toString();
      const m = await fetch(base + 'manifest.json');
      if (!m.ok) return {base, fatal: 'manifest HTTP ' + m.status};
      const manifest = await m.json();
      const shapes = new Set(Object.values(manifest.shapes));
      const missing = [], wrong = [];
      for (const name of Object.keys(manifest.files)) {
        const r = await fetch(base + name);
        if (!r.ok) { missing.push(name + ' HTTP ' + r.status); continue; }
        const body = await r.json();
        // every chunk that names a shape must name one the manifest declares
        if (body && body.schema && !shapes.has(body.schema)) wrong.push(name + ' ' + body.schema);
      }
      return {base, count: Object.keys(manifest.files).length, missing, wrong,
              manifest_schema: manifest.schema,
              index: (await (await fetch(base + 'index.json')).json()).schema};
    }"""
    at_sub = p3.evaluate(read_chunks)
    p3.goto(f"{ROOT}#/design", wait_until="networkidle")
    at_root = p3.evaluate(read_chunks)
    check("data (i): every chunk the manifest lists resolves against the document at the site root and under the "
          "preview subpath, and every one that names a shape names a declared shape",
          at_root.get("count", 0) > 200 and at_root.get("count") == at_sub.get("count")
          and not at_root.get("missing") and not at_root.get("wrong")
          and not at_sub.get("missing") and not at_sub.get("wrong")
          and at_root.get("manifest_schema") == "tark.chunks.v1" and at_root.get("index") == "tark.index.v1"
          and at_sub["base"].endswith("/previews/999/data/"),
          f"root {str(at_root)[:400]}, preview {str(at_sub)[:200]}")
    # legacy URL redirects
    p3.goto(f"{ROOT}#view=evaluation&plan=plan_tech_media&product=hl_paf", wait_until="networkidle")
    p3.wait_for_timeout(200)
    check("routing: a legacy #view= URL is rewritten to the new route in place",
          p3.evaluate("() => location.hash") == "#/product/hl_paf/record?plan=plan_tech_media")
    browser.close()

httpd.shutdown(); httpd2.shutdown()
shutil.rmtree(sub_root, ignore_errors=True)
if args.axe_out:
    Path(args.axe_out).write_text(json.dumps({"date": date.today().isoformat(), "routes": ROUTES, "reports": axe_reports}, indent=1))
print(f"\n{len(FAILS)} failure(s)." if FAILS else "\nWeb gate passes.")
sys.exit(1 if FAILS else 0)

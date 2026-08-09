# Tark — Investor Demo Runbook

## URLs
- **Primary (new frontend, static):** https://oscargladysz-arch.github.io/fiduciary-demo/
  - Served from the `gh-pages` branch. If the URL 404s, enable Pages once:
    GitHub repo → Settings → Pages → Source: *Deploy from a branch* →
    Branch `gh-pages`, folder `/ (root)` → Save. Propagation ≤ 2 minutes.
- **Legacy (v9 Streamlit):** the existing Streamlit Cloud deploy (auto-redeploys
  from `main` pushes). Keep alive until the new frontend has run one real
  investor meeting; then it may be retired.
- **Local (always works, no network):**
  ```
  cd ~/Projects/fiduciary-demo && source .venv/bin/activate
  python src/build_site.py && python -m http.server 8410 -d site
  # -> http://localhost:8410
  ```
  Streamlit fallback: `streamlit run app.py`.

## Redeploying the frontend
```
source .venv/bin/activate && python src/build_site.py
TMP=$(mktemp -d) && cp -R site/. "$TMP"/ && touch "$TMP"/.nojekyll
git -C "$TMP" init -q -b gh-pages && git -C "$TMP" add -A
git -C "$TMP" commit -q -m "deploy" 
git -C "$TMP" push -f https://github.com/oscargladysz-arch/fiduciary-demo.git gh-pages
```
`site/data.js` and `site/memos/` are BUILD OUTPUTS (gitignored on the code
branches) — regenerate with `python src/build_site.py`; never hand-edit them.
The build refuses to emit the bundle if any plan-sponsor token would leak.

## Reset steps before a demo
1. `git checkout main && git pull`
2. `python src/validate_data.py` (should print "All clean")
3. `python src/build_site.py && python src/test_frontend.py` (full e2e — ~40s)
4. Open the Pages URL, hard-refresh (Cmd+Shift+R) to bust module cache.
5. Land on **Reference Plans** with the tech/media plan selected (default).

## Known rough edges (workbench build)
- Search queries and pins are local (localStorage) by design — they never
  enter URLs; a shared link reproduces configuration, not your query text.
- Palette command grammar is minimal (views, products, plans, cells,
  compare, density) — fuzzy matching is substring-based.
- Saved scenarios are per-browser (no sync — nothing leaves the origin).
- `hl_paf` / `kkr_kpec` / `breit` PME windows move in fiscal-year steps
  (annual disclosure is the honest granularity); only CCLFX has the smooth
  monthly slider.
- Browser module caching: after a redeploy, one hard refresh may be needed.
- Glossary hover-chips need a hover/tap; on touch devices tap the dotted term.
- Zero cells are human-verified yet (CF2 pass outstanding); the UI says so —
  that is a feature, not a gap. Record state: 54% evidenced · 18% computed ·
  27% documented-unavailable · 0 unresolved.

## Fallback plan (in order)
1. Pages URL fails → local `http.server` (step above, 10 seconds).
2. Laptop dies → `docs/screenshots/01…10.png` walk the full 7-minute script.
3. Deep questions on provenance → open `data/evidence/<product>_evidence.csv`
   live: it is the human-verification interface and reads like a ledger.

## What is enforced by machines (say this in the meeting)
- Pre-commit runs 7 gates: data contract, analytics, benchmark engine, memo,
  Streamlit suite, site build (anonymization gate), frontend e2e (240-combo
  render sweep + 4-sponsor anonymization + JS/Python parity).
- No number reaches a surface unless it is in the cited data layer or is
  recomputed live from it; scenario math is always labeled ILLUSTRATIVE.
- `verified` status can only be set by a human editing the evidence CSV.

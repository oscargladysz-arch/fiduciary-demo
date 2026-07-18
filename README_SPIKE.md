# Tark Drop v8 — Increment 6: M5 + M6 + Ship Kit
### Tested live 2026-07-18. The decision memo, the liquidity match, the demo script, and the deploy runbook. This is 8/10, pending your deploy click.

## What's new in v8
1. **`src/tark_memo.py` (M5)** — generates a per-product Word decision memo: rule citation (91 FR 16088), meaningful-benchmark language, six-factor findings table synthesized from the evidence cells, benchmark selection with scoring rationale and the **full rejection log**, the window-sensitivity disclosure, a provenance appendix, signature block. DXYZ gets the **escalation variant**: "no meaningful benchmark constructible — do not proceed," as a filed record. Six memos pre-generated in `data/memos/`; the Benchmark view now has a **Download decision memo** button. Visually verified per the docx skill (rendered to images and inspected).
2. **`src/tark_liquidity.py` (M6)** — the product-to-plan match, three honestly separated layers: wrapper FACTS from cell 3.1 · the STRUCTURAL DIA test (daily 404(c) menus vs quarterly wrappers — names the bridging structures) · an ILLUSTRATIVE scenario (labeled, parameterized, never asserted as fact). Verdicts: BREIT **conditional-weak** (its own gating precedent), DXYZ **aligned-mechanical** (with the premium caveat), the rest **conditional** with capacity headroom shown. New app view **Liquidity Match**; cells 3.7/3.9 now computed with provenance. Coverage: **26%**.
3. **`src/test_memo.py`** — fifth suite: memos exist, carry the rule cite, the PME, the CDLI rejection, the K-1 finding, the escalation — and never the sponsor's name.
4. **Ship kit:** `requirements.txt` · `docs/demo_script.md` (the 7-minute walkthrough with talking beats) · deploy runbook below.

## Install & run
```
cd ~/Projects/fiduciary-demo
unzip -o ~/Downloads/tark_drop_v8.zip -d .
python src/validate_data.py
python src/test_memo.py
python src/test_app.py
streamlit run app.py
```
Walk the new **Liquidity Match** view (cclfx, then breit), then Benchmark → **Download decision memo** and open the docx. Then the hook and the close:
```
cat > .git/hooks/pre-commit << 'HOOK'
#!/bin/sh
source .venv/bin/activate 2>/dev/null
python src/validate_data.py && python src/test_analytics.py && python src/test_benchmark.py && python src/test_memo.py && python src/test_app.py
HOOK
chmod +x .git/hooks/pre-commit
git add -A && git commit -m "increment 6: M5 memo + M6 liquidity match + ship kit" && git push
```

## Deploy (your click, ~5 minutes)
1. share.streamlit.io → sign in with GitHub → **New app**.
2. Repo `oscargladysz-arch/fiduciary-demo`, branch `main`, file `app.py`. (Private repo is fine — grant Streamlit access when prompted.)
3. Advanced settings → Python 3.12 → **Deploy**. The app is self-contained: all data committed, no secrets, no raw filings needed.
4. Smoke-test the live URL against the demo script, all five views, memo download included.

## The scoreboard, honestly
**8/10 on the build plan** once the deploy link is live: all seven acceptance criteria pass — anchor plan · picker · six-factor scorecard with citations · index-agnostic benchmark engine with rejection log · liquidity match · memo export · DXYZ failing loudly — deployed, every number cited or labeled. The remaining two points are not code: practitioner validation of the methodology (Gate C), your §4 hand-worked PME (August), design polish, and six-product extraction depth.

## Standing ledger
Oscar's reads (PAF 2.2 rate + 4.2 · CCLFX/DXYZ auditor lines) · CF2's verification pass (54 seeded cells) + TR-gap check · CF1's FR read + kill-shot watch · **Gate A: July 31 — thirteen days** — and per the roadmap, the August methodology window opens right behind it.

# Tark Drop v7 — Increment 5: M4, the Screens
### Tested live 2026-07-18. The build is now something you can put in front of a human.

## What's new in v7
1. **`app.py` — the demo, four views.** *Anchor Plan*: the real (anonymized) 5500 economics — $565.8M, +24.8% YoY, 5,120 accounts at $110,515 average — with the liquidity-tail callout (1,847 separated-with-balances = 36% of accounts, wired to cell 3.9's story). *Candidate Roster*: six products, six wrappers, live evidence-coverage %. *Six-Factor Evaluation*: the 54 cells in six tabs, status-chipped, every extracted value with its expandable citation (document · section · quote · extracted-by · verified-by). *Benchmark Selection*: primary/secondary cards with KS-PME and Direct Alpha, the full scoring rationale, the **rejection log as a first-class table**, DXYZ's escalation banner, and the window-sensitivity disclosure printed right under the PME — the methodology finding, on screen.
2. **`src/test_app.py` — 61 UI checks via Streamlit AppTest**, headlined by the third truthfulness-class gate of the project: the **anonymization test** — the sponsor's name must appear in *zero* rendered views, every view × every product. The project rule is now machine-enforced.
3. **Validator upgrade (born from your sabotage drill):** extracted/verified cells must carry non-empty `extracted_by` — provenance is part of the record. Your mis-aimed edit found the gap; this closes it.
4. Theme via `.streamlit/config.toml` — no hand-rolled CSS, per the plan.

## Install & run
```
cd ~/Projects/fiduciary-demo
unzip -o ~/Downloads/tark_drop_v7.zip -d .
python src/validate_data.py
python src/test_app.py
streamlit run app.py
```
`test_app.py` executes the app ~50 times — expect 1–2 minutes. Then the streamlit command opens the browser: walk the demo path — **Anchor Plan → Candidate Roster → Six-Factor Evaluation (hl_paf, Fees tab, open the 2.1 source) → Benchmark Selection (cliffwater_cclfx — find CDLI in the rejection log) → Benchmark Selection (dxyz — the escalation)**. Ctrl+C when done.

**Update the hook to all four suites** (the ~90-second pre-commit is the price of the anonymization guarantee):
```
cat > .git/hooks/pre-commit << 'HOOK'
#!/bin/sh
source .venv/bin/activate 2>/dev/null
python src/validate_data.py && python src/test_analytics.py && python src/test_benchmark.py && python src/test_app.py
HOOK
chmod +x .git/hooks/pre-commit
```
Then:
```
git add -A && git commit -m "increment 5: M4 screens + 61 UI tests + anonymization gate" && git push
```

## Open human items
Standing: Oscar's three short reads · CF2's verification pass + CCLFX TR-gap cross-check · **Gate A: July 31 — thirteen days.**

## Next from Claude — Increment 6 (M5 + M6, ship)
The python-docx decision memo (rule language + citations + the rejection log), the product-to-plan liquidity match (CCLFX's 8-quarter repurchase series vs the anchor plan's 1,847-account tail), DXYZ fail path polish, Streamlit Cloud deploy, demo script. Nothing needed to start.

# Tark

Tark evaluates alternative investment products (interval funds, tender-offer
funds, non-traded BDCs and REITs, listed vehicles) as candidate designated
investment alternatives for 401(k) plans, against the six factors of the
Department of Labor's proposed safe harbor, 91 FR 16088 (March 31, 2026,
RIN 1210-AC38, proposed 29 CFR 2550.404a-6, docket EBSA-2026-0166).

Every number on a surface is in the cited data layer or is recomputed live
from it. Every cell carries a status whose tier is never blurred: T1
`structured` (machine-read regulatory data), T2 `extracted-unverified` (AI
extraction with a citation, awaiting a human), T3 `verified` (a human signed
the evidence row). Only a human editing `data/evidence/*.csv` can set
`verified`. Scenario and slider output is labeled ILLUSTRATIVE.

## Layout

- `data/`: the record. `products/*.json` and `evidence/*.csv` (54 cells per
  product, both stores kept equal by the validator), `facts/` (typed
  projections), `plans/` (four anonymized reference plans), `cohorts/`,
  `benchmarks/`, `liquidity/`, `series*/`, `census/` (the T1 universe),
  `citations/` (offline accession resolution), `manifest.csv` (accessions),
  `as_of.json` (record as-of date). Decision memos are build output, one per
  plan and product, generated into `site/memos/` by `src/build_site.py`.
- `src/`: producers (`produce.py` runs them in a fixed order), the engines
  (`tark_analytics.py`, `tark_benchmark.py`, `tark_liquidity.py`,
  `tark_cohort.py`, `tark_memo.py`), the site build (`build_site.py`), the
  validators and gates (`validate_*.py`, `test_*.py`, `corrections_log.py`).
- `site/`: the static frontend. Vanilla JS, hash-routed, reads only the
  bundles the build writes (`data.js`, `series.js`, `census.data.js`,
  `census/`), which are gitignored.
- `docs/`: the audit (`GAP_ANALYSIS_2026-09-03.md`), the decisions log
  (`DECISIONS_2026-09.md`), build reports, the investor runbook
  (`INVESTOR_DEMO.md`), the demo script, the human verification queue and
  the crosscheck report with its generated corrections log.
- `app.py`: the legacy Streamlit surface, kept until the static frontend
  has run one real meeting.

## Setup

```
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp hooks/pre-commit .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
export TARK_SEC_CONTACT='Your Name your@email'   # only for the EDGAR and series fetchers
```

Playwright uses the Chromium the environment provides. Do not run
`playwright install` unless the frontend gate says the browser is missing.

## Commands

```
python src/validate_data.py            # data contract
python src/produce.py                  # regenerate every derived artifact, in order
python src/build_site.py               # write the site bundles (refuses on a sponsor-token leak)
python -m http.server 8410 -d site     # serve the frontend locally
sh hooks/pre-commit                    # every gate, in hook order
```

Producers are deterministic: `TARK_AS_OF` overrides the record as-of date
and `TARK_DATA_DIR` points them at a scratch copy. The freshness gate reruns
them into a scratch copy and fails if a committed artifact differs.

## Rules that the gates enforce

- Nothing sets a cell to `verified`. The invariants gate asserts the count
  is 0 and `verified_by` is empty in this repository.
- No invented number, quote, document name, accession or date. An unsourced
  value is `n/a - <reason>` or `partial`.
- Anonymization of the four reference plans on every surface: the build
  refuses the bundle and the memos on any sponsor token.
- T2 evidence rows are immutable except through an allowlisted correction in
  `docs/crosscheck_report.md`, where every changed published number is
  logged with its old value, new value and cause.
- Gates only grow. An expected value changes only when the audit or a
  recomputation shows the assertion encoded a bug, with the reason in the
  commit.
- No em dash and no semicolon in user-facing copy. Formulas use `*` and `/`.

See `docs/DECISIONS_2026-09.md` for every design decision and
`docs/BUILD_REPORT_6.md` for the state of the remediation.

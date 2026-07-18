# Tark Drop v7.1 — Extraction Pass 2 (data-only mini-drop)
### Tested live 2026-07-18. Coverage 15% → 22%; every product up; DXYZ resurrected; the roster's tax story found.

## What's new
1. **17 new/upgraded cells across all six products**, all cited. Highlights:
   - **The K-1 finding (demo gold):** K-PEC issues **Schedule K-1s** (~75 days after year-end, may be delayed) — per dictionary 6.4, near-disqualifying operationally in DC plans. Meanwhile SPRIM's own prospectus *markets* "Form 1099 DIV or Form 1099-B tax reporting **instead of K-1s**" as a Favorable Structure bullet. The complexity factor's cleanest cross-product contrast, in the funds' own words.
   - K-PEC repurchase caps confirmed: 5.0% of aggregate NAV quarterly. BREIT's 2022–24 gating confirmed in its own risk language ("periods of prorated fulfillment"). BREIT cap-rate rows extracted (Rental Housing 7.2%/5.4%, Industrial 7.5%/5.5%).
   - CCLFX repurchase verbatim: "up to five percent (5%) of its outstanding shares" (N-23C3A) — **one item off Oscar's list.** PAF's stated comparators found (S&P 500 + MSCI World) and wired into the engine profile.
   - **DXYZ 0% → 16%:** 2.00% management fee, 4.53% expense ratio, $438M net assets after the ~$324M 2025 ATM raise, NYSE listing language, Level-3 footnote, and market-value total returns of **+613.45% (2024) then −47.96% (2025)** — the fail case quantified from its own highlights.
   - Two disciplined refusals: DXYZ's "KPMG" hit was the shareholder letter citing KPMG *research*, not the auditor; CCLFX's auditor signature still eluded the regex. Both stay honestly pending rather than wrongly seeded.
2. **New status kind: `computed`** — L3 cells the pipeline has genuinely completed (CCLFX vol/de-smoothing/PME, DXYZ drawdown/price-series, PAF & SPRIM PME) now show :violet[● computed (pipeline)] with provenance pointing at `metrics.json` / the selection JSONs, and count toward coverage. Same validator requirements as extracted: value + source + provenance, no exceptions. This is the honest fix to "why is coverage so low" — some cells were done by code, and the meter now says so.

## Install & run
```
cd ~/Projects/fiduciary-demo
unzip -o ~/Downloads/tark_drop_v7_1.zip -d .
python src/validate_data.py
python src/coverage.py
git add -A && git commit -m "extraction pass 2: +17 cells, computed status, coverage 22%" && git push
```
Expected coverage: breit 20 · cclfx 29 · dxyz 16 · hl_paf 27 · kkr_kpec 18 · stepstone 22 · **TOTAL 22%**. The commit runs the full four-suite hook (~2 min). Then reload the app — the roster and the chips tell the new story.

## The shrunken human list
- **Oscar (three short reads, updated):** PAF incentive-fee **rate** (the structure is now in; the % remains — 486BPOS "Incentive Fee" section) · PAF ASC 820 table (4.2) · CCLFX auditor line (one Cmd+F for "auditor since" in its N-CSR). DXYZ's auditor too if you're in the mood — same Cmd+F.
- **CF2 (now load-bearing):** 42 seeded cells await verification — flip `extracted-unverified` → `verified`; plus the CCLFX TR-gap cross-check.
- **Deliberately still pending, with pointers in the CSVs:** BREIT deduction rate + monthly proration tables · K-PEC early-fee rate + return-table values · SPRIM expense ratios · tax confirmations for paf/cclfx/breit/dxyz.

## Standing
**Gate A: July 31 — thirteen days.** Increment 6 (memo generator + liquidity match + deploy) fires on "go."

# Tark Spike v1 — EDGAR Pipeline + First Evidence Column
### Tested against live EDGAR 2026-07-09. Drop into `~/Projects/fiduciary-demo`, run once, commit.

## What this is
The Phase 0 spike from the roadmap, complete: a working EDGAR fetcher, the verified product registry, and the first real column of the evidence matrix — Hamilton Lane Private Assets Fund, with 9 cells already extracted from its June 2026 annual report and current tender offer.

## Install & run (venv active; `requests` already installed)
```
cd ~/Projects/fiduciary-demo
unzip ~/Downloads/tark_spike_v1.zip
echo "data/raw/" >> .gitignore
python src/fetch_edgar.py --list
python src/fetch_edgar.py hl_paf
git add -A && git commit -m "spike: EDGAR fetcher + HL PAF evidence scaffold" && git push
```
The fetch re-downloads PAF's six documents to your machine (~16MB, a minute or two). Everything else in the zip is committed; raw filings are gitignored and reproducible via `data/manifest.csv`.

## Roster verdicts (verified vs. live EDGAR, 2026-07-09)
| Handoff said | Reality | Verdict |
|---|---|---|
| "Hamilton Lane HLPIF" | No such registrant. The registered HL evergreen is the **Private Assets Fund** (CIK 1803491, tender-offer fund, ~$5.80B) | **hl_paf — IN. Fix the memo's name.** |
| Blackstone BXPE | Files 10-Q + Form D/A only: Reg D private placement, no public prospectus | **OUT** of demo roster |
| (swap) | **StepStone Private Markets** (CIK 1789470): 486BPOS, 424B3, tender offers — data-rich registered peer | **IN (stepstone_spm)** |
| "KKR K-PRIME" | Resolves offshore. SEC-reporting KKR vehicle = **K-PEC** (CIK 1957845, 10-K filer) | **IN (kkr_kpec)** |
| Blackstone BREIT | CIK 1662972, 10-K filer | **IN (breit)** |
| Destiny Tech100 DXYZ | CIK 1843974, listed CEF | **IN (dxyz) — the fail case** |
| Capital Group KKR US Equity+ | Registrant did not resolve cleanly on EDGAR | Slot **OPEN**. Next candidate to verify: **Cliffwater Corporate Lending Fund (CCLFX)** — true Rule 23c-3 interval fund, private credit, adviser publishes the CDLI benchmark |
| BlackRock/Great Gray PE TDF | CIT — no EDGAR by design | Stays the "partnership required" slide |

## What's already extracted (real, cited, awaiting CF2 verification)
Management fee **1.40% on Managed Assets** (the fee-base-includes-leverage trap from dictionary cell 2.1, confirmed in the wild) · incentive-fee drag on NII: 1.45% FY26 / 0.84% FY25 / 1.95% FY24 / 2.52% FY23 · Class I returns 1yr 14.60%, SI 15.36% · NAV/share FY22→FY26: 12.35 → 19.77 · expense limits 1.45%/0.75%/1.00% by class · quarterly tender 5.00% (+2.00% upsize), implying ~$5.80B net assets · 2.00% early repurchase fee · $76.5M credit line · auditor Cohen & Company (not Big-4 — an evaluative datum).
Full provenance in `data/evidence/hl_paf_evidence.csv`; pending cells mapped in `docs/extraction_worksheet.md` (~1 focused hour).

## Next tasks by owner
- **Oscar:** run the commands above; do the extraction hour per the worksheet (5.1, 2.2, 4.2 are the quick wins); send Nick follow-ups per plan.
- **CF2:** the N-CSR Consolidated Schedule of Investments is the named list of PAF's underlying GP funds — that IS your pension-disclosure target list. Then verify every seeded row (flip `extracted-unverified` → `verified`).
- **CF1:** Federal Register Examples read (dictionary v0.9 → v1.0) — start date still owed. New standing watch item below.
- **Claude (next increment):** 2nd + 3rd product pulls (stepstone_spm, dxyz), CCLFX verification for the open slot, Form 5500 anchor-plan pull (blocked on one decision — see chat), benchmark-methodology doc skeleton for the August window.

## Dictionary deltas v0.91 (post BlackRock/Preqin, July 8 2026 announcement)
1. **Cell 5.6 reframed:** from "benchmark suitability memo" to "benchmark SELECTION-AND-JUSTIFICATION engine output." The moat is the defensible choice + documentation, not index construction. M3 design requirement: **index-agnostic** — must ingest third-party indices (Preqin, MSCI-Burgiss, Cliffwater, NCREIF) AND construct custom PME/peer cohorts, then argue and document the selection.
2. **Cell 5.3 upgraded:** Preqin is now a NAMED L2 counterparty with a productized path — their July 8 expansion explicitly offers API and redistribution arrangements for third-party platforms. Future licensing lane, not competitor.
3. **Cells 5.4/5.3 caveat:** Preqin's 140k peer benchmarks are LP-cash-flow DRAWDOWN-fund data; comparability to '40 Act semi-liquid wrappers (NAV-based, our roster) is itself a suitability question the engine must argue — commoditization pressure is real for drawdown cohorts, not yet for our wrapper class, but their spring 2026 private-credit expansion already reached "semi-liquid vehicles." Direction of travel: toward us.
4. **CF1 standing watch (kill-shot shapes):** (a) any Preqin/Aladdin ERISA/DC six-factor module priced for advisors; (b) final rule or *Intel* litigation anointing a specific index family as the "meaningful benchmark" answer; (c) incumbent workflow vendors (RPAG, fi360, Morningstar) shipping a six-factor alt module.

## Standing guardrails (unchanged)
Script fetches, humans extract, CF2 verifies · every number cited or labeled illustrative · no NLP auto-parsing in the spike · discovery outranks code until Gate B · Gate A (equity/OBA/kill criteria) blocks Phase 1 feature code — **July 31**.

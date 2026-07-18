# Tark Spike v2 — Pipeline + 4 Products + Anchor Plan
### Tested against live EDGAR + DOL EBSA data 2026-07-12. Drop into `~/Projects/fiduciary-demo`, run once, commit.

## What's new in v2 (over v1)
1. **Anchor plan locked and extracted** — `data/plans/anchor_plan.json`: real Form 5500 / Schedule H economics for the chosen plan (plan-year 2024): net assets $565.8M (up 24.8% YoY), 5,120 accounts, avg balance $110,515, admin expense ratio 0.098%, 404(c) fully participant-directed (DIA framework squarely applies). Sponsor identity kept in a private field; **display label is "US media/technology company 401(k) plan (~$570M, NY)" — the sponsor name never appears on demo surfaces.**
2. **Roster CLOSED at six** — `cliffwater_cclfx` added to the registry: TRUE Rule 23c-3 interval fund, private credit, ~$28B, adviser publishes the CDLI index (cell 5.3 tie-in).
3. **Fetcher upgrade: `history_sets`** — pulls the N most recent filings of a form as a time series. First use: CCLFX's 8 quarterly N-23C3A repurchase notifications (2024-07 → 2026-05) = cell 3.3 as STRUCTURED DATA, unique among the roster.
4. **Scaffolds for products 2–4** — wrapper-aware evidence CSVs + JSONs for `stepstone_spm`, `dxyz`, `cliffwater_cclfx` (DXYZ's premium/discount cells marked ACTIVE; its tender cells n/a; etc.).
5. **Methodology skeleton** — `docs/benchmark_methodology_skeleton.md`: the section-by-section structure (with formula slots and MUST-ANSWER prompts) for the August design doc. §4's worked PAF example is the Gate C review artifact.

## Install & run (venv active)
```
cd ~/Projects/fiduciary-demo
unzip -o ~/Downloads/tark_spike_v2.zip
python src/fetch_edgar.py hl_paf stepstone_spm dxyz cliffwater_cclfx
git add -A && git commit -m "spike v2: 4 products + cliffwater + anchor plan + methodology skeleton" && git push
```
Heads-up: CCLFX's annual report is 66MB and its holdings file 133MB — that product's fetch takes a minute or two. All raw filings stay gitignored; the manifest (28 rows) makes every pull reproducible.

## Roster — FINAL (6/6)
| Key | Fund | Wrapper | Role |
|---|---|---|---|
| hl_paf | Hamilton Lane Private Assets Fund | tender-offer | seeded first column (9 cells extracted) |
| stepstone_spm | StepStone Private Markets | tender-offer | fresh 2025 base prospectus |
| kkr_kpec | KKR Private Equity Conglomerate | '34 Act non-traded | 10-K data lane |
| breit | Blackstone REIT | '34 Act non-traded REIT | RE + the gating case study |
| cliffwater_cclfx | Cliffwater Corporate Lending Fund | TRUE interval (23c-3) | private credit + structured repurchase series |
| dxyz | Destiny Tech100 | listed CEF | THE FAIL CASE |
Excluded (documented in fetcher): bxpe (Reg D), capital_group_kkr (unresolved), BlackRock/Great Gray TDF (CIT — partnership slide).

## Next tasks by owner
- **Oscar:** run the 4 commands; extraction hour on hl_paf per `docs/extraction_worksheet.md` (5.1, 2.2, 4.2 first); then the same pass on cclfx's latest N-23C3A (repurchase % = ten-minute win).
- **CF2:** PAF N-CSR Schedule of Investments = the underlying-GP target list; verify all seeded hl_paf rows.
- **CF1:** Federal Register Examples read (v0.9 → v1.0) — start date still owed; kill-shot watch per README v1 stands.
- **Claude (queued):** seed-extraction pass on stepstone + cclfx; anchor-plan Streamlit screen comes AFTER Gate A/B per roadmap.

## Standing guardrails
Script fetches, humans extract, CF2 verifies · every number cited or labeled illustrative · anonymize the sponsor on ALL demo surfaces · discovery outranks code until Gate B (Sep 7) · **Gate A (equity / Citi OBA / kill criteria) = July 31.**

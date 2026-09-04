# Tark Demo Script v7, 7 minutes (the advisor workflow)

Setup: reset per `docs/INVESTOR_DEMO.md`. The app lands on the **Screener**
with the tech/media plan selected in the header. Fallback:
`docs/screenshots/after_2026-09/`.

Rule for the speaker: every number below is a record value or a live
recomputation from it, and the table at the end names the surface and the
record location of each one. Read a number off the screen before saying it.
If the screen disagrees with this script, the screen is right and the script
is stale. Coverage counts are read from the Coverage view, never recited.

**0:00, Screener (landing).** "Sixteen products, one plan in the header,
every row a cell from the record or a fact recomputed from it. This is what a
3(21) advisor sees on day one: the candidates, the plan, and the six factors
of the proposed safe harbor, 91 FR 16088, before anyone has formed an
opinion."

**0:40, Six-Factor Evaluation, Hamilton Lane Private Assets Fund (hl_paf).**
Open the Authority panel. "Six factors, paragraphs (g) to (l) of proposed
29 CFR 2550.404a-6, and every cell is chipped with its paragraph. We do not
paraphrase the rule. The panel links the Federal Register document and the
docket, and it says plainly whether the verbatim text has been fetched into
this build or not." Scroll to the fees factor. "Cell 2.1 headline: 1.40% on
managed assets, leverage-inclusive. That is the fee-base trap, and the
headline is the typed fact, not a regex over the prose." Click the cell.
"The drawer: document, section, verbatim quote, the accession, the EDGAR
link, and the status, extracted-unverified. No human has signed this row and
the drawer says so."

**1:40, Fee Matrix.** "Same typed facts, sixteen rows. DXYZ: 2.50% on gross
assets including borrowings. The KKR conglomerate fund (kkr_kpec): Schedule
K-1, the recordkeeper beat. Cliffwater (cliffwater_cclfx): 1.36% net expense
ratio. The '34-Act REIT rows read 'n/a' on the expense line, and the bar
chart lists them under 'no comparable line' with the reason from the record:
no TER line exists for that wrapper, so the matrix refuses to invent one. A
bar appears only where a net expense ratio exists in the record."

**2:30, Benchmark Selection, cliffwater_cclfx.** "Cell 5.1: the fund
expressly declares no benchmark, and the card says so instead of hiding a
placeholder. Rubric v2, twelve points, five criteria, every point traced to a
typed descriptor. Primary: the leave-one-out private-credit peer composite,
10 of 12, KS-PME 0.9756 over FY2021 to FY2025, four overlapping fiscal years,
with the fiscal-year alignment note printed. Secondary: BKLN, 9 of 12, on a
different series, KS-PME 1.2532 over its own window. The ledger: CDLI at 5 of
12, below the threshold of 7, with the reason per criterion printed." Switch
to hl_paf. "Here the fund states the S&P 500 and MSCI World as comparators.
Both are on the card as declared benchmarks, both scored, both fail the
strategy gate at strategy_match 1 of 3. A declaration earns no points by
itself." Switch to arkvx. "And when nothing passes the gate the engine
escalates: no meaningful benchmark constructible, with the required next step
printed. It does not pick the least bad ETF."

**3:45, Liquidity Match, sreit then hl_paf.** "Two layers, never blurred. The
structural verdict reads typed facts only. Starwood REIT: twelve dealings a
year, 0% cap on aggregate NAV, program suspended, gating history yes.
Verdict: misaligned, under all four plans. No plan input can talk it back."
Switch to hl_paf, then switch the header plan from the tech/media plan to the
consulting-alumni plan. "The scenario layer is labeled ILLUSTRATIVE and it
moves with the plan: conditional under the tech plan, conditional-weak under
the consulting plan, because the modeled demand rises against the same 20%
annual capacity, four dealings at 5% of net assets. The structural layer
stays partial, because the record has not established this fund's gating
history, and the card names the missing fact instead of guessing."

**4:45, Advisor inputs.** Back on the Evaluation view, scroll to the
complexity factor. "Cells 6.6 and 6.8 belong to paragraph (l): operational
fit and the fiduciary's own capacity. They are advisor-completed, never
extracted. The form emits a patch file, the status is advisor-stated with its
own badge and its own coverage segment, the memo carries it in its own
section, and it is never counted as evidence."

**5:20, Packet.** "Download the decision memo and the committee packet for
the plan in the header. The file name carries the plan. Sections: the
regulatory basis quoted, six-factor findings as complete sentences with the
typed facts, benchmark selection with the ledger, liquidity match with the
ILLUSTRATIVE scenario, a recommendation section that lists the flags and says
the memo does not decide, the scope sentence that this safe harbor covers
selection and not monitoring, case law at cell 5.7 marked partial, and a
provenance section with the true counts. It says zero verified because zero
are."

**6:00, Verification.** "Tier 1 first, the rows this script just spoke
aloud, each with the spoken-aloud badge. The form beside a row makes the
command for `src/verify_cell.py`, which needs a human signer and a date. The
site writes nothing. The human-verification count on this page is 0 and it
will say 0 until a person signs a row."

**6:30, Universe, close.** "Underneath the sixteen: 3,599 registered wrappers
counted from filing behavior, 241 interval funds, 516 tender CEFs, 378 BDCs,
1,072 non-traded REITs, census as of 2026-08-25, validator-enforced, and
72,502 private pooled funds behind them that a fiduciary cannot see into.
'Evaluate this fund' on any row gives the one command that scaffolds and
extracts the next product under the same contract. Sixteen evaluated, 3,599
counted, zero verified, and the machine's tier and the human's tier never
confused. That is the product."

## Numbers this script speaks, and where each lives

Tier 1 of `docs/verification_queue.md` is derived from the cell rows of this
table. The artifact rows are recomputed by `src/produce.py` and tied across
surfaces by the reconcile gate (`src/reconcile.py`).

| spoken | surface | record location |
|---|---|---|
| 1.40% on managed assets, leverage-inclusive | Evaluation, Fee Matrix | hl_paf cell 2.1 (typed facts mgmt_fee_pct, mgmt_fee_base) |
| 2.50% on gross assets incl. borrowings | Fee Matrix | dxyz cell 2.1 |
| Schedule K-1 | Fee Matrix | kkr_kpec cell 6.4 |
| 1.36% net expense ratio | Fee Matrix, Screener | cliffwater_cclfx cell 2.3 |
| the fund declares no benchmark | Benchmark Selection | cliffwater_cclfx cell 5.1 |
| peer composite 10 of 12, KS-PME 0.9756, FY2021 to FY2025 | Benchmark Selection, Screener, cell 1.8, memo | `data/benchmarks/cliffwater_cclfx_selection.json` |
| BKLN 9 of 12, KS-PME 1.2532 | Benchmark Selection | same artifact, secondary |
| CDLI 5 of 12, rejected | Benchmark Selection ledger | same artifact, rejected list |
| S&P 500 and MSCI World stated, 8 of 12, strategy_match 1 of 3 | Benchmark Selection | hl_paf cell 5.1 and `data/benchmarks/hl_paf_selection.json` |
| no meaningful benchmark constructible | Benchmark Selection | arkvx cell 5.1 and `data/benchmarks/arkvx_selection.json` |
| 12x per year, 0% cap on aggregate NAV, suspended, gating yes, misaligned | Liquidity Match | sreit cells 3.1 and 3.3, `data/liquidity/<plan>__sreit_match.json` |
| 4x per year, 5% of net assets, 20% annual capacity | Liquidity Match | hl_paf cell 3.1, `data/liquidity/<plan>__hl_paf_match.json` |
| conditional under the tech plan, conditional-weak under the consulting plan (ILLUSTRATIVE) | Liquidity Match | hl_paf match files for plan_tech_media and plan_consulting_alumni |
| 3,599 wrappers, 241 / 516 / 378 / 1,072, 72,502 dark, as of 2026-08-25 | Universe | `data/census/census.json`, `data/census/universe.json` (validator-enforced T1) |
| 0 verified | Verification, Coverage, memo provenance | live count over `data/evidence/*.csv` |

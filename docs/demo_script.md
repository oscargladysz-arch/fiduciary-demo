# Tark Demo Script v8, 7 minutes (the advisor workflow)

Setup: reset per `docs/INVESTOR_DEMO.md`. The app lands on the **Screener**
with the tech/media plan selected in the header. Fallback:
`docs/screenshots/after_r2/`.

Rule for the speaker: every number below is a record value or a live
recomputation from it, and the table at the end names the surface and the
record location of each one. Read a number off the screen before saying it.
If the screen disagrees with this script, the screen is right and the script
is stale. Coverage counts are read from the Coverage view, never recited.

What changed from v7 (decision 7.3 in `docs/DECISIONS_2026-09.md`): this
version speaks no peer-composite number. A PME is spoken only against a
public market series and only with its data-source caveat. The Authority
panel is not opened, because the verbatim rule text is not in this build.
The Cliffwater expense figure is named by its basis. The closing table is
re-derived and Tier 1 of `docs/verification_queue.md` is re-derived from it.

**0:00, Screener (landing).** "Sixteen products, one plan in the header,
every row a cell from the record or a fact recomputed from it. This is what a
3(21) advisor sees on day one: the candidates, the plan, and the six factors
of the proposed safe harbor, 91 FR 16088, before anyone has formed an
opinion. Two performance columns, not one: KS-PME against a public proxy
where a public series exists, and the peer relative wealth ratio where the
comparator is a peer composite. They sort separately because they are
different statistics."

**0:40, Six-Factor Evaluation, Hamilton Lane Private Assets Fund (hl_paf).**
"Six factors, paragraphs (g) to (l) of proposed 29 CFR 2550.404a-6, and
every cell is chipped with its paragraph. The Authority panel links the
Federal Register document and the docket, and it says that the verbatim text
of the paragraphs is not yet in this build. We do not paraphrase the rule, so
today we leave the panel closed." Scroll to the fees factor. "Cell 2.1
headline: 1.40% on managed assets, leverage-inclusive. That is the fee-base
trap, and the headline is the typed fact, not a regex over the prose." Click
the cell. "The drawer: document, section, verbatim quote, the accession from
the filing manifest, the EDGAR link built from that accession, and the
status, extracted-unverified. No human has signed this row and the drawer
says so."

**1:40, Fee Matrix.** "Same typed facts, sixteen rows. DXYZ: 2.50% on gross
assets including borrowings. The KKR conglomerate fund (kkr_kpec): Schedule
K-1, the recordkeeper beat. Cliffwater (cliffwater_cclfx): 1.36% expense
ratio before waivers, excluding interest expense, 3.31% including interest,
and the label names the basis instead of calling it net. The '34-Act REIT
rows read 'n/a' on the expense line, and the bar chart lists them under 'no
comparable line' with the reason from the record: no TER line exists for
that wrapper, so the matrix refuses to invent one. A bar appears only where
an expense ratio exists in the record."

**2:30, Benchmark Selection, cliffwater_cclfx.** "Cell 5.1: the fund
expressly declares no benchmark, and the card says so instead of hiding a
placeholder. The Tark benchmark rubric, twelve points, five criteria, every
point traced to a typed descriptor. Primary: the leave-one-out private-credit
peer composite, 9 of 12, four members named on the card. Its statistic is a
relative wealth ratio, not a PME, because a peer composite is appraisal-based
and cannot be bought, and the card says so. I am not reading that ratio
aloud today: the alignment note on the card says the members are aligned by
fiscal-year label, and the calendar-aligned recomputation is the next
engineering step. Secondary: BKLN, the senior loan proxy, 9 of 12, KS-PME
1.2532 over 2019-06-05 to 2026-07-17, computed on Yahoo adjusted close,
which approximates NAV total return, and the card names that source beside
the fund return. The ledger: CDLI at 5 of 12, below the threshold of 7, with
the reason per criterion printed, including that the index is published by
the fund's own adviser, which is a fact from the affiliation map and not a
string match." Switch to hl_paf. "Here the fund states the S&P 500 and MSCI
World as comparators. Both are on the card as declared benchmarks, both
scored 8 of 12, both fail the strategy gate at strategy match 1 of 3. A
declaration earns no points by itself." Switch to arkvx. "And when nothing
passes the gate the engine escalates: no meaningful benchmark constructible,
with the required next step printed. It does not pick the least bad ETF."

**3:45, Liquidity Match, sreit then hl_paf.** "Two layers, never blurred.
The structural verdict reads typed facts only and does not move with the
plan. Starwood REIT: repurchases suspended since the April 29, 2026
amendment, 0% cap on aggregate NAV for ordinary requests, gating history
yes. Structural verdict: misaligned, plan-independent. No plan input can
talk it back." Switch to hl_paf, then switch the header plan from the
tech/media plan to the consulting-alumni plan. "The scenario layer is labeled
ILLUSTRATIVE and it moves with the plan: conditional under the tech plan,
conditional-weak under the consulting plan, because the modeled demand rises
from 10.4% to 13.7% of the position per year against the same 20% annual
capacity, quarterly offers at 5% of net assets. The structural layer stays
partial, because the record has not established this fund's gating history,
and the card names the missing fact instead of guessing."

**4:45, Advisor inputs.** Back on the Evaluation view, scroll to the
complexity factor. "Cells 6.6 and 6.8 belong to paragraph (l): operational
fit and the fiduciary's own capacity. They are advisor-completed, never
extracted. The form makes a statement file that the advisor sends to Tark,
the status is advisor-stated with its own badge and its own coverage
segment, the memo carries it in its own section, and it is never counted as
evidence."

**5:20, Packet.** "Download the decision memo and the committee packet for
the plan in the header. The file name carries the plan. Sections: the
regulatory basis with the paragraph numbers and the plain statement that the
verbatim text is not yet in this build, six-factor findings as complete
sentences with the typed facts, benchmark selection with the ledger and the
alignment note, liquidity match with the structural verdict and the
ILLUSTRATIVE scenario, a recommendation section that lists the flags and
says the memo does not decide, case law at cell 5.7 marked partial, and a
provenance section with the true counts. It says zero verified because zero
are."

**6:00, Verification.** "Tier 1 first, the rows this script just spoke
aloud, each with the spoken-aloud badge. The form beside a row makes a
signature request that a named person sends to Tark with a date. The site
writes nothing. The human-verification count on this page is 0 and it will
say 0 until a person signs a row."

**6:30, Universe, then The Funnel, close.** On the Universe view: "Underneath
the sixteen: 3,599 registered wrappers counted from filing behavior, census
as of 2026-08-25, validator-enforced. 'Evaluate this fund' on any row makes
the request that scaffolds and extracts the next product under the same
contract." Switch to The Funnel: "By class: 241 interval funds, 516 tender
CEFs, 378 BDCs, 1,072 non-traded REITs. And behind them, 72,502 private
pooled funds that a fiduciary cannot see into. Sixteen evaluated, 3,599
counted, zero verified, and the machine's tier and the human's tier never
confused. That is the product."

## Numbers this script speaks, and where each lives

Tier 1 of `docs/verification_queue.md` is derived from the cell rows of this
table. The artifact rows are recomputed by the producer chain and tied across
surfaces by the reconcile gate. The peer-composite ratio is deliberately
absent from the spoken column.

| spoken | surface | record location |
|---|---|---|
| 1.40% on managed assets, leverage-inclusive | Evaluation, Fee Matrix | hl_paf cell 2.1 (typed facts mgmt_fee_pct, mgmt_fee_base) |
| accession 0001213900-26-066804, N-CSR filed 2026-06-09, status extracted-unverified | Evaluation drawer | hl_paf cell 2.1 accession column, `data/manifest.csv` row for CIK 1803491 |
| 2.50% on gross assets incl. borrowings | Fee Matrix | dxyz cell 2.1 |
| Schedule K-1 | Fee Matrix | kkr_kpec cell 6.4 |
| 1.36% expense ratio before waivers, excluding interest expense, 3.31% including interest | Fee Matrix, Screener, Evaluation | cliffwater_cclfx cell 2.3 (typed fact expense_ratio_pct with its basis) |
| the fund expressly declares no benchmark | Benchmark Selection | cliffwater_cclfx cell 5.1 |
| peer composite primary, 9 of 12, relative wealth ratio (the ratio itself is not spoken) | Benchmark Selection, cell 5.3 | `data/benchmarks/cliffwater_cclfx_selection.json`, primary |
| BKLN 9 of 12, KS-PME 1.2532, 2019-06-05 to 2026-07-17, Yahoo adjusted close | Benchmark Selection, Screener, cell 1.8, memo | same artifact, secondary |
| CDLI 5 of 12, rejected, affiliated with the fund's adviser | Benchmark Selection ledger | same artifact, rejected list, and the affiliation map in `data/registry.json` |
| S&P 500 and MSCI World stated, 8 of 12 each, strategy match 1 of 3 | Benchmark Selection | hl_paf cell 5.1 and `data/benchmarks/hl_paf_selection.json` |
| no meaningful benchmark constructible | Benchmark Selection | arkvx cell 5.1 and `data/benchmarks/arkvx_selection.json` |
| repurchases suspended since the April 29, 2026 amendment, 0% cap on aggregate NAV, gating yes, structural verdict misaligned | Liquidity Match | sreit cells 3.1 and 3.3, `data/liquidity/<plan>__sreit_match.json` |
| quarterly offers, 5% per quarter on net assets, 20% per year | Liquidity Match | hl_paf cell 3.1, `data/liquidity/<plan>__hl_paf_match.json` |
| 10.4% then 13.7% of the position per year, conditional then conditional-weak (ILLUSTRATIVE) | Liquidity Match | hl_paf match files for plan_tech_media and plan_consulting_alumni |
| 3,599 wrappers, as of 2026-08-25 | Universe, The Funnel | `data/census/census.json` (validator-enforced T1) |
| 241 / 516 / 378 / 1,072 by class, 72,502 dark | The Funnel | `data/census/census.json`, `data/census/universe.json` (validator-enforced T1) |
| 0 verified | Verification, Coverage, memo provenance | live count over `data/evidence/*.csv` |

## Surface checks

The frontend gate reads the lines below and fails when a text is not on the
named view under the named plan. Format: view | product | plan | text on
screen. The drawer rows name the cell in the plan column. A "-" product means
the view does not depend on the product.

- screener | - | plan_tech_media | KS-PME vs public proxy
- screener | - | plan_tech_media | Peer relative wealth ratio
- evaluation | hl_paf | plan_tech_media | 1.40% on managed assets
- drawer | hl_paf | 2.1 | 0001213900-26-066804
- drawer | hl_paf | 2.1 | extracted · unverified
- fees | - | plan_tech_media | 2.50% on gross assets incl. borrowings
- fees | - | plan_tech_media | Schedule K-1
- fees | - | plan_tech_media | 1.36%
- evaluation | cliffwater_cclfx | plan_tech_media | 1.36% expense ratio, before waivers, excluding interest expense
- benchmarks | cliffwater_cclfx | plan_tech_media | expressly declares no
- benchmarks | cliffwater_cclfx | plan_tech_media | 9/12
- benchmarks | cliffwater_cclfx | plan_tech_media | Relative wealth ratio vs peer composite
- benchmarks | cliffwater_cclfx | plan_tech_media | Not a public market equivalent
- benchmarks | cliffwater_cclfx | plan_tech_media | 1.2532
- benchmarks | cliffwater_cclfx | plan_tech_media | 2019-06-05 to 2026-07-17
- benchmarks | cliffwater_cclfx | plan_tech_media | Yahoo adjusted close
- benchmarks | cliffwater_cclfx | plan_tech_media | 5/12
- benchmarks | cliffwater_cclfx | plan_tech_media | affiliation map
- benchmarks | hl_paf | plan_tech_media | 8/12
- benchmarks | arkvx | plan_tech_media | NO MEANINGFUL BENCHMARK CONSTRUCTIBLE
- liquidity | sreit | plan_tech_media | suspended since the April 29, 2026 amendment
- liquidity | sreit | plan_tech_media | misaligned
- liquidity | hl_paf | plan_tech_media | 5% per quarter, 20% per year
- liquidity | hl_paf | plan_tech_media | 10.4% of the position per year vs 20% annual wrapper capacity
- liquidity | hl_paf | plan_tech_media | conditional
- liquidity | hl_paf | plan_consulting_alumni | 13.7% of the position per year vs 20% annual wrapper capacity
- liquidity | hl_paf | plan_consulting_alumni | conditional-weak
- verification | - | plan_tech_media | spoken aloud
- census | - | plan_tech_media | 3,599
- funnel | - | plan_tech_media | 241
- funnel | - | plan_tech_media | 516
- funnel | - | plan_tech_media | 378
- funnel | - | plan_tech_media | 1,072
- funnel | - | plan_tech_media | 72,502
- census | - | plan_tech_media | 2026-08-25

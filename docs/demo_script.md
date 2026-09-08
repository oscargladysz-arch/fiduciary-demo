# Tark Demo Script v10, 7 minutes (the advisor workflow)

Setup: reset per `docs/INVESTOR_DEMO.md`. The app lands on the **Screener**
with the tech/media plan selected in the header. Fallback:
`docs/screenshots/after_r2/`.

Rule for the speaker: every number below is a record value or a live
recomputation from it, and the table at the end names the surface and the
record location of each one. Read a number off the screen before saying it.
If the screen disagrees with this script, the screen is right and the script
is stale. Coverage counts are read from the Coverage view, never recited.

What changed from v9 (decision 7.29): the verbatim text of paragraphs (g)
to (l) is in the build, fetched from the Federal Register on 2026-09-07, so
the 0:40 beat opens the Authority panel and reads the first words of
paragraph (k) off the screen. What changed from v8 (decisions 7.1, 7.21,
7.24 and 7.27 in `docs/DECISIONS_2026-09.md`): the benchmark card carries two named
comparisons, "Meaningful benchmark (paragraph (k))" and "Peer comparison
(paragraphs (g) and (h))". The peer ratio is now calendar-aligned with n per
period, so v9 speaks it, always with its label and never as a benchmark or a
PME. A PME is spoken only against a public market series and only with its
data-source caveat. Where the meaningful benchmark is a published index the
record does not hold, the card says so and the spoken PME is the reference
comparison, named as such. The liquidity beat starts from the plan's filed
outflow proxy. The Authority panel is opened once, at 0:40, and the speaker
reads the rule text there, never from memory. The closing table is re-derived and Tier 1 of
`docs/verification_queue.md` is re-derived from it.

**0:00, Screener (landing).** "Sixteen products, one plan in the header,
every row a cell from the record or a fact recomputed from it. This is what a
3(21) advisor sees on day one: the candidates, the plan, and the six factors
of the proposed safe harbor, 91 FR 16088, before anyone has formed an
opinion. Two performance columns, not one: KS-PME against a public proxy
where a public series exists, and the peer relative wealth ratio from cell
1.12. They sort separately because they are different statistics, and the
second one is never a benchmark."

**0:40, Six-Factor Evaluation, Hamilton Lane Private Assets Fund (hl_paf).**
"Six factors, paragraphs (g) to (l) of proposed 29 CFR 2550.404a-6, and
every cell is chipped with its paragraph. The Authority panel links the
Federal Register document and the docket, and it quotes the paragraphs
verbatim from the fetched text, the rule paragraph in view and the
Department's examples one click away." Open the panel and read the first
sentence under paragraph (k) off the screen, then close it. "We do not
paraphrase the rule. What you just heard is the Federal Register's text,
hashed in the record." Scroll to the fees factor. "Cell 2.1
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
placeholder. Two comparisons, each named for the paragraph it answers.
Meaningful benchmark, paragraph (k): BKLN, the senior loan proxy, 7 of 10 on
the Tark benchmark rubric, twelve points, five criteria, every point traced
to a typed descriptor. KS-PME 1.2532 over 2019-06-05 to 2026-07-17, computed
on Yahoo adjusted close, which approximates NAV total return, and the card
names that source beside the fund return. The ledger: CDLI, the
strategy-exact index, scores 6 of 10 and is ineligible, because it is
published by the fund's own adviser, a fact from the affiliation map and not
a string match. Peer comparison, paragraphs (g) and (h): the four other
private credit products on identical calendar years, 2021 to 2025, n equals
four in every period, relative wealth ratio 1.0613. That is a history of
similar investments, not a benchmark and not a PME, and the card says so
twice." Switch to hl_paf. "Here the meaningful benchmark is the Cambridge
Associates private equity benchmark, 8 of 10, cited and not held, so the
card shows no number for it and says why. The reference comparison, named as
a reference and not the benchmark, is PSP, the listed private equity proxy,
KS-PME 1.9565 on filed fiscal-year returns. The fund's own S&P 500 and MSCI
World are SEC-required comparators, 6 of 10 each, they fail the strategy
gate at 1 of 3, and each still gets its own comparison on the card. A
comparator earns no points for being named in a filing. The peer comparison
here is formed over the three peers that share the fund's March year end,
FY2023 to FY2026, n equals three in every period, relative wealth ratio
1.0971. The fourth peer reports calendar years and is excluded by name, with
the reason printed, and stays in the side-by-side table." Switch to arkvx. "And
when nothing passes the gate the engine escalates: no meaningful benchmark
constructible, with every candidate scored and the required next step
printed. It does not pick the least bad ETF."

**3:45, Liquidity Match, sreit then hl_paf.** "Two layers, never blurred.
The structural verdict reads typed facts only and does not move with the
plan. Starwood REIT: repurchases suspended since the April 29, 2026
amendment, 0% cap on aggregate NAV for ordinary requests, gating history
yes. Structural verdict: misaligned, plan-independent. No plan input can
talk it back." Switch to hl_paf, then switch the header plan from the
tech/media plan to the consulting-alumni plan. "The scenario layer is labeled
ILLUSTRATIVE and it starts from the plan's own filing: the filed outflow
proxy from Schedule H, total expenses less administrative expenses over
beginning net assets, applied to the position. The tech plan filed 11.7% of
the position per year, the consulting plan 6.5%, both against the same 20%
annual capacity, quarterly offers at 5% of net assets. The sliders are the
stress around that base, so the verdict is conditional-weak under the tech
plan, where the stressed demand of 20.5% crosses the cap, and conditional
under the consulting plan, where it stays at 19.2%. The slider assumption,
10.4% and 13.7%, is printed beside the filed rate and never blended with it.
The structural layer stays partial, because the record has not established
this fund's gating history, and the card names the missing fact instead of
guessing."

**4:45, Advisor inputs.** Back on the Evaluation view, scroll to the
complexity factor. "Cells 6.6 and 6.8 belong to paragraph (l): operational
fit and the fiduciary's own capacity. They are advisor-completed, never
extracted. The form makes a statement file that the advisor sends to Tark,
the status is advisor-stated with its own badge and its own coverage
segment, the record carries it in its own section, and it is never counted as
evidence."

**5:20, Packet.** "Download the Investment Selection Record for the plan
in the header, and the rule text as its attachment. The file name carries
the plan. Page one is the decision summary and the signature block. Then
the regulatory basis with the paragraph numbers and the rule paragraph under
each letter quoted verbatim, the attachment cited by its content hash,
six-factor findings as complete sentences from the facts on record,
benchmark selection with the ledger of every candidate, the rubric defined
once and the alignment note, the liquidity match with the structural verdict
and the ILLUSTRATIVE scenario, the flags and the sentence that the record
does not decide, case law at cell 5.7 marked partial, and provenance grouped
by filing with the true counts. It says zero verified because zero
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
surfaces by the reconcile gate. The peer ratio is spoken with its label
(cell 1.12), never as a benchmark.

| spoken | surface | record location |
|---|---|---|
| 1.40% on managed assets, leverage-inclusive | Evaluation, Fee Matrix | hl_paf cell 2.1 (typed facts mgmt_fee_pct, mgmt_fee_base) |
| accession 0001213900-26-066804, N-CSR filed 2026-06-09, status extracted-unverified | Evaluation drawer | hl_paf cell 2.1 accession column, `data/manifest.csv` row for CIK 1803491 |
| 2.50% on gross assets incl. borrowings | Fee Matrix | dxyz cell 2.1 |
| Schedule K-1 | Fee Matrix | kkr_kpec cell 6.4 |
| 1.36% expense ratio before waivers, excluding interest expense, 3.31% including interest | Fee Matrix, Screener, Evaluation | cliffwater_cclfx cell 2.3 (typed fact expense_ratio_pct with its basis) |
| the fund expressly declares no benchmark | Benchmark Selection | cliffwater_cclfx cell 5.1 |
| meaningful benchmark BKLN 7 of 10, KS-PME 1.2532, 2019-06-05 to 2026-07-17, Yahoo adjusted close | Benchmark Selection, Screener, cell 1.8, memo | `data/benchmarks/cliffwater_cclfx_selection.json`, slot_k |
| CDLI 6 of 10, ineligible, affiliated with the fund's adviser | Benchmark Selection ledger | same artifact, rejected list, and the affiliation map in `data/registry.json` |
| peer comparison 2021 to 2025, n=4, relative wealth ratio 1.0613, not a benchmark, not a PME | Benchmark Selection, cell 1.12, memo | same artifact, slot_g |
| Cambridge PE benchmark 8 of 10, cited, not held, no number, "Meaningful benchmark by descriptor. No comparison until its series is held." | Benchmark Selection | hl_paf cell 5.3 and `data/benchmarks/hl_paf_selection.json`, slot_k |
| peer comparison over the three March-year-end peers, FY2023 to FY2026, n=3, relative wealth ratio 1.0971, KKR excluded by name | Benchmark Selection, cell 1.12, memo | same artifact, slot_g |
| reference comparison PSP, KS-PME 1.9565, filed fiscal-year returns | Benchmark Selection, cell 1.8, memo | same artifact, reference_comparison |
| S&P 500 and MSCI World SEC-required comparators, 6 of 10 each, strategy match 1 of 3 | Benchmark Selection | hl_paf cell 5.1 and the same artifact, declared |
| no meaningful benchmark constructible | Benchmark Selection | arkvx cell 5.1 and `data/benchmarks/arkvx_selection.json` |
| repurchases suspended since the April 29, 2026 amendment, 0% cap on aggregate NAV, gating yes, structural verdict misaligned | Liquidity Match | sreit cells 3.1 and 3.3, `data/liquidity/<plan>__sreit_match.json` |
| quarterly offers, 5% per quarter on net assets, 20% per year | Liquidity Match | hl_paf cell 3.1, `data/liquidity/<plan>__hl_paf_match.json` |
| filed outflow proxy 11.7% then 6.5% of the position per year, stressed 20.5% then 19.2%, conditional-weak then conditional (ILLUSTRATIVE), slider assumption 10.4% and 13.7% beside it | Liquidity Match | hl_paf match files for plan_tech_media and plan_consulting_alumni, and the two plan files' filed outflow blocks |
| 3,599 wrappers, as of 2026-08-25 | Universe, The Funnel | `data/census/census.json` (validator-enforced T1) |
| 241 / 516 / 378 / 1,072 by class, 72,502 dark | The Funnel | `data/census/census.json`, `data/census/universe.json` (validator-enforced T1) |
| 0 verified | Verification, Coverage, memo provenance | live count over `data/evidence/*.csv` |

## Surface checks

The frontend gate reads the lines below and fails when a text is not on the
named view under the named plan. Format: view | product | plan | text on
screen. The drawer rows name the cell in the plan column. A "-" product means
the view does not depend on the product.

- screener | - | plan_tech_media | KS-PME vs reference proxy
- screener | - | plan_tech_media | Peer relative wealth ratio (cell 1.12)
- evaluation | hl_paf | plan_tech_media | 1.40% on managed assets
- drawer | hl_paf | 2.1 | 0001213900-26-066804
- drawer | hl_paf | 2.1 | extracted · unverified
- fees | - | plan_tech_media | 2.50% on gross assets incl. borrowings
- fees | - | plan_tech_media | Schedule K-1
- fees | - | plan_tech_media | 1.36%
- evaluation | cliffwater_cclfx | plan_tech_media | 1.36% expense ratio, before waivers, excluding interest expense
- benchmarks | cliffwater_cclfx | plan_tech_media | expressly declares no
- benchmarks | cliffwater_cclfx | plan_tech_media | Meaningful benchmark (paragraph (k))
- benchmarks | cliffwater_cclfx | plan_tech_media | 7 of 10
- benchmarks | cliffwater_cclfx | plan_tech_media | 1.2532
- benchmarks | cliffwater_cclfx | plan_tech_media | 2019-06-05 to 2026-07-17
- benchmarks | cliffwater_cclfx | plan_tech_media | Yahoo adjusted close
- benchmarks | cliffwater_cclfx | plan_tech_media | 6 of 10
- benchmarks | cliffwater_cclfx | plan_tech_media | affiliated provider
- benchmarks | cliffwater_cclfx | plan_tech_media | Peer comparison (paragraphs (g) and (h))
- benchmarks | cliffwater_cclfx | plan_tech_media | Relative wealth ratio vs peer composite
- benchmarks | cliffwater_cclfx | plan_tech_media | 1.0613
- benchmarks | cliffwater_cclfx | plan_tech_media | 2021 to 2025
- benchmarks | cliffwater_cclfx | plan_tech_media | Never a benchmark and never a PME
- benchmarks | hl_paf | plan_tech_media | 8 of 10
- benchmarks | hl_paf | plan_tech_media | No comparison until its series is held
- benchmarks | hl_paf | plan_tech_media | Reference comparison, not the meaningful benchmark
- benchmarks | hl_paf | plan_tech_media | 1.9565
- benchmarks | hl_paf | plan_tech_media | SEC-required comparator
- benchmarks | hl_paf | plan_tech_media | 1.0971
- benchmarks | hl_paf | plan_tech_media | FY2023 to FY2026
- benchmarks | hl_paf | plan_tech_media | excluded from the composite
- benchmarks | arkvx | plan_tech_media | NO MEANINGFUL BENCHMARK CONSTRUCTIBLE
- liquidity | sreit | plan_tech_media | suspended since the April 29, 2026 amendment
- liquidity | sreit | plan_tech_media | misaligned
- liquidity | hl_paf | plan_tech_media | 5% per quarter, 20% per year
- liquidity | hl_paf | plan_tech_media | 11.7% of the position per year vs 20% annual wrapper capacity
- liquidity | hl_paf | plan_tech_media | 10.4% of the position per year vs 20% annual wrapper capacity
- liquidity | hl_paf | plan_tech_media | 20.5% vs 20%
- liquidity | hl_paf | plan_tech_media | Scenario verdict: CONDITIONAL-WEAK
- liquidity | hl_paf | plan_consulting_alumni | 6.5% of the position per year vs 20% annual wrapper capacity
- liquidity | hl_paf | plan_consulting_alumni | 13.7% of the position per year vs 20% annual wrapper capacity
- liquidity | hl_paf | plan_consulting_alumni | 19.2% vs 20%
- liquidity | hl_paf | plan_consulting_alumni | Scenario verdict: CONDITIONAL ILLUSTRATIVE
- verification | - | plan_tech_media | spoken aloud
- census | - | plan_tech_media | 3,599
- funnel | - | plan_tech_media | 241
- funnel | - | plan_tech_media | 516
- funnel | - | plan_tech_media | 378
- funnel | - | plan_tech_media | 1,072
- funnel | - | plan_tech_media | 72,502
- census | - | plan_tech_media | 2026-08-25

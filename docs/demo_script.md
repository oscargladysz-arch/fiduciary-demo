# Tark Demo Script v11, 7 minutes (the adviser workflow)

Setup: reset per `docs/INVESTOR_DEMO.md`. The app lands on **Start** with the
tech/media plan selected. Fallback: `docs/screenshots/after_r3/`.

Rule for the speaker: every number below is a record value or a live
recomputation from it, and the table at the end names the surface and the
record location of each one. Read a number off the screen before saying it.
If the screen disagrees with this script, the screen is right and the script
is stale. Coverage counts are read from the Coverage route, never recited.

What changed from v10: the frontend was rebuilt (R3-P1), so every beat names
a route rather than a view of the old application. Start is new and the
script opens there, because it is what an adviser meets. The fee matrix is a
preset of the Screener rather than a route of its own. The price-versus-value
exhibit is inside the record of the fund it describes. The rule text is
behind a control in the top bar of every route rather than a panel that
followed the reader around. Every number in the closing table is unchanged:
the record did not move, the surfaces did.

**0:00, Start.** "This is what a 3(21) adviser sees on day one. Three things
to do: evaluate a fund for a plan, compare candidates, produce the committee
document. One plan selected, in the header, and the panels that depend on it
say so. Underneath: the counts. Sixteen funds evaluated on the same record,
594 of 685 answerable rows resolved, 407 with a filing behind them, and zero
signed by a person. That last number is the honest one and it is on the
first screen." Open the rule control in the top bar. "The rule this record
maps to is 91 FR 16088, proposed 29 CFR 2550.404a-6, paragraphs (g) to (l),
and the panel quotes them verbatim from the Federal Register with the
fingerprint of what was read. We do not paraphrase a rule. A paraphrase of a
rule is a claim about the rule." Read the first sentence under paragraph (k)
off the screen, then close it.

**0:50, Screener.** "Sixteen funds, nineteen facts, each one read the same
way. Two performance columns, not one: the public market equivalent against
a reference proxy where a public series exists, and the peer relative wealth
ratio. They sort separately because they are different statistics, and the
second one is never a benchmark. Every figure has the filing it came from one
click away, and a figure the record does not hold prints the reason instead
of a dash." Click "Show fees only". "The same table as a fee view: the rate,
and beside it the base it is charged on, because a fee is only comparable
against its base. DXYZ: 2.50% on gross assets including borrowings. The KKR
conglomerate fund: Schedule K-1, the recordkeeper beat. Cliffwater: 1.36%
before waivers, excluding interest expense."

**1:40, the record, Hamilton Lane Private Assets Fund.** "Six factors,
paragraphs (g) to (l), fifty-five rows. Each row leads with what it found,
and the full text and its provenance are one disclosure away rather than
filling the page. Cell 2.1: 1.40% on managed assets, leverage-inclusive.
That is the fee-base trap, and the headline is the fact the record typed, not
a pattern matched over prose." Open the source. "The document, the section,
the sentence itself, who read it, whether anyone has signed it, and a link to
the filing on EDGAR built from the accession in the manifest. The status is
extracted, not verified, and the drawer says so."

**2:30, the benchmark panel, Cliffwater Corporate Lending Fund.** "Cell 5.1:
the fund expressly declares no benchmark, and the card says so instead of
hiding a placeholder. Two comparisons, each named for the paragraph it
answers. Meaningful benchmark, paragraph (k): the senior loan proxy, 7 of 10
on the rubric, and the criteria are behind a disclosure with each one
defined. Public market equivalent 1.2532 over 2019-06-05 to 2026-07-17, on
Yahoo adjusted close, which approximates NAV total return, and the panel
names that source beside the figure. The ledger: the strategy-exact index
scores 6 of 10 and is not eligible at any score, because its publisher is
tied to one of the fund's own advisers, which is a fact from the affiliation
map and not a string match. Peer comparison, paragraphs (g) and (h): the four
other private credit funds on identical calendar years, 2021 to 2025, four in
every period, relative wealth ratio 1.0613. That is a history of similar
investments, not a benchmark and not a public market equivalent, and the
panel says so." Switch to Hamilton Lane. "Here the meaningful benchmark is a
published private equity benchmark, 8 of 10, cited and not held, so the card
shows no number for it and says why. The reference comparison, labelled a
reference and not the benchmark, is the listed private equity proxy, public
market equivalent 1.9565 on filed fiscal-year returns. The fund's own S&P 500
and MSCI World are SEC-required comparators, 6 of 10 each, and each fails the
strategy gate at 1 of 3. A comparator earns no points for being named in a
filing." Switch to ARK Venture. "And when nothing passes, the engine
escalates: no meaningful benchmark constructible, every candidate scored, the
next step printed. It does not pick the least bad exchange-traded fund."

**3:45, the liquidity panel, Starwood REIT then Hamilton Lane.** "Two layers,
never blurred. The structural verdict reads the dealing terms and does not
move with the plan. Starwood: repurchases suspended since the April 29, 2026
amendment, a 0% cap for ordinary requests, gating history on record.
Structural verdict misaligned, plan-independent. No plan input talks it back."
Switch to Hamilton Lane, then change the plan to the consulting-alumni plan.
"The scenario layer is marked illustrative and starts from the plan's own
filing: the filed outflow proxy from Schedule H, total expenses less
administrative expenses over beginning net assets. The tech plan filed 11.7%
of the position a year, the consulting plan 6.5%, both against the same 20%
yearly capacity, quarterly offers at 5% of net assets." Move the allocation
control. "Every figure on the page moves together, because there is one live
state behind all of them. Underneath, unedited, are the record's own
sentences at the filed inputs, which is what the document for this plan
prints, so a committee can match the two line by line."

**4:45, adviser inputs.** Back on the record, open the complexity factor.
"Cells 6.6 and 6.8 belong to paragraph (l): operational fit and the
fiduciary's own capacity. They are adviser inputs, never extracted. The form
writes a statement file the adviser sends in, the row carries one chip that
says adviser input, and it is never counted as evidence."

**5:20, the documents panel.** "The Investment Selection Record for the fund
and the plan in the header, and the rule text as its attachment, both real
downloads with their sizes. Page one is the decision summary and the
signature block. Then the regulatory basis with each paragraph quoted
verbatim, the attachment cited by its content fingerprint, the six-factor
findings as complete sentences, the benchmark selection with the ledger of
every candidate, the liquidity match with both layers, the flags, and
provenance grouped by filing with the true counts. It says zero signed
because zero are."

**6:00, Verification.** "Tier one first, the rows this script just spoke, in
the order the queue sets. The form beside a row writes a signature request
that a named person sends in with a date. There is no control on this page
that marks a row verified, because a person does that outside this page. The
count is 0 and it will say 0 until somebody signs."

**6:30, Universe, then the funnel, close.** On Universe: "Underneath the
sixteen: 3,599 registered wrappers counted from filing behaviour, as of
2026-08-25. Every filter is in the address, every entity opens its own
provenance, and every accession links to the filing." Switch to the funnel:
"By class: 241 interval funds, 516 tender-offer closed-end funds, 378
business development companies, 1,072 non-traded real estate trusts. And
behind them, 72,502 private pooled funds a fiduciary cannot see into. Sixteen
evaluated, 3,599 counted, zero signed, and the machine's tier and the human's
tier never confused. That is the product."

## Numbers this script speaks, and where each lives

Tier 1 of `docs/verification_queue.md` is derived from the cell rows of this
table. The artifact rows are recomputed by the producer chain and tied across
surfaces by the reconcile gate. The peer ratio is spoken with its label
(cell 1.12), never as a benchmark.

| spoken | surface | record location |
|---|---|---|
| 1.40% on managed assets, leverage-inclusive | record, Screener | hl_paf cell 2.1 (typed facts mgmt_fee_pct, mgmt_fee_base) |
| accession 0001213900-26-066804, N-CSR filed 2026-06-09, status extracted | citation drawer | hl_paf cell 2.1 accession column, `data/manifest.csv` row for CIK 1803491 |
| 2.50% on gross assets incl. borrowings | Screener, fees preset | dxyz cell 2.1 |
| Schedule K-1 | Screener, fees preset | kkr_kpec cell 6.4 |
| 1.36% expense ratio before waivers, excluding interest expense, 3.31% including interest | Screener, record | cliffwater_cclfx cell 2.3 (typed fact expense_ratio_pct with its basis) |
| the fund expressly declares no benchmark | benchmark panel | cliffwater_cclfx cell 5.1 |
| meaningful benchmark 7 of 10, public market equivalent 1.2532, 2019-06-05 to 2026-07-17, Yahoo adjusted close | benchmark panel, Screener, cell 1.8, document | `data/benchmarks/cliffwater_cclfx_selection.json`, slot_k |
| the strategy-exact index 6 of 10, not eligible, publisher tied to an adviser of the fund | benchmark panel ledger | same artifact, rejected list, and the affiliation map in `data/registry.json` |
| peer comparison 2021 to 2025, four per period, relative wealth ratio 1.0613, not a benchmark | benchmark panel, cell 1.12, document | same artifact, slot_g |
| published private equity benchmark 8 of 10, cited, not held, no number | benchmark panel | hl_paf cell 5.3 and `data/benchmarks/hl_paf_selection.json`, slot_k |
| peer comparison over the three March-year-end peers, FY2023 to FY2026, three per period, relative wealth ratio 1.0971 | benchmark panel, cell 1.12, document | same artifact, slot_g |
| reference comparison, public market equivalent 1.9565, filed fiscal-year returns | benchmark panel, cell 1.8, document | same artifact, reference_comparison |
| S&P 500 and MSCI World SEC-required comparators, 6 of 10 each, strategy match 1 of 3 | benchmark panel | hl_paf cell 5.1 and the same artifact, declared |
| no meaningful benchmark constructible | benchmark panel | arkvx cell 5.1 and `data/benchmarks/arkvx_selection.json` |
| repurchases suspended since the April 29, 2026 amendment, 0% cap, structural verdict misaligned | liquidity panel | sreit cells 3.1 and 3.3, `data/liquidity/<plan>__sreit_match.json` |
| quarterly offers, 5% per quarter on net assets, 20% per year | liquidity panel | hl_paf cell 3.1, `data/liquidity/<plan>__hl_paf_match.json` |
| filed outflow proxy 11.7% then 6.5% of the position a year | liquidity panel | hl_paf match files for plan_tech_media and plan_consulting_alumni |
| 594 of 685 resolved, 407 cited, 0 signed | Start, Coverage | live over `data/products/*.json` and `data/evidence/*.csv` |
| 3,599 wrappers, as of 2026-08-25 | Universe, funnel | `data/census/census.json` (validator-enforced T1) |
| 241 / 516 / 378 / 1,072 by class, 72,502 dark | funnel | `data/census/census.json`, `data/census/universe.json` (validator-enforced T1) |
| 0 verified | Verification, Coverage, document provenance | live count over `data/evidence/*.csv` |

## Surface checks

The web gate reads the lines below and fails when a text is not on the named
route under the named plan. Format: route | product | plan | text on screen.
A "-" product means the route does not depend on a product. A route may
carry the state it is read in, as `record?factor=2` does. Every disclosure
on the route is opened before the text is looked for, because text a reader
can reach is text on the page.

- screener | - | plan_tech_media | Public market equivalent vs the reference proxy
- screener | - | plan_tech_media | Growth against the peer group
- screener | - | plan_tech_media | 2.50%
- screener | - | plan_tech_media | K-1
- record?factor=2 | hl_paf | plan_tech_media | 1.40% on managed assets
- record?factor=2 | hl_paf | plan_tech_media | Extracted
- record?factor=2 | cliffwater_cclfx | plan_tech_media | 1.36%
- benchmark | cliffwater_cclfx | plan_tech_media | Meaningful benchmark (paragraph (k))
- benchmark | cliffwater_cclfx | plan_tech_media | 7 of 10
- benchmark | cliffwater_cclfx | plan_tech_media | 1.2532
- benchmark | cliffwater_cclfx | plan_tech_media | 2019-06-05 to 2026-07-17
- benchmark | cliffwater_cclfx | plan_tech_media | Yahoo adjusted close
- benchmark | cliffwater_cclfx | plan_tech_media | 6 of 10
- benchmark | cliffwater_cclfx | plan_tech_media | Relative wealth ratio
- benchmark | cliffwater_cclfx | plan_tech_media | 1.0613
- benchmark | cliffwater_cclfx | plan_tech_media | 2021 to 2025
- benchmark | hl_paf | plan_tech_media | 8 of 10
- benchmark | hl_paf | plan_tech_media | 1.9565
- benchmark | hl_paf | plan_tech_media | 1.0971
- benchmark | hl_paf | plan_tech_media | FY2023 to FY2026
- liquidity | sreit | plan_tech_media | Misaligned
- liquidity | hl_paf | plan_tech_media | 11.7
- liquidity | hl_paf | plan_consulting_alumni | 6.5
- coverage | - | plan_tech_media | 594
- coverage | - | plan_tech_media | 685
- verification | - | plan_tech_media | pending
- universe | - | plan_tech_media | 3,599
- funnel | - | plan_tech_media | 3,599
- funnel | - | plan_tech_media | 241
- funnel | - | plan_tech_media | 516
- funnel | - | plan_tech_media | 378
- funnel | - | plan_tech_media | 1,072
- start | - | plan_tech_media | 594
- start | - | plan_tech_media | 407

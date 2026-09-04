# Benchmark selection methodology

Status: written section by section as the P1 remediation lands
(2026-09). Sections 1 to 3 describe the engine as committed. Sections 4
to 10 were written before any rubric code changed (P1-B preparation) and
commit the engine to an expected outcome per product that the gates then
assert. `docs/benchmark_methodology_skeleton.md` is the 2026-08 question
list this document answers.

Notation: `*` for multiplication, `/` for division. Every number quoted
here is recomputed by `src/tark_benchmark.py` from `data/` and asserted by
`src/test_benchmark.py`. Regulatory text is quoted only from
`data/authority/` once it has been fetched into the build. Until then the
surfaces say so and no rule language is paraphrased here.

## 1. The comparison window

A fund is compared with a candidate over the effective window: the fund's
own window clipped to the candidate series' coverage.

- Daily NAV series (cliffwater_cclfx, pflex, cion_ares, arkvx): the
  intersection of the two date ranges, on both sides.
- Annual return lists (amg_pantheon, ares_pmf, bcred, ocic, breit, sreit,
  hl_paf): whole fiscal years only. A fiscal year counts when it starts on
  or after the candidate series' first date and ends on or before its last
  date. Fiscal year i runs from the window start with the year advanced by
  i to the next such date, the last one ending on the window end.
- A single disclosed annualized figure (kkr_kpec's inception-to-date
  return, stepstone_spm's five-year figure) is never interpolated over a
  shorter window. When its span lies outside the candidate's coverage the
  slot says "comparison not computable on held data" with the reason.

One anchor. Fund growth, index growth and the flows inside the PME all read
the level on or before each window date from the full series. A window
that starts on a Saturday or a holiday therefore anchors at the last
observation before it, on both sides. The identity
`KS-PME = fund growth / index growth` holds on every two-point comparison
and is asserted.

Every held proxy series is an investable ETF's Yahoo adjusted close, a
total-return proxy for its index family (SPY, URTH, BKLN, PSP, VNQ).
Fund series are the fund's own Yahoo adjusted close where a class ticker
exists (approximates NAV total return with distributions reinvested) or
the raw daily close where the fund is exchange-traded (a market price,
labeled as such and never benchmarked as a portfolio). Every chart that
draws one of these series prints that label beside it, from one map in
the bundle built from `data/series/series_manifest.json`.

The card, the lab, the memo and the Streamlit view print the effective
window and, when it differs from the fund's own, the clip note ("proxy
series begins 2018-07-18"). Every held proxy series runs 2018-07-18 to
2026-07-17 because `src/fetch_series.py` pulled eight years on that day.
Refetching the proxies over a longer window widens the effective windows
and the gates relog the numbers.

## 2. Annualization

`fund_ann_pct` and `index_ann_pct` are `growth ** (1 / years) - 1` with
`years` the actual/365.25 day count of the effective window, the same
clock as Direct Alpha and the JS lab. A disclosed annualized figure keeps
its disclosed span, so the fund side prints the filing's number and the
index side is annualized over the same span.

## 3. Flows, KS-PME and Direct Alpha

The primary comparison is two-point: one contribution of 1.0 at the
window start and one valuation of `fund growth` at the window end.

- KS-PME (Kaplan and Schoar) future-values every flow to the final date
  at the index's growth and divides the value of distributions plus
  terminal value by the value of contributions:
  `KS-PME = sum(positive flows * I_T / I_t) / sum(-negative flows * I_T / I_t)`.
  With two flows this is `fund growth / index growth`.
- Direct Alpha (Gredil, Griffiths and Stucke) is the IRR of the same
  flows after each has been future-valued at the index. It is the
  annualized form of the same two-point comparison, not a second piece
  of evidence.

For daily NAV products a second row, `ks_pme_monthly_schedule`, is
computed and labeled ILLUSTRATIVE wherever it appears: one unit of cash at
the window start and at each fund month-end strictly inside the window,
each buying `1 / NAV` units, all valued once at the window end. It shows
how the verdict would read for a participant contributing steadily rather
than once. It is a schedule assumption, not a fact about the fund, and the
two-point figure stays primary on the card, in the memo and in the rubric.
Annual-tier products have no such row because no intra-year NAV path is
on record.

Every figure in this section is window-sensitive on appraisal-lagged NAVs
and can be smoothing-flattered. The Analysis Lab recomputes all of them
on any held proxy and any window start, with the same code path as the
engine (parity is asserted by the frontend gate).

## 4. What the rubric reads: typed descriptors

The v2 rubric scores a product against a candidate from typed descriptors,
never from an integer typed on a menu entry. The descriptors below come
from the record (the cell in brackets) and move into `data/registry.json`
with their citations in P1-7. Until then the cohort files hold the
strategy tags and this table is the design.

| product | asset class / sub-strategy | wrapper, pricing, NAV cadence [4.1] | dealing [3.1, 3.3] | leverage regime | held return data [1.1, 1.2] | declared benchmark [5.1] |
|---|---|---|---|---|---|---|
| cliffwater_cclfx | private credit / direct lending | interval fund, NAV, daily | quarterly, 5% cap | 1940-Act asset coverage | daily NAV series | none (expressly declares no benchmark) |
| pflex | private credit / multi-sector credit | interval fund, NAV, daily | quarterly, 5% cap | 1940-Act asset coverage | daily NAV series | none (documented absence) |
| cion_ares | private credit / diversified credit | interval fund, NAV, daily | quarterly, 5% cap | 1940-Act asset coverage | daily NAV series | Credit Suisse Leveraged Loan Index |
| bcred | private credit / direct lending | non-traded BDC, NAV, monthly | quarterly, 5% cap | BDC 150% asset coverage | annual returns 2021 to 2025 | none |
| ocic | private credit / direct lending | non-traded BDC, NAV, monthly (quarterly valuation) | quarterly, 5% cap | BDC 150% asset coverage | annual returns 2021 to 2025 | none (cell partial) |
| hl_paf | private equity / evergreen secondaries and directs | tender-offer fund, NAV, monthly | quarterly, 5% cap | 1940-Act asset coverage | annual returns FY2022 to FY2026 | S&P 500 and MSCI World comparators |
| stepstone_spm | private equity / evergreen secondaries-led | tender-offer fund, NAV, monthly | quarterly, 5% cap | 1940-Act asset coverage | five-year annualized figure, FY2021 to FY2026 | MSCI World |
| ares_pmf | private equity / evergreen secondaries-led | tender-offer fund, NAV, monthly | quarterly (cap not typed) | 1940-Act asset coverage | annual returns FY2023 to FY2026 | MSCI World |
| amg_pantheon | private equity / evergreen fund of funds | tender-offer LLC, NAV, monthly | quarterly, 5% cap | 1940-Act asset coverage | annual returns FY2017 to FY2026 | MSCI World |
| kkr_kpec | private equity / conglomerate of controlled businesses | '34-Act LLC, NAV, monthly | quarterly, 5% cap | '34-Act (no asset-coverage rule) | inception-to-date annualized, 2023-09 to 2025-12 | none |
| breit | real estate / core-plus non-traded | non-traded REIT, NAV, monthly | monthly, 2% monthly and 5% quarterly caps | REIT leverage | annual returns 2023 to 2025 | none |
| sreit | real estate / non-traded | non-traded REIT, NAV, monthly | suspended | REIT leverage | one annual return, 2025 | none |
| jll_ipt | real estate / core non-traded | non-traded REIT, NAV, daily | daily dealing, quarterly 5% cap | REIT leverage | none computable (per-class ranges only, P1-13) | NFI-ODCE |
| dxyz | venture / pre-IPO holdings in a listed CEF | listed CEF, market price, daily | exchange | 1940-Act asset coverage | daily market price (premium-driven) | NASDAQ Composite |
| ssss | venture / late-stage growth in a listed BDC | listed BDC, market price, daily | exchange | BDC 150% asset coverage | daily market price (discount-driven) | S&P 500, with a no-suitable-benchmark disclaimer |
| arkvx | venture / venture and growth in an interval fund | interval fund, NAV, daily | quarterly, 5% cap | 1940-Act asset coverage | daily NAV series | none in the prospectus |

| candidate | asset class / sub-strategy | listed | data held | provider | lane |
|---|---|---|---|---|---|
| bkln | public credit / broadly syndicated loans | ETF | daily | Invesco, Morningstar LSTA index family | B |
| cdli | private credit / direct lending index | no | cited, not held | Cliffwater (the adviser of cliffwater_cclfx) | B |
| peer_credit | private credit / the cohort's other members | no | annual, constructed from filings | Tark cohort engine | C |
| psp | private equity / listed private equity | ETF | daily | Invesco, Red Rocks index | B |
| urth | public equity / MSCI World | ETF | daily | iShares, MSCI | B, A where declared |
| spy | public equity / S&P 500 | ETF | daily | SPDR, S&P DJI | B, A where declared |
| cambridge_pe, cambridge_re | private equity or real estate / benchmark indices | no | licensed, not held | Cambridge Associates | B |
| peer_evergreen, peer_kpec | private equity / the cohort's other members | no | annual, constructed from filings | Tark cohort engine | C |
| vnq | real estate / listed REITs | ETF | daily | Vanguard, MSCI US REIT | B |
| odce | real estate / open-end core funds | no | cited, not held | NCREIF | B, A for jll_ipt |
| peer_reit | real estate / the cohort's other members | no | refused (two members after leave-one-out) | Tark cohort engine | C |
| csll | public credit / leveraged loans | no | cited, not held | Credit Suisse (UBS) | A for cion_ares |
| nasdaq_comp | public equity / NASDAQ Composite | no | cited, not held | Nasdaq | A for dxyz |
| peer_venture | venture / the cohort's other members | no | refused (heterogeneous pricing bases) | Tark cohort engine | C |

Lane D entries (`pme_bkln`, `pme_psp`, `pme_psp_k`, `pme_vnq`) are removed:
a PME against BKLN is the BKLN comparison, not a second candidate, and in
v1 it made the "secondary" the primary under another name.

## 5. Strategy match and the gate

`strategy_match` is read from one matrix keyed by the product's and the
candidate's (asset class, sub-strategy). The matrix also produces the
reason string.

- 3: same asset class and same sub-strategy. A direct-lending index or a
  cohort of direct lenders for a direct-lending fund. ODCE for a core
  non-traded REIT. A private-equity benchmark index or the evergreen cohort
  for an evergreen PE fund.
- 2: same asset class, different sub-strategy, or the public-market
  version of the asset class. Syndicated loans for direct lending. Listed
  private equity for evergreen PE or for a PE conglomerate. Listed REITs
  for non-traded real estate. The direct-lending cohort for a multi-sector
  or diversified credit fund. The evergreen cohort for a conglomerate.
- 1: an adjacent asset class that shares the dominant risk. Broad public
  equity for private equity or venture. Listed private equity for venture.
- 0: unrelated. Public equity for credit or real estate.

The gate: a candidate with `strategy_match` below 2 is ineligible for
primary or secondary. Its ledger line reads "rejected: strategy gate
(score X/12 but strategy_match Y/3)". A declared benchmark that fails the
gate stays on the card as a fact, with one sentence saying it fails.

## 6. Scoring rubric v2 (12 points)

| criterion | points | rule |
|---|---:|---|
| strategy_match | 0 to 3 | the matrix in section 5 |
| risk_liquidity_match | 0 to 3 | 3: a NAV-class candidate whose observation cadence matches the fund's held return cadence and whose members all share the fund's leverage regime. 2: a NAV-class candidate with a different cadence or a mixed leverage regime, or a daily market proxy for an exchange-traded fund. 1: a daily market proxy against a semi-liquid NAV fund. 0: no computable series, or the fund's price is decoupled from its NAV. |
| investability | 0 or 2 | 2 when the comparison can be computed on held data (a held series or a computable composite), 0 for a cited index. Window clipping is reported in the window note, not scored. |
| data_quality | 0 to 2 | 2 daily or monthly held. 1 annual or quarterly with at least 3 overlapping years. 0 cited, not computed. |
| provider_independence | 0 or 2 | 0 when the provider is the fund's adviser or sub-adviser (registry), else 2. Judged per product, not per menu. |

A synthetic candidate scores 12 and the gate asserts it. On the data held
today no product reaches `risk_liquidity_match` 3: the private credit
cohort mixes interval funds with BDCs, the evergreen cohort carries a
'34-Act LLC, and the real estate cohort's composite is refused. The card
prints "max attainable on held data: N/12" per product so the reader sees
the ceiling the data sets. The threshold for primary and secondary stays
7.

## 7. Lanes, independence, escalation

- Lane A, the declared benchmark (cell 5.1), is always a candidate. Where
  it is held (SPY, URTH, ODCE) it is tagged A and scored on its merits.
  Where it is not held (CSLLI, NASDAQ Composite) it is a cited candidate
  at investability 0 and data_quality 0. The declaration itself earns no
  points: four evergreen funds declare MSCI World, and rewarding the
  declaration would push a broad equity ETF through the gate. A product
  that declares none carries "fund declares no benchmark (cell 5.1)".
- Lane B: third-party indices and investable proxies.
- Lane C: the cohort composite, leave-one-out per subject. Members with
  fewer than 12 months in a fiscal year are excluded, the composite is
  aligned on fiscal-year overlap with the misalignment printed, it is
  refused below 3 remaining members, and it earns data_quality 1 only
  with at least 3 overlapping years. It is shown as the rule's "history of
  a similar type of investment" comparison.
- Independence is judged per product: the registry's adviser and
  sub-adviser against the candidate's provider. CDLI is adviser-owned for
  cliffwater_cclfx and independent for the other four private credit
  products. BKLN's note no longer claims that every private credit fund
  declares no benchmark.
- Escalation is computable: when no candidate passes the gate and reaches
  7, the product escalates with the ledger showing why each candidate
  fell (arkvx: public equity and listed PE fail the gate, the venture
  composite is refused). The flag path stays for the two exchange-traded
  funds whose price is decoupled from NAV (dxyz, ssss).

## 8. Secondary, ties, short windows

Primary and secondary must differ by series. Where no eligible second
candidate exists the card says "no eligible secondary". Ties break on
strategy_match, then risk_liquidity_match, then data_quality, then menu
order. A comparison window shorter than 3 years is labeled "low
confidence: N-year window" on the card and in the memo (sreit one year,
kkr_kpec 2.33 years).

## 9. Expected outcome, v1 to v2

Written before the rubric code changed. The v1 columns are read from
`data/benchmarks/v1_snapshot/` by `src/test_benchmark.py` and must never
drift. The v2 columns are the prediction this document commits to. When
P1-12 lands, the same gate asserts them against the live artifacts, and
any difference is a finding to explain here, not a number to adjust.

| product | v1 primary | v1 secondary | v2 primary (expected) | v2 secondary (expected) | max attainable v2 |
|---|---|---|---|---|---|
| cliffwater_cclfx | bkln 9/12 | pme_bkln 9/12 | peer_credit 10/12 | bkln 9/12 | 10/12 |
| pflex | bkln 9/12 | pme_bkln 9/12 | peer_credit 9/12 | bkln 9/12 | 9/12 |
| cion_ares | bkln 9/12 | pme_bkln 9/12 | peer_credit 9/12 | bkln 9/12 | 9/12 |
| bcred | bkln 9/12 | pme_bkln 9/12 | peer_credit 10/12 | bkln 9/12 | 10/12 |
| ocic | bkln 9/12 | pme_bkln 9/12 | peer_credit 10/12 | bkln 9/12 | 10/12 |
| hl_paf | psp 9/12 | urth 8/12 | peer_evergreen 10/12 | psp 9/12 | 10/12 |
| stepstone_spm | psp 9/12 | urth 8/12 | peer_evergreen 10/12 | psp 9/12 | 10/12 |
| ares_pmf | psp 9/12 | urth 8/12 | peer_evergreen 10/12 | psp 9/12 | 10/12 |
| amg_pantheon | psp 9/12 | urth 8/12 | peer_evergreen 10/12 | psp 9/12 | 10/12 |
| kkr_kpec | psp_k 9/12 | urth_k 8/12 | psp_k 9/12 | peer_kpec 8/12 | 9/12 |
| breit | vnq 9/12 | odce 8/12 | vnq 9/12 | odce 7/12 | 9/12 |
| sreit | vnq 9/12 | odce 8/12 | vnq 9/12 | odce 7/12 | 9/12 |
| jll_ipt | none | none | vnq 9/12 | odce 7/12 | 9/12 |
| arkvx | psp_v 8/12 | spy 7/12 | escalation | none | none eligible |
| dxyz | escalation | none | escalation | none | none eligible |
| ssss | escalation | none | escalation | none | none eligible |

Why each row moves:

- Private credit: the leave-one-out composite of four peers scores 10 for
  the three direct lenders (strategy 3, NAV-class annual composite 2,
  computable 2, annual with 3 or more overlapping years 1, independent 2)
  and 9 for pflex and cion_ares (strategy 2). BKLN stays 9 (strategy 2,
  daily proxy against a semi-liquid fund 1, held 2, daily 2, independent
  2). Where the two tie at 9 the risk criterion breaks it for the
  composite. CDLI scores 7 for bcred and ocic (cited) and 5 for
  cliffwater_cclfx (adviser-owned) and never wins. cion_ares's declared
  CSLLI scores 5 and the card says the declared benchmark fails.
- Evergreen PE: the composite scores 10 and PSP 9. URTH and SPY, declared
  by four funds, score 8 and fail the gate at strategy 1, and the card
  says so.
- kkr_kpec: its held figure spans 2023-09 to 2025-12, so the composite
  overlaps only two fiscal years and earns data_quality 0: 8, behind PSP
  at 9.
- Non-traded REITs: the cohort has three members, so leave-one-out leaves
  two and the composite is refused. VNQ 9 primary, ODCE 7 as a cited
  secondary (strategy 3, NAV-class 2, cited 0 and 0, independent 2).
  jll_ipt gets the same selection with an honest "no computable fund
  series" comparison (P1-13).
- Venture: arkvx moves from PSP 8 to computable escalation. dxyz and ssss
  stay escalated by the price-decoupling flag, with the declared NASDAQ
  Composite and S&P 500 in the ledger.
- "Max attainable" is the highest score an eligible candidate reaches on
  held data.

## 10. Rule mapping

Each criterion carries a basis string until the verbatim text is in the
build: "factor order per the 2026-09-03 audit's check of 91 FR 16088,
verbatim text not in this build". The mapping, as basis strings and not
as quotations: strategy and risk match answer the meaningful-benchmark
definition (the paragraph the audit identifies as (k)). Lane C answers the
"history of a similar type of investment" fallback. Lane A brings the
fund's own declared benchmark in as an input the fiduciary must weigh.
Investability, data quality and independence are process quality under
the prudence standard, which the rule text does not enumerate.
`src/fetch_authority.py` fetches paragraphs (g) to (l) of proposed
2550.404a-6 verbatim into `data/authority/` on a machine with network,
verifying the citation and the RIN first. Until it has run, no surface
quotes the rule.

# Benchmark methodology, architecture v3

Status: rewritten for R2-P1-A (2026-09-06) around decision 7.1 of
`docs/DECISIONS_2026-09.md` and its defaults in 7.21. Sections 1 to 3
describe the comparison arithmetic. Sections 4 to 8 specify Slot K, the
meaningful benchmark. Section 9 specifies Slot G, the peer comparison,
and the alignment rule. Section 10 is the naming rule. Section 11 works
two products through both slots. Section 12 maps the slots to the rule.
Every number quoted in section 11 is recomputed from `data/` by the engine
and asserted against this document by the benchmark gate. Regulatory text
is quoted only from `data/authority/` once it has been fetched into the
build. Until then this document names paragraphs by letter and paraphrases
nothing.

Notation: `*` for multiplication, `/` for division.

## 0. Two slots, two paragraphs

Every card, memo and record carries two comparisons, named as such, that
answer different paragraphs of the proposed rule:

- Slot K, "Meaningful benchmark (paragraph (k))": one candidate chosen by
  the rubric in section 6 from the fund's declared benchmark (Lane A),
  exchange-traded strategy proxies (Lane B) and published strategy indices
  (Lane P). It carries a PME only when its series is a public market price
  series, a relative wealth ratio when its series is appraisal-based, and
  no number at all when it is cited but not held.
- Slot G, "Peer comparison (paragraphs (g) and (h))": the cohort, side by
  side over identical periods with n per period, an equal-weight
  leave-one-out composite only where every peer reports the period, and a
  relative wealth ratio for the fund against it. Slot G is never called the
  benchmark and never a PME.

Cells 1.8, 5.3, 5.5 and 5.6 carry Slot K. Cell 1.12 carries Slot G. Cell
5.4 carries the cohort's one member table. The Screener's "KS-PME vs public
proxy" column is Slot K's PME when Slot K is a public series and otherwise
the reference comparison of section 7, named as such in the fact's note.

## 1. The comparison window

A fund is compared with a public market series over the effective window:
the fund's own window clipped to the series' coverage.

- Daily NAV series (cliffwater_cclfx, pflex, cion_ares, arkvx): the
  intersection of the two date ranges, on both sides.
- Filed fiscal-year returns (amg_pantheon, ares_pmf, bcred, ocic, breit,
  sreit, hl_paf, stepstone_spm, kkr_kpec): whole fiscal years only. A
  fiscal year counts when it starts on or after the series' first date and
  ends on or before its last date.
- No product carries a single annualized figure any more (R2-P1-6, section
  8): stepstone_spm and kkr_kpec moved to their filed fiscal-year series.

One anchor. Fund growth, index growth and the flows inside the PME all read
the level on or before each window date from the full series. The identity
`KS-PME = fund growth / index growth` holds on every two-point comparison
and is asserted.

Every held proxy series is an investable ETF's Yahoo adjusted close, a
total-return proxy for its index family (SPY, URTH, BKLN, PSP, VNQ). Fund
series are the fund's own Yahoo adjusted close where a class ticker exists
(approximates NAV total return with distributions reinvested) or the raw
daily close where the fund is exchange-traded (a market price, labeled as
such and never benchmarked as a portfolio). Every surface prints the source
beside the return.

## 2. Annualization

`fund_ann_pct` and `index_ann_pct` are `growth ** (1 / years) - 1` with
`years` the actual/365.25 day count of the effective window for a series
comparison, and the count of periods for an aligned-period comparison.

## 3. Flows, KS-PME, Direct Alpha, relative wealth ratio

The comparison is two-point: one contribution of 1.0 at the window start
and one valuation of `fund growth` at the window end.

- KS-PME (Kaplan and Schoar) future-values every flow to the final date at
  the index's growth and divides the value of distributions plus terminal
  value by the value of contributions. With two flows this is
  `fund growth / index growth`. It is computed only against a public market
  price series.
- Direct Alpha (Gredil, Griffiths and Stucke) is the IRR of the same flows
  after each has been future-valued at the index: the annualized form of
  the same two-point comparison, not a second piece of evidence.
- For daily NAV products a second row, `ks_pme_monthly_schedule`, is
  computed and labeled ILLUSTRATIVE wherever it appears: one unit of cash at
  the window start and at each fund month-end inside the window, valued at
  the window end. The two-point figure stays primary.
- Against an appraisal-based comparator (a published strategy index whose
  series is held, or the Slot G peer composite) the statistic is a relative
  wealth ratio, `fund growth / comparator growth` over identical periods,
  and an annualized excess return, `ratio ** (1 / years) - 1`. It is never
  called a PME (section 10).

Every figure is window-sensitive on appraisal-lagged NAVs and can be
smoothing-flattered. The Analysis Lab recomputes the public-series
comparisons on any held proxy and any window start with the same code path
(parity asserted by the frontend gate) and shows Slot G under its own label.

## 4. What the rubric reads: typed descriptors

The rubric scores a product against a candidate from typed descriptors,
never from an integer typed on a menu entry. Product descriptors come from
`data/registry.json` (asset class, sub-strategy, pricing class, leverage
regime, advisers, the one return basis, the typed Lane A entries, each with
its source cell) and from the facts layer (dealing cadence, cap period,
caps, gate history, program status, cells 3.1 and 3.3). Candidate
descriptors are typed on the candidate table in the engine.

| candidate | asset class / sub-strategy | pricing | liquidity class | data | lane | provider |
|---|---|---|---|---|---|---|
| bkln | public credit / syndicated loans | market | daily market | held (Yahoo adjusted close) | B | Invesco, Morningstar LSTA class |
| cdli | private credit / direct lending | appraisal NAV | appraisal index, no dealing mechanism | cited until the headline series is acquired | P | Cliffwater (the adviser of cliffwater_cclfx) |
| lsta | public credit / syndicated loans | market | daily market | cited | P | Morningstar, LSTA |
| csll | public credit / leveraged loans | market | daily market | cited | P | Credit Suisse (UBS) |
| bbg_agg | public credit / core bonds | market | daily market | cited | A only | Bloomberg |
| ice_bofa_hy | public credit / high yield | market | daily market | cited | A only | ICE Data Indices |
| psp | listed private equity | market | daily market | held | B | Invesco, Red Rocks |
| urth | public equity / MSCI World | market | daily market | held | B, A where named | iShares, MSCI |
| spy | public equity / S&P 500 | market | daily market | held | B, A where named | SPDR, S&P DJI |
| nasdaq_comp | public equity / NASDAQ Composite | market | daily market | cited | A only | Nasdaq |
| cambridge_pe | private equity / private-market index | appraisal NAV | appraisal index | licensed, not held | P | Cambridge Associates |
| vnq | listed real estate / listed REITs | market | daily market | held | B | Vanguard, MSCI US REIT |
| odce | real estate / private-market index | appraisal NAV | appraisal index of periodically dealt funds | cited until the headline series is acquired | P, A for jll_ipt | NCREIF |

Menus per strategy: private credit (bkln, cdli, lsta, csll), evergreen
private equity and the private equity conglomerate (urth, psp,
cambridge_pe), pre-IPO and venture (spy, psp), non-traded real estate (vnq,
odce). Lane A entries join the menu of the product that names them.
Burgiss and Cambridge Real Estate are equivalent licensed benchmarks that
are not held. They are not on the menus because they would only tie the
licensed candidate already there and the tie would be decided
alphabetically. They join the day a license exists.

The peer composite is not a candidate. It is Slot G (section 9).

## 5. Strategy match and the gate

`strategy_match` is read from one matrix keyed by the product's and the
candidate's (asset class, sub-strategy). The matrix also produces the
reason string.

- 3: same asset class and same sub-strategy, or a private-market index of
  the same asset class. CDLI for a direct-lending fund. ODCE for a
  non-traded REIT. The Cambridge PE benchmark for an evergreen PE fund.
- 2: same asset class, different sub-strategy, or the public-market version
  of the asset class. Syndicated loans for direct lending. CDLI for a
  multi-sector credit fund. Listed private equity for evergreen PE or for a
  PE conglomerate. Listed REITs for non-traded real estate.
- 1: an adjacent asset class that shares the dominant risk. Broad public
  equity for private equity or venture. Listed private equity for venture.
- 0: unrelated. Public equity for credit or real estate.

The gate: a candidate with `strategy_match` below 2 is ineligible for Slot
K. Its ledger line reads "rejected: strategy gate (score X/12 but
strategy_match Y/3)". A declared benchmark or SEC-required comparator that
fails the gate stays on the card as a fact with that sentence, and its own
comparison is still computed when its series is held (section 7).

## 6. Scoring rubric v3.1, Slot K (10 points)

Four criteria. The fifth criterion of v3, pricing basis match, was a
function of the same two inputs as the risk criterion (the fund's pricing
class and the candidate's liquidity class) and double-counted them, so
every cited appraisal index beat every held ETF by exactly one point.
It is dropped (R3-P2-2). The threshold and the gate are fractions of
their maxima, printed as "x of N" on every surface.

| criterion | points | rule |
|---|---:|---|
| strategy match | 0 to 3 | the matrix in section 5, gate below 2 of 3 |
| risk and liquidity match | 0 to 3 | read from the facts layer (dealing cadence, caps, gating history, program status) against the candidate's typed liquidity class, never from the cadence of the held return file. 3: an appraisal-based index against a periodically dealt NAV fund whose filings disclose no proration and no suspension, or a daily market series against an exchange-traded fund whose price tracks NAV. 2: an appraisal-based index against a NAV fund that has prorated requests or suspended repurchases (the index carries no such gate). 1: a daily market series against a semi-liquid NAV fund (the case the PME construct exists for). 0: the fund's price is decoupled from its NAV, or an appraisal index for a market-priced fund. Every input that fires is named in the reason, and the gate asserts that perturbing gating history, program status or dealing cadence moves the criterion. A null gating history counts as "no proration or suspension disclosed in the filings on record", and the reason says so. |
| provider independence | 0 or 2 | 0 when the registry's affiliation map ties the candidate's provider entity to one of the fund's adviser entities, and 0 makes the candidate ineligible for Slot K: an index the fund's own adviser publishes is never the fund's meaningful benchmark. 2 otherwise. Affiliation is a fact read from the map, never a string match. |
| data held | 0 or 2 | the one possession criterion. 2 when the candidate's series is in the record, public (Yahoo adjusted close) or published (an acquired headline series). 0 when it is cited or licensed and not held. Possession moves 2 of 10 points. |

Threshold: six tenths of the maximum, 6 of 10 (the nearest tenth at or
above the 7 of 12 the v3 rubric used). Gate: strategy match 2 of 3. A
synthetic candidate scores 10 of 10 and the gate asserts it. On the record
today the strategy-exact appraisal indices reach 3 of 3 on the risk
criterion for every NAV fund whose filings disclose no proration and no
suspension. The card prints "max attainable by an eligible candidate on
held data N of 10" per product.

Properties the gate asserts: moving one input moves one criterion
(affiliation moves independence alone, acquiring a series moves data held
alone, a sub-strategy change moves strategy match alone), the held return
file's cadence moves nothing, perturbing any typed liquidity fact moves the
risk criterion for at least one candidate class, and the words "published
by the fund's own adviser" appear only where the map says so.

## 7. Lanes, the reference comparison, escalation

- Lane A is typed from cell 5.1 (R2-P1-5). "Declared benchmark": the
  prospectus or shareholder report names the index as the fund's
  performance benchmark (dxyz's NASDAQ Composite, stepstone_spm's MSCI
  World, jll_ipt's NFI-ODCE). "SEC-required comparator": a broad-based
  index shown because the shareholder report or 10-K must show one (hl_paf,
  amg_pantheon, ares_pmf, arkvx, ssss's S&P 500 and Nasdaq index, pflex's
  ICE BofA US High Yield, cion_ares's Credit Suisse Leveraged Loan,
  jll_ipt's S&P 500, cliffwater_cclfx's two illustrative comparators). Both
  types are scored in Slot K like any other candidate. The declaration
  itself earns no points. Every Lane A entry with a held series gets its
  own fund-versus-index comparison, shown on the card and in the memo even
  when it is not selected, except for a fund whose price is decoupled from
  its NAV (dxyz, ssss): no comparison is computed on a market-price series,
  it would benchmark the premium, not the portfolio (R3-P2-4). A product
  with no "declared" entry states why.
- Lane B: exchange-traded strategy proxies with a held series.
- Lane P: published strategy indices. Cited until their headline series is
  acquired (R2-P1-1, section 9.3), then held with a relative wealth ratio.
- A cited candidate can be Slot K. It holds the slot by descriptor
  (decision 8.5): the card, cell 5.3, the Screener, Compare and the record
  print one sentence, "Meaningful benchmark by descriptor. No comparison
  until its series is held.", and the selection record carries the typed
  flag `by_descriptor`. When Slot K carries no number, the highest-ranked
  held public market series that passes the gate and the affiliation rule
  is shown as the reference comparison, named "reference comparison, not
  the meaningful benchmark", on the card, in cell 1.8, in the facts, on the
  Screener and Compare columns ("KS-PME vs reference proxy") and in the
  memo. The reference loop continues past a held proxy whose comparison is
  not computable and records the candidates it passed over with the reason
  (`reference_skipped`, R3-P2-6).
- Escalation is generated from the strategy's display name and the
  candidates scored (R2-P1-7). Computable escalation: the text says which
  of two things every candidate did, fail the strategy gate (strategy match
  below 2 of 3) or score below the threshold (6 of 10), lists every
  candidate with its score and the reason it fell, and names what would
  change it. Flag path: the fund's price is decoupled from NAV (dxyz,
  ssss), the text says every candidate would benchmark the premium.

## 8. Ties, short windows, one basis

Candidates are ordered by score, then strategy match, then risk and
liquidity match, then data held, then candidate name. An eligible candidate
with the same score as the selection carries the typed flag `tied` and the
one tie sentence, "Tied on score. Ordered by strategy match, then risk and
liquidity match, then data held, then name.", on the card, in cell 5.6 and
in the memo. The word "outranked" does not appear (audit round 2 item 18).

A comparison window shorter than 3 years is labeled "low confidence:
N-year window" on the card and in the memo.

One return basis per product (R2-P1-6): the registry's `held_returns` kind
feeds every slot and every Lane A comparison, and the gate asserts that
every comparison of a product names the same fund return source. A NAV
fund's held series is labeled "Yahoo adjusted close, approximates NAV total
return". An exchange-traded fund's is labeled "Yahoo adjusted close, a
market price with distributions reinvested, not NAV" (R3-P2-4).
stepstone_spm uses its filed fiscal-year series (FY2022 to FY2026, Class
I). kkr_kpec uses its filed GAAP-NAV calendar-year returns (2024 and 2025,
Class I, the 2023 period from commencement is partial and excluded). The
annualized figures those two products disclose stay in cell 1.2 as
evidence and are no longer engine inputs.

## 9. Slot G: the peer comparison and the alignment rule (rule 14)

### 9.1 Member returns, one basis each

Every member's period returns come from its one basis (section 8), built
by one module shared by the engine and the cohort builder, so a cohort has
one member table (audit round 2 item 20):

- a daily series gives calendar years from the adjusted close, complete
  years only (an observation in the last week of December on both ends),
- filed fiscal-year returns whose year ends 12-31 are calendar years
  (bcred, ocic, kkr_kpec, breit, sreit),
- filed fiscal-year returns ending in another month are fiscal years keyed
  by their end date (the four March-year evergreen PE funds) and are never
  averaged with calendar years,
- stub and partial periods are excluded.

### 9.2 The table, the composite, the ratio

The side-by-side table lists every period any member reports, each
member's return or "n/a", and n, the count of members reporting. It is
printed for every cohort, refused or not.

The composite is leave-one-out for the subject, equal-weight, formed only
over periods that every aligned peer reports on the subject's own period
kind with the same year-end month (identical start and end dates), with at
least three aligned peers. A peer on another basis is excluded from the
composite by name with the reason, and stays in the side-by-side table
with its own periods and n (R3-P2-5: evergreen private equity forms its
composite over the four March-year-end members and excludes the
December-year-end member, and that member as the subject is refused
because no peer shares its basis). The ratio runs over the longest run of
consecutive common periods the subject also reports. Refusals, each with
its reason on the card and in cell 1.12: fewer than three peers (the
non-traded REIT and venture cohorts), heterogeneous pricing bases (market
price against appraisal NAV), fewer than three peers on the subject's
basis, a member with no period returns on record (named), no common
period. Calendar-quarter alignment waits for quarterly total returns, which
no annual-tier member prints.

Every Slot G block carries a survivorship sentence (the cohort is the
roster's surviving, still-filing products, so a composite carries
survivorship bias in the fund's favor) and a heterogeneity sentence
generated from the members' typed wrapper types and leverage regimes.

### 9.3 Published index series (Lane P held)

When a published headline series is acquired
(`data/series_quarterly/idx_<id>.csv`, columns `period_end` and
`total_return_pct`, one row per calendar quarter, with a manifest entry
naming the URL, the fetch date and the license note), the candidate
becomes held and its comparison is a relative wealth ratio on identical
periods: calendar quarters where the fund has a daily series, otherwise
the fund's own filed years compounded from the index's four quarter-ends
(a March fiscal year is the four quarter-ends June to March). The
normalizer for a downloaded file is `src/fetch_index_series.py`.

## 10. The naming rule (rule 12)

KS-PME, PME and Direct Alpha name a comparison against a public market
price series and nothing else. A comparison against an appraisal-based
comparator (a published strategy index, the peer composite) is a relative
wealth ratio and an excess return. The rule is enforced on the artifact
(no `ks_pme` key on an appraisal-based comparison, the statistic string
starts with "relative wealth ratio"), on cells 1.8, 1.12, 5.5 and 5.6 (no
sentence about the peer comparison carries a PME name), on the bundle
card, in every memo and packet, and on the Screener's column headers.

## 11. Worked examples

### 11.1 cliffwater_cclfx

Slot K. CDLI scores 6 of 10 (strategy 3, risk 3, independence 0, data held
0) and is ineligible: Cliffwater publishes it and advises the fund, per the
affiliation map. BKLN scores 7 of 10 (strategy 2, risk 1, independence 2,
data held 2) and is selected. The three other credit indices (Morningstar
LSTA, Credit Suisse Leveraged Loan, Bloomberg US Aggregate) score 5 of 10,
cited, below the threshold. The comparison against BKLN over 2019-06-05 to
2026-07-17 on the fund's Yahoo adjusted close: KS-PME 1.2532, Direct Alpha
3.22%/yr, fund 7.89%/yr against the proxy's 4.52%/yr. Max attainable 7 of
10.

Slot G. Peers: bcred, pflex, cion_ares, ocic, each on its one basis
(calendar years from the adjusted close for pflex and cion_ares, filed
December fiscal years for bcred and ocic). Every peer reports 2021 to
2025, n=4 in every period. Fund growth 1.5567, composite growth 1.4668,
relative wealth ratio 1.0613, excess return 1.2%/yr. The audit's own
recomputation against the three December-fiscal-year peers alone (item
13, about 1.03) is reproduced by the gate from the same table.

### 11.2 hl_paf

Slot K. The Cambridge Associates US PE benchmark scores 8 of 10 (strategy
3, risk 3, independence 2, data held 0) and is selected by descriptor,
cited and not held, so it carries no number and the card prints the
decided sentence. PSP scores 7 of 10 (strategy 2, risk 1, independence 2,
data held 2) and is the reference comparison: KS-PME 1.9565 over
2021-03-31 to 2026-03-31 on the filed fiscal-year returns, named on the
card as a reference and not the benchmark. The SEC-required comparators
(S&P 500, MSCI World) fail the strategy gate at 6 of 10 and still show
their own comparisons.

Slot G. Three of the four peers report March fiscal years (stepstone_spm,
ares_pmf, amg_pantheon) and form the composite with the fund over FY2023
to FY2026, n=3 in every period, relative wealth ratio 1.0971. kkr_kpec
reports calendar years and is excluded by name with that reason, and stays
in the side-by-side table.

## 12. Rule mapping

Each criterion carries a basis string until the verbatim text is in the
build. Slot K answers the meaningful-benchmark definition of paragraph
(k). Slot G answers the history-of-similar-investments comparison of
paragraphs (g) and (h). Lane A brings the fund's own declared benchmark
or SEC-required comparator in as an input the fiduciary must weigh.
Independence, data held and pricing basis are process quality under the
prudence standard, which the rule text does not enumerate. Until the
authority text has been fetched and hashed into the build, no surface
quotes the rule.

## 13. The selection lock (R3-P2-19)

Every selection record carries `recorded_at` (the record's as-of instant,
midnight UTC of the as-of date in `data/as_of.json`, never a wall clock,
so the producer run reproduces byte for byte), `rubric_version`, `inputs`
(the filings by accession for the cells the rubric reads, each a manifest
row with its form and filing date, the series files by content hash, and
the descriptors read from the registry and the facts by a hash of the
exact values), and `record_hash`, SHA-256 over the canonical JSON of the
whole record without the hash field. The first time a record hash appears
the runner keeps a dated copy under `data/benchmarks/history/<key>/`,
named by the recorded date and the first eight characters of the hash, so
a re-record never overwrites a prior record. The card prints "Selection
recorded <date>, record <first 8 of the hash>", the memo prints the full
hash, and the gate recomputes every hash and refuses a record where any
differs.

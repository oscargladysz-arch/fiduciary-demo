# Benchmark selection methodology

Status: written section by section as the P1 remediation lands
(2026-09). Sections 1 to 3 describe the engine as committed. The scoring
rubric (v2), the strategy matrix, the eligibility gate, the four lanes,
the tie-breaks, the expected v1 to v2 outcome per product and the rule
paragraph each criterion maps to are added by the P1-B preparation task
before any rubric code changes. `docs/benchmark_methodology_skeleton.md`
is the 2026-08 question list this document answers.

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

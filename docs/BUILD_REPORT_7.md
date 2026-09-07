# BUILD REPORT 7, round 2 remediation of the 2026-09-05 audit

Specification: `docs/GAP_ANALYSIS_2026-09-05.md` (46 numbered findings).
Decisions, defaults taken where the brief was silent, and every discrepancy
between the brief, the audit and the record: `docs/DECISIONS_2026-09.md`,
section 7. Branch `claude/tark-round-2-audit-jl9q4q` (the harness-assigned
branch, decision 7.7), one task-tagged commit per task, nothing squashed,
`main` untouched. This report grows by phase. Phase R2-P0 is complete and
recorded below. R2-P1, R2-P2 and R2-P3 are appended as they land.

The non-negotiables held throughout and the gates assert them: no cell was
set to `verified` (the count is 0. Since R2-P2-1 the gate no longer pins
it: it accepts a verified row only as a human signature written by the
verification tool after the quote was found in the filing), no number, quote, document name,
accession or date was invented (every accession now comes from
`data/manifest.csv` and nowhere else), tier language is never blurred, the
four reference plans stay anonymized, gates only grew, every changed
published value is in the generated corrections table, no secret entered a
tracked file, and no developer instruction, path, script name or internal
key renders on a surface or in a document.

## 1. Baseline, recorded 2026-09-05 before any change (decision 7.9)

Branch at `4519e61` (main plus the audit document). Python 3.11, Playwright
1.56.0 against the preinstalled Chromium build 1194. Network policy: sec.gov,
data.sec.gov, federalregister.gov, dol.gov, the market-data hosts and
github.io are blocked from the build container, PyPI and the GitHub API are
reachable, no `ANTHROPIC_API_KEY`, `data/raw/` absent (decision 7.8).

| measure | baseline |
|---|---:|
| gates in `hooks/pre-commit` | 18 |
| hook exit code | 0 |
| `[PASS]` lines | 849 |
| hook wall time | 107 s |
| cells, by status kind | 406 extracted-unverified, 205 n/a, 161 computed, 75 partial, 16 fetched, 1 structured, 0 verified |
| `site/data.js` | 1,035,854 bytes |
| screenshots | `docs/screenshots/baseline_r2/`, 42 files, 8.5 MB |

## 2. R2-P0, the Tuesday cut: tasks and commits

| task | commit | what changed |
|---|---|---|
| R2-P0-1 | `b760889` | The eight hl_paf citations carry the manifest's N-CSR accession 0001213900-26-066804. The resolver is manifest-first and reports a conflict when the text disagrees with the manifest. The validator refuses any accession that is not a manifest row for the product. The drawer URL is built from CIK and accession. A missing N-CEN manifest row for cion_ares was added from the record. |
| R2-P0-2 | `7e8ba68` | Affiliation is read from an explicit map in `data/registry.json` (Cliffwater to CDLI), never from a string match. URTH scores 2 of 2 on independence for ares_pmf and cion_ares. A peer composite scores 1 of 2 because the evaluator built it. Methodology section 9 repinned from a recomputation. |
| R2-P0-3 | `e16ad2d` | Every developer sentence is gone from the Authority panel, the Liquidity view, the Plans view, the memos and the packets. Internal keys render through display maps or not at all. New gate `test_surfaces` scans the bundle, 158 rendered states and 128 documents against 33 forbidden patterns. |
| R2-P0-5 | `786de22` | Liquidity reason strings read the typed facts they cite: dealing cadence from a typed enum, the binding annual capacity from the caps list (breit 20%, not 24%), a suspended program reads as suspended, and the consulting-plan breit scenario reads thin headroom. |
| R2-P0-4 | `2a2130f` | One abbreviation-aware sentence splitter shared by the site and the memo. Cell 5.7 no longer headlines as "Anderson v." and no memo row ends at an abbreviation. |
| R2-P0-7 | `bb2de10` | Cell 3.9 headlines the structural verdict alone, plan-independent. The scenario verdict is stated per plan with the ILLUSTRATIVE label. The Plans view says which layer the plan drives. Reconcile reads both layers in all 64 memos. |
| R2-P0-8 | `141f9ac` | The 2.3 headline is labeled by the typed basis clause ("1.36% expense ratio, before waivers, excluding interest expense" for Cliffwater), never an assumed "net". |
| R2-P0-9 | `fe3176c` | The escalated memo states what the record holds and does not decide. The memo gate refuses legal conclusions. |
| R2-P0-6 | `54b9d0f` | The peer-composite comparison is a relative wealth ratio with an excess return, never a PME. Each slot names its fund return source on the card, in cell 1.8 and in the memo. The Screener has two performance columns that sort on their own kind. 210 renamed fields logged in the corrections table under the R2-P0-6 cause, no figure changed. |
| R2-P0-10 | this commit and the deploy entry | Demo script v8, Tier 1 re-derived, runbook updated, deploy log started, the pre-deploy EDGAR URL check script, the demo script surface-check gate, after screenshots, the recorded deploy. |

## 3. Reproduction table, audit items 1 to 10

"Before" is the state at the baseline commit as the audit reproduced it and
as the baseline run confirmed it. "After" names the commit and the evidence.
"Gate" names the check that now fails if the defect returns.

| item | audit finding | before (baseline) | after | gate |
|---|---|---|---|---|
| 1 | Dead EDGAR link on Tier 1 cells (hl_paf 1.1, 1.2, 2.1, 2.3, 2.7, 3.6, 4.2, 4.5) | CSV and JSON carried `0001213900-26-054176*`, the drawer linked `.../000121390026054176/` (404 per the audit) | `b760889`: accession 0001213900-26-066804 in the CSV, the JSON and the drawer, URL `.../000121390026066804/ea0291054-01_ncsr.htm` from the manifest row | `validate_data` (accession must be a manifest row for the product, a text accession that disagrees with the manifest is an error), `test_invariants` (drawer URL equals CIK plus accession, no resolver conflicts), `check_edgar_urls.py` on a networked machine |
| 2 | False affiliation from a substring test (URTH "published by the fund's own adviser (Ares)", arkvx composite "(ARK)") | ares_pmf URTH 0 of 2, card 6 of 12. cion_ares URTH 0 of 2, 5 of 12. arkvx ledger row 03 named ARK | `7e8ba68`: `data/registry.json` affiliation map, URTH 2 of 2, CDLI 0 of 2 for Cliffwater only, composites 1 of 2 with the evaluator named as the constructor | `test_benchmark` (every product against every candidate, an affiliation reason only where the map says so, a synthetic map entry is honored) |
| 3 | Developer instructions on committee surfaces (run python ..., askebsa.dol.gov is blocked, anonymization is a project display rule) | Authority panel six times, all 64 memos, Liquidity view on 56 of 64 pages, Plans view, all 128 documents | `e16ad2d`: "The verbatim text of paragraphs (g) to (l) is not yet in this build", "Schedule H line 2e is not yet in the plan record", the anonymization rule string is not printed | `test_surfaces` (bundle, 158 rendered states, 128 documents, 33 patterns) |
| 4 | Headlines cut at abbreviations ("Anderson v.", about 250 memo rows) | 5.7 headline "Anderson v." on 16 products | `2a2130f`: shared `first_sentence` with an abbreviation list, single initials, dotted acronyms and parenthesis depth | `reconcile` (no headline or plain ends at an abbreviation), `test_memo` (no findings row ends at one) |
| 5 | Liquidity reason text contradicted by its own typed facts (sreit 12x/year over suspended, jll_ipt 4x/year vs daily, breit 24% vs 20% binding cap, "Adequate headroom" at 68.5%) | as the audit reproduced, all four plans | `786de22`: dealing labels from the typed enum, binding cap = the smallest annualized cap (breit 20%), suspended reads suspended, breit consulting plan reads thin headroom | `test_liquidity` (binding cap, dealing and caps labels, null never 0), `reconcile` (scenario sentence per plan) |
| 6 | Internal identifiers as headlines ("peer_evergreen selected, 10/12", "rubric v2, engine output", `private_credit`, "a private private equity index for a evergreen pe fund") | live on 5.3, 5.6, card subtitles, ares_pmf ledger row 01 | `e16ad2d`: display maps for strategy, cohort, lane, asset class, sub-strategy, candidate and rubric names on every surface and document | `test_surfaces` (bare keys and the retired phrases are forbidden patterns) |
| 7 | Two fund returns on one card with no source note | cclfx primary 10.57%/yr (filed fiscal years), secondary 7.89%/yr (Yahoo), unexplained | `54b9d0f`: each slot prints "Fund, filed fiscal-year returns" or "Fund, Yahoo adjusted close", the artifact carries `fund_return_source` per comparison | `reconcile` (fund return source required on every comparison, tied to cell 1.8 and the memo), `test_frontend` (card labels) |
| 8 | Screener KS-PME column mixes composite ratios with ETF PMEs | one sortable column over two statistics | `54b9d0f`: "KS-PME vs public proxy" and "Peer relative wealth ratio", each sorted on its own kind | `test_frontend` (both columns present), `reconcile` (facts `pme_public_proxy` and `peer_relative_wealth_ratio` agree with the artifact by kind) |
| 9 | Tier blur on the 3.9 headline, Plans view says the plan drives every verdict | "verdict varies by plan: conditional, conditional-weak" under the structural line, 13 products and 52 memos | `bb2de10`: 3.9 headline "structural verdict X, plan-independent", scenario per plan labeled illustrative, Plans view sentence corrected | `reconcile` (structural headline and per-plan scenario phrase in all 64 memos), `test_liquidity`, `test_frontend` |
| 10 | "Net expense ratio" hardcoded as the 2.3 label | cclfx spoken as "1.36% net expense ratio" | `141f9ac`: label from the typed basis, "1.36% expense ratio, before waivers, excluding interest expense (3.31% including interest, FY2026)", `EXPENSE_BASIS` typed for 13 products | `reconcile` (headline tie), `test_frontend`, and the demo script surface-check gate speaks the basis |

## 4. Gates added or grown in R2-P0

- New `test_surfaces` (gate 18 of 19): no developer instruction, path,
  script name or internal key in the bundle, on any rendered view or in any
  generated document.
- `validate_data`: accession must be a manifest row for the product, the
  "or written in its citation" escape is gone, facts enums and shapes.
- `test_invariants`: drawer URL from CIK plus accession, resolver conflicts
  are errors, every ledger accession is in the manifest, 1.8 check by kind.
- `test_benchmark`: affiliation from the map only, all products against all
  candidates, composite keys and statistic names, two-point identity per
  kind, repinned selections cited to the recomputation.
- `test_liquidity`: binding cap, dealing and caps labels, null capacity
  never 0, structural and scenario layers by name.
- `test_memo`: no legal conclusion, escalation phrase, abbreviations.
- `reconcile`: EDGAR URL in the bundle equals the manifest, abbreviations,
  both liquidity layers in all 64 memos, comparison by kind with the naming
  gate (no PME name in a composite sentence), fund return source required.
- `test_frontend`: composite and series card labels, two Screener columns,
  the Tier 1 drawer against the CSV, and the demo script's surface-check
  block (every spoken text renders on the named view under the named plan,
  and no composite ratio is spoken).
- `test_docs`: the demo script version is the same in the queue and the
  runbook, the surface-check block exists, the deploy log names the
  pre-deploy EDGAR check.
- `test_copy`: owns the demo script, the deploy log and this report.
- `corrections_log`: watches the accession column and the renamed
  comparison fields.

## 5. Deploy

Entry 1 of `docs/DEPLOY_LOG.md`. Source commit `0d37757`, hook run 2026-09-05
08:39 UTC (19 gates, exit 0, 906 PASS lines, 141 s), deployed as `gh-pages`
commit `d74e91c` (`94bf391..d74e91c`, 135 files changed), the deployed tree
identical to `site/` apart from `.nojekyll`. The Tier 1 drawer check passed
against the local build of that commit for all ten cells. The EDGAR HTTP 200
check is not done: the container does not reach sec.gov, and a person runs
`python src/check_edgar_urls.py` on a networked machine before Tuesday. The
live URL was not opened from the container (github.io is blocked).

## 6. What could not be done from this container

Recorded in decision 7.8 and repeated here so nobody describes them as done:
the HTTP 200 check of the Tier 1 EDGAR URLs (`check_edgar_urls.py` exits 2
here, run it on a networked machine before Tuesday), the verbatim rule text
fetch, the CDLI and NFI-ODCE headline series, Schedule H, the case-law
source documents, the calibration run and the 17th product. Opening the live
URL is also blocked from here (github.io), so the Tier 1 drawer check was
run against the local build of the deployed commit and is repeated by the
frontend gate on every run.

## 7. R2-P1, engine truth: tasks

Started 2026-09-06 after R2-P0 merged into `main` (`eb6242d`) and the live
site carried the Tuesday cut (decision 7.20). Not deployed: the Tuesday cut
stays live until the sends, and R2-P1 goes out from a recorded run after
it. The commit hashes are in section 11.

| task | what changed | decision |
|---|---|---|
| R2-P1-1 | The published-index path: `src/fetch_index_series.py` normalizes a downloaded or fetched CDLI or NFI-ODCE headline file into `data/series_quarterly/idx_<id>.csv` (period_end, total_return_pct, one row per calendar quarter) and records URL, fetch date, licence note and source hash in the quarterly manifest. The engine treats the index as held the moment the file exists and compares on identical periods with a relative wealth ratio. The fetch itself needs a networked machine (section 9). | 7.2 |
| R2-P1-2 | Slot K and Slot G in the engine. Rubric v3 (12 points: strategy match 3 with the gate, risk and liquidity match 3, provider independence 2 with affiliated providers ineligible, data held 2, pricing basis match 2). Ties print "tied on score, ordered by strategy_match, then risk_liquidity_match, then data held, then alphabetical" and the word "outranked" is gone. The naming rule is enforced on the artifact, cells 1.8, 1.12, 5.5 and 5.6, the card, the memos and the Screener headers. New cell 1.12 carries Slot G. | 7.1, 7.21 |
| R2-P1-3 | Calendar alignment (rule 14). One member table per cohort from one basis per product: calendar years from the daily series (cclfx, pflex, cadux), filed December years (bcred, ocic, kkr_kpec, breit, sreit), March years kept as fiscal years and never averaged with calendar years. Composite only where every peer reports the period, at least three peers, identical dates, n printed. Evergreen private equity and the REIT and venture cohorts refuse the ratio and show the table. | 7.21 |
| R2-P1-4 | `risk_liquidity_match` reads the facts layer (dealing cadence, cap period, caps, gate history, program status) against the candidate's typed liquidity class. The held return file's cadence moves nothing (property test). | 7.21 |
| R2-P1-5 | Lane A typed from cell 5.1: "declared" (dxyz, stepstone_spm, jll_ipt's NFI-ODCE) and "SEC-required comparator" (hl_paf, amg_pantheon, ares_pmf, cion_ares, pflex, arkvx, ssss, jll_ipt's S&P 500, cliffwater_cclfx's two illustrative comparators). Three cited candidates added for those comparators. Every Lane A entry with a held series gets its own comparison on the card, in cell 1.8 and in the memo. | 7.21 |
| R2-P1-6 | One basis per product. stepstone_spm on its filed fiscal-year series (growth 1.9504 FY2022 to FY2026), kkr_kpec on its GAAP-NAV calendar years 2024 and 2025 (a two-year window, labeled low confidence). jll_ipt's NFI-ODCE is Slot K, cited and not held, no number. A property test asserts every comparison of a product names the same fund return source. | 7.21 |
| R2-P1-7 | Escalation text is generated from the strategy's display name and the candidates scored, with the required next step derived from the menu. | 7.21 |
| R2-P1-8 | Analysis Lab opens on Slot K's series when held, else on the reference series, and shows Slot G under its own label with the table and the ratio. The card carries two named slot cards, the Lane A strip, the reference block, the tie chip and the ledger. The Cohorts view charts the one member table and says when no composite return is formed. | 7.21 |
| R2-P1-9 | Methodology rewritten around the two slots with both scoring rules, the alignment rule, the naming rule, the affiliation map and worked examples for cclfx and hl_paf. The expected-outcome table is deleted as a test oracle. The benchmark gate is property tests (one fact moves one criterion, affiliation only from the map, naming, alignment, ties, one basis, the audit's hand recomputations). | 7.21 |
| R2-P1-10 | The scenario base is the plan's filed outflow proxy (Schedule H totals over beginning net assets, recomputed by the validator), the sliders are the stress around it, both printed and never blended. | 7.24 |
| R2-P1-11 | The allocation slider moves dollar demand against the fund's dollar capacity for the six products whose net assets are typed, and is removed with one sentence elsewhere. | 7.24 |
| R2-P1-12 | gate_history typed by one written rule with an evidence phrase per fact, validated against the cell text. ares_pmf, kkr_kpec, arkvx and amg_pantheon move to null, bcred to True on its own Q2-2026 sentence. | 7.25 |
| R2-P1-13 | Cells 1.6, 1.7, 1.10, 3.7, 4.7 and 4.8 are written by the owned-cells writer from the analytics supplement's new series diagnostics, the held series and the plan records. 3.7 is plan-independent in the record and plan-specific in each memo. | 7.26 |
| R2-P1-14 | The case-law seeding literal is deleted. A fetcher saves the docket page, the questions presented and the opinion with hashed manifest rows and writes cell 5.7 from them. The unverified argument-term sentence is stripped from all 16 records through the corrections log. | 7.23 |
| R2-P1-15 | Memo: alignment note and the typed Lane A sentences in the benchmark section, structured boilerplate only above zero, plan-specific 3.7, 3.8 and 3.9 lines from the memo's own plan, the packet's Exhibit B under its heading, no status word as a headline. The memo gate reads all 64 memos and all 64 packets for another plan's label, counts or match file. | 7.26 |
| R2-P1-16 | The authority fetcher and parser round-trip (one blockquote line per paragraph, roman sub-paragraphs told from letters by sequence), a real-shaped synthetic XML fixture, a hashed manifest for the Federal Register document. The panel and the memo render the verbatim text only once the fetch has run on a networked machine. Ran on 2026-09-07 on Oscar's machine (70 paragraphs, content hash aef7a946 and the rest in the manifest row): the panel quotes the rule paragraph under each letter with the examples folded, the memo quotes the rule paragraphs in its regulatory basis and the full text in its last appendix, and the paragraphs ride the lazy chunk so the first-paint bundle stays under its pin. | 7.22, 7.29 |

## 8. Reproduction table, audit items 11 to 35

"Before" is the state the audit reproduced. "After" is the state of this
branch, with the figure read from the artifact, and "gate" names the check
that fails if the defect returns.

| item | audit finding | before | after | gate |
|---|---|---|---|---|
| 11 | Peer-composite comparison labeled KS-PME | 9 cards, 36 memos, cells 1.8 and 5.5, the Screener column | Slot G is a relative wealth ratio everywhere, the artifact carries no PME key on any appraisal-based comparison, the card says "Never a benchmark and never a PME" | `test_benchmark` (naming rule on every committed comparison), `reconcile` (cells, bundle, memos), `test_frontend` |
| 12 | Factor (k) filled with the (g)/(h) comparison | composite primary for 9 products | Two named slots. Slot K is a public or published index or proxy (BKLN for cclfx at 8 of 12, CDLI for bcred and ocic, the Cambridge PE benchmark for evergreen PE, NFI-ODCE for the REITs). Slot G is the cohort in cell 1.12 and is never a candidate | `test_benchmark` (no peer id on any menu, slot labels), `test_frontend` (both slot cards) |
| 13 | Composite label-aligned across March, June and December years, 0.9756 published, about 1.03 recomputed | cclfx 0.9756 on fiscal-year labels, 2022 dropped | cclfx on calendar years 2021 to 2025, n=4 in every period: fund growth 1.5567, composite 1.4668, ratio 1.0613. The audit's own subset (the three December-year peers as filed) reproduces at 1.028 inside the gate. Evergreen PE refuses the ratio | `test_benchmark` (hand recomputation 1.5567 and 1.028, alignment properties), `test_cohort` |
| 14 | Published indices structurally excluded by 4 possession points | CDLI 7 or 5, ODCE and Cambridge 7, composite 10 | Possession is one criterion worth 2. CDLI is Slot K for bcred and ocic at 9 of 12 (cited, no number), NFI-ODCE for breit, sreit and jll_ipt at 9, the Cambridge PE benchmark for evergreen PE at 9. The ledger prints every criterion so a reader sees a candidate lost on data, not fit. The normalizer for the CDLI and ODCE headline series is in the repository | `test_benchmark` (acquiring a series moves data_held alone), methodology section 6 |
| 15 | Expected-outcome table written first and reproduced by the cascade | `test_benchmark` asserted the methodology table | The table is deleted. The gate is property tests, and the methodology's worked-example figures are read back from the artifacts | `test_benchmark` |
| 16 | risk_liquidity_match read the held file's cadence | `_held_cadence` | The criterion reads the facts layer and prints the fund's dealing terms in its reason. The held kind moves nothing | `test_benchmark` (property) |
| 17 | Lane A typing inconsistent, fund-versus-declared PME not computed | cion_ares, amg_pantheon, ares_pmf declared, pflex and arkvx absent | Typed per product from cell 5.1. hl_paf's S&P 500 and MSCI World are SEC-required comparators at 7 of 12 with their own PMEs (1.1603 and 1.2386) on the card and in the memo | `test_benchmark` (typing and comparisons), `validate_data` (type vocabulary) |
| 18 | Ties logged as rankings ("outranked"), jll_ipt's ODCE described as held | ODCE over Cambridge RE by menu order | Equal-score eligible candidates are logged "tied" with the ordering sentence (pflex: CDLI and BKLN at 8, ordered on risk match). The status string says "cited, not held" for every unheld index. The licensed duplicate (Cambridge RE) is off the menu so no alphabetical tie decides a slot | `test_benchmark` (tie wording, no "outranked", jll_ipt status) |
| 19 | stepstone_spm mixed the fiscal-year series with a 5-year AATR, kkr_kpec mixed GAAP and transactional NAV | two bases per product | One basis each: stepstone_spm fiscal-year series (PSP reference KS-PME 1.8718 on growth 1.9504), kkr_kpec GAAP-NAV calendar years 2024 and 2025 (PSP reference KS-PME 1.0387, low confidence). Both logged as corrections | `test_benchmark` (one basis per product) |
| 20 | Two composites for one cohort | cohort artifact and engine differed | One member table (`src/tark_periods.py`) feeds the cohort artifact and Slot G. The Cohorts view charts it | `test_cohort`, `test_benchmark` |
| 21 | Escalation advice hard-coded | "a venture index" for every strategy | Generated from the strategy and the candidates scored | `test_benchmark` |
| 22 | Lab default proxy was the strategy ETF, the composite not explorable | 9 of 15 products | The lab opens on Slot K's series or the reference series and shows Slot G under its own label | `test_frontend` (lab default equals the artifact) |
| 23 | Allocation slider decorative | identical at 1%, 5%, 50% | Moves dollar demand and the plan's share of fund capacity for six products, removed with a sentence elsewhere | `test_liquidity`, `test_frontend` (JS parity) |
| 24 | Schedule H never read, slider ranking the reverse of the filings | consulting alone conditional-weak | Filed outflow proxy is the base (tech 11.69%, consulting 6.50%, manufacturer 11.53%, restaurant 10.75%). hl_paf: conditional-weak under tech (stressed 20.5% vs 20%), conditional under consulting (19.2%) | `test_liquidity` (lowest-filed plan never the only weak plan) |
| 25 | Scenario verdict a function of the plan alone | 13 products conditional under three plans | The verdict now moves with the filed rate and the wrapper's cap per product | `test_liquidity` |
| 26 | gate_history typed False on non-disclosure, validate_facts checked numbers only | ares_pmf, kkr_kpec, arkvx False | One written rule, evidence phrase per fact checked against the cell. Four products to null, bcred to True on its own proration sentence | `validate_data` (phrases), `test_liquidity` |
| 27 | Latent JS null-cap defect | `cadence * cap_pct` | Fixed in R2-P0-5, parity re-asserted over the filed base and the dollar figures | `test_frontend` |
| 28 | Constant citation list cited n/a cells | 3.5 and 3.7 in every match | Citations are the non-n/a cells per product (R2-P0-5), and 3.7 is now computed for every product | `test_liquidity` |
| 29 | Legal conclusion in 12 memos | fixed in R2-P0-9 | unchanged, still gated | `test_memo` |
| 30 | Cross-plan leaks, 24 unowned computed cells | tech counts in 18 memos of other plans, 3.8 and 3.9 cited one plan's match | 3.7 plan-independent in the record and plan-specific in each memo, 3.8 and 3.9 lines from the memo's own match, the six cell families owned by the writer | `test_memo` (64 memos and 64 packets, no other plan's label, counts or match file), `test_artifacts_fresh` |
| 31 | Case-law cell sourced to a string literal with an unverified argument-term sentence | seeding script, 16 records | Literal deleted, sentence stripped through the corrections log, fetcher with hashed manifest rows ready for a networked run | `test_ingest` (source-document checks), `test_memo` |
| 32 | Alignment note missing from the memo | card only | In the memo's benchmark section for Slot G and for any published-index comparison | `reconcile` (alignment note in every memo) |
| 33 | "Structured" boilerplate in all 64 memos | 15 products with 0 structured cells | The sentence appears only where the product has a structured cell | `test_memo` |
| 34 | Packet: empty Exhibit B, status word as headline, ODCE "selected" with no comparison, reconcile read 16 memos | as found | Exhibit B carries the section under its heading, the headline column never prints a status word, a selected cited index says "no comparison computed", reconcile reads all 64 memos | `test_memo`, `reconcile` |
| 35 | Census `listed_other_classes` not share-class aware | as found | Not in R2-P1 (R2-P3 per the audit's plan) | none yet |

## 9. What a networked person runs for R2-P1

Recorded in decisions 7.2, 7.8, 7.22 and 7.23. Each script prints its own
runbook in its header.

1. `python src/fetch_index_series.py --id cdli --url <sponsor page or file> --license "<terms as read>"`, then the same for `odce`. If the sponsor refuses automated access, download once by hand and add `--from-file <file> --fetched <date>`. Then `python src/produce.py`, the hook, and the corrections log carries every number that moved when the engine treats the index as held.
2. `export TARK_SEC_CONTACT='Name email'` and `python src/fetch_authority.py`, commit the markdown and its manifest row together, rebuild, and the panel and the memo render paragraphs (g) to (l). Done 2026-09-07 (decision 7.29).
3. `pip install pypdf`, `python src/fetch_caselaw.py fetch --opinion-url <confirmed URL>`, then `apply` (dry run) and `apply --write`, then the printed corrections and allowlist commands.
4. `python src/check_edgar_urls.py` before any deploy, as in the deploy log.

## 10. Gates grown in R2-P1

- `test_benchmark`: property tests replace the oracle table (one fact moves one criterion, affiliation only from the map, naming rule on every committed comparison, alignment rule, tie wording, one basis per product, the reference comparison, the published-index path on a synthetic file, the audit's hand recomputations, the methodology's worked examples read back).
- `reconcile`: Slot K, the reference comparison and Slot G tied across artifact, bundle, cells 1.8 and 1.12, facts and all 64 memos, with the naming rule on every peer sentence.
- `test_memo`: cross-plan leak gate over 64 memos and 64 packets, own-plan 3.7 line, no status word as a headline, structured sentence only above zero, Exhibit B under its heading.
- `test_liquidity`: filed outflow proxy recomputed per plan, the lowest-filed plan never the only weak plan, evidence phrases proven on a corrupted scratch copy, JS parity over the filed base and dollar figures.
- `validate_data`: typed Lane A entries, evidence phrases on booleans and enums, cell 1.12 in every record.
- `test_frontend`: both slot cards on every product, tie chips, the lab's default equals the artifact, the demo script's 48 surface rows, the spoken peer ratio only as the labeled peer comparison and equal to the artifact.
- `test_ingest`: the sources gate (authority round trip, case-law fetch on fixtures, the strip on a synthetic sentence).
- `corrections_log`: watches every owned cell (17), the v3 slots, the reference and declared comparisons, and takes `--only` so each write carries the cause of the task that moved the number.

## 11. R2-P1 commits

One commit per task group, all made after the full hook passed on the final
tree of the series (2026-09-06 18:36:55 to 18:39:51 UTC, 19 gates, exit 0,
1,027 PASS lines, 176 s). Where a file carries the hunks of more than one
task the message says so.

| commit | tasks |
|---|---|
| `e80250f` | R2-P1-1 |
| `ae8413a` | R2-P1-2, R2-P1-3, R2-P1-4, R2-P1-5, R2-P1-6, R2-P1-7, R2-P1-9 (and the regenerated record files of every R2-P1 task) |
| `68eeb78` | R2-P1-8 (and the liquidity view hunks of R2-P1-10 and R2-P1-11) |
| `2d6a80f` | R2-P1-10, R2-P1-11, R2-P1-12 |
| `e6a2816` | R2-P1-13, R2-P1-15 |
| `99d77d1` | R2-P1-14, R2-P1-16 |
| `12c4fd2` | R2-P1 close: decisions, demo script v9, queue, runbook, this report, corrections table |
| `be0aa29` | R2-P1-16 close: the authority text fetched on 2026-09-07, rendered, demo script v10 (decision 7.29) |

## 12. R2-P2, an advisor can act: tasks

| task | what landed | decision |
|---|---|---|
| R2-P2-1 | The verification gate admits a human signature: `test_invariants` accepts a verified row only in the form `verify_cell.py` writes (signer, ISO date, product JSON and CSV agreeing, the tool's two allowlist rows as the marker), pins extracted plus verified at 406 instead of verified at 0. `verify_cell.py` finds the recorded quote in the cited filing before it writes (manifest local file, `--fetch`, or `--document`), fragment by fragment across an ellipsis, and refuses without a document. The signer filter is word-bounded, so Talbot and Cabot are people. Audit items 37 and 38. | 7.4, 7.30 |
| R2-P2-2 | The advisor, plan-intake and verification forms offer their file as a named download (a browser blob with the bytes shown on screen) and a copy button, hidden again when the form is refused. The intake's sponsor hint no longer refuses "company" or "CO" and the reference sponsors' tokens are screened by the same list the build refuses to emit. Audit items 36 and 39. | 7.31 |
| R2-P2-3 | The ingest writes the held filing's record path and accession on every row it produces, so the verification tool resolves the document from the ledger alone. Audit item 41, first clause. The rest of item 41 waits for the networked run. | 7.32 |

## 13. Gates grown in R2-P2

- `test_invariants`: the verified pin becomes the signature contract (form, person, agreement, marker), the totals pin holds the sum.
- `test_ingest`: the word-bounded signer filter, in-order fragment matching, refusal without a document, refusal on a document without the quote, a real signature on the scratch record writing both files and the marker rows into a scratch report while the repository's report is untouched, the gate accepting that row and refusing a forged verified_by, a script signer and a JSON that disagrees with the CSV. Intake: a reference sponsor's token refused without printing it, "company" and "CO" accepted.
- `test_frontend`: each form's download name, blob bytes equal to the text shown, copy button, the file hidden on refusal, the "company, CO" label accepted.
- `test_ingest`: the ledger columns on every row the canned run wrote, the verification dry run resolving the filing from the ledger, refusal once the columns are blank.

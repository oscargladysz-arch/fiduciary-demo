# BUILD REPORT 7, round 2 remediation of the 2026-09-05 audit

Specification: `docs/GAP_ANALYSIS_2026-09-05.md` (46 numbered findings).
Decisions, defaults taken where the brief was silent, and every discrepancy
between the brief, the audit and the record: `docs/DECISIONS_2026-09.md`,
section 7. Branch `claude/tark-round-2-audit-jl9q4q` (the harness-assigned
branch, decision 7.7), one task-tagged commit per task, nothing squashed,
`main` untouched. This report grows by phase. Phase R2-P0 is complete and
recorded below. R2-P1, R2-P2 and R2-P3 are appended as they land.

The non-negotiables held throughout and the gates assert them: no cell was
set to `verified` (the count is 0 and the gate still pins it until R2-P2-1
rewrites it for a human signature), no number, quote, document name,
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

The deploy of this phase is entry 1 of `docs/DEPLOY_LOG.md`: source commit,
hook run, build, resulting `gh-pages` commit, the Tier 1 drawer check and
what could not be checked from the build container.

## 6. What could not be done from this container

Recorded in decision 7.8 and repeated here so nobody describes them as done:
the HTTP 200 check of the Tier 1 EDGAR URLs (`check_edgar_urls.py` exits 2
here, run it on a networked machine before Tuesday), the verbatim rule text
fetch, the CDLI and NFI-ODCE headline series, Schedule H, the case-law
source documents, the calibration run and the 17th product. Opening the live
URL is also blocked from here (github.io), so the Tier 1 drawer check was
run against the local build of the deployed commit and is repeated by the
frontend gate on every run.

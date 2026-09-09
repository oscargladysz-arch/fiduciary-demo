# BUILD REPORT 8, round 3 (the cloud session)

Cloud session. Specification: the round-3 brief of 2026-09-07 (sections 0
to 11), the audit `docs/GAP_ANALYSIS_2026-09-07.md`, and the decisions in
`docs/DECISIONS_2026-09.md` section 8 (8.1 to 8.20 decided by Oscar, 8.21
onward the judgment calls of this session, each marked default and
reversible). Branch `claude/r3-parallel-sessions-qw0o1f` (decision 8.23),
one task-tagged commit per task group, nothing squashed, `main` untouched,
one pull request per phase from its own branch (decision 8.25). The
laptop session's phases (R3-P3 networked runs, R3-P4 accounts and runs)
are not described here as done, in any words, because they did not run
here (decision 8.4).

The non-negotiables held and the gates assert them: no cell was set to
verified (the count is 0 on every surface and in every document), no
number, quote, document name, accession or date was invented, tier
language is never blurred, the four reference plans stay anonymized in
every document and view, gates only grew (20 to 22 in the hook, every
existing check kept), every changed published number is in the
corrections table under its task's cause, no secret entered a tracked
file, a build, a log line or a screenshot, no em dash or semicolon in
copy or documents, no partner data exists anywhere in the public tree, no
auth code was written, no service was created and no money was spent.

## 1. Timeline, planned against actual

| Milestone (section 3 of the brief) | Planned | Actual (cloud session) | Session |
|---|---|---|---|
| Nothing deploys before the last send (1:02pm Eastern Sep 8) | Sep 8 | Nothing deployed from this session. Entry 3 is Oscar's hand deploy after the last send, from pull request 4's recorded green run. | Oscar |
| The Tuesday patch prepared (R3-P0-2) | Sep 7 night | 2026-09-08, `949ef7d`, pull request 4, CI green | cloud |
| Design checkpoint on a preview build (R3-P1-5, -6) | Sep 16 | 2026-09-08, `d053954`, pull request 5, preview at `previews/5/#/design`, both themes, 1440 and 390 px. Approved by Oscar on 2026-09-08 as built, recorded as decision 8.21 (amended after this report was written). | cloud, Oscar |
| CI green on main with previews per pull request (R3-P0-3) | Sep 18 | 2026-09-08, `c3dedfb` and `3f4886b`, green on every push since, 16 runs, previews for pull requests 5, 6 and 7. Green on `main` waits for the first merge. | cloud |
| Ingest hardened with mocked-model tests (R3-P3-3) | Sep 18 | 2026-09-08, `2cb593e`, pull request 7, the ingest gate at 143 checks, CI green | cloud |
| R3-P2 complete | Sep 25 | 2026-09-08, `f2925c0`, `13b9b94`, `a484b77`, `b6027f8`, pull request 6, CI green, preview `previews/6/` | cloud |
| Index series, case law, census fields, identity out of the tree (R3-P3-1, -2, -7, -9) | Sep 25 | Not run here (network). The laptop session's. | laptop |
| Supabase project, Render service, private repository exist, schema and policies applied (R3-P4-1, -2) | Sep 25 | The schema, the policies, the storage rules and the runbook steps exist, pull request 8. No project, service or repository was created (Oscar's actions). | cloud, Oscar |
| R3-P1 passes every gate on a preview, old `site/js` deleted | Oct 2 | The views are not started and are blocked on the checkpoint approval (decisions 8.2 and 8.21). What exists: the design system, the components, the router, the web gate, and the data layer the views will read (the JSON chunks and the adapter, decision 8.37). | cloud |
| Workspace: invite, login, plan intake, fund submission, job status. The Actions worker runs a mocked-model job end to end | Oct 9 | The API, the admin CLI, the worker and the workflow templates exist and a mocked-model job runs end to end against a fake Supabase in the hook (`worker/test_worker.py`). Not run in Actions (no private repository yet). The frontend routes (R3-P4-5) wait on R3-P1. | cloud, laptop |
| The proof run within the $50 cap (R3-P4-8), the fallback rehearsed (R3-P4-9) | Oct 16 | Not run. The unattended path has not passed R3-P4-8. | laptop |
| Keep-alive, backup restored once, runbook complete, three concurrent mocked jobs | Oct 23 | The workflows and scripts exist. None has run against a host. | laptop |

Slippage: none on the cloud session's items. Every cloud item planned for
September landed on September 8, ahead of its date. The items that depend
on Oscar's accounts and the laptop session's network are reported above as
not run, on the day it is known.

## 2. What changed, by phase

### R3-P0-2, the Tuesday patch (`949ef7d`, pull request 4)
Citation buttons render on a fresh Screener and Comparison load (the base
chunk carries, per product, the list of cells that have a source, so the
button paints before the lazy chunk arrives and the drawer fills from that
chunk when it opens), Back and Forward work (history entries on view,
product, plan and cohort changes, replace on filter and slider changes,
`popstate` renders the route), every donut has a size. Three frontend
checks added. No type size, color, copy or spoken number touched. The
125% zoom line is in the runbook's setup. Deploy is Oscar's after the
last send, as entry 3 of the deploy log, from the recorded green run.

### R3-P0-3, CI and previews (`c3dedfb`, `3f4886b`)
`.github/workflows/gates.yml`: the full hook on every push and pull
request with the pinned Playwright, Chromium, LibreOffice Writer and now
poppler-utils, the EDGAR check from the repository secret, preview builds
under `gh-pages/previews/<pr>/` with the URL posted on the pull request
and the folder removed on close, the root deploy from a green `main` with
the deploy-log entry in a commit marked to skip CI. The workflow never
receives a model key, never runs the ingest, never sees partner data.
Twenty six runs so far: run 1 exited in 20 ms before any gate (dash treats
a dot-source of a missing file as fatal, fixed by `3f4886b`), every run
after it green, listed in section 5.

### R3-P1-5 and R3-P1-6, the design system (`d053954`, pull request 5)
`web/`: Vite, React 18, TypeScript, a hash router that pushes history and
rewrites legacy URLs, one tokens file (ink scale, surfaces, the accent
tuned to 4.5:1 and 3:1 in both themes, statuses, verdicts, type steps with
a 12 px floor, a 4-based space scale, radii, shadows, durations, the dark
set), a formatting layer on Intl, the components with their keyboard
behavior and ARIA, one chart module with text at token sizes and a table
alternative, the `#/design` route rendering every token and component in
every state, and `src/test_web.py` (the token gate, the formatting gate,
the guideline audit as properties on every route at 1440 and 390 px in
both themes, axe-core with zero findings at any level in
`docs/design/axe_2026-09-08.json`, the performance budget, keyboard
checks, the theme toggle, reduced motion, the preview subpath, the legacy
redirect). Eight screenshots under `docs/screenshots/design_checkpoint/`.
No view rebuilt: the checkpoint comes first (decision 8.2).

### R3-P1 data access, the chunks and the adapter (decision 8.37)
The view shapes live once, in `src/tark_views.py`. The site build writes
them as 195 JSON chunks under `site/data/` (an index, a screener chunk, and
per product a record, selection, cohort and facts chunk with a liquidity
and a documents chunk per plan), the workspace API answers its reference
routes from the same builder, and a job's worker writes a partner's record
with it. `web/src/data/` is the adapter the views will use: the static one
fetches the chunks relative to the document, which is correct at the site
root and under a pull request preview, the workspace one fetches the API
with the reader's session token, and the build flag picks one.

The gates that hold it: the allowlist scanner now reads the chunks as a
surface (17,803 string values across 195 files), the web gate runs the
adapter's unit tests and then fetches every chunk it declares from a page
served at the root and under `previews/999/`, and the workspace gate reads
the reference routes for their schema names. No view is rebuilt: this is
data, and it is not what the checkpoint gates.

### R3-P1, the frontend rebuilt and the old one deleted

All eighteen views. The route table is one list that the switch, the four
sidebar groups, the palette and the gate all read, so a route cannot exist in
one and not the other. Twelve global routes and six panels under a fund, with
the panels sharing a header that carries the fund, its wrapper, what the
record holds on it, and the plan selector only where the figures move with
the plan.

How it was built (decision 8.39): fourteen views in parallel, one agent per
view, each writing exactly one file against the design system, the copy
layer, the formatting layer and the adapter, each followed by an adversarial
pass over its own file. The route table, the stylesheet and every shared
component stayed in one pair of hands, and every view was integrated one at a
time through the gate. Eleven of the fourteen passed the guideline audit and
axe-core on the first run, and with one exception the defects the gate found
were in shared components rather than in views, so fixing one fixed every
view at once.

The defects the audit named, in the order it found them:
- a cell card was an h4 under an h2
- the note beside an inline control pushed a row past a 390 px viewport
- a table virtualized in one layout only and, when it did, rendered every row
  anyway because nothing bounded its container
- a sort button in a table header was a pixel under the tap target
- an inline popover button was squeezed under it by the line box around it
- a date field and a text area offered a password manager the chance to fill a
  plan's net assets
- a placeholder showed its example with no ellipsis
- links, navigation items and tabs left the double-tap delay in place
- a download link had a line box's hit target rather than a control's
- a gap cell printed a bare dash with its reason reachable only by hovering

Three defects the gate could not have found before this round, because the
rules that find them did not exist (decision 8.40). A route that renders
nothing passes every structural rule, so the audit now asserts each route
renders the record. A figure that renders blank passes too, which is how the
record's totals were found to nest their counts where a product's coverage
carries them flat. And a numeral written into a view's markup is a number
nobody can trace, so the gate scans every component and view for one.

Two capabilities the rebuild had lost and this restored: the analysis lab
recomputes the public market equivalent and the yearly edge against any proxy
and any window, which the first pass had reduced to two growth lines, and the
rule text is reachable from every route again, which the first pass had
dropped entirely (the paragraphs shipped in the chunks and no view opened
them).

The old application is deleted: its markup, its stylesheet, its eighteen views
and the gate that walked them. That gate had 242 checks and 227 of them
walked the old application. None were dropped. The rendered sweep for
developer strings moved to the web gate, over 120 rendered states of the
rebuilt routes. The figures on screen moved there too and are now read out of
the record rather than a hand-written list, 56 figures across all sixteen
funds. The interactive recompute is the liquidity panel's live-state checks.
The parity of the analytics moved to `web/src/analytics/*.test.ts`, which is
where a parity check belongs.

What deploys is assembled by one script (`src/assemble_site.py`) that puts the
built application and the record into one tree, refuses to run if the
application would overwrite the record's own folders, and keeps the
verification bundle out of the deployable tree. The bundle is still written,
because the reconciliation and the bundle checks read it, but nothing serves
it. The follow-up that would finish the job is to point the reconciliation at
the chunks and stop writing the bundle at all.

### R3-P2, the record and the documents (pull request 6)
- `f2925c0` R3-P2-1 to -6, -17e, -19 (decision 8.28): rubric v3.1 with a
  load-bearing risk and liquidity criterion read from the dealing terms on
  record, the collinear criterion dropped, 10 points, threshold 6 of 10,
  every score "x of N", Slot K by descriptor with the decided sentence,
  the tie as a typed flag, the escalation as two clauses, market-price
  labels for DXYZ and NSLR, the evergreen composite over the four
  March-year-end members, and the selection lock (`recorded_at`, inputs by
  accession and content hash, a SHA-256 record hash, a dated history copy)
  that the gate recomputes and reproduces from a fresh run. 208
  corrections rows.
- `13b9b94` R3-P2-7 to -11, -17a to -17d, R3-P1-10 (decisions 8.29 to
  8.31): the scenario record types what fired (the figures compared, the
  binding cap and its base, the cadence, the program status with its
  as-of date, the gating history, the per-window test) in one sentence on
  the card, in the bullet and in the record, gated by perturbation.
  `repurchase_program_status` typed from cell 3.1's own words for every
  product with a program. One coverage arithmetic (594 of 685 resolved).
  The accession escape gone. An intake plan passes the surfaces gate.
  Cell 3.7 per plan. n/a committee cells never open. sreit's net assets
  typed. The filed since-inception return typed and reconciled for cclfx.
  The liquidity view's bullets from one live state. 45 corrections rows.
- `a484b77` R3-P2-12 (decision 8.32): the allowlist gate, five prose
  rules over the bundle (15,538 strings), every rendered view (158
  states) and every document (65), with the provenance exemptions the
  design system names, a copy layer that prints the record's keys as
  words, the writers' own developer words rewritten at the source, thirty
  cells reworded with no figure changed under 28 allowlist rows and 93
  corrections rows.
- `b6027f8` R3-P2-13 to -18 (decision 8.33): the Investment Selection
  Record replaces the memo and the packet. Page one is the decision
  summary and the signature block. Attachment A is the verbatim rule text,
  one file cited by its content hash. Fixed Word layout (grids summing to
  the text width, repeating header rows, no split rows, keep-with-next, a
  running header, a page-count footer with the as-of date and the DRAFT
  mark, core properties from the record's date, a contents field). The
  punctuation rule in `display_copy`. The record gate reads the document
  XML and exports through LibreOffice Writer in CI (green: "LibreOffice
  text export of six records: the summary comes first, both verdicts read,
  the attachment hash is cited").

### R3-P3-3, the ingest hardened (`2cb593e`, pull request 7, decision 8.34)
Token and dollar accounting at a configured price list, the cost estimate
before the first call and the refusal when it is over the budget, the
budget and wall-time stops with every finished cell kept, a write after
every cell (atomic), one retry at half the context, per-cell page
retrieval under a context cap with the whole corpus cached when it fits,
inline XBRL and hidden blocks stripped, PDF through pdftotext, exhibits
when the registry names them, the accession and the record path from the
manifest row, a working dry run on a copy that includes this product's
raw filings, a progress callback, `run_product` as the library entry, and
`src/mock_model.py` with fixtures. `promote`, `fetch_edgar` and the census
cache bind under the data root. The ingest gate grew from 80 to 112 of its
own checks (143 with the sources block), every one against the mock
(decision 8.17). The price list is
configuration the laptop session confirms before the proof run.

### R3-P4, the network-free part (`da912d4`, `2e87656`, `65f2757`, `493c797`, pull request 8, decisions 8.35 and 8.36)
`db/`: the schema, the row-level policies and the storage rules. `app/`:
the API that verifies the Supabase token and forwards it so the policies
decide, with no service key in the request path, the admin CLI, and a
fake Supabase for the gates. `worker/`: the job runner with the pipeline
as a child process inside the pinned checkout, the workflow templates
for the private repository, the backup and the restore. `tests/tenancy/`:
the generator from the schema. `docs/WORKSPACE.md`: the runbook with the
free-tier table to fill on the day. `docs/security/asvs_review_2026-09-08.md`:
the review by a fresh subagent, with every fail fixed (section 9). Two gates joined the
hook. `service/` is retired. What a job yields for a fund nobody has
typed is stated in the runbook and in decision 8.35, not dressed up.

## 3. Gates, before and after

| Run | Tree | Gates | `[PASS]` lines | `[FAIL]` lines |
|---|---|---|---|---|
| Baseline (orientation, 2026-09-07) | `main` merged with round 2 | 19 | 1,048 | 0 |
| R3-P0-2 commit hook | `949ef7d` | 19 | 1,058 | 0 |
| Design checkpoint commit hook | `d053954` | 20 | 1,097 | 0 |
| R3-P2 record commit hook | `b6027f8` | 20 | 1,154 | 0 |
| R3-P3-3 commit hook | `2cb593e` | 20 | 1,192 | 0 |
| R3-P3-3 in CI (run 34183243632, Writer installed) | `2cb593e` | 20 | 1,193 | 0 |
| R3-P4 commit hook (the installed copy of the hook, 20 gates: the two new gates ran by hand before the commit, 41 and 19 checks green) | `da912d4` | 20 | 1,186 | 0 |
| R3-P4 in CI (the tracked hook, 22 gates, run 34184682230) | `da912d4` | 22 | 1,243 | 0 |
| R3-P4 runbook commit hook | `2e87656` | 22 | 1,243 | 0 |
| R3-P4 security fixes commit hook | `65f2757` | 22 | 1,252 | 0 |
| R3-P4 second-pass fixes commit hook | `493c797` | 22 | 1,258 | 0 |
| This report's own commit hook | `b77f0f9` | 22 | 1,259 | 0 |
| R3-P1 data access commit hook | `c2a24c6` | 22 | 1,263 | 0 |

The gates that grew or joined: `test_web` (20th, R3-P1-6, which now also
runs the data adapter's unit tests and reads every chunk from a served
page), the allowlist
family in `test_surfaces` (R3-P2-12), the selection lock and the
perturbation checks in `test_benchmark` and `test_liquidity` (R3-P2-1,
-7, -19), the record gate `test_memo` (R3-P2-18), the ingest gate's 32
new checks (R3-P3-3), `test_workspace` and `test_worker` (21st and 22nd,
R3-P4), and the allowlist scanner's new chunk family (R3-P1 data access).
Every earlier check is kept.

## 4. The verification protocol (section 9 of the brief), what ran here

1. Gates through the hook and CI: above. Every commit's hook run is in
   the session's run logs and every push's CI run is green
   (section 5). The deploy-log entry for this round is Oscar's entry 3.
2. The guideline audit: runs in `test_web` on the rebuilt routes (`#/` and
   `#/design`) at 1440 and 390 px in both themes, properties not phrases,
   with the fetched rule set pinned by hash in
   `docs/design/web-interface-guidelines_2026-09-07.md`. The public views
   are not rebuilt yet, so the audit covers the design route only.
3. axe-core: zero findings at any level on the rebuilt routes,
   `docs/design/axe_2026-09-08.json`.
4. The token, copy, formatting, performance and preview-subpath gates: in
   the hook and CI, green.
5. Manual browser checks with screenshots: the baseline set (43 images,
   `docs/screenshots/baseline_r3/`) and the design checkpoint set (8). The
   after set for the rebuilt views does not exist because the views are
   not rebuilt. The keyboard, Back and Forward, density and slider checks
   are asserted by `test_frontend` and `test_web`, not photographed.
6. The documents: the LibreOffice export ran in CI on six records and
   passed. Page counts and a visual check of pages 1 to 3 at Letter and
   A4 need Writer, which this container does not have (decision 8.24).
   Oscar or the laptop session opens four records. The sample comparison
   did not happen: `docs/reference/committee_packet_sample/` is absent
   (8.22 stays reserved).
7. The engine, recomputed by hand from the record files (section 6 below):
   cclfx Slot G 1.0613, the four filed outflow proxies, the risk and
   liquidity criterion for cclfx against BKLN and CDLI, one lock hash.
8. The workspace: the ASVS review ran here and every fail it found is
   fixed and gated (section 9). Nothing else ran, because nothing else
   can run without a host: the tenancy tests against a project, the proof
   run, the concurrent jobs, the fallback rehearsal, the restore, the
   keep-alive evidence and the free-tier table are the laptop session's
   and Oscar's, and are listed here as not run.
9. Money: section 7.
10. The audit reproduced: section 8.

## 5. CI runs on the public repository

| Run | Event | Branch | Head | Result |
|---|---|---|---|---|
| (none) | pull request 4 | `round-3-cloud-p0` | `949ef7d` | no CI run: the branch predates the workflow. Its hook run is in the session log (`r3p02_commit_hook.log`, green). |
| 1 | push | working branch | `c3dedfb` | failed in 20 ms before any gate (the dot-source under dash) |
| 2 | push | working branch | `3f4886b` | green |
| 3, 4, 5 | push, push, pull request 5 | working branch, `round-3-cloud-p1-design` | `d053954` | green, preview `previews/5/` |
| 6 | push | working branch | `f2925c0` | green |
| 7 | push | working branch | `13b9b94` | green |
| 8 | push | working branch | `a484b77` | green |
| 9, 10, 11 | push, push, pull request 6 | working branch, `round-3-cloud-p2` | `b6027f8` | green, preview `previews/6/` |
| 12 | push | working branch | `2cb593e` | green, 1,193 `[PASS]` |
| 13 | push | working branch | `da912d4` | green, 1,243 `[PASS]`, the 22-gate hook, the PDF reader exercised through pdftotext there |
| 14, 15 | push, pull request 7 | `round-3-cloud-p3` | `2cb593e` | green, preview `previews/7/` |
| 16 | push | working branch | `2e87656` | green |
| 17 | push | working branch | `65f2757` | green |
| 18 | push | working branch | `493c797` | green |
| 19, 20 | push, pull request 8 | `round-3-cloud-p4` | `493c797` | green, preview `previews/8/` |
| 21, 22, 23 | push, push, pull request 8 | working branch, `round-3-cloud-p4` | `b77f0f9` | green |
| 24, 25, 26 | push, push, pull request 9 | working branch, `round-3-cloud-p1-data` | `c2a24c6` | green, preview `previews/9/` |

Every run after the first is green. Runs later than 26 are in the
repository's own list: this report was written from the tree of `c2a24c6`.

The root deploy job is skipped on every run because no run is on `main`
yet. It fires on the first merge.

## 6. Hand recomputations (protocol item 7)

All four reproduce the record to the printed precision.

cclfx Slot G, the relative wealth ratio against the private credit peer
composite (`data/benchmarks/cliffwater_cclfx_selection.json`, `slot_g.composite.rows`).
Composite return per year is the equal-weight mean of the four members.
Growth is the product of 1 plus the return.

| Year | Fund return % | Member returns % (BCRED, PFLEX, CION Ares, OCIC) | Composite % | Fund growth | Composite growth |
|---|---|---|---|---|---|
| 2021 | 10.38 | 12.6, 11.29, 9.21, 4.3 | 9.3500 (recorded 9.35) | 1.1038 | 1.0935 |
| 2022 | 2.05 | 3.6, -15.36, -2.85, 5.2 | -2.3525 (recorded -2.35) | 1.1264 | 1.0678 |
| 2023 | 12.66 | 14.4, 9.25, 12.99, 13.5 | 12.5350 (recorded 12.54) | 1.2690 | 1.2016 |
| 2024 | 12.62 | 11.0, 15.27, 10.39, 11.5 | 12.0400 (recorded 12.04) | 1.4292 | 1.3463 |
| 2025 | 8.92 | 8.0, 12.2, 7.69, 7.9 | 8.9475 (recorded 8.95) | 1.5567 | 1.4668 |

Fund growth 1.5567 (recorded 1.5567), composite growth 1.4668 (recorded
1.4668), ratio 1.5567 / 1.4668 = 1.0613 (recorded 1.0613).

The four filed outflow proxies, (total expenses less administrative
expenses) / net assets at the start of the year * 100, from
`data/plans/*.json` `financials`:

| Plan | Arithmetic | Recomputed % | Recorded % |
|---|---|---|---|
| plan_consulting_alumni | (591,747,728 - 1,900,982) / 9,075,762,188 * 100 | 6.50 | 6.5 |
| plan_manufacturer_union | (84,229,623 - 0) / 730,545,316 * 100 | 11.53 | 11.53 |
| plan_restaurant_hourly | (149,669,956 - 1,621,511) / 1,376,802,027 * 100 | 10.75 | 10.75 |
| plan_tech_media | (53,548,189 - 553,200) / 453,298,334 * 100 | 11.69 | 11.69 |

The risk and liquidity criterion for cclfx (rubric v3.1, decision 8.28).
The fund's dealing terms on record: quarterly dealing, a 5% cap per
quarter, no gating history on record, program active, NAV pricing, price
not decoupled. BKLN is a daily market series against a semi-liquid NAV
fund: 1 of 3 (recorded 1). CDLI is an appraisal-based index against a
periodically dealt NAV fund with no proration and no suspension disclosed:
3 of 3 (recorded 3). CDLI is then rejected on provider independence (0,
Cliffwater's own index), so BKLN holds Slot K at 7 of 10 and CDLI is the
highest-ranked candidate at 6 of 10 with the affiliation reason, as the
record prints.

One lock hash: the canonical JSON of the cclfx selection without its
`record_hash` field (sorted keys, no whitespace, unicode kept, 15,238
bytes) hashed with SHA-256 gives
`1da9dd45ffa8f987acfa89e2e0a7018c026c41ee7e43bbcb151ae793d0897fd3`, the
recorded value.

## 7. Money

| Service | Tier | Limit | This month's spend |
|---|---|---|---|
| GitHub Actions (public repository) | free for public repositories | unlimited minutes on public repositories | $0 |
| GitHub Pages | free | 1 GB site, 100 GB bandwidth per month (read at setup by Oscar) | $0 |
| Anthropic model usage | the one proof run under `TARK_BUDGET_USD` (50) | $50 total | $0, no real call was made from this session |
| Supabase, Render, the private repository | not created | to be read on the day (runbook section 12) | $0 |

Recurring charges: $0. Model usage: $0. Nothing was enabled that charges.

## 8. The audit reproduced (protocol item 10)

Status words: Fixed, Partially fixed (what remains), Not attempted (why).

### Section 4.1, global chrome

| Item | Status | Where |
|---|---|---|
| Sidebar navigation (buttons, internal scroll, mobile block) | Not attempted. R3-P1 views wait on the checkpoint (8.21). The rebuilt shell exists (Sidebar, MobileNavSheet with links). | `web/src/components/shell.tsx` |
| Plan select on every view | Not attempted (R3-P1-2 gives the plan selector only to the panels that use it). | |
| Product select without a label | Not attempted (R3-P1). | |
| copy link, filter state in the share link | Not attempted (R3-P1). | |
| compact density wipes forms and sliders | Not attempted (R3-P1). | |
| Palette without a dialog role, Esc to body | Fixed in the component set (a labeled dialog, focus returned), not yet on the public views. | `web/src/components/overlay.tsx`, `test_web` |
| Authority panel | Not attempted (R3-P1). | |
| Hash routing, Back leaves the site | Fixed. History entries on view, product, plan and cohort changes, `popstate` renders the route, three navigations then three Backs return to the landing route. | `949ef7d`, `test_frontend` |
| Render model destroys focus and state | Partially fixed. The liquidity view rebuilds its bullets from one live state without a full re-render (R3-P1-10). The full component model is R3-P1. | `13b9b94` |
| Citation drawer without focus and a dialog role | Fixed in the component set (Drawer takes focus, labeled, Esc returns focus), not yet on the public views. | `test_web` |
| Glossary terms hover-only | Fixed in the component set (Term with keyboard and touch reach). | `web/src/components/primitives.tsx` |
| Fonts and first paint | Partially fixed. `source` ships in the base chunk so the landing paint is complete (rule 20). The bundle split and preloads are R3-P1. | `949ef7d` |
| Accessibility baseline | Partially fixed. The rebuilt routes pass axe-core with zero findings. The public views are unchanged. | `docs/design/axe_2026-09-08.json` |
| Theming | Fixed in the design system (light and dark, `color-scheme`, `data-theme`, the toggle gated). | `d053954` |
| Locale | Fixed in the design system (the formatting layer on Intl, gated). | `web/src/format` |
| Print | Not attempted (R3-P1). | |

### Section 4.2, the 18 views

| View | Status |
|---|---|
| Universe | Not attempted for the controls (R3-P1). The "Evaluate this fund" panel no longer offers a service (retired). |
| Funnel | Not attempted (R3-P1). The method notes no longer print bare identifiers (R3-P2-12). |
| Screener | Partially fixed: citation buttons on a fresh load (R3-P0-2), the dealing column reads the typed program status (R3-P2-7). Table layout, tabular figures, `aria-sort` are R3-P1. |
| Comparison | Partially fixed: the meaningful benchmark row prints "reference, not the benchmark" beside the proxy figure and the by-descriptor sentence where Slot K is cited (R3-P2-3). Chips and the hidden checkboxes are R3-P1. |
| Evidence Search | Not attempted (R3-P1). |
| Packet | Fixed for the documents: the record and the attachment replace the memo and the packet (R3-P2-13). The pin label and the controls are R3-P1. |
| Reference Plans | Fixed: an intake plan passes the surfaces gate, its provenance reads "plan intake, date" (R3-P2-10). The form attributes are R3-P1. |
| Candidate Roster | Fixed: the 16 rings render at size (R3-P0-2). Wrapper chips print labels through the copy layer (R3-P2-12). |
| Six-Factor Evaluation | Partially fixed: cell 3.7 leads with the plan's own sentence (R3-P2-11), headlines and cells go through the copy layer (R3-P2-12), 1.8 and 5.5 carry the reconciliation sentence (R3-P2-17d). Duplicate headlines are R3-P1. |
| Benchmark Selection | Fixed in substance: rubric v3.1, criterion display names, "x of N", the tie sentence, the escalation, the lock line (R3-P2-1 to -6, -19). The peer table overflow is R3-P1. |
| Cohorts | Fixed: caveats print fund names and labels, the exclusion log renders from the record, no path (R3-P2-5, -12). Headers and the chart are R3-P1. |
| Fee Matrix | Partially fixed: the chart title names the basis (R3-P2-12 rewording). The table layout is R3-P1. |
| Liquidity Match | Fixed: the bullets and the block read one live state (R3-P1-10), the drivers sentence names what fired (R3-P2-7). Slider labels and `aria-valuetext` are R3-P1. |
| Analysis Lab | Partially fixed: the judgment box prints display names (R3-P2-1). Links and chart text are R3-P1. |
| DXYZ Price vs NAV | Partially fixed: the series is labeled a market price everywhere (R3-P2-4). The placement is R3-P1. |
| De-smoothing Lab | Not attempted (R3-P1). |
| Coverage and Provenance | Fixed: the donuts render (R3-P0-2), the headline reads 594 of 685 with the four counts (R3-P2-8), no path in the cards (R3-P2-12). |
| Verification | Partially fixed: the queue source is named in words (R3-P2-12). The form and the row count are R3-P1. |

### Section 5, engine and record

| Item | Status |
|---|---|
| 1 `risk_liquidity_match` not load-bearing | Fixed, R3-P2-1: reads the dealing terms, perturbation moves it, gated. |
| 2 `pricing_basis_match` collinear | Fixed, R3-P2-2: dropped, 10 points, threshold 6 of 10. |
| 3 the reference figure beside the cited index with no "reference" word | Fixed, R3-P2-3: "reference, not the benchmark" on the Screener and Comparison rows, the by-descriptor sentence where Slot K is cited. |
| 4 dxyz and ssss series labels | Fixed, R3-P2-4: market price, no comparison on a decoupled price series. |
| 5 evergreen composite refused for all five | Fixed, R3-P2-5: the four March-year-end members align, the December member excluded by name. |
| 6 ssss's Nasdaq not typed | Fixed, R3-P2-4: typed as a required comparator. |
| 7 the reference loop breaks after the first candidate | Fixed, R3-P2-6: continues past a non-computable comparison and records the skip. |
| 8 the scenario verdict a function of the plan alone | Partially fixed, R3-P2-7: the record types what fired and the gate proves a product's cap moves its verdict alone. While every product's annual cap is 20% the verdicts still sort by plan. What remains is the data, not the rule. |
| 9 `suspended` literally sreit | Fixed, R3-P2-7: the program status is typed from cell 3.1's words for all 16. |
| 10 the accession escape | Fixed, R3-P2-9. |
| 11 cell 5.7 case law from snippets | Not attempted here: R3-P3-2 is the laptop session's networked run. |
| 12 685 of 685 resolved | Fixed, R3-P2-8: 594 of 685, the four counts side by side. |
| 13 `verify_cell --document` accepts any file with the quote | Not attempted: no signature this round (decision 8.12), and the brief withdrew R3-P3-10. Open for the round after. |
| 14 the first intake plan fails the hook | Fixed, R3-P2-10. |
| 15 "tied: tied on score" | Fixed, R3-P2-3: one tie sentence, a typed flag. |

### Section 6, the documents

| Item | Status |
|---|---|
| 1 length, the appendix printed twice, byte-identical body | Fixed, R3-P2-13 and -14: one record, the rule text once as an attachment cited by hash, page one the decision summary. |
| 2 tables break outside Word | Fixed, R3-P2-15: fixed grids, header rows repeat, no split rows, keep-with-next, read from the XML by the gate, exported through Writer in CI. |
| 3 no headers, footers, page numbers, contents, properties | Fixed, R3-P2-15. |
| 4 findings are raw cell text | Fixed, R3-P2-13: one generated sentence per factor leads, with a cell behind every clause, the cells follow through the copy layer. |
| 5 no metric defined | Fixed, R3-P2-13: KS-PME, Direct Alpha and the relative wealth ratio defined once, the rubric's criteria by display name. |
| 6 code and workflow language | Fixed, R3-P2-12: zero hits of the five prose rules over 65 documents. |
| 7 copy hygiene | Fixed, R3-P2-16 and -17: the punctuation rule, "periods", lowercase starts reworded at the source. Verdict codes still print in capitals by design and are now defined in the liquidity section. |
| 8 internal contradictions | Fixed: one coverage arithmetic (R3-P2-8), n/a committee cells never open (R3-P2-17b), sreit's net assets typed (R3-P2-17c), the 9.34% reconciled with the series figure (R3-P2-17d), the REIT refusal names the member with no period returns (R3-P2-5). |
| 9 the Recommendation adds nothing | Partially fixed, R3-P2-13: the decision summary and the recommendation say what the record found and what would change the outcome where the engines say it. The sample comparison (8.22) is still open. |
| 10 the packet's content belongs on the first pages | Fixed, R3-P2-13: page one. |

### Section 8, the design audit

| Item | Status |
|---|---|
| Accessibility, focus states, forms, animation, typography, content handling, charts, touch, layout, dark mode, locale, copy on the public views | Not attempted on the public views: R3-P1 waits on the checkpoint (8.2, 8.21). Every one of those rules is a gated property of the rebuilt components and routes (`test_web`), and the design checkpoint is on a preview build for Oscar's approval. |
| Tokens bypassed by literals | Fixed in the design system: the token gate refuses a literal in the built CSS and JS. |
| Information architecture around three tasks | Not attempted (R3-P1-1). The landing and the product-scoped routes are specified and the components exist. |
| Back and Forward, donuts, citations on a fresh load | Fixed (R3-P0-2). |

## 9. The security review (protocol item 8, the part that runs without a host)

A fresh subagent read only the policies, the schema, the storage rules,
the auth module, the API, the admin command line, the job runner and the
three workflow templates, against the OWASP ASVS 4.0.3 Level 1 controls
that apply to a hosted-auth application. Its report is
`docs/security/asvs_review_2026-09-08.md`.

First pass: pass 59, fail 10 across 9 fix items, not applicable 13, over 82
verdict rows. Every fail is fixed and every fix is held by a check in
`app/test_workspace.py` (49 checks) or `worker/test_worker.py` (22). The
ten, in the reviewer's order:

| Control | What it found | The fix |
|---|---|---|
| 4.1.2 | A member of workspace A could write a job row straight to the database naming workspace B's plan, and the runner would run it and upload B's plan data under A. | The product and the plan must belong to the job's workspace: composite keys on the table, the same test in the insert policy, and the runner refuses such a job before anything runs. |
| 4.1.3 | A revoke from the public role alone left the default grant, so the anon key could call the spend total and read every workspace's spend. | Revoked from anon and from authenticated, with the pattern named for every function added later. |
| 5.3.8 | The dispatch payload was expanded inside a shell script in the worker workflow, so a crafted job id would run commands beside the keys. | The payload reaches the step through the environment, never a shell script, and the runner refuses a job id that is not a uuid. |
| 12.3.1 | The plan key, chosen by the user, became a file name and an argument with no check on the runner. | The runner refuses a key outside the record's vocabulary, a manifest path outside the output, and a file type the store does not accept. |
| 5.1.3 | Workspace ids were unvalidated strings and the CIK was checked only for digits, so a malformed body surfaced as a failure of the workspace. | Ids validated by shape, the CIK by a digit pattern, a malformed body answered with one plain sentence. |
| 5.2.2 | No length cap on the plan's source note and no request body limit. | The note is capped and a body over 256 KB is refused before it is read. |
| 14.4.2 | No content-disposition header, so an answer could be rendered as a page. | Every answer is marked as an attachment. |
| 14.2.1 | The nightly backup installed a dependency unpinned, in the job that holds the database password. | It installs from the checkout's own requirements, and its checkout is a variable to pin at the proof run. |
| 8.3.2 | No way to remove a workspace's data on request. | A command in the admin CLI removes the storage prefix and then the row, which cascades through every table, with the runbook sentence beside it. |
| 11.1.4 | An unknown key id forced an unthrottled fetch of the project's key set on every request. | One forced refresh per thirty seconds. |

Beyond the fails, the observations taken in the same commit: the token's
issuer and its required claims are checked, the default privileges of the
authenticated role are revoked so row-level security is not the only
layer, a member can write only the five events a user causes into the
audit trail, the three workflows declare read-only permissions and the job
workflow refuses a commit that is not on the public main branch, the
database password and the token secret never reach the child process, the
child's error stream goes to a file so it cannot block the parent, the
store accepts only the file types the worker writes, the signed-URL
lifetime is clamped to an hour, both hosts must be https at load, and a
running job is requeued only with an explicit flag.

A second fresh reviewer then re-ran the review over the fixes and appended
its pass to the same file: pass 64, fail 5, not applicable 13, over the
same 82 rows. Five of the ten were closed and it confirmed each with
evidence. It earned its keep on the other five:

- The key-set fix did not bite where it mattered. The refresh window only
  applied once a key set was cached, and a project that signs with a
  secret publishes no keys, so the cache stayed empty and every request
  whose token merely claimed an asymmetric algorithm still cost one
  outbound fetch. The verifier now caches the answer whatever it holds,
  emptiness included, and makes at most one request per window. The
  unauthenticated database check answers from a one-minute cache for the
  same reason.
- The body cap measured only a request that declared its length. The API
  now refuses a body that declares none, rather than reading it to find
  out how big it is.
- The size cap lived in the API and not in the column a member can reach
  directly. It is in the column now, guarded for a project created from
  the earlier file.
- The sentence about removal was in the runbook and not in the app. It is
  in the footer.
- The four dependencies the nightly backup installs while it holds the
  database password are pinned.

Its seven findings in the changed lines are answered in the same commit:
an id or a key that only trails a newline is no longer the id or the key
it trails, a percent-encoded dot-dot in a manifest path is caught, the
child's error file is closed on every path out, and the removal command
pages the storage listing and refuses to delete the rows while an object
is still there. The rule that a new table or function needs its own
revoke went into the runbook, where it will be applied rather than
remembered.

Not fixed here because they are not code: multi-factor authentication on
the Supabase organization and on the account that owns the private
repository, and the project's access token lifetime. Both are Oscar's
actions at setup, in the runbook. The observations the second pass marks
not taken are product decisions rather than defects: a cap on how many
jobs a workspace may queue, a login row per token rather than per call,
and the API's log ring leaving memory for the host's log.

The lesson worth keeping: the first pass found ten fails, and the second
pass found that three of my ten fixes did not hold where the finding
lived. A review that is not re-run over its own fixes is a reading, not a
gate.

## 10. The R3-P3 runs

None ran here. The laptop session runs R3-P3-1 (index series), R3-P3-2
(case law), R3-P3-7 (census fields), R3-P3-9 (identity out of the tree),
and R3-P3-4 (calibration, only after the proof run and only with what
remains). Their real numbers go here when they exist.

## 11. The proof run, the recording and the cost

Not run. The unattended path has not passed R3-P4-8. The fallback has not
been rehearsed. The concurrent mocked jobs have not run in Actions. The
mocked-model job that runs end to end in the hook (`worker/test_worker.py`)
is a rehearsal against a fake Supabase, not the workspace.

## 12. The pull requests

| Number | Phase | Head | State |
|---|---|---|---|
| 4 | R3-P0-2, the Tuesday patch | `949ef7d` | open, Oscar merges and deploys it after the last send |
| 5 | R3-P1-5 and R3-P1-6, the design system and the checkpoint | `d053954` | merged. Approved by Oscar on 2026-09-08, decision 8.21 (amended after this report was written) |
| 6 | R3-P2, the record and the documents | `b6027f8` | open |
| 7 | R3-P3-3, the ingest hardened | `2cb593e` | open |
| 8 | R3-P4, the workspace, network-free | `b77f0f9` | open |
| 9 | R3-P1 data access, the chunks and the adapter | `c2a24c6` | open |

Each is stacked on the one before it, because each phase builds on the
last and `main` is untouched. Merging them in order, oldest first, is the
shortest path. Every one is green in CI on its own head.

## 13. Decisions taken by this session

8.21 to 8.35 in `docs/DECISIONS_2026-09.md`, each default and reversible,
with 8.21 and 8.22 reserved for Oscar and the sample. The ones a reader
of this report needs: 8.23 (branch names), 8.25 (one branch per phase for
pull requests), 8.28 (rubric v3.1), 8.29 (the scenario record), 8.30 (one
coverage arithmetic), 8.32 (the allowlist gate), 8.33 (the record), 8.34
(the ingest hardened, the price list as unconfirmed configuration), 8.35
(the workspace code, what a job yields for an untyped fund).

## 14. Open items, in the order they block

1. Oscar merges pull request 4 and deploys entry 3 after 1:02pm Eastern
   on September 8, then opens the checkpoint at `previews/5/#/design` and
   records 8.21. R3-P1's views start on that approval, and they have their
   data layer waiting for them (pull request 9).
2. Oscar creates the Supabase project, the Render service and the private
   repository per `docs/WORKSPACE.md` sections 2 to 4, and fills the
   free-tier table.
3. The laptop session runs the tenancy tests, confirms the price list,
   and runs R3-P3-1, -2, -7, -9.
4. The security work that needs a project: the tenancy tests from the
   outside, multi-factor authentication on the Supabase organization and
   on the GitHub account that owns the private repository, and the access
   token lifetime (section 9).
5. The registry entry and the facts mapping for ACAP Strategic Fund, from
   the filings, before the proof run.
6. Demo script v11 waits for the routes it would describe (R3-P1). The
   queue's "(v10)" line stays until then.

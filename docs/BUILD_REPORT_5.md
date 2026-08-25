# BUILD REPORT 5 — The Census (T1): the whole universe, the honest way

Mission: close the "Bloomberg for alts" gap for 401(k) fiduciaries without
lying about what a machine can know. Everything a fiduciary can now search
is tiered by provenance: **T1 structured filing data** (machine-read,
per-field source/ref/as-of, no model judgment) → **T2 extracted-unverified**
(AI extraction from filings, cited, awaiting human check) → **T3 verified**
(a human independently re-checked and signed — untouchable by tooling).

## The universe, counted (real counts, no padding)

Enumerated from filing behavior only (C2 — no strategy claims at T1):

| wrapper class | how detected | count |
|---|---|---:|
| interval fund (Rule 23c-3) | Form N-23C3A filings (form exists only for 23c-3 funds) | 245 |
| tender-offer CEF | SC TO-I filings ∩ N-2-family registration | 516 |
| BDC | Form N-54A election | 378 |
| non-traded REIT | SIC 6798 + 10-K + no exchange listing | 1,072 |
| listed CEF | N-2-family + exchange listing confirmed in submissions | 213 |
| unlisted CEF (other) | N-2-family, no listing, no tender/interval behavior | 1,174 |
| non-traded '34-Act (other) | roster reconciliation (see limits) | 1 |
| **TOTAL** | | **3,599** |

Raw enumeration sizes: 245 N-23C3A filers, 378 N-54A filers, 3,041 SC TO-I
filers (mostly operating-company self-tenders, filtered by the N-2
intersection), 2,277 N-2-family registrants, 1,255 SIC-6798 10-K filers.

**The dark universe**: 72,502 private pooled funds filed a NEW Form D in the
trailing 24 months (window 2024-09-01→2026-08-25; +34,357 amendments; EFTS
phrase query on the Form D "Pooled Investment Fund" industry group,
month-split so the 10k result cap never truncates). No NAV, no fee table,
no structured data — a 401(k) fiduciary cannot see into those at all. The
3,599 registered wrappers above are the entire addressable, evaluable
universe, and the census now covers it.

### Method limits, stated

- EFTS full-text coverage starts 2001; funds whose only relevant filings
  predate 2001 are not seen.
- "Listed" means an exchange listing confirmed in SEC submissions
  `exchanges[]`. An OTC quotation is NOT a listing — the tickers oracle
  alone misclassifies non-traded REITs (BREIT trades OTC as BSTT and
  remains non-traded). This distinction is enforced in code.
- `unlisted_cef_other` is real but behaviorally opaque: N-2 registrants
  with no listing and no detectable tender/interval activity. The wrapper
  is known; the liquidity mechanism (if any) is not — said so on every
  such record.
- One wrapper class cannot be enumerated universe-wide: non-traded '34-Act
  reporting companies (kkr_kpec's class) file 10-K like any operating
  company and have no distinguishing form signature. The roster member is
  added individually by reconciliation, with the limitation recorded in
  `method_notes` — its census count covers roster entries only, and says so.

### Enumeration war stories (why the counts can be trusted)

- browse-edgar's form-type-only company search returns an empty feed;
  enumeration pivoted to EFTS with empty query + forms filter, year-split.
- browse-edgar's SIC-axis atom feed has an SEC-side bug: every name renders
  as `ARRAY(0x…)`. Only `<cik>` elements are reliable; names were resolved
  from each entity's submissions JSON.
- Two enumeration reruns were forced by these discoveries; every pull is
  checkpointed per (form, year) and resumable, so reruns cost minutes.

## The three-tier data model as shipped

- `structured` is a first-class cell status (C1): value + source + dataset
  ref + as-of required by the validator, own badge ("structured filing
  data (T1)"), counted as covered. No model judgment is involved — the
  verification queue ranks these LOWEST (mis-transcription is the only
  failure mode).
- Every census field carries `{source: ncen|xbrl|submissions|efts, ref,
  as_of}` or an explicit `reason` (C3). `src/validate_census.py` enforces
  this mechanically and runs in the pre-commit gate.
- Name hints (C2) are derived from the fund NAME only, marked
  non-authoritative, excluded from filters by default, and badged "hint"
  wherever they render. A name is never a strategy claim.

## Census data sources

- **N-CEN structured datasets** (DERA, trailing four quarters 2025q3–2026q2):
  registrant type, total series, NAV-error-corrected flag, qualified-opinion
  flag, auditor, per-fund interval self-classification, avg net assets,
  management fee, net operating expenses, NAV/share, advisers.
- **XBRL companyconcept** (us-gaap:Assets, latest instant) for '34-Act
  filers (REITs/BDCs). NAV/share is issuer-custom tagged and therefore
  honestly `unavailable-structured` — not guessed.
- **submissions JSON** for every entity: current name, exchange listings,
  tickers, first filing, latest annual, filing-form histogram.
- **EFTS hit streams** as cadence evidence: per-CIK N-23C3A and SC TO-I
  counts with first/last dates.
- Interval cross-check: N-CEN self-classification vs N-23C3A filing
  behavior — agreement or disagreement recorded per entity, never smoothed.

## The promotion pipeline, demonstrated twice (roster 14 → 16)

`python src/promote.py <cik> --key <key>` — R1 identity check against live
EDGAR submissions (former names printed), 54-cell scaffold + paired evidence
CSV, census-answerable cells prefilled at status `structured`, extraction
worklist emitted. The prefill policy is deliberately narrow: only cells the
census FULLY answers (4.5 auditor+opinion flag, 4.6 NAV-error flag scoped
to its period, 1.10 unlisted n/a). A census field that partly answers a
cell (N-CEN management fee without its base) is never dressed up as an
answer.

### Case study 1 — ocic: Blue Owl Credit Income Corp. (CIK 1812554)

The census flagged it: non-traded BDC (N-54A 2020), unlisted, 46 SC TO-I
tenders 2021→2026. R1 caught the rename in the SEC record (f/k/a Owl Rock
Core Income Corp., renamed 2023-07-06). BDCs do not file N-CEN, so the
scaffold honestly prefilled only 1.10. Extraction findings that matter:
**1.25% management fee on NET assets** (the friendly variant — same rate as
bcred, and the advisory agreement governs over contradictory risk-factor
boilerplate the verifier caught); 12.5%/5%-hurdle two-part incentive
($232.2M income incentive FY2025); ~9% all-in expense ratios including
7.59% interest; **no early-repurchase fee at all** (vs bcred's 2%
deduction); 12 clean quarterly tenders BUT repurchase demand tripled to
$2.0B in FY2025 and the May 2026 offer is sized at the full 5% cap — with
tendered-vs-repurchased counts never disclosed, so `gate_history` ships as
an honest null ("a clean False would overclaim"). KS-PME 1.152 / Direct
Alpha 2.87%/yr vs BKLN on printed calendar returns 2021–2025; the 2020
partial-period return (7 weeks, non-annualized) was EXCLUDED from the
calendar-year series when the cohort composite tried to average it.

### Case study 2 — cion_ares: CION Ares Diversified Credit Fund (CIK 1678124)

Census: interval fund (39 N-23C3A filings 2017→2026), N-CEN self-class
AGREES with behavior. Scaffold prefilled 1.10 + 4.5 + 4.6 from N-CEN.
Extraction findings: **1.25% on leverage-inclusive MANAGED assets = 1.89%
of net assets at FY2025 actual leverage, per the prospectus's own
restatement** — and the N-CEN structured dataset independently reports the
1.89% figure, so T1 and T2 corroborate each other on the fee trap; 15%
income incentive over a 6% annualized hurdle with full catch-up; fee-table
totals 6.90–7.74% with no contractual cap ($0 expense support paid
FY2025); quarterly 5% offers, all four FY2025 offers undersubscribed
(2.09–2.88%); the **Adviser is its own Rule 2a-5 valuation designee for a
78.8% Level 3 book**; dual-adviser economics (Ares sub-adviser gets 40% of
fees). Ticker trap caught during integration: **CADCX is the Class C
ticker** — the shipped daily NAV series is Class I (CADUX, 2,293 days
2017→2026), which also powered computed de-smoothing diagnostics (lag-1
rho 0.075, raw vol 6.07% vs de-smoothed 6.57%, max drawdown −15.48%) and a
daily-granularity KS-PME 1.238 / Direct Alpha 2.37%/yr vs BKLN.

### Verification discipline on the promotions

Extraction ran as two agents over the six primary filings on disk; then a
12-verifier adversarial workflow (2 products × 6 factors, each prompted to
REFUTE) re-checked all 82 extracted/partial/n-a cells against the source
text. It returned 15 findings — 4 overclaims, 5 imprecisions, 6 minor
citation errors, **zero factually wrong numbers** — and every finding was
applied to the record before commit (e.g. "overlap is expected" →
"could be significant overlap", the filings' actual modality; lender legal
names marked as inference from facility names). Both products landed at
**zero unresolved cells** (all 16 products: 864/864 resolved), with
cohort placement (private_credit n=5 — percentile phrasing now R4-legal
and used), liquidity verdicts for all four plans, real benchmark
selections, and regenerated decision memos.

## Census UI as shipped (the ≤500KB chunk, honestly)

3,599 entities with per-field provenance cannot fit one 500KB chunk, so
the census ships in three honest pieces: a **302KB index chunk**
(screener fields only) that lazy-loads exactly like the series chunk; **64
detail shards** (~4.3MB total, ≤89KB each) carrying every field's
{source, ref, as-of}, fetched only when an entity is opened; and a **59KB
auditor/adviser sidecar** fetched only when a text filter is used — text
filters live in memory and never enter the URL (leak-proof links, same law
as evidence search). Universe screener (wrapper/listed/interval/tender-
recency/evaluated/assets filters + badged opt-in hint filter), entity
detail with detection evidence and the promotion panel, and the Funnel
(dark universe → enumerated → structured → evaluated → verified, true
counts). The tier legend renders on every census surface. To keep data.js
under its 1.2MB first-paint budget at 16 products, the per-plan liquidity
matches moved onto the lazy series chunk — no budget was weakened.

## Gates (only grew)

Pre-commit now runs 9 gates: validate_data, **validate_census** (new:
provenance completeness, C2 hint discipline, classification evidence,
roster linkage both ways, count consistency), test_analytics,
**test_cohort** (existed but was never wired into the hook — fixed),
test_benchmark, test_memo, test_app, build_site (anonymization refusal +
chunk budgets), test_frontend (**135 checks**, up from 110: census filter
correctness, cclfx census→evaluation round-trip, promoted-link parity
with the roster, BREIT/SREIT OTC-not-listed regression checks, C2 hint
badging, shard round-trips, lazy-chunk boot checks, budget enforcement).
The verification queue ranks `structured` cells LOWEST — machine
transcription of a structured dataset is the least likely thing in the
record to be wrong, and the ordering itself is a statement about honesty.

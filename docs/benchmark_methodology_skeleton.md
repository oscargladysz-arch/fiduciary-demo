# Benchmark Selection & Justification Methodology — Design Doc SKELETON (v0)
### Owner: Oscar. Window: Aug 8–30 (the free window). Reviewer: 1 Persona B practitioner (Gate C, Oct 2). Status: SKELETON — every section below is a set of questions the finished doc must answer, not answers.

**Design requirement (locked, post-Preqin):** the engine is INDEX-AGNOSTIC. It does not compete with index vendors; it generates candidates (third-party indices + constructed cohorts + PME), scores them, selects, and — the product — DOCUMENTS the justification and the rejections. Notation: `*` for multiplication, `/` for division, everywhere.

**Regulatory anchor to restate in §0:** the rule requires a "meaningful benchmark," states no single benchmark is meaningful for all DIAs, and falls back to "the history of a similar type of investment" where none exists. *Anderson v. Intel* (Oct Term 2026) will shape the pleading standard. The doc must read like it was written by someone who knows this.

---

## §1 Inputs inventory (per wrapper)
MUST ANSWER: For each of our six wrappers, exactly which return/cash-flow inputs exist? (NAV total-return series, distribution composition, tender/repurchase history, LP cash flows: yes/no/proxy.) Cross-reference dictionary cells 1.1, 1.4, 5.5. Where LP flows don't exist (all our '40 Act wrappers), specify the NAV+distribution proxy construction precisely.

## §2 Candidate generation (four lanes)
MUST ANSWER, per lane, with rules a stranger could replicate:
- **(a) Self-declared benchmark** (cell 5.1): always a candidate; never auto-accepted. What disqualifies it?
- **(b) Asset-class indices** (cell 5.3): the shortlist per strategy (private credit → Cliffwater CDLI, Morningstar LSTA; PE → Cambridge/Preqin/MSCI-Burgiss; RE → NCREIF NPI/ODCE). Which free tiers suffice for the demo; which need licensing (flag, don't buy).
- **(c) Constructed peer cohort** (cell 5.4): inclusion rules — same wrapper class? same strategy tags (from N-2 text)? minimum track length? minimum AUM? How is survivorship handled? Universe source = our EDGAR registry + expansion method.
- **(d) Public-market equivalent**: which index, and why (investability standard).

## §3 Comparability adjustments
MUST ANSWER with formulas:
- **De-smoothing** (cells 1.7, 4.8): specify the unsmoothing model. Slot: first-order autocorrelation adjustment, r_true_t = (r_obs_t − rho * r_obs_t-1) / (1 − rho). Justify model choice vs. alternatives; state when NOT to de-smooth.
- **Fee alignment**: net-vs-gross rules when comparing fund to index (indices are frictionless — how is that disclosed?).
- **Wrapper mismatch**: drawdown-fund IRR vs. NAV total return — why PME is the bridge; when a Preqin drawdown cohort is and is not a fair comparator for a '40 Act evergreen (this paragraph IS the answer to "why not just use Preqin").

## §4 PME / Direct Alpha
MUST ANSWER: exact computation, wrapper-level.
- Kaplan-Schoar PME = PV(distributions + terminal NAV, discounted at index) / PV(contributions, discounted at index). Define the wrapper-level proxy flows.
- Direct Alpha = the annualized rate implied by index-discounted net flows. 
- Worked example BY HAND: HL PAF vs. two candidate indices, using the FY22–FY26 NAV/distribution data already in evidence. (This worked example is the Gate C review artifact.)

## §5 Selection logic (the defensibility core)
MUST ANSWER: the scoring rubric — strategy match, risk/liquidity match, investability, data quality/provider independence (a manufacturer-owned index scores what on independence, and why that field exists) — weights, tie-breakers, and the rule for PRIMARY vs. SECONDARY benchmark. Non-negotiable output: every REJECTED candidate is logged WITH its reason. The rejection log is half the legal value.

## §6 Output contract → memo generator (M5)
MUST ANSWER: the exact fields the suitability memo consumes: chosen benchmark(s), construction description, adjustment disclosures, rejected-candidates table, rule-language citations, case-law hook (5.7). One page per product, written so an ERISA attorney nods.

## §7 Validation plan
Three test cases: hl_paf (should land a defensible composite), cliffwater_cclfx (CDLI should win — does the rubric agree?), dxyz (should FAIL to produce a meaningful benchmark — the engine must be able to say so; that is a feature). Then practitioner review (Weiss/Guo-type) before any code hardens.

## §8 Open questions to close via discovery
- Ellis: is Preqin/CDLI treated as fiduciary-grade for semi-liquid wrappers at Mercer, or directional-only?
- Sargent: will advisors accept a BlackRock-owned benchmark for a BlackRock product, or does independence bind?
- Any Persona B: what does your current scorecard use when no peer group exists — verbatim?

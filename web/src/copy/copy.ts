/* The copy layer (R3-P1-9). Every internal name a surface would otherwise
 * print goes through here, and every reader-facing sentence about the record
 * lives here rather than inside a view.
 *
 * Most of the mapping is the record’s own and arrives in the index chunk
 * (wrapper, base, strategy, lane, candidate, slot, cell, factor and rubric
 * names, and the glossary). What is added below is the frontend’s own
 * vocabulary: the seven statuses, the four verdicts, the tiers, the job
 * states and the universe’s classes. Nothing else may map a name.
 *
 * Tier language never blurs. Structured is the filing’s own tagged number,
 * extracted is a quote a person can open, human-verified is a signature. An
 * agent pass is not verification and never says so.
 */
import type { ChipKind } from "../components/primitives";

export interface Term { label: string; definition: string }

/* ------------------------------------------------------------- statuses */
/* The status a cell carries, as a reader meets it. `kind` picks the chip’s
 * pair, `tier` says which tier the row sits in, `label` is the only string
 * that reaches the DOM. */
export interface StatusCopy extends Term { kind: ChipKind; tier: "T1" | "T2" | "T3" | null }

const STATUS: Record<string, StatusCopy> = {
  structured: {
    label: "Structured", tier: "T1", kind: "structured",
    definition: "Read from the filing’s own tagged data, not from prose.",
  },
  "extracted-unverified": {
    label: "Extracted", tier: "T2", kind: "extracted",
    definition: "Read from a filing, with the document, the section and the quote on record. Not yet signed by a person.",
  },
  verified: {
    label: "Human-verified", tier: "T3", kind: "verified",
    definition: "A named person signed this row against the filing.",
  },
  computed: {
    label: "Computed", tier: null, kind: "computed",
    definition: "Calculated from other rows of this record, on figures you can open.",
  },
  partial: {
    label: "Partial", tier: null, kind: "partial",
    definition: "Part of the answer is on record and the rest is not disclosed.",
  },
  fetched: {
    label: "From a held series", tier: null, kind: "partial",
    definition: "Taken from a price or value series held on file, named beside the figure.",
  },
  "n/a": {
    label: "Not applicable", tier: null, kind: "na",
    definition: "The question does not apply to this wrapper, and the reason is on the row.",
  },
  "advisor-stated": {
    label: "Adviser input", tier: null, kind: "advisor",
    definition: "Entered by the adviser. An input to the evaluation, never evidence.",
  },
  pending: {
    label: "Pending", tier: null, kind: "pending",
    definition: "Not answered yet.",
  },
};

/** The status of a cell, as a reader meets it. An unknown status reads as
 *  pending rather than printing whatever the record held. */
export function status(raw: string | undefined | null): StatusCopy {
  const key = String(raw || "").trim().toLowerCase();
  if (STATUS[key]) return STATUS[key];
  // a status may carry a qualifier after a space, a comma, a colon or a
  // bracket: "n/a, not publicly available: ..." is still not applicable
  const head = key.split(/[\s:,(]/)[0];
  return STATUS[head] || STATUS.pending;
}

export const STATUS_ORDER = ["structured", "extracted-unverified", "verified", "computed",
  "partial", "fetched", "n/a", "advisor-stated"] as const;

/** The tier legend, said once per route that shows tiers. */
export const TIERS: Term[] = [
  { label: "Tier 1", definition: "Structured. The filing’s own tagged number." },
  { label: "Tier 2", definition: "Extracted and cited. A document, a section and a quote you can open." },
  { label: "Tier 3", definition: "Human-verified. A named person has signed the row." },
];

/* ------------------------------------------------------------- verdicts */
export interface VerdictCopy extends Term { kind: ChipKind }
const VERDICT: Record<string, VerdictCopy> = {
  aligned: {
    label: "Aligned", kind: "aligned",
    definition: "The fund’s dealing terms meet the plan’s stated need without a condition.",
  },
  conditional: {
    label: "Conditional", kind: "conditional",
    definition: "The need is met only while a stated condition holds.",
  },
  conditional_weak: {
    label: "Conditional and weak", kind: "weak",
    definition: "The condition that has to hold is thin, and the filings show how it can fail.",
  },
  misaligned: {
    label: "Misaligned", kind: "misaligned",
    definition: "The dealing terms do not meet the plan’s stated need.",
  },
};
export function verdict(raw: string | undefined | null): VerdictCopy {
  const key = String(raw || "").trim().toLowerCase().replace(/[\s-]+/g, "_");
  return VERDICT[key] || { label: "Not decided", kind: "pending", definition: "No verdict is on record for this pair." };
}

/* -------------------------------------------------------- the universe */
/* The seven wrapper classes the universe sorts by, in reader words. */
export const CENSUS_CLASS: Record<string, string> = {
  bdc: "Business development company",
  interval_23c3: "Interval fund",
  tender_cef: "Tender-offer closed-end fund",
  nontraded_reit: "Non-traded real estate trust",
  listed_cef: "Listed closed-end fund",
  unlisted_cef_other: "Unlisted closed-end fund, other",
  nontraded_34act_other: "Non-traded registrant, other",
};

/** The universe’s row fields, named for a reader rather than by position. */
export const CENSUS_FIELD: Record<string, string> = {
  nm: "Name",
  cls: "Class",
  assets: "Total assets",
  latest_annual: "Latest annual filing",
  tender_count: "Buyback windows on file",
  tender_last: "Last buyback window",
  listed: "Exchange-listed common shares",
  ncen: "Annual census filing on record",
  interval: "Files as an interval fund",
  agree: "The two interval signals agree",
  evaluated: "Evaluated in the record",
  structured: "Structured facts on file",
};

/* --------------------------------------------------------- job states */
/* The workspace’s job states. A queue position is a fact, never a guess at
 * a finish time. */
export const JOB_STATE: Record<string, string> = {
  queued: "Waiting to start",
  claimed: "Starting",
  running: "Running",
  done: "Finished",
  failed: "Stopped",
  refused: "Refused",
  cancelled: "Cancelled",
};

/* ------------------------------------------------------- the sentences */
/* Sentences a route says about the record as a whole. They are here so one
 * change reaches every surface that says them. */
export const SAY = {
  verificationPending: "Human verification: pending.",
  verificationCount: (signed: number, total: number) =>
    `${signed} of ${total} cells signed by a person. Offered to design partners.`,
  illustrative: "Illustrative",
  illustrativeNote: "A scenario you set, not a figure from a filing.",
  reference: "Reference comparison, not the benchmark",
  referenceNote: "A public series shown for orientation. The meaningful benchmark is the one the rule asks for.",
  planDependent: "This panel depends on the plan.",
  anonymized: "Plan sponsors are anonymized on every surface.",
  noRecord: "That part of the record has not been published here.",
  emptyFilter: "No row matches what you have selected.",
  loadingRecord: "Loading the record",
} as const;

/* ------------------------------------------------------------- titles */
/* One title per route, used by the document title and the page header, so a
 * route never builds its own name from a path segment. */
export const ROUTE_TITLE: Record<string, string> = {
  start: "Start",
  universe: "Universe",
  funnel: "From the universe to the record",
  screener: "Screener",
  compare: "Compare",
  search: "Evidence search",
  packet: "Committee packet",
  plans: "Reference plans",
  roster: "Candidate roster",
  coverage: "Coverage and provenance",
  verification: "Verification",
  design: "Design system",
  product: "Product",
};

/** Title Case for a heading or a button, sentence case for body copy. This
 *  returns the route’s own title and never a path segment. */
export function routeTitle(head: string): string {
  return ROUTE_TITLE[head] || ROUTE_TITLE.start;
}

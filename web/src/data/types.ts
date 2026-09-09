// The view shapes, as src/tark_views.py builds them. One schema name per
// shape: when a shape changes, its version changes with it and both sides
// change in the same commit.

export type ViewName = "record" | "selection" | "liquidity" | "cohort" | "facts" | "series" | "documents";

export interface CellDisplay {
  headline: string;
  plain: string;
  typed?: boolean;
}

export interface EdgarLink {
  form: string;
  filing_date: string;
  accession: string;
  url: string;
}

export interface Cell {
  element?: string;
  value: string;
  status: string;
  source?: string;
  section?: string;
  quote?: string;
  extracted_by?: string;
  verified_by?: string;
  display: CellDisplay;
  /** the ledger’s accession, said in words where it points at a set */
  accession?: string;
  /** the filings that accession resolves to, from the manifest */
  edgar?: EdgarLink[];
  rule?: { paragraph?: string; status?: string; note?: string };
}

export interface FactorRollup {
  label: string;
  total: number;
  evidenced: number;
  computed: number;
  soft: number;
  na: number;
}

export interface Coverage {
  structured: number;
  extracted: number;
  verified: number;
  computed: number;
  partial: number;
  fetched: number;
  na: number;
  pending: number;
  total: number;
  resolvable: number;
  resolved: number;
  evidenced: number;
  soft: number;
  headline: string;
}

export interface ProductSummary {
  key: string;
  fund_name: string;
  cik: string;
  wrapper_type: string;
  wrapper_label: string;
  cohort: string;
  strategy: string;
  depth: string;
  as_of: string;
  coverage: Pick<Coverage, "evidenced" | "computed" | "soft" | "na" | "verified" | "resolved" | "resolvable">;
  cited: string[];
}

export interface PlanSummary {
  key: string;
  label: string;
  plan_year: string;
  demand_sentence: string;
}

export interface IndexView {
  schema: "tark.index.v1";
  products: ProductSummary[];
  plans: PlanSummary[];
  cohorts: Record<string, { label: string; members: string[] }>;
  cells: Record<string, { label: string; factor: string }>;
  factors: Record<string, string>;
  labels: {
    wrapper: Record<string, string>;
    base: Record<string, string>;
    strategy: Record<string, string>;
    lane: Record<string, string>;
    candidate: Record<string, string>;
    slot: Record<string, string>;
  };
  glossary: Record<string, string>;
  rubric: {
    label: string;
    max: number;
    threshold: number;
    gate_min: number;
    criteria: string[];
    criterion_label: Record<string, string>;
    criterion_max: Record<string, number>;
    criterion_definition: Record<string, string>;
    tie_sentence: string;
    by_descriptor_sentence: string;
  };
  coverage_totals: { counts: Record<string, number>; [k: string]: unknown };
  rule: { citation: string; paragraphs: string; title: string };
  human_verification: string;
}

export interface ScreenerView {
  schema: "tark.screener.v1";
  products: Record<string, { fund_name: string; facts: Record<string, unknown>; cited: string[] }>;
  human_verification: string;
}

export interface RecordView {
  schema: "tark.record.v1";
  product_key: string;
  fund_name: string;
  cik: string;
  wrapper: string;
  wrapper_label: string;
  coverage: Coverage;
  factors: Record<string, FactorRollup>;
  cells: Record<string, Cell>;
  registry: Record<string, string | boolean | null>;
  human_verification: string;
}

export interface SelectionView {
  schema: "tark.selection.v1";
  product_key: string;
  selection: Record<string, unknown> | null;
}

export interface LiquidityView {
  schema: "tark.liquidity.v1";
  product_key: string;
  plan_key: string;
  match: Record<string, unknown> | null;
}

export interface CohortView {
  schema: "tark.cohort.v1";
  product_key: string;
  cohort_id: string;
  cohort: Record<string, unknown> | null;
}

export interface FactsView {
  schema: "tark.facts.v1";
  product_key: string;
  facts: Record<string, unknown>;
}

export interface DocumentsView {
  schema: "tark.documents.v1";
  product_key: string;
  plan_key: string;
  record: string;
  attachment: string | null;
  human_verification: string;
}

export interface Manifest {
  schema: "tark.chunks.v1";
  shapes: Record<string, string>;
  products: string[];
  plans: string[];
  files: Record<string, number>;
}

/** A daily series in transport form: a base date, day offsets, values. */
export interface CompactSeries { base: string; d: number[]; v: number[] }

export interface DailyView {
  schema: "tark.daily.v1";
  series_id: string;
  source: Partial<SeriesSource>;
  points: CompactSeries;
}

/** Expand a transported series back to [date, value] pairs. */
export function expandSeries(s: CompactSeries | null | undefined): [string, number][] {
  if (!s || !s.base) return [];
  const base = new Date(s.base + "T00:00:00Z").getTime();
  const day = 24 * 60 * 60 * 1000;
  return s.d.map((offset, i) => [new Date(base + offset * day).toISOString().slice(0, 10), s.v[i]]);
}

export interface SeriesSource {
  ticker: string; source: string; role: string;
  first: string; last: string; pulled?: string;
  column: string; label: string;
}

export interface SeriesView {
  schema: "tark.series.v1";
  product_key: string;
  annual: Record<string, string>[];
  monthly: [string, number][];
  quarterly: [string, number][];
  daily: { series: string; ticker: string; column: string; price_series: boolean; label: string } | null;
  sources: Record<string, SeriesSource>;
  supplement: Record<string, unknown>;
  /** the filed value-per-share table a fund prints beside its market price */
  filed_nav: Record<string, unknown> | null;
}

export interface PlansView {
  schema: "tark.plans.v1";
  plans: Record<string, Record<string, unknown>>;
  order: string[];
  human_verification: string;
}

export interface FunnelStep { id: string; label: string; value: number | null; note: string }
export interface FunnelView {
  schema: "tark.funnel.v1";
  steps: FunnelStep[];
  counts_by_class: Record<string, number>;
  method_notes: string[];
  as_of: string;
  totals: Record<string, unknown>;
  crosscheck: Record<string, unknown>;
  verified_by_product: Record<string, number>;
  human_verification: string;
}

export interface CoverageView {
  schema: "tark.coverage.v1";
  totals: { counts: Record<string, number>; [k: string]: unknown };
  products: Record<string, { fund_name: string; coverage: Coverage; factors: Record<string, FactorRollup> }>;
  crosscheck: Record<string, unknown>;
  human_verification: string;
}

export interface VerificationRow {
  product_key: string; fund_name: string; cell: string; tier: number | null;
  element: string; status: string; source: string; section: string; verified_by: string;
}
export interface VerificationView {
  schema: "tark.verification.v1";
  rows: VerificationRow[];
  tiers: Record<string, string>;
  verified: Record<string, number>;
  verifiable: Record<string, number>;
  signed: number;
  total: number;
  human_verification: string;
}

export interface AuthorityView {
  schema: "tark.authority.v1";
  rule: Record<string, unknown>;
  citation: string;
  authority: { paragraphs?: Record<string, string[]>; [k: string]: unknown };
  cells: Record<string, Record<string, unknown>>;
}

export interface EvidenceRow {
  product_key: string; fund_name: string; cell: string; element: string;
  value: string; status: string; source: string; section: string; quote: string;
}
export interface EvidenceView {
  schema: "tark.evidence.v1";
  rows: EvidenceRow[];
  human_verification: string;
}

export interface CohortsView {
  schema: "tark.cohorts.v1";
  cohorts: Record<string, Record<string, unknown>>;
  caveats: Record<string, unknown>;
  exclusions: { name: string; reason: string }[];
  members: Record<string, string[]>;
  human_verification: string;
}

export interface LabView {
  schema: "tark.lab.v1";
  matrix: Record<string, Record<string, {
    score: number; max: number; criteria: Record<string, number>; reasons: string[];
    candidate: string; on_menu: boolean; eligible: boolean; verdict: string;
  }>>;
  profiles: Record<string, Record<string, unknown>>;
  library: Record<string, Record<string, unknown>>;
  sources: Record<string, SeriesSource>;
  human_verification: string;
}

/** One universe row, positional to keep 3,599 of them small. */
export type CensusRow = [string, string, number, number, string, number, string, number, string];
export interface CensusView {
  schema: "tark.census.v1";
  as_of: string;
  total: number;
  counts_by_class: Record<string, number>;
  dark_universe: Record<string, unknown>;
  method_notes: string[];
  cls_codes: Record<string, string>;
  hints: string[];
  shards: number;
  row_fields: string[];
  entities: Record<string, CensusRow>;
}

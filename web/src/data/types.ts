// The view shapes, as src/tark_views.py builds them. One schema name per
// shape: when a shape changes, its version changes with it and both sides
// change in the same commit.

export type ViewName = "record" | "selection" | "liquidity" | "cohort" | "facts" | "documents";

export interface CellDisplay {
  headline: string;
  plain: string;
  typed?: boolean;
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
  labels: { wrapper: Record<string, string>; base: Record<string, string> };
  coverage_totals: Record<string, number | string>;
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

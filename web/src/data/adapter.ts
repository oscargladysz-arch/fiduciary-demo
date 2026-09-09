// One interface between the views and wherever the record comes from.
//
// The public demo reads JSON chunks the site build wrote (StaticAdapter).
// A partner's workspace reads the same shapes from the API (ApiAdapter).
// A view never knows which one it has: it asks for a record and receives
// the shape src/tark_views.py builds, whichever server answered.
//
// The adapter is chosen at build time by TARK_ADAPTER (see vite.config.ts).

import type {
  AuthorityView, CensusView, CohortView, CohortsView, CoverageView, DailyView, DocumentsView,
  EvidenceView, FactsView, FunnelView, IndexView, LabView, LiquidityView,
  Manifest, PlansView, RecordView, ScreenerView, SelectionView, SeriesView,
  VerificationView,
} from "./types";

export interface TarkData {
  /** How this adapter reaches the record, for the empty states to say. */
  readonly source: "static" | "api";
  getIndex(): Promise<IndexView>;
  getScreener(): Promise<ScreenerView>;
  getRecord(productKey: string): Promise<RecordView>;
  getSelection(productKey: string): Promise<SelectionView>;
  getCohort(productKey: string): Promise<CohortView>;
  getFacts(productKey: string): Promise<FactsView>;
  getSeries(productKey: string): Promise<SeriesView>;
  getLiquidity(planKey: string, productKey: string): Promise<LiquidityView>;
  getDocuments(planKey: string, productKey: string): Promise<DocumentsView>;
  /** The manifest, where the source has one. The static build does. */
  getManifest?(): Promise<Manifest>;
  /* The reference set the public demo describes. A workspace has its own
   * record and no universe, so these are optional and a view that wants one
   * asks whether the source has it before it renders a route that needs it. */
  getPlans?(): Promise<PlansView>;
  getFunnel?(): Promise<FunnelView>;
  getCoverage?(): Promise<CoverageView>;
  getVerification?(): Promise<VerificationView>;
  getAuthority?(): Promise<AuthorityView>;
  getEvidence?(): Promise<EvidenceView>;
  getCohorts?(): Promise<CohortsView>;
  getLab?(): Promise<LabView>;
  getCensus?(): Promise<CensusView>;
  getCensusShard?(n: number): Promise<Record<string, Record<string, unknown>>>;
  getCensusSearch?(): Promise<Record<string, string>>;
  /** One held daily series by its id, for the chart that draws it. */
  getDailySeries?(seriesId: string): Promise<DailyView>;
}

export class DataError extends Error {
  constructor(readonly url: string, readonly status: number, message: string) {
    super(message);
    this.name = "DataError";
  }
}

/** One sentence a view may show. Never a status code on its own. */
export function dataErrorSentence(e: unknown): string {
  if (e instanceof DataError) {
    if (e.status === 404) return "That part of the record is not on this build.";
    if (e.status === 401 || e.status === 403) return "Sign in to a workspace you belong to.";
    return "The record could not be read just now. Try again in a moment.";
  }
  return "The record could not be read just now. Try again in a moment.";
}

export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new DataError(url, 0, "the record could not be reached");
  }
  if (!response.ok) throw new DataError(url, response.status, `the record answered ${response.status}`);
  return (await response.json()) as T;
}

/** A cache that keeps one promise per key, so two views asking at once ask once. */
export function once<T>(): (key: string, make: () => Promise<T>) => Promise<T> {
  const held = new Map<string, Promise<T>>();
  return (key, make) => {
    const there = held.get(key);
    if (there) return there;
    const started = make().catch((e) => {
      held.delete(key);            // a failure is not an answer to keep
      throw e;
    });
    held.set(key, started);
    return started;
  };
}

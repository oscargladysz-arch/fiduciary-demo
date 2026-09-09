// The public demo's adapter: the JSON chunks src/build_site.py wrote under
// data/, beside the built application. Paths are relative to the document,
// so the same build serves the site root and a pull request preview under
// previews/<number>/ without knowing which it is.

import { fetchJson, once, type TarkData } from "./adapter";
import type {
  AuthorityView, CensusView, CohortView, CohortsView, CoverageView, DailyView, DocumentsView,
  EvidenceView, FactsView, FunnelView, IndexView, LabView, LiquidityView,
  Manifest, PlansView, RecordView, ScreenerView, SelectionView, SeriesView,
  VerificationView,
} from "./types";

export class StaticAdapter implements TarkData {
  readonly source = "static" as const;
  private readonly base: string;
  private readonly hold = once<unknown>();

  constructor(base?: string) {
    // "data/" against the document's own base URL: correct at the root and
    // under a preview subpath, and it never leaves the deployed folder
    this.base = base ?? new URL("data/", document.baseURI).toString();
  }

  private get<T>(path: string): Promise<T> {
    return this.hold(path, () => fetchJson<T>(this.base + path)) as Promise<T>;
  }

  getIndex(): Promise<IndexView> { return this.get<IndexView>("index.json"); }
  getScreener(): Promise<ScreenerView> { return this.get<ScreenerView>("screener.json"); }
  getManifest(): Promise<Manifest> { return this.get<Manifest>("manifest.json"); }
  getRecord(k: string): Promise<RecordView> { return this.get<RecordView>(`product/${k}/record.json`); }
  getSelection(k: string): Promise<SelectionView> { return this.get<SelectionView>(`product/${k}/selection.json`); }
  getCohort(k: string): Promise<CohortView> { return this.get<CohortView>(`product/${k}/cohort.json`); }
  getFacts(k: string): Promise<FactsView> { return this.get<FactsView>(`product/${k}/facts.json`); }
  getLiquidity(plan: string, k: string): Promise<LiquidityView> {
    return this.get<LiquidityView>(`product/${k}/liquidity/${plan}.json`);
  }
  getDocuments(plan: string, k: string): Promise<DocumentsView> {
    return this.get<DocumentsView>(`product/${k}/documents/${plan}.json`);
  }
  getSeries(k: string): Promise<SeriesView> { return this.get<SeriesView>(`product/${k}/series.json`); }

  getPlans(): Promise<PlansView> { return this.get<PlansView>("plans.json"); }
  getFunnel(): Promise<FunnelView> { return this.get<FunnelView>("funnel.json"); }
  getCoverage(): Promise<CoverageView> { return this.get<CoverageView>("coverage.json"); }
  getVerification(): Promise<VerificationView> { return this.get<VerificationView>("verification.json"); }
  getAuthority(): Promise<AuthorityView> { return this.get<AuthorityView>("authority.json"); }
  getEvidence(): Promise<EvidenceView> { return this.get<EvidenceView>("evidence.json"); }
  getCohorts(): Promise<CohortsView> { return this.get<CohortsView>("cohorts.json"); }
  getLab(): Promise<LabView> { return this.get<LabView>("lab.json"); }
  getCensus(): Promise<CensusView> { return this.get<CensusView>("census/index.json"); }
  getCensusShard(n: number): Promise<Record<string, Record<string, unknown>>> {
    return this.get<Record<string, Record<string, unknown>>>(`census/d/${n}.json`);
  }
  getCensusSearch(): Promise<Record<string, string>> {
    return this.get<Record<string, string>>("census/search.json");
  }
  getDailySeries(id: string): Promise<DailyView> { return this.get<DailyView>(`daily/${id}.json`); }
}

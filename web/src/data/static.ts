// The public demo's adapter: the JSON chunks src/build_site.py wrote under
// data/, beside the built application. Paths are relative to the document,
// so the same build serves the site root and a pull request preview under
// previews/<number>/ without knowing which it is.

import { fetchJson, once, type TarkData } from "./adapter";
import type {
  CohortView, DocumentsView, FactsView, IndexView, LiquidityView,
  Manifest, RecordView, ScreenerView, SelectionView,
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
}

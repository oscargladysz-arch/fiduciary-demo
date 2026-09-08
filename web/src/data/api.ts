// The workspace's adapter: the same shapes from the API, with the reader's
// own session token on every request, so the database's policies decide what
// comes back. The sixteen reference products are read-only and come from the
// reference routes. A partner's own record is addressed by its record id.

import { fetchJson, once, type TarkData } from "./adapter";
import type {
  CohortView, DocumentsView, FactsView, IndexView, LiquidityView,
  RecordView, ScreenerView, SelectionView, SeriesView, ViewName,
} from "./types";

export type TokenSource = () => string | null | Promise<string | null>;

export class ApiAdapter implements TarkData {
  readonly source = "api" as const;
  private readonly hold = once<unknown>();

  constructor(private readonly base: string, private readonly token: TokenSource,
              private readonly recordId?: string) {}

  private async headers(): Promise<HeadersInit> {
    const t = await this.token();
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  private async ask<T>(path: string): Promise<T> {
    return fetchJson<T>(`${this.base}${path}`, { headers: await this.headers() });
  }

  private get<T>(path: string): Promise<T> {
    return this.hold(path, () => this.ask<T>(path)) as Promise<T>;
  }

  /** A workspace record's view when this adapter was given a record id,
   *  the read-only reference otherwise. */
  private view(name: ViewName, productKey: string, plan?: string): string {
    if (this.recordId) return `/records/${this.recordId}/${name}.json`;
    const q = plan ? `?plan=${encodeURIComponent(plan)}` : "";
    return `/reference/${productKey}/${name}.json${q}`;
  }

  getIndex(): Promise<IndexView> { return this.get<IndexView>("/reference/index.json"); }
  getScreener(): Promise<ScreenerView> { return this.get<ScreenerView>("/reference/screener.json"); }
  getRecord(k: string): Promise<RecordView> { return this.get<RecordView>(this.view("record", k)); }
  getSelection(k: string): Promise<SelectionView> { return this.get<SelectionView>(this.view("selection", k)); }
  getCohort(k: string): Promise<CohortView> { return this.get<CohortView>(this.view("cohort", k)); }
  getFacts(k: string): Promise<FactsView> { return this.get<FactsView>(this.view("facts", k)); }
  getSeries(k: string): Promise<SeriesView> { return this.get<SeriesView>(this.view("series", k)); }
  getLiquidity(plan: string, k: string): Promise<LiquidityView> {
    return this.get<LiquidityView>(this.view("liquidity", k, plan));
  }
  getDocuments(plan: string, k: string): Promise<DocumentsView> {
    return this.get<DocumentsView>(this.view("documents", k, plan));
  }
}

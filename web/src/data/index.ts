// Which adapter this build has, decided once, at build time.

import { StaticAdapter } from "./static";
import { ApiAdapter, type TokenSource } from "./api";
import type { TarkData } from "./adapter";

declare const __TARK_ADAPTER__: string;
declare const __TARK_API_BASE__: string;

let held: TarkData | null = null;
let tokenSource: TokenSource = () => null;

/** The workspace sets this once the reader has a session. */
export function useToken(source: TokenSource): void {
  tokenSource = source;
  held = null;
}

export function data(): TarkData {
  if (!held) {
    held = __TARK_ADAPTER__ === "api"
      ? new ApiAdapter(__TARK_API_BASE__, () => tokenSource())
      : new StaticAdapter();
  }
  return held;
}

export { StaticAdapter } from "./static";
export { ApiAdapter } from "./api";
export { DataError, dataErrorSentence } from "./adapter";
export type { TarkData } from "./adapter";
export type * from "./types";

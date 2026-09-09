/* Reading the record from a view: one hook, three states, no view left to
 * invent its own loading or error string.
 *
 * `useAsync` is deliberately small. The adapter already holds one promise per
 * chunk, so two views asking for the same thing ask the network once, and a
 * component that unmounts mid-flight simply stops writing state. */
import { useEffect, useMemo, useRef, useState } from "react";
import { data } from "./index";
import { dataErrorSentence } from "./adapter";
import type { IndexView } from "./types";

export interface Asked<T> {
  value: T | null;
  error: string | null;
  loading: boolean;
}

export function useAsync<T>(make: () => Promise<T>, deps: unknown[]): Asked<T> {
  const [state, set] = useState<Asked<T>>({ value: null, error: null, loading: true });
  const seq = useRef(0);
  useEffect(() => {
    const mine = ++seq.current;
    set((s) => ({ value: s.value, error: null, loading: true }));
    make().then(
      (value) => { if (seq.current === mine) set({ value, error: null, loading: false }); },
      (e) => { if (seq.current === mine) set({ value: null, error: dataErrorSentence(e), loading: false }); },
    );
    // the caller’s deps are the identity of the request
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

/** The index: the roster, the plans, the labels and the counts every route
 *  needs before it knows what it is showing. */
export function useIndex(): Asked<IndexView> {
  return useAsync(() => data().getIndex(), []);
}

/** The product keys and the plan keys this build has, for validating what a
 *  URL claims before a view acts on it. */
export function useKeys(index: IndexView | null) {
  return useMemo(() => ({
    products: new Set((index?.products || []).map((p) => p.key)),
    plans: new Set((index?.plans || []).map((p) => p.key)),
  }), [index]);
}

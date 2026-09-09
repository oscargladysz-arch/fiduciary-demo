/* The selected plan, in one place.
 *
 * The plan is URL state on the routes that use it (R3-P1-2), so a link
 * carries it and Back returns to it. It is remembered per browser only as a
 * fallback for a route that opens without one. A route that does not depend
 * on the plan never writes it into its own links, which is what stopped the
 * old site from carrying a Screener filter into a Liquidity link. */
import { useCallback } from "react";
import { setParams, useRoute } from "./router";
import type { IndexView } from "../data/types";

const REMEMBER = "tark.plan";

/** The panels whose figures change with the plan. Every other route ignores
 *  it and does not put it in a link. */
export const PLAN_PANELS = new Set(["liquidity", "documents", "record", "benchmark", "packet", "plans"]);

export function planDependent(head: string, panel: string): boolean {
  return PLAN_PANELS.has(panel) || PLAN_PANELS.has(head);
}

function remembered(): string | null {
  try { return localStorage.getItem(REMEMBER); } catch { return null; }
}

/** The plan a route is showing: the URL’s, else the one this browser used
 *  last, else the first the index lists. A key the build does not have is
 *  ignored rather than trusted. */
export function usePlan(index: IndexView | null): [string, (k: string) => void] {
  const r = useRoute();
  const keys = (index?.plans || []).map((p) => p.key);
  const asked = r.params.get("plan") || "";
  const fallback = remembered() || "";
  const key = keys.includes(asked) ? asked : keys.includes(fallback) ? fallback : keys[0] || "";
  const set = useCallback((k: string) => {
    try { localStorage.setItem(REMEMBER, k); } catch { /* storage may be blocked */ }
    // a plan change is a navigation, not a filter: it gets a history entry
    setParams({ plan: k }, { replace: false, scroll: "keep" });
  }, []);
  return [key, set];
}

export function planLabel(index: IndexView | null, key: string): string {
  return (index?.plans || []).find((p) => p.key === key)?.label || "";
}

export function planOptions(index: IndexView | null) {
  return (index?.plans || []).map((p) => ({ value: p.key, label: p.label }));
}

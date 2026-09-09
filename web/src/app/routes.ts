/* The route table (R3-P1-2). Two kinds of route.
 *
 * Global routes show no product header and no product selector. Product
 * routes are panels under one fund and share a header. The table is the one
 * place either fact is written, so the shell, the navigation, the palette and
 * the gate all read the same list and cannot disagree about what exists.
 *
 * A view is a lazy chunk. Adding one here is what puts it on the route, in
 * the navigation and in the gate's walk. */
import { lazy } from "react";
import type { LazyExoticComponent } from "react";
import type { IconName } from "../components/primitives";

export interface RouteDef {
  /** the first path segment, or the panel name under /product/<key>/ */
  id: string;
  label: string;
  icon?: IconName;
  view?: LazyExoticComponent<() => JSX.Element>;
  /** the panels whose figures change with the selected plan */
  plan?: boolean;
  /** kept out of the sidebar, reachable by link */
  hidden?: boolean;
}

export const GLOBAL: RouteDef[] = [
  { id: "start", label: "Start", icon: "arrowRight", view: lazy(() => import("../views/StartView")) },
  { id: "universe", label: "Universe", icon: "search", view: lazy(() => import("../views/UniverseView")) },
  { id: "funnel", label: "From the universe to the record", icon: "chart", view: lazy(() => import("../views/FunnelView")) },
  { id: "screener", label: "Screener", icon: "table", view: lazy(() => import("../views/ScreenerView")) },
  { id: "compare", label: "Compare", icon: "compare", view: lazy(() => import("../views/CompareView")) },
  { id: "roster", label: "Roster", icon: "evaluate", view: lazy(() => import("../views/RosterView")) },
  { id: "plans", label: "Plans", icon: "plan", plan: true, view: lazy(() => import("../views/PlansView")) },
  { id: "search", label: "Evidence search", icon: "search", view: lazy(() => import("../views/SearchView")) },
  { id: "packet", label: "Packet", icon: "pin", plan: true, view: lazy(() => import("../views/PacketView")) },
  { id: "coverage", label: "Coverage", icon: "check" },
  { id: "verification", label: "Verification", icon: "document" },
  { id: "design", label: "Design system", icon: "info", view: lazy(() => import("../views/DesignView")) },
];

export const PANELS: RouteDef[] = [
  { id: "record", label: "Record", icon: "table", plan: true, view: lazy(() => import("../views/RecordView")) },
  { id: "benchmark", label: "Benchmark", icon: "chart", plan: true },
  { id: "liquidity", label: "Liquidity", icon: "plan", plan: true },
  { id: "cohort", label: "Cohort", icon: "compare" },
  { id: "lab", label: "Analysis lab", icon: "evaluate" },
  { id: "documents", label: "Documents", icon: "document", plan: true },
];

export const GLOBAL_BY_ID = new Map(GLOBAL.map((r) => [r.id, r]));
export const PANEL_BY_ID = new Map(PANELS.map((r) => [r.id, r]));

/** Every route the application answers, as the gate walks them. */
export function everyRoutePath(sampleProduct: string): string[] {
  return [
    ...GLOBAL.map((r) => `/${r.id}`),
    ...PANELS.map((r) => `/product/${sampleProduct}/${r.id}`),
  ];
}

export function isProductRoute(segments: string[]): boolean {
  return segments[0] === "product";
}

/** The four sidebar groups (R3-P1-4), by route id. */
export const NAV_GROUPS: { label: string; ids: string[] }[] = [
  { label: "Start and universe", ids: ["start", "universe", "funnel"] },
  { label: "Products", ids: ["screener", "compare", "roster", "plans"] },
  { label: "Workbench", ids: ["search", "packet"] },
  { label: "Integrity", ids: ["coverage", "verification", "design"] },
];

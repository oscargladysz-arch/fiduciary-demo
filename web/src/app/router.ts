/* A hash router that pushes a history entry on a route, product, plan or
 * cohort change and replaces it on filter, sort, column, window and slider
 * changes (R3-P1-3). Back and Forward re-render the route the URL names.
 * URL state is keys, ids and numbers only: every value is validated by the
 * view that reads it, and free text never enters the URL. */
import { useEffect, useState } from "react";

export interface Route {
  /** path segments after "#/", e.g. ["product", "hl_paf", "record"] */
  segments: string[];
  /** query parameters after "?" */
  params: URLSearchParams;
  /** the raw hash, for equality checks */
  hash: string;
}

const listeners = new Set<() => void>();
let current: Route;

export function parse(hash: string): Route {
  let h = hash.replace(/^#/, "");
  // legacy routes from the previous frontend: #view=...&plan=...&product=...
  if (h.startsWith("view=") || h.startsWith("?view=") || /^[a-z_]+=/.test(h)) {
    h = legacyToPath(new URLSearchParams(h.replace(/^\?/, "")));
  }
  if (!h.startsWith("/")) h = "/" + h;
  const q = h.indexOf("?");
  const path = q >= 0 ? h.slice(0, q) : h;
  const params = new URLSearchParams(q >= 0 ? h.slice(q + 1) : "");
  const segments = path.split("/").filter(Boolean);
  return { segments: segments.length ? segments : ["start"], params, hash: "#" + h };
}

/** The 18 legacy views of site/js/main.js, mapped to the new routes. */
const LEGACY_VIEWS: Record<string, string> = {
  census: "/universe", funnel: "/funnel", screener: "/screener", compare: "/compare",
  search: "/search", packet: "/packet", plans: "/plans", roster: "/roster",
  evaluation: "/product/{p}/record", benchmarks: "/product/{p}/benchmark",
  cohorts: "/product/{p}/cohort", fees: "/screener?preset=fees",
  liquidity: "/product/{p}/liquidity", pme: "/product/{p}/lab?tab=analysis",
  dxyz: "/product/dxyz/record?panel=price-vs-nav", desmooth: "/product/{p}/lab?tab=desmoothing",
  coverage: "/coverage", verification: "/verification",
};
const LEGACY_PASSTHROUGH = ["plan", "compare", "cohort", "proxy", "win", "rho", "density",
  "f_wrapper", "f_base", "f_tax", "f_gate", "f_big4", "f_verdict", "f_vonly", "pme_min", "pme_max",
  "sort", "dir", "cols", "f_cohort", "f_depth", "c_class", "c_listed", "c_interval", "c_tender",
  "c_eval", "c_amin", "c_amax", "c_hint", "c_cik"];

export function legacyToPath(q: URLSearchParams): string {
  const view = q.get("view") || "screener";
  const product = q.get("product") || "hl_paf";
  let path = LEGACY_VIEWS[view] || "/start";
  path = path.replace("{p}", encodeURIComponent(product));
  const out = new URLSearchParams(path.includes("?") ? path.slice(path.indexOf("?") + 1) : "");
  path = path.includes("?") ? path.slice(0, path.indexOf("?")) : path;
  for (const k of LEGACY_PASSTHROUGH) {
    const v = q.get(k);
    if (v) out.set(k, v);
  }
  // the plan only rides along on the routes that use it
  if (!/\/(record|benchmark|liquidity|documents)$|^\/packet|^\/plans/.test(path)) out.delete("plan");
  const qs = out.toString();
  return qs ? `${path}?${qs}` : path;
}

current = parse(location.hash);

function emit() {
  current = parse(location.hash);
  for (const l of listeners) l();
}

let lastHash = location.hash;
function onPop() {
  if (location.hash === lastHash) return;
  const canonical = parse(location.hash).hash;
  if (location.hash && canonical !== location.hash) history.replaceState(history.state, "", canonical);
  lastHash = location.hash;
  emit();
}
if (typeof window !== "undefined") {
  window.addEventListener("popstate", onPop);
  window.addEventListener("hashchange", onPop);
  // a legacy URL on first load is rewritten in place (replace, no new entry)
  const rewritten = parse(location.hash).hash;
  if (location.hash && rewritten !== location.hash) {
    history.replaceState(history.state, "", rewritten);
    lastHash = location.hash;
    current = parse(location.hash);
  }
}

export function buildHash(path: string, params?: URLSearchParams | Record<string, string | undefined>): string {
  const p = params instanceof URLSearchParams ? params : new URLSearchParams();
  if (params && !(params instanceof URLSearchParams)) {
    for (const [k, v] of Object.entries(params)) if (v) p.set(k, v);
  }
  const qs = p.toString();
  return "#" + (path.startsWith("/") ? path : "/" + path) + (qs ? "?" + qs : "");
}

export interface NavigateOptions { replace?: boolean; scroll?: "top" | "keep"; state?: unknown }

/** Navigate to a path with params. Pushes by default (a route change). */
export function navigate(path: string, params?: URLSearchParams | Record<string, string | undefined>, opts: NavigateOptions = {}) {
  const hash = buildHash(path, params);
  if (hash === location.hash) return;
  if (opts.replace) history.replaceState(opts.state ?? history.state, "", hash);
  else history.pushState(opts.state ?? null, "", hash);
  lastHash = hash;
  emit();
  if (opts.scroll !== "keep" && !opts.replace) window.scrollTo(0, 0);
}

/** Change parameters of the current route. Replaces by default (a filter,
 * sort, column, window or slider change), keeps scroll and focus. */
export function setParams(patch: Record<string, string | null | undefined>, opts: NavigateOptions = { replace: true, scroll: "keep" }) {
  const p = new URLSearchParams(current.params);
  for (const [k, v] of Object.entries(patch)) {
    if (v === null || v === undefined || v === "") p.delete(k); else p.set(k, v);
  }
  navigate("/" + current.segments.join("/"), p, { replace: true, scroll: "keep", ...opts });
}

export function useRoute(): Route {
  const [r, setR] = useState(current);
  useEffect(() => {
    const l = () => setR(current);
    listeners.add(l);
    return () => { listeners.delete(l); };
  }, []);
  return r;
}

export function currentRoute(): Route { return current; }

/** The product key of a product-scoped route, else null. */
export function routeProduct(r: Route): string | null {
  return r.segments[0] === "product" && r.segments[1] ? decodeURIComponent(r.segments[1]) : null;
}

/** The panel name of a product-scoped route ("record", "benchmark", ...). */
export function routePanel(r: Route): string {
  return r.segments[0] === "product" ? (r.segments[2] || "record") : r.segments[0];
}

/** Scroll positions per hash, restored on Back. */
const scrollMemory = new Map<string, number>();
export function rememberScroll() { scrollMemory.set(location.hash, window.scrollY); }
export function restoreScroll(hash: string): boolean {
  const y = scrollMemory.get(hash);
  if (y === undefined) return false;
  window.scrollTo(0, y);
  return true;
}

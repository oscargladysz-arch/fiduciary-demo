/* The application: the shell, the route switch, the palette. Views are lazy
 * chunks with modulepreload. Routes not yet rebuilt render an honest empty
 * state until their view lands. */
import { Suspense, lazy, useEffect, useState } from "react";
import { useRoute, navigate } from "./router";
import { AppShell } from "../components/shell";
import type { NavGroup } from "../components/shell";
import { Palette } from "../components/overlay";
import { EmptyState, Skeleton, ToastProvider } from "../components/primitives";
import type { PaletteItem } from "../components/overlay";

const DesignView = lazy(() => import("../views/DesignView"));

const GROUPS: NavGroup[] = [
  { label: "Start and universe", items: [
    { to: "/start", label: "Start", icon: "arrowRight" },
    { to: "/universe", label: "Universe", icon: "search" },
    { to: "/funnel", label: "Funnel", icon: "chart" },
  ] },
  { label: "Products", items: [
    { to: "/screener", label: "Screener", icon: "table" },
    { to: "/compare", label: "Compare", icon: "compare" },
    { to: "/roster", label: "Roster", icon: "evaluate" },
    { to: "/plans", label: "Plans", icon: "plan" },
  ] },
  { label: "Workbench", items: [
    { to: "/search", label: "Evidence search", icon: "search" },
    { to: "/packet", label: "Packet", icon: "pin" },
  ] },
  { label: "Integrity", items: [
    { to: "/coverage", label: "Coverage", icon: "check" },
    { to: "/verification", label: "Verification", icon: "document" },
    { to: "/design", label: "Design system", icon: "info" },
  ] },
];

function RouteSwitch() {
  const r = useRoute();
  const head = r.segments[0];
  useEffect(() => { document.title = `${head === "start" ? "Start" : head[0].toUpperCase() + head.slice(1)} · Tark`; }, [head]);
  if (head === "design") return <Suspense fallback={<Skeleton lines={6} label="Loading the design system" />}><DesignView /></Suspense>;
  return (
    <div className="stack-4">
      <h1>{head[0].toUpperCase() + head.slice(1)}</h1>
      <EmptyState title="This view is not rebuilt yet">The rebuilt frontend lands view by view after the design checkpoint. The current site carries this view.</EmptyState>
    </div>
  );
}

export default function App() {
  const [palette, setPalette] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette(true); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);
  const items: PaletteItem[] = GROUPS.flatMap((g) => g.items.map((it) => ({ id: it.to, label: it.label, kind: "View", run: () => navigate(it.to) })));
  return (
    <ToastProvider>
      <AppShell groups={GROUPS} footer={<p className="t-12 t-3">Every figure is real and cited, or labeled illustrative. Plan sponsors are anonymized on every surface. Human verification: pending.</p>}>
        <RouteSwitch />
      </AppShell>
      <Palette open={palette} onClose={() => setPalette(false)} items={items} />
    </ToastProvider>
  );
}

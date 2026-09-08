/* The application: the shell, the route switch, the palette.
 *
 * The route table (app/routes.ts) is the one list. The switch renders the
 * view a route names, the sidebar renders the same ids in four groups, and
 * the palette offers the same routes plus every product and plan. A route
 * whose view is not rebuilt yet says so rather than pretending. */
import { Suspense, useEffect, useMemo, useState } from "react";
import { navigate, routePanel, routeProduct, useRoute } from "./router";
import { GLOBAL, GLOBAL_BY_ID, NAV_GROUPS, PANELS, PANEL_BY_ID } from "./routes";
import { usePlan } from "./plan";
import { AppShell } from "../components/shell";
import type { NavGroup } from "../components/shell";
import { ProductHeader, useProduct } from "../components/product";
import { Palette } from "../components/overlay";
import { EmptyState, Skeleton, ToastProvider } from "../components/primitives";
import type { PaletteItem } from "../components/overlay";
import { SAY, routeTitle } from "../copy/copy";
import { useIndex } from "../data/hooks";
import type { IndexView } from "../data/types";

const GROUPS: NavGroup[] = NAV_GROUPS.map((g) => ({
  label: g.label,
  items: g.ids.map((id) => {
    const r = GLOBAL_BY_ID.get(id);
    return { to: `/${id}`, label: r?.label || id, icon: r?.icon };
  }),
}));

function NotRebuilt({ label }: { label: string }) {
  return (
    <div className="stack-4">
      <h1>{label}</h1>
      <EmptyState title="This view is not rebuilt yet">
        The rebuilt frontend lands view by view. The current site carries this view until it does.
      </EmptyState>
    </div>
  );
}

function RouteSwitch({ index }: { index: IndexView | null }) {
  const r = useRoute();
  const panel = routePanel(r);
  const productKey = routeProduct(r);
  const product = useProduct(index);
  const def = productKey ? PANEL_BY_ID.get(panel) : GLOBAL_BY_ID.get(r.segments[0]);
  const title = productKey ? (product?.fund_name || routeTitle("product")) : routeTitle(r.segments[0]);

  useEffect(() => {
    document.title = `${productKey ? `${title}, ${def?.label || ""}` : title} · Tark`;
  }, [title, productKey, def]);

  if (productKey && index && !product) {
    return <EmptyState title={SAY.noRecord}>This build does not carry a fund with that name.</EmptyState>;
  }
  const body = def?.view
    ? <Suspense fallback={<Skeleton lines={6} label={SAY.loadingRecord} />}><def.view /></Suspense>
    : <NotRebuilt label={def?.label || routeTitle(r.segments[0])} />;

  if (!productKey) return body;
  if (!index || !product) return <Skeleton lines={6} label={SAY.loadingRecord} />;
  return (
    <div className="stack-5">
      <ProductHeader index={index} product={product} panel={panel} />
      {body}
    </div>
  );
}

function usePaletteItems(index: IndexView | null): PaletteItem[] {
  const [plan] = usePlan(index);
  return useMemo(() => {
    const items: PaletteItem[] = GLOBAL.map((r) => ({
      id: `route:${r.id}`, label: r.label, kind: "View", run: () => navigate(`/${r.id}`),
    }));
    for (const p of index?.products || []) {
      items.push({
        id: `product:${p.key}`, label: p.fund_name, kind: "Fund", hint: p.wrapper_label,
        run: () => navigate(`/product/${p.key}/record`, { plan }),
      });
      for (const panel of PANELS) {
        items.push({
          id: `panel:${p.key}:${panel.id}`, label: `${p.fund_name}, ${panel.label}`, kind: "Panel",
          run: () => navigate(`/product/${p.key}/${panel.id}`, panel.plan ? { plan } : undefined),
        });
      }
    }
    for (const pl of index?.plans || []) {
      items.push({
        id: `plan:${pl.key}`, label: pl.label, kind: "Plan",
        run: () => navigate("/plans", { plan: pl.key }),
      });
    }
    return items;
  }, [index, plan]);
}

export default function App() {
  const [palette, setPalette] = useState(false);
  const { value: index } = useIndex();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette(true); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);
  const items = usePaletteItems(index);
  return (
    <ToastProvider>
      <AppShell groups={GROUPS} footer={
        <p className="t-12 t-3">
          Every figure is real and cited, or labeled illustrative. {SAY.anonymized}{" "}
          {SAY.verificationPending} To remove a workspace and everything in it, ask the administrator.
        </p>}>
        <RouteSwitch index={index} />
      </AppShell>
      <Palette open={palette} onClose={() => setPalette(false)} items={items} />
    </ToastProvider>
  );
}

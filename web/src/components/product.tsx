/* The product header (R3-P1-2): the one thing every panel under a fund
 * shares. The fund's name, its wrapper, what the record holds on it, the
 * panel tabs as links, and the plan selector only on the panels whose figures
 * change with the plan, with the sentence that says so.
 *
 * A global route never renders this, and never carries a product in its
 * links, which is what kept the old site's Screener filters out of a
 * Liquidity link. */
import { navigate, useRoute } from "../app/router";
import { PANELS } from "../app/routes";
import { planOptions, usePlan } from "../app/plan";
import { Chip, Icon, Link } from "./primitives";
import { ContextChip } from "./shell";
import { SAY } from "../copy/copy";
import { fmtInt } from "../format/format";
import type { IndexView, ProductSummary } from "../data/types";

export function ProductHeader({ index, product, panel }:
  { index: IndexView; product: ProductSummary; panel: string }) {
  const [plan, setPlan] = usePlan(index);
  const here = PANELS.find((p) => p.id === panel);
  const cov = product.coverage;
  return (
    <header className="producthead">
      <div className="producthead__name">
        <h1 className="t-24 t-balance" translate="no">{product.fund_name}</h1>
        <Chip kind="wrapper">{product.wrapper_label}</Chip>
        <Chip kind="tier">{fmtInt(cov.evidenced)} cited</Chip>
        <Chip kind="computed">{fmtInt(cov.computed)} computed</Chip>
        <Chip kind="pending">{fmtInt(cov.verified)} signed</Chip>
      </div>
      <nav className="producthead__nav" aria-label="This fund">
        {PANELS.map((p) => (
          <Link key={p.id} to={`/product/${product.key}/${p.id}`} params={p.plan ? { plan } : undefined}
            quiet className="tab" aria-current={p.id === panel ? "page" : undefined}>
            {p.icon && <Icon name={p.icon} size="sm" />}{p.label}
          </Link>
        ))}
      </nav>
      {here?.plan && (
        <div className="row">
          <ContextChip id="product-plan" label="Plan" value={plan} options={planOptions(index)}
            onChange={setPlan} note={SAY.planDependent} />
        </div>
      )}
    </header>
  );
}

/** The product a product-scoped route names, or null when the URL names one
 *  this build does not have. A view shows an empty state rather than acting
 *  on a key it cannot resolve. */
export function useProduct(index: IndexView | null): ProductSummary | null {
  const r = useRoute();
  if (!index || r.segments[0] !== "product") return null;
  const key = decodeURIComponent(r.segments[1] || "");
  return index.products.find((p) => p.key === key) || null;
}

export function gotoProduct(key: string, panel: string, plan?: string) {
  navigate(`/product/${key}/${panel}`, plan ? { plan } : undefined);
}

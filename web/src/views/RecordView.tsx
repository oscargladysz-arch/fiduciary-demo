/* The record: one fund on fifty-five rows, grouped by the six factors.
 *
 * Content rules (R3-P1-10). The headline is the typed fact when the record
 * has one, otherwise the finding in one line with no status word in front of
 * it and no trailing ellipsis. The full text and its provenance open under a
 * disclosure rather than filling the page. The source control is a labeled
 * button naming the row it opens, not one of fifty identical glyphs. An
 * adviser-completed row carries one chip, not two.
 *
 * The premium exhibit for a fund whose shares trade at a price of their own
 * lives here, under the factors it belongs to, rather than as an item in the
 * navigation named after one fund. */
import { useMemo } from "react";
import { setParams, useRoute } from "../app/router";
import { usePins, isPinned } from "../app/pins";
import { CiteButton } from "../components/citation";
import { Disclosure } from "../components/overlay";
import { Button, Card, CardHead, Chip, EmptyState, Legend, Link, Skeleton, Stat, StatRow, useToast }
  from "../components/primitives";
import { Donut } from "../charts/charts";
import { PremiumPanel, premiumOf } from "../components/premium";
import { SAY, TIERS, status as statusCopy } from "../copy/copy";
import { useAsync, useIndex } from "../data/hooks";
import { data } from "../data/index";
import { fmtInt, fmtOf } from "../format/format";
import type { Cell, RecordView as RecordShape, SeriesView } from "../data/types";

const FACTOR_ORDER = ["1", "2", "3", "4", "5", "6"];

function CellRow({ record, cid, cell, plan }:
  { record: RecordShape; cid: string; cell: Cell; plan: string }) {
  const st = statusCopy(cell.status);
  const { pins, add, remove, restore } = usePins();
  const toast = useToast();
  const pinned = isPinned(pins, record.product_key, cid);
  const element = cell.element || cid;
  const headline = cell.display?.headline || cell.value;
  const body = cell.value || "";
  // the headline leads and the body carries the rest: a body that is only the
  // headline again is not shown twice
  const bodyAddsSomething = body.trim() && body.trim() !== headline.trim();

  const onPin = () => {
    if (pinned) {
      const at = pins.findIndex((p) => p.productKey === record.product_key && p.cell === cid);
      const gone = remove(record.product_key, cid);
      if (gone) toast(`Removed ${cid} from the packet.`, { label: "Undo", onClick: () => restore(gone, at) });
      return;
    }
    const result = add({ productKey: record.product_key, fundName: record.fund_name, cell: cid, element });
    toast(result === "added" ? `Added ${cid}, ${element}, to the packet.` : `${cid} is already in the packet.`);
  };

  return (
    <Card className="stack-2" as="article" id={`cell-${cid}`}>
      <div className="card__head">
        <h3 className="card__title">
          <span className="t-eyebrow" translate="no">{cid}</span> {element}
        </h3>
        <div className="row-3">
          <Chip kind={st.kind}>{st.label}</Chip>
          {cell.display?.typed && <Chip kind="tier">Typed</Chip>}
        </div>
      </div>
      <p className="t-14">{headline}</p>
      <div className="row-3">
        {cell.source && (
          <CiteButton target={{ productKey: record.product_key, fundName: record.fund_name, cell: cid }}
            label={`Open ${cell.source.split(",")[0]}`} />
        )}
        <Button variant="quiet" icon="pin" onClick={onPin}
          aria-pressed={pinned}
          aria-label={pinned ? `Remove ${cid}, ${element}, from the packet` : `Add ${cid}, ${element}, to the packet`}>
          {pinned ? "In the packet" : "Add to the packet"}
        </Button>
      </div>
      {bodyAddsSomething && (
        <Disclosure summary="Full text and provenance" id={`disc-${cid}`}>
          <div className="stack-2">
            <p className="t-14 t-2">{body}</p>
            <dl className="field-list">
              {cell.source && (<><dt>Document</dt><dd>{cell.source}</dd></>)}
              {cell.section && (<><dt>Section</dt><dd>{cell.section}</dd></>)}
              {cell.rule?.paragraph && (<><dt>Paragraph of the rule</dt><dd>{cell.rule.paragraph}</dd></>)}
              <dt>Signed by</dt>
              <dd>{cell.verified_by || "Nobody yet. Human verification is pending."}</dd>
            </dl>
          </div>
        </Disclosure>
      )}
      {plan && cid === "3.7" && <p className="t-13 t-3">{SAY.planDependent}</p>}
    </Card>
  );
}

export default function RecordView() {
  const r = useRoute();
  const key = decodeURIComponent(r.segments[1] || "");
  const plan = r.params.get("plan") || "";
  const { value: index } = useIndex();
  const { value: record, error, loading } = useAsync<RecordShape>(() => data().getRecord(key), [key]);
  // the premium exhibit rides on the fund's own series chunk, and only a fund
  // whose shares trade at a price of their own has one
  const { value: series } = useAsync<SeriesView>(() => data().getSeries(key), [key]);
  const open = r.params.get("factor") || "1";
  // the premium exhibit used to be a route of its own. A link that names it
  // opens the factor it now lives under and scrolls to it, rather than
  // landing on a page that is gone.
  const wantsPremium = r.params.get("panel") === "price-vs-nav";

  const byFactor = useMemo(() => {
    const out: Record<string, [string, Cell][]> = {};
    for (const [cid, cell] of Object.entries(record?.cells || {})) {
      const n = cid.split(".")[0];
      (out[n] = out[n] || []).push([cid, cell]);
    }
    for (const n of Object.keys(out)) {
      out[n].sort((a, b) => Number(a[0].split(".")[1]) - Number(b[0].split(".")[1]));
    }
    return out;
  }, [record]);

  if (error) return <EmptyState title={SAY.noRecord}>{error}</EmptyState>;
  if (loading || !record || !index) return <Skeleton lines={10} label={SAY.loadingRecord} />;

  const cov = record.coverage;
  const factors = record.factors || {};

  return (
    <div className="stack-5">
      <StatRow>
        <Stat label="Rows resolved" value={fmtOf(cov.resolved, cov.resolvable)}
          source="Structured, extracted, computed or answered not applicable" />
        <Stat label="With a filing behind them" value={fmtInt(cov.evidenced)}
          source="A document, a section and a quote" />
        <Stat label="Calculated here" value={fmtInt(cov.computed)} source="From figures on this record" />
        <Stat label="Signed by a person" value={fmtInt(cov.verified)} source={SAY.verificationPending} />
      </StatRow>

      <section className="stack-4" aria-labelledby="factors">
        <h2 id="factors" className="t-20">The six factors</h2>
        <div className="grid-3">
          {FACTOR_ORDER.filter((n) => factors[n]).map((n) => {
            const f = factors[n];
            const cited = f.evidenced, computed = f.computed, soft = f.soft, na = f.na;
            return (
              <Card key={n} as="article" className="stack-2">
                <CardHead title={<>{f.label}</>} level={3} />
                <Donut
                  title={`${f.label}: ${cited} of ${f.total} rows with a filing behind them`}
                  center={fmtOf(cited, f.total)} centerSub="cited"
                  segments={[
                    { label: "Cited", value: cited, color: "var(--status-extracted-fg)" },
                    { label: "Calculated", value: computed, color: "var(--status-computed-fg)" },
                    { label: "Partly on record", value: soft, color: "var(--status-partial-fg)" },
                    { label: "Not applicable", value: na, color: "var(--status-na-fg)" },
                  ]}
                />
                <Button variant="quiet" iconRight="chevronDown"
                  aria-expanded={open === n}
                  onClick={() => setParams({ factor: n })}>
                  {open === n ? `Showing ${f.label}` : `Show ${f.label}`}
                </Button>
              </Card>
            );
          })}
        </div>
      </section>

      <section className="stack-4" aria-labelledby="rows">
        <h2 id="rows" className="t-20">
          {factors[open]?.label || "Rows"}{" "}
          <span className="t-14 t-3">{fmtInt((byFactor[open] || []).length)} rows</span>
        </h2>
        {(open === "1" || open === "4") && series && premiumOf(series) && (
          <div id="price-vs-nav" ref={(el) => { if (el && wantsPremium) el.scrollIntoView({ block: "start" }); }}>
            <PremiumPanel series={series} fundName={record.fund_name} />
          </div>
        )}
        {(byFactor[open] || []).map(([cid, cell]) => (
          <CellRow key={cid} record={record} cid={cid} cell={cell} plan={plan} />
        ))}
        {(byFactor[open] || []).length === 0 && (
          <EmptyState title="No rows under this factor">This build carries no rows for that factor.</EmptyState>
        )}
      </section>

      <Card sunken>
        <CardHead title="How to read this record" level={2} />
        <Legend label="Tiers" items={TIERS.map((t, i) => ({
          label: t.label, kind: (["structured", "extracted", "verified"] as const)[i],
        }))} />
        <p className="t-13 t-3">
          {SAY.verificationCount(cov.verified, cov.total)}{" "}
          <Link to="/verification">See the verification queue</Link>
        </p>
      </Card>
    </div>
  );
}

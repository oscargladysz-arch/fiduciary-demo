/* The candidate roster: every evaluated fund as one card.
 *
 * The coverage ring is drawn at the size the chart module draws it, and the
 * same counts stand beside it in words: the old view drew sixteen rings at
 * zero by zero, so the only carrier of the number was invisible.
 *
 * Sixteen cards carrying the same three link texts would be sixteen ambiguous
 * links, so every link on a card names the fund it opens. The three panels the
 * cards link to depend on the plan, so the links carry it.
 *
 * The cohort and wrapper filters serialize into the address and replace the
 * history entry rather than pushing one, so Back leaves the roster rather than
 * walking its filters.
 */
import { useMemo } from "react";
import { setParams, useRoute } from "../app/router";
import { planLabel, usePlan } from "../app/plan";
import { Donut } from "../charts/charts";
import { Field, Select } from "../components/form";
import { Card, CardHead, Chip, EmptyState, Legend, Link, Skeleton, Stat, StatRow }
  from "../components/primitives";
import { PageHeader } from "../components/shell";
import { SAY, TIERS, routeTitle } from "../copy/copy";
import { useIndex } from "../data/hooks";
import { fmtInt, fmtOf } from "../format/format";
import type { ProductSummary } from "../data/types";

const EVERY = "";  // the empty option of a filter, meaning every value

/* the four kinds a row of a record can be in, in the words a reader meets and in
 * the token colors the record view uses for the same four */
const KINDS = [
  { key: "evidenced", label: "Cited", color: "var(--status-extracted-fg)" },
  { key: "computed", label: "Calculated", color: "var(--status-computed-fg)" },
  { key: "soft", label: "Partly on record", color: "var(--status-partial-fg)" },
  { key: "na", label: "Not applicable", color: "var(--status-na-fg)" },
] as const;

function rowsOf(p: ProductSummary): number {
  return p.coverage.evidenced + p.coverage.computed + p.coverage.soft + p.coverage.na;
}

function byName(a: ProductSummary, b: ProductSummary): number {
  return a.fund_name < b.fund_name ? -1 : a.fund_name > b.fund_name ? 1 : 0;
}

export default function RosterView() {
  const r = useRoute();
  const { value: index, error, loading } = useIndex();
  const [plan] = usePlan(index);

  // a filter the address claims is honored only if this build carries it
  const askedCohort = r.params.get("f_cohort") || EVERY;
  const askedWrapper = r.params.get("f_wrapper") || EVERY;
  const cohort = index && index.cohorts[askedCohort] ? askedCohort : EVERY;
  const wrapper = index && index.products.some((p) => p.wrapper_type === askedWrapper)
    ? askedWrapper : EVERY;

  const shown = useMemo(() => {
    const all = [...(index?.products || [])].sort(byName);
    return all.filter((p) => (!cohort || p.cohort === cohort) && (!wrapper || p.wrapper_type === wrapper));
  }, [index, cohort, wrapper]);

  if (error) return <EmptyState title={SAY.noRecord}>{error}</EmptyState>;
  if (loading || !index) return <Skeleton lines={8} label={SAY.loadingRecord} />;

  const counts = index.coverage_totals.counts || {};
  const signed = counts.verified || 0;
  const cells = Number(index.coverage_totals.total || 0);
  const filtered = !!cohort || !!wrapper;
  const label = planLabel(index, plan);

  const cohortOptions = [{ value: EVERY, label: "Every cohort" }, ...Object.entries(index.cohorts)
    .map(([id, c]) => ({ value: id, label: c.label }))
    .sort((a, b) => (a.label < b.label ? -1 : 1))];

  const wrappers = new Map<string, string>();
  for (const p of index.products) {
    if (!wrappers.has(p.wrapper_type)) {
      wrappers.set(p.wrapper_type, p.wrapper_label || index.labels.wrapper[p.wrapper_type] || p.wrapper_type);
    }
  }
  const wrapperOptions = [{ value: EVERY, label: "Every wrapper" }, ...Array.from(wrappers)
    .map(([value, text]) => ({ value, label: text }))
    .sort((a, b) => (a.label < b.label ? -1 : 1))];

  return (
    <div className="stack-5">
      <PageHeader
        title={routeTitle("roster")}
        sub={"Every fund evaluated on the six-factor record, with the wrapper it uses, the strategy in words, "
          + "the cohort it is compared against, and how much of its record has a filing behind it."}
        actions={<Link to="/screener">See the same funds as a table</Link>}
      />

      <StatRow>
        <Stat label="Funds evaluated" value={fmtInt(index.products.length)}
          source="Each on the same six-factor record" />
        <Stat label="Cohorts" value={fmtInt(Object.keys(index.cohorts).length)}
          source="Each with its members named" />
        <Stat label="Cells signed by a person" value={fmtInt(signed)} source={SAY.verificationPending} />
      </StatRow>

      <Card>
        <div className="filterbar" role="group" aria-label="Filters">
          <Field label="Cohort" inline>
            {(ids) => <Select ids={ids} small options={cohortOptions} value={cohort}
              onChange={(e) => setParams({ f_cohort: e.target.value })} />}
          </Field>
          <Field label="Wrapper" inline>
            {(ids) => <Select ids={ids} small options={wrapperOptions} value={wrapper}
              onChange={(e) => setParams({ f_wrapper: e.target.value })} />}
          </Field>
        </div>
        <p className="t-13 t-3" aria-live="polite">
          Showing {fmtInt(shown.length)} of {fmtInt(index.products.length)} evaluated funds.
          {filtered && (<>{" "}<Link to="/roster" replace>Clear the filters</Link></>)}
        </p>
        {label && (
          <p className="t-13 t-3">
            The record, the benchmark and the liquidity panel depend on the plan, so every card here opens
            them for {label}.{" "}
            <Link to="/plans" params={{ plan }}>Change the plan</Link>
          </p>
        )}
      </Card>

      <section className="stack-4" aria-labelledby="roster-funds">
        <h2 id="roster-funds" className="t-20">The evaluated funds</h2>

        {shown.length === 0 && (
          <EmptyState title="No fund matches what you have selected"
            action={<Link to="/roster" replace>Clear the filters</Link>}>
            {index.products.length > 0
              ? "Widen the cohort or the wrapper to see the rest of the roster."
              : "A fund appears here once its record holds the rows the six factors ask for."}
          </EmptyState>
        )}

        <div className="grid-2">
          {shown.map((p) => {
            const cov = p.coverage;
            const rows = rowsOf(p);
            const strategy = index.labels.strategy[p.strategy] || "";
            const cohortLabel = index.cohorts[p.cohort]?.label || "";
            const wrapperLabel = p.wrapper_label || index.labels.wrapper[p.wrapper_type] || "";
            const values: Record<string, number> = {
              evidenced: cov.evidenced, computed: cov.computed, soft: cov.soft, na: cov.na,
            };
            return (
              <Card key={p.key} as="article" className="stack-2">
                <CardHead title={<span translate="no">{p.fund_name}</span>} level={3}>
                  {wrapperLabel && <Chip kind="wrapper">{wrapperLabel}</Chip>}
                </CardHead>

                <dl className="field-list">
                  <dt>Strategy</dt>
                  <dd>{strategy || "Not named on the record"}</dd>
                  <dt>Cohort</dt>
                  <dd>{cohortLabel || "Not placed in a cohort"}</dd>
                </dl>

                <Donut
                  title={`${p.fund_name}, the rows of its record by what stands behind them`}
                  center={fmtInt(cov.evidenced)} centerSub="cited"
                  segments={KINDS.map((k) => ({ label: k.label, value: values[k.key], color: k.color }))}
                />

                <p className="t-13 t-2">
                  {fmtOf(cov.evidenced, rows)} rows carry a document, a section and a quote you can open.
                </p>
                <p className="t-12 t-3">
                  {fmtInt(cov.computed)} calculated, {fmtInt(cov.soft)} partly on record,{" "}
                  {fmtInt(cov.na)} not applicable, {fmtInt(cov.verified)} signed by a person.
                </p>

                <div className="row-3">
                  <Link to={`/product/${p.key}/record`} params={{ plan }}
                    aria-label={`Open the record for ${p.fund_name}`}>Open the record</Link>
                  <Link to={`/product/${p.key}/benchmark`} params={{ plan }}
                    aria-label={`Open the benchmark for ${p.fund_name}`}>Open the benchmark</Link>
                  <Link to={`/product/${p.key}/liquidity`} params={{ plan }}
                    aria-label={`Open the liquidity panel for ${p.fund_name}`}>Open the liquidity panel</Link>
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      <Card sunken>
        <CardHead title="How to read a ring" level={2} />
        <p className="t-14 t-2">
          Each ring counts the rows of one record. A cited row carries the document, the section and the
          sentence it was read from. A calculated row is worked out from figures on the same record. Partly
          on record means part of the answer is disclosed and the rest is not. A not applicable row carries
          the reason the question does not apply to that wrapper.
        </p>
        <Legend label="Tiers" items={TIERS.map((t, i) => ({
          label: t.label, kind: (["structured", "extracted", "verified"] as const)[i],
        }))} />
        <p className="t-13 t-3">
          {SAY.verificationCount(signed, cells)}{" "}
          <Link to="/verification">See the verification queue</Link>
        </p>
      </Card>
    </div>
  );
}

/* Coverage and provenance: what the record holds, and how it is counted.
 *
 * The old page printed the resolvable count as though every cell in it were
 * resolved, because partial and from-a-held-series cells were counted as
 * resolved. This page states the arithmetic instead: the resolved figure, the
 * base it is taken from, and every kind that is not in it, in words and in
 * numbers, with each definition visible on the page rather than on hover.
 *
 * Tier language never blurs here. Structured is the tagged number, extracted
 * is a quote a reader can open, and a signature is the only thing called
 * signed. Nothing on this record is signed by a person, the count says so,
 * and the cross-check is an agent pass, never verification.
 */
import { Fragment, useMemo } from "react";
import { setParams, useRoute } from "../app/router";
import { Donut } from "../charts/charts";
import { Card, CardHead, Chip, EmptyState, Legend, Link, Skeleton, Stat, StatRow, Term }
  from "../components/primitives";
import { PageHeader } from "../components/shell";
import { Table } from "../components/table";
import type { Column, SortState } from "../components/table";
import { SAY, TIERS, status as statusCopy } from "../copy/copy";
import { useAsync } from "../data/hooks";
import { data } from "../data/index";
import { fmtDate, fmtInt, fmtOf, fmtPct, typographic } from "../format/format";
import type { Coverage, CoverageView as CoverageShape } from "../data/types";

/* The chunk carries more on its totals and on its cross-check than the shared
 * shapes declare, so the two the page reads are named here. Every field is
 * optional: what the record does not hold is not printed. */
interface Totals {
  counts?: Record<string, number>;
  products?: number;
  resolvable?: number;
  resolved?: number;
  total?: number;
}
interface Crosscheck {
  cells_checked?: number;
  confirmed?: number;
  corrected?: number;
  unlocatable?: number;
  products?: number;
  human_verified?: number;
  date?: string;
  source?: string;
}
interface FundRow { key: string; name: string; cov: Coverage }

/* One color per kind, from the status tokens, so a ring and a chip of the
 * same kind cannot disagree. */
const RING: Record<string, string> = {
  structured: "var(--status-structured-fg)",
  extracted: "var(--status-extracted-fg)",
  verified: "var(--status-verified-bg)",
  computed: "var(--status-computed-fg)",
  partial: "var(--status-partial-fg)",
  na: "var(--status-na-fg)",
  pending: "var(--pending-fg)",
};

const COUNTED = {
  resolved: "Counts as resolved",
  soft: "Counted separately as partly on record",
  outside: "Outside the resolvable base",
  open: "Not resolved",
} as const;

const TIER_LABEL: Record<string, string> = { T1: TIERS[0].label, T2: TIERS[1].label, T3: TIERS[2].label };

/** Cells with a filing behind them: the tagged numbers and the quoted ones. */
function evidencedOf(c: Coverage): number {
  return c.evidenced ?? c.structured + c.extracted;
}
/** Cells only partly on record: part of the answer, or a held series. */
function softOf(c: Coverage): number {
  return c.soft ?? c.partial + c.fetched;
}
function shareOf(c: Coverage): number {
  return c.resolvable > 0 ? (c.resolved / c.resolvable) * 100 : 0;
}

/** The four rings of one fund, in the order the record counts them. */
function fundSegments(c: Coverage) {
  return [
    { label: "With a filing behind them", value: evidencedOf(c), color: RING.extracted },
    { label: "Calculated", value: c.computed, color: RING.computed },
    { label: "Partly on record", value: softOf(c), color: RING.partial },
    { label: "Not applicable", value: c.na, color: RING.na },
  ];
}

interface KindRow { id: string; statusKey: string; count: number; counted: string }

export default function CoverageView() {
  const r = useRoute();
  /* A workspace keeps its own record and may carry no whole-record count, so
   * the page asks the source whether it has one before it renders. */
  const { value: cov, error, loading } = useAsync<CoverageShape | null>(
    () => data().getCoverage?.() ?? Promise.resolve(null), []);

  const rows = useMemo<FundRow[]>(() => Object.entries(cov?.products || {})
    .map(([key, p]) => ({ key, name: p.fund_name, cov: p.coverage })), [cov]);

  const columns = useMemo<Column<FundRow>[]>(() => fundColumns(), []);

  const sort: SortState | null = r.params.get("sort")
    ? { id: r.params.get("sort")!, dir: r.params.get("dir") === "desc" ? "desc" : "asc" }
    : null;
  const visible = r.params.get("cols") ? r.params.get("cols")!.split(".") : null;

  if (error) return <EmptyState title={SAY.noRecord}>{error}</EmptyState>;
  if (loading) return <Skeleton lines={10} label={SAY.loadingRecord} />;
  if (!cov) {
    return (
      <EmptyState title={SAY.noRecord}>
        This source answers one record at a time and carries no count across the whole record.
      </EmptyState>
    );
  }

  const totals = (cov.totals || {}) as Totals;
  const counts = totals.counts || {};
  const n = (key: string) => Number(counts[key] || 0);

  const structured = n("structured");
  const extracted = n("extracted");
  const verified = n("verified");
  const computed = n("computed");
  const partial = n("partial");
  const fetched = n("fetched");
  const na = n("na");
  const pending = n("pending");

  const evidenced = counts.evidenced ?? structured + extracted;
  const soft = counts.soft ?? partial + fetched;
  const resolved = totals.resolved ?? counts.resolved ?? structured + extracted + verified + computed;
  const resolvable = totals.resolvable ?? counts.resolvable ?? resolved + soft;
  const total = totals.total ?? counts.total ?? resolvable + na;
  const funds = totals.products ?? rows.length;

  const kinds: KindRow[] = [
    { id: "structured", statusKey: "structured", count: structured, counted: COUNTED.resolved },
    { id: "extracted", statusKey: "extracted-unverified", count: extracted, counted: COUNTED.resolved },
    { id: "verified", statusKey: "verified", count: verified, counted: COUNTED.resolved },
    { id: "computed", statusKey: "computed", count: computed, counted: COUNTED.resolved },
    { id: "partial", statusKey: "partial", count: partial, counted: COUNTED.soft },
    { id: "fetched", statusKey: "fetched", count: fetched, counted: COUNTED.soft },
    { id: "na", statusKey: "n/a", count: na, counted: COUNTED.outside },
    { id: "pending", statusKey: "pending", count: pending, counted: COUNTED.open },
  ];

  const wholeSegments = [
    { label: statusCopy("structured").label, value: structured, color: RING.structured },
    { label: statusCopy("extracted-unverified").label, value: extracted, color: RING.extracted },
    { label: statusCopy("verified").label, value: verified, color: RING.verified },
    { label: statusCopy("computed").label, value: computed, color: RING.computed },
    { label: "Partly on record", value: soft, color: RING.partial },
    { label: statusCopy("n/a").label, value: na, color: RING.na },
    { label: statusCopy("pending").label, value: pending, color: RING.pending },
  ];

  const cc = (cov.crosscheck || {}) as Crosscheck;
  const ccPairs: { term: string; value: string }[] = [
    { term: "Cells re-located", value: cc.cells_checked === undefined ? "" : fmtInt(cc.cells_checked) },
    { term: "Confirmed", value: cc.confirmed === undefined ? "" : fmtInt(cc.confirmed) },
    { term: "Corrected", value: cc.corrected === undefined ? "" : fmtInt(cc.corrected) },
    { term: "Could not be found again", value: cc.unlocatable === undefined ? "" : fmtInt(cc.unlocatable) },
    { term: "Funds covered", value: cc.products === undefined ? "" : fmtInt(cc.products) },
    { term: "Date of the pass", value: fmtDate(cc.date) },
    { term: "Where the pass is written down", value: cc.source || "" },
    { term: "Signed by a person", value: cc.human_verified === undefined ? "" : fmtInt(cc.human_verified) },
  ].filter((p) => p.value !== "");

  return (
    <div className="stack-5">
      <PageHeader
        title="Coverage and provenance"
        sub={`What the record holds, and how each cell is counted. The resolved figure is printed with the base it is taken from, so a cell that is only partly on record never counts as a whole one.`}
        actions={<Link to="/verification">Go to verification</Link>}
      />

      <StatRow>
        <Stat label="Cells on the record" value={fmtInt(total)} source={`Across ${fmtInt(funds)} funds`} />
        <Stat label="Resolved" value={fmtOf(resolved, resolvable)} source="Of the cells that could be answered" />
        <Stat label="With a filing behind them" value={fmtInt(evidenced)}
          source="A tagged number, or a document, a section and a quote" />
        <Stat label="Signed by a person" value={fmtInt(verified)} source={SAY.verificationPending} />
      </StatRow>

      <section className="stack-4" aria-labelledby="arithmetic">
        <h2 id="arithmetic" className="t-20">How the record is counted</h2>

        <div className="two-col">
          <Card className="stack-2">
            <CardHead title="Every cell on the record" level={3} />
            <Donut
              title="The whole record by kind"
              size={200}
              center={fmtInt(total)}
              centerSub="cells"
              segments={wholeSegments}
            />
          </Card>

          <Card className="stack-2">
            <CardHead title="The arithmetic" level={3} />
            <p className="t-16 t-num">{fmtOf(resolved, resolvable)} resolvable cells resolved.</p>
            <dl className="field-list">
              <dt>Resolved</dt>
              <dd className="t-num">
                {`${fmtInt(structured)} structured + ${fmtInt(extracted)} extracted + ${fmtInt(verified)} signed by a person + ${fmtInt(computed)} calculated = ${fmtInt(resolved)} resolved`}
              </dd>
              <dt>Resolvable</dt>
              <dd className="t-num">
                {`${fmtInt(resolved)} resolved + ${fmtInt(partial)} partial + ${fmtInt(fetched)} from a held series = ${fmtInt(resolvable)} resolvable`}
              </dd>
              <dt>On the record</dt>
              <dd className="t-num">
                {`${fmtInt(resolvable)} resolvable + ${fmtInt(na)} not applicable = ${fmtInt(total)} cells`}
              </dd>
            </dl>
            <p className="t-13 t-2">
              {`Structured, extracted, signed and calculated cells count as resolved. Partial and from-a-held-series cells are counted apart from them, ${fmtInt(soft)} in all, because only part of the answer is on record. A not applicable cell is answered with the reason on the row and sits outside the resolvable base, so it never lifts the resolved figure. Pending is not resolved, and ${fmtInt(pending)} cells are pending.`}
            </p>
          </Card>
        </div>

        <Table
          id="coverage-kinds"
          caption="Every kind of cell on the record, what it means, and how the count treats it."
          columns={kindColumns()}
          rows={kinds}
          rowKey={(k) => k.id}
          empty="No kind of cell is on the record yet."
        />
      </section>

      <section className="stack-4" aria-labelledby="byfund">
        <h2 id="byfund" className="t-20">Coverage by fund</h2>
        <p className="t-13 t-3" aria-live="polite">
          {`Showing ${fmtInt(rows.length)} funds. `}
          {SAY.verificationPending}
        </p>
        {rows.length === 0 ? (
          <EmptyState title="No fund is counted yet">
            A fund appears here once its record has been read and its cells counted.
          </EmptyState>
        ) : (
          <Table
            id="coverage-funds"
            caption={`Each fund, its cells by kind, and its resolved count against its resolvable base. ${SAY.verificationPending}`}
            columns={columns}
            rows={rows}
            rowKey={(row) => row.key}
            sort={sort}
            onSort={(s) => setParams({ sort: s?.id || null, dir: s?.dir || null })}
            visible={visible}
            onVisible={(ids) => setParams({ cols: ids ? ids.join(".") : null })}
            empty="No fund is counted yet."
          />
        )}
      </section>

      <section className="stack-4" aria-labelledby="rings">
        <h2 id="rings" className="t-20">Each fund at a glance</h2>
        {rows.length === 0 ? (
          <EmptyState title="No fund is counted yet">
            A ring appears here for each fund the record carries.
          </EmptyState>
        ) : (
          <div className="grid-2">
            {rows.map((row) => (
              <Card key={row.key} as="article" className="stack-2">
                <CardHead
                  title={<Link to={`/product/${row.key}/record`} translate="no">{row.name}</Link>}
                  level={3}
                />
                <Donut
                  title={`${row.name}, cells by kind`}
                  size={120}
                  center={fmtPct(shareOf(row.cov), 0)}
                  centerSub="resolved"
                  segments={fundSegments(row.cov)}
                />
                <p className="t-13 t-3 t-num">
                  {`${fmtOf(row.cov.resolved, row.cov.resolvable)} resolvable cells resolved. ${fmtInt(softOf(row.cov))} partly on record. ${fmtInt(row.cov.verified)} signed by a person.`}
                </p>
              </Card>
            ))}
          </div>
        )}
      </section>

      <section className="stack-4" aria-labelledby="crosscheck">
        <h2 id="crosscheck" className="t-20">The cross-check</h2>
        {ccPairs.length === 0 ? (
          <EmptyState title="No cross-check is on the record">
            A pass appears here once one has run over the cells and been written down.
          </EmptyState>
        ) : (
          <Card className="stack-2">
            <CardHead title="An agent pass over the cited cells" level={3}>
              <Chip kind="pending">Not verification</Chip>
            </CardHead>
            <p className="t-14 t-2">
              {cc.products !== undefined && cc.cells_checked !== undefined
                ? `One checking agent for each of the ${fmtInt(cc.products)} funds went back to the filings and found the cited cells again, ${fmtInt(cc.cells_checked)} of them in all. An agent pass is a second read, not a signature, so the record never counts it as verification.`
                : `An agent pass went back to the filings and found the cited cells again. An agent pass is a second read, not a signature, so the record never counts it as verification.`}
            </p>
            <dl className="field-list">
              {ccPairs.map((p) => (
                <Fragment key={p.term}>
                  <dt>{p.term}</dt>
                  <dd className="t-num">{p.value}</dd>
                </Fragment>
              ))}
            </dl>
          </Card>
        )}
      </section>

      <section className="stack-4" aria-labelledby="signed">
        <h2 id="signed" className="t-20">Human verification</h2>
        <Card sunken className="stack-2">
          <Legend label="Tiers" items={TIERS.map((t, i) => ({
            label: t.label, kind: (["structured", "extracted", "verified"] as const)[i],
          }))} />
          <p className="t-13 t-3">
            {SAY.verificationCount(verified, total)} {SAY.verificationPending}{" "}
            <Link to="/verification">See what a signature would cover</Link>
          </p>
        </Card>
      </section>
    </div>
  );
}

/* ------------------------------------------------------------ the kinds */
/* Each kind carries its definition twice: on the label, reachable by keyboard
 * and by tap, and as text on the page, so it is never hover-only. */
function kindColumns(): Column<KindRow>[] {
  return [
    {
      id: "kind", header: "Kind", label: "Kind", fixed: true,
      cell: (k) => {
        const st = statusCopy(k.statusKey);
        return <Term def={typographic(st.definition)}>{st.label}</Term>;
      },
    },
    {
      id: "tier", header: "Tier", label: "Tier",
      cell: (k) => {
        const st = statusCopy(k.statusKey);
        return st.tier
          ? <Chip kind={st.kind}>{TIER_LABEL[st.tier]}</Chip>
          : <span className="t-13 t-3">Outside the three tiers</span>;
      },
    },
    {
      id: "cells", header: "Cells", label: "Cells", numeric: true,
      cell: (k) => fmtInt(k.count),
    },
    {
      id: "counted", header: "How the count treats it", label: "How the count treats it",
      cell: (k) => <span className="t-13">{k.counted}</span>,
    },
    {
      id: "means", header: "What it means", label: "What it means",
      cell: (k) => <span className="t-13 t-2">{typographic(statusCopy(k.statusKey).definition)}</span>,
    },
  ];
}

/* ------------------------------------------------------------ the funds */
function fundColumns(): Column<FundRow>[] {
  return [
    {
      id: "fund", header: "Fund", label: "Fund", fixed: true,
      sortValue: (row) => row.name,
      cell: (row) => <Link to={`/product/${row.key}/record`} translate="no">{row.name}</Link>,
    },
    {
      id: "evidenced", header: "With a filing behind them", label: "With a filing behind them",
      numeric: true, sortValue: (row) => evidencedOf(row.cov),
      cell: (row) => fmtInt(evidencedOf(row.cov)),
    },
    {
      id: "computed", header: "Calculated", label: "Calculated",
      numeric: true, sortValue: (row) => row.cov.computed,
      cell: (row) => fmtInt(row.cov.computed),
    },
    {
      id: "soft", header: "Partly on record", label: "Partly on record",
      numeric: true, sortValue: (row) => softOf(row.cov),
      cell: (row) => fmtInt(softOf(row.cov)),
    },
    {
      id: "na", header: "Not applicable", label: "Not applicable",
      numeric: true, sortValue: (row) => row.cov.na,
      cell: (row) => fmtInt(row.cov.na),
    },
    {
      id: "verified", header: "Signed by a person", label: "Signed by a person",
      numeric: true, sortValue: (row) => row.cov.verified,
      cell: (row) => fmtInt(row.cov.verified),
    },
    {
      id: "resolved", header: "Resolved of resolvable", label: "Resolved of resolvable",
      numeric: true, sortValue: (row) => shareOf(row.cov),
      cell: (row) => fmtOf(row.cov.resolved, row.cov.resolvable),
    },
  ];
}

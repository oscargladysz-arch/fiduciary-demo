/* From the universe to the record. The steps between every registered
 * wrapper on file and the cells a person has signed.
 *
 * Every count on this route comes from the funnel chunk. A step that arrives
 * without a count of its own falls back to a figure the same chunk carries,
 * says which figure it used, and wears the computed chip: nothing here is
 * guessed and nothing is hard-coded, the number of steps included.
 *
 * Every string the chunk carries is either mapped to the words this page
 * uses everywhere else or held back. A step label goes through the label map
 * below, a step note and a method note through the same readability test,
 * and a class count is dropped unless the copy layer names its class.
 *
 * The share between two steps is computed live from the two counts. Where
 * the unit changes and the second count is larger than the first, the row
 * says the unit changed rather than printing a share above one hundred, and
 * it names both units from the map rather than assuming which two steps it
 * sits between.
 *
 * The cross-check is an agent pass. It is described in those words, it is
 * never called verification, and the count of signed cells sits beside it
 * so the two can never be read as the same thing.
 */
import { Fragment } from "react";
import { BarChart } from "../charts/charts";
import { Card, CardHead, Chip, EmptyState, Icon, Link, Skeleton, Stat, StatRow }
  from "../components/primitives";
import { PageHeader } from "../components/shell";
import { CENSUS_CLASS, SAY, routeTitle } from "../copy/copy";
import { useAsync } from "../data/hooks";
import { data } from "../data/index";
import { fmtDate, fmtInt, fmtNum, fmtOf, fmtPct, typographic } from "../format/format";
import type { FunnelStep, FunnelView as FunnelShape } from "../data/types";

/* The two open shapes of the chunk, as this route reads them. */
interface Totals {
  counts?: Record<string, number>;
  products?: number;
  resolvable?: number;
  resolved?: number;
  total?: number;
}
interface CrossCheck {
  cells_checked?: number;
  confirmed?: number;
  corrected?: number;
  unlocatable?: number;
  products?: number;
  date?: string;
}

/** What each step counts, in the reader’s words: the label beside the figure,
 *  and the singular and plural the share sentence needs. A step the map does
 *  not name counts cells of the record. */
const UNIT: Record<string, string> = { dark: "Wrappers", evaluated: "Funds" };
const UNIT_ONE: Record<string, string> = { dark: "wrapper", evaluated: "fund" };
const UNIT_MANY: Record<string, string> = { dark: "wrappers", evaluated: "funds" };

/** The name of each step, in the words the rest of this page uses. The record
 *  files a step under a key and carries a label of its own, and that label is
 *  the record’s vocabulary rather than the reader’s: the map turns the key
 *  into the page’s words, and the record’s label stands in only for a step
 *  the map does not know, and only while it reads as something a person can
 *  check. */
const STEP_LABEL: Record<string, string> = {
  dark: "Registered wrappers on file",
  evaluated: "Funds evaluated in full",
  resolved: "Cells resolved",
  evidenced: "Cells with a filing behind them",
  verified: "Cells signed by a person",
};

/** A figure the record does not carry says so rather than printing nothing. */
function figure(v: number | undefined | null): string {
  return typeof v === "number" ? fmtInt(v) : "Not on record";
}

/* A sentence from the chunk that would print an internal name is held back
 * rather than rewritten: a folder, a file name, a name joined by an
 * underscore, a ticket, a system endpoint, a code value, one of the words
 * that belong to the people who build this rather than to a reader, or the
 * name of a control this page does not have. */
const INTERNAL: RegExp[] = [
  /[A-Za-z0-9]_[A-Za-z0-9]/,
  /\.(json|py|csv|md|txt|ya?ml|js|html?)\b/i,
  /\b(data|docs|src|site|web)\//i,
  /\bR\d+-P\d+(-\d+)?\b/,
  /\bP\d-\d+\b/,
  /\b(EFTS|browse-edgar)\b/i,
  /\b(null|None|True|False|NaN)\b/,
  /\b(engine|artifacts?|typed|the writer|the build|this build|the site)\b/i,
  /\bsliders?\b/i,
];
function readable(note: string | undefined | null): boolean {
  const s = String(note || "");
  return s.trim().length > 0 && !INTERNAL.some((re) => re.test(s));
}

/** The step, named. */
function stepLabel(step: FunnelStep): string {
  return STEP_LABEL[step.id] || (readable(step.label) ? step.label : "A further step of the record");
}

interface Counted { step: FunnelStep; value: number | null; basis: string }

/* A step with no count of its own falls back to a figure the same chunk
 * carries, and the basis sentence says which one. */
function counted(steps: FunnelStep[], totals: Totals): Counted[] {
  const counts = totals.counts || {};
  return steps.map((step) => {
    if (typeof step.value === "number") return { step, value: step.value, basis: "" };
    if (step.id === "resolved" && typeof totals.resolved === "number") {
      return { step, value: totals.resolved, basis: "Read from the coverage totals the record keeps." };
    }
    if (step.id === "evidenced"
      && typeof counts.structured === "number" && typeof counts.extracted === "number") {
      return {
        step, value: counts.structured + counts.extracted,
        basis: `Counted as ${fmtInt(counts.structured)} structured plus ${fmtInt(counts.extracted)} extracted.`,
      };
    }
    return { step, value: null, basis: "" };
  });
}

/** The share between two steps, computed from the two counts beside it. */
function Drop({ from, to }: { from: Counted; to: Counted }) {
  const a = from.value;
  const b = to.value;
  if (a === null || b === null || a <= 0) {
    return (
      <p className="t-13 t-3">
        The share is not shown between these two steps, because one of them carries no count.
      </p>
    );
  }
  const basis = `${fmtInt(b)} / ${fmtInt(a)}`;
  if (b <= a) {
    const carried = (b / a) * 100;
    return (
      <div className="row-3">
        <Icon name="down" />
        <span className="t-13">Falls away</span>
        <span className="t-num t-semibold t-20">{fmtPct(100 - carried)}</span>
        <span className="t-12 t-3">Carried forward {fmtPct(carried)}, that is {basis}.</span>
      </div>
    );
  }
  return (
    <div className="row-3">
      <Icon name="down" />
      <span className="t-13">The unit changes here</span>
      <span className="t-num t-semibold t-20">{fmtNum(b / a, 1)}</span>
      <span className="t-12 t-3">
        {UNIT_MANY[to.step.id] || "cells of the record"} for each{" "}
        {UNIT_ONE[from.step.id] || "cell of the record"}, that is {basis}.
      </span>
    </div>
  );
}

export default function FunnelView() {
  const { value: funnel, error, loading } = useAsync<FunnelShape | null>(() => {
    const source = data();
    return source.getFunnel ? source.getFunnel() : Promise.resolve(null);
  }, []);

  if (error) return <EmptyState title={SAY.noRecord}>{error}</EmptyState>;
  if (loading) return <Skeleton lines={12} label={SAY.loadingRecord} />;
  if (!funnel) {
    return (
      <EmptyState title={SAY.noRecord}>
        This source carries the evaluated record but not the universe it was drawn from.
      </EmptyState>
    );
  }

  const totals = (funnel.totals || {}) as Totals;
  const counts = totals.counts || {};
  const cross = (funnel.crosscheck || {}) as CrossCheck;
  const rows = counted(funnel.steps || [], totals);
  const first = rows.find((r) => r.step.id === "dark") || rows[0] || null;
  const asOf = fmtDate(funnel.as_of);

  const signed = typeof counts.verified === "number" ? counts.verified : null;
  const cells = typeof totals.total === "number" ? totals.total : null;
  const byProduct = funnel.verified_by_product || {};
  const funds = Object.keys(byProduct).length;
  const fundsSigned = Object.values(byProduct).filter((n) => Number(n) > 0).length;

  const classes = Object.entries(funnel.counts_by_class || {})
    .filter(([key]) => Boolean(CENSUS_CLASS[key]))
    .map(([key, value]) => ({ label: CENSUS_CLASS[key], value: Number(value) }))
    .sort((a, b) => b.value - a.value);
  const classTotal = classes.reduce((a, c) => a + c.value, 0);
  const unnamed = Object.keys(funnel.counts_by_class || {}).length - classes.length;

  const notes = (funnel.method_notes || []).filter(readable);
  const held = (funnel.method_notes || []).length - notes.length;

  return (
    <div className="stack-5">
      <PageHeader
        title={routeTitle("funnel")}
        sub={"From every registered wrapper on file down to the cells a person has signed, with the share "
          + "that reaches each next step computed from the two counts beside it."}
        actions={<Link to="/universe">Search the universe</Link>}
      />

      <StatRow>
        <Stat label={first ? stepLabel(first.step) : STEP_LABEL.dark}
          value={figure(first ? first.value : null)}
          source={asOf ? `As of ${asOf}` : "Every wrapper the universe enumerates"} />
        <Stat label={STEP_LABEL.evaluated} value={figure(totals.products)}
          source="Each on the same six-factor record" />
        <Stat label={STEP_LABEL.resolved}
          value={typeof totals.resolved === "number" && typeof totals.resolvable === "number"
            ? fmtOf(totals.resolved, totals.resolvable)
            : figure(totals.resolved)}
          source="Structured, extracted, computed or answered not applicable" />
        <Stat label={STEP_LABEL.verified} value={figure(signed)}
          source={SAY.verificationPending} />
      </StatRow>

      <section className="stack-4" aria-labelledby="funnel-steps">
        <h2 id="funnel-steps" className="t-20">The steps, in order</h2>
        <p className="t-14 t-2">The steps at the top count wrappers and funds. The steps below them
          count cells of the record, so the unit changes once on the way down.</p>
        {rows.length === 0 ? (
          <EmptyState title="No step is on record here">
            The universe count and the coverage totals of the record fill this list.
          </EmptyState>
        ) : rows.map((row, i) => (
          <Fragment key={row.step.id}>
            <Card>
              <CardHead title={stepLabel(row.step)} level={3}>
                {row.basis && <Chip kind="computed">Computed</Chip>}
              </CardHead>
              <Stat large label={UNIT[row.step.id] || "Cells"} value={figure(row.value)} />
              {readable(row.step.note) && <p className="t-14 t-2">{typographic(row.step.note)}</p>}
              {row.basis && <p className="t-12 t-3">{row.basis}</p>}
            </Card>
            {i < rows.length - 1 && <Drop from={row} to={rows[i + 1]} />}
          </Fragment>
        ))}
      </section>

      <section className="stack-4" aria-labelledby="funnel-classes">
        <h2 id="funnel-classes" className="t-20">The wrappers on file, by class</h2>
        {classes.length === 0 ? (
          <EmptyState title="No class count is on record here">
            {unnamed > 0
              ? `The universe sorts every wrapper it enumerates into one class, and this page has no reader `
                + `name for any of the ${fmtInt(unnamed)} classes it counted.`
              : "The universe sorts every wrapper it enumerates into one class, and those counts fill this chart."}
          </EmptyState>
        ) : (
          <Card>
            <BarChart
              title="Registered wrappers by class"
              description="Every registered wrapper on file, sorted into one class each, largest class first."
              bars={classes}
              format={fmtInt}
              footer={
                <>
                  {asOf ? `As of ${asOf}. ` : ""}
                  The classes shown add to {fmtInt(classTotal)} wrappers.
                  {unnamed > 0 && ` ${fmtInt(unnamed)} further classes are left out here, because this page has `
                    + "no reader name for them."}
                </>
              }
            />
          </Card>
        )}
      </section>

      <section className="stack-4" aria-labelledby="funnel-check">
        <h2 id="funnel-check" className="t-20">The cross-check and the signatures</h2>
        <div className="two-col">
          <Card>
            <CardHead title="An agent pass over the record" level={3}>
              <Chip kind="accent">Agent pass</Chip>
            </CardHead>
            <p className="t-14 t-2">An agent pass re-opened the filings and looked for each figure a second
              time. It is a check on the record, not a signature by a person, and it moved no cell into a
              higher tier.</p>
            <dl className="field-list">
              <dt>Cells re-located</dt>
              <dd className="t-num">{figure(cross.cells_checked)}</dd>
              <dt>Confirmed</dt>
              <dd className="t-num">{figure(cross.confirmed)}</dd>
              <dt>Corrected</dt>
              <dd className="t-num">{figure(cross.corrected)}</dd>
              <dt>Not found a second time</dt>
              <dd className="t-num">{figure(cross.unlocatable)}</dd>
              <dt>Funds covered</dt>
              <dd className="t-num">
                {typeof cross.products === "number" && typeof totals.products === "number"
                  ? fmtOf(cross.products, totals.products)
                  : figure(cross.products)}
              </dd>
              <dt>Date of the pass</dt>
              <dd>{cross.date ? fmtDate(cross.date) : "Not on record"}</dd>
            </dl>
          </Card>

          <Card>
            <CardHead title={STEP_LABEL.verified} level={3}>
              <Chip kind="pending">Pending</Chip>
            </CardHead>
            <Stat large label="Signed cells" value={figure(signed)} source={SAY.verificationPending} />
            {signed !== null && cells !== null && (
              <p className="t-14 t-2">{SAY.verificationCount(signed, cells)}</p>
            )}
            {funds > 0 && (
              <p className="t-13 t-3">{fmtOf(fundsSigned, funds)} funds carry a signed cell.</p>
            )}
            <Link to="/verification">Open the verification queue</Link>
          </Card>
        </div>
      </section>

      <section className="stack-4" aria-labelledby="funnel-method">
        <h2 id="funnel-method" className="t-20">How the universe was counted</h2>
        <Card sunken>
          {notes.length === 0 ? (
            <p className="t-14 t-2">
              {held > 0
                ? "Every method note on record here names internal systems and file names rather than "
                  + "anything a reader can check, so none of them is shown."
                : "No method note is on record here. The steps the universe was counted by fill this list."}
            </p>
          ) : (
            <ul className="stack-2">
              {notes.map((note, i) => (
                <li key={i} className="t-14 t-2">{typographic(note)}</li>
              ))}
            </ul>
          )}
          {notes.length > 0 && held > 0 && (
            <p className="t-13 t-3">{fmtInt(held)} further notes are held back here, because they name
              internal systems and file names rather than anything a reader can check.</p>
          )}
        </Card>
      </section>
    </div>
  );
}

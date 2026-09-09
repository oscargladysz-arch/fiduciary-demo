/* Reference plans, a global route.
 *
 * The anonymized plans the record holds, and the intake form for one more.
 * How many there are is read from the record and never written into prose.
 * Every figure on a plan card is read from that plan record and formatted
 * here, never restated in prose, and a figure the record does not hold prints
 * the reason the record gives beside its label rather than a bare dash.
 *
 * Choosing a plan is a navigation and not a filter: it goes through the plan
 * selector, so the choice rides in the address, a link carries it and Back
 * returns to the plan a reader came from.
 *
 * The intake form is what the reader enters, never evidence, and it says so
 * with the adviser chip the copy layer defines. It validates in the browser,
 * counts what needs attention in a live region, and produces a file that
 * carries the entered fields and the date and nothing else.
 */
import { Fragment, useMemo, useState } from "react";
import { planOptions, usePlan } from "../app/plan";
import { Field, FileDownload, Input, NumberInput, useUnsavedGuard } from "../components/form";
import { Disclosure } from "../components/overlay";
import { Button, Card, CardHead, Chip, EmptyState, Link, Skeleton, Stat, StatRow } from "../components/primitives";
import { ContextChip, PageHeader } from "../components/shell";
import { SAY, status as statusCopy } from "../copy/copy";
import { useAsync, useIndex } from "../data/hooks";
import { data } from "../data/index";
import { fmtDate, fmtDateShort, fmtInt, fmtIso, fmtMoney, fmtPct } from "../format/format";
import type { PlansView as PlansShape } from "../data/types";

/* ------------------------------------------------------ the plan document */
/* The public plan document, as the plan chunk carries it. The shared view
 * shapes do not carry it, so the shape this view reads is stated here. */
interface Counts { [field: string]: number | null | undefined }
interface ProxyInput { meaning?: string; value?: number | null }
interface OutflowProxy {
  value?: number | null;
  reason?: string;
  unit?: string;
  formula?: string;
  what?: string;
  inputs?: Record<string, ProxyInput>;
}
interface NotOnRecord { value?: number | null; reason?: string; source?: string }
interface PlanSource { publisher?: string; pulled?: string }
interface PlanDoc {
  plan_key?: string;
  display_label?: string;
  plan_year?: string;
  demand_sentence?: string;
  archetype?: string;
  participants?: Counts;
  financials?: Counts;
  schedule_h?: {
    filed_outflow_proxy?: OutflowProxy;
    benefit_payments_2e?: NotOnRecord;
    qdia_indicator?: NotOnRecord;
  };
  plan_characteristics?: { codes_decoded?: string; note?: string; pension_benefit_codes?: string };
  source?: PlanSource;
}

/** A plan year as the filing states it, both ends through the date layer. */
function planYear(raw: string | undefined): string {
  const m = /^\s*(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})\s*$/.exec(raw || "");
  if (m) return `${fmtDateShort(m[1])} to ${fmtDateShort(m[2])}`;
  return (raw || "").trim() || "Not on record";
}

/** A figure the record holds, or the reason the record gives for not holding
 *  it. Never a bare dash and never a guess. */
function Figure({ value, render, reason }:
  { value: number | null | undefined; render: (n: number) => string; reason?: string }) {
  if (typeof value !== "number") {
    return <span className="t-13 t-3">{reason || "Not on record"}</span>;
  }
  return <span className="t-num">{render(value)}</span>;
}

/* ------------------------------------------------------------ a plan card */
function PlanCard({ planKey, doc, selected }: { planKey: string; doc: PlanDoc; selected: boolean }) {
  const people = doc.participants || {};
  const money = doc.financials || {};
  const sh = doc.schedule_h || {};
  const proxy = sh.filed_outflow_proxy || {};
  const proxyReason = proxy.reason || sh.benefit_payments_2e?.reason;
  const chars = doc.plan_characteristics || {};
  const source = doc.source || {};

  return (
    <Card as="article" className="stack-4" aria-current={selected ? "true" : undefined}>
      <CardHead title={doc.display_label || "A plan on record"} level={3}>
        {selected && <Chip kind="accent">Selected</Chip>}
      </CardHead>

      {doc.archetype && <p className="t-13 t-3">{doc.archetype}</p>}

      <dl className="field-list">
        <dt>Plan year</dt>
        <dd>{planYear(doc.plan_year)}</dd>
        <dt>Participants with account balances</dt>
        <dd><Figure value={people.with_account_balances} render={fmtInt} /></dd>
        <dt>Active participants</dt>
        <dd><Figure value={people.active_eoy} render={fmtInt} /></dd>
        <dt>Separated participants with balances</dt>
        <dd><Figure value={people.separated_deferred_vested} render={fmtInt} /></dd>
        <dt>Retirees receiving payments</dt>
        <dd><Figure value={people.retired_receiving} render={fmtInt} /></dd>
        <dt>Net assets at the end of the plan year</dt>
        <dd><Figure value={money.net_assets_eoy} render={(n) => fmtMoney(n)} /></dd>
        <dt>Filed outflow proxy</dt>
        <dd>
          <Figure value={proxy.value} render={(n) => fmtPct(n)} reason={proxyReason} />
          {typeof proxy.value === "number" && proxy.unit && (
            <div className="t-12 t-3">{proxy.unit}</div>
          )}
        </dd>
      </dl>

      {doc.demand_sentence && <p className="t-14 t-2">{doc.demand_sentence}</p>}

      <Disclosure summary={<>What is behind these figures
        <span className="sr-only"> for {doc.display_label || "this plan on record"}</span></>}>
        <div className="stack-4">
          {proxy.what && <p className="t-13 t-2">{proxy.what}</p>}
          {proxy.formula && (
            <dl className="field-list">
              <dt>Worked out as</dt>
              <dd className="t-13">{proxy.formula}</dd>
              {Object.entries(proxy.inputs || {}).map(([field, input]) => (
                <Fragment key={field}>
                  <dt>{input.meaning || "An input on record"}</dt>
                  <dd><Figure value={input.value} render={(n) => fmtMoney(n)} /></dd>
                </Fragment>
              ))}
            </dl>
          )}
          {chars.codes_decoded && (
            <dl className="field-list">
              <dt>Benefit codes as filed</dt>
              <dd>{chars.pension_benefit_codes || "Not on record"}</dd>
              <dt>What those codes say</dt>
              <dd className="t-13">{chars.codes_decoded}</dd>
              {chars.note && (<><dt>What that means here</dt><dd className="t-13">{chars.note}</dd></>)}
            </dl>
          )}
          {sh.qdia_indicator && typeof sh.qdia_indicator.value !== "number" && sh.qdia_indicator.reason && (
            <p className="t-13 t-3">Default investment election: {sh.qdia_indicator.reason}.</p>
          )}
          {source.publisher && (
            <p className="t-12 t-3">
              Read from {source.publisher}
              {source.pulled ? `, pulled ${fmtDate(source.pulled)}` : ""}.
            </p>
          )}
        </div>
      </Disclosure>

      {selected
        ? <p className="t-13 t-3">Every panel that follows the plan is reading this one.</p>
        : <Link to="/plans" params={{ plan: planKey }}
          aria-label={`Use this plan, ${doc.display_label || "a plan on record"}`}>Use this plan</Link>}
    </Card>
  );
}

/* --------------------------------------------------------- the intake form */
type Kind = "text" | "count" | "money";
interface Spec { key: string; label: string; ask: string; kind: Kind; hint?: string; required?: boolean }

/* The order here is the order of the fields in the file the form produces. */
const NAMING: Spec[] = [
  {
    key: "display_label", label: "Display label for the plan", ask: "a display label", kind: "text", required: true,
    hint: "How the plan should read on screen. A description of the plan and its size is enough, leave the sponsor out of it.",
  },
  {
    key: "plan_year", label: "Plan year", ask: "the plan year", kind: "text", required: true,
    hint: "The plan year these figures cover, written the way the filing writes it.",
  },
];
const FILED: Spec[] = [
  {
    key: "net_assets_eoy", label: "Net assets at the end of the plan year",
    ask: "net assets at the end of the plan year", kind: "money",
    hint: "Total net assets at the close of the year, from the plan financial schedule.",
  },
  {
    key: "net_assets_boy", label: "Net assets at the beginning of the plan year",
    ask: "net assets at the beginning of the plan year", kind: "money",
    hint: "The same schedule at the start of the year. An outflow rate is measured against this figure.",
  },
  {
    key: "tot_admin_expenses", label: "Total administrative expenses",
    ask: "total administrative expenses", kind: "money",
    hint: "Administrative expenses for the plan year, from the same schedule.",
  },
  {
    key: "tot_expenses", label: "Total expenses", ask: "total expenses", kind: "money",
    hint: "All expenses for the plan year. Total expenses less administrative expenses stands in for benefit payments while the benefits line is not on record.",
  },
  {
    key: "with_account_balances", label: "Participants with account balances",
    ask: "the number of participants with account balances", kind: "count",
    hint: "Everyone holding an account at the end of the plan year.",
  },
  {
    key: "active_eoy", label: "Active participants", ask: "the number of active participants", kind: "count",
    hint: "Participants still working for the sponsor at the end of the plan year.",
  },
  {
    key: "separated_deferred_vested", label: "Separated participants with balances",
    ask: "the number of separated participants with balances", kind: "count",
    hint: "People who have left and still hold an account. This is the near-term liquidity tail.",
  },
  {
    key: "retired_receiving", label: "Retirees receiving payments",
    ask: "the number of retirees receiving payments", kind: "count",
    hint: "Retired participants drawing benefits at the end of the plan year.",
  },
  {
    key: "pension_benefit_codes", label: "Pension benefit codes", ask: "the pension benefit codes", kind: "text",
    hint: "The plan characteristic codes exactly as the filing lists them, run together with no spaces.",
  },
];
const FIELDS: Spec[] = [...NAMING, ...FILED];

const NUMBER = /^\d+(\.\d+)?$/;
function cleaned(raw: string): string { return raw.replace(/[,\s]/g, ""); }

/** One sentence, beside the field, saying what is wrong with it. */
function errorFor(spec: Spec, raw: string): string {
  const v = (raw || "").trim();
  if (!v) return spec.required ? `Enter ${spec.ask} before the file can be produced.` : "";
  if (spec.kind !== "text" && !NUMBER.test(cleaned(v))) {
    return "Enter this as a number, using digits and at most one decimal point.";
  }
  return "";
}

function IntakeForm() {
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const advisor = statusCopy("advisor-stated");

  const set = (key: string, v: string) => setValues((s) => ({ ...s, [key]: v }));

  const errors = useMemo(() => {
    const out: Record<string, string> = {};
    for (const spec of FIELDS) {
      const message = errorFor(spec, values[spec.key] || "");
      if (message) out[spec.key] = message;
    }
    return out;
  }, [values]);

  const needing = Object.keys(errors).length;
  const dirty = FIELDS.some((spec) => (values[spec.key] || "").trim() !== "");
  useUnsavedGuard(dirty);

  const ready = submitted && needing === 0 && dirty;

  const fileText = useMemo(() => {
    const out: Record<string, string | number> = {};
    for (const spec of FIELDS) {
      const raw = (values[spec.key] || "").trim();
      if (!raw) continue;
      out[spec.key] = spec.kind === "text" ? raw : Number(cleaned(raw));
    }
    out.date = fmtIso(new Date());
    return JSON.stringify(out, null, 2);
  }, [values]);

  const slug = (values.display_label || "").toLowerCase().replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "").slice(0, 48);
  const fileName = slug ? `plan-profile-${slug}` : "plan-profile";

  const live = !submitted ? ""
    : needing === 0 ? "Every field checks out. The file is ready below."
      : `${fmtInt(needing)} ${needing === 1 ? "field needs" : "fields need"} attention.`;

  const control = (spec: Spec) => (
    <Field key={spec.key} label={spec.label} hint={spec.hint} required={spec.required}
      error={submitted ? errors[spec.key] : undefined}>
      {(ids) => (spec.kind === "text"
        ? <Input ids={ids} value={values[spec.key] || ""} autoComplete="off" spellCheck={false}
          onChange={(e) => set(spec.key, e.target.value)} />
        : <NumberInput ids={ids} value={values[spec.key] || ""} autoComplete="off" decimal={spec.kind === "money"}
          onChange={(e) => set(spec.key, e.target.value)} />)}
    </Field>
  );

  return (
    <Card className="stack-4">
      <div className="row-3">
        <Chip kind="advisor">{advisor.label}</Chip>
        <span className="t-13 t-3">{advisor.definition}</span>
      </div>
      <p className="t-14 t-2">
        Enter what your own plan filing states and this page writes a small file of those figures. The file is
        written in your browser and saved to your computer, and nothing is sent anywhere.
      </p>

      <form className="stack-4" noValidate onSubmit={(e) => { e.preventDefault(); setSubmitted(true); }}>
        <h3 className="t-16">The plan and its year</h3>
        <div className="grid-2">{NAMING.map(control)}</div>

        <h3 className="t-16">What the filing shows</h3>
        <div className="grid-2">{FILED.map(control)}</div>

        <div className="form-actions">
          <Button variant="primary" size="md" type="submit">Check the form and write the file</Button>
          <Button variant="secondary" onClick={() => { setValues({}); setSubmitted(false); }}>Start again</Button>
        </div>
        <p className="t-13 t-3" aria-live="polite">{live}</p>
      </form>

      {ready && (
        <div className="stack-4">
          <FileDownload name={fileName} text={fileText} label="Download the plan profile"
            description={`Written on ${fmtDate(new Date())}. It carries the fields you entered and the date, and nothing else.`} />
          <p className="t-14 t-2">
            Send the file to the person who runs your evaluation. They load it as one more plan, and every panel
            that follows the plan then reads your own filed figures instead of a reference plan. Keep the label
            free of the sponsor name and the file stays anonymous.
          </p>
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------- the route */
const INTRO = `These plans are anonymized stand-ins for the sponsors we work with, each one assembled from a filed plan record. Every figure below comes from that plan record, and nothing here names or identifies a sponsor. ${SAY.anonymized}`;

export default function PlansView() {
  const { value: index, error: indexError, loading: indexLoading } = useIndex();
  const { value: plans, error, loading } = useAsync<PlansShape | null>(() => {
    const source = data();
    return source.getPlans ? source.getPlans() : Promise.resolve(null);
  }, []);
  const [plan, setPlan] = usePlan(index);
  const structured = statusCopy("structured");

  const cards = useMemo(() => {
    if (!plans) return [] as { key: string; doc: PlanDoc }[];
    const order = plans.order && plans.order.length ? plans.order : Object.keys(plans.plans || {});
    return order
      .filter((key) => plans.plans && plans.plans[key])
      .map((key) => ({ key, doc: plans.plans[key] as unknown as PlanDoc }));
  }, [plans]);

  if (error || indexError) return <EmptyState title={SAY.noRecord}>{error || indexError}</EmptyState>;
  if (loading || indexLoading || !index) return <Skeleton lines={10} label={SAY.loadingRecord} />;

  const counts = index.coverage_totals.counts || {};

  return (
    <div className="stack-5">
      <PageHeader title="Reference plans" sub={INTRO} />

      <StatRow>
        <Stat label="Reference plans" value={fmtInt(cards.length)}
          source="Each one anonymized, each one from a filed plan record" />
        <Stat label="Signed by a person" value={fmtInt(counts.verified || 0)} source={SAY.verificationPending} />
      </StatRow>

      <section className="stack-4" aria-labelledby="plans-record">
        <h2 id="plans-record" className="t-20">The plans on record</h2>

        <Card className="stack-2">
          <ContextChip id="plans-plan" label="Plan" value={plan} options={planOptions(index)} onChange={setPlan}
            note="The panels that follow the plan read this choice, and it rides in the address so Back returns to it." />
          <p className="t-13 t-3">
            <Chip kind="structured">{structured.label}</Chip> {structured.definition}
          </p>
        </Card>

        {cards.length === 0 ? (
          <EmptyState title="No reference plan is on record here">
            A plan appears here once a filed plan record for it is loaded into the workspace.
          </EmptyState>
        ) : (
          <div className="grid-2">
            {cards.map(({ key, doc }) => (
              <PlanCard key={key} planKey={key} doc={doc} selected={key === plan} />
            ))}
          </div>
        )}
      </section>

      <section className="stack-4" aria-labelledby="plans-intake">
        <h2 id="plans-intake" className="t-20">Add your own plan</h2>
        <IntakeForm />
      </section>

      <Card sunken>
        <CardHead title="How to read these plan figures" level={2} />
        <p className="t-14 t-2">
          A plan figure above is the filing tagging its own number, so a figure here and the same figure on a
          liquidity panel cannot disagree. A figure the plan record does not hold says why in place of the number.
          What you enter in the form is your own input to the evaluation and is never treated as evidence.
        </p>
        <p className="t-13 t-3">
          {SAY.anonymized} {SAY.verificationPending}{" "}
          {SAY.verificationCount(counts.verified || 0, Number(index.coverage_totals.total) || 0)}{" "}
          <Link to="/verification">See the verification queue</Link>
        </p>
      </Card>
    </div>
  );
}

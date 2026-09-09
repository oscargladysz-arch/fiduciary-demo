/* The liquidity panel: one fund, one plan, two verdicts, one live state.
 *
 * The page this replaces printed the record’s own bullets above a block the
 * reader could move, so the first moved position made the page argue with
 * itself. Here there is exactly one state object. It starts where the record
 * set it, the URL carries it, and every figure on the page is computed from
 * it. While it sits at the record’s own positions the page shows the record’s
 * own sentence, word for word. Once it does not, the page shows the sentence
 * it just computed, and says which of the two the reader is looking at.
 *
 * The two verdicts are separate readings and are never blended. The
 * structural one reads the dealing terms and holds whatever the plan is. The
 * scenario one is illustrative, depends on the plan, and is labeled on every
 * surface that carries it.
 *
 * No h1: the product header above this panel supplies it. */
import { Fragment, useEffect, useMemo, useState } from "react";
import { setParams, useRoute } from "../app/router";
import { usePlan } from "../app/plan";
import { BarChart } from "../charts/charts";
import { CiteButton, NoFigure } from "../components/citation";
import { Slider } from "../components/form";
import { Disclosure } from "../components/overlay";
import {
  Button, Card, CardHead, Chip, EmptyState, Link, Skeleton, Stat, StatRow, VerdictBanner,
} from "../components/primitives";
import type { BannerKind } from "../components/primitives";
import { Table } from "../components/table";
import type { Column } from "../components/table";
import { SAY, status as statusCopy, verdict as verdictCopy } from "../copy/copy";
import { useAsync, useIndex } from "../data/hooks";
import { data } from "../data/index";
import { fmtDate, fmtInt, fmtMoney, fmtMoneyCompact, fmtNum, fmtPct, withUnit } from "../format/format";
import type { LiquidityView as LiquidityShape } from "../data/types";

/* ------------------------------------------------------------- the shape */
/* The liquidity chunk carries its match as an open map, so the fields this
 * panel reads are named here rather than in the shared types. */
interface FiledOutflow {
  formula?: string; inputs?: Record<string, number>; label?: string;
  plan_year?: string; rate_pct?: number; source?: string; what?: string;
}
interface PlanInputs {
  filed_outflow_proxy_pct?: number; net_assets?: number; plan_year?: string;
  separated_with_balances?: number; tail_share?: number; tail_share_pct?: number;
}
interface WindowFacts { cap_per_window_pct?: number; period?: string; windows_per_year?: number }
interface Drivers {
  binding_cap?: { pct?: number; period?: string } | null;
  cadence_per_year?: number; rung?: string; sentence?: string; window?: WindowFacts | null;
}
interface FundCapacity {
  available?: boolean; annual_capacity_usd?: number; fund_net_assets_usd?: number;
  net_assets_approx?: boolean; net_assets_cell?: string;
}
interface Scenario {
  active_annual_turnover_pct?: number; allocation_pct_of_plan?: number;
  annual_wrapper_capacity_pct?: number | null; capacity_note?: string; drivers?: Drivers;
  filed_outflow_proxy_pct?: number; fund_capacity?: FundCapacity; plan_allocation_usd?: number;
  schedule_h_lines?: string[]; tail_annual_turnover_pct?: number;
}
interface Stressed { multiples?: { active_multiple?: number; tail_multiple?: number }; outcome?: string }
interface WrapperFacts {
  annual_capacity_pct?: number | null; cadence_per_year?: number; cap_base?: string;
  cap_pct?: number | null; cap_period?: string | null; caps_label?: string; dealing_label?: string;
  early_fee?: string; exchange?: boolean; gate_history?: boolean; net_assets_cell?: string;
  program_status?: string | null; program_status_as_of?: string | null;
}
interface Match {
  citations?: string[]; filed_outflow?: FiledOutflow; layers?: string; missing_facts?: string[];
  missing_facts_labels?: string[]; plan_direction?: string; plan_display_label?: string;
  plan_inputs?: PlanInputs; scenario?: Scenario; scenario_verdict?: string; stressed_scenario?: Stressed;
  structural_reasons?: string[]; verdict?: string; wrapper_facts?: WrapperFacts;
  /* the sentences the document for this plan carries, unedited */
  scenario_reasons?: string[];
}

/* --------------------------------------------------------- reader words */
/* Record values the copy layer does not map, said in plain words here. */
const DIRECTION: Record<string, string> = {
  total: "Participants direct every account",
  partial: "Participants direct part of the plan",
};
const PROGRAM_STATUS: Record<string, string> = {
  active: "Accepting requests",
  suspended: "Suspended",
};
/* A verdict the record qualifies, where the copy layer maps only its head. */
const QUALIFIER: Record<string, string> = { mechanical: "On the dealing mechanics" };
/* The filed figures the outflow proxy is built from. A key with no entry here
 * is not printed, because its own name is not a reader’s word. */
const INPUT_LABEL: Record<string, string> = {
  net_assets_boy: "Net assets at the start of the plan year",
  tot_expenses: "Total expenses",
  tot_admin_expenses: "Total administrative expenses",
};

const BANNER = new Set(["aligned", "conditional", "weak", "misaligned", "partial", "pending", "info", "alarm"]);
function bannerKind(kind: string): BannerKind {
  return (BANNER.has(kind) ? kind : "pending") as BannerKind;
}

interface Reading { kind: BannerKind; label: string; definition: string; qualifier: string }
/** The verdict as a reader meets it. The copy layer decides the label and the
 *  one-line definition. Where the record qualifies a verdict the copy layer
 *  maps only under its head, the head decides and the qualifier is said
 *  beside it, and where the record carries a state rather than a verdict the
 *  copy layer’s own word for that state is used. */
function reading(raw: string | undefined): Reading {
  const whole = verdictCopy(raw);
  if (whole.kind !== "pending") {
    return { kind: bannerKind(whole.kind), label: whole.label, definition: whole.definition, qualifier: "" };
  }
  const parts = String(raw || "").split("-");
  const head = verdictCopy(parts[0]);
  if (head.kind !== "pending") {
    return {
      kind: bannerKind(head.kind), label: head.label, definition: head.definition,
      qualifier: QUALIFIER[parts[1]] || "",
    };
  }
  const state = statusCopy(parts[0]);
  return { kind: bannerKind(state.kind), label: state.label, definition: state.definition, qualifier: "" };
}

/** A sentence the record cites carries its dates in filing form. Every date a
 *  reader sees goes through the date formatter, sentences included. */
function datesInWords(s: string | undefined): string {
  return String(s || "").replace(/\d{4}-\d{2}-\d{2}/g, (iso) => fmtDate(iso) || iso);
}
function sentenceCase(s: string | undefined): string {
  const v = String(s || "");
  return v ? v.charAt(0).toUpperCase() + v.slice(1) : "";
}

/* ------------------------------------------------------------ the state */
/* One object. Four numbers the record itself carries, each of which the
 * reader can move, and nothing on the page that is not computed from them. */
interface Inputs { allocation: number; outflow: number; tail: number; active: number }
interface Span { min: number; max: number; step: number }
type Field = keyof Inputs;

const PARAM: Record<Field, string> = {
  allocation: "alloc", outflow: "outflow", tail: "tail", active: "active",
};
/* The travel of each control, widened where the record’s own position sits
 * outside it, so the record’s position is always reachable. */
function spans(d: Inputs): Record<Field, Span> {
  const to = (ceiling: number, at: number, step: number): Span =>
    ({ min: 0, max: Math.max(ceiling, Math.ceil(at * 2)), step });
  return {
    allocation: to(25, d.allocation, 0.1),
    outflow: to(40, d.outflow, 0.01),
    tail: to(60, d.tail, 0.1),
    active: to(40, d.active, 0.1),
  };
}

const round2 = (v: number) => Math.round(v * 100) / 100;
const FIELDS: Field[] = ["allocation", "outflow", "tail", "active"];

function readInputs(params: URLSearchParams, d: Inputs, s: Record<Field, Span>): Inputs {
  const out = { ...d };
  for (const f of FIELDS) {
    const raw = params.get(PARAM[f]);
    if (raw === null) continue;
    const n = Number(raw);
    if (!Number.isFinite(n)) continue;
    out[f] = round2(Math.min(s[f].max, Math.max(s[f].min, n)));
  }
  return out;
}
function sameInputs(a: Inputs, b: Inputs): boolean {
  return FIELDS.every((f) => Math.abs(a[f] - b[f]) < 1e-9);
}

/* ------------------------------------------------------- the arithmetic */
interface Live {
  positionUsd: number | null;
  filedPct: number; turnoverPct: number; stressedPct: number; incrementPct: number;
  filedUsd: number | null; turnoverUsd: number | null; stressedUsd: number | null;
  capacityPct: number | null; capacityUsd: number | null;
  windows: number | null; capPerWindowPct: number | null;
  filedPerWindow: number | null; turnoverPerWindow: number | null; stressedPerWindow: number | null;
  headroomPct: number | null; fundSharePct: number | null;
  rung: string;
}

function compute(inputs: Inputs, m: Match): Live {
  const pi = m.plan_inputs || {};
  const sc = m.scenario || {};
  const wf = m.wrapper_facts || {};
  const mult = m.stressed_scenario?.multiples || {};
  const tailShare = typeof pi.tail_share === "number" ? pi.tail_share : 0;
  const tailMult = typeof mult.tail_multiple === "number" ? mult.tail_multiple : 1;
  const activeMult = typeof mult.active_multiple === "number" ? mult.active_multiple : 1;
  const netAssets = typeof pi.net_assets === "number" ? pi.net_assets : null;

  const positionUsd = netAssets === null ? null : (netAssets * inputs.allocation) / 100;
  const turnoverPct = inputs.tail * tailShare + inputs.active * (1 - tailShare);
  const stressedTurnover = inputs.tail * tailMult * tailShare + inputs.active * activeMult * (1 - tailShare);
  const incrementPct = stressedTurnover - turnoverPct;
  const stressedPct = inputs.outflow + incrementPct;

  const capacityPct = typeof sc.annual_wrapper_capacity_pct === "number" ? sc.annual_wrapper_capacity_pct
    : typeof wf.annual_capacity_pct === "number" ? wf.annual_capacity_pct : null;
  /* a wrapper can carry two caps, and the binding one decides the window: the
   * record names it, so it is read rather than picked here */
  const bound = sc.drivers?.window?.cap_per_window_pct ?? sc.drivers?.binding_cap?.pct;
  const capPerWindowPct = typeof bound === "number" ? bound
    : typeof wf.cap_pct === "number" ? wf.cap_pct : null;
  const perYear = sc.drivers?.window?.windows_per_year;
  const windows = typeof perYear === "number" ? perYear
    : typeof wf.cadence_per_year === "number" && capPerWindowPct !== null ? wf.cadence_per_year : null;

  const share = (pct: number) => (positionUsd === null ? null : (positionUsd * pct) / 100);
  const perWindow = (pct: number) => (windows && windows > 0 && capPerWindowPct !== null ? pct / windows : null);
  const fundCapacityUsd = m.scenario?.fund_capacity?.annual_capacity_usd;
  const filedUsd = share(inputs.outflow);

  return {
    positionUsd,
    filedPct: inputs.outflow, turnoverPct, stressedPct, incrementPct,
    filedUsd, turnoverUsd: share(turnoverPct), stressedUsd: share(stressedPct),
    capacityPct, capacityUsd: capacityPct === null ? null : share(capacityPct),
    windows, capPerWindowPct,
    filedPerWindow: perWindow(inputs.outflow),
    turnoverPerWindow: perWindow(turnoverPct),
    stressedPerWindow: perWindow(stressedPct),
    headroomPct: capacityPct === null ? null : capacityPct - stressedPct,
    fundSharePct: filedUsd !== null && typeof fundCapacityUsd === "number" && fundCapacityUsd > 0
      ? (filedUsd / fundCapacityUsd) * 100 : null,
    rung: wf.exchange ? "exchange"
      : capacityPct === null ? "unknown"
        : inputs.outflow > capacityPct ? "base"
          : stressedPct > capacityPct ? "stress" : "none",
  };
}

/** The sentence for the positions the reader is holding. The record’s own
 *  sentence is shown instead while those positions are the record’s. */
function recomputed(live: Live, period: string): string {
  const filed = fmtPct(live.filedPct, 1);
  const stressed = fmtPct(live.stressedPct, 1);
  const cap = live.capacityPct === null ? "" : fmtPct(live.capacityPct, 1);
  const head = live.rung === "exchange"
    ? `Shares trade on the exchange, so ${filed} and ${stressed} of the position a year are selling rates against market depth and no fund cap applies.`
    : live.capacityPct === null
      ? `The yearly capacity of this wrapper is not on record, so ${filed} and ${stressed} of the position a year cannot be set against it.`
      : live.rung === "base"
        ? `The outflow rate alone passes the capacity: ${filed} of the position a year against a yearly capacity of ${cap}.`
        : live.rung === "stress"
          ? `The outflow rate ${filed} of the position a year sits inside the yearly capacity ${cap} and the stressed demand ${stressed} passes it.`
          : `Neither rate reaches the limit: the outflow rate ${filed} and the stressed demand ${stressed} of the position a year both sit inside the yearly capacity ${cap}.`;
  const win = live.capPerWindowPct !== null && live.filedPerWindow !== null && live.stressedPerWindow !== null
    ? ` Per ${period}: ${fmtPct(live.filedPerWindow, 1)} at the outflow rate and ${fmtPct(live.stressedPerWindow, 1)} stressed, against a cap of ${fmtPct(live.capPerWindowPct, 1)}.`
    : "";
  return head + win;
}

/* --------------------------------------------------------- small pieces */
function Figure({ value, reason }: { value: string; reason: string }) {
  return value ? <span className="t-num">{value}</span> : <span className="t-13 t-3">{reason}</span>;
}

interface RateRow { id: string; label: string; pct: number | null; per: number | null; usd: number | null; note: string }

function rateColumns(period: string, withWindow: boolean): Column<RateRow>[] {
  const cols: Column<RateRow>[] = [
    { id: "what", header: "Rate", label: "Rate", fixed: true, cell: (row) => row.label },
    {
      id: "year", header: "Of the position a year", label: "Of the position a year", numeric: true,
      cell: (row) => <Figure value={row.pct === null ? "" : fmtPct(row.pct, 1)} reason={row.note} />,
    },
  ];
  if (withWindow) {
    cols.push({
      id: "window", header: `Per ${period}`, label: `Per ${period}`, numeric: true,
      cell: (row) => <Figure value={row.per === null ? "" : fmtPct(row.per, 1)} reason={row.note} />,
    });
  }
  cols.push({
    id: "usd", header: "A year, in dollars", label: "A year, in dollars", numeric: true,
    cell: (row) => <Figure value={row.usd === null ? "" : fmtMoneyCompact(row.usd)} reason={row.note} />,
  });
  return cols;
}

/* ------------------------------------------------------------ the panel */
export default function LiquidityView() {
  const r = useRoute();
  const key = decodeURIComponent(r.segments[1] || "");
  const { value: index, error: indexError, loading: indexLoading } = useIndex();
  const [plan] = usePlan(index);
  const { value, error, loading } = useAsync<LiquidityShape>(
    () => data().getLiquidity(plan, key), [plan, key]);
  const match = (value?.match || null) as Match | null;

  /* the record’s own positions, and the travel around them */
  const defaults = useMemo<Inputs>(() => {
    const sc = match?.scenario || {};
    const pi = match?.plan_inputs || {};
    const num = (v: unknown, fallback: number) => (typeof v === "number" && Number.isFinite(v) ? v : fallback);
    return {
      allocation: num(sc.allocation_pct_of_plan, 0),
      outflow: num(sc.filed_outflow_proxy_pct, num(pi.filed_outflow_proxy_pct, 0)),
      tail: num(sc.tail_annual_turnover_pct, 0),
      active: num(sc.active_annual_turnover_pct, 0),
    };
  }, [match]);
  const travel = useMemo(() => spans(defaults), [defaults]);

  /* the one state object. The URL holds it, so a link carries the scenario
   * and Back leaves the panel rather than walking every position. */
  const [inputs, setInputs] = useState<Inputs>(() => readInputs(r.params, defaults, travel));
  const [moved, setMoved] = useState<Field | "">("");
  useEffect(() => {
    const next = readInputs(r.params, defaults, travel);
    setInputs((prev) => (sameInputs(prev, next) ? prev : next));
  }, [r.params, defaults, travel]);

  const live = useMemo(() => compute(inputs, match || {}), [inputs, match]);
  const touched = !sameInputs(inputs, defaults);

  const set = (field: Field, v: number) => {
    const next = { ...inputs, [field]: round2(v) };
    setMoved(field);
    setInputs(next);
    const patch: Record<string, string | null> = {};
    for (const f of FIELDS) {
      patch[PARAM[f]] = Math.abs(next[f] - defaults[f]) < 1e-9 ? null : String(round2(next[f]));
    }
    setParams(patch);
  };
  const reset = () => {
    setMoved("");
    setInputs(defaults);
    const patch: Record<string, string | null> = {};
    for (const f of FIELDS) patch[PARAM[f]] = null;
    setParams(patch);
  };

  if (error || indexError) return <EmptyState title={SAY.noRecord}>{error || indexError}</EmptyState>;
  if (loading || indexLoading || !value || !index) return <Skeleton lines={10} label={SAY.loadingRecord} />;

  const product = index.products.find((p) => p.key === key) || null;
  if (!match || !product) {
    return (
      <EmptyState title={SAY.noRecord}>
        No liquidity reading is on record for this fund and this plan. One appears once the wrapper’s
        dealing terms and the plan’s filed outflow are both on record.
      </EmptyState>
    );
  }
  const fundName = product.fund_name;
  const wf = match.wrapper_facts || {};
  const sc = match.scenario || {};
  const pi = match.plan_inputs || {};
  const fo = match.filed_outflow || {};
  const drivers = sc.drivers || {};
  const period = drivers.window?.period || drivers.binding_cap?.period || wf.cap_period || "window";
  const structural = reading(match.verdict);
  const scenario = reading(match.scenario_verdict);
  const missing = match.missing_facts_labels || [];
  const gateUnknown = (match.missing_facts || []).includes("gate_history");
  const sentence = touched ? recomputed(live, period) : datesInWords(drivers.sentence);
  const outflowLabel = sentenceCase(fo.label || "filed outflow rate");

  const cells = (match.citations || []).filter((c) => /^\d+(\.\d+)?$/.test(c));
  const notes = (match.citations || []).filter((c) => !/^\d+(\.\d+)?$/.test(c));

  const rows: RateRow[] = [
    {
      id: "filed", label: `At the ${fo.label || "filed outflow rate"}`,
      pct: live.filedPct, per: live.filedPerWindow, usd: live.filedUsd, note: "Not on record",
    },
    {
      id: "turnover", label: "At the turnover assumption",
      pct: live.turnoverPct, per: live.turnoverPerWindow, usd: live.turnoverUsd, note: "Not on record",
    },
    {
      id: "stressed", label: "Under the stress multiples",
      pct: live.stressedPct, per: live.stressedPerWindow, usd: live.stressedUsd, note: "Not on record",
    },
    {
      id: "capacity", label: "What the wrapper can absorb",
      pct: live.capacityPct, per: live.capPerWindowPct, usd: live.capacityUsd,
      note: wf.caps_label || "Not on record",
    },
  ];

  const fundCapacity = sc.fund_capacity || {};
  const fundReason = wf.exchange
    ? "An exchange-listed wrapper has no fund-level capacity to share. Exit is at the market price."
    : live.capacityPct === 0
      ? "The wrapper absorbs nothing while repurchases are suspended, so a share of it is undefined."
      : "The fund’s aggregate net assets are not on record, so this position cannot be set against the fund’s own capacity.";

  return (
    <div className="stack-5">
      <section className="stack-4" aria-labelledby="lq-verdicts">
        <h2 id="lq-verdicts" className="t-20">The two readings</h2>
        <div className="grid-2">
          <Card as="article" className="stack-4">
            <CardHead title="The dealing terms" level={3}>
              <Chip kind="wrapper">Holds for every plan</Chip>
            </CardHead>
            <VerdictBanner kind={structural.kind} label={structural.label} definition={structural.definition}
              legendTo="/design"
              chip={structural.qualifier ? <Chip kind="neutral">{structural.qualifier}</Chip> : undefined} />
            <dl className="field-list">
              <dt>Dealing</dt>
              <dd>{datesInWords(wf.dealing_label) || "Not on record"}</dd>
              <dt>Caps</dt>
              <dd>{wf.caps_label || "Not on record"}</dd>
              <dt>Early repurchase fee</dt>
              <dd>{wf.early_fee || "Not on record"}</dd>
              <dt>Repurchase program</dt>
              <dd>
                {wf.program_status
                  ? `${PROGRAM_STATUS[wf.program_status] || sentenceCase(wf.program_status)}${wf.program_status_as_of ? `, as of ${fmtDate(wf.program_status_as_of)}` : ""}`
                  : wf.exchange ? "No repurchase program. Shares are sold on the exchange." : "Not on record"}
              </dd>
              <dt>Buyback limits used</dt>
              <dd>{gateUnknown ? "Not on record" : wf.gate_history ? "Used at least once" : "None identified"}</dd>
            </dl>
            {(match.structural_reasons || []).length > 0 && (
              <Disclosure summary="The reading behind this" id="lq-structural">
                <dl className="field-list">
                  {(match.structural_reasons || []).map((why, i) => {
                    const at = why.indexOf(": ");
                    const head = at > 0 && at <= 48 ? why.slice(0, at) : "On the dealing terms";
                    const body = at > 0 && at <= 48 ? why.slice(at + 2) : why;
                    return (
                      <Fragment key={i}>
                        <dt>{sentenceCase(head)}</dt>
                        <dd>{datesInWords(body)}</dd>
                      </Fragment>
                    );
                  })}
                </dl>
              </Disclosure>
            )}
          </Card>

          <Card as="article" className="stack-4">
            <CardHead title="This plan against those terms" level={3}>
              <Chip kind="illustrative">{SAY.illustrative}</Chip>
            </CardHead>
            <VerdictBanner kind={scenario.kind} label={scenario.label} definition={scenario.definition}
              legendTo="/design" chip={<Chip kind="illustrative">{SAY.illustrative}</Chip>} />
            <p className="t-13 t-3">{SAY.illustrativeNote} {SAY.planDependent}</p>
            <dl className="field-list">
              <dt>Plan</dt>
              <dd>{match.plan_display_label || "Not on record"}</dd>
              <dt>Who directs the accounts</dt>
              <dd>{DIRECTION[String(match.plan_direction || "")] || "Not on record"}</dd>
              <dt>Plan year</dt>
              <dd>{datesInWords(pi.plan_year) || "Not on record"}</dd>
            </dl>
            <p className="t-12 t-3">{SAY.anonymized}</p>
          </Card>
        </div>
      </section>

      <section className="stack-4" aria-labelledby="lq-filed">
        <h2 id="lq-filed" className="t-20">What the plan filed</h2>
        <StatRow>
          <Stat label="Plan net assets" value={fmtMoneyCompact(pi.net_assets)}
            source={fo.plan_year ? `Plan year ${datesInWords(fo.plan_year)}` : "From the plan record"} />
          <Stat label={outflowLabel} value={fmtPct(fo.rate_pct ?? pi.filed_outflow_proxy_pct, 1)}
            source={fo.what || "From the plan record"} />
          <Stat label="Separated participants with balances" value={fmtInt(pi.separated_with_balances)}
            source="The accounts nearest the exit" />
          <Stat label="Their share of all accounts" value={fmtPct(pi.tail_share_pct, 1)}
            source="Weights the turnover assumption" />
        </StatRow>
      </section>

      <section className="stack-4" aria-labelledby="lq-scenario">
        <h2 id="lq-scenario" className="t-20">The scenario you set</h2>

        <Card className="stack-4">
          <CardHead title="The positions" level={3}>
            <Chip kind="illustrative">{SAY.illustrative}</Chip>
          </CardHead>
          <div className="grid-2">
            <Slider id="lq-alloc" label="Share of the plan held in this fund" value={inputs.allocation}
              min={travel.allocation.min} max={travel.allocation.max} step={travel.allocation.step}
              format={(v) => fmtPct(v, 1)} onChange={(v) => set("allocation", v)}
              hint={`The record sets this at ${fmtPct(defaults.allocation, 1)}`}
              liveText={moved === "allocation" ? sentence : undefined} />
            <Slider id="lq-outflow" label={`${outflowLabel}, a year`} value={inputs.outflow}
              min={travel.outflow.min} max={travel.outflow.max} step={travel.outflow.step}
              format={(v) => fmtPct(v, 2)} onChange={(v) => set("outflow", v)}
              hint={`The plan filed ${fmtPct(defaults.outflow, 2)}`}
              liveText={moved === "outflow" ? sentence : undefined} />
            <Slider id="lq-tail" label="Yearly turnover of separated accounts" value={inputs.tail}
              min={travel.tail.min} max={travel.tail.max} step={travel.tail.step}
              format={(v) => fmtPct(v, 1)} onChange={(v) => set("tail", v)}
              hint={`On ${fmtPct(pi.tail_share_pct, 1)} of the accounts`}
              liveText={moved === "tail" ? sentence : undefined} />
            <Slider id="lq-active" label="Yearly turnover of the rest" value={inputs.active}
              min={travel.active.min} max={travel.active.max} step={travel.active.step}
              format={(v) => fmtPct(v, 1)} onChange={(v) => set("active", v)}
              hint={`The record sets this at ${fmtPct(defaults.active, 1)}`}
              liveText={moved === "active" ? sentence : undefined} />
          </div>
          <div className="row-3">
            <Button variant="secondary" icon="arrowLeft" onClick={reset} disabled={!touched}>
              Return to the record’s positions
            </Button>
            <span className="t-12 t-3">{SAY.illustrativeNote}</span>
          </div>
        </Card>

        <Card className="stack-4">
          <CardHead title="What those positions produce" level={3} />
          <div className="stack-2" aria-live="polite">
            <p className="t-12 t-3">
              {touched
                ? "Recomputed from the positions above."
                : "The record’s own sentence, at the record’s own positions."}
            </p>
            <p className="t-14 t-pretty">{sentence}</p>
            {!touched && match.stressed_scenario?.outcome && (
              <p className="t-13 t-2 t-pretty">{sentenceCase(datesInWords(match.stressed_scenario.outcome))}</p>
            )}
          </div>

          <StatRow>
            <Stat label="The plan’s position in this fund"
              value={live.positionUsd === null
                ? <NoFigure reason="The plan’s net assets are not on record" />
                : fmtMoneyCompact(live.positionUsd)}
              source={`${fmtPct(inputs.allocation, 1)} of ${fmtMoneyCompact(pi.net_assets)}`} />
            <Stat label="Asked for at the outflow rate" value={fmtPct(live.filedPct, 1)}
              source={live.filedUsd === null ? "Of the position a year" : `${fmtMoneyCompact(live.filedUsd)} a year`} />
            <Stat label="Asked for under the stress multiples" value={fmtPct(live.stressedPct, 1)}
              source={live.stressedUsd === null ? "Of the position a year" : `${fmtMoneyCompact(live.stressedUsd)} a year`} />
            <Stat label="Headroom under the stress"
              value={live.headroomPct === null
                ? <NoFigure reason={wf.caps_label || "No yearly capacity on record"}
                  target={wf.net_assets_cell ? { productKey: key, fundName, cell: wf.net_assets_cell } : undefined} />
                : fmtPct(live.headroomPct, 1)}
              source="Yearly capacity less the stressed demand" />
          </StatRow>

          <BarChart
            title="A year of demand against what the wrapper can absorb"
            description="The plan’s yearly demand at the outflow rate, at the turnover assumption and under the stress multiples, each as a share of the position, beside the wrapper’s yearly capacity."
            bars={[
              { label: "At the outflow rate", value: live.filedPct, color: "var(--chart-1)" },
              { label: "At the turnover assumption", value: live.turnoverPct, color: "var(--chart-2)" },
              { label: "Under the stress multiples", value: live.stressedPct, color: "var(--chart-3)" },
              {
                label: "What the wrapper absorbs", value: live.capacityPct, color: "var(--chart-4)",
                note: wf.caps_label || "Not on record",
              },
            ]}
            format={(v) => fmtPct(v, 1)}
            footer={sentenceCase(datesInWords(sc.capacity_note))} />

          <Table
            id="lq-rates"
            caption={`Every figure at the positions set above. ${SAY.illustrativeNote}`}
            columns={rateColumns(period, live.capPerWindowPct !== null && !!live.windows)}
            rows={rows}
            rowKey={(row) => row.id}
            empty={SAY.noRecord} />

          <StatRow>
            <Stat label={`The binding cap, each ${period}`}
              value={live.capPerWindowPct === null
                ? <NoFigure reason={wf.caps_label || "No cap on record"} />
                : fmtPct(live.capPerWindowPct, 1)}
              source={`${live.windows ? withUnit(fmtInt(live.windows), "offers a year") : "Dealing on the exchange"}${wf.cap_base && wf.cap_base !== "not on record" ? `, on ${wf.cap_base}` : ""}`} />
            <Stat label="This position, of the fund’s yearly capacity"
              value={live.fundSharePct === null
                ? <NoFigure reason={fundReason}
                  target={fundCapacity.net_assets_cell
                    ? { productKey: key, fundName, cell: fundCapacity.net_assets_cell } : undefined} />
                : fmtPct(live.fundSharePct, 2)}
              source={typeof fundCapacity.annual_capacity_usd === "number"
                ? `${fmtMoneyCompact(fundCapacity.annual_capacity_usd)} a year across every holder`
                : "Shared with every other holder"} />
          </StatRow>
        </Card>
      </section>

      <section className="stack-4" aria-labelledby="lq-how">
        <h2 id="lq-how" className="t-20">How this is computed</h2>
        <Card>
          <Disclosure summary="The formula, the filed inputs and the two layers" id="lq-how-open">
            <div className="stack-4">
              <dl className="field-list">
                <dt>{outflowLabel}</dt>
                <dd>{fo.formula || "Not on record"}</dd>
                <dt>What it measures</dt>
                <dd>{fo.what || "Not on record"}</dd>
                <dt>Read from</dt>
                <dd>{datesInWords(fo.source) || "Not on record"}</dd>
                {Object.entries(fo.inputs || {})
                  .filter(([name]) => INPUT_LABEL[name])
                  .map(([name, amount]) => (
                    <Fragment key={name}>
                      <dt>{INPUT_LABEL[name]}</dt>
                      <dd>{fmtMoney(amount)}</dd>
                    </Fragment>
                  ))}
              </dl>
              <dl className="field-list">
                <dt>The position</dt>
                <dd>share of the plan * plan net assets</dd>
                <dt>Demand a year</dt>
                <dd>rate * the position</dd>
                <dt>Turnover assumption</dt>
                <dd>{`separated turnover * ${fmtPct(pi.tail_share_pct, 1)} + the turnover of the rest * the remaining share`}</dd>
                <dt>Stressed demand</dt>
                <dd>{`the ${fo.label || "filed outflow rate"} + (separated turnover * ${fmtNum(match.stressed_scenario?.multiples?.tail_multiple, 1)} + the turnover of the rest * ${fmtNum(match.stressed_scenario?.multiples?.active_multiple, 1)}, weighted the same way) less the turnover assumption`}</dd>
                {!!live.windows && (
                  <>
                    <dt>Per {period}</dt>
                    <dd>{`the yearly rate / ${fmtInt(live.windows)} offers a year`}</dd>
                  </>
                )}
                {!!live.windows && live.capPerWindowPct !== null && (
                  <>
                    <dt>What the wrapper absorbs</dt>
                    <dd>{`the cap each ${period} * ${fmtInt(live.windows)} offers a year`}</dd>
                  </>
                )}
              </dl>
              <p className="t-13 t-2 t-pretty">{datesInWords(match.layers)}</p>
              {(sc.schedule_h_lines || []).map((line, i) => (
                <p key={i} className="t-13 t-2 t-pretty">{datesInWords(line)}</p>
              ))}
              {/* The record's own sentences, unedited. The document for this
                  plan and this fund prints these words, and a committee
                  reading the document beside the screen has to be able to
                  match them line for line. Everything above is the same
                  figures arranged for reading. */}
              {(match.scenario_reasons || []).length > 0 && (
                <div className="stack-2">
                  <h3 className="t-14 t-semibold">
                    {touched ? "As the record states it, at the filed inputs" : "As the record states it"}
                  </h3>
                  {touched && (
                    <p className="t-13 t-3">
                      You have moved an input, so the figures above are yours. These sentences are the
                      record's, at the filed inputs, and they are what the document for this plan carries.
                    </p>
                  )}
                  <ul className="field-list">
                    {(match.scenario_reasons || []).map((line, i) => (
                      <li key={i} className="t-13 t-2 t-pretty">{line}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </Disclosure>
        </Card>
      </section>

      <section className="stack-4" aria-labelledby="lq-missing">
        <h2 id="lq-missing" className="t-20">What is not on the filings yet</h2>
        <Card className="stack-2">
          {missing.length > 0 ? (
            <>
              <div className="row-3">
                {missing.map((label) => <Chip key={label} kind="pending">{sentenceCase(label)}</Chip>)}
              </div>
              <p className="t-13 t-2">
                The reading of the dealing terms stays partial until these are read from the filings.
              </p>
            </>
          ) : (
            <p className="t-13 t-2">
              Every fact these two readings need is on record for this fund. Nothing here is waiting on a filing.
            </p>
          )}
        </Card>
      </section>

      <section className="stack-4" aria-labelledby="lq-sources">
        <h2 id="lq-sources" className="t-20">Where these figures come from</h2>
        <Card sunken className="stack-2">
          <div className="row-3">
            {cells.map((cell) => (
              <CiteButton key={cell} target={{ productKey: key, fundName, cell }}
                label={`Open ${index.cells[cell]?.label || "the row"}`} />
            ))}
          </div>
          {notes.map((note, i) => (
            <p key={i} className="t-13 t-3 provenance">{sentenceCase(datesInWords(note))}</p>
          ))}
          <p className="t-13 t-3">
            {SAY.verificationCount(index.coverage_totals.counts.verified, index.coverage_totals.counts.total)}{" "}
            <Link to="/verification">See the verification queue</Link>
          </p>
        </Card>
      </section>
    </div>
  );
}

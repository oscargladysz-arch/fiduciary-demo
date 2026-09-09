/* Compare. Two to four funds beside each other on the rows the record holds,
 * with the difference test written down rather than left to the eye.
 *
 * The picker is a real group of checkboxes, so every fund is reachable by
 * keyboard and the group is announced as one. A fifth pick is refused in a
 * sentence rather than swallowed, and the selection rides in the address as
 * keys, so one reader can hand a comparison to another.
 *
 * One chip per cell: the tier the row sits in. The filing behind a figure
 * opens from the citation button beside it, never from a second chip. A cell
 * the record does not hold prints the reason the record gives.
 */
import { useId, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { setParams, useRoute } from "../app/router";
import { BarChart } from "../charts/charts";
import { CiteButton } from "../components/citation";
import { Checkbox } from "../components/form";
import { Card, CardHead, Chip, EmptyState, Legend, Link, Skeleton, Stat, StatRow } from "../components/primitives";
import { PageHeader } from "../components/shell";
import { Table } from "../components/table";
import type { Column } from "../components/table";
import { SAY, TIERS, status as statusCopy, verdict as verdictCopy } from "../copy/copy";
import { useAsync, useIndex, useKeys } from "../data/hooks";
import { data } from "../data/index";
import { fmtInt, fmtMoneyCompact, fmtNum, fmtOf, fmtPct, truncate, withUnit } from "../format/format";
import type { IndexView, ScreenerView as ScreenerShape } from "../data/types";

const MOST = 4;
const LEAST = 2;

interface Fact { value?: unknown; status?: string; source_cell?: string; note?: string; reason?: string; basis?: string }
interface Fund { key: string; name: string; facts: Record<string, Fact>; cited: Set<string> }

type Kind = "number" | "category";
interface FactRow {
  id: string;
  label: string;
  kind: Kind;
  /** which row of the record this line reads for this fund */
  at: (fund: Fund) => string;
  /** the value in reader words, called only where the record holds one */
  show: (f: Fact) => ReactNode;
  /** what the difference test reads, null where the record holds nothing */
  keyOf: (f: Fact) => number | string | null;
  /** the basis the fund states for the figure, printed beside it */
  basis?: (f: Fact) => string | undefined;
}

const NO_LABEL = "Not named in plain words on this record";

/* Dealing cadence and the two liquidity verdicts the copy layer does not
 * carry, said in plain words rather than in the name the record files them
 * under. */
const CADENCE: Record<string, string> = {
  daily: "Daily",
  monthly: "Monthly",
  quarterly: "Quarterly",
  exchange: "Traded on an exchange",
};
const EXTRA_VERDICT: Record<string, string> = {
  "aligned-mechanical": "Aligned, exit is on an exchange",
  partial: "Partly on record",
};

function factOf(fund: Fund, name: string): Fact {
  return fund.facts[name] || {};
}
function same(name: string) {
  return () => name;
}
function text(map: Record<string, string>, v: unknown): string {
  return map[String(v ?? "")] || NO_LABEL;
}
function verdictText(v: unknown): string {
  const raw = String(v ?? "");
  if (EXTRA_VERDICT[raw]) return EXTRA_VERDICT[raw];
  return verdictCopy(raw).label;
}
function num(f: Fact): number | null {
  return typeof f.value === "number" ? f.value : null;
}
function str(f: Fact): string | null {
  return f.value === null || f.value === undefined ? null : String(f.value);
}

/* Print only the fields the fee carries: a fee whose rate is not disclosed
 * says so rather than printing an empty percent. */
interface Incentive { present?: boolean; rate_pct?: number | null; hurdle_pct?: number | null }
function incentive(v: Incentive | null): string {
  if (!v) return "Not on record";
  if (!v.present) return "None";
  const parts: string[] = [];
  if (v.rate_pct !== null && v.rate_pct !== undefined) parts.push(fmtPct(v.rate_pct));
  if (v.hurdle_pct !== null && v.hurdle_pct !== undefined) parts.push(`${fmtPct(v.hurdle_pct)} hurdle`);
  return parts.length ? parts.join(", ") : "Charged, rate not disclosed";
}
interface Early { present?: boolean; rate_pct?: number | null; window?: string }
function early(v: Early | null): string {
  if (!v) return "Not on record";
  if (!v.present) return "None";
  const rate = v.rate_pct !== null && v.rate_pct !== undefined ? fmtPct(v.rate_pct) : "Charged, rate not disclosed";
  return v.window ? `${rate}, ${v.window}` : rate;
}

/* ------------------------------------------------------------- the rows */
function linesOf(index: IndexView): FactRow[] {
  const wrapper = index.labels.wrapper;
  const base = index.labels.base;
  const max = index.rubric.max;
  return [
    {
      id: "wrapper", label: "Wrapper", kind: "category", at: same("wrapper_type"),
      show: (f) => text(wrapper, f.value), keyOf: str,
    },
    {
      id: "fee", label: "Management fee", kind: "number", at: same("mgmt_fee_pct"),
      show: (f) => fmtPct(f.value as number), keyOf: num,
    },
    {
      id: "base", label: "Fee base", kind: "category", at: same("mgmt_fee_base"),
      show: (f) => text(base, f.value), keyOf: str,
    },
    {
      id: "incentive", label: "Incentive fee", kind: "category", at: same("incentive_fee"),
      show: (f) => incentive(f.value as Incentive),
      keyOf: (f) => {
        const v = f.value as Incentive | null;
        if (!v) return null;
        return `${v.present ? "on" : "off"}/${v.rate_pct ?? ""}/${v.hurdle_pct ?? ""}`;
      },
    },
    {
      id: "ter", label: "Expense ratio", kind: "number", at: same("expense_ratio_pct"),
      show: (f) => fmtPct(f.value as number), keyOf: num,
      basis: (f) => (typeof f.basis === "string" && f.basis ? f.basis : undefined),
    },
    {
      id: "early", label: "Early repurchase fee", kind: "category", at: same("early_repurchase"),
      show: (f) => early(f.value as Early),
      keyOf: (f) => {
        const v = f.value as Early | null;
        if (!v) return null;
        return `${v.present ? "on" : "off"}/${v.rate_pct ?? ""}/${v.window ?? ""}`;
      },
    },
    {
      id: "dealing", label: "Dealing", kind: "category",
      // a suspended buyback program is the dealing fact for that fund, and
      // its own row is the one a reader should open
      at: (fund) => (factOf(fund, "repurchase_program_status").value === "suspended"
        ? "repurchase_program_status" : "dealing_cadence"),
      show: (f) => (f.value === "suspended" ? "Buyback program suspended" : text(CADENCE, f.value)),
      keyOf: str,
    },
    {
      id: "cap", label: "Cap per window", kind: "number", at: same("repurchase_cap_pct"),
      show: (f) => withUnit(fmtNum(f.value as number, 2), "%"), keyOf: num,
    },
    {
      id: "gate", label: "Buyback limits used", kind: "category", at: same("gate_history"),
      show: (f) => (f.value === true ? "Used at least once" : "None identified"), keyOf: str,
    },
    {
      id: "tax", label: "Tax form", kind: "category", at: same("tax_form"),
      show: (f) => String(f.value), keyOf: str,
    },
    {
      id: "big4", label: "Auditor among the four largest", kind: "category", at: same("big4"),
      show: (f) => (f.value === true ? "Yes" : "No"), keyOf: str,
    },
    {
      id: "track", label: "Track record", kind: "number", at: same("track_record_years"),
      show: (f) => withUnit(fmtNum(f.value as number, 1), "years"), keyOf: num,
    },
    {
      id: "aum", label: "Net assets", kind: "number", at: same("net_assets_usd"),
      show: (f) => fmtMoneyCompact(f.value as number), keyOf: num,
    },
    {
      id: "score", label: "Benchmark selection score", kind: "number", at: same("selection_score"),
      show: (f) => fmtOf(f.value as number, max), keyOf: num,
    },
    {
      id: "verdict", label: "Liquidity, structural", kind: "category",
      at: same("liquidity_structural_verdict"),
      show: (f) => verdictText(f.value), keyOf: str,
    },
  ];
}

const FEE_LINES = ["fee", "base", "incentive", "ter", "early"];

/** More than a tenth of the highest apart, or not all the same. */
function differs(line: FactRow, sel: Fund[]): boolean {
  const vals = sel
    .map((fund) => line.keyOf(factOf(fund, line.at(fund))))
    .filter((v): v is number | string => v !== null && v !== undefined);
  if (vals.length < LEAST) return false;
  if (line.kind === "number") {
    const nums = vals.filter((v): v is number => typeof v === "number");
    if (nums.length < LEAST) return false;
    const hi = Math.max(...nums), lo = Math.min(...nums);
    const span = Math.abs(hi);
    if (span === 0) return hi !== lo;
    return hi - lo > span / 10;
  }
  return new Set(vals.map((v) => String(v))).size > 1;
}

/* ------------------------------------------------------------- one cell */
/* The value, the basis where the fund states one, the tier of the row and
 * the filing it was read from. One chip, one citation. */
function Value({ fund, line }: { fund: Fund; line: FactRow }) {
  const name = line.at(fund);
  const f = factOf(fund, name);
  const st = statusCopy(f.status);
  const cell = f.source_cell || "";
  const target = cell && fund.cited.has(cell) ? { productKey: fund.key, fundName: fund.name, cell } : null;
  const missing = f.value === null || f.value === undefined;
  const basis = missing ? undefined : line.basis?.(f);
  return (
    <div className="stack-2">
      <span className={missing ? "t-13 t-3" : line.kind === "number" ? "t-num" : "t-14"}>
        {missing ? (f.reason || "Not on record") : line.show(f)}
      </span>
      {basis && <span className="t-12 t-3">Basis: {basis}</span>}
      <span className="row-3">
        <Chip kind={st.kind}>{st.label}</Chip>
        {target && <CiteButton target={target} compact />}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------- the view */
export default function CompareView() {
  const r = useRoute();
  const gid = useId();
  const [refusal, setRefusal] = useState("");
  const { value: index, error: iErr, loading: iLoading } = useIndex();
  const { value: screener, error, loading } = useAsync<ScreenerShape>(() => data().getScreener(), []);
  const keys = useKeys(index);

  const funds = useMemo<Fund[]>(() => {
    if (!index || !screener) return [];
    return index.products
      .filter((p) => screener.products[p.key])
      .map((p) => {
        const s = screener.products[p.key];
        return {
          key: p.key,
          name: s.fund_name || p.fund_name,
          facts: (s.facts || {}) as Record<string, Fact>,
          cited: new Set(s.cited || []),
        };
      });
  }, [index, screener]);

  const order = useMemo(() => funds.map((f) => f.key), [funds]);
  const asked = r.params.get("compare") || "";

  /* the address holds keys only, deduplicated, in roster order, and names the
   * first two funds when it names none */
  const chosen = useMemo(() => {
    const want = new Set(asked.split(".").map((s) => s.trim()).filter((k) => keys.products.has(k)));
    const inOrder = order.filter((k) => want.has(k)).slice(0, MOST);
    if (inOrder.length) return inOrder;
    return asked ? [] : order.slice(0, LEAST);
  }, [asked, order, keys]);

  const sel = useMemo(
    () => chosen.map((k) => funds.find((f) => f.key === k)).filter((f): f is Fund => !!f),
    [chosen, funds],
  );

  const lines = useMemo(() => (index ? linesOf(index) : []), [index]);
  const marked = useMemo(() => {
    const out = new Set<string>();
    for (const line of lines) if (differs(line, sel)) out.add(line.id);
    return out;
  }, [lines, sel]);

  const columns = useMemo<Column<FactRow>[]>(() => [
    {
      id: "line", header: "Row of the record", label: "Row of the record", fixed: true,
      cell: (line) => (
        <div className="stack-2">
          <span className="t-14 t-medium">{line.label}</span>
          {marked.has(line.id) && <Chip kind="accent">Differs</Chip>}
        </div>
      ),
    },
    ...sel.map((fund) => ({
      id: fund.key,
      header: <Link to={`/product/${fund.key}/record`} translate="no">{fund.name}</Link>,
      label: fund.name,
      cell: (line: FactRow) => <Value fund={fund} line={line} />,
    })),
  ], [sel, marked]);

  const apply = (next: string[]) => {
    setRefusal("");
    setParams({ compare: order.filter((k) => next.includes(k)).join(".") });
  };
  const toggle = (fund: Fund, on: boolean) => {
    if (on) {
      if (chosen.length >= MOST) {
        setRefusal(`Four funds is the most this comparison holds and two is the least. `
          + `Clear one before you add ${fund.name}.`);
        return;
      }
      apply([...chosen, fund.key]);
      return;
    }
    if (chosen.length <= 1) {
      setRefusal("One fund stays chosen. Pick a second one, because a comparison needs two.");
      return;
    }
    apply(chosen.filter((k) => k !== fund.key));
  };

  if (error || iErr) return <EmptyState title={SAY.noRecord}>{error || iErr}</EmptyState>;
  if (loading || iLoading || !screener || !index) return <Skeleton lines={10} label={SAY.loadingRecord} />;

  const signed = index.coverage_totals.counts.verified;
  const total = Number(index.coverage_totals.total);
  const feeLines = lines.filter((l) => FEE_LINES.includes(l.id));
  const enough = sel.length >= LEAST;

  if (funds.length === 0) {
    return (
      <div className="stack-5">
        <PageHeader title="Compare" />
        <EmptyState title="No fund is on the comparison yet">
          The roster carries no evaluated fund. A fund appears here once its record holds the rows
          this comparison reads.
        </EmptyState>
      </div>
    );
  }

  return (
    <div className="stack-5">
      <PageHeader
        title="Compare"
        sub={"Two to four funds on the same rows of the record. Every figure opens the filing it was read from, "
          + "and a row the record does not hold says why."}
        actions={<Link to="/screener">Open the screener</Link>}
      />

      <StatRow>
        <Stat label="Funds side by side" value={fmtInt(sel.length)} source={`Of ${fmtInt(funds.length)} evaluated`} />
        <Stat label="Rows that differ" value={fmtOf(marked.size, lines.length)}
          source="On the test below, across the funds you chose" />
        <Stat label="Signed by a person" value={fmtInt(signed)} source={SAY.verificationPending} />
      </StatRow>

      <section className="stack-4" aria-labelledby={`${gid}-pick`}>
        <h2 id={`${gid}-pick`} className="t-20">Choose the funds</h2>
        <Card className="stack-2">
          <div className="field__label" id={`${gid}-group`}>Funds on the comparison</div>
          <div className="field__hint" id={`${gid}-hint`}>
            Two funds at the least and four at the most. Clear one to make room for another.
          </div>
          <div className="grid-3" role="group" aria-labelledby={`${gid}-group`} aria-describedby={`${gid}-hint`}>
            {funds.map((fund) => (
              <Checkbox key={fund.key} label={fund.name} checked={chosen.includes(fund.key)}
                onChange={(e) => toggle(fund, e.target.checked)} />
            ))}
          </div>
          <p className="t-13 t-3" aria-live="polite">
            {refusal || `${fmtInt(sel.length)} of ${fmtInt(funds.length)} funds chosen.`}
          </p>
        </Card>
      </section>

      <section className="stack-4" aria-labelledby={`${gid}-side`}>
        <h2 id={`${gid}-side`} className="t-20">Side by side</h2>
        {!enough ? (
          <EmptyState title="Choose a second fund">
            A comparison needs two funds. Choose one more above and the rows fill in with what the
            record holds for each of them.
          </EmptyState>
        ) : (
          <>
            <p className="t-13 t-3">
              A row is marked Differs where the funds are materially apart. For a figure that means the
              highest and the lowest are more than a tenth of the highest apart. For a category it means
              the values are not all the same. A row where fewer than two of the chosen funds carry a
              value is left unmarked.
            </p>
            <p className="t-13 t-3" aria-live="polite">
              Marked as differing: {fmtOf(marked.size, lines.length)} rows, across the{" "}
              {fmtInt(sel.length)} funds you chose.
            </p>
            <Table
              id="compare"
              caption={`The rows the record holds for the funds you chose. ${SAY.verificationPending}`}
              columns={columns}
              rows={lines}
              rowKey={(line) => line.id}
              empty={SAY.emptyFilter}
            />
          </>
        )}
      </section>

      {enough && (
        <section className="stack-4" aria-labelledby={`${gid}-fees`}>
          <h2 id={`${gid}-fees`} className="t-20">Fees</h2>
          <Card className="stack-2">
            <CardHead title="Expense ratio, as each fund states it" level={3} />
            <BarChart
              title="Expense ratio by fund"
              description={"One bar per chosen fund. A fund with no comparable expense line carries the reason "
                + "the record gives instead of a bar."}
              bars={sel.map((fund) => {
                const f = factOf(fund, "expense_ratio_pct");
                const v = typeof f.value === "number" ? f.value : null;
                return {
                  label: fund.name, value: v,
                  note: v === null ? truncate(f.reason || "Not on record", 44) : undefined,
                };
              })}
              format={(v) => fmtPct(v)}
              footer={"Each ratio is read on the basis its own fund states, and those bases are not the same. "
                + "The basis sits beside every figure in the rows below, and the full reason sits there too "
                + "where a fund has no comparable line."}
            />
          </Card>
          <Table
            id="compare-fees"
            caption={`The fee rows for the funds you chose, each figure with the basis its fund states. ${SAY.verificationPending}`}
            columns={columns}
            rows={feeLines}
            rowKey={(line) => line.id}
            empty={SAY.emptyFilter}
          />
        </section>
      )}

      <Card sunken className="stack-2">
        <CardHead title="How to read this comparison" level={2} />
        <Legend label="Tiers" items={TIERS.map((t, i) => ({
          label: t.label, kind: (["structured", "extracted", "verified"] as const)[i],
        }))} />
        <p className="t-13 t-3">
          Every cell carries the tier of the row behind it, and the button beside it opens the filing the
          figure was read from. Where a public series stands beside a fund it is labeled {SAY.reference}.{" "}
          {SAY.referenceNote} The meaningful benchmark for each fund sits on its own benchmark panel.{" "}
          {SAY.verificationCount(signed, total)}
        </p>
      </Card>
    </div>
  );
}

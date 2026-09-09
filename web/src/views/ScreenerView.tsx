/* Screener. Sixteen funds on nineteen typed facts, each figure with the row
 * it was read from one click away.
 *
 * Every column reads a typed fact, so a value here and the same value on the
 * record cannot disagree. A fact with no value prints the reason the record
 * gives, never a bare dash. The citation button is on the first paint,
 * because the chunk carries which cells have a source before any drawer text
 * is fetched (rule 20).
 *
 * Filter, sort and column state serialize into the URL and replace the
 * history entry rather than pushing one, so Back leaves the Screener rather
 * than walking its filters, and they are scoped to this route: no other
 * route’s link carries them. */
import { useMemo } from "react";
import { setParams, useRoute } from "../app/router";
import { CiteButton } from "../components/citation";
import { Field, Select } from "../components/form";
import { Card, Chip, EmptyState, Legend, Link, Skeleton, Stat, StatRow } from "../components/primitives";
import { PageHeader } from "../components/shell";
import { Table } from "../components/table";
import type { Column, SortState } from "../components/table";
import { SAY, TIERS, status as statusCopy, verdict as verdictCopy } from "../copy/copy";
import { useAsync, useIndex } from "../data/hooks";
import { data } from "../data/index";
import { fmtInt, fmtMoneyCompact, fmtNum, fmtPct, fmtRatio, withUnit } from "../format/format";
import type { IndexView, ScreenerView as ScreenerShape } from "../data/types";

interface Fact { value?: unknown; status?: string; source_cell?: string; note?: string; reason?: string }
interface Row { key: string; name: string; facts: Record<string, Fact>; cited: Set<string> }

const NONE = "";  // the empty option of a filter, meaning "every value"
/** The fee preset: what a reader comparing cost looks at, and nothing else. */
const FEE_COLUMNS = ["name", "wrapper", "fee", "base", "incentive", "ter", "early", "aum"];

function fact(row: Row, name: string): Fact {
  return row.facts[name] || {};
}

/** A figure with the row it came from beside it. A missing value prints the
 *  record’s own reason. */
function Figure({ row, name, render }: { row: Row; name: string; render?: (v: never) => string }) {
  const f = fact(row, name);
  const cell = f.source_cell || "";
  const target = cell && row.cited.has(cell) ? { productKey: row.key, fundName: row.name, cell } : null;
  const missing = f.value === null || f.value === undefined;
  return (
    <span className="row-3">
      <span className={missing ? "t-13 t-3" : "t-num"}>
        {missing ? (f.reason || "Not on record") : (render ? render(f.value as never) : String(f.value))}
      </span>
      {target && <CiteButton target={target} compact />}
    </span>
  );
}

function money(v: number): string { return fmtMoneyCompact(v); }

export default function ScreenerView() {
  const r = useRoute();
  const { value: index, error: iErr, loading: iLoading } = useIndex();
  const { value: screener, error, loading } = useAsync<ScreenerShape>(() => data().getScreener(), []);

  const rows = useMemo<Row[]>(() => {
    if (!screener) return [];
    return Object.entries(screener.products).map(([key, p]) => ({
      key, name: p.fund_name,
      facts: (p.facts || {}) as Record<string, Fact>,
      cited: new Set(p.cited || []),
    }));
  }, [screener]);

  const columns = useMemo<Column<Row>[]>(() => cols(index), [index]);

  const sort: SortState | null = r.params.get("sort")
    ? { id: r.params.get("sort")!, dir: r.params.get("dir") === "desc" ? "desc" : "asc" }
    : null;
  // the fee matrix is a preset of this route rather than a view of its own
  // (R3-P1-2): it selects the fee columns and says what it is showing
  const preset = r.params.get("preset") || "";
  const visible = r.params.get("cols")
    ? r.params.get("cols")!.split(".")
    : preset === "fees" ? FEE_COLUMNS : null;
  const fWrapper = r.params.get("f_wrapper") || NONE;
  const fTax = r.params.get("f_tax") || NONE;
  const fBase = r.params.get("f_base") || NONE;
  const fGate = r.params.get("f_gate") || NONE;
  const fVerdict = r.params.get("f_verdict") || NONE;

  const shown = useMemo(() => rows.filter((row) => {
    const v = (n: string) => fact(row, n).value;
    if (fWrapper && v("wrapper_type") !== fWrapper) return false;
    if (fTax && v("tax_form") !== fTax) return false;
    if (fBase && v("mgmt_fee_base") !== fBase) return false;
    if (fGate === "yes" && v("gate_history") !== true) return false;
    if (fGate === "none" && v("gate_history") === true) return false;
    if (fVerdict && String(v("liquidity_structural_verdict") || "").replace(/-/g, "_") !== fVerdict) return false;
    return true;
  }), [rows, fWrapper, fTax, fBase, fGate, fVerdict]);

  if (error || iErr) return <EmptyState title={SAY.noRecord}>{error || iErr}</EmptyState>;
  if (loading || iLoading || !screener || !index) return <Skeleton lines={10} label={SAY.loadingRecord} />;

  const values = (name: string) => Array.from(new Set(rows
    .map((row) => fact(row, name).value)
    .filter((v) => typeof v === "string" && v))) as string[];

  const opt = (v: string, label: string) => ({ value: v, label });
  const wrapperOptions = [opt(NONE, "Every wrapper"), ...values("wrapper_type")
    .map((v) => opt(v, index.labels.wrapper[v] || v))];
  const baseOptions = [opt(NONE, "Every fee base"), ...values("mgmt_fee_base")
    .map((v) => opt(v, index.labels.base[v] || v))];
  const taxOptions = [opt(NONE, "Every tax form"), ...values("tax_form").map((v) => opt(v, v))];
  const verdictOptions = [opt(NONE, "Every verdict"),
    ...["aligned", "conditional", "conditional_weak", "misaligned"].map((v) => opt(v, verdictCopy(v).label))];

  return (
    <div className="stack-5">
      <PageHeader
        title={preset === "fees" ? "Fees" : "Screener"}
        sub={preset === "fees"
          ? ("What each fund charges, on the basis the record holds. A fee is only comparable against the base it "
            + "is charged on, so the base is beside the rate.")
          : ("Sixteen funds on the same typed facts. Every figure opens the filing it was read from, and a figure "
            + "the record does not hold says why.")}
        actions={preset === "fees"
          ? <Link to="/screener">Show every column</Link>
          : <Link to="/screener" params={{ preset: "fees" }}>Show fees only</Link>}
      />

      <StatRow>
        <Stat label="Funds" value={fmtInt(shown.length)} source={`of ${fmtInt(rows.length)} evaluated`} />
        <Stat label="Rows behind these columns" value={fmtInt(index.coverage_totals.counts.evidenced)}
          source="Each with a document, a section and a quote" />
        <Stat label="Signed by a person" value={fmtInt(index.coverage_totals.counts.verified)}
          source={SAY.verificationPending} />
      </StatRow>

      <Card>
        <div className="filterbar" role="group" aria-label="Filters">
          <Field label="Wrapper" inline>
            {(ids) => <Select ids={ids} small options={wrapperOptions} value={fWrapper}
              onChange={(e) => setParams({ f_wrapper: e.target.value })} />}
          </Field>
          <Field label="Fee base" inline>
            {(ids) => <Select ids={ids} small options={baseOptions} value={fBase}
              onChange={(e) => setParams({ f_base: e.target.value })} />}
          </Field>
          <Field label="Tax form" inline>
            {(ids) => <Select ids={ids} small options={taxOptions} value={fTax}
              onChange={(e) => setParams({ f_tax: e.target.value })} />}
          </Field>
          <Field label="Buyback limits used" inline>
            {(ids) => <Select ids={ids} small value={fGate}
              options={[opt(NONE, "Either"), opt("yes", "Used at least once"), opt("none", "None identified")]}
              onChange={(e) => setParams({ f_gate: e.target.value })} />}
          </Field>
          <Field label="Liquidity verdict" inline>
            {(ids) => <Select ids={ids} small options={verdictOptions} value={fVerdict}
              onChange={(e) => setParams({ f_verdict: e.target.value })} />}
          </Field>
        </div>
        <p className="t-13 t-3" aria-live="polite">
          Showing {fmtInt(shown.length)} of {fmtInt(rows.length)} funds.
          {(fWrapper || fBase || fTax || fGate || fVerdict) && (
            <>{" "}<Link to="/screener" replace>Clear the filters</Link></>
          )}
        </p>
      </Card>

      <Table
        id="screener"
        caption={`Sixteen evaluated funds on nineteen typed facts. ${SAY.verificationPending}`}
        columns={columns}
        rows={shown}
        rowKey={(row) => row.key}
        sort={sort}
        onSort={(s) => setParams({ sort: s?.id || null, dir: s?.dir || null })}
        visible={visible}
        onVisible={(ids) => setParams({ cols: ids ? ids.join(".") : null })}
        empty={SAY.emptyFilter}
      />

      <Card sunken>
        <Legend label="Tiers" items={TIERS.map((t, i) => ({
          label: t.label, kind: (["structured", "extracted", "verified"] as const)[i],
        }))} />
        <p className="t-13 t-3">
          {SAY.reference}. {SAY.referenceNote} The meaningful benchmark for each fund is on its{" "}
          benchmark panel. {SAY.verificationCount(index.coverage_totals.counts.verified,
            index.coverage_totals.counts.total)}
        </p>
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------- columns */
function cols(index: IndexView | null): Column<Row>[] {
  const wrapper = index?.labels.wrapper || {};
  const base = index?.labels.base || {};
  const rubricMax = index?.rubric.max ?? 0;
  const byDescriptor = index?.rubric.by_descriptor_sentence || "";

  const num = (name: string) => (row: Row) => {
    const v = fact(row, name).value;
    return typeof v === "number" ? v : null;
  };

  return [
    {
      id: "name", header: "Fund", label: "Fund", fixed: true,
      sortValue: (row) => row.name,
      cell: (row) => <Link to={`/product/${row.key}/record`} translate="no">{row.name}</Link>,
    },
    {
      id: "wrapper", header: "Wrapper", label: "Wrapper",
      sortValue: (row) => String(fact(row, "wrapper_type").value || ""),
      cell: (row) => <Figure row={row} name="wrapper_type" render={(v: string) => wrapper[v] || v} />,
    },
    {
      id: "fee", header: "Management fee", label: "Management fee", numeric: true, sortValue: num("mgmt_fee_pct"),
      cell: (row) => <Figure row={row} name="mgmt_fee_pct" render={(v: number) => fmtPct(v)} />,
    },
    {
      id: "base", header: "Fee base", label: "Fee base",
      sortValue: (row) => String(fact(row, "mgmt_fee_base").value || ""),
      cell: (row) => <Figure row={row} name="mgmt_fee_base" render={(v: string) => base[v] || v} />,
    },
    {
      id: "incentive", header: "Incentive fee", label: "Incentive fee",
      cell: (row) => <Figure row={row} name="incentive_fee" render={incentive} />,
    },
    {
      id: "ter", header: "Expense ratio", label: "Expense ratio", numeric: true, sortValue: num("expense_ratio_pct"),
      cell: (row) => <Figure row={row} name="expense_ratio_pct" render={(v: number) => fmtPct(v)} />,
    },
    {
      id: "early", header: "Early repurchase fee", label: "Early repurchase fee",
      cell: (row) => <Figure row={row} name="early_repurchase" render={early} />,
    },
    {
      id: "cadence", header: "Dealing", label: "Dealing",
      sortValue: num("repurchase_cadence_per_year"),
      cell: (row) => {
        const suspended = fact(row, "repurchase_program_status").value === "suspended";
        return suspended
          ? <span className="row-3"><Chip kind="misaligned">Suspended</Chip>
            <CiteButton target={{ productKey: row.key, fundName: row.name, cell: fact(row, "repurchase_program_status").source_cell || "3.1" }} compact /></span>
          : <Figure row={row} name="dealing_cadence" />;
      },
    },
    {
      id: "cap", header: "Cap per window", label: "Cap per window", numeric: true, sortValue: num("repurchase_cap_pct"),
      cell: (row) => <Figure row={row} name="repurchase_cap_pct" render={(v: number) => withUnit(fmtNum(v, 2), "%")} />,
    },
    {
      id: "gate", header: "Buyback limits used", label: "Buyback limits used",
      sortValue: (row) => (fact(row, "gate_history").value === true ? 1 : 0),
      cell: (row) => <Figure row={row} name="gate_history"
        render={(v: boolean) => (v ? "Used at least once" : "None identified")} />,
    },
    {
      id: "tax", header: "Tax form", label: "Tax form",
      sortValue: (row) => String(fact(row, "tax_form").value || ""),
      cell: (row) => <Figure row={row} name="tax_form" />,
    },
    {
      id: "big4", header: "Auditor among the four largest", label: "Auditor among the four largest",
      cell: (row) => <Figure row={row} name="big4" render={(v: boolean) => (v ? "Yes" : "No")} />,
    },
    {
      id: "pme", header: <>Public market equivalent vs the reference proxy</>,
      label: "Public market equivalent vs the reference proxy",
      numeric: true, sortValue: num("pme_public_proxy"),
      cell: (row) => <Figure row={row} name="pme_public_proxy" render={(v: number) => fmtRatio(v)} />,
    },
    {
      id: "alpha", header: "Yearly edge over the reference proxy", label: "Yearly edge over the reference proxy",
      numeric: true, sortValue: num("direct_alpha_public_proxy"),
      cell: (row) => <Figure row={row} name="direct_alpha_public_proxy"
        render={(v: number) => `${fmtPct(v)} a year`} />,
    },
    {
      id: "peer", header: "Growth against the peer group", label: "Growth against the peer group",
      numeric: true, sortValue: num("peer_relative_wealth_ratio"),
      cell: (row) => <Figure row={row} name="peer_relative_wealth_ratio" render={(v: number) => fmtRatio(v)} />,
    },
    {
      id: "score", header: "Benchmark selection score", label: "Benchmark selection score",
      numeric: true, sortValue: num("selection_score"),
      cell: (row) => <Figure row={row} name="selection_score" render={(v: number) => `${fmtInt(v)} of ${fmtInt(rubricMax)}`} />,
    },
    {
      id: "bydesc", header: "Meaningful benchmark", label: "Meaningful benchmark",
      cell: (row) => (fact(row, "slot_k_by_descriptor").value === true
        ? <span className="row-3"><span className="t-13">{byDescriptor}</span>
          <CiteButton target={{ productKey: row.key, fundName: row.name, cell: fact(row, "slot_k_by_descriptor").source_cell || "1.11" }} compact /></span>
        : <Figure row={row} name="pme_public_proxy_name" render={(v: string) => `Compared against ${v}`} />),
    },
    {
      id: "verdict", header: "Liquidity, structural", label: "Liquidity, structural",
      sortValue: (row) => String(fact(row, "liquidity_structural_verdict").value || ""),
      cell: (row) => {
        const f = fact(row, "liquidity_structural_verdict");
        if (f.value === null || f.value === undefined) return <Figure row={row} name="liquidity_structural_verdict" />;
        const v = verdictCopy(String(f.value));
        return (
          <span className="row-3">
            <Chip kind={v.kind}>{v.label}</Chip>
            {f.source_cell && row.cited.has(f.source_cell) && (
              <CiteButton target={{ productKey: row.key, fundName: row.name, cell: f.source_cell }} compact />
            )}
          </span>
        );
      },
    },
    {
      id: "track", header: "Track record", label: "Track record", numeric: true, sortValue: num("track_record_years"),
      cell: (row) => <Figure row={row} name="track_record_years" render={(v: number) => `${fmtInt(v)} years`} />,
    },
    {
      id: "aum", header: "Net assets", label: "Net assets", numeric: true, sortValue: num("net_assets_usd"),
      cell: (row) => <Figure row={row} name="net_assets_usd" render={money} />,
    },
    {
      id: "status", header: "Tier of these rows", label: "Tier of these rows",
      cell: (row) => {
        const st = statusCopy(fact(row, "mgmt_fee_pct").status);
        return <Chip kind={st.kind}>{st.label}</Chip>;
      },
    },
  ];
}

/* Print only the fields the fact carries: a fee whose rate is not disclosed
 * says so rather than printing an empty percent. */
function incentive(v: { present?: boolean; rate_pct?: number | null; hurdle_pct?: number | null } | null): string {
  if (!v) return "Not on record";
  if (!v.present) return "None";
  const parts: string[] = [];
  if (v.rate_pct !== null && v.rate_pct !== undefined) parts.push(fmtPct(v.rate_pct));
  if (v.hurdle_pct !== null && v.hurdle_pct !== undefined) parts.push(`${fmtPct(v.hurdle_pct)} hurdle`);
  return parts.length ? parts.join(", ") : "Charged, rate not disclosed";
}

function early(v: { present?: boolean; rate_pct?: number | null; window?: string } | null): string {
  if (!v) return "Not on record";
  if (!v.present) return "None";
  const rate = v.rate_pct !== null && v.rate_pct !== undefined ? fmtPct(v.rate_pct) : "Charged, rate not disclosed";
  return v.window ? `${rate}, ${v.window}` : rate;
}

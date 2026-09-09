/* The premium exhibit (R3-P1-2). Where a fund's shares trade at a price of
 * their own, the gap between that price and the fund's own NAV is a fact
 * about the fund, so it belongs inside that fund's record, under the factors
 * it speaks to, rather than as an item in the navigation named after one
 * fund which every other fund's header then ignored.
 *
 * Every figure here comes from the record: the filed quarterly NAV table the
 * fund prints, the held market-price series, and the premium the record
 * computed against the most recent filed NAV. Nothing is computed from a live
 * NAV, because a live NAV is not observable between filings, and the note
 * says so in the fund's own terms. */
import { Card, CardHead, Chip, Stat, StatRow } from "./primitives";
import { LineChart } from "../charts/charts";
import { Table } from "./table";
import { fmtDate, fmtMoney, fmtNum, fmtPct, withUnit } from "../format/format";
import type { SeriesView } from "../data/types";

const notOnRecord = "Not on record";

interface FiledRow {
  period: string;
  nav_per_share: number;
  price_high?: number;
  price_low?: number;
  premium_pct_at_high?: number;
  premium_pct_at_low?: number;
}
interface Premium {
  last_close?: number;
  last_close_date?: string;
  latest_filed_nav?: number;
  latest_nav_period_end?: string | null;
  premium_pct_vs_latest_filed_nav?: number;
  filed_premium_range_pct?: [number, number];
  note?: string;
  inputs?: string[];
}

/** The supplement key a premium exhibit rides on, where the record has one. */
export function premiumOf(series: SeriesView | null): Premium | null {
  if (!series) return null;
  const entry = Object.entries(series.supplement || {}).find(([k]) => k.endsWith("_premium"));
  return entry ? (entry[1] as Premium) : null;
}

export function PremiumPanel({ series, fundName }: { series: SeriesView; fundName: string }) {
  const premium = premiumOf(series);
  if (!premium) return null;
  const filed = (series.filed_nav || null) as { rows?: FiledRow[]; source?: string; note?: string } | null;
  const rows = filed?.rows || [];
  const range = premium.filed_premium_range_pct;
  const priceLabel = series.daily?.label || "Market price";

  return (
    <Card as="article" className="stack-4">
      <CardHead title="Market price against the fund’s own value" level={3}>
        <Chip kind="partial">Market price</Chip>
      </CardHead>
      <p className="t-14 t-2">
        Shares of {fundName} trade at whatever a buyer will pay, which is not what the fund says a share is
        worth. The gap is the premium. It is measured against the most recent NAV the fund has filed, because
        the value between filings is not observable.
      </p>

      <StatRow>
        {premium.last_close !== undefined && (
          <Stat label="Last close" value={fmtMoney(premium.last_close, 2)}
            source={premium.last_close_date ? `As of ${fmtDate(premium.last_close_date)}` : priceLabel} />
        )}
        {premium.latest_filed_nav !== undefined && (
          <Stat label="Most recent filed value per share" value={fmtMoney(premium.latest_filed_nav, 2)}
            source={premium.latest_nav_period_end
              ? `Period ended ${fmtDate(premium.latest_nav_period_end)}`
              : "From the fund’s own filed table"} />
        )}
        {premium.premium_pct_vs_latest_filed_nav !== undefined && (
          <Stat large label="Premium against that value"
            value={fmtPct(premium.premium_pct_vs_latest_filed_nav)}
            source="Price less filed value, divided by filed value" />
        )}
        {range && (
          <Stat label="Range the fund has filed"
            value={`${fmtPct(range[0])} to ${fmtPct(range[1])}`}
            source="From the fund’s own table of quarters" />
        )}
      </StatRow>

      {rows.length > 0 && (
        <LineChart
          title={`Filed value per share against the quarter’s price range, ${fundName}`}
          description={"One point per quarter from the fund’s own filed table: the value per share it reported, "
            + "and the highest and lowest price its shares traded at in that quarter."}
          height={260}
          yFormat={(v) => fmtMoney(v, 2)}
          series={[
            {
              id: "nav", label: "Filed value per share",
              points: rows.map((r) => ({ x: shortPeriod(r.period), y: r.nav_per_share })),
            },
            {
              id: "high", label: "Highest price in the quarter", dashed: true,
              points: rows.filter((r) => r.price_high !== undefined)
                .map((r) => ({ x: shortPeriod(r.period), y: r.price_high as number })),
            },
            {
              id: "low", label: "Lowest price in the quarter", dashed: true,
              points: rows.filter((r) => r.price_low !== undefined)
                .map((r) => ({ x: shortPeriod(r.period), y: r.price_low as number })),
            },
          ]}
          footer={filed?.source ? <span className="t-12 t-3">Read from {filed.source}</span> : undefined}
        />
      )}

      {rows.length > 0 && (
        <Table
          caption={"The fund\u2019s own quarterly table: value per share, the price range, and the premium at each end."}
          rows={rows}
          rowKey={(r) => r.period}
          cards
          columns={[
            { id: "period", label: "Quarter", header: "Quarter", fixed: true, cell: (r) => shortPeriod(r.period) },
            { id: "nav", label: "Value per share", header: "Value per share", numeric: true,
              sortValue: (r) => r.nav_per_share, cell: (r) => fmtMoney(r.nav_per_share, 2) },
            { id: "high", label: "Highest price", header: "Highest price", numeric: true,
              cell: (r) => (r.price_high === undefined ? notOnRecord : fmtMoney(r.price_high, 2)) },
            { id: "low", label: "Lowest price", header: "Lowest price", numeric: true,
              cell: (r) => (r.price_low === undefined ? notOnRecord : fmtMoney(r.price_low, 2)) },
            { id: "ph", label: "Premium at the high", header: "Premium at the high", numeric: true,
              cell: (r) => (r.premium_pct_at_high === undefined ? notOnRecord : fmtPct(r.premium_pct_at_high)) },
            { id: "pl", label: "Premium at the low", header: "Premium at the low", numeric: true,
              cell: (r) => (r.premium_pct_at_low === undefined ? notOnRecord : fmtPct(r.premium_pct_at_low)) },
          ]}
        />
      )}

      {premium.note && <p className="t-13 t-3">{premium.note}</p>}
      {premium.inputs && premium.inputs.length > 0 && (
        <p className="t-13 t-3">Read from {premium.inputs.join(" and ")}.</p>
      )}
      <p className="t-13 t-3">
        A comparison against this fund’s traded price measures the premium, not the portfolio. Where the record
        compares this fund to a public series, it says so beside the figure.
      </p>
    </Card>
  );
}

/** "Q1 2026 (January 1, 2026 - March 31, 2026)" reads as "Q1 2026" on an axis. */
function shortPeriod(period: string): string {
  const head = period.split(" (")[0].trim();
  return head || period;
}

/** A number a chart axis shows without a currency mark. */
export function plainNumber(v: number): string {
  return withUnit(fmtNum(v, 2), "");
}

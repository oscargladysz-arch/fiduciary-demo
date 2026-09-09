/* The analysis lab for one fund: two tabs over the same record.
 *
 * The first tab grades a comparison the reader chooses. The record scored
 * every fund against every proxy in the library at write time, so the grade
 * beside the reader’s choice is the record’s own rubric answering it, not a
 * new judgment made here. The choice rides in the URL, so a link carries it.
 *
 * The second tab corrects the serial correlation an appraisal process leaves
 * in a reported series. It runs only where the record holds a monthly or
 * finer series, and where it does not the panel says why in words about that
 * fund’s own series. The old lab printed the text of an unrelated row there,
 * which read as an explanation and was not one: that is the defect this
 * panel fixes.
 *
 * Nothing here is human-verified. Every figure the lab draws is recomputed
 * from the series and the returns on record and says so, and a comparison
 * the reader sets carries the illustrative chip.
 *
 * The chart never sets a viewBox: the chart component computes its scales
 * per container, so its axis text stays at the smallest token size at every
 * width. */
import { Fragment } from "react";
import { setParams, useRoute } from "../app/router";
import { LineChart } from "../charts/charts";
import { Field, Select } from "../components/form";
import { Tabs } from "../components/overlay";
import { Card, CardHead, Chip, EmptyState, Link, Skeleton, Stat, StatRow, Term, VerdictBanner }
  from "../components/primitives";
import { SAY } from "../copy/copy";
import { directAlpha, ksPme } from "../analytics/math";
import type { Flow } from "../analytics/math";
import { useAsync, useIndex } from "../data/hooks";
import { data } from "../data/index";
import { expandSeries } from "../data/types";
import { MINUS, fmtDate, fmtInt, fmtN, fmtNum, fmtOf, fmtPct, fmtRatio } from "../format/format";
import type { DailyView, IndexView, LabView as LabShape, SeriesSource, SeriesView } from "../data/types";

/* ------------------------------------------------------------- the shapes
 * The lab chunk carries its profiles and its library as open records, so
 * the fields this panel reads are named here rather than in the shared
 * types. Every field is optional: a fund holds one return input, not all. */
type Point = [string, number];
type Graded = LabShape["matrix"][string][string];

interface Profile {
  default_proxy?: string;
  /** one return per fiscal year, oldest first */
  fy_returns?: number[];
  /** the first and last date those fiscal years cover */
  fy_window?: string[];
  /** a single since-inception figure and the years it covers */
  aatr?: number;
  aatr_years?: number;
  /** the held series this fund’s own line is drawn from */
  fund_series?: string;
  granularity?: string;
  price_series_warning?: string;
}

/** The correction as the record itself recorded it, where it did. */
interface Diagnostics {
  basis?: string;
  window?: string;
  monthly_obs?: number;
  lag1_autocorr_rho?: number;
  nav_path_ann_vol_pct?: number;
  desmoothed_ann_vol_pct?: number;
}

/** Six returns is the fewest this panel will draw a correction from. */
const LEAST_MONTH_ENDS = 7;
const MONTHS_A_YEAR = 12;

const ROLE_WORDS: Record<string, string> = {
  fund: "The fund’s own series",
  index_proxy: "The comparison series",
};

const DESMOOTHING_FALLBACK = "Appraisal prices react late and move little, so reported volatility "
  + "understates the risk taken. The correction restores the movement the pricing process hides.";

/* -------------------------------------------------------------- the maths
 * Each of these is the browser side of a figure the record computes the
 * same way, so a number here and the same number on the record agree. */

function plainWords(name: string): string {
  const t = String(name || "").replace(/_/g, " ").trim();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : "";
}

function roleWords(role: string): string {
  return ROLE_WORDS[role] || plainWords(role) || "Series on record";
}

/** A series whose level is a traded price rather than a value per share. */
function isMarketPrice(s: SeriesSource | undefined): boolean {
  return !!s && /market price/i.test(String(s.label || ""));
}

/** One observation per month, the last of each month. */
function monthEnds(points: Point[]): Point[] {
  const by = new Map<string, Point>();
  for (const p of points) by.set(p[0].slice(0, 7), p);
  return Array.from(by.keys()).sort().map((m) => by.get(m) as Point);
}

function periodReturns(values: number[]): number[] {
  const out: number[] = [];
  for (let i = 1; i < values.length; i += 1) out.push(values[i] / values[i - 1] - 1);
  return out;
}

function mean(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

function stdev(xs: number[]): number {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  return Math.sqrt(xs.reduce((a, x) => a + (x - m) ** 2, 0) / (xs.length - 1));
}

/** Volatility of a period return series, stated per year, in percent. */
function yearlyVolPct(returns: number[], perYear: number): number {
  return stdev(returns) * Math.sqrt(perYear) * 100;
}

/** The correlation between one period’s return and the one before it. */
function lag1(returns: number[]): number {
  if (returns.length < 3) return 0;
  const a = returns.slice(1);
  const b = returns.slice(0, -1);
  const ma = mean(a);
  const mb = mean(b);
  let num = 0;
  for (let i = 0; i < a.length; i += 1) num += (a[i] - ma) * (b[i] - mb);
  const den = Math.sqrt(a.reduce((s, x) => s + (x - ma) ** 2, 0)
    * b.reduce((s, y) => s + (y - mb) ** 2, 0));
  return den ? num / den : 0;
}

/** First-order Geltner correction, one output per return after the first. */
function corrected(returns: number[], rho: number): number[] {
  const out: number[] = [];
  for (let t = 1; t < returns.length; t += 1) out.push((returns[t] - rho * returns[t - 1]) / (1 - rho));
  return out;
}

/** The level on or before a date. Null before the series starts, because a
 *  level there would silently anchor on the first observation. */
function levelOn(points: Point[], d: string): number | null {
  if (!points.length || d < points[0][0]) return null;
  let lvl = points[0][1];
  for (const [di, vi] of points) {
    if (di <= d) lvl = vi;
    else break;
  }
  return lvl;
}

/** The start and end of each fiscal year the record holds a return for. */
function fiscalYearBounds(win: string[], n: number): [string, string][] {
  const w0 = win[0] || "";
  const w1 = win[1] || "";
  const y0 = Number(w0.slice(0, 4));
  const starts = Array.from({ length: n }, (_, i) => `${y0 + i}${w0.slice(4)}`);
  return starts.map((s, i) => [s, i + 1 < n ? starts[i + 1] : w1] as [string, string]);
}

/** The two dates a recorded window names, for clipping to it. */
function windowDates(w: string): [string, string] | null {
  const m = /(\d{4}-\d{2}-\d{2})\D+(\d{4}-\d{2}-\d{2})/.exec(w || "");
  return m ? [m[1], m[2]] : null;
}

function windowWords(w: string): string {
  const m = /(\d{4}-\d{2}-\d{2})\D+(\d{4}-\d{2}-\d{2})/.exec(w || "");
  if (!m) return w || "";
  const tail = w.slice(m[0].length).trim();
  return `${fmtDate(m[1])} to ${fmtDate(m[2])}${tail ? ` ${tail}` : ""}`;
}

/** The correction as the record recorded it, where the fund’s own chunk
 *  carries one. Found by the fields it holds rather than by its name. */
function diagnosticsOf(series: SeriesView): Diagnostics | null {
  for (const held of Object.values(series.supplement || {})) {
    const d = held as Diagnostics;
    if (d && typeof d.lag1_autocorr_rho === "number") return d;
  }
  return null;
}

/** What the record itself says about a fund’s return where it holds no
 *  usable series, taken from the return rows and nowhere else. */
function returnNote(series: SeriesView): string {
  const rows = series.annual || [];
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    const note = String(rows[i].note || "").trim();
    if (note) return note;
  }
  return "";
}

/** What the lab holds for a fund, in one line, for the roster of the others. */
function inputWords(profile: Profile | undefined): string {
  if (!profile) return "No return input on record.";
  if (profile.fund_series) return "A monthly or finer series on record.";
  if (profile.fy_returns && profile.fy_window && profile.fy_window.length === 2) {
    return `Returns by fiscal year, ${fmtInt(profile.fy_returns.length)} on record, `
      + `${fmtDate(profile.fy_window[0])} to ${fmtDate(profile.fy_window[1])}.`;
  }
  if (typeof profile.aatr === "number") return "One return since inception on record.";
  return "No return input on record.";
}

/* ------------------------------------------------------- the comparison */

interface Comparison {
  fund: Point[];
  proxy: Point[];
  note: string;
  reason: string;
}

/** Both lines from one start, the fund from the returns on record and the
 *  comparison from the levels held, over the part of the window the two
 *  have in common. */
function pairSeries(profile: Profile, fundHeld: Point[], proxy: Point[], proxyName: string): Comparison {
  const empty = (reason: string): Comparison => ({ fund: [], proxy: [], note: "", reason });
  if (!proxy.length) {
    return empty("The comparison series is not held on this record, so there is nothing to draw the fund against.");
  }
  const p0 = proxy[0][0];
  const p1 = proxy[proxy.length - 1][0];
  const span = `${proxyName} is held from ${fmtDate(p0)} to ${fmtDate(p1)}.`;
  const fy = profile.fy_returns || null;
  const win = profile.fy_window && profile.fy_window.length === 2 ? profile.fy_window : null;
  let fund: Point[] = [];
  let note = "";

  if (fy && fy.length && win) {
    const bounds = fiscalYearBounds(win, fy.length);
    const kept = bounds.map((b, i) => ({ b, i })).filter((x) => x.b[0] >= p0 && x.b[1] <= p1);
    if (!kept.length) {
      return empty(`No whole fiscal year on record lies inside the comparison series. ${span}`);
    }
    let acc = 1;
    fund = [[kept[0].b[0], 1]];
    for (const x of kept) {
      acc *= 1 + fy[x.i];
      fund.push([x.b[1], acc]);
    }
    if (kept.length < bounds.length) {
      note = `${fmtOf(bounds.length - kept.length, bounds.length)} fiscal years on record fall outside `
        + `the comparison series and are left out. ${span}`;
    }
  } else if (typeof profile.aatr === "number" && typeof profile.aatr_years === "number" && win) {
    if (win[0] < p0 || win[1] > p1) {
      return empty(`The one return on record covers ${fmtDate(win[0])} to ${fmtDate(win[1])}, `
        + `which the comparison series does not cover. ${span}`);
    }
    fund = [[win[0], 1], [win[1], (1 + profile.aatr) ** profile.aatr_years]];
  } else if (fundHeld.length) {
    const all = monthEnds(fundHeld);
    const inside = all.filter(([d]) => d >= p0 && d <= p1);
    if (inside.length < 2) {
      return empty(`The series held for this fund and the comparison series do not overlap. ${span}`);
    }
    const base = inside[0][1];
    fund = inside.map(([d, v]) => [d, v / base] as Point);
    if (inside.length < all.length) {
      note = `${fmtOf(all.length - inside.length, all.length)} month ends held for this fund fall `
        + `outside the comparison series and are left out. ${span}`;
    }
  } else {
    return empty("The record holds no return input for this fund that the lab can recompute.");
  }

  const anchor = levelOn(proxy, fund[0][0]);
  if (!anchor) {
    return empty(`The comparison series carries no level on or before ${fmtDate(fund[0][0])}. ${span}`);
  }
  const drawn: Point[] = [];
  for (const [d] of fund) {
    const lvl = levelOn(proxy, d);
    if (lvl !== null) drawn.push([d, lvl / anchor]);
  }
  if (drawn.length < 2) {
    return empty(`The comparison series carries fewer than two levels over this window. ${span}`);
  }
  return { fund, proxy: drawn, note, reason: "" };
}

/* ----------------------------------------------------------- the sources */

function SourceLines({ sources, ids, lead }:
  { sources: Record<string, SeriesSource>; ids: string[]; lead?: string }) {
  const rows: { id: string; s: SeriesSource }[] = [];
  const seen = new Set<string>();
  for (const id of ids) {
    const s = sources[id];
    if (!id || seen.has(id) || !s) continue;
    seen.add(id);
    rows.push({ id, s });
  }
  if (!rows.length && !lead) return null;
  return (
    <div className="stack-2">
      {lead && <p className="t-13 t-2">{lead}</p>}
      {rows.length > 0 && (
        <dl className="field-list">
          {rows.map(({ id, s }) => (
            <Fragment key={id}>
              <dt>
                <span translate="no">{s.ticker}</span>
                {isMarketPrice(s) && <> <Chip kind="accent">Market price</Chip></>}
              </dt>
              <dd className="t-13">
                {s.label}. {roleWords(s.role)}. Read from {s.source}. Held from {fmtDate(s.first)} to{" "}
                {fmtDate(s.last)}{s.pulled ? `, pulled ${fmtDate(s.pulled)}` : ""}.
              </dd>
            </Fragment>
          ))}
        </dl>
      )}
    </div>
  );
}

/* ---------------------------------------------------------- other funds */

function OtherFunds({ index, profiles, currentKey, tab }:
  { index: IndexView; profiles: Record<string, Profile>; currentKey: string; tab: string }) {
  const others = index.products.filter((p) => p.key !== currentKey);
  if (!others.length) return null;
  return (
    <section className="stack-4" aria-labelledby="lab-others">
      <h2 id="lab-others" className="t-20">The other funds</h2>
      <p className="t-13 t-3">
        The lab never stands one fund in for another. Each name below opens the same two tabs on its
        own record, and the line under it says what that record holds.
      </p>
      <ul className="stack-2">
        {others.map((p) => (
          <li key={p.key}>
            <Link to={`/product/${p.key}/lab`} params={{ tab }}>
              Open the analysis lab for {p.fund_name}
            </Link>
            <div className="t-13 t-3">{inputWords(profiles[p.key])}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}

/* --------------------------------------------------------- the grade card */

function GradeCard({ index, graded }: { index: IndexView; graded: Graded }) {
  const rubric = index.rubric;
  const gated = rubric.criteria[0] || "";
  const gateLabel = rubric.criterion_label[gated] || plainWords(gated);
  return (
    <Card className="stack-4">
      <div className="card__head">
        <h3 className="card__title">{graded.candidate}</h3>
        <Chip kind={graded.eligible ? "aligned" : "misaligned"}>
          {graded.eligible ? "Eligible" : "Not eligible"}
        </Chip>
      </div>
      <StatRow>
        <Stat label="Score against the rubric" value={fmtOf(graded.score, graded.max)}
          source={rubric.label} large />
        <Stat label="To be eligible" value={fmtOf(rubric.threshold, rubric.max)}
          source={`With ${gateLabel} at ${fmtOf(rubric.gate_min, rubric.criterion_max[gated])} or better`} />
        <Stat label="On the record’s own menu for this fund" value={graded.on_menu ? "Yes" : "No"}
          source={graded.on_menu
            ? "The record considered this comparison for this fund"
            : "Graded on its descriptors alone"} />
      </StatRow>
      <VerdictBanner kind={graded.eligible ? "aligned" : "misaligned"}
        label="What the rubric says of this comparison" definition={graded.verdict} />
      <div className="stack-2">
        <p className="t-13 t-3">The four criteria, each with what it measures.</p>
        <dl className="field-list">
          {rubric.criteria.map((c) => (
            <Fragment key={c}>
              <dt>
                {rubric.criterion_label[c] || plainWords(c)},{" "}
                <span className="t-num">{fmtOf(graded.criteria[c], rubric.criterion_max[c])}</span>
              </dt>
              <dd className="t-13">{rubric.criterion_definition[c] || ""}</dd>
            </Fragment>
          ))}
        </dl>
      </div>
      <div className="stack-2">
        <p className="t-13 t-3">Why it scored that way, in the words the record logged.</p>
        <ul className="stack-2">
          {graded.reasons.map((reason) => <li key={reason} className="t-13 t-2">{reason}</li>)}
        </ul>
      </div>
      <p className="t-13 t-2">
        {graded.on_menu
          ? "This comparison is on the record’s own candidate menu for this fund."
          : "This comparison is not on the record’s own candidate menu for this fund. It is graded here on its descriptors alone."}
      </p>
    </Card>
  );
}

/* -------------------------------------------------------- the chart card */

function ComparisonCard({ sources, profile, proxyId, proxyName, fundName }:
  { sources: Record<string, SeriesSource>; profile: Profile; proxyId: string; proxyName: string; fundName: string }) {
  const fundSeriesId = profile.fund_series || "";
  const { value: held, error, loading } = useAsync<{ proxy: Point[]; fund: Point[] }>(() => {
    const d = data();
    if (!d.getDailySeries || !proxyId) return Promise.resolve({ proxy: [], fund: [] });
    const wanted: Promise<DailyView | null>[] = [
      d.getDailySeries(proxyId),
      fundSeriesId ? d.getDailySeries(fundSeriesId) : Promise.resolve(null),
    ];
    return Promise.all(wanted).then(([p, f]) => ({
      proxy: p ? expandSeries(p.points) : [],
      fund: f ? expandSeries(f.points) : [],
    }));
  }, [proxyId, fundSeriesId]);

  if (error) return <EmptyState title={SAY.noRecord}>{error}</EmptyState>;
  if (loading || !held) return <Skeleton lines={6} label={SAY.loadingRecord} />;

  const pair = pairSeries(profile, held.fund, held.proxy, proxyName);
  if (!pair.fund.length) {
    return (
      <EmptyState title="No comparison to draw for this pair">
        <div className="stack-2">
          <p>{pair.reason}</p>
          <p className="t-13 t-3">
            The grade above still holds: the rubric reads the descriptors of the two, and it does not
            need a window they share.
          </p>
        </div>
      </EmptyState>
    );
  }

  const marketPriceFund = isMarketPrice(sources[fundSeriesId]);
  const footer = [pair.note, marketPriceFund ? profile.price_series_warning || "" : ""]
    .filter(Boolean).join(" ");

  // the two statistics, recomputed here over exactly the window drawn above,
  // by the same arithmetic the engine uses (web/src/analytics/math.ts, whose
  // parity with the engine is a test). A public market equivalent is only a
  // public market equivalent against a public market series: against anything
  // else the ratio is shown without that name.
  const flows: Flow[] = [[pair.fund[0][0], -1], [pair.fund[pair.fund.length - 1][0],
    pair.fund[pair.fund.length - 1][1] / pair.fund[0][1]]];
  const proxyLevels: Point[] = pair.proxy;
  let ratio: number | null = null;
  let edge: number | null = null;
  try {
    ratio = ksPme(flows, proxyLevels);
    edge = directAlpha(flows, proxyLevels);
  } catch {
    ratio = null;
    edge = null;
  }
  const proxyIsPublic = !isMarketPrice(sources[proxyId])
    || (sources[proxyId] || {}).role !== undefined;
  const statName = proxyIsPublic ? "Public market equivalent" : "Growth against the comparison";

  return (
    <Card className="stack-4">
      <div className="card__head">
        <h3 className="card__title">Growth of one unit of value, both lines from the same start</h3>
        <Chip kind="illustrative">{SAY.illustrative}</Chip>
      </div>
      <p className="t-13 t-2">
        {SAY.illustrativeNote} Each step of the fund line is a return on record, and each step of the
        comparison line is the level held for that date.
      </p>
      <LineChart
        title={`${fundName} beside ${proxyName}`}
        description={"Two lines from one start date: the fund drawn from the returns on record, and the "
          + "comparison series drawn from the levels held on the same dates."}
        series={[
          { id: "fund", label: fundName, points: pair.fund.map(([x, y]) => ({ x, y })) },
          { id: "proxy", label: proxyName, points: pair.proxy.map(([x, y]) => ({ x, y })), dashed: true },
        ]}
        yFormat={(v) => fmtNum(v, 2)}
        footer={footer || undefined} />
      <StatRow>
        <Stat label={statName} value={ratio === null ? "Not computable here" : fmtRatio(ratio)}
          source={`Recomputed over ${fmtDate(pair.fund[0][0])} to ${fmtDate(pair.fund[pair.fund.length - 1][0])}`} />
        <Stat label="Yearly edge over the comparison"
          value={edge === null ? "Not computable here" : `${fmtPct(edge * 100)} a year`}
          source="The annualized excess rate over the same window" />
      </StatRow>
      <p className="t-13 t-3">
        Both figures are recomputed here from the returns on record and the levels held, over the window
        drawn above. {SAY.reference} where the comparison is a public series shown for orientation:
        the meaningful benchmark for this fund is on its benchmark panel.
      </p>
      <SourceLines sources={sources} ids={[fundSeriesId, proxyId]}
        lead={fundSeriesId ? undefined
          : "The fund line is drawn from the fiscal-year returns on record rather than from a held series."} />
    </Card>
  );
}

/* -------------------------------------------------------- analysis panel */

function AnalysisPanel({ index, sources, library, profile, graded, proxyId, fundKey, fundName }:
  {
    index: IndexView; sources: Record<string, SeriesSource>; library: Record<string, string>;
    profile: Profile; graded: Record<string, Graded>; proxyId: string; fundKey: string;
    fundName: string;
  }) {
  const options = Object.keys(library).map((id) => ({ value: id, label: library[id] }));
  const proxyName = library[proxyId] || "";
  const chosen = graded[proxyId] || null;
  const defaultName = profile.default_proxy ? library[profile.default_proxy] || "" : "";

  return (
    <div className="stack-5">
      {profile.price_series_warning && (
        <VerdictBanner kind="alarm" label="This fund is followed by a market price"
          definition={profile.price_series_warning} />
      )}

      <section className="stack-4" aria-labelledby="lab-grade">
        <h2 id="lab-grade" className="t-20">Grade any comparison against the rubric</h2>
        <div className="filterbar" role="group" aria-label="The comparison to grade">
          <Field label="Comparison series" inline
            hint="Every series in the library, graded for this fund by the record itself.">
            {(ids) => (
              <Select ids={ids} small options={options} value={proxyId}
                onChange={(e) => setParams({ proxy: e.target.value })} />
            )}
          </Field>
        </div>
        <p className="t-13 t-3" aria-live="polite">
          {chosen
            ? `Graded ${fmtOf(chosen.score, chosen.max)} against ${proxyName}.`
            : `No grade is on record for ${proxyName} against this fund.`}
          {defaultName && (
            <>
              {" "}The comparison the record itself made for this fund is {defaultName}.
              {profile.default_proxy !== proxyId && (
                <>
                  {" "}
                  <Link to={`/product/${fundKey}/lab`} replace
                    params={{ tab: "analysis", proxy: profile.default_proxy }}>
                    Show that one instead
                  </Link>
                </>
              )}
            </>
          )}
        </p>
        {chosen
          ? <GradeCard index={index} graded={chosen} />
          : (
            <EmptyState title="No grade for this pair">
              The record grades the library against each fund when it is written. It carries no grade for
              this pair, so there is nothing to show rather than a score assembled here.
            </EmptyState>
          )}
      </section>

      <section className="stack-4" aria-labelledby="lab-chart">
        <h2 id="lab-chart" className="t-20">The two series over the window they share</h2>
        <ComparisonCard sources={sources} profile={profile} proxyId={proxyId} proxyName={proxyName}
          fundName={fundName} />
      </section>
    </div>
  );
}

/* ----------------------------------------------------- desmoothing panel */

function DesmoothingPanel({ index, sources, series, profile, fundName }:
  {
    index: IndexView; sources: Record<string, SeriesSource>; series: SeriesView;
    profile: Profile | null; fundName: string;
  }) {
  const fundSeriesId = profile?.fund_series || "";
  const { value: held, error, loading } = useAsync<Point[]>(() => {
    const d = data();
    if (!fundSeriesId || !d.getDailySeries) return Promise.resolve([] as Point[]);
    return d.getDailySeries(fundSeriesId).then((v) => expandSeries(v.points));
  }, [fundSeriesId]);

  if (error) return <EmptyState title={SAY.noRecord}>{error}</EmptyState>;
  if (loading || !held) return <Skeleton lines={6} label={SAY.loadingRecord} />;

  const diagnostics = diagnosticsOf(series);
  const recorded = diagnostics?.window ? windowDates(diagnostics.window) : null;
  const monthly = (series.monthly || []) as Point[];
  const fromHeld = held.length > 0;
  const points = fromHeld
    ? monthEnds(held)
    : (recorded ? monthly.filter(([d]) => d >= recorded[0] && d <= recorded[1]) : monthly);

  if (points.length < LEAST_MONTH_ENDS) {
    return (
      <div className="stack-5">
        <EmptyState title="This correction cannot run for this fund">
          <div className="stack-2">
            <p>{whyNotAvailable(profile, points.length)}</p>
            {!profile && returnNote(series) && (
              <p className="t-13 t-2">What the record says of this fund’s return: {returnNote(series)}</p>
            )}
            <p className="t-13 t-3">
              The correction reads one observation a month or finer. It is not run on a yearly figure,
              and no other series stands in for this one.
            </p>
          </div>
        </EmptyState>
      </div>
    );
  }

  const dates = points.map(([d]) => d);
  const returns = periodReturns(points.map(([, v]) => v));
  const rho = lag1(returns);
  if (!(rho < 0.999)) {
    return (
      <EmptyState title="This correction cannot run for this fund">
        The month-to-month correlation of this series is at or above one, and the correction divides by
        one less than it. A series that moves this closely with itself carries no correction this method
        can make.
      </EmptyState>
    );
  }
  const after = corrected(returns, rho);
  const volReported = yearlyVolPct(returns, MONTHS_A_YEAR);
  const volAfter = yearlyVolPct(after, MONTHS_A_YEAR);
  const marketPrice = isMarketPrice(sources[fundSeriesId]);
  const definition = index.glossary["de-smoothing"] || DESMOOTHING_FALLBACK;

  return (
    <div className="stack-5">
      {profile?.price_series_warning && (
        <VerdictBanner kind="alarm" label="This fund is followed by a market price"
          definition={profile.price_series_warning} />
      )}

      <section className="stack-4" aria-labelledby="lab-desmooth">
        <h2 id="lab-desmooth" className="t-20">What the reported series holds back</h2>
        <p className="t-14 t-2">
          An appraisal process prices slowly, so a reported series moves less than the assets under it
          do.{" "}
          <Term def={definition}>De-smoothing</Term>{" "}
          is the first-order Geltner correction, and it restores the movement that pricing process
          hides. Each corrected month is (the return this month {MINUS} rho * the return last month) /
          (1 {MINUS} rho), where rho is the correlation between one month and the one before it. It
          corrects that correlation and nothing else. It cannot show what the appraisals never marked,
          such as a stale price, a buyback limit reached, or a market price parting from value.
        </p>
        {marketPrice && (
          <p className="t-13 t-2">
            The series below is a market price. An exchange price carries no appraisal lag, so the
            correction is drawn here for contrast and never as a measure of risk.
          </p>
        )}
        <StatRow>
          <Stat label="Correlation between one month and the one before" value={fmtNum(rho, 3)}
            source={`Read from ${fmtN(returns.length)} monthly returns`} />
          <Stat label="Yearly volatility as reported" value={fmtPct(volReported, 2)}
            source="From the series named below" />
          <Stat label="Yearly volatility after the correction" value={fmtPct(volAfter, 2)}
            source="The same series with that correlation removed" />
          {volReported > 0 && (
            <Stat label="What the correction multiplies it by" value={fmtRatio(volAfter / volReported, 2)}
              source="Volatility after the correction / volatility as reported" />
          )}
        </StatRow>

        <Card className="stack-4">
          <div className="card__head">
            <h3 className="card__title">Monthly return as reported and after the correction</h3>
            <Chip kind="computed">Computed here</Chip>
          </div>
          <p className="t-13 t-2">
            Recomputed here from the series named below rather than read from a filing.
          </p>
          <LineChart
            title={`Monthly return, ${fundName}`}
            description={"Two lines: the monthly return of the series on record, and the same months "
              + "after the first-order correction, which starts one month later."}
            series={[
              {
                id: "reported", label: "As reported",
                points: returns.map((v, i) => ({ x: dates[i + 1], y: v * 100 })),
              },
              {
                id: "corrected", label: "After the correction", dashed: true,
                points: after.map((v, i) => ({ x: dates[i + 2], y: v * 100 })),
              },
            ]}
            yFormat={(v) => fmtPct(v, 1)}
            footer={fromHeld
              ? `Month ends taken from the series held for this fund, ${fmtDate(dates[0])} to ${fmtDate(dates[dates.length - 1])}.`
              : `Month ends taken from the value per share the record prints, ${fmtDate(dates[0])} to ${fmtDate(dates[dates.length - 1])}.`} />
          <SourceLines sources={sources} ids={[fundSeriesId]}
            lead={fromHeld ? undefined
              : (diagnostics?.basis
                ? `The observations are the value per share the record prints. Basis: ${diagnostics.basis}.`
                : "The observations are the value per share the record prints.")} />
        </Card>

        {!fromHeld && diagnostics && (
          <Card sunken className="stack-2">
            <CardHead title="The same correction as the record recorded it" level={3} />
            <dl className="field-list">
              {diagnostics.lag1_autocorr_rho !== undefined && (
                <>
                  <dt>Correlation between one month and the one before</dt>
                  <dd className="t-num">{fmtNum(diagnostics.lag1_autocorr_rho, 3)}</dd>
                </>
              )}
              {diagnostics.nav_path_ann_vol_pct !== undefined && (
                <>
                  <dt>Yearly volatility as reported</dt>
                  <dd className="t-num">{fmtPct(diagnostics.nav_path_ann_vol_pct, 2)}</dd>
                </>
              )}
              {diagnostics.desmoothed_ann_vol_pct !== undefined && (
                <>
                  <dt>Yearly volatility after the correction</dt>
                  <dd className="t-num">{fmtPct(diagnostics.desmoothed_ann_vol_pct, 2)}</dd>
                </>
              )}
              {diagnostics.monthly_obs !== undefined && (
                <>
                  <dt>Monthly observations</dt>
                  <dd className="t-num">{fmtInt(diagnostics.monthly_obs)}</dd>
                </>
              )}
              {diagnostics.window && (
                <>
                  <dt>Window</dt>
                  <dd>{windowWords(diagnostics.window)}</dd>
                </>
              )}
              {diagnostics.basis && (
                <>
                  <dt>Basis</dt>
                  <dd>{diagnostics.basis}</dd>
                </>
              )}
            </dl>
          </Card>
        )}
      </section>
    </div>
  );
}

/** Why the correction cannot run here, in words about this fund’s own
 *  series. Never the text of a row that answers another question. */
function whyNotAvailable(profile: Profile | null, monthEndsHeld: number): string {
  if (!profile) {
    return "The lab holds no return input for this fund, so there is no monthly series to correct.";
  }
  if (monthEndsHeld > 0) {
    return `The record holds ${fmtInt(monthEndsHeld)} month ends for this fund, and this correction `
      + `reads at least ${fmtInt(LEAST_MONTH_ENDS)} before it means anything.`;
  }
  if (profile.fund_series) {
    return "The monthly series this fund is followed by could not be read from this source, so there "
      + "is nothing here to correct yet.";
  }
  if (profile.fy_returns && profile.fy_window && profile.fy_window.length === 2) {
    return `The record holds this fund’s returns by fiscal year: ${fmtInt(profile.fy_returns.length)} `
      + `of them, ${fmtDate(profile.fy_window[0])} to ${fmtDate(profile.fy_window[1])}. A yearly figure `
      + "carries no month-to-month correlation to correct.";
  }
  if (typeof profile.aatr === "number") {
    return "The record holds one return since inception for this fund and no series under it, so there "
      + "is nothing month by month to correct.";
  }
  return "The record holds no monthly or finer series for this fund.";
}

/* ---------------------------------------------------------------- panel */

export default function LabView() {
  const r = useRoute();
  const key = decodeURIComponent(r.segments[1] || "");
  const tab = r.params.get("tab") === "desmoothing" ? "desmoothing" : "analysis";
  const { value: index, error: iErr, loading: iLoading } = useIndex();
  const { value: lab, error: lErr, loading: lLoading } = useAsync<LabShape | null>(() => {
    const d = data();
    return d.getLab ? d.getLab() : Promise.resolve(null);
  }, []);
  const { value: series, error: sErr, loading: sLoading } = useAsync<SeriesView>(
    () => data().getSeries(key), [key]);

  if (iErr || lErr || sErr) {
    return <EmptyState title={SAY.noRecord}>{iErr || lErr || sErr}</EmptyState>;
  }
  if (iLoading || lLoading || sLoading || !index || !series) {
    return <Skeleton lines={10} label={SAY.loadingRecord} />;
  }
  if (!lab) {
    return (
      <EmptyState title={SAY.noRecord}>
        This source does not carry the analysis lab. It is part of the public record rather than of a
        workspace.
      </EmptyState>
    );
  }

  const profiles = (lab.profiles || {}) as unknown as Record<string, Profile>;
  const library = (lab.library || {}) as unknown as Record<string, string>;
  const sources = lab.sources || {};
  const profile = profiles[key] || null;
  const graded = lab.matrix[key] || null;
  const fundName = index.products.find((p) => p.key === key)?.fund_name || "";
  const proxyIds = Object.keys(library);
  const asked = r.params.get("proxy") || "";
  const fallback = profile?.default_proxy && library[profile.default_proxy]
    ? profile.default_proxy
    : proxyIds[0] || "";
  const proxyId = library[asked] ? asked : fallback;

  const analysis = profile && graded
    ? (
      <AnalysisPanel index={index} sources={sources} library={library} profile={profile}
        graded={graded} proxyId={proxyId} fundKey={key} fundName={fundName} />
    )
    : (
      <div className="stack-5">
        <EmptyState title="This fund is not in the comparison set">
          <div className="stack-2">
            <p>
              The lab holds no return input for this fund, so there is nothing here to grade against a
              comparison series and nothing to draw.
            </p>
            {returnNote(series) && (
              <p className="t-13 t-2">
                What the record says of this fund’s return: {returnNote(series)}
              </p>
            )}
          </div>
        </EmptyState>
      </div>
    );

  return (
    <div className="stack-5">
      <Tabs label="The analysis lab" value={tab}
        onChange={(id) => setParams({ tab: id }, { replace: false })}
        tabs={[
          { id: "analysis", label: "Comparison", panel: analysis },
          {
            id: "desmoothing",
            label: "De-smoothing",
            panel: (
              <DesmoothingPanel index={index} sources={sources} series={series} profile={profile}
                fundName={fundName} />
            ),
          },
        ]} />

      <OtherFunds index={index} profiles={profiles} currentKey={key} tab={tab} />

      <Card sunken>
        <CardHead title="How to read this lab" level={2} />
        <p className="t-13 t-3">
          Every figure the lab draws is recomputed from the series and the returns on record, and a
          comparison you choose carries the illustrative chip. Nothing on this page is signed by a
          person. {SAY.verificationCount(index.coverage_totals.counts.verified,
            index.coverage_totals.counts.total)} {SAY.verificationPending}{" "}
          <Link to="/verification">See the verification queue</Link>
        </p>
      </Card>
    </div>
  );
}

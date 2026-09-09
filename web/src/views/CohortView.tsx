/* The cohort panel: the funds this one is set beside, the caveats that bound
 * the comparison, the composite where the record forms one, and the
 * candidates the record considered and did not admit.
 *
 * The caveat block is the defect this panel fixes. The record holds each
 * caveat as one line: a shouted label, a sentence, and a bracket carrying
 * every fund and the value it holds. The old surface printed that line
 * whole, so a reader met registry keys, shouted enum values and a path to a
 * document inside a paragraph. Here the line is taken apart: the label is
 * sentence-cased, the sentence stands on its own, and the bracket becomes a
 * list of fund names against their values. A caveat that still carries an
 * internal name after that is not printed at all, and the panel says how
 * many were withheld and why, because a reader cannot check a name only the
 * record understands.
 *
 * A composite is only formed where every peer in it reports the period on
 * the same basis, so periods short of that are named in the table and left
 * off the chart rather than averaged across two bases. */
import { Fragment, useMemo } from "react";
import { setParams, useRoute } from "../app/router";
import { LineChart } from "../charts/charts";
import { Card, CardHead, Chip, EmptyState, Link, Skeleton, Stat, StatRow } from "../components/primitives";
import { Table } from "../components/table";
import type { Column, SortState } from "../components/table";
import { SAY } from "../copy/copy";
import { useAsync, useIndex } from "../data/hooks";
import { DataError, data } from "../data/index";
import { fmtDate, fmtInt, fmtN, fmtOf, fmtPct, typographic } from "../format/format";
import type { CohortView as CohortShape, CohortsView, IndexView } from "../data/types";

/* ------------------------------------------------------- the local shapes */
/* The chunk types the record as an open map, so the parts this panel reads
 * are named here rather than in the shared types. */
interface MemberEntry { depth?: string; membership_rationale?: string; wrapper_type?: string }
interface PeriodRow {
  composite_return_pct: number | null;
  label?: string;
  members?: string[];
  n?: number;
  period: string;
  period_kind?: string;
}
interface Composite {
  composite_members?: string[];
  composite_note?: string;
  composite_refused_reason?: string;
  excluded_members?: { member: string; reason: string }[];
  granularity?: string;
  member_period_kind?: Record<string, string>;
  member_source?: Record<string, string | null>;
  reason?: string;
  refused?: boolean;
  rows?: PeriodRow[];
  weighting?: string;
}
interface Cohort {
  caveats?: string[];
  composite?: Composite;
  label?: string;
  members?: Record<string, MemberEntry>;
  n?: number;
}
interface MemberRow {
  key: string;
  name: string;
  wrapper: string;
  subject: boolean;
  depth: string;
  periods: string;
  why: string;
}
interface Caveat { label: string; body: string; intro: string; items: { name: string; value: string }[] }

/* Words for the two enumerations this panel meets. A value with no entry is
 * said in plain words rather than printed as the record spells it. */
const DEPTH: Record<string, string> = {
  full: "Every row of the record",
  cohort: "The rows the cohort compares",
};
const PERIOD_BASIS: Record<string, string> = {
  fiscal_year: "Fiscal-year returns on record",
  calendar_year: "Calendar-year returns on record",
  none: "No period returns on record",
};
/* Words a reader knows in capitals. Everything else in a shouted label is
 * lowered when the label is sentence-cased. */
const KEPT_UP = new Set(["NAV", "BDC", "REIT", "PE", "LLC", "CEF", "IPO"]);

/* A name only the record understands. A caveat or an entry carrying one is
 * withheld and counted rather than printed at a reader. */
const INTERNAL: RegExp[] = [
  /[A-Za-z0-9]_[A-Za-z0-9]/,
  /\.(?:json|py|csv|md|ts|tsx|js|yaml|yml)\b/i,
  /\b(?:data|docs|src|site|web|tests)\//i,
  /\bR\d+(?:-P\d+)?\b/,
  /\b(?:engine|artifact|writer)\b/i,
];
/** The keys the record files each fund under. They are names for the record,
 *  not for a reader, so a sentence carrying one is withheld. Matched in the
 *  lower case the record files them in, which leaves a fund’s own market name
 *  in capitals alone. */
function keyPattern(index: IndexView): RegExp | null {
  const keys = index.products.map((p) => p.key).filter((k) => /^[a-z0-9_]+$/.test(k));
  return keys.length ? new RegExp(`\\b(?:${keys.join("|")})\\b`) : null;
}
function hasInternal(s: string, keys: RegExp | null): boolean {
  return INTERNAL.some((re) => re.test(s)) || (keys ? keys.test(s) : false);
}

/* ------------------------------------------------------------- the words */
function sentenceCase(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
}
/** Every date the record wrote as digits, read out in words. */
function datesInWords(s: string): string {
  return String(s || "").replace(/\d{4}-\d{2}-\d{2}/g, (iso) => fmtDate(iso) || iso);
}
/** What the record wrote, as a reader meets it: no emphasis marks left over
 *  from a document, dates in words, curly quotes. */
function clean(s: string | null | undefined): string {
  const flat = String(s || "").replace(/\*\*|__/g, "").replace(/\s+,\s+/g, ", ").replace(/\s{2,}/g, " ").trim();
  return typographic(datesInWords(flat));
}

/* The record writes some of its notes to itself. Two substitutions carry
 * those notes to a reader without changing what they say.
 *
 * The first names each fund the way a reader names it, in place of the key
 * the record files it under, which is the mapping rule 9 of the copy layer
 * asks for.
 *
 * The second protects the tier words. The record uses “verified” in these
 * notes for a filing it located and read, which is not what verified means
 * on this record: verified means a named person signed the row, and nobody
 * has. The check keeps its meaning as “confirmed” so the signature word is
 * left for the count of signed cells alone. The tier shorthand is spelled
 * out for the same reason. */
function readerWords(s: string, byKey: Record<string, string>): string {
  let out = String(s || "");
  for (const [k, name] of Object.entries(byKey)) {
    out = out.replace(new RegExp(`\\b${k}\\b`, "g"), name);
  }
  return out
    .replace(/\bVerified\b/g, "Confirmed")
    .replace(/\bverified\b/g, "confirmed")
    .replace(/\bunverified\b/g, "unconfirmed")
    .replace(/\bverifiable\b/g, "confirmable")
    .replace(/\bT([123])\b/g, "Tier $1");
}
/** One line of the record, ready to read. */
function prose(s: string | null | undefined, byKey: Record<string, string>): string {
  return clean(readerWords(String(s || ""), byKey));
}
/** A sentence ends in a stop. */
function stop(s: string): string {
  return s && !/[.?!]$/.test(s) ? `${s}.` : s;
}
/** A shouted label, lowered word by word, with the acronyms a reader knows
 *  left standing. */
function unshout(label: string): string {
  const said = label
    .split(/([\s-]+)/)
    .map((part) => (KEPT_UP.has(part) ? part : part.toLowerCase()))
    .join("");
  return KEPT_UP.has(said.split(/[\s-]/)[0]) ? said : sentenceCase(said);
}

/* --------------------------------------------------------- the caveat cut */
/** The fund name as this caveat writes it: the record’s display name, or the
 *  same name without the aside the record keeps after it. */
function needleFor(name: string, text: string): string | null {
  const shorter = name.replace(/\s*\([^)]*\)\s*$/, "").trim();
  for (const candidate of [name, shorter]) {
    if (candidate && text.includes(`${candidate}:`)) return candidate;
  }
  return null;
}

/** One caveat, taken apart. The label leads, the sentence stands alone, and
 *  the bracket becomes a fund and its value on each line. */
function cutCaveat(raw: string, names: string[]): Caveat | null {
  const text = String(raw || "").trim();
  if (!text) return null;
  const shouted = /^([A-Z][A-Z0-9\s-]*[A-Z])\s*:\s*([\s\S]*)$/.exec(text);
  const label = shouted ? unshout(shouted[1].trim()) : "";
  let rest = shouted ? shouted[2].trim() : text;

  let intro = "";
  const items: { name: string; value: string }[] = [];
  const bracket = /^([\s\S]*?)\s*\[([^\]]*)\]\s*$/.exec(rest);
  if (bracket) {
    rest = bracket[1].trim();
    const inner = bracket[2];
    const hits: { name: string; at: number; len: number }[] = [];
    for (const name of names) {
      const needle = needleFor(name, inner);
      if (!needle) continue;
      const at = inner.indexOf(`${needle}:`);
      if (at >= 0) hits.push({ name, at, len: needle.length });
    }
    hits.sort((a, b) => a.at - b.at);
    if (!hits.length) return null;   // a bracket this panel cannot name fund by fund
    intro = sentenceCase(inner.slice(0, hits[0].at).replace(/[\s:,]+$/, "").trim());
    hits.forEach((hit, i) => {
      const from = hit.at + hit.len + 1;
      const to = i + 1 < hits.length ? hits[i + 1].at : inner.length;
      const value = inner.slice(from, to).trim().replace(/[,\s]+$/, "").trim();
      if (value) items.push({ name: hit.name, value: clean(value) });
    });
  }
  return { label: label || "A note on this comparison", body: stop(sentenceCase(clean(rest))), intro, items };
}

/* ---------------------------------------------------------- the composite */
/** The period in words, from the date the record holds, never as the record
 *  spells the period out. */
function periodLabel(row: PeriodRow): string {
  const when = fmtDate(row.period);
  if (!when) return clean(row.label) || "Period not dated on the record";
  const kind = row.period_kind === "fiscal_year" ? "Fiscal year to "
    : row.period_kind === "calendar_year" ? "Calendar year to " : "";
  return `${kind}${when}`;
}

function askCohorts(): Promise<CohortsView> {
  const source = data();
  if (!source.getCohorts) {
    return Promise.reject(new DataError("cohorts", 404, "this source carries no cohort roster"));
  }
  return source.getCohorts();
}

/* ------------------------------------------------------------- the panel */
export default function CohortView() {
  const r = useRoute();
  const key = decodeURIComponent(r.segments[1] || "");
  const { value: index, error: indexError, loading: indexLoading } = useIndex();
  const { value: chunk, error, loading } = useAsync<CohortShape>(() => data().getCohort(key), [key]);
  // the roster of every cohort carries the log of what was not admitted: the
  // panel renders without it rather than failing with it
  const { value: roster, error: rosterError, loading: rosterLoading } = useAsync<CohortsView>(() => askCohorts(), []);

  const sort: SortState | null = r.params.get("sort")
    ? { id: r.params.get("sort")!, dir: r.params.get("dir") === "desc" ? "desc" : "asc" }
    : null;
  const visible = r.params.get("cols") ? r.params.get("cols")!.split(".") : null;

  const cohort = (chunk?.cohort || null) as Cohort | null;
  const cohortId = chunk?.cohort_id || "";

  const keys = useMemo(() => (index ? keyPattern(index) : null), [index]);
  const byKey = useMemo<Record<string, string>>(() => {
    const out: Record<string, string> = {};
    for (const p of index?.products || []) if (/^[a-z0-9_]+$/.test(p.key)) out[p.key] = p.fund_name;
    return out;
  }, [index]);

  const memberKeys = useMemo<string[]>(() => {
    const ordered = roster?.members?.[cohortId] || index?.cohorts?.[cohortId]?.members || [];
    const held = Object.keys(cohort?.members || {});
    const seen = new Set<string>();
    const out: string[] = [];
    for (const k of [...ordered, ...held]) {
      if (held.includes(k) && !seen.has(k)) { seen.add(k); out.push(k); }
    }
    return out;
  }, [roster, index, cohort, cohortId]);

  const rows = useMemo<MemberRow[]>(() => {
    if (!cohort || !index) return [];
    const composite = cohort.composite || {};
    const left = composite.excluded_members || [];
    return memberKeys.map((k) => {
      const entry = (cohort.members || {})[k] || {};
      const product = index.products.find((p) => p.key === k);
      const name = product?.fund_name || "A fund this panel cannot name";
      const source = composite.member_source?.[k];
      const stated = left.find((e) => e.member === name);
      const basis = source
        ? sentenceCase(prose(source, byKey))
        : stated ? stop(sentenceCase(prose(stated.reason, byKey)))
          : PERIOD_BASIS[String(composite.member_period_kind?.[k] || "")] || "Not on record";
      const why = stop(prose(entry.membership_rationale, byKey));
      return {
        key: k,
        name,
        wrapper: index.labels.wrapper[String(entry.wrapper_type || "")]
          || product?.wrapper_label || "Not on record",
        subject: k === key,
        depth: DEPTH[String(entry.depth || "")] || "Not stated on the record",
        periods: hasInternal(basis, keys) ? "Stated on the record in shorthand of its own" : basis,
        why: !why ? "No reason on record"
          : hasInternal(why, keys) ? "The record states this in shorthand of its own rather than in words a reader can check."
            : why,
      };
    });
  }, [cohort, index, memberKeys, key, keys, byKey]);

  const caveats = useMemo<{ shown: Caveat[]; withheld: number }>(() => {
    const names = rows.map((row) => row.name);
    const shown: Caveat[] = [];
    let withheld = 0;
    for (const raw of cohort?.caveats || []) {
      const cut = cutCaveat(readerWords(raw, byKey), names);
      if (!cut) { withheld += 1; continue; }
      const said = `${cut.label} ${cut.body} ${cut.intro} ${cut.items.map((i) => i.value).join(" ")}`;
      if (hasInternal(said, keys)) { withheld += 1; continue; }
      shown.push(cut);
    }
    return { shown, withheld };
  }, [cohort, rows, keys, byKey]);

  const excluded = useMemo(() => {
    const all = (roster?.exclusions || []).map((e) => ({
      name: prose(e.name, byKey),
      reason: stop(sentenceCase(prose(e.reason, byKey))),
    }));
    const shown = all.filter((e) => !hasInternal(`${e.name} ${e.reason}`, keys));
    return { shown, withheld: all.length - shown.length };
  }, [roster, keys, byKey]);

  if (error || indexError) return <EmptyState title={SAY.noRecord}>{error || indexError}</EmptyState>;
  if (loading || indexLoading || !chunk || !index) return <Skeleton lines={10} label={SAY.loadingRecord} />;

  const subject = index.products.find((p) => p.key === key);
  const label = prose(cohort?.label, byKey) || index.cohorts?.[cohortId]?.label || "";

  if (!cohort || !label) {
    return (
      <EmptyState title="No cohort on record for this fund">
        A cohort appears here once the record admits at least two peers this fund can be set beside on the
        same wrapper and the same strategy, each with filings of its own.
      </EmptyState>
    );
  }

  const composite = cohort.composite || {};
  const periods = composite.rows || [];
  const peers = composite.composite_members || [];
  const charted = periods.filter((row) => typeof row.composite_return_pct === "number");
  const offChart = periods.length - charted.length;
  const refusal = composite.refused
    ? stop(sentenceCase(prose(composite.reason, byKey)))
    : composite.composite_refused_reason ? stop(sentenceCase(prose(composite.composite_refused_reason, byKey))) : "";
  const left = composite.excluded_members || [];

  return (
    <div className="stack-5">
      <section className="stack-4" aria-labelledby="cohort-head">
        <h2 id="cohort-head" className="t-24 t-balance">{label}</h2>
        <p className="t-14 t-2">
          The funds the record sets {subject?.fund_name || "this fund"} beside, what the comparison can carry
          and where it stops carrying. Every figure here is the record’s own.
        </p>
        <StatRow>
          <Stat label="Funds in this cohort" value={fmtInt(rows.length)}
            source="Each one evaluated on filings of its own" />
          <Stat label="Peers in the composite" value={peers.length ? fmtInt(peers.length) : "None"}
            source={peers.length ? "Reporting the same periods on the same basis" : "No composite is formed"} />
          <Stat label="Periods with a composite" value={periods.length ? fmtOf(charted.length, periods.length) : fmtInt(0)}
            source="A period every peer in the composite reports" />
          <Stat label="Signed by a person" value={fmtInt(index.coverage_totals.counts.verified)}
            source={SAY.verificationPending} />
        </StatRow>
      </section>

      <section className="stack-4" aria-labelledby="cohort-members">
        <h2 id="cohort-members" className="t-20">The funds in this cohort</h2>
        <p className="t-13 t-3" aria-live="polite">
          {fmtInt(rows.length)} funds, and the reason the record gives for each one being here.
        </p>
        <Table
          id="cohort-members-table"
          caption={`The funds in ${label}, the wrapper each one uses and why the record admitted it. ${SAY.verificationPending}`}
          columns={memberColumns()}
          rows={rows}
          rowKey={(row) => row.key}
          sort={sort}
          onSort={(s) => setParams({ sort: s?.id || null, dir: s?.dir || null })}
          visible={visible}
          onVisible={(ids) => setParams({ cols: ids ? ids.join(".") : null })}
          empty="The record holds no members for this cohort." />
      </section>

      <section className="stack-4" aria-labelledby="cohort-caveats">
        <h2 id="cohort-caveats" className="t-20">Where the comparison needs care</h2>
        <p className="t-14 t-2">
          Each note names one thing that differs across these funds, then gives the value the record holds for
          every fund in turn. A difference here does not stop the comparison, it bounds what the comparison
          can mean.
        </p>
        {caveats.shown.length === 0 && caveats.withheld === 0 && (
          <EmptyState title="No comparability note on record">
            A note appears here when the funds in this cohort differ on how they are priced, how much they may
            borrow, what exit rights they owe or how often they value what they hold.
          </EmptyState>
        )}
        <div className="stack-4">
          {caveats.shown.map((caveat) => (
            <Card key={caveat.label + caveat.body.slice(0, 24)} as="article" className="stack-2">
              <CardHead title={caveat.label} level={3} />
              <p className="t-14">{caveat.body}</p>
              {caveat.items.length > 0 && (
                <div className="stack-2">
                  {caveat.intro && <p className="t-12 t-3">{caveat.intro}</p>}
                  <dl className="field-list">
                    {caveat.items.map((item) => (
                      <Fragment key={item.name}>
                        <dt translate="no">{item.name}</dt>
                        <dd>{item.value}</dd>
                      </Fragment>
                    ))}
                  </dl>
                </div>
              )}
            </Card>
          ))}
        </div>
        {caveats.withheld > 0 && (
          <p className="t-13 t-3">
            {fmtInt(caveats.withheld)}{" "}
            {caveats.withheld === 1 ? "further note is" : "further notes are"} not shown here. The record
            states {caveats.withheld === 1 ? "it" : "them"} in shorthand of its own rather than in fund names
            and values a reader can check against a filing.
          </p>
        )}
      </section>

      <section className="stack-4" aria-labelledby="cohort-composite">
        <h2 id="cohort-composite" className="t-20">The peer composite</h2>
        <p className="t-14 t-2">
          An equal-weight average of the peers that report the same period on the same basis, period by
          period, never a running total.
        </p>

        {refusal ? (
          <Card sunken className="stack-2">
            <CardHead title="What the record says about forming this composite" level={3} />
            <p className="t-14">{refusal}</p>
          </Card>
        ) : charted.length >= 2 ? (
          <Card className="stack-2">
            <LineChart
              title={`Composite return by period, ${label}`}
              description={"One line: the equal-weight return of the peer composite in each period the record "
                + "forms one for. Periods short of the full set of peers are left off and are named in the "
                + "table below."}
              series={[{
                id: "composite",
                label: "Peer composite",
                points: charted.map((row) => ({ x: row.period, y: row.composite_return_pct as number })),
              }]}
              yFormat={(v) => fmtPct(v)}
              footer={"Each point is the return of that period on its own. The table below carries every "
                + "period, the funds reporting it and how many that is."} />
          </Card>
        ) : (
          <Card sunken className="stack-2">
            <CardHead title="Too few periods to draw a line" level={3} />
            <p className="t-14">
              A line needs at least two periods every peer in the composite reports. The record forms{" "}
              {fmtInt(charted.length)} of {fmtInt(periods.length)}. The table below carries them all.
            </p>
          </Card>
        )}

        {offChart > 0 && (
          <p className="t-13 t-3">
            {fmtOf(charted.length, periods.length)} periods carry a composite. The other {fmtInt(offChart)}{" "}
            {offChart === 1 ? "is" : "are"} left off the chart because fewer than the{" "}
            {peers.length ? fmtInt(peers.length) : fmtInt(0)} peers of the composite report{" "}
            {offChart === 1 ? "it" : "them"} on the same basis.
          </p>
        )}

        <Table
          id="cohort-periods-table"
          caption={`Every period the record holds for ${label}, the funds reporting it, and the composite `
            + `return where one is formed. This is the table behind the chart.`}
          columns={periodColumns(index, peers.length)}
          rows={periods}
          rowKey={(row) => `${row.period}-${row.period_kind || "period"}`}
          empty="The record holds no periods for this cohort." />

        {left.length > 0 && (
          <Card as="article" className="stack-2">
            <CardHead title="Funds left out of the composite" level={3} />
            <dl className="field-list">
              {left.map((entry) => (
                <Fragment key={entry.member}>
                  <dt translate="no">{prose(entry.member, byKey)}</dt>
                  <dd>{stop(sentenceCase(prose(entry.reason, byKey)))}</dd>
                </Fragment>
              ))}
            </dl>
          </Card>
        )}

        <Card sunken className="stack-2">
          <CardHead title="How this composite is formed" level={3} />
          <dl className="field-list">
            <dt>Weighting</dt>
            <dd>{stop(sentenceCase(prose(composite.weighting, byKey))) || "Not on record"}</dd>
            <dt>Periods</dt>
            <dd>{stop(sentenceCase(prose(composite.granularity, byKey))) || "Not on record"}</dd>
            {composite.composite_note && (
              <><dt>What it covers</dt><dd>{stop(sentenceCase(prose(composite.composite_note, byKey)))}</dd></>
            )}
          </dl>
        </Card>
      </section>

      <section className="stack-4" aria-labelledby="cohort-exclusions">
        <h2 id="cohort-exclusions" className="t-20">Candidates the record did not admit</h2>
        <p className="t-14 t-2">
          Funds the record looked at for these cohorts and left out, each with the reason it gives. A
          candidate left out is part of the reasoning, not a gap in it.
        </p>
        {rosterError && (
          <EmptyState title={SAY.noRecord}>{rosterError}</EmptyState>
        )}
        {!rosterError && rosterLoading && <Skeleton lines={4} label={SAY.loadingRecord} />}
        {!rosterError && !rosterLoading && (
          <Table
            id="cohort-exclusions-table"
            caption="The candidates considered for the cohorts on this record and not admitted, with the reason the record gives."
            columns={EXCLUSION_COLUMNS}
            rows={excluded.shown}
            rowKey={(row) => row.name}
            empty="No candidate was turned away on this record." />
        )}
        {excluded.withheld > 0 && (
          <p className="t-13 t-3">
            {fmtInt(excluded.withheld)}{" "}
            {excluded.withheld === 1 ? "entry is" : "entries are"} not shown here. The record gives the reason
            in shorthand of its own rather than in words a reader can check.
          </p>
        )}
      </section>

      <Card sunken className="stack-2">
        <CardHead title="How to read this cohort" level={2} />
        <p className="t-13 t-3">
          A composite is only shown where every peer in it reports the period on the same basis. Where one
          peer reports on another basis, that period is named and left out rather than averaged across two
          bases.
        </p>
        <p className="t-13 t-3">
          A peer comparison is never a public market equivalent. These peers are valued by appraisal and
          cannot be bought as a public series, so a reading against them is relative to this group and says
          nothing about a public market. The benchmark the rule asks for is on the benchmark panel for this
          fund.{" "}
          <Link to={`/product/${key}/benchmark`} params={{ plan: r.params.get("plan") || undefined }}>
            See the benchmark panel
          </Link>
        </p>
        <p className="t-13 t-3">
          {SAY.verificationCount(index.coverage_totals.counts.verified, index.coverage_totals.counts.total)}{" "}
          <Link to="/verification">See the verification queue</Link>
        </p>
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------- columns */
function memberColumns(): Column<MemberRow>[] {
  return [
    {
      id: "name", header: "Fund", label: "Fund", fixed: true,
      sortValue: (row) => row.name,
      cell: (row) => <Link to={`/product/${row.key}/record`} translate="no">{row.name}</Link>,
    },
    {
      id: "wrapper", header: "Wrapper", label: "Wrapper",
      sortValue: (row) => row.wrapper,
      cell: (row) => <span className="t-13">{row.wrapper}</span>,
    },
    {
      id: "here", header: "In this panel", label: "In this panel",
      sortValue: (row) => (row.subject ? 0 : 1),
      cell: (row) => <Chip kind={row.subject ? "accent" : "neutral"}>{row.subject ? "Subject" : "Peer"}</Chip>,
    },
    {
      id: "depth", header: "Record depth", label: "Record depth",
      sortValue: (row) => row.depth,
      cell: (row) => <span className="t-13">{row.depth}</span>,
    },
    {
      id: "periods", header: "Returns on record", label: "Returns on record",
      cell: (row) => <span className="t-13 t-2">{row.periods}</span>,
    },
    {
      id: "why", header: "Why it is here", label: "Why it is here",
      cell: (row) => <span className="t-13 t-2">{row.why}</span>,
    },
  ];
}

function periodColumns(index: IndexView, peerCount: number): Column<PeriodRow>[] {
  const nameOf = (k: string) => index.products.find((p) => p.key === k)?.fund_name || "";
  return [
    {
      id: "period", header: "Period", label: "Period", fixed: true,
      cell: (row) => <span className="t-13">{periodLabel(row)}</span>,
    },
    {
      id: "n", header: "Funds reporting", label: "Funds reporting", numeric: true,
      cell: (row) => <span className="t-num">{fmtInt(row.n ?? (row.members || []).length)}</span>,
    },
    {
      id: "return", header: "Composite return", label: "Composite return", numeric: true,
      cell: (row) => (typeof row.composite_return_pct === "number"
        ? <span className="t-num">{fmtPct(row.composite_return_pct)}</span>
        : (
          <span className="t-13 t-3">
            Not formed at {fmtN(row.n ?? (row.members || []).length)}
            {peerCount ? ` of ${fmtInt(peerCount)}` : ""}
          </span>
        )),
    },
    {
      id: "who", header: "Which funds", label: "Which funds",
      cell: (row) => (
        <span className="t-13 t-2" translate="no">
          {(row.members || []).map(nameOf).filter(Boolean).join(", ") || "None on record"}
        </span>
      ),
    },
  ];
}

const EXCLUSION_COLUMNS: Column<{ name: string; reason: string }>[] = [
  {
    id: "candidate", header: "Candidate", label: "Candidate", fixed: true,
    cell: (row) => <span className="t-13" translate="no">{row.name}</span>,
  },
  {
    id: "reason", header: "Why it was not admitted", label: "Why it was not admitted",
    cell: (row) => <span className="t-13 t-2">{row.reason}</span>,
  },
];

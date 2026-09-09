/* Evidence search: every cited row of the record, searched on the value and
 * on the sentence quoted out of the filing.
 *
 * The box never takes focus on arrival: the skip link is the first Tab stop
 * on every route, and a control that claims the caret on a narrow viewport
 * opens the keyboard over text the reader has not read yet. It takes focus
 * only when Clear sends it there, and a re-render caused by a keystroke, a
 * filter or a sort never steals the caret back, which is what the previous
 * frontend did.
 *
 * What a reader types stays out of the link (R3-P1-3): free text never
 * enters the URL. The fund and the tier are keys, so they do serialize, and
 * they replace the history entry rather than pushing one, which leaves Back
 * pointing at the route the reader came from.
 *
 * A long value is shown as the sentence the match sits in, shortened with
 * the ellipsis character. The match itself is highlighted by splitting the
 * text in React and rendering <mark> around the run, never by assembling
 * markup out of a string.
 *
 * The sentence quoted out of the filing is the document’s own text and is
 * never edited, so it is marked verbatim: it carries the straight quotes,
 * the apostrophes and the punctuation the filing printed, and the typography
 * rules that hold over this frontend’s own prose do not reach it.
 *
 * Tier language is the record’s own and does not blur: extracted is a quote
 * a reader can open, and nothing here is signed by a person. */
import { useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { setParams, useRoute } from "../app/router";
import { CiteButton } from "../components/citation";
import { Field, Input, Select } from "../components/form";
import { Button, Card, CardHead, Chip, EmptyState, Legend, Link, Skeleton, Stat, StatRow }
  from "../components/primitives";
import { PageHeader } from "../components/shell";
import { Table } from "../components/table";
import type { Column, SortState } from "../components/table";
import { SAY, TIERS, routeTitle, status as statusCopy } from "../copy/copy";
import { useAsync, useIndex } from "../data/hooks";
import { DataError, data } from "../data/index";
import { ELLIPSIS, fmtInt, fmtOf } from "../format/format";
import type { EvidenceRow, EvidenceView } from "../data/types";

/** the longest value shown before the sentence around the match is taken */
const MAX_EXCERPT = 220;
/** where one sentence of a value ends */
const BREAK = /[.!?\n]/;
const NONE = "";  // the empty option of a filter, meaning every value
/** the one sentence under the H1, said the same way in every state */
const SUB = "Search reaches the value and the quoted sentence of every row of the record that names a filing behind it.";

/* The tier of a row, in the record’s own vocabulary. The record qualifies a
 * status after a comma ("not applicable, no market price exists"), so the
 * head of the status is what the tier reads from, and the qualifier stays on
 * the row itself. The token on the left is what rides in the URL. */
const TIERS_IN_ORDER: { token: string; key: string }[] = [
  { token: "structured", key: "structured" },
  { token: "extracted", key: "extracted-unverified" },
  { token: "verified", key: "verified" },
  { token: "computed", key: "computed" },
  { token: "partial", key: "partial" },
  { token: "fetched", key: "fetched" },
  { token: "na", key: "n/a" },
  { token: "advisor", key: "advisor-stated" },
];

function tierToken(raw: string): string {
  const s = String(raw || "").trim().toLowerCase();
  for (const t of TIERS_IN_ORDER) if (s.startsWith(t.key)) return t.token;
  if (s.startsWith("extracted")) return "extracted";
  return "pending";
}

function tierKey(token: string): string {
  const found = TIERS_IN_ORDER.find((t) => t.token === token);
  return found ? found.key : "pending";
}

interface Hit {
  row: EvidenceRow;
  /** lowercased once, so a keystroke does not lowercase the whole record again */
  value: string;
  quote: string;
  token: string;
  order: number;
}

/** The sentence the match sits in, shortened at both ends where it was cut. */
function excerpt(text: string, needle: string): string {
  const body = (text || "").trim();
  if (body.length <= MAX_EXCERPT) return body;
  const at = needle ? body.toLowerCase().indexOf(needle) : -1;
  if (at < 0) return body.slice(0, MAX_EXCERPT).trimEnd() + ELLIPSIS;
  let start = 0;
  for (let i = at - 1; i > 0; i--) {
    if (BREAK.test(body[i]) && /\s/.test(body[i + 1] || " ")) { start = i + 1; break; }
  }
  let end = body.length;
  for (let i = at + needle.length; i < body.length; i++) {
    if (BREAK.test(body[i]) && /\s/.test(body[i + 1] || " ")) { end = i + 1; break; }
  }
  if (end - start > MAX_EXCERPT) {
    start = Math.max(start, at - Math.round(MAX_EXCERPT / 3));
    end = Math.min(end, at + needle.length + MAX_EXCERPT);
  }
  const cut = body.slice(start, end).trim();
  return (start > 0 ? ELLIPSIS : "") + cut + (end < body.length ? ELLIPSIS : "");
}

/** The match, highlighted by splitting the text rather than by building
 *  markup out of it. */
function Marked({ text, needle }: { text: string; needle: string }) {
  if (!needle) return <>{text}</>;
  const lower = text.toLowerCase();
  const parts: ReactNode[] = [];
  let from = 0;
  let at = lower.indexOf(needle);
  while (at >= 0) {
    if (at > from) parts.push(text.slice(from, at));
    parts.push(<mark key={`${at}`}>{text.slice(at, at + needle.length)}</mark>);
    from = at + needle.length;
    at = lower.indexOf(needle, from);
  }
  if (from < text.length) parts.push(text.slice(from));
  return <>{parts}</>;
}

function askEvidence(): Promise<EvidenceView> {
  const source = data();
  if (!source.getEvidence) {
    return Promise.reject(new DataError("evidence", 404, "this source carries no cited rows"));
  }
  return source.getEvidence();
}

export default function SearchView() {
  const r = useRoute();
  const { value: index, loading: indexLoading } = useIndex();
  const { value: evidence, error, loading } = useAsync<EvidenceView>(() => askEvidence(), []);

  const [query, setQuery] = useState("");
  // the search box does not take focus on arrival: the skip link is the
  // first Tab stop on every route, and a reader who lands here has not read
  // the page yet. It takes focus only when Clear sends it there, and a
  // keystroke, a filter or a sort leaves the caret where the reader put it.
  const box = useRef<HTMLInputElement>(null);

  const hits = useMemo<Hit[]>(() => (evidence?.rows || []).map((row) => {
    const [factor, within] = row.cell.split(".");
    return {
      row,
      value: (row.value || "").toLowerCase(),
      quote: (row.quote || "").toLowerCase(),
      token: tierToken(row.status),
      order: Number(factor) * 1000 + Number(within || 0),
    };
  }), [evidence]);

  const funds = useMemo(() => {
    const seen = new Map<string, string>();
    for (const h of hits) if (!seen.has(h.row.product_key)) seen.set(h.row.product_key, h.row.fund_name);
    return [...seen.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [hits]);

  const tokensPresent = useMemo(() => new Set(hits.map((h) => h.token)), [hits]);

  // what the URL claims, validated against what the record holds
  const claimedFund = r.params.get("f_fund") || NONE;
  const fund = funds.some(([key]) => key === claimedFund) ? claimedFund : NONE;
  const claimedTier = r.params.get("f_tier") || NONE;
  const tier = tokensPresent.has(claimedTier) ? claimedTier : NONE;

  const needle = query.trim().toLowerCase();
  const shown = useMemo(() => hits.filter((h) => {
    if (fund && h.row.product_key !== fund) return false;
    if (tier && h.token !== tier) return false;
    if (!needle) return true;
    return h.value.includes(needle) || h.quote.includes(needle);
  }), [hits, fund, tier, needle]);

  // one object per URL state rather than one per render: the table sorts
  // eight hundred rows off this identity, and a keystroke must not re-sort
  const sortId = r.params.get("sort");
  const sortDir = r.params.get("dir");
  const sort = useMemo<SortState | null>(
    () => (sortId ? { id: sortId, dir: sortDir === "desc" ? "desc" : "asc" } : null),
    [sortId, sortDir]);

  const columns = useMemo<Column<Hit>[]>(() => [
    {
      id: "fund", header: "Fund", label: "Fund", fixed: true,
      sortValue: (h) => h.row.fund_name,
      cell: (h) => (
        <Link to={`/product/${h.row.product_key}/record`} translate="no">{h.row.fund_name}</Link>
      ),
    },
    {
      id: "cell", header: "Row of the record", label: "Row of the record",
      sortValue: (h) => h.order,
      // the same row of the record appears once per fund, so the visible text
      // repeats while the destination does not: the fund is added to the name,
      // after the visible text rather than in place of it
      cell: (h) => {
        const rowLabel = index?.cells[h.row.cell]?.label || h.row.element;
        return (
          <Link to={`/product/${h.row.product_key}/record`} params={{ factor: h.row.cell.split(".")[0] }}
            aria-label={`${h.row.cell} ${rowLabel}, ${h.row.fund_name}`}>
            <span className="t-eyebrow" translate="no">{h.row.cell}</span>{" "}
            {rowLabel}
          </Link>
        );
      },
    },
    {
      id: "value", header: "What the row says", label: "What the row says",
      cell: (h) => {
        const inQuote = !!needle && h.quote.includes(needle);
        return (
          // the record writes a value as one slash-joined run where the filing
          // did ("purchases/repurchases/distributions"), and a browser breaks
          // neither slashes nor an accession: at 390 px such a run leaves the
          // column and then the viewport unless it is told it may break
          <div className="stack-2" style={{ overflowWrap: "anywhere" }}>
            <span className="t-13"><Marked text={excerpt(h.row.value, needle)} needle={needle} /></span>
            {inQuote && (
              <span className="t-12 t-3" data-verbatim="true">
                {"“"}<Marked text={excerpt(h.row.quote, needle)} needle={needle} />{"”"}
              </span>
            )}
          </div>
        );
      },
    },
    {
      id: "tier", header: "Tier", label: "Tier",
      sortValue: (h) => statusCopy(tierKey(h.token)).label,
      cell: (h) => {
        const st = statusCopy(tierKey(h.token));
        return <Chip kind={st.kind} title={st.definition}>{st.label}</Chip>;
      },
    },
    {
      id: "source", header: "Source", label: "Source",
      cell: (h) => (
        <CiteButton target={{ productKey: h.row.product_key, fundName: h.row.fund_name, cell: h.row.cell }} compact />
      ),
    },
  ], [index, needle]);

  // the error state is a state of this route, not a page of its own: it keeps
  // the H1 the route is named by, so the heading order holds here too
  if (error) {
    return (
      <div className="stack-5">
        <PageHeader title={routeTitle("search")} sub={SUB} />
        <EmptyState title={SAY.noRecord}>{error}</EmptyState>
      </div>
    );
  }

  const verified = Number(index?.coverage_totals.counts.verified ?? 0);
  const cellsOnRecord = Number(index?.coverage_totals.total ?? 0);
  const fundOptions = [{ value: NONE, label: "Every fund" },
    ...funds.map(([key, name]) => ({ value: key, label: name }))];
  const tierOptions = [{ value: NONE, label: "Every tier" },
    ...TIERS_IN_ORDER.filter((t) => tokensPresent.has(t.token))
      .map((t) => ({ value: t.token, label: statusCopy(t.key).label }))];
  const narrowed = !!(needle || fund || tier);

  const clear = () => {
    setQuery("");
    setParams({ f_fund: null, f_tier: null });
    box.current?.focus();
  };

  let results: ReactNode;
  if (loading) {
    results = <Skeleton lines={10} label={SAY.loadingRecord} />;
  } else if (hits.length === 0) {
    results = (
      <EmptyState title={SAY.noRecord}>
        A row arrives here once a cell of the record names the document it was read from.
      </EmptyState>
    );
  } else if (shown.length === 0) {
    results = (
      <EmptyState
        title="Nothing on record matches that"
        action={narrowed ? <Button onClick={clear}>Clear the search and the filters</Button> : undefined}
      >
        A word or a number from a value on record, or from a sentence quoted out of a filing, would match.
        Try a shorter word, or widen the fund and the tier.
      </EmptyState>
    );
  } else {
    results = (
      <Table<Hit>
        id="evidence-results"
        caption={`Cited rows of the record, searched on the value and on the quoted sentence. ${SAY.verificationPending}`}
        columns={columns}
        rows={shown}
        rowKey={(h) => `${h.row.product_key}:${h.row.cell}`}
        sort={sort}
        onSort={(s) => setParams({ sort: s?.id || null, dir: s?.dir || null })}
        maxHeight="var(--table-max)"
        empty={SAY.emptyFilter}
      />
    );
  }

  return (
    <div className="stack-5">
      <PageHeader
        title={routeTitle("search")}
        sub={SUB}
        actions={<Link to="/coverage">Coverage and provenance</Link>}
      />

      {loading || indexLoading ? <Skeleton lines={3} label={SAY.loadingRecord} /> : (
        <StatRow>
          <Stat label="Rows with a filing behind them" value={fmtInt(hits.length)}
            source="One per cell that carries a document, a section or a quoted sentence" />
          <Stat label="Funds" value={fmtInt(funds.length)} source="Every fund evaluated in the record" />
          {/* the count of signed cells is the index chunk's own figure: where
              the index is not on hand there is no figure to show, and a zero
              typed in its place would read as one */}
          {index && <Stat label="Signed by a person" value={fmtInt(verified)} source={SAY.verificationPending} />}
        </StatRow>
      )}

      <Card className="stack-4">
        <CardHead title="Find a value or a quoted sentence" level={2} />
        <Field label="Search the record"
          hint="What you type is never written into the link. A link you copy carries the fund and the tier only.">
          {(ids) => (
            <Input ids={ids} ref={box} type="search" value={query} spellCheck={false}
              placeholder="A word or a number from a filing…"
              onChange={(e) => setQuery(e.target.value)} />
          )}
        </Field>

        <div className="filterbar" role="group" aria-label="Filters">
          <Field label="Fund" inline>
            {(ids) => <Select ids={ids} small options={fundOptions} value={fund}
              onChange={(e) => setParams({ f_fund: e.target.value })} />}
          </Field>
          <Field label="Tier of the row" inline>
            {(ids) => <Select ids={ids} small options={tierOptions} value={tier}
              onChange={(e) => setParams({ f_tier: e.target.value })} />}
          </Field>
        </div>

        {/* the count is the live region and nothing else is: a control inside
            one is read out again every time the count changes */}
        <div className="row">
          <p className="t-13 t-3" aria-live="polite">
            {loading
              ? `${SAY.loadingRecord}${ELLIPSIS}`
              : `Showing ${fmtOf(shown.length, hits.length)} rows.`}
          </p>
          {!loading && narrowed && (
            <Button variant="quiet" onClick={clear}>Clear the search and the filters</Button>
          )}
        </div>
      </Card>

      <section className="stack-4">
        <h2 className="t-20">Results</h2>
        {results}
      </section>

      <Card sunken className="stack-2">
        <Legend label="Tiers" items={TIERS.map((t, i) => ({
          label: t.label, kind: (["structured", "extracted", "verified"] as const)[i],
        }))} />
        <p className="t-13 t-3">
          A search reaches what is on record and nothing else. {SAY.verificationPending}{" "}
          {index && <>{SAY.verificationCount(verified, cellsOnRecord)}{" "}</>}
          An extracted row carries the document, the section and the sentence a reader can open beside it.
        </p>
      </Card>
    </div>
  );
}

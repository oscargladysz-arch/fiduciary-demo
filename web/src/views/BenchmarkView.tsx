/* The benchmark panel for one fund.
 *
 * Two slots, and each card leads with the candidate the record chose rather
 * than with the method that chose it. The meaningful benchmark is the
 * paragraph (k) comparison. The peer comparison is the cohort side by side.
 * How the choice was made sits behind a Method disclosure, and the rubric
 * sits behind a second one, so a reader meets a name and a number first.
 *
 * The statistic is named for what it is. A public market equivalent is only
 * ever a comparison against a public market series. A comparison against an
 * appraisal-based peer composite is a relative wealth ratio and says so.
 *
 * Nothing here is a legal conclusion. Where no candidate clears both the
 * strategy gate and the score threshold the record escalates, and the card
 * prints the escalation as written with the two limits shown apart, because
 * a total at the threshold still fails a gate it never cleared. */
import { Fragment, useMemo } from "react";
import { setParams, useRoute } from "../app/router";
import { LineChart } from "../charts/charts";
import { CiteButton } from "../components/citation";
import { Field, Select } from "../components/form";
import { Disclosure } from "../components/overlay";
import { Card, CardHead, Chip, EmptyState, Link, Skeleton, Stat, StatRow, Term, VerdictBanner }
  from "../components/primitives";
import { Table } from "../components/table";
import type { Column, SortState } from "../components/table";
import { SAY } from "../copy/copy";
import { useAsync, useIndex } from "../data/hooks";
import { data } from "../data/index";
import { fmtDate, fmtInt, fmtN, fmtOf, fmtPct, fmtRatio, hashPrefix } from "../format/format";
import type { IndexView, SelectionView } from "../data/types";

/* ------------------------------------------------------------- the shapes
 * The selection chunk arrives as an open record, so the shapes it carries
 * are named here rather than in the shared types. Every field is optional:
 * a card renders a key only where the record holds it. */
interface Comparison {
  comparator_kind?: string;
  direct_alpha_pct?: number | null;
  excess_return_pct?: number | null;
  fund_ann_pct?: number | null;
  fund_growth_x?: number | null;
  fund_return_source?: string;
  fund_window?: string;
  index_ann_pct?: number | null;
  index_growth_x?: number | null;
  kind?: string;
  ks_pme?: number | null;
  ks_pme_monthly_schedule?: number | null;
  low_confidence?: string | null;
  n?: number | null;
  not_pme_note?: string;
  relative_wealth_ratio?: number | null;
  schedule_contributions?: number | null;
  schedule_note?: string | null;
  statistic?: string;
  window?: string;
  window_note?: string;
  window_years?: number | null;
}

interface CompositeRow {
  composite_return_pct?: number | null;
  fund_return_pct?: number | null;
  label: string;
  n?: number | null;
  period: string;
}

interface Composite extends Comparison {
  alignment_note?: string;
  candidate?: string;
  excluded?: { member: string; reason: string }[];
  n_peers?: number | null;
  period_kind?: string;
  periods?: string[];
  reason?: string | null;
  rows?: CompositeRow[];
  status?: string;
  weighting?: string;
}

interface Candidate {
  by_descriptor?: boolean;
  candidate: string;
  comparator_kind?: string;
  comparison?: Comparison | null;
  comparison_note?: string | null;
  criteria?: Record<string, number>;
  held?: boolean;
  lane?: string;
  max?: number;
  reasons?: string[];
  score?: number | null;
}

interface SlotK {
  escalation?: string | null;
  label?: string;
  max_attainable?: number | null;
  selected?: Candidate | null;
  ties?: unknown[];
}

interface PeerRow {
  label: string;
  n?: number | null;
  period: string;
  period_kind?: string;
  returns: Record<string, number | null>;
}

interface SlotG {
  cohort_label?: string;
  composite?: Composite;
  heterogeneity_note?: string;
  label?: string;
  member_names?: string[];
  member_period_kind?: Record<string, string>;
  member_source?: Record<string, string | null>;
  members?: string[];
  survivorship_note?: string;
  table?: PeerRow[];
}

interface Declared {
  cell?: string;
  comparison?: Comparison | null;
  comparison_note?: string | null;
  held?: boolean;
  name: string;
  status?: string;
  type_label?: string;
}

interface Rejected {
  candidate: string;
  criteria?: Record<string, number>;
  lane?: string;
  max?: number;
  reasons?: string[];
  rejection?: string;
  score?: number | null;
  tied?: boolean;
}

interface Reference {
  candidate: string;
  comparison?: Comparison | null;
  held?: boolean;
  lane?: string;
  note?: string;
  score?: number | null;
}

interface Inputs {
  accessions?: { accession: string; cell?: string; filing_date?: string; form?: string }[];
  cells?: string[];
  descriptors?: Record<string, { count?: number; fields?: string[]; path?: string; sha256?: string }>;
  note?: string;
  record_hash?: string;
  recorded_at?: string;
  series?: { path?: string; sha256?: string }[];
}

interface Selection {
  basis?: { label?: string };
  declared?: Declared[];
  declared_none_reason?: string | null;
  inputs?: Inputs;
  record_hash?: string;
  recorded_at?: string;
  reference_comparison?: Reference | null;
  reference_skipped?: { candidate: string; note?: string }[];
  rejected?: Rejected[];
  slot_g?: SlotG;
  slot_k?: SlotK;
  source_cells?: string[];
  strategy?: string;
}

/* ------------------------------------------------------------- small help */

/** Period bases in reader words: the record names them for itself. */
const PERIOD_KIND: Record<string, string> = {
  fiscal_year: "fiscal year",
  calendar_year: "calendar year",
};

/** An internal name with no map, said in plain words rather than printed
 *  as it is stored. */
function plainWords(name: string): string {
  const t = String(name || "").replace(/_/g, " ").trim();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : "";
}

/** The name the record gives a held series, as a reader can read it. The field
 *  holds a stored location on some records, so anything shaped like one is
 *  left out rather than printed: a name for a reader has words in it. */
function readerName(name: string | undefined): string {
  const t = String(name || "").trim();
  if (!t) return "";
  if (/(^|[\s(])(?:data|docs|src|site|web)\//i.test(t)) return "";
  if (!/\s/.test(t) && (/[/\\]/.test(t) || /\.[A-Za-z0-9]{1,5}$/.test(t))) return "";
  return t;
}

/** The first sentence of a note. The rest goes behind Method, so the card
 *  carries one alignment sentence and never a paragraph. */
function firstSentence(text: string): string {
  const t = (text || "").trim();
  const m = /^[\s\S]*?[.!?](?=\s|$)/.exec(t);
  return m ? m[0] : t;
}

function afterFirstSentence(text: string): string {
  const t = (text || "").trim();
  const head = firstSentence(t);
  return t.length > head.length ? t.slice(head.length).trim() : "";
}

interface Named { label: string; value: string; term: string }

/** The statistic, named for what it is. A public market equivalent needs a
 *  public market series on the other side: a peer composite is appraisal
 *  based, cannot be bought, and is a relative wealth ratio instead. */
function statisticOf(c: Comparison | null | undefined): Named | null {
  if (!c) return null;
  const againstPublic = c.kind === "series"
    && /public market/i.test(String(c.comparator_kind || ""));
  if (c.relative_wealth_ratio !== null && c.relative_wealth_ratio !== undefined) {
    return {
      label: "Relative wealth ratio", term: "relative wealth ratio",
      value: fmtRatio(c.relative_wealth_ratio),
    };
  }
  if (c.ks_pme !== null && c.ks_pme !== undefined) {
    return againstPublic
      ? { label: "Public market equivalent", term: "KS-PME", value: fmtRatio(c.ks_pme) }
      : { label: "Wealth ratio against the comparator", term: "relative wealth ratio", value: fmtRatio(c.ks_pme) };
  }
  return null;
}

/** A statistic name with its one-line definition behind a tooltip, where the
 *  record carries a definition for it. */
function StatName({ glossary, term, children }:
  { glossary: Record<string, string>; term: string; children: string }) {
  const def = glossary[term];
  return def ? <Term def={def}>{children}</Term> : <>{children}</>;
}

/** The window a comparison ran over, and its low-confidence note where the
 *  record carries one. */
function WindowLine({ c }: { c: Comparison }) {
  return (
    <div className="row-3">
      {c.window && <span className="t-13 t-3">Window {c.window}</span>}
      {c.window_note && <span className="t-13 t-3">{c.window_note}</span>}
      {c.low_confidence && (
        <>
          <Chip kind="partial">Low confidence</Chip>
          <span className="t-13 t-3">{c.low_confidence}</span>
        </>
      )}
    </div>
  );
}

/** The figures behind a comparison, said once, under Method. */
function ComparisonDetail({ c, glossary }: { c: Comparison; glossary: Record<string, string> }) {
  return (
    <div className="stack-2">
      <dl className="field-list">
        {c.comparator_kind && (<><dt>What it is compared against</dt><dd>{c.comparator_kind}</dd></>)}
        {c.fund_return_source && (<><dt>Where the fund return comes from</dt><dd>{c.fund_return_source}</dd></>)}
        {c.window && (<><dt>Window</dt><dd>{c.window}</dd></>)}
        {c.fund_ann_pct !== null && c.fund_ann_pct !== undefined && (
          <><dt>Fund, each year</dt><dd className="t-num">{fmtPct(c.fund_ann_pct)}</dd></>)}
        {c.index_ann_pct !== null && c.index_ann_pct !== undefined && (
          <><dt>Comparator, each year</dt><dd className="t-num">{fmtPct(c.index_ann_pct)}</dd></>)}
        {c.fund_growth_x !== null && c.fund_growth_x !== undefined && (
          <><dt>Fund growth over the window</dt><dd className="t-num">{fmtRatio(c.fund_growth_x)}</dd></>)}
        {c.index_growth_x !== null && c.index_growth_x !== undefined && (
          <><dt>Comparator growth over the window</dt><dd className="t-num">{fmtRatio(c.index_growth_x)}</dd></>)}
        {c.direct_alpha_pct !== null && c.direct_alpha_pct !== undefined && (
          <>
            <dt><StatName glossary={glossary} term="Direct Alpha">Yearly edge over the comparator</StatName></dt>
            <dd className="t-num">{fmtPct(c.direct_alpha_pct)} a year</dd>
          </>)}
        {c.excess_return_pct !== null && c.excess_return_pct !== undefined && (
          <><dt>Yearly excess return</dt><dd className="t-num">{fmtPct(c.excess_return_pct)} a year</dd></>)}
        {c.n !== null && c.n !== undefined && (<><dt>Members in every period</dt><dd>{fmtN(c.n)}</dd></>)}
      </dl>
      <p className="t-13 t-3">
        The ratio is fund growth / comparator growth over identical periods, one contribution at the
        start of the window and one valuation at the end.
      </p>
      {c.not_pme_note && <p className="t-13 t-2">{c.not_pme_note}</p>}
      {c.schedule_note && (
        <div className="row-3">
          <Chip kind="illustrative">{SAY.illustrative}</Chip>
          <span className="t-13 t-3">
            {c.schedule_note}
            {c.ks_pme_monthly_schedule !== null && c.ks_pme_monthly_schedule !== undefined
              ? ` Ratio on that schedule ${fmtRatio(c.ks_pme_monthly_schedule)}.`
              : ""}
          </span>
        </div>
      )}
    </div>
  );
}

/** The rubric, once, behind a disclosure: each criterion with the points the
 *  candidate earned and the record’s own one-line definition. */
function CriteriaTable({ index, criteria, summary }:
  { index: IndexView; criteria: Record<string, number>; summary: string }) {
  const rubric = index.rubric;
  interface Row { id: string; label: string; earned: number; max: number; definition: string }
  const rows: Row[] = (rubric.criteria || []).filter((c) => c in criteria).map((c) => ({
    id: c,
    label: rubric.criterion_label[c] || plainWords(c),
    earned: criteria[c],
    max: rubric.criterion_max[c],
    definition: rubric.criterion_definition[c] || "",
  }));
  const columns: Column<Row>[] = [
    { id: "criterion", header: "Criterion", label: "Criterion", fixed: true, cell: (r) => r.label },
    {
      id: "points", header: "Points", label: "Points", numeric: true,
      cell: (r) => <span className="t-num">{fmtOf(r.earned, r.max)}</span>,
    },
    {
      id: "definition", header: "What it measures", label: "What it measures",
      cell: (r) => <span className="t-13 t-2">{r.definition || "No definition on record."}</span>,
    },
  ];
  return (
    <Disclosure summary={summary}>
      <div className="stack-2">
        <Table
          caption={`${rubric.label}. Threshold ${fmtOf(rubric.threshold, rubric.max)}.`}
          columns={columns} rows={rows} rowKey={(r) => r.id} cards={false}
          empty="This candidate carries no scored criteria on the record." />
      </div>
    </Disclosure>
  );
}

/* ------------------------------------------------------------- the panel */

export default function BenchmarkView() {
  const r = useRoute();
  const key = decodeURIComponent(r.segments[1] || "");
  const { value: index, error: iErr, loading: iLoading } = useIndex();
  const { value: view, error, loading } =
    useAsync<SelectionView>(() => data().getSelection(key), [key]);

  const sel = (view?.selection || null) as unknown as Selection | null;

  // the ledger’s one filter, in the URL as a key so a link carries it
  const role = r.params.get("role") || "";
  const lsort: SortState | null = r.params.get("lsort")
    ? { id: r.params.get("lsort")!, dir: r.params.get("ldir") === "desc" ? "desc" : "asc" }
    : null;
  const psort: SortState | null = r.params.get("psort")
    ? { id: r.params.get("psort")!, dir: r.params.get("pdir") === "desc" ? "desc" : "asc" }
    : null;

  const ledger = useMemo(() => ledgerRows(sel, index), [sel, index]);
  const shown = useMemo(
    () => (role ? ledger.filter((row) => row.role === role) : ledger),
    [ledger, role]);

  if (error || iErr) return <EmptyState title={SAY.noRecord}>{error || iErr}</EmptyState>;
  if (loading || iLoading || !index) return <Skeleton lines={10} label={SAY.loadingRecord} />;
  if (!sel || !sel.slot_k) {
    return (
      <EmptyState title={SAY.noRecord}>
        No benchmark selection is on record for this fund. One is written when the candidate menu for
        its strategy is scored against the rubric.
      </EmptyState>
    );
  }

  const rubric = index.rubric;
  const glossary = index.glossary || {};
  const fundName = index.products.find((p) => p.key === key)?.fund_name || "";
  const slotK = sel.slot_k;
  const slotG = sel.slot_g;
  const picked = slotK.selected || null;
  const pickedStat = statisticOf(picked?.comparison);
  const composite = slotG?.composite;
  const compositeComputed = composite?.status === "computed";
  const compositeStat = compositeComputed ? statisticOf(composite) : null;
  const gated = rubric.criteria[0] || "";
  const gateLabel = rubric.criterion_label[gated] || plainWords(gated);
  const gateMax = rubric.criterion_max[gated];
  const kLabel = slotK.label || index.labels.slot.slot_k || "Meaningful benchmark";
  const gLabel = slotG?.label || index.labels.slot.slot_g || "Peer comparison";
  const recordedAt = sel.inputs?.recorded_at || sel.recorded_at || "";
  const recordHash = sel.inputs?.record_hash || sel.record_hash || "";
  // a held series is listed only where the record both names it in reader
  // words and locks it by content, so no row prints a stored location and no
  // row prints a blank where a name or a lock belongs
  const heldSeries = (sel.inputs?.series || [])
    .map((held) => ({ name: readerName(held.path), lock: hashPrefix(held.sha256) }))
    .filter((held) => held.name && held.lock);
  // the reference block belongs only where the meaningful benchmark carries
  // no comparison of its own, so it can never read as the answer
  const reference = !picked?.comparison ? sel.reference_comparison || null : null;
  const referenceStat = statisticOf(reference?.comparison);
  const ties = (sel.rejected || []).filter((x) => x.tied === true);

  // what the card says in place of a statistic. A candidate can carry no
  // comparison at all, or carry one the record gives no ratio for, and neither
  // may render as a blank where a figure belongs.
  const decided = !picked
    ? ""
    : picked.comparison
      ? "The record computes no ratio from the comparison it holds for this candidate."
      : (picked.by_descriptor ? rubric.by_descriptor_sentence : "")
        || picked.comparison_note
        || "No comparison is computed for this candidate on the record.";

  // one alignment sentence on the card, in the words of the record: the
  // criterion that asks whether the two liquidity processes match. The rest
  // of the reasoning sits behind Method.
  const alignLabel = rubric.criterion_label[rubric.criteria[1] || ""] || "";
  const alignK = picked
    ? firstSentence((picked.reasons || []).find((x) => alignLabel && x.startsWith(alignLabel))
      || (picked.reasons || [])[0] || "")
    : "";

  const roleOptions = [
    { value: "", label: "Every candidate" },
    { value: "selected", label: "Selected and reference" },
    { value: "declared", label: "Declared and required" },
    { value: "peer", label: "Peer comparison" },
    { value: "rejected", label: "Not selected" },
  ];

  return (
    <div className="stack-5">
      <StatRow>
        <Stat
          label={kLabel}
          value={picked ? fmtOf(picked.score, rubric.max) : "No candidate"}
          source={picked ? picked.candidate : firstSentence(slotK.escalation || "")} />
        {pickedStat ? (
          <Stat
            label={<StatName glossary={glossary} term={pickedStat.term}>{pickedStat.label}</StatName>}
            value={pickedStat.value}
            source={picked?.comparison?.window || ""} />
        ) : (
          <Stat label="Comparison on the meaningful benchmark" value="None computed"
            source={decided || firstSentence(slotK.escalation || "")} />
        )}
        {compositeStat ? (
          <Stat
            label={<StatName glossary={glossary} term={compositeStat.term}>{compositeStat.label}</StatName>}
            value={compositeStat.value}
            source={composite?.window || ""} />
        ) : (
          <Stat label="Peer comparison" value="No composite"
            source={composite?.reason || "The cohort carries no composite on the record."} />
        )}
        <Stat
          label="What a candidate has to clear"
          value={fmtOf(rubric.threshold, rubric.max)}
          source={`Total score, and ${fmtOf(rubric.gate_min, gateMax)} on ${gateLabel.toLowerCase()} on its own`} />
      </StatRow>

      <p className="t-13 t-3">
        Return basis for every comparison: {sel.basis?.label || "not stated on the record"}.
        {sel.strategy && index.labels.strategy[sel.strategy]
          ? ` Strategy on record: ${index.labels.strategy[sel.strategy]}.`
          : ""}
      </p>

      {/* ------------------------------------------------------- slot K */}
      <section className="stack-4" aria-labelledby="slot-k">
        <h2 id="slot-k" className="t-20">{kLabel}</h2>

        <Card as="article" className="stack-4" data-slot="k">
          {picked ? (
            <>
              <div className="card__head">
                <h3 className="card__title">{picked.candidate}</h3>
                <div className="row-3">
                  <Chip kind="accent">Selected</Chip>
                  <Chip kind="tier">{fmtOf(picked.score, rubric.max)}</Chip>
                  {picked.lane && index.labels.lane[picked.lane] && (
                    <Chip kind="wrapper">{index.labels.lane[picked.lane]}</Chip>
                  )}
                  <Chip kind={picked.held ? "structured" : "pending"}>
                    {picked.held ? "Series held" : "Series not held"}
                  </Chip>
                </div>
              </div>

              {picked.comparator_kind && (
                <p className="t-14 t-2">Compared against {picked.comparator_kind}.</p>
              )}

              {picked.comparison && pickedStat ? (
                <>
                  <StatRow>
                    <Stat large
                      label={<StatName glossary={glossary} term={pickedStat.term}>{pickedStat.label}</StatName>}
                      value={pickedStat.value}
                      source={picked.comparison.comparator_kind} />
                    {picked.comparison.direct_alpha_pct !== null
                      && picked.comparison.direct_alpha_pct !== undefined && (
                      <Stat
                        label={<StatName glossary={glossary} term="Direct Alpha">Yearly edge over the comparator</StatName>}
                        value={`${fmtPct(picked.comparison.direct_alpha_pct)} a year`}
                        source={picked.comparison.fund_return_source} />
                    )}
                  </StatRow>
                  <WindowLine c={picked.comparison} />
                </>
              ) : (
                <p className="t-14" data-by-descriptor={picked.by_descriptor ? "true" : undefined}>{decided}</p>
              )}

              {alignK && <p className="t-13 t-2">{alignK}</p>}

              <Disclosure summary="Method: how this candidate was chosen">
                <div className="stack-2">
                  <p className="t-13 t-2">
                    {rubric.label}. A candidate needs {fmtOf(rubric.threshold, rubric.max)} in all and{" "}
                    {fmtOf(rubric.gate_min, gateMax)} on {gateLabel.toLowerCase()} on its own. A candidate
                    whose publisher is tied to one of the advisers of the fund is not eligible at any score.
                  </p>
                  {slotK.max_attainable !== null && slotK.max_attainable !== undefined && (
                    <p className="t-13 t-3">
                      Best an eligible candidate could reach on the data the record holds:{" "}
                      {fmtOf(slotK.max_attainable, rubric.max)}.
                    </p>
                  )}
                  <ul className="stack-2">
                    {(picked.reasons || []).map((reason, i) => <li key={i} className="t-13 t-2">{reason}</li>)}
                  </ul>
                  {picked.comparison && (
                    <ComparisonDetail c={picked.comparison} glossary={glossary} />
                  )}
                </div>
              </Disclosure>

              {picked.criteria && (
                <CriteriaTable index={index} criteria={picked.criteria}
                  summary={`The criteria behind ${fmtOf(picked.score, rubric.max)}`} />
              )}
            </>
          ) : (
            <>
              <CardHead title="No candidate was selected" level={3}>
                <Chip kind="misaligned">Escalated</Chip>
              </CardHead>
              <VerdictBanner kind="alarm" label="The record does not name a meaningful benchmark for this fund"
                definition={slotK.escalation || "No reason is on record."} />
              <StatRow>
                <Stat label={`${gateLabel}, the minimum on that criterion alone`}
                  value={fmtOf(rubric.gate_min, gateMax)}
                  source="Below this a candidate is not eligible, whatever its total." />
                <Stat label="Score threshold, the minimum total"
                  value={fmtOf(rubric.threshold, rubric.max)}
                  source="A total counts only once the criterion above is cleared." />
              </StatRow>
              <p className="t-13 t-3">
                The two limits are separate. A candidate can reach the total and still fail on the one
                criterion, which is why a score at the threshold is not on its own a pass.
              </p>
            </>
          )}

          <div className="row-3">
            {(sel.source_cells || []).map((cell) => (
              <CiteButton key={cell} target={{ productKey: key, fundName, cell }}
                label="Open the row behind this selection" />
            ))}
          </div>

          {recordedAt && recordHash ? (
            <p className="t-13 t-3 provenance" data-lock="true">
              Selection recorded {fmtDate(recordedAt)}, record {hashPrefix(recordHash)}
            </p>
          ) : (
            <p className="t-13 t-3">The selection is not locked: no decision date and no record fingerprint are on file for it.</p>
          )}
        </Card>

        {reference && (
          <Card as="article" className="stack-4" data-reference="true">
            <div className="card__head">
              <h3 className="card__title">{reference.candidate}</h3>
              <div className="row-3">
                <Chip kind="pending">{SAY.reference}</Chip>
                {reference.lane && index.labels.lane[reference.lane] && (
                  <Chip kind="wrapper">{index.labels.lane[reference.lane]}</Chip>
                )}
                {reference.score !== null && reference.score !== undefined && (
                  <Chip kind="tier">{fmtOf(reference.score, rubric.max)}</Chip>
                )}
              </div>
            </div>
            <p className="t-13 t-2">{SAY.referenceNote}</p>
            {referenceStat && reference.comparison && (
              <>
                <StatRow>
                  <Stat
                    label={<StatName glossary={glossary} term={referenceStat.term}>{referenceStat.label}</StatName>}
                    value={referenceStat.value}
                    source={reference.comparison.comparator_kind} />
                  {reference.comparison.direct_alpha_pct !== null
                    && reference.comparison.direct_alpha_pct !== undefined && (
                    <Stat
                      label={<StatName glossary={glossary} term="Direct Alpha">Yearly edge over the comparator</StatName>}
                      value={`${fmtPct(reference.comparison.direct_alpha_pct)} a year`}
                      source={reference.comparison.fund_return_source} />
                  )}
                </StatRow>
                <WindowLine c={reference.comparison} />
                <Disclosure summary="Method: what this reference is and is not">
                  <div className="stack-2">
                    {reference.note && <p className="t-13 t-2">{reference.note}</p>}
                    <ComparisonDetail c={reference.comparison} glossary={glossary} />
                  </div>
                </Disclosure>
              </>
            )}
          </Card>
        )}

        {(sel.reference_skipped || []).length > 0 && (
          <Card sunken className="stack-2">
            <CardHead title={SAY.reference} level={3} />
            <p className="t-13 t-2">{SAY.referenceNote}</p>
            <ul className="stack-2">
              {(sel.reference_skipped || []).map((skipped) => (
                <li key={skipped.candidate} className="t-13 t-3">
                  {skipped.candidate}: {skipped.note || "No comparison is on record."}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>

      {/* ------------------------------------------------------- slot G */}
      {slotG && (
        <section className="stack-4" aria-labelledby="slot-g">
          <h2 id="slot-g" className="t-20">{gLabel}</h2>
          <Card as="article" className="stack-4" data-slot="g">
            <div className="card__head">
              <h3 className="card__title">
                {composite?.candidate || slotG.cohort_label || "Peer cohort"}
              </h3>
              <div className="row-3">
                <Chip kind="wrapper">{slotG.cohort_label || "Peer cohort"}</Chip>
                <Chip kind={compositeComputed ? "computed" : "pending"}>
                  {compositeComputed ? "Composite computed" : "Composite refused"}
                </Chip>
                {composite?.n_peers !== null && composite?.n_peers !== undefined && (
                  <Chip kind="neutral">{fmtN(composite.n_peers)} peers</Chip>
                )}
              </div>
            </div>

            {compositeComputed && composite && compositeStat ? (
              <>
                <StatRow>
                  <Stat large
                    label={<StatName glossary={glossary} term={compositeStat.term}>{compositeStat.label}</StatName>}
                    value={compositeStat.value}
                    source="Appraisal-based peers, never a public market equivalent" />
                  {composite.excess_return_pct !== null && composite.excess_return_pct !== undefined && (
                    <Stat label="Yearly excess return over the peers"
                      value={`${fmtPct(composite.excess_return_pct)} a year`}
                      source={composite.fund_return_source} />
                  )}
                </StatRow>
                <WindowLine c={composite} />
                {composite.not_pme_note && <p className="t-13 t-2">{composite.not_pme_note}</p>}
                {composite.alignment_note && (
                  <p className="t-13 t-2">{firstSentence(composite.alignment_note)}</p>
                )}
              </>
            ) : compositeComputed ? (
              <p className="t-14">
                The cohort carries a composite on the record, and the record computes no ratio from it.
              </p>
            ) : (
              <p className="t-14">
                Composite refused: {composite?.reason || "no reason is on record."}
              </p>
            )}

            <Disclosure summary="Method: how the peers were put side by side">
              <div className="stack-2">
                {composite?.weighting && <p className="t-13 t-2">{composite.weighting}.</p>}
                {composite?.alignment_note && afterFirstSentence(composite.alignment_note) && (
                  <p className="t-13 t-2">{afterFirstSentence(composite.alignment_note)}</p>
                )}
                {slotG.heterogeneity_note && <p className="t-13 t-2">{slotG.heterogeneity_note}</p>}
                {slotG.survivorship_note && <p className="t-13 t-2">{slotG.survivorship_note}</p>}
                {(composite?.excluded || []).length > 0 && (
                  <ul className="stack-2">
                    {(composite?.excluded || []).map((x) => (
                      <li key={x.member} className="t-13 t-3">Left out of the composite, {x.member}: {x.reason}</li>
                    ))}
                  </ul>
                )}
                {slotG.member_source && Object.keys(slotG.member_source).length > 0 && (
                  <dl className="field-list">
                    {Object.entries(slotG.member_source).map(([name, source]) => {
                      const kind = slotG.member_period_kind?.[name] || "";
                      const basis = PERIOD_KIND[kind] || "";
                      return (
                        <Fragment key={name}>
                          <dt>{name}</dt>
                          <dd>
                            {source
                              ? `${source}${basis ? `, on a ${basis} basis` : ""}`
                              : basis
                                ? `No return source is on record, and this member reports on a ${basis} basis.`
                                : "No return source is on record for this member."}
                          </dd>
                        </Fragment>
                      );
                    })}
                  </dl>
                )}
                {compositeComputed && composite && (
                  <ComparisonDetail c={composite} glossary={glossary} />
                )}
              </div>
            </Disclosure>

            {compositeComputed && (composite?.rows || []).length > 1 && (
              <PeerChart rows={composite?.rows || []} fundName={fundName}
                compositeName={composite?.candidate || "Peer composite"}
                window={composite?.window || ""} />
            )}

            <PeerTable slotG={slotG} fundName={fundName} sort={psort} />
          </Card>
        </section>
      )}

      {/* ---------------------------------------------- declared record */}
      <section className="stack-4" aria-labelledby="declared">
        <h2 id="declared" className="t-20">What the fund itself names</h2>
        <Card className="stack-4">
          <p className="t-13 t-2">
            The declaration itself earns no points. A comparator a fund prints, or one the rules require it
            to print, is scored on the same rubric as every other candidate.
          </p>
          {(sel.declared || []).length > 0 ? (
            <div className="stack-2">
              {(sel.declared || []).map((d) => {
                const stat = statisticOf(d.comparison);
                return (
                <div key={d.name} className="stack-2">
                  <div className="row-3">
                    <span className="t-14 t-medium">{d.name}</span>
                    {d.type_label && <Chip kind="wrapper">{d.type_label}</Chip>}
                    <Chip kind={d.held ? "structured" : "pending"}>
                      {d.held ? "Series held" : "Series not held"}
                    </Chip>
                    {d.cell && (
                      <CiteButton target={{ productKey: key, fundName, cell: d.cell }}
                        label="Open the row this comparator was read from" />
                    )}
                  </div>
                  <p className="t-13 t-3">{d.status || "No outcome is on record."}</p>
                  {d.comparison_note && <p className="t-13 t-3">{d.comparison_note}</p>}
                  {d.comparison && stat && (
                    <p className="t-13 t-2">
                      <StatName glossary={glossary} term={stat.term}>{stat.label}</StatName>{" "}
                      <span className="t-num">{stat.value}</span>
                      {d.comparison.window ? `, over ${d.comparison.window}` : ""}
                    </p>
                  )}
                </div>
                );
              })}
            </div>
          ) : (
            <p className="t-14">
              {sel.declared_none_reason
                ? `The fund declares no benchmark (${sel.declared_none_reason}).`
                : "The record holds no declared comparator for this fund."}
            </p>
          )}
          {sel.declared_none_reason && (sel.declared || []).length > 0 && (
            <p className="t-13 t-3">
              The fund declares no benchmark ({sel.declared_none_reason}).
            </p>
          )}
        </Card>
      </section>

      {/* ------------------------------------------------------- ledger */}
      <section className="stack-4" aria-labelledby="ledger">
        <h2 id="ledger" className="t-20">Every candidate and what became of it</h2>
        <Card>
          <div className="filterbar" role="group" aria-label="Filter the candidates">
            <Field label="Show" inline>
              {(ids) => (
                <Select ids={ids} small options={roleOptions} value={role}
                  onChange={(e) => setParams({ role: e.target.value })} />
              )}
            </Field>
          </div>
          <p className="t-13 t-3" aria-live="polite">
            Showing {fmtInt(shown.length)} of {fmtInt(ledger.length)} candidates.
            {role && (
              <>{" "}
                <Link to={`/product/${key}/benchmark`} params={{ plan: r.params.get("plan") || undefined }}
                  replace>Show every candidate</Link>
              </>
            )}
          </p>
        </Card>
        <Table
          id="ledger-table"
          caption={`Every candidate scored for ${fundName || "this fund"}, what kind of comparator it is, `
            + "its score and what became of it."}
          columns={LEDGER_COLUMNS}
          rows={shown}
          rowKey={(row) => row.id}
          sort={lsort}
          onSort={(s) => setParams({ lsort: s?.id || null, ldir: s?.dir || null })}
          empty={SAY.emptyFilter} />
        {ties.length > 0 && <p className="t-13 t-3">{rubric.tie_sentence}</p>}
      </section>

      {/* ------------------------------------------------- what was read */}
      <section className="stack-4" aria-labelledby="locked">
        <h2 id="locked" className="t-20">What the selection was read from</h2>
        <Card className="stack-4">
          {sel.inputs?.note && <p className="t-13 t-2">{sel.inputs.note}</p>}
          {(sel.inputs?.accessions || []).length > 0 && (
            <dl className="field-list">
              {(sel.inputs?.accessions || []).map((a) => (
                <Fragment key={a.accession}>
                  <dt>{a.form || "Filing"}{a.filing_date ? `, filed ${fmtDate(a.filing_date)}` : ""}</dt>
                  <dd className="provenance">{a.accession}</dd>
                </Fragment>
              ))}
            </dl>
          )}
          {(sel.inputs?.cells || []).length > 0 && (
            <div className="stack-2">
              <h3 className="t-14 t-semibold">Rows of the record this reads</h3>
              <div className="row-3">
                {(sel.inputs?.cells || []).map((cell) => (
                  <CiteButton key={cell} target={{ productKey: key, fundName, cell }}
                    label="Open the row" />
                ))}
              </div>
            </div>
          )}
          {heldSeries.length > 0 && (
            <div className="stack-2">
              <h3 className="t-14 t-semibold">Series held, each locked by its content</h3>
              <dl className="field-list">
                {heldSeries.map((held) => (
                  <Fragment key={held.lock + held.name}>
                    <dt>{held.name}</dt>
                    <dd className="provenance">{held.lock}</dd>
                  </Fragment>
                ))}
              </dl>
            </div>
          )}
          {recordedAt && recordHash && (
            <p className="t-13 t-3 provenance">
              Selection recorded {fmtDate(recordedAt)}, record {hashPrefix(recordHash)}
            </p>
          )}
        </Card>
      </section>

      <Card sunken>
        <CardHead title="How to read this panel" level={2} />
        <p className="t-13 t-3">
          {SAY.reference}. {SAY.referenceNote} A public market equivalent is only ever a comparison
          against a public market series. The peer composite is appraisal-based and cannot be bought, so
          it is reported as a relative wealth ratio and never as a public market equivalent.{" "}
          {SAY.verificationCount(index.coverage_totals.counts.verified, index.coverage_totals.counts.total)}{" "}
          <Link to="/verification">See the verification queue</Link>
        </p>
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------ peer chart */

function PeerChart({ rows, fundName, compositeName, window: windowLabel }:
  { rows: CompositeRow[]; fundName: string; compositeName: string; window: string }) {
  const usable = rows.filter((row) =>
    typeof row.fund_return_pct === "number" && typeof row.composite_return_pct === "number");
  if (usable.length < 2) return null;
  // the count of members behind the composite is stated only where every
  // period plotted reports the same one, because the sentence says every period
  const counts = usable.map((row) => row.n);
  const members = typeof counts[0] === "number" && counts.every((n) => n === counts[0])
    ? counts[0] : null;
  return (
    <LineChart
      title={`Return by period, this fund beside the peer composite${windowLabel ? `, ${windowLabel}` : ""}`}
      description={"Two lines: the return of the fund in each period, and the equal-weight peer composite "
        + "over the same periods, on identical period boundaries."}
      series={[
        {
          id: "fund", label: fundName || "This fund",
          points: usable.map((row) => ({ x: row.period, y: row.fund_return_pct as number })),
        },
        {
          id: "peers", label: compositeName,
          points: usable.map((row) => ({ x: row.period, y: row.composite_return_pct as number })),
        },
      ]}
      yFormat={(v) => fmtPct(v)}
      footer={"Each point is the return of that period on its own, never a cumulative figure."
        + (members !== null ? ` Peers reporting every period shown: ${fmtN(members)}.` : "")} />
  );
}

/* ------------------------------------------------------------ peer table */

function PeerTable({ slotG, fundName, sort }:
  { slotG: SlotG; fundName: string; sort: SortState | null }) {
  const rows = slotG.table || [];
  const names = useMemo(() => {
    const seen: string[] = [];
    for (const row of rows) {
      for (const name of Object.keys(row.returns || {})) if (!seen.includes(name)) seen.push(name);
    }
    return seen;
  }, [rows]);

  const columns = useMemo<Column<PeerRow>[]>(() => {
    const out: Column<PeerRow>[] = [{
      id: "period", header: "Period", label: "Period", fixed: true,
      sortValue: (row) => row.period,
      cell: (row) => (
        <span className="t-13">
          {row.label}
          {row.period_kind && PERIOD_KIND[row.period_kind] && row.period_kind !== "fiscal_year"
            ? ` (${PERIOD_KIND[row.period_kind]})` : ""}
        </span>
      ),
    }];
    // the index carries the fund's full registered name and the cohort table
    // its short one, so the column is marked on either
    const short = fundName.split(" (")[0].trim();
    names.forEach((name, i) => {
      const isFund = !!fundName && (name === fundName || (!!short && name === short));
      const header = isFund ? `${name} (this fund)` : name;
      out.push({
        id: `m${i}`, header, label: header, numeric: true,
        sortValue: (row) => (typeof row.returns[name] === "number" ? (row.returns[name] as number) : null),
        cell: (row) => (typeof row.returns[name] === "number"
          ? <span className="t-num">{fmtPct(row.returns[name] as number)}</span>
          : <span className="t-13 t-3">Not on record</span>),
      });
    });
    out.push({
      id: "n", header: "Reporting", label: "Members reporting", numeric: true,
      sortValue: (row) => (typeof row.n === "number" ? row.n : null),
      cell: (row) => <span className="t-num">{typeof row.n === "number" ? fmtN(row.n) : "Not on record"}</span>,
    });
    return out;
  }, [names, fundName]);

  if (rows.length === 0) {
    return (
      <EmptyState title="No peer periods on record">
        This cohort carries no side-by-side periods. One appears when two or more members of the cohort
        file a return for the same period.
      </EmptyState>
    );
  }

  return (
    <div data-peer-table="true">
      <Table
        id="peers"
        caption={`${slotG.cohort_label || "The cohort"} side by side, each period on identical boundaries, `
          + `with the number of members reporting it.`}
        columns={columns}
        rows={rows}
        rowKey={(row) => row.period}
        sort={sort}
        onSort={(s) => setParams({ psort: s?.id || null, pdir: s?.dir || null })}
        maxHeight="var(--table-max)"
        empty="No period is on record for this cohort." />
    </div>
  );
}

/* ---------------------------------------------------------------- ledger */

interface LedgerRow {
  id: string;
  role: string;
  slot: string;
  candidate: string;
  lane: string;
  score: string;
  scoreValue: number | null;
  outcome: string;
  tied: boolean;
}

const LEDGER_COLUMNS: Column<LedgerRow>[] = [
  {
    id: "slot", header: "Role", label: "Role", fixed: true,
    sortValue: (row) => row.slot,
    cell: (row) => <span className="t-13">{row.slot}</span>,
  },
  {
    id: "candidate", header: "Candidate", label: "Candidate",
    sortValue: (row) => row.candidate,
    cell: (row) => (
      <span className="row-3">
        <span>{row.candidate}</span>
        {row.tied && <Chip kind="partial">Tied</Chip>}
      </span>
    ),
  },
  {
    id: "lane", header: "Kind of comparator", label: "Kind of comparator",
    sortValue: (row) => row.lane,
    cell: (row) => <span className="t-13 t-2">{row.lane}</span>,
  },
  {
    id: "score", header: "Score", label: "Score", numeric: true,
    sortValue: (row) => row.scoreValue,
    cell: (row) => <span className="t-num">{row.score}</span>,
  },
  {
    id: "outcome", header: "Outcome", label: "Outcome",
    cell: (row) => <span className="t-13 t-2">{row.outcome}</span>,
  },
];

/** One ledger row per candidate: the selected slot, the reference, each
 *  comparator the fund or the rules name, the peer slot, then the rest. */
function ledgerRows(sel: Selection | null, index: IndexView | null): LedgerRow[] {
  if (!sel || !index) return [];
  const rubric = index.rubric;
  const lane = (id?: string) => (id && index.labels.lane[id]) || "";
  const score = (v: number | null | undefined) =>
    (v === null || v === undefined ? "Not scored" : fmtOf(v, rubric.max));
  const out: LedgerRow[] = [];
  const slotK = sel.slot_k || {};
  const kLabel = slotK.label || index.labels.slot.slot_k || "Meaningful benchmark";
  const picked = slotK.selected;

  if (picked) {
    const stat = statisticOf(picked.comparison);
    out.push({
      id: "k", role: "selected", slot: kLabel, candidate: picked.candidate,
      lane: lane(picked.lane), score: score(picked.score), scoreValue: picked.score ?? null, tied: false,
      outcome: stat && picked.comparison
        ? `${stat.label} ${stat.value}, over ${picked.comparison.window || "the window on record"}`
        : (picked.by_descriptor ? rubric.by_descriptor_sentence : "")
          || picked.comparison_note || "Selected, no comparison computed.",
    });
  } else if (slotK.escalation) {
    out.push({
      id: "k", role: "selected", slot: kLabel, candidate: "None", lane: "", score: "Not scored",
      scoreValue: null, tied: false, outcome: slotK.escalation,
    });
  }

  const reference = sel.reference_comparison;
  if (reference) {
    const stat = statisticOf(reference.comparison);
    out.push({
      id: "reference", role: "selected", slot: SAY.reference, candidate: reference.candidate,
      lane: lane(reference.lane), score: score(reference.score), scoreValue: reference.score ?? null,
      tied: false,
      outcome: stat && reference.comparison
        ? `${stat.label} ${stat.value}, over ${reference.comparison.window || "the window on record"}`
        : reference.note || SAY.referenceNote,
    });
  }

  (sel.declared || []).forEach((d, i) => {
    out.push({
      id: `declared-${i}`, role: "declared",
      slot: d.type_label ? d.type_label.charAt(0).toUpperCase() + d.type_label.slice(1) : "Named by the fund",
      candidate: d.name, lane: index.labels.lane.A || "", score: "Scored on the same rubric",
      scoreValue: null, tied: false,
      outcome: d.status || d.comparison_note || "No outcome is on record.",
    });
  });

  const slotG = sel.slot_g;
  if (slotG) {
    const composite = slotG.composite || {};
    const stat = composite.status === "computed" ? statisticOf(composite) : null;
    out.push({
      id: "g", role: "peer", slot: slotG.label || index.labels.slot.slot_g || "Peer comparison",
      candidate: composite.candidate || slotG.cohort_label || "Peer cohort",
      lane: "Peer cohort", score: "Not scored", scoreValue: null, tied: false,
      outcome: stat
        ? `${stat.label} ${stat.value}, over ${composite.window || "the periods on record"}`
        : composite.status === "computed"
          ? "A composite is on record for this cohort, and the record computes no ratio from it."
          : `Composite refused: ${composite.reason || "no reason is on record."}`,
    });
  }

  (sel.rejected || []).forEach((rj, i) => {
    out.push({
      id: `rejected-${i}`, role: "rejected", slot: "Not selected", candidate: rj.candidate,
      lane: lane(rj.lane), score: score(rj.score), scoreValue: rj.score ?? null,
      tied: rj.tied === true,
      outcome: rj.rejection || "No reason is on record.",
    });
  });

  return out;
}

/* The documents panel: what a committee takes away for one fund and one plan.
 *
 * Two documents and nothing else. The Investment Selection Record carries the
 * fund’s figures with the filing behind each one, and Attachment A carries the
 * text of the rule word for word, so the record and the rule it answers are
 * read side by side. Both links are real files beside the deployed page,
 * addressed from the document’s own base so the site root and a preview under
 * a subpath both resolve. The reader meets each document by its name in words
 * and never by the name it is stored under.
 *
 * Nothing here is claimed beyond what the record holds. Where the selection
 * carries the date it was recorded and the hash of the recorded document, the
 * panel says so and prints both. Where it does not, the panel says the
 * selection is not locked rather than describing a lock that is not there. The
 * same applies to the contents: the sections are printed only where the record
 * lists them.
 *
 * The two documents are written for the selected plan, so the panel depends on
 * the plan and says so.
 *
 * No h1: the product header above this panel supplies it. */
import { useRoute } from "../app/router";
import { planLabel, usePlan } from "../app/plan";
import { Card, CardHead, EmptyState, Icon, Link, Skeleton } from "../components/primitives";
import { SAY } from "../copy/copy";
import { useAsync, useIndex } from "../data/hooks";
import { data } from "../data/index";
import { fmtDate, hashPrefix } from "../format/format";
import type { DocumentsView as DocumentsShape, SelectionView } from "../data/types";

/* ------------------------------------------------------------- the shapes */
/* The documents chunk names the two files and the verification state. A later
 * record may also list the sections of the document, in the order it wrote
 * them, and the contents list prints them where it does. Both are optional,
 * because the record here carries neither and the panel says so rather
 * than inventing a list. */
interface DocumentsChunk extends DocumentsShape {
  sections?: string[];
  contents?: string[];
}

/* The selection chunk arrives as an open record. The two fields the lock line
 * needs are named here rather than in the shared types. */
interface Lock {
  recorded_at?: string;
  record_hash?: string;
}

/** A document beside the built site, addressed from the document’s own base,
 *  so the same page serves the site root and a preview under a subpath. */
function memoHref(name: string): string {
  return new URL("memos/" + name, document.baseURI).toString();
}

/** A section name is printed only where it reads as a reader’s words. An
 *  entry that carries an internal key, a path or a file name is skipped
 *  rather than printed under a name that is not a reader’s. */
function readerWords(part: string): boolean {
  const s = (part || "").trim();
  if (!s || s.includes("_") || s.includes("/")) return false;
  return /[A-Za-z]{2,}\s+[A-Za-z]{2,}/.test(s);
}

/** One real download: the document named in reader words, the link, and one
 *  sentence saying what is inside it. */
function Download({ name, title, note, label }:
  { name: string; title: string; note: string; label: string }) {
  return (
    <div className="download">
      <div className="download__row">
        <Icon name="document" />
        <span className="download__name">{title}</span>
        <span className="spacer" />
        {/* a download is a primary action, not a word inside a sentence: it
            gets a control's hit target rather than a line box's */}
        <Link href={memoHref(name)} download aria-label={label} className="btn btn--secondary">
          <Icon name="download" size="sm" />Download
        </Link>
      </div>
      <div className="download__meta">{note}</div>
    </div>
  );
}

/* ------------------------------------------------------------- the panel */
export default function DocumentsView() {
  const r = useRoute();
  const key = decodeURIComponent(r.segments[1] || "");
  const { value: index, error: indexError, loading: indexLoading } = useIndex();
  const [plan] = usePlan(index);

  const { value: docs, error, loading } = useAsync<DocumentsChunk | null>(
    () => (plan && key ? data().getDocuments(plan, key) : Promise.resolve(null)), [plan, key]);
  const { value: selection, error: selectionError, loading: selectionLoading } =
    useAsync<SelectionView | null>(
      () => (key ? data().getSelection(key) : Promise.resolve(null)), [key]);

  if (error || indexError) {
    return <EmptyState title={SAY.noRecord}>{error || indexError}</EmptyState>;
  }
  if (indexLoading || loading || !index) {
    return <Skeleton lines={8} label={SAY.loadingRecord} />;
  }
  if (!plan) {
    return (
      <EmptyState title={SAY.noRecord}>
        No reference plan is on file here, and these two documents are written for one plan at a time.
      </EmptyState>
    );
  }
  if (!docs) {
    return (
      <EmptyState title={SAY.noRecord}>
        Choosing a plan from the list fills this panel with the documents written for it.
      </EmptyState>
    );
  }

  const fundName = index.products.find((p) => p.key === key)?.fund_name || "";
  const label = planLabel(index, plan);
  const contents = (docs.sections || docs.contents || []).filter(readerWords);
  const lock = ((selection?.selection || null) as unknown) as Lock | null;
  const recordedAt = lock?.recorded_at || "";
  const recordHash = lock?.record_hash || "";
  const locked = Boolean(recordedAt && recordHash);
  const forWhom = fundName ? `${fundName} and ${label}` : label;

  return (
    <div className="stack-5">
      <section className="stack-4" aria-labelledby="docs-what">
        <h2 id="docs-what" className="t-20">The Investment Selection Record</h2>
        <p className="t-14 t-2">
          The Investment Selection Record is the document a committee keeps: one fund, one plan, and every
          figure it states shown with the filing it was read from, the section of that filing and the sentence
          itself. The text of the rule is attached word for word, so the record and the rule it answers are
          read together. {SAY.planDependent} This one is written for {label}.
        </p>
      </section>

      <section className="stack-4" aria-labelledby="docs-files">
        <h2 id="docs-files" className="t-20">What you can take away</h2>

        <Card as="article" className="stack-2">
          <CardHead title="Investment Selection Record" level={3} />
          {docs.record ? (
            <Download
              name={docs.record}
              title="Investment Selection Record"
              note={`Written for ${forWhom}. Every figure in it names the document, the section and the sentence it was read from.`}
              label={`Download the Investment Selection Record for ${forWhom}`}
            />
          ) : (
            <p className="t-13 t-3">No Investment Selection Record has been written for this fund and this plan.</p>
          )}
        </Card>

        <Card as="article" className="stack-2">
          <CardHead title="Attachment A, the rule text" level={3} />
          {docs.attachment ? (
            <Download
              name={docs.attachment}
              title="Attachment A, the rule text"
              note={`The verbatim text of paragraphs ${index.rule.paragraphs} of the proposed rule, attached to the record so the reader holds one against the other.`}
              label={`Download Attachment A, the rule text, beside the record for ${forWhom}`}
            />
          ) : (
            <p className="t-13 t-3">Attachment A, the rule text, is not attached here.</p>
          )}
        </Card>
      </section>

      <section className="stack-4" aria-labelledby="docs-contents">
        <h2 id="docs-contents" className="t-20">What is inside the record</h2>
        {contents.length > 0 ? (
          <ol className="stack-2">
            {contents.map((part, i) => <li key={`${i}-${part}`} className="t-14 t-2">{part}</li>)}
          </ol>
        ) : (
          <p className="t-14 t-2">
            The contents are not listed here. Open the document to read its sections in the order
            it sets them out.
          </p>
        )}
      </section>

      <section className="stack-4" aria-labelledby="docs-lock">
        <h2 id="docs-lock" className="t-20">The selection behind it</h2>
        {selectionLoading ? (
          <Skeleton lines={2} label={SAY.loadingRecord} />
        ) : selectionError ? (
          <p className="t-14 t-2">{selectionError}</p>
        ) : locked ? (
          <Card className="stack-2">
            <p className="t-14 t-2">
              The benchmark selection this record rests on carries the date it was recorded and a hash of the
              recorded document, so a reader can tell whether what is in front of them is what was recorded.
            </p>
            <p className="t-13 t-3 provenance" data-lock="true">
              Selection recorded {fmtDate(recordedAt)}, record {hashPrefix(recordHash)}
            </p>
          </Card>
        ) : (
          <p className="t-14 t-2">The selection is not locked: no decision date and no record fingerprint are on file for it.</p>
        )}
      </section>

      <section className="stack-4" aria-labelledby="docs-open">
        <h2 id="docs-open" className="t-20">The figures on screen</h2>
        <p className="t-14 t-2">
          Every figure the document carries is on this site as well, on the row it was read from. Open a row
          to read the document, the section and the sentence behind it.
        </p>
        <div className="row-3">
          <Link to={`/product/${key}/record`} params={{ plan }}>Open the record</Link>
          <Link to={`/product/${key}/benchmark`} params={{ plan }}>Open the benchmark panel</Link>
        </div>
      </section>

      <Card sunken>
        <CardHead title="How to read these documents" level={2} />
        <p className="t-14 t-2">
          Nothing in either document is a legal conclusion. The record answers paragraphs{" "}
          {index.rule.paragraphs} of {index.rule.citation}, and the attachment carries that text unedited.
        </p>
        <p className="t-13 t-3" aria-live="polite">
          {SAY.verificationPending}{" "}
          {SAY.verificationCount(index.coverage_totals.counts.verified || 0,
            index.coverage_totals.counts.total || 0)}{" "}
          <Link to="/verification">See the verification queue</Link>
        </p>
      </Card>
    </div>
  );
}

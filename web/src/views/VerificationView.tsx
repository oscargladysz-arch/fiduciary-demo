/* The verification queue: what a person would sign, in the order the queue
 * sets, and the request a person produces.
 *
 * Nothing on this route can sign a row. There is no control that marks a cell
 * signed, no hidden form waiting per row, and no wording that lets a second
 * automated pass stand in for a person. The one thing a reader can do here is
 * fill in a single form and take away a small request file for whoever runs
 * the signing.
 *
 * The old page carried one hidden form per row, fifty of them in the
 * document at once. This carries one, inside a dialog, opened by the row a
 * reader chose, and it closes with the dialog.
 *
 * The count of signed rows comes from the record itself and it is zero. Every sentence
 * about it comes from the copy layer, so the queue, the record and the packet
 * cannot say different things about the same number. */
import { useMemo, useState } from "react";
import { CiteButton } from "../components/citation";
import { DateInput, Field, FileDownload, Input, Textarea, useUnsavedGuard } from "../components/form";
import { Dialog } from "../components/overlay";
import { Button, Card, CardHead, Chip, EmptyState, Legend, Link, Skeleton, Stat, StatRow, VerdictBanner }
  from "../components/primitives";
import { PageHeader } from "../components/shell";
import { Table } from "../components/table";
import type { Column } from "../components/table";
import { SAY, TIERS, routeTitle, status as statusCopy } from "../copy/copy";
import { useAsync, useIndex } from "../data/hooks";
import { data } from "../data/index";
import { fmtDate, fmtInt } from "../format/format";
import type { VerificationRow, VerificationView as VerificationShape } from "../data/types";

/* What a row prints where the record left a field empty: the reason, never a
 * bare dash and never a guess. */
const NO_ELEMENT = "The name of this row is not on record.";
const NO_DOCUMENT = "The document behind this row is not named on the queue.";

/* A group the queue orders but gives no title, and the rows it orders under
 * no group at all. Both say what they are in plain words. */
const UNTITLED_GROUP = "A group the queue orders without a title of its own";
const OUTSIDE_GROUP = "Rows the queue does not place in a group";

interface Group { id: string; title: string; rows: VerificationRow[] }

/** The queue in the order it was written, cut into its groups: the numbered
 *  ones first, lowest first, and whatever the queue left ungrouped last. */
function groupsOf(queue: VerificationShape | null): Group[] {
  if (!queue) return [];
  const held = new Map<string, VerificationRow[]>();
  for (const row of queue.rows) {
    const id = typeof row.tier === "number" ? String(row.tier) : "";
    const there = held.get(id);
    if (there) there.push(row); else held.set(id, [row]);
  }
  const numbered = [...held.keys()].filter((k) => k !== "").sort((a, b) => Number(a) - Number(b));
  const out: Group[] = numbered.map((id) => ({
    id,
    title: (queue.tiers || {})[id] || UNTITLED_GROUP,
    rows: held.get(id) || [],
  }));
  const loose = held.get("");
  if (loose && loose.length) out.push({ id: "ungrouped", title: OUTSIDE_GROUP, rows: loose });
  return out;
}

/** A file name a person can find again, from the fund and the row. */
function slug(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
}

/* --------------------------------------------------------- the one form */

interface Draft { signer: string; role: string; date: string; note: string }
const EMPTY: Draft = { signer: "", role: "", date: "", note: "" };

/** The single signature request form. It is mounted only while its dialog is
 *  open, for the one row the reader chose, and it writes a file. It cannot
 *  sign anything: the file is what the person who signs works from. */
function RequestForm({ row, onClose }: { row: VerificationRow; onClose: () => void }) {
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [submitted, setSubmitted] = useState(false);
  const set = (k: keyof Draft, v: string) => setDraft((d) => ({ ...d, [k]: v }));

  const dirty = Object.values(draft).some((v) => v.trim() !== "");
  useUnsavedGuard(dirty);

  const errors: Record<string, string> = {
    signer: draft.signer.trim() ? "" : "Enter the name of the person who will sign this row.",
    role: draft.role.trim() ? "" : "Enter the role that person holds.",
    date: draft.date ? "" : "Choose the date the signature is planned for.",
  };
  const needing = Object.values(errors).filter(Boolean).length;
  const ready = submitted && needing === 0;

  const text = useMemo(() => JSON.stringify({
    fund: row.fund_name,
    cell: row.cell,
    signer: draft.signer.trim(),
    role: draft.role.trim(),
    date: draft.date,
    note: draft.note.trim(),
  }, null, 2), [row, draft]);

  const name = `signature-request-${slug(row.fund_name)}-${slug(row.cell)}`;
  const live = !submitted ? ""
    : needing === 0 ? "Every field checks out. The request is ready below."
      : `${fmtInt(needing)} ${needing === 1 ? "field needs" : "fields need"} attention.`;

  return (
    <div className="stack-4">
      <dl className="field-list">
        <dt>Fund</dt>
        <dd translate="no">{row.fund_name}</dd>
        <dt>Row</dt>
        <dd><span translate="no">{row.cell}</span>{row.element ? `, ${row.element}` : ""}</dd>
        <dt>Document</dt>
        <dd>{row.source || NO_DOCUMENT}</dd>
        {row.section && (<><dt>Where in the document</dt><dd>{row.section}</dd></>)}
      </dl>

      <p className="t-14 t-2">
        Nothing here signs the row. This writes the request that the person who signs works from, and the
        record stays exactly as it is until they have signed.
      </p>

      <form className="stack-4" noValidate onSubmit={(e) => { e.preventDefault(); setSubmitted(true); }}>
        <Field label="Name of the person who will sign" required
          hint="The signature carries a name, so the row can be traced back to a person."
          error={submitted ? errors.signer : undefined}>
          {(ids) => <Input ids={ids} value={draft.signer} spellCheck={false}
            onChange={(e) => set("signer", e.target.value)} />}
        </Field>
        <Field label="Role that person holds" required
          hint="What lets them sign for the plan, in their own words."
          error={submitted ? errors.role : undefined}>
          {(ids) => <Input ids={ids} value={draft.role} spellCheck={false}
            onChange={(e) => set("role", e.target.value)} />}
        </Field>
        <Field label="Date the signature is planned for" required
          error={submitted ? errors.date : undefined}>
          {(ids) => <DateInput ids={ids} value={draft.date} onChange={(e) => set("date", e.target.value)} />}
        </Field>
        <Field label="Note for the person who signs"
          hint="Optional. Anything they should know before they open the filing.">
          {(ids) => <Textarea ids={ids} rows={3} value={draft.note}
            onChange={(e) => set("note", e.target.value)} />}
        </Field>

        <div className="form-actions">
          <Button variant="primary" size="md" type="submit">Check the form and write the request</Button>
          <Button variant="secondary" onClick={() => { setDraft(EMPTY); setSubmitted(false); }}>Start again</Button>
          <Button variant="quiet" onClick={onClose}>Close</Button>
        </div>
        <p className="t-13 t-3" aria-live="polite">{live}</p>
      </form>

      {ready && (
        <FileDownload name={name} text={text} label="Download the signature request"
          description={`Planned for ${fmtDate(draft.date)}. It carries the fund, the row, the person who will `
            + `sign, their role, the date and the note, and nothing else.`} />
      )}
    </div>
  );
}

/* ------------------------------------------------------------- the queue */

/** The columns of one group. The request button opens the one dialog: no row
 *  carries a form of its own. */
function columnsOf(onPrepare: (row: VerificationRow) => void): Column<VerificationRow>[] {
  return [
    {
      id: "fund", header: "Fund", label: "Fund", fixed: true,
      cell: (row) => (
        <Link to={`/product/${row.product_key}/record`} params={{ factor: row.cell.split(".")[0] }} translate="no">
          {row.fund_name}
        </Link>
      ),
    },
    {
      id: "row", header: "Row", label: "Row",
      cell: (row) => (
        <span className="row-3">
          <span className="t-eyebrow" translate="no">{row.cell}</span>
          <span className={row.element ? "t-14" : "t-13 t-3"}>{row.element || NO_ELEMENT}</span>
        </span>
      ),
    },
    {
      id: "tier", header: "Tier of this row", label: "Tier of this row",
      cell: (row) => {
        const st = statusCopy(row.status);
        return (
          <span className="row-3">
            <Chip kind={st.kind}>{st.label}</Chip>
            {st.tier && <Chip kind="tier">{st.tier}</Chip>}
          </span>
        );
      },
    },
    {
      id: "document", header: "Document", label: "Document",
      cell: (row) => <span className={row.source ? "t-13 t-2" : "t-13 t-3"}>{row.source || NO_DOCUMENT}</span>,
    },
    {
      id: "cite", header: "Source", label: "Source",
      cell: (row) => (
        <CiteButton target={{ productKey: row.product_key, fundName: row.fund_name, cell: row.cell }} />
      ),
    },
    {
      id: "request", header: "Signature request", label: "Signature request",
      cell: (row) => (
        <Button icon="document" aria-haspopup="dialog" onClick={() => onPrepare(row)}
          aria-label={`Prepare a signature request for ${row.cell}, ${row.element || "row"}, ${row.fund_name}`}>
          Prepare a signature request
        </Button>
      ),
    },
  ];
}

export default function VerificationView() {
  const { value: index, error: indexError, loading: indexLoading } = useIndex();
  const { value: queue, error, loading } = useAsync<VerificationShape | null>(() => {
    const source = data();
    return source.getVerification ? source.getVerification() : Promise.resolve(null);
  }, []);
  const [target, setTarget] = useState<VerificationRow | null>(null);

  const groups = useMemo(() => groupsOf(queue), [queue]);
  const columns = useMemo(() => columnsOf(setTarget), []);

  /* The rows a person could sign, added up from the count the record holds per
   * fund, and the funds those counts cover. */
  const couldBeSigned = useMemo(() => Object.values(queue?.verifiable || {})
    .reduce((a, b) => a + (typeof b === "number" ? b : 0), 0), [queue]);
  const funds = Object.keys(queue?.verifiable || {}).length;
  /* The denominator every other surface uses: the cells the record holds. */
  const cells = Number(index?.coverage_totals.total ?? 0);

  const body = () => {
    if (error || indexError) return <EmptyState title={SAY.noRecord}>{error || indexError}</EmptyState>;
    if (loading || indexLoading) return <Skeleton lines={10} label={SAY.loadingRecord} />;
    if (!queue || !index) {
      return (
        <EmptyState title={SAY.noRecord}>
          This page reads the queue that comes with the record, and the record this page is reading does not
          carry one.
        </EmptyState>
      );
    }

    return (
      <>
        <VerdictBanner kind="pending" label={SAY.verificationPending}
          definition={SAY.verificationCount(queue.signed, cells)} />

        <StatRow>
          <Stat label="Rows signed by a person" value={fmtInt(queue.signed)} source={SAY.verificationPending} />
          <Stat label="Rows that could be signed" value={fmtInt(couldBeSigned)}
            source={`Across ${fmtInt(funds)} funds, each row read from a filing with the sentence on record.`} />
          <Stat label="In the queue now" value={fmtInt(queue.rows.length)}
            source="The rows the queue puts in front of a person first." />
        </StatRow>

        <p className="t-13 t-3" aria-live="polite">
          {fmtInt(queue.rows.length)} rows are in the queue, in {fmtInt(groups.length)}{" "}
          {groups.length === 1 ? "group" : "groups"}.
        </p>

        <Card className="stack-2">
          <CardHead title="What a signature means here" level={2} />
          <p className="t-14 t-2">
            A signature is a named person saying that they opened the filing, read the row against it, and
            found that the two agree. It carries that person’s name, their role and the date they signed.
          </p>
          <p className="t-14 t-2">
            {fmtInt(queue.signed)} of the rows on this record carry one. A second automated pass over the same
            filing is not a signature and moves no count.
          </p>
          <p className="t-14 t-2">
            Signing is done by a person away from this page. What this page can do is write the request that
            person works from. The queue itself arrives with the record, and it lists the rows the record has
            read from a filing and holds as not yet signed.
          </p>
        </Card>

        {queue.rows.length === 0 ? (
          <EmptyState title="The queue is empty">
            Nothing is waiting for a person to sign. A row joins this queue when the record reads it from a
            filing and holds it as not yet signed.
          </EmptyState>
        ) : groups.map((g) => (
          <section key={g.id} className="stack-4" aria-labelledby={`queue-${g.id}`}>
            <h2 id={`queue-${g.id}`} className="t-20">{g.title}</h2>
            <p className="t-13 t-3">
              {fmtInt(g.rows.length)} {g.rows.length === 1 ? "row" : "rows"}, in the order the queue sets.
            </p>
            <Table
              caption={`${fmtInt(g.rows.length)} rows of the queue under ${g.title}, in the order the queue sets. `
                + SAY.verificationPending}
              columns={columns}
              rows={g.rows}
              rowKey={(row) => `${row.product_key}:${row.cell}`}
              empty="No row of the queue sits under this heading."
            />
          </section>
        ))}

        <Card className="stack-2">
          <CardHead title="What happens next" level={2} />
          <p className="t-14 t-2">
            The file goes to whoever runs the signing. They open the filing, read the row against it, and sign
            it under their own name and role.
          </p>
          <p className="t-14 t-2">
            The count on this page, and the same count on every other page, moves only once a person has
            signed. Taking a request file away changes nothing on its own.
          </p>
        </Card>

        <Card sunken>
          <CardHead title="How to read this queue" level={2} />
          <Legend label="Tiers" items={TIERS.map((t, i) => ({
            label: t.label, kind: (["structured", "extracted", "verified"] as const)[i],
          }))} />
          <p className="t-13 t-3">
            {SAY.verificationPending} {SAY.verificationCount(queue.signed, cells)}{" "}
            <Link to="/screener">Open the screener</Link>
          </p>
        </Card>
      </>
    );
  };

  return (
    <div className="stack-5">
      <PageHeader
        title={routeTitle("verification")}
        sub={"Every row here has been read from a filing and is waiting for a person to sign it. Signing "
          + "happens away from this page, so nothing on this page can mark a row as signed."}
      />

      {body()}

      {target && (
        <Dialog open onClose={() => setTarget(null)}
          title={`Signature request for ${target.cell}, ${target.fund_name}`}>
          <RequestForm row={target} onClose={() => setTarget(null)} />
        </Dialog>
      )}
    </div>
  );
}

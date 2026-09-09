/* The citation (R3-P1-10). One button and one drawer, used by every surface
 * that shows a figure read from a filing.
 *
 * The button is an icon and a label, and its accessible name says which cell
 * it opens, so fifty of them on one page are fifty distinct names rather than
 * fifty identical glyphs. The drawer carries the document, the section, the
 * verbatim sentence, who extracted it, the verification state and a link to
 * every filing the accession resolves to. Every link comes from the manifest
 * through the record chunk, never assembled here (rule 15).
 *
 * The text arrives with the product’s own record chunk, so a page of sixteen
 * products does not carry sixteen records until a reader opens one. */
import { useState } from "react";
import { Drawer } from "./overlay";
import { Button, Chip, EmptyState, Icon, Link, Skeleton } from "./primitives";
import { SAY, status as statusCopy } from "../copy/copy";
import { useAsync } from "../data/hooks";
import { data } from "../data/index";
import { fmtDate } from "../format/format";
import type { Cell } from "../data/types";

export interface CiteTarget { productKey: string; fundName: string; cell: string }

function Body({ target }: { target: CiteTarget }) {
  const { value: record, error, loading } = useAsync(
    () => data().getRecord(target.productKey), [target.productKey]);
  if (error) return <EmptyState title={SAY.noRecord}>{error}</EmptyState>;
  if (loading || !record) return <Skeleton lines={5} label={SAY.loadingRecord} />;
  const cell: Cell | undefined = record.cells[target.cell];
  if (!cell) {
    return <EmptyState title={SAY.noRecord}>No row with that name has been published for this fund.</EmptyState>;
  }
  const st = statusCopy(cell.status);
  return (
    <div className="stack-4">
      <div className="row">
        <Chip kind={st.kind}>{st.label}</Chip>
        {st.tier && <Chip kind="tier">{st.tier}</Chip>}
      </div>
      <p className="t-13 t-2">{st.definition}</p>

      <dl className="field-list">
        <dt>Element</dt>
        <dd>{cell.element || target.cell}</dd>
        <dt>Value on record</dt>
        <dd>{cell.display?.plain || cell.value}</dd>
        {cell.source && (<><dt>Document</dt><dd>{cell.source}</dd></>)}
        {cell.section && (<><dt>Section</dt><dd>{cell.section}</dd></>)}
        {cell.extracted_by && (<><dt>Read by</dt><dd>{cell.extracted_by}</dd></>)}
        <dt>Signed by</dt>
        <dd>{cell.verified_by || "Nobody yet. Human verification is pending."}</dd>
      </dl>

      {cell.quote && (
        <blockquote className="quote">
          <p>{cell.quote}</p>
        </blockquote>
      )}

      {cell.accession && (
        <p className="t-13 t-3 provenance">{cell.accession}</p>
      )}

      {cell.edgar && cell.edgar.length > 0 && (
        <div className="stack-2">
          <h3 className="t-14 t-semibold">Open the filing</h3>
          <ul className="field-list">
            {cell.edgar.map((f) => (
              <li key={f.accession + f.url}>
                <Link href={f.url} external>
                  {f.form}{f.filing_date ? `, filed ${fmtDate(f.filing_date)}` : ""}
                  <Icon name="external" size="sm" />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** The citation button. `cell` is the row it opens, and the accessible name
 *  says so, because a page carries many of these. */
export function CiteButton({ target, label = "Open the citation", compact }:
  { target: CiteTarget; label?: string; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const name = `${label} for ${target.cell}, ${target.fundName}`;
  return (
    <>
      {compact
        ? <Button variant="icon" icon="cite" label={name} onClick={() => setOpen(true)} aria-haspopup="dialog" />
        : <Button variant="quiet" icon="cite" onClick={() => setOpen(true)} aria-label={name} aria-haspopup="dialog">Source</Button>}
      <Drawer open={open} onClose={() => setOpen(false)}
        title={`${target.cell}, ${target.fundName}`}>
        <Body target={target} />
      </Drawer>
    </>
  );
}

/** What a surface shows where the record has no figure: the reason, never a
 *  bare dash, and the citation where a cell was attempted. */
export function NoFigure({ reason, target }: { reason?: string; target?: CiteTarget }) {
  return (
    <span className="row-3">
      <span className="t-13 t-3">{reason || "Not on record"}</span>
      {target && <CiteButton target={target} compact />}
    </span>
  );
}

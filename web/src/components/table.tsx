/* Table: sticky header, sticky first column, sortable header buttons with
 * aria-sort, tabular figures, row virtualization above 50 rows, a column
 * picker, a responsive card layout under 720 px, an empty state and a caption. */
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Button, Icon } from "./primitives";
import { Checkbox } from "./form";
import { Disclosure } from "./overlay";

export interface Column<Row> {
  id: string;
  header: ReactNode;
  /** the plain-text header for the card layout's data-label and the column picker */
  label: string;
  cell: (row: Row) => ReactNode;
  /** a value to sort on, null sorts last */
  sortValue?: (row: Row) => number | string | null;
  numeric?: boolean;
  /** cannot be hidden by the picker */
  fixed?: boolean;
  width?: string;
}
export interface SortState { id: string; dir: "asc" | "desc" }

export function sortRows<Row>(rows: Row[], columns: Column<Row>[], sort: SortState | null): Row[] {
  if (!sort) return rows;
  const col = columns.find((c) => c.id === sort.id);
  if (!col?.sortValue) return rows;
  const dir = sort.dir === "desc" ? -1 : 1;
  return [...rows].sort((a, b) => {
    const av = col.sortValue!(a), bv = col.sortValue!(b);
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    if (typeof av === "string" || typeof bv === "string") return String(av).localeCompare(String(bv)) * dir;
    return (av - bv) * dir;
  });
}

interface TableProps<Row> {
  caption: ReactNode;
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  sort?: SortState | null;
  onSort?: (s: SortState | null) => void;
  visible?: string[] | null;
  onVisible?: (ids: string[] | null) => void;
  empty?: ReactNode;
  cards?: boolean;
  dense?: boolean;
  /** virtualize above this many rows */
  virtualAbove?: number;
  maxHeight?: string;
  id?: string;
}
export function Table<Row>({ caption, columns, rows, rowKey, sort = null, onSort, visible = null, onVisible, empty = "Nothing to show", cards = true, virtualAbove = 50, maxHeight, id }: TableProps<Row>) {
  const cols = useMemo(() => columns.filter((c) => c.fixed || !visible || visible.includes(c.id)), [columns, visible]);
  const sorted = useMemo(() => sortRows(rows, columns, sort), [rows, columns, sort]);
  const virtual = sorted.length > virtualAbove;
  const wrapRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: virtual ? sorted.length : 0,
    getScrollElement: () => wrapRef.current,
    estimateSize: () => 40,
    overscan: 12,
  });
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const bp = getComputedStyle(document.documentElement).getPropertyValue("--bp-table-cards").trim();
    if (!bp) return;
    const mq = window.matchMedia(`(max-width: ${bp})`);
    const on = () => setNarrow(mq.matches);
    on(); mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  const useVirtual = virtual && !narrow;
  const toggleSort = (c: Column<Row>) => {
    if (!c.sortValue || !onSort) return;
    if (sort?.id === c.id) onSort(sort.dir === "asc" ? { id: c.id, dir: "desc" } : null);
    else onSort({ id: c.id, dir: "asc" });
  };
  const header = (
    <thead>
      <tr>
        {cols.map((c) => {
          const active = sort?.id === c.id;
          return (
            <th key={c.id} scope="col" className={c.numeric ? "num" : undefined} style={c.width ? { minWidth: c.width } : undefined}
              aria-sort={c.sortValue ? (active ? (sort!.dir === "asc" ? "ascending" : "descending") : "none") : undefined}>
              {c.sortValue && onSort ? (
                <button type="button" className="sortbtn" onClick={() => toggleSort(c)} aria-label={`Sort by ${c.label}${active ? (sort!.dir === "asc" ? ", ascending" : ", descending") : ""}`}>
                  {c.header}{active && <Icon name={sort!.dir === "asc" ? "up" : "down"} size="sm" />}
                </button>
              ) : c.header}
            </th>
          );
        })}
      </tr>
    </thead>
  );
  const renderRow = (row: Row, style?: React.CSSProperties) => (
    <tr key={rowKey(row)} style={style}>
      {cols.map((c) => <td key={c.id} className={c.numeric ? "num" : undefined} data-label={c.label}>{c.cell(row)}</td>)}
    </tr>
  );
  const items = rowVirtualizer.getVirtualItems();
  const padTop = useVirtual && items.length ? items[0].start : 0;
  const padBottom = useVirtual && items.length ? rowVirtualizer.getTotalSize() - items[items.length - 1].end : 0;
  return (
    <div>
      {onVisible && (
        <div className="row" style={{ marginBottom: "var(--s-2)" }}>
          <Disclosure plain summary={`Columns (${cols.length} of ${columns.length})`}>
            <div className="colpicker">
              {columns.map((c) => (
                <Checkbox key={c.id} label={c.label} checked={c.fixed || !visible || visible.includes(c.id)} disabled={c.fixed}
                  onChange={(e) => {
                    const on = new Set(visible || columns.map((x) => x.id));
                    if (e.target.checked) on.add(c.id); else on.delete(c.id);
                    const next = columns.map((x) => x.id).filter((x) => on.has(x));
                    onVisible(next.length === columns.length ? null : next);
                  }} />
              ))}
              <Button variant="quiet" onClick={() => onVisible(null)}>Show all</Button>
            </div>
          </Disclosure>
        </div>
      )}
      <div className="tblwrap" ref={wrapRef} style={maxHeight ? { maxHeight } : undefined} tabIndex={0} role="region" aria-label={typeof caption === "string" ? caption : undefined} id={id}>
        <table className={`tbl${cards ? " tbl--cards" : ""}`}>
          <caption>{caption}</caption>
          {header}
          <tbody>
            {sorted.length === 0 && <tr><td colSpan={cols.length} className="tbl__empty">{empty}</td></tr>}
            {useVirtual ? (
              <>
                {padTop > 0 && <tr aria-hidden="true"><td colSpan={cols.length} style={{ height: padTop, padding: 0, border: 0 }} /></tr>}
                {items.map((v) => renderRow(sorted[v.index]))}
                {padBottom > 0 && <tr aria-hidden="true"><td colSpan={cols.length} style={{ height: padBottom, padding: 0, border: 0 }} /></tr>}
              </>
            ) : sorted.map((r) => renderRow(r))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** A gap cell: an honest dash with the reason reachable, never a blank. */
export function Gap({ reason }: { reason?: string }) {
  return <span className="tbl__gap" title={reason}>—<span className="sr-only">{reason ? ` ${reason}` : " not available"}</span></span>;
}

/* Overlays: a focus trap, Drawer (dialog, Esc, returns focus, aria-labelledby),
 * Dialog, Palette (combobox and listbox, arrow navigation, Esc returns focus),
 * Tabs, Disclosure (summary as a button with hover and focus, chevron aria-hidden). */
import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, ReactNode } from "react";
import { Button, Icon } from "./primitives";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Traps Tab inside the element while open, restores focus on close. */
export function useFocusTrap(open: boolean, onClose: () => void, initialSelector?: string) {
  const ref = useRef<HTMLDivElement>(null);
  const restore = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!open) return;
    restore.current = document.activeElement as HTMLElement | null;
    const el = ref.current;
    const first = (initialSelector && el?.querySelector<HTMLElement>(initialSelector)) || el?.querySelector<HTMLElement>(FOCUSABLE) || el;
    window.setTimeout(() => first?.focus(), 0);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.stopPropagation(); onClose(); return; }
      if (e.key !== "Tab" || !el) return;
      const items = [...el.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((x) => x.offsetParent !== null || x === document.activeElement);
      if (!items.length) { e.preventDefault(); return; }
      const i = items.indexOf(document.activeElement as HTMLElement);
      if (e.shiftKey && (i <= 0)) { e.preventDefault(); items[items.length - 1].focus(); }
      else if (!e.shiftKey && i === items.length - 1) { e.preventDefault(); items[0].focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      restore.current?.focus?.();
    };
  }, [open, onClose, initialSelector]);
  return ref;
}

/* ------------------------------------------------------------ drawer */
export function Drawer({ open, onClose, title, children, describedBy }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; describedBy?: string }) {
  const id = useId();
  const ref = useFocusTrap(open, onClose, ".drawer__close");
  if (!open) return null;
  return (
    <div className="drawer" ref={ref} role="dialog" aria-modal="true" aria-labelledby={`${id}-t`} aria-describedby={describedBy}>
      <button type="button" className="drawer__scrim" aria-label="Close" onClick={onClose} tabIndex={-1} />
      <div className="drawer__panel">
        <div className="drawer__head">
          <h2 id={`${id}-t`} className="drawer__title t-16">{title}</h2>
          <Button variant="icon" icon="close" label="Close" className="drawer__close" onClick={onClose} />
        </div>
        <div className="drawer__body">{children}</div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ dialog */
export function Dialog({ open, onClose, title, children, initialSelector }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; initialSelector?: string }) {
  const id = useId();
  const ref = useFocusTrap(open, onClose, initialSelector);
  if (!open) return null;
  return (
    <div className="dialog" ref={ref} role="dialog" aria-modal="true" aria-labelledby={`${id}-t`} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="dialog__panel">
        <div className="drawer__head">
          <h2 id={`${id}-t`} className="drawer__title t-16">{title}</h2>
          <Button variant="icon" icon="close" label="Close" onClick={onClose} />
        </div>
        {children}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ palette */
export interface PaletteItem { id: string; label: string; kind: string; hint?: string; run: () => void }
/* A combobox over a listbox: typing filters, arrows move, Enter runs, Esc
 * closes and returns focus to the opener. */
export function Palette({ open, onClose, items, placeholder = "Go to a view, product, plan or cell" }:
  { open: boolean; onClose: () => void; items: PaletteItem[]; placeholder?: string }) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const id = useId();
  const ref = useFocusTrap(open, onClose, "input");
  useEffect(() => { if (open) { setQ(""); setActive(0); } }, [open]);
  const terms = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const shown = (terms.length ? items.filter((it) => terms.every((t) => `${it.label} ${it.kind} ${it.hint || ""}`.toLowerCase().includes(t))) : items).slice(0, 40);
  useEffect(() => { setActive(0); }, [q]);
  const onKey = (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, shown.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Home") { e.preventDefault(); setActive(0); }
    else if (e.key === "End") { e.preventDefault(); setActive(shown.length - 1); }
    else if (e.key === "Enter" && shown[active]) { e.preventDefault(); shown[active].run(); onClose(); }
  };
  useEffect(() => {
    document.getElementById(`${id}-opt-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [active, id]);
  if (!open) return null;
  return (
    <div className="dialog" ref={ref} role="dialog" aria-modal="true" aria-label="Command palette" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="dialog__panel">
        <input className="palette__input" type="text" role="combobox" aria-expanded="true" aria-controls={`${id}-list`}
          aria-activedescendant={shown[active] ? `${id}-opt-${active}` : undefined} aria-autocomplete="list" aria-label={placeholder}
          placeholder={placeholder} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} autoComplete="off" spellCheck={false} />
        <ul className="palette__list" id={`${id}-list`} role="listbox" aria-label="Results">
          {shown.length === 0 && <li className="palette__empty" role="option" aria-selected="false">Nothing matches</li>}
          {shown.map((it, i) => (
            <li key={it.id} id={`${id}-opt-${i}`} role="option" aria-selected={i === active} className="palette__item"
              onMouseEnter={() => setActive(i)} onMouseDown={(e) => e.preventDefault()} onClick={() => { it.run(); onClose(); }}>
              <span>{it.label}</span>
              {it.hint && <span className="t-3 t-12">{it.hint}</span>}
              <span className="palette__kind">{it.kind}</span>
            </li>
          ))}
        </ul>
        <div className="palette__hint" aria-live="polite">{shown.length} of {items.length} · <span className="kbd">↑</span> <span className="kbd">↓</span> to move, <span className="kbd">Enter</span> to open, <span className="kbd">Esc</span> to close</div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ tabs */
export interface Tab { id: string; label: ReactNode; panel: ReactNode }
export function Tabs({ tabs, value, onChange, label }: { tabs: Tab[]; value: string; onChange: (id: string) => void; label: string }) {
  const id = useId();
  const listRef = useRef<HTMLDivElement>(null);
  const onKey = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    const i = tabs.findIndex((t) => t.id === value);
    let next = i;
    if (e.key === "ArrowRight") next = (i + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    else return;
    e.preventDefault();
    onChange(tabs[next].id);
    (listRef.current?.children[next] as HTMLElement | undefined)?.focus();
  };
  const current = tabs.find((t) => t.id === value) || tabs[0];
  return (
    <div>
      <div className="tabs" role="tablist" aria-label={label} ref={listRef} onKeyDown={onKey}>
        {tabs.map((t) => (
          <button key={t.id} type="button" role="tab" id={`${id}-tab-${t.id}`} className="tab" aria-selected={t.id === current.id}
            aria-controls={`${id}-panel-${t.id}`} tabIndex={t.id === current.id ? 0 : -1} onClick={() => onChange(t.id)}>{t.label}</button>
        ))}
      </div>
      <div role="tabpanel" id={`${id}-panel-${current.id}`} aria-labelledby={`${id}-tab-${current.id}`} tabIndex={0}>{current.panel}</div>
    </div>
  );
}

/* ------------------------------------------------------------ disclosure */
export function Disclosure({ summary, children, open, onToggle, plain, id }: { summary: ReactNode; children: ReactNode; open?: boolean; onToggle?: (open: boolean) => void; plain?: boolean; id?: string }) {
  const [local, setLocal] = useState(!!open);
  const isOpen = open ?? local;
  const toggle = useCallback((e: React.SyntheticEvent<HTMLDetailsElement>) => {
    const next = (e.currentTarget as HTMLDetailsElement).open;
    setLocal(next); onToggle?.(next);
  }, [onToggle]);
  return (
    <details className={`disc${plain ? " disc--plain" : ""}`} open={isOpen} onToggle={toggle} id={id}>
      <summary className="disc__summary"><Icon name="chevron" size="sm" className="disc__chevron" />{summary}</summary>
      <div className="disc__body">{children}</div>
    </details>
  );
}

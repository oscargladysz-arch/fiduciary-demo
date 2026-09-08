/* Primitives: Icon, Button, Link, Chip, Card, Stat, VerdictBanner, EmptyState,
 * Skeleton, Toast, Tooltip. Each documents its keyboard behavior, ARIA and
 * states in docs/design/DESIGN_SYSTEM.md and renders on #/design. */
import { createContext, forwardRef, useCallback, useContext, useEffect, useId, useRef, useState } from "react";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";
import { navigate } from "../app/router";
import { ELLIPSIS } from "../format/format";

/* ------------------------------------------------------------ icons */
/* One small inline set. Every icon is aria-hidden unless it is the only
 * content of a button, in which case the button carries the name. */
const PATHS: Record<string, string> = {
  search: "M10.5 3a7.5 7.5 0 1 1 0 15a7.5 7.5 0 0 1 0-15zm0 2a5.5 5.5 0 1 0 0 11a5.5 5.5 0 0 0 0-11zm5.7 10.3l4.5 4.5l-1.4 1.4l-4.5-4.5z",
  menu: "M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z",
  close: "M6.4 5l12.6 12.6l-1.4 1.4L5 6.4zM5 17.6L17.6 5L19 6.4L6.4 19z",
  chevron: "M9 5l7 7l-7 7l-1.4-1.4L13.2 12L7.6 6.4z",
  chevronDown: "M5 9l7 7l7-7l-1.4-1.4L12 13.2L6.4 7.6z",
  external: "M14 3h7v7h-2V6.4l-8.3 8.3l-1.4-1.4L17.6 5H14zM5 5h6v2H7v10h10v-4h2v6H5z",
  cite: "M6 4h9l5 5v11H6zm8 1.5V10h4.5zM8 12h8v2H8zm0 4h8v2H8z",
  pin: "M12 2l2.5 5l5.5.8l-4 3.9l.9 5.5L12 14.6L7.1 17.2l.9-5.5l-4-3.9L9.5 7z",
  check: "M9 16.2l-3.5-3.5L4 14.2l5 5l12-12l-1.4-1.4z",
  info: "M12 2a10 10 0 1 1 0 20a10 10 0 0 1 0-20zm0 2a8 8 0 1 0 0 16a8 8 0 0 0 0-16zm-1 6h2v7h-2zm0-3h2v2h-2z",
  download: "M11 3h2v10.2l3.6-3.6l1.4 1.4l-6 6l-6-6l1.4-1.4l3.6 3.6zM4 19h16v2H4z",
  copy: "M8 2h11v13h-2V4H8zM4 6h11v16H4zm2 2v12h7V8z",
  up: "M12 4l6 6l-1.4 1.4L13 7.8V20h-2V7.8l-3.6 3.6L6 10z",
  down: "M12 20l-6-6l1.4-1.4l3.6 3.6V4h2v12.2l3.6-3.6L18 14z",
  trash: "M9 3h6v2h5v2h-1v14H5V7H4V5h5zm-2 4v12h10V7zm2 2h2v8H9zm4 0h2v8h-2z",
  table: "M3 4h18v16H3zm2 2v3h14V6zm0 5v3h6v-3zm8 0v3h6v-3zm-8 5v3h6v-3zm8 0v3h6v-3z",
  chart: "M4 20V4h2v14h14v2zm4-4v-6h2v6zm4 0V8h2v8zm4 0v-4h2v4z",
  sun: "M12 7a5 5 0 1 1 0 10a5 5 0 0 1 0-10zm0-5h0l1 3h-2zM12 19l1 3h-2zM2 12l3-1v2zm17-1l3 1l-3 1zM5.6 4.2l2.1 2.1l-1.4 1.4l-2.1-2.1zm10.7 12.1l2.1 2.1l-1.4 1.4l-2.1-2.1zM4.2 18.4l2.1-2.1l1.4 1.4l-2.1 2.1zM16.3 6.3l2.1-2.1l1.4 1.4l-2.1 2.1z",
  moon: "M12 3a9 9 0 1 0 9 9c0-.5 0-.9-.1-1.4A6 6 0 0 1 13.4 3.1C13 3 12.5 3 12 3z",
  plus: "M11 4h2v7h7v2h-7v7h-2v-7H4v-2h7z",
  arrowRight: "M13 5l7 7l-7 7l-1.4-1.4l4.6-4.6H4v-2h12.2l-4.6-4.6z",
  arrowLeft: "M11 5l-7 7l7 7l1.4-1.4L7.8 13H20v-2H7.8l4.6-4.6z",
  evaluate: "M4 4h16v16H4zm2 2v12h12V6zm2 7l2.5 2.5L16 10l1.4 1.4l-6.9 6.9l-3.9-3.9z",
  compare: "M3 5h8v14H3zm10 0h8v14h-8zM5 7v10h4V7zm10 0v10h4V7z",
  document: "M6 2h9l5 5v15H6zm8 2v4h4zM8 12h8v2H8zm0 4h8v2H8z",
  plan: "M4 3h16v18H4zm2 2v14h12V5zm2 2h8v2H8zm0 4h8v2H8zm0 4h5v2H8z",
  dot: "M12 8a4 4 0 1 1 0 8a4 4 0 0 1 0-8z",
};
export type IconName = keyof typeof PATHS;
export function Icon({ name, size = "md", className = "", label }: { name: IconName; size?: "sm" | "md" | "lg"; className?: string; label?: string }) {
  const cls = `icon${size === "sm" ? " icon--sm" : size === "lg" ? " icon--lg" : ""} ${className}`.trim();
  return (
    <svg className={cls} viewBox="0 0 24 24" aria-hidden={label ? undefined : "true"} role={label ? "img" : undefined}
      aria-label={label} focusable="false">
      <path d={PATHS[name]} fill="currentColor" />
    </svg>
  );
}

/* ------------------------------------------------------------ button */
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "quiet" | "icon";
  size?: "sm" | "md";
  icon?: IconName;
  iconRight?: IconName;
  loading?: boolean;
  /** required for the icon variant: the accessible name */
  label?: string;
}
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "sm", icon, iconRight, loading, label, className = "", children, type = "button", ...rest }, ref) {
  if (variant === "icon" && !label) throw new Error("an icon button needs a label");
  const cls = `btn btn--${variant === "icon" ? "icon btn--secondary" : variant}${size === "md" ? " btn--md" : ""} ${className}`.trim();
  return (
    <button ref={ref} type={type} className={cls} aria-label={variant === "icon" ? label : rest["aria-label"]}
      aria-busy={loading || undefined} data-loading={loading ? "true" : undefined} {...rest}>
      {icon && <Icon name={icon} />}
      {variant !== "icon" && (loading ? `${children}${ELLIPSIS}` : children)}
      {iconRight && <Icon name={iconRight} />}
    </button>
  );
});

/* ------------------------------------------------------------ link */
export interface LinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  /** an in-app route path such as "/product/hl_paf/record" */
  to?: string;
  params?: Record<string, string | undefined>;
  quiet?: boolean;
  external?: boolean;
  replace?: boolean;
}
/* Every navigation control is an <a href>: Cmd-click and middle-click open a
 * tab, a plain click pushes a history entry through the router. */
export function Link({ to, params, quiet, external, replace, className = "", children, onClick, ...rest }: LinkProps) {
  const href = to ? "#" + (to.startsWith("/") ? to : "/" + to) + (params && Object.values(params).some(Boolean)
    ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString() : "") : rest.href;
  const cls = `link${quiet ? " link--quiet" : ""}${external ? " link--ext" : ""} ${className}`.trim();
  const handle = (e: React.MouseEvent<HTMLAnchorElement>) => {
    onClick?.(e);
    if (!to || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    navigate(to, params, { replace });
  };
  return (
    <a href={href} className={cls} onClick={handle} {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})} {...rest}>
      {children}
    </a>
  );
}

/* ------------------------------------------------------------ chip */
export type ChipKind = "structured" | "extracted" | "verified" | "computed" | "partial" | "na" | "advisor"
  | "aligned" | "conditional" | "weak" | "misaligned" | "illustrative" | "pending" | "tier" | "wrapper" | "neutral" | "accent";
/* The text is the label. Color never carries information alone. 12 px minimum. */
export function Chip({ kind = "neutral", children, title, className = "" }: { kind?: ChipKind; children: ReactNode; title?: string; className?: string }) {
  return <span className={`chip chip--${kind} ${className}`.trim()} title={title}>{children}</span>;
}

/* ------------------------------------------------------------ card */
export function Card({ children, raised, sunken, className = "", as: As = "section", ...rest }:
  { children: ReactNode; raised?: boolean; sunken?: boolean; className?: string; as?: "section" | "div" | "article" } & React.HTMLAttributes<HTMLElement>) {
  return <As className={`card${raised ? " card--raised" : ""}${sunken ? " card--sunken" : ""} ${className}`.trim()} {...rest}>{children}</As>;
}
export function CardHead({ title, children, level = 3 }: { title: ReactNode; children?: ReactNode; level?: 2 | 3 | 4 }) {
  const H = `h${level}` as "h2" | "h3" | "h4";
  return <div className="card__head"><H className="card__title">{title}</H>{children}</div>;
}
export function CardLink({ to, params, children, className = "" }: { to: string; params?: Record<string, string | undefined>; children: ReactNode; className?: string }) {
  return <Link to={to} params={params} quiet className={`card card--link ${className}`.trim()}>{children}</Link>;
}

/* ------------------------------------------------------------ stat */
export function Stat({ label, value, unit, source, large, id }: { label: ReactNode; value: ReactNode; unit?: ReactNode; source?: ReactNode; large?: boolean; id?: string }) {
  return (
    <div className="stat" id={id}>
      <div className="stat__label">{label}</div>
      <div className={`stat__value${large ? " stat__value--lg" : ""}`}>{value}{unit && <span className="stat__unit">{unit}</span>}</div>
      {source && <div className="stat__source">{source}</div>}
    </div>
  );
}
export function StatRow({ children }: { children: ReactNode }) { return <div className="statrow">{children}</div>; }

/* ------------------------------------------------------------ verdict banner */
export type BannerKind = "aligned" | "conditional" | "weak" | "misaligned" | "partial" | "pending" | "info" | "alarm";
/* A defined label, its one-line definition inline, a legend link. */
export function VerdictBanner({ kind, label, definition, legendTo, children, chip }:
  { kind: BannerKind; label: ReactNode; definition?: ReactNode; legendTo?: string; children?: ReactNode; chip?: ReactNode }) {
  return (
    <div className={`banner banner--${kind}`} role="status">
      <div className="banner__head">{label}{chip}{legendTo && <Link to={legendTo} className="t-12">Legend</Link>}</div>
      {definition && <div className="banner__def">{definition}</div>}
      {children}
    </div>
  );
}

/* ------------------------------------------------------------ empty state, skeleton */
export function EmptyState({ title, children, action }: { title: ReactNode; children?: ReactNode; action?: ReactNode }) {
  return <div className="empty" role="status"><div className="empty__title">{title}</div>{children && <div>{children}</div>}{action}</div>;
}
export function Skeleton({ lines = 3, label = "Loading" }: { lines?: number; label?: string }) {
  return (
    <div className="stack-2" role="status" aria-live="polite" aria-label={`${label}${ELLIPSIS}`}>
      {Array.from({ length: lines }, (_, i) => <span key={i} className="skel" style={{ width: `${100 - (i % 3) * 18}%` }} aria-hidden="true" />)}
      <span className="sr-only">{label}{ELLIPSIS}</span>
    </div>
  );
}

/* ------------------------------------------------------------ toasts */
interface ToastItem { id: number; text: string; action?: { label: string; onClick: () => void } }
const ToastCtx = createContext<(text: string, action?: ToastItem["action"]) => void>(() => {});
export function useToast() { return useContext(ToastCtx); }
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const seq = useRef(0);
  const push = useCallback((text: string, action?: ToastItem["action"]) => {
    const id = ++seq.current;
    setItems((xs) => [...xs, { id, text, action }]);
    window.setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), action ? 8000 : 4000);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite" aria-atomic="false">
        {items.map((t) => (
          <div key={t.id} className="toast" role="status">
            <span>{t.text}</span>
            {t.action && <Button variant="quiet" onClick={() => { t.action?.onClick(); setItems((xs) => xs.filter((x) => x.id !== t.id)); }}>{t.action.label}</Button>}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

/* ------------------------------------------------------------ tooltip as a popover */
/* Reachable by keyboard (a button, Enter or Space toggles, Esc closes) and by
 * tap. The trigger is described by the popover through aria-describedby.
 * The glossary lives here: <Term def="...">word</Term>. */
export function Tooltip({ children, content, label = "More information", alignRight }: { children?: ReactNode; content: ReactNode; label?: string; alignRight?: boolean }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent | FocusEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { setOpen(false); (ref.current?.querySelector("button") as HTMLElement | null)?.focus(); } };
    document.addEventListener("mousedown", onDoc); document.addEventListener("focusin", onDoc); document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("focusin", onDoc); document.removeEventListener("keydown", onKey); };
  }, [open]);
  return (
    <span className="tip" ref={ref}>
      {children}
      <button type="button" className="tip__btn" aria-label={label} aria-expanded={open} aria-controls={id}
        aria-describedby={open ? id : undefined} onClick={() => setOpen((o) => !o)}>
        <Icon name="info" size="sm" />
      </button>
      <span id={id} role="tooltip" className={`tip__pop${alignRight ? " tip__pop--right" : ""}`} hidden={!open}>{content}</span>
    </span>
  );
}
export function Term({ children, def }: { children: ReactNode; def: ReactNode }) {
  return <Tooltip content={def} label={`Definition of ${typeof children === "string" ? children : "this term"}`}><span className="term">{children}</span></Tooltip>;
}

/* ------------------------------------------------------------ legend */
export function Legend({ items, label = "Legend" }: { items: { label: ReactNode; kind?: ChipKind; color?: string }[]; label?: string }) {
  return (
    <div className="legend" role="list" aria-label={label}>
      {items.map((it, i) => (
        <span key={i} className="legend__item" role="listitem">
          {it.kind ? <Chip kind={it.kind}>{it.label}</Chip> : <><span className="legend__swatch" style={{ background: it.color }} aria-hidden="true" />{it.label}</>}
        </span>
      ))}
    </div>
  );
}

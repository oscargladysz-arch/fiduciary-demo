/* AppShell, Sidebar, MobileNavSheet, PageHeader, ContextChip, theme toggle. */
import { useCallback, useEffect, useId, useState } from "react";
import type { ReactNode } from "react";
import { navigate, useRoute } from "../app/router";
import { Button, Icon, Link } from "./primitives";
import type { IconName } from "./primitives";
import { useFocusTrap } from "./overlay";

export interface NavItem { to: string; label: string; icon?: IconName; match?: (segments: string[]) => boolean }
export interface NavGroup { label: string; items: NavItem[] }

export function useTheme(): [string, (t: string) => void] {
  const [theme, set] = useState<string>(() => document.documentElement.dataset.theme || "system");
  const apply = useCallback((t: string) => {
    set(t);
    try { if (t === "system") localStorage.removeItem("tark.theme"); else localStorage.setItem("tark.theme", t); } catch { /* storage may be blocked */ }
    if (t === "system") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = t;
  }, []);
  return [theme, apply];
}

export function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  const dark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  return <Button variant="icon" icon={dark ? "sun" : "moon"} label={dark ? "Switch to the light theme" : "Switch to the dark theme"} onClick={() => setTheme(dark ? "light" : "dark")} />;
}

function isActive(item: NavItem, segments: string[]): boolean {
  if (item.match) return item.match(segments);
  const target = item.to.replace(/^\//, "").split("?")[0];
  return segments[0] === target;
}

export function Sidebar({ groups, footer }: { groups: NavGroup[]; footer?: ReactNode }) {
  const r = useRoute();
  return (
    <nav className="sidebar" aria-label="Main">
      <Link to="/start" quiet className="wordmark" aria-label="Tark, start">TARK</Link>
      {groups.map((g) => (
        <div key={g.label} className="sidebar__group">
          <div className="t-eyebrow sidebar__label">{g.label}</div>
          {g.items.map((it) => (
            <Link key={it.to} to={it.to} quiet className="navlink" aria-current={isActive(it, r.segments) ? "page" : undefined}>
              {it.icon && <Icon name={it.icon} />}{it.label}
            </Link>
          ))}
        </div>
      ))}
      {footer}
    </nav>
  );
}

export function MobileNavSheet({ open, onClose, groups, footer }: { open: boolean; onClose: () => void; groups: NavGroup[]; footer?: ReactNode }) {
  const ref = useFocusTrap(open, onClose, ".sheet__close");
  const r = useRoute();
  const id = useId();
  useEffect(() => { if (open) onClose(); /* a route change closes the sheet */ // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [r.hash]);
  if (!open) return null;
  return (
    <div className="sheet" ref={ref} role="dialog" aria-modal="true" aria-labelledby={`${id}-t`}>
      <div className="sheet__panel">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <h2 id={`${id}-t`} className="t-16">Navigation</h2>
          <Button variant="icon" icon="close" label="Close navigation" className="sheet__close" onClick={onClose} />
        </div>
        <Sidebar groups={groups} footer={footer} />
      </div>
      <button type="button" className="sheet__scrim" aria-label="Close navigation" onClick={onClose} tabIndex={-1} />
    </div>
  );
}

export function AppShell({ groups, header, children, footer }: { groups: NavGroup[]; header?: ReactNode; children: ReactNode; footer?: ReactNode }) {
  const [collapsed, setCollapsed] = useState<boolean>(() => { try { return localStorage.getItem("tark.sidebar") === "collapsed"; } catch { return false; } });
  const [sheet, setSheet] = useState(false);
  const toggle = () => { setCollapsed((c) => { try { localStorage.setItem("tark.sidebar", c ? "open" : "collapsed"); } catch { /* ignore */ } return !c; }); };
  return (
    <div className={`shell${collapsed ? " shell--collapsed" : ""}`}>
      <a href="#main" className="skiplink" onClick={(e) => { e.preventDefault(); const m = document.getElementById("main"); m?.focus(); m?.scrollIntoView(); }}>Skip to content</a>
      <aside className="shell__side"><Sidebar groups={groups} footer={footer} /></aside>
      <div className="shell__main">
        <header className="mobilebar">
          <Button variant="icon" icon="menu" label="Open navigation" onClick={() => setSheet(true)} aria-expanded={sheet} />
          <Link to="/start" quiet className="wordmark" aria-label="Tark, start">TARK</Link>
          <span className="spacer" />
          <ThemeToggle />
        </header>
        <header className="topbar">
          <Button variant="icon" icon="menu" label={collapsed ? "Show the sidebar" : "Hide the sidebar"} onClick={toggle} aria-expanded={!collapsed} />
          {header}
          <span className="spacer" />
          <ThemeToggle />
        </header>
        <main id="main" className="shell__content" tabIndex={-1}>{children}</main>
      </div>
      <MobileNavSheet open={sheet} onClose={() => setSheet(false)} groups={groups} footer={footer} />
    </div>
  );
}

/* A page header: the H1, a one-sentence subtitle, actions. The H1 sits
 * within the first 200 px on mobile because the shell puts nothing above
 * it but the 56 px bar. */
export function PageHeader({ title, eyebrow, sub, actions, children, display }: { title: ReactNode; eyebrow?: ReactNode; sub?: ReactNode; actions?: ReactNode; children?: ReactNode; display?: boolean }) {
  return (
    <header className="pagehead">
      {eyebrow && <div className="t-eyebrow">{eyebrow}</div>}
      <div className="pagehead__row">
        <h1 className={`pagehead__title${display ? " t-display t-32" : ""}`}>{title}</h1>
        {actions && <div className="pagehead__actions">{actions}</div>}
      </div>
      {sub && <p className="pagehead__sub">{sub}</p>}
      {children}
    </header>
  );
}

/* A context chip: the plan or the product, shown only where it acts. */
export function ContextChip({ label, value, options, onChange, id, note }: { label: string; value: string; options: { value: string; label: string }[]; onChange: (v: string) => void; id: string; note?: ReactNode }) {
  return (
    <div className="field field--inline">
      <label htmlFor={id} className="field__label">{label}</label>
      <select id={id} className="select select--sm" value={value} onChange={(e) => onChange(e.target.value)} style={{ width: "auto", maxWidth: "100%" }}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      {note && <span className="t-12 t-3">{note}</span>}
    </div>
  );
}

export function goto(path: string, params?: Record<string, string | undefined>) { navigate(path, params); }

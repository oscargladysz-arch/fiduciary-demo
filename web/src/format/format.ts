/* The formatting layer. Every number and date on every surface passes
 * through here (R3-P1-8). Intl with the viewer’s locale, non-breaking
 * spaces between a number and its unit, curly quotes, the ellipsis
 * character. The formatting gate greps the built JS for toFixed( and for
 * toLocaleString( without options. */

export const NBSP = " ";
export const ELLIPSIS = "…";
export const THIN = " ";
export const MINUS = "−";

let cachedLocales: string[] | null = null;
/* the viewer’s languages, each validated: a headless browser can report a
 * tag such as en-US@posix that Intl refuses */
function locales(): string[] {
  if (cachedLocales) return cachedLocales;
  const out: string[] = [];
  const cands = typeof navigator !== "undefined" && navigator.languages ? [...navigator.languages] : [];
  for (const c of cands) {
    try { out.push(...Intl.getCanonicalLocales(c)); } catch { /* skip an invalid tag */ }
  }
  cachedLocales = out.length ? out : ["en-US"];
  return cachedLocales;
}

const cache = new Map<string, Intl.NumberFormat>();
function nf(opts: Intl.NumberFormatOptions): Intl.NumberFormat {
  const key = JSON.stringify(opts);
  let f = cache.get(key);
  if (!f) { f = new Intl.NumberFormat(locales(), opts); cache.set(key, f); }
  return f;
}

export type Numberish = number | string | null | undefined;

function num(v: Numberish): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** A count: 3,599 */
export function fmtInt(v: Numberish): string {
  const n = num(v); if (n === null) return "";
  return nf({ maximumFractionDigits: 0 }).format(n);
}

/** A number to a stated number of decimals: 1.0613 */
export function fmtNum(v: Numberish, digits = 2): string {
  const n = num(v); if (n === null) return "";
  return nf({ minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
}

/** A ratio such as a KS-PME, four decimals by convention on the record */
export function fmtRatio(v: Numberish, digits = 4): string {
  return fmtNum(v, digits);
}

/** A percentage from a percent value (11.69 -> 11.69%) */
export function fmtPct(v: Numberish, digits = 2): string {
  const n = num(v); if (n === null) return "";
  return nf({ style: "percent", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n / 100);
}

/** A percentage from a fraction (0.1169 -> 11.69%) */
export function fmtFraction(v: Numberish, digits = 2): string {
  const n = num(v); if (n === null) return "";
  return nf({ style: "percent", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
}

/** Dollars in full: $570,000,000 */
export function fmtMoney(v: Numberish, digits = 0): string {
  const n = num(v); if (n === null) return "";
  return nf({ style: "currency", currency: "USD", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
}

/** Compact dollars: $570M, $8.25B, $28.3M */
export function fmtMoneyCompact(v: Numberish, digits = 1): string {
  const n = num(v); if (n === null) return "";
  return nf({ style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: digits }).format(n);
}

/** Basis points */
export function fmtBps(v: Numberish): string {
  const n = num(v); if (n === null) return "";
  return `${fmtInt(n)}${NBSP}bps`;
}

/** A number with its unit, joined by a non-breaking space: "5 years" */
export function withUnit(v: string, unit: string): string {
  return v ? `${v}${NBSP}${unit}` : "";
}

/** n=5 with a non-breaking space either side of the equals sign */
export function fmtN(n: Numberish): string {
  const v = num(n); if (v === null) return "";
  return `n${NBSP}=${NBSP}${fmtInt(v)}`;
}

/** "x of N" */
export function fmtOf(x: Numberish, n: Numberish): string {
  const a = num(x), b = num(n);
  if (a === null || b === null) return "";
  return `${fmtInt(a)}${NBSP}of${NBSP}${fmtInt(b)}`;
}

const dcache = new Map<string, Intl.DateTimeFormat>();
function df(opts: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = JSON.stringify(opts);
  let f = dcache.get(key);
  if (!f) { f = new Intl.DateTimeFormat(locales(), { timeZone: "UTC", ...opts }); dcache.set(key, f); }
  return f;
}

function parseDate(v: string | Date | null | undefined): Date | null {
  if (!v) return null;
  if (v instanceof Date) return Number.isNaN(v.getTime()) ? null : v;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v);
  if (m) return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "June 9, 2026" */
export function fmtDate(v: string | Date | null | undefined): string {
  const d = parseDate(v); if (!d) return "";
  return df({ year: "numeric", month: "long", day: "numeric" }).format(d);
}

/** "Jun 9, 2026" for tight columns */
export function fmtDateShort(v: string | Date | null | undefined): string {
  const d = parseDate(v); if (!d) return "";
  return df({ year: "numeric", month: "short", day: "numeric" }).format(d);
}

/** ISO where a filing date is quoted verbatim: 2026-06-09 */
export function fmtIso(v: string | Date | null | undefined): string {
  const d = parseDate(v); if (!d) return "";
  return d.toISOString().slice(0, 10);
}

/** "June 9, 2026, 14:03 UTC" */
export function fmtDateTime(v: string | Date | null | undefined): string {
  const d = parseDate(v); if (!d) return "";
  return `${df({ year: "numeric", month: "long", day: "numeric" }).format(d)}, ${df({ hour: "2-digit", minute: "2-digit", hour12: false }).format(d)}${NBSP}UTC`;
}

/** Elapsed seconds as "4 min 5 s" */
export function fmtElapsed(seconds: Numberish): string {
  const s = num(seconds); if (s === null) return "";
  const m = Math.floor(s / 60), r = Math.round(s - m * 60);
  return m > 0 ? `${fmtInt(m)}${NBSP}min ${fmtInt(r)}${NBSP}s` : `${fmtInt(r)}${NBSP}s`;
}

/** Bytes as "41 KB" */
export function fmtBytes(v: Numberish): string {
  const n = num(v); if (n === null) return "";
  if (n < 1024) return `${fmtInt(n)}${NBSP}B`;
  if (n < 1024 * 1024) return `${fmtNum(n / 1024, 0)}${NBSP}KB`;
  return `${fmtNum(n / (1024 * 1024), 1)}${NBSP}MB`;
}

/** Straight quotes and apostrophes to curly, three dots to the ellipsis */
export function typographic(s: string): string {
  return s
    .replace(/\.\.\./g, ELLIPSIS)
    .replace(/(^|[\s(\[{])"/g, "$1“")
    .replace(/"/g, "”")
    .replace(/(^|[\s(\[{])'/g, "$1‘")
    .replace(/'/g, "’");
}

/** Truncate with the ellipsis character, never a bare cut */
export function truncate(s: string, n: number): string {
  if (!s || s.length <= n) return s || "";
  return s.slice(0, Math.max(0, n - 1)).trimEnd() + ELLIPSIS;
}

/** Loading strings end with the ellipsis character */
export function loading(what: string): string {
  return `${what}${ELLIPSIS}`;
}

/** A hash prefix for the selection lock line */
export function hashPrefix(h: string | null | undefined, n = 8): string {
  return h ? h.slice(0, n) : "";
}

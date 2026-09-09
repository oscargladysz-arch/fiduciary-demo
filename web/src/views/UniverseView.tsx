/* The Universe. Every registered wrapper the record can find on file, about
 * three and a half thousand of them, with the detail for one entity fetched
 * only when a reader opens it.
 *
 * Everything on this page is tier one: a number the filing tagged itself, or
 * a date and a count taken from the filer’s own submission history. Nothing
 * here is read out of prose and nothing here is signed by a person, so the
 * tier legend is shown once and the pending sentence sits beside it.
 *
 * Three chunks, fetched at three different moments. The summary arrives on
 * the first paint and carries one positional row per entity. The full record
 * for one entity arrives when the reader opens that entity, one shard of
 * sixty-four. The auditor and adviser index arrives only when the reader
 * types in that box, because it is worth nothing until then.
 *
 * The record was assembled with notes written for its own operators. Where a
 * note or a line of evidence is written in that shorthand it is held back and
 * counted rather than printed, because a reader cannot use it.
 *
 * Filter, sort, column and open-entity state serialize into the URL and
 * replace the history entry rather than pushing one. The two text boxes never
 * enter the URL. */
import { Fragment, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { setParams, useRoute } from "../app/router";
import { Field, Input, NumberInput, Select } from "../components/form";
import { Drawer } from "../components/overlay";
import { Button, Card, CardHead, EmptyState, Icon, Legend, Link, Skeleton, Stat, StatRow }
  from "../components/primitives";
import { PageHeader } from "../components/shell";
import { Table, sortRows } from "../components/table";
import type { Column, SortState } from "../components/table";
import { CENSUS_CLASS, CENSUS_FIELD, SAY, TIERS, routeTitle } from "../copy/copy";
import { useAsync, useIndex } from "../data/hooks";
import { data } from "../data/index";
import {
  ELLIPSIS, fmtDate, fmtDateShort, fmtInt, fmtMoney, fmtMoneyCompact, fmtNum, fmtOf, typographic,
} from "../format/format";
import type { CensusRow, CensusView } from "../data/types";

/* ------------------------------------------------------------ shapes */
/* The shard’s own shape: every field carries its value beside where it came
 * from and when. types.ts holds the summary shape only, so the record for one
 * entity is described here. */
interface Prov { value?: unknown; source?: string; ref?: string; as_of?: string; reason?: string }
type Entity = Record<string, unknown>;

interface Row {
  cik: string;
  name: string;
  cls: string;
  flags: number;
  assets: number;
  latest: string;
  windows: number;
  lastWindow: string;
  productKey: string;
}

/* the bits of the summary row’s flag field, as row_fields documents them */
const FLAG = { listed: 1, ncen: 2, interval: 4, agree: 8, evaluated: 16, structured: 32 };

const CAP = 400;                 // rows put in the table at once
const MILLION = 1000000;         // the assets boxes are read in millions
const EITHER = "";               // a filter that accepts every value
const YES = "y";
const NO = "n";

/* ------------------------------------------------------- reader words */
/* Where the record names a field with its own shorthand and copy.ts has no
 * word for it, the word is here, in plain language. Nothing prints the
 * record’s own key. */
const FIELD: Record<string, string> = {
  first_filing: "First filing on record",
  filings: "Filings on record, by form",
  nav: "Net asset value per share",
  signals: "Signals the record found",
  exchanges: "Exchanges named in the filings",
  tickers: "Ticker symbols on file",
  listing_open: "Why the listing answer is open",
  hint: "Words in the name",
  windows: "Buyback windows on file",
  first_window: "First buyback window",
  filer: "SEC filer number",
  auditor: "Auditor",
  advisers: "Advisers",
  company_type: "Company type on the filing",
  nav_error: "A net asset value error was corrected in the year",
  opinion: "The auditor opinion is qualified",
  filing_fund: "Fund named in the filing",
  avg_assets: "Average net assets",
  mgmt_fee: "Management fee as filed",
  net_expenses: "Net operating expenses as filed",
  filing_nav: "Net asset value per share as filed",
  filing_interval: "Interval fund, as the filing answers it",
};

/* What a provenance line came from, in reader words. */
const SOURCE_WORDS: Record<string, string> = {
  submissions: "From the filer’s own submission history at the SEC",
  xbrl: "From the tagged financial data in the filing",
  ncen: "From the annual census filing",
};

/* The three interval signals the record cross-checks. */
const INTERVAL_SIGNAL: Record<string, string> = {
  ncen_self_classified_interval: "The annual census filing calls it an interval fund",
  n23c3a_filing_behavior: "It keeps filing the yearly notice an interval fund files",
  agreement: CENSUS_FIELD.agree,
};

const MONTHS: Record<string, string> = {
  JAN: "01", FEB: "02", MAR: "03", APR: "04", MAY: "05", JUN: "06",
  JUL: "07", AUG: "08", SEP: "09", OCT: "10", NOV: "11", DEC: "12",
};

/* ------------------------------------------------------------ helpers */
function text(v: unknown): string { return typeof v === "string" ? v : ""; }
function numOr(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}
function strings(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x) => typeof x === "string") as string[] : [];
}
function prov(rec: Entity, key: string): Prov | null {
  const v = rec[key];
  return v && typeof v === "object" && !Array.isArray(v) ? v as Prov : null;
}
function bag(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v) ? v as Record<string, unknown> : {};
}

/** A class key in reader words. The seven the record uses are in copy.ts. */
function classWords(key: string): string {
  return CENSUS_CLASS[key] || "A class the record does not name here";
}

/** A date the annual census filing writes as 31-DEC-2025, as the date it is,
 *  so every date on the page still goes through the formatter. */
function isoish(raw: string): string {
  const m = /^(\d{2})-([A-Za-z]{3})-(\d{4})$/.exec(raw.trim());
  const month = m ? MONTHS[m[2].toUpperCase()] : undefined;
  return m && month ? `${m[3]}-${month}-${m[1]}` : raw;
}

/** A filing number, only where the reference is one. Every other reference
 *  the record keeps is the name of a file it read, which no reader can use. */
function accession(ref: string): string {
  return /^\d{10}-\d{2}-\d{6}$/.test(ref.trim()) ? ref.trim() : "";
}

/** A sentence a reader can use, or nothing. A line written in the collection
 *  step’s own shorthand is held back: a key joined by an underscore, a file
 *  name, a path, a query written as a key and a value, or one of the tool
 *  names the collection step used. */
const OPERATOR_WORDS = ["efts", "browse-edgar", "checkpoint", "oracle", "company tickers",
  "full-text search", "year-split", "month-split", "companyconcept", "us-gaap"];
function readerSafe(s: string): boolean {
  if (!s.trim()) return false;
  if (/[a-z0-9]_[a-z0-9]/i.test(s)) return false;
  if (/\.(json|csv|py|md|txt|tsv)\b/i.test(s)) return false;
  if (/\b(data|docs|src)\//.test(s)) return false;
  if (/=/.test(s)) return false;
  if (/\bnull\b/i.test(s)) return false;
  const low = s.toLowerCase();
  return !OPERATOR_WORDS.some((w) => low.includes(w));
}

/** The reason the record gives for holding no figure, in reader words where
 *  the record wrote it in its own shorthand. */
function readerReason(raw: string): string {
  if (!raw.trim()) return "The record gives no reason for this.";
  const low = raw.toLowerCase();
  if (low.includes("assets") && low.includes("tagged")) {
    return "The filing tags no total assets figure in its own structured data, so the record holds none.";
  }
  if (low.includes("nav")) {
    return "Net asset value per share is tagged by each issuer in its own way, so the record does not read one at tier one.";
  }
  if (readerSafe(raw)) return typographic(raw);
  return "The record gives a reason for this in the collection step’s own shorthand rather than in reader words.";
}

/** A name hint, as words rather than as the token the record files it under. */
function hintWords(h: string): string {
  const s = h.replace(/\?/g, " ").replace(/-/g, " ").replace(/\s+/g, " ").trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
}

/** What a provenance block says: where the value came from, as of when, and
 *  the filing number where the reference is one. */
function provSentence(p: Prov | null): string {
  if (!p) return "The record carries no source line for this field.";
  const head = SOURCE_WORDS[text(p.source)] || "On the record";
  const when = fmtDate(isoish(text(p.as_of)));
  const acc = accession(text(p.ref));
  return `${head}${when ? `, as of ${when}` : ""}.${acc ? ` Filing ${acc}.` : ""}`;
}

/** Yes, no, or the sentence the filing gives instead of an answer. */
function yesNo(v: unknown): string {
  if (v === true || v === "Y") return "Yes";
  if (v === false || v === "N") return "No";
  return "The filing does not answer this.";
}

/* --------------------------------------------------------- the chunks */
function askCensus(): Promise<CensusView> {
  const api = data();
  return api.getCensus ? api.getCensus() : Promise.reject(new Error("no universe on this source"));
}
function askShard(n: number): Promise<Record<string, Entity>> {
  const api = data();
  return api.getCensusShard ? api.getCensusShard(n) : Promise.reject(new Error("no universe on this source"));
}
function askSearch(): Promise<Record<string, string>> {
  const api = data();
  return api.getCensusSearch ? api.getCensusSearch() : Promise.resolve({});
}

/* ------------------------------------------------------------- entry */
function Entry({ label, value, source, note }:
  { label: ReactNode; value: ReactNode; source?: Prov | null; note?: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>
        <div className="t-14">{value}</div>
        <div className="t-12 t-3">{note || provSentence(source || null)}</div>
      </dd>
    </>
  );
}

/* ------------------------------------------------------- the detail */
/* One entity, from the shard its filer number falls in. */
function EntityDetail({ census, row }: { census: CensusView; row: Row }) {
  const shards = census.shards || 1;
  const n = ((Number(row.cik) % shards) + shards) % shards;
  const { value: shard, error, loading } = useAsync<Record<string, Entity>>(() => askShard(n), [n]);

  if (error) return <EmptyState title={SAY.noRecord}>{error}</EmptyState>;
  if (loading || !shard) return <Skeleton lines={10} label={SAY.loadingRecord} />;

  const rec = shard[row.cik];
  if (!rec) {
    return (
      <EmptyState title={SAY.noRecord}>
        The summary row for this entity is on file, and the record behind it is not.
      </EmptyState>
    );
  }

  const enc = prov(rec, "enc");
  const listed = prov(rec, "lif");
  const listingOpen = prov(rec, "lsig");
  const tickers = prov(rec, "tk");
  const assets = prov(rec, "ta");
  const nav = prov(rec, "nav");
  const first = prov(rec, "ff");
  const annual = prov(rec, "la");
  const filings = prov(rec, "fs");
  const cross = prov(rec, "ic");
  const ncen = prov(rec, "nc");
  const windows = bag(rec.toi);
  const evidence = strings(rec.ev).filter(readerSafe);
  const evidenceHeld = strings(rec.ev).length - evidence.length;
  const hints = strings(rec.hint).map(hintWords).filter(Boolean);
  const signals = strings(rec.sig).map(classWords);
  const exchanges = strings(rec.ex);

  const annualValue = bag(annual?.value);
  const annualUrl = text(annualValue.url);          // only ever a link the record itself holds
  const annualForm = text(annualValue.form);
  const annualDate = fmtDate(text(annualValue.date));
  const annualAcc = accession(text(annualValue.accession));

  const filingCounts = Object.entries(bag(filings?.value))
    .map(([form, count]) => [form, numOr(count) || 0] as [string, number])
    .sort((a, b) => b[1] - a[1]);

  const ncenValue = bag(ncen?.value);
  const fund = bag(ncenValue.pf);
  const advisers = strings(fund.advisers);

  const money = (p: Prov | null, digits = 0) => {
    if (!p) return "The record holds no figure for this entity.";
    const v = numOr(p.value);
    if (v !== null) return fmtMoney(v, digits);
    return readerReason(text(p.reason));
  };
  const filed = (v: unknown, render: (n: number) => string) => {
    const n2 = numOr(v);
    return n2 === null ? "The filing does not carry this figure." : render(n2);
  };

  return (
    <div className="stack-4">
      <h3 className="t-14 t-semibold">What the record holds</h3>
      <dl className="field-list">
        <Entry label={CENSUS_FIELD.nm} value={text(enc?.value) || row.name} source={enc} />
        <Entry label={CENSUS_FIELD.cls} value={classWords(row.cls)}
          note="The record places it here on the evidence below." />
        {signals.length > 0 && (
          <Entry label={FIELD.signals} value={signals.join(", ")}
            note="Every class signal the filings show for this entity." />
        )}
        <Entry label={CENSUS_FIELD.listed}
          value={listed?.value === null || listed?.value === undefined
            ? readerReason(text(listed?.reason)) : yesNo(listed?.value)}
          source={listed} />
        {listingOpen && (
          <Entry label={FIELD.listing_open} value={readerReason(text(listingOpen.reason))} source={listingOpen} />
        )}
        {exchanges.length > 0 && (
          <Entry label={FIELD.exchanges} value={exchanges.join(", ")}
            note="Named in the filer’s submission history." />
        )}
        {tickers && (
          <Entry label={FIELD.tickers} value={strings(tickers.value).join(", ") || "None on record"} source={tickers} />
        )}
        <Entry label={CENSUS_FIELD.assets} value={money(assets)} source={assets} />
        {nav && <Entry label={FIELD.nav} value={money(nav, 2)} source={nav} />}
        {first && <Entry label={FIELD.first_filing} value={fmtDate(text(first.value)) || "None on record"} source={first} />}
        <Entry label={CENSUS_FIELD.latest_annual}
          value={annual
            ? (
              <span className="row-3">
                <span>{`${annualForm || "The annual filing"}${annualDate ? `, filed ${annualDate}` : ""}`}</span>
                {annualUrl && (
                  <Link href={annualUrl} external>Open the filing<Icon name="external" size="sm" /></Link>
                )}
              </span>
            )
            : "None on record"}
          source={annual} />
        {annual && !annualUrl && annualAcc && (
          <Entry label="Filing number" value={<span className="provenance">{annualAcc}</span>}
            note="Printed as text. A link to this filing is not on record, so nothing here opens it." />
        )}
        <Entry label={CENSUS_FIELD.tender_count}
          value={row.windows > 0 ? fmtInt(row.windows) : "None on record"}
          note="Counted from the buyback offers in the filer’s submission history." />
        {row.windows > 0 && (
          <>
            <Entry label={FIELD.first_window} value={fmtDate(text(windows.first)) || "Not on record"}
              note="Taken from the same offers." />
            <Entry label={CENSUS_FIELD.tender_last} value={fmtDate(text(windows.last)) || "Not on record"}
              note="Taken from the same offers." />
          </>
        )}
        {hints.length > 0 && (
          <Entry label={FIELD.hint} value={hints.join(", ")}
            note="Read from the name alone, never from what the entity holds." />
        )}
        <Entry label={FIELD.filer} value={<span className="provenance">{row.cik}</span>}
          note="The number the SEC files this entity under." />
      </dl>

      {row.productKey && (
        <p className="t-14">
          <Link to={`/product/${row.productKey}/record`}>Open the six-factor record for this fund</Link>
        </p>
      )}

      <h3 className="t-14 t-semibold">Why the record places it here</h3>
      {evidence.length > 0
        ? (
          <ul className="stack-2">
            {evidence.map((e) => <li key={e} className="t-13 t-2">{typographic(e)}</li>)}
          </ul>
        )
        : <p className="t-13 t-3">No line of evidence for this entity is written in reader words.</p>}
      {evidenceHeld > 0 && (
        <p className="t-12 t-3">
          {evidenceHeld === 1
            ? "One further line is held back because it is written in the collection step’s own shorthand."
            : `${fmtInt(evidenceHeld)} further lines are held back because they are written in the collection step’s own shorthand.`}
        </p>
      )}

      {cross && (
        <>
          <h3 className="t-14 t-semibold">{CENSUS_FIELD.interval}</h3>
          <dl className="field-list">
            {Object.entries(bag(cross.value)).map(([k, v]) => (
              <Fragment key={k}>
                <Entry label={INTERVAL_SIGNAL[k] || "A signal the record does not name here"}
                  value={yesNo(v)} source={cross} />
              </Fragment>
            ))}
          </dl>
        </>
      )}

      {ncen && (
        <>
          <h3 className="t-14 t-semibold">{CENSUS_FIELD.ncen}</h3>
          <dl className="field-list">
            <Entry label={FIELD.auditor} value={text(ncenValue.auditor) || "Not named in the filing"} source={ncen} />
            {advisers.length > 0 && <Entry label={FIELD.advisers} value={advisers.join(", ")} source={ncen} />}
            {text(fund.fund_name) && <Entry label={FIELD.filing_fund} value={text(fund.fund_name)} source={ncen} />}
            <Entry label={FIELD.company_type} value={text(ncenValue.ict) || "Not stated in the filing"} source={ncen} />
            <Entry label={FIELD.avg_assets} value={filed(fund.avg_net_assets, (v) => fmtMoney(v))} source={ncen} />
            <Entry label={FIELD.filing_nav} value={filed(fund.nav_per_share, (v) => fmtMoney(v, 2))} source={ncen} />
            <Entry label={FIELD.mgmt_fee} value={filed(fund.management_fee, (v) => fmtNum(v, 2))} source={ncen} />
            <Entry label={FIELD.net_expenses} value={filed(fund.net_operating_expenses, (v) => fmtNum(v, 2))} source={ncen} />
            <Entry label={FIELD.filing_interval} value={yesNo(fund.is_interval)} source={ncen} />
            <Entry label={FIELD.nav_error} value={yesNo(ncenValue.nav_err)} source={ncen} />
            <Entry label={FIELD.opinion} value={yesNo(ncenValue.oq)} source={ncen} />
          </dl>
          <p className="t-12 t-3">
            The management fee and the net operating expenses are kept exactly as the filing reports them.
            The record carries no unit for either one, so none is shown here.
          </p>
        </>
      )}

      {filingCounts.length > 0 && (
        <>
          <h3 className="t-14 t-semibold">{FIELD.filings}</h3>
          <dl className="field-list">
            {filingCounts.map(([form, count]) => (
              <Fragment key={form}>
                <dt translate="no">{form}</dt>
                <dd className="t-num">{fmtInt(count)}</dd>
              </Fragment>
            ))}
          </dl>
          <p className="t-12 t-3">{provSentence(filings)}</p>
        </>
      )}

      <p className="t-12 t-3">
        Every figure here is tier one. {SAY.verificationPending}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------ columns */
function makeColumns(open: (cik: string) => void): Column<Row>[] {
  return [
    {
      id: "name", header: CENSUS_FIELD.nm, label: CENSUS_FIELD.nm, fixed: true,
      sortValue: (row) => row.name,
      cell: (row) => (
        <Button variant="quiet" translate="no" aria-haspopup="dialog"
          aria-label={`Open what the record holds for ${row.name}`} onClick={() => open(row.cik)}>
          {row.name}
        </Button>
      ),
    },
    {
      id: "class", header: CENSUS_FIELD.cls, label: CENSUS_FIELD.cls,
      sortValue: (row) => classWords(row.cls),
      cell: (row) => <span className="t-13">{classWords(row.cls)}</span>,
    },
    {
      id: "assets", header: CENSUS_FIELD.assets, label: CENSUS_FIELD.assets, numeric: true,
      sortValue: (row) => (row.assets > 0 ? row.assets : null),
      cell: (row) => (row.assets > 0
        ? <span className="t-num">{fmtMoneyCompact(row.assets)}</span>
        : <span className="t-13 t-3">Not on this row</span>),
    },
    {
      id: "annual", header: CENSUS_FIELD.latest_annual, label: CENSUS_FIELD.latest_annual,
      sortValue: (row) => row.latest || null,
      cell: (row) => (row.latest
        ? <span className="t-num">{fmtDateShort(row.latest)}</span>
        : <span className="t-13 t-3">None on record</span>),
    },
    {
      id: "windows", header: CENSUS_FIELD.tender_count, label: CENSUS_FIELD.tender_count, numeric: true,
      sortValue: (row) => row.windows,
      cell: (row) => (row.windows > 0
        ? (
          <span className="t-13">
            <span className="t-num">{fmtInt(row.windows)}</span>
            {row.lastWindow ? `, last ${fmtDateShort(row.lastWindow)}` : ""}
          </span>
        )
        : <span className="t-13 t-3">None on record</span>),
    },
    {
      id: "evaluated", header: CENSUS_FIELD.evaluated, label: CENSUS_FIELD.evaluated,
      sortValue: (row) => (row.productKey ? 1 : 0),
      cell: (row) => (row.productKey
        ? <Link to={`/product/${row.productKey}/record`}>Open the record</Link>
        : <span className="t-13 t-3">Not evaluated</span>),
    },
  ];
}

/* --------------------------------------------------------------- view */
export default function UniverseView() {
  const r = useRoute();
  const { value: census, error, loading } = useAsync<CensusView>(() => askCensus(), []);
  const { value: index } = useIndex();
  const [name, setName] = useState("");
  const [who, setWho] = useState("");

  const needle = who.trim().toLowerCase();
  const wantSearch = needle.length >= 2;
  const { value: searchIndex, loading: searching } =
    useAsync<Record<string, string>>(() => (wantSearch ? askSearch() : Promise.resolve({})), [wantSearch]);

  const rows = useMemo<Row[]>(() => {
    if (!census) return [];
    const codes = census.cls_codes || {};
    return Object.entries(census.entities || {}).map(([cik, raw]) => {
      const e = raw as CensusRow;
      return {
        cik,
        name: e[0] || "",
        cls: codes[e[1]] || "",
        flags: e[2] || 0,
        assets: e[3] || 0,
        latest: e[4] || "",
        windows: e[5] || 0,
        lastWindow: e[6] || "",
        productKey: e[8] || "",
      };
    });
  }, [census]);

  const columns = useMemo<Column<Row>[]>(
    () => makeColumns((cik) => setParams({ c_cik: cik })), []);

  const classCounts = census?.counts_by_class || {};
  const p = r.params;
  const fClass = Object.prototype.hasOwnProperty.call(classCounts, p.get("c_class") || "")
    ? p.get("c_class") as string : EITHER;
  const fListed = choice(p.get("c_listed"));
  const fInterval = choice(p.get("c_interval"));
  const fWindows = choice(p.get("c_windows"));
  const fEval = choice(p.get("c_eval"));
  const rawMin = p.get("c_amin") || "";
  const rawMax = p.get("c_amax") || "";
  const aMin = wholeNumber(rawMin);
  const aMax = wholeNumber(rawMax);

  const shown = useMemo(() => {
    const min = aMin === null ? null : aMin * MILLION;
    const max = aMax === null ? null : aMax * MILLION;
    const nameNeedle = name.trim().toLowerCase();
    return rows.filter((row) => {
      if (fClass && row.cls !== fClass) return false;
      if (!flagged(row.flags, FLAG.listed, fListed)) return false;
      if (!flagged(row.flags, FLAG.interval, fInterval)) return false;
      if (!flagged(row.flags, FLAG.evaluated, fEval)) return false;
      if (fWindows === YES && row.windows === 0) return false;
      if (fWindows === NO && row.windows > 0) return false;
      if (min !== null && row.assets < min) return false;
      if (max !== null && (row.assets === 0 || row.assets > max)) return false;
      if (nameNeedle && !row.name.toLowerCase().includes(nameNeedle)) return false;
      if (wantSearch) {
        const hay = searchIndex ? searchIndex[row.cik] || "" : "";
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
  }, [rows, fClass, fListed, fInterval, fEval, fWindows, aMin, aMax, name, wantSearch, needle, searchIndex]);

  const sort: SortState = p.get("sort")
    ? { id: p.get("sort") as string, dir: p.get("dir") === "asc" ? "asc" : "desc" }
    : { id: "assets", dir: "desc" };
  const visible = p.get("cols") ? (p.get("cols") as string).split(".") : null;
  const capped = useMemo(() => sortRows(shown, columns, sort).slice(0, CAP),
    [shown, columns, sort.id, sort.dir]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return (
      <EmptyState title={SAY.noRecord}>
        {error} The universe is part of the public reference set, and a workspace carries its own record instead.
      </EmptyState>
    );
  }
  if (loading || !census) return <Skeleton lines={12} label={SAY.loadingRecord} />;

  const open = p.get("c_cik") || "";
  const openRow = open ? rows.find((row) => row.cik === open) || null : null;
  const counts = index?.coverage_totals.counts || {};
  const evaluated = rows.filter((row) => row.flags & FLAG.evaluated).length;
  const structured = rows.filter((row) => row.flags & FLAG.structured).length;
  const filtered = fClass || fListed || fInterval || fWindows || fEval || rawMin || rawMax || name || who;

  const notes = (census.method_notes || []).filter(readerSafe);
  const notesHeld = (census.method_notes || []).length - notes.length;
  const dark = census.dark_universe || {};
  const darkWhat = text(dark.what);
  const darkWindow = text(dark.window).split("..");
  const newNotices = numOr(dark.formd_new_notices);
  const amendments = numOr(dark.formd_amendments);

  const classOptions = [{ value: EITHER, label: "Every class" },
    ...Object.entries(classCounts)
      .sort((a, b) => b[1] - a[1])
      .map(([k, n]) => ({ value: k, label: `${classWords(k)} (${fmtInt(n)})` }))];

  return (
    <div className="stack-5">
      <PageHeader
        title={routeTitle("universe")}
        sub={"Every registered wrapper the record can find on file, with the class each one falls in, what its "
          + "filings tag and when it last filed. Every row here is tier one: a figure the filing tagged itself, "
          + "or a date and a count taken from the filer’s own submission history."}
        actions={<Link to="/funnel">{routeTitle("funnel")}</Link>}
      />

      <StatRow>
        <Stat label="Entities on file" value={fmtInt(census.total)}
          source={`As the record stood on ${fmtDate(census.as_of)}`} />
        <Stat label={CENSUS_FIELD.structured} value={fmtOf(structured, census.total)}
          source="The rest carry filing behavior and dates only" />
        <Stat label={CENSUS_FIELD.evaluated} value={fmtInt(evaluated)}
          source="Each one on the six-factor record" />
        <Stat label="Rows signed by a person" value={fmtInt(counts.verified || 0)}
          source={SAY.verificationPending} />
      </StatRow>

      <Card sunken>
        <CardHead title="How to read this page" level={2} />
        <Legend label="Tiers" items={TIERS.map((t, i) => ({
          label: t.label, kind: (["structured", "extracted", "verified"] as const)[i],
        }))} />
        <p className="t-13 t-3">
          Nothing on this page is read out of prose and nothing on it is signed by a person. Where a filing tags
          no figure, the row says so and the entity detail gives the reason the record holds. Across the evaluated
          record, {SAY.verificationCount(counts.verified || 0, counts.total || 0)}{" "}
          <Link to="/verification">See the verification queue</Link>
        </p>
      </Card>

      <section className="stack-4" aria-labelledby="universe-filters">
        <h2 id="universe-filters" className="t-20">Narrow the universe</h2>
        <Card>
          <div className="filterbar" role="group" aria-label="Filters">
            <Field label={CENSUS_FIELD.cls} inline>
              {(ids) => <Select ids={ids} small options={classOptions} value={fClass}
                onChange={(e) => setParams({ c_class: e.target.value })} />}
            </Field>
            <Field label={CENSUS_FIELD.listed} inline>
              {(ids) => <Select ids={ids} small value={fListed}
                options={[{ value: EITHER, label: "Either" }, { value: YES, label: "Listed" },
                  { value: NO, label: "Not listed" }]}
                onChange={(e) => setParams({ c_listed: e.target.value })} />}
            </Field>
            <Field label={CENSUS_FIELD.interval} inline>
              {(ids) => <Select ids={ids} small value={fInterval}
                options={[{ value: EITHER, label: "Either" }, { value: YES, label: "Files as one" },
                  { value: NO, label: "Does not" }]}
                onChange={(e) => setParams({ c_interval: e.target.value })} />}
            </Field>
            <Field label={CENSUS_FIELD.tender_count} inline>
              {(ids) => <Select ids={ids} small value={fWindows}
                options={[{ value: EITHER, label: "Either" }, { value: YES, label: "One or more on file" },
                  { value: NO, label: "None on file" }]}
                onChange={(e) => setParams({ c_windows: e.target.value })} />}
            </Field>
            <Field label={CENSUS_FIELD.evaluated} inline>
              {(ids) => <Select ids={ids} small value={fEval}
                options={[{ value: EITHER, label: "Either" }, { value: YES, label: "On the record" },
                  { value: NO, label: "Not evaluated" }]}
                onChange={(e) => setParams({ c_eval: e.target.value })} />}
            </Field>
            <Field label="Total assets, at least" hint="In millions of dollars" inline>
              {(ids) => <NumberInput ids={ids} small value={rawMin} placeholder="0…"
                onChange={(e) => setParams({ c_amin: e.target.value.replace(/[^0-9]/g, "") || null })} />}
            </Field>
            <Field label="Total assets, at most" hint="In millions of dollars" inline>
              {(ids) => <NumberInput ids={ids} small value={rawMax} placeholder="0…"
                onChange={(e) => setParams({ c_amax: e.target.value.replace(/[^0-9]/g, "") || null })} />}
            </Field>
            <Field label="Name contains" hint="Stays in this browser" inline>
              {(ids) => <Input ids={ids} small value={name} autoComplete="off"
                onChange={(e) => setName(e.target.value)} />}
            </Field>
            <Field label="Auditor or adviser contains" hint="Looked up only once you type" inline>
              {(ids) => <Input ids={ids} small value={who} autoComplete="off"
                onChange={(e) => setWho(e.target.value)} />}
            </Field>
            {filtered && (
              <Button variant="quiet" onClick={() => {
                setName(""); setWho("");
                setParams({ c_class: null, c_listed: null, c_interval: null, c_windows: null,
                  c_eval: null, c_amin: null, c_amax: null });
              }}>Clear the filters</Button>
            )}
          </div>
          <p className="t-13 t-3" aria-live="polite">
            {`Showing ${fmtOf(shown.length, rows.length)} entities.`}
            {shown.length > CAP && ` The table holds the first ${fmtInt(CAP)} of them in this order.`}
            {wantSearch && searching && ` Reading the auditor and adviser list${ELLIPSIS}`}
            {wantSearch && !searching && " The auditor and adviser text is on the entities whose annual census filing names one."}
          </p>
        </Card>
      </section>

      <section className="stack-4" aria-labelledby="universe-table">
        <h2 id="universe-table" className="t-20">Entities on file</h2>
        {rows.length === 0
          ? (
            <EmptyState title="No entity is on file">
              The record carries no universe rows. Once the sweep of the filings has run, every registered
              wrapper it found is listed here.
            </EmptyState>
          )
          : (
            <Table
              id="universe"
              caption={`Registered wrappers on file as the record stood on ${fmtDate(census.as_of)}. `
                + `The name opens what the record holds for that entity. ${SAY.verificationPending}`}
              columns={columns}
              rows={capped}
              rowKey={(row) => row.cik}
              sort={sort}
              onSort={(s) => setParams({ sort: s?.id || null, dir: s?.dir || null })}
              visible={visible}
              onVisible={(ids) => setParams({ cols: ids ? ids.join(".") : null })}
              empty={SAY.emptyFilter}
            />
          )}
      </section>

      <section className="stack-4" aria-labelledby="universe-shape">
        <h2 id="universe-shape" className="t-20">What the universe holds</h2>
        <div className="grid-2">
          <Card as="article" className="stack-2">
            <CardHead title="Wrappers by class" level={3} />
            <dl className="field-list">
              {Object.entries(classCounts).sort((a, b) => b[1] - a[1]).map(([k, n]) => (
                <Fragment key={k}>
                  <dt>{classWords(k)}</dt>
                  <dd className="t-num">{fmtInt(n)}</dd>
                </Fragment>
              ))}
              <dt>Every class</dt>
              <dd className="t-num">{fmtInt(census.total)}</dd>
            </dl>
          </Card>

          <Card as="article" className="stack-2">
            <CardHead title="What a plan fiduciary cannot see into" level={3} />
            {darkWhat
              ? <p className="t-14 t-2">{typographic(darkWhat)}</p>
              : <p className="t-13 t-3">The record carries no sentence about the funds outside this universe.</p>}
            {newNotices !== null && amendments !== null && (
              <p className="t-13 t-3">
                {`${fmtInt(newNotices)} new notices and ${fmtInt(amendments)} amendments`}
                {darkWindow.length === 2 ? `, from ${fmtDate(darkWindow[0])} to ${fmtDate(darkWindow[1])}.` : "."}
              </p>
            )}
          </Card>
        </div>

        <Card as="article" className="stack-2">
          <CardHead title="How the universe was put together" level={3} />
          {notes.length > 0
            ? (
              <ul className="stack-2">
                {notes.map((noteText) => <li key={noteText} className="t-13 t-2">{typographic(noteText)}</li>)}
              </ul>
            )
            : <p className="t-13 t-3">No note about how this universe was put together is in reader words.</p>}
          {notesHeld > 0 && (
            <p className="t-12 t-3">
              {notesHeld === 1
                ? "One further note is not shown because it is written in the collection step’s own shorthand rather than in words a reader can use."
                : `${fmtInt(notesHeld)} further notes are not shown because they are written in the collection step’s own shorthand rather than in words a reader can use.`}
            </p>
          )}
        </Card>
      </section>

      <Drawer open={!!openRow} onClose={() => setParams({ c_cik: null })}
        title={openRow ? openRow.name : ""}>
        {openRow && <EntityDetail census={census} row={openRow} />}
      </Drawer>
    </div>
  );
}

/* ---------------------------------------------------------- URL state */
/** A three-way filter from the URL: either, yes or no, and nothing else. */
function choice(v: string | null): string {
  return v === YES || v === NO ? v : EITHER;
}
/** A whole number from the URL, or nothing. */
function wholeNumber(v: string): number | null {
  if (!/^\d+$/.test(v)) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}
/** Whether a row passes a three-way filter over one bit of the flag field. */
function flagged(flags: number, bit: number, want: string): boolean {
  if (want === YES) return (flags & bit) !== 0;
  if (want === NO) return (flags & bit) === 0;
  return true;
}

/* The kitchen-sink route #/design: every token and every component in every
 * state, both themes. The guideline audit and axe-core run against it, and
 * Oscar approves the design system on it at the checkpoint (decision 8.2). */
import { useState } from "react";
import { PageHeader } from "../components/shell";
import { Button, Card, CardHead, Chip, EmptyState, Icon, Legend, Link, Skeleton, Stat, StatRow, Term, Tooltip, VerdictBanner, useToast } from "../components/primitives";
import type { ChipKind, IconName } from "../components/primitives";
import { Dialog, Disclosure, Drawer, Palette, Tabs } from "../components/overlay";
import { Checkbox, DateInput, Field, FileDownload, Input, NumberInput, PasswordInput, RadioGroup, Select, Slider, Textarea } from "../components/form";
import { Table, Gap } from "../components/table";
import type { SortState } from "../components/table";
import { ProgressList } from "../components/progress";
import { fmtDate, fmtInt, fmtMoneyCompact, fmtN, fmtOf, fmtPct, fmtRatio, NBSP } from "../format/format";
import { LineChart, Donut, BarChart } from "../charts/charts";

const INK = ["900", "800", "700", "600", "500", "400", "300", "200", "100", "50"];
const ACCENT = ["50", "100", "200", "300", "400", "500", "600", "700", "800", "900"];
const STATUS: { kind: ChipKind; label: string }[] = [
  { kind: "structured", label: "Structured" }, { kind: "extracted", label: "Extracted, unverified" }, { kind: "verified", label: "Verified" },
  { kind: "computed", label: "Computed" }, { kind: "partial", label: "Partial" }, { kind: "na", label: "Not applicable" }, { kind: "advisor", label: "Adviser input" },
];
const VERDICTS: { kind: ChipKind; label: string }[] = [
  { kind: "aligned", label: "Aligned" }, { kind: "conditional", label: "Conditional" }, { kind: "weak", label: "Conditional, weak" }, { kind: "misaligned", label: "Misaligned" },
  { kind: "illustrative", label: "Illustrative" }, { kind: "pending", label: "Pending" },
];
const ICONS: IconName[] = ["search", "menu", "close", "chevron", "chevronDown", "external", "cite", "pin", "check", "info", "download", "copy", "up", "down", "trash", "table", "chart", "sun", "moon", "plus", "arrowRight", "arrowLeft", "evaluate", "compare", "document", "plan"];

interface DemoRow { key: string; name: string; fee: number | null; pme: number | null; wrapper: string; status: ChipKind }
const ROWS: DemoRow[] = Array.from({ length: 60 }, (_, i) => ({
  key: `row${i}`, name: `Sample product ${i + 1}`, fee: i % 7 === 0 ? null : 0.5 + (i % 9) * 0.25, pme: i % 5 === 0 ? null : 0.9 + (i % 11) * 0.03,
  wrapper: ["Interval fund", "Tender offer fund", "Non-traded BDC", "Non-traded REIT"][i % 4], status: (["extracted", "computed", "partial", "structured"] as ChipKind[])[i % 4],
}));

export default function DesignView() {
  const toast = useToast();
  const [drawer, setDrawer] = useState(false);
  const [dialog, setDialog] = useState(false);
  const [palette, setPalette] = useState(false);
  const [tab, setTab] = useState("one");
  const [slider, setSlider] = useState(5);
  const [sort, setSort] = useState<SortState | null>(null);
  const [visible, setVisible] = useState<string[] | null>(null);
  const [radio, setRadio] = useState("a");
  const series = Array.from({ length: 24 }, (_, i) => ({ x: new Date(Date.UTC(2024, i, 1)).toISOString().slice(0, 10), y: 100 + Math.sin(i / 3) * 12 + i }));
  return (
    <div className="stack-5">
      <PageHeader eyebrow="Design system" title="Every token and component, in every state" sub="This page is the approval surface for the design checkpoint and the target of the guideline audit and axe-core. Switch the theme with the toggle in the bar." />

      <Card>
        <CardHead title="Color" level={2} />
        <div className="stack-4">
          <div>
            <div className="t-eyebrow">Ink scale</div>
            <div className="row">{INK.map((s) => <div key={s} className="stack-2" style={{ width: "var(--s-8)" }}><span className="skel" style={{ background: `var(--ink-${s})`, height: "var(--s-6)" }} aria-hidden="true" /><span className="t-12 t-3">{s}</span></div>)}</div>
          </div>
          <div>
            <div className="t-eyebrow">Accent, the plum</div>
            <div className="row">{ACCENT.map((s) => <div key={s} className="stack-2" style={{ width: "var(--s-8)" }}><span className="skel" style={{ background: `var(--accent-${s})`, height: "var(--s-6)" }} aria-hidden="true" /><span className="t-12 t-3">{s}</span></div>)}</div>
            <p className="t-13 t-2" style={{ marginTop: "var(--s-2)" }}>Text uses 700 (9.5:1 on white), non-text uses 500 (4.7:1). The alternative accent proposed at the checkpoint is an ink blue, shown in the decisions file. The focus ring is a separate blue so it stays visible on plum buttons.</p>
          </div>
          <div>
            <div className="t-eyebrow">Surfaces</div>
            <div className="row">{["paper", "panel", "panel-sunken", "line", "line-strong", "focus", "alarm"].map((s) => <div key={s} className="stack-2" style={{ width: "var(--s-8)" }}><span className="skel" style={{ background: `var(--${s})`, height: "var(--s-6)", border: "var(--bw) solid var(--line-strong)" }} aria-hidden="true" /><span className="t-12 t-3">{s}</span></div>)}</div>
          </div>
        </div>
      </Card>

      <Card>
        <CardHead title="Type" level={2} />
        <div className="stack-2">
          <div className="t-display t-32">Fraunces 32, the landing H1 and the wordmark only</div>
          <div className="t-24 t-semibold">Inter 24 semibold, a page title</div>
          <div className="t-20 t-semibold">Inter 20 semibold, a section title</div>
          <div className="t-16">Inter 16, body on the landing page</div>
          <div className="t-14">Inter 14, body everywhere else. Numbers set in tabular figures: <span className="tabular">1,048{NBSP}checks, 0.9756, $28.3M</span></div>
          <div className="t-13">Inter 13, table cells and buttons</div>
          <div className="t-12 t-3">Inter 12, captions and chips. Nothing on any surface is smaller.</div>
          <div className="t-eyebrow">An eyebrow, 12 px, 0.06em tracking</div>
          <p className="t-14">Curly quotes and apostrophes: “the plan’s filed outflow proxy”. Non-breaking spaces: {fmtN(5)}, 2%{NBSP}&lt;{NBSP}1{NBSP}year, ⌘{NBSP}K. Formatting: {fmtInt(3599)}, {fmtPct(11.69)}, {fmtRatio(1.0613)}, {fmtMoneyCompact(570_000_000)}, {fmtDate("2026-06-09")}, {fmtOf(8, 12)}.</p>
        </div>
      </Card>

      <Card>
        <CardHead title="Buttons and links" level={2} />
        <div className="stack-4">
          <div className="row-3">
            <Button variant="primary">Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="quiet">Quiet</Button>
            <Button variant="icon" icon="cite" label="Open the citation for cell 2.1" />
            <Button variant="primary" size="md" icon="download">Download the record</Button>
            <Button variant="primary" disabled>Disabled</Button>
            <Button variant="secondary" loading>Loading</Button>
            <Button variant="secondary" onClick={() => toast("Copied to the clipboard")}>Show a toast</Button>
            <Button variant="secondary" onClick={() => toast("Pin removed", { label: "Undo", onClick: () => toast("Pin restored") })}>Toast with undo</Button>
          </div>
          <div className="row-3">
            <Link to="/start">An in-app link</Link>
            <Link to="/start" quiet>A quiet link</Link>
            <Link href="https://www.sec.gov/" external>EDGAR, external</Link>
            <span className="kbd">⌘</span><span className="kbd">K</span>
            <span className="provenance">a code-styled provenance field: 0001213900-26-066804</span>
          </div>
          <p className="t-13 t-2">Every button shows rest, hover, focus-visible (the two-tone ring), active and disabled. Tab through this row to see the ring. Icon buttons carry an accessible name.</p>
        </div>
      </Card>

      <Card>
        <CardHead title="Chips and legends" level={2} />
        <div className="stack-4">
          <div><div className="t-eyebrow">Statuses</div><div className="row">{STATUS.map((s) => <Chip key={s.kind} kind={s.kind}>{s.label}</Chip>)}</div></div>
          <div><div className="t-eyebrow">Verdicts and markers</div><div className="row">{VERDICTS.map((s) => <Chip key={s.kind} kind={s.kind}>{s.label}</Chip>)}</div></div>
          <div><div className="t-eyebrow">Tiers and wrappers</div><div className="row"><Chip kind="tier">T1 structured</Chip><Chip kind="tier">T2 extracted</Chip><Chip kind="tier">T3 human-verified</Chip><Chip kind="wrapper">Interval fund</Chip><Chip kind="accent">Plan</Chip></div></div>
          <Legend items={[...STATUS.map((s) => ({ label: s.label, kind: s.kind }))]} label="Status legend" />
        </div>
      </Card>

      <Card>
        <CardHead title="Stats and banners" level={2} />
        <div className="stack-4">
          <StatRow>
            <Stat label="Filed outflow proxy" value={fmtPct(11.69)} source="Form 5500, plan year 2025" />
            <Stat label="Net assets" value={fmtMoneyCompact(570_000_000)} unit="plan" />
            <Stat label="KS-PME vs reference proxy" value={fmtRatio(1.0613)} source="Reference comparison, not the benchmark" large />
            <Stat label="Cells signed" value={fmtOf(0, 55)} source="Human verification: pending" />
          </StatRow>
          <VerdictBanner kind="aligned" label="Aligned" definition="The plan’s filed outflow rate fits inside the wrapper’s dealing capacity with headroom." chip={<Chip kind="illustrative">Illustrative</Chip>} legendTo="/design" />
          <VerdictBanner kind="conditional" label="Conditional" definition="Fits at the filed rate, thin under the stressed rate." />
          <VerdictBanner kind="weak" label="Conditional, weak" definition="Fits at the filed rate, exceeded under the stressed rate." />
          <VerdictBanner kind="misaligned" label="Misaligned" definition="The wrapper cannot meet the plan’s filed rate." />
          <VerdictBanner kind="partial" label="Partial" definition="A fact the verdict needs is not printed in the filings." />
          <VerdictBanner kind="pending" label="Human verification: pending" definition="0 of 55 cells signed. Offered to design partners." />
          <VerdictBanner kind="info" label="Meaningful benchmark by descriptor" definition="No comparison until its series is held." />
        </div>
      </Card>

      <Card>
        <CardHead title="Table" level={2}>
          <span className="t-12 t-3">60 rows, virtualized above 50, sortable, column picker, cards under 720 px</span>
        </CardHead>
        <Table<DemoRow> caption="Sample products (illustrative rows for the design system)" rows={ROWS} rowKey={(r) => r.key} sort={sort} onSort={setSort} visible={visible} onVisible={setVisible}
          maxHeight="var(--table-max)"
          columns={[
            { id: "name", header: "Product", label: "Product", fixed: true, cell: (r) => <Link to="/design" quiet><span translate="no">{r.name}</span></Link>, sortValue: (r) => r.name },
            { id: "wrapper", header: "Wrapper", label: "Wrapper", cell: (r) => <Chip kind="wrapper">{r.wrapper}</Chip>, sortValue: (r) => r.wrapper },
            { id: "fee", header: "Management fee", label: "Management fee", numeric: true, cell: (r) => r.fee === null ? <Gap reason="not printed in the filings" /> : fmtPct(r.fee), sortValue: (r) => r.fee },
            { id: "pme", header: "KS-PME vs reference proxy", label: "KS-PME vs reference proxy", numeric: true, cell: (r) => r.pme === null ? <Gap reason="no public series held" /> : fmtRatio(r.pme), sortValue: (r) => r.pme },
            { id: "status", header: "Status", label: "Status", cell: (r) => <Chip kind={r.status}>{STATUS.find((s) => s.kind === r.status)?.label}</Chip> },
            { id: "cite", header: "Source", label: "Source", cell: () => <Button variant="icon" icon="cite" label="Open the citation" onClick={() => setDrawer(true)} /> },
          ]} />
      </Card>

      <Card>
        <CardHead title="Charts" level={2}>
          <span className="t-12 t-3">Responsive SVG, text at token sizes, table alternative, keyboard tooltips</span>
        </CardHead>
        <div className="two-col">
          <LineChart title="A sample series" description="Twenty-four monthly points rising with a sine wave, illustrative." series={[{ id: "a", label: "Sample series", points: series }]} yFormat={(v) => fmtInt(v)} />
          <div className="stack-4">
            <Donut title="Coverage of a sample record" segments={[{ label: "Extracted", value: 38, color: "var(--status-extracted-fg)" }, { label: "Computed", value: 11, color: "var(--status-computed-fg)" }, { label: "Partial", value: 4, color: "var(--status-partial-fg)" }, { label: "Not applicable", value: 2, color: "var(--ink-300)" }]} center="0" centerSub="signed" size={120} />
            <BarChart title="Expense ratios" description="Four sample expense ratios, illustrative." bars={[{ label: "Fund A", value: 1.36 }, { label: "Fund B", value: 2.1 }, { label: "Fund C", value: 0.95 }, { label: "Fund D", value: 3.31 }]} format={(v) => fmtPct(v)} />
          </div>
        </div>
      </Card>

      <Card>
        <CardHead title="Forms" level={2} />
        <div className="two-col">
          <div className="stack-4">
            <Field label="Plan name" hint="Shown under its anonymized label on every surface." required>{(ids) => <Input ids={ids} name="plan_name" autoComplete="organization" placeholder="Regional hospital 403(b) plan…" />}</Field>
            <Field label="Net assets, end of year" hint="Dollars, from Form 5500 Schedule H.">{(ids) => <NumberInput ids={ids} name="net_assets" placeholder="570000000" />}</Field>
            <Field label="Plan year end">{(ids) => <DateInput ids={ids} name="plan_year_end" />}</Field>
            <Field label="Wrapper" error="Choose a wrapper class.">{(ids) => <Select ids={ids} name="wrapper" options={[{ value: "", label: "Choose…" }, { value: "interval", label: "Interval fund" }, { value: "tender", label: "Tender offer fund" }]} />}</Field>
            <Field label="Password">{(ids) => <PasswordInput ids={ids} name="password" />}</Field>
          </div>
          <div className="stack-4">
            <Field label="Adviser statement" hint="Recorded as adviser input, never as a filing fact.">{(ids) => <Textarea ids={ids} name="statement" rows={4} />}</Field>
            <Checkbox label="Verified only" name="vonly" />
            <RadioGroup label="Density" name="density" value={radio} onChange={setRadio} options={[{ value: "a", label: "Comfortable" }, { value: "b", label: "Compact" }]} />
            <Slider label="Allocation to the fund" value={slider} min={1} max={20} step={1} onChange={setSlider} format={(v) => fmtPct(v, 0)} hint="Moves the plan’s dollar demand against the fund’s dollar capacity." liveText={`Allocation ${fmtPct(slider, 0)}, demand ${fmtMoneyCompact(570_000_000 * slider / 100 * 0.1169)}`} />
            <FileDownload name="plan_intake_sample.json" text={JSON.stringify({ sample: true, allocation_pct: slider }, null, 2)} description="A real download: the bytes are the text on screen." />
          </div>
        </div>
      </Card>

      <Card>
        <CardHead title="Overlays, tabs, disclosures, tooltips" level={2} />
        <div className="stack-4">
          <div className="row-3">
            <Button variant="secondary" onClick={() => setDrawer(true)}>Open a drawer</Button>
            <Button variant="secondary" onClick={() => setDialog(true)}>Open a dialog</Button>
            <Button variant="secondary" onClick={() => setPalette(true)}>Open the palette</Button>
            <span>A defined term: <Term def="Kaplan-Schoar public market equivalent: the ratio of the fund’s distributions and residual value to the value the same contributions would have reached in the public proxy.">KS-PME</Term></span>
            <Tooltip content="Everything a tooltip says is reachable by keyboard and by tap."><span>Tooltip</span></Tooltip>
          </div>
          <Tabs label="Sample tabs" value={tab} onChange={setTab} tabs={[{ id: "one", label: "Analysis", panel: <p>The first panel.</p> }, { id: "two", label: "De-smoothing", panel: <p>The second panel.</p> }]} />
          <Disclosure summary="Full text and provenance"><p>A collapsed body with its chevron marked decorative and a summary that is a real disclosure button.</p></Disclosure>
          <Disclosure summary="How this is computed" plain><p>A plain disclosure without a card border.</p></Disclosure>
        </div>
      </Card>

      <Card>
        <CardHead title="Progress, empty and loading states" level={2} />
        <div className="two-col">
          <ProgressList steps={[
            { id: "q", label: "Queued", state: "done", seconds: 2 }, { id: "f", label: "Fetching filings", state: "done", seconds: 41 },
            { id: "x", label: "Extracting cells", detail: `Cell ${fmtOf(12, 55)}`, state: "active", seconds: 130 },
            { id: "b", label: "Computing the benchmark and the liquidity match", state: "todo" }, { id: "w", label: "Writing the documents", state: "todo" },
          ]} />
          <div className="stack-4">
            <EmptyState title="No plan yet" action={<Button variant="primary" icon="plus">Add your plan</Button>}>Create a plan from the intake fields or pick a reference plan.</EmptyState>
            <Skeleton lines={4} label="Loading the record" />
          </div>
        </div>
      </Card>

      <Card>
        <CardHead title="Icons" level={2} />
        <div className="row-3">{ICONS.map((n) => <span key={n} className="stack-2" style={{ width: "var(--s-8)", textAlign: "center" }}><Icon name={n} /><span className="t-12 t-3" style={{ display: "block" }}>{n}</span></span>)}</div>
      </Card>

      <Drawer open={drawer} onClose={() => setDrawer(false)} title="2.1 · Management fee (Sample product)">
        <dl className="field-list">
          <dt>Document</dt><dd translate="no">N-CSR FY2026 (filed June 9, 2026)</dd>
          <dt>Section</dt><dd>Notes to financial statements, note 4</dd>
          <dt>Verbatim quote</dt><dd><blockquote className="quote">“The Adviser is entitled to a management fee at an annual rate of 1.50% of the Fund’s net assets.”</blockquote></dd>
          <dt>EDGAR</dt><dd><Link href="https://www.sec.gov/" external>N-CSR 2026-06-09 0001213900-26-066804</Link></dd>
          <dt>Extracted by</dt><dd>Tark extraction, July 2026</dd>
          <dt>Human verification</dt><dd><Chip kind="pending">Pending</Chip> a person verifies the row through the verification step</dd>
        </dl>
      </Drawer>
      <Dialog open={dialog} onClose={() => setDialog(false)} title="Remove this pin?">
        <div className="drawer__body"><p>The pin can be restored from the toast for a few seconds.</p><div className="form-actions"><Button variant="primary" onClick={() => { setDialog(false); toast("Pin removed", { label: "Undo", onClick: () => undefined }); }}>Remove</Button><Button variant="secondary" onClick={() => setDialog(false)}>Keep</Button></div></div>
      </Dialog>
      <Palette open={palette} onClose={() => setPalette(false)} items={[
        { id: "start", label: "Start", kind: "View", run: () => undefined }, { id: "screener", label: "Screener", kind: "View", run: () => undefined },
        { id: "hl_paf", label: "Hamilton Lane Private Assets Fund", kind: "Product", hint: "Tender offer fund", run: () => undefined },
        { id: "plan", label: "Technology and media company 401(k) plan", kind: "Plan", run: () => undefined },
      ]} />
    </div>
  );
}

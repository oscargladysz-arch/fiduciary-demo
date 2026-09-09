/* The committee packet: the rows a reader has collected, and the documents
 * written for a fund and a plan.
 *
 * A pin is (fund, row). It lives in this browser only, which the page says out
 * loud, because nothing here is kept on a server. Every pin prints the row’s
 * element name beside its number, and a pin that carries no name says so
 * rather than printing an empty word: the old site printed the fund, the row
 * number and nothing after it.
 *
 * Reordering is two buttons rather than a drag, so a keyboard alone can do it,
 * and each button’s name says which row it moves. Removing a row offers an
 * undo that puts the row back where it stood. Clearing the packet is the one
 * action with no undo, so it asks first. */
import { useCallback, useMemo, useState } from "react";
import { planLabel, planOptions, usePlan } from "../app/plan";
import { usePins } from "../app/pins";
import type { Pin } from "../app/pins";
import { Dialog } from "../components/overlay";
import { Button, Card, CardHead, EmptyState, Icon, Link, Skeleton, useToast } from "../components/primitives";
import { ContextChip, PageHeader } from "../components/shell";
import { SAY, routeTitle } from "../copy/copy";
import { useAsync, useIndex } from "../data/hooks";
import { data, dataErrorSentence } from "../data/index";
import { fmtInt } from "../format/format";
import type { DocumentsView, IndexView } from "../data/types";

/** A pin with the place it holds in the reader’s own order. */
interface Item { pin: Pin; at: number }
interface Group { key: string; fundName: string; items: Item[] }
/** The documents chunk for one fund, or the reason it could not be read. */
interface DocEntry { key: string; doc: DocumentsView | null; error: string | null }

const NO_NAME = "The name of this row is not on record.";

/** A document beside the built site, addressed from the document’s own base,
 *  so the same page serves the site root and a preview under a subpath. */
function memoHref(name: string): string {
  return new URL("memos/" + name, document.baseURI).toString();
}

/** The fund’s name as the record holds it, else the name the pin carried. */
function fundNameOf(index: IndexView | null, pin: Pin): string {
  const known = (index?.products || []).find((p) => p.key === pin.productKey);
  return known?.fund_name || pin.fundName || "";
}

function plural(n: number, one: string, many: string): string {
  return n === 1 ? one : many;
}

export default function PacketView() {
  const { value: index, error, loading } = useIndex();
  const [plan, setPlan] = usePlan(index);
  const { pins, add, remove, restore, move, clear } = usePins();
  const toast = useToast();
  const [confirming, setConfirming] = useState(false);
  const [said, setSaid] = useState("");

  /* Grouped by fund, in the order the reader collected them: the first fund
   * pinned leads, and within a fund the pins keep their own order. */
  const groups = useMemo<Group[]>(() => {
    const byKey = new Map<string, Group>();
    const order: string[] = [];
    pins.forEach((pin, at) => {
      let g = byKey.get(pin.productKey);
      if (!g) {
        g = { key: pin.productKey, fundName: fundNameOf(index, pin), items: [] };
        byKey.set(pin.productKey, g);
        order.push(pin.productKey);
      }
      g.items.push({ pin, at });
    });
    return order.map((k) => byKey.get(k) as Group);
  }, [pins, index]);

  const fundsKey = groups.map((g) => g.key).join(",");

  /* One documents chunk per fund with a pin. A fund whose chunk cannot be read
   * carries its own sentence rather than emptying the page. */
  const { value: docs, loading: docsLoading } = useAsync<DocEntry[]>(() => {
    const keys = fundsKey ? fundsKey.split(",") : [];
    if (!plan || keys.length === 0) return Promise.resolve([]);
    return Promise.all(keys.map((k) => data().getDocuments(plan, k).then(
      (doc): DocEntry => ({ key: k, doc, error: null }),
      (e): DocEntry => ({ key: k, doc: null, error: dataErrorSentence(e) }),
    )));
  }, [plan, fundsKey]);

  const onMove = useCallback((g: Group, j: number, delta: number) => {
    const from = g.items[j];
    const to = g.items[j + delta];
    if (!from || !to) return;
    move(from.at, to.at);
    const name = (from.pin.element || "").trim();
    setSaid(`${from.pin.cell}${name ? `, ${name}` : ""} is now ${fmtInt(j + delta + 1)} of `
      + `${fmtInt(g.items.length)} under ${g.fundName}.`);
  }, [move]);

  const onRemove = useCallback((pin: Pin, at: number) => {
    const gone = remove(pin.productKey, pin.cell);
    if (!gone) return;
    const name = (gone.element || "").trim();
    const what = `${gone.cell}${name ? `, ${name}` : ""}`;
    toast(`Removed ${what} from the packet.`, {
      label: "Undo",
      onClick: () => {
        // add is what refuses a duplicate, so a row already back in the packet
        // is not copied. It appends, so the row is then put back where it stood.
        if (add(gone) === "already") {
          toast(`${what} is already in the packet.`);
          return;
        }
        remove(gone.productKey, gone.cell);
        restore(gone, at);
      },
    });
  }, [add, remove, restore, toast]);

  if (error) return <EmptyState title={SAY.noRecord}>{error}</EmptyState>;
  if (loading || !index) return <Skeleton lines={8} label={SAY.loadingRecord} />;

  const label = planLabel(index, plan);
  const signed = index.coverage_totals.counts.verified ?? 0;
  const cells = Number(index.coverage_totals.total ?? 0);
  const docByKey = new Map((docs || []).map((d) => [d.key, d]));

  return (
    <div className="stack-5">
      <PageHeader
        title={routeTitle("packet")}
        sub={"A packet is the set of rows you have pinned from the records, kept beside the documents written "
          + "for the fund and the plan. Pins live in this browser only and are not stored anywhere else."}
        actions={
          <div className="row-3 no-print">
            <Button icon="document" onClick={() => window.print()}>Print the packet</Button>
            {pins.length > 0 && (
              <Button icon="trash" aria-haspopup="dialog" onClick={() => setConfirming(true)}>
                Clear the packet
              </Button>
            )}
          </div>
        }
      />

      <p className="print-only t-13">Committee packet for {label}. {SAY.verificationPending}</p>

      <Card>
        <CardHead title="Your plan" level={2} />
        <ContextChip id="packet-plan" label="Plan" value={plan} options={planOptions(index)}
          onChange={setPlan} note={SAY.planDependent} />
        <p className="t-13 t-3">The documents below are written for the plan selected here. {SAY.anonymized}</p>
      </Card>

      <section className="stack-4" aria-labelledby="packet-rows">
        <h2 id="packet-rows" className="t-20">Pinned rows</h2>
        <p className="t-13 t-3" aria-live="polite">
          {fmtInt(pins.length)} {plural(pins.length, "row", "rows")} pinned, across{" "}
          {fmtInt(groups.length)} {plural(groups.length, "fund", "funds")}.
        </p>

        {groups.length === 0 ? (
          <EmptyState title="Nothing is pinned yet"
            action={<Link to="/screener">Open the screener</Link>}>
            Open the record for a fund and use the button that adds a row to the packet. Every row you add
            appears here, grouped by fund, with the documents for the plan you have selected.
          </EmptyState>
        ) : groups.map((g) => (
          <Card key={g.key} as="article" className="stack-4">
            <CardHead title={<span translate="no">{g.fundName || SAY.noRecord}</span>} level={3}>
              <span className="t-13 t-3">
                {fmtInt(g.items.length)} {plural(g.items.length, "row", "rows")}
              </span>
            </CardHead>
            <div className="stack-4" role="list">
              {g.items.map((it, j) => {
                const name = (it.pin.element || "").trim();
                const what = `${it.pin.cell}, ${name || "name not on record"}, ${g.fundName}`;
                return (
                  <div key={`${it.pin.productKey}:${it.pin.cell}`} className="stack-2" role="listitem">
                    <div className="row-3">
                      <span className="t-eyebrow" translate="no">{it.pin.cell}</span>
                      <span className={name ? "t-medium" : "t-13 t-3"}>{name || NO_NAME}</span>
                      <span className="spacer" />
                      <Button variant="quiet" icon="up" disabled={j === 0}
                        aria-label={`Move up ${what}`} onClick={() => onMove(g, j, -1)}>Move up</Button>
                      <Button variant="quiet" icon="down" disabled={j === g.items.length - 1}
                        aria-label={`Move down ${what}`} onClick={() => onMove(g, j, 1)}>Move down</Button>
                      <Button variant="quiet" icon="trash"
                        aria-label={`Remove ${what} from the packet`}
                        onClick={() => onRemove(it.pin, it.at)}>Remove</Button>
                    </div>
                    <div className="row-3">
                      <span className="t-13 t-3" translate="no">{g.fundName || SAY.noRecord}</span>
                      <Link to={`/product/${it.pin.productKey}/record`}
                        params={{ plan, factor: it.pin.cell.split(".")[0] }}
                        aria-label={`Open the row ${what} in the record`}>Open the row</Link>
                      {!name && (
                        <span className="t-13 t-3">Pin it again from the record to carry the name across.</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        ))}
      </section>

      {groups.length > 0 && (
        <section className="stack-4" aria-labelledby="packet-docs">
          <h2 id="packet-docs" className="t-20">Documents</h2>
          <p className="t-14 t-2">
            One Investment Selection Record for each fund in the packet, written for {label}, with the text of
            the rule attached. {SAY.planDependent}
          </p>
          {docsLoading && <Skeleton lines={4} label={SAY.loadingRecord} />}
          {!docsLoading && groups.map((g) => {
            const entry = docByKey.get(g.key);
            return (
              <Card key={g.key} as="article" className="stack-2">
                <CardHead title={<span translate="no">{g.fundName || SAY.noRecord}</span>} level={3} />
                {!entry || entry.error ? (
                  <p className="t-13 t-3">{entry?.error || SAY.noRecord}</p>
                ) : (
                  <>
                    {entry.doc && entry.doc.record ? (
                      <div className="download">
                        <div className="download__row">
                          <Icon name="document" />
                          <span className="download__name">Investment Selection Record</span>
                          <span className="spacer" />
                          <Link href={memoHref(entry.doc.record)} download
                            aria-label={`Download the Investment Selection Record for ${g.fundName} and ${label}`}>
                            Download<Icon name="download" size="sm" />
                          </Link>
                        </div>
                        <div className="download__meta">Written for {g.fundName} and {label}.</div>
                      </div>
                    ) : (
                      <p className="t-13 t-3">No Investment Selection Record has been written for this fund and this plan.</p>
                    )}
                    {entry.doc && entry.doc.attachment ? (
                      <div className="download">
                        <div className="download__row">
                          <Icon name="document" />
                          <span className="download__name">Attachment A, the text of the rule</span>
                          <span className="spacer" />
                          <Link href={memoHref(entry.doc.attachment)} download
                            aria-label={`Download Attachment A, the text of the rule, beside the record for ${g.fundName}`}>
                            Download<Icon name="download" size="sm" />
                          </Link>
                        </div>
                        <div className="download__meta">
                          The verbatim text of paragraphs {index.rule.paragraphs} of the proposed rule.{" "}
                          {index.rule.citation}
                        </div>
                      </div>
                    ) : (
                      <p className="t-13 t-3">Attachment A is not attached here.</p>
                    )}
                  </>
                )}
              </Card>
            );
          })}
        </section>
      )}

      <Card sunken>
        <CardHead title="How to read this packet" level={2} />
        <p className="t-14 t-2">
          A pinned row is a pointer into the record rather than a copy of it. Open a row to read the document,
          the section and the sentence it was taken from.
        </p>
        <p className="t-13 t-3">
          {SAY.verificationPending} {SAY.verificationCount(signed, cells)}{" "}
          <Link to="/verification">See the verification queue</Link>
        </p>
      </Card>

      <Dialog open={confirming} onClose={() => setConfirming(false)} title="Clear the packet">
        <div className="stack-4">
          <p className="t-14 t-2">
            Clearing removes every pinned row from this browser. Removing one row offers an undo. Clearing the
            packet does not.
          </p>
          <div className="row-3">
            <Button variant="primary"
              onClick={() => { clear(); setConfirming(false); toast("The packet is empty."); }}>
              Clear the packet
            </Button>
            <Button onClick={() => setConfirming(false)}>Keep the packet</Button>
          </div>
        </div>
      </Dialog>

      <p className="sr-only" aria-live="polite">{said}</p>
    </div>
  );
}

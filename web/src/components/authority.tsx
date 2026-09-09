/* The authority panel: the rule this record maps to, in the rule's own words.
 *
 * It is reachable from every route, because the question it answers ("what
 * does the rule actually say") comes up on every route. It opens as a dialog
 * that takes focus and returns it, fetches the paragraphs only when a reader
 * opens it, and closes on a route change rather than following the reader
 * around.
 *
 * The paragraphs are the Federal Register's text, unedited, fetched once and
 * carried with the hash of what was fetched. Nothing here is paraphrased: a
 * paraphrase of a rule is a claim about the rule. */
import { useEffect, useState } from "react";
import { useRoute } from "../app/router";
import { Drawer } from "./overlay";
import { Button, EmptyState, Link, Skeleton } from "./primitives";
import { SAY } from "../copy/copy";
import { useAsync } from "../data/hooks";
import { data } from "../data/index";
import { fmtDate, hashPrefix } from "../format/format";
import type { AuthorityView } from "../data/types";

const LETTERS = ["g", "h", "i", "j", "k", "l"];

function Body() {
  const { value, error, loading } = useAsync<AuthorityView>(
    () => (data().getAuthority ? data().getAuthority!() : Promise.reject(new Error("no authority"))), []);
  if (error) return <EmptyState title={SAY.noRecord}>{error}</EmptyState>;
  if (loading || !value) return <Skeleton lines={8} label="Loading the rule" />;

  const rule = (value.rule || {}) as Record<string, string>;
  const auth = value.authority || {};
  const paragraphs = auth.paragraphs || {};
  const fetched = auth.fetched_at as string | undefined;
  const sha = auth.sha256 as string | undefined;

  return (
    <div className="stack-4">
      <p className="t-14 t-2">
        This record maps to {value.citation}, proposed 29 CFR 2550.404a-6, paragraphs (g) to (l). Every row
        of every fund carries the paragraph it answers.
      </p>
      <dl className="field-list">
        <dt>Citation</dt>
        <dd>{value.citation}</dd>
        {rule.docket && (<><dt>Docket</dt><dd>{rule.docket}</dd></>)}
        {fetched && (<><dt>Text read on</dt><dd>{fmtDate(fetched)}</dd></>)}
        {sha && (<><dt>Fingerprint of what was read</dt>
          <dd className="provenance">{hashPrefix(sha, 12)}</dd></>)}
      </dl>
      <div className="row-3">
        {rule.fr_url && <Link href={rule.fr_url} external>The rule in the Federal Register</Link>}
        {rule.docket_url && <Link href={rule.docket_url} external>The docket</Link>}
      </div>

      {LETTERS.filter((l) => paragraphs[l]).map((letter) => (
        <section key={letter} className="stack-2">
          <h3 className="t-16">Paragraph ({letter})</h3>
          <blockquote className="quote" data-verbatim="true">
            {(paragraphs[letter] || []).map((para, i) => <p key={i}>{para}</p>)}
          </blockquote>
        </section>
      ))}

      {!LETTERS.some((l) => paragraphs[l]) && (
        <EmptyState title="The rule text is not on this record">
          The citation and the links above are on record. The paragraphs are read from the Federal
          Register and are not part of what has been published here.
        </EmptyState>
      )}

      <p className="t-13 t-3">
        The words above are the Federal Register's, unedited. Where this record summarises a paragraph it
        says so and links back to it.
      </p>
    </div>
  );
}

/** The control that opens the panel. It lives in the shell, so it is on every
 *  route, and the panel closes when the route changes. */
export function AuthorityButton() {
  const [open, setOpen] = useState(false);
  const r = useRoute();
  useEffect(() => { setOpen(false); }, [r.hash]);
  return (
    <>
      <Button variant="quiet" icon="document" onClick={() => setOpen(true)} aria-haspopup="dialog"
        aria-label="Read the rule this record maps to">
        The rule
      </Button>
      <Drawer open={open} onClose={() => setOpen(false)} title="The rule this record maps to">
        {open && <Body />}
      </Drawer>
    </>
  );
}

/* Start (R3-P1-1). The landing view, built on the three things an adviser
 * comes here to do: evaluate a fund for a plan, compare candidates, produce
 * the committee document.
 *
 * No table. The Screener is one click away. What is on the first paint is
 * complete (rule 20): the three cards, the plan selector, a finder over the
 * evaluated products and the wider universe, the tier legend, and the one
 * sentence about human verification, all from the index chunk. */
import { useId, useMemo, useState } from "react";
import { navigate } from "../app/router";
import { planOptions, usePlan } from "../app/plan";
import { Card, CardHead, Chip, EmptyState, Icon, Legend, Link, Skeleton, Stat, StatRow, Term }
  from "../components/primitives";
import { ContextChip, PageHeader } from "../components/shell";
import { Field, Input } from "../components/form";
import { SAY, TIERS } from "../copy/copy";
import { useIndex } from "../data/hooks";
import { fmtInt, fmtOf } from "../format/format";

interface Found { key: string; name: string; sub: string; to: string; evaluated: boolean }

export default function StartView() {
  const { value: index, error, loading } = useIndex();
  const [plan, setPlan] = usePlan(index);
  const [q, setQ] = useState("");
  const listId = useId();

  const hits = useMemo<Found[]>(() => {
    if (!index || q.trim().length < 2) return [];
    const needle = q.trim().toLowerCase();
    return index.products
      .filter((p) => p.fund_name.toLowerCase().includes(needle) || p.wrapper_label.toLowerCase().includes(needle))
      .slice(0, 8)
      .map((p) => ({
        key: p.key, name: p.fund_name, sub: p.wrapper_label,
        to: `/product/${p.key}/record`, evaluated: true,
      }));
  }, [index, q]);

  if (error) return <EmptyState title={SAY.noRecord}>{error}</EmptyState>;
  if (loading || !index) return <Skeleton lines={8} label={SAY.loadingRecord} />;

  const counts = index.coverage_totals.counts || {};
  const products = index.products.length;

  return (
    <div className="stack-5">
      <PageHeader
        display
        title="Evaluate an alternative investment for a retirement plan"
        sub={"Every figure on this site is read from a filing and cited, or calculated from figures that are. "
          + "Where a number is a scenario you set, it is marked illustrative."}
      />

      <StatRow>
        <Stat label="Products evaluated" value={fmtInt(products)} source="Each on the same six-factor record" />
        <Stat label="Cells resolved" value={fmtOf(counts.resolved, counts.resolvable)}
          source="Structured, extracted, computed or answered not applicable" />
        <Stat label="Cells with a filing behind them" value={fmtInt(counts.evidenced)}
          source="A document, a section and a quote you can open" />
        <Stat label="Cells signed by a person" value={fmtInt(counts.verified)}
          source={SAY.verificationPending} />
      </StatRow>

      <section className="stack-4" aria-labelledby="start-tasks">
        <h2 id="start-tasks" className="t-20">Start with a task</h2>
        <div className="entrycards">
          <Link to="/screener" quiet className="card card--link entrycard">
            <Icon name="evaluate" size="lg" />
            <h3 className="card__title">Evaluate a Fund for My Plan</h3>
            <p className="t-14 t-2">Open the record for one fund: the six factors, every figure with the filing
              behind it, and what its dealing terms mean for the plan you have selected.</p>
          </Link>
          <Link to="/compare" quiet className="card card--link entrycard">
            <Icon name="compare" size="lg" />
            <h3 className="card__title">Compare Candidates</h3>
            <p className="t-14 t-2">Put two to four funds side by side on the same rows, with the differences
              that matter marked and each one traceable to its source.</p>
          </Link>
          <Link to="/packet" quiet className="card card--link entrycard">
            <Icon name="document" size="lg" />
            <h3 className="card__title">Produce the Committee Document</h3>
            <p className="t-14 t-2">Build the Investment Selection Record for a fund and a plan, with the rule
              text attached and every figure cited.</p>
          </Link>
        </div>
      </section>

      <div className="two-col">
        <Card>
          <CardHead title="Your plan" level={2} />
          <p className="t-14 t-2">Four reference plans stand in for the sponsors we work with, each anonymized.
            The panels that depend on the plan say so.</p>
          <ContextChip id="start-plan" label="Plan" value={plan} options={planOptions(index)} onChange={setPlan} />
          <p className="t-13 t-3">{(index.plans.find((p) => p.key === plan) || {}).demand_sentence}</p>
          <Link to="/plans" params={{ plan }}>See the four plans and add your own</Link>
        </Card>

        <Card>
          <CardHead title="Find a fund" level={2} />
          <Field label="Fund name or wrapper" hint="Type two letters or more">
            {(ids) => (
              <Input ids={ids} value={q} onChange={(e) => setQ(e.target.value)} type="search"
                autoComplete="off" spellCheck={false} aria-controls={listId} />
            )}
          </Field>
          <div id={listId} className="finder" aria-live="polite">
            {q.trim().length >= 2 && hits.length === 0 && (
              <p className="t-14 t-2">No evaluated fund matches that. The universe holds every registered
                wrapper on file. <Link to="/universe">Search the universe</Link></p>
            )}
            {hits.length > 0 && (
              <>
                <p className="sr-only">{hits.length} matching funds</p>
                <ul className="finder__list">
                  {hits.map((h) => (
                    <li key={h.key}>
                      <Link to={h.to} params={{ plan }} quiet>
                        <span className="t-medium">{h.name}</span>
                        <span className="t-13 t-3">{h.sub}</span>
                        <Chip kind="tier">Evaluated</Chip>
                      </Link>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
          <p className="t-13 t-3">
            Not one of the {fmtInt(products)} evaluated funds?{" "}
            <Link to="/universe">Search the whole universe of registered wrappers</Link>
          </p>
        </Card>
      </div>

      <Card sunken>
        <CardHead title="How to read the record" level={2} />
        <p className="t-14 t-2">
          Each row of the record carries the tier it sits in. A{" "}
          <Term def={TIERS[1].definition}>cited</Term> row opens the document, the section and the sentence it
          came from. Nothing on this site is human-verified yet: {SAY.verificationCount(counts.verified || 0, counts.total || 0)}
          {" "}An agent re-check is not verification and is never counted as one.
        </p>
        <Legend label="Tiers" items={TIERS.map((t, i) => ({
          label: t.label, kind: (["structured", "extracted", "verified"] as const)[i],
        }))} />
        <p className="t-13 t-3">
          {SAY.anonymized} The rule this record maps to is {index.rule.citation}, paragraphs{" "}
          {index.rule.paragraphs}.{" "}
          <Link to="/coverage">See coverage and provenance</Link>
        </p>
      </Card>

      <p className="t-13 t-3">
        Prefer the table? <Link to="/screener" onClick={() => navigate("/screener")}>Open the screener</Link>
      </p>
    </div>
  );
}

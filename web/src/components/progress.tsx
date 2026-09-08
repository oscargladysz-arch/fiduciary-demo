/* ProgressList for job status: each step with its state and time. */
import { fmtElapsed } from "../format/format";
import { Icon } from "./primitives";

export type StepState = "done" | "active" | "todo" | "failed";
export interface Step { id: string; label: string; detail?: string; state: StepState; seconds?: number }
export function ProgressList({ steps, label = "Progress" }: { steps: Step[]; label?: string }) {
  const active = steps.find((s) => s.state === "active");
  return (
    <div>
      <ol className="progress" aria-label={label}>
        {steps.map((s, i) => (
          <li key={s.id} className="progress__step" aria-current={s.state === "active" ? "step" : undefined}>
            <span className={`progress__mark progress__mark--${s.state}`} aria-hidden="true">
              {s.state === "done" ? <Icon name="check" size="sm" /> : s.state === "failed" ? <Icon name="close" size="sm" /> : i + 1}
            </span>
            <span>
              <span className="t-medium">{s.label}</span>
              <span className="sr-only">, {s.state === "done" ? "done" : s.state === "active" ? "in progress" : s.state === "failed" ? "failed" : "not started"}</span>
              {s.detail && <div className="progress__detail">{s.detail}</div>}
            </span>
            <span className="progress__time">{s.seconds !== undefined ? fmtElapsed(s.seconds) : ""}</span>
          </li>
        ))}
      </ol>
      <div className="sr-only" aria-live="polite">{active ? `${active.label}${active.detail ? `, ${active.detail}` : ""}` : ""}</div>
    </div>
  );
}

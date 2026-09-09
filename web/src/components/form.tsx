/* Form primitives: Field (label, hint, inline error with aria-describedby),
 * Input, NumberInput (inputmode), DateInput, Select, Checkbox, Radio, Slider
 * (visible value, aria-valuetext, live region), Textarea, PasswordInput with a
 * show toggle, FileDownload (a real <a download> with size, plus copy), an
 * unsaved-changes guard. */
import { forwardRef, useEffect, useId, useMemo, useRef, useState } from "react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { Button, Icon, useToast } from "./primitives";
import { fmtBytes } from "../format/format";

interface FieldProps { label: ReactNode; hint?: ReactNode; error?: ReactNode; required?: boolean; children: (ids: { id: string; describedBy?: string; invalid: boolean }) => ReactNode; inline?: boolean }
export function Field({ label, hint, error, required, children, inline }: FieldProps) {
  const id = useId();
  const ids = [hint ? `${id}-h` : "", error ? `${id}-e` : ""].filter(Boolean).join(" ") || undefined;
  return (
    <div className={`field${inline ? " field--inline" : ""}`}>
      <label htmlFor={id} className="field__label">{label}{required && <span aria-hidden="true"> *</span>}</label>
      {children({ id, describedBy: ids, invalid: !!error })}
      {hint && <div id={`${id}-h`} className="field__hint">{hint}</div>}
      {error && <div id={`${id}-e`} className="field__error" role="alert">{error}</div>}
    </div>
  );
}

type Ids = { id: string; describedBy?: string; invalid: boolean };
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { ids?: Ids; small?: boolean }>(function Input({ ids, small, className = "", ...rest }, ref) {
  return <input ref={ref} id={ids?.id} aria-describedby={ids?.describedBy} aria-invalid={ids?.invalid || undefined}
    autoComplete="off" className={`input${small ? " input--sm" : ""} ${className}`.trim()} {...rest} />;
});
export const NumberInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { ids?: Ids; small?: boolean; decimal?: boolean }>(function NumberInput({ ids, small, decimal, className = "", ...rest }, ref) {
  return <input ref={ref} id={ids?.id} aria-describedby={ids?.describedBy} aria-invalid={ids?.invalid || undefined} type="text"
    inputMode={decimal ? "decimal" : "numeric"} pattern={decimal ? "[0-9]*[.,]?[0-9]*" : "[0-9]*"} autoComplete="off"
    className={`input input--num${small ? " input--sm" : ""} ${className}`.trim()} {...rest} />;
});
export const DateInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { ids?: Ids }>(function DateInput({ ids, className = "", ...rest }, ref) {
  return <input ref={ref} id={ids?.id} aria-describedby={ids?.describedBy} aria-invalid={ids?.invalid || undefined} type="date"
    autoComplete="off" className={`input ${className}`.trim()} {...rest} />;
});
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & { ids?: Ids; small?: boolean; options: { value: string; label: string; disabled?: boolean }[] }>(function Select({ ids, small, options, className = "", ...rest }, ref) {
  return (
    <select ref={ref} id={ids?.id} aria-describedby={ids?.describedBy} aria-invalid={ids?.invalid || undefined} className={`select${small ? " select--sm" : ""} ${className}`.trim()} {...rest}>
      {options.map((o) => <option key={o.value} value={o.value} disabled={o.disabled}>{o.label}</option>)}
    </select>
  );
});
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement> & { ids?: Ids }>(function Textarea({ ids, className = "", ...rest }, ref) {
  return <textarea ref={ref} id={ids?.id} aria-describedby={ids?.describedBy} aria-invalid={ids?.invalid || undefined}
    autoComplete="off" className={`textarea ${className}`.trim()} {...rest} />;
});

/* Checkbox and Radio share the hit target: the whole label is the control. */
export function Checkbox({ label, ...rest }: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode }) {
  return <label className="check"><input type="checkbox" {...rest} /><span>{label}</span></label>;
}
export function Radio({ label, ...rest }: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode }) {
  return <label className="check"><input type="radio" {...rest} /><span>{label}</span></label>;
}
export function RadioGroup({ label, name, value, onChange, options }: { label: ReactNode; name: string; value: string; onChange: (v: string) => void; options: { value: string; label: ReactNode }[] }) {
  return (
    <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
      <legend className="field__label">{label}</legend>
      <div className="row-3">{options.map((o) => <Radio key={o.value} name={name} value={o.value} checked={value === o.value} onChange={() => onChange(o.value)} label={o.label} />)}</div>
    </fieldset>
  );
}

/* A slider with a visible value, aria-valuetext and a polite live region for
 * the recompute it drives. Fires on input (every move), not only on change. */
export function Slider({ label, value, min, max, step = 1, onChange, format, hint, id: givenId, liveText }:
  { label: ReactNode; value: number; min: number; max: number; step?: number; onChange: (v: number) => void; format: (v: number) => string; hint?: ReactNode; id?: string; liveText?: string }) {
  const auto = useId(); const id = givenId || auto;
  return (
    <div className="slider">
      <div className="slider__row">
        <label htmlFor={id} className="field__label">{label}</label>
        <output htmlFor={id} className="slider__value" aria-live="off">{format(value)}</output>
      </div>
      <div className="slider__row">
        <input id={id} type="range" min={min} max={max} step={step} value={value} aria-valuetext={format(value)}
          aria-describedby={hint ? `${id}-h` : undefined} onInput={(e) => onChange(Number((e.target as HTMLInputElement).value))} onChange={(e) => onChange(Number(e.target.value))} />
      </div>
      {hint && <div id={`${id}-h`} className="field__hint">{hint}</div>}
      {liveText !== undefined && <div className="sr-only" aria-live="polite">{liveText}</div>}
    </div>
  );
}

export function PasswordInput({ ids, ...rest }: InputHTMLAttributes<HTMLInputElement> & { ids?: Ids }) {
  const [show, setShow] = useState(false);
  return (
    <div className="pw">
      <Input ids={ids} type={show ? "text" : "password"} autoComplete="current-password" {...rest} />
      <Button variant="secondary" onClick={() => setShow((s) => !s)} aria-pressed={show}>{show ? "Hide" : "Show"}</Button>
    </div>
  );
}

/* A real download: an <a download> whose href is a blob of the bytes on
 * screen, with the size, plus a copy button. */
export function FileDownload({ name, text, mime = "application/json", label = "Download", description }: { name: string; text: string; mime?: string; label?: string; description?: ReactNode }) {
  const toast = useToast();
  const url = useMemo(() => URL.createObjectURL(new Blob([text], { type: mime })), [text, mime]);
  useEffect(() => () => URL.revokeObjectURL(url), [url]);
  const size = new TextEncoder().encode(text).length;
  return (
    <div className="download">
      <div className="download__row">
        <Icon name="document" />
        <span className="download__name" translate="no">{name}</span>
        <span className="download__meta">{fmtBytes(size)}</span>
        <span className="spacer" />
        <a className="btn btn--primary" href={url} download={name}><Icon name="download" />{label}</a>
        <Button variant="secondary" icon="copy" onClick={() => { navigator.clipboard?.writeText(text).then(() => toast("Copied to the clipboard")); }}>Copy</Button>
      </div>
      {description && <div className="download__meta">{description}</div>}
    </div>
  );
}

/* Warns before the page unloads while a form has unsaved input. */
export function useUnsavedGuard(dirty: boolean) {
  const ref = useRef(dirty); ref.current = dirty;
  useEffect(() => {
    const h = (e: BeforeUnloadEvent) => { if (ref.current) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, []);
}

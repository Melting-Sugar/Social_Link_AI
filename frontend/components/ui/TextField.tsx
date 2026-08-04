import { forwardRef, type InputHTMLAttributes } from "react";

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, error, hint, id, ...inputProps },
  ref
) {
  const fieldId = id ?? inputProps.name;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={fieldId} className="text-[11.5px] font-bold text-ink-soft">
        {label}
      </label>
      <input
        ref={ref}
        id={fieldId}
        className="rounded-xl border border-line bg-surface px-3.5 py-3 text-[14px] text-ink outline-none focus-visible:outline-2 focus-visible:outline-ink"
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined}
        {...inputProps}
      />
      {hint && !error && (
        <p id={`${fieldId}-hint`} className="text-[10px] leading-relaxed text-ink-soft">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${fieldId}-error`} className="text-[10px] leading-relaxed text-ink">
          {error}
        </p>
      )}
    </div>
  );
});

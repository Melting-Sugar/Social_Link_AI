import type { ButtonHTMLAttributes } from "react";

export function PrimaryButton({
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="submit"
      className={`w-full rounded-2xl bg-coral px-4 py-[15px] text-[14.5px] font-bold tracking-wide text-on-accent transition-colors hover:bg-coral-strong active:bg-coral-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-ink disabled:opacity-50 ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

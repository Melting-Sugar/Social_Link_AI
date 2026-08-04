import type { ReactNode } from "react";

// Shared shell for L-①〜⑤ and E-①: centered card, readable on phone and
// desktop alike (§11: "スマホ利用を前提とし、PCでも崩れないレスポンシブ").
export function AuthPageShell({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <main className="flex flex-1 items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm rounded-3xl border border-line bg-surface p-7 shadow-[var(--shadow-app)]">
        <h1 className="text-[17px] font-extrabold text-ink text-balance">{title}</h1>
        {description && <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">{description}</p>}
        <div className="mt-6 flex flex-col gap-4">{children}</div>
      </div>
    </main>
  );
}

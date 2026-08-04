import Link from "next/link";

export default function TitlePage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 px-6 py-16 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-[22px] bg-gradient-to-br from-coral to-gold">
        <svg viewBox="0 0 24 24" fill="none" stroke="var(--on-accent)" strokeWidth="1.8" strokeLinecap="round" className="h-7 w-7">
          <circle cx="7" cy="8" r="2.6" />
          <circle cx="17" cy="16" r="2.6" />
          <path d="M9.2 9.6 14.8 14.4" />
        </svg>
      </div>
      <div>
        <h1 className="text-[20px] font-extrabold tracking-wide text-ink">Social Link AI</h1>
        <p className="mt-2 max-w-[240px] text-[12.5px] leading-relaxed text-ink-soft">
          会話のあとに、静かに振り返る。
          <br />
          今のあなたのペースで。
        </p>
      </div>
      <Link
        href="/scene"
        className="w-full max-w-[280px] rounded-2xl bg-coral px-4 py-[15px] text-center text-[14.5px] font-bold tracking-wide text-on-accent transition-colors hover:bg-coral-strong"
      >
        サポートを開始する
      </Link>
    </main>
  );
}

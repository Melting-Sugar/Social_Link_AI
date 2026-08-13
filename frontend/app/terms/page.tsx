import { readLegalDoc } from "@/lib/read-legal-doc";

// Server component: reads the canonical draft directly from
// content/legal/ at request time so this page can never drift out of
// sync with the source of truth. No markdown-rendering dependency added
// for one draft page — whitespace-pre-wrap is enough to keep
// headings/lists legible.
export default function TermsPage() {
  const content = readLegalDoc("terms-of-service.md");

  return (
    <main className="flex-1 px-5 py-8">
      <div className="mx-auto max-w-xl whitespace-pre-wrap text-[13px] leading-relaxed text-ink">{content}</div>
    </main>
  );
}

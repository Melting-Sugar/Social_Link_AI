import { readLegalDoc } from "@/lib/read-legal-doc";

// See app/terms/page.tsx for why this reads the markdown source directly
// rather than duplicating the content.
export default function PrivacyPage() {
  const content = readLegalDoc("privacy-policy.md");

  return (
    <main className="flex-1 px-5 py-8">
      <div className="mx-auto max-w-xl whitespace-pre-wrap text-[13px] leading-relaxed text-ink">{content}</div>
    </main>
  );
}

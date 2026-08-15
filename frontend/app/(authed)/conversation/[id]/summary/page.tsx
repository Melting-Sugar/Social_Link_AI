"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { conversationApi } from "@/lib/conversation-api";
import { useNavigationGuard } from "@/lib/navigation-guard-context";

const UNSAVED_GUARD_MESSAGE = "今ここを押すとデータが記録されません。よろしいですか？";

// A-⑤. §11.5: /log (A-⑥) needs these bullets too, but the backend never
// persists an intermediate "pending summary" (raw transcripts aren't kept
// around to regenerate it from, §8) — so the client round-trips them via
// sessionStorage between this page and /log.
const STORAGE_KEY_PREFIX = "social-link:summary:";

export default function ConversationSummaryPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [bullets, setBullets] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // A-⑥（/log側）の保存操作をするまで、この会話は保存されない（§8） —
  // フッターナビで離脱しかけたら警告する（2026-08-15ユーザー指示）。
  const { setGuarded } = useNavigationGuard();
  useEffect(() => {
    setGuarded(true, UNSAVED_GUARD_MESSAGE);
    return () => setGuarded(false);
  }, [setGuarded]);

  useEffect(() => {
    conversationApi
      .generateSummary(id)
      .then((res) => {
        setBullets(res.summary_bullets);
        sessionStorage.setItem(`${STORAGE_KEY_PREFIX}${id}`, JSON.stringify(res.summary_bullets));
      })
      .catch(() => setError("振り返りの生成に失敗しました。"));
  }, [id]);

  return (
    <div className="flex flex-1 flex-col px-5 py-6">
      <h2 className="text-[16px] font-extrabold text-ink">今日の会話のまとめ</h2>
      <p className="mt-3 text-[10.5px] text-ink-soft">AIによる推定です。実際の状況と異なる場合があります。</p>

      {error && <p className="mt-4 text-[13px] text-ink">{error}</p>}
      {!bullets && !error && <p className="mt-4 text-[13px] text-ink-soft">まとめを作成しています...</p>}

      {bullets && (
        <ul className="mt-4 flex flex-col gap-2.5">
          {bullets.map((bullet, i) => (
            <li key={i} className="rounded-2xl border border-line bg-surface p-3.5 text-[13px] leading-relaxed text-ink">
              {bullet}
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        disabled={!bullets}
        onClick={() => router.push(`/conversation/${id}/log`)}
        className="mt-6 rounded-2xl bg-coral px-4 py-[15px] text-[14.5px] font-bold text-on-accent transition-colors active:bg-coral-strong disabled:opacity-50"
      >
        記録する →
      </button>
    </div>
  );
}

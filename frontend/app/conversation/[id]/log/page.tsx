"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { CONDITION_LABELS, recordApi, type Condition } from "@/lib/record-api";

const CONDITIONS: Condition[] = ["very_good", "good", "tired", "unwell"];

export default function ConversationLogPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [condition, setCondition] = useState<Condition | null>(null);
  const [moodScore, setMoodScore] = useState(5);
  const [nextGoal, setNextGoal] = useState("");
  const [memo, setMemo] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!condition) {
      setError("体調を選択してください。");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const raw = sessionStorage.getItem(`social-link:summary:${id}`);
      const summaryBullets: string[] = raw ? JSON.parse(raw) : [];
      await recordApi.log(id, {
        condition,
        mood_anxiety_score: moodScore,
        next_goal: nextGoal || null,
        memo: memo || null,
        summary_bullets: summaryBullets,
      });
      sessionStorage.removeItem(`social-link:summary:${id}`);
      router.push("/history");
    } catch {
      setError("記録の保存に失敗しました。もう一度お試しください。");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col px-5 py-6">
      <h2 className="text-[16px] font-extrabold text-ink">今日の記録</h2>

      <div className="mt-5 flex flex-col gap-5">
        <div>
          <p className="text-[11.5px] font-bold text-ink-soft">体調</p>
          <div className="mt-2 grid grid-cols-4 gap-2">
            {CONDITIONS.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setCondition(c)}
                className={`rounded-xl border px-2 py-2.5 text-[11px] font-bold transition-colors active:bg-coral-tint ${
                  condition === c ? "border-coral bg-coral-tint text-ink" : "border-line bg-surface text-ink-soft"
                }`}
              >
                {CONDITION_LABELS[c]}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label htmlFor="mood" className="text-[11.5px] font-bold text-ink-soft">
            気分・不安度（0〜10）
          </label>
          <input
            id="mood"
            type="range"
            min={0}
            max={10}
            value={moodScore}
            onChange={(e) => setMoodScore(Number(e.target.value))}
            className="mt-2 w-full accent-coral"
          />
          <p className="text-center text-[13px] font-bold tabular-nums text-ink">{moodScore}</p>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="next-goal" className="text-[11.5px] font-bold text-ink-soft">
            次回目標（任意）
          </label>
          <input
            id="next-goal"
            value={nextGoal}
            onChange={(e) => setNextGoal(e.target.value)}
            className="rounded-xl border border-line bg-surface px-3.5 py-3 text-[14px] text-ink outline-none focus-visible:outline-2 focus-visible:outline-ink"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="memo" className="text-[11.5px] font-bold text-ink-soft">
            メモ（任意）
          </label>
          <textarea
            id="memo"
            value={memo}
            onChange={(e) => setMemo(e.target.value)}
            rows={3}
            className="rounded-xl border border-line bg-surface px-3.5 py-3 text-[14px] text-ink outline-none focus-visible:outline-2 focus-visible:outline-ink"
          />
        </div>

        {error && <p className="text-[12px] text-ink">{error}</p>}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={isSubmitting}
          className="rounded-2xl bg-coral px-4 py-[15px] text-[14.5px] font-bold text-on-accent transition-colors active:bg-coral-strong disabled:opacity-50"
        >
          {isSubmitting ? "記録中..." : "記録する"}
        </button>
      </div>
    </div>
  );
}

"use client";

import { useRef, useState } from "react";
import { SCENE_LABELS, type Scene } from "@/lib/conversation-api";
import { statementCheckApi, type StatementCheckResponse } from "@/lib/statement-check-api";
import { FREE_TEXT_MAX_LENGTH, FREE_TEXT_MAX_LENGTH_MESSAGE } from "@/lib/validation";

const SCENES: Scene[] = ["school_university", "workplace", "first_meeting", "friend", "romantic"];

export default function StatementCheckPage() {
  const [statementText, setStatementText] = useState("");
  const [scene, setScene] = useState<Scene>("friend");
  const [result, setResult] = useState<StatementCheckResponse | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isCheckingRef = useRef(false);
  const isTooLong = statementText.length > FREE_TEXT_MAX_LENGTH;

  const handleCheck = async () => {
    if (!statementText.trim() || isTooLong || isCheckingRef.current) return;
    isCheckingRef.current = true;
    setIsChecking(true);
    setError(null);
    setResult(null);
    try {
      const res = await statementCheckApi.check(statementText, scene);
      setResult(res);
    } catch {
      setError("判定に失敗しました。もう一度お試しください。");
    } finally {
      isCheckingRef.current = false;
      setIsChecking(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col px-5 py-6">
      <h2 className="text-[16px] font-extrabold text-ink">発言チェック</h2>
      <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">
        言おうとしている発言を入力すると、この場面で大丈夫そうか確認できます。
      </p>

      <div className="mt-5 flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="scene" className="text-[11.5px] font-bold text-ink-soft">
            場面
          </label>
          <select
            id="scene"
            value={scene}
            onChange={(e) => setScene(e.target.value as Scene)}
            className="rounded-xl border border-line bg-surface px-3.5 py-3 text-[14px] text-ink"
          >
            {SCENES.map((s) => (
              <option key={s} value={s}>
                {SCENE_LABELS[s]}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="statement" className="text-[11.5px] font-bold text-ink-soft">
            発言案
          </label>
          <textarea
            id="statement"
            value={statementText}
            onChange={(e) => setStatementText(e.target.value)}
            rows={4}
            aria-invalid={isTooLong || undefined}
            className="rounded-xl border border-line bg-surface px-3.5 py-3 text-[14px] text-ink outline-none focus-visible:outline-2 focus-visible:outline-ink"
          />
          <p className={`text-right text-[10.5px] ${isTooLong ? "text-ink" : "text-ink-soft"}`}>
            {statementText.length}/{FREE_TEXT_MAX_LENGTH}
          </p>
          {isTooLong && <p className="text-[12px] text-ink">{FREE_TEXT_MAX_LENGTH_MESSAGE}</p>}
        </div>

        {error && <p className="text-[12px] text-ink">{error}</p>}

        <button
          type="button"
          onClick={handleCheck}
          disabled={isChecking || !statementText.trim() || isTooLong}
          className="rounded-2xl bg-coral px-4 py-[15px] text-[14.5px] font-bold text-on-accent transition-colors active:bg-coral-strong disabled:opacity-50"
        >
          {isChecking ? "確認中..." : "確認する"}
        </button>

        {result && (
          <div className={`rounded-2xl p-4 ${result.is_safe ? "bg-coral-tint" : "bg-caution-tint"}`}>
            <p className="text-[10.5px] text-ink-soft">AIによる推定です。実際の状況と異なる場合があります。</p>
            <p className="mt-1.5 text-[13.5px] font-bold text-ink">
              {result.is_safe ? "大丈夫そうです" : "少し注意した方が良いかもしれません"}
            </p>
            <p className="mt-2 text-[13px] leading-relaxed text-ink">{result.feedback}</p>
          </div>
        )}
      </div>
    </div>
  );
}

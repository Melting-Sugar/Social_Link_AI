"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { CONDITION_LABELS, recordApi } from "@/lib/record-api";

export default function HistoryPage() {
  const queryClient = useQueryClient();
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const deletingIdRef = useRef<string | null>(null);

  const { data: records, isLoading } = useQuery({
    queryKey: ["records"],
    queryFn: () => recordApi.list(),
  });

  const handleDelete = async (recordId: string) => {
    if (deletingIdRef.current !== null) return;
    deletingIdRef.current = recordId;
    setDeletingId(recordId);
    try {
      await recordApi.delete(recordId);
      await queryClient.invalidateQueries({ queryKey: ["records"] });
    } finally {
      deletingIdRef.current = null;
      setDeletingId(null);
    }
  };

  return (
    <div className="flex flex-1 flex-col px-5 py-6">
      <h2 className="text-[16px] font-extrabold text-ink">今までの記録</h2>

      {isLoading && <p className="mt-4 text-[13px] text-ink-soft">読み込み中...</p>}
      {records && records.length === 0 && <p className="mt-4 text-[13px] text-ink-soft">まだ記録がありません。</p>}

      <div className="mt-4 flex flex-col gap-3">
        {records?.map((record) => (
          <div key={record.id} className="rounded-2xl border border-line bg-surface p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-[12px] font-bold text-ink-soft">{record.date}</p>
                <p className="mt-1 text-[13px] font-bold text-ink">
                  体調：{CONDITION_LABELS[record.condition]} ／ 気分・不安度：{record.mood_anxiety_score}
                </p>
              </div>
              <button
                type="button"
                onClick={() => handleDelete(record.id)}
                disabled={deletingId === record.id}
                className="text-[11px] font-bold text-ink-soft underline underline-offset-2 disabled:opacity-50"
              >
                削除
              </button>
            </div>
            {record.summary_bullets.length > 0 && (
              <ul className="mt-3 flex flex-col gap-1.5">
                {record.summary_bullets.map((bullet, i) => (
                  <li key={i} className="text-[12.5px] leading-relaxed text-ink">
                    ・{bullet}
                  </li>
                ))}
              </ul>
            )}
            {record.next_goal && <p className="mt-2 text-[12px] text-ink-soft">次回目標：{record.next_goal}</p>}
            {record.memo && <p className="mt-1 text-[12px] text-ink-soft">メモ：{record.memo}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

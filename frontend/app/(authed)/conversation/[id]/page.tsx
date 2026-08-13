"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { SceneBar } from "@/components/SceneBar";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import {
  ANALYSIS_STAGE_LABELS,
  RELATIONSHIP_DISTANCE_LABELS,
  SUGGESTION_CATEGORY_LABELS,
  conversationApi,
  type RecordingResponse,
} from "@/lib/conversation-api";
import { useNavigationGuard } from "@/lib/navigation-guard-context";

const MAX_RECORDING_SECONDS = 60; // §11.3, 確定事項28 — capped for MVP to keep AmiVoice analysis latency tolerable

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

type Phase = "recording" | "analyzing";

export default function ConversationPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("recording");
  const [activeRecordingId, setActiveRecordingId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const uploadedBlobRef = useRef<Blob | null>(null);

  const { data: conversation } = useQuery({
    queryKey: ["conversation", id],
    queryFn: () => conversationApi.get(id),
  });

  const { isRecording, elapsedSeconds, audioBlob, error, start, stop, reset } = useAudioRecorder({
    maxSeconds: MAX_RECORDING_SECONDS,
  });

  // Upload exactly once per finished recording — audioBlob only changes
  // identity when a fresh recording finishes (reset() clears it back to
  // null before the next round).
  useEffect(() => {
    if (!audioBlob || uploadedBlobRef.current === audioBlob) return;
    uploadedBlobRef.current = audioBlob;
    setUploadError(null);
    conversationApi
      .uploadRecording(id, audioBlob, elapsedSeconds)
      .then((res) => {
        setActiveRecordingId(res.id);
        setPhase("analyzing");
      })
      .catch(() => setUploadError("録音のアップロードに失敗しました。もう一度お試しください。"));
    // elapsedSeconds is read once at upload time, not a reactive dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioBlob, id]);

  const { data: recording } = useQuery({
    queryKey: ["recording", id, activeRecordingId],
    queryFn: () => conversationApi.getRecording(id, activeRecordingId as string),
    enabled: activeRecordingId !== null,
    // §11.6: keep polling until the pipeline settles either way.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "completed" || status === "failed" ? false : 2000;
    },
  });

  // 録音中（録音画面かつ録音が作動している）・解析中はフッターナビでの
  // 離脱を確認ダイアログでガードする（2026-08-12ユーザー指示）。
  const { setGuarded } = useNavigationGuard();
  const isAnalyzing = phase === "analyzing" && recording?.status !== "completed" && recording?.status !== "failed";
  useEffect(() => {
    setGuarded((phase === "recording" && isRecording) || isAnalyzing);
    return () => setGuarded(false);
  }, [phase, isRecording, isAnalyzing, setGuarded]);

  const handleRecordAgain = () => {
    setActiveRecordingId(null);
    uploadedBlobRef.current = null;
    reset();
    setPhase("recording");
  };

  return (
    <div className="flex flex-1 flex-col">
      {conversation && <SceneBar scene={conversation.scene} />}

      {phase === "recording" && (
        <RecordingPhase
          isRecording={isRecording}
          elapsedSeconds={elapsedSeconds}
          onStart={start}
          onStop={stop}
          recorderError={error}
          uploadError={uploadError}
        />
      )}

      {phase === "analyzing" && recording && recording.status === "failed" && (
        <FailedPhase message={recording.error_message} onRetry={handleRecordAgain} />
      )}

      {phase === "analyzing" && recording && recording.status === "completed" && (
        <ResultPhase
          recording={recording}
          onRecordAgain={handleRecordAgain}
          onFinish={() => router.push(`/conversation/${id}/summary`)}
        />
      )}

      {phase === "analyzing" && recording && recording.status !== "failed" && recording.status !== "completed" && (
        <AnalyzingPhase recording={recording} />
      )}
    </div>
  );
}

function RecordingPhase({
  isRecording,
  elapsedSeconds,
  onStart,
  onStop,
  recorderError,
  uploadError,
}: {
  isRecording: boolean;
  elapsedSeconds: number;
  onStart: () => void;
  onStop: () => void;
  recorderError: string | null;
  uploadError: string | null;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="rounded-full bg-gold-tint px-3 py-1.5 text-[10.5px] font-bold text-ink">
        相手にも録音・分析についてひと言伝えましょう
      </div>
      <p className="text-[26px] font-extrabold tracking-wide tabular-nums text-ink">{formatElapsed(elapsedSeconds)}</p>
      <p className="text-[10.5px] text-ink-soft">上限{MAX_RECORDING_SECONDS}秒</p>
      <p className="max-w-[230px] text-[12px] leading-relaxed text-ink-soft">
        ボタンを押して録音を開始してください。もう一度押すと録音を終了し、解析を始めます。
      </p>
      <button
        type="button"
        aria-label={isRecording ? "録音を終了して分析する" : "録音を開始する"}
        onClick={isRecording ? onStop : onStart}
        className="flex h-[92px] w-[92px] items-center justify-center rounded-full bg-caution transition-colors active:bg-caution-strong"
      >
        {isRecording ? (
          <span className="h-6 w-6 rounded-sm bg-on-accent" />
        ) : (
          <svg viewBox="0 0 24 24" fill="var(--on-accent)" className="h-6 w-6">
            <path d="M12 15a3 3 0 0 0 3-3V7a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z" />
          </svg>
        )}
      </button>
      {recorderError && <p className="text-[12px] text-ink">{recorderError}</p>}
      {uploadError && <p className="text-[12px] text-ink">{uploadError}</p>}
    </div>
  );
}

function FailedPhase({ message, onRetry }: { message: string | null; onRetry: () => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="text-[13px] text-ink">{message ?? "解析中に問題が発生しました。もう一度お試しください。"}</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-2xl bg-coral px-5 py-3 text-[13.5px] font-bold text-on-accent transition-colors active:bg-coral-strong"
      >
        もう一度録音する
      </button>
    </div>
  );
}

function AnalyzingPhase({ recording }: { recording: RecordingResponse }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
      <div className="h-8 w-8 animate-spin rounded-full border-[3px] border-line border-t-coral" />
      <p className="text-[14.5px] font-bold text-ink">解析中...</p>
      <p className="text-[11.5px] text-ink-soft">
        {recording.current_stage ? ANALYSIS_STAGE_LABELS[recording.current_stage] : "準備しています..."}
      </p>
      <p className="text-[10.5px] text-ink-soft">通常、60秒ほどで解析が完了します</p>
      {recording.topic_ready && (
        <div className="mt-3 w-full max-w-xs rounded-xl bg-coral-tint px-3.5 py-2.5 text-left text-[11.5px] font-bold text-ink">
          話題：{recording.topic}
        </div>
      )}
    </div>
  );
}

function ResultPhase({
  recording,
  onRecordAgain,
  onFinish,
}: {
  recording: RecordingResponse;
  onRecordAgain: () => void;
  onFinish: () => void;
}) {
  return (
    <div className="flex flex-1 flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {recording.single_speaker_detected && (
          <div className="mb-3 rounded-xl bg-caution-tint px-3.5 py-2.5 text-[11px] leading-relaxed text-ink">
            今回は片方の発言のみで解析しました。相手の反応など、判断できない項目があります。
          </div>
        )}
        {/* §11.11: AI推定である旨を常時表示 */}
        <p className="mb-3 text-[10.5px] text-ink-soft">AIによる推定です。実際の状況と異なる場合があります。</p>

        <div className="flex flex-col gap-3.5">
          <Card eyebrow="現在の話題" body={recording.topic} />
          <div className="grid grid-cols-2 gap-2.5">
            <Card eyebrow="会話の流れ" body={recording.flow} />
            <Card eyebrow="相手の反応" body={recording.other_reaction} />
          </div>
          {recording.relationship_distance && (
            <Card eyebrow="関係性の距離感" body={RELATIONSHIP_DISTANCE_LABELS[recording.relationship_distance]} />
          )}
          {recording.suggestion_category && (
            <div className="rounded-2xl border border-line bg-surface p-3.5">
              <p className="mb-1.5 text-[10.5px] font-bold uppercase tracking-wide text-ink-soft">次に話すと良いこと</p>
              <span className="inline-block rounded-full bg-gold px-2.5 py-1 text-[11px] font-bold text-on-accent">
                {SUGGESTION_CATEGORY_LABELS[recording.suggestion_category]}
              </span>
              <p className="mt-2 text-[13px] leading-relaxed text-ink">{recording.suggestion_text}</p>
            </div>
          )}
        </div>
      </div>
      <div className="flex gap-2 border-t border-line p-4">
        <button
          type="button"
          onClick={onRecordAgain}
          className="flex-1 rounded-2xl border border-line bg-surface-sunken px-4 py-3 text-[13px] font-bold text-ink transition-colors active:bg-line"
        >
          もう一度録音する
        </button>
        <button
          type="button"
          onClick={onFinish}
          className="flex-1 rounded-2xl bg-coral px-4 py-3 text-[13px] font-bold text-on-accent transition-colors active:bg-coral-strong"
        >
          会話を終了する →
        </button>
      </div>
    </div>
  );
}

function Card({ eyebrow, body }: { eyebrow: string; body: string | null }) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-3.5">
      <p className="mb-1.5 text-[10.5px] font-bold uppercase tracking-wide text-ink-soft">{eyebrow}</p>
      <p className="text-[13px] leading-relaxed text-ink">{body ?? "…"}</p>
    </div>
  );
}

"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { PrimaryButton } from "@/components/ui/PrimaryButton";
import { TextLink } from "@/components/ui/TextLink";
import { useAudioRecorder } from "@/hooks/useAudioRecorder";
import { ApiError } from "@/lib/api-client";
import { useNavigationGuard } from "@/lib/navigation-guard-context";
import { safeInternalPath } from "@/lib/safe-redirect";
import { voiceProfileApi } from "@/lib/voice-profile-api";

const MAX_RECORDING_SECONDS = 60; // 会話サポートの録音画面と同じ上限（§11.3）

function VoiceEnrollForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const returnTo = safeInternalPath(searchParams.get("next"), "/settings");
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { isRecording, elapsedSeconds, audioBlob, error, start, stop, reset } = useAudioRecorder({
    maxSeconds: MAX_RECORDING_SECONDS,
  });

  // 録音中・録音済み未送信・登録処理中に不用意にフッターナビへ移動して
  // 録り直しになることを防ぐ（2026-08-12ユーザー指示、会話サポート画面と
  // 同じガード）。audioBlobがある＝録音は完了したがまだ登録ボタンを押して
  // いない状態も、離脱すると録音内容が失われるためガード対象に含める。
  const { setGuarded } = useNavigationGuard();
  useEffect(() => {
    setGuarded(isRecording || isSubmitting || audioBlob !== null);
    return () => setGuarded(false);
  }, [isRecording, isSubmitting, audioBlob, setGuarded]);

  // isSubmitting(state)だけをガードにすると、Reactの再描画が1回挟まる
  // までのわずかな間に連打が両方通ってしまう（ボタンのdisabledは再描画後
  // にしか反映されない）。refは同期的に読み書きできるため、その隙間を
  // 塞げる。
  const isSubmittingRef = useRef(false);
  const handleSubmit = async () => {
    if (!audioBlob || isSubmittingRef.current) return;
    isSubmittingRef.current = true;
    setSubmitError(null);
    setIsSubmitting(true);
    try {
      const result = await voiceProfileApi.register(audioBlob);
      // setQueryData, not just invalidateQueries: /scene's useQuery has
      // no active observer while we're still on this page, so
      // invalidateQueries only marks the cache stale — it doesn't
      // rewrite it. staleTime is 0, so the moment /scene mounts it
      // synchronously renders that STILL-STALE { registered: false }
      // on its first pass (the real refetch lands async, after), and
      // its effect redirects straight back here before the refetch
      // ever gets a chance to land. Writing the known-correct result
      // directly closes that race — /scene's first render already
      // sees { registered: true }, no redirect fires. invalidateQueries
      // stays too, as a real revalidation against the server.
      queryClient.setQueryData(["voice-profile-status"], result);
      await queryClient.invalidateQueries({ queryKey: ["voice-profile-status"] });
      router.push(returnTo);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "声紋の登録に失敗しました。");
    } finally {
      isSubmittingRef.current = false;
      setIsSubmitting(false);
    }
  };

  return (
    <main className="flex flex-1 items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm rounded-3xl border border-line bg-surface p-7 shadow-[var(--shadow-app)]">
        <h1 className="text-[17px] font-extrabold text-ink text-balance">声を登録しましょう</h1>
        <p className="mt-1.5 text-[13px] leading-relaxed text-ink-soft">
          あなたの声を登録すると、会話の相手と自動的に区別できるようになります。10秒ほど、自由に話しかけてください。
        </p>
        <div className="mt-4 rounded-2xl bg-gold-tint p-3.5 text-[11px] leading-relaxed text-ink">
          登録した声の情報は、<b>会話の相手を判別する目的にのみ</b>使用します。それ以外の目的で利用したり、外部へ提供したりすることはありません。詳しくは
          <TextLink href="/terms" className="mx-1">
            利用規約
          </TextLink>
          をご覧ください。
        </div>

        <div className="mt-6 flex flex-col items-center gap-4">
          {!audioBlob ? (
            <>
              <button
                type="button"
                onClick={isRecording ? stop : start}
                aria-label={isRecording ? "録音を終了する" : "録音を開始する"}
                className="flex h-20 w-20 items-center justify-center rounded-full bg-caution transition-all active:scale-95 active:bg-caution-strong"
              >
                <span className={isRecording ? "h-5 w-5 rounded-sm bg-on-accent" : "h-6 w-6 rounded-full bg-on-accent"} />
              </button>
              <p className="text-[12px] text-ink-soft">
                {isRecording ? `録音中 ${elapsedSeconds}秒` : "ボタンを押して録音を開始"}
              </p>
              <p className="text-[10.5px] text-ink-soft">上限{MAX_RECORDING_SECONDS}秒</p>
              {error && <p className="text-[12px] text-ink">{error}</p>}
            </>
          ) : (
            <>
              <p className="text-[13px] text-ink">録音が完了しました（{elapsedSeconds}秒）</p>
              <div className="flex w-full gap-2">
                <button
                  type="button"
                  onClick={reset}
                  className="flex-1 rounded-2xl border border-line bg-surface-sunken px-4 py-3 text-[13px] font-bold text-ink"
                >
                  録り直す
                </button>
                <PrimaryButton onClick={handleSubmit} disabled={isSubmitting} className="flex-1">
                  {isSubmitting ? "登録中..." : "この声を登録する"}
                </PrimaryButton>
              </div>
              {submitError && <p className="text-[12px] text-ink">{submitError}</p>}
            </>
          )}
        </div>
      </div>
    </main>
  );
}

export default function VoiceEnrollPage() {
  return (
    <Suspense fallback={null}>
      <VoiceEnrollForm />
    </Suspense>
  );
}

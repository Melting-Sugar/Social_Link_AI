"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseAudioRecorderOptions {
  maxSeconds?: number;
  onAutoStop?: () => void;
}

/**
 * §11.4: recording itself is `MediaRecorder`-based; the waveform/elapsed-
 * time display stays entirely client-side (never sent to the backend —
 * only the final blob is uploaded once stopped).
 */
export function useAudioRecorder({ maxSeconds, onAutoStop }: UseAudioRecorderOptions = {}) {
  const [isRecording, setIsRecording] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stop = useCallback(() => {
    mediaRecorderRef.current?.stop();
    setIsRecording(false);
    if (intervalRef.current) clearInterval(intervalRef.current);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        setAudioBlob(new Blob(chunksRef.current, { type: recorder.mimeType }));
        streamRef.current?.getTracks().forEach((t) => t.stop());
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
      setElapsedSeconds(0);
      setAudioBlob(null);
      // §11.3: the 30-minute cap is enforced here, in the timer tick
      // itself, rather than via a separate effect watching elapsedSeconds
      // — calling stop() from a reactive effect is a cascading-render
      // anti-pattern (caught by eslint-plugin-react-hooks).
      intervalRef.current = setInterval(() => {
        setElapsedSeconds((s) => {
          const next = s + 1;
          if (maxSeconds && next >= maxSeconds) {
            stop();
            onAutoStop?.();
          }
          return next;
        });
      }, 1000);
    } catch {
      // §11.7-style specific messaging, not a generic failure.
      setError("マイクにアクセスできませんでした。マイクの権限をご確認ください。");
    }
  }, [maxSeconds, onAutoStop, stop]);

  const reset = useCallback(() => {
    setAudioBlob(null);
    setElapsedSeconds(0);
  }, []);

  useEffect(() => () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
  }, []);

  return { isRecording, elapsedSeconds, audioBlob, error, start, stop, reset };
}

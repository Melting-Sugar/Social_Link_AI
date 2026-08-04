import asyncio
import threading

import azure.cognitiveservices.speech as speechsdk

from app.core.config import get_settings
from app.integrations.stt.base import STTProvider, STTResult, STTSegment


class AzureSpeechProvider(STTProvider):
    """§3.5 — recommended STT vendor: diarization confirmed GA (2024-05),
    large vendor with low continuity risk (this project has already been
    burned twice by smaller vendors discontinuing adjacent APIs — §3.7,
    §12.2). Uses the Speech SDK's `ConversationTranscriber` against a local
    WAV file rather than the REST batch-transcription API, specifically to
    avoid requiring a separate Blob Storage hop just to hand Azure a URL.

    Verified against a live Azure endpoint (2026-08-04, requirements
    §10 confirmed item 24): transcription, punctuation, and speaker
    labeling all work as documented against a ja-JP test clip.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._speech_key = settings.azure_speech_key
        self._region = settings.azure_speech_region

    async def transcribe(self, audio_path: str) -> STTResult:
        return await asyncio.to_thread(self._transcribe_sync, audio_path)

    def _transcribe_sync(self, audio_path: str) -> STTResult:
        speech_config = speechsdk.SpeechConfig(subscription=self._speech_key, region=self._region)
        # §3.4: Azure's own docs note diarization timestamps aren't
        # perfectly synced to the audio timeline; word-level timestamps
        # are the documented mitigation.
        speech_config.set_property(
            speechsdk.PropertyId.SpeechServiceResponse_RequestWordLevelTimestamps, "true"
        )
        speech_config.speech_recognition_language = "ja-JP"
        audio_config = speechsdk.audio.AudioConfig(filename=audio_path)

        transcriber = speechsdk.transcription.ConversationTranscriber(
            speech_config=speech_config, audio_config=audio_config
        )

        segments: list[STTSegment] = []
        done = threading.Event()
        errors: list[Exception] = []

        def on_transcribed(evt: speechsdk.transcription.ConversationTranscriptionEventArgs) -> None:
            result = evt.result
            if result.reason == speechsdk.ResultReason.RecognizedSpeech and result.text:
                segments.append(
                    STTSegment(
                        speaker_label=result.speaker_id or "unknown",
                        text=result.text,
                        start_ms=result.offset // 10_000,  # 100ns ticks -> ms
                        end_ms=(result.offset + result.duration) // 10_000,
                    )
                )

        def on_stopped(evt: speechsdk.SessionEventArgs) -> None:
            done.set()

        def on_canceled(evt: speechsdk.transcription.ConversationTranscriptionCanceledEventArgs) -> None:
            if evt.reason == speechsdk.CancellationReason.Error:
                errors.append(RuntimeError(f"Azure STT canceled: {evt.error_details}"))
            done.set()

        transcriber.transcribed.connect(on_transcribed)
        transcriber.session_stopped.connect(on_stopped)
        transcriber.canceled.connect(on_canceled)

        transcriber.start_transcribing_async().get()
        done.wait()
        transcriber.stop_transcribing_async().get()

        if errors:
            raise errors[0]

        segments.sort(key=lambda s: s.start_ms)
        full_transcript = " ".join(s.text for s in segments)
        return STTResult(segments=segments, full_transcript=full_transcript)

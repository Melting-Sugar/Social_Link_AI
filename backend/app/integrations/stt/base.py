from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class STTSegment:
    """One utterance from the diarized transcript. `speaker_label` is
    whatever the STT vendor calls it (e.g. "Guest-1") — it does NOT yet
    mean self/other. That mapping is §12's job (integrations/speaker_id)."""

    speaker_label: str
    text: str
    start_ms: int
    end_ms: int


@dataclass
class STTResult:
    segments: list[STTSegment]
    full_transcript: str
    # Populated only by providers that bundle prosody/sentiment data into
    # the same call as transcription (e.g. AmiVoice ESAS, §12.3 確定事項25) —
    # mirrors ProsodyResult.raw_vendor_response. AnalysisService checks for
    # this to skip a redundant separate ProsodyProvider call.
    raw_vendor_response: dict | None = None


class STTProvider(ABC):
    """§3.7: kept swappable behind an interface — this project has already
    hit two vendor-discontinuation surprises (Hume, Azure Speaker
    Recognition) for adjacent services, so nothing here assumes Azure is
    permanent."""

    @abstractmethod
    async def transcribe(self, audio_path: str) -> STTResult:
        """`audio_path` is a normalized WAV file (16kHz/16bit/mono, §3.4) on
        local disk. Must diarize (§3.3: diarization is done once, here —
        prosody/speaker-id providers receive already-split per-speaker
        clips, never the raw mix)."""
        raise NotImplementedError

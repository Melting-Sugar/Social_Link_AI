from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProsodyResult:
    """§3.2 — tone/inflection/intensity-derived emotion dimensions for one
    speaker's clip. Deliberately vendor-agnostic: each provider maps its
    own output onto this shape so `analysis_service` never branches on
    vendor. Kept loose (free-form scores dict) since the concrete
    dimensions differ per PoC candidate (§3.6) and haven't been decided."""

    scores: dict[str, float]
    raw_vendor_response: dict | None = None


class ProsodyProvider(ABC):
    """§3.6 / §3.7 — PoC-gated (requirements §13 next-steps #1). No vendor
    is implemented yet; see empath.py / imentiv.py / audeering.py for
    explicit not-yet-implemented stubs with the intended call shape."""

    @abstractmethod
    async def analyze(self, audio_path: str) -> ProsodyResult:
        """`audio_path` is ALREADY a single-speaker clip (§3.3 — diarization
        happens once, upstream, in STT)."""
        raise NotImplementedError

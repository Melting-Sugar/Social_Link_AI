from abc import ABC, abstractmethod


class SpeakerIdProvider(ABC):
    """§12.3 — self-hosted speaker-embedding model, chosen specifically to
    have zero vendor-discontinuation risk after this project already lost
    two adjacent commercial APIs (Hume §3.7, Azure Speaker Recognition
    §12.2)."""

    @abstractmethod
    async def extract_embedding(self, audio_path: str) -> list[float]:
        """Text-independent — no fixed enrollment phrase required (§12.3)."""
        raise NotImplementedError

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

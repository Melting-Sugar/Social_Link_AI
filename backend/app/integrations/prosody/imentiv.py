from app.integrations.prosody.base import ProsodyProvider, ProsodyResult


class ImentivProsodyProvider(ProsodyProvider):
    """§3.6 — deprioritized candidate: Japanese support was never confirmed
    across three research passes (§3.6 PoC優先順位改訂). NOT yet
    implemented: requirements §13 next-steps #1 (PoC not run)."""

    async def analyze(self, audio_path: str) -> ProsodyResult:
        raise NotImplementedError(
            "ImentivProsodyProvider is a stub — prosody vendor PoC "
            "(requirements §13 next-steps #1) has not been run yet, and "
            "this candidate is deprioritized pending Japanese-support "
            "confirmation (§3.6)."
        )

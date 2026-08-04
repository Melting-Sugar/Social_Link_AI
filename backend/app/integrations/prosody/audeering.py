from app.integrations.prosody.base import ProsodyProvider, ProsodyResult


class AudeeringProsodyProvider(ProsodyProvider):
    """§3.6 — kept as a comparison point for academic credibility
    (openSMILE has a 10+ year track record), language-independence
    unconfirmed. NOT yet implemented: requirements §13 next-steps #1 (PoC
    not run)."""

    async def analyze(self, audio_path: str) -> ProsodyResult:
        raise NotImplementedError(
            "AudeeringProsodyProvider is a stub — prosody vendor PoC "
            "(requirements §13 next-steps #1) has not been run yet."
        )

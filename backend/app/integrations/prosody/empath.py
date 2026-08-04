from app.integrations.prosody.base import ProsodyProvider, ProsodyResult


class EmpathProsodyProvider(ProsodyProvider):
    """§3.6 — top PoC priority (Japanese-tuned, PoC優先順位改訂). NOT yet
    implemented: requirements §13 next-steps #1 (PoC not run).

    When implementing for real, §3.6 already specifies the constraints to
    build around: REST API, PCM WAVE 16bit mono 11025Hz, clips under 5s
    (resample from STT's 16kHz and split longer utterances — both should
    live in this adapter so callers never see Empath's quirks)."""

    async def analyze(self, audio_path: str) -> ProsodyResult:
        raise NotImplementedError(
            "EmpathProsodyProvider is a stub — prosody vendor PoC "
            "(requirements §13 next-steps #1) has not been run yet."
        )

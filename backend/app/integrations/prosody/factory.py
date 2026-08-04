from app.core.config import get_settings
from app.integrations.prosody.audeering import AudeeringProsodyProvider
from app.integrations.prosody.base import ProsodyProvider
from app.integrations.prosody.empath import EmpathProsodyProvider
from app.integrations.prosody.imentiv import ImentivProsodyProvider


class NullProsodyProvider(ProsodyProvider):
    """Default when PROSODY_PROVIDER=none (§13 next-steps #1 not yet run).
    Returns an empty result instead of raising, so the rest of the
    pipeline (STT + LLM) stays exercisable end-to-end without a prosody
    vendor — analysis_service treats an empty scores dict as "no prosody
    signal available" rather than a failure."""

    async def analyze(self, audio_path: str) -> "ProsodyResult":  # noqa: F821
        from app.integrations.prosody.base import ProsodyResult

        return ProsodyResult(scores={})


def get_prosody_provider() -> ProsodyProvider:
    """§6: vendor selection is a config switch, never a call-site branch."""
    provider = get_settings().prosody_provider
    match provider:
        case "empath":
            return EmpathProsodyProvider()
        case "imentiv":
            return ImentivProsodyProvider()
        case "audeering":
            return AudeeringProsodyProvider()
        case _:
            return NullProsodyProvider()

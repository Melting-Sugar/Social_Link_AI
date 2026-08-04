from app.core.config import get_settings
from app.integrations.speaker_id.base import SpeakerIdProvider
from app.integrations.speaker_id.ecapa_local import EcapaLocalSpeakerIdProvider
from app.integrations.speaker_id.pyannote_local import PyannoteLocalSpeakerIdProvider


class NullSpeakerIdProvider(SpeakerIdProvider):
    """Default when SPEAKER_ID_PROVIDER=none — lets the rest of the app
    (including voice enrollment's own tests) run without the optional
    PyTorch dependency group installed."""

    async def extract_embedding(self, audio_path: str) -> list[float]:
        raise NotImplementedError(
            "No speaker-id provider configured — set SPEAKER_ID_PROVIDER=ecapa_local "
            "and `uv sync --extra speaker-id` to enable it."
        )


def get_speaker_id_provider() -> SpeakerIdProvider:
    match get_settings().speaker_id_provider:
        case "ecapa_local":
            return EcapaLocalSpeakerIdProvider()
        case "pyannote_local":
            return PyannoteLocalSpeakerIdProvider()
        case _:
            return NullSpeakerIdProvider()

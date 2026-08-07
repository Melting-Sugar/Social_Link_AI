import asyncio

from app.core.config import get_settings
from app.integrations.speaker_id.base import SpeakerIdProvider

# Module-level cache — see ecapa_local.py for why (get_speaker_id_provider()
# builds a fresh instance per Celery task; this avoids reloading per task).
_cached_inference = None


class PyannoteLocalSpeakerIdProvider(SpeakerIdProvider):
    """§12.3 — the second PoC candidate (requirements §13 next-steps #2),
    weaker published benchmark than SpeechBrain (VoxCeleb EER 2.8% vs
    0.69% — see ecapa_local.py), implemented here so the comparison in the
    requirements doc is backed by a real, runnable adapter on both sides
    rather than one implementation and one citation.

    Requires the optional `speaker-id` dependency group
    (`uv sync --extra speaker-id`) and a Hugging Face access token with
    `pyannote/embedding`'s terms accepted (HF_TOKEN in .env.keys) — unlike
    SpeechBrain's model, pyannote's is gated and cannot be downloaded
    anonymously. This is itself a finding from the PoC, not an assumption:
    see requirements §12.3 for the practical-friction comparison.
    """

    _MODEL_SOURCE = "pyannote/embedding"

    def _get_inference(self):
        global _cached_inference
        if _cached_inference is None:
            try:
                from pyannote.audio import Inference, Model
            except ImportError as exc:
                raise ImportError(
                    "Speaker identification requires the optional 'speaker-id' "
                    "dependency group — run `uv sync --extra speaker-id`."
                ) from exc
            token = get_settings().hf_token or None
            model = Model.from_pretrained(self._MODEL_SOURCE, use_auth_token=token)
            _cached_inference = Inference(model, window="whole")
        return _cached_inference

    async def extract_embedding(self, audio_path: str) -> list[float]:
        return await asyncio.to_thread(self._extract_embedding_sync, audio_path)

    def _extract_embedding_sync(self, audio_path: str) -> list[float]:
        inference = self._get_inference()
        embedding = inference(audio_path)
        return embedding.tolist()

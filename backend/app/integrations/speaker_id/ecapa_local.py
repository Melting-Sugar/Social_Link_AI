import asyncio

from app.integrations.speaker_id.base import SpeakerIdProvider


class EcapaLocalSpeakerIdProvider(SpeakerIdProvider):
    """§12.3 — provisional pick between the two PoC candidates: SpeechBrain's
    ECAPA-TDNN has the stronger published benchmark (VoxCeleb EER 0.69% vs
    pyannote-audio's 2.8%), so it's implemented here as the working default.
    The formal comparison is still requirements §13 next-steps #2 — if that
    PoC favors pyannote-audio instead, add a sibling adapter and flip
    SPEAKER_ID_PROVIDER, nothing above this layer needs to change (§6).

    Requires the optional `speaker-id` dependency group
    (`uv sync --extra speaker-id`) — PyTorch/SpeechBrain are large and kept
    out of the base install so the rest of the app can run without them
    (§5). Model loading is lazy for the same reason.
    """

    _MODEL_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"

    def __init__(self) -> None:
        self._classifier = None

    def _get_classifier(self):
        if self._classifier is None:
            try:
                from speechbrain.inference.speaker import EncoderClassifier
            except ImportError as exc:
                raise ImportError(
                    "Speaker identification requires the optional 'speaker-id' "
                    "dependency group — run `uv sync --extra speaker-id`."
                ) from exc
            self._classifier = EncoderClassifier.from_hparams(source=self._MODEL_SOURCE)
        return self._classifier

    async def extract_embedding(self, audio_path: str) -> list[float]:
        # Model inference is CPU/GPU-bound and blocking — keep it off the
        # event loop (same pattern as the Azure STT adapter).
        return await asyncio.to_thread(self._extract_embedding_sync, audio_path)

    def _extract_embedding_sync(self, audio_path: str) -> list[float]:
        import torchaudio

        classifier = self._get_classifier()
        signal, _sample_rate = torchaudio.load(audio_path)
        embedding = classifier.encode_batch(signal)
        return embedding.squeeze().tolist()

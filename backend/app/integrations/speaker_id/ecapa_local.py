import asyncio

from app.integrations.speaker_id.base import SpeakerIdProvider

_MODEL_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"

# Module-level, not instance-level: get_speaker_id_provider() (§6) builds a
# fresh EcapaLocalSpeakerIdProvider() on every call, i.e. every single
# Celery task — an instance attribute would re-pay the model-load cost on
# every recording. Caching at module scope means only the first task to
# run in a given worker process pays it (measured ~2-8s); every task after
# that in the same prefork process reuses it. Safe without a lock: Celery
# prefork workers run one task at a time per process.
_cached_classifier = None


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

    def _get_classifier(self):
        global _cached_classifier
        if _cached_classifier is None:
            try:
                from speechbrain.inference.speaker import EncoderClassifier
            except ImportError as exc:
                raise ImportError(
                    "Speaker identification requires the optional 'speaker-id' "
                    "dependency group — run `uv sync --extra speaker-id`."
                ) from exc
            _cached_classifier = EncoderClassifier.from_hparams(source=_MODEL_SOURCE)
        return _cached_classifier

    async def extract_embedding(self, audio_path: str) -> list[float]:
        # Model inference is CPU/GPU-bound and blocking — keep it off the
        # event loop (same pattern as the Azure STT adapter).
        return await asyncio.to_thread(self._extract_embedding_sync, audio_path)

    def _extract_embedding_sync(self, audio_path: str) -> list[float]:
        # Not torchaudio.load(): as of torchaudio 2.9 it's a thin wrapper
        # around torchcodec, which dynamically links against a specific
        # FFmpeg ABI version — failed to load its shared library in
        # production ("Could not load ... libtorchcodec_core4.so").
        # soundfile (libsndfile) has no such version coupling. audio_path
        # is always mono (temp_storage.py normalizes with `-ac 1`), so
        # this 1D array becomes the (batch=1, samples) shape
        # encode_batch() expects — the same shape torchaudio.load() used
        # to produce for mono input via its channels-first (1, samples).
        import soundfile as sf
        import torch

        classifier = self._get_classifier()
        data, _sample_rate = sf.read(audio_path, dtype="float32")
        signal = torch.from_numpy(data).unsqueeze(0)
        embedding = classifier.encode_batch(signal)
        return embedding.squeeze().tolist()

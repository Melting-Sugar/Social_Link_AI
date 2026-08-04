import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.slicing import delete_speaker_clips, slice_audio_by_speaker
from app.audio.temp_storage import delete_temp_file
from app.integrations.llm.claude import ClaudeClient
from app.integrations.prosody.factory import get_prosody_provider
from app.integrations.speaker_id.factory import get_speaker_id_provider
from app.integrations.stt.amivoice import extract_prosody_scores
from app.integrations.stt.factory import get_stt_provider
from app.models.conversation import Conversation
from app.models.recording import RecordingStatus
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.recording_repository import RecordingRepository
from app.repositories.voice_profile_repository import VoiceProfileRepository

logger = logging.getLogger(__name__)


class AnalysisService:
    """§3.2's 3-layer pipeline + §12's self/other resolution, orchestrated
    for one Recording. Runs inside a Celery task (app/workers/
    analysis_worker.py), never called directly from the API — the upload
    endpoint only kicks the job off (§11.5).

    §12.3 確定事項25: with the default STT_PROVIDER=amivoice, the STT and
    prosody layers collapse into a single vendor call (AmiVoice ESAS) —
    the separate ProsodyProvider stage only actually runs as a fallback
    (STT_PROVIDER=azure or a future non-bundled STT vendor)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._recordings = RecordingRepository(session)
        self._conversations = ConversationRepository(session)
        self._voice_profiles = VoiceProfileRepository(session)
        self._stt = get_stt_provider()
        self._prosody = get_prosody_provider()
        self._speaker_id = get_speaker_id_provider()
        self._llm = ClaudeClient()

    async def run(self, recording_id: uuid.UUID) -> None:
        recording = await self._recordings.get_by_id(recording_id)
        if recording is None:
            logger.warning("analysis_service.run: recording %s not found", recording_id)
            return

        wav_path = recording.temp_audio_path
        speaker_clips: dict[str, str] = {}

        try:
            await self._recordings.set_status(recording, RecordingStatus.PROCESSING)
            await self._session.commit()

            if wav_path is None:
                raise RuntimeError("録音ファイルが見つかりません。")

            conversation = await self._session.get(Conversation, recording.conversation_id)
            if conversation is None:
                raise RuntimeError("会話が見つかりません。")

            # 1. STT — diarized transcript (§3.3: split happens once, here)
            stt_result = await self._stt.transcribe(wav_path)
            if not stt_result.segments:
                raise RuntimeError("音声が検出できませんでした。マイクの位置を確認し、もう一度お試しください。")

            # 2. Fast topic extraction — §11.6 progressive reveal
            topic = await self._llm.extract_topic(transcript=stt_result.full_transcript)
            await self._recordings.set_topic(recording, topic)
            await self._session.commit()

            # 3. §12: resolve which diarized speaker is "self" via voice-
            # profile cosine similarity, then relabel the transcript.
            speaker_clips = await slice_audio_by_speaker(wav_path, stt_result.segments)
            self_label = await self._resolve_self_speaker(conversation.user_id, speaker_clips)
            if self_label is None:
                raise RuntimeError(
                    "話者の識別に失敗しました。設定画面から声紋の登録状況をご確認のうえ、"
                    "もう一度お試しください。"
                )
            other_label = next((label for label in speaker_clips if label != self_label), None)

            relabeled_transcript = "\n".join(
                f"[{'user' if seg.speaker_label == self_label else 'other'}] {seg.text}"
                for seg in stt_result.segments
            )

            # 4. Prosody — on the OTHER speaker's clip specifically: the
            # value proposition (§2, §3.1) is reading the conversation
            # partner's reaction, not the user's own tone. §12.3 確定事項25:
            # AmiVoice bundles ESAS sentiment into the same STT call, so
            # when available it's used directly instead of a second vendor
            # call (slice_audio_by_speaker's per-speaker clip is only
            # needed as a fallback path here — §12's self/other resolution
            # above still needs it regardless of STT vendor).
            prosody_scores: dict[str, float] = {}
            if other_label is not None:
                if stt_result.raw_vendor_response is not None:
                    other_segments = [
                        seg for seg in stt_result.segments if seg.speaker_label == other_label
                    ]
                    prosody_scores = extract_prosody_scores(
                        stt_result.raw_vendor_response, other_segments
                    )
                if not prosody_scores:
                    try:
                        prosody_result = await self._prosody.analyze(speaker_clips[other_label])
                        prosody_scores = prosody_result.scores
                    except NotImplementedError:
                        # §3.6 no separate prosody vendor active — proceed
                        # without prosody input, not as a failure
                        # (Realtime-only-style degradation).
                        prosody_scores = {}

            # 5. Full interpretive report (Sonnet 5, §11.11-compliant prompt)
            report = await self._llm.generate_conversation_report(
                transcript=relabeled_transcript,
                prosody_scores=prosody_scores,
                scene=conversation.scene.value,
            )
            await self._recordings.set_flow(recording, report.flow)
            await self._recordings.set_reaction(recording, report.other_reaction)
            await self._recordings.set_relationship(recording, report.relationship_distance)
            await self._recordings.set_suggestion(
                recording, report.suggestion_category, report.suggestion_text
            )
            await self._recordings.set_status(recording, RecordingStatus.COMPLETED)
            await self._session.commit()

        except Exception as exc:
            logger.exception("analysis_service.run failed for recording %s", recording_id)
            await self._recordings.set_status(recording, RecordingStatus.FAILED, error_message=str(exc))
            await self._session.commit()
        finally:
            # §11.5 / §8: temp audio (mixed + per-speaker clips) is deleted
            # unconditionally, success or failure.
            if wav_path is not None:
                delete_temp_file(wav_path)
            delete_speaker_clips(speaker_clips)
            await self._recordings.clear_temp_audio_path(recording)
            await self._session.commit()

    async def _resolve_self_speaker(
        self, user_id: uuid.UUID, speaker_clips: dict[str, str]
    ) -> str | None:
        voice_profile = await self._voice_profiles.get_by_user_id(user_id)
        if voice_profile is None:
            return None

        best_label: str | None = None
        best_similarity = -1.0
        for label, clip_path in speaker_clips.items():
            try:
                embedding = await self._speaker_id.extract_embedding(clip_path)
            except NotImplementedError:
                return None
            similarity = self._speaker_id.cosine_similarity(embedding, voice_profile.embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_label = label
        return best_label

import asyncio
import logging
import uuid
from dataclasses import dataclass

import anthropic
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.slicing import delete_speaker_clips, slice_audio_by_speaker
from app.audio.temp_storage import delete_temp_file
from app.core.config import get_settings
from app.integrations.llm.claude import ClaudeClient
from app.integrations.prosody.factory import get_prosody_provider
from app.integrations.speaker_id.factory import get_speaker_id_provider
from app.integrations.stt.amivoice import extract_prosody_scores
from app.integrations.stt.factory import get_stt_provider
from app.models.conversation import Conversation
from app.models.recording import AnalysisStage, Recording, RecordingStatus
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.recording_repository import RecordingRepository
from app.repositories.voice_profile_repository import VoiceProfileRepository

logger = logging.getLogger(__name__)

_NETWORK_ERROR_MESSAGE = "通信エラーが発生しました。電波の良い場所でもう一度お試しください。"
_VENDOR_ERROR_MESSAGE = "解析中に問題が発生しました。もう一度お試しください。"

# 2026-08-12ユーザー指示: 個々の処理（AmiVoice呼び出し等）ごとに別々の
# タイムアウトを設けるのではなく、解析全体で1本の締め切りにする。
# amivoice.py自身の600秒ポーリング上限やhttpxの60秒/リクエスト上限は
# それぞれの内部実装の保険としてそのまま残すが、実際に効くのは常に
# こちらの300秒の方が先（バックストップの関係、amivoice.py参照）。
_PIPELINE_TIMEOUT_SECONDS = 300.0

_STAGE_ERROR_LABELS: dict[AnalysisStage | None, str] = {
    AnalysisStage.ANALYZING_CONVERSATION: "会話内容の分析",
    AnalysisStage.SEPARATING_SPEAKERS: "話者の分離",
    AnalysisStage.GENERATING_REPORT: "レポートの生成",
}


@dataclass
class SpeakerResolution:
    """§12 self/other voiceprint resolution outcome. Each side is the set
    of raw diarized labels resolved to that role — usually one label, but
    two when AmiVoice's diarization split a single physical speaker into
    two labels and _resolve_speakers() merged them back together (see
    its "both individually clear speaker_id_min_similarity" branch).
    `self_label`/`other_label` are None together only when identification
    genuinely failed (no profile, threshold not met, extraction
    unsupported) — see `self_only`/`other_only` for the "only one
    physical speaker was ever captured" case, which is NOT a failure,
    just a limited result."""

    self_label: frozenset[str] | None
    other_label: frozenset[str] | None
    self_only: bool = False
    other_only: bool = False


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
        self._settings = get_settings()
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

            try:
                await asyncio.wait_for(
                    self._run_pipeline(recording, wav_path, speaker_clips),
                    timeout=_PIPELINE_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                # current_stage was last committed by whichever step was in
                # progress when the deadline hit (set_stage()+commit() below
                # happen right as each step starts) — that's what actually
                # went wrong, not a generic failure.
                stage_label = _STAGE_ERROR_LABELS.get(recording.current_stage, "解析")
                raise RuntimeError(
                    f"解析に時間がかかりすぎたため中断しました（{stage_label}に時間が"
                    "かかっています）。もう一度お試しください。"
                ) from None

        except RuntimeError as exc:
            # Our own explicitly-raised messages above are already
            # curated, user-facing Japanese — safe to show as-is.
            logger.exception("analysis_service.run failed for recording %s", recording_id)
            await self._recordings.set_status(recording, RecordingStatus.FAILED, error_message=str(exc))
            await self._session.commit()
        except (TimeoutError, httpx.HTTPError):
            logger.exception("analysis_service.run network error for recording %s", recording_id)
            await self._recordings.set_status(
                recording, RecordingStatus.FAILED, error_message=_NETWORK_ERROR_MESSAGE
            )
            await self._session.commit()
        except anthropic.APIError:
            logger.exception("analysis_service.run Claude API error for recording %s", recording_id)
            await self._recordings.set_status(
                recording, RecordingStatus.FAILED, error_message=_VENDOR_ERROR_MESSAGE
            )
            await self._session.commit()
        except Exception:
            # Anything unanticipated: never surface the raw exception text
            # to the user (§11.5 — error copy should be specific to what
            # actually happened, and a bare Python exception string is
            # neither specific nor necessarily safe to display).
            logger.exception("analysis_service.run unexpected error for recording %s", recording_id)
            await self._recordings.set_status(
                recording, RecordingStatus.FAILED, error_message=_VENDOR_ERROR_MESSAGE
            )
            await self._session.commit()
        finally:
            # §11.5 / §8: temp audio (mixed + per-speaker clips) is deleted
            # unconditionally, success or failure. speaker_clips is filled
            # in-place by _run_pipeline (not reassigned here) specifically
            # so a mid-flight timeout cancellation still leaves whatever
            # was already sliced visible for cleanup.
            if wav_path is not None:
                delete_temp_file(wav_path)
            delete_speaker_clips(speaker_clips)
            await self._recordings.clear_temp_audio_path(recording)
            await self._session.commit()

    async def _run_pipeline(
        self, recording: Recording, wav_path: str | None, speaker_clips: dict[str, str]
    ) -> None:
        """The actual STT->speaker-id->prosody->LLM pipeline (§3.2), wrapped
        by run() in a single overall asyncio.wait_for deadline rather than
        per-step timeouts (2026-08-12 user instruction)."""
        if wav_path is None:
            raise RuntimeError("録音ファイルが見つかりません。")

        conversation = await self._session.get(Conversation, recording.conversation_id)
        if conversation is None:
            raise RuntimeError("会話が見つかりません。")

        # 1. STT — diarized transcript (§3.3: split happens once, here)
        await self._recordings.set_stage(recording, AnalysisStage.ANALYZING_CONVERSATION)
        await self._session.commit()
        stt_result = await self._stt.transcribe(wav_path)
        if not stt_result.segments:
            raise RuntimeError("音声が検出できませんでした。マイクの位置を確認し、もう一度お試しください。")

        # 2. Fast topic extraction — §11.6 progressive reveal
        topic = await self._llm.extract_topic(transcript=stt_result.full_transcript)
        await self._recordings.set_topic(recording, topic)
        await self._session.commit()

        # 3. §12: resolve which diarized speaker is "self" via voice-
        # profile cosine similarity, then relabel the transcript.
        await self._recordings.set_stage(recording, AnalysisStage.SEPARATING_SPEAKERS)
        await self._session.commit()
        # .update(), not reassignment — speaker_clips is the same dict the
        # caller's `finally` cleans up, so a mid-flight timeout cancellation
        # still leaves whatever was already sliced visible for deletion.
        speaker_clips.update(await slice_audio_by_speaker(wav_path, stt_result.segments))
        resolution = await self._resolve_speakers(conversation.user_id, speaker_clips)

        if resolution.self_label is None and resolution.other_label is None:
            raise RuntimeError(
                "話者の識別に失敗しました。設定画面から声紋の登録状況をご確認のうえ、"
                "もう一度お試しください。"
            )

        # 話者が1人しか分離できなかった場合でも、声紋照合で「誰だったか」
        # は分かるので、エラーで止めずレポート生成まで進める
        # （2026-08-12ユーザー指示、①の修正から発展）。検出できなかった
        # 側については無理に推測させず、その旨をLLMに伝えて正直に
        # 書かせる（missing_speaker_note、claude.py参照）。UIにも
        # single_speaker_detectedとして開示する。
        missing_speaker_note: str | None = None
        if resolution.self_only:
            missing_speaker_note = (
                "相手の発言を検出できませんでした。文字起こしはあなたの発言のみです。"
            )
        elif resolution.other_only:
            missing_speaker_note = (
                "あなたの発言を検出できませんでした。文字起こしは相手の発言のみです。"
            )
        if missing_speaker_note is not None:
            await self._recordings.set_single_speaker_detected(recording, True)
            await self._session.commit()

        # Usually one raw diarized label each; two when a same-speaker
        # collapse (_SAME_SPEAKER_COLLAPSE_THRESHOLD) merged a spurious
        # split back into one physical speaker. self_labels empty means
        # nothing resolved as self (other_only case) — never treated as
        # "everything is self" by the `in` checks below.
        self_labels = resolution.self_label or frozenset()
        other_labels = resolution.other_label

        # 「あなた」「相手」は英語の[user]/[other]タグのままLLMに渡すと、
        # 生成文中に"userが〜""otherも〜"と英語のまま出力されてしまう
        # ため（実際に確認済み）、最初から日本語ラベルで渡す。
        relabeled_transcript = "\n".join(
            f"[{'あなた' if seg.speaker_label in self_labels else '相手'}] {seg.text}"
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
        # other_labels is None specifically in the self_only case (§12,
        # missing_speaker_note above) — no other-speaker clip exists to
        # get prosody from at all, so skip it entirely rather than
        # erroring. other_only DOES still have other_labels set, so
        # prosody on the other speaker's tone remains available even
        # without the user's own audio.
        prosody_scores: dict[str, float] = {}
        if other_labels:
            if stt_result.raw_vendor_response is not None:
                other_segments = [
                    seg for seg in stt_result.segments if seg.speaker_label in other_labels
                ]
                prosody_scores = extract_prosody_scores(stt_result.raw_vendor_response, other_segments)
            if not prosody_scores:
                try:
                    # A collapsed pair still only has one underlying real
                    # voice, so any one member clip represents it.
                    prosody_result = await self._prosody.analyze(speaker_clips[next(iter(other_labels))])
                    prosody_scores = prosody_result.scores
                except NotImplementedError:
                    # §3.6 no separate prosody vendor active — proceed
                    # without prosody input, not as a failure
                    # (Realtime-only-style degradation).
                    prosody_scores = {}

        # 5. Full interpretive report (Sonnet 5, §11.11-compliant prompt).
        # Prior-round context (if this isn't round 1) gives the model
        # continuity across a multi-round conversation session, though
        # the prompt explicitly tells it not to let this override
        # what THIS round's actual content shows (claude.py).
        previous_round_context = await self._build_previous_round_context(recording)
        await self._recordings.set_stage(recording, AnalysisStage.GENERATING_REPORT)
        await self._session.commit()
        report = await self._llm.generate_conversation_report(
            transcript=relabeled_transcript,
            prosody_scores=prosody_scores,
            scene=conversation.scene.value,
            previous_round_context=previous_round_context,
            missing_speaker_note=missing_speaker_note,
        )
        await self._recordings.set_flow(recording, report.flow)
        await self._recordings.set_reaction(recording, report.other_reaction)
        await self._recordings.set_relationship(recording, report.relationship_distance)
        await self._recordings.set_suggestion(
            recording, report.suggestion_category, report.suggestion_text
        )
        await self._recordings.set_status(recording, RecordingStatus.COMPLETED)
        await self._session.commit()

    async def _resolve_speakers(
        self, user_id: uuid.UUID, speaker_clips: dict[str, str]
    ) -> SpeakerResolution:
        voice_profile = await self._voice_profiles.get_by_user_id(user_id)
        if voice_profile is None:
            return SpeakerResolution(self_label=None, other_label=None)

        similarities: dict[str, float] = {}
        for label, clip_path in speaker_clips.items():
            try:
                embedding = await self._speaker_id.extract_embedding(clip_path)
            except NotImplementedError:
                return SpeakerResolution(self_label=None, other_label=None)
            similarities[label] = self._speaker_id.cosine_similarity(embedding, voice_profile.embedding)

        if len(similarities) == 1:
            # 話者分離が1人分しか出なかったケース（実際にAzure/AmiVoiceどちら
            # でも起こりうると確認済み）。声紋照合でその1人が自分か相手かを
            # 判別し、レポート生成を諦めるのではなく限定的な結果として扱う
            # （run()側でself_only/other_onlyとして専用メッセージを出す）。
            [(label, similarity)] = similarities.items()
            if similarity >= self._settings.speaker_id_min_similarity:
                return SpeakerResolution(self_label=frozenset({label}), other_label=None, self_only=True)
            return SpeakerResolution(self_label=None, other_label=frozenset({label}), other_only=True)

        # 2人以上分離できた場合（diarizationMaxSpeaker=2のAmiVoiceでは常に
        # 2人、Azureフォールバックでは3人以上の可能性もあるがrun()側は
        # 元々1人しかother_labelを見ないため、3人目以降は無視する既存の
        # 挙動を維持する）。最高スコアが絶対的な下限、かつ2位との差が
        # 十分でなければ「自信を持って判別できない」として識別失敗扱いにする。
        ranked = sorted(similarities.items(), key=lambda item: item[1], reverse=True)
        best_label, best_similarity = ranked[0]
        second_label, second_similarity = ranked[1]
        if (
            best_similarity < self._settings.speaker_id_min_similarity
            or (best_similarity - second_similarity) < self._settings.speaker_id_min_margin
        ):
            # AmiVoiceの話者分離は、実際は1人しか話していない録音でも、
            # まれに2ラベルに誤って分割することがある（実データで確認
            # 済み — 登録済みユーザーで繰り返し「話者の識別に失敗」が
            # 発生し、調べたところ上位2ラベルとも単独で見れば登録声紋に
            # 十分似ている＝2位との僅差だけがmarginチェックに引っかかって
            # いたケースだった）。margin不足の原因が「best自体が弱い」の
            # ではなく「上位2つとも登録声紋に対し個別に十分な類似度がある」
            # ことであれば、別人との取り違えではなく本人の誤分割である
            # 可能性が高いと判断し、単一話者ケースと同じ救済に倒す。
            # （ラベル同士を直接比較する方式も検討したが、合成音声での
            # 実測でクリーンな別人同士でも0.8超の類似度が出ることがあり、
            # 誤って別人を統合しかねず不採用とした — 登録声紋との個別の
            # 一致度のみを根拠にする、より保守的なこの方式を採用）。
            if (
                best_similarity >= self._settings.speaker_id_min_similarity
                and second_similarity >= self._settings.speaker_id_min_similarity
            ):
                merged = frozenset({best_label, second_label})
                return SpeakerResolution(self_label=merged, other_label=None, self_only=True)
            return SpeakerResolution(self_label=None, other_label=None)

        other_label = frozenset(label for label in speaker_clips if label != best_label)
        return SpeakerResolution(self_label=frozenset({best_label}), other_label=other_label)

    async def _build_previous_round_context(self, recording: Recording) -> str | None:
        if recording.round_number <= 1:
            return None
        prior_rounds = await self._recordings.list_by_conversation(recording.conversation_id)
        previous = next(
            (
                r
                for r in prior_rounds
                if r.round_number == recording.round_number - 1 and r.status == RecordingStatus.COMPLETED
            ),
            None,
        )
        if previous is None:
            return None
        return (
            f"話題: {previous.topic}\n会話の流れ: {previous.flow}\n"
            f"相手の反応: {previous.other_reaction}\n関係性の距離感: {previous.relationship_distance}"
        )

import asyncio
import logging
import uuid
from dataclasses import dataclass

import anthropic
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.audio.slicing import delete_speaker_clips, slice_audio_by_speaker
from app.audio.temp_storage import (
    delete_audio_bytes,
    delete_temp_file,
    materialize_audio_from_redis,
)
from app.core.config import get_settings
from app.integrations.exceptions import VendorResponseError
from app.integrations.llm.claude import ClaudeClient
from app.integrations.prosody.factory import get_prosody_provider
from app.integrations.speaker_id.factory import get_speaker_id_provider
from app.integrations.stt.amivoice import extract_prosody_scores
from app.integrations.stt.base import STTResult
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
    of raw diarized labels resolved to that role — usually one label.
    `self_label`/`other_label` are None together only when identification
    genuinely failed (no profile, threshold not met, extraction
    unsupported) AND `self_absent` is False — see `self_only`/`other_only`
    for the "only one physical speaker was ever captured" case, which is
    NOT a failure, just a limited result.

    2026-08-15ユーザー指示: 2人分離できた場合、best_similarityが閾値を
    超えていれば2位の値に関わらずbestを自分とみなす（marginチェック廃止）。
    bestが閾値未満なら2位も必ず閾値未満（best>=second）なので、自分は
    この会話に参加していないとみなし、self_absent=Trueとして
    other_label_a/bに両方の生ラベルを個別に保持する（他者2名の会話として
    別経路で分析するため、self_label/other_labelは使わずNoneのまま）。"""

    self_label: frozenset[str] | None
    other_label: frozenset[str] | None
    self_only: bool = False
    other_only: bool = False
    self_absent: bool = False
    other_label_a: frozenset[str] | None = None
    other_label_b: frozenset[str] | None = None


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

        # temp_audio_path is just a non-null marker at this point (see
        # recordings.py) — the actual bytes live in Redis, since this
        # worker is a separate Fly Machine from the api process that
        # wrote them, with its own independent local disk. Materializing
        # here writes a fresh local copy this machine can actually read.
        wav_path: str | None = None
        speaker_clips: dict[str, str] = {}

        try:
            await self._recordings.set_status(recording, RecordingStatus.PROCESSING)
            await self._session.commit()

            if recording.temp_audio_path is not None:
                wav_path = await materialize_audio_from_redis(str(recording.id))

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

        except VendorResponseError:
            # Raised by vendor adapters (amivoice.py, claude.py) for a raw,
            # English, technical failure (e.g. AmiVoice's own error payload
            # dumped into the message) — caught ahead of the plain
            # RuntimeError branch below so it never reaches str(exc)/the
            # user. Confirmed live: real recordings surfaced AmiVoice's
            # raw {'status': 'error', ...} payload as the on-screen message.
            logger.exception("analysis_service.run vendor error for recording %s", recording_id)
            await self._recordings.set_status(
                recording, RecordingStatus.FAILED, error_message=_VENDOR_ERROR_MESSAGE
            )
            await self._session.commit()
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
            await delete_audio_bytes(str(recording.id))
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

        if resolution.self_label is None and resolution.other_label is None and not resolution.self_absent:
            raise RuntimeError(
                "話者の識別に失敗しました。設定画面から声紋の登録状況をご確認のうえ、"
                "もう一度お試しください。"
            )

        if resolution.self_absent:
            # 2026-08-15ユーザー指示: 両者とも自分の声紋に一致しなかった
            # 場合、自分はこの会話に参加していないとみなし、他者2名の
            # 会話として別経路で分析する（relationship_distance・
            # suggestionは自分視点の項目のため生成しない）。
            await self._recordings.set_self_absent(recording, True)
            await self._session.commit()
            await self._run_third_party_pipeline(
                recording, stt_result, resolution, speaker_clips, conversation.scene.value
            )
            return

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

    async def _run_third_party_pipeline(
        self,
        recording: Recording,
        stt_result: STTResult,
        resolution: SpeakerResolution,
        speaker_clips: dict[str, str],
        scene: str,
    ) -> None:
        """2026-08-15ユーザー指示: 自分がこの会話に参加していないと判定
        された場合の別経路。話者を「参加者A」「参加者B」としてラベル付け
        し、2名分の反応を生成する。relationship_distance・suggestionは
        自分視点の項目のため生成しない（run()側で自然に空のまま — UIも
        値がnullなら該当セクションを表示しない、既存の設計をそのまま
        使う）。"""
        labels_a = resolution.other_label_a or frozenset()
        labels_b = resolution.other_label_b or frozenset()

        relabeled_transcript = "\n".join(
            f"[{'参加者A' if seg.speaker_label in labels_a else '参加者B'}] {seg.text}"
            for seg in stt_result.segments
        )

        async def _prosody_for(labels: frozenset[str]) -> dict[str, float]:
            if not labels:
                return {}
            scores: dict[str, float] = {}
            if stt_result.raw_vendor_response is not None:
                segs = [seg for seg in stt_result.segments if seg.speaker_label in labels]
                scores = extract_prosody_scores(stt_result.raw_vendor_response, segs)
            if not scores:
                try:
                    result = await self._prosody.analyze(speaker_clips[next(iter(labels))])
                    scores = result.scores
                except NotImplementedError:
                    scores = {}
            return scores

        prosody_a = await _prosody_for(labels_a)
        prosody_b = await _prosody_for(labels_b)

        await self._recordings.set_stage(recording, AnalysisStage.GENERATING_REPORT)
        await self._session.commit()
        report = await self._llm.generate_third_party_conversation_report(
            transcript=relabeled_transcript,
            prosody_scores_a=prosody_a,
            prosody_scores_b=prosody_b,
            scene=scene,
        )
        await self._recordings.set_flow(recording, report.flow)
        await self._recordings.set_reaction(recording, report.reaction_a)
        await self._recordings.set_reaction_2(recording, report.reaction_b)
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

        logger.info(
            "speaker resolution similarities for user %s: %s (min_similarity=%.2f)",
            user_id,
            {label: round(score, 4) for label, score in similarities.items()},
            self._settings.speaker_id_min_similarity,
        )

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
        # 挙動を維持する）。
        # 2026-08-15ユーザー指示: best_similarityが閾値を超えていれば、
        # 2位の値に関わらずbest=自分・残り=相手とする（旧来のmargin
        # チェックは廃止 — 実データで、本人の発話同士でも0.15程度のばら
        # つきがあり、僅差を理由に本人まで弾いてしまっていたため）。
        ranked = sorted(similarities.items(), key=lambda item: item[1], reverse=True)
        best_label, best_similarity = ranked[0]
        second_label, _second_similarity = ranked[1]
        if best_similarity >= self._settings.speaker_id_min_similarity:
            other_label = frozenset(label for label in speaker_clips if label != best_label)
            return SpeakerResolution(self_label=frozenset({best_label}), other_label=other_label)

        # best自体が閾値未満 → 2位も必ず閾値未満（best>=second のため）。
        # 自分はこの会話に参加していないとみなし、2名とも「他者」として
        # 扱う（2026-08-15ユーザー指示）。
        return SpeakerResolution(
            self_label=None,
            other_label=None,
            self_absent=True,
            other_label_a=frozenset({best_label}),
            other_label_b=frozenset({second_label}),
        )

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

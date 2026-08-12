import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recording import AnalysisStage, Recording, RecordingStatus


class RecordingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        conversation_id: uuid.UUID,
        round_number: int,
        duration_sec: int,
        temp_audio_path: str,
    ) -> Recording:
        recording = Recording(
            conversation_id=conversation_id,
            round_number=round_number,
            duration_sec=duration_sec,
            temp_audio_path=temp_audio_path,
            status=RecordingStatus.PENDING,
        )
        self._session.add(recording)
        await self._session.flush()
        return recording

    async def get_by_id_in_conversation(
        self, recording_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> Recording | None:
        result = await self._session.execute(
            select(Recording).where(
                Recording.id == recording_id, Recording.conversation_id == conversation_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, recording_id: uuid.UUID) -> Recording | None:
        return await self._session.get(Recording, recording_id)

    async def list_by_conversation(self, conversation_id: uuid.UUID) -> list[Recording]:
        result = await self._session.execute(
            select(Recording)
            .where(Recording.conversation_id == conversation_id)
            .order_by(Recording.round_number)
        )
        return list(result.scalars().all())

    async def next_round_number(self, conversation_id: uuid.UUID) -> int:
        existing = await self.list_by_conversation(conversation_id)
        return (max((r.round_number for r in existing), default=0)) + 1

    async def set_status(
        self, recording: Recording, status: RecordingStatus, error_message: str | None = None
    ) -> None:
        recording.status = status
        recording.error_message = error_message
        await self._session.flush()

    async def set_stage(self, recording: Recording, stage: AnalysisStage) -> None:
        recording.current_stage = stage
        await self._session.flush()

    async def set_topic(self, recording: Recording, topic: str) -> None:
        recording.topic = topic
        recording.topic_ready = True
        await self._session.flush()

    async def set_flow(self, recording: Recording, flow: str) -> None:
        recording.flow = flow
        recording.flow_ready = True
        await self._session.flush()

    async def set_reaction(self, recording: Recording, other_reaction: str) -> None:
        recording.other_reaction = other_reaction
        recording.reaction_ready = True
        await self._session.flush()

    async def set_relationship(self, recording: Recording, relationship_distance: str) -> None:
        recording.relationship_distance = relationship_distance
        recording.relationship_ready = True
        await self._session.flush()

    async def set_suggestion(
        self, recording: Recording, suggestion_category: str, suggestion_text: str
    ) -> None:
        recording.suggestion_category = suggestion_category
        recording.suggestion_text = suggestion_text
        recording.suggestion_ready = True
        await self._session.flush()

    async def clear_temp_audio_path(self, recording: Recording) -> None:
        recording.temp_audio_path = None
        await self._session.flush()

    async def get_orphaned_temp_files(self, cutoff: datetime) -> list[Recording]:
        """§11.5 — Celery Beat safety net: a recording whose temp audio path
        is still set well after it should have been processed and deleted
        means the worker crashed or failed before its `finally` cleanup ran."""
        result = await self._session.execute(
            select(Recording).where(
                Recording.temp_audio_path.is_not(None), Recording.created_at < cutoff
            )
        )
        return list(result.scalars().all())

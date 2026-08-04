import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.enums import Scene
from app.models.record import Record


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, user_id: uuid.UUID, scene: Scene, started_at: datetime) -> Conversation:
        conversation = Conversation(user_id=user_id, scene=scene, started_at=started_at)
        self._session.add(conversation)
        await self._session.flush()
        return conversation

    async def get_by_id_for_user(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> Conversation | None:
        result = await self._session.execute(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def mark_ended(self, conversation: Conversation, ended_at: datetime) -> None:
        conversation.ended_at = ended_at
        await self._session.flush()

    async def get_unsaved_older_than(self, cutoff: datetime) -> list[Conversation]:
        """§5 確定事項16 — a Conversation with no linked Record and started
        before `cutoff` is "abandoned" (user never completed A-⑥) and is a
        candidate for the Celery Beat cleanup sweep."""
        has_record = select(Record.id).where(Record.conversation_id == Conversation.id).exists()
        result = await self._session.execute(
            select(Conversation).where(Conversation.started_at < cutoff, ~has_record)
        )
        return list(result.scalars().all())

    async def delete(self, conversation: Conversation) -> None:
        await self._session.delete(conversation)

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Condition
from app.models.record import Record
from app.repositories.record_repository import RecordRepository


class RecordService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._records = RecordRepository(session)

    async def create(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        condition: Condition,
        mood_anxiety_score: int,
        next_goal: str | None,
        memo: str | None,
        summary_bullets: list[str],
    ) -> Record:
        """A-⑥: this is the operation that makes a Conversation exempt from
        the cleanup sweep (§5, §11.9) — everything else about it is
        deleted if this never happens."""
        return await self._records.create(
            conversation_id=conversation_id,
            user_id=user_id,
            date=datetime.now(UTC).date(),
            condition=condition,
            mood_anxiety_score=mood_anxiety_score,
            next_goal=next_goal,
            memo=memo,
            summary_bullets=summary_bullets,
        )

    async def list_for_user(self, user_id: uuid.UUID) -> list[Record]:
        return await self._records.list_for_user(user_id)

    async def delete(self, record_id: uuid.UUID, user_id: uuid.UUID) -> None:
        record = await self._records.get_by_id_for_user(record_id, user_id)
        if record is None:
            raise ValueError("記録が見つかりません。")
        await self._records.delete(record)

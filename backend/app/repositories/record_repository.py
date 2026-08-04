import uuid
from datetime import date as date_type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Condition
from app.models.record import Record


class RecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        date: date_type,
        condition: Condition,
        mood_anxiety_score: int,
        next_goal: str | None,
        memo: str | None,
        summary_bullets: list[str],
    ) -> Record:
        record = Record(
            conversation_id=conversation_id,
            user_id=user_id,
            date=date,
            condition=condition,
            mood_anxiety_score=mood_anxiety_score,
            next_goal=next_goal,
            memo=memo,
            summary_bullets=summary_bullets,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_by_id_for_user(self, record_id: uuid.UUID, user_id: uuid.UUID) -> Record | None:
        result = await self._session.execute(
            select(Record).where(Record.id == record_id, Record.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Record]:
        result = await self._session.execute(
            select(Record).where(Record.user_id == user_id).order_by(Record.date.desc())
        )
        return list(result.scalars().all())

    async def delete(self, record: Record) -> None:
        await self._session.delete(record)

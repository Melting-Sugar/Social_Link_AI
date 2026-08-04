import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.voice_profile import VoiceProfile


class VoiceProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> VoiceProfile | None:
        result = await self._session.execute(
            select(VoiceProfile).where(VoiceProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, *, user_id: uuid.UUID, embedding: list[float]) -> VoiceProfile:
        """E-① supports re-registration, which simply overwrites the
        existing embedding (§11.1)."""
        existing = await self.get_by_user_id(user_id)
        if existing is not None:
            existing.embedding = embedding
            await self._session.flush()
            return existing
        profile = VoiceProfile(user_id=user_id, embedding=embedding)
        self._session.add(profile)
        await self._session.flush()
        return profile

    async def delete(self, profile: VoiceProfile) -> None:
        await self._session.delete(profile)

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def get_profile(self, user_id: uuid.UUID) -> User | None:
        return await self._users.get_by_id(user_id)

    async def delete_account(self, user: User) -> None:
        """§11.5 / privacy-policy.md §6: deleting the account deletes
        everything tied to it. Every child FK (RefreshToken, VoiceProfile,
        Conversation, Record — and Recording via Conversation) is declared
        with ON DELETE CASCADE, so the database itself removes them once
        this row is gone; no manual per-table cleanup needed here."""
        await self._users.delete(user)

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email_or_username(self, identifier: str) -> User | None:
        result = await self._session.execute(
            select(User).where((User.email == identifier) | (User.username == identifier))
        )
        return result.scalar_one_or_none()

    async def create(self, *, email: str, username: str, password_hash: str) -> User:
        user = User(email=email, username=username, password_hash=password_hash)
        self._session.add(user)
        await self._session.flush()
        return user

    async def update_password_hash(self, user: User, new_hash: str) -> None:
        user.password_hash = new_hash
        await self._session.flush()

    async def mark_email_verified(self, user: User) -> None:
        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(UTC)
            await self._session.flush()

    async def delete(self, user: User) -> None:
        await self._session.delete(user)

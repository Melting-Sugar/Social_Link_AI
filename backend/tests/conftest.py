import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Point at a dedicated test database *before* app.core.config is imported
# anywhere, so Settings() picks it up. Never run tests against the dev DB.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://social_link:social_link@localhost:5432/social_link_test",
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-for-real-use")
os.environ.setdefault("ENVIRONMENT", "dev")

from app.core.db import get_db_session
from app.main import app
from app.models.base import Base


@pytest_asyncio.fixture
async def db_session():
    """Fresh schema per test — cheap enough at this table count, and
    guarantees tests never see leftover state from one another."""
    settings_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(settings_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

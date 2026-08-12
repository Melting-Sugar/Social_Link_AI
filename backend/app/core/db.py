from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# §5 確定事項: API layer uses the async engine. FastAPI/uvicorn runs one
# event loop for the whole process lifetime, so a pooled engine (reusing
# asyncpg connections across requests) is correct and desirable here.
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

# Celery workers (app/workers/) instead call asyncio.run(...) once per
# task — a brand-new event loop every time. asyncpg connections are bound
# to the loop that created them, so handing a task a connection pooled
# from a *previous* task's (now-closed) loop crashes with "Future
# attached to a different loop" — this was silently breaking every
# second-and-later analysis and, worse, every run of the 30-minute
# cleanup sweep after a worker's first cycle, since both used the same
# pooled `engine` above. NullPool means no connection is ever reused
# across calls, which is exactly what a loop-per-task worker needs.
worker_engine = create_async_engine(settings.database_url, poolclass=NullPool)
worker_session_factory = async_sessionmaker(worker_engine, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session

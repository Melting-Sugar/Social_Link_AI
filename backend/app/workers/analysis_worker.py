import asyncio
import uuid

from app.core.celery_app import celery_app
from app.core.db import worker_session_factory
from app.services.analysis_service import AnalysisService


@celery_app.task(name="app.workers.analysis_worker.analyze_recording_task")
def analyze_recording_task(recording_id: str) -> None:
    """§5: Celery tasks are synchronous by design — this thin wrapper
    bridges into the async services/repositories via asyncio.run(...)
    rather than maintaining a separate sync data-access layer."""
    asyncio.run(_run(uuid.UUID(recording_id)))


async def _run(recording_id: uuid.UUID) -> None:
    async with worker_session_factory() as session:
        await AnalysisService(session).run(recording_id)

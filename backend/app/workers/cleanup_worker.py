import asyncio
from datetime import UTC, datetime, timedelta

from app.audio.temp_storage import delete_audio_bytes
from app.core.celery_app import celery_app
from app.core.db import worker_session_factory
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.recording_repository import RecordingRepository

_UNSAVED_CONVERSATION_CUTOFF = timedelta(hours=3)
_ORPHANED_AUDIO_CUTOFF = timedelta(hours=1)


@celery_app.task(name="app.workers.cleanup_worker.cleanup_unsaved_conversations")
def cleanup_unsaved_conversations() -> None:
    asyncio.run(_cleanup_unsaved_conversations())


@celery_app.task(name="app.workers.cleanup_worker.cleanup_orphaned_temp_audio")
def cleanup_orphaned_temp_audio() -> None:
    asyncio.run(_cleanup_orphaned_temp_audio())


async def _cleanup_unsaved_conversations() -> None:
    """§5 確定事項16 / §2, §8: enforces "conversations never saved via
    A-⑥ are deleted promptly." There's no client-side "user walked away"
    signal (closing a tab fires nothing), so this periodic sweep is the
    actual enforcement mechanism, not just a backstop."""
    cutoff = datetime.now(UTC) - _UNSAVED_CONVERSATION_CUTOFF
    async with worker_session_factory() as session:
        repo = ConversationRepository(session)
        for conversation in await repo.get_unsaved_older_than(cutoff):
            await repo.delete(conversation)
        await session.commit()


async def _cleanup_orphaned_temp_audio() -> None:
    """§11.5 safety net: catches temp audio a worker failed to delete in
    its own `finally` block (e.g. a crash mid-pipeline). The bytes live
    in Redis (temp_audio_path is just a non-null marker — see
    recordings.py/analysis_service.py), and Redis's own TTL already
    expires them on its own; this sweep's real job is clearing the DB
    marker so the recording doesn't look like it's still pending
    forever, with the delete_audio_bytes() call as a no-op-if-already-
    gone belt-and-suspenders."""
    cutoff = datetime.now(UTC) - _ORPHANED_AUDIO_CUTOFF
    async with worker_session_factory() as session:
        repo = RecordingRepository(session)
        for recording in await repo.get_orphaned_temp_files(cutoff):
            if recording.temp_audio_path:
                await delete_audio_bytes(str(recording.id))
            await repo.clear_temp_audio_path(recording)
        await session.commit()

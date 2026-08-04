from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "social_link_app",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.analysis_worker",
        "app.workers.cleanup_worker",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tokyo",
    enable_utc=True,
)

# §5 確定事項16 / §11.5: unsaved Conversations and any orphaned temp audio
# files must not linger — there is no client-side "user walked away" signal,
# so a periodic sweep is the only reliable enforcement of the "delete
# promptly" retention policy (§2, §8).
celery_app.conf.beat_schedule = {
    "cleanup-unsaved-conversations": {
        "task": "app.workers.cleanup_worker.cleanup_unsaved_conversations",
        "schedule": crontab(minute="*/30"),
    },
    "cleanup-orphaned-temp-audio": {
        "task": "app.workers.cleanup_worker.cleanup_orphaned_temp_audio",
        "schedule": crontab(minute="*/30"),
    },
}

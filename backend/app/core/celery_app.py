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
    # 2026-08-12ユーザー指示で analysis_service.py 側に解析パイプライン
    # 全体で1本の締め切り（300秒、_PIPELINE_TIMEOUT_SECONDS）を設けたため、
    # 通常はそちらが必ず先に発火し、素直にFAILEDへ倒す（finally節のクリーン
    # アップも正常に走る）。ここは「その仕組み自体が何らかの理由で機能
    # しなかった場合」のための、独立した第二の安全網 — 300秒に近い値に
    # しておくことで、万一の際もユーザーを長時間待たせない（以前は840/900
    # 秒だった。§11.5の一時ファイル削除はsoft発火時点でも実行される）。
    task_soft_time_limit=330,
    task_time_limit=360,
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

import uuid

from fastapi import APIRouter, Form, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.audio.temp_storage import save_upload_and_normalize
from app.core.config import get_settings
from app.repositories.recording_repository import RecordingRepository
from app.schemas.recording import RecordingResponse
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/api/conversations", tags=["recordings"])


@router.post(
    "/{conversation_id}/recordings",
    response_model=RecordingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_recording(
    conversation_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
    audio: UploadFile,
    duration_sec: int = Form(...),
) -> RecordingResponse:
    """A-③停止時（または30分到達時）。§11.5: normalizes + writes to shared
    temp storage, creates the Recording row, then hands off to Celery —
    the actual STT→speaker-id→prosody→LLM pipeline runs out-of-request
    (analysis_service via app/workers/analysis_worker.py)."""
    settings = get_settings()
    if not (0 < duration_sec <= settings.max_recording_seconds):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"録音時間は{settings.max_recording_seconds}秒以内である必要があります。",
        )

    await ConversationService(session).get_for_user(conversation_id, current_user.id)

    raw_bytes = await audio.read()
    wav_path = await save_upload_and_normalize(raw_bytes, original_filename=audio.filename or "recording.webm")

    recordings_repo = RecordingRepository(session)
    round_number = await recordings_repo.next_round_number(conversation_id)
    recording = await recordings_repo.create(
        conversation_id=conversation_id,
        round_number=round_number,
        duration_sec=duration_sec,
        temp_audio_path=wav_path,
    )
    await session.commit()

    # Imported here (not at module load) so this router doesn't force a
    # Celery broker connection just to be imported/tested.
    from app.workers.analysis_worker import analyze_recording_task

    analyze_recording_task.delay(str(recording.id))

    return RecordingResponse.model_validate(recording, from_attributes=True)


@router.get("/{conversation_id}/recordings/{recording_id}", response_model=RecordingResponse)
async def get_recording(
    conversation_id: uuid.UUID,
    recording_id: uuid.UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> RecordingResponse:
    """解析中/A-④のポーリング対象 (§11.5, §11.6)."""
    await ConversationService(session).get_for_user(conversation_id, current_user.id)
    recording = await RecordingRepository(session).get_by_id_in_conversation(recording_id, conversation_id)
    if recording is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="録音記録が見つかりません。")
    return RecordingResponse.model_validate(recording, from_attributes=True)

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import MessageResponse
from app.schemas.voice_profile import VoiceProfileStatusResponse
from app.services.voice_enrollment_service import VoiceEnrollmentService

router = APIRouter(prefix="/api/voice-profile", tags=["voice-profile"])


@router.post("", response_model=VoiceProfileStatusResponse, status_code=status.HTTP_201_CREATED)
async def register_voice_profile(
    current_user: CurrentUser, session: DbSession, audio: UploadFile
) -> VoiceProfileStatusResponse:
    """E-①: register or re-register (§11.1 — re-registration just
    overwrites, per voice_profile_repository.upsert)."""
    raw_bytes = await audio.read()
    service = VoiceEnrollmentService(session)
    await service.register(user_id=current_user.id, raw_bytes=raw_bytes, filename=audio.filename or "voice.webm")
    await session.commit()
    return VoiceProfileStatusResponse(registered=True)


@router.get("", response_model=VoiceProfileStatusResponse)
async def get_voice_profile_status(current_user: CurrentUser, session: DbSession) -> VoiceProfileStatusResponse:
    """D-①のステータス表示、及びフロントmiddlewareのリダイレクト判定に使用 (§11.5)."""
    registered = await VoiceEnrollmentService(session).get_status(current_user.id)
    return VoiceProfileStatusResponse(registered=registered)


@router.delete("", response_model=MessageResponse)
async def delete_voice_profile(current_user: CurrentUser, session: DbSession) -> MessageResponse:
    deleted = await VoiceEnrollmentService(session).delete(current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="声紋が登録されていません。")
    await session.commit()
    return MessageResponse(message="声紋データを削除しました。")

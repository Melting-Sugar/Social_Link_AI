import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import MessageResponse
from app.schemas.record import RecordResponse
from app.services.record_service import RecordService

router = APIRouter(prefix="/api/records", tags=["records"])


@router.get("", response_model=list[RecordResponse])
async def list_records(current_user: CurrentUser, session: DbSession) -> list[RecordResponse]:
    """C-①."""
    records = await RecordService(session).list_for_user(current_user.id)
    return [RecordResponse.model_validate(r, from_attributes=True) for r in records]


@router.delete("/{record_id}", response_model=MessageResponse)
async def delete_record(record_id: uuid.UUID, current_user: CurrentUser, session: DbSession) -> MessageResponse:
    try:
        await RecordService(session).delete(record_id, current_user.id)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MessageResponse(message="記録を削除しました。")

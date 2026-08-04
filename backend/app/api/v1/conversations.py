import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.conversation import (
    ConversationResponse,
    CreateConversationRequest,
    SummaryResponse,
)
from app.schemas.record import CreateRecordRequest, RecordResponse
from app.services.conversation_service import ConversationService
from app.services.record_service import RecordService

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: CreateConversationRequest, current_user: CurrentUser, session: DbSession
) -> ConversationResponse:
    """A-②: the returned id drives /conversation/[id] on the frontend for
    the rest of the flow (§11.4)."""
    conversation = await ConversationService(session).create(user_id=current_user.id, scene=payload.scene)
    await session.commit()
    return ConversationResponse.model_validate(conversation, from_attributes=True)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> ConversationResponse:
    """§11.4: "リロードしても会話が失われない" — the frontend re-fetches the
    conversation (for its `scene`, to render SceneBar) by id on every load
    rather than relying on client-side navigation state. Missing from the
    original §11.5 endpoint list; added while building the conversation
    page since nothing else can satisfy the reload-safety requirement."""
    try:
        conversation = await ConversationService(session).get_for_user(conversation_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ConversationResponse.model_validate(conversation, from_attributes=True)


@router.post("/{conversation_id}/summary", response_model=SummaryResponse)
async def generate_summary(
    conversation_id: uuid.UUID, current_user: CurrentUser, session: DbSession
) -> SummaryResponse:
    """A-⑤."""
    try:
        bullets = await ConversationService(session).generate_summary(conversation_id, current_user.id)
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SummaryResponse(summary_bullets=bullets)


@router.post("/{conversation_id}/log", response_model=RecordResponse, status_code=status.HTTP_201_CREATED)
async def log_record(
    conversation_id: uuid.UUID,
    payload: CreateRecordRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> RecordResponse:
    """A-⑥: the operation that makes this conversation permanent (§2, §5)."""
    try:
        await ConversationService(session).get_for_user(conversation_id, current_user.id)
        record = await RecordService(session).create(
            conversation_id=conversation_id,
            user_id=current_user.id,
            condition=payload.condition,
            mood_anxiety_score=payload.mood_anxiety_score,
            next_goal=payload.next_goal,
            memo=payload.memo,
            summary_bullets=payload.summary_bullets,
        )
        await session.commit()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return RecordResponse.model_validate(record, from_attributes=True)

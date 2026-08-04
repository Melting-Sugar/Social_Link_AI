import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Scene


class CreateConversationRequest(BaseModel):
    scene: Scene


class ConversationResponse(BaseModel):
    id: uuid.UUID
    scene: Scene
    started_at: datetime
    ended_at: datetime | None


class SummaryResponse(BaseModel):
    summary_bullets: list[str]

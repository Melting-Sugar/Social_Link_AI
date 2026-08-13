import uuid
from datetime import date as date_type

from pydantic import BaseModel, Field, field_validator

from app.models.enums import Condition


class CreateRecordRequest(BaseModel):
    """A-⑥: saving this is what makes a Conversation survive the cleanup
    sweep (§5, §11.9). `summary_bullets` is round-tripped from whatever
    POST /conversations/{id}/summary (A-⑤) returned — the backend never
    persists an intermediate "pending summary" between the two steps,
    since raw transcripts aren't kept around to regenerate it from (§8)."""

    condition: Condition
    mood_anxiety_score: int = Field(ge=0, le=10)
    next_goal: str | None = None
    memo: str | None = None
    summary_bullets: list[str]

    @field_validator("next_goal", "memo")
    @classmethod
    def free_text_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 400:
            raise ValueError("送信できるのは400字までです。")
        return v


class RecordResponse(BaseModel):
    id: uuid.UUID
    date: date_type
    condition: Condition
    mood_anxiety_score: int
    next_goal: str | None
    memo: str | None
    summary_bullets: list[str]

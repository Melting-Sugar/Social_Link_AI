from pydantic import BaseModel, field_validator

from app.models.enums import Scene


class StatementCheckRequest(BaseModel):
    statement_text: str
    scene: Scene
    relationship_context: str | None = None

    @field_validator("statement_text")
    @classmethod
    def statement_text_length(cls, v: str) -> str:
        if len(v) > 400:
            raise ValueError("送信できるのは400字までです。")
        return v


class StatementCheckResponse(BaseModel):
    is_safe: bool
    feedback: str

from pydantic import BaseModel

from app.models.enums import Scene


class StatementCheckRequest(BaseModel):
    statement_text: str
    scene: Scene
    relationship_context: str | None = None


class StatementCheckResponse(BaseModel):
    is_safe: bool
    feedback: str

import uuid

from pydantic import BaseModel

from app.models.enums import RelationshipDistance, SuggestionCategory
from app.models.recording import AnalysisStage, RecordingStatus


class RecordingResponse(BaseModel):
    """§11.5: every `*_ready` flag lets the frontend show that field the
    moment it's true instead of waiting for `status == completed`
    (§11.6 progressive reveal)."""

    id: uuid.UUID
    round_number: int
    status: RecordingStatus
    current_stage: AnalysisStage | None
    error_message: str | None
    single_speaker_detected: bool
    self_absent: bool

    topic: str | None
    topic_ready: bool
    flow: str | None
    flow_ready: bool
    other_reaction: str | None
    reaction_ready: bool
    other_reaction_2: str | None
    reaction_2_ready: bool
    relationship_distance: RelationshipDistance | None
    relationship_ready: bool
    suggestion_category: SuggestionCategory | None
    suggestion_text: str | None
    suggestion_ready: bool

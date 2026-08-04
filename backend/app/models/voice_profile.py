import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Float

from app.models.base import Base, UUIDPrimaryKeyMixin


class VoiceProfile(UUIDPrimaryKeyMixin, Base):
    """§11.9 / §12.3 — one embedding vector per user, no raw audio ever
    stored. Scale is tiny (one row compared against at most 2 speakers per
    conversation), so a plain float array is sufficient — no pgvector
    dependency needed."""

    __tablename__ = "voice_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    embedding: Mapped[list[float]] = mapped_column(ARRAY(Float), nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="voice_profile")  # noqa: F821

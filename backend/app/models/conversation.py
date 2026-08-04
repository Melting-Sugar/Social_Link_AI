import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import Scene


class Conversation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """§11.9 — deleted promptly (by app/workers/cleanup_worker.py, §5) if
    never saved via A-⑥. Only conversations with a Record survive."""

    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene: Mapped[Scene] = mapped_column(Enum(Scene, native_enum=False), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    recordings: Mapped[list["Recording"]] = relationship(  # noqa: F821
        back_populates="conversation", cascade="all, delete-orphan", order_by="Recording.round_number"
    )

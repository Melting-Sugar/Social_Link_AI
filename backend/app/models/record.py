import uuid
from datetime import date as date_type

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import Condition


class Record(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """§11.9 — the one thing that survives beyond a conversation's own
    lifecycle: kept until the user deletes it or the account (§2, §8)."""

    __tablename__ = "records"
    __table_args__ = (
        CheckConstraint(
            "mood_anxiety_score >= 0 AND mood_anxiety_score <= 10", name="ck_record_mood_range"
        ),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date_type] = mapped_column(nullable=False)
    condition: Mapped[Condition] = mapped_column(Enum(Condition, native_enum=False), nullable=False)
    mood_anxiety_score: Mapped[int] = mapped_column(Integer, nullable=False)
    next_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A-⑤ の内容（振り返り箇条書き）。将来的に §11.11 の「AI推定」方針の
    # 対象になる（§11.11 今後の適用範囲）。
    summary_bullets: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)

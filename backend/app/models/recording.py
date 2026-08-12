import uuid
from enum import StrEnum

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models.enums import RelationshipDistance, SuggestionCategory


class RecordingStatus(StrEnum):
    """Overall job status for the Celery analysis pipeline (§11.5)."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisStage(StrEnum):
    """UI満足度向上のための解析中進捗表示（2026-08-12ユーザー指示）。
    status=PROCESSINGの間、AnalysisService.run()が実際に通過する3段階と
    1:1で対応させる（frontendは(N/3)表示に変換、conversation/[id]/page.tsx
    参照）。"""

    ANALYZING_CONVERSATION = "analyzing_conversation"  # AmiVoice STT/話者分離/感情分析
    SEPARATING_SPEAKERS = "separating_speakers"  # 声紋照合による自分/相手の判別
    GENERATING_REPORT = "generating_report"  # Sonnet 5レポート生成


class Recording(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """§11.9. The `*_ready` flags implement the progressive-reveal polling
    design from §11.5/§11.6 — the frontend polls GET .../recordings/{rid}
    and shows each field as soon as its flag flips, instead of waiting for
    the whole pipeline. Deleted when its parent Conversation is deleted."""

    __tablename__ = "recordings"
    # 確定事項28: MVP向けに録音上限を30分(1800秒)から60秒へ短縮
    __table_args__ = (CheckConstraint("duration_sec <= 60", name="ck_recording_duration_max"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[RecordingStatus] = mapped_column(
        Enum(RecordingStatus, native_enum=False), nullable=False, default=RecordingStatus.PENDING
    )
    current_stage: Mapped[AnalysisStage | None] = mapped_column(
        Enum(AnalysisStage, native_enum=False), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 機能① の出力（§2, §11.1 A-④）。「会話の流れ」「相手の反応」「関係性の
    # 距離感」はAIの解釈が介在するため、断定調ではなく推定を示す文言で
    # 生成する（§11.11 出力文言の方針）。
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_ready: Mapped[bool] = mapped_column(default=False)
    flow: Mapped[str | None] = mapped_column(Text, nullable=True)
    flow_ready: Mapped[bool] = mapped_column(default=False)
    other_reaction: Mapped[str | None] = mapped_column(Text, nullable=True)
    reaction_ready: Mapped[bool] = mapped_column(default=False)
    relationship_distance: Mapped[RelationshipDistance | None] = mapped_column(
        Enum(RelationshipDistance, native_enum=False), nullable=True
    )
    relationship_ready: Mapped[bool] = mapped_column(default=False)
    suggestion_category: Mapped[SuggestionCategory | None] = mapped_column(
        Enum(SuggestionCategory, native_enum=False), nullable=True
    )
    suggestion_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggestion_ready: Mapped[bool] = mapped_column(default=False)

    # §11.5: file path in shared temp storage while a job is in flight; set
    # back to NULL once the worker deletes the file (§11.5 録音アップロードの
    # 受け渡し). Never a permanent audio store (§8).
    temp_audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="recordings")  # noqa: F821

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class PasswordResetToken(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """§11.2 確定: "署名付き・有効期限付き・使い切りの" reset token. A bare
    JWT can be signed and given an expiry, but nothing about a stateless
    JWT enforces single-use — this row is what makes the token unusable a
    second time (`used_at` set on redemption), the same way RefreshToken
    makes revocation possible. Not in the original §11.9 draft list; added
    here as the natural, necessary implementation of an already-confirmed
    requirement, same situation as RefreshToken."""

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

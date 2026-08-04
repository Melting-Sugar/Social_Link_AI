"""Import every model here so SQLAlchemy can resolve string-based forward
references between them (relationship() targets) and so Alembic's
autogenerate sees the full metadata."""

from app.models.base import Base
from app.models.conversation import Conversation
from app.models.password_reset_token import PasswordResetToken
from app.models.record import Record
from app.models.recording import Recording
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.models.voice_profile import VoiceProfile

__all__ = [
    "Base",
    "Conversation",
    "PasswordResetToken",
    "Record",
    "Recording",
    "RefreshToken",
    "User",
    "VoiceProfile",
]

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    email_verified: bool
    created_at: datetime

    @classmethod
    def from_model(cls, user) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            email_verified=user.email_verified_at is not None,
            created_at=user.created_at,
        )

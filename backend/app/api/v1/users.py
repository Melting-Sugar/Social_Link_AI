from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, DbSession
from app.core.config import get_settings
from app.schemas.auth import MessageResponse
from app.schemas.user import UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.from_model(current_user)


@router.delete("/me", response_model=MessageResponse)
async def delete_me(current_user: CurrentUser, session: DbSession, response: Response) -> MessageResponse:
    await UserService(session).delete_account(current_user)
    await session.commit()
    settings = get_settings()
    response.delete_cookie(key=settings.refresh_token_cookie_name, path="/", domain=settings.cookie_domain)
    return MessageResponse(message="アカウントを削除しました。")

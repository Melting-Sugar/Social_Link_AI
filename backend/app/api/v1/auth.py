from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.deps import DbSession
from app.core.config import get_settings
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotUsernameRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_refresh_cookie(response: Response, refresh_jwt: str, expires_at) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.refresh_token_cookie_name,
        value=refresh_jwt,
        httponly=True,
        secure=settings.environment == "prod",
        samesite="lax",
        expires=expires_at,
        # path="/" (not "/api/auth"): the frontend's proxy.ts (§11.4) needs
        # to see this cookie on every page request to decide whether to
        # redirect to /login — scoping it to only the auth endpoints would
        # make it invisible there. domain=None in dev (host-only, works
        # across localhost ports since cookies ignore port); set
        # COOKIE_DOMAIN in prod to the shared parent domain so it's visible
        # across the app./api. subdomains (§5).
        path="/",
        domain=settings.cookie_domain,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: DbSession, response: Response) -> TokenResponse:
    service = AuthService(session)
    try:
        user = await service.register(
            email=payload.email, username=payload.username, password=payload.password
        )
        access_token, refresh_jwt, expires_at = await service.issue_token_pair(user)
        await session.commit()
    except AuthError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    _set_refresh_cookie(response, refresh_jwt, expires_at)
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: DbSession, response: Response) -> TokenResponse:
    service = AuthService(session)
    try:
        user = await service.authenticate(identifier=payload.identifier, password=payload.password)
        access_token, refresh_jwt, expires_at = await service.issue_token_pair(user)
        await session.commit()
    except AuthError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    _set_refresh_cookie(response, refresh_jwt, expires_at)
    return TokenResponse(access_token=access_token)


def _cleared_cookie_headers() -> dict[str, str]:
    """A cookie-clearing Set-Cookie header, for attaching to an
    HTTPException via its `headers=` param. Note: mutating the endpoint's
    injected `Response` and then raising HTTPException does NOT work —
    FastAPI's exception handler builds an entirely new response and
    ignores it. Passing headers on the exception itself is the only
    reliable way to set a header on an error response."""
    settings = get_settings()
    temp = Response()
    temp.delete_cookie(key=settings.refresh_token_cookie_name, path="/", domain=settings.cookie_domain)
    return {"set-cookie": temp.headers["set-cookie"]}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, session: DbSession) -> TokenResponse:
    settings = get_settings()
    refresh_jwt = request.cookies.get(settings.refresh_token_cookie_name)
    if refresh_jwt is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ログインが必要です。")

    service = AuthService(session)
    try:
        access_token = await service.refresh_access_token(refresh_jwt)
    except AuthError as exc:
        # A stale/invalid cookie must be cleared here, not just rejected:
        # proxy.ts (§11.4) only checks whether the cookie is *present* to
        # decide whether a page is "logged in", not whether it's actually
        # valid. Without this, an expired/revoked refresh token leaves the
        # cookie sitting in the browser forever — every protected page
        # bounces the user to /login (this call fails client-side), but
        # /login itself immediately bounces back to / because proxy still
        # sees a cookie, trapping the user in a loop with no way to reach
        # the actual login form.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers=_cleared_cookie_headers(),
        ) from exc
    return TokenResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request, session: DbSession, response: Response) -> MessageResponse:
    settings = get_settings()
    refresh_jwt = request.cookies.get(settings.refresh_token_cookie_name)
    if refresh_jwt is not None:
        await AuthService(session).logout(refresh_jwt)
        await session.commit()
    response.delete_cookie(key=settings.refresh_token_cookie_name, path="/", domain=settings.cookie_domain)
    return MessageResponse(message="ログアウトしました。")


@router.post("/forgot-username", response_model=MessageResponse)
async def forgot_username(payload: ForgotUsernameRequest, session: DbSession) -> MessageResponse:
    # §11.2: identical response whether or not the email is registered.
    await AuthService(session).forgot_username(payload.email)
    await session.commit()
    return MessageResponse(message="一致するアカウントが存在すればユーザー名を送信しました。")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest, session: DbSession) -> MessageResponse:
    await AuthService(session).forgot_password(payload.email)
    await session.commit()
    return MessageResponse(message="一致するアカウントが存在すればパスワード再設定用のメールを送信しました。")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, session: DbSession) -> MessageResponse:
    service = AuthService(session)
    try:
        await service.reset_password(token=payload.token, new_password=payload.new_password)
        await session.commit()
    except AuthError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MessageResponse(message="パスワードを再設定しました。")

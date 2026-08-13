import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    TokenType,
    create_access_token,
    create_password_reset_token,
    create_refresh_jwt,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.integrations.email.resend_client import EmailClient
from app.models.user import User
from app.repositories.password_reset_token_repository import PasswordResetTokenRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised for any auth failure that should surface as an HTTP 400/401.
    Kept as one exception type — the API layer decides the status code,
    this layer just explains what went wrong (§6: services hold business
    logic, not HTTP concerns)."""


async def _send_best_effort(send: Callable[[], Awaitable[Any]], *, what: str) -> None:
    """Discovered in end-to-end testing (2026-08-04): a Resend outage/bad
    key made `send_registration_complete` raise, which — uncaught — failed
    the *entire* registration request even though the account had already
    been created. Every notification email in this service is a courtesy,
    never a precondition for the surrounding operation succeeding: log and
    move on rather than let an email-provider failure look like an auth
    failure to the caller (and, for forgot-username/forgot-password,
    propagating it would also have undermined §11.2's enumeration
    protection — a real account hitting an email failure must not look
    different from a nonexistent one)."""
    try:
        await send()
    except Exception:
        logger.exception("Non-critical email send failed: %s", what)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._refresh_tokens = RefreshTokenRepository(session)
        self._reset_tokens = PasswordResetTokenRepository(session)
        self._email = EmailClient()
        self._settings = get_settings()

    async def register(self, *, email: str, username: str, password: str) -> User:
        if await self._users.get_by_email(email) is not None:
            raise AuthError("このメールアドレスは既に登録されています。")
        if await self._users.get_by_username(username) is not None:
            raise AuthError("このユーザー名は既に使用されています。")
        try:
            user = await self._users.create(
                email=email, username=username, password_hash=hash_password(password)
            )
        except IntegrityError as exc:
            # 上のget_by_email/get_by_usernameチェックとこのINSERTの間に、
            # 同じメール/ユーザー名での別リクエストが割り込むレースは理論上
            # 起こりうる（極めて低頻度）。DBのUNIQUE制約自体は二重登録を
            # 正しく防ぐが、素のIntegrityError（→生の500エラー）として
            # 漏らさず、通常の重複時と同じ案内文言に倒す。
            raise AuthError("このメールアドレスまたはユーザー名は既に登録されています。") from exc
        await _send_best_effort(
            lambda: self._email.send_registration_complete(to_email=email, username=username),
            what="registration-complete",
        )
        return user

    async def authenticate(self, *, identifier: str, password: str) -> User:
        user = await self._users.get_by_email_or_username(identifier)
        # Deliberately identical error for "no such user" and "wrong
        # password" — distinguishing them would leak account existence.
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("メールアドレス（またはユーザー名）またはパスワードが正しくありません。")
        return user

    async def issue_token_pair(self, user: User) -> tuple[str, str, datetime]:
        """Returns (access_token, refresh_token_jwt, refresh_expires_at) —
        the caller (API layer) puts the access token in the response body
        and the refresh token in an httpOnly cookie (§5)."""
        access_token = create_access_token(str(user.id))
        expires_at = datetime.now(UTC) + timedelta(
            days=self._settings.refresh_token_expire_days
        )
        refresh_jwt = create_refresh_jwt(str(user.id), expires_at)
        await self._refresh_tokens.create(
            user_id=user.id, token_hash=hash_token(refresh_jwt), expires_at=expires_at
        )
        return access_token, refresh_jwt, expires_at

    async def refresh_access_token(self, refresh_jwt: str) -> str:
        try:
            payload = decode_token(refresh_jwt, TokenType.REFRESH)
        except jwt.PyJWTError as exc:
            raise AuthError("リフレッシュトークンが無効です。再度ログインしてください。") from exc

        stored = await self._refresh_tokens.get_valid_by_hash(hash_token(refresh_jwt))
        if stored is None:
            raise AuthError("リフレッシュトークンが無効です。再度ログインしてください。")
        return create_access_token(payload["sub"])

    async def logout(self, refresh_jwt: str) -> None:
        stored = await self._refresh_tokens.get_valid_by_hash(hash_token(refresh_jwt))
        if stored is not None:
            await self._refresh_tokens.revoke(stored)

    async def forgot_username(self, email: str) -> None:
        """§11.2: always succeeds from the caller's point of view — whether
        or not the email is registered is never revealed (enumeration
        protection)."""
        user = await self._users.get_by_email(email)
        if user is not None:
            await _send_best_effort(
                lambda: self._email.send_username_reminder(to_email=email, username=user.username),
                what="username-reminder",
            )

    async def forgot_password(self, email: str) -> None:
        user = await self._users.get_by_email(email)
        if user is None:
            return
        expires_at = datetime.now(UTC) + timedelta(
            hours=self._settings.password_reset_token_expire_hours
        )
        reset_jwt = create_password_reset_token(str(user.id), expires_at)
        await self._reset_tokens.create(
            user_id=user.id, token_hash=hash_token(reset_jwt), expires_at=expires_at
        )
        reset_url = f"{self._settings.frontend_base_url}/reset-password?token={reset_jwt}"
        await _send_best_effort(
            lambda: self._email.send_password_reset(to_email=email, reset_url=reset_url),
            what="password-reset",
        )

    async def reset_password(self, *, token: str, new_password: str) -> None:
        try:
            payload = decode_token(token, TokenType.PASSWORD_RESET)
        except jwt.PyJWTError as exc:
            raise AuthError("リンクの有効期限が切れているか、無効です。") from exc

        stored = await self._reset_tokens.get_valid_by_hash(hash_token(token))
        if stored is None:
            raise AuthError("リンクの有効期限が切れているか、無効です。")

        user = await self._users.get_by_id(uuid.UUID(payload["sub"]))
        if user is None:
            raise AuthError("リンクの有効期限が切れているか、無効です。")

        await self._users.update_password_hash(user, hash_password(new_password))
        # §11.2 確定 2026-08-04: first successful reset doubles as implicit
        # email verification.
        await self._users.mark_email_verified(user)
        await self._reset_tokens.mark_used(stored)
        # Password changed — invalidate every existing session, not just
        # the one that requested the reset.
        await self._refresh_tokens.revoke_all_for_user(user.id)

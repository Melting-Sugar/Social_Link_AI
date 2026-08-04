import hashlib
import re
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

# §5 / §10 確定事項16: Argon2id, OWASP's first-recommended password hash.
_hasher = PasswordHasher()

_HALFWIDTH_ALPHA = re.compile(r"[A-Za-z]")
_FULLWIDTH_ALPHA = re.compile(r"[Ａ-Ｚａ-ｚ]")
_DIGIT = re.compile(r"[0-9０-９]")
_SYMBOL = re.compile(
    r"[!-/:-@\[-`{-~　-〿！-／：-＠［-｀｛-･]"
)


def validate_password_strength(raw_password: str) -> None:
    """§11.2: 8+ chars, using 2+ of {half-width alpha, full-width alpha,
    digit, symbol}. Must run on the RAW (pre-NFKC) input — normalizing
    first would collapse full-width characters into their half-width
    equivalents, making that class undetectable. Raises ValueError with a
    user-facing Japanese message on failure."""
    if len(raw_password) < 8:
        raise ValueError("パスワードは8文字以上で入力してください。")
    classes_present = sum(
        bool(pattern.search(raw_password))
        for pattern in (_HALFWIDTH_ALPHA, _FULLWIDTH_ALPHA, _DIGIT, _SYMBOL)
    )
    if classes_present < 2:
        raise ValueError(
            "パスワードは、半角英字・全角英字・数字・記号のうち2種類以上を組み合わせてください。"
        )


def normalize_password(raw_password: str) -> str:
    """NFKC-normalize before hashing/verifying so full-width vs half-width
    variants of the same characters compare equal (§11.2)."""
    return unicodedata.normalize("NFKC", raw_password)


def hash_password(raw_password: str) -> str:
    return _hasher.hash(normalize_password(raw_password))


def verify_password(raw_password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, normalize_password(raw_password))
    except VerifyMismatchError:
        return False


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    PASSWORD_RESET = "password_reset"


def hash_token(token: str) -> str:
    """Deterministic hash for refresh/reset tokens — distinct from Argon2id
    password hashing, which is intentionally slow and salted and therefore
    unsuitable for exact-match DB lookups by hash."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": TokenType.ACCESS,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_jwt(user_id: str, expires_at: datetime) -> str:
    """The refresh Cookie's payload. Possession alone is not sufficient to
    use it — the caller must also look up the matching RefreshToken row
    (by hash) and confirm it is not revoked/expired (§5, §11.9).

    Includes a random `jti`: found via end-to-end testing that without one,
    two tokens issued for the same user within the same wall-clock second
    (e.g. register immediately followed by login) encode to the byte-
    identical JWT — HS256 signing is deterministic and `iat`/`exp` truncate
    to whole seconds — which then collided on RefreshToken.token_hash's
    unique constraint."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": TokenType.REFRESH,
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_password_reset_token(user_id: str, expires_at: datetime) -> str:
    """Same `jti` reasoning as create_refresh_jwt — PasswordResetToken.
    token_hash is also unique-constrained."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": TokenType.PASSWORD_RESET,
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Raises jwt.PyJWTError (or subclasses) on any invalid/expired/
    wrong-type token — callers should catch that broadly and translate to
    a 401."""
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"expected token type {expected_type!r}")
    return payload

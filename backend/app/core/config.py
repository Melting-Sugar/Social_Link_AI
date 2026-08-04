from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["dev", "prod"] = "dev"

    # Database / broker — §5
    database_url: str = "postgresql+asyncpg://social_link:social_link@localhost:5432/social_link"
    redis_url: str = "redis://localhost:6379/0"

    # Auth — §5, §11.2. JWT access token is short-lived; refresh token is the
    # long-lived, httpOnly-cookie-held one, checked against RefreshToken (DB).
    jwt_secret_key: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    refresh_token_cookie_name: str = "refresh_token"
    password_reset_token_expire_hours: int = 1

    # Used to build the password-reset link sent by email (§11.2).
    frontend_base_url: str = "http://localhost:3000"

    # None in dev: host-only cookie, works across localhost ports since
    # cookies ignore port in their matching rules. In prod, set to the
    # shared parent domain (e.g. ".example.com") so the refresh cookie is
    # visible across the frontend/backend subdomains (§5).
    cookie_domain: str | None = None

    # CORS — frontend/backend are separate origins (§5's subdomain note)
    cors_allowed_origins: list[str] = ["http://localhost:3000"]

    # External vendors
    anthropic_api_key: str = ""
    azure_speech_key: str = ""
    azure_speech_region: str = "japaneast"
    resend_api_key: str = ""
    email_from_address: str = "noreply@example.com"

    # §3.6 — prosody vendor is PoC-gated (next-steps #1); provider is
    # selected via env var so swapping candidates never touches call sites.
    prosody_provider: Literal["empath", "imentiv", "audeering", "none"] = "none"

    # §12.3 — speaker-ID model is PoC-gated (next-steps #2). "none" keeps the
    # base app runnable without the optional heavy PyTorch dependency group.
    speaker_id_provider: Literal["ecapa_local", "none"] = "none"

    # §4.2 — HybridPipeline is the recommended/default path; RealtimeOnly is
    # documented but not yet implemented (see integrations/llm).
    pipeline_mode: Literal["hybrid", "realtime_only"] = "hybrid"

    # §11.5 — shared local-disk handoff between the API process and Celery
    # workers for uploaded audio (personal-dev phase; §11.5 notes the future
    # upgrade path to object storage for horizontal scaling).
    temp_audio_dir: str = "/tmp/social-link-audio"

    # §11.3 / §3.4
    max_recording_seconds: int = 1800


@lru_cache
def get_settings() -> Settings:
    return Settings()

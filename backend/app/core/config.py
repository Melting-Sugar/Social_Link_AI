from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root, resolved from this file's own location rather than the
# process's cwd — the same class of bug found in frontend/lib/
# read-legal-doc.ts (cwd varies with how the process is launched; a
# path relative to __file__ doesn't).
_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# .env.keys (project root, gitignored): the single canonical file for
# every third-party vendor API key (Anthropic/Azure Speech/Resend) — see
# .env.keys.example and requirements-definition.md for why this lives
# outside backend/.env. Loaded first so backend/.env (app-level config:
# DB URL, JWT secret, CORS, ...) can still override in local dev if ever
# needed.
_ENV_KEYS_PATH = _PROJECT_ROOT / ".env.keys"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_ENV_KEYS_PATH, ".env"), env_file_encoding="utf-8", extra="ignore"
    )

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

    # External vendor API keys — values come from .env.keys (project root),
    # never from backend/.env (see _ENV_KEYS_PATH above).
    anthropic_api_key: str = ""
    azure_speech_key: str = ""
    azure_speech_region: str = "japaneast"
    resend_api_key: str = ""
    email_from_address: str = "noreply@example.com"
    # pyannote/embedding is gated on Hugging Face Hub — needed only for
    # SPEAKER_ID_PROVIDER=pyannote_local (§12.3 PoC candidate #2).
    hf_token: str = ""
    # 確定事項25-28 — AmiVoice ESAS採用に伴うSTTベンダー。
    amivoice_api_key: str = ""

    # §12.3 確定事項25 — AmiVoice ESASは音声認識と不可分なため既定はAmiVoice
    # (STT自体もAmiVoiceが兼ねる)。Azureは非アクティブ化した実装として残す。
    stt_provider: Literal["azure", "amivoice"] = "amivoice"

    # §3.6 確定事項27 — Empathは実データ検証の結果不採用。AmiVoice以外の
    # 単独プロソディベンダーは現状採用しておらず、STT_PROVIDER=amivoiceの
    # 場合はAnalysisServiceがSTTに同梱されたESASの結果を使うため、この設定
    # 自体が使われない（STT_PROVIDER=azureに戻した場合のみ有効になる）。
    prosody_provider: Literal["empath", "imentiv", "audeering", "none"] = "none"

    # §12.3 — speaker-ID model is PoC-gated (next-steps #2). "none" keeps the
    # base app runnable without the optional heavy PyTorch dependency group.
    speaker_id_provider: Literal["ecapa_local", "pyannote_local", "none"] = "none"

    # §4.2 — HybridPipeline is the recommended/default path; RealtimeOnly is
    # documented but not yet implemented (see integrations/llm).
    pipeline_mode: Literal["hybrid", "realtime_only"] = "hybrid"

    # §11.5 — shared local-disk handoff between the API process and Celery
    # workers for uploaded audio (personal-dev phase; §11.5 notes the future
    # upgrade path to object storage for horizontal scaling).
    temp_audio_dir: str = "/tmp/social-link-audio"

    # §11.3 / §3.4 — 確定事項28: MVPは60秒に制限（AmiVoiceの単発リクエスト
    # 処理時間がリアルタイム比1倍程度で安定している範囲に収める。録音中
    # チャンク並行投稿による長時間対応は次のステップ#1のベンダー確認待ち）
    max_recording_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()

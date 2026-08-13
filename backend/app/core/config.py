from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_DEFAULT_JWT_SECRET = "change-me-in-.env"

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
    jwt_secret_key: str = _INSECURE_DEFAULT_JWT_SECRET
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

    # §12 自分/相手の声紋照合の信頼度しきい値。best_similarityがこれ未満、
    # または2位候補との差がmin_margin未満なら識別失敗として扱う。値は
    # プレースホルダー — 合成音声でのPoC（0.88 vs 0.20）はあるが、実運用の
    # 生録音での検証はまだ行っていない。ユーザー自身の実音声での試用結果を
    # 踏まえて調整する想定（要件定義書参照）。
    speaker_id_min_similarity: float = 0.5
    speaker_id_min_margin: float = 0.15

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

    @model_validator(mode="after")
    def _reject_dev_defaults_in_prod(self) -> "Settings":
        # These fields all default to something that only makes sense on a
        # developer's own machine. Left unset in a real deployment, each
        # fails differently — some loudly (DATABASE_URL/REDIS_URL: nothing
        # is listening, connection refused at startup; CORS_ALLOWED_ORIGINS:
        # every request from the real frontend origin is browser-blocked,
        # obvious immediately) and some silently (FRONTEND_BASE_URL: the
        # app runs fine, but every password-reset email links to
        # http://localhost:3000 — dead for any real user, and nothing
        # anywhere surfaces that as an error). Reject all of them up front
        # in prod rather than let each one fail in its own confusing way
        # later. HS256 is a shared-secret signature — anyone holding the
        # exact JWT_SECRET_KEY string can forge a valid access token for
        # any user_id with no password needed, and the default is the
        # literal, publicly-visible string committed in this file.
        if self.environment != "prod":
            return self

        problems: list[str] = []
        if self.jwt_secret_key == _INSECURE_DEFAULT_JWT_SECRET:
            problems.append("JWT_SECRET_KEY is still the insecure default")
        if "localhost" in self.database_url:
            problems.append("DATABASE_URL still points at localhost")
        if "localhost" in self.redis_url:
            problems.append("REDIS_URL still points at localhost")
        if "localhost" in self.frontend_base_url:
            problems.append("FRONTEND_BASE_URL still points at localhost")
        if any("localhost" in origin for origin in self.cors_allowed_origins):
            problems.append("CORS_ALLOWED_ORIGINS still contains a localhost origin")
        if problems:
            raise ValueError(
                "Refusing to start with ENVIRONMENT=prod and dev-only settings: "
                + "; ".join(problems)
                + ". Set real values in .env before deploying."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

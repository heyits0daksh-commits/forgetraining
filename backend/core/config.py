"""
Central configuration for FORGE.

Every value that used to be hardcoded across main.py / app.py (data file paths,
host, port, CORS, API base URL) now lives here and can be overridden via a
.env file or real environment variables, without touching code.

Usage:
    from backend.core.config import settings
    settings.EXERCISES_JSON_PATH
"""
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = two levels up from this file (backend/core/config.py -> FORGE/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App metadata ---
    APP_NAME: str = "FORGE Engine - Knowledge Graph Prescription Engine"
    APP_VERSION: str = "5.0.0"
    DEBUG: bool = False
    # "development" (default) lets the app boot with the insecure default
    # SECRET_KEY, printing a warning only - the documented double-click/
    # zero-setup local workflow keeps working. Set ENVIRONMENT=production in
    # .env before exposing this to real users: main.py's startup hook then
    # hard-fails instead of warning if SECRET_KEY is still the default,
    # since a forgeable JWT signing key in production is a full account-
    # takeover vulnerability, not a "fix it later" warning.
    ENVIRONMENT: str = "development"
    # --- Logging (Phase 9) ---
    # Standard stdlib level name ("DEBUG"/"INFO"/"WARNING"/"ERROR"). See
    # backend/core/logging.py - every log line is JSON either way; this only
    # controls the floor of what gets emitted.
    LOG_LEVEL: str = "INFO"

    # --- Paths ---
    DATA_DIR: Path = DEFAULT_DATA_DIR
    EXERCISES_FILENAME: str = "exercises.json"
    # Directory holding the three FORGE S&C Template Libraries (grappling,
    # striking, MMA) - see backend/services/sc_template_library.py. Kept in
    # its own subdirectory rather than dropped loose in DATA_DIR since these
    # are three separate source files, not one growing database like
    # exercises.json.
    SC_TEMPLATES_DIR: Path = DEFAULT_DATA_DIR / "sc_templates"
    # Where the data-migration scripts (scripts/enrich_exercises.py,
    # generate_batch*_equipment.py) write their pre-migration snapshot before
    # touching exercises.json. Kept out of DATA_DIR itself so a fresh
    # `data/` listing isn't dominated by old snapshots (this is the setting
    # the README's "moved backups into data/backups/" bug fix note refers
    # to - previously the scripts had this path hardcoded to DATA_DIR
    # directly, so every re-run re-cluttered data/ instead).
    BACKUP_DIR: Path = DEFAULT_DATA_DIR / "backups"
    # SQLite file backing the adaptive-readiness / session-history feature
    # (backend/core/database.py, backend/models/db_models.py). Lives beside
    # exercises.json in DATA_DIR by default so a fresh checkout "just works"
    # with zero setup - override DATABASE_URL directly (any SQLAlchemy URL,
    # e.g. a real Postgres DSN) if you want persistence outside this repo.
    DATABASE_URL: str = ""

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            # Render/Heroku-style DSNs start with "postgres://", which
            # SQLAlchemy 2.x no longer accepts - it needs "postgresql://".
            if url.startswith("postgres://"):
                url = "postgresql://" + url[len("postgres://"):]
            return url
        return f"sqlite:///{self.DATA_DIR / 'forge.db'}"

    # --- Auth (Phase 6: persistent user profiles) ---
    # HMAC-signing key for JWT access tokens (backend/core/security.py). The
    # fallback below is fine for local dev only - anyone deploying this for
    # real users MUST set a real random SECRET_KEY via .env (e.g.
    # `python -c "import secrets; print(secrets.token_hex(32))"`), or every
    # token this app issues is forgeable by anyone who reads this source.
    SECRET_KEY: str = "dev-only-insecure-secret-change-me-via-env"
    JWT_ALGORITHM: str = "HS256"
    # The access token is the bearer credential sent on every request, so
    # it stays short-lived; the refresh token (below) is what keeps a user
    # signed in and it's only ever sent to the one /auth/refresh endpoint,
    # and is revocable (RefreshTokenDB) unlike a JWT, which can't be
    # un-issued before it naturally expires.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # 365 days, rotated on every use (auth_service.refresh_access_token
    # issues a fresh one each time and revokes the old) - so as long as the
    # frontend's silent-refresh flow (accounts.js) runs at least once a
    # year, the user effectively never has to log in again on that device.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 365
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # --- API server ---
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    # Off by default: autoreload is a dev convenience, not something that
    # should be silently on for anyone who runs `python -m backend.main`
    # without an explicit .env. Set API_RELOAD=true in .env for local dev.
    API_RELOAD: bool = False
    # "*" is deliberate here (not a placeholder) - the web UI is meant to be
    # opened directly as a local file (file://), which sends `Origin: null`,
    # so a fixed allowlist would break the documented double-click workflow.
    # This is safe specifically because allow_credentials is False below:
    # per the CORS spec, "*" + credentials is invalid anyway (browsers reject
    # it), and this app has no cookies/auth to leak. If you add auth, swap
    # this for an explicit origin list and turn allow_credentials back on.
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["*"])

    # --- Frontend (frontend/web/index.html) ---
    # The web UI computes its own API base in-browser (query param or same-
    # origin default) rather than reading this, but it's kept as the
    # documented default backend address for anyone scripting against the API.
    FRONTEND_API_BASE: str = "http://127.0.0.1:8000"
    METADATA_CACHE_TTL_SECONDS: int = 30

    # --- Future-AI-feature hooks (Phase 17) ---
    # Off by default - see backend/services/ai_hooks.py for the full design
    # note. Flipping this on today still has zero effect unless a key below
    # is also set; it exists so the setting itself doesn't need adding later
    # once a real provider exists.
    AI_FEATURES_ENABLED: bool = False
    # Real providers (Phase 17 second pass): only actually used when
    # AI_FEATURES_ENABLED is True AND one of the keys below is set -
    # get_insight_provider() falls back to the no-op provider otherwise, on
    # purpose (a missing key should never be a startup failure for a
    # feature this optional). get_insight_provider() picks Anthropic first
    # if ANTHROPIC_API_KEY is set, else NVIDIA if NVIDIA_API_KEY is set,
    # else the no-op provider - never commit a real key value here.
    #
    # Anthropic: key from https://console.anthropic.com/, put in .env.
    ANTHROPIC_API_KEY: Optional[str] = None
    AI_MODEL: str = "claude-sonnet-4-6"
    # NVIDIA NIM (OpenAI-compatible /chat/completions): free-tier key from
    # https://build.nvidia.com/, put in .env as NVIDIA_API_KEY. Default
    # model is a small, fast instruct model - plenty for a 2-3 sentence
    # note; swap NVIDIA_MODEL for a bigger one (e.g.
    # "meta/llama-3.1-70b-instruct") if you want richer notes and don't
    # mind the extra latency/cost.
    NVIDIA_API_KEY: Optional[str] = None
    NVIDIA_MODEL: str = "meta/llama-3.1-8b-instruct"
    AI_MAX_TOKENS: int = 220
    # Session generation already does real work (DAG walk over 731
    # exercises); the AI insight is decoration on top of an already-valid
    # response, so it gets a short budget and any failure (timeout
    # included) falls back to no insight rather than slowing down or
    # breaking the core request - see AnthropicInsightProvider's docstring.
    AI_TIMEOUT_SECONDS: float = 8.0

    # --- In-app exercise demo videos (Phase 18) ---
    # Free key from https://console.cloud.google.com/apis/credentials with
    # "YouTube Data API v3" enabled. Without it, /api/v1/exercises/{id}/video
    # just reports the feature as unconfigured - see backend/services/
    # video_lookup.py for which channel each exercise category resolves to.
    YOUTUBE_API_KEY: Optional[str] = None

    @property
    def EXERCISES_JSON_PATH(self) -> Path:
        return self.DATA_DIR / self.EXERCISES_FILENAME


# Single shared instance — import this everywhere instead of re-instantiating Settings().
settings = Settings()

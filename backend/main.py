"""FORGE FastAPI app entrypoint.

Phase 2 (docs/ROADMAP.md): this file previously bundled the
ProgressionEngine implementation AND all API routes in one 1697-line
file. It's now thin - app creation, CORS, the startup hook, and
mounting the routes - with the engine living in
backend/services/progression_engine.py and every endpoint in
backend/api/routes.py. No behavior, endpoint path, or route logic
changed in this split.

Phase 9/10 (this pass): structured logging (backend/core/logging.py) and
a consistent JSON error envelope for every error response
(backend/core/exceptions.py) are wired in here. The old `@app.on_event
("startup")` hook is now a `lifespan` context manager instead - same
behavior (init_db + the insecure-SECRET_KEY check still run exactly once
at boot), just without the deprecation warning `on_event` throws under
current FastAPI (see docs/ROADMAP.md's Phase 15 note).
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from backend.core.config import settings
from backend.core.database import init_db
from backend.core.exceptions import register_exception_handlers
from backend.core.logging import RequestIDMiddleware, configure_logging, get_logger
from backend.api.routes import router

configure_logging(settings.LOG_LEVEL)
logger = get_logger("startup")


def _check_secret_key() -> None:
    insecure_secret = settings.SECRET_KEY == "dev-only-insecure-secret-change-me-via-env"
    if insecure_secret and settings.ENVIRONMENT.lower() == "production":
        # Hard-fail, not a warning: ENVIRONMENT=production is an explicit
        # opt-in signal that this is reachable by real users, so booting
        # with a forgeable JWT signing key here is a full account-takeover
        # vulnerability, not a "fix it later" issue. Refuse to start.
        raise RuntimeError(
            "Refusing to start: ENVIRONMENT=production but SECRET_KEY is still "
            "the insecure default. Generate one with "
            "`python -c \"import secrets; print(secrets.token_hex(32))\"` and "
            "set it in .env before deploying."
        )
    elif insecure_secret:
        # Loud, not fatal: local/dev usage (the documented double-click
        # workflow) should keep working with zero setup, but anyone actually
        # exposing this to real users needs to see this before they do.
        logger.warning(
            "insecure_secret_key",
            extra={"hint": "set a real SECRET_KEY in .env before deploying"},
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creates data/forge.db (and its tables) on first run; no-op after that.
    # See backend/core/database.py - Phase 4 (session history / adaptive
    # readiness) and Phase 6 (users) share this one SQLite file.
    init_db()
    _check_secret_key()
    logger.info("forge_startup_complete", extra={"environment": settings.ENVIRONMENT})
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    # No cookies/auth headers are used anywhere in this app, so credentials
    # aren't needed - and "*" origins + allow_credentials=True is an invalid
    # combination per the CORS spec (browsers reject it outright). See
    # config.py's CORS_ORIGINS comment for why "*" itself is kept.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Registered after CORSMiddleware so it runs "closer to the app" (Starlette
# middleware executes in reverse-add order on the way in) - the request id
# needs to exist before any route or the CORS layer's own logic runs into
# an error, and the response header it adds should survive CORS' own
# header handling rather than being added first and then never seen again.
app.add_middleware(RequestIDMiddleware)

app.include_router(router)

# Serve the frontend (frontend/web) as static files at "/", so a single
# deployed service (e.g. one Render web service) hosts both the API
# (under /api/v1/...) and the UI at the same URL - no separate static
# host, no CORS setup, no second deployment needed. Mounted last so it
# never shadows the /api/v1/* routes above. html=True makes "/" serve
# index.html automatically.
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "web"
if _FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.API_RELOAD,
    )

"""Custom exception hierarchy + FastAPI exception handlers (Phase 10 of
docs/ROADMAP.md).

Before this pass, error handling was ad hoc: most 404/401/409s were raised
as bare `HTTPException(status_code=..., detail=...)` inline at the call
site, and the two generation endpoints each had their own hand-rolled
`except Exception` -> `print()` + 500 fallback (see backend/api/routes.py's
git history / ROADMAP for that shape). That worked but meant:

- no consistent error *shape* for API clients to parse (some errors were
  a bare string `detail`, nothing was structured)
- every unexpected-exception path had to remember, individually, to not
  leak internals when DEBUG is off
- no single place to log an error consistently before returning it

This module fixes that with:

1. A small `ForgeError` hierarchy (`NotFoundError`, `ConflictError`,
   `UnauthorizedError`, `BadRequestError`, `ValidationError`,
   `RateLimitedError`) - raise these instead of `HTTPException` in
   new/touched code. Existing `HTTPException` raises in routes.py still
   work unchanged (FastAPI handles those itself) - this is additive, not
   a forced rewrite of every call site. See ROADMAP.md's Phase 10 note
   for which call sites were migrated in this pass and which weren't.
2. `register_exception_handlers(app)` - wires both `ForgeError` and the
   fallback `Exception` case to always return the same JSON envelope:
       {"error": {"code": "...", "message": "...", "request_id": "..."}}
   `request_id` comes from `backend.core.logging`'s request-id middleware
   (falls back to null if the middleware isn't installed, so this module
   has no hard import-order dependency on it).
3. Every unhandled exception is logged via the structured logger
   (backend.core.logging.get_logger) with the request id attached *before*
   the generic response goes out - the old per-endpoint `print()` calls
   are gone; nothing is silently lost.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("forge.errors")


class ForgeError(Exception):
    """Base class for FORGE's own exception hierarchy. Carries everything
    needed to render a consistent JSON error response - subclasses just
    fix `status_code`/`code` and are raised with a human `message`.

    Not a replacement for FastAPI/Starlette's own `HTTPException` (which
    is still perfectly fine to raise directly, and is handled by FastAPI
    itself) - this exists for call sites that want a *named*, catchable
    error type (e.g. a service-layer function raising `NotFoundError`
    without importing FastAPI at all) rather than constructing an
    `HTTPException` inline.
    """

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self, message: str, *, code: Optional[str] = None, headers: Optional[dict[str, str]] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.headers = headers
        self.details = details
        if code is not None:
            self.code = code


class NotFoundError(ForgeError):
    status_code = 404
    code = "not_found"


class ConflictError(ForgeError):
    status_code = 409
    code = "conflict"


class UnauthorizedError(ForgeError):
    status_code = 401
    code = "unauthorized"


class BadRequestError(ForgeError):
    """A malformed/invalid request that isn't quite pydantic's own 422
    ValidationError shape - e.g. an expired one-time token, or (see
    program_builder.generate_program) an id that parses fine but doesn't
    name anything real. Same 400 status prior inline `HTTPException(400,
    ...)` call sites already used - this just gives them the same
    consistent `{"error": {...}}` envelope every other ForgeError gets."""
    status_code = 400
    code = "bad_request"


class ValidationError(ForgeError):
    status_code = 422
    code = "validation_error"


class RateLimitedError(ForgeError):
    status_code = 429
    code = "rate_limited"


class SevereInjuryBlockedError(ForgeError):
    """(v5.18) Raised by ProgressionEngine.generate_session before any
    exercise selection runs, when injury_taxonomy.resolve_severe_injuries
    finds a severity-3 injury among request.injuries - see that function's
    docstring for why this blocks the whole program, not just the affected
    joint. `details["blocked_injuries"]` carries the structured
    name/joint/clinical_red_flags list so a client can render the specific
    red flags, not just the flat message string."""
    status_code = 422
    code = "severe_injury_block"


def _request_id(request: Request) -> Optional[str]:
    # Set by backend.core.logging's RequestIDMiddleware. Looked up lazily
    # (via request.state) rather than imported, so this module works even
    # if that middleware is ever removed/reordered - the envelope just
    # carries request_id: null instead of failing to build.
    return getattr(request.state, "request_id", None)


def _error_envelope(*, code: str, message: str, request_id: Optional[str], details: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    envelope: dict[str, Any] = {"error": {"code": code, "message": message, "request_id": request_id}}
    if details:
        envelope["error"]["details"] = details
    return envelope


def register_exception_handlers(app: FastAPI) -> None:
    """Call once from main.py after `app = FastAPI(...)`. Registers:

    - ForgeError -> its own status_code/code/message, logged at WARNING
      (these are expected/handled error paths, e.g. a 404 - not a bug).
    - Exception (catch-all) -> always a 500 with a generic client-facing
      message (full exception logged server-side either way, and only
      echoed to the client when settings.DEBUG is on - mirrors the
      pre-existing per-endpoint behavior in generate-workout/
      generate-program, just centralized instead of duplicated).
    """
    # Imported here, not at module top, to avoid a circular import: config
    # doesn't depend on this module, but keeping the dependency one-directional
    # (this module -> config, never the reverse) is worth the small indirection.
    from backend.core.config import settings

    @app.exception_handler(ForgeError)
    async def _forge_error_handler(request: Request, exc: ForgeError) -> JSONResponse:
        rid = _request_id(request)
        logger.warning(
            "handled_error",
            extra={"forge_code": exc.code, "status_code": exc.status_code, "request_id": rid},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_envelope(code=exc.code, message=exc.message, request_id=rid, details=exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        rid = _request_id(request)
        # exc_info=True so the full traceback lands in the log even though
        # the client only ever gets a generic message by default.
        logger.error(
            "unhandled_error",
            exc_info=True,
            extra={"request_id": rid, "path": request.url.path},
        )
        message = str(exc) if settings.DEBUG else "Internal server error."
        return JSONResponse(
            status_code=500,
            content=_error_envelope(code="internal_error", message=message, request_id=rid),
        )

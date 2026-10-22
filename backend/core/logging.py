"""Structured logging (Phase 9 of docs/ROADMAP.md).

Before this pass there was no logging configuration at all - the only
signal on error was a handful of ad hoc `print(f"[generate-workout]
unhandled error: {e!r}")` calls in backend/api/routes.py, which don't carry
a timestamp, a level, or anything to correlate one request's log lines
together. This module fixes that:

- `configure_logging()` - call once at startup (main.py's lifespan). Sets
  up a single stdlib `logging` root handler that emits one JSON object per
  line to stdout - deliberately stdlib-only (no `structlog`/`python-json-
  logger` dependency added) since a working, greppable JSON-lines format is
  all this app needs and it keeps requirements.txt from growing for this.
  Every `logging.getLogger(...)` call anywhere in the app (including
  uvicorn's own loggers) goes through this formatter once configured.
- `RequestIDMiddleware` - assigns a short request id to every inbound
  request (reuses an inbound `X-Request-ID` header if the caller already
  set one, e.g. a load balancer or another service, so a trace can be
  correlated end-to-end instead of getting a new id at every hop), stores
  it on `request.state.request_id` (read by backend.core.exceptions'
  handlers so error responses carry it too), echoes it back as a response
  header, and logs one line per request with method/path/status/duration.
- `get_logger(name)` - thin wrapper so call sites don't need to remember
  the `"forge." + name` prefix convention.

Deliberately not done in this pass: shipping logs anywhere off-box (a real
deployment would want these JSON lines picked up by whatever log
aggregator it uses - CloudWatch, Datadog, etc. - which is an infra choice
outside this app's code, not a gap in it), and per-request log *sampling*
(every request logs today; fine at current traffic, worth revisiting only
if request-log volume itself ever becomes the bottleneck).
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

_RESERVED_LOG_RECORD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class _JSONFormatter(logging.Formatter):
    """Renders each log record as one JSON object per line. Any `extra=`
    kwargs passed to a logging call (e.g. `logger.info("x", extra={"foo":
    1})`) are merged straight into the object, so call sites don't need to
    pre-serialize anything themselves."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_LOG_RECORD_ATTRS and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Idempotent - safe to call more than once (e.g. once from main.py's
    lifespan and again from a test fixture); re-calling just replaces the
    root handler instead of stacking duplicate handlers, which would
    otherwise double- (or triple-) log every line."""
    root = logging.getLogger()
    root.setLevel(level)
    for existing in list(root.handlers):
        root.removeHandler(existing)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())
    root.addHandler(handler)
    # uvicorn's access logger is deliberately left alone / not silenced -
    # RequestIDMiddleware's own per-request line (below) is what carries the
    # request id, but uvicorn's line is still useful during local dev for
    # anyone tailing raw stdout without a JSON-aware viewer.


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"forge.{name}")


_access_logger = get_logger("access")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assigns/propagates a request id and logs one structured line per
    request. Installed in main.py via `app.add_middleware(RequestIDMiddleware)`
    - runs on every request, including ones that raise, so the access log
    line and the request id are both present even on a 500.
    """

    def __init__(self, app: ASGIApp, header_name: str = "X-Request-ID"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(self.header_name) or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            # Let backend.core.exceptions' catch-all handler build the actual
            # response - this middleware only needs to make sure the access
            # log line still gets written (with a 500) before re-raising.
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            _access_logger.error(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
                exc_info=True,
            )
            raise
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        response.headers[self.header_name] = request_id
        _access_logger.info(
            "request_handled",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response

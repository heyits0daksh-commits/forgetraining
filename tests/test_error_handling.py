"""Phase 9/10 (docs/ROADMAP.md): structured logging + custom exception
handling. These tests exercise the actual FastAPI app (same `client`
fixture the rest of the Phase 13 suite uses), plus the JSON formatter
directly with plain stdlib `logging` (no app needed for that part).
"""
import json
import logging

from backend.core.logging import _JSONFormatter


def test_unknown_sport_returns_structured_error_envelope(client):
    """A NotFoundError-raising endpoint (Phase 10 migration) should return
    the {"error": {"code", "message", "request_id"}} envelope, not a bare
    {"detail": ...} - and the request_id in the body should match the
    X-Request-ID response header set by RequestIDMiddleware."""
    r = client.get("/api/v1/sports/NotARealSport")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "not_found"
    assert "NotARealSport" in body["error"]["message"]
    assert body["error"]["request_id"] is not None
    assert r.headers["x-request-id"] == body["error"]["request_id"]


def test_duplicate_registration_returns_conflict_envelope(client, registered_user):
    """ConflictError (Phase 10 migration of the old 409 HTTPException in
    /auth/register) round-trips the same envelope shape."""
    r = client.post(
        "/api/v1/auth/register",
        json={"email": registered_user["email"], "password": "another-password", "accepted_terms": True},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


def test_every_response_carries_a_request_id_header(client):
    """RequestIDMiddleware should stamp X-Request-ID on every response,
    success or error, not just ones that go through the error handlers."""
    r = client.get("/api/v1/metadata")
    assert r.status_code == 200
    assert r.headers.get("x-request-id")


def test_incoming_request_id_is_echoed_back(client):
    """A caller-supplied X-Request-ID (e.g. from an upstream proxy) should
    be reused, not overwritten, so a trace can be correlated end-to-end."""
    r = client.get("/api/v1/metadata", headers={"X-Request-ID": "caller-supplied-id"})
    assert r.headers["x-request-id"] == "caller-supplied-id"


def test_refresh_with_garbage_token_returns_structured_error_envelope(client):
    """Auth-service pass follow-up: refresh_access_token used to raise a
    bare HTTPException with a {"detail": ...} body - migrated to
    UnauthorizedError so it gets the same {"error": {...}} envelope every
    other 401/404/409 in the app already carries."""
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"})
    assert r.status_code == 401
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["request_id"] is not None


def test_me_with_garbage_token_returns_structured_error_envelope_and_www_authenticate(client):
    """get_current_user's 401 also migrated - and its WWW-Authenticate
    header (required by the OAuth2 bearer spec) is preserved by ForgeError's
    new optional `headers` field, not silently dropped by the switch away
    from a raw HTTPException."""
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"
    assert r.headers.get("www-authenticate") == "Bearer"


def test_password_reset_confirm_with_bad_token_returns_bad_request_envelope(client):
    """confirm_password_reset's two 400s migrated to the new BadRequestError
    - same 400 status as the original inline HTTPException(400, ...), now
    with the {"error": {"code": "bad_request", ...}} envelope."""
    r = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": "not-a-real-token", "new_password": "a-new-password-123"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"


def test_json_formatter_emits_one_parseable_json_object_per_record():
    record = logging.LogRecord(
        name="forge.test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="something_happened", args=(), exc_info=None,
    )
    record.request_id = "abc123"
    line = _JSONFormatter().format(record)
    parsed = json.loads(line)
    assert parsed["message"] == "something_happened"
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "forge.test"
    assert parsed["request_id"] == "abc123"


def test_json_formatter_includes_traceback_on_exception():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        record = logging.LogRecord(
            name="forge.test", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="unhandled_error", args=(), exc_info=sys.exc_info(),
        )
    parsed = json.loads(_JSONFormatter().format(record))
    assert "ValueError: boom" in parsed["exception"]

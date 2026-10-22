"""
Auth lifecycle (Phase 6 + critical-gap pass): register -> login -> refresh
-> logout, and password-reset request/confirm. This exact flow is the one
ROADMAP.md has repeated in every pass since Phase 2 as "still needs the
real uvicorn smoke test" — this is that test, now runnable for real since
fastapi/sqlalchemy/pyjwt are actually installed.
"""
def test_register_returns_token_and_creates_usable_account(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "hunter2hunter2", "accepted_terms": True},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["health_data_consent_given"] is False


def test_register_without_accepting_terms_is_422(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "noterms@example.com", "password": "hunter2hunter2"},
    )
    assert r.status_code == 422


def test_register_with_accepted_terms_false_is_422(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "declined@example.com", "password": "hunter2hunter2", "accepted_terms": False},
    )
    assert r.status_code == 422


def test_saving_injuries_without_health_data_consent_is_400(client, registered_user):
    headers = {"Authorization": f"Bearer {registered_user['access_token']}"}
    r = client.put(
        "/api/v1/auth/me",
        json={"injuries": ["Rotator Cuff Tear"]},
        headers=headers,
    )
    assert r.status_code == 400


def test_saving_injuries_with_health_data_consent_succeeds_and_is_remembered(client, registered_user):
    headers = {"Authorization": f"Bearer {registered_user['access_token']}"}
    r = client.put(
        "/api/v1/auth/me",
        json={"injuries": ["Rotator Cuff Tear"], "health_data_consent": True},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["health_data_consent_given"] is True

    # A later save with a non-empty list doesn't need to re-send consent -
    # it's already on file.
    r2 = client.put(
        "/api/v1/auth/me",
        json={"injuries": ["Rotator Cuff Tear", "ACL Tear"]},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text


def test_clearing_injuries_never_requires_consent(client, registered_user):
    headers = {"Authorization": f"Bearer {registered_user['access_token']}"}
    r = client.put(
        "/api/v1/auth/me",
        json={"injuries": []},
        headers=headers,
    )
    assert r.status_code == 200, r.text


def test_delete_account_removes_account_and_revokes_access(client, registered_user):
    headers = {"Authorization": f"Bearer {registered_user['access_token']}"}
    r = client.delete("/api/v1/auth/me", headers=headers)
    assert r.status_code == 204

    # The account is gone - logging in again with the same credentials fails.
    r2 = client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert r2.status_code == 401


def test_delete_account_requires_auth(client):
    r = client.delete("/api/v1/auth/me")
    assert r.status_code == 401


def test_duplicate_email_registration_is_409(client, registered_user):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": registered_user["email"], "password": "different-pw-123", "accepted_terms": True},
    )
    assert r.status_code == 409


def test_password_too_short_is_422(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "short"},
    )
    assert r.status_code == 422


def test_login_with_correct_password(client, registered_user):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


def test_login_with_wrong_password_is_401(client, registered_user):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "totally-wrong-pw"},
    )
    assert r.status_code == 401


def test_login_unknown_email_is_401_not_500(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "whatever-pw-123"},
    )
    assert r.status_code == 401


def test_me_requires_auth(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_with_valid_token(client, registered_user, auth_headers):
    r = client.get("/api/v1/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == registered_user["email"]


def test_me_with_garbage_token_is_401_not_500(client):
    r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


def test_update_profile(client, auth_headers):
    r = client.put(
        "/api/v1/auth/me",
        headers=auth_headers,
        json={"primary_sport": "Boxing", "experience_level": "Intermediate"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["primary_sport"] == "Boxing"


def test_refresh_rotates_token_and_old_refresh_token_stops_working(client, registered_user):
    old_refresh = registered_user["refresh_token"]
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200, r.text
    new_body = r.json()
    assert new_body["access_token"]
    assert new_body["refresh_token"] != old_refresh

    # old refresh token was rotated out — reusing it must fail, not succeed.
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r2.status_code == 401


def test_refresh_with_garbage_token_is_401_not_500(client):
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"})
    assert r.status_code == 401


def test_logout_revokes_refresh_token(client, registered_user):
    refresh = registered_user["refresh_token"]
    r = client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    assert r.status_code == 204

    # revoked refresh token must no longer work for /auth/refresh.
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 401


def test_password_reset_request_is_always_generic(client, registered_user):
    """Must not leak whether an email has an account (enumeration guard)."""
    r_known = client.post(
        "/api/v1/auth/password-reset/request", json={"email": registered_user["email"]}
    )
    r_unknown = client.post(
        "/api/v1/auth/password-reset/request", json={"email": "nobody@example.com"}
    )
    assert r_known.status_code == 202
    assert r_unknown.status_code == 202
    assert r_known.json() == r_unknown.json()


def test_password_reset_confirm_with_bad_token_is_rejected(client):
    r = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": "not-a-real-token", "new_password": "brand-new-pw-123"},
    )
    assert r.status_code in (400, 401, 404)


def test_login_rate_limit_kicks_in(client, registered_user):
    """10/min per IP per the docstring in routes.py — the 11th attempt in
    the same minute must be throttled, not silently allowed through."""
    for _ in range(10):
        client.post(
            "/api/v1/auth/login",
            json={"email": registered_user["email"], "password": "wrong-pw-each-time"},
        )
    r = client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "wrong-pw-each-time"},
    )
    assert r.status_code == 429

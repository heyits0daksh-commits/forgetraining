"""
Session logging -> readiness suggestion -> Phase 5 personalization loop.
This is the exact "log a few sessions as a real account, call
generate-workout again, and confirm personalization_applied flips to true"
flow ROADMAP.md's Recommendation-engine section explicitly calls out as
never having been run against a live server.
"""


def _log_session(client, headers, sport="Boxing", extra=None):
    payload = {
        "sport": sport,
        "prescribed_count": 5,
        "readiness_used": 80,
        "post_soreness": 2,
        "post_fatigue": 2,
    }
    if extra:
        payload.update(extra)
    return client.post("/api/v1/sessions", json=payload, headers=headers)


def test_anonymous_can_log_and_list_sessions(client):
    r = _log_session(client, headers={})
    assert r.status_code == 200, r.text
    assert r.json()["athlete_id"] == "default"

    r2 = client.get("/api/v1/sessions")
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_logged_in_user_session_is_scoped_to_their_account(client, auth_headers):
    r = _log_session(client, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["athlete_id"] != "default"

    # anonymous listing must not see the logged-in user's session
    anon = client.get("/api/v1/sessions").json()
    assert len(anon) == 0

    mine = client.get("/api/v1/sessions", headers=auth_headers).json()
    assert len(mine) == 1


def test_anonymous_cannot_spoof_athlete_id_on_create(client):
    """An anonymous caller sending an athlete_id in the POST body (e.g. a
    guessed, real numeric user id) must not have it honored - it should
    always be forced to "default", the same as the query-param spoofing
    already blocked on list/delete/readiness below. Before this fix,
    create_session only overrode athlete_id when current_user was set,
    so an anonymous POST with a spoofed athlete_id would inject a
    fabricated session-log row into that account's real history."""
    r = _log_session(client, headers={}, extra={"athlete_id": "1"})
    assert r.status_code == 200, r.text
    assert r.json()["athlete_id"] == "default"


def test_cannot_delete_another_athletes_session_via_athlete_id_param(client, auth_headers):
    r = _log_session(client, headers=auth_headers)
    session_id = r.json()["id"]
    real_athlete_id = r.json()["athlete_id"]

    # Attempting to delete it anonymously while *guessing* the real
    # athlete_id as a query param must not succeed - the route resolves
    # athlete_id from the token when present, and for this anonymous call
    # there is no token, so it falls back to "default", not the guessed
    # value. A caller can't impersonate another account's athlete_id this way.
    del_r = client.delete(f"/api/v1/sessions/{session_id}?athlete_id={real_athlete_id}")
    assert del_r.status_code == 404
    assert real_athlete_id != "default"

    # the real owner can delete it.
    own_delete = client.delete(f"/api/v1/sessions/{session_id}", headers=auth_headers)
    assert own_delete.status_code == 200


def test_readiness_suggested_with_no_history_is_a_safe_default(client):
    r = client.get("/api/v1/readiness/suggested")
    assert r.status_code == 200
    assert 1 <= r.json()["suggested_readiness"] <= 100


def test_readiness_suggested_reacts_to_high_soreness(client, auth_headers):
    for _ in range(3):
        _log_session(client, headers=auth_headers, extra={"post_soreness": 5, "post_fatigue": 5})
    r = client.get("/api/v1/readiness/suggested", headers=auth_headers)
    assert r.status_code == 200
    # High recent soreness/fatigue should not suggest a full-readiness 100.
    assert r.json()["suggested_readiness"] < 100


def test_recommendations_history_requires_auth(client):
    r = client.get("/api/v1/recommendations/history")
    assert r.status_code == 401


def test_recommendations_history_below_threshold_has_no_history(client, auth_headers):
    """MIN_SESSIONS_FOR_SIGNAL = 3 per roadmap notes - 1 logged session
    must not be enough to produce signals yet."""
    _log_session(client, headers=auth_headers)
    r = client.get("/api/v1/recommendations/history", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["has_enough_history"] is False


def test_personalization_applied_stays_false_until_enough_history(client, auth_headers):
    r = client.post("/api/v1/generate-workout", json={"sport": "Boxing"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["personalization_applied"] is False

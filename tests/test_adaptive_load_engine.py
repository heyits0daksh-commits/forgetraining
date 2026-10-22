"""
compute_adaptive_load_adjustment (backend/services/recommendation_engine.py)
- the whole-session, history-driven volume/intensity nudge layered on top of
readiness_factor/deload_mode/_prescribe_volume inside generate_session.

Separate from test_sessions_and_readiness.py (which covers the pre-existing
per-exercise personalization_applied/history_signals loop) and from
test_rehab_stage_progression.py / test_tissue_demand_escalation.py (injury
safety, unrelated). This file exercises the new session-RPE-trend,
weekly-volume-spike, missed-session, and aggregate-plateau signals end to end
through the real /api/v1/sessions -> /api/v1/generate-workout loop.
"""
from datetime import datetime, timedelta, timezone


def _log(client, headers, *, days_ago, rpe=None, sport="Boxing", sets_per_exercise=0, post_soreness=2, post_fatigue=2):
    date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    log = []
    if sets_per_exercise:
        log = [{
            "exId": "jab_cross_001",
            "sets": [{"weight": 20, "reps": 10} for _ in range(sets_per_exercise)],
        }]
    payload = {
        "sport": sport,
        "date": date,
        "prescribed_count": 5,
        "readiness_used": 80,
        "post_soreness": post_soreness,
        "post_fatigue": post_fatigue,
        "log": log,
    }
    if rpe is not None:
        payload["rpe"] = rpe
    r = client.post("/api/v1/sessions", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_below_threshold_history_is_a_complete_noop(client, auth_headers):
    """3 logged sessions is enough for personalization_applied (threshold 3)
    but below MIN_SESSIONS_FOR_LOAD_ADJUSTMENT (4) - adaptive_training_load
    must stay inactive with both multipliers at 1.0."""
    for i in range(3):
        _log(client, auth_headers, days_ago=i, rpe=7)
    r = client.post("/api/v1/generate-workout", json={"sport": "Boxing"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    adaptive = r.json()["adaptive_training_load"]
    assert adaptive["active"] is False
    assert adaptive["volume_multiplier"] == 1.0
    assert adaptive["intensity_multiplier"] == 1.0
    assert adaptive["auto_deload_recommended"] is False


def test_anonymous_caller_gets_inactive_adaptive_load(client):
    r = client.post("/api/v1/generate-workout", json={"sport": "Boxing"})
    assert r.status_code == 200, r.text
    adaptive = r.json()["adaptive_training_load"]
    assert adaptive == {
        "active": False, "volume_multiplier": 1.0, "intensity_multiplier": 1.0,
        "auto_deload_recommended": False, "sessions_considered": 0, "reasons": [],
    }


def test_rising_session_rpe_backs_off_intensity_and_volume(client, auth_headers):
    """3 older sessions at RPE 6, 3 more recent sessions at RPE 8: a clear
    upward trend should trim both intensity_multiplier and volume_multiplier
    below 1.0, fold into readiness_factor, and explain itself."""
    for days_ago in (6, 5, 4):
        _log(client, auth_headers, days_ago=days_ago, rpe=6)
    for days_ago in (3, 2, 1):
        _log(client, auth_headers, days_ago=days_ago, rpe=8)

    r = client.post("/api/v1/generate-workout", json={"sport": "Boxing", "readiness": 80}, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    adaptive = body["adaptive_training_load"]
    assert adaptive["active"] is True
    assert adaptive["intensity_multiplier"] < 1.0
    assert adaptive["volume_multiplier"] < 1.0
    assert adaptive["auto_deload_recommended"] is False
    assert any("RPE" in reason for reason in adaptive["reasons"])
    # readiness_factor (80% baseline) must come back lower than 0.80 once
    # the intensity nudge is folded in.
    assert body["readiness_factor"] < 0.80


def test_very_high_recent_rpe_triggers_auto_deload(client, auth_headers):
    """Recent-window average RPE >= 8.5 should flip auto_deload_recommended
    and force deload_mode true even though the stated readiness (80) alone
    would not have triggered deload."""
    for days_ago in (6, 5, 4):
        _log(client, auth_headers, days_ago=days_ago, rpe=6.5)
    for days_ago in (3, 2, 1):
        _log(client, auth_headers, days_ago=days_ago, rpe=9.5)

    r = client.post("/api/v1/generate-workout", json={"sport": "Boxing", "readiness": 80}, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["adaptive_training_load"]["auto_deload_recommended"] is True
    assert body["deload_mode"] is True


def test_falling_rpe_with_headroom_nudges_intensity_up(client, auth_headers):
    """Effort trending down while still comfortably sub-max (recent avg <=
    6.5) should nudge intensity_multiplier above 1.0 - the mirror image of
    the rising-RPE case."""
    for days_ago in (6, 5, 4):
        _log(client, auth_headers, days_ago=days_ago, rpe=8)
    for days_ago in (3, 2, 1):
        _log(client, auth_headers, days_ago=days_ago, rpe=6)

    r = client.post("/api/v1/generate-workout", json={"sport": "Boxing", "readiness": 80}, headers=auth_headers)
    assert r.status_code == 200, r.text
    adaptive = r.json()["adaptive_training_load"]
    assert adaptive["intensity_multiplier"] > 1.0
    assert any("down" in reason for reason in adaptive["reasons"])


def test_weekly_volume_spike_caps_volume_multiplier(client, auth_headers):
    """Logged set volume more than 1.4x higher this week than last week
    should trip the acute:chronic spike check and cap volume_multiplier
    below 1.0, independent of RPE (no rpe logged on any of these)."""
    # "Last week" (8-13 days ago): light, 2 sets per session x 3 sessions = 6 sets.
    for days_ago in (13, 11, 9):
        _log(client, auth_headers, days_ago=days_ago, sets_per_exercise=2)
    # "This week" (0-6 days ago): heavy, 5 sets per session x 3 sessions = 15 sets.
    for days_ago in (5, 3, 1):
        _log(client, auth_headers, days_ago=days_ago, sets_per_exercise=5)

    r = client.post("/api/v1/generate-workout", json={"sport": "Boxing", "readiness": 80}, headers=auth_headers)
    assert r.status_code == 200, r.text
    adaptive = r.json()["adaptive_training_load"]
    assert adaptive["volume_multiplier"] < 1.0
    assert any("volume jumped" in reason for reason in adaptive["reasons"])


def test_returning_from_a_long_break_eases_back_in(client, auth_headers):
    """4 sessions logged in a tight recent cluster (small typical gap),
    then generating a new workout today - if the most recent logged
    session itself is old enough relative to the athlete's own typical
    cadence, both multipliers should ease down."""
    for days_ago in (40, 39, 38, 37):
        _log(client, auth_headers, days_ago=days_ago, rpe=6)

    r = client.post("/api/v1/generate-workout", json={"sport": "Boxing", "readiness": 80}, headers=auth_headers)
    assert r.status_code == 200, r.text
    adaptive = r.json()["adaptive_training_load"]
    assert adaptive["active"] is True
    assert adaptive["volume_multiplier"] < 1.0
    assert adaptive["intensity_multiplier"] < 1.0
    assert any("since your last logged session" in reason for reason in adaptive["reasons"])


def test_per_set_rpe_and_rir_are_read_when_session_level_rpe_is_absent(client, auth_headers):
    """When a session omits the top-level `rpe` field but the frontend
    logged per-set rpe/rir inline (a free-form pass-through field), the
    engine should still derive a usable session-effort number from those
    sets rather than treating the session as having no effort data at all."""
    def _log_with_set_effort(days_ago, set_values, key):
        date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        payload = {
            "sport": "Boxing",
            "date": date,
            "prescribed_count": 5,
            "post_soreness": 2,
            "post_fatigue": 2,
            "log": [{
                "exId": "jab_cross_001",
                "sets": [{"weight": 20, "reps": 10, key: v} for v in set_values],
            }],
        }
        r = client.post("/api/v1/sessions", json=payload, headers=auth_headers)
        assert r.status_code == 200, r.text

    # Prior window: per-set RPE ~6. Recent window: per-set RPE ~8.5 (via RIR=1.5 -> RPE 8.5).
    for days_ago in (6, 5, 4):
        _log_with_set_effort(days_ago, [6, 6, 6], "rpe")
    for days_ago in (3, 2, 1):
        _log_with_set_effort(days_ago, [1.5, 1.5, 1.5], "rir")

    r = client.post("/api/v1/generate-workout", json={"sport": "Boxing", "readiness": 80}, headers=auth_headers)
    assert r.status_code == 200, r.text
    adaptive = r.json()["adaptive_training_load"]
    assert adaptive["active"] is True
    assert adaptive["intensity_multiplier"] < 1.0


def test_generate_program_runs_without_error_with_history_and_fight_week_phase(client, auth_headers):
    """generate-program must call through to the same adaptive-load engine
    per day (not a duplicate implementation), threading training_phase and
    days_per_week down to it, without erroring or degrading the program."""
    for days_ago in (6, 5, 4):
        _log(client, auth_headers, days_ago=days_ago, rpe=8, sport="MMA")
    for days_ago in (3, 2, 1):
        _log(client, auth_headers, days_ago=days_ago, rpe=6, sport="MMA")

    r = client.post(
        "/api/v1/generate-program",
        json={
            "primary_goal": "General Fitness",
            "sport": "MMA",
            "days_per_week": 3,
            "weeks": 1,
            "training_phase": "Fight Week",
        },
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["program"]) == 1
    assert all(day["exercise_count"] > 0 for day in body["program"][0]["days"])


def test_fight_week_phase_caps_multipliers_at_baseline(client, auth_headers):
    """Direct unit-level check (not through the HTTP response shape, which
    doesn't surface adaptive_training_load per program day): the same
    falling-RPE-with-headroom history that pushes intensity_multiplier above
    1.0 in test_falling_rpe_with_headroom_nudges_intensity_up must be capped
    back to <=1.0 once training_phase='Fight Week' is passed in - a taper
    phase should never let this engine push harder than baseline."""
    for days_ago in (6, 5, 4):
        _log(client, auth_headers, days_ago=days_ago, rpe=8)
    for days_ago in (3, 2, 1):
        _log(client, auth_headers, days_ago=days_ago, rpe=6)

    from backend.core.database import SessionLocal
    from backend.services.recommendation_engine import compute_adaptive_load_adjustment

    # athlete_id: pull it off the one session we just logged, same way the
    # routes resolve it (str(current_user.id)).
    sessions = client.get("/api/v1/sessions", headers=auth_headers).json()
    athlete_id = sessions[0]["athlete_id"]

    db = SessionLocal()
    try:
        no_phase = compute_adaptive_load_adjustment(db, athlete_id, sport="Boxing")
        fight_week = compute_adaptive_load_adjustment(db, athlete_id, sport="Boxing", training_phase="Fight Week")
    finally:
        db.close()

    assert no_phase["intensity_multiplier"] > 1.0
    assert fight_week["intensity_multiplier"] <= 1.0
    assert fight_week["volume_multiplier"] <= 1.0


def test_forced_deload_caps_multipliers_at_baseline(client, auth_headers):
    """v5.35 - closes the 'four uncoordinated deload signals' gap: the same
    falling-RPE-with-headroom history that pushes intensity_multiplier above
    1.0 (see test_fight_week_phase_caps_multipliers_at_baseline right above)
    must be capped back to <=1.0 once forced_deload=True is passed in -
    identical treatment to Fight Week, for a session some other signal
    (readiness/soreness/a calendar deload week) already decided should be
    lighter, not harder."""
    for days_ago in (6, 5, 4):
        _log(client, auth_headers, days_ago=days_ago, rpe=8)
    for days_ago in (3, 2, 1):
        _log(client, auth_headers, days_ago=days_ago, rpe=6)

    from backend.core.database import SessionLocal
    from backend.services.recommendation_engine import compute_adaptive_load_adjustment

    sessions = client.get("/api/v1/sessions", headers=auth_headers).json()
    athlete_id = sessions[0]["athlete_id"]

    db = SessionLocal()
    try:
        not_forced = compute_adaptive_load_adjustment(db, athlete_id, sport="Boxing")
        forced = compute_adaptive_load_adjustment(db, athlete_id, sport="Boxing", forced_deload=True)
    finally:
        db.close()

    assert not_forced["intensity_multiplier"] > 1.0
    assert forced["intensity_multiplier"] <= 1.0
    assert forced["volume_multiplier"] <= 1.0
    # A bad-enough signal can still recommend easing FURTHER during an
    # already-forced-lighter session - forced_deload only ever stops it from
    # pushing harder than baseline, it doesn't disable the engine.
    assert forced["auto_deload_recommended"] == not_forced["auto_deload_recommended"]


def test_generate_session_low_readiness_prevents_adaptive_load_from_pushing_intensity_up(
    client, auth_headers,
):
    """End-to-end proof through the real generate-workout path (not just the
    unit-level check above): the exact falling-RPE history that would push
    readiness_factor UP via adaptive_load['intensity_multiplier'] must not do
    so once the request's own readiness is low enough to trigger deload_mode
    on its own - this is the actual bug (adaptive_load was computed before
    deload_mode existed, so it had no way to know) that forced_deload fixes."""
    for days_ago in (6, 5, 4):
        _log(client, auth_headers, days_ago=days_ago, rpe=8, sport="Boxing")
    for days_ago in (3, 2, 1):
        _log(client, auth_headers, days_ago=days_ago, rpe=6, sport="Boxing")

    r_normal = client.post(
        "/api/v1/generate-workout", json={"sport": "Boxing", "readiness": 80}, headers=auth_headers,
    )
    r_low_readiness = client.post(
        "/api/v1/generate-workout", json={"sport": "Boxing", "readiness": 20}, headers=auth_headers,
    )
    assert r_normal.status_code == 200, r_normal.text
    assert r_low_readiness.status_code == 200, r_low_readiness.text

    normal_adaptive = r_normal.json()["adaptive_training_load"]
    low_adaptive = r_low_readiness.json()["adaptive_training_load"]

    assert normal_adaptive["intensity_multiplier"] > 1.0
    assert low_adaptive["intensity_multiplier"] <= 1.0
    assert r_low_readiness.json()["deload_mode"] is True

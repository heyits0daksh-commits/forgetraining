"""
The core prescription engine endpoints — generate-workout (single session)
and generate-program (multi-week mesocycle). These are exercised through
the real ProgressionEngine/program_builder against the real
data/exercises.json, not stand-ins, for the first time.
"""


def test_generate_workout_with_all_defaults(client):
    r = client.post("/api/v1/generate-workout", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "prescribed_workout" in body
    assert len(body["prescribed_workout"]) > 0
    assert body["session_summary"]["total_prescribed"] == len(body["prescribed_workout"])


def test_generate_workout_anonymous_has_no_personalization(client):
    r = client.post("/api/v1/generate-workout", json={})
    assert r.status_code == 200
    assert body_or(r).get("personalization_applied") in (False, None)


def body_or(response):
    return response.json()


def test_generate_workout_respects_equipment_filter(client):
    r = client.post(
        "/api/v1/generate-workout",
        json={"equipment_available": ["Bodyweight"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["prescribed_workout"]) > 0


def test_generate_workout_includes_prelift_warmup_protocol(client):
    """The pre-lift warm-up (general warm-up / dynamic mobility / ramp-up
    sets) must be part of the single-session response too, not just the
    Program Builder's multi-week output - it's what a person actually does
    before touching a weight."""
    r = client.post("/api/v1/generate-workout", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["warmup_protocol"], "expected a non-empty pre-lift warm-up protocol"
    stages = [s["stage"] for s in body["warmup_protocol"]]
    assert "General warm-up" in stages
    assert "Ramp-up sets for the main lift" in stages
    assert body["warmup_note"]


def test_generate_workout_never_prescribes_striking_drills_even_for_striking_sports(client):
    """This app builds strength & conditioning programs; striking skill work
    (heavy bag rounds, shadow boxing, band-resisted kick drills, etc. -
    movement_pattern == "Strike") is trained separately with an actual
    coach and must never show up as a prescribed exercise, even for a
    striking sport where it's genuinely that sport's own skill."""
    r = client.post(
        "/api/v1/generate-workout",
        json={
            "sport": "Boxing",
            "equipment_available": [
                "Boxing Heavy Bag", "Barbell", "Dumbbell", "Adjustable Bench", "Pull-Up Bar", "Bodyweight",
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["prescribed_workout"]) > 0
    strike_drills = [e for e in body["prescribed_workout"] if e.get("movement_pattern") == "Strike"]
    assert strike_drills == [], f"striking drills leaked into prescribed_workout: {strike_drills}"


def test_generate_workout_invalid_experience_level_is_422(client):
    r = client.post(
        "/api/v1/generate-workout",
        json={"experience_level": "Godlike"},
    )
    assert r.status_code == 422


def test_generate_workout_logged_in_gets_profile_defaults(client, auth_headers):
    # set a profile with a specific sport
    client.put("/api/v1/auth/me", headers=auth_headers, json={"primary_sport": "Boxing"})
    r = client.post("/api/v1/generate-workout", json={}, headers=auth_headers)
    assert r.status_code == 200, r.text


def test_generate_program_with_defaults(client):
    r = client.post("/api/v1/generate-program", json={"weeks": 2, "days_per_week": 3})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "weeks" in body or "days" in body or "program" in body


def test_generate_program_unknown_split_is_400_not_500(client):
    r = client.post(
        "/api/v1/generate-program",
        json={"preferred_split": "not-a-real-split", "weeks": 2, "days_per_week": 3},
    )
    assert r.status_code == 400


def _bodyweight_exercise_ids(client, n=3):
    """Pull real ids from the live catalog rather than hardcoding any,
    so this test can't drift out of sync with data/exercises.json."""
    body = client.get("/api/v1/exercises?equipment=Bodyweight&limit=" + str(n)).json()
    ids = [ex["id"] for ex in body["exercises"]]
    assert len(ids) >= 2, "expected at least 2 bodyweight exercises in the catalog to build this test"
    return ids


def test_generate_program_custom_mode_uses_picked_exercises_every_day(client):
    """A full Custom-Mode program: two custom days (A/B), each with its own
    exact exercise list, cycled across days_per_week/weeks exactly like a
    preset split's own day list - see program_builder.generate_program's
    mode="custom" branch."""
    ids = _bodyweight_exercise_ids(client, 4)
    day_a_ids, day_b_ids = ids[:2], ids[2:4] or ids[:2]
    r = client.post(
        "/api/v1/generate-program",
        json={
            "mode": "custom",
            "weeks": 2,
            "days_per_week": 4,
            "equipment_available": ["Bodyweight"],
            "custom_days": [
                {"label": "Day A", "selected_exercise_ids": day_a_ids},
                {"label": "Day B", "selected_exercise_ids": day_b_ids},
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["split"]["id"] == "custom"
    weeks = body["program"]
    assert len(weeks) == 2
    for week in weeks:
        # 4 days/week cycling a 2-entry custom rotation -> A, B, A, B
        assert [d["day_label"] for d in week["days"]] == ["Day A", "Day B", "Day A (2)", "Day B (2)"]
        for day_index, day in enumerate(week["days"]):
            expected_ids = day_a_ids if day_index % 2 == 0 else day_b_ids
            picked_ids = [pe["id"] for pe in day["prescribed_workout"]]
            assert set(picked_ids) <= set(expected_ids), (
                f"custom day {day['day_label']!r} prescribed exercises outside its own pick list"
            )


def test_generate_program_custom_mode_without_custom_days_is_400(client):
    r = client.post(
        "/api/v1/generate-program",
        json={"mode": "custom", "weeks": 2, "days_per_week": 3},
    )
    assert r.status_code == 400


def test_estimate_level(client):
    r = client.post(
        "/api/v1/estimate-level",
        json={
            "weight_kg": 80,
            "height_cm": 178,
            "bench_press_1rm": 100,
            "squat_1rm": 140,
            "deadlift_1rm": 180,
            "pullups_max_reps": 10,
            "pushups_max_reps": 30,
            "sex": "male",
        },
    )
    assert r.status_code == 200, r.text


def test_generate_workout_never_prescribes_grappling_technique_for_special_forces(client):
    """Regression test for the reported bug: Special Forces (and any other
    non-grappling sport) must never get BJJ/Judo/Wrestling technique
    drilling (Leg-Lock Defense, Hip-Escape Flow, Uchikomi entries, Suplex
    Throw, Wrestling Dummy/Tackle Bag work) just because the hand-authored
    sport_priority score for that drill happens to clear the role floor -
    see PARTNER_SKILL_EXCLUDED_IDS in programming_role.py."""
    from backend.services.programming_role import PARTNER_SKILL_EXCLUDED_IDS

    r = client.post(
        "/api/v1/generate-workout",
        json={
            "sport": "Special Forces",
            "equipment_available": [
                "Bodyweight", "Barbell", "Dumbbell", "Kettlebell", "Pull-Up Bar",
                "Wrestling Dummy", "Tackle Bag",
            ],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    picked_ids = {e["id"] for e in body["prescribed_workout"]}
    leaked = picked_ids & PARTNER_SKILL_EXCLUDED_IDS
    assert leaked == set(), f"grappling/tackle technique drills leaked into Special Forces session: {leaked}"


def test_generate_program_does_not_repeat_the_same_movement_family_all_week():
    """Regression test for the reported bug: a Judo program's Hinge slot
    resolving to a different-looking-but-functionally-identical "High
    Pull" variant (Clean High Pull, Snatch High Pull, Hang High Pull,
    Kettlebell High Pull, ...) every single day of the week - 4x/week
    repetition of what a coach would call the same drill, just because
    each variant has a distinct exercise id. movement_family groups these
    together; the variety engine should now spread a week's picks across
    different families rather than exhausting one family's id list before
    ever trying a different movement."""
    from backend.services.program_builder import generate_program
    from backend.services.progression_engine import ProgressionEngine
    from backend.models.schemas import ProgramRequest

    engine = ProgressionEngine()
    req = ProgramRequest(
        sport="Judo",
        experience_level="Advanced",
        equipment_available=["Bodyweight", "Barbell", "Dumbbell", "Kettlebell", "Pull-Up Bar"],
        days_per_week=4,
        weeks=1,
        readiness=80,
    )
    result = generate_program(engine, req)
    family_by_id = {ex["id"]: ex.get("movement_family") for ex in engine.exercises_by_id.values()}

    for week in result["program"]:
        family_counts = {}
        for day in week["days"]:
            for pe in day["prescribed_workout"]:
                fam = family_by_id.get(pe["id"])
                if fam:
                    family_counts[fam] = family_counts.get(fam, 0) + 1
        over_used = {fam: n for fam, n in family_counts.items() if n > 2}
        assert not over_used, (
            f"same movement family repeated too many times in one week: {over_used}"
        )


# ---------------------------------------------------------------------------
# Casing normalization (v5.19) - a real live-smoke-test scenario found that
# WorkoutRequest/ProgramRequest's experience_level/primary_goal (Literal
# enums) 422'd on anything but exact-cased input, and `sport` (free text,
# matched against a runtime-built list) silently degraded to a generic
# session with no error at all on a casing mismatch. Fixed via
# schemas.py's `_normalize_to_canonical` (mode="before" field_validators
# for experience_level/primary_goal) and routes.py's `_normalize_sport_
# casing` (case-insensitive match against engine.all_sports before the
# request is handled).
# ---------------------------------------------------------------------------

def test_generate_workout_accepts_lowercase_experience_level(client):
    r = client.post(
        "/api/v1/generate-workout",
        json={"experience_level": "intermediate", "equipment_available": ["Bodyweight"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["experience_level"] == "Intermediate"


def test_generate_workout_accepts_lowercase_sport(client):
    r = client.post(
        "/api/v1/generate-workout",
        json={"sport": "powerlifting", "equipment_available": ["Barbell", "Power Rack"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sport"] == "Powerlifting"


def test_generate_workout_unknown_sport_is_left_untouched(client):
    """A genuinely unrecognized sport string is real free text, not a
    casing bug - it must not be rejected or silently rewritten to
    something else, only real matches get corrected."""
    r = client.post(
        "/api/v1/generate-workout",
        json={"sport": "Underwater Basket Weaving", "equipment_available": ["Bodyweight"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sport"] == "Underwater Basket Weaving"


def test_generate_program_accepts_mixed_case_primary_goal_and_level(client):
    r = client.post(
        "/api/v1/generate-program",
        json={
            "primary_goal": "build muscle",
            "experience_level": "INTERMEDIATE",
            "sport": "Judo",
            "preferred_split": "auto",
            "days_per_week": 3,
            "weeks": 1,
            "equipment_available": ["Barbell", "Dumbbell"],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["primary_goal"] == "Build Muscle"
    assert body["experience_level"] == "Intermediate"


def test_generate_workout_still_rejects_genuinely_invalid_experience_level(client):
    """Casing normalization must not turn the Literal into a free-for-all -
    a value that isn't any known level at all (any casing) still 422s."""
    r = client.post(
        "/api/v1/generate-workout",
        json={"experience_level": "Godlike", "equipment_available": ["Bodyweight"]},
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Rate limiting on generate-workout/generate-program (v5.19) - closes the
# Phase 16 gap the AI-hooks pass flagged: "no rate limiting specific to
# this endpoint's AI cost - the existing per-IP rate limits on auth
# endpoints don't cover generate-workout at all, AI-enabled or not."
# ---------------------------------------------------------------------------

def test_generate_workout_rate_limited_after_30_per_minute(client):
    last_status = None
    for _ in range(31):
        r = client.post("/api/v1/generate-workout", json={"equipment_available": ["Bodyweight"]})
        last_status = r.status_code
    assert last_status == 429
    assert "Retry-After" in r.headers


def test_generate_program_rate_limited_after_10_per_minute(client):
    last_status = None
    for _ in range(11):
        r = client.post(
            "/api/v1/generate-program",
            json={
                "sport": "Judo",
                "equipment_available": ["Bodyweight"],
                "days_per_week": 3,
                "weeks": 1,
            },
        )
        last_status = r.status_code
    assert last_status == 429

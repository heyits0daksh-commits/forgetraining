"""
volume_engine.py - weekly SET volume per muscle group, checked against
experience/goal-scaled landmarks. See that module's own docstring for the
design rationale (muscle-group collapsing, full/half-credit set counting,
LOOK_JACKED_LEVELS reuse).

Two layers, same split test_adaptive_load_engine.py/test_sessions_and_
readiness.py already use elsewhere in this suite:
  1. Unit-level tests against real `data/exercises.json` exercise entries
     (no FastAPI/DB needed) - fast, and pin down exact numbers.
  2. End-to-end tests through POST /api/v1/generate-program, confirming the
     real engine's output actually carries `weekly_volume` /
     `weekly_volume_summary` / `under_dosed_muscles` / `over_dosed_muscles`,
     not just that the standalone function works in isolation.
"""
import json
from pathlib import Path

from backend.services.volume_engine import (
    compute_weekly_muscle_sets,
    evaluate_weekly_volume,
    landmark_for,
)

_EXERCISES = json.load(open(Path(__file__).resolve().parent.parent / "data" / "exercises.json"))["exercises"]
_BY_ID = {e["id"]: e for e in _EXERCISES}


class _FakeEngine:
    exercises_by_id = _BY_ID


def _find(name_substr):
    for e in _EXERCISES:
        if name_substr.lower() in e["name"].lower():
            return e["id"]
    raise AssertionError(f"no exercise matching {name_substr!r} in data/exercises.json")


def test_primary_mover_gets_full_credit_secondary_gets_half():
    bench_id = _find("Flat Bench Press")
    bench = _BY_ID[bench_id]
    assert "Pectoralis Major" in bench["primary_muscles"]
    day_results = [{"prescribed_workout": [{"id": bench_id, "prescription": {"sets": 4}}]}]
    totals = compute_weekly_muscle_sets(_FakeEngine(), day_results)
    assert totals["Chest"] == 4.0
    for m in bench.get("secondary_muscles", []):
        group = {"Triceps Brachii": "Triceps", "Anterior Deltoid": "Shoulders"}.get(m, m)
        if group in totals:
            assert totals[group] == 2.0  # half credit


def test_sets_missing_or_zero_are_skipped_not_counted_as_zero_volume_bug():
    day_results = [{"prescribed_workout": [
        {"id": _find("Flat Bench Press"), "prescription": {}},  # no "sets" key
        {"id": _find("Back Squat"), "prescription": {"sets": 0}},  # zero sets
    ]}]
    totals = compute_weekly_muscle_sets(_FakeEngine(), day_results)
    assert totals == {}


def test_landmark_scales_down_for_non_hypertrophy_goals():
    build_muscle = landmark_for("Chest", "Intermediate", "Build Muscle")
    get_strong = landmark_for("Chest", "Intermediate", "Get Strong")
    conditioning = landmark_for("Chest", "Intermediate", "Conditioning")
    assert build_muscle == (14.0, 18.0)  # LOOK_JACKED_LEVELS Intermediate, unscaled (1.0x)
    assert get_strong[1] < build_muscle[1]
    assert conditioning[1] < get_strong[1]


def test_untracked_muscle_group_is_reported_but_not_flagged():
    landmark = landmark_for("Forearms", "Intermediate", "Build Muscle")
    assert landmark is None
    ev = evaluate_weekly_volume({"Forearms": 12.0}, "Intermediate", "Build Muscle")
    assert ev["Forearms"]["status"] == "not_tracked"
    assert ev["Forearms"]["target_range"] is None


def test_status_bands_under_optimal_high_excessive():
    # Beginner Chest landmark is 8-10 sets/week (LOOK_JACKED_LEVELS, 1.0x for Build Muscle).
    ev = evaluate_weekly_volume(
        {"Chest": 3.0}, "Beginner", "Build Muscle")
    assert ev["Chest"]["status"] == "under"
    ev = evaluate_weekly_volume({"Chest": 9.0}, "Beginner", "Build Muscle")
    assert ev["Chest"]["status"] == "optimal"
    ev = evaluate_weekly_volume({"Chest": 12.0}, "Beginner", "Build Muscle")
    assert ev["Chest"]["status"] == "high"
    ev = evaluate_weekly_volume({"Chest": 20.0}, "Beginner", "Build Muscle")
    assert ev["Chest"]["status"] == "excessive"


def test_landmark_tracked_muscle_never_trained_still_shows_up_as_under():
    # A leg-day-only week - Chest never appears in weekly_sets at all.
    ev = evaluate_weekly_volume({"Quads": 12.0}, "Intermediate", "Build Muscle")
    assert "Chest" in ev
    assert ev["Chest"]["weekly_sets"] == 0
    assert ev["Chest"]["status"] == "under"


# ---------------------------------------------------------------------------
# End-to-end, through the real API. Same standing caveat as every other pass
# noted in docs/ROADMAP.md: this sandbox has no network access to install
# fastapi/pydantic, so these were written to the same contract as the rest
# of tests/test_generation_endpoints.py but NOT executed here - run
# `pytest tests/test_volume_engine.py -q` once network access exists.
# ---------------------------------------------------------------------------

def test_generate_program_response_carries_weekly_volume_per_week(client):
    r = client.post("/api/v1/generate-program", json={
        "weeks": 2, "days_per_week": 4, "primary_goal": "Build Muscle", "experience_level": "Intermediate",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "weekly_volume_summary" in body
    for week in body["program"]:
        assert "weekly_volume" in week
        for muscle, info in week["weekly_volume"].items():
            assert "weekly_sets" in info and "status" in info


def test_generate_program_flags_under_dosed_muscles_on_a_short_program(client):
    # 1 day/week, 1 week - not enough total sets for any muscle to hit even
    # a scaled-down landmark, so under_dosed_muscles should be non-empty.
    r = client.post("/api/v1/generate-program", json={
        "weeks": 1, "days_per_week": 1, "primary_goal": "Build Muscle", "experience_level": "Intermediate",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["under_dosed_muscles"]


def test_generate_program_goal_changes_the_target_range_not_just_the_verdict(client):
    payload_base = {"weeks": 1, "days_per_week": 4, "experience_level": "Intermediate"}
    r_hyp = client.post("/api/v1/generate-program", json={**payload_base, "primary_goal": "Build Muscle"})
    r_str = client.post("/api/v1/generate-program", json={**payload_base, "primary_goal": "Get Strong"})
    assert r_hyp.status_code == 200 and r_str.status_code == 200
    chest_hyp = r_hyp.json()["weekly_volume_summary"].get("Chest", {}).get("target_range")
    chest_str = r_str.json()["weekly_volume_summary"].get("Chest", {}).get("target_range")
    if chest_hyp and chest_str:
        assert chest_str["high"] < chest_hyp["high"]

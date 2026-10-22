"""
Regression test (v5.17 data fix): every exercise that requires a sustained
flexed-wrist grip to perform - hanging/pulling from a bar, rings, or
hangboard, or a heavy strongman-style grip carry/hold - must carry 'Wrist'
in joint_stress.

Before this fix, exercises like Chin-Up, Wide-Grip Pull-Up, Weighted
Pull-Up, and Farmer Handles Carry had no 'Wrist' tag, so the injury-safety
engine (which only screens an exercise against a joint it actually lists in
joint_stress) never excluded them for a person with a wrist injury - e.g.
someone with a wrist flexor tendon injury above that joint's difficulty
ceiling was still being prescribed Wide-Grip Pull-Up or heavier Farmer
Handles work.
"""
import json

from backend.core.config import settings


GRIP_HANG_EQUIPMENT = {"Pull-up Bar", "Rings", "Climbing Hangboard", "Climbing Hold / Hangboard"}
HEAVY_GRIP_EQUIPMENT = {"Conan's Wheel", "Fingal's Fingers", "Farmer Handles"}


def _load_exercises():
    with open(settings.EXERCISES_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["exercises"]


def test_hang_and_heavy_grip_exercises_are_tagged_wrist():
    exercises = _load_exercises()
    missing = [
        e["name"]
        for e in exercises
        if e.get("equipment") in (GRIP_HANG_EQUIPMENT | HEAVY_GRIP_EQUIPMENT)
        and "Wrist" not in e.get("joint_stress", [])
    ]
    assert missing == [], f"Grip/hang exercises missing the 'Wrist' joint_stress tag: {missing}"


def test_wrist_flexor_tendon_partial_tear_excludes_higher_difficulty_wrist_work(client=None):
    """End-to-end: a wrist injury must exclude the exact family of exercises
    that motivated this fix (Chin-Up, Wide-Grip/Weighted Pull-Up, Farmer
    Handles work), via the real generate-workout endpoint.

    Uses the severity-2 (Partial Tear) grade rather than the original
    severity-3 (Complete Rupture) grade this test was written against: the
    v5.18 whole-program severe-injury gate (see test_severe_injury_block.py)
    now deliberately blocks generation entirely for any severity-3 injury
    before exercise selection ever runs, which is correct at that severity
    but means a 200 with per-exercise exclusions is no longer reachable
    there. Severity 2's difficulty ceiling is 2 (SEVERITY_DIFFICULTY_CEILING
    in injury_taxonomy.py), so this asserts the general form of the same
    guarantee: no prescribed exercise both stresses the Wrist *and* exceeds
    that ceiling - covering Wide-Grip Pull-Up, Weighted Pull-Up, and the
    heavier Farmer Handles variants from the family this fix tagged."""
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)
    payload = {
        "mode": "preset",
        "sport": "Special Forces",
        "experience_level": "Intermediate",
        "equipment_available": [
            "Bodyweight", "Barbell", "Dumbbell", "Kettlebell",
            "Cable Machine", "Pull-up Bar", "Rings", "Farmer Handles",
        ],
        "injuries": ["Wrist Flexor Tendons - Partial Tear"],
    }
    r = client.post("/api/v1/generate-workout", json=payload)
    assert r.status_code == 200
    data = r.json()

    exercises = _load_exercises()
    by_id = {e["id"]: e for e in exercises}
    for item in data["prescribed_workout"]:
        ex = by_id.get(item["id"], {})
        joint_stress = ex.get("joint_stress", [])
        if "Wrist" in joint_stress:
            assert ex.get("difficulty", 1) <= 2, (
                f"{item['name']} stresses Wrist at difficulty "
                f"{ex.get('difficulty')} (exceeds the severity-2 ceiling of "
                "2) but was prescribed for a wrist injury"
            )

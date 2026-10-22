"""
Regression tests for two prescription bugs reported against real usage:
"kettlebell swing and many more exercises" getting wrong reps/sets, and
that going wrong specifically "if a person chooses a goal".

Bug 1 (progression_engine.py ordering): several Kettlebell Hinge-category
movements (One-Handed Swing, Kettlebell Deadlift, Kettlebell High Pull,
Kettlebell Romanian Deadlift) have a 0.0 deadlift_ratio in exercises.json -
same as a genuine isolation accessory's ratio. Because the isolation check
ran before the kettlebell-ballistic check, these exercises were silently
routed into the generic isolation branch (no working weight at all, plain
10-20 rep prescription) instead of the moderate-load/higher-rep kettlebell
prescription that branch exists to give them - even though Russian
Kettlebell Swing (ratio 0.5, same movement family) got it correctly.

Bug 2 (program_builder.py goal remap): _apply_prescription_bias remaps any
type=="strength"/"strength_bodyweight" prescription onto the selected
goal's Power/Strength/Hypertrophy window. Kettlebell ballistic work (type
"strength") and dynamic Core/Grip work (type "strength_bodyweight") share
those types with genuine barbell lifts and weighted bodyweight skills, so
choosing ANY goal (Get Strong, Power, Build Muscle, ...) was collapsing a
Kettlebell Swing into a low-rep near-max barbell-style prescription, and a
Hanging Knee Raise into the same. Fixed with explicit "ballistic"/
"accessory" flags that _apply_prescription_bias now checks and skips.
"""
import json
from pathlib import Path

from backend.services.progression_engine import ProgressionEngine
from backend.services.program_builder import _apply_prescription_bias, GOAL_PROFILES

_EXERCISES = json.load(open(Path(__file__).resolve().parent.parent / "data" / "exercises.json"))["exercises"]
_BY_ID = {e["id"]: e for e in _EXERCISES}

_ALL_GOALS = list(GOAL_PROFILES.keys())


def _prescribe(exercise_id, goal=None):
    data = _BY_ID[exercise_id]
    base = ProgressionEngine._prescribe_volume_core(data, readiness_factor=1.0, deload=False)
    profile = GOAL_PROFILES.get(goal, GOAL_PROFILES["General Fitness"])
    return _apply_prescription_bias(dict(base), None, profile)


# --- Bug 1: every KB Hinge movement reaches the kettlebell branch, not isolation ---

def test_one_handed_kb_swing_gets_kettlebell_prescription_not_isolation():
    presc = _prescribe("kb_swing_1h_001")
    assert presc["type"] == "strength"
    assert presc.get("ballistic") is True
    assert presc.get("load_pct_1rm") is not None
    assert 8 <= presc["reps"] <= 20


def test_kb_deadlift_and_kb_rdl_and_kb_high_pull_get_real_prescriptions():
    for ex_id in ("kb_deadlift_001", "kettlebell_rdl_001", "kb_high_pull_001"):
        presc = _prescribe(ex_id)
        assert presc["type"] == "strength", ex_id
        assert presc.get("ballistic") is True, ex_id
        assert presc.get("load_pct_1rm") is not None, ex_id


def test_russian_kb_swing_still_gets_kettlebell_prescription():
    # This one already had a nonzero ratio and worked before the fix -
    # confirms the reorder didn't regress the already-working case.
    presc = _prescribe("kb_swing_001")
    assert presc["type"] == "strength"
    assert presc.get("ballistic") is True
    assert 20 <= presc["load_pct_1rm"] <= 60


# --- Bug 2: goal selection must not corrupt kettlebell/core prescriptions ---

def test_kb_swing_prescription_is_goal_invariant_and_stays_ballistic_ranged():
    for goal in _ALL_GOALS + [None]:
        presc = _prescribe("kb_swing_001", goal)
        assert presc["type"] == "strength"
        # Never collapsed into a barbell-style near-max low-rep prescription.
        assert presc["reps"] >= 8, f"goal={goal} collapsed KB swing reps to {presc['reps']}"
        assert presc["load_pct_1rm"] <= 60, f"goal={goal} pushed KB swing load to {presc['load_pct_1rm']}%"
        assert presc["sets"] <= 4


def test_core_grip_dynamic_work_is_goal_invariant():
    core_id = next(e["id"] for e in _EXERCISES if "hanging knee raise" in e["name"].lower())
    for goal in _ALL_GOALS + [None]:
        presc = _prescribe(core_id, goal)
        assert presc["type"] == "strength_bodyweight"
        assert presc.get("accessory") is True
        # Never collapsed into a 1-6 rep barbell-skill-style prescription.
        assert presc["reps"] >= 8, f"goal={goal} collapsed core reps to {presc['reps']}"


def test_genuine_barbell_strength_lift_still_remaps_by_goal():
    # Sanity check the fix is scoped correctly: a real loaded barbell lift
    # (not flagged ballistic/accessory) must still respond to goal selection -
    # this is existing, intended behavior and must not be broken.
    squat_id = "bb_back_squat_001"
    strength_presc = _prescribe(squat_id, "Get Strong")
    power_presc = _prescribe(squat_id, "Power / Explosiveness")
    hypertrophy_presc = _prescribe(squat_id, "Build Muscle")
    assert strength_presc["reps"] != hypertrophy_presc["reps"]
    assert power_presc["reps"] <= strength_presc["reps"] <= hypertrophy_presc["reps"]

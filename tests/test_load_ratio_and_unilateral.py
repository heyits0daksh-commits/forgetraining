"""
Unit tests for backend/services/load_prescription.add_working_weight's two
new inputs (FORGE spec 1.2):

  1. `strength_requirements` - lets an exercise override the flat
     per-category ratio (_ANCHOR_BY_CATEGORY) with its own
     {bench,squat,deadlift}_ratio, so e.g. Good Morning and Sumo Deadlift -
     both "Hinge" - no longer get identical load prescriptions.
  2. `movement_type` - applies a unilateral-loading discount (global bridge
     default, overridable via strength_requirements.unilateral_adjustment_
     factor) to single-arm/single-leg barbell or machine exercises, without
     stacking on top of an exercise ratio that's already been hand-tuned.

These are pure-function tests against load_prescription directly (no
FastAPI client needed) - fast, and isolate the math from the rest of the
prescription pipeline (progression_engine's difficulty/readiness formula,
program_builder's bias remapping, etc), which are already covered
elsewhere.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.load_prescription import add_working_weight


class _Bio:
    """Minimal stand-in for schemas.UserBiometrics - only the fields
    add_working_weight actually reads."""
    def __init__(self, deadlift_1rm=180.0, squat_1rm=150.0, bench_press_1rm=120.0,
                 weight_kg=80.0, pullups_max_reps=0):
        self.deadlift_1rm = deadlift_1rm
        self.squat_1rm = squat_1rm
        self.bench_press_1rm = bench_press_1rm
        self.weight_kg = weight_kg
        self.pullups_max_reps = pullups_max_reps


def _prescription(pct=70):
    return {"type": "strength", "load_pct_1rm": pct, "sets": 4, "reps": 6, "rest_seconds": 120}


# --- Section 1: per-exercise load ratio ------------------------------------

def test_good_morning_and_sumo_deadlift_no_longer_match():
    """The exact bug the spec calls out: two 'Hinge' exercises with very
    different real intensity used to get the same working weight because
    the category ratio (1.00) was applied to both regardless of the
    exercise's own strength_requirements ratio."""
    bio = _Bio(deadlift_1rm=180.0)
    good_morning_sr = {"bench_ratio": 0.0, "squat_ratio": 0.5, "deadlift_ratio": 0.4}
    sumo_deadlift_sr = {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.9}

    gm = add_working_weight(_prescription(), "Hinge", bio, equipment="Barbell",
                             strength_requirements=good_morning_sr, movement_type="Bilateral")
    sd = add_working_weight(_prescription(), "Hinge", bio, equipment="Barbell",
                             strength_requirements=sumo_deadlift_sr, movement_type="Bilateral")

    assert gm["working_weight_kg"] < sd["working_weight_kg"]
    # 180 * 0.4 * 0.70 = 50.4 -> nearest 2.5kg plate increment
    assert gm["working_weight_kg"] == 50.0
    # 180 * 0.9 * 0.70 = 113.4 -> nearest 2.5kg plate increment
    assert sd["working_weight_kg"] == 112.5


def test_unmigrated_exercise_falls_back_to_category_default():
    """No strength_requirements at all (or a ratio of 0/missing) must
    behave exactly like before this feature existed - the incremental-
    migration guarantee from the spec."""
    bio = _Bio(deadlift_1rm=180.0)
    result_no_reqs = add_working_weight(_prescription(), "Hinge", bio, equipment="Barbell")
    result_zero_ratio = add_working_weight(
        _prescription(), "Hinge", bio, equipment="Barbell",
        strength_requirements={"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0},
    )
    # Hinge's category default ratio is 1.00 ("direct" match) -> 180 * 0.70 = 126 -> 125.0
    assert result_no_reqs["working_weight_kg"] == 125.0
    assert result_zero_ratio["working_weight_kg"] == 125.0
    assert result_no_reqs["weight_confidence"] == "direct"
    assert result_no_reqs.get("weight_note") is None


def test_exercise_ratio_overrides_a_nonzero_category_default_too():
    """Horizontal Pull's category default (0.55) is itself just a
    typical-row estimate - an exercise with its own calibrated ratio
    (Pendlay Row: 0.6) should use that instead, not the generic figure."""
    bio = _Bio(deadlift_1rm=180.0)
    pendlay_sr = {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.6}
    result = add_working_weight(_prescription(pct=70), "Horizontal Pull", bio, equipment="Barbell",
                                 strength_requirements=pendlay_sr, movement_type="Bilateral")
    # 180 * 0.6 * 0.70 = 75.6 -> 75.0, NOT the category-default 180*0.55*0.70=69.3->70.0
    assert result["working_weight_kg"] == 75.0
    assert "specific exercise" in result["weight_note"]


# --- Section 2: unilateral load adjustment ----------------------------------

def test_unilateral_barbell_exercise_with_own_ratio_is_not_double_discounted():
    """Single Arm Barbell Row already carries a hand-calibrated
    deadlift_ratio (0.45, well below Pendlay Row's 0.6) - the global
    unilateral bridge factor must NOT also apply on top of it."""
    bio = _Bio(deadlift_1rm=180.0)
    sr = {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.45}
    result = add_working_weight(_prescription(pct=70), "Horizontal Pull", bio, equipment="Barbell",
                                 strength_requirements=sr, movement_type="Unilateral")
    # 180 * 0.45 * 0.70 = 56.7 -> 57.5, no extra 0.55 stacked on top
    assert result["working_weight_kg"] == 57.5
    assert "adjusted for single-arm" not in (result.get("weight_note") or "")


def test_unilateral_barbell_exercise_without_ratio_gets_bridge_factor():
    """An uncalibrated unilateral barbell/machine exercise (no
    exercise-specific ratio yet) should fall back to category default *
    the global unilateral bridge factor, with the adjustment surfaced in
    weight_note per the spec's 'why this weight' integration point."""
    bio = _Bio(deadlift_1rm=180.0)
    sr = {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0}
    result = add_working_weight(_prescription(pct=70), "Horizontal Pull", bio, equipment="Barbell",
                                 strength_requirements=sr, movement_type="Unilateral")
    # 180 * 0.55(category default) * 0.70 = 69.3, * 0.55(bridge factor) = 38.115 -> 37.5
    assert result["working_weight_kg"] == 37.5
    assert "adjusted for single-arm/single-leg loading" in result["weight_note"]


def test_unilateral_bridge_factor_is_overridable_per_exercise():
    bio = _Bio(deadlift_1rm=180.0)
    sr = {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0,
          "unilateral_adjustment_factor": 0.8}
    result = add_working_weight(_prescription(pct=70), "Horizontal Pull", bio, equipment="Barbell",
                                 strength_requirements=sr, movement_type="Unilateral")
    # 69.3 * 0.8 = 55.44 -> 55.0, using the override instead of the 0.55 default
    assert result["working_weight_kg"] == 55.0


def test_unilateral_dumbbell_exercise_is_not_double_discounted():
    """Dumbbell/kettlebell exercises already get a per-implement discount
    (DB_KB_LOAD_RATIO) purely from being loaded one hand at a time - the
    unilateral bridge factor must not stack on top of that too."""
    bio = _Bio(deadlift_1rm=180.0)
    sr = {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0}
    result = add_working_weight(_prescription(pct=70), "Horizontal Pull", bio, equipment="Dumbbell",
                                 strength_requirements=sr, movement_type="Unilateral")
    # 180 * 0.55 * 0.70 = 69.3, * 0.40 (DB_KB_LOAD_RATIO, per-implement) = 27.72 -> nearest 2kg = 28.0
    # NOT also multiplied by the 0.55 unilateral bridge factor.
    assert result["working_weight_kg"] == 28.0
    assert "adjusted for single-arm" not in result["weight_note"]


def test_bilateral_exercise_never_gets_unilateral_discount():
    bio = _Bio(deadlift_1rm=180.0)
    sr = {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0}
    result = add_working_weight(_prescription(pct=70), "Horizontal Pull", bio, equipment="Barbell",
                                 strength_requirements=sr, movement_type="Bilateral")
    assert result["working_weight_kg"] == 70.0  # category default only, no unilateral factor

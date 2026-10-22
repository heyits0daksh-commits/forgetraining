"""
v5.13 GREEN/YELLOW/RED safety classification — a coach/athlete-facing label
for "is this specific exercise appropriate for this specific injury",
layered on top of (not a replacement for) the existing four-tier
safe/caution/high_risk/contraindicated model. See
injury_taxonomy.classify_exercise_safety's module-level comment for the
full design rationale; these tests exist to pin down the one property that
actually matters: the color tracks the exercise's own demand profile
against the injury's tissue sensitivity, not the severity number alone.
"""
from backend.services.injury_taxonomy import (
    classify_exercise_safety,
    classify_injury_risk,
    worst_safety_color,
)


def _exercise(**overrides):
    base = {
        "chain_type": None,
        "movement_plane": "Sagittal",
        "movement_type": "Bilateral",
        "force_type": None,
        "velocity_type": None,
        "stability_requirement": 0,
        "balance_requirement": 0,
        "mobility_requirement": 0,
    }
    base.update(overrides)
    return base


LOW_DEMAND = _exercise()  # trips zero derive_tissue_demands() flags
HIGH_MUSCLE_DEMAND = _exercise(force_type="Stretch-Shortening Cycle", velocity_type="Reactive")  # trips 2 Muscle axes


# ---------------------------------------------------------------------------
# Severity 3 (structural failure) is the one place severity alone decides -
# and that's a legitimate exception (no tissue integrity left to relate any
# exercise's demands to), not the general rule.
# ---------------------------------------------------------------------------
def test_severity_3_is_always_red_regardless_of_demand_profile():
    low = classify_exercise_safety(3, 1, tissue="Muscle", exercise=LOW_DEMAND)
    high = classify_exercise_safety(3, 1, tissue="Muscle", exercise=HIGH_MUSCLE_DEMAND)
    assert low["color"] == "RED"
    assert high["color"] == "RED"


def test_severity_3_is_red_even_with_no_tissue_or_exercise_supplied():
    assert classify_exercise_safety(3, 1)["color"] == "RED"


# ---------------------------------------------------------------------------
# The core "not simply severity" property: same severity, same joint/tissue,
# different color purely because the exercise's own demands differ.
# ---------------------------------------------------------------------------
def test_same_severity_different_exercises_yield_different_colors():
    """A severity-1 (mild) muscle strain: a low-demand exercise reads GREEN,
    a high-demand one (that recreates the injury mechanism) reads RED - the
    severity number never changes, only the exercise does."""
    low = classify_exercise_safety(1, 1, tissue="Muscle", exercise=LOW_DEMAND)
    high = classify_exercise_safety(1, 1, tissue="Muscle", exercise=HIGH_MUSCLE_DEMAND)
    assert low["color"] == "GREEN"
    assert high["color"] == "RED"
    assert low["color"] != high["color"]


def test_same_exercise_different_tissue_sensitivity_yields_different_colors():
    """The same demanding exercise is RED for a tissue sensitive to the axes
    it trips, but reads lower for a tissue that isn't."""
    exercise = _exercise(chain_type="Open Chain")  # trips only high_shear
    # Ligament is sensitive to high_shear (but needs a 2nd axis to hit RED)
    ligament = classify_exercise_safety(1, 1, tissue="Ligament", exercise=exercise)
    # Bone is not sensitive to high_shear at all
    bone = classify_exercise_safety(1, 1, tissue="Bone", exercise=exercise)
    assert ligament["color"] == "YELLOW"
    assert bone["color"] == "GREEN"


def test_one_matched_axis_is_yellow_not_red():
    exercise = _exercise(velocity_type="Reactive")  # trips high_velocity + high_impact, only high_velocity is muscle-relevant
    result = classify_exercise_safety(1, 1, tissue="Muscle", exercise=exercise)
    assert result["color"] == "YELLOW"


def test_two_matched_axes_is_red_even_at_mild_severity():
    result = classify_exercise_safety(1, 1, tissue="Muscle", exercise=HIGH_MUSCLE_DEMAND)
    assert result["color"] == "RED"


def test_moderate_severity_can_still_be_green_with_zero_demand_overlap():
    """Severity 2 (moderate/partial tear) doesn't force YELLOW/RED by
    itself - a low-demand exercise that's also within the difficulty
    ceiling reads GREEN."""
    result = classify_exercise_safety(2, 1, tissue="Muscle", exercise=LOW_DEMAND)
    assert result["color"] == "GREEN"


def test_difficulty_ceiling_still_provides_a_floor_with_zero_demand_matches():
    """An exercise that overshoots the severity's difficulty ceiling can't
    read as fully clear just because it happens to trip none of the
    tracked demand axes - the base tier still acts as a floor."""
    base_tier = classify_injury_risk(1, 4)  # severity 1 ceiling is 3 -> difficulty 4 is high_risk
    assert base_tier == "high_risk"
    result = classify_exercise_safety(1, 4, tissue="Muscle", exercise=LOW_DEMAND)
    assert result["color"] == "YELLOW"


def test_no_tissue_or_exercise_falls_back_to_difficulty_ceiling_only():
    """Omitting tissue/exercise (e.g. an injury string that didn't resolve
    to a taxonomy tissue) still returns a sensible color from the
    difficulty-ceiling floor alone, same graceful-fallback contract
    classify_injury_risk already has."""
    assert classify_exercise_safety(1, 1)["color"] == "GREEN"
    assert classify_exercise_safety(1, 3)["color"] == "YELLOW"


def test_rationale_is_always_a_nonempty_string():
    for severity, difficulty in [(1, 1), (2, 3), (3, 1)]:
        result = classify_exercise_safety(severity, difficulty, tissue="Muscle", exercise=HIGH_MUSCLE_DEMAND)
        assert isinstance(result["rationale"], str) and result["rationale"]


# ---------------------------------------------------------------------------
# worst_safety_color
# ---------------------------------------------------------------------------
def test_worst_safety_color_picks_the_most_restrictive():
    assert worst_safety_color(["GREEN", "YELLOW"]) == "YELLOW"
    assert worst_safety_color(["GREEN", "YELLOW", "RED"]) == "RED"
    assert worst_safety_color(["GREEN", "GREEN"]) == "GREEN"


def test_worst_safety_color_empty_list_defaults_to_green():
    assert worst_safety_color([]) == "GREEN"


# ---------------------------------------------------------------------------
# End-to-end: the label actually reaches the API surface for a real injury,
# on both the exercises the engine keeps in the session (with a color) and
# the ones it excludes (also with a color, plus on the alternatives it
# suggests instead).
# ---------------------------------------------------------------------------
def test_generate_workout_attaches_safety_classification_for_a_real_injury(client):
    r = client.post(
        "/api/v1/generate-workout",
        json={"injuries": ["Pectoralis Major Strain - Grade I Strain (Mild)"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    valid_colors = {"GREEN", "YELLOW", "RED"}

    classified = [
        ex for ex in body["prescribed_workout"] if "safety_classification" in ex
    ]
    for ex in classified:
        assert ex["safety_classification"]["color"] in valid_colors
        assert ex["safety_classification"]["details"]

    for ex in body.get("excluded_exercises", []):
        if "safety_classification" in ex:
            assert ex["safety_classification"]["color"] in valid_colors
        for alt in ex.get("alternatives", []):
            assert alt["safety_classification"]["color"] in valid_colors


def test_injury_swap_endpoint_attaches_safety_classification(client):
    exercises = client.get("/api/v1/exercises", params={"search": "Bench Press"}).json()["exercises"]
    assert exercises, "expected at least one bench-press-family exercise in the catalog"
    ex_id = exercises[0]["id"]
    r = client.get(
        f"/api/v1/exercises/{ex_id}/injury-swap",
        params={"injuries": "Pectoralis Major Strain - Grade I Strain (Mild)"},
    )
    assert r.status_code == 200, r.text
    options = r.json()["options"]
    for opt in options:
        assert opt["safety_classification"] in {"GREEN", "YELLOW", "RED"}

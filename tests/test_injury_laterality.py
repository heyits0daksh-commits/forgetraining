"""
v5.15 injury laterality — a one-sided ("left"/"right") injury no longer
blanket-blocks an exercise the database already marks as trained one side
at a time (`movement_type == "Unilateral"`, e.g. Single-Leg Leg Press,
Single-Arm Dumbbell Row, Pistol Squat): the injured side is simply skipped,
so the exercise still "works" (is still prescribable) instead of being
excluded outright.

Core properties under test:
  - omitting `side` (every pre-v5.15 call site) reproduces the exact
    pre-v5.15 result
  - a "bilateral" injury is unaffected regardless of movement_type
  - a one-sided injury only relaxes the check for movement_type ==
    "Unilateral" - "Alternating" (e.g. Walking Lunge, Farmer's Carry, both
    limbs load within the same set) and "Bilateral" exercises are unaffected
  - severity 3 (structural failure) is NEVER relaxed by laterality, on
    either classify_injury_risk or classify_exercise_safety
  - classify_exercise_safety mirrors the same relaxation, returning GREEN
    with an explanatory rationale
  - ProgressionEngine._resolve_injury_side turns WorkoutRequest.injury_sides
    into the {joint: side} map the engine actually filters on, including
    the "conflicting sides on the same joint -> bilateral" combining rule
  - find_alternatives honors injury_joint_side the same way
"""
from backend.services.injury_taxonomy import (
    INJURY_SIDES,
    OPPOSITE_SIDE,
    classify_exercise_safety,
    classify_injury_risk,
    find_alternatives,
    laterality_clears_joint,
)
from backend.services.progression_engine import ProgressionEngine


def _exercise(**overrides):
    base = {
        "id": "ex_1",
        "chain_type": None,
        "movement_plane": "Sagittal",
        "movement_type": "Bilateral",
        "force_type": None,
        "velocity_type": None,
        "stability_requirement": 0,
        "balance_requirement": 0,
        "mobility_requirement": 0,
        "difficulty": 3,
    }
    base.update(overrides)
    return base


UNILATERAL = _exercise(movement_type="Unilateral")
ALTERNATING = _exercise(movement_type="Alternating")
BILATERAL = _exercise(movement_type="Bilateral")


def test_injury_sides_vocabulary():
    assert INJURY_SIDES == ["left", "right", "bilateral"]
    assert OPPOSITE_SIDE == {"left": "right", "right": "left"}


def test_omitting_side_is_unchanged_pre_v5_15_behavior():
    """side=None (the default) must reproduce the exact pre-v5.15 result,
    for every existing call shape."""
    assert classify_injury_risk(2, 3, exercise=UNILATERAL) == \
        classify_injury_risk(2, 3, exercise=UNILATERAL, side=None)
    assert classify_injury_risk(1, 2) == classify_injury_risk(1, 2, side=None)
    assert classify_exercise_safety(2, 3, exercise=UNILATERAL) == \
        classify_exercise_safety(2, 3, exercise=UNILATERAL, side=None)


def test_one_sided_injury_clears_unilateral_exercise():
    """A severity-2 injury with a difficulty-3 Unilateral exercise would
    normally read high_risk (ceiling 2, difficulty 3 = ceiling+1) - a
    one-sided injury on a side-selectable exercise must clear it entirely."""
    unstaged = classify_injury_risk(2, 3, exercise=UNILATERAL)
    assert unstaged == "high_risk"
    assert classify_injury_risk(2, 3, exercise=UNILATERAL, side="left") == "safe"
    assert classify_injury_risk(2, 3, exercise=UNILATERAL, side="right") == "safe"


def test_bilateral_side_never_relaxes_anything():
    """An explicit 'bilateral' side must behave identically to no side at
    all - it's the conservative, both-sides-affected default."""
    assert classify_injury_risk(2, 3, exercise=UNILATERAL, side="bilateral") == \
        classify_injury_risk(2, 3, exercise=UNILATERAL)


def test_alternating_and_bilateral_exercises_unaffected_by_side():
    """Only movement_type == 'Unilateral' is side-selectable. Alternating
    (both limbs load within the same set) and Bilateral exercises must
    stay exactly as restrictive regardless of a one-sided injury."""
    assert classify_injury_risk(2, 3, exercise=ALTERNATING, side="left") == \
        classify_injury_risk(2, 3, exercise=ALTERNATING)
    assert classify_injury_risk(2, 3, exercise=BILATERAL, side="left") == \
        classify_injury_risk(2, 3, exercise=BILATERAL)
    assert classify_injury_risk(2, 3, exercise=ALTERNATING, side="left") == "high_risk"
    assert classify_injury_risk(2, 3, exercise=BILATERAL, side="left") == "high_risk"


def test_severity_3_never_relaxed_by_laterality():
    """Structural failure (severity 3) stays contraindicated on every side/
    movement_type combination - this app never lets a self-reported side
    substitute for a clinician's clearance at that severity."""
    assert classify_injury_risk(3, 1, exercise=UNILATERAL, side="left") == "contraindicated"
    assert classify_injury_risk(3, 1, exercise=UNILATERAL, side="right") == "contraindicated"
    assert laterality_clears_joint("left", 3, UNILATERAL) is False


def test_laterality_clears_joint_predicate():
    assert laterality_clears_joint("left", 1, UNILATERAL) is True
    assert laterality_clears_joint("right", 1, UNILATERAL) is True
    assert laterality_clears_joint("bilateral", 1, UNILATERAL) is False
    assert laterality_clears_joint(None, 1, UNILATERAL) is False
    assert laterality_clears_joint("left", 1, ALTERNATING) is False
    assert laterality_clears_joint("left", 1, BILATERAL) is False
    assert laterality_clears_joint("left", 1, None) is False


def test_classify_exercise_safety_mirrors_the_relaxation():
    result = classify_exercise_safety(2, 3, exercise=UNILATERAL, side="left")
    assert result["color"] == "GREEN"
    assert "left" in result["rationale"]
    assert "right" in result["rationale"]

    # bilateral side (or no side) keeps the original color
    unrelaxed = classify_exercise_safety(2, 3, exercise=UNILATERAL)
    assert unrelaxed["color"] != "GREEN"


def test_classify_exercise_safety_severity_3_stays_red_despite_side():
    result = classify_exercise_safety(3, 1, exercise=UNILATERAL, side="left")
    assert result["color"] == "RED"


# ==========================================================================
# ProgressionEngine._resolve_injury_side
# ==========================================================================

_ACL_GRADE_2 = "acl/ligament tear - grade 2 (partial tear)"


def test_resolve_injury_side_basic():
    user_injuries = {_ACL_GRADE_2}
    sides = {"ACL/Ligament Tear - Grade 2 (Partial Tear)": "left"}
    resolved = ProgressionEngine._resolve_injury_side(user_injuries, sides)
    assert resolved == {"Knee": "left"}


def test_resolve_injury_side_omitted_map_is_empty():
    user_injuries = {_ACL_GRADE_2}
    assert ProgressionEngine._resolve_injury_side(user_injuries, None) == {}
    assert ProgressionEngine._resolve_injury_side(user_injuries, {}) == {}


def test_resolve_injury_side_ignores_unrecognized_values():
    user_injuries = {_ACL_GRADE_2}
    sides = {"ACL/Ligament Tear - Grade 2 (Partial Tear)": "top"}
    assert ProgressionEngine._resolve_injury_side(user_injuries, sides) == {}


def test_resolve_injury_side_unmatched_injury_string_is_skipped():
    """A bare/legacy tag that doesn't resolve to a taxonomy entry (e.g.
    'Knee' typed literally) is left out, same as the other three resolvers -
    the legacy hard-block path is untouched by laterality."""
    user_injuries = {"knee"}
    sides = {"Knee": "left"}
    assert ProgressionEngine._resolve_injury_side(user_injuries, sides) == {}


def test_resolve_injury_side_conflicting_sides_combine_to_bilateral():
    """Two matched injuries on the same joint with different explicit
    sides can't both be satisfied by 'skip one side' - the combined result
    must widen to bilateral (no relaxation), not arbitrarily pick one."""
    hamstring_g1 = "hamstrings strain - grade i strain (mild)"
    hamstring_g2 = "hamstrings strain - grade ii strain (partial tear)"
    user_injuries = {hamstring_g1, hamstring_g2}
    sides = {
        "Hamstrings Strain - Grade I Strain (Mild)": "left",
        "Hamstrings Strain - Grade II Strain (Partial Tear)": "right",
    }
    resolved = ProgressionEngine._resolve_injury_side(user_injuries, sides)
    # Both entries are on the same joint (Hip or Knee depending on taxonomy
    # region) - whichever joint it resolves to, the side must be bilateral.
    assert set(resolved.values()) == {"bilateral"}


# ==========================================================================
# find_alternatives + injury_joint_side
# ==========================================================================

def test_find_alternatives_honors_injury_joint_side():
    all_exercises = {
        "source": _exercise(id="source", movement_pattern="Squat", category="Legs", difficulty=2),
        "cand_uni": _exercise(
            id="cand_uni", movement_pattern="Squat", category="Legs",
            movement_type="Unilateral", difficulty=3, joint_stress=["Knee"],
        ),
    }
    all_exercises["cand_uni"]["joint_stress"] = ["Knee"]
    severity = {"Knee": 2}

    # Without side info, the candidate's difficulty (3) exceeds the
    # severity-2 ceiling (2) by more than one step relative to caution -
    # it should be excluded.
    without_side = find_alternatives(
        all_exercises["source"], all_exercises, severity, max_results=5,
    )
    assert all(a["id"] != "cand_uni" for a in without_side)

    # With a one-sided injury_joint_side and the candidate being
    # side-selectable, it should now be included.
    with_side = find_alternatives(
        all_exercises["source"], all_exercises, severity, max_results=5,
        injury_joint_side={"Knee": "left"},
    )
    assert any(a["id"] == "cand_uni" for a in with_side)

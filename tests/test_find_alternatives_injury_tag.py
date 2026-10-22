"""
Regression test: find_alternatives() must not suggest a candidate that
carries the person's own selected named injury in its `injuries_to_avoid`
tag, even when that candidate clears the joint/severity/difficulty ceiling
check on its own.

Before the fix, `clears_joints()` inside find_alternatives only checked
severity/difficulty/tissue/stage against `joint_stress` - it never looked at
`injuries_to_avoid`, the exact-name contraindication list every exercise
carries and that generate_session's own `qualifies`/`is_safe` gate already
respects. That let an excluded exercise's "safe swap" suggestion include
another exercise explicitly tagged unsafe for the exact injury the person
selected (e.g. a Wide-Grip Pull-Up tagged "Rotator Cuff" being offered as
the alternative for someone excluded for a Rotator Cuff injury).
"""
from backend.services.injury_taxonomy import find_alternatives, INJURY_TAXONOMY


def _exercise(**overrides):
    base = {
        "id": "ex",
        "name": "Exercise",
        "movement_pattern": "Pull",
        "category": "Vertical Pull",
        "difficulty": 3,
        "equipment": "Bodyweight",
        "joint_stress": ["Shoulder"],
        "injuries_to_avoid": [],
        "alternatives": [],
        "regressions": [],
    }
    base.update(overrides)
    return base


def test_candidate_carrying_named_injury_tag_is_excluded_when_user_injuries_passed():
    inj = INJURY_TAXONOMY["Rotator Cuff"]
    injury_joint_severity = {inj["joint"]: inj["severity"]}
    user_injuries = {"rotator cuff"}

    victim = _exercise(id="victim", difficulty=4, injuries_to_avoid=["Rotator Cuff"])
    tagged_candidate = _exercise(
        id="tagged", name="Wide-Grip Pull-Up", difficulty=3,
        injuries_to_avoid=["Rotator Cuff"],
    )
    clean_candidate = _exercise(id="clean", name="Band Face Pull", difficulty=1)

    all_exercises = {c["id"]: c for c in (victim, tagged_candidate, clean_candidate)}

    alts = find_alternatives(
        victim, all_exercises, injury_joint_severity,
        max_results=5, user_injuries=user_injuries,
    )

    names = [a["name"] for a in alts]
    assert "Wide-Grip Pull-Up" not in names
    assert "Band Face Pull" in names


def test_omitting_user_injuries_reproduces_pre_fix_behavior():
    """user_injuries is optional - every existing call site that doesn't
    pass it keeps behaving exactly as before (name-tag contraindications
    aren't screened, only joint/severity/tissue/stage)."""
    inj = INJURY_TAXONOMY["Rotator Cuff"]
    injury_joint_severity = {inj["joint"]: inj["severity"]}

    victim = _exercise(id="victim", difficulty=4, injuries_to_avoid=["Rotator Cuff"])
    tagged_candidate = _exercise(
        id="tagged", name="Wide-Grip Pull-Up", difficulty=3,
        injuries_to_avoid=["Rotator Cuff"],
    )
    all_exercises = {c["id"]: c for c in (victim, tagged_candidate)}

    alts = find_alternatives(victim, all_exercises, injury_joint_severity, max_results=5)

    assert [a["name"] for a in alts] == ["Wide-Grip Pull-Up"]


def test_candidate_still_excluded_on_severity_even_with_user_injuries_passed():
    """user_injuries adds a check, it doesn't remove the existing
    joint/severity/difficulty screening."""
    inj = INJURY_TAXONOMY["Rotator Cuff"]
    injury_joint_severity = {inj["joint"]: inj["severity"]}
    user_injuries = {"rotator cuff"}

    victim = _exercise(id="victim", difficulty=5, injuries_to_avoid=[])
    too_hard = _exercise(id="hard", name="Freestanding HSPU", difficulty=5, injuries_to_avoid=[])
    all_exercises = {c["id"]: c for c in (victim, too_hard)}

    alts = find_alternatives(
        victim, all_exercises, injury_joint_severity,
        max_results=5, user_injuries=user_injuries,
    )

    assert alts == []

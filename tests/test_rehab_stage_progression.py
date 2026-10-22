"""
v5.14 rehab-stage progression model — REHAB_STAGES / classify_injury_risk's
optional `stage` kwarg / classify_exercise_safety's optional `stage` kwarg /
find_alternatives' optional `injury_joint_stage` kwarg.

Core properties under test:
  - omitting `stage` reproduces the exact pre-v5.14 result for every
    existing call shape (severity+difficulty, +tissue/exercise)
  - stage only ever narrows (never loosens) what severity+difficulty alone
    would allow
  - a stage's blocked demand axes (e.g. plyometric/impact work during
    early_recovery) hard-block regardless of raw difficulty
  - severity 3 (structural failure) is never unblocked by a self-reported
    stage
  - later stages progressively re-permit more demanding axes, ending at
    return_to_performance with no extra restriction beyond severity itself
"""
from backend.services.injury_taxonomy import (
    REHAB_STAGES,
    classify_exercise_safety,
    classify_injury_risk,
    resolve_rehab_stage,
    rehab_stage_reference,
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


PLYO_EXERCISE = _exercise(force_type="Stretch-Shortening Cycle", velocity_type="Reactive")
LOW_DEMAND = _exercise()


def test_omitting_stage_is_unchanged_pre_v5_14_behavior():
    """stage=None (the default) must reproduce the exact pre-v5.14 result
    for every call shape, with or without tissue/exercise."""
    assert classify_injury_risk(1, 2) == classify_injury_risk(1, 2, stage=None)
    assert classify_injury_risk(1, 3, tissue="Muscle", exercise=PLYO_EXERCISE) == \
        classify_injury_risk(1, 3, tissue="Muscle", exercise=PLYO_EXERCISE, stage=None)
    assert classify_injury_risk(2, 2) == "caution"
    assert classify_injury_risk(2, 2, stage=None) == "caution"


def test_rehab_stages_ordered_early_to_full_return():
    assert REHAB_STAGES == [
        "early_recovery",
        "controlled_loading",
        "strength_rebuilding",
        "advanced_strength",
        "plyometric_reactive",
        "return_to_performance",
    ]


def test_early_recovery_blocks_plyometric_exercise_regardless_of_difficulty():
    """A reactive/plyometric exercise (Muscle-sensitive to high_eccentric +
    high_velocity) must be contraindicated in early_recovery even at
    difficulty 1, where the raw severity ceiling alone would allow it."""
    base = classify_injury_risk(1, 1, tissue="Muscle", exercise=PLYO_EXERCISE)
    assert base in ("safe", "caution")  # raw severity/difficulty alone would allow this
    staged = classify_injury_risk(1, 1, tissue="Muscle", exercise=PLYO_EXERCISE, stage="early_recovery")
    assert staged == "contraindicated"


def test_return_to_performance_matches_severity_only_result():
    """The final stage imposes no extra restriction beyond the severity
    ceiling itself - it should reproduce the un-staged result exactly."""
    for difficulty in range(1, 6):
        base = classify_injury_risk(1, difficulty, tissue="Muscle", exercise=PLYO_EXERCISE)
        staged = classify_injury_risk(
            1, difficulty, tissue="Muscle", exercise=PLYO_EXERCISE, stage="return_to_performance",
        )
        assert staged == base


def test_stage_never_loosens_past_severity_ceiling():
    """A severity-2 injury has a hard ceiling of difficulty 2 regardless of
    stage - even return_to_performance (raw ceiling 5) can't push a
    severity-2 injury's effective ceiling past what severity itself allows."""
    assert classify_injury_risk(2, 4, stage="return_to_performance") == "contraindicated"
    assert classify_injury_risk(2, 3, stage="return_to_performance") == "high_risk"
    assert classify_injury_risk(2, 2, stage="return_to_performance") == "caution"
    assert classify_injury_risk(2, 1, stage="return_to_performance") == "safe"


def test_severity_3_never_unblocked_by_stage():
    """Structural-failure injuries stay contraindicated no matter what
    stage is passed - a self-reported stage never overrides this."""
    for stage in REHAB_STAGES:
        assert classify_injury_risk(3, 1, stage=stage) == "contraindicated"
        assert classify_injury_risk(3, 1, tissue="Muscle", exercise=LOW_DEMAND, stage=stage) == "contraindicated"


def test_stages_progressively_permit_plyometric_work():
    """Walking a severity-1 muscle strain through the stages in order, the
    plyometric exercise should stay blocked until plyometric_reactive, then
    be allowed (at low difficulty) from there on."""
    results = {
        stage: classify_injury_risk(1, 1, tissue="Muscle", exercise=PLYO_EXERCISE, stage=stage)
        for stage in REHAB_STAGES
    }
    assert results["early_recovery"] == "contraindicated"
    assert results["controlled_loading"] == "contraindicated"
    assert results["strength_rebuilding"] == "contraindicated"
    # advanced_strength doesn't block high_eccentric/high_velocity, only high_impact
    assert results["advanced_strength"] in ("safe", "caution")
    assert results["plyometric_reactive"] in ("safe", "caution")
    assert results["return_to_performance"] in ("safe", "caution")


def test_resolve_rehab_stage_defaults_by_severity():
    assert resolve_rehab_stage(3, None) == "early_recovery"
    assert resolve_rehab_stage(2, None) == "controlled_loading"
    assert resolve_rehab_stage(1, None) == "strength_rebuilding"


def test_resolve_rehab_stage_prefers_explicit_valid_stage():
    assert resolve_rehab_stage(1, "plyometric_reactive") == "plyometric_reactive"


def test_resolve_rehab_stage_falls_back_on_unrecognized_stage():
    assert resolve_rehab_stage(2, "not_a_real_stage") == "controlled_loading"


def test_classify_exercise_safety_stage_only_worsens_color():
    """The stage-aware color can only be the same or worse (never better)
    than the color computed without a stage. Use an exercise that trips
    only one Muscle-sensitive axis (large_rom_demand) - base color is
    YELLOW (single-axis match), but early_recovery hard-blocks
    large_rom_demand for Muscle, so the staged color must worsen to RED."""
    rom_exercise = _exercise(mobility_requirement=60)
    base = classify_exercise_safety(1, 1, tissue="Muscle", exercise=rom_exercise)
    assert base["color"] == "YELLOW"
    staged = classify_exercise_safety(
        1, 1, tissue="Muscle", exercise=rom_exercise, stage="early_recovery",
    )
    order = {"GREEN": 0, "YELLOW": 1, "RED": 2}
    assert order[staged["color"]] >= order[base["color"]]
    assert staged["color"] == "RED"
    assert "Rehab stage" in staged["rationale"]


def test_classify_exercise_safety_omitting_stage_is_unchanged():
    base = classify_exercise_safety(1, 2, tissue="Muscle", exercise=LOW_DEMAND)
    same = classify_exercise_safety(1, 2, tissue="Muscle", exercise=LOW_DEMAND, stage=None)
    assert base == same


def test_classify_exercise_safety_severity_3_ignores_stage():
    for stage in REHAB_STAGES:
        result = classify_exercise_safety(3, 1, stage=stage)
        assert result["color"] == "RED"


def test_rehab_stage_reference_shape():
    ref = rehab_stage_reference()
    assert [r["stage"] for r in ref] == REHAB_STAGES
    for row in ref:
        assert set(row.keys()) == {"stage", "label", "description", "difficulty_ceiling"}
        assert isinstance(row["difficulty_ceiling"], int)

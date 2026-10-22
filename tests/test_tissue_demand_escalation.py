"""
v5.12 tissue-demand escalation — classify_injury_risk(tissue=..., exercise=...)
optionally bumps a "safe"/"caution" base tier up one notch when the exercise's
derived demand profile (exercise_metadata.derive_tissue_demands) hits enough
axes that tissue type is generally sensitive to (injury_taxonomy's
TISSUE_DEMAND_SENSITIVITY). See classify_injury_risk's docstring:
  - escalation only ever tightens (safe->caution, caution->high_risk), never
    loosens an already-computed tier
  - it requires >= _DEMAND_ESCALATION_THRESHOLD (2) matching axes, not just 1
  - omitting `tissue`/`exercise` reproduces the exact pre-v5.12 (severity +
    difficulty only) behavior for every existing call site
"""
from backend.services.injury_taxonomy import classify_injury_risk


def _exercise(**overrides):
    """Minimal exercise dict with every field derive_tissue_demands() reads,
    defaulted to values that trip zero demand flags."""
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


def test_two_argument_call_is_unchanged_pre_v5_12_behavior():
    """No tissue/exercise supplied -> pure severity+difficulty classification,
    exactly as every pre-v5.12 call site and test relies on."""
    assert classify_injury_risk(1, 2) == "safe"
    assert classify_injury_risk(1, 3) == "caution"
    assert classify_injury_risk(1, 4) == "high_risk"
    assert classify_injury_risk(1, 5) == "contraindicated"
    assert classify_injury_risk(3, 1) == "contraindicated"


def test_no_escalation_when_tissue_has_no_sensitivity_entry():
    """An unrecognized/absent tissue type falls back to the base tier even
    though an exercise dict was supplied."""
    demanding_exercise = _exercise(
        chain_type="Open Chain",
        movement_plane="Transverse",
        velocity_type="Reactive",
        force_type="Stretch-Shortening Cycle",
    )
    assert classify_injury_risk(1, 3, tissue="NotARealTissue", exercise=demanding_exercise) == "caution"


def test_no_escalation_below_the_matched_axis_threshold():
    """Muscle is sensitive to high_eccentric/high_velocity/large_rom_demand.
    An exercise tripping only ONE of those axes must not escalate the base
    tier - the threshold is >=2 matches, not >=1."""
    exercise = _exercise(velocity_type="Reactive")  # trips only high_velocity (and high_impact, not muscle-relevant)
    assert classify_injury_risk(1, 3, tissue="Muscle", exercise=exercise) == "caution"


def test_escalates_safe_to_caution_at_threshold():
    """Two matched axes for Muscle (high_eccentric + high_velocity) escalates
    an otherwise-safe base tier to caution."""
    exercise = _exercise(force_type="Stretch-Shortening Cycle", velocity_type="Reactive")
    base = classify_injury_risk(1, 1)
    assert base == "safe"
    assert classify_injury_risk(1, 1, tissue="Muscle", exercise=exercise) == "caution"


def test_escalates_caution_to_high_risk_at_threshold():
    """Same two-axis match, but starting from a base tier of caution."""
    exercise = _exercise(force_type="Stretch-Shortening Cycle", velocity_type="Reactive")
    base = classify_injury_risk(1, 3)
    assert base == "caution"
    assert classify_injury_risk(1, 3, tissue="Muscle", exercise=exercise) == "high_risk"


def test_never_de_escalates_contraindicated():
    """Severity 3 (or a difficulty past the ceiling) is contraindicated
    regardless of demand profile - escalation only ever adds caution, and
    there's no tier above contraindicated or below it to move to here."""
    exercise = _exercise(
        chain_type="Open Chain",
        movement_plane="Transverse",
        velocity_type="Reactive",
        force_type="Stretch-Shortening Cycle",
    )
    assert classify_injury_risk(3, 1, tissue="Muscle", exercise=exercise) == "contraindicated"
    assert classify_injury_risk(1, 5, tissue="Muscle", exercise=exercise) == "contraindicated"


def test_high_risk_tier_has_no_further_escalation():
    """high_risk isn't a key in _TIER_ESCALATION, so a demanding exercise
    landing there stays at high_risk rather than being pushed to some
    non-existent tier beyond it."""
    exercise = _exercise(force_type="Stretch-Shortening Cycle", velocity_type="Reactive")
    base = classify_injury_risk(1, 4)
    assert base == "high_risk"
    assert classify_injury_risk(1, 4, tissue="Muscle", exercise=exercise) == "high_risk"


def test_escalation_is_tissue_specific():
    """A Closed Chain + Frontal-plane exercise trips exactly two demand
    flags overall (high_compression, frontal_plane_loading). No single
    tissue type here is sensitive to *both* of those axes at once, so none
    should reach the >=2 threshold and escalate - matched-axis counting is
    per-tissue, not a raw count of every flag the exercise trips."""
    exercise = _exercise(chain_type="Closed Chain", movement_plane="Frontal")
    assert classify_injury_risk(1, 1, tissue="Bone", exercise=exercise) == "safe"       # matches only high_compression
    assert classify_injury_risk(1, 1, tissue="Ligament", exercise=exercise) == "safe"   # matches only frontal_plane_loading
    assert classify_injury_risk(1, 1, tissue="Joint", exercise=exercise) == "safe"      # matches only high_compression

    # Ligament IS sensitive to both frontal_plane_loading and large_rom_demand;
    # adding mobility_requirement>=60 gives it a second matched axis and
    # crosses the threshold, while Bone (not sensitive to either) does not.
    exercise_with_rom = _exercise(chain_type="Closed Chain", movement_plane="Frontal", mobility_requirement=60)
    assert classify_injury_risk(1, 1, tissue="Ligament", exercise=exercise_with_rom) == "caution"
    assert classify_injury_risk(1, 1, tissue="Bone", exercise=exercise_with_rom) == "safe"

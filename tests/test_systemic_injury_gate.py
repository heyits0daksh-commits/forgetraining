"""
v5.16 systemic-injury gate — INJURY_TAXONOMY's `systemic` field and
injury_taxonomy.resolve_systemic_injury.

v5.30 update: the three Concussion entries were the only ones flagged
`systemic=True` until the clinician review packet's Part 2 question
("should anything else be systemic?") surfaced eight more severity-3
entries whose own movement_restrictions/clinical_red_flags text already
described a whole-body training stop ("no training until medically
cleared", "not a training-programmable condition", "do not attempt any
exercise") while `systemic` was left unset - meaning the app was only
ever blocking exercises tagged to that entry's one joint. See
SYSTEMIC_INJURY_NAMES below for the full current list.

WHY THIS EXISTS
Every other injury in the taxonomy is scoped to one joint: classify_injury_risk
is only ever called for an exercise if that exercise's own joint_stress list
contains the joint the injury maps to (see progression_engine.generate_session's
per-joint loop). That's correct for a knee or shoulder injury - a bench press
genuinely doesn't load an injured knee. It's NOT correct for a concussion,
which is mapped to joint="Neck" purely because that's the closest of the 8
exercises.json joint tags (see the module docstring's "Head & Thorax" note) -
before this gate, a user reporting "Concussion - Grade 3 (Loss of
Consciousness)" would still be prescribed a full squat/bench/deadlift session,
because none of those exercises tag "Neck", even though that entry's own
movement_restrictions say "No training of any kind until medically cleared".

Core properties under test:
  - resolve_systemic_injury only matches entries flagged `systemic=True`
    (i.e. it's a no-op for every other injury in the taxonomy - regression
    safety for every existing joint-scoped call site)
  - it picks the worst severity among multiple matched injuries, same as the
    existing {joint: ...} resolvers
  - classify_injury_risk, called with a systemic injury's (severity, stage)
    and NO tissue/exercise/side, gates purely on difficulty/stage - exactly
    the same function every other injury already uses, just invoked without
    being scoped to one joint's exercises
  - severity 3 (Concussion - Grade 3) is contraindicated at every difficulty,
    matching "no training of any kind"
  - an explicit early_recovery stage tightens a mild (severity 1) concussion
    below what severity alone would allow, matching "light non-contact
    aerobic activity only"
"""
from backend.services.injury_taxonomy import (
    INJURY_TAXONOMY,
    classify_injury_risk,
    resolve_systemic_injury,
)

GRADE1 = "concussion - grade 1 (no loc, symptoms <15min)"
GRADE2 = "concussion - grade 2 (no loc, symptoms >15min)"
GRADE3 = "concussion - grade 3 (loss of consciousness)"

# v5.30: the full, current set of systemic entries - kept as an explicit
# list (not "anything not concussion") so a future addition/removal has to
# touch this test deliberately instead of silently passing or failing.
SYSTEMIC_INJURY_NAMES = {
    "Concussion - Grade 1 (No LOC, Symptoms <15min)",
    "Concussion - Grade 2 (No LOC, Symptoms >15min)",
    "Concussion - Grade 3 (Loss of Consciousness)",
    "Acute Compartment Syndrome - Anterior Leg",
    "Acute Compartment Syndrome - Deep Posterior Leg",
    "Cervical Facet Injury - Stage 3 (Bilateral Dislocation)",
    "Lumbar Fracture - Unstable (Two/Three Column)",
    "Massive Central Disc Herniation",
    "Burst Fracture (Spine)",
    "Fracture-Dislocation with Spinal Cord Injury",
    "Rib Fracture - Displaced/Multiple (Flail Chest Risk)",
}


def test_concussion_entries_are_flagged_systemic():
    for name, entry in INJURY_TAXONOMY.items():
        if name.lower().startswith("concussion"):
            assert entry["systemic"] is True, name


def test_systemic_flag_matches_expected_set_exactly():
    """Pins the full current systemic set so an addition/removal is a
    deliberate, reviewed change to this test - not a silent taxonomy edit."""
    actual = {n for n, e in INJURY_TAXONOMY.items() if e.get("systemic")}
    assert actual == SYSTEMIC_INJURY_NAMES


def test_non_systemic_injuries_are_unaffected():
    """Every taxonomy entry outside the known systemic set must NOT be
    flagged systemic, and resolve_systemic_injury must ignore them entirely
    (return None, None) - this is the regression guard that nothing about
    the existing per-joint injuries changed."""
    non_systemic_sample = {
        n.lower() for n in INJURY_TAXONOMY
        if n not in SYSTEMIC_INJURY_NAMES
    }
    for name, entry in INJURY_TAXONOMY.items():
        if name not in SYSTEMIC_INJURY_NAMES:
            assert not entry.get("systemic"), name

    severity, stage = resolve_systemic_injury(non_systemic_sample)
    assert (severity, stage) == (None, None)


def test_resolve_systemic_injury_no_match_returns_none():
    assert resolve_systemic_injury(set()) == (None, None)
    assert resolve_systemic_injury({"acl tear - grade 1 (mild sprain)"}) == (None, None)


def test_resolve_systemic_injury_matches_concussion_severity():
    assert resolve_systemic_injury({GRADE1}) == (1, None)
    assert resolve_systemic_injury({GRADE2}) == (2, None)
    assert resolve_systemic_injury({GRADE3}) == (3, None)


def test_resolve_systemic_injury_worst_of_multiple_matches():
    """Mirrors _resolve_injury_severity's 'worst severity wins' rule."""
    severity, _ = resolve_systemic_injury({GRADE1, GRADE3})
    assert severity == 3


def test_resolve_systemic_injury_honors_explicit_stage():
    severity, stage = resolve_systemic_injury({GRADE1}, {GRADE1: "early_recovery"})
    assert (severity, stage) == (1, "early_recovery")

    # An unrecognized stage string is ignored, same as the joint-scoped
    # resolvers already do for a bad WorkoutRequest.injury_stages value.
    severity, stage = resolve_systemic_injury({GRADE1}, {GRADE1: "not_a_real_stage"})
    assert (severity, stage) == (1, None)


def test_grade3_contraindicated_at_every_difficulty():
    """Severity 3 -> contraindicated regardless of difficulty or stage,
    same as any other severity-3 injury - a squat (difficulty 1) is just as
    blocked as a max-effort lift, because the gate isn't about which
    exercise, it's "no training until cleared"."""
    severity, stage = resolve_systemic_injury({GRADE3})
    for difficulty in (1, 2, 3, 4, 5):
        assert classify_injury_risk(severity, difficulty, stage=stage) == "contraindicated"


def test_grade1_without_stage_uses_severity_ceiling_only():
    """No explicit stage given -> falls back to the same severity-1 ceiling
    (difficulty <=3 safe) every other mild injury uses. This is a known,
    accepted limitation shared with every other injury in this file (see
    DEFAULT_REHAB_STAGE_FOR_SEVERITY's docstring) - it's why callers should
    still collect an explicit stage where possible, not a bug introduced by
    this gate."""
    severity, stage = resolve_systemic_injury({GRADE1})
    assert classify_injury_risk(severity, 2, stage=stage) == "safe"
    assert classify_injury_risk(severity, 3, stage=stage) == "caution"
    assert classify_injury_risk(severity, 4, stage=stage) == "high_risk"


def test_grade1_with_early_recovery_stage_is_tighter():
    """Once a stage is actually reported, it can only tighten - never loosen
    - what severity alone allows (same rule test_rehab_stage_progression.py
    already covers for joint-scoped injuries)."""
    severity, stage = resolve_systemic_injury({GRADE1}, {GRADE1: "early_recovery"})
    unstaged_tier = classify_injury_risk(severity, 1, stage=None)
    staged_tier = classify_injury_risk(severity, 1, stage=stage)
    assert unstaged_tier == "safe"
    assert staged_tier == "caution"


def test_browse_endpoints_surface_clinical_red_flags():
    """(v5.17) The two grouped-taxonomy browse functions (the only place
    injury data reaches the frontend/API) must include clinical_red_flags
    per grade, and it must actually match the source taxonomy entry - not
    just be present-but-empty."""
    from backend.services.injury_taxonomy import (
        grouped_injury_taxonomy,
        grouped_injury_taxonomy_by_muscle_group,
    )

    for grouped_fn in (grouped_injury_taxonomy, grouped_injury_taxonomy_by_muscle_group):
        grouped = grouped_fn()
        found_grade3 = False
        for conditions in grouped.values():
            for cond in conditions:
                for grade in cond["grades"]:
                    assert "clinical_red_flags" in grade
                    assert isinstance(grade["clinical_red_flags"], list)
                    if grade["name"] == "Concussion - Grade 3 (Loss of Consciousness)":
                        found_grade3 = True
                        assert len(grade["clinical_red_flags"]) > 0
                        assert grade["clinical_red_flags"] == INJURY_TAXONOMY[grade["name"]]["clinical_red_flags"]
        assert found_grade3, f"{grouped_fn.__name__} never surfaced Concussion - Grade 3"

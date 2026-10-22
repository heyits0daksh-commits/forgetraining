"""
v5.18 whole-program severe-injury gate — injury_taxonomy.resolve_severe_injuries,
core.exceptions.SevereInjuryBlockedError, and the check wired into
ProgressionEngine.generate_session.

WHY THIS EXISTS
Before this pass, a severity-3 ("structural failure - the joint cannot be
trusted under any real load") injury only excluded exercises that loaded
the specific joint it mapped to (SEVERITY_DIFFICULTY_CEILING[3] = None,
i.e. every difficulty is contraindicated *for that joint*). Someone with a
Grade 3 ACL tear would still get a full upper-body program - correct for
the exercise-selection layer, but not what's wanted at the whole-program
level: a severity-3 injury should stop program generation outright and
send the person to a clinician, the same way resolve_systemic_injury
already does for concussion specifically. resolve_severe_injuries()
generalizes that "block everything" behavior to every severity-3 entry in
the taxonomy, not just the ones flagged `systemic`.

Core properties under test:
  - resolve_severe_injuries only matches taxonomy entries with severity==3
    (regression safety: severity 1/2 injuries are completely unaffected -
    they must keep getting exercise-level exclusion + alternates, not a
    full block, per the "moderate/mild get alternates" requirement)
  - it returns every matched severe injury (not just the first/worst one),
    each carrying its own clinical_red_flags so the block message/detail
    can show *why*, not just *that* generation is blocked
  - ProgressionEngine.generate_session raises SevereInjuryBlockedError
    before any exercise selection happens, for both a single-session
    request and a multi-week program (program_builder.generate_program
    calls generate_session per day, so the first day's raise stops the
    whole program - it never gets partway through generating some days
    and not others)
  - a severity-1/2 injury never triggers this path, and existing
    exercise-level behavior (per-joint exclusion, find_alternatives) is
    unaffected - this is additive, not a replacement
  - the FastAPI layer surfaces this as 422 with the standard ForgeError
    envelope, `error.code == "severe_injury_block"`, and
    `error.details.blocked_injuries` containing each matched injury's
    name/joint/clinical_red_flags
"""
import pytest

from backend.services.injury_taxonomy import INJURY_TAXONOMY, resolve_severe_injuries

SEV3_NAME = next(n for n, e in INJURY_TAXONOMY.items() if e["severity"] == 3)
SEV3_SECOND = next(
    n for n, e in INJURY_TAXONOMY.items() if e["severity"] == 3 and n != SEV3_NAME
)
SEV2_NAME = next(n for n, e in INJURY_TAXONOMY.items() if e["severity"] == 2)
SEV1_NAME = next(n for n, e in INJURY_TAXONOMY.items() if e["severity"] == 1)
# A moderate Lower Back injury specifically (rather than SEV2_NAME's
# arbitrary joint) for the excluded_exercises/alternatives tests below -
# guarantees real overlap with the barbell squat/deadlift movements those
# tests' equipment list actually offers, so a passing assertion reflects
# the fix and isn't just luck-of-dict-ordering on which joint SEV2_NAME
# happens to be.
SEV2_LOWER_BACK_NAME = "Erector Spinae Strain - Grade II Strain (Partial Tear)"


# ---------------------------------------------------------------------------
# Unit-level: resolve_severe_injuries
# ---------------------------------------------------------------------------

def test_no_injuries_resolves_empty():
    assert resolve_severe_injuries(set()) == []


def test_mild_and_moderate_injuries_never_match():
    """Regression guard: this gate must stay scoped to severity 3 only -
    mild/moderate injuries keep the existing alternate-finding behavior,
    they must never trip the whole-program block."""
    assert resolve_severe_injuries({SEV1_NAME.lower()}) == []
    assert resolve_severe_injuries({SEV2_NAME.lower()}) == []
    assert resolve_severe_injuries({SEV1_NAME.lower(), SEV2_NAME.lower()}) == []


def test_severity_3_injury_matches():
    matches = resolve_severe_injuries({SEV3_NAME.lower()})
    assert len(matches) == 1
    assert matches[0]["name"] == SEV3_NAME
    assert matches[0]["joint"] == INJURY_TAXONOMY[SEV3_NAME]["joint"]
    assert matches[0]["clinical_red_flags"], "block detail must carry the injury's own red flags"


def test_multiple_severity_3_injuries_all_returned_not_just_worst():
    matches = resolve_severe_injuries({SEV3_NAME.lower(), SEV3_SECOND.lower()})
    names = {m["name"] for m in matches}
    assert names == {SEV3_NAME, SEV3_SECOND}


def test_mixed_severities_only_returns_the_severe_ones():
    matches = resolve_severe_injuries({SEV3_NAME.lower(), SEV2_NAME.lower(), SEV1_NAME.lower()})
    assert [m["name"] for m in matches] == [SEV3_NAME]


def test_unmatched_injury_string_is_ignored():
    """A string that isn't in the taxonomy at all (raw joint name, typo,
    legacy literal tag) is simply skipped here, same convention every
    other resolver in this module already follows."""
    assert resolve_severe_injuries({"not a real injury"}) == []


def test_results_sorted_by_name_for_deterministic_messages():
    matches = resolve_severe_injuries({SEV3_NAME.lower(), SEV3_SECOND.lower()})
    assert [m["name"] for m in matches] == sorted([SEV3_NAME, SEV3_SECOND])


# ---------------------------------------------------------------------------
# Engine-level: ProgressionEngine.generate_session raises before selection
# ---------------------------------------------------------------------------

def test_generate_session_raises_for_severe_injury():
    from backend.core.exceptions import SevereInjuryBlockedError
    from backend.models.schemas import WorkoutRequest
    from backend.services.progression_engine import ProgressionEngine

    engine = ProgressionEngine()
    req = WorkoutRequest(
        equipment_available=["Bodyweight", "Barbell", "Dumbbell"],
        injuries=[SEV3_NAME],
    )
    with pytest.raises(SevereInjuryBlockedError) as excinfo:
        engine.generate_session(req)

    err = excinfo.value
    assert err.status_code == 422
    assert err.code == "severe_injury_block"
    assert err.details is not None
    blocked = err.details["blocked_injuries"]
    assert [b["name"] for b in blocked] == [SEV3_NAME]
    assert blocked[0]["clinical_red_flags"]


def test_generate_session_unaffected_for_moderate_or_mild_injury():
    """Regression guard mirrored at the engine level: severity 1/2 must
    still produce a normal session (exercises for the affected joint
    excluded/swapped, not the whole session blocked)."""
    from backend.models.schemas import WorkoutRequest
    from backend.services.progression_engine import ProgressionEngine

    engine = ProgressionEngine()
    req = WorkoutRequest(
        equipment_available=["Bodyweight", "Barbell", "Dumbbell"],
        injuries=[SEV2_NAME],
    )
    result = engine.generate_session(req)
    assert len(result["prescribed_workout"]) > 0


# ---------------------------------------------------------------------------
# HTTP-level: both generation endpoints surface the 422 envelope
# ---------------------------------------------------------------------------

def test_generate_workout_endpoint_422s_for_severe_injury(client):
    r = client.post(
        "/api/v1/generate-workout",
        json={"equipment_available": ["Bodyweight"], "injuries": [SEV3_NAME]},
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["error"]["code"] == "severe_injury_block"
    blocked = body["error"]["details"]["blocked_injuries"]
    assert blocked[0]["name"] == SEV3_NAME
    assert blocked[0]["clinical_red_flags"]


def test_generate_program_endpoint_422s_for_severe_injury_before_building_any_week(client):
    """program_builder.generate_program calls generate_session once per
    (week, day) - the block must fire on the very first call and stop the
    whole program, not partially build some days then fail."""
    r = client.post(
        "/api/v1/generate-program",
        json={
            "weeks": 3,
            "days_per_week": 4,
            "equipment_available": ["Bodyweight"],
            "injuries": [SEV3_NAME],
        },
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["error"]["code"] == "severe_injury_block"
    assert body["error"]["details"]["blocked_injuries"][0]["name"] == SEV3_NAME


def test_generate_workout_endpoint_unaffected_for_mild_injury(client):
    r = client.post(
        "/api/v1/generate-workout",
        json={"equipment_available": ["Bodyweight"], "injuries": [SEV1_NAME]},
    )
    assert r.status_code == 200, r.text
    assert len(r.json()["prescribed_workout"]) > 0


# ---------------------------------------------------------------------------
# excluded_exercises must reach the client on BOTH endpoints - it was being
# silently dropped for /generate-program (program_builder.py never copied
# session_result["excluded_exercises"] onto the per-day dict it appends to
# day_results), which meant a moderate/mild injury's alternate-exercise
# suggestions never reached a Program Builder user even though the engine
# computed them - only /generate-workout (single session) had this working.
# ---------------------------------------------------------------------------

def test_generate_workout_surfaces_excluded_exercises_and_alternatives(client):
    """A moderate injury with a chest-loading exercise it excludes should
    come back with either real alternatives or the explicit
    alternatives_note fallback - never neither."""
    r = client.post(
        "/api/v1/generate-workout",
        json={
            "equipment_available": ["Barbell", "Dumbbell", "Bodyweight", "Adjustable Bench"],
            "injuries": [SEV2_LOWER_BACK_NAME],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "excluded_exercises" in body
    assert body["excluded_exercises"], (
        "expected at least one exercise excluded for a moderate Lower Back injury "
        "given a squat/deadlift-capable equipment set"
    )
    for ex in body["excluded_exercises"]:
        if ex.get("risk_tier"):
            assert ex.get("alternatives") or ex.get("alternatives_note"), (
                f"{ex['name']} was excluded on injury grounds with no alternatives "
                "and no alternatives_note fallback"
            )


def test_generate_program_days_carry_excluded_exercises(client):
    """Regression test for the drop described above: each day in a
    generated program must carry the same excluded_exercises data
    /generate-workout returns for an equivalent single session, not an
    empty/missing key."""
    r = client.post(
        "/api/v1/generate-program",
        json={
            "weeks": 1,
            "days_per_week": 3,
            "equipment_available": ["Barbell", "Dumbbell", "Bodyweight", "Adjustable Bench"],
            "injuries": [SEV2_LOWER_BACK_NAME],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    days = body["program"][0]["days"]
    assert all("excluded_exercises" in d for d in days), (
        "every program day must carry excluded_exercises, same as /generate-workout"
    )
    # At least one day should actually have a non-empty list, given a
    # moderate injury and a movement-heavy equipment set - otherwise this
    # test can't tell a real fix from an always-empty list satisfying the
    # bare "key exists" check above.
    assert any(d["excluded_exercises"] for d in days), (
        "expected at least one day to have real excluded_exercises entries for this injury"
    )

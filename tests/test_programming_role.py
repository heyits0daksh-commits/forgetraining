"""
Regression coverage for programming_role.classify_programming_role.

Neck Bridge bug (fixed): Wrestler's Neck Bridge is the only "Sport Specific"
category exercise in the database that is a static Isometric hold rather
than a live/dynamic drill. classify_programming_role used to route every
"Sport Specific" exercise straight to "Skill / Technical" (session_order_rank
2 - right after the warm-up, before every strength and power lift) with no
check on force_type. neck_bridge_001 is a universal neck/grip add-on
present in essentially every generated session, so this put neck training
second in the running order on every split, directly contradicting the
manual's explicit instruction (repeated in every sport chapter) that the
neck/grip block runs "at the very end of a training day... not before"
heavy pulling/squatting.

These tests pin the corrected behavior so it can't silently regress:
Isometric "Sport Specific" holds go to Core & Stability (after strength),
while every dynamic "Sport Specific" drill keeps going to Skill / Technical
(early, while the CNS is fresh) exactly as before - EXCEPT live striking
drills (movement_pattern == "Strike": heavy bag rounds, shadow boxing,
band-resisted kick drills, etc.) AND live grappling/tackle technique
drilling against a bag/dummy/opponent-simulator (Wrestling Dummy
takedowns, Tackle Bag drills, Judo/BJJ entries and escapes - see
PARTNER_SKILL_EXCLUDED_IDS in programming_role.py), both of which route to
STRIKE_SKILL_EXCLUDED_ROLE instead, for every sport including the sport
they were authored for - see STRIKE_SKILL_EXCLUDED_ROLE's docstring in
programming_role.py for why: this app builds strength & conditioning
programs, and any sport's specific technique is trained separately with an
actual coach, so it's excluded from a generated session entirely rather
than given any strength-training slot.

Bug fixed alongside this: before PARTNER_SKILL_EXCLUDED_IDS existed, these
grappling/tackle drills stayed in "Skill / Technical" and got pulled into
ANY sport whose hand-authored sport_priority score cleared the role floor -
e.g. a Special Forces or HYROX program could come back with BJJ's
"Leg-Lock Defense Mobility Flow" or "Bridge-to-Hip-Escape Flow", technique
that sport has no use for and this app was never a coach for in the first
place.
"""
import json

from backend.core.config import settings
from backend.services.programming_role import (
    PARTNER_SKILL_EXCLUDED_IDS,
    ROLE_RANK,
    STRIKE_SKILL_EXCLUDED_ROLE,
    classify_programming_role,
    session_order_rank,
)


def _load_exercises():
    with open(settings.EXERCISES_JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {ex["id"]: ex for ex in data["exercises"]}


def test_neck_bridge_runs_after_strength_not_as_skill_work():
    exercises = _load_exercises()
    ex = exercises["neck_bridge_001"]
    role, _ = classify_programming_role(ex)
    assert role == "Core & Stability"
    assert session_order_rank(role) > session_order_rank("Primary Strength")


def test_dynamic_sport_specific_drills_still_run_early():
    """Every other 'Sport Specific' exercise (dynamic, non-Isometric, not a
    live striking drill, not a partner/bag technique drill, and not Ruck
    March) must keep sequencing before Primary Strength, same as pre-fix."""
    exercises = _load_exercises()
    dynamic_sport_specific = [
        ex for ex in exercises.values()
        if ex.get("category") == "Sport Specific"
        and ex.get("force_type") != "Isometric"
        and ex.get("movement_pattern") != "Strike"
        and ex["id"] not in PARTNER_SKILL_EXCLUDED_IDS
        and "ruck march" not in ex.get("name", "").lower()
    ]
    assert dynamic_sport_specific, "expected at least one dynamic Sport Specific exercise"
    for ex in dynamic_sport_specific:
        role, _ = classify_programming_role(ex)
        assert role == "Skill / Technical", ex["id"]
        assert session_order_rank(role) < session_order_rank("Primary Strength")


def test_partner_technique_drills_route_to_excluded_role_for_every_sport():
    """Wrestling Dummy / Tackle Bag / Uchikomi / Leg-Lock / Hip-Escape /
    Suplex / clinch-and-footwork bag drills - anything that's really 'drill
    technique X against equipment simulating a partner' - must never get a
    strength-training role, for ANY sport, including the sport it was
    authored for. This is the fix for the reported bug where a Special
    Forces or HYROX program could come back with BJJ leg-lock/hip-escape
    technique it has no use for."""
    exercises = _load_exercises()
    assert PARTNER_SKILL_EXCLUDED_IDS, "expected a non-empty exclusion set"
    for ex_id in PARTNER_SKILL_EXCLUDED_IDS:
        assert ex_id in exercises, ex_id
        role, _ = classify_programming_role(exercises[ex_id])
        assert role == STRIKE_SKILL_EXCLUDED_ROLE, ex_id
        assert role not in ROLE_RANK, "excluded role must stay outside the strength-training ROLE_ORDER"


def test_special_forces_and_hyrox_never_get_bjj_or_judo_technique():
    """Regression test for the exact reported bug: generating a session for
    Special Forces (or HYROX) must never surface BJJ/Judo submission-
    grappling technique drills, regardless of how high their hand-authored
    sport_priority score is for that sport."""
    from backend.models.schemas import WorkoutRequest
    from backend.services.progression_engine import ProgressionEngine

    engine = ProgressionEngine()
    bjj_judo_technique_ids = {
        "leglock_defense_flow_001", "bridge_hipescape_001",
        "judo_uchikomi_001", "shadow_uchikomi_001", "dummy_suplex_001",
    }
    for sport in ("Special Forces", "HYROX"):
        request = WorkoutRequest(
            sport=sport, experience_level="Advanced",
            equipment_available=["Bodyweight", "Barbell", "Dumbbell", "Kettlebell"],
            readiness=80,
        )
        result = engine.generate_session(request)
        picked_ids = {ex["id"] for ex in result["prescribed_workout"]}
        overlap = picked_ids & bjj_judo_technique_ids
        assert not overlap, f"{sport} session included BJJ/Judo technique drills: {overlap}"


def test_strike_drills_route_to_warmup_not_strength_role():
    """Live striking/bag work (movement_pattern == 'Strike') never gets a
    strength-training role (Skill/Technical, Primary Strength, Accessory,
    etc.) for ANY sport, including striking sports themselves - it's
    round-based warm-up material, not loaded sets-and-reps volume."""
    exercises = _load_exercises()
    strike_drills = [ex for ex in exercises.values() if ex.get("movement_pattern") == "Strike"]
    assert strike_drills, "expected at least one Strike movement_pattern exercise"
    for ex in strike_drills:
        role, _ = classify_programming_role(ex)
        assert role == STRIKE_SKILL_EXCLUDED_ROLE, ex["id"]
        assert role not in ROLE_RANK, "warm-up role must stay outside the strength-training ROLE_ORDER"


def test_ruck_march_runs_last_as_conditioning_finisher():
    """Ruck March (any variant) is a single continuous time/distance effort,
    not a technical drill or a carry accessory - it must always route to
    Conditioning / Finisher, the last slot in the running order."""
    exercises = _load_exercises()
    ruck_variants = [ex for ex in exercises.values() if "ruck march" in ex.get("name", "").lower()]
    assert ruck_variants, "expected at least one Ruck March exercise"
    for ex in ruck_variants:
        role, _ = classify_programming_role(ex)
        assert role == "Conditioning / Finisher", ex["id"]
        assert session_order_rank(role) == session_order_rank("Conditioning / Finisher")
        assert session_order_rank(role) > session_order_rank("Primary Strength")


def test_ruck_march_prescribed_by_time_and_distance_not_sets_reps():
    """Ruck March must never come back as sets/reps or sets/distance - it's
    a single continuous effort measured in time and distance, the way an
    actual ruck program (military PT, GORUCK, etc.) prescribes it."""
    from backend.services.progression_engine import ProgressionEngine

    exercises = _load_exercises()
    ruck_variants = [ex for ex in exercises.values() if "ruck march" in ex.get("name", "").lower()]
    assert ruck_variants, "expected at least one Ruck March exercise"
    for ex in ruck_variants:
        prescription = ProgressionEngine._prescribe_volume(ex, readiness_factor=0.8, deload=False)
        assert prescription["type"] == "ruck", ex["id"]
        assert "sets" not in prescription, ex["id"]
        assert "reps" not in prescription, ex["id"]
        assert prescription["distance_km"] > 0
        assert prescription["duration_minutes"] > 0


def test_plank_still_runs_as_a_primer():
    """Front Plank (Core, difficulty 1) is the documented example of a true
    low-load primer and should keep warming the pattern up, not shift."""
    exercises = _load_exercises()
    ex = exercises["plank_001"]
    role, _ = classify_programming_role(ex)
    assert role == "Primer / Activation"
    assert session_order_rank(role) == ROLE_RANK["Primer / Activation"]


# --- Three-tier strength split (v5.23) --------------------------------
#
# Session architecture bug: classify_programming_role used to collapse
# every loaded-strength exercise (Squat/Hinge/Horizontal-Vertical Push/
# Pull) at difficulty >= 3 into a single "Primary Strength" role, so a
# true max-effort barbell lift (difficulty 5) and a goblet squat
# (difficulty 3) got identical sequencing/selection treatment. A real
# coach's session runs Warm-up -> Power -> Primary Strength -> Secondary
# Strength -> Assistance/Accessory -> ... - a distinct "second big lift"
# tier that sits after the day's heaviest lift but before lighter
# accessory work. These tests pin the corrected three-tier split so it
# can't silently regress back to the two-tier collapse.

def test_loaded_strength_splits_into_three_difficulty_tiers():
    """Within the loaded-strength categories, difficulty tier decides
    Primary vs. Secondary vs. Accessory.

    BUG FIXED: this docstring/test used to carve out "high-fatigue_cost
    outliers like a freestanding handstand push-up" as correctly caught
    earlier as Conditioning/Finisher - that was documenting a real bug,
    not a design choice: the fatigue_cost >= 60 check used to fire before
    this branch on ANY category, and every difficulty-5 exercise has
    fatigue_cost 70 regardless of category, so EVERY hardest-tier lift in
    every loaded-strength category (Max Effort Squat, Overhead Squat, Bar
    Muscle-Up, One-Arm Pull-Up, ...) was getting pulled out of Primary
    Strength and run dead last as a "finisher" instead. classify_programming_role
    now only lets the fatigue_cost fallback fire as a last resort, after
    this (and every other specific-category) branch has already had a
    chance - so every loaded-strength exercise, including the hardest
    ones, now actually reaches this branch."""
    exercises = _load_exercises()
    _LOADED_STRENGTH_CATEGORIES = {
        "Horizontal Push", "Vertical Push", "Horizontal Pull", "Vertical Pull",
        "Squat", "Hinge",
    }
    strength_tier_roles = {"Primary Strength", "Secondary Strength", "Accessory / Hypertrophy"}
    loaded = [ex for ex in exercises.values() if ex.get("category") in _LOADED_STRENGTH_CATEGORIES]
    assert loaded, "expected at least one loaded-strength-category exercise"
    seen_roles = set()
    checked = 0
    for ex in loaded:
        role, _ = classify_programming_role(ex)
        if role not in strength_tier_roles:
            continue  # e.g. an explosive Hinge pull (force_type Stretch-Shortening Cycle) correctly caught by the Power & Explosive branch first
        checked += 1
        difficulty = ex.get("difficulty", 1)
        seen_roles.add(role)
        if difficulty >= 4:
            assert role == "Primary Strength", ex["id"]
        elif difficulty == 3:
            assert role == "Secondary Strength", ex["id"]
        else:
            assert role == "Accessory / Hypertrophy", ex["id"]
    assert checked > 0
    # the data actually populates all three tiers, not just two
    assert strength_tier_roles <= seen_roles


def test_secondary_strength_sequences_between_primary_and_accessory():
    assert session_order_rank("Primary Strength") < session_order_rank("Secondary Strength")
    assert session_order_rank("Secondary Strength") < session_order_rank("Accessory / Hypertrophy")
    # and stays after Power/Skill, before Core & Stability / Conditioning,
    # same coaching order every other role already respects
    assert session_order_rank("Power & Explosive") < session_order_rank("Secondary Strength")
    assert session_order_rank("Secondary Strength") < session_order_rank("Core & Stability")


def test_generated_session_respects_full_coaching_order():
    """Live regression for the reported bug: a generated session's roles,
    once sorted by session_order_rank (exactly what generate_session does),
    must never place a later-phase role before an earlier-phase one -
    Primary Strength before Secondary Strength before Accessory, etc."""
    from backend.models.schemas import UserBiometrics, WorkoutRequest
    from backend.services.progression_engine import ProgressionEngine

    engine = ProgressionEngine()
    bio = UserBiometrics(
        height_cm=178, weight_kg=85, bench_press_1rm=110, squat_1rm=150,
        deadlift_1rm=180, pullups_max_reps=12, pushups_max_reps=40, sex="male",
    )
    for minutes in (30, 45, 60, 75, 90):
        request = WorkoutRequest(
            sport="Powerlifting", experience_level="Advanced",
            equipment_available=["Barbell", "Adjustable Bench", "Squat Rack", "Dumbbell", "Pull-Up Bar"],
            session_duration_minutes=minutes, biometrics=bio,
        )
        result = engine.generate_session(request)
        ranks = [ex["session_order_rank"] for ex in result["prescribed_workout"]]
        assert ranks == sorted(ranks), (minutes, ranks)

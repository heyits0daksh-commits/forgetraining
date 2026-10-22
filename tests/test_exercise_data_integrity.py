"""
Data-integrity checks for data/exercises.json, formalizing as real pytest
the ad-hoc verification every generate_batchN script has repeated by hand
in its own docstring (zero duplicate ids, no dangling DAG references, every
equipment type has at least 5 exercises, every exercise carries the full
v4+ field set). Running this as a test means the next batch script's
"Verified: ..." claim is actually checked by CI, not just asserted in prose.
"""
import json

from backend.core.config import settings
from backend.services.injury_taxonomy import INJURY_TAXONOMY

REQUIRED_FIELDS = {
    "id",
    "name",
    "category",
    "movement_pattern",
    "equipment",
    "difficulty",
}

# Single-purpose sport-specific implements that will never realistically
# reach 5 variations - each one exists in the database for exactly the one
# manual exercise that needed it (see add_missing_manual_exercises.py),
# not as a broad equipment category like Barbell/Dumbbell that a real gap
# would be worth flagging for.
_NICHE_EQUIPMENT_EXEMPT = {
    "Speed Bag",
    "Climbing Hold / Hangboard",
    "Partner / Clinch Bag",
    # v5.36 (batch21, generate_batch21_missing_gym_staples.py): six
    # single-purpose gym machines, each introduced for exactly the one
    # exercise that machine performs (a preacher curl machine only does
    # preacher curls; a hip thrust machine only does hip thrusts) - same
    # shape as the three above, not a broad category like Cable Machine
    # or Leg Press Machine that spans many different movements.
    "Calf Raise Machine",
    "Ab Crunch Machine",
    "Preacher Curl Machine",
    "Triceps Dip Machine",
    "Hip Thrust Machine",
    "Assisted Pull-up Machine",
}


def _load_exercises():
    with open(settings.EXERCISES_JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["exercises"]


def test_no_duplicate_ids():
    exercises = _load_exercises()
    ids = [ex["id"] for ex in exercises]
    assert len(ids) == len(set(ids)), "duplicate exercise id(s) found"


def test_every_equipment_type_has_at_least_five_exercises():
    """`equipment` is a single string per exercise (e.g. "Bodyweight"), never
    a list - `for eq in ex.get("equipment", [])` iterated the STRING's
    individual characters instead of counting it as one value, which is why
    this test was previously reporting a bogus equipment type of "/"
    (harvested out of entries like "Partner / Clinch Bag"). Fixed to treat
    equipment as the scalar it actually is.

    With that fixed, 3 equipment types genuinely sit under the 5-exercise
    floor: Speed Bag, Climbing Hold/Hangboard, Partner/Clinch Bag. All three
    are single-purpose sport-specific implements (boxing conditioning, rock
    climbing grip work, combat-sports partner drills respectively) added by
    add_missing_manual_exercises.py specifically to fill a manual-exercise
    gap that had no other equipment match - by nature a one-off, not a
    broad equipment category anyone would expect 5 variations of (unlike
    Barbell/Dumbbell/Kettlebell etc.). _NICHE_EQUIPMENT_EXEMPT documents
    that explicitly rather than silently loosening the floor for everything.
    """
    exercises = _load_exercises()
    counts = {}
    for ex in exercises:
        eq = ex.get("equipment")
        if eq:
            counts[eq] = counts.get(eq, 0) + 1
    thin = {
        eq: n for eq, n in counts.items()
        if n < 5 and eq not in _NICHE_EQUIPMENT_EXEMPT
    }
    assert not thin, f"equipment types under the 5-exercise floor: {thin}"


def test_no_dangling_dag_references():
    exercises = _load_exercises()
    known_ids = {ex["id"] for ex in exercises}
    dangling = []
    for ex in exercises:
        for field in ("progressions", "regressions", "alternatives"):
            for ref in ex.get(field) or []:
                if ref not in known_ids:
                    dangling.append((ex["id"], field, ref))
    assert not dangling, f"dangling DAG references: {dangling[:10]}"


def test_every_exercise_has_required_fields():
    exercises = _load_exercises()
    missing = {
        ex.get("id", "<no id>"): sorted(REQUIRED_FIELDS - ex.keys())
        for ex in exercises
        if not REQUIRED_FIELDS.issubset(ex.keys())
    }
    assert not missing, f"exercises missing required fields: {missing}"


def test_exercise_count_matches_roadmap_claim():
    """data/exercises.json's schema_notes v5.17 (batch15) documented a
    running total of 761. scripts/add_missing_manual_exercises.py ran
    after batch15 (undocumented in schema_notes - it isn't part of the
    numbered batchN/vX.Y narrative) and added 8 more exercises to fill
    manual-exercise gaps tag_manual_exercises.py couldn't match to an
    existing entry (Band-Resisted Kick Drills, Clinch Grip Carries,
    Change-of-Direction 5-10-5, Hill or Stair Sprints, Leg-Lock Defense
    Mobility Flow, Lock-Off Holds, Shuttle Runs (Yo-Yo IR1 style), Speed
    Bag / Double-End Bag) - 761 + 8 = 769. v5.12 (batch16,
    generate_batch16_arms_curl_tricep.py) then added 10 Dumbbell/Barbell/
    Bodyweight bicep-curl and triceps-isolation exercises - 769 + 10 = 779.
    v5.13 (batch17, generate_batch17_curl_variations.py) added 10 more
    biceps curl variations (preacher, spider, drag, Zottman, cross-body
    hammer, cable rope hammer, single-arm cable, 21s, waiter, reverse-grip
    barbell) - 779 + 10 = 789. v5.14 (batch18, generate_batch18_
    triceps_variations.py) added 9 triceps-isolation exercises - 789 + 9 =
    798. v5.15 (batch19, generate_batch19_new_equipment.py) introduced the
    "Adjustable Bench" and "Sit-Up Bench" equipment types with 5 exercises each -
    798 + 10 = 808. v5.16 (batch20, generate_batch20_rehab_mobility.py) added
    20 difficulty-1/2 rehab & mobility exercises closing the early-recovery
    gap for the hip abductor group (Gluteus Medius/Minimus, TFL) plus
    Hamstrings, Quadriceps, Pectoralis Major, Biceps Brachii/Brachialis,
    Triceps Brachii, and the back group - 808 + 20 = 828. A data-integrity
    pass then found "Prone Y-T-W Raise" duplicated under two ids
    (prone_ytw_raise_001, the fuller entry with sport_priority/
    movement_family/progressions populated, and back_prone_ytw_001, a
    thinner duplicate referenced nowhere else in the file) and removed the
    thinner duplicate - 828 - 1 = 827. v5.36 (batch21, generate_batch21_
    missing_gym_staples.py) then added 19 common gym exercises found
    genuinely missing while auditing the FORGE S&C Template Libraries
    against this file for v5.35 (a plain Barbell Shrug, Dumbbell Lateral
    Raise, calf raise machines, an ab crunch machine, the triceps pushdown/
    extension family this file had none of before, a bilateral hip thrust
    family, DB Seated Press, Trap Bar Squat, Landmine Pallof Press, and the
    wrist curl family this file also had none of before) - 827 + 19 = 846,
    the actual current count this test now pins to.
    """
    exercises = _load_exercises()
    assert len(exercises) == 846


def test_every_injuries_to_avoid_tag_resolves_in_taxonomy():
    """v5.11: every injuries_to_avoid string used anywhere in the file must
    exactly match (case-insensitive) an INJURY_TAXONOMY entry name, or
    progression_engine._resolve_injury_severity() silently can't find it and
    that exercise falls back to flat literal-tag matching instead of the
    severity-tiered four-tier risk model every other exercise gets. This
    would have caught the 15/31-tag mismatch fixed in v5.11 - keep it green
    by adding a matching taxonomy entry (see injury_taxonomy.py's "Bare/
    vernacular umbrella terms" section for the pattern) whenever a new
    injuries_to_avoid string is introduced, rather than reusing/inventing an
    ad-hoc one."""
    exercises = _load_exercises()
    taxonomy_lower = {name.lower() for name in INJURY_TAXONOMY}
    unresolved = {}
    for ex in exercises:
        for tag in ex.get("injuries_to_avoid", []):
            if tag.lower() not in taxonomy_lower:
                unresolved.setdefault(tag, []).append(ex["id"])
    assert not unresolved, f"injuries_to_avoid tags with no INJURY_TAXONOMY match: {unresolved}"


def test_injuries_to_avoid_joint_is_in_exercises_joint_stress():
    """v5.21: every injuries_to_avoid tag's own taxonomy `joint` must be
    present in that same exercise's joint_stress list. injury_taxonomy.py's
    anatomy veto (map_injuries_to_avoid.py's _vote/_fallback_top and
    find_alternatives' clears_joints) assumes this holds - a tag whose joint
    isn't in joint_stress is inert for filtering (classify_injury_risk never
    even sees that joint on this exercise) even though the exercise data
    itself claims the injury is relevant, which is a silent contradiction
    rather than a working exclusion. Fixed for the 11 exercises this caught
    at introduction (see scripts/data_ops/fix_joint_stress_gaps.py) - keep
    green by adding the missing joint_stress tag (not by editing the
    taxonomy's joint mapping, which is the deliberately-curated side)."""
    exercises = _load_exercises()
    taxonomy_joint = {name: entry["joint"] for name, entry in INJURY_TAXONOMY.items()}
    mismatches = {}
    for ex in exercises:
        js = set(ex.get("joint_stress", []))
        for tag in ex.get("injuries_to_avoid", []):
            joint = taxonomy_joint.get(tag)
            if joint and joint not in js:
                mismatches.setdefault(ex["id"], []).append((tag, joint))
    assert not mismatches, (
        f"exercises whose injuries_to_avoid tag names a joint missing from "
        f"their own joint_stress: {mismatches}"
    )


def test_back_squat_family_flags_shoulder_and_offers_shoulder_safe_swap():
    """v5.22: straight-bar back-squat variants (bar racked across the traps,
    requiring shoulder extension/external rotation) must carry 'Shoulder' in
    joint_stress - without it, the injury-safety engine never considers
    these risky for a shoulder injury at all (see
    scripts/data_ops/add_shoulder_friendly_swaps.py). Each must also declare
    at least one genuinely shoulder-joint-stress-free alternative (Belt
    Squat / Belt Squat Machine / Goblet Squat / Landmine Squat), not just a
    same-problem swap like Safety Squat Bar (which still carries its own
    'Shoulder' tag from the yoke resting on the shoulder girdle)."""
    exercises = _load_exercises()
    by_id = {ex["id"]: ex for ex in exercises}
    shoulder_free_squat_swaps = {
        "beltsquat_001", "belt_squat_machine_001", "db_goblet_squat_001", "landmine_squat_001",
    }
    back_squat_family = [
        "bb_back_squat_001", "highbar_backsquat_001", "lowbar_backsquat_001",
        "pause_backsquat_001", "tempo_backsquat_001", "banded_backsquat_001",
        "chain_backsquat_001", "reverseband_squat_001", "accommodating_squat_001",
        "dynamiceffort_squat_001", "maxeffort_squat_001", "monolift_squat_001",
        "speed_squat_001", "concentric_box_squat_001", "narrow_stance_squat_001",
        "wide_stance_squat_001",
    ]
    for eid in back_squat_family:
        ex = by_id[eid]
        assert "Shoulder" in ex.get("joint_stress", []), f"{eid} missing Shoulder joint_stress"
        alts = set(ex.get("alternatives", []))
        assert alts & shoulder_free_squat_swaps, f"{eid} has no shoulder-safe declared alternative"


def test_shoulder_loaded_barbell_lifts_declare_an_alternative():
    """v5.22: every barbell bench/press/row/deadlift exercise this batch
    touched must have at least one declared alternative (never left at [])
    so a shoulder-injury user actually gets a coach-plausible swap offered,
    not just whatever the same-pattern fallback pool happens to contain."""
    exercises = _load_exercises()
    by_id = {ex["id"]: ex for ex in exercises}
    touched = [
        "floor_press_001", "flat_bench_001", "incline_bench_001", "decline_bench_001",
        "closegrip_bench_001", "widegrip_bench_001", "reversegrip_bench_001",
        "spoto_press_001", "larsen_press_001", "board_press_001", "guillotine_press_001",
        "slingshot_bench_001", "chain_bench_001", "speed_bench_001",
        "bb_closegripfloorpress_001", "bb_jmpress_001",
        "bb_overhead_press_001", "push_press_001", "push_jerk_001", "split_jerk_001",
        "strict_press_001", "military_press_001", "zpress_001", "bradford_press_001",
        "behindneck_press_001",
        "bb_bent_over_row_001", "pendlay_row_001", "meadows_row_001", "yates_row_001",
        "singlearm_bb_row_001", "inverted_row_bent_001", "inverted_row_straight_001",
        "bb_deadlift_001", "zercher_deadlift_001",
    ]
    for eid in touched:
        assert by_id[eid].get("alternatives"), f"{eid} has no declared alternatives"

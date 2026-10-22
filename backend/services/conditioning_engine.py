"""
conditioning_engine.py — real equipment/injury gating AND per-athlete
prescription scaling for the 85 FORGE S&C Template exercise-name
references that forge_category_audit.md's Category A classifies as
"genuinely out of scope by design" for exercises.json: ruck marches,
compromised runs, race-load carries/sleds, wall-ball/rower/SkiErg/bike
intervals, running-zone work, swim drills, hangboard/campus-board/
bouldering, combat-sports rounds, tackle/scrum drives, and multi-exercise
complexes. None of those are single discrete lifts that belong in
exercises.json's biomechanical schema (same reasoning the audit gives) —
but that doesn't mean they should just pass through unchecked.

WHAT WAS HAPPENING BEFORE THIS MODULE
build_template_fidelity_program (program_builder.py) resolves every
template exercise name against exercises.json (exact match, then
sc_template_library.fuzzy_resolve_exercise_name). When a name fails BOTH
of those — which is exactly what happens for all 85 names here — it falls
all the way through to `verified: False`, passed to the athlete completely
unchecked: no equipment check, no injury check, no scaling to their
experience level. A "Heavy Sled Push — Overload (110-125% race load)" is
handed to someone with a Grade 2 knee sprain exactly as written, with
zero gate in between.

WHAT THIS MODULE ADDS
`resolve_conditioning_exercise` gives each of those 85 names the same two
things a real exercises.json entry gets in build_template_fidelity_program:
  1. A gate — `_conditioning_block_reason` runs the identical four-tier
     equipment/severity/difficulty/systemic-injury check
     `_template_exercise_block_reason` runs for real exercises, just
     against a lightweight equivalent shape stored in CONDITIONING_PROTOCOLS
     instead of a full exercises.json entry (equipment, joint_stress,
     difficulty — the only three fields that logic actually reads).
  2. A prescription — `prescribe_conditioning` generates the actual
     distance/duration/load/rest scheme for THIS athlete's
     experience_level and training phase, instead of only ever handing
     back the template author's one fixed number. Scaling is intentionally
     conservative and table-driven (see _EXPERIENCE_MULTIPLIER/_PHASE_
     MULTIPLIER below) rather than trying to model true conditioning
     periodization — the goal is "an appropriately-sized dose for this
     person right now," not a full aerobic/lactic training-plan engine.

WHY THE GATE LOGIC IS DUPLICATED HERE INSTEAD OF IMPORTED
`_template_exercise_block_reason` lives in program_builder.py, and
program_builder.py is the module that needs to call INTO this one (to
resolve a name build_template_fidelity_program couldn't otherwise place)
— importing the other direction would be circular. Same reasoning
program_builder.py's own module comment already gives for duplicating
ProgressionEngine's four injury resolvers rather than restructuring
around the circular import; this follows that established pattern rather
than introducing a new one. `_conditioning_block_reason` below is a pure
function of (protocol, equipment/injury state) with no shared mutable
state, so the duplication carries the same low risk it does there.

WHAT THIS MODULE DELIBERATELY DOES NOT DO
- No `injuries_to_avoid` named-injury override list (unlike real
  exercises.json entries) — getting a specific taxonomy injury NAME wrong
  fails silently (an unmatched string just never excludes anything), so
  rather than guess spellings, every protocol here relies on the graduated
  joint_stress + difficulty + severity check alone, same as any
  exercises.json entry with an empty injuries_to_avoid list. A severity-3
  ("severe") injury on any tagged joint still excludes outright regardless
  of difficulty (SEVERITY_DIFFICULTY_CEILING[3] is None) — that part of the
  safety net doesn't depend on this list at all.
- No true periodized progression (no week-by-week ramp persisted across
  a mesocycle the way progression_engine.py tracks for lifts). `phase` is
  a single explicit argument the caller supplies per call, not state this
  module tracks — good enough for "scale today's prescription," not a
  replacement for a real conditioning periodization model.
"""

from typing import Dict, List, Optional

from backend.services.injury_taxonomy import classify_injury_risk
from backend.services.sc_template_library import normalize_exercise_name

# ==========================================================================
# FAMILY CODES — the audit's own 7 Category A groupings, kept as a closed
# set so callers (and this module's own display fields) can filter/report
# by family without re-deriving it from load_type.
# ==========================================================================
FAMILY_RUCK_RACE_LOAD = "ruck_race_load"
FAMILY_SLED_SPRINT = "sled_sprint"
FAMILY_WALL_BALL_ERG = "wall_ball_erg"
FAMILY_RUNNING_ZONE = "running_zone"
FAMILY_SWIM = "swim"
FAMILY_CLIMBING = "climbing"
FAMILY_COMBAT_TACKLE_COMPLEX = "combat_tackle_complex"

_FAMILY_ENERGY_SYSTEM: Dict[str, str] = {
    FAMILY_RUCK_RACE_LOAD: "strength_endurance",
    FAMILY_SLED_SPRINT: "power",
    FAMILY_WALL_BALL_ERG: "lactic",
    FAMILY_RUNNING_ZONE: "aerobic",
    FAMILY_SWIM: "mixed",
    FAMILY_CLIMBING: "strength_endurance",
    FAMILY_COMBAT_TACKLE_COMPLEX: "lactic",
}

_FAMILY_LABEL: Dict[str, str] = {
    FAMILY_RUCK_RACE_LOAD: "Ruck / race-load carry",
    FAMILY_SLED_SPRINT: "Sled / sprint conditioning",
    FAMILY_WALL_BALL_ERG: "Wall ball / erg / bike conditioning",
    FAMILY_RUNNING_ZONE: "Running - zone conditioning",
    FAMILY_SWIM: "Swim conditioning",
    FAMILY_CLIMBING: "Climbing - hangboard / bouldering",
    FAMILY_COMBAT_TACKLE_COMPLEX: "Combat rounds / tackle / complex",
}


# ==========================================================================
# REGISTRY — one entry per Category A name (see forge_category_audit.md).
# Deliberately NOT the 86th name, "Sled Push (Heavy)": that one turned out
# to be a wording variant of a real exercises.json lift (Heavy Sled Push)
# and was added to sc_template_library._DISAMBIGUATED_ALIASES instead, so
# it now resolves to real exercise data before this module is ever
# consulted (see that file's "push sled" hint entry).
#
# Each entry:
#   name            - exact template exercise-name string (the audit's
#                     verbatim wording), also the dict key's un-normalized
#                     source
#   family          - one of the FAMILY_* constants above
#   load_type       - which _PRESCRIPTION_BUILDERS function applies
#   equipment       - single primary equipment string, checked the same
#                     way _template_exercise_block_reason checks a real
#                     exercise's `equipment` field
#   difficulty      - 1-5, feeds classify_injury_risk exactly like a real
#                     exercise's `difficulty` field
#   joint_stress    - tuple of canonical joint tags (the same 8 tags
#                     exercises.json/injury_taxonomy.py use: Ankle, Elbow,
#                     Hip, Knee, Lower Back, Neck, Shoulder, Wrist)
#   params          - load_type-specific baseline numbers, scaled by
#                     prescribe_conditioning
#   reference_count - how many times this name is used across all
#                     templates (from the audit; carried through purely
#                     for display/prioritization, never read by the gate
#                     or the prescription builders)
#   requires_supervision / safety_note - set only on the handful of swim
#                     entries the audit itself flagged
#                     buddy-supervised/coached; surfaced verbatim in the
#                     resolved output so a caller can't silently drop it
CONDITIONING_PROTOCOLS: Dict[str, Dict] = {}


def _add(name: str, family: str, load_type: str, equipment: str, difficulty: int,
         joint_stress: tuple, params: Dict, reference_count: int,
         requires_supervision: bool = False, safety_note: Optional[str] = None) -> None:
    key = normalize_exercise_name(name)
    CONDITIONING_PROTOCOLS[key] = {
        "name": name,
        "family": family,
        "family_label": _FAMILY_LABEL[family],
        "energy_system": _FAMILY_ENERGY_SYSTEM[family],
        "load_type": load_type,
        "equipment": equipment,
        "difficulty": difficulty,
        "joint_stress": list(joint_stress),
        "params": dict(params),
        "reference_count": reference_count,
        "requires_supervision": requires_supervision,
        "safety_note": safety_note,
    }


# --- Ruck / compromised-run / race-load protocols ---
_add("Ruck March (steady pace)", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Ruck Vest", 2,
     ("Knee", "Hip", "Lower Back"), dict(distance_m=6000, load_pct_race=100, sets=1, rest_s=0), 124)
_add("Compromised Run 1km (post-station, race distance)", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Bodyweight", 3,
     ("Knee", "Ankle", "Hip"), dict(distance_m=1000, load_pct_race=100, sets=1, rest_s=0), 108)
_add("Compromised Run 400m (post-station)", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Bodyweight", 3,
     ("Knee", "Ankle", "Hip"), dict(distance_m=400, load_pct_race=100, sets=1, rest_s=0), 107)
_add("Compromised Run 800m (post-station)", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Bodyweight", 3,
     ("Knee", "Ankle", "Hip"), dict(distance_m=800, load_pct_race=100, sets=1, rest_s=0), 105)
_add("Heavy Sled Push — Overload (110-125% race load)", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Sled", 4,
     ("Knee", "Hip", "Lower Back"), dict(distance_m=25, load_pct_race=118, sets=4, rest_s=150), 40)
_add("Heavy Farmers Carry — Overload (110-125% race load)", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Farmer Handles", 4,
     ("Lower Back", "Shoulder", "Wrist"), dict(distance_m=25, load_pct_race=118, sets=4, rest_s=150), 28)
_add("Heavy Sled Pull — Overload (110-125% race load)", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Sled", 4,
     ("Knee", "Hip", "Lower Back"), dict(distance_m=25, load_pct_race=118, sets=4, rest_s=150), 27)
_add("Sandbag Lunges — Overload (110-120% race load)", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Sandbag", 4,
     ("Knee", "Hip", "Lower Back"), dict(distance_m=20, load_pct_race=115, sets=3, rest_s=120), 27)
_add("Sled Pull — Race Distance/Load", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Sled", 3,
     ("Knee", "Hip", "Lower Back"), dict(distance_m=25, load_pct_race=100, sets=3, rest_s=120), 27)
_add("Sandbag Lunges — Race Distance/Load", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Sandbag", 3,
     ("Knee", "Hip", "Lower Back"), dict(distance_m=20, load_pct_race=100, sets=3, rest_s=120), 27)
_add("Farmers Carry — Race Distance/Load", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Farmer Handles", 3,
     ("Lower Back", "Shoulder", "Wrist"), dict(distance_m=25, load_pct_race=100, sets=3, rest_s=120), 27)
_add("Farmers Carry + Run Brick (100m carry into 200m run)", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Farmer Handles", 3,
     ("Lower Back", "Shoulder", "Knee"), dict(distance_m=300, load_pct_race=100, sets=3, rest_s=120), 25)
_add("Burpee Broad Jumps — Race Distance/Reps", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Bodyweight", 3,
     ("Knee", "Ankle", "Shoulder"), dict(distance_m=25, load_pct_race=100, sets=3, rest_s=90), 19)
_add("Yoke Walk (Approach-Load Simulation)", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Yoke", 4,
     ("Lower Back", "Hip", "Knee"), dict(distance_m=20, load_pct_race=110, sets=4, rest_s=150), 16)
_add("Ruck-On Stair Climb", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Ruck Vest", 3,
     ("Knee", "Hip", "Ankle"), dict(duration_s=600, load_pct_race=100, sets=1, rest_s=0), 15)
_add("Hill Ruck Repeats", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Ruck Vest", 4,
     ("Knee", "Hip", "Ankle"), dict(distance_m=200, load_pct_race=100, sets=5, rest_s=180), 5)
_add("Ruck-On Lunges", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Ruck Vest", 4,
     ("Knee", "Hip", "Lower Back"), dict(distance_m=20, load_pct_race=100, sets=3, rest_s=120), 3)
_add("Sled Push — Race Distance/Load", FAMILY_RUCK_RACE_LOAD, "race_load_carry", "Sled", 3,
     ("Knee", "Hip", "Lower Back"), dict(distance_m=25, load_pct_race=100, sets=3, rest_s=120), 39)

# --- Sled/sprint conditioning ---
_add("Sled Drag", FAMILY_SLED_SPRINT, "sled_sprint", "Sled", 2,
     ("Knee", "Hip", "Lower Back"), dict(distance_m=20, load_pct_bw=50, reps=6, rest_s=90), 59)
_add("Sled Push", FAMILY_SLED_SPRINT, "sled_sprint", "Sled", 2,
     ("Knee", "Hip", "Lower Back"), dict(distance_m=20, load_pct_bw=50, reps=6, rest_s=90), 51)
_add("5-10-5 Shuttle (Sled-Resisted)", FAMILY_SLED_SPRINT, "shuttle_ladder", "Sled", 3,
     ("Knee", "Ankle", "Hip"), dict(steps_m=[5, 10, 5], load_pct_bw=20, rounds=5, rest_s=90), 46)
_add("Sled Push Ladder (25m-50m-25m)", FAMILY_SLED_SPRINT, "shuttle_ladder", "Sled", 3,
     ("Knee", "Hip", "Lower Back"), dict(steps_m=[25, 50, 25], load_pct_bw=40, rounds=1, rest_s=120), 41)
_add("Heavy Sled Sprint (Acceleration Overload)", FAMILY_SLED_SPRINT, "sled_sprint", "Sled", 4,
     ("Knee", "Hip", "Ankle"), dict(distance_m=20, load_pct_bw=70, reps=5, rest_s=180), 39)
_add("Resisted Sled Sprint (Light Load)", FAMILY_SLED_SPRINT, "sled_sprint", "Sled", 2,
     ("Knee", "Hip", "Ankle"), dict(distance_m=20, load_pct_bw=15, reps=6, rest_s=90), 36)
_add("Resistance-Band Resisted Sprint", FAMILY_SLED_SPRINT, "sled_sprint", "Resistance Band", 2,
     ("Knee", "Hip", "Ankle"), dict(distance_m=20, load_pct_bw=10, reps=6, rest_s=90), 36)
_add("Prowler Sprint", FAMILY_SLED_SPRINT, "sled_sprint", "Sled", 3,
     ("Knee", "Hip", "Ankle"), dict(distance_m=20, load_pct_bw=35, reps=6, rest_s=120), 16)
_add("Sled Sprint (light)", FAMILY_SLED_SPRINT, "sled_sprint", "Sled", 2,
     ("Knee", "Hip", "Ankle"), dict(distance_m=20, load_pct_bw=15, reps=6, rest_s=90), 15)
_add("Sled Pull Ladder (25m-50m-25m)", FAMILY_SLED_SPRINT, "shuttle_ladder", "Sled", 3,
     ("Knee", "Hip", "Lower Back"), dict(steps_m=[25, 50, 25], load_pct_bw=40, rounds=1, rest_s=120), 26)

# --- Wall ball / rowing / SkiErg / jump-rope conditioning ---
_add("Wall Balls — Race Reps", FAMILY_WALL_BALL_ERG, "erg_interval", "Medicine Ball", 3,
     ("Knee", "Shoulder", "Lower Back"), dict(reps=75, target_pct_race_pace=100, rounds=1, rest_s=0), 48)
_add("Wall Ball Ladder (25-50-25 reps)", FAMILY_WALL_BALL_ERG, "shuttle_ladder", "Medicine Ball", 3,
     ("Knee", "Shoulder", "Lower Back"), dict(steps_m=[25, 50, 25], load_pct_bw=0, rounds=1, rest_s=120), 48)
_add("Wall Ball EMOM (10-15 reps/min)", FAMILY_WALL_BALL_ERG, "erg_interval", "Medicine Ball", 3,
     ("Knee", "Shoulder", "Lower Back"), dict(reps=12, target_pct_race_pace=100, rounds=10, rest_s=0), 44)
_add("Rower Intervals", FAMILY_WALL_BALL_ERG, "erg_interval", "Rowing Erg", 2,
     ("Lower Back", "Shoulder", "Knee"), dict(distance_m=500, target_pct_race_pace=90, rounds=5, rest_s=120), 47)
_add("SkiErg 500m Repeats (Power)", FAMILY_WALL_BALL_ERG, "erg_interval", "SkiErg", 3,
     ("Shoulder", "Lower Back"), dict(distance_m=500, target_pct_race_pace=95, rounds=5, rest_s=150), 42)
_add("Jump Rope Intervals", FAMILY_WALL_BALL_ERG, "erg_interval", "Jump Rope", 2,
     ("Ankle", "Knee"), dict(duration_s=60, target_pct_race_pace=100, rounds=8, rest_s=30), 41)
_add("SkiErg Technique Pyramid (250-500-750-500-250m)", FAMILY_WALL_BALL_ERG, "shuttle_ladder", "SkiErg", 2,
     ("Shoulder", "Lower Back"), dict(steps_m=[250, 500, 750, 500, 250], load_pct_bw=0, rounds=1, rest_s=90), 39)
_add("SkiErg 1000m @ Race Pace", FAMILY_WALL_BALL_ERG, "erg_interval", "SkiErg", 3,
     ("Shoulder", "Lower Back"), dict(distance_m=1000, target_pct_race_pace=100, rounds=1, rest_s=0), 39)
_add("Row 500m Repeats (Power)", FAMILY_WALL_BALL_ERG, "erg_interval", "Rowing Erg", 3,
     ("Lower Back", "Shoulder", "Knee"), dict(distance_m=500, target_pct_race_pace=95, rounds=5, rest_s=150), 28)
_add("Row Technique Pyramid (250-500-750-500-250m)", FAMILY_WALL_BALL_ERG, "shuttle_ladder", "Rowing Erg", 2,
     ("Lower Back", "Shoulder", "Knee"), dict(steps_m=[250, 500, 750, 500, 250], load_pct_bw=0, rounds=1, rest_s=90), 27)
_add("Row 1000m @ Race Pace", FAMILY_WALL_BALL_ERG, "erg_interval", "Rowing Erg", 3,
     ("Lower Back", "Shoulder", "Knee"), dict(distance_m=1000, target_pct_race_pace=100, rounds=1, rest_s=0), 25)
_add("Assault Bike Intervals", FAMILY_WALL_BALL_ERG, "erg_interval", "Assault Bike", 3,
     ("Knee", "Hip"), dict(duration_s=30, target_pct_race_pace=100, rounds=8, rest_s=60), 25)
_add("Burpee Broad Jump EMOM", FAMILY_WALL_BALL_ERG, "erg_interval", "Bodyweight", 4,
     ("Knee", "Ankle", "Shoulder"), dict(reps=5, target_pct_race_pace=100, rounds=10, rest_s=0), 21)
_add("Burpee Broad Jump Ladder (20m-40m-20m)", FAMILY_WALL_BALL_ERG, "shuttle_ladder", "Bodyweight", 4,
     ("Knee", "Ankle", "Shoulder"), dict(steps_m=[20, 40, 20], load_pct_bw=0, rounds=1, rest_s=120), 20)

# --- Running/zone conditioning ---
_add("Long Steady Run", FAMILY_RUNNING_ZONE, "zone_run", "Bodyweight", 1,
     ("Knee", "Ankle", "Hip"), dict(duration_min=40, hr_zone=2), 40)
_add("Easy Zone 2 Run", FAMILY_RUNNING_ZONE, "zone_run", "Bodyweight", 1,
     ("Knee", "Ankle", "Hip"), dict(duration_min=35, hr_zone=2), 40)
_add("Threshold Intervals (Zone 4, 3-6min reps)", FAMILY_RUNNING_ZONE, "zone_run", "Bodyweight", 3,
     ("Knee", "Ankle", "Hip"), dict(duration_min=4, hr_zone=4, rounds=4, rest_s=120), 30)
_add("Tempo Run (Zone 3)", FAMILY_RUNNING_ZONE, "zone_run", "Bodyweight", 2,
     ("Knee", "Ankle", "Hip"), dict(duration_min=25, hr_zone=3), 30)

# --- Swim drills ---
_add("Freestyle Interval Swim", FAMILY_SWIM, "swim", "Pool", 2,
     ("Shoulder",), dict(distance_m=100, rounds=8, rest_s=30), 116)
_add("Combat Sidestroke Drill", FAMILY_SWIM, "swim", "Pool", 2,
     ("Shoulder", "Neck"), dict(distance_m=50, rounds=6, rest_s=30), 25)
_add("Underwater Distance Swim (buddy-supervised only)", FAMILY_SWIM, "swim", "Pool", 4,
     ("Shoulder",), dict(distance_m=25, rounds=4, rest_s=60), 25, requires_supervision=True,
     safety_note=("Breath-hold work carries a drowning risk (shallow-water/hypoxic blackout) "
                  "even for strong swimmers - never trained alone, always with a dedicated "
                  "in-water spotter watching only this swimmer."))
_add("Tread Water (weighted vest, coached)", FAMILY_SWIM, "swim", "Pool", 3,
     ("Shoulder", "Hip"), dict(duration_s=120, rounds=3, rest_s=60), 25, requires_supervision=True,
     safety_note=("Added load changes buoyancy and fatigue-to-failure timing - run under a "
                  "coach who can pull the vest/end the set, not solo."))
_add("Fin Kick Sets", FAMILY_SWIM, "swim", "Pool", 2,
     ("Ankle", "Hip"), dict(distance_m=50, rounds=6, rest_s=30), 25)
_add("Pool-Based Med-Ball Throw", FAMILY_SWIM, "swim", "Pool", 2,
     ("Shoulder",), dict(reps=10, rounds=3, rest_s=60), 15)
_add("Swim Sprint Intervals", FAMILY_SWIM, "swim", "Pool", 3,
     ("Shoulder",), dict(distance_m=50, rounds=8, rest_s=45), 6)
_add("Surface Dive Practice (coached)", FAMILY_SWIM, "swim", "Pool", 3,
     ("Shoulder", "Neck"), dict(reps=8, rounds=1, rest_s=30), 5, requires_supervision=True,
     safety_note=("Head-first entries and breath control around a pool floor/obstacle need "
                  "direct coaching supervision, not solo practice."))
_add("Vertical Kick Hold (coached)", FAMILY_SWIM, "swim", "Pool", 3,
     ("Hip", "Ankle"), dict(duration_s=60, rounds=4, rest_s=45), 5, requires_supervision=True,
     safety_note=("A weighted/fatigue-limit hold in deep water needs a coach positioned to "
                  "assist if the swimmer can no longer stay above the surface."))

# --- Climbing (hangboard / campus board / bouldering / route-specific) ---
_add("Pinch Block Hang", FAMILY_CLIMBING, "hang_climb", "Climbing Hangboard", 4,
     ("Elbow", "Wrist"), dict(hang_duration_s=10, edge_mm=None, sets=5, rest_s=180), 36)
_add("Sloper Hang (Fingerboard Sloper Rail)", FAMILY_CLIMBING, "hang_climb", "Climbing Hangboard", 4,
     ("Elbow", "Wrist", "Shoulder"), dict(hang_duration_s=10, edge_mm=None, sets=5, rest_s=180), 36)
_add("Three-Finger Drag Hang", FAMILY_CLIMBING, "hang_climb", "Climbing Hangboard", 4,
     ("Elbow", "Wrist"), dict(hang_duration_s=10, edge_mm=20, sets=5, rest_s=180), 29)
_add("Open-Hand Edge Hang", FAMILY_CLIMBING, "hang_climb", "Climbing Hangboard", 3,
     ("Elbow", "Wrist"), dict(hang_duration_s=10, edge_mm=20, sets=5, rest_s=180), 29)
_add("4x4 Boulder Circuit (On-the-Minute)", FAMILY_CLIMBING, "hang_climb", "Climbing Hold / Hangboard", 4,
     ("Elbow", "Wrist", "Shoulder"), dict(hang_duration_s=240, edge_mm=None, sets=4, rest_s=240), 23)
_add("Forearm Pump Circuit (Fingerboard + Pull-Up)", FAMILY_CLIMBING, "hang_climb", "Climbing Hangboard", 3,
     ("Elbow", "Wrist", "Shoulder"), dict(hang_duration_s=20, edge_mm=None, sets=4, rest_s=90), 22)
_add("Hangboard Max Hang (10-14mm edge)", FAMILY_CLIMBING, "hang_climb", "Climbing Hangboard", 4,
     ("Elbow", "Wrist"), dict(hang_duration_s=7, edge_mm=12, sets=6, rest_s=180), 21)
_add("Campus Board Ladders (Match)", FAMILY_CLIMBING, "hang_climb", "Campus Board", 5,
     ("Elbow", "Wrist", "Shoulder"), dict(hang_duration_s=0, edge_mm=None, sets=6, rest_s=180), 12)
_add("Limit Bouldering (Max Move)", FAMILY_CLIMBING, "hang_climb", "Climbing Hold / Hangboard", 5,
     ("Elbow", "Wrist", "Shoulder", "Knee"), dict(hang_duration_s=0, edge_mm=None, sets=6, rest_s=180), 12)
_add("Campus-to-Board Power-Endurance Circuit", FAMILY_CLIMBING, "hang_climb", "Campus Board", 5,
     ("Elbow", "Wrist", "Shoulder"), dict(hang_duration_s=180, edge_mm=None, sets=4, rest_s=180), 12)
_add("Campus Board Endurance Ladders", FAMILY_CLIMBING, "hang_climb", "Campus Board", 4,
     ("Elbow", "Wrist", "Shoulder"), dict(hang_duration_s=120, edge_mm=None, sets=4, rest_s=150), 12)
_add("Dyno Practice (Two-Hand)", FAMILY_CLIMBING, "hang_climb", "Climbing Hold / Hangboard", 5,
     ("Elbow", "Wrist", "Shoulder"), dict(hang_duration_s=0, edge_mm=None, sets=6, rest_s=180), 12)
_add("Hangboard Min-Edge Hang (7-10mm)", FAMILY_CLIMBING, "hang_climb", "Climbing Hangboard", 5,
     ("Elbow", "Wrist"), dict(hang_duration_s=6, edge_mm=8, sets=6, rest_s=180), 9)
_add("Campus Board Bumps", FAMILY_CLIMBING, "hang_climb", "Campus Board", 5,
     ("Elbow", "Wrist", "Shoulder"), dict(hang_duration_s=0, edge_mm=None, sets=6, rest_s=180), 9)
_add("ARC Traverse (Low-Intensity Continuous)", FAMILY_CLIMBING, "hang_climb", "Climbing Hold / Hangboard", 2,
     ("Elbow", "Wrist"), dict(hang_duration_s=900, edge_mm=None, sets=1, rest_s=0), 17)
_add("Systems-Board Route Simulation", FAMILY_CLIMBING, "hang_climb", "Systems Board", 3,
     ("Elbow", "Wrist", "Shoulder"), dict(hang_duration_s=300, edge_mm=None, sets=3, rest_s=180), 13)

# --- Combat sports rounds/rounds-based skill work ---
_add("Shadowboxing Rounds", FAMILY_COMBAT_TACKLE_COMPLEX, "rounds", "Bodyweight", 1,
     ("Shoulder",), dict(round_count=5, round_length_s=180, rest_s=60), 29)
_add("Heavy Bag Rounds", FAMILY_COMBAT_TACKLE_COMPLEX, "rounds", "Boxing Heavy Bag", 2,
     ("Shoulder", "Wrist"), dict(round_count=5, round_length_s=180, rest_s=60), 20)
_add("Sparring-Pace Bag Rounds", FAMILY_COMBAT_TACKLE_COMPLEX, "rounds", "Boxing Heavy Bag", 3,
     ("Shoulder", "Wrist"), dict(round_count=5, round_length_s=180, rest_s=60), 17)
_add("Focus-Mitt Rounds", FAMILY_COMBAT_TACKLE_COMPLEX, "rounds", "Focus Mitts", 2,
     ("Shoulder", "Wrist"), dict(round_count=5, round_length_s=180, rest_s=60), 12)

# --- Sport-specific tackle/scrum drills ---
_add("Tackle-Bag Drive (Sled-Loaded)", FAMILY_COMBAT_TACKLE_COMPLEX, "rounds", "Tackle Bag", 3,
     ("Neck", "Shoulder", "Lower Back", "Knee"), dict(round_count=6, round_length_s=10, rest_s=60), 51)
_add("Scrum-Sled Drive (Team/Machine)", FAMILY_COMBAT_TACKLE_COMPLEX, "rounds", "Sled", 4,
     ("Neck", "Shoulder", "Lower Back", "Knee"), dict(round_count=6, round_length_s=10, rest_s=90), 20)
_add("Wrestle-Up to Sled Drive Complex", FAMILY_COMBAT_TACKLE_COMPLEX, "rounds", "Wrestling Dummy", 4,
     ("Neck", "Shoulder", "Lower Back", "Knee"), dict(round_count=5, round_length_s=15, rest_s=90), 28)

# --- Multi-exercise "complex"/circuit bundles ---
_add("Sandbag Complex (carry+clean+squat)", FAMILY_COMBAT_TACKLE_COMPLEX, "complex", "Sandbag", 3,
     ("Lower Back", "Knee", "Shoulder"), dict(work_s=45, rounds=4, rest_s=60), 15)
_add("Sandbag Carry Circuit", FAMILY_COMBAT_TACKLE_COMPLEX, "complex", "Sandbag", 3,
     ("Lower Back", "Knee", "Shoulder"), dict(work_s=45, rounds=4, rest_s=60), 15)
_add("Landmine Complex (row+press+rotation)", FAMILY_COMBAT_TACKLE_COMPLEX, "complex", "Landmine", 2,
     ("Shoulder", "Lower Back"), dict(work_s=45, rounds=4, rest_s=60), 9)
# "KB Complex (swing+goblet squat+carry)" and "Kettlebell Complex" both
# normalize to the same key ("kb" expands to "kettlebell" and the
# parenthetical is dropped) - genuinely the same movement under two
# template spellings, not a false collision, so one shared entry covers
# both rather than the two silently overwriting each other. reference_count
# is the sum of both (9 + 5); resolve_conditioning_exercise always returns
# the CALLER's own original ex_entry name for display, so which spelling a
# given template used is never lost even though the registry has one entry.
_add("Kettlebell Complex", FAMILY_COMBAT_TACKLE_COMPLEX, "complex", "Kettlebell", 3,
     ("Lower Back", "Knee", "Shoulder"), dict(work_s=45, rounds=4, rest_s=60), 14)
_add("Trap-Bar Complex (deadlift+jump+carry)", FAMILY_COMBAT_TACKLE_COMPLEX, "complex", "Trap Bar", 4,
     ("Lower Back", "Knee", "Hip"), dict(work_s=45, rounds=4, rest_s=90), 7)
_add("Farmer's Carry Shuttle", FAMILY_COMBAT_TACKLE_COMPLEX, "complex", "Farmer Handles", 3,
     ("Lower Back", "Shoulder", "Wrist"), dict(work_s=30, rounds=5, rest_s=60), 5)

del _add


def resolve_conditioning_protocol(name: str) -> Optional[Dict]:
    """Exact-normalized lookup only (unlike fuzzy_resolve_exercise_name's
    equipment-word-diff fallback for lifts) - every name in
    CONDITIONING_PROTOCOLS is copied verbatim from a real template's own
    wording, so there's no "coach's wording differs from the database's"
    gap here to bridge. Returns a COPY of the registry entry so a caller
    can freely add per-call fields (prescription, verified, etc.) without
    mutating the shared registry."""
    entry = CONDITIONING_PROTOCOLS.get(normalize_exercise_name(name))
    return dict(entry) if entry else None


# ==========================================================================
# GATE — same shape as program_builder._template_exercise_block_reason,
# against a conditioning-protocol entry instead of an exercises.json entry.
# ==========================================================================

def _conditioning_block_reason(
    protocol: Dict,
    user_equipment: set,
    injury_joint_severity: Dict[str, int],
    injury_joint_tissue: Dict[str, str],
    injury_joint_stage: Dict[str, str],
    injury_joint_side: Dict[str, str],
    systemic_severity: Optional[int],
    systemic_stage: Optional[str],
) -> Optional[str]:
    """None if `protocol` is safe and equipped-for as-is; otherwise a short
    reason it isn't. Mirrors _template_exercise_block_reason's equipment
    check and four-tier per-joint injury-risk check exactly (same
    classify_injury_risk call, same severity/stage/side arguments) plus
    the same systemic-injury check - the only thing intentionally left out
    is the named injuries_to_avoid override list, since this registry
    doesn't carry one (see module docstring)."""
    eq = protocol.get("equipment", "Bodyweight")
    if user_equipment and eq.lower() != "bodyweight" and eq.lower() not in user_equipment:
        return f"Equipment not available ({eq})"

    difficulty = protocol.get("difficulty", 1)
    for joint_name in protocol.get("joint_stress", []):
        severity = injury_joint_severity.get(joint_name)
        if severity is None:
            continue
        tier = classify_injury_risk(
            severity, difficulty,
            tissue=injury_joint_tissue.get(joint_name), exercise=None,
            stage=injury_joint_stage.get(joint_name), side=injury_joint_side.get(joint_name),
        )
        if tier in ("high_risk", "contraindicated"):
            return f"{joint_name} injury risk too high at this difficulty"

    if systemic_severity is not None:
        systemic_tier = classify_injury_risk(systemic_severity, difficulty, stage=systemic_stage)
        if systemic_tier in ("high_risk", "contraindicated"):
            return "Systemic injury restriction"

    return None


# ==========================================================================
# PRESCRIPTION SCALING
# ==========================================================================
# Deliberately conservative, table-driven multipliers - not a physiological
# model. Beginners get less volume/intensity than the template's baseline
# numbers, Advanced athletes get more, and a "peak"/"taper" phase shifts
# volume down while a "build" phase (the default) uses the baseline as-is.
# Values that represent a HARD safety ceiling rather than a dose (edge_mm,
# hr_zone, requires_supervision) are never scaled - only volume/duration/
# distance/load numbers are.
# The full 5-tier scale backend.models.schemas.EXPERIENCE_LEVELS uses, not
# just 3 - a template's own `level` can be "Novice" or "Elite" too, and
# (for the Special Forces library specifically) a domain-specific spelling
# like "Selection Candidate"/"Elite / Tier 1" that
# sc_template_library.SPECIAL_FORCES_LEVEL_ALIASES already maps back onto
# this same 5-tier scale - callers should run a template's raw `level`
# through sc_template_library.resolve_wizard_level's inverse (or just look
# it up in SPECIAL_FORCES_LEVEL_ALIASES.values() -> keys) before passing it
# here if it might be one of those Operator-style strings.
EXPERIENCE_LEVELS_ORDER = ("Beginner", "Novice", "Intermediate", "Advanced", "Elite")

_EXPERIENCE_MULTIPLIER: Dict[str, float] = {
    "Beginner": 0.70,
    "Novice": 0.85,
    "Intermediate": 1.0,
    "Advanced": 1.15,
    "Elite": 1.25,
}

PHASES_ORDER = ("base", "build", "peak", "taper")

_PHASE_MULTIPLIER: Dict[str, float] = {
    "base": 0.85,
    "build": 1.0,
    "peak": 1.1,
    "taper": 0.6,
}

# Race-load-carry overload prescriptions (110-125% race load) are a % of
# race load, not a volume dose - scaling those UP with experience the same
# way volume scales would push a Beginner past what "overload" already
# means for anyone. Only the low/high band position moves with experience
# (Beginner -> low end of the stated overload band, Elite -> high end);
# rounds/distance still scale normally.
_OVERLOAD_BAND = {"Beginner": -8, "Novice": -4, "Intermediate": 0, "Advanced": 5, "Elite": 8}

# Minimum floors so scaling down for a Beginner/taper combination never
# produces a degenerate prescription (0 reps, a 0-second hang, etc.).
_MIN_SETS_OR_ROUNDS = 1
_MIN_HANG_DURATION_S = 3
_MIN_REST_S = 15


def _round_to(value: float, step: int) -> int:
    return max(step, int(round(value / step) * step))


def _scale_int(base: Optional[int], mult: float, floor: int = 1, step: int = 1) -> Optional[int]:
    if base is None:
        return None
    return max(floor, _round_to(base * mult, step))


def _combined_multiplier(experience_level: str, phase: str) -> float:
    return _EXPERIENCE_MULTIPLIER.get(experience_level, 1.0) * _PHASE_MULTIPLIER.get(phase, 1.0)


def _prescribe_race_load_carry(params: Dict, experience_level: str, phase: str) -> Dict:
    mult = _combined_multiplier(experience_level, phase)
    load_pct = params.get("load_pct_race", 100)
    if load_pct > 100:
        # Genuine overload band - shift the target within the stated band
        # by experience rather than scaling the % itself with phase.
        load_pct = load_pct + _OVERLOAD_BAND.get(experience_level, 0)
    out = {
        "load_pct_race": load_pct,
        "sets": _scale_int(params.get("sets"), mult, floor=_MIN_SETS_OR_ROUNDS),
        "rest_s": _scale_int(params.get("rest_s"), 1 / max(mult, 0.01), floor=0, step=15) if params.get("rest_s") else 0,
    }
    if params.get("distance_m") is not None:
        out["distance_m"] = _scale_int(params["distance_m"], mult, floor=5, step=5)
    if params.get("duration_s") is not None:
        out["duration_s"] = _scale_int(params["duration_s"], mult, floor=30, step=15)
    return out


def _prescribe_sled_sprint(params: Dict, experience_level: str, phase: str) -> Dict:
    mult = _combined_multiplier(experience_level, phase)
    return {
        "distance_m": _scale_int(params.get("distance_m"), mult, floor=5, step=5),
        "load_pct_bw": params.get("load_pct_bw"),  # a safety-relevant load target, not a volume dose - held fixed
        "reps": _scale_int(params.get("reps"), mult, floor=2),
        "rest_s": max(_MIN_REST_S, _scale_int(params.get("rest_s"), 1 / max(mult, 0.01), floor=0, step=15)),
    }


def _prescribe_shuttle_ladder(params: Dict, experience_level: str, phase: str) -> Dict:
    mult = _combined_multiplier(experience_level, phase)
    return {
        "steps_m": params.get("steps_m"),  # the ladder's own shape is the exercise - not rescaled
        "load_pct_bw": params.get("load_pct_bw"),
        "rounds": _scale_int(params.get("rounds"), mult, floor=_MIN_SETS_OR_ROUNDS),
        "rest_s": max(_MIN_REST_S, _scale_int(params.get("rest_s"), 1 / max(mult, 0.01), floor=0, step=15)),
    }


def _prescribe_erg_interval(params: Dict, experience_level: str, phase: str) -> Dict:
    mult = _combined_multiplier(experience_level, phase)
    out = {
        "target_pct_race_pace": params.get("target_pct_race_pace"),  # a pace TARGET, not a volume dose
        "rounds": _scale_int(params.get("rounds"), mult, floor=_MIN_SETS_OR_ROUNDS),
        "rest_s": max(_MIN_REST_S, _scale_int(params.get("rest_s"), 1 / max(mult, 0.01), floor=0, step=15)) if params.get("rest_s") else 0,
    }
    if params.get("distance_m") is not None:
        out["distance_m"] = params["distance_m"]  # a named race-distance interval - not rescaled
    if params.get("duration_s") is not None:
        out["duration_s"] = _scale_int(params["duration_s"], mult, floor=10, step=5)
    if params.get("reps") is not None:
        out["reps"] = _scale_int(params["reps"], mult, floor=1)
    return out


def _prescribe_zone_run(params: Dict, experience_level: str, phase: str) -> Dict:
    mult = _combined_multiplier(experience_level, phase)
    out = {
        "hr_zone": params.get("hr_zone"),  # the zone IS the prescription - never rescaled
        "duration_min": _scale_int(params.get("duration_min"), mult, floor=10),
    }
    if params.get("rounds") is not None:
        out["rounds"] = _scale_int(params.get("rounds"), mult, floor=1)
        out["rest_s"] = max(_MIN_REST_S, _scale_int(params.get("rest_s"), 1 / max(mult, 0.01), floor=0, step=15))
    return out


def _prescribe_swim(params: Dict, experience_level: str, phase: str) -> Dict:
    mult = _combined_multiplier(experience_level, phase)
    out = {"rounds": _scale_int(params.get("rounds"), mult, floor=1),
           "rest_s": max(_MIN_REST_S, _scale_int(params.get("rest_s"), 1 / max(mult, 0.01), floor=0, step=15))}
    if params.get("distance_m") is not None:
        out["distance_m"] = _scale_int(params["distance_m"], mult, floor=25, step=25)
    if params.get("duration_s") is not None:
        out["duration_s"] = _scale_int(params["duration_s"], mult, floor=15, step=15)
    if params.get("reps") is not None:
        out["reps"] = _scale_int(params["reps"], mult, floor=1)
    return out


def _prescribe_hang_climb(params: Dict, experience_level: str, phase: str) -> Dict:
    # Grip/tendon loading is the highest injury-risk load_type here (finger
    # pulleys don't forgive an aggressive volume ramp) - deliberately
    # scale hang duration and sets MORE conservatively than the shared
    # multiplier by never increasing hang duration past the template's own
    # baseline for anyone below Intermediate, only ever holding or
    # shortening it.
    mult = _combined_multiplier(experience_level, phase)
    conservative_mult = min(mult, 1.0) if experience_level in ("Beginner", "Novice") else mult
    out = {
        "edge_mm": params.get("edge_mm"),  # a hold-size safety ceiling, not a dose - never rescaled
        "sets": _scale_int(params.get("sets"), mult, floor=_MIN_SETS_OR_ROUNDS),
        "rest_s": max(30, _scale_int(params.get("rest_s"), 1 / max(mult, 0.01), floor=0, step=15)),
    }
    hang = params.get("hang_duration_s")
    if hang:
        out["hang_duration_s"] = _scale_int(hang, conservative_mult, floor=_MIN_HANG_DURATION_S, step=1)
    else:
        out["hang_duration_s"] = hang
    return out


def _prescribe_rounds(params: Dict, experience_level: str, phase: str) -> Dict:
    mult = _combined_multiplier(experience_level, phase)
    return {
        "round_count": _scale_int(params.get("round_count"), mult, floor=2),
        "round_length_s": params.get("round_length_s"),  # a rules-defined round length - not rescaled
        "rest_s": max(_MIN_REST_S, _scale_int(params.get("rest_s"), 1 / max(mult, 0.01), floor=0, step=15)),
    }


def _prescribe_complex(params: Dict, experience_level: str, phase: str) -> Dict:
    mult = _combined_multiplier(experience_level, phase)
    return {
        "work_s": params.get("work_s"),  # station duration is the format - not rescaled
        "rounds": _scale_int(params.get("rounds"), mult, floor=2),
        "rest_s": max(_MIN_REST_S, _scale_int(params.get("rest_s"), 1 / max(mult, 0.01), floor=0, step=15)),
    }


_PRESCRIPTION_BUILDERS = {
    "race_load_carry": _prescribe_race_load_carry,
    "sled_sprint": _prescribe_sled_sprint,
    "shuttle_ladder": _prescribe_shuttle_ladder,
    "erg_interval": _prescribe_erg_interval,
    "zone_run": _prescribe_zone_run,
    "swim": _prescribe_swim,
    "hang_climb": _prescribe_hang_climb,
    "rounds": _prescribe_rounds,
    "complex": _prescribe_complex,
}


def prescribe_conditioning(protocol: Dict, experience_level: str = "Intermediate", phase: str = "build") -> Dict:
    """The concrete distance/duration/load/rest scheme for THIS athlete,
    built from `protocol["params"]` (the template's own baseline numbers)
    scaled by `_EXPERIENCE_MULTIPLIER`/`_PHASE_MULTIPLIER` above.
    `experience_level` should be one of EXPERIENCE_LEVELS_ORDER and `phase`
    one of PHASES_ORDER; an unrecognized value of either just falls back
    to a 1.0 multiplier (Intermediate/build) rather than raising, since a
    bad phase/level string shouldn't be able to block a workout the same
    way a genuine safety failure does."""
    builder = _PRESCRIPTION_BUILDERS[protocol["load_type"]]
    prescription = builder(protocol["params"], experience_level, phase)
    prescription["load_type"] = protocol["load_type"]
    prescription["experience_level"] = experience_level
    prescription["phase"] = phase
    return prescription


# ==========================================================================
# TOP-LEVEL ENTRY POINT
# ==========================================================================

def resolve_conditioning_exercise(
    name: str,
    user_equipment: set,
    injury_joint_severity: Dict[str, int],
    injury_joint_tissue: Dict[str, str],
    injury_joint_stage: Dict[str, str],
    injury_joint_side: Dict[str, str],
    systemic_severity: Optional[int],
    systemic_stage: Optional[str],
    experience_level: str = "Intermediate",
    phase: str = "build",
) -> Optional[Dict]:
    """The conditioning-protocol equivalent of resolving + gating + pricing
    a real exercises.json entry in build_template_fidelity_program. Returns
    None if `name` isn't one of the 85 CONDITIONING_PROTOCOLS entries (the
    caller's existing verified:False passthrough is still the right
    fallback for anything genuinely unrecognized). Otherwise always
    returns a dict - conditioning protocols aren't equipment/injury-
    substituted the way a lift is (find_alternatives has nothing to swap a
    ruck march for), so a failed gate check comes back `excluded: True`
    with a reason instead of ever being silently dropped or substituted.

    The returned dict deliberately omits `name`: a couple of registry
    entries are shared by two template spellings that normalize to the
    same key (see the "Kettlebell Complex" comment above), so the
    caller's OWN `name` (the exact wording their template used) - not the
    registry's canonical one - is what should end up in the output, the
    same way build_template_fidelity_program keeps `ex_entry`'s own name
    for every non-substituted exercise.
    """
    protocol = resolve_conditioning_protocol(name)
    if protocol is None:
        return None

    reason = _conditioning_block_reason(
        protocol, user_equipment, injury_joint_severity, injury_joint_tissue,
        injury_joint_stage, injury_joint_side, systemic_severity, systemic_stage,
    )

    result = {
        "conditioning_protocol": True,
        "family": protocol["family"],
        "family_label": protocol["family_label"],
        "energy_system": protocol["energy_system"],
        "equipment": protocol["equipment"],
        "difficulty": protocol["difficulty"],
    }
    if protocol["requires_supervision"]:
        result["requires_supervision"] = True
        result["safety_note"] = protocol["safety_note"]

    if reason is not None:
        result["verified"] = False
        result["excluded"] = True
        result["exclusion_reason"] = reason
        return result

    result["verified"] = True
    result["prescription"] = prescribe_conditioning(protocol, experience_level, phase)
    return result

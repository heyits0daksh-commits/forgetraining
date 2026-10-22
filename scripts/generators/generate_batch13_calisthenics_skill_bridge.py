"""
generate_batch13_calisthenics_skill_bridge.py — closes gaps in the pure-
calisthenics skill progressions (push, planche, handstand) so an athlete
with NOTHING but a pull-up bar + dip station (or literally just floor +
wall) has a complete, no-cost path from beginner to elite bodyweight
skill work, same spirit as batch10/11/12's equipment-availability audits.

GAPS FOUND (all equipment="Bodyweight" or "Parallel Bars" — zero cost):

  1. Wall Walk — the standard bridge between Decline Pike Push-Up (diff 3)
     and Wall-Supported Handstand Push-Up (diff 4). Without it the chain
     jumps straight from a decline pike to a wall-supported HSPU, which is
     a big coordination/confidence gap for someone training alone with no
     spotter or coach.
  2. Tiger Bend Push-Up — Freestanding HSPU (diff 5, Elite) had no
     progression at all; this is the standard next skill (bent-arm, deep
     ROM handstand push-up) for someone who has already got freestanding
     HSPU.
  3. Pseudo Planche Push-Up — the standard strength-building bridge from a
     normal push-up into the planche line (Planche Lean had no regression
     at all, so there was no organic on-ramp into planche work from the
     push category most people already train).
  4. Frog Stand (Crow Pose) — an accessible, low-difficulty balance skill
     that gives a second, easier entry point into the planche line
     alongside Planche Lean (added as an additional regression on Tucked
     Planche, not a replacement).

Existing exercises are updated (progressions/regressions only) to splice
these into the chain — no other field on any pre-existing exercise is
touched:
  - decline_pike_pushup_001.progressions: [wall_hspu_001] -> [wall_walk_001]
  - wall_hspu_001.regressions: [decline_pike_pushup_001] -> [wall_walk_001]
  - freestanding_hspu_001.progressions: [] -> [tiger_bend_pushup_001]
  - pushup_002.progressions: [] -> [pseudo_planche_pushup_001]
  - planche_lean_001.regressions: [] -> [pseudo_planche_pushup_001]
  - tucked_planche_001.regressions: [planche_lean_001] ->
        [planche_lean_001, frog_stand_001]
  - hollow_hold_001.progressions: [hanging_leg_raise_001] ->
        [hanging_leg_raise_001, frog_stand_001]

Same authoring discipline as prior batches: base fields hand-tagged from
real biomechanics/coaching progressions, run through enrich_exercise()
afterward so movement-analysis/athletic-quality fields aren't hand-faked.

Run: python scripts/generate_batch13_calisthenics_skill_bridge.py
Then: python scripts/enrich_batch13_only.py
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:
    from backend.core.config import settings
    SRC = settings.EXERCISES_JSON_PATH
    BACKUP = settings.BACKUP_DIR / "exercises_pre_batch13_backup.json"
except ModuleNotFoundError:
    _ROOT = Path(__file__).resolve().parent.parent.parent
    SRC = _ROOT / "data" / "exercises.json"
    BACKUP = _ROOT / "data" / "backups" / "exercises_pre_batch13_backup.json"

_SPORT_KEYS = [
    "Wrestling", "Judo", "Sambo", "BJJ", "Boxing", "Muay Thai", "Kickboxing",
    "Sanda", "Rugby", "Rock Climbing", "HYROX", "Special Forces", "MMA",
    "Powerlifting", "Look Jacked",
]

NEW_EXERCISES = [
    {
        "id": "wall_walk_001",
        "name": "Wall Walk",
        "category": "Vertical Push",
        "movement_pattern": "Push",
        "difficulty": 3,
        "experience_level": "Intermediate",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Anterior Deltoid", "Upper Trapezius"],
        "secondary_muscles": ["Triceps Brachii", "Rectus Abdominis"],
        "stabilizers": ["Core"],
        "joint_stress": ["Wrist", "Shoulder"],
        "injuries_to_avoid": ["Shoulder Instability (General/Atraumatic)"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": ["wall_hspu_001"], "regressions": ["decline_pike_pushup_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            72, 77, 77, 77, 58, 58, 58, 58, 48, 88, 48, 85, 68, 42, 37,
        ])),
    },
    {
        "id": "tiger_bend_pushup_001",
        "name": "Tiger Bend Push-Up",
        "category": "Vertical Push",
        "movement_pattern": "Push",
        "difficulty": 5,
        "experience_level": "Elite",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Anterior Deltoid", "Triceps Brachii"],
        "secondary_muscles": ["Upper Trapezius", "Pectoralis Major"],
        "stabilizers": ["Core", "Rotator Cuff"],
        "joint_stress": ["Wrist", "Shoulder", "Elbow"],
        "injuries_to_avoid": ["Shoulder Instability (General/Atraumatic)", "Rotator Cuff"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": ["freestanding_hspu_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            75, 80, 80, 80, 55, 55, 55, 55, 45, 96, 45, 88, 68, 50, 43,
        ])),
    },
    {
        "id": "pseudo_planche_pushup_001",
        "name": "Pseudo Planche Push-Up",
        "category": "Horizontal Push",
        "movement_pattern": "Push",
        "difficulty": 3,
        "experience_level": "Intermediate",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Anterior Deltoid", "Pectoralis Major"],
        "secondary_muscles": ["Triceps Brachii", "Serratus Anterior"],
        "stabilizers": ["Core", "Wrist Flexors"],
        "joint_stress": ["Wrist", "Shoulder"],
        "injuries_to_avoid": ["Wrist Pain"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 20},
        "progressions": ["planche_lean_001"], "regressions": ["pushup_002"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            73, 78, 78, 78, 58, 58, 58, 58, 48, 90, 48, 82, 68, 40, 48,
        ])),
    },
    {
        "id": "frog_stand_001",
        "name": "Frog Stand (Crow Pose)",
        "category": "Full Body",
        "movement_pattern": "Isometric",
        "difficulty": 2,
        "experience_level": "Novice",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Anterior Deltoid", "Rectus Abdominis"],
        "secondary_muscles": ["Wrist Flexors", "Hip Flexors"],
        "stabilizers": ["Core"],
        "joint_stress": ["Wrist"],
        "injuries_to_avoid": ["Wrist Pain"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": ["tucked_planche_001"], "regressions": ["hollow_hold_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            60, 65, 62, 65, 45, 45, 45, 45, 38, 82, 38, 60, 55, 22, 25,
        ])),
    },
]

# (id, field_to_edit, new_value) — existing exercises whose links get
# spliced to include the new skill-bridge exercises above. Every edit is
# additive/splice-only; no other field is touched.
EXISTING_LINK_EDITS = [
    ("decline_pike_pushup_001", "progressions", ["wall_walk_001"]),
    ("wall_hspu_001", "regressions", ["wall_walk_001"]),
    ("freestanding_hspu_001", "progressions", ["tiger_bend_pushup_001"]),
    ("pushup_002", "progressions", ["pseudo_planche_pushup_001"]),
    ("planche_lean_001", "regressions", ["pseudo_planche_pushup_001"]),
    ("tucked_planche_001", "regressions", ["planche_lean_001", "frog_stand_001"]),
    ("hollow_hold_001", "progressions", ["hanging_leg_raise_001", "frog_stand_001"]),
]


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_ids = {e["id"] for e in data["exercises"]}
    dupes = [e["id"] for e in NEW_EXERCISES if e["id"] in existing_ids]
    if dupes:
        raise SystemExit(f"These ids already exist, aborting: {dupes}")

    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(SRC, BACKUP)

    data["exercises"].extend(NEW_EXERCISES)

    by_id = {e["id"]: e for e in data["exercises"]}
    for ex_id, field, new_value in EXISTING_LINK_EDITS:
        if ex_id not in by_id:
            raise SystemExit(f"Expected existing id not found, aborting: {ex_id}")
        by_id[ex_id][field] = new_value

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Added {len(NEW_EXERCISES)} calisthenics skill-bridge exercises and "
          f"spliced {len(EXISTING_LINK_EDITS)} existing progression/regression "
          f"links. Total exercises in file: {len(data['exercises'])}. "
          f"Backup written to {BACKUP}.")


if __name__ == "__main__":
    main()

"""
generate_batch12_bodyweight_category_coverage.py — closes the last (and
biggest) bodyweight gap: a full audit of every category in the database
against equipment="Bodyweight" showed FIVE categories with ZERO bodyweight
exercises at all: Carry, Conditioning, Grip, Power, Rotational.

That's a serious problem for program_builder's split templates - every
SPLIT_TEMPLATES day slot in program_builder.py includes "Power", "Carry",
"Conditioning" and/or "Core"/grip-adjacent categories (see the "Full Body"
and "Upper/Lower" template day definitions), and every sport chapter in the
manual prescribes an energy-system-conditioning block every session. An
athlete on equipment_available=["Bodyweight"] wasn't just getting the same
exercise repeated (the batch10/batch11 bugs) - for these 5 categories they
were getting NOTHING, because there was nothing in the pool for
generate_session's category filter to find. That's a silent gap, not an
error, so nothing would have surfaced it except an equipment-availability
audit like this one.

FIX - 2 new bodyweight exercises per zero-coverage category (10 total),
each a real, commonly-coached bodyweight substitute for that category's
purpose:

  Conditioning: Burpees, Mountain Climbers
      The two most standard zero-equipment conditioning drills; oddly
      absent despite 33 Conditioning exercises existing for every other
      equipment type.
  Carry: Bear Crawl, Crab Walk Carry
      Bodyweight "loaded carry" substitutes - quadrupedal locomotion under
      your own bodyweight trains the same anti-extension/anti-rotation
      trunk demand a farmer's carry does, just without external load.
  Grip: Doorframe Dead Hang, Fingertip Push-Up Hold
      Passive/active grip-endurance work needing nothing but a doorframe
      ledge or the floor - same "doorframe = free household prop" pattern
      as batch11's Doorframe Row/Pull-Up.
  Power: Clap Push-Up, Bodyweight Power Skip
      Explosive/ballistic output trained through the two movement families
      (upper-body plyo push, lower-body horizontal RFD) that don't need a
      medicine ball or barbell to overload rate of force development.
  Rotational: Standing Bodyweight Woodchopper, Shadow Rotational Pivot Drill
      Trunk-rotation training without a cable stack or band - an armswing
      woodchopper pattern and a pivot-and-strike drill (the actual
      hip-rotation mechanism a cable woodchopper is training, just without
      the external resistance).

Same authoring discipline as every prior batch: base fields hand-tagged
from real biomechanics, run through enrich_exercise() afterward so the
movement-analysis/athletic-quality fields aren't hand-faked.

Run: python scripts/generate_batch12_bodyweight_category_coverage.py
Then: python scripts/enrich_batch12_only.py
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:
    from backend.core.config import settings
    SRC = settings.EXERCISES_JSON_PATH
    BACKUP = settings.BACKUP_DIR / "exercises_pre_batch12_backup.json"
except ModuleNotFoundError:
    _ROOT = Path(__file__).resolve().parent.parent.parent
    SRC = _ROOT / "data" / "exercises.json"
    BACKUP = _ROOT / "data" / "backups" / "exercises_pre_batch12_backup.json"

_SPORT_KEYS = [
    "Wrestling", "Judo", "Sambo", "BJJ", "Boxing", "Muay Thai", "Kickboxing",
    "Sanda", "Rugby", "Rock Climbing", "HYROX", "Special Forces", "MMA",
    "Powerlifting", "Look Jacked",
]

NEW_EXERCISES = [
    # --- Conditioning ---
    {
        "id": "burpee_001",
        "name": "Burpee",
        "category": "Conditioning",
        "movement_pattern": "Full Body",
        "difficulty": 2,
        "experience_level": "Novice",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Quadriceps", "Pectoralis Major", "Anterior Deltoid"],
        "secondary_muscles": ["Gluteus Maximus", "Triceps Brachii"],
        "stabilizers": ["Core"],
        "joint_stress": ["Shoulder", "Knee", "Wrist"],
        "injuries_to_avoid": ["Patellar Tendon", "Wrist Pain"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": ["mountain_climber_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            75, 70, 70, 72, 78, 80, 80, 75, 70, 55, 90, 85, 78, 20, 45,
        ])),
    },
    {
        "id": "mountain_climber_001",
        "name": "Mountain Climbers",
        "category": "Conditioning",
        "movement_pattern": "Full Body",
        "difficulty": 1,
        "experience_level": "Beginner",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Rectus Abdominis", "Hip Flexors"],
        "secondary_muscles": ["Anterior Deltoid", "Quadriceps"],
        "stabilizers": ["Core"],
        "joint_stress": ["Shoulder", "Wrist"],
        "injuries_to_avoid": ["Wrist Pain"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": ["burpee_001"], "regressions": [], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            65, 60, 60, 62, 68, 70, 70, 65, 60, 45, 82, 75, 68, 15, 40,
        ])),
    },
    # --- Carry ---
    {
        "id": "bear_crawl_001",
        "name": "Bear Crawl",
        "category": "Carry",
        "movement_pattern": "Carry",
        "difficulty": 2,
        "experience_level": "Novice",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Anterior Deltoid", "Rectus Abdominis", "Quadriceps"],
        "secondary_muscles": ["Triceps Brachii", "Hip Flexors"],
        "stabilizers": ["Core"],
        "joint_stress": ["Shoulder", "Wrist", "Knee"],
        "injuries_to_avoid": ["Wrist Pain"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": [], "alternatives": ["crabwalk_carry_001"],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            78, 72, 70, 75, 45, 50, 50, 65, 65, 60, 70, 80, 68, 15, 35,
        ])),
    },
    {
        "id": "crabwalk_carry_001",
        "name": "Crab Walk Carry",
        "category": "Carry",
        "movement_pattern": "Carry",
        "difficulty": 2,
        "experience_level": "Novice",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Triceps Brachii", "Gluteus Maximus", "Rectus Abdominis"],
        "secondary_muscles": ["Anterior Deltoid", "Hip Flexors"],
        "stabilizers": ["Core"],
        "joint_stress": ["Wrist", "Shoulder"],
        "injuries_to_avoid": ["Wrist Pain"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": [], "alternatives": ["bear_crawl_001"],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            60, 55, 55, 62, 35, 40, 40, 50, 55, 50, 55, 65, 55, 15, 30,
        ])),
    },
    # --- Grip ---
    {
        "id": "doorframe_deadhang_001",
        "name": "Doorframe Dead Hang",
        "category": "Grip",
        "movement_pattern": "Hang",
        "difficulty": 1,
        "experience_level": "Beginner",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Forearm Flexors", "Latissimus Dorsi"],
        "secondary_muscles": ["Trapezius"],
        "stabilizers": ["Rotator Cuff"],
        "joint_stress": ["Shoulder", "Elbow", "Wrist"],
        "injuries_to_avoid": ["Shoulder Instability (General/Atraumatic)"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": ["fingertip_pushup_hold_001"], "regressions": [], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            70, 68, 68, 65, 30, 30, 30, 45, 45, 85, 40, 55, 55, 15, 25,
        ])),
    },
    {
        "id": "fingertip_pushup_hold_001",
        "name": "Fingertip Push-Up Hold",
        "category": "Grip",
        "movement_pattern": "Isometric",
        "difficulty": 3,
        "experience_level": "Advanced",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Forearm Flexors", "Pectoralis Major"],
        "secondary_muscles": ["Anterior Deltoid", "Triceps Brachii"],
        "stabilizers": ["Core"],
        "joint_stress": ["Wrist", "Elbow"],
        "injuries_to_avoid": ["Wrist Pain"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 10},
        "progressions": [], "regressions": ["doorframe_deadhang_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            55, 60, 55, 58, 25, 25, 25, 40, 30, 90, 30, 45, 45, 10, 20,
        ])),
    },
    # --- Power ---
    {
        "id": "clap_pushup_001",
        "name": "Clap Push-Up",
        "category": "Power",
        "movement_pattern": "Explosive Pull",
        "difficulty": 3,
        "experience_level": "Advanced",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Pectoralis Major", "Anterior Deltoid", "Triceps Brachii"],
        "secondary_muscles": ["Serratus Anterior"],
        "stabilizers": ["Core"],
        "joint_stress": ["Wrist", "Elbow", "Shoulder"],
        "injuries_to_avoid": ["Wrist Pain", "Shoulder Instability (General/Atraumatic)"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 15},
        "progressions": [], "regressions": [], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            65, 62, 62, 60, 88, 85, 85, 80, 60, 30, 65, 70, 75, 20, 40,
        ])),
    },
    {
        "id": "power_skip_001",
        "name": "Bodyweight Power Skip",
        "category": "Power",
        "movement_pattern": "Explosive Pull",
        "difficulty": 2,
        "experience_level": "Intermediate",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Gluteus Maximus", "Quadriceps", "Gastrocnemius"],
        "secondary_muscles": ["Hip Flexors"],
        "stabilizers": ["Core"],
        "joint_stress": ["Knee", "Ankle"],
        "injuries_to_avoid": ["Patellar Tendon", "Lateral Ankle Sprain - Grade 1 (Mild)"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": [], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            60, 58, 55, 55, 65, 68, 68, 62, 75, 35, 65, 62, 62, 15, 35,
        ])),
    },
    # --- Rotational ---
    {
        "id": "standing_woodchop_bw_001",
        "name": "Standing Bodyweight Woodchopper",
        "category": "Rotational",
        "movement_pattern": "Rotational",
        "difficulty": 1,
        "experience_level": "Beginner",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Obliques", "Rectus Abdominis"],
        "secondary_muscles": ["Anterior Deltoid", "Gluteus Maximus"],
        "stabilizers": ["Core"],
        "joint_stress": ["Lower Back"],
        "injuries_to_avoid": ["Low Back Pain"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": ["shadow_pivot_drill_001"], "regressions": [], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            55, 58, 55, 55, 60, 65, 65, 65, 50, 35, 45, 45, 55, 15, 30,
        ])),
    },
    {
        "id": "shadow_pivot_drill_001",
        "name": "Shadow Rotational Pivot Drill",
        "category": "Rotational",
        "movement_pattern": "Rotational",
        "difficulty": 2,
        "experience_level": "Novice",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Obliques", "Gluteus Maximus"],
        "secondary_muscles": ["Anterior Deltoid", "Quadriceps"],
        "stabilizers": ["Core"],
        "joint_stress": ["Knee", "Lower Back"],
        "injuries_to_avoid": ["Low Back Pain", "Patellar Tendon"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": ["standing_woodchop_bw_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            62, 65, 60, 58, 70, 78, 78, 78, 55, 35, 48, 50, 65, 15, 32,
        ])),
    },
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

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Added {len(NEW_EXERCISES)} exercises across 5 previously-empty "
          f"bodyweight categories. Total exercises in file: {len(data['exercises'])}. "
          f"Backup written to {BACKUP}.")


if __name__ == "__main__":
    main()

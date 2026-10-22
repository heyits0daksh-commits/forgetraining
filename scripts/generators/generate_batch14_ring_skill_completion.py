"""
generate_batch14_ring_skill_completion.py — the ring (equipment="Rings")
library already had 27 exercises spanning Ring Row through Maltese Cross,
but auditing every ring exercise's progressions/regressions found FOUR
empty progression slots at real coaching bottlenecks — places where a ring
athlete had reached a skill with nowhere further to go in the chain, or had
to jump a skill level with no drilling tool in between:

  1. ring_handstand_001 (Ring Handstand) had progressions: [] — no
     handstand-strength skill built on top of it. Added Ring Handstand
     Push-Up as its natural next step.
  2. ring_lsit_hold_001 (Ring L-Sit Hold) had progressions: [] — no
     harder static-hold skill past a full L-sit on rings. Added Ring V-Sit.
  3. ring_muscleup_001 (Ring Muscle-Up) is trained straight from
     ring_false_grip_hang_001/skin_the_cat_001 with no dedicated drill for
     the transition itself (the classic weak point of the skill) — every
     OTHER muscle-up variant in the file has a transition drill
     (parallelbars_muscleuptransition_001 already exists for the parallel
     bar version) but rings didn't. Added Ring Muscle-Up Transition Drill.
  4. iron_cross_001 (Iron Cross) had progressions: [] and maltese_cross_001
     (Maltese Cross) is the file's hardest ring skill with no step between
     Cross and Maltese — Victorian Cross is the standard gymnastics-strength
     skill that sits between them. Added it, spliced into both ends.

Only equipment="Rings" exercises added. No barbell/machine/etc scope here —
this batch is specifically "does the ring line have a complete, gapless
skill tree", same audit spirit as batch12 (bodyweight category coverage)
and batch13 (calisthenics push/planche skill bridge).

Existing exercises are updated (progressions/regressions only, spliced not
replaced) to link these in:
  - ring_handstand_001.progressions: [] -> [ring_hspu_001]
  - ring_lsit_hold_001.progressions: [] -> [ring_vsit_001]
  - ring_muscleup_001.regressions: [bar_muscleup_001] ->
        [bar_muscleup_001, ring_muscleuptransition_001]
  - iron_cross_001.progressions: [] -> [victorian_cross_001]
  - maltese_cross_001.regressions: [iron_cross_001, ring_planche_001] ->
        [iron_cross_001, ring_planche_001, victorian_cross_001]

Same authoring discipline as prior batches: base fields hand-tagged from
real gymnastics/calisthenics coaching progressions, run through
enrich_exercise() afterward so movement-analysis/athletic-quality fields
aren't hand-faked.

Run: python scripts/generate_batch14_ring_skill_completion.py
Then: python scripts/enrich_batch14_only.py
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:
    from backend.core.config import settings
    SRC = settings.EXERCISES_JSON_PATH
    BACKUP = settings.BACKUP_DIR / "exercises_pre_batch14_backup.json"
except ModuleNotFoundError:
    _ROOT = Path(__file__).resolve().parent.parent.parent
    SRC = _ROOT / "data" / "exercises.json"
    BACKUP = _ROOT / "data" / "backups" / "exercises_pre_batch14_backup.json"

_SPORT_KEYS = [
    "Wrestling", "Judo", "Sambo", "BJJ", "Boxing", "Muay Thai", "Kickboxing",
    "Sanda", "Rugby", "Rock Climbing", "HYROX", "Special Forces", "MMA",
    "Powerlifting", "Look Jacked",
]

NEW_EXERCISES = [
    {
        "id": "ring_hspu_001",
        "name": "Ring Handstand Push-Up",
        "category": "Vertical Push",
        "movement_pattern": "Push",
        "difficulty": 5,
        "experience_level": "Elite",
        "equipment": "Rings",
        "equipment_level": 3,
        "primary_muscles": ["Anterior Deltoid", "Triceps Brachii"],
        "secondary_muscles": ["Upper Trapezius", "Pectoralis Major"],
        "stabilizers": ["Core", "Rotator Cuff", "Wrist Flexors"],
        "joint_stress": ["Wrist", "Shoulder", "Elbow"],
        "injuries_to_avoid": ["Shoulder Instability (General/Atraumatic)", "Rotator Cuff"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": ["ring_handstand_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            72, 78, 78, 78, 52, 52, 52, 52, 42, 96, 42, 85, 65, 48, 45,
        ])),
    },
    {
        "id": "ring_vsit_001",
        "name": "Ring V-Sit",
        "category": "Core",
        "movement_pattern": "Isometric",
        "difficulty": 4,
        "experience_level": "Advanced",
        "equipment": "Rings",
        "equipment_level": 3,
        "primary_muscles": ["Rectus Abdominis", "Hip Flexors"],
        "secondary_muscles": ["Anterior Deltoid", "Triceps Brachii"],
        "stabilizers": ["Core", "Wrist Flexors"],
        "joint_stress": ["Wrist", "Shoulder", "Lower Back"],
        "injuries_to_avoid": ["Low Back Pain", "Wrist Pain"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": ["ring_lsit_hold_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            68, 72, 70, 74, 55, 55, 55, 55, 45, 88, 45, 68, 62, 25, 30,
        ])),
    },
    {
        "id": "ring_muscleuptransition_001",
        "name": "Ring Muscle-Up Transition Drill",
        "category": "Pull",
        "movement_pattern": "Pull",
        "difficulty": 4,
        "experience_level": "Advanced",
        "equipment": "Rings",
        "equipment_level": 3,
        "primary_muscles": ["Latissimus Dorsi", "Triceps Brachii", "Pectoralis Major"],
        "secondary_muscles": ["Biceps Brachii", "Anterior Deltoid"],
        "stabilizers": ["Core", "Wrist Flexors"],
        "joint_stress": ["Shoulder", "Elbow", "Wrist"],
        "injuries_to_avoid": ["Shoulder Instability (General/Atraumatic)", "Wrist Pain"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 8, "pushups": 0},
        "progressions": ["ring_muscleup_001"], "regressions": ["ring_false_grip_hang_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            70, 68, 68, 72, 55, 55, 55, 55, 50, 78, 48, 75, 65, 30, 38,
        ])),
    },
    {
        "id": "victorian_cross_001",
        "name": "Victorian Cross",
        "category": "Full Body",
        "movement_pattern": "Isometric",
        "difficulty": 5,
        "experience_level": "Elite",
        "equipment": "Rings",
        "equipment_level": 3,
        "primary_muscles": ["Latissimus Dorsi", "Pectoralis Major", "Anterior Deltoid"],
        "secondary_muscles": ["Triceps Brachii", "Rectus Abdominis"],
        "stabilizers": ["Core", "Rotator Cuff", "Wrist Flexors"],
        "joint_stress": ["Shoulder", "Elbow", "Wrist"],
        "injuries_to_avoid": ["Shoulder Instability (General/Atraumatic)", "Rotator Cuff"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": ["maltese_cross_001"], "regressions": ["iron_cross_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            68, 72, 70, 72, 45, 45, 45, 45, 38, 90, 35, 78, 62, 22, 35,
        ])),
    },
]

EXISTING_LINK_EDITS = [
    ("ring_handstand_001", "progressions", ["ring_hspu_001"]),
    ("ring_lsit_hold_001", "progressions", ["ring_vsit_001"]),
    ("ring_muscleup_001", "regressions", ["bar_muscleup_001", "ring_muscleuptransition_001"]),
    ("iron_cross_001", "progressions", ["victorian_cross_001"]),
    ("maltese_cross_001", "regressions", ["iron_cross_001", "ring_planche_001", "victorian_cross_001"]),
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

    print(f"Added {len(NEW_EXERCISES)} ring skill-completion exercises and "
          f"spliced {len(EXISTING_LINK_EDITS)} existing progression/regression "
          f"links. Total exercises in file: {len(data['exercises'])}. "
          f"Backup written to {BACKUP}.")


if __name__ == "__main__":
    main()

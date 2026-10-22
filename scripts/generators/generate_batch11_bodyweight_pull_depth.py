"""
generate_batch11_bodyweight_pull_depth.py — fixes a second real content gap
found while investigating the batch10 variety bug: category=Horizontal Pull
and category=Vertical Pull under equipment="Bodyweight" had exactly ONE
exercise each in the entire database:
    inverted_table_row_001  (Horizontal Pull) - needs a sturdy table
    ropeclimb_pull_001      (Vertical Pull)   - needs a rope, AND gates on
                                                 strength_requirements.pullups=8,
                                                 i.e. you already need to be
                                                 able to do 8 strict pull-ups
                                                 before the engine will even
                                                 offer it
So an athlete with genuinely zero equipment (no table, no rope, no bar - a
person training in a small room or a park with nothing) had no rotation
AND no true beginner entry point into pulling work at all: Vertical Pull
had a single option and it was gated at an advanced strength level. That's
worse than the batch10 bug (that was "always the same exercise" - this is
"no exercise below advanced level, and only one option, full stop").

FIX - 4 new bodyweight exercises, no purchased equipment, spanning
Beginner -> Intermediate so there's an actual on-ramp:
  - scapular_wall_slide_001  (Vertical Pull, difficulty 1, Beginner)
        True zero-equipment vertical-pull-pattern regression (uses a wall,
        which every dwelling has) - the missing entry point below
        ropeclimb_pull_001's difficulty 4/pullups-8 floor.
  - doorframe_pullup_001     (Vertical Pull, difficulty 3, Intermediate)
        Ledge-grip pull-up off a doorframe top edge - common in Indian
        households (chaukhat) and elsewhere; gated at pullups=2, not 8, so
        it's reachable well before ropeclimb_pull_001.
  - prone_ytw_raise_001      (Horizontal Pull, difficulty 1, Beginner)
        Floor-only scapular-retraction drill, zero equipment at all.
  - doorframe_row_001        (Horizontal Pull, difficulty 2, Novice)
        Leaning bodyweight row using a doorframe edge as the anchor.

Same convention the file already uses (inverted_table_row_001 and
ropeclimb_pull_001 are both tagged equipment="Bodyweight" despite using a
table/rope respectively - a doorframe or wall is the same category of
"free, already in every home" prop, not a purchased implement, so these
follow that existing precedent rather than inventing a new equipment type).

Progression chain wired so program_builder's regression/progression lookups
have somewhere to go: scapular_wall_slide_001 -> doorframe_pullup_001 ->
ropeclimb_pull_001, and prone_ytw_raise_001 -> doorframe_row_001 ->
inverted_table_row_001.

Run: python scripts/generate_batch11_bodyweight_pull_depth.py
Then: python scripts/enrich_batch11_only.py
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:
    from backend.core.config import settings
    SRC = settings.EXERCISES_JSON_PATH
    BACKUP = settings.BACKUP_DIR / "exercises_pre_batch11_backup.json"
except ModuleNotFoundError:
    _ROOT = Path(__file__).resolve().parent.parent.parent
    SRC = _ROOT / "data" / "exercises.json"
    BACKUP = _ROOT / "data" / "backups" / "exercises_pre_batch11_backup.json"

_SPORT_KEYS = [
    "Wrestling", "Judo", "Sambo", "BJJ", "Boxing", "Muay Thai", "Kickboxing",
    "Sanda", "Rugby", "Rock Climbing", "HYROX", "Special Forces", "MMA",
    "Powerlifting", "Look Jacked",
]

NEW_EXERCISES = [
    {
        "id": "scapular_wall_slide_001",
        "name": "Scapular Wall Slide",
        "category": "Vertical Pull",
        "movement_pattern": "Pull",
        "difficulty": 1,
        "experience_level": "Beginner",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Trapezius", "Rhomboids"],
        "secondary_muscles": ["Rear Deltoid"],
        "stabilizers": ["Rotator Cuff"],
        "joint_stress": ["Shoulder"],
        "injuries_to_avoid": [],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": ["doorframe_pullup_001"], "regressions": [], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            45, 45, 45, 45, 35, 35, 35, 35, 35, 55, 40, 45, 42, 25, 30,
        ])),
    },
    {
        "id": "doorframe_pullup_001",
        "name": "Doorframe Pull-Up (Ledge Grip)",
        "category": "Vertical Pull",
        "movement_pattern": "Pull",
        "difficulty": 3,
        "experience_level": "Intermediate",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Latissimus Dorsi", "Biceps Brachii"],
        "secondary_muscles": ["Rear Deltoid", "Rhomboids"],
        "stabilizers": ["Core"],
        "joint_stress": ["Shoulder", "Elbow", "Wrist"],
        "injuries_to_avoid": ["Shoulder Instability (General/Atraumatic)"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 2, "pushups": 0},
        "progressions": ["ropeclimb_pull_001"], "regressions": ["scapular_wall_slide_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            70, 70, 68, 68, 50, 50, 50, 50, 55, 65, 55, 70, 62, 30, 40,
        ])),
    },
    {
        "id": "prone_ytw_raise_001",
        "name": "Prone Y-T-W Raise",
        "category": "Horizontal Pull",
        "movement_pattern": "Pull",
        "difficulty": 1,
        "experience_level": "Beginner",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Trapezius", "Rhomboids"],
        "secondary_muscles": ["Rear Deltoid", "Erector Spinae"],
        "stabilizers": ["Core"],
        "joint_stress": ["Shoulder"],
        "injuries_to_avoid": [],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": ["doorframe_row_001"], "regressions": [], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            48, 48, 48, 48, 40, 40, 40, 40, 38, 45, 40, 45, 44, 25, 32,
        ])),
    },
    {
        "id": "doorframe_row_001",
        "name": "Doorframe Row",
        "category": "Horizontal Pull",
        "movement_pattern": "Pull",
        "difficulty": 2,
        "experience_level": "Novice",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Latissimus Dorsi", "Rhomboids"],
        "secondary_muscles": ["Biceps Brachii"],
        "stabilizers": ["Core"],
        "joint_stress": ["Shoulder", "Wrist"],
        "injuries_to_avoid": [],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": ["inverted_table_row_001"], "regressions": ["prone_ytw_raise_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            68, 72, 72, 72, 62, 62, 62, 62, 52, 75, 52, 80, 65, 30, 36,
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

    # Wire the existing exercises' own regressions/progressions to point at
    # the new ones, so the DAG is coherent both directions (not just the
    # new exercises pointing at the old ones).
    by_id = {e["id"]: e for e in data["exercises"]}
    by_id["ropeclimb_pull_001"]["regressions"] = list(dict.fromkeys(
        by_id["ropeclimb_pull_001"].get("regressions", []) + ["doorframe_pullup_001"]
    ))
    by_id["inverted_table_row_001"]["regressions"] = list(dict.fromkeys(
        by_id["inverted_table_row_001"].get("regressions", []) + ["doorframe_row_001"]
    ))

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Added {len(NEW_EXERCISES)} exercises, patched 2 existing regressions. "
          f"Total exercises in file: {len(data['exercises'])}. "
          f"Backup written to {BACKUP}.")


if __name__ == "__main__":
    main()

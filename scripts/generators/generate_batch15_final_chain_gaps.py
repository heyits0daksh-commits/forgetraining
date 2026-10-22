"""
generate_batch15_final_chain_gaps.py — final gap-closing pass over the
calisthenics-accessible equipment (Bodyweight, Pull-up Bar, Parallel Bars,
Rings, Resistance Band, Suspension Trainer). Audited every exercise in
these equipment types for empty progressions/regressions and filtered out
everything that's a legitimate dead end (accessory/isolation moves, sport-
drills, conditioning work — these genuinely don't have a "next skill" and
forcing one would be fabricated data, not a real gap). Three real,
well-established gaps remained:

  1. One-Arm Push-Up was MISSING FROM THE DATABASE ENTIRELY. Both
     Archer Push-Up (diff 3, Bodyweight) and Archer Ring Push-Up (diff 4,
     Rings) — the standard lead-ins to it — dead-ended with empty
     progressions, because there was nothing to progress to. This is one
     of the most standard advanced calisthenics push skills and its
     absence was the single biggest real gap found.
  2. Pistol Squat (diff 4) had no progression. Weighted Pistol Squat is
     the standard next step (added under equipment=Bodyweight, same
     convention as Weighted Pull-Up staying under its base-movement
     equipment rather than being filed as Dumbbell/Kettlebell).
  3. Rope Climb Pull (diff 4) had no progression. Legless Rope Climb
     (removing the leg assist) is the standard next step.

Additionally, two SPLICE-ONLY fixes (no new exercises, just linking
existing ones that were sitting disconnected from an obvious neighbor):
  - Ring Dip (diff 3) had progressions: [] even though Ring Archer Dip
    (diff 4) already exists in the file as its natural next step — it was
    only linked backward to Parallel Bar Dip, never to Ring Dip.
  - Archer Ring Pull-Up (diff 4) had progressions: [] even though
    One-Arm Pull-Up (diff 5) already exists — strength on a ring archer
    pull-up transfers directly to a bar one-arm pull-up, same as the bar
    archer pull-up already progressing there.

Run: python scripts/generate_batch15_final_chain_gaps.py
Then: python scripts/enrich_batch15_only.py
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:
    from backend.core.config import settings
    SRC = settings.EXERCISES_JSON_PATH
    BACKUP = settings.BACKUP_DIR / "exercises_pre_batch15_backup.json"
except ModuleNotFoundError:
    _ROOT = Path(__file__).resolve().parent.parent.parent
    SRC = _ROOT / "data" / "exercises.json"
    BACKUP = _ROOT / "data" / "backups" / "exercises_pre_batch15_backup.json"

_SPORT_KEYS = [
    "Wrestling", "Judo", "Sambo", "BJJ", "Boxing", "Muay Thai", "Kickboxing",
    "Sanda", "Rugby", "Rock Climbing", "HYROX", "Special Forces", "MMA",
    "Powerlifting", "Look Jacked",
]

NEW_EXERCISES = [
    {
        "id": "one_arm_pushup_001",
        "name": "One-Arm Push-Up",
        "category": "Horizontal Push",
        "movement_pattern": "Push",
        "difficulty": 5,
        "experience_level": "Elite",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Pectoralis Major", "Triceps Brachii"],
        "secondary_muscles": ["Anterior Deltoid", "Rectus Abdominis"],
        "stabilizers": ["Obliques", "Wrist Flexors"],
        "joint_stress": ["Wrist", "Elbow", "Shoulder"],
        "injuries_to_avoid": ["Shoulder Instability (General/Atraumatic)", "Wrist Pain"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": ["archer_pushup_001", "archer_ring_pushup_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            78, 73, 73, 78, 88, 83, 83, 83, 73, 58, 73, 88, 81, 43, 51,
        ])),
    },
    {
        "id": "weighted_pistol_squat_001",
        "name": "Weighted Pistol Squat",
        "category": "Squat",
        "movement_pattern": "Squat",
        "difficulty": 5,
        "experience_level": "Elite",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Quadriceps", "Gluteus Maximus"],
        "secondary_muscles": ["Hamstrings"],
        "stabilizers": ["Erector Spinae", "Gluteus Medius"],
        "joint_stress": ["Knee", "Hip"],
        "injuries_to_avoid": ["Patellar Tendon"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": ["pistol_squat_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            83, 78, 78, 68, 68, 78, 78, 78, 88, 48, 93, 93, 75, 51, 51,
        ])),
    },
    {
        "id": "legless_ropeclimb_001",
        "name": "Legless Rope Climb",
        "category": "Vertical Pull",
        "movement_pattern": "Pull",
        "difficulty": 5,
        "experience_level": "Elite",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Latissimus Dorsi", "Forearm Flexors"],
        "secondary_muscles": ["Biceps Brachii", "Core"],
        "stabilizers": ["Rotator Cuff"],
        "joint_stress": ["Shoulder", "Elbow"],
        "injuries_to_avoid": ["Shoulder Instability (General/Atraumatic)"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": ["ropeclimb_pull_001"], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            78, 78, 78, 73, 58, 58, 58, 58, 73, 58, 63, 80, 68, 47, 51,
        ])),
    },
]

EXISTING_LINK_EDITS = [
    ("archer_pushup_001", "progressions", ["one_arm_pushup_001"]),
    ("archer_ring_pushup_001", "progressions", ["one_arm_pushup_001"]),
    ("pistol_squat_001", "progressions", ["weighted_pistol_squat_001"]),
    ("ropeclimb_pull_001", "progressions", ["legless_ropeclimb_001"]),
    # splice-only fixes, no new exercises involved:
    ("ring_dip_001", "progressions", ["ring_archer_dip_001"]),
    ("ring_archer_dip_001", "regressions", ["parallel_bar_dip_001", "ring_dip_001"]),
    ("archer_ring_pullup_001", "progressions", ["one_arm_pullup_001"]),
    ("one_arm_pullup_001", "regressions", ["archer_pullup_001", "archer_ring_pullup_001"]),
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

    print(f"Added {len(NEW_EXERCISES)} exercises and spliced "
          f"{len(EXISTING_LINK_EDITS)} existing progression/regression "
          f"links. Total exercises in file: {len(data['exercises'])}. "
          f"Backup written to {BACKUP}.")


if __name__ == "__main__":
    main()

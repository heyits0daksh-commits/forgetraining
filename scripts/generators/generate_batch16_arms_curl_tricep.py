"""
generate_batch16_arms_curl_tricep.py — adds 10 new arm-isolation exercises
closing a user-reported gap: the database had EZ-bar and cable curls/
pushdowns but no plain Dumbbell or Barbell bicep-curl variations, no
hammer curl, no dumbbell tricep extension/kickback work, and no bench dip.

WHY THESE: Dumbbell and Barbell are both already well-established equipment
types in the database (37 and 121 existing entries respectively, levels 3
and 5 - reused here rather than inventing new numbers), but neither had a
single bicep curl or triceps-isolation entry. This batch adds 5 biceps and
5 triceps exercises across Dumbbell, Barbell, and Bodyweight.

Follows the exact pattern of generate_batch6_thin_equipment.py: hand-tagged
joint_stress / injuries_to_avoid per exercise (reusing exact taxonomy-
matching strings already used elsewhere in the file, e.g. cable_bicepcurl_001
and ezbar_skullcrusher_001), reuses each equipment's EXISTING equipment_level,
small and reviewable rather than exhaustive.

Run: python scripts/generators/generate_batch16_arms_curl_tricep.py
Then: python scripts/enrichment/enrich_exercises.py   (derives v4.0+ fields for the new entries)
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from backend.core.config import settings

SRC = settings.EXERCISES_JSON_PATH
BACKUP = settings.BACKUP_DIR / "exercises_pre_batch16_backup.json"

# equipment_level values taken from existing exercises using this equipment
# (see data/exercises.json) so new entries stay consistent.
EQUIPMENT_LEVEL = {
    "Dumbbell": 3,
    "Barbell": 5,
    "Bodyweight": 1,
}

# arm-isolation accessory work — general hypertrophy tool, moderate but
# secondary transfer to grappling/combat sports (grip/pull assistance),
# noticeably higher for Look Jacked since these are classic aesthetic lifts.
TEMPLATE_CURL = {
    "Wrestling": 40, "Judo": 40, "Sambo": 40, "BJJ": 40, "Boxing": 42,
    "Muay Thai": 42, "Kickboxing": 42, "Sanda": 42, "Rugby": 45,
    "Rock Climbing": 35, "HYROX": 35, "Special Forces": 40, "MMA": 41,
    "Powerlifting": 30, "Look Jacked": 55,
}
TEMPLATE_TRICEP = {
    "Wrestling": 42, "Judo": 40, "Sambo": 40, "BJJ": 38, "Boxing": 48,
    "Muay Thai": 48, "Kickboxing": 48, "Sanda": 48, "Rugby": 48,
    "Rock Climbing": 32, "HYROX": 40, "Special Forces": 45, "MMA": 45,
    "Powerlifting": 33, "Look Jacked": 55,
}


def sp(template, **overrides):
    d = dict(template)
    d.update(overrides)
    return d


def ex(id_, name, category, pattern, difficulty, level, equipment,
       primary, secondary, stabilizers, joint_stress, injuries, reqs,
       template, **sp_overrides):
    return {
        "id": id_, "name": name, "category": category, "movement_pattern": pattern,
        "difficulty": difficulty, "experience_level": level,
        "equipment": equipment, "equipment_level": EQUIPMENT_LEVEL[equipment],
        "primary_muscles": primary, "secondary_muscles": secondary, "stabilizers": stabilizers,
        "joint_stress": joint_stress, "injuries_to_avoid": injuries,
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0,
                                   "pullups": 0, "pushups": 0, **reqs},
        "progressions": [], "regressions": [], "alternatives": [],
        "sport_priority": sp(template, **sp_overrides),
    }


NEW = []

# ---- Biceps (+5) ----
NEW += [
ex("db_bicepcurl_001", "Standing Dumbbell Bicep Curl", "Vertical Pull", "Pull", 1, "Beginner", "Dumbbell",
   ["Biceps Brachii"], ["Forearms"], [],
   ["Elbow"], [],
   {}, TEMPLATE_CURL),
ex("db_hammercurl_001", "Dumbbell Hammer Curl", "Vertical Pull", "Pull", 1, "Beginner", "Dumbbell",
   ["Biceps Brachii", "Forearms"], ["Forearm Flexors"], [],
   ["Elbow"], [],
   {}, TEMPLATE_CURL, **{"Rock Climbing": 45}),
ex("bb_curl_001", "Standing Barbell Curl", "Vertical Pull", "Pull", 2, "Novice", "Barbell",
   ["Biceps Brachii"], ["Forearms"], ["Core"],
   ["Elbow", "Lower Back"], ["Medial Epicondylalgia (Golfer's Elbow)"],
   {}, TEMPLATE_CURL),
ex("db_concentrationcurl_001", "Dumbbell Concentration Curl", "Vertical Pull", "Pull", 2, "Novice", "Dumbbell",
   ["Biceps Brachii"], ["Forearms"], [],
   ["Elbow"], [],
   {}, TEMPLATE_CURL, **{"Look Jacked": 58}),
ex("db_inclinecurl_001", "Incline Dumbbell Curl", "Vertical Pull", "Pull", 2, "Novice", "Dumbbell",
   ["Biceps Brachii"], ["Forearms"], ["Shoulder"],
   ["Elbow", "Shoulder"], ["Long Head Biceps Tendon - Tendinitis/Tendinosis (Tendinopathy)"],
   {}, TEMPLATE_CURL, **{"Look Jacked": 58}),
]

# ---- Triceps (+5) ----
NEW += [
ex("db_overheadtricep_001", "Dumbbell Overhead Tricep Extension", "Vertical Push", "Push", 2, "Novice", "Dumbbell",
   ["Triceps Brachii"], [], ["Core"],
   ["Elbow", "Shoulder"], ["Lateral Epicondylalgia (Tennis Elbow)"],
   {}, TEMPLATE_TRICEP),
ex("db_tricepkickback_001", "Dumbbell Tricep Kickback", "Vertical Push", "Push", 1, "Beginner", "Dumbbell",
   ["Triceps Brachii"], [], ["Core"],
   ["Elbow"], [],
   {}, TEMPLATE_TRICEP),
ex("db_skullcrusher_001", "Dumbbell Skullcrusher", "Horizontal Push", "Push", 2, "Novice", "Dumbbell",
   ["Triceps Brachii"], [], [],
   ["Elbow"], ["UCL Sprain - Grade III Sprain (Complete Rupture)"],
   {}, TEMPLATE_TRICEP),
ex("bodyweight_benchdip_001", "Bench Dip", "Vertical Push", "Push", 2, "Novice", "Bodyweight",
   ["Triceps Brachii"], ["Anterior Deltoid"], ["Core"],
   ["Elbow", "Shoulder"], ["Shoulder Instability (General/Atraumatic)"],
   {"pushups": 1}, TEMPLATE_TRICEP),
ex("bb_closegripfloorpress_001", "Barbell Close-Grip Floor Press", "Horizontal Push", "Push", 2, "Novice", "Barbell",
   ["Triceps Brachii"], ["Pectoralis Major"], ["Core"],
   ["Elbow", "Wrist", "Shoulder"], ["Medial Epicondylalgia (Golfer's Elbow)"],
   {"bench_ratio": 0.6}, TEMPLATE_TRICEP),
]

print(f"Generated {len(NEW)} new exercises across "
      f"{len(set(e['equipment'] for e in NEW))} equipment types.")


def main():
    settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_ids = {e["id"] for e in data["exercises"]}
    dupes = [e["id"] for e in NEW if e["id"] in existing_ids]
    if dupes:
        raise SystemExit(f"Duplicate IDs, aborting: {dupes}")

    seen = set()
    internal_dupes = [e["id"] for e in NEW if e["id"] in seen or seen.add(e["id"])]
    if internal_dupes:
        raise SystemExit(f"Duplicate IDs within this batch, aborting: {internal_dupes}")

    data["exercises"].extend(NEW)

    data["version"] = "5.12.0"
    data["schema_notes"] += (
        "\n\nv5.12 adds 10 new exercises (generate_batch16_arms_curl_tricep.py, "
        "769 -> 779) closing a gap where Dumbbell and Barbell had zero bicep-curl "
        "or triceps-isolation entries despite being the two most common equipment "
        "types: Standing Dumbbell Bicep Curl, Dumbbell Hammer Curl, Standing "
        "Barbell Curl, Dumbbell Concentration Curl, Incline Dumbbell Curl, "
        "Dumbbell Overhead Tricep Extension, Dumbbell Tricep Kickback, Dumbbell "
        "Skullcrusher, Bench Dip, and Barbell Close-Grip Floor Press. Run through "
        "the same enrich_exercise() pipeline as the rest of the database."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(data['exercises'])} total exercises to {SRC}. "
          f"Backup at {BACKUP}. Now run scripts/enrichment/enrich_exercises.py.")


if __name__ == "__main__":
    main()

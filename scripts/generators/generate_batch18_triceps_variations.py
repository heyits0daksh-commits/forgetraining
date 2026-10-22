"""
generate_batch18_triceps_variations.py — adds 9 new pure triceps-isolation
exercises. The database had 64 exercises where Triceps Brachii appears
somewhere (mostly presses/dips where triceps is a secondary mover), but
only 11 where it's the sole primary muscle (EZ Bar Skullcrusher, Close Grip
Bench Press, Board Press, Cable Tricep Pushdown, Cable Overhead Tricep
Extension, Band Overhead Tricep Extension, Dumbbell Overhead Tricep
Extension, Dumbbell Tricep Kickback, Dumbbell Skullcrusher, Bench Dip,
Barbell Close-Grip Floor Press) — no plain Barbell Skullcrusher/JM Press,
no Dumbbell Tate Press or single-arm overhead extension, and only 2 of the
4 common cable-pushdown attachments (plain + overhead), missing rope,
V-bar, reverse-grip, and single-arm.

WHY THESE: cross-checked against the existing 11 to avoid duplicates.
Follows the exact pattern of generate_batch16/17: reuses each equipment's
EXISTING equipment_level (Barbell 5, Dumbbell 3, Cable Machine 10), reuses
exact taxonomy-matching injury strings already used elsewhere in the file
plus the Triceps Tendon / Triceps Strain entries confirmed against
injury_taxonomy.py.

Run: python scripts/generators/generate_batch18_triceps_variations.py
Then: python scripts/enrichment/enrich_exercises.py   (derives v4.0+ fields for the new entries)
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from backend.core.config import settings

SRC = settings.EXERCISES_JSON_PATH
BACKUP = settings.BACKUP_DIR / "exercises_pre_batch18_backup.json"

EQUIPMENT_LEVEL = {
    "Barbell": 5,
    "Dumbbell": 3,
    "Cable Machine": 10,
}

# same accessory-lift sport_priority template batch16/17 used for arm
# isolation work — moderate secondary transfer to striking/grappling
# (lockout strength), noticeably higher for Look Jacked.
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

NEW += [
ex("bb_skullcrusher_001", "Barbell Skullcrusher", "Horizontal Push", "Push", 2, "Novice", "Barbell",
   ["Triceps Brachii"], [], [],
   ["Elbow"], ["Triceps Tendon - Tendinitis/Tendinosis (Tendinopathy)"],
   {}, TEMPLATE_TRICEP),
ex("bb_jmpress_001", "Barbell JM Press", "Horizontal Push", "Push", 3, "Intermediate", "Barbell",
   ["Triceps Brachii"], ["Pectoralis Major"], [],
   ["Elbow", "Shoulder"], ["Triceps Tendon - Tendinitis/Tendinosis (Tendinopathy)"],
   {"bench_ratio": 0.55}, TEMPLATE_TRICEP),
ex("db_tatepress_001", "Dumbbell Tate Press", "Horizontal Push", "Push", 2, "Novice", "Dumbbell",
   ["Triceps Brachii"], [], [],
   ["Elbow"], ["Triceps Tendon - Tendinitis/Tendinosis (Tendinopathy)"],
   {}, TEMPLATE_TRICEP),
ex("db_singlearmoverheadtricep_001", "Dumbbell Single-Arm Overhead Tricep Extension", "Vertical Push", "Push", 2, "Novice", "Dumbbell",
   ["Triceps Brachii"], [], ["Core"],
   ["Elbow", "Shoulder"], [],
   {}, TEMPLATE_TRICEP),
ex("cable_ropepushdown_001", "Cable Rope Tricep Pushdown", "Vertical Push", "Push", 1, "Beginner", "Cable Machine",
   ["Triceps Brachii"], [], [],
   ["Elbow"], [],
   {}, TEMPLATE_TRICEP),
ex("cable_vbarpushdown_001", "Cable V-Bar Tricep Pushdown", "Vertical Push", "Push", 1, "Beginner", "Cable Machine",
   ["Triceps Brachii"], [], [],
   ["Elbow"], [],
   {}, TEMPLATE_TRICEP),
ex("cable_reversegrippushdown_001", "Cable Reverse-Grip Tricep Pushdown", "Vertical Push", "Push", 2, "Novice", "Cable Machine",
   ["Triceps Brachii"], ["Forearms"], [],
   ["Elbow", "Wrist"], [],
   {}, TEMPLATE_TRICEP),
ex("cable_singlearmpushdown_001", "Cable Single-Arm Tricep Pushdown", "Vertical Push", "Push", 2, "Novice", "Cable Machine",
   ["Triceps Brachii"], [], ["Core"],
   ["Elbow"], [],
   {}, TEMPLATE_TRICEP),
ex("cable_ropeoverheadext_001", "Cable Rope Overhead Tricep Extension", "Vertical Push", "Push", 2, "Novice", "Cable Machine",
   ["Triceps Brachii"], [], ["Core"],
   ["Elbow", "Shoulder"], [],
   {}, TEMPLATE_TRICEP),
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

    data["version"] = "5.14.0"
    data["schema_notes"] += (
        "\n\nv5.14 adds 9 new triceps-isolation exercises (generate_batch18_"
        "triceps_variations.py, 789 -> 798) closing gaps left after batch16: "
        "Barbell Skullcrusher, Barbell JM Press, Dumbbell Tate Press, "
        "Dumbbell Single-Arm Overhead Tricep Extension, Cable Rope Tricep "
        "Pushdown, Cable V-Bar Tricep Pushdown, Cable Reverse-Grip Tricep "
        "Pushdown, Cable Single-Arm Tricep Pushdown, and Cable Rope Overhead "
        "Tricep Extension. Run through the same enrich_exercise() pipeline "
        "as the rest of the database."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(data['exercises'])} total exercises to {SRC}. "
          f"Backup at {BACKUP}. Now run scripts/enrichment/enrich_exercises.py.")


if __name__ == "__main__":
    main()

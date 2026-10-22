"""
generate_batch17_curl_variations.py — adds 10 biceps curl variations that
were still missing after batch16 (which only closed the Dumbbell/Barbell
"zero entries" gap with 5 basic curls). This batch rounds the curl family
out with the well-known variations lifters actually ask for: preacher,
spider, drag, Zottman, cross-body hammer, cable rope hammer, single-arm
cable, 21s, waiter, and reverse-grip barbell curl.

WHY THESE: cross-checked against the existing 9 curl entries (EZ Bar Curl,
Cable Bicep Curl, EZ Bar Reverse Curl, EZ Bar Preacher Curl, Standing
Dumbbell Bicep Curl, Dumbbell Hammer Curl, Standing Barbell Curl, Dumbbell
Concentration Curl, Incline Dumbbell Curl) — every exercise below is a
distinct movement pattern/equipment combo not already covered (e.g. a
Dumbbell Preacher Curl and Barbell Reverse Curl didn't exist even though
their EZ-bar counterparts did).

Follows the exact pattern of generate_batch16_arms_curl_tricep.py: reuses
each equipment's EXISTING equipment_level (Dumbbell 3, Barbell 5, EZ Curl
Bar 21, Cable Machine 10), reuses exact taxonomy-matching injury strings
already used elsewhere in the file (Medial Epicondylalgia (Golfer's Elbow),
Long Head Biceps Tendon - Tendinitis/Tendinosis (Tendinopathy), Distal
Biceps Tendon Rupture).

Run: python scripts/generators/generate_batch17_curl_variations.py
Then: python scripts/enrichment/enrich_exercises.py   (derives v4.0+ fields for the new entries)
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from backend.core.config import settings

SRC = settings.EXERCISES_JSON_PATH
BACKUP = settings.BACKUP_DIR / "exercises_pre_batch17_backup.json"

# equipment_level values taken from existing exercises using this equipment
# (see data/exercises.json) so new entries stay consistent.
EQUIPMENT_LEVEL = {
    "Dumbbell": 3,
    "Barbell": 5,
    "EZ Curl Bar": 21,
    "Cable Machine": 10,
}

# same accessory-lift sport_priority template batch16 used — general
# hypertrophy tool, moderate secondary transfer to grappling/combat sports
# (grip/pull assistance), noticeably higher for Look Jacked.
TEMPLATE_CURL = {
    "Wrestling": 40, "Judo": 40, "Sambo": 40, "BJJ": 40, "Boxing": 42,
    "Muay Thai": 42, "Kickboxing": 42, "Sanda": 42, "Rugby": 45,
    "Rock Climbing": 35, "HYROX": 35, "Special Forces": 40, "MMA": 41,
    "Powerlifting": 30, "Look Jacked": 55,
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
ex("db_preachercurl_001", "Dumbbell Preacher Curl", "Vertical Pull", "Pull", 2, "Novice", "Dumbbell",
   ["Biceps Brachii"], ["Forearms"], [],
   ["Elbow"], ["Distal Biceps Tendon Rupture"],
   {}, TEMPLATE_CURL, **{"Look Jacked": 58}),
ex("ezbar_spidercurl_001", "EZ Bar Spider Curl", "Vertical Pull", "Pull", 2, "Novice", "EZ Curl Bar",
   ["Biceps Brachii"], ["Forearms"], [],
   ["Elbow"], ["Distal Biceps Tendon Rupture"],
   {}, TEMPLATE_CURL, **{"Look Jacked": 58}),
ex("bb_dragcurl_001", "Barbell Drag Curl", "Vertical Pull", "Pull", 2, "Novice", "Barbell",
   ["Biceps Brachii"], ["Forearms"], ["Core"],
   ["Elbow", "Shoulder"], ["Medial Epicondylalgia (Golfer's Elbow)"],
   {}, TEMPLATE_CURL),
ex("db_zottmancurl_001", "Dumbbell Zottman Curl", "Vertical Pull", "Pull", 2, "Novice", "Dumbbell",
   ["Biceps Brachii", "Forearms"], ["Forearm Flexors"], [],
   ["Elbow", "Wrist"], [],
   {}, TEMPLATE_CURL, **{"Rock Climbing": 45}),
ex("db_crossbodyhammercurl_001", "Dumbbell Cross-Body Hammer Curl", "Vertical Pull", "Pull", 1, "Beginner", "Dumbbell",
   ["Biceps Brachii", "Forearms"], ["Forearm Flexors"], [],
   ["Elbow"], [],
   {}, TEMPLATE_CURL, **{"Rock Climbing": 45}),
ex("cable_ropehammercurl_001", "Cable Rope Hammer Curl", "Vertical Pull", "Pull", 1, "Beginner", "Cable Machine",
   ["Biceps Brachii", "Forearms"], ["Forearm Flexors"], [],
   ["Elbow"], [],
   {}, TEMPLATE_CURL, **{"Rock Climbing": 45}),
ex("cable_singlearmcurl_001", "Single-Arm Cable Curl", "Vertical Pull", "Pull", 1, "Beginner", "Cable Machine",
   ["Biceps Brachii"], ["Forearms"], ["Core"],
   ["Elbow"], [],
   {}, TEMPLATE_CURL),
ex("bb_21s_001", "Barbell 21s", "Vertical Pull", "Pull", 3, "Intermediate", "Barbell",
   ["Biceps Brachii"], ["Forearms"], ["Core"],
   ["Elbow"], ["Long Head Biceps Tendon - Tendinitis/Tendinosis (Tendinopathy)"],
   {}, TEMPLATE_CURL, **{"Look Jacked": 60}),
ex("db_waitercurl_001", "Dumbbell Waiter Curl", "Vertical Pull", "Pull", 2, "Novice", "Dumbbell",
   ["Biceps Brachii"], ["Forearms"], ["Core"],
   ["Elbow", "Wrist"], [],
   {}, TEMPLATE_CURL),
ex("bb_reversecurl_001", "Barbell Reverse Curl", "Vertical Pull", "Pull", 2, "Novice", "Barbell",
   ["Forearm Flexors", "Biceps Brachii"], ["Forearms"], [],
   ["Elbow", "Wrist"], ["Lateral Epicondylalgia (Tennis Elbow)"],
   {}, TEMPLATE_CURL, **{"Rock Climbing": 45}),
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

    data["version"] = "5.13.0"
    data["schema_notes"] += (
        "\n\nv5.13 adds 10 new biceps curl variations (generate_batch17_"
        "curl_variations.py, 779 -> 789) rounding out the curl family beyond "
        "batch16's basic Dumbbell/Barbell curls: Dumbbell Preacher Curl, EZ "
        "Bar Spider Curl, Barbell Drag Curl, Dumbbell Zottman Curl, Dumbbell "
        "Cross-Body Hammer Curl, Cable Rope Hammer Curl, Single-Arm Cable "
        "Curl, Barbell 21s, Dumbbell Waiter Curl, and Barbell Reverse Curl. "
        "Run through the same enrich_exercise() pipeline as the rest of the "
        "database."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(data['exercises'])} total exercises to {SRC}. "
          f"Backup at {BACKUP}. Now run scripts/enrichment/enrich_exercises.py.")


if __name__ == "__main__":
    main()

"""
generate_batch19_new_equipment.py — introduces two new equipment types the
database had no entries for at all: "Bench" (a flat/utility bench used as
the defining piece of equipment — feet/hands/back elevated or supported)
and "Sit-Up Bench" (an adjustable decline board for weighted ab work).

WHY: the database already tags exercises by whichever apparatus actually
defines the movement (e.g. "Landmine", "GHD", "Ab Wheel" are all equipment
values even though the load itself is a barbell/bodyweight) — but nothing
used "Bench" or "Sit-Up Bench" that way, even though a flat bench is
required hardware for a huge chunk of a real gym (bench press variations
already exist tagged by their load implement — Barbell/Dumbbell/Smith
Machine/etc — consistent with that same pattern; this batch does NOT
retag those, it adds the movements where the bench itself, not a barbell
or dumbbell, is the defining piece of equipment and none of which already
exist under another equipment tag).

Checked against the full existing exercise list first: Bulgarian Split
Squat, Step-Up, Single-Leg Hip Thrust, Incline Push-Up, and Bench Dip
already exist (tagged Dumbbell/Plyo Box/Bodyweight/Bodyweight respectively)
— every exercise below is a distinct bench-defined movement not already
in the file.

Follows the exact pattern of generate_batch16/17/18: new equipment_levels
(48, 49) picked past the current max (47, Balance Board) so nothing
collides; injuries_to_avoid reuses exact taxonomy-matching strings already
used elsewhere in the file (Low Back Pain, Shoulder Instability
(General/Atraumatic)).

Run: python scripts/generators/generate_batch19_new_equipment.py
Then: python scripts/enrichment/enrich_exercises.py   (derives v4.0+ fields for the new entries)
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from backend.core.config import settings

SRC = settings.EXERCISES_JSON_PATH
BACKUP = settings.BACKUP_DIR / "exercises_pre_batch19_backup.json"

EQUIPMENT_LEVEL = {
    "Bench": 48,
    "Sit-Up Bench": 49,
}

# bodyweight push-family template, matched to Incline Push-Up's existing
# sport_priority (grappling/combat-heavy, low powerlifting/aesthetic
# transfer since it's an unweighted bodyweight movement).
TEMPLATE_PUSH_BW = {
    "Wrestling": 70, "Judo": 75, "Sambo": 75, "BJJ": 75, "Boxing": 65,
    "Muay Thai": 65, "Kickboxing": 65, "Sanda": 65, "Rugby": 55,
    "Rock Climbing": 80, "HYROX": 55, "Special Forces": 85, "MMA": 69,
    "Powerlifting": 35, "Look Jacked": 42,
}
# loaded triceps-isolation template, matched to Bench Dip's existing
# sport_priority.
TEMPLATE_TRICEP = {
    "Wrestling": 42, "Judo": 40, "Sambo": 40, "BJJ": 38, "Boxing": 48,
    "Muay Thai": 48, "Kickboxing": 48, "Sanda": 48, "Rugby": 48,
    "Rock Climbing": 32, "HYROX": 40, "Special Forces": 45, "MMA": 45,
    "Powerlifting": 33, "Look Jacked": 55,
}
# unilateral hinge/glute template, matched to Single-Leg Hip Thrust's
# existing sport_priority.
TEMPLATE_HINGE = {
    "Wrestling": 80, "Judo": 75, "Sambo": 75, "BJJ": 65, "Boxing": 65,
    "Muay Thai": 75, "Kickboxing": 75, "Sanda": 75, "Rugby": 85,
    "Rock Climbing": 45, "HYROX": 90, "Special Forces": 90, "MMA": 72,
    "Powerlifting": 47, "Look Jacked": 33,
}
# core/ab template, matched to GHD Sit-Up's existing sport_priority.
TEMPLATE_CORE = {
    "Wrestling": 70, "Judo": 70, "Sambo": 70, "BJJ": 70, "Boxing": 60,
    "Muay Thai": 65, "Kickboxing": 65, "Sanda": 65, "Rugby": 70,
    "Rock Climbing": 60, "HYROX": 75, "Special Forces": 80, "MMA": 66,
    "Powerlifting": 18, "Look Jacked": 22,
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

# ---- Bench (+5) ----
NEW += [
ex("bench_declinepushup_001", "Decline Push-Up (Bench)", "Horizontal Push", "Push", 2, "Novice", "Bench",
   ["Pectoralis Major", "Anterior Deltoid"], ["Triceps Brachii"], ["Core"],
   ["Wrist", "Shoulder"], ["Shoulder Instability (General/Atraumatic)"],
   {"pushups": 1}, TEMPLATE_PUSH_BW),
ex("bench_weighteddip_001", "Weighted Bench Dip", "Vertical Push", "Push", 2, "Novice", "Bench",
   ["Triceps Brachii"], ["Anterior Deltoid"], ["Core"],
   ["Elbow", "Shoulder"], ["Shoulder Instability (General/Atraumatic)"],
   {"pushups": 1}, TEMPLATE_TRICEP),
ex("bench_singleleghipthrust_001", "Bench Single-Leg Hip Thrust", "Hinge", "Hinge", 2, "Novice", "Bench",
   ["Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Lower Back", "Hip"], [],
   {}, TEMPLATE_HINGE),
ex("bench_elevatedplank_001", "Elevated Plank (Bench)", "Core", "Isometric", 2, "Novice", "Bench",
   ["Rectus Abdominis"], ["Obliques"], ["Shoulder"],
   ["Lower Back", "Shoulder"], [],
   {}, TEMPLATE_CORE),
ex("bench_pikepushup_001", "Bench Pike Push-Up", "Vertical Push", "Push", 3, "Intermediate", "Bench",
   ["Anterior Deltoid", "Triceps Brachii"], ["Upper Trapezius"], [],
   ["Wrist", "Shoulder"], ["Shoulder Instability (General/Atraumatic)"],
   {}, TEMPLATE_PUSH_BW, **{"Look Jacked": 48}),
]

# ---- Sit-Up Bench (+5) ----
NEW += [
ex("situpbench_declinesitup_001", "Decline Sit-Up", "Core", "Flexion", 2, "Novice", "Sit-Up Bench",
   ["Rectus Abdominis"], ["Hip Flexors"], [],
   ["Lower Back"], ["Low Back Pain"],
   {}, TEMPLATE_CORE),
ex("situpbench_declinecrunch_001", "Decline Crunch", "Core", "Flexion", 1, "Beginner", "Sit-Up Bench",
   ["Rectus Abdominis"], [], [],
   ["Lower Back"], [],
   {}, TEMPLATE_CORE),
ex("situpbench_declinetwist_001", "Decline Russian Twist", "Core", "Rotational", 2, "Novice", "Sit-Up Bench",
   ["Obliques"], ["Rectus Abdominis"], [],
   ["Lower Back"], ["Low Back Pain"],
   {}, TEMPLATE_CORE),
ex("situpbench_declineraise_001", "Decline Bench Leg Raise", "Core", "Flexion", 2, "Novice", "Sit-Up Bench",
   ["Rectus Abdominis"], ["Hip Flexors"], [],
   ["Lower Back", "Hip"], ["Low Back Pain"],
   {}, TEMPLATE_CORE),
ex("situpbench_weighteddeclinesitup_001", "Weighted Decline Sit-Up", "Core", "Flexion", 3, "Intermediate", "Sit-Up Bench",
   ["Rectus Abdominis"], ["Hip Flexors"], [],
   ["Lower Back"], ["Low Back Pain"],
   {}, TEMPLATE_CORE, **{"Look Jacked": 30}),
]

print(f"Generated {len(NEW)} new exercises across "
      f"{len(set(e['equipment'] for e in NEW))} new equipment types.")


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

    data["version"] = "5.15.0"
    data["schema_notes"] += (
        "\n\nv5.15 introduces two new equipment types the database had zero "
        "entries for (generate_batch19_new_equipment.py, 798 -> 808): "
        "\"Bench\" (Decline Push-Up (Bench), Weighted Bench Dip, Bench "
        "Single-Leg Hip Thrust, Elevated Plank (Bench), Bench Pike Push-Up) "
        "and \"Sit-Up Bench\" (Decline Sit-Up, Decline Crunch, Decline "
        "Russian Twist, Decline Bench Leg Raise, Weighted Decline Sit-Up). "
        "Existing Bench Press variations are intentionally left tagged by "
        "their load implement (Barbell/Dumbbell/Smith Machine/etc), "
        "consistent with how Landmine/GHD/Ab Wheel already work in this "
        "file - this batch only adds movements where the bench itself, not "
        "a barbell or dumbbell, is the defining piece of equipment and none "
        "of which existed under another equipment tag (checked against "
        "Bulgarian Split Squat, Step-Up, Single-Leg Hip Thrust, Incline "
        "Push-Up, and Bench Dip, which were already present elsewhere). Run "
        "through the same enrich_exercise() pipeline as the rest of the "
        "database."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(data['exercises'])} total exercises to {SRC}. "
          f"Backup at {BACKUP}. Now run scripts/enrichment/enrich_exercises.py.")


if __name__ == "__main__":
    main()

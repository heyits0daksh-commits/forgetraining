"""
generate_batch6_thin_equipment.py — adds exercises to the equipment types
that were thinnest relative to how common they are in a real commercial
gym: Cable Machine, Lat Pulldown Machine, Leg Press Machine, Leg Curl
Machine, Leg Extension Machine, Seated Row Machine, Chest Press Machine,
Shoulder Press Machine, Pec Deck Machine, Smith Machine, Hack Squat
Machine, High Row Machine, Resistance Band, and Medicine Ball.

WHY THESE: batch2-5 filled out combat-sport/strongman/powerlifting-specific
equipment. Now that FORGE is aimed at general commercial-app users (not
just the manual's combat-sport athletes), the biggest remaining gap is
standard machine-based gym equipment — most general-public gym-goers train
on cable stacks and selectorized machines far more than atlas stones or
axle bars, and those equipment types had only 1-3 exercises each (vs.
30-40+ for Barbell/Bodyweight).

Follows the exact pattern of generate_batch2/3_equipment.py: hand-tagged
joint_stress / injuries_to_avoid per exercise (not machine-generated),
reuses each equipment's EXISTING equipment_level (checked against the
current exercises.json rather than inventing new numbers), small and
reviewable rather than exhaustive.

Run: python scripts/generate_batch6_thin_equipment.py
Then: python scripts/enrich_exercises.py   (derives v4.0+ fields for the new entries)
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from backend.core.config import settings

SRC = settings.EXERCISES_JSON_PATH
BACKUP = settings.BACKUP_DIR / "exercises_pre_batch6_backup.json"

# equipment_level values taken from the existing exercises for each of
# these equipment names (see data/exercises.json) so new entries stay
# consistent with what's already there rather than inventing new numbers.
EQUIPMENT_LEVEL = {
    "Cable Machine": 10,
    "Lat Pulldown Machine": 15,
    "Leg Press Machine": 13,
    "Leg Curl Machine": 18,
    "Leg Extension Machine": 17,
    "Seated Row Machine": 16,
    "Chest Press Machine": 41,
    "Shoulder Press Machine": 42,
    "Pec Deck Machine": 19,
    "Smith Machine": 20,
    "Hack Squat Machine": 14,
    "High Row Machine": 43,
    "Resistance Band": 8,
    "Medicine Ball": 20,
}

TEMPLATES = {
    # cable/machine isolation & accessory work — general hypertrophy tool,
    # moderate transfer to every combat/field sport, not a specialty lift
    "machine_iso": {"Wrestling": 45, "Judo": 45, "Sambo": 45, "BJJ": 45, "Boxing": 50,
                     "Muay Thai": 50, "Kickboxing": 50, "Sanda": 50, "Rugby": 55,
                     "Rock Climbing": 40, "HYROX": 45, "Special Forces": 45, "MMA": 48},
    # machine/cable pressing (chest, shoulder press machines, smith bench/OHP)
    "machine_push": {"Wrestling": 55, "Judo": 50, "Sambo": 55, "BJJ": 50, "Boxing": 65,
                      "Muay Thai": 60, "Kickboxing": 60, "Sanda": 60, "Rugby": 65,
                      "Rock Climbing": 30, "HYROX": 60, "Special Forces": 65, "MMA": 58},
    # machine/cable pulling (lat pulldown, seated row, high row, cable row)
    "machine_pull": {"Wrestling": 65, "Judo": 65, "Sambo": 65, "BJJ": 65, "Boxing": 55,
                      "Muay Thai": 55, "Kickboxing": 55, "Sanda": 55, "Rugby": 60,
                      "Rock Climbing": 55, "HYROX": 50, "Special Forces": 60, "MMA": 60},
    # machine leg work (leg press, leg curl, leg extension, hack squat)
    "machine_legs": {"Wrestling": 60, "Judo": 60, "Sambo": 60, "BJJ": 55, "Boxing": 45,
                      "Muay Thai": 55, "Kickboxing": 55, "Sanda": 55, "Rugby": 75,
                      "Rock Climbing": 30, "HYROX": 70, "Special Forces": 70, "MMA": 55},
    # smith machine compound lifts — fixed bar path, beginner-friendly version
    # of the free-weight compound
    "smith_compound": {"Wrestling": 55, "Judo": 55, "Sambo": 55, "BJJ": 50, "Boxing": 45,
                        "Muay Thai": 45, "Kickboxing": 45, "Sanda": 45, "Rugby": 65,
                        "Rock Climbing": 25, "HYROX": 55, "Special Forces": 60, "MMA": 50},
    # resistance-band accessory / prehab / warm-up work
    "band_accessory": {"Wrestling": 50, "Judo": 50, "Sambo": 50, "BJJ": 50, "Boxing": 55,
                        "Muay Thai": 55, "Kickboxing": 55, "Sanda": 55, "Rugby": 50,
                        "Rock Climbing": 50, "HYROX": 45, "Special Forces": 50, "MMA": 52},
    # medicine-ball explosive/power & rotational conditioning work
    "medball_power": {"Wrestling": 65, "Judo": 65, "Sambo": 60, "BJJ": 55, "Boxing": 75,
                       "Muay Thai": 75, "Kickboxing": 75, "Sanda": 75, "Rugby": 75,
                       "Rock Climbing": 40, "HYROX": 70, "Special Forces": 75, "MMA": 70},
}


def sp(template, **overrides):
    d = dict(TEMPLATES[template])
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

# ---- Cable Machine (+8) ----
NEW += [
ex("cable_triceppushdown_001", "Cable Tricep Pushdown", "Vertical Push", "Push", 1, "Beginner", "Cable Machine",
   ["Triceps Brachii"], [], [],
   ["Elbow"], ["Tennis Elbow"],
   {}, "machine_iso"),
ex("cable_bicepcurl_001", "Cable Bicep Curl", "Vertical Pull", "Pull", 1, "Beginner", "Cable Machine",
   ["Biceps Brachii"], ["Forearms"], [],
   ["Elbow"], [],
   {}, "machine_iso"),
ex("cable_facepull_001", "Cable Face Pull", "Horizontal Pull", "Pull", 2, "Novice", "Cable Machine",
   ["Rear Deltoid", "Rhomboids"], ["Traps"], ["Rotator Cuff"],
   ["Shoulder"], ["Shoulder Instability", "Rotator Cuff"],
   {}, "machine_iso", Boxing=70, **{"Muay Thai": 68, "Kickboxing": 68}),
ex("cable_woodchopper_001", "Cable Woodchopper", "Rotational", "Rotational", 2, "Novice", "Cable Machine",
   ["Obliques"], ["Core"], ["Hip"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "machine_iso", Wrestling=65, Judo=65, Sambo=65, BJJ=60, Rugby=65, MMA=62),
ex("cable_lateralraise_001", "Cable Lateral Raise", "Vertical Push", "Push", 1, "Beginner", "Cable Machine",
   ["Lateral Deltoid"], [], [],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "machine_iso"),
ex("cable_chestfly_001", "Cable Chest Fly", "Horizontal Push", "Push", 2, "Novice", "Cable Machine",
   ["Pectoralis Major"], ["Anterior Deltoid"], [],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "machine_iso"),
ex("cable_overheadtricep_001", "Cable Overhead Tricep Extension", "Vertical Push", "Push", 2, "Novice", "Cable Machine",
   ["Triceps Brachii"], [], ["Core"],
   ["Elbow", "Shoulder"], ["Tennis Elbow"],
   {}, "machine_iso"),
ex("cable_pallofpress_001", "Cable Pallof Press", "Core", "Anti-Rotation", 2, "Novice", "Cable Machine",
   ["Obliques", "Core"], [], ["Shoulder"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "machine_iso", Wrestling=60, Judo=60, Sambo=60, BJJ=60, Rugby=55, **{"Rock Climbing": 55}, MMA=58),
]

# ---- Lat Pulldown Machine (+3) ----
NEW += [
ex("latpulldown_vbar_001", "V-Bar Lat Pulldown", "Vertical Pull", "Pull", 2, "Novice", "Lat Pulldown Machine",
   ["Latissimus Dorsi"], ["Biceps Brachii", "Rhomboids"], [],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {"pullups": 1}, "machine_pull"),
ex("latpulldown_reversegrip_001", "Reverse-Grip Lat Pulldown", "Vertical Pull", "Pull", 2, "Novice", "Lat Pulldown Machine",
   ["Latissimus Dorsi"], ["Biceps Brachii"], [],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {"pullups": 1}, "machine_pull"),
ex("latpulldown_straightarm_001", "Straight-Arm Pulldown", "Vertical Pull", "Pull", 2, "Novice", "Lat Pulldown Machine",
   ["Latissimus Dorsi"], ["Triceps Brachii"], ["Core"],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "machine_pull"),
]

# ---- Leg Press Machine (+3) ----
NEW += [
ex("legpress_narrow_001", "Narrow-Stance Leg Press", "Squat", "Squat", 2, "Novice", "Leg Press Machine",
   ["Quadriceps"], ["Glutes"], [],
   ["Knee"], ["Meniscus Tear - Grade 3 (True Structural Tear)", "Jumper's Knee (Patellar Tendinopathy)"],
   {"squat_ratio": 0.9}, "machine_legs"),
ex("legpress_wide_001", "Wide-Stance Leg Press", "Squat", "Squat", 2, "Novice", "Leg Press Machine",
   ["Glutes", "Quadriceps"], ["Hamstrings"], [],
   ["Knee", "Hip"], ["ACL/Ligament Tear - Grade 3 (Complete Rupture)"],
   {"squat_ratio": 0.9}, "machine_legs"),
ex("legpress_calfpress_001", "Calf Press on Leg Press Machine", "Calf Raise", "Isometric", 1, "Beginner", "Leg Press Machine",
   ["Gastrocnemius", "Soleus"], [], [],
   ["Ankle"], ["Achilles"],
   {}, "machine_legs"),
]

# ---- Leg Curl Machine (+2) ----
NEW += [
ex("legcurl_standing_001", "Standing Leg Curl", "Hinge", "Flexion", 2, "Novice", "Leg Curl Machine",
   ["Hamstrings"], [], ["Core"],
   ["Knee"], ["Hamstring Strain - Grade 2 (Partial Tear)"],
   {}, "machine_legs"),
ex("legcurl_singleleg_001", "Single-Leg Seated Leg Curl", "Hinge", "Flexion", 3, "Intermediate", "Leg Curl Machine",
   ["Hamstrings"], [], ["Core"],
   ["Knee"], ["Hamstring Strain - Grade 2 (Partial Tear)"],
   {}, "machine_legs"),
]

# ---- Leg Extension Machine (+2) ----
NEW += [
ex("legext_singleleg_001", "Single-Leg Extension", "Squat", "Isometric", 3, "Intermediate", "Leg Extension Machine",
   ["Quadriceps"], [], [],
   ["Knee"], ["Jumper's Knee (Patellar Tendinopathy)", "Meniscus Tear - Grade 3 (True Structural Tear)"],
   {}, "machine_legs"),
ex("legext_isohold_001", "Leg Extension Isometric Hold", "Squat", "Isometric", 2, "Novice", "Leg Extension Machine",
   ["Quadriceps"], [], [],
   ["Knee"], ["Jumper's Knee (Patellar Tendinopathy)"],
   {}, "machine_legs"),
]

# ---- Seated Row Machine (+3) ----
NEW += [
ex("seatedrow_closegrip_001", "Close-Grip Seated Row", "Horizontal Pull", "Pull", 2, "Novice", "Seated Row Machine",
   ["Rhomboids", "Latissimus Dorsi"], ["Biceps Brachii"], [],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {"pullups": 1}, "machine_pull"),
ex("seatedrow_neutralgrip_001", "Neutral-Grip Seated Row", "Horizontal Pull", "Pull", 2, "Novice", "Seated Row Machine",
   ["Rhomboids", "Latissimus Dorsi"], ["Biceps Brachii", "Rear Deltoid"], [],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {"pullups": 1}, "machine_pull"),
ex("seatedrow_highhandle_001", "High-Handle Seated Row", "Horizontal Pull", "Pull", 2, "Novice", "Seated Row Machine",
   ["Rear Deltoid", "Rhomboids"], ["Traps"], [],
   ["Shoulder"], ["Shoulder Instability", "Rotator Cuff"],
   {}, "machine_pull", Boxing=65, **{"Muay Thai": 62, "Kickboxing": 62}),
]

# ---- Chest Press Machine (+2) ----
NEW += [
ex("chest_press_incline_machine_001", "Incline Chest Press Machine", "Horizontal Push", "Push", 2, "Novice", "Chest Press Machine",
   ["Pectoralis Major", "Anterior Deltoid"], ["Triceps Brachii"], [],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {"bench_ratio": 0.55}, "machine_push"),
ex("chest_press_singlearm_machine_001", "Single-Arm Chest Press Machine", "Horizontal Push", "Push", 3, "Intermediate", "Chest Press Machine",
   ["Pectoralis Major"], ["Triceps Brachii", "Core"], ["Core"],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {"bench_ratio": 0.35}, "machine_push"),
]

# ---- Shoulder Press Machine (+2) ----
NEW += [
ex("shoulder_press_singlearm_machine_001", "Single-Arm Shoulder Press Machine", "Vertical Push", "Push", 3, "Intermediate", "Shoulder Press Machine",
   ["Anterior Deltoid"], ["Triceps Brachii", "Core"], ["Core"],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {}, "machine_push"),
ex("shoulder_press_neutralgrip_machine_001", "Neutral-Grip Shoulder Press Machine", "Vertical Push", "Push", 2, "Novice", "Shoulder Press Machine",
   ["Anterior Deltoid"], ["Triceps Brachii"], [],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {}, "machine_push"),
]

# ---- Pec Deck Machine (+2) ----
NEW += [
ex("pecdeck_reverse_001", "Reverse Pec Deck (Rear Delt Fly)", "Horizontal Pull", "Pull", 2, "Novice", "Pec Deck Machine",
   ["Rear Deltoid"], ["Rhomboids", "Traps"], [],
   ["Shoulder"], ["Shoulder Instability", "Rotator Cuff"],
   {}, "machine_pull"),
ex("pecdeck_singlearm_001", "Single-Arm Pec Deck Fly", "Horizontal Push", "Push", 2, "Novice", "Pec Deck Machine",
   ["Pectoralis Major"], ["Anterior Deltoid"], ["Core"],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "machine_push"),
]

# ---- Smith Machine (+4) ----
NEW += [
ex("smith_row_001", "Smith Machine Row", "Horizontal Pull", "Pull", 2, "Novice", "Smith Machine",
   ["Rhomboids", "Latissimus Dorsi"], ["Biceps Brachii", "Rear Deltoid"], ["Core"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {"pullups": 1}, "smith_compound"),
ex("smith_reverselunge_001", "Smith Machine Reverse Lunge", "Squat", "Lunge", 3, "Intermediate", "Smith Machine",
   ["Quadriceps", "Glutes"], ["Hamstrings"], ["Core"],
   ["Knee", "Hip", "Ankle"], ["ACL/Ligament Tear - Grade 3 (Complete Rupture)"],
   {"squat_ratio": 0.4}, "smith_compound"),
ex("smith_rdl_001", "Smith Machine Romanian Deadlift", "Hinge", "Hinge", 3, "Intermediate", "Smith Machine",
   ["Hamstrings", "Glutes"], ["Erector Spinae"], ["Core"],
   ["Lower Back", "Hip"], ["Low Back Pain", "Hamstring Strain - Grade 2 (Partial Tear)"],
   {"deadlift_ratio": 0.6}, "smith_compound"),
ex("smith_inclinepress_001", "Smith Machine Incline Press", "Horizontal Push", "Push", 2, "Novice", "Smith Machine",
   ["Pectoralis Major", "Anterior Deltoid"], ["Triceps Brachii"], ["Core"],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {"bench_ratio": 0.6}, "smith_compound"),
]

# ---- Hack Squat Machine (+2) ----
NEW += [
ex("hacksquat_narrow_001", "Narrow-Stance Hack Squat", "Squat", "Squat", 3, "Intermediate", "Hack Squat Machine",
   ["Quadriceps"], ["Glutes"], [],
   ["Knee"], ["Jumper's Knee (Patellar Tendinopathy)", "Meniscus Tear - Grade 3 (True Structural Tear)"],
   {"squat_ratio": 0.85}, "machine_legs"),
ex("hacksquat_wide_001", "Wide-Stance Hack Squat", "Squat", "Squat", 3, "Intermediate", "Hack Squat Machine",
   ["Glutes", "Quadriceps"], ["Hamstrings"], [],
   ["Knee", "Hip"], ["ACL/Ligament Tear - Grade 3 (Complete Rupture)"],
   {"squat_ratio": 0.85}, "machine_legs"),
]

# ---- High Row Machine (+2) ----
NEW += [
ex("high_row_machine_singlearm_001", "Single-Arm High Row Machine", "Horizontal Pull", "Pull", 2, "Novice", "High Row Machine",
   ["Rhomboids", "Rear Deltoid"], ["Biceps Brachii", "Core"], ["Core"],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "machine_pull"),
ex("high_row_machine_widegrip_001", "Wide-Grip High Row Machine", "Horizontal Pull", "Pull", 2, "Novice", "High Row Machine",
   ["Rear Deltoid", "Rhomboids"], ["Traps"], [],
   ["Shoulder"], ["Shoulder Instability", "Rotator Cuff"],
   {}, "machine_pull", Boxing=65, **{"Muay Thai": 62, "Kickboxing": 62}),
]

# ---- Resistance Band (+6) ----
NEW += [
ex("band_facepull_001", "Band Face Pull", "Horizontal Pull", "Pull", 1, "Beginner", "Resistance Band",
   ["Rear Deltoid", "Rhomboids"], ["Traps"], ["Rotator Cuff"],
   ["Shoulder"], ["Shoulder Instability", "Rotator Cuff"],
   {}, "band_accessory", Boxing=68, **{"Muay Thai": 65, "Kickboxing": 65}),
ex("band_lateralwalk_001", "Band Lateral Walk", "Squat", "Lateral", 1, "Beginner", "Resistance Band",
   ["Glutes"], ["Hip Abductors"], ["Core"],
   ["Hip", "Knee"], ["ACL/Ligament Tear - Grade 3 (Complete Rupture)"],
   {}, "band_accessory", Wrestling=60, Judo=60, Rugby=60, **{"Rock Climbing": 50}),
ex("band_overheadtricep_001", "Band Overhead Tricep Extension", "Vertical Push", "Push", 1, "Beginner", "Resistance Band",
   ["Triceps Brachii"], [], ["Core"],
   ["Elbow", "Shoulder"], ["Tennis Elbow"],
   {}, "band_accessory"),
ex("band_row_001", "Band Row", "Horizontal Pull", "Pull", 1, "Beginner", "Resistance Band",
   ["Rhomboids", "Latissimus Dorsi"], ["Biceps Brachii"], [],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {}, "band_accessory"),
ex("band_deadlift_001", "Banded Deadlift", "Hinge", "Hinge", 2, "Novice", "Resistance Band",
   ["Glutes", "Hamstrings"], ["Erector Spinae"], ["Core"],
   ["Lower Back", "Hip"], ["Low Back Pain"],
   {}, "band_accessory"),
ex("band_woodchopper_001", "Band Woodchopper", "Rotational", "Rotational", 2, "Novice", "Resistance Band",
   ["Obliques"], ["Core"], ["Hip"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "band_accessory", Wrestling=62, Judo=62, Sambo=62, BJJ=58, MMA=60),
]

# ---- Medicine Ball (+4) ----
NEW += [
ex("medball_situpthrow_001", "Medicine Ball Sit-Up Throw", "Core", "Flexion", 2, "Novice", "Medicine Ball",
   ["Rectus Abdominis"], ["Hip Flexors"], ["Core"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "medball_power"),
ex("medball_russiantwist_001", "Medicine Ball Russian Twist", "Core", "Rotational", 2, "Novice", "Medicine Ball",
   ["Obliques"], ["Core"], ["Hip"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "medball_power", Wrestling=60, Judo=60, Sambo=60, BJJ=58, MMA=58),
ex("medball_wallball_001", "Medicine Ball Wall Ball", "Squat", "Squat", 3, "Intermediate", "Medicine Ball",
   ["Quadriceps", "Glutes"], ["Shoulders", "Core"], ["Core"],
   ["Knee", "Shoulder"], [],
   {}, "medball_power", **{"HYROX": 85}),
ex("medball_pushup_001", "Medicine Ball Push-Up", "Horizontal Push", "Push", 3, "Intermediate", "Medicine Ball",
   ["Pectoralis Major", "Triceps Brachii"], ["Anterior Deltoid"], ["Core"],
   ["Wrist", "Shoulder"], ["Wrist Pain", "Shoulder Instability"],
   {}, "medball_power"),
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
    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(data['exercises'])} total exercises to {SRC}. "
          f"Backup at {BACKUP}. Now run scripts/enrich_exercises.py.")


if __name__ == "__main__":
    main()

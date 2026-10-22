"""
generate_batch7_equipment_rehab.py — two things in one batch, both flagged
as gaps by inspecting the live data rather than guessed at:

1. EQUIPMENT DEPTH: the 15 equipment types sitting at exactly 1 exercise and
   the 12 sitting at exactly 2 (Battle Ropes, Rowing Erg, Tackle Bag,
   Captain's Chair, Ab Wheel, Yoke, Agility Ladder, Buffalo Bar, Tire,
   Conan's Wheel, Fingal's Fingers, Husafell Stone, V Squat Machine,
   Pendulum Squat Machine, Belt Squat Machine, Assault Bike, Trap Bar,
   Climbing Hangboard, Parallel Bars, EZ Curl Bar, Jump Rope, Reverse Hyper,
   Seal Row Bench, Cambered Bar, Swiss Bar, Keg, Plate-Loaded Lever Machine)
   get +2 exercises each — every equipment type in the database now has at
   least 3, most at least 4, so picking that equipment in the app actually
   unlocks a real session instead of 1-2 repeats.

2. REHAB GAP: is_rehab_candidate() (knowledge_graph.py) requires difficulty
   <=2 AND the exercise's own joint-stability athletic-quality tag >=40 for
   the injured joint. Querying that against the live file before this batch:
   every joint had rehab candidates EXCEPT Neck, which had ZERO at any
   severity - a person with a neck injury got no rehab-candidate exercises
   back from the engine at all, not because the app doesn't reason about
   neck injuries (injury_taxonomy.py has full Neck entries) but because no
   exercise in the database was ever built to deliberately train neck
   stability at a low enough difficulty to qualify. Ankle had only 6, thin
   next to Shoulder/Hip/Knee's 50+. This batch adds 6 low-difficulty
   (difficulty=2, the same "caution-tier for moderate injuries, safe-tier
   for mild" ceiling every existing rehab-candidate exercise sits at)
   Neck-stability exercises and 6 Ankle-stability exercises, so both joints
   have real rehab candidates for the first time / at real depth.

Two new equipment types come with the rehab additions - Neck Harness and
Balance Board - both real, common rehab/prehab equipment that the database
had no entries for at all. Added to a new "Rehab & Mobility" group in
exercise_metadata.py's EQUIPMENT_CATEGORIES (equipment_level 46/47,
continuing on from the existing max of 45) so they show up correctly
grouped in the equipment catalog instead of falling into "Other".

Follows the exact pattern of generate_batch6_thin_equipment.py: hand-tagged
joint_stress / injuries_to_avoid per exercise, small and reviewable,
existing equipment_level values reused where the equipment already existed.

Run: python scripts/generate_batch7_equipment_rehab.py
Then: python scripts/enrich_batch7_only.py   (derives v4.0+ fields for the new entries)
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from backend.core.config import settings

SRC = settings.EXERCISES_JSON_PATH
BACKUP = settings.BACKUP_DIR / "exercises_pre_batch7_backup.json"

# equipment_level values taken from the existing exercises.json entries for
# each of the already-present equipment types; 46/47 are new (continuing on
# from the existing max of 45) for the two brand-new rehab equipment types.
EQUIPMENT_LEVEL = {
    "Battle Ropes": 6, "Rowing Erg": 6, "Tackle Bag": 10, "Captain's Chair": 2,
    "Ab Wheel": 25, "Yoke": 29, "Agility Ladder": 30, "Buffalo Bar": 5,
    "Tire": 34, "Conan's Wheel": 35, "Fingal's Fingers": 36, "Husafell Stone": 38,
    "V Squat Machine": 39, "Pendulum Squat Machine": 40, "Belt Squat Machine": 44,
    "Assault Bike": 9, "Trap Bar": 5, "Climbing Hangboard": 6, "Parallel Bars": 2,
    "EZ Curl Bar": 21, "Jump Rope": 32, "Reverse Hyper": 35, "Seal Row Bench": 36,
    "Cambered Bar": 5, "Swiss Bar": 5, "Keg": 37, "Plate-Loaded Lever Machine": 45,
    "Resistance Band": 8, "Bodyweight": 1,
    "Neck Harness": 46, "Balance Board": 47,
}

TEMPLATES = {
    "conditioning_gpp": {"Wrestling": 60, "Judo": 55, "Sambo": 55, "BJJ": 55, "Boxing": 75,
                          "Muay Thai": 75, "Kickboxing": 75, "Sanda": 75, "Rugby": 70,
                          "Rock Climbing": 50, "HYROX": 90, "Special Forces": 85, "MMA": 72},
    "strongman_carry": {"Wrestling": 55, "Judo": 50, "Sambo": 55, "BJJ": 45, "Boxing": 40,
                         "Muay Thai": 40, "Kickboxing": 40, "Sanda": 40, "Rugby": 75,
                         "Rock Climbing": 30, "HYROX": 80, "Special Forces": 80, "MMA": 50},
    "machine_legs": {"Wrestling": 60, "Judo": 60, "Sambo": 60, "BJJ": 55, "Boxing": 45,
                      "Muay Thai": 55, "Kickboxing": 55, "Sanda": 55, "Rugby": 75,
                      "Rock Climbing": 30, "HYROX": 70, "Special Forces": 70, "MMA": 55},
    "barbell_compound": {"Wrestling": 60, "Judo": 60, "Sambo": 60, "BJJ": 55, "Boxing": 50,
                          "Muay Thai": 50, "Kickboxing": 50, "Sanda": 50, "Rugby": 70,
                          "Rock Climbing": 30, "HYROX": 55, "Special Forces": 65, "MMA": 55},
    "grip_core": {"Wrestling": 65, "Judo": 65, "Sambo": 60, "BJJ": 65, "Boxing": 55,
                  "Muay Thai": 55, "Kickboxing": 55, "Sanda": 55, "Rugby": 55,
                  "Rock Climbing": 75, "HYROX": 55, "Special Forces": 60, "MMA": 60},
    "combat_specific": {"Wrestling": 85, "Judo": 80, "Sambo": 75, "BJJ": 70, "Boxing": 60,
                         "Muay Thai": 70, "Kickboxing": 70, "Sanda": 70, "Rugby": 85,
                         "Rock Climbing": 20, "HYROX": 40, "Special Forces": 70, "MMA": 75},
    "machine_pull": {"Wrestling": 65, "Judo": 65, "Sambo": 65, "BJJ": 65, "Boxing": 55,
                      "Muay Thai": 55, "Kickboxing": 55, "Sanda": 55, "Rugby": 60,
                      "Rock Climbing": 55, "HYROX": 50, "Special Forces": 60, "MMA": 60},
    "machine_push": {"Wrestling": 55, "Judo": 50, "Sambo": 55, "BJJ": 50, "Boxing": 65,
                      "Muay Thai": 60, "Kickboxing": 60, "Sanda": 60, "Rugby": 65,
                      "Rock Climbing": 30, "HYROX": 60, "Special Forces": 65, "MMA": 58},
    "rehab_neck": {"Wrestling": 60, "Judo": 55, "Sambo": 55, "BJJ": 50, "Boxing": 65,
                   "Muay Thai": 60, "Kickboxing": 60, "Sanda": 60, "Rugby": 65,
                   "Rock Climbing": 30, "HYROX": 35, "Special Forces": 50, "MMA": 60},
    "rehab_ankle": {"Wrestling": 55, "Judo": 55, "Sambo": 50, "BJJ": 45, "Boxing": 55,
                     "Muay Thai": 60, "Kickboxing": 60, "Sanda": 58, "Rugby": 65,
                     "Rock Climbing": 55, "HYROX": 60, "Special Forces": 55, "MMA": 58},
}

_LEVEL_TO_XP = {1: "Beginner", 2: "Novice", 3: "Intermediate", 4: "Advanced", 5: "Elite"}


def sp(template, **overrides):
    d = dict(TEMPLATES[template])
    d.update(overrides)
    return d


def ex(id_, name, category, pattern, difficulty, equipment,
       primary, secondary, stabilizers, joint_stress, injuries, reqs,
       template, **sp_overrides):
    return {
        "id": id_, "name": name, "category": category, "movement_pattern": pattern,
        "difficulty": difficulty, "experience_level": _LEVEL_TO_XP[difficulty],
        "equipment": equipment, "equipment_level": EQUIPMENT_LEVEL[equipment],
        "primary_muscles": primary, "secondary_muscles": secondary, "stabilizers": stabilizers,
        "joint_stress": joint_stress, "injuries_to_avoid": injuries,
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0,
                                   "pullups": 0, "pushups": 0, **reqs},
        "progressions": [], "regressions": [], "alternatives": [],
        "sport_priority": sp(template, **sp_overrides),
    }


NEW = []

# ---- Battle Ropes (1 -> 3) ----
NEW += [
ex("battleropes_slams_001", "Battle Rope Slams", "Conditioning", "Complex", 2, "Battle Ropes",
   ["Anterior Deltoid", "Latissimus Dorsi"], ["Core"], ["Erector Spinae"],
   ["Shoulder", "Lower Back"], ["Shoulder Instability", "Low Back Pain"],
   {}, "conditioning_gpp"),
ex("battleropes_circles_001", "Battle Rope Circles", "Conditioning", "Complex", 2, "Battle Ropes",
   ["Anterior Deltoid", "Lateral Deltoid"], ["Core", "Forearm Flexors"], [],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "conditioning_gpp"),
]

# ---- Rowing Erg (1 -> 3) ----
NEW += [
ex("rowingerg_steady_001", "Rowing Erg Steady State", "Conditioning", "Pull", 1, "Rowing Erg",
   ["Latissimus Dorsi", "Quadriceps"], ["Hamstrings", "Rhomboids"], ["Core"],
   ["Lower Back", "Knee"], [],
   {}, "conditioning_gpp"),
ex("rowingerg_sprint_001", "Rowing Erg 500m Sprint", "Conditioning", "Pull", 3, "Rowing Erg",
   ["Latissimus Dorsi", "Quadriceps"], ["Hamstrings", "Rhomboids"], ["Core"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "conditioning_gpp", HYROX=95),
]

# ---- Tackle Bag (1 -> 3) ----
NEW += [
ex("tacklebag_sprawl_001", "Tackle Bag Sprawl", "Sport Specific", "Complex", 3, "Tackle Bag",
   ["Pectoralis Major", "Quadriceps"], ["Core", "Anterior Deltoid"], ["Hip Flexors"],
   ["Shoulder", "Lower Back"], ["Shoulder Instability", "Low Back Pain"],
   {}, "combat_specific"),
ex("tacklebag_hipdrive_001", "Tackle Bag Explosive Hip Drive", "Sport Specific", "Complex", 3, "Tackle Bag",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings", "Core"], ["Erector Spinae"],
   ["Knee", "Lower Back"], ["Low Back Pain"],
   {}, "combat_specific", Rugby=90),
]

# ---- Captain's Chair (1 -> 3) ----
NEW += [
ex("captainschair_kneeraise_001", "Captain's Chair Knee Raise", "Core", "Flexion", 2, "Captain's Chair",
   ["Rectus Abdominis"], ["Hip Flexors"], ["Obliques"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "grip_core"),
ex("captainschair_obliqueraise_001", "Captain's Chair Oblique Raise", "Core", "Rotational", 3, "Captain's Chair",
   ["Obliques"], ["Hip Flexors"], ["Rectus Abdominis"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "grip_core"),
]

# ---- Ab Wheel (1 -> 3) ----
NEW += [
ex("abwheel_standing_001", "Standing Ab Wheel Rollout", "Core", "Anti-Extension", 5, "Ab Wheel",
   ["Rectus Abdominis"], ["Latissimus Dorsi", "Shoulders"], ["Erector Spinae"],
   ["Lower Back", "Shoulder"], ["Low Back Pain", "Shoulder Instability"],
   {}, "grip_core"),
ex("abwheel_lateral_001", "Ab Wheel Lateral Rollout", "Core", "Anti-Extension", 4, "Ab Wheel",
   ["Obliques"], ["Rectus Abdominis"], ["Shoulders"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "grip_core"),
]

# ---- Yoke (1 -> 3) ----
NEW += [
ex("yoke_statichold_001", "Yoke Static Hold", "Carry", "Isometric", 3, "Yoke",
   ["Erector Spinae", "Quadriceps"], ["Core", "Trapezius"], ["Glutes"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("yoke_turncarry_001", "Yoke Walk & Turn", "Carry", "Carry", 4, "Yoke",
   ["Erector Spinae", "Quadriceps"], ["Core", "Trapezius"], ["Glutes"],
   ["Lower Back", "Knee", "Ankle"], ["Low Back Pain"],
   {}, "strongman_carry"),
]

# ---- Agility Ladder (1 -> 3) ----
NEW += [
ex("agilityladder_icky_001", "Ladder Icky Shuffle", "Full Body", "Complex", 2, "Agility Ladder",
   ["Quadriceps", "Calves"], ["Hip Flexors"], ["Core"],
   ["Ankle", "Knee"], [],
   {}, "conditioning_gpp"),
ex("agilityladder_lateral_001", "Lateral Ladder Shuffle", "Full Body", "Complex", 2, "Agility Ladder",
   ["Quadriceps", "Gluteus Medius"], ["Calves"], ["Core"],
   ["Ankle", "Knee"], [],
   {}, "conditioning_gpp"),
]

# ---- Buffalo Bar (1 -> 3) ----
NEW += [
ex("buffalobar_deadlift_001", "Buffalo Bar Deadlift", "Hinge", "Hinge", 3, "Buffalo Bar",
   ["Gluteus Maximus", "Hamstrings"], ["Erector Spinae"], ["Core"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "barbell_compound"),
ex("buffalobar_bench_001", "Buffalo Bar Bench Press", "Horizontal Push", "Push", 3, "Buffalo Bar",
   ["Pectoralis Major"], ["Triceps Brachii", "Anterior Deltoid"], ["Core"],
   ["Shoulder", "Wrist"], ["Shoulder Instability"],
   {}, "barbell_compound"),
]

# ---- Tire (1 -> 3) ----
NEW += [
ex("tire_sledgehammer_001", "Tire Sledgehammer Strike", "Full Body", "Complex", 2, "Tire",
   ["Obliques", "Latissimus Dorsi"], ["Core", "Forearm Flexors"], ["Erector Spinae"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "combat_specific", HYROX=60),
ex("tire_jumpover_001", "Tire Jump-Overs", "Jump", "Jump", 3, "Tire",
   ["Quadriceps", "Gluteus Maximus"], ["Calves"], ["Core"],
   ["Knee", "Ankle"], ["ACL/Ligament Tear - Grade 3 (Complete Rupture)"],
   {}, "conditioning_gpp"),
]

# ---- Conan's Wheel (1 -> 3) ----
NEW += [
ex("conanswheel_hold_001", "Conan's Wheel Static Hold", "Carry", "Isometric", 4, "Conan's Wheel",
   ["Erector Spinae", "Trapezius"], ["Core"], ["Glutes"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("conanswheel_halflap_001", "Conan's Wheel Half Lap", "Carry", "Carry", 5, "Conan's Wheel",
   ["Erector Spinae", "Quadriceps"], ["Core", "Trapezius"], ["Glutes"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "strongman_carry"),
]

# ---- Fingal's Fingers (1 -> 3) ----
NEW += [
ex("fingalsfingers_toss_001", "Fingal's Fingers Toss", "Full Body", "Explosive Pull", 4, "Fingal's Fingers",
   ["Erector Spinae", "Gluteus Maximus"], ["Hamstrings", "Core"], ["Trapezius"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("fingalsfingers_carry_001", "Fingal's Fingers Carry", "Carry", "Carry", 3, "Fingal's Fingers",
   ["Forearm Flexors", "Erector Spinae"], ["Core"], ["Trapezius"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
]

# ---- Husafell Stone (1 -> 3) ----
NEW += [
ex("husafell_squat_001", "Husafell Stone Squat", "Squat", "Squat", 4, "Husafell Stone",
   ["Quadriceps", "Gluteus Maximus"], ["Erector Spinae"], ["Core"],
   ["Knee", "Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("husafell_shouldercarry_001", "Husafell Stone Shoulder Carry", "Carry", "Carry", 4, "Husafell Stone",
   ["Trapezius", "Erector Spinae"], ["Core"], ["Glutes"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "strongman_carry"),
]

# ---- V Squat Machine (1 -> 3) ----
NEW += [
ex("vsquat_singleleg_001", "V Squat Machine Single-Leg", "Squat", "Squat", 4, "V Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
ex("vsquat_pause_001", "V Squat Machine Pause Squat", "Squat", "Squat", 3, "V Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
]

# ---- Pendulum Squat Machine (1 -> 3) ----
NEW += [
ex("pendulum_singleleg_001", "Pendulum Squat Single-Leg", "Squat", "Squat", 4, "Pendulum Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
ex("pendulum_pause_001", "Pendulum Squat Pause Rep", "Squat", "Squat", 3, "Pendulum Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
]

# ---- Belt Squat Machine (1 -> 3) ----
NEW += [
ex("beltsquatmachine_march_001", "Belt Squat Machine March", "Squat", "Squat", 2, "Belt Squat Machine",
   ["Hip Flexors", "Quadriceps"], ["Core"], ["Glutes"],
   ["Knee", "Hip"], [],
   {}, "machine_legs"),
ex("beltsquatmachine_splitsquat_001", "Belt Squat Machine Split Squat", "Squat", "Lunge", 3, "Belt Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
]

# ---- Assault Bike (2 -> 4) ----
NEW += [
ex("assaultbike_steady_001", "Assault Bike Steady State", "Conditioning", "Complex", 1, "Assault Bike",
   ["Quadriceps", "Anterior Deltoid"], ["Hamstrings", "Latissimus Dorsi"], ["Core"],
   ["Knee"], [],
   {}, "conditioning_gpp"),
ex("assaultbike_tabata_001", "Assault Bike Tabata", "Conditioning", "Complex", 4, "Assault Bike",
   ["Quadriceps", "Anterior Deltoid"], ["Hamstrings", "Latissimus Dorsi"], ["Core"],
   ["Knee"], [],
   {}, "conditioning_gpp", HYROX=95, **{"Special Forces": 90}),
]

# ---- Trap Bar (2 -> 4) ----
NEW += [
ex("trapbar_farmercarry_001", "Trap Bar Farmer Carry", "Carry", "Carry", 2, "Trap Bar",
   ["Forearm Flexors", "Trapezius"], ["Core"], ["Erector Spinae"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry", **{"HYROX": 65}),
ex("trapbar_shrug_001", "Trap Bar Shrug", "Hinge", "Hinge", 2, "Trap Bar",
   ["Trapezius"], ["Forearm Flexors"], ["Erector Spinae"],
   ["Lower Back"], [],
   {}, "barbell_compound"),
]

# ---- Climbing Hangboard (2 -> 4) ----
NEW += [
ex("hangboard_repeaters_001", "Hangboard Repeaters", "Grip", "Isometric", 3, "Climbing Hangboard",
   ["Forearm Flexors"], ["Latissimus Dorsi"], [],
   ["Elbow", "Wrist"], ["Golfer's Elbow"],
   {}, "grip_core", **{"Rock Climbing": 90}),
ex("hangboard_onearm_001", "Hangboard One-Arm Hang", "Grip", "Isometric", 5, "Climbing Hangboard",
   ["Forearm Flexors"], ["Latissimus Dorsi", "Shoulders"], ["Core"],
   ["Elbow", "Wrist", "Shoulder"], ["Golfer's Elbow", "Shoulder Instability"],
   {}, "grip_core", **{"Rock Climbing": 95}),
]

# ---- Parallel Bars (2 -> 4) ----
NEW += [
ex("parallelbars_support_001", "Parallel Bar Support Hold", "Core", "Isometric", 2, "Parallel Bars",
   ["Triceps Brachii", "Pectoralis Major"], ["Core"], ["Anterior Deltoid"],
   ["Shoulder", "Wrist"], ["Shoulder Instability"],
   {}, "grip_core"),
ex("parallelbars_walkingdip_001", "Parallel Bar Walking Dip", "Vertical Push", "Push", 4, "Parallel Bars",
   ["Triceps Brachii", "Pectoralis Major"], ["Anterior Deltoid"], ["Core"],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {}, "grip_core"),
]

# ---- EZ Curl Bar (2 -> 4) ----
NEW += [
ex("ezbar_reversecurl_001", "EZ Bar Reverse Curl", "Horizontal Pull", "Pull", 2, "EZ Curl Bar",
   ["Forearm Flexors", "Biceps Brachii"], [], [],
   ["Elbow", "Wrist"], ["Tennis Elbow"],
   {}, "grip_core"),
ex("ezbar_uprightrow_001", "EZ Bar Upright Row", "Vertical Pull", "Pull", 2, "EZ Curl Bar",
   ["Lateral Deltoid", "Trapezius"], ["Biceps Brachii"], [],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {}, "machine_pull"),
]

# ---- Jump Rope (2 -> 4) ----
NEW += [
ex("jumprope_highknees_001", "Jump Rope High Knees", "Conditioning", "Jump", 2, "Jump Rope",
   ["Calves", "Hip Flexors"], ["Quadriceps"], ["Core"],
   ["Ankle", "Knee"], [],
   {}, "conditioning_gpp"),
ex("jumprope_singleleg_001", "Single-Leg Jump Rope", "Conditioning", "Jump", 3, "Jump Rope",
   ["Calves"], ["Quadriceps"], ["Ankle Stabilizers"],
   ["Ankle", "Knee"], ["Lateral Ankle Sprain - Grade 1 (Mild)"],
   {}, "conditioning_gpp"),
]

# ---- Reverse Hyper (2 -> 4) ----
NEW += [
ex("reversehyper_pulse_001", "Reverse Hyper Pulse Reps", "Hinge", "Hinge", 2, "Reverse Hyper",
   ["Glutes", "Erector Spinae"], ["Hamstrings"], ["Core"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "barbell_compound"),
ex("reversehyper_widestance_001", "Reverse Hyper Wide Stance", "Hinge", "Hinge", 2, "Reverse Hyper",
   ["Glutes", "Erector Spinae"], ["Hamstrings"], ["Core"],
   ["Lower Back", "Hip"], ["Low Back Pain"],
   {}, "barbell_compound"),
]

# ---- Seal Row Bench (2 -> 4) ----
NEW += [
ex("sealrow_widegrip_001", "Seal Row Wide Grip", "Horizontal Pull", "Pull", 2, "Seal Row Bench",
   ["Rhomboids", "Latissimus Dorsi"], ["Rear Deltoid"], [],
   ["Shoulder", "Elbow"], [],
   {}, "machine_pull"),
ex("sealrow_pause_001", "Seal Row Pause Rep", "Horizontal Pull", "Pull", 3, "Seal Row Bench",
   ["Rhomboids", "Latissimus Dorsi"], ["Biceps Brachii"], [],
   ["Shoulder", "Elbow"], [],
   {}, "machine_pull"),
]

# ---- Cambered Bar (2 -> 4) ----
NEW += [
ex("camberedbar_bench_001", "Cambered Bar Bench Press", "Horizontal Push", "Push", 3, "Cambered Bar",
   ["Pectoralis Major"], ["Triceps Brachii", "Anterior Deltoid"], ["Core"],
   ["Shoulder", "Wrist"], ["Shoulder Instability"],
   {}, "barbell_compound"),
ex("camberedbar_row_001", "Cambered Bar Bent-Over Row", "Horizontal Pull", "Pull", 2, "Cambered Bar",
   ["Latissimus Dorsi", "Rhomboids"], ["Biceps Brachii"], ["Erector Spinae"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "machine_pull"),
]

# ---- Swiss Bar (2 -> 4) ----
NEW += [
ex("swissbar_floorpress_001", "Swiss Bar Floor Press", "Horizontal Push", "Push", 2, "Swiss Bar",
   ["Pectoralis Major", "Triceps Brachii"], ["Anterior Deltoid"], ["Core"],
   ["Shoulder", "Elbow"], [],
   {}, "barbell_compound"),
ex("swissbar_row_001", "Swiss Bar Row", "Horizontal Pull", "Pull", 2, "Swiss Bar",
   ["Latissimus Dorsi", "Rhomboids"], ["Biceps Brachii"], ["Erector Spinae"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "machine_pull"),
]

# ---- Keg (2 -> 4) ----
NEW += [
ex("keg_clean_001", "Keg Clean", "Power", "Explosive Pull", 4, "Keg",
   ["Gluteus Maximus", "Trapezius"], ["Hamstrings", "Core"], ["Erector Spinae"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "strongman_carry", HYROX=70),
ex("keg_shouldercarry_001", "Keg Shoulder Carry", "Carry", "Carry", 3, "Keg",
   ["Trapezius", "Erector Spinae"], ["Core"], ["Glutes"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "strongman_carry"),
]

# ---- Plate-Loaded Lever Machine (2 -> 4) ----
NEW += [
ex("lever_shoulderpress_001", "Lever Shoulder Press", "Vertical Push", "Push", 2, "Plate-Loaded Lever Machine",
   ["Anterior Deltoid"], ["Triceps Brachii"], ["Core"],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "machine_push"),
ex("lever_pulldown_001", "Lever Pulldown", "Vertical Pull", "Pull", 2, "Plate-Loaded Lever Machine",
   ["Latissimus Dorsi"], ["Biceps Brachii", "Rhomboids"], [],
   ["Shoulder", "Elbow"], [],
   {}, "machine_pull"),
]

# ---- Neck rehab/prehab (fixes the zero-rehab-candidate gap on the Neck
# joint - see module docstring). Difficulty=2 throughout: the difficulty
# ceiling is_rehab_candidate() enforces, and 30 + difficulty*8 = 46 clears
# the 40 stability-quality floor exercise_metadata.py's joint_stress loop
# awards for training a stressed joint, since Neck is in joint_stress on
# every entry here. ----
NEW += [
ex("neckharness_flexion_001", "Neck Harness Flexion", "Core", "Flexion", 2, "Neck Harness",
   ["Neck Flexors"], [], ["Trapezius"],
   ["Neck"], ["Neck Pain"],
   {}, "rehab_neck"),
ex("neckharness_extension_001", "Neck Harness Extension", "Core", "Isometric", 2, "Neck Harness",
   ["Neck Extensors"], ["Trapezius"], [],
   ["Neck"], ["Neck Pain"],
   {}, "rehab_neck"),
ex("neckharness_lateral_001", "Neck Harness Lateral Flexion", "Core", "Lateral", 2, "Neck Harness",
   ["Sternocleidomastoid"], ["Trapezius"], [],
   ["Neck"], ["Neck Pain"],
   {}, "rehab_neck"),
ex("band_neckrotation_001", "Band Neck Rotation", "Core", "Rotational", 2, "Resistance Band",
   ["Sternocleidomastoid"], ["Neck Flexors"], [],
   ["Neck"], ["Neck Pain"],
   {}, "rehab_neck"),
ex("bodyweight_chintuck_001", "Isometric Chin Tuck Hold", "Core", "Isometric", 2, "Bodyweight",
   ["Neck Flexors"], ["Trapezius"], ["Core"],
   ["Neck"], ["Neck Pain"],
   {}, "rehab_neck"),
ex("bodyweight_prone_neckextension_001", "Prone Neck Extension", "Core", "Isometric", 2, "Bodyweight",
   ["Neck Extensors"], ["Trapezius", "Erector Spinae"], [],
   ["Neck"], ["Neck Pain", "Cervical Facet Injury - Stage 1 (Distraction Instability)"],
   {}, "rehab_neck"),
]

# ---- Ankle rehab/prehab (6 -> 12; brings Ankle rehab-candidate depth up
# toward the other joints - same difficulty=2 reasoning as the Neck block
# above). ----
NEW += [
ex("balanceboard_singleleg_001", "Balance Board Single-Leg Stand", "Core", "Isometric", 2, "Balance Board",
   ["Ankle Stabilizers"], ["Gastrocnemius", "Soleus"], ["Core"],
   ["Ankle"], ["Lateral Ankle Sprain - Grade 1 (Mild)"],
   {}, "rehab_ankle"),
ex("balanceboard_squat_001", "Balance Board Squat", "Core", "Isometric", 2, "Balance Board",
   ["Ankle Stabilizers", "Quadriceps"], ["Gastrocnemius"], ["Core"],
   ["Ankle", "Knee"], ["Lateral Ankle Sprain - Grade 1 (Mild)"],
   {}, "rehab_ankle"),
ex("band_ankledorsiflexion_001", "Band Ankle Dorsiflexion", "Calf Raise", "Isometric", 2, "Resistance Band",
   ["Tibialis Anterior"], [], ["Ankle Stabilizers"],
   ["Ankle"], ["Lateral Ankle Sprain - Grade 1 (Mild)"],
   {}, "rehab_ankle"),
ex("band_ankleeversion_001", "Band Ankle Eversion", "Calf Raise", "Isometric", 2, "Resistance Band",
   ["Peroneals"], [], ["Ankle Stabilizers"],
   ["Ankle"], ["High Ankle Sprain (Syndesmosis Tear)"],
   {}, "rehab_ankle"),
ex("band_ankleinversion_001", "Band Ankle Inversion", "Calf Raise", "Isometric", 2, "Resistance Band",
   ["Tibialis Anterior"], ["Peroneals"], ["Ankle Stabilizers"],
   ["Ankle"], ["Lateral Ankle Sprain - Grade 1 (Mild)"],
   {}, "rehab_ankle"),
ex("bodyweight_singlelegcalfraise_001", "Single-Leg Calf Raise Isometric Hold", "Calf Raise", "Isometric", 2, "Bodyweight",
   ["Gastrocnemius", "Soleus"], [], ["Ankle Stabilizers"],
   ["Ankle"], ["Achilles"],
   {}, "rehab_ankle"),
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
          f"Backup at {BACKUP}. Now run scripts/enrich_batch7_only.py.")


if __name__ == "__main__":
    main()

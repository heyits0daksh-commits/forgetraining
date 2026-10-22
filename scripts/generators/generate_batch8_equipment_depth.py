"""
generate_batch8_equipment_depth.py — closes out the equipment-depth pass
batch6/7 started. Querying the live file before this batch: 50 equipment
types still sat at only 3 or 4 exercises (vs. 30-40+ for Barbell/
Bodyweight) — mostly single-purpose machines, specialty bars, strongman
implements, and conditioning tools that batch6 (general commercial
machines) and batch7 (the very thinnest, 1-2 count, plus the Neck/Ankle
rehab gap) didn't reach.

This batch gives every one of those 50 equipment types +2 exercises,
matching the exact +2-per-equipment pattern batch6/7 used — small and
reviewable per equipment rather than exhaustive, consistent across the
whole batch rather than guessing higher counts for some and lower for
others. A few of these types (isolation machines, single-implement
strongman tools) genuinely don't have much more real exercise variety
beyond this without inventing gimmick movements, so +2 (bringing them to
5-6) is close to their realistic ceiling anyway; bar-based/bodyweight
equipment has more room but stays at +2 here for consistency — a future
batch can revisit any of these individually if real demand shows up.

Follows the exact pattern of generate_batch6/7: hand-tagged joint_stress /
injuries_to_avoid per exercise, existing equipment_level values reused
from the current exercises.json (no new equipment introduced), new
exercise names checked against every existing name for each equipment
so nothing here duplicates what's already in the database.

Run: python scripts/generate_batch8_equipment_depth.py
Then: python scripts/enrich_batch8_only.py   (derives v4.0+ fields for the new entries)
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "data" / "exercises.json"
BACKUP = ROOT / "data" / "backups" / "exercises_pre_batch8_backup.json"

# equipment_level values taken from the existing exercises.json entries for
# each of these (already-present) equipment types — no new equipment
# introduced in this batch, so no new numbers to invent.
EQUIPMENT_LEVEL = {
    "Balance Board": 47, "Wrestling Dummy": 10, "Sled": 11, "Battle Ropes": 6,
    "Rowing Erg": 6, "Tackle Bag": 10, "Captain's Chair": 2,
    "Hack Squat Machine": 14, "Leg Extension Machine": 17, "Pec Deck Machine": 19,
    "Safety Squat Bar": 5, "Ab Wheel": 25, "Suspension Trainer": 26,
    "Weighted Vest": 27, "Yoke": 29, "Agility Ladder": 30, "Boxing Heavy Bag": 31,
    "Squat Rack": 33, "Belt Squat": 34, "Hyperextension Bench": 5,
    "Buffalo Bar": 5, "Log Bar": 5, "Atlas Stone": 33, "Tire": 34,
    "Conan's Wheel": 35, "Fingal's Fingers": 36, "Husafell Stone": 38,
    "V Squat Machine": 39, "Pendulum Squat Machine": 40, "Chest Press Machine": 41,
    "Shoulder Press Machine": 42, "High Row Machine": 43, "Belt Squat Machine": 44,
    "Neck Harness": 46, "Farmer Handles": 5, "Assault Bike": 9, "Trap Bar": 5,
    "Climbing Hangboard": 6, "Parallel Bars": 2, "Leg Curl Machine": 18,
    "EZ Curl Bar": 21, "GHD": 24, "Jump Rope": 32, "Reverse Hyper": 35,
    "Seal Row Bench": 36, "Cambered Bar": 5, "Axle Bar": 5, "Swiss Bar": 5,
    "Keg": 37, "Plate-Loaded Lever Machine": 45,
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
    "rehab_ankle": {"Wrestling": 55, "Judo": 55, "Sambo": 50, "BJJ": 45, "Boxing": 55,
                     "Muay Thai": 60, "Kickboxing": 60, "Sanda": 58, "Rugby": 65,
                     "Rock Climbing": 55, "HYROX": 60, "Special Forces": 55, "MMA": 58},
    "rehab_neck": {"Wrestling": 60, "Judo": 55, "Sambo": 55, "BJJ": 50, "Boxing": 65,
                   "Muay Thai": 60, "Kickboxing": 60, "Sanda": 60, "Rugby": 65,
                   "Rock Climbing": 30, "HYROX": 35, "Special Forces": 50, "MMA": 60},
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

# ---- Balance Board (2 -> 4) ----
NEW += [
ex("balanceboard_reach_001", "Balance Board Single-Leg Reach", "Core", "Isometric", 2, "Balance Board",
   ["Ankle Stabilizers", "Gluteus Medius"], ["Hamstrings"], ["Core"],
   ["Ankle"], ["Lateral Ankle Sprain - Grade 1 (Mild)"],
   {}, "rehab_ankle"),
ex("balanceboard_plank_001", "Balance Board Plank Hold", "Core", "Isometric", 3, "Balance Board",
   ["Rectus Abdominis", "Ankle Stabilizers"], ["Anterior Deltoid"], ["Core"],
   ["Ankle", "Shoulder"], ["Lateral Ankle Sprain - Grade 1 (Mild)"],
   {}, "rehab_ankle"),
]

# ---- Wrestling Dummy (3 -> 5) ----
NEW += [
ex("wrestlingdummy_doubleleg_001", "Wrestling Dummy Double-Leg Takedown", "Sport Specific", "Complex", 3, "Wrestling Dummy",
   ["Quadriceps", "Gluteus Maximus"], ["Erector Spinae", "Core"], ["Hip Flexors"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "combat_specific"),
ex("wrestlingdummy_sprawl_001", "Wrestling Dummy Sprawl Drill", "Sport Specific", "Complex", 3, "Wrestling Dummy",
   ["Pectoralis Major", "Core"], ["Anterior Deltoid", "Quadriceps"], ["Hip Flexors"],
   ["Shoulder", "Lower Back"], ["Shoulder Instability", "Low Back Pain"],
   {}, "combat_specific"),
]

# ---- Sled (3 -> 5) ----
NEW += [
ex("sled_row_001", "Sled Row", "Horizontal Pull", "Pull", 2, "Sled",
   ["Latissimus Dorsi", "Rhomboids"], ["Biceps Brachii"], ["Erector Spinae"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "conditioning_gpp"),
ex("sled_lateraldrag_001", "Lateral Sled Drag", "Conditioning", "Lateral", 2, "Sled",
   ["Gluteus Medius", "Quadriceps"], ["Hip Abductors"], ["Core"],
   ["Knee", "Hip"], [],
   {}, "conditioning_gpp"),
]

# ---- Battle Ropes (3 -> 5) ----
NEW += [
ex("battleropes_snake_001", "Battle Rope Snake Waves", "Conditioning", "Lateral", 2, "Battle Ropes",
   ["Anterior Deltoid", "Obliques"], ["Core"], ["Erector Spinae"],
   ["Shoulder", "Lower Back"], ["Shoulder Instability"],
   {}, "conditioning_gpp"),
ex("battleropes_jumpingwaves_001", "Battle Rope Jumping Waves", "Conditioning", "Jump", 3, "Battle Ropes",
   ["Anterior Deltoid", "Quadriceps"], ["Calves", "Core"], ["Ankle Stabilizers"],
   ["Shoulder", "Knee", "Ankle"], ["Shoulder Instability"],
   {}, "conditioning_gpp"),
]

# ---- Rowing Erg (3 -> 5) ----
NEW += [
ex("rowingerg_2ktt_001", "Rowing Erg 2000m Time Trial", "Conditioning", "Pull", 4, "Rowing Erg",
   ["Latissimus Dorsi", "Quadriceps"], ["Hamstrings", "Rhomboids"], ["Core"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "conditioning_gpp", HYROX=90),
ex("rowingerg_pyramid_001", "Rowing Erg Pyramid Intervals", "Conditioning", "Pull", 3, "Rowing Erg",
   ["Latissimus Dorsi", "Quadriceps"], ["Hamstrings", "Rhomboids"], ["Core"],
   ["Lower Back", "Knee"], [],
   {}, "conditioning_gpp"),
]

# ---- Tackle Bag (3 -> 5) ----
NEW += [
ex("tacklebag_choptackle_001", "Tackle Bag Chop Tackle", "Sport Specific", "Complex", 3, "Tackle Bag",
   ["Quadriceps", "Core"], ["Anterior Deltoid"], ["Hip Flexors"],
   ["Shoulder", "Knee"], ["Shoulder Instability"],
   {}, "combat_specific", Rugby=90),
ex("tacklebag_wrapdrive_001", "Tackle Bag Wrap and Drive", "Sport Specific", "Complex", 3, "Tackle Bag",
   ["Pectoralis Major", "Quadriceps"], ["Core", "Erector Spinae"], ["Hip Flexors"],
   ["Shoulder", "Lower Back"], ["Shoulder Instability", "Low Back Pain"],
   {}, "combat_specific", Rugby=88),
]

# ---- Captain's Chair (3 -> 5) ----
NEW += [
ex("captainschair_windshield_001", "Captain's Chair Windshield Wipers", "Core", "Rotational", 4, "Captain's Chair",
   ["Obliques"], ["Rectus Abdominis", "Hip Flexors"], ["Core"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "grip_core"),
ex("captainschair_lhold_001", "Captain's Chair Static L-Hold", "Core", "Isometric", 3, "Captain's Chair",
   ["Rectus Abdominis", "Hip Flexors"], [], ["Obliques"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "grip_core"),
]

# ---- Hack Squat Machine (3 -> 5) ----
NEW += [
ex("hacksquat_singleleg_001", "Hack Squat Machine Single-Leg", "Squat", "Squat", 4, "Hack Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
ex("hacksquat_pause_001", "Hack Squat Pause Rep", "Squat", "Squat", 3, "Hack Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
]

# ---- Leg Extension Machine (3 -> 5) ----
NEW += [
ex("legextension_partial_001", "Leg Extension Top-Range Partials", "Squat", "Squat", 2, "Leg Extension Machine",
   ["Quadriceps"], [], [],
   ["Knee"], ["Jumper's Knee (Patellar Tendinopathy)"],
   {}, "machine_legs"),
ex("legextension_slowecc_001", "Leg Extension Slow Eccentric", "Squat", "Squat", 3, "Leg Extension Machine",
   ["Quadriceps"], [], [],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
]

# ---- Pec Deck Machine (3 -> 5) ----
NEW += [
ex("pecdeck_isohold_001", "Pec Deck Iso Hold", "Horizontal Push", "Push", 2, "Pec Deck Machine",
   ["Pectoralis Major"], ["Anterior Deltoid"], [],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "machine_push"),
ex("pecdeck_partialsqueeze_001", "Pec Deck Partial Rep Squeeze", "Horizontal Push", "Push", 2, "Pec Deck Machine",
   ["Pectoralis Major"], [], [],
   ["Shoulder"], [],
   {}, "machine_push"),
]

# ---- Safety Squat Bar (3 -> 5) ----
NEW += [
ex("ssb_carry_001", "Safety Squat Bar Front-Loaded Carry", "Carry", "Carry", 3, "Safety Squat Bar",
   ["Erector Spinae", "Core"], ["Trapezius"], ["Quadriceps"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "barbell_compound"),
ex("ssb_boxsquat_001", "Safety Squat Bar Box Squat", "Squat", "Squat", 3, "Safety Squat Bar",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee", "Lower Back"], ["Low Back Pain"],
   {}, "barbell_compound"),
]

# ---- Ab Wheel (3 -> 5) ----
NEW += [
ex("abwheel_pike_001", "Kneeling Ab Wheel Pike", "Core", "Anti-Extension", 3, "Ab Wheel",
   ["Rectus Abdominis"], ["Hip Flexors"], ["Shoulders"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "grip_core"),
ex("abwheel_singlearm_001", "Ab Wheel Single-Arm Rollout", "Core", "Anti-Extension", 5, "Ab Wheel",
   ["Rectus Abdominis", "Obliques"], ["Shoulders", "Latissimus Dorsi"], ["Erector Spinae"],
   ["Lower Back", "Shoulder", "Wrist"], ["Low Back Pain", "Shoulder Instability"],
   {}, "grip_core"),
]

# ---- Suspension Trainer (3 -> 5) ----
NEW += [
ex("trx_fallout_001", "TRX Fallout", "Core", "Anti-Extension", 3, "Suspension Trainer",
   ["Rectus Abdominis"], ["Anterior Deltoid"], ["Core"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "grip_core"),
ex("trx_hamstringcurl_001", "TRX Hamstring Curl", "Hinge", "Hinge", 3, "Suspension Trainer",
   ["Hamstrings"], ["Glutes"], ["Core"],
   ["Knee", "Lower Back"], ["Hamstring Strain"],
   {}, "grip_core"),
]

# ---- Weighted Vest (3 -> 5) ----
NEW += [
ex("weightedvest_pushup_001", "Weighted Vest Push-Up", "Horizontal Push", "Push", 3, "Weighted Vest",
   ["Pectoralis Major", "Anterior Deltoid"], ["Triceps Brachii"], ["Core"],
   ["Wrist", "Shoulder"], ["Shoulder Instability"],
   {}, "conditioning_gpp"),
ex("weightedvest_boxjump_001", "Weighted Vest Box Jump", "Jump", "Jump", 4, "Weighted Vest",
   ["Quadriceps", "Gluteus Maximus"], ["Calves"], ["Core"],
   ["Knee", "Ankle"], ["ACL/Ligament Tear - Grade 3 (Complete Rupture)"],
   {}, "conditioning_gpp", **{"Special Forces": 88}),
]

# ---- Yoke (3 -> 5) ----
NEW += [
ex("yoke_march_001", "Yoke Loaded March", "Carry", "Carry", 3, "Yoke",
   ["Erector Spinae", "Quadriceps"], ["Core"], ["Glutes"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("yoke_speedcarry_001", "Yoke Speed Carry", "Carry", "Carry", 4, "Yoke",
   ["Erector Spinae", "Quadriceps"], ["Core", "Trapezius"], ["Glutes"],
   ["Lower Back", "Knee", "Ankle"], ["Low Back Pain"],
   {}, "strongman_carry", HYROX=85),
]

# ---- Agility Ladder (3 -> 5) ----
NEW += [
ex("agilityladder_crossover_001", "Ladder Crossover Step", "Full Body", "Complex", 2, "Agility Ladder",
   ["Quadriceps", "Gluteus Medius"], ["Calves"], ["Core"],
   ["Ankle", "Knee"], [],
   {}, "conditioning_gpp"),
ex("agilityladder_2insprint_001", "Ladder 2-In Sprint", "Full Body", "Complex", 3, "Agility Ladder",
   ["Quadriceps", "Hip Flexors"], ["Calves"], ["Core"],
   ["Ankle", "Knee"], [],
   {}, "conditioning_gpp"),
]

# ---- Boxing Heavy Bag (3 -> 5) ----
NEW += [
ex("heavybag_elbowstrikes_001", "Heavy Bag Elbow Strikes", "Sport Specific", "Strike", 3, "Boxing Heavy Bag",
   ["Triceps Brachii", "Core"], ["Anterior Deltoid"], ["Obliques"],
   ["Elbow", "Shoulder"], ["Shoulder Instability"],
   {}, "combat_specific"),
ex("heavybag_footwork_001", "Heavy Bag Footwork Circling Drill", "Sport Specific", "Complex", 2, "Boxing Heavy Bag",
   ["Calves", "Quadriceps"], ["Hip Abductors"], ["Core"],
   ["Ankle", "Knee"], [],
   {}, "combat_specific"),
]

# ---- Squat Rack (3 -> 5) ----
NEW += [
ex("squatrack_pinpull_001", "Rack Pull from Pins (Mid-Shin)", "Hinge", "Hinge", 4, "Squat Rack",
   ["Erector Spinae", "Gluteus Maximus"], ["Hamstrings", "Trapezius"], ["Core"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "barbell_compound"),
ex("squatrack_spotopress_001", "Spoto Press (Pin Press)", "Horizontal Push", "Push", 4, "Squat Rack",
   ["Pectoralis Major"], ["Triceps Brachii", "Anterior Deltoid"], ["Core"],
   ["Shoulder", "Wrist"], ["Shoulder Instability"],
   {}, "barbell_compound"),
]

# ---- Belt Squat (3 -> 5) ----
NEW += [
ex("beltsquat_lateralstep_001", "Belt Squat Lateral Step", "Squat", "Lateral", 3, "Belt Squat",
   ["Gluteus Medius", "Quadriceps"], ["Hip Abductors"], ["Core"],
   ["Knee", "Hip"], [],
   {}, "machine_legs"),
ex("beltsquat_goodmorning_001", "Belt Squat Good Morning", "Hinge", "Hinge", 3, "Belt Squat",
   ["Hamstrings", "Erector Spinae"], ["Glutes"], ["Core"],
   ["Lower Back"], ["Low Back Pain", "Hamstring Strain"],
   {}, "machine_legs"),
]

# ---- Hyperextension Bench (3 -> 5) ----
NEW += [
ex("hyperextbench_singleleg_001", "Single-Leg Back Extension", "Hinge", "Hinge", 3, "Hyperextension Bench",
   ["Erector Spinae", "Glutes"], ["Hamstrings"], ["Core"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "barbell_compound"),
ex("hyperextbench_obliqueraise_001", "Hyperextension Bench Oblique Raise", "Rotational", "Lateral", 2, "Hyperextension Bench",
   ["Obliques"], ["Erector Spinae"], ["Core"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "barbell_compound"),
]

# ---- Buffalo Bar (3 -> 5) ----
NEW += [
ex("buffalobar_press_001", "Buffalo Bar Overhead Press", "Vertical Push", "Push", 3, "Buffalo Bar",
   ["Anterior Deltoid"], ["Triceps Brachii"], ["Core"],
   ["Shoulder", "Lower Back"], ["Shoulder Instability"],
   {}, "barbell_compound"),
ex("buffalobar_goodmorning_001", "Buffalo Bar Good Morning", "Hinge", "Hinge", 3, "Buffalo Bar",
   ["Hamstrings", "Erector Spinae"], ["Glutes"], ["Core"],
   ["Lower Back"], ["Low Back Pain", "Hamstring Strain"],
   {}, "barbell_compound"),
]

# ---- Log Bar (3 -> 5) ----
NEW += [
ex("logbar_bearhug_001", "Log Bar Bear Hug Carry", "Carry", "Carry", 3, "Log Bar",
   ["Erector Spinae", "Core"], ["Trapezius"], ["Forearm Flexors"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("logbar_frontsquat_001", "Log Bar Front Squat", "Squat", "Squat", 4, "Log Bar",
   ["Quadriceps", "Gluteus Maximus"], ["Core"], ["Erector Spinae"],
   ["Knee", "Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
]

# ---- Atlas Stone (3 -> 5) ----
NEW += [
ex("atlasstone_carry_001", "Atlas Stone Carry", "Carry", "Carry", 4, "Atlas Stone",
   ["Erector Spinae", "Forearm Flexors"], ["Core"], ["Glutes"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("atlasstone_maxheight_001", "Atlas Stone Max Height Load", "Power", "Explosive Pull", 5, "Atlas Stone",
   ["Gluteus Maximus", "Erector Spinae"], ["Hamstrings", "Core"], ["Trapezius"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "strongman_carry"),
]

# ---- Tire (3 -> 5) ----
NEW += [
ex("tire_drag_001", "Tire Drag", "Conditioning", "Complex", 2, "Tire",
   ["Quadriceps", "Erector Spinae"], ["Core"], ["Forearm Flexors"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("tire_bearcrawlpush_001", "Tire Bear Crawl Push", "Full Body", "Complex", 3, "Tire",
   ["Quadriceps", "Pectoralis Major"], ["Core", "Anterior Deltoid"], ["Erector Spinae"],
   ["Shoulder", "Knee"], ["Shoulder Instability"],
   {}, "strongman_carry"),
]

# ---- Conan's Wheel (3 -> 5) ----
NEW += [
ex("conanswheel_fulllap_001", "Conan's Wheel Full Lap Carry", "Carry", "Carry", 5, "Conan's Wheel",
   ["Erector Spinae", "Quadriceps"], ["Core", "Trapezius"], ["Glutes"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("conanswheel_press_001", "Conan's Wheel Press", "Vertical Push", "Push", 4, "Conan's Wheel",
   ["Anterior Deltoid", "Triceps Brachii"], ["Core"], ["Erector Spinae"],
   ["Shoulder", "Lower Back"], ["Shoulder Instability"],
   {}, "strongman_carry"),
]

# ---- Fingal's Fingers (3 -> 5) ----
NEW += [
ex("fingalsfingers_relayflip_001", "Fingal's Fingers Relay Flip", "Power", "Explosive Pull", 4, "Fingal's Fingers",
   ["Erector Spinae", "Gluteus Maximus"], ["Hamstrings", "Core"], ["Trapezius"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("fingalsfingers_press_001", "Fingal's Fingers Overhead Press", "Vertical Push", "Push", 4, "Fingal's Fingers",
   ["Anterior Deltoid"], ["Triceps Brachii", "Core"], ["Erector Spinae"],
   ["Shoulder", "Lower Back"], ["Shoulder Instability"],
   {}, "strongman_carry"),
]

# ---- Husafell Stone (3 -> 5) ----
NEW += [
ex("husafell_overbar_001", "Husafell Stone Over Bar", "Power", "Explosive Pull", 5, "Husafell Stone",
   ["Gluteus Maximus", "Erector Spinae"], ["Hamstrings", "Core"], ["Trapezius"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("husafell_zercher_001", "Husafell Stone Zercher Carry", "Carry", "Carry", 4, "Husafell Stone",
   ["Erector Spinae", "Biceps Brachii"], ["Core"], ["Quadriceps"],
   ["Lower Back", "Elbow"], ["Low Back Pain"],
   {}, "strongman_carry"),
]

# ---- V Squat Machine (3 -> 5) ----
NEW += [
ex("vsquat_widestance_001", "V Squat Machine Wide Stance", "Squat", "Squat", 3, "V Squat Machine",
   ["Quadriceps", "Adductors"], ["Gluteus Maximus"], ["Core"],
   ["Knee", "Hip"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
ex("vsquat_15rep_001", "V Squat Machine 1.5 Rep", "Squat", "Squat", 4, "V Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
]

# ---- Pendulum Squat Machine (3 -> 5) ----
NEW += [
ex("pendulum_deficit_001", "Pendulum Squat Deficit", "Squat", "Squat", 4, "Pendulum Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee", "Hip"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
ex("pendulum_tempoecc_001", "Pendulum Squat Tempo Eccentric", "Squat", "Squat", 3, "Pendulum Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
]

# ---- Chest Press Machine (3 -> 5) ----
NEW += [
ex("chestpress_decline_001", "Decline Chest Press Machine", "Horizontal Push", "Push", 2, "Chest Press Machine",
   ["Pectoralis Major"], ["Triceps Brachii"], ["Core"],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "machine_push"),
ex("chestpress_isohold_001", "Chest Press Machine Iso Hold", "Horizontal Push", "Push", 2, "Chest Press Machine",
   ["Pectoralis Major"], ["Triceps Brachii", "Anterior Deltoid"], [],
   ["Shoulder"], [],
   {}, "machine_push"),
]

# ---- Shoulder Press Machine (3 -> 5) ----
NEW += [
ex("shoulderpress_partial_001", "Shoulder Press Machine Partial Reps", "Vertical Push", "Push", 2, "Shoulder Press Machine",
   ["Anterior Deltoid"], ["Triceps Brachii"], [],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "machine_push"),
ex("shoulderpress_arnoldstyle_001", "Seated Arnold-Style Machine Press", "Vertical Push", "Push", 3, "Shoulder Press Machine",
   ["Anterior Deltoid", "Lateral Deltoid"], ["Triceps Brachii"], ["Core"],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "machine_push"),
]

# ---- High Row Machine (3 -> 5) ----
NEW += [
ex("highrow_closegrip_001", "High Row Machine Close-Grip", "Horizontal Pull", "Pull", 2, "High Row Machine",
   ["Rhomboids", "Latissimus Dorsi"], ["Biceps Brachii"], [],
   ["Shoulder", "Elbow"], [],
   {}, "machine_pull"),
ex("highrow_isohold_001", "High Row Machine Iso Hold", "Horizontal Pull", "Pull", 2, "High Row Machine",
   ["Rhomboids", "Trapezius"], ["Rear Deltoid"], [],
   ["Shoulder"], [],
   {}, "machine_pull"),
]

# ---- Belt Squat Machine (3 -> 5) ----
NEW += [
ex("beltsquatmachine_lateralstep_001", "Belt Squat Machine Lateral Step", "Squat", "Lateral", 3, "Belt Squat Machine",
   ["Gluteus Medius", "Quadriceps"], ["Hip Abductors"], ["Core"],
   ["Knee", "Hip"], [],
   {}, "machine_legs"),
ex("beltsquatmachine_pulse_001", "Belt Squat Machine Pulse Squat", "Squat", "Squat", 2, "Belt Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
]

# ---- Neck Harness (3 -> 5) ----
NEW += [
ex("neckharness_rotation_001", "Neck Harness Rotation", "Core", "Rotation", 2, "Neck Harness",
   ["Sternocleidomastoid"], ["Neck Flexors"], [],
   ["Neck"], ["Neck Pain"],
   {}, "rehab_neck"),
ex("neckharness_weightednod_001", "Neck Harness Weighted Nod", "Core", "Flexion", 2, "Neck Harness",
   ["Neck Flexors"], ["Neck Extensors"], [],
   ["Neck"], ["Neck Pain"],
   {}, "rehab_neck"),
]

# ---- Farmer Handles (4 -> 6) ----
NEW += [
ex("farmerhandles_suitcase_001", "Farmer Handles Suitcase Carry", "Carry", "Carry", 3, "Farmer Handles",
   ["Obliques", "Forearm Flexors"], ["Core"], ["Erector Spinae"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("farmerhandles_overheadcarry_001", "Farmer Handles Overhead Carry", "Carry", "Carry", 4, "Farmer Handles",
   ["Anterior Deltoid", "Core"], ["Triceps Brachii"], ["Erector Spinae"],
   ["Shoulder", "Lower Back"], ["Shoulder Instability"],
   {}, "strongman_carry"),
]

# ---- Assault Bike (4 -> 6) ----
NEW += [
ex("assaultbike_reversepedal_001", "Assault Bike Reverse Pedal Intervals", "Conditioning", "Complex", 2, "Assault Bike",
   ["Hamstrings", "Anterior Deltoid"], ["Quadriceps", "Latissimus Dorsi"], ["Core"],
   ["Knee"], [],
   {}, "conditioning_gpp"),
ex("assaultbike_emom_001", "Assault Bike EMOM", "Conditioning", "Complex", 3, "Assault Bike",
   ["Quadriceps", "Anterior Deltoid"], ["Hamstrings", "Latissimus Dorsi"], ["Core"],
   ["Knee"], [],
   {}, "conditioning_gpp", HYROX=88),
]

# ---- Trap Bar (4 -> 6) ----
NEW += [
ex("trapbar_deficit_001", "Trap Bar Deficit Deadlift", "Hinge", "Hinge", 4, "Trap Bar",
   ["Gluteus Maximus", "Hamstrings"], ["Erector Spinae"], ["Core"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "barbell_compound"),
ex("trapbar_row_001", "Trap Bar Bent-Over Row", "Horizontal Pull", "Pull", 3, "Trap Bar",
   ["Latissimus Dorsi", "Rhomboids"], ["Biceps Brachii"], ["Erector Spinae"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "barbell_compound"),
]

# ---- Climbing Hangboard (4 -> 6) ----
NEW += [
ex("hangboard_weighteddeadhang_001", "Hangboard Weighted Dead Hang", "Grip", "Isometric", 4, "Climbing Hangboard",
   ["Forearm Flexors"], ["Latissimus Dorsi"], ["Core"],
   ["Elbow", "Wrist", "Shoulder"], ["Golfer's Elbow"],
   {}, "grip_core", **{"Rock Climbing": 92}),
ex("hangboard_pullup_001", "Hangboard Pull-Up", "Vertical Pull", "Pull", 4, "Climbing Hangboard",
   ["Latissimus Dorsi", "Forearm Flexors"], ["Biceps Brachii"], ["Core"],
   ["Elbow", "Wrist", "Shoulder"], ["Golfer's Elbow", "Shoulder Instability"],
   {}, "grip_core", **{"Rock Climbing": 90}),
]

# ---- Parallel Bars (4 -> 6) ----
NEW += [
ex("parallelbars_straddle_001", "Parallel Bar Straddle Hold", "Core", "Isometric", 4, "Parallel Bars",
   ["Rectus Abdominis", "Hip Flexors"], ["Triceps Brachii"], ["Core"],
   ["Shoulder", "Wrist"], ["Shoulder Instability"],
   {}, "grip_core"),
ex("parallelbars_muscleuptransition_001", "Parallel Bar Muscle-Up Transition Drill", "Vertical Push", "Push", 5, "Parallel Bars",
   ["Triceps Brachii", "Pectoralis Major"], ["Anterior Deltoid", "Latissimus Dorsi"], ["Core"],
   ["Shoulder", "Elbow", "Wrist"], ["Shoulder Instability"],
   {}, "grip_core"),
]

# ---- Leg Curl Machine (4 -> 6) ----
NEW += [
ex("legcurl_isohold_001", "Leg Curl Machine Iso Hold", "Hinge", "Isometric", 2, "Leg Curl Machine",
   ["Hamstrings"], [], [],
   ["Knee"], ["Hamstring Strain"],
   {}, "machine_legs"),
ex("legcurl_stretchpartial_001", "Leg Curl Machine Stretch-Position Partials", "Hinge", "Hinge", 2, "Leg Curl Machine",
   ["Hamstrings"], [], [],
   ["Knee"], ["Hamstring Strain - Grade 1 (Mild Strain)"],
   {}, "machine_legs"),
]

# ---- EZ Curl Bar (4 -> 6) ----
NEW += [
ex("ezbar_preachercurl_001", "EZ Bar Preacher Curl", "Vertical Pull", "Pull", 2, "EZ Curl Bar",
   ["Biceps Brachii"], ["Forearm Flexors"], [],
   ["Elbow"], ["Golfer's Elbow"],
   {}, "machine_pull"),
ex("ezbar_closegripbench_001", "EZ Bar Close-Grip Bench Press", "Horizontal Push", "Push", 3, "EZ Curl Bar",
   ["Triceps Brachii", "Pectoralis Major"], ["Anterior Deltoid"], ["Core"],
   ["Elbow", "Shoulder", "Wrist"], ["Tennis Elbow"],
   {}, "barbell_compound"),
]

# ---- GHD (4 -> 6) ----
NEW += [
ex("ghd_obliqueraise_001", "GHD Oblique Raise", "Rotational", "Lateral", 3, "GHD",
   ["Obliques"], ["Rectus Abdominis"], ["Core"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "grip_core"),
ex("ghd_pronelegraise_001", "GHD Prone Leg Raise", "Hinge", "Hinge", 4, "GHD",
   ["Glutes", "Hamstrings"], ["Erector Spinae"], ["Core"],
   ["Lower Back"], ["Low Back Pain", "Hamstring Strain"],
   {}, "grip_core"),
]

# ---- Jump Rope (4 -> 6) ----
NEW += [
ex("jumprope_boxerskip_001", "Jump Rope Boxer Skip", "Conditioning", "Jump", 2, "Jump Rope",
   ["Calves"], ["Quadriceps"], ["Ankle Stabilizers"],
   ["Ankle"], [],
   {}, "conditioning_gpp", Boxing=90, **{"Muay Thai": 88, "Kickboxing": 88}),
ex("jumprope_crisscross_001", "Jump Rope Criss-Cross", "Conditioning", "Jump", 3, "Jump Rope",
   ["Calves", "Anterior Deltoid"], ["Quadriceps"], ["Core"],
   ["Ankle", "Shoulder"], [],
   {}, "conditioning_gpp"),
]

# ---- Reverse Hyper (4 -> 6) ----
NEW += [
ex("reversehyper_bentknee_001", "Reverse Hyper Bent-Knee Variation", "Hinge", "Hinge", 2, "Reverse Hyper",
   ["Glutes", "Hamstrings"], ["Erector Spinae"], ["Core"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "barbell_compound"),
ex("reversehyper_rotational_001", "Reverse Hyper Rotational Twist", "Rotational", "Rotational", 3, "Reverse Hyper",
   ["Obliques", "Erector Spinae"], ["Glutes"], ["Core"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "barbell_compound"),
]

# ---- Seal Row Bench (4 -> 6) ----
NEW += [
ex("sealrow_closegrip_001", "Seal Row Close Grip", "Horizontal Pull", "Pull", 2, "Seal Row Bench",
   ["Latissimus Dorsi", "Biceps Brachii"], ["Rhomboids"], [],
   ["Shoulder", "Elbow"], [],
   {}, "machine_pull"),
ex("sealrow_isohold_001", "Seal Row Iso Hold", "Horizontal Pull", "Pull", 2, "Seal Row Bench",
   ["Rhomboids", "Latissimus Dorsi"], ["Rear Deltoid"], [],
   ["Shoulder"], [],
   {}, "machine_pull"),
]

# ---- Cambered Bar (4 -> 6) ----
NEW += [
ex("camberedbar_press_001", "Cambered Bar Overhead Press", "Vertical Push", "Push", 3, "Cambered Bar",
   ["Anterior Deltoid"], ["Triceps Brachii"], ["Core"],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "barbell_compound"),
ex("camberedbar_frontsquat_001", "Cambered Bar Front Squat", "Squat", "Squat", 4, "Cambered Bar",
   ["Quadriceps", "Gluteus Maximus"], ["Core"], ["Erector Spinae"],
   ["Knee", "Lower Back"], ["Low Back Pain"],
   {}, "barbell_compound"),
]

# ---- Axle Bar (4 -> 6) ----
NEW += [
ex("axlebar_row_001", "Axle Bar Bent-Over Row", "Horizontal Pull", "Pull", 3, "Axle Bar",
   ["Latissimus Dorsi", "Rhomboids"], ["Forearm Flexors"], ["Erector Spinae"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "barbell_compound"),
ex("axlebar_farmercarry_001", "Axle Bar Farmer Carry", "Carry", "Carry", 3, "Axle Bar",
   ["Forearm Flexors", "Erector Spinae"], ["Core"], ["Trapezius"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
]

# ---- Swiss Bar (4 -> 6) ----
NEW += [
ex("swissbar_press_001", "Swiss Bar Overhead Press", "Vertical Push", "Push", 3, "Swiss Bar",
   ["Anterior Deltoid"], ["Triceps Brachii"], ["Core"],
   ["Shoulder", "Wrist"], ["Shoulder Instability"],
   {}, "barbell_compound"),
ex("swissbar_closegripbench_001", "Swiss Bar Close-Grip Bench Press", "Horizontal Push", "Push", 3, "Swiss Bar",
   ["Triceps Brachii", "Pectoralis Major"], ["Anterior Deltoid"], ["Core"],
   ["Elbow", "Shoulder", "Wrist"], ["Tennis Elbow"],
   {}, "barbell_compound"),
]

# ---- Keg (4 -> 6) ----
NEW += [
ex("keg_squat_001", "Keg Squat", "Squat", "Squat", 3, "Keg",
   ["Quadriceps", "Gluteus Maximus"], ["Core"], ["Erector Spinae"],
   ["Knee", "Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("keg_bearhug_001", "Keg Bear Hug Carry", "Carry", "Carry", 3, "Keg",
   ["Erector Spinae", "Core"], ["Trapezius"], ["Forearm Flexors"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
]

# ---- Plate-Loaded Lever Machine (4 -> 6) ----
NEW += [
ex("lever_legpress_001", "Lever Leg Press", "Squat", "Push", 3, "Plate-Loaded Lever Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
ex("lever_squat_001", "Lever Squat", "Squat", "Squat", 3, "Plate-Loaded Lever Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee", "Lower Back"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
]

print(f"Generated {len(NEW)} new exercises across "
      f"{len(set(e['equipment'] for e in NEW))} equipment types.")


def main():
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
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
          f"Backup at {BACKUP}. Now run scripts/enrich_batch8_only.py.")


if __name__ == "__main__":
    main()

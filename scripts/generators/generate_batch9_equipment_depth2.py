"""
generate_batch9_equipment_depth2.py — next pass after batch8. Querying the
live file before this batch: batch8 brought every equipment type up to a
floor of 5 exercises, but that left 36 equipment types sitting at exactly
that floor (mostly isolation machines, strongman implements, and combat/
conditioning tools) while general-purpose equipment (Barbell 121, Dumbbell
37, Kettlebell 37, Bodyweight 46, Cable Machine 11, Resistance Band 16,
Power Rack 19, Pull-up Bar 26, Rings 27) has real depth.

This batch gives each of those 36 equipment-types-at-5 another +2, matching
the exact +2-per-equipment pattern batch6/7/8 used — small and reviewable
per equipment, consistent across the whole batch. New movements were chosen
to be genuinely distinct from the 5 already in the file for that equipment
(different movement_pattern or category, not just a renamed duplicate) —
checked against the current exercises.json entry-by-entry before writing
this file.

Follows the exact pattern of generate_batch6/7/8: hand-tagged joint_stress /
injuries_to_avoid per exercise (reusing the vocabulary already in
exercises.json, no new injury strings introduced), existing equipment_level
values reused from the current file (no new equipment introduced), muscle
names reused from the vocabulary already in use elsewhere in the file.

Run: python scripts/generate_batch9_equipment_depth2.py
Then: python scripts/enrich_batch9_only.py   (derives v4.0+ fields for the new entries)
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "data" / "exercises.json"
BACKUP = ROOT / "data" / "backups" / "exercises_pre_batch9_backup.json"

# equipment_level values taken from the existing exercises.json entries for
# each of these (already-present) equipment types — no new equipment
# introduced in this batch, so no new numbers to invent.
EQUIPMENT_LEVEL = {
    "Ab Wheel": 25, "Agility Ladder": 30, "Atlas Stone": 33, "Balance Board": 47,
    "Battle Ropes": 6, "Belt Squat": 34, "Belt Squat Machine": 44,
    "Boxing Heavy Bag": 31, "Buffalo Bar": 5, "Captain's Chair": 2,
    "Chest Press Machine": 41, "Conan's Wheel": 35, "Fingal's Fingers": 36,
    "Hack Squat Machine": 14, "High Row Machine": 43, "Husafell Stone": 38,
    "Hyperextension Bench": 5, "Leg Extension Machine": 17, "Leg Press Machine": 13,
    "Log Bar": 5, "Neck Harness": 46, "Pec Deck Machine": 19,
    "Pendulum Squat Machine": 40, "Rowing Erg": 6, "Safety Squat Bar": 5,
    "Seated Row Machine": 16, "Shoulder Press Machine": 42, "Sled": 11,
    "Squat Rack": 33, "Suspension Trainer": 26, "Tackle Bag": 10, "Tire": 34,
    "V Squat Machine": 39, "Weighted Vest": 27, "Wrestling Dummy": 10, "Yoke": 29,
}

# Same 10-template sport_priority vocabulary as batch6/7/8, copied verbatim
# (self-contained script, not imported, matching how batch8 was written).
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

# ---- Ab Wheel (5 -> 7) ----
NEW += [
ex("abwheel_feetelevated_001", "Feet-Elevated Ab Wheel Rollout", "Core", "Anti-Extension", 5, "Ab Wheel",
   ["Rectus Abdominis"], ["Anterior Deltoid", "Latissimus Dorsi"], ["Core"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "grip_core"),
ex("abwheel_reversecrunch_001", "Ab Wheel Reverse Crunch", "Core", "Flexion", 2, "Ab Wheel",
   ["Rectus Abdominis"], ["Hip Flexors"], ["Obliques"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "grip_core"),
]

# ---- Agility Ladder (5 -> 7) ----
NEW += [
ex("agilityladder_hipturns_001", "Ladder Hip Turns", "Full Body", "Lateral", 2, "Agility Ladder",
   ["Gluteus Medius", "Hip Abductors"], ["Quadriceps"], ["Ankle Stabilizers"],
   ["Hip", "Ankle"], [],
   {}, "conditioning_gpp"),
ex("agilityladder_backwardrun_001", "Ladder Backward Run", "Full Body", "Sprint", 2, "Agility Ladder",
   ["Hamstrings", "Calves"], ["Quadriceps"], ["Ankle Stabilizers"],
   ["Ankle", "Knee"], [],
   {}, "conditioning_gpp"),
]

# ---- Atlas Stone (5 -> 7) ----
NEW += [
ex("atlasstone_medley_001", "Atlas Stone Circuit Medley", "Full Body", "Complex", 5, "Atlas Stone",
   ["Erector Spinae", "Quadriceps"], ["Core", "Trapezius"], ["Forearm Flexors"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "strongman_carry", HYROX=85),
ex("atlasstone_statichold_001", "Atlas Stone Static Lift Hold", "Carry", "Isometric", 4, "Atlas Stone",
   ["Erector Spinae", "Core"], ["Forearm Flexors"], ["Trapezius"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
]

# ---- Balance Board (5 -> 7) ----
NEW += [
ex("balanceboard_lateralshift_001", "Balance Board Lateral Shift", "Core", "Lateral", 2, "Balance Board",
   ["Ankle Stabilizers", "Gluteus Medius"], ["Hip Abductors"], ["Core"],
   ["Ankle"], ["Lateral Ankle Sprain - Grade 1 (Mild)"],
   {}, "rehab_ankle"),
ex("balanceboard_rotationalreach_001", "Balance Board Rotational Reach", "Core", "Rotation", 3, "Balance Board",
   ["Obliques", "Ankle Stabilizers"], ["Gluteus Medius"], ["Core"],
   ["Ankle", "Lower Back"], ["Lateral Ankle Sprain - Grade 1 (Mild)"],
   {}, "rehab_ankle"),
]

# ---- Battle Ropes (5 -> 7) ----
NEW += [
ex("battleropes_squatwaves_001", "Battle Rope Alternating Waves with Squat", "Conditioning", "Complex", 3, "Battle Ropes",
   ["Anterior Deltoid", "Quadriceps"], ["Core", "Gluteus Maximus"], ["Erector Spinae"],
   ["Shoulder", "Knee"], ["Shoulder Instability"],
   {}, "conditioning_gpp"),
ex("battleropes_slamintervals_001", "Battle Rope Slam Sprint Intervals", "Conditioning", "Sprint", 3, "Battle Ropes",
   ["Anterior Deltoid", "Core"], ["Latissimus Dorsi"], ["Erector Spinae"],
   ["Shoulder", "Lower Back"], ["Shoulder Instability", "Low Back Pain"],
   {}, "conditioning_gpp", HYROX=88),
]

# ---- Belt Squat (5 -> 7) ----
NEW += [
ex("beltsquat_pulse_001", "Belt Squat Pulse Squat", "Squat", "Squat", 2, "Belt Squat",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
ex("beltsquat_singlelegrdl_001", "Belt Squat Single-Leg RDL", "Hinge", "Hinge", 3, "Belt Squat",
   ["Hamstrings", "Gluteus Maximus"], ["Erector Spinae"], ["Gluteus Medius"],
   ["Lower Back", "Hip"], ["Hamstring Strain - Grade 1 (Mild Strain)"],
   {}, "machine_legs"),
]

# ---- Belt Squat Machine (5 -> 7) ----
NEW += [
ex("beltsquatmachine_singleleg_001", "Belt Squat Machine Single-Leg", "Squat", "Squat", 4, "Belt Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
ex("beltsquatmachine_goodmorning_001", "Belt Squat Machine Good Morning", "Hinge", "Hinge", 3, "Belt Squat Machine",
   ["Hamstrings", "Erector Spinae"], ["Gluteus Maximus"], ["Core"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "machine_legs"),
]

# ---- Boxing Heavy Bag (5 -> 7) ----
NEW += [
ex("heavybag_clinchwork_001", "Heavy Bag Clinch Work", "Sport Specific", "Complex", 3, "Boxing Heavy Bag",
   ["Trapezius", "Core"], ["Anterior Deltoid", "Hip Flexors"], ["Forearm Flexors"],
   ["Shoulder", "Neck"], ["Shoulder Instability"],
   {}, "combat_specific", **{"Muay Thai": 90}),
ex("heavybag_lowkicks_001", "Heavy Bag Low Kick Conditioning", "Sport Specific", "Strike", 2, "Boxing Heavy Bag",
   ["Gluteus Maximus", "Obliques"], ["Quadriceps", "Hip Flexors"], ["Core"],
   ["Hip", "Knee"], [],
   {}, "combat_specific", **{"Muay Thai": 92, "Kickboxing": 90}),
]

# ---- Buffalo Bar (5 -> 7) ----
NEW += [
ex("buffalobar_frontsquat_001", "Buffalo Bar Front Squat", "Squat", "Squat", 4, "Buffalo Bar",
   ["Quadriceps", "Gluteus Maximus"], ["Core"], ["Erector Spinae"],
   ["Knee", "Wrist"], ["Chondromalacia Patella", "Wrist Pain"],
   {}, "barbell_compound"),
ex("buffalobar_row_001", "Buffalo Bar Bent-Over Row", "Horizontal Pull", "Pull", 3, "Buffalo Bar",
   ["Latissimus Dorsi", "Rhomboids"], ["Biceps Brachii"], ["Erector Spinae"],
   ["Lower Back", "Elbow"], ["Low Back Pain"],
   {}, "barbell_compound"),
]

# ---- Captain's Chair (5 -> 7) ----
NEW += [
ex("captainschair_reversecrunch_001", "Captain's Chair Reverse Crunch", "Core", "Flexion", 2, "Captain's Chair",
   ["Rectus Abdominis"], ["Hip Flexors"], ["Obliques"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "grip_core"),
ex("captainschair_sidekneeraise_001", "Captain's Chair Side Knee Raise", "Core", "Lateral", 2, "Captain's Chair",
   ["Obliques"], ["Hip Flexors"], ["Rectus Abdominis"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "grip_core"),
]

# ---- Chest Press Machine (5 -> 7) ----
NEW += [
ex("chestpress_partial_001", "Chest Press Machine Partial Reps", "Horizontal Push", "Push", 2, "Chest Press Machine",
   ["Pectoralis Major"], ["Triceps Brachii"], ["Anterior Deltoid"],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "machine_push"),
ex("chestpress_explosive_001", "Chest Press Machine Explosive Press", "Horizontal Push", "Push", 3, "Chest Press Machine",
   ["Pectoralis Major", "Triceps Brachii"], ["Anterior Deltoid"], ["Core"],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {}, "machine_push"),
]

# ---- Conan's Wheel (5 -> 7) ----
NEW += [
ex("conanswheel_bearhugcarry_001", "Conan's Wheel Bear Hug Carry", "Carry", "Carry", 4, "Conan's Wheel",
   ["Erector Spinae", "Core"], ["Trapezius"], ["Forearm Flexors"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("conanswheel_speedlap_001", "Conan's Wheel Speed Lap", "Carry", "Carry", 5, "Conan's Wheel",
   ["Quadriceps", "Erector Spinae"], ["Core"], ["Forearm Flexors"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "strongman_carry", HYROX=82),
]

# ---- Fingal's Fingers (5 -> 7) ----
NEW += [
ex("fingalsfingers_drag_001", "Fingal's Fingers Drag", "Carry", "Carry", 3, "Fingal's Fingers",
   ["Erector Spinae", "Quadriceps"], ["Core"], ["Forearm Flexors"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("fingalsfingers_bearhuglift_001", "Fingal's Fingers Bear Hug Lift", "Full Body", "Complex", 4, "Fingal's Fingers",
   ["Erector Spinae", "Quadriceps"], ["Core", "Trapezius"], ["Forearm Flexors"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
]

# ---- Hack Squat Machine (5 -> 7) ----
NEW += [
ex("hacksquat_15rep_001", "Hack Squat Machine 1.5 Rep", "Squat", "Squat", 4, "Hack Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella", "Jumper's Knee (Patellar Tendinopathy)"],
   {}, "machine_legs"),
ex("hacksquat_deficit_001", "Hack Squat Machine Deficit", "Squat", "Squat", 4, "Hack Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee", "Hip"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
]

# ---- High Row Machine (5 -> 7) ----
NEW += [
ex("highrow_neutralgrip_001", "High Row Machine Neutral-Grip", "Horizontal Pull", "Pull", 2, "High Row Machine",
   ["Latissimus Dorsi", "Rhomboids"], ["Biceps Brachii"], ["Trapezius"],
   ["Shoulder", "Elbow"], [],
   {}, "machine_pull"),
ex("highrow_partialsqueeze_001", "High Row Machine Partial Rep Squeeze", "Horizontal Pull", "Pull", 2, "High Row Machine",
   ["Rhomboids", "Trapezius"], ["Latissimus Dorsi"], [],
   ["Shoulder"], [],
   {}, "machine_pull"),
]

# ---- Husafell Stone (5 -> 7) ----
NEW += [
ex("husafell_statichold_001", "Husafell Stone Static Hold", "Carry", "Isometric", 4, "Husafell Stone",
   ["Erector Spinae", "Core"], ["Trapezius"], ["Forearm Flexors"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("husafell_lungecarry_001", "Husafell Stone Lunge Carry", "Carry", "Lunge", 4, "Husafell Stone",
   ["Quadriceps", "Erector Spinae"], ["Gluteus Maximus", "Core"], ["Hip Flexors"],
   ["Knee", "Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
]

# ---- Hyperextension Bench (5 -> 7) ----
NEW += [
ex("hyperextbench_isohold_001", "Hyperextension Bench Isometric Hold", "Hinge", "Isometric", 2, "Hyperextension Bench",
   ["Erector Spinae", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Lower Back"], ["Low Back Pain", "Lower Back Strain"],
   {}, "grip_core"),
ex("hyperextbench_rotationaltwist_001", "Hyperextension Bench Rotational Twist", "Rotational", "Rotation", 2, "Hyperextension Bench",
   ["Obliques", "Erector Spinae"], ["Gluteus Maximus"], ["Core"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "grip_core"),
]

# ---- Leg Extension Machine (5 -> 7) ----
NEW += [
ex("legextension_15rep_001", "Leg Extension Machine 1.5 Rep", "Squat", "Squat", 3, "Leg Extension Machine",
   ["Quadriceps"], [], [],
   ["Knee"], ["Jumper's Knee (Patellar Tendinopathy)", "Chondromalacia Patella"],
   {}, "machine_legs"),
ex("legextension_pulse_001", "Leg Extension Machine Pulse Reps", "Squat", "Squat", 2, "Leg Extension Machine",
   ["Quadriceps"], [], [],
   ["Knee"], ["Jumper's Knee (Patellar Tendinopathy)"],
   {}, "machine_legs"),
]

# ---- Leg Press Machine (5 -> 7) ----
NEW += [
ex("legpress_pause_001", "Leg Press Machine Pause Rep", "Squat", "Squat", 3, "Leg Press Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
ex("legpress_highfoot_001", "Leg Press Machine High-Foot Placement", "Squat", "Squat", 2, "Leg Press Machine",
   ["Gluteus Maximus", "Hamstrings"], ["Quadriceps"], ["Core"],
   ["Knee", "Hip"], ["Hamstring Strain - Grade 1 (Mild Strain)"],
   {}, "machine_legs"),
]

# ---- Log Bar (5 -> 7) ----
NEW += [
ex("logbar_pushpress_001", "Log Bar Push Press", "Vertical Push", "Push", 4, "Log Bar",
   ["Anterior Deltoid", "Triceps Brachii"], ["Quadriceps", "Core"], ["Trapezius"],
   ["Shoulder", "Lower Back"], ["Shoulder Instability", "Low Back Pain"],
   {}, "strongman_carry"),
ex("logbar_row_001", "Log Bar Row", "Horizontal Pull", "Pull", 3, "Log Bar",
   ["Latissimus Dorsi", "Rhomboids"], ["Biceps Brachii"], ["Erector Spinae"],
   ["Lower Back"], ["Low Back Pain"],
   {}, "strongman_carry"),
]

# ---- Neck Harness (5 -> 7) ----
NEW += [
ex("neckharness_isohold_001", "Neck Harness Isometric Hold", "Core", "Isometric", 2, "Neck Harness",
   ["Neck Extensors", "Neck Flexors"], [], ["Trapezius"],
   ["Neck"], ["Cervical Facet Injury - Stage 1 (Distraction Instability)"],
   {}, "rehab_neck"),
ex("neckharness_diagonalflexion_001", "Neck Harness Diagonal Flexion", "Core", "Flexion", 2, "Neck Harness",
   ["Sternocleidomastoid", "Neck Flexors"], [], ["Neck Extensors"],
   ["Neck"], ["Cervical Facet Injury - Stage 1 (Distraction Instability)"],
   {}, "rehab_neck"),
]

# ---- Pec Deck Machine (5 -> 7) ----
NEW += [
ex("pecdeck_hightolow_001", "Pec Deck Machine High-to-Low Fly", "Horizontal Push", "Push", 2, "Pec Deck Machine",
   ["Pectoralis Major"], ["Anterior Deltoid"], ["Core"],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "machine_push"),
ex("pecdeck_pulse_001", "Pec Deck Machine Pulse Reps", "Horizontal Push", "Push", 2, "Pec Deck Machine",
   ["Pectoralis Major"], [], ["Anterior Deltoid"],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "machine_push"),
]

# ---- Pendulum Squat Machine (5 -> 7) ----
NEW += [
ex("pendulum_15rep_001", "Pendulum Squat Machine 1.5 Rep", "Squat", "Squat", 4, "Pendulum Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
ex("pendulum_narrowstance_001", "Pendulum Squat Machine Narrow Stance", "Squat", "Squat", 3, "Pendulum Squat Machine",
   ["Quadriceps"], ["Gluteus Maximus"], ["Core"],
   ["Knee"], ["Jumper's Knee (Patellar Tendinopathy)"],
   {}, "machine_legs"),
]

# ---- Rowing Erg (5 -> 7) ----
NEW += [
ex("rowingerg_100msprint_001", "Rowing Erg 100m Sprint Repeats", "Conditioning", "Pull", 3, "Rowing Erg",
   ["Latissimus Dorsi", "Quadriceps"], ["Hamstrings"], ["Core"],
   ["Lower Back"], [],
   {}, "conditioning_gpp", HYROX=85),
ex("rowingerg_10kendurance_001", "Rowing Erg 10k Endurance Row", "Conditioning", "Pull", 4, "Rowing Erg",
   ["Latissimus Dorsi", "Quadriceps"], ["Hamstrings", "Rhomboids"], ["Core"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "conditioning_gpp"),
]

# ---- Safety Squat Bar (5 -> 7) ----
NEW += [
ex("ssb_splitsquat_001", "Safety Squat Bar Split Squat", "Squat", "Lunge", 3, "Safety Squat Bar",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee", "Hip"], ["Chondromalacia Patella"],
   {}, "barbell_compound"),
ex("ssb_deadstartsquat_001", "Safety Squat Bar Anderson Squat (Dead Start)", "Squat", "Squat", 4, "Safety Squat Bar",
   ["Quadriceps", "Gluteus Maximus"], ["Core"], ["Erector Spinae"],
   ["Knee", "Lower Back"], ["Low Back Pain"],
   {}, "barbell_compound"),
]

# ---- Seated Row Machine (5 -> 7) ----
NEW += [
ex("seatedrow_lowhandle_001", "Seated Row Machine Low-Handle Row", "Horizontal Pull", "Pull", 2, "Seated Row Machine",
   ["Latissimus Dorsi", "Rhomboids"], ["Biceps Brachii"], ["Erector Spinae"],
   ["Lower Back", "Elbow"], ["Low Back Pain"],
   {}, "machine_pull"),
ex("seatedrow_isohold_001", "Seated Row Machine Iso Hold", "Horizontal Pull", "Pull", 2, "Seated Row Machine",
   ["Rhomboids", "Trapezius"], ["Latissimus Dorsi"], [],
   ["Shoulder"], [],
   {}, "machine_pull"),
]

# ---- Shoulder Press Machine (5 -> 7) ----
NEW += [
ex("shoulderpress_widegrip_001", "Shoulder Press Machine Wide-Grip Press", "Vertical Push", "Push", 2, "Shoulder Press Machine",
   ["Anterior Deltoid"], ["Triceps Brachii"], ["Trapezius"],
   ["Shoulder"], ["Shoulder Instability", "Rotator Cuff"],
   {}, "machine_push"),
ex("shoulderpress_isohold_001", "Shoulder Press Machine Iso Hold", "Vertical Push", "Push", 2, "Shoulder Press Machine",
   ["Anterior Deltoid"], [], ["Triceps Brachii"],
   ["Shoulder"], ["Rotator Cuff"],
   {}, "machine_push"),
]

# ---- Sled (5 -> 7) ----
NEW += [
ex("sled_harnessdrag_001", "Sled Forward Harness Drag", "Conditioning", "Carry", 2, "Sled",
   ["Quadriceps", "Gluteus Maximus"], ["Core"], ["Erector Spinae"],
   ["Knee", "Hip"], [],
   {}, "conditioning_gpp", HYROX=82),
ex("sled_heavypush_001", "Heavy Sled Push", "Conditioning", "Push", 4, "Sled",
   ["Quadriceps", "Gluteus Maximus"], ["Core"], ["Anterior Deltoid"],
   ["Knee", "Shoulder"], [],
   {}, "conditioning_gpp", HYROX=90),
]

# ---- Squat Rack (5 -> 7) ----
NEW += [
ex("squatrack_pinpress_001", "Squat Rack Pin Press (Dead-Stop Bench)", "Horizontal Push", "Push", 4, "Squat Rack",
   ["Pectoralis Major", "Triceps Brachii"], ["Anterior Deltoid"], ["Core"],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {}, "barbell_compound"),
ex("squatrack_pinsquathold_001", "Squat Rack Isometric Pin Squat Hold", "Squat", "Isometric", 3, "Squat Rack",
   ["Quadriceps", "Gluteus Maximus"], ["Core"], ["Erector Spinae"],
   ["Knee", "Lower Back"], ["Chondromalacia Patella"],
   {}, "barbell_compound"),
]

# ---- Suspension Trainer (5 -> 7) ----
NEW += [
ex("trx_yfly_001", "TRX Y-Fly", "Vertical Pull", "Pull", 3, "Suspension Trainer",
   ["Posterior Deltoid", "Trapezius"], ["Rhomboids"], ["Core"],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "grip_core"),
ex("trx_chestpress_001", "TRX Chest Press", "Horizontal Push", "Push", 2, "Suspension Trainer",
   ["Pectoralis Major"], ["Triceps Brachii", "Anterior Deltoid"], ["Core"],
   ["Shoulder"], ["Shoulder Instability"],
   {}, "grip_core"),
]

# ---- Tackle Bag (5 -> 7) ----
NEW += [
ex("tacklebag_reactionread_001", "Tackle Bag Reaction Read Tackle", "Sport Specific", "Complex", 3, "Tackle Bag",
   ["Quadriceps", "Core"], ["Gluteus Maximus"], ["Hip Flexors"],
   ["Knee", "Lower Back"], ["Low Back Pain"],
   {}, "combat_specific", Rugby=90),
ex("tacklebag_lowdrivefinish_001", "Tackle Bag Low Drive Finish", "Sport Specific", "Push", 3, "Tackle Bag",
   ["Quadriceps", "Gluteus Maximus"], ["Core"], ["Erector Spinae"],
   ["Knee", "Lower Back"], ["Low Back Pain"],
   {}, "combat_specific", Rugby=92),
]

# ---- Tire (5 -> 7) ----
NEW += [
ex("tire_lateralhopovers_001", "Tire Lateral Hop-Overs", "Jump", "Lateral", 3, "Tire",
   ["Gluteus Medius", "Quadriceps"], ["Calves"], ["Ankle Stabilizers"],
   ["Knee", "Ankle"], ["High Ankle Sprain (Syndesmosis Tear)"],
   {}, "conditioning_gpp"),
ex("tire_stepovers_001", "Tire Step-Overs", "Full Body", "Complex", 2, "Tire",
   ["Quadriceps", "Hip Flexors"], ["Calves"], ["Core"],
   ["Knee", "Ankle"], [],
   {}, "conditioning_gpp"),
]

# ---- V Squat Machine (5 -> 7) ----
NEW += [
ex("vsquat_deficit_001", "V Squat Machine Deficit Squat", "Squat", "Squat", 4, "V Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee", "Hip"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
ex("vsquat_tempoecc_001", "V Squat Machine Tempo Eccentric", "Squat", "Squat", 3, "V Squat Machine",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Knee"], ["Chondromalacia Patella"],
   {}, "machine_legs"),
]

# ---- Weighted Vest (5 -> 7) ----
NEW += [
ex("weightedvest_sprint_001", "Weighted Vest Sprint Intervals", "Conditioning", "Sprint", 4, "Weighted Vest",
   ["Quadriceps", "Hamstrings"], ["Calves", "Core"], ["Ankle Stabilizers"],
   ["Knee", "Ankle"], ["Hamstring Strain - Grade 1 (Mild Strain)"],
   {}, "conditioning_gpp", **{"Special Forces": 90}),
ex("weightedvest_dip_001", "Weighted Vest Dip", "Vertical Push", "Push", 4, "Weighted Vest",
   ["Triceps Brachii", "Pectoralis Major"], ["Anterior Deltoid"], ["Core"],
   ["Shoulder", "Elbow"], ["Shoulder Instability"],
   {}, "conditioning_gpp"),
]

# ---- Wrestling Dummy (5 -> 7) ----
NEW += [
ex("wrestlingdummy_singlelegfinish_001", "Wrestling Dummy Single-Leg Finish", "Sport Specific", "Complex", 3, "Wrestling Dummy",
   ["Quadriceps", "Erector Spinae"], ["Core", "Gluteus Maximus"], ["Hip Flexors"],
   ["Lower Back", "Knee"], ["Low Back Pain"],
   {}, "combat_specific"),
ex("wrestlingdummy_snapdown_001", "Wrestling Dummy Snap-Down Drill", "Sport Specific", "Pull", 3, "Wrestling Dummy",
   ["Latissimus Dorsi", "Core"], ["Erector Spinae"], ["Forearm Flexors"],
   ["Shoulder", "Lower Back"], ["Low Back Pain"],
   {}, "combat_specific"),
]

# ---- Yoke (5 -> 7) ----
NEW += [
ex("yoke_lateralcarry_001", "Yoke Lateral Carry", "Carry", "Lateral", 4, "Yoke",
   ["Erector Spinae", "Gluteus Medius"], ["Core"], ["Trapezius"],
   ["Lower Back", "Hip"], ["Low Back Pain"],
   {}, "strongman_carry"),
ex("yoke_racksupporthold_001", "Yoke Partial Rack Support Hold", "Carry", "Isometric", 3, "Yoke",
   ["Trapezius", "Erector Spinae"], ["Core"], ["Forearm Flexors"],
   ["Lower Back", "Shoulder"], ["Low Back Pain"],
   {}, "strongman_carry"),
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
          f"Backup at {BACKUP}. Now run scripts/enrich_batch9_only.py.")


if __name__ == "__main__":
    main()

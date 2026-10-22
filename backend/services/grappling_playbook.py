"""
grappling_playbook.py — the Iowa State Grappling Strength & Conditioning
Playbook (BJJ / Judo / Sambo / Wrestling, Beginner->Elite), expressed as
data the live engine reasons over, same contract as conditioning_protocols.py
for the Combat Sports & Rugby manual and sport_profiles.py for transfer
scoring: no printed page is reproduced as a static "here's the PDF" screen -
every table below is a lookup the Program Builder and progression engine
can actually pull a number from.

WHY A SEPARATE MODULE FROM conditioning_protocols.py
conditioning_protocols.py already carries the sport-agnostic reference
material that sits *around* the lifting templates for the wider combat/
contact-sports population this build already serves (energy systems,
aerobic/lactic menus, the pre-lift warm-up, universal neck/grip add-ons).
The Iowa State playbook is scoped tighter - four grappling arts only - but
goes considerably deeper INSIDE the lifting template than that module does:
it's the first source this codebase has that publishes an actual per-level,
per-quality sets/reps/%1RM/rest grid (Section 8's templates), a 4-week wave
so that grid moves across a training block (Section 9), a %1RM-to-rep
translation table, a gated Olympic-lift progression ladder, a 5-level
rotational-strength spectrum, and a body-area-indexed injury-armor system.
None of that has an existing home: strength_standards.py classifies a level
from tested numbers but has no opinion on what to prescribe once an athlete
is at that level; programming_role.py orders exercises within a session but
doesn't define the loading grid those exercises pull from. This module is
that missing per-level prescription layer, scoped to the four sports the
source playbook actually covers - it does not replace or restate
sport_profiles.py's SPORT_QUALITY_PROFILES (why an exercise transfers),
conditioning_protocols.py (aerobic/lactic conditioning), or
injury_taxonomy.py (named-injury filtering); it plugs into all three.

GRAPPLING_SPORTS is deliberately the same four keys already present in
sport_profiles.SPORT_QUALITY_PROFILES (Wrestling, Judo, Sambo, BJJ) - this
module adds a second, complementary layer of per-level programming detail
for sports the engine already scores exercises for, rather than introducing
new sport identities the rest of the engine doesn't recognize.

RECONCILING TWO PROGRESSION RULES
progression_engine.py's existing autoregulation step already nudges load
from session RPE. This playbook expresses the same coaching judgment as an
explicit rule instead of a derived one: "final work set <=RPE 8 with clean
technique -> add ~2.5-5% next exposure; RPE >=9.5 -> repeat or reduce; for
power/Olympic work, add load only if bar/movement speed stays high." Kept
here as GRAPPLING_PROGRESSION_RULE (one rule, reused across all five levels
- the playbook states it identically at every level) rather than folded
silently into progression_engine.py's own load-nudge, so a caller can show
the coaching rule in the athlete's own words instead of just its numeric
effect.
"""

from typing import Dict, List, Optional

GRAPPLING_SPORTS: List[str] = ["Wrestling", "Judo", "Sambo", "BJJ"]

LEVELS: List[str] = ["Beginner", "Novice", "Intermediate", "Advanced", "Elite"]

# ---------------------------------------------------------------------------
# Section 2/3 — Athlete classification + testing battery & benchmarks.
# Classify by training age/force expression, never by mat rank - see
# strength_standards.py for the numeric estimate this text-level rule backs.
# ---------------------------------------------------------------------------
CLASSIFICATION_RULE = (
    "Classify by training age, technical competency in the weight room, force "
    "expression, recovery capacity, injury history, and competition demands - "
    "never by mat rank or ego. Program the lifter you have, not the grappler "
    "you wish you had."
)

# Test -> (quality it measures, what it's used for, retest frequency).
TESTING_BATTERY: List[Dict] = [
    {"test": "Trap-bar 3-5RM", "quality": "Max force", "use": "Lower-body force", "frequency": "8-12 wk"},
    {"test": "Bench 3-5RM", "quality": "Upper push", "use": "Pressing strength", "frequency": "8-12 wk"},
    {"test": "Weighted pull-up", "quality": "Vertical pull", "use": "Grappling pulling", "frequency": "6-10 wk"},
    {"test": "Broad jump", "quality": "Horizontal power", "use": "Projection/athleticism", "frequency": "4-8 wk"},
    {"test": "Rotational MB throw", "quality": "Rotational power", "use": "Hip-trunk sequencing", "frequency": "4-8 wk"},
    {"test": "CMJ", "quality": "Explosiveness", "use": "Readiness/trend", "frequency": "Weekly/biweekly"},
    {"test": "Weighted farmer carry (bodyweight load, timed)", "quality": "Grip/trunk endurance", "use": "Positional grinding strength", "frequency": "8-12 wk"},
    {"test": "3-position hang clean (technical, not max)", "quality": "Power expression", "use": "Transfer of Olympic ladder work", "frequency": "8-12 wk"},
]
TESTING_BATTERY_NOTE = (
    "Track a small, repeatable battery rather than a huge one nobody actually "
    "retests. Use trends, not single tests - a number moving the wrong "
    "direction across three test cycles tells you a lot more than one number "
    "in isolation."
)

# Relative-strength guideline targets by level. x BW = multiple of bodyweight.
# A guideline, not a mandate - deliberately separate from
# strength_standards.py's _BARBELL_STANDARDS (that table classifies a level
# from a number; this one is the playbook's own stated target once someone
# is already at a level, and covers a movement - weighted pull-up - the
# generic table doesn't).
RELATIVE_STRENGTH_TARGETS: Dict[str, Dict[str, str]] = {
    "Beginner": {"trap_bar_deadlift": "1.0-1.3x BW", "bench": "0.7-0.9x BW", "weighted_pull_up": "Bodyweight for reps", "broad_jump": "Establish baseline"},
    "Novice": {"trap_bar_deadlift": "1.4-1.7x BW", "bench": "1.0-1.1x BW", "weighted_pull_up": "+10-25 lb", "broad_jump": "+5-10% over baseline"},
    "Intermediate": {"trap_bar_deadlift": "1.8-2.1x BW", "bench": "1.2-1.35x BW", "weighted_pull_up": "+25-45 lb", "broad_jump": "Top 50% of squad"},
    "Advanced": {"trap_bar_deadlift": "2.2-2.5x BW", "bench": "1.4-1.55x BW", "weighted_pull_up": "+45-70 lb", "broad_jump": "Top 25% of squad"},
    "Elite": {"trap_bar_deadlift": "2.5x+ BW", "bench": "1.55x+ BW", "weighted_pull_up": "+70 lb+", "broad_jump": "Top of squad, trending stable"},
}

# ---------------------------------------------------------------------------
# Section 4 — RAMP warm-up system. Raise, Activate, Mobilize, Potentiate, in
# that order. Deliberately separate from conditioning_protocols.WARMUP_
# PROTOCOL (that one is the Combat Sports manual's own pre-lift sequence,
# built for the wider sport population this build already serves) - RAMP is
# this playbook's own four-phase structure and shouldn't be silently merged
# into a different manual's warm-up under one shared name.
# ---------------------------------------------------------------------------
RAMP_WARMUP: List[Dict] = [
    {"phase": "Raise", "duration": "3-5 min", "content": "Bike, row, or light skip/jog to raise core temperature and heart rate."},
    {"phase": "Activate", "duration": "3-5 min", "content": "Glute bridge/band walk, scap activation, core bracing drill."},
    {"phase": "Mobilize", "duration": "3-5 min", "content": "Hip 90/90, thoracic rotation, ankle rocks - joints the session will load."},
    {"phase": "Potentiate", "duration": "4-6 min", "content": "Build-up sets of the day's first lift, or 2-3 low-intensity jumps/throws."},
]
RAMP_RULE = (
    "If the warm-up leaves the athlete breathing hard or sweating through "
    "their shirt before the bar even loads, it was conditioning - cut it."
)

# ---------------------------------------------------------------------------
# Section 5.3 — Rotational strength, the 5-level spectrum. Grapplers
# generate almost all throwing/scrambling power through the trunk; this is
# central programming, not accessory work.
# ---------------------------------------------------------------------------
ROTATIONAL_SPECTRUM: List[Dict] = [
    {"level": 1, "name": "Anti-rotation", "template": "Pallof press, suitcase carry"},
    {"level": 2, "name": "Controlled rotation", "template": "Cable lift/chop, landmine rotation"},
    {"level": 3, "name": "Loaded rotation", "template": "Landmine rotational press/row"},
    {"level": 4, "name": "Ballistic rotation", "template": "Medicine-ball scoop and shot-put throws"},
    {"level": 5, "name": "Contrast", "template": "Heavy anti-rotation set immediately followed by a ballistic throw"},
]

# ---------------------------------------------------------------------------
# Section 5.6 — Recovery & autoregulation status. Same 4-tier shape as
# readiness_service.py's continuous 0-100 suggested-readiness score, but
# expressed as the playbook's own coach-facing traffic-light bands rather
# than a computed number - kept as a thin mapping (see
# autoregulation_status_for_readiness) so a UI can show the coaching phrase
# alongside the existing numeric score instead of one replacing the other.
# ---------------------------------------------------------------------------
AUTOREGULATION_STATUS: List[Dict] = [
    {"status": "Green", "template": "Good sleep/readiness; run the full plan"},
    {"status": "Yellow", "template": "Moderate fatigue; cut accessory sets 20-30%"},
    {"status": "Orange", "template": "High mat fatigue; keep only key strength/power"},
    {"status": "Red", "template": "Pain, illness, marked performance drop; stop or replace session and refer to medical staff when appropriate"},
]


def autoregulation_status_for_readiness(readiness_0_100: float) -> Dict:
    """Maps readiness_service.py's continuous suggested-readiness score
    (0-100) onto the playbook's own Green/Yellow/Orange/Red coaching bands.
    Thresholds are this module's own reasonable split of the playbook's
    four qualitative bands across the existing 0-100 scale (the source
    playbook doesn't publish numeric cutoffs, only the coaching template
    per band), not a value taken from the manual itself.
    """
    if readiness_0_100 >= 80:
        band = AUTOREGULATION_STATUS[0]
    elif readiness_0_100 >= 60:
        band = AUTOREGULATION_STATUS[1]
    elif readiness_0_100 >= 35:
        band = AUTOREGULATION_STATUS[2]
    else:
        band = AUTOREGULATION_STATUS[3]
    return {**band, "readiness_used": readiness_0_100}


# ---------------------------------------------------------------------------
# Section 6 — Olympic-lift progression ladder. Nobody skips a step; the gate
# rule is technical cleanliness under fatigue, not a fresh first rep.
# ---------------------------------------------------------------------------
OLYMPIC_LADDER: List[Dict] = [
    {"step": 1, "movement": "Hang high pull (dumbbell or barbell)", "purpose": "Teach the vertical pull and shrug pattern with low technical cost"},
    {"step": 2, "movement": "Hang muscle clean", "purpose": "Add the turnover without a full pull under"},
    {"step": 3, "movement": "Hang power clean", "purpose": "Full pull, athlete catches in a quarter-squat"},
    {"step": 4, "movement": "Power clean from blocks/floor", "purpose": "Extend the pull range once catch position is reliable"},
    {"step": 5, "movement": "Push press / jerk drive", "purpose": "Convert leg drive into overhead force expression"},
    {"step": 6, "movement": "Full clean & jerk / snatch derivatives (Advanced-Elite only)", "purpose": "Reserve for athletes with clean mobility, coaching supervision, and no red-flag joint history"},
]
OLYMPIC_LADDER_GATE_RULE = (
    "An athlete does not advance a step until the current step is "
    "technically clean under fatigue, not just on a fresh first rep."
)

# ---------------------------------------------------------------------------
# Section 7 — Discipline-specific supplemental blocks. Layer 2-3 of these
# onto an athlete's template on top of the universal six pillars, based on
# primary discipline. Complements, doesn't replace,
# sport_profiles.SPORT_QUALITY_PROFILES: that dict says which athletic
# qualities transfer for scoring exercises already in the database; this
# says which named block-level additions the playbook itself recommends
# layering on for each sport's specific demands.
# ---------------------------------------------------------------------------
DISCIPLINE_SUPPLEMENTAL_BLOCKS: Dict[str, Dict] = {
    "Wrestling": {
        "demands": "Repeated explosive hip extension, penetration-step power, sprawl speed, top-position control, gas-tank strength endurance.",
        "additions": [
            "Broad jump -> shot-entry contrast pairing (jump then immediately drill a live shot)",
            "Heavy sled drags for drive-phase leg strength without joint pounding",
            "Anti-rotation carries for scramble stability",
            "Neck bridges and harness work for bridging/defense strength",
            "Repeated-effort circuits (:20 hard / :40 easy) to mirror match energy systems",
        ],
    },
    "Judo": {
        "demands": "Grip fighting endurance, off-balancing (kuzushi) power, explosive hip rotation for throws, falling/landing resilience.",
        "additions": [
            "Heavy gi/rope pulls and static grip holds for kumi-kata strength",
            "Landmine rotational throws to mirror uchi-mata / seoi-nage torque",
            "Trap-bar jump shrugs for explosive hip extension into a lift",
            "Judo-specific falling drills paired with light plyometrics for shock absorption",
            "Single-leg RDL and lateral bound work for off-balance recovery strength",
        ],
    },
    "BJJ": {
        "demands": "Positional isometric strength, grip and forearm endurance, hip-driven guard passing/retention power, long-duration strength-endurance.",
        "additions": [
            "Long-duration isometric holds (Pallof, plank variations) at position-specific joint angles",
            "Dead-hang and towel-grip endurance work",
            "Hip thrust and single-leg bridge variations for guard retention and bridging escapes",
            "Turkish get-up progressions for whole-body control under load",
            "Extended-set carries (60-90s) to build the grinding strength BJJ rewards",
        ],
    },
    "Sambo": {
        "demands": "Explosive throwing power with leg-lock-specific hip and knee resilience, combined striking-adjacent hip rotation, high-output grip strength.",
        "additions": [
            "Rotational medicine-ball throws at multiple heights (hip, chest, overhead) for varied throw entries",
            "Nordic curls and reverse hyper work for posterior-chain leg-lock defense",
            "Landmine single-arm press for off-angle pushing strength",
            "Ankle and knee prehab circuit given leg-lock exposure",
            "Explosive step-in lunges to mirror sambo throw entries",
        ],
    },
}


def discipline_supplemental_block(sport: str) -> Optional[Dict]:
    """The playbook's Section 7 block for one of the four grappling sports,
    or None for anything outside GRAPPLING_SPORTS - same "None means not
    covered" contract as sport_profiles.sport_conditioning_profile.
    """
    return DISCIPLINE_SUPPLEMENTAL_BLOCKS.get(sport)


# ---------------------------------------------------------------------------
# Section 8/9 — Level-by-level programming templates + percentage-based
# loading. Every level shares the same seven training qualities; sets/reps/
# %1RM/rest scale with training age. This is the per-level prescription
# grid strength_standards.py never had an opinion on - it only classifies
# which level someone is at, not what to load once they're there.
# ---------------------------------------------------------------------------
LEVEL_LOADING: Dict[str, Dict] = {
    "Beginner": {
        "loading_pct_range": "50-70%", "weekly_sessions": "2-3", "key_rule": "Perfect reps over everything",
        "split": [
            {"day": "Mon", "session": "Full Body A", "objective": "Force + skill"},
            {"day": "Wed", "session": "Full Body B", "objective": "Power + unilateral"},
            {"day": "Fri", "session": "Full Body C", "objective": "Upper/lower balance"},
        ],
        "qualities": {
            "Max Strength": {"sets_reps": "3x5-8", "pct_1rm": "55-70%", "examples": "Squat/SSB, trap-bar DL, bench, weighted pull-up", "rest": "2-4 min"},
            "Explosive/Ballistic": {"sets_reps": "3x6-10", "pct_1rm": "30-45% (bodyweight/light-load jumps & throws)", "examples": "Jump, throw, high pull, landmine press", "rest": "2-4 min"},
            "Grappling Accessory": {"sets_reps": "2-3x8-12", "pct_1rm": "60-70%", "examples": "Row, split squat, chop/lift, sled", "rest": "60-150 s"},
            "Hypertrophy/Isolation": {"sets_reps": "2x10-15", "pct_1rm": "50-65%", "examples": "Curl, lateral raise, triceps, hamstring curl", "rest": "60-150 s"},
            "Loaded Carry / Grip": {"sets_reps": "3x20-30m", "pct_1rm": "BW-0.5x BW load", "examples": "Farmer, suitcase, yoke, towel hang", "rest": "60-150 s"},
            "Olympic / Power Derivative": {"sets_reps": "3x3-5 (primer: hang pulls, MB scoop toss)", "pct_1rm": "40-55% (technical primer only)", "examples": "Hang clean, high pull, push press, snatch pull", "rest": "2-4 min"},
            "Prehab / Armor": {"sets_reps": "2-3x10-15, slow tempo", "pct_1rm": "Bodyweight/band, light", "examples": "Cuff, scap, neck iso, VMO, copenhagen", "rest": "45-90 s"},
        },
    },
    "Novice": {
        "loading_pct_range": "60-80%", "weekly_sessions": "3", "key_rule": "Own the patterns before loading them",
        "split": [
            {"day": "Mon", "session": "Lower", "objective": "Force + hypertrophy"},
            {"day": "Tue", "session": "Upper", "objective": "Force + pulling"},
            {"day": "Thu", "session": "Power", "objective": "Jumps/throws + strength"},
            {"day": "Sat", "session": "Full Body", "objective": "Mass + grip"},
        ],
        "qualities": {
            "Max Strength": {"sets_reps": "4x4-6", "pct_1rm": "65-78%", "examples": "Squat/SSB, trap-bar DL, bench, weighted pull-up", "rest": "2-4 min"},
            "Explosive/Ballistic": {"sets_reps": "3x6-10", "pct_1rm": "30-45%", "examples": "Jump, throw, high pull, landmine press", "rest": "2-4 min"},
            "Grappling Accessory": {"sets_reps": "3x8-12", "pct_1rm": "65-75%", "examples": "Row, split squat, chop/lift, sled", "rest": "60-150 s"},
            "Hypertrophy/Isolation": {"sets_reps": "3x10-15", "pct_1rm": "55-68%", "examples": "Curl, lateral raise, triceps, hamstring curl", "rest": "60-150 s"},
            "Loaded Carry / Grip": {"sets_reps": "4x20-40m", "pct_1rm": "0.5-0.75x BW load", "examples": "Farmer, suitcase, yoke, towel hang", "rest": "60-150 s"},
            "Olympic / Power Derivative": {"sets_reps": "3-4x3-5 (hang high pull, push press)", "pct_1rm": "50-65%", "examples": "Hang clean, high pull, push press, snatch pull", "rest": "2-4 min"},
            "Prehab / Armor": {"sets_reps": "3x10-15", "pct_1rm": "Bodyweight/band, light-moderate", "examples": "Cuff, scap, neck iso, VMO, copenhagen", "rest": "45-90 s"},
        },
    },
    "Intermediate": {
        "loading_pct_range": "70-88%", "weekly_sessions": "3-4", "key_rule": "Explosive intent on every rep",
        "split": [
            {"day": "Mon", "session": "Lower Force", "objective": "Max strength"},
            {"day": "Tue", "session": "Upper Force", "objective": "Max strength"},
            {"day": "Thu", "session": "Power", "objective": "Explosive + rotation"},
            {"day": "Sat", "session": "Hypertrophy", "objective": "Jacked + grip"},
        ],
        "qualities": {
            "Max Strength": {"sets_reps": "4-5x3-5", "pct_1rm": "75-87%", "examples": "Squat/SSB, trap-bar DL, bench, weighted pull-up", "rest": "2-4 min"},
            "Explosive/Ballistic": {"sets_reps": "4x5-8", "pct_1rm": "30-50% (or 10-20% BW for MB)", "examples": "Jump, throw, high pull, landmine press", "rest": "2-4 min"},
            "Grappling Accessory": {"sets_reps": "3-4x6-10", "pct_1rm": "70-80%", "examples": "Row, split squat, chop/lift, sled", "rest": "60-150 s"},
            "Hypertrophy/Isolation": {"sets_reps": "3x8-12", "pct_1rm": "60-72%", "examples": "Curl, lateral raise, triceps, hamstring curl", "rest": "60-150 s"},
            "Loaded Carry / Grip": {"sets_reps": "4x30-40m", "pct_1rm": "0.75-1.0x BW load", "examples": "Farmer, suitcase, yoke, towel hang", "rest": "60-150 s"},
            "Olympic / Power Derivative": {"sets_reps": "4-5x2-3 (power clean/snatch derivatives)", "pct_1rm": "60-75%", "examples": "Hang clean, high pull, push press, snatch pull", "rest": "2-4 min"},
            "Prehab / Armor": {"sets_reps": "3x8-12", "pct_1rm": "Light external load", "examples": "Cuff, scap, neck iso, VMO, copenhagen", "rest": "45-90 s"},
        },
    },
    "Advanced": {
        "loading_pct_range": "75-92%", "weekly_sessions": "3-5", "key_rule": "Manage fatigue, protect bar speed",
        "split": [
            {"day": "Mon", "session": "Force 1", "objective": "Heavy lower + pull"},
            {"day": "Tue", "session": "Force 2", "objective": "Heavy upper + rotation"},
            {"day": "Thu", "session": "Power", "objective": "Speed + throws"},
            {"day": "Fri/Sat", "session": "Specialized", "objective": "Hypertrophy or weak points"},
        ],
        "qualities": {
            "Max Strength": {"sets_reps": "4-6x2-4", "pct_1rm": "82-91%", "examples": "Squat/SSB, trap-bar DL, bench, weighted pull-up", "rest": "2-4 min"},
            "Explosive/Ballistic": {"sets_reps": "3-5x4-8", "pct_1rm": "30-50%", "examples": "Jump, throw, high pull, landmine press", "rest": "2-4 min"},
            "Grappling Accessory": {"sets_reps": "3-4x5-8", "pct_1rm": "72-82%", "examples": "Row, split squat, chop/lift, sled", "rest": "60-150 s"},
            "Hypertrophy/Isolation": {"sets_reps": "2-4x8-12", "pct_1rm": "62-75%", "examples": "Curl, lateral raise, triceps, hamstring curl", "rest": "60-150 s"},
            "Loaded Carry / Grip": {"sets_reps": "4x30-50m", "pct_1rm": "1.0-1.25x BW load", "examples": "Farmer, suitcase, yoke, towel hang", "rest": "60-150 s"},
            "Olympic / Power Derivative": {"sets_reps": "5-6x1-3 (full lifts, contrast pairing)", "pct_1rm": "70-85%", "examples": "Hang clean, high pull, push press, snatch pull", "rest": "2-4 min"},
            "Prehab / Armor": {"sets_reps": "3-4x6-10", "pct_1rm": "Light-moderate external load", "examples": "Cuff, scap, neck iso, VMO, copenhagen", "rest": "45-90 s"},
        },
    },
    "Elite": {
        "loading_pct_range": "80-95%+", "weekly_sessions": "3-5", "key_rule": "Smallest dose that keeps qualities sharp",
        "split": [
            {"day": "Mon", "session": "Heavy", "objective": "High force, low volume"},
            {"day": "Tue", "session": "Power", "objective": "Max velocity"},
            {"day": "Thu", "session": "Heavy", "objective": "Upper/lower force"},
            {"day": "Sat", "session": "Transfer", "objective": "Throws, jumps, carries, targeted mass"},
        ],
        "qualities": {
            "Max Strength": {"sets_reps": "3-6x1-3", "pct_1rm": "88-95%+", "examples": "Squat/SSB, trap-bar DL, bench, weighted pull-up", "rest": "2-4 min"},
            "Explosive/Ballistic": {"sets_reps": "3-4x3-6", "pct_1rm": "30-50%", "examples": "Jump, throw, high pull, landmine press", "rest": "2-4 min"},
            "Grappling Accessory": {"sets_reps": "2-4x4-8", "pct_1rm": "75-85%", "examples": "Row, split squat, chop/lift, sled", "rest": "60-150 s"},
            "Hypertrophy/Isolation": {"sets_reps": "2-3x6-10", "pct_1rm": "65-78%", "examples": "Curl, lateral raise, triceps, hamstring curl", "rest": "60-150 s"},
            "Loaded Carry / Grip": {"sets_reps": "3-5x20-40m", "pct_1rm": "1.25x+ BW load", "examples": "Farmer, suitcase, yoke, towel hang", "rest": "60-150 s"},
            "Olympic / Power Derivative": {"sets_reps": "5-6x1-2 (crisp singles/doubles, full recovery)", "pct_1rm": "78-90%", "examples": "Hang clean, high pull, push press, snatch pull", "rest": "2-4 min"},
            "Prehab / Armor": {"sets_reps": "2-4x8-12, targeted only", "pct_1rm": "Moderate external load", "examples": "Cuff, scap, neck iso, VMO, copenhagen", "rest": "45-90 s"},
        },
    },
}

GRAPPLING_PROGRESSION_RULE = (
    "When the final work set finishes at <=RPE 8 with clean technique, add "
    "~2.5-5% load next exposure. If RPE >=9.5, repeat or reduce. For power/"
    "Olympic work, add load only if bar/movement speed stays high - never "
    "chase a rep that turns into a grind."
)


def level_loading_table(level: str) -> Optional[Dict]:
    """Section 8's full per-quality loading grid for one level, plus its
    weekly split and key rule. Returns None for a level string outside
    LEVELS (mirrors experience_level's own Literal validation in
    schemas.py - this module doesn't re-validate, callers already have).
    """
    return LEVEL_LOADING.get(level)


# Section 9 — Standard %1RM-to-rep chart. Find the rep range a template
# prescribes, cross-reference this table, that's the starting load.
PCT_1RM_REP_CHART: List[Dict] = [
    {"pct_1rm": "100%", "approx_reps": "1", "typical_use": "Max-effort test only - rare, and only Advanced/Elite"},
    {"pct_1rm": "95%", "approx_reps": "2", "typical_use": "Peak/competition-prep singles-doubles"},
    {"pct_1rm": "90%", "approx_reps": "3-4", "typical_use": "Advanced/Elite heavy strength work"},
    {"pct_1rm": "85%", "approx_reps": "5", "typical_use": "Intermediate-Elite main strength sets"},
    {"pct_1rm": "80%", "approx_reps": "6-8", "typical_use": "Novice-Intermediate main strength sets"},
    {"pct_1rm": "75%", "approx_reps": "8-10", "typical_use": "Beginner-Novice main strength sets"},
    {"pct_1rm": "70%", "approx_reps": "10-12", "typical_use": "Accessory/hypertrophy work, technical primers"},
    {"pct_1rm": "65%", "approx_reps": "12-15", "typical_use": "Hypertrophy/isolation, higher-rep accessory"},
    {"pct_1rm": "60%", "approx_reps": "15-18", "typical_use": "Warm-up ramping, technical/isolation work"},
    {"pct_1rm": "50% or less", "approx_reps": "20+", "typical_use": "Warm-up sets, prehab/armor, technical drilling"},
]

# Section 9 — 4-week wave, main lift % of 1RM by level. Applies to the Max
# Strength (heavy) and Olympic/Power Derivative rows of LEVEL_LOADING. Week
# 4 is always a deload: drop volume ~40% at the listed percentage.
WAVE_PROGRESSION: Dict[str, Dict[str, str]] = {
    "Beginner": {"week_1": "55-60%", "week_2": "60-65%", "week_3": "65-70%", "week_4": "45-50%, low volume"},
    "Novice": {"week_1": "65-68%", "week_2": "70-73%", "week_3": "75-78%", "week_4": "50-55%, low volume"},
    "Intermediate": {"week_1": "75-78%", "week_2": "80-83%", "week_3": "85-87%", "week_4": "55-60%, low volume"},
    "Advanced": {"week_1": "82-85%", "week_2": "86-88%", "week_3": "89-91%", "week_4": "60-65%, low volume"},
    "Elite": {"week_1": "85-88%", "week_2": "89-91%", "week_3": "92-95%", "week_4": "65-70%, low volume"},
}
WAVE_VELOCITY_OVERRIDE_RULE = (
    "If bar speed or jump/throw output drops noticeably at the prescribed %, "
    "that's the ceiling for the day - cap the load there regardless of what "
    "the wave chart says. The wave is a plan, not a promise."
)


def wave_week_pct(level: str, week: int) -> Optional[str]:
    """The %1RM band for a given level at a given week (1-4) of the 4-week
    wave. `week` outside 1-4 wraps to the nearest boundary week rather than
    raising, since a macrocycle (see MACROCYCLE_PHASES) repeats this same
    4-week wave across multiple blocks - callers passing an absolute
    program week should take `((week - 1) % 4) + 1` before calling this.
    """
    table = WAVE_PROGRESSION.get(level)
    if not table:
        return None
    week = max(1, min(4, week))
    return table[f"week_{week}"]


# ---------------------------------------------------------------------------
# Section 10 — Injury prevention / armor system. Grapplers get hurt in
# predictable places. Programmed into every level's Prehab/Armor slot
# above, not optional "if there's time" work. Body-area keys deliberately
# match injury_taxonomy.py's own joint tags (Shoulder, Neck, Knee, Elbow,
# Ankle; Low Back / Hip is injury_taxonomy's "Lower Back" + "Hip" combined,
# since the playbook programs them as one combined-area slot) so a caller
# already holding a joint tag from an injury lookup can go straight to the
# matching armor protocol without a second translation table.
# ---------------------------------------------------------------------------
ARMOR_PROTOCOLS: Dict[str, Dict] = {
    "Shoulder": {"template": "Band pull-aparts, external rotation, prone Y-T-W, scap push-up", "dose": "2-3x12-15, light load, daily-tolerable"},
    "Neck": {"template": "4-way iso holds, harness bridges, manual resistance", "dose": "3x20-30s holds, progress conservatively"},
    "Knee": {"template": "Copenhagen plank, reverse Nordic, terminal knee extension", "dose": "2-3x8-12 per side"},
    "Low Back / Hip": {"template": "Bird-dog, dead bug, 90/90 hip switch, suitcase carry", "dose": "2-3x10-12 or 30-40m"},
    "Elbow / Grip": {"template": "Wrist curls/extensions, band pull-throughs, plate pinch", "dose": "2-3x12-15"},
    "Ankle": {"template": "Calf raise (straight + bent knee), single-leg balance reach", "dose": "2-3x10-15 per side"},
}
ARMOR_PLACEMENT_RULE = (
    "Run prehab either at the start of the session as part of warm-up "
    "potentiation, or as a finisher - never wedged between two heavy "
    "strength sets where it can blunt performance."
)


def armor_protocol_for_joint(joint: str) -> Optional[Dict]:
    """Looks up ARMOR_PROTOCOLS off an injury_taxonomy.py-style joint tag.
    Handles the one naming split described above (Lower Back / Hip ->
    combined "Low Back / Hip" slot); anything else is a direct key match.
    """
    if joint in ("Lower Back", "Hip"):
        return ARMOR_PROTOCOLS["Low Back / Hip"]
    if joint in ("Elbow", "Grip", "Wrist"):
        return ARMOR_PROTOCOLS["Elbow / Grip"]
    return ARMOR_PROTOCOLS.get(joint)


# ---------------------------------------------------------------------------
# Section 11 — Exercise selection matrix. A coaching reference, not a rigid
# prescription; the athlete's sport practice, bodyweight, competition
# schedule, and recovery determine the final dose.
# ---------------------------------------------------------------------------
EXERCISE_SELECTION_MATRIX: Dict[str, str] = {
    "Primary strength": "Safety-bar squat, trap-bar deadlift, bench press, weighted pull-up, heavy row",
    "Power": "Jumps, medicine-ball throws, high pulls, clean derivatives, trap-bar jumps, landmine power press",
    "Rotation": "Landmine rotation, cable chop/lift, rotational throws, anti-rotation carries",
    "Grip": "Towel pull-ups, thick-handle holds, farmer carry, suitcase carry, plate pinches",
    "Neck": "Isometrics; controlled flexion/extension/lateral work; progress conservatively",
    "Hypertrophy": "Incline press, rows, pull-downs, lateral raises, curls, triceps, hamstrings, calves",
    "Sled": "Push, drag, backward drag; useful when low soreness is desired",
    "Olympic derivative": "Hang high pull, hang muscle/power clean, push press, snatch pull",
    "Prehab": "Band external rotation, Copenhagen plank, dead bug, reverse Nordic",
}

# ---------------------------------------------------------------------------
# Section 12 — 16-week macrocycle. Two deloads and a dedicated taper;
# compress or repeat blocks depending on competition density.
# ---------------------------------------------------------------------------
MACROCYCLE_PHASES: List[Dict] = [
    {"weeks": "1-3", "phase": "General Prep", "template": "Technical volume, hypertrophy base, movement competency"},
    {"weeks": "4", "phase": "Deload / Test", "template": "Reduce volume ~40%; run testing battery"},
    {"weeks": "5-8", "phase": "Strength Accumulation", "template": "Build max strength and work capacity; introduce Olympic derivatives"},
    {"weeks": "8", "phase": "Deload / Retest", "template": "Reduce volume; retest key lifts and jumps"},
    {"weeks": "9-12", "phase": "Power-Strength", "template": "Shift toward speed-strength; contrast pairing; rotational ballistic work peaks"},
    {"weeks": "12", "phase": "Deload", "template": "Light week before competition block begins"},
    {"weeks": "13-15", "phase": "Competition Prep / Taper", "template": "Cut accessory volume, preserve intensity and bar speed"},
    {"weeks": "16", "phase": "Peak / Competition", "template": "Minimal, high-quality touches only; prioritize freshness"},
]

# In-season load management by mat-load band (distinct axis from the
# macrocycle above - this adjusts a given week's S&C dose to how hard mat
# practice already was that week, not where the week sits in the 16-week
# block).
IN_SEASON_LOAD_MANAGEMENT: List[Dict] = [
    {"mat_load": "High mat load", "template": "2-3 S&C sessions; low volume, moderate-high intensity"},
    {"mat_load": "Moderate mat load", "template": "3 sessions; maintain strength and power"},
    {"mat_load": "Low mat load", "template": "3-4 sessions; add hypertrophy and development"},
    {"mat_load": "Competition week", "template": "Short exposures; preserve speed and confidence"},
]


def macrocycle_phase_for_week(week: int) -> Optional[Dict]:
    """The MACROCYCLE_PHASES entry covering an absolute 1-16 program week.
    Weeks 4, 8, and 12 each appear as their own single-week deload/retest
    phase in the table (not folded into the block before/after them),
    matching the playbook's own week-by-week breakdown.
    """
    # Single-week deload/retest entries (4, 8, 12) are checked before range
    # entries: week 8 falls inside both the "5-8" range and its own "8"
    # row, and the playbook's table lists the range first - a naive
    # first-match scan would return "Strength Accumulation" for week 8
    # instead of the single-week "Deload / Retest" row the playbook
    # actually intends for that week.
    for entry in MACROCYCLE_PHASES:
        if "-" not in entry["weeks"] and int(entry["weeks"]) == week:
            return entry
    for entry in MACROCYCLE_PHASES:
        w = entry["weeks"]
        if "-" in w:
            lo, hi = w.split("-")
            if int(lo) <= week <= int(hi):
                return entry
    return None


# ---------------------------------------------------------------------------
# Section 13 — Session cards. Seven reusable session shapes; pick exercises
# from EXERCISE_SELECTION_MATRIX and load from LEVEL_LOADING. Explosive
# work always precedes heavy strength work in the same session - the same
# ordering principle programming_role.py's ROLE_ORDER already encodes
# (Power & Explosive ranks above Primary/Secondary Strength there); these
# cards are a coarser, named-slot view of the same idea for the four
# grappling sports specifically, not a competing order.
# ---------------------------------------------------------------------------
SESSION_CARDS: Dict[str, List[str]] = {
    "Power + Rotation": ["Jump/throw", "Primary strength", "Rotational power", "Grappling accessory", "Grip/carry", "Optional hypertrophy"],
    "Upper Hypertrophy": ["Jump/throw", "Primary press", "Secondary pull", "Shoulder/arm accessory", "Grip/carry", "Optional isolation"],
    "Lower Strength": ["Jump/throw", "Primary squat/hinge", "Unilateral strength", "Posterior chain accessory", "Carry", "Optional calf/hamstring"],
    "Grip + Pulling": ["Jump/throw", "Primary pull", "Row variation", "Curl/forearm", "Grip endurance", "Optional back accessory"],
    "Max Strength": ["Jump/throw (low volume)", "Primary strength (heavy)", "Secondary strength", "Grappling accessory", "Grip/carry", "Optional hypertrophy"],
    "Olympic Power": ["Hang pull/clean progression", "Push press/jerk drive", "Primary strength", "Rotational ballistic throw", "Grip/carry", "Optional prehab"],
    "Discipline Conditioning": ["Sport-specific movement prep", "Explosive contrast pair", "Repeated-effort circuit (:20/:40)", "Grip/neck finisher", "Sled work", "Cool-down prehab"],
}
SESSION_CARD_SEQUENCING_RULE = (
    "Always sequence explosive work before heavy strength work in the same "
    "session. If mat fatigue is high, cut the optional hypertrophy/finisher "
    "slot first. If power quality drops mid-session, reduce load and volume "
    "rather than forcing output - a slow rep training explosiveness is "
    "training the wrong quality."
)


def session_card(name: str) -> Optional[List[str]]:
    """One of the seven named session shapes as an ordered list of block
    labels. `name` must match a SESSION_CARDS key exactly (case-sensitive,
    same convention as sport_profiles' sport-name keys).
    """
    return SESSION_CARDS.get(name)


# ---------------------------------------------------------------------------
# Section 14 — Recovery & fueling basics. General, sport-science-level
# guidance only; individual nutrition needs vary by weight class, cut
# history, and medical status - work these out with a dietitian/physician,
# never guess. This module surfaces the guidance text only; it does not
# compute calories, macros, or a cut plan for anyone.
# ---------------------------------------------------------------------------
RECOVERY_FUELING_GUIDANCE: List[str] = [
    "Athletes chasing strength and lean mass generally need a caloric surplus on lifting days and enough protein spread across meals to support repair - work with a dietitian for individual targets.",
    "Sleep is a training variable, not an afterthought: most competitive athletes need 7-9 hours, more during high-load blocks.",
    "Hydration and electrolyte management matter most around weight-class sports - build cut plans with qualified medical/nutrition staff, never guess.",
    "Deload weeks are for recovery, not for testing willpower - cut volume, keep a little intensity, and let adaptation catch up.",
]

COACHES_FINAL_WORD = (
    "This is a template library, not a rulebook. The best exercise is the "
    "one that produces the required adaptation with high technical quality, "
    "manageable fatigue, and a clear progression path. Build them strong, "
    "build them explosive, build them resilient - and never let the weight "
    "room take anything away from what happens on the mat."
)


def grappling_playbook_reference(sport: Optional[str] = None, level: Optional[str] = None) -> Dict:
    """Everything in this module, bundled for a single API response - same
    shape as conditioning_protocols.conditioning_reference(). Pass `sport`
    to include that sport's Section 7 supplemental block (None if `sport`
    isn't one of GRAPPLING_SPORTS) and `level` to include that level's
    Section 8 loading grid + Section 9 wave (None if `level` isn't a valid
    LEVELS entry); omit either for the generic reference response, which
    still returns every level/sport-agnostic table.
    """
    return {
        "classification_rule": CLASSIFICATION_RULE,
        "testing_battery": TESTING_BATTERY,
        "testing_battery_note": TESTING_BATTERY_NOTE,
        "relative_strength_targets": RELATIVE_STRENGTH_TARGETS.get(level) if level else RELATIVE_STRENGTH_TARGETS,
        "ramp_warmup": RAMP_WARMUP,
        "ramp_rule": RAMP_RULE,
        "rotational_spectrum": ROTATIONAL_SPECTRUM,
        "autoregulation_status": AUTOREGULATION_STATUS,
        "olympic_ladder": OLYMPIC_LADDER,
        "olympic_ladder_gate_rule": OLYMPIC_LADDER_GATE_RULE,
        "discipline_supplemental_block": discipline_supplemental_block(sport) if sport else None,
        "level_loading": level_loading_table(level) if level else LEVEL_LOADING,
        "grappling_progression_rule": GRAPPLING_PROGRESSION_RULE,
        "pct_1rm_rep_chart": PCT_1RM_REP_CHART,
        "wave_progression": WAVE_PROGRESSION.get(level) if level else WAVE_PROGRESSION,
        "wave_velocity_override_rule": WAVE_VELOCITY_OVERRIDE_RULE,
        "armor_protocols": ARMOR_PROTOCOLS,
        "armor_placement_rule": ARMOR_PLACEMENT_RULE,
        "exercise_selection_matrix": EXERCISE_SELECTION_MATRIX,
        "macrocycle_phases": MACROCYCLE_PHASES,
        "in_season_load_management": IN_SEASON_LOAD_MANAGEMENT,
        "session_cards": SESSION_CARDS,
        "session_card_sequencing_rule": SESSION_CARD_SEQUENCING_RULE,
        "recovery_fueling_guidance": RECOVERY_FUELING_GUIDANCE,
        "coaches_final_word": COACHES_FINAL_WORD,
    }

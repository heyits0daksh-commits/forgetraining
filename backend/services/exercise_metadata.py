"""
exercise_metadata.py — v4.0 metadata enrichment (movement analysis + athletic
quality tags), derived rather than hand-typed.

WHY DERIVED, NOT HAND-AUTHORED:
The v4.0 spec asks for ~15 movement-analysis fields and ~33 athletic-quality
scores (0-100) on every exercise. For 175 exercises that's roughly 8,000
individual numbers. Hand-typing 8,000 numbers in one pass produces numbers
that look precise but aren't actually verified against anything — which is
worse than not having them, because a training engine that silently trusts
fabricated scores makes worse decisions than one that admits it doesn't know.

Instead, this module encodes the judgment ONCE per movement category (a
strength coach's mental model: "vertical pulls build X, cost Y in CNS fatigue,
require Z stability") and then derives each exercise's actual values from
that category baseline plus real signal already present on the exercise
(difficulty, equipment, which joints it stresses, its movement_pattern, its
name). This is the same principle the rest of FORGE already uses — the
metadata endpoint and injury taxonomy are both "derive from what the data
already says" rather than "maintain a second hand-typed copy" — applied to
the new fields.

This is intentionally reviewable: change one row in CATEGORY_PROFILES and
every exercise in that category updates consistently. A future pass can
override individual exercises where a coach disagrees with the category
default, without touching this derivation logic.

USAGE:
    from exercise_metadata import enrich_exercise
    enriched_fields = enrich_exercise(exercise_dict)
    exercise_dict.update(enriched_fields)   # purely additive — no existing
                                             # key is ever read from or
                                             # written to by this module
"""

from typing import Dict, List

# ==========================================================================
# 1. ATHLETIC QUALITY TAGS — full list from the v4.0 spec, section 2, plus
# three v5.1 additions (Wrist/Elbow/Lower Back Stability) so every joint in
# joint_stress's actual 8-tag vocabulary (see injury_taxonomy.py's module
# docstring: Wrist, Elbow, Shoulder, Neck, Lower Back, Hip, Knee, Ankle) has
# a matching stability tag - the original 5 (Shoulder/Hip/Knee/Ankle/Neck)
# silently left Wrist, Elbow, and Lower Back with no stability tag at all,
# which meant no exercise could ever be a rehab candidate for an injury on
# those three joints (JOINT_STABILITY_TAG.get(joint) returned None ->
# is_rehab_candidate short-circuited to False) and knowledge_graph.py's
# joint nodes silently omitted them (see that module's fix).
# ==========================================================================
ATHLETIC_QUALITY_TAGS: List[str] = [
    "Max Strength", "Relative Strength", "Hypertrophy", "Muscular Endurance",
    "Power", "Explosiveness", "Acceleration", "Deceleration", "Top Speed",
    "Agility", "Change of Direction", "Reactive Strength", "Elastic Strength",
    "Rate of Force Development", "Grip Strength", "Grip Endurance",
    "Core Stability", "Anti Rotation", "Anti Extension", "Anti Flexion",
    "Anti Lateral Flexion", "Rotational Power", "Shoulder Stability",
    "Hip Stability", "Knee Stability", "Ankle Stability", "Neck Strength",
    "Wrist Stability", "Elbow Stability", "Lower Back Stability",
    "Conditioning", "Work Capacity", "VO2", "Anaerobic Capacity",
    "Aerobic Capacity", "Recovery",
]

# ==========================================================================
# 2. CATEGORY BASELINES
# ==========================================================================
# One row per exercises.json `category` value. Every score is 0-100 unless
# noted. Categories not listed fall back to _DEFAULT_PROFILE.
#
# "Recovery" here means "how much this movement itself doubles as active
# recovery" (low-difficulty mobility work scores high; max-effort barbell
# work scores near zero) — not to be confused with recovery_time_hours below,
# which is how long the body needs *after* the exercise.
CATEGORY_PROFILES: Dict[str, Dict] = {
    "Horizontal Push": dict(
        plane="Sagittal", chain="Closed Chain", force="Concentric",
        stability=45, balance=25, coordination=35, mobility=30,
        tags=dict(**{
            "Max Strength": 55, "Relative Strength": 65, "Hypertrophy": 60,
            "Muscular Endurance": 45, "Power": 35, "Explosiveness": 25,
            "Core Stability": 40, "Anti Extension": 35,
            "Shoulder Stability": 40, "Grip Strength": 15,
        }),
    ),
    "Vertical Push": dict(
        plane="Sagittal", chain="Open Chain", force="Concentric",
        stability=65, balance=40, coordination=45, mobility=45,
        tags=dict(**{
            "Max Strength": 55, "Relative Strength": 60, "Hypertrophy": 55,
            "Power": 35, "Core Stability": 45, "Anti Extension": 30,
            "Shoulder Stability": 60, "Neck Strength": 25, "Grip Strength": 20,
        }),
    ),
    "Horizontal Pull": dict(
        plane="Sagittal", chain="Open Chain", force="Concentric",
        stability=40, balance=25, coordination=35, mobility=25,
        tags=dict(**{
            "Max Strength": 55, "Relative Strength": 55, "Hypertrophy": 55,
            "Muscular Endurance": 45, "Grip Strength": 40, "Grip Endurance": 35,
            "Core Stability": 30, "Shoulder Stability": 35,
        }),
    ),
    "Vertical Pull": dict(
        plane="Sagittal", chain="Open Chain", force="Concentric",
        stability=50, balance=25, coordination=40, mobility=35,
        tags=dict(**{
            "Max Strength": 55, "Relative Strength": 65, "Hypertrophy": 55,
            "Muscular Endurance": 45, "Grip Strength": 55, "Grip Endurance": 45,
            "Core Stability": 35, "Shoulder Stability": 45,
        }),
    ),
    "Squat": dict(
        plane="Sagittal", chain="Closed Chain", force="Concentric",
        stability=45, balance=35, coordination=30, mobility=45,
        tags=dict(**{
            "Max Strength": 65, "Relative Strength": 60, "Hypertrophy": 60,
            "Muscular Endurance": 40, "Power": 40, "Knee Stability": 45,
            "Hip Stability": 40, "Core Stability": 35,
        }),
    ),
    "Hinge": dict(
        plane="Sagittal", chain="Closed Chain", force="Concentric",
        stability=45, balance=30, coordination=35, mobility=40,
        tags=dict(**{
            "Max Strength": 70, "Relative Strength": 60, "Hypertrophy": 55,
            "Power": 45, "Rate of Force Development": 30, "Hip Stability": 50,
            "Grip Strength": 35, "Core Stability": 40, "Anti Flexion": 35,
        }),
    ),
    "Core": dict(
        plane="Multi-planar", chain="Hybrid", force="Isometric",
        stability=65, balance=40, coordination=35, mobility=25,
        tags=dict(**{
            "Core Stability": 75, "Anti Rotation": 30, "Anti Extension": 30,
            "Anti Flexion": 30, "Anti Lateral Flexion": 30,
            "Muscular Endurance": 45, "Hip Stability": 25,
        }),
    ),
    "Full Body": dict(
        plane="Multi-planar", chain="Hybrid", force="Stretch-Shortening Cycle",
        stability=55, balance=45, coordination=55, mobility=35,
        tags=dict(**{
            "Power": 55, "Explosiveness": 45, "Rate of Force Development": 40,
            "Work Capacity": 50, "Conditioning": 45, "Core Stability": 40,
            "Grip Strength": 35, "Anaerobic Capacity": 40,
        }),
    ),
    "Carry": dict(
        plane="Sagittal", chain="Closed Chain", force="Isometric",
        stability=55, balance=40, coordination=30, mobility=20,
        tags=dict(**{
            "Grip Strength": 65, "Grip Endurance": 70, "Core Stability": 55,
            "Anti Lateral Flexion": 40, "Work Capacity": 55,
            "Muscular Endurance": 50, "Conditioning": 40,
        }),
    ),
    "Grip": dict(
        plane="Sagittal", chain="Open Chain", force="Isometric",
        stability=35, balance=15, coordination=20, mobility=15,
        tags=dict(**{
            "Grip Strength": 75, "Grip Endurance": 60, "Muscular Endurance": 30,
        }),
    ),
    "Jump": dict(
        plane="Sagittal", chain="Closed Chain", force="Stretch-Shortening Cycle",
        stability=40, balance=45, coordination=55, mobility=30,
        tags=dict(**{
            "Power": 70, "Explosiveness": 65, "Reactive Strength": 60,
            "Elastic Strength": 55, "Rate of Force Development": 55,
            "Acceleration": 40, "Knee Stability": 30, "Ankle Stability": 35,
        }),
    ),
    "Power": dict(
        plane="Multi-planar", chain="Closed Chain", force="Stretch-Shortening Cycle",
        stability=45, balance=40, coordination=55, mobility=30,
        tags=dict(**{
            "Power": 75, "Explosiveness": 65, "Rate of Force Development": 60,
            "Acceleration": 40, "Hip Stability": 30,
        }),
    ),
    "Conditioning": dict(
        plane="Multi-planar", chain="Hybrid", force="Concentric",
        stability=25, balance=20, coordination=30, mobility=20,
        tags=dict(**{
            "Conditioning": 75, "Work Capacity": 70, "VO2": 60,
            "Anaerobic Capacity": 55, "Aerobic Capacity": 50,
            "Muscular Endurance": 45,
        }),
    ),
    "Sport Specific": dict(
        plane="Multi-planar", chain="Hybrid", force="Stretch-Shortening Cycle",
        stability=50, balance=45, coordination=60, mobility=35,
        tags=dict(**{
            "Agility": 45, "Change of Direction": 40, "Power": 40,
            "Reactive Strength": 35, "Core Stability": 35,
        }),
    ),
}

_DEFAULT_PROFILE = dict(
    plane="Sagittal", chain="Hybrid", force="Concentric",
    stability=35, balance=30, coordination=30, mobility=30,
    tags={},
)

# All tags default to this floor before category/exercise adjustments, so
# every exercise reports a full, consistent tag set rather than sparse zeros.
_TAG_FLOOR = 10


# ==========================================================================
# 3. PER-EXERCISE MODIFIERS
# ==========================================================================
# Small, explainable nudges on top of the category baseline, driven by real
# fields already on the exercise — not invented per exercise.

_UNILATERAL_MARKERS = ("single", "one-arm", "one arm", "pistol", "bulgarian", "archer", "uneven")
_ALTERNATING_MARKERS = ("alternating", "walking lunge", "farmer")


# ==========================================================================
# EQUIPMENT CATALOG — groups exercises.json's ~65 raw `equipment` strings
# into the buckets a person actually shops/thinks in (Free Weights, Machines,
# Strongman, etc.), so the equipment browser can show "Free Weights" as a
# section instead of one un-grouped alphabetical checkbox list. Any
# equipment string found in the data but not listed here falls into "Other"
# automatically (build_equipment_catalog below) rather than silently
# disappearing - so this list drifting behind new exercises.json entries
# degrades gracefully instead of hiding equipment from the browser.
# ==========================================================================
EQUIPMENT_CATEGORIES: Dict[str, List[str]] = {
    "Bodyweight": ["Bodyweight", "Suspension Trainer", "Rings", "Parallel Bars", "Pull-up Bar"],
    "Free Weights": [
        "Barbell", "Dumbbell", "Kettlebell", "EZ Curl Bar", "Trap Bar",
        "Safety Squat Bar", "Cambered Bar", "Swiss Bar", "Buffalo Bar",
        "Log Bar", "Axle Bar", "Landmine", "Medicine Ball",
    ],
    "Machines": [
        "Cable Machine", "Lat Pulldown Machine", "Leg Press Machine",
        "Leg Curl Machine", "Leg Extension Machine", "Chest Press Machine",
        "Shoulder Press Machine", "Seated Row Machine", "High Row Machine",
        "Pec Deck Machine", "Hack Squat Machine", "Smith Machine",
        "Pendulum Squat Machine", "V Squat Machine", "Belt Squat Machine",
        "Plate-Loaded Lever Machine", "Calf Raise Machine", "Ab Crunch Machine",
        "Preacher Curl Machine", "Triceps Dip Machine", "Hip Thrust Machine",
        "Assisted Pull-up Machine",
    ],
    "Racks & Benches": [
        "Power Rack", "Squat Rack", "Hyperextension Bench", "Seal Row Bench",
        "GHD", "Captain's Chair", "Reverse Hyper", "Belt Squat",
        "Adjustable Bench", "Sit-Up Bench",
    ],
    "Strongman": [
        "Atlas Stone", "Husafell Stone", "Conan's Wheel", "Yoke", "Sled",
        "Tire", "Keg", "Sandbag", "Farmer Handles", "Fingal's Fingers", "Log Bar",
    ],
    "Conditioning": [
        "Assault Bike", "Rowing Erg", "Jump Rope", "Battle Ropes",
        "Agility Ladder", "Plyo Box", "Weighted Vest",
    ],
    "Grip & Accessory": ["Ab Wheel", "Resistance Band", "Climbing Hangboard"],
    "Combat Sport": ["Boxing Heavy Bag", "Tackle Bag", "Wrestling Dummy"],
    # v5.8 (batch7): dedicated rehab/prehab equipment - previously had no
    # entries in the database at all, which was part of why the Neck joint
    # had zero rehab-candidate exercises (see generate_batch7_equipment_rehab.py).
    "Rehab & Mobility": ["Neck Harness", "Balance Board"],
}

_EQUIPMENT_TO_CATEGORY: Dict[str, str] = {
    eq: cat for cat, items in EQUIPMENT_CATEGORIES.items() for eq in items
}


def build_equipment_catalog(exercises: List[Dict]) -> List[Dict]:
    """One row per equipment type actually present in the database: which
    shopping/gym-area category it belongs to, how many exercises it
    unlocks, and which movement categories those exercises cover - e.g. a
    Kettlebell row showing categories=['Horizontal Push','Hinge','Squat',
    'Carry','Core',...] is the concrete answer to "kettlebell should cover
    everything, not just swings" - a person can see, before picking it,
    that it actually does. Grouped by EQUIPMENT_CATEGORIES section so the
    browser can render sections instead of one flat alphabetical list."""
    by_equipment: Dict[str, Dict] = {}
    for ex in exercises:
        eq = ex.get("equipment", "Bodyweight")
        entry = by_equipment.setdefault(eq, {"count": 0, "categories": set(), "sports": set()})
        entry["count"] += 1
        if ex.get("category"):
            entry["categories"].add(ex["category"])
        entry["sports"].update(ex.get("sport_priority", {}).keys())

    rows = []
    for eq, info in by_equipment.items():
        rows.append({
            "equipment": eq,
            "group": _EQUIPMENT_TO_CATEGORY.get(eq, "Other"),
            "exercise_count": info["count"],
            "movement_categories": sorted(info["categories"]),
            # A rough "how much of the movement library does this equipment
            # alone cover" signal - 8 is the number of loaded-strength +
            # carry/core categories in the database (see main.py's
            # _LOADED_STRENGTH_CATEGORIES plus Carry/Core).
            "pattern_coverage": len(info["categories"]),
        })
    rows.sort(key=lambda r: (r["group"], -r["exercise_count"]))
    return rows


def _movement_type(ex: Dict) -> str:
    name = ex.get("name", "").lower()
    pattern = (ex.get("movement_pattern") or "").lower()
    if any(m in name for m in _ALTERNATING_MARKERS):
        return "Alternating"
    if any(m in name for m in _UNILATERAL_MARKERS):
        return "Unilateral"
    if "carry" in pattern or ex.get("category") == "Carry":
        return "Bilateral"
    return "Bilateral"


def _movement_plane(ex: Dict, base_plane: str) -> str:
    pattern = (ex.get("movement_pattern") or "").lower()
    name = (ex.get("name") or "").lower()
    if "rotat" in pattern or "rotat" in name or "chop" in name or "twist" in name:
        return "Transverse"
    if "lunge" in pattern or "lateral" in name:
        return "Frontal"
    if pattern in ("complex", "ballistic") or ex.get("category") in ("Full Body", "Sport Specific"):
        return "Multi-planar"
    return base_plane


def _force_type(ex: Dict, base_force: str) -> str:
    pattern = (ex.get("movement_pattern") or "")
    if pattern == "Isometric":
        return "Isometric"
    if pattern in ("Ballistic", "Explosive Pull", "Jump", "Throw"):
        return "Stretch-Shortening Cycle"
    return base_force


def _velocity_type(ex: Dict) -> str:
    pattern = (ex.get("movement_pattern") or "")
    difficulty = ex.get("difficulty", 1)
    if pattern in ("Jump", "Throw", "Ballistic"):
        return "Reactive"
    if pattern == "Explosive Pull":
        return "Explosive"
    if ex.get("category") in ("Conditioning",):
        return "Speed Strength"
    if difficulty >= 4 and ex.get("equipment") in ("Barbell", "Trap Bar", "Power Rack"):
        return "Max Strength"
    return "Slow Strength"


def _chain_type(ex: Dict, base_chain: str) -> str:
    pattern = (ex.get("movement_pattern") or "")
    if pattern in ("Throw", "Ballistic") or ex.get("equipment") in ("Medicine Ball", "Battle Ropes"):
        return "Open Chain"
    return base_chain


# ==========================================================================
# TISSUE-DEMAND PROFILE (Phase 19) — reads an exercise's *existing* v4.0
# movement-analysis fields (movement_plane, movement_type, chain_type,
# force_type, velocity_type, stability/balance/mobility_requirement) into a
# set of named biomechanical-demand flags: compression, shear, rotation,
# frontal-plane (valgus/varus-relevant) loading, impact, velocity, ROM,
# eccentric loading, unilateral loading, instability.
#
# WHY THIS EXISTS: injury_taxonomy.classify_injury_risk() previously only
# ever saw two numbers - injury severity and exercise difficulty - so two
# exercises stressing the same joint at the same difficulty (e.g. a heavy
# closed-chain Back Squat vs. a fast open-chain Leg Extension kick) were
# indistinguishable to the risk model even though they load the joint very
# differently. This function is the missing link: every value it reads
# already exists on every exercise (nothing here is invented or newly
# authored per-exercise), it's just never been read for injury purposes.
#
# This returns *exercise-level* demand flags, not joint-specific ones -
# consistent with how joint_stress/difficulty are already exercise-level
# in this codebase. classify_injury_risk() pairs a joint's injury (via its
# `tissue` field, see injury_taxonomy.TISSUE_DEMAND_SENSITIVITY) against
# this profile.
# ==========================================================================
def derive_tissue_demands(ex: Dict) -> Dict[str, bool]:
    """Pure, derived-only tissue-demand profile for one exercise. Every flag
    is computed from fields enrich_exercise() already produces - no new data
    is authored here, so this is safe to call at request time on any
    already-enriched exercise without touching exercises.json."""
    chain_type = ex.get("chain_type")
    movement_plane = ex.get("movement_plane")
    movement_type = ex.get("movement_type")
    force_type = ex.get("force_type")
    velocity_type = ex.get("velocity_type")
    stability = ex.get("stability_requirement", 0) or 0
    balance = ex.get("balance_requirement", 0) or 0
    mobility = ex.get("mobility_requirement", 0) or 0

    return {
        # Closed-chain (foot/hand fixed against a surface) loading drives
        # axial/joint-surface compression; open-chain loading (e.g. a leg
        # extension) isolates the limb and produces relatively more shear
        # at the joint for the same resistance - the same open- vs.
        # closed-chain distinction real ACL-rehab protocols use.
        "high_compression": chain_type == "Closed Chain",
        "high_shear": chain_type == "Open Chain",
        # Transverse-plane movement is rotation about the joint's long axis.
        "high_rotation": movement_plane == "Transverse",
        # Frontal-plane loading of a lower-limb joint (lateral lunges,
        # lateral bounds, cutting) is exactly what produces valgus/varus
        # stress at that joint.
        "frontal_plane_loading": movement_plane == "Frontal",
        # Reactive (jump/throw/ballistic-pattern) exercises involve rapid
        # force absorption on landing/catching - the closest existing proxy
        # for impact loading.
        "high_impact": velocity_type == "Reactive",
        "high_velocity": velocity_type in ("Reactive", "Explosive", "Speed Strength"),
        # Range-of-motion demand already exists as a 0-100 score.
        "large_rom_demand": mobility >= 60,
        # Stretch-Shortening Cycle movements load the tissue eccentrically
        # (the stretch phase) immediately before the concentric phase -
        # the defining feature of plyometric/reactive loading.
        "high_eccentric": force_type == "Stretch-Shortening Cycle",
        "unilateral_loading": movement_type in ("Unilateral", "Alternating"),
        "high_instability": max(stability, balance) >= 60,
    }


# Public (not underscore-prefixed): knowledge_graph.py imports this directly
# instead of keeping its own copy, so the two modules can't drift out of sync
# the way they previously did (that drift was the root cause of the joint-
# node/rehab-candidacy gap on Wrist/Elbow/Lower Back - see the
# ATHLETIC_QUALITY_TAGS comment above). All 8 joints exercises.json actually
# carries in joint_stress are covered now, not just the original 5.
JOINT_STABILITY_TAG = {
    "Shoulder": "Shoulder Stability",
    "Hip": "Hip Stability",
    "Knee": "Knee Stability",
    "Ankle": "Ankle Stability",
    "Neck": "Neck Strength",
    "Wrist": "Wrist Stability",
    "Elbow": "Elbow Stability",
    "Lower Back": "Lower Back Stability",
}

_GRIP_EQUIPMENT = {"Barbell", "Kettlebell", "Pull-up Bar", "Rings", "Farmer Handles",
                    "Trap Bar", "Climbing Hangboard", "Battle Ropes"}


def enrich_exercise(ex: Dict) -> Dict:
    """Return the v4.0 additive fields for one exercise. Never reads intent
    to overwrite an existing key — caller decides how to merge, and every
    field returned here is new in v4.0 (see the ABSOLUTE RULES the upgrade
    prompt itself sets: don't remove or rename existing fields)."""
    category = ex.get("category")
    profile = CATEGORY_PROFILES.get(category, _DEFAULT_PROFILE)
    difficulty = ex.get("difficulty", 1)
    equipment = ex.get("equipment", "Bodyweight")
    joint_stress = ex.get("joint_stress", [])

    # ---- movement analysis ----
    movement_plane = _movement_plane(ex, profile["plane"])
    movement_type = _movement_type(ex)
    chain_type = _chain_type(ex, profile["chain"])
    force_type = _force_type(ex, profile["force"])
    velocity_type = _velocity_type(ex)

    # Instability equipment (rings, kettlebells, single-limb work) bumps the
    # stabilizer-demand fields; nothing here is invented from scratch, it's a
    # fixed +/- nudge off the category baseline.
    instability_bonus = 15 if equipment in ("Rings", "Kettlebell") else 0
    instability_bonus += 10 if movement_type in ("Unilateral", "Alternating") else 0

    stability_requirement = min(100, profile["stability"] + instability_bonus + difficulty * 3)
    balance_requirement = min(100, profile["balance"] + instability_bonus + difficulty * 2)
    coordination_requirement = min(100, profile["coordination"] + (10 if force_type == "Stretch-Shortening Cycle" else 0) + difficulty * 3)
    mobility_requirement = min(100, profile["mobility"] + difficulty * 2)

    technical_complexity = max(1, min(5, round(difficulty * 0.8 + (1 if force_type == "Stretch-Shortening Cycle" else 0))))
    learning_curve = max(1, min(5, round(technical_complexity * 0.9 + (1 if equipment in ("Rings", "Barbell") else 0))))
    skill_requirement = max(1, min(5, round((technical_complexity + learning_curve) / 2)))

    cns_load_equipment = equipment in ("Barbell", "Trap Bar", "Power Rack", "Rings")
    CNS_fatigue = min(100, difficulty * 15 + (15 if force_type == "Stretch-Shortening Cycle" else 0) + (10 if cns_load_equipment else 0))
    fatigue_cost = min(100, difficulty * 14 + (10 if category in ("Conditioning", "Full Body", "Carry") else 0))
    recovery_time_hours = round(12 + CNS_fatigue * 0.6)

    # ---- athletic quality tags ----
    tags = {t: _TAG_FLOOR for t in ATHLETIC_QUALITY_TAGS}
    tags.update(profile.get("tags", {}))

    # Difficulty scales strength/power-adjacent qualities but not conditioning
    # qualities (a hard set of 5 heavy squats isn't "more conditioning").
    strength_adjacent = (
        "Max Strength", "Relative Strength", "Hypertrophy", "Power",
        "Explosiveness", "Rate of Force Development",
    )
    for t in strength_adjacent:
        if t in tags and tags[t] > _TAG_FLOOR:
            tags[t] = min(100, round(tags[t] + (difficulty - 3) * 5))

    # Joint-stressed = joint-trained: an exercise that stresses the shoulder
    # is, by definition, building shoulder stability under load.
    for joint in joint_stress:
        tag = JOINT_STABILITY_TAG.get(joint)
        if tag:
            tags[tag] = min(100, max(tags.get(tag, _TAG_FLOOR), 30 + difficulty * 8))

    if equipment in _GRIP_EQUIPMENT:
        tags["Grip Strength"] = min(100, max(tags["Grip Strength"], 35 + difficulty * 5))
        tags["Grip Endurance"] = min(100, max(tags["Grip Endurance"], 25 + difficulty * 4))

    if movement_type == "Unilateral":
        tags["Agility"] = min(100, tags.get("Agility", _TAG_FLOOR) + 10)
        tags["Change of Direction"] = min(100, tags.get("Change of Direction", _TAG_FLOOR) + 5)

    if movement_plane == "Transverse":
        tags["Rotational Power"] = min(100, max(tags.get("Rotational Power", _TAG_FLOOR), 35 + difficulty * 8))
        tags["Anti Rotation"] = min(100, max(tags.get("Anti Rotation", _TAG_FLOOR), 30 + difficulty * 6))

    if force_type == "Isometric":
        tags["Muscular Endurance"] = min(100, tags.get("Muscular Endurance", _TAG_FLOOR) + 10)

    if force_type == "Stretch-Shortening Cycle":
        tags["Reactive Strength"] = min(100, max(tags.get("Reactive Strength", _TAG_FLOOR), 35 + difficulty * 8))
        tags["Elastic Strength"] = min(100, max(tags.get("Elastic Strength", _TAG_FLOOR), 30 + difficulty * 7))

    # "Recovery" tag = how much this movement doubles as active recovery for
    # the athlete, which is the inverse of how taxing it is.
    tags["Recovery"] = max(0, 100 - CNS_fatigue - fatigue_cost // 2)

    return {
        "movement_plane": movement_plane,
        "movement_type": movement_type,
        "chain_type": chain_type,
        "force_type": force_type,
        "velocity_type": velocity_type,
        "stability_requirement": stability_requirement,
        "balance_requirement": balance_requirement,
        "coordination_requirement": coordination_requirement,
        "mobility_requirement": mobility_requirement,
        "technical_complexity": technical_complexity,
        "learning_curve": learning_curve,
        "skill_requirement": skill_requirement,
        "fatigue_cost": fatigue_cost,
        "CNS_fatigue": CNS_fatigue,
        "recovery_time_hours": recovery_time_hours,
        "athletic_qualities": tags,
    }


# ==========================================================================
# 6. GROUPING TAXONOMY (v5.18) — is_compound, is_olympic_lift, push_pull,
# upper_lower, chain_emphasis. Requested so the library/session builder can
# filter or group by these five axes directly instead of the caller
# re-deriving them ad hoc. Same rule as everything above: every value is
# derived from fields the exercise already carries (name, category,
# movement_pattern, primary/secondary_muscles, joint_stress) — nothing
# hand-typed per exercise.
# ==========================================================================

# `category` alone can't tell compound from isolation — e.g. "Standing
# Barbell Curl" and "Cable Tricep Pushdown" both live under Vertical Pull /
# Vertical Push in this schema, next to genuinely multi-joint lifts in the
# same category. So compound/isolation is decided by (a) known isolation
# movement names, with (b) a muscle/joint-count fallback for the handful of
# isolation movements that don't match any keyword (skullcrushers, decline
# crunch, isometric quad sets) — a classic isolation signature is exactly
# one primary muscle, no secondary muscles, no stabilizers engaged.
_ISOLATION_KEYWORDS = (
    "curl", "extension", "fly", "flye", "kickback", "pushdown",
    "shrug", "pec deck", "lateral raise", "front raise", "calf raise",
    "rear delt raise",
)


def _is_isolation(ex: Dict) -> bool:
    name = ex.get("name", "").lower()
    if any(k in name for k in _ISOLATION_KEYWORDS):
        return True
    return (
        len(ex.get("primary_muscles", [])) <= 1
        and not ex.get("secondary_muscles")
        and not ex.get("stabilizers")
    )


# Grip/press/pull variants of the barbell "Clean" and "Snatch" competition
# lifts (and their standard training derivatives — hang/power/block/tall/
# muscle/split/squat receiving positions, high pulls, jerks) count as
# Olympic lifts. Exercises that only borrow the clean/snatch hand grip on an
# otherwise ordinary squat/deadlift/RDL do not — they're accessory strength
# work, not the competition movement.
_OLYMPIC_LIFT_KEYWORDS = ("clean", "snatch", "jerk")
_OLYMPIC_LIFT_EXCLUDE_NAMES = {
    "Snatch-Grip Deadlift", "Snatch Grip Romanian Deadlift",
    "Clean Grip Front Squat", "Clean Grip Deadlift", "Clean Deadlift",
}


def _is_olympic_lift(ex: Dict) -> bool:
    name = ex.get("name", "")
    if name in _OLYMPIC_LIFT_EXCLUDE_NAMES:
        return False
    return any(k in name.lower() for k in _OLYMPIC_LIFT_KEYWORDS)


# push_pull only fires for exercises whose movement_pattern IS a push or a
# pull — squats/hinges/carries/etc. are correctly neither, so the field is
# nullable rather than forced into one bucket.
def _push_pull(ex: Dict):
    pattern = ex.get("movement_pattern")
    if pattern == "Push":
        return "Push"
    if pattern in ("Pull", "Explosive Pull"):
        return "Pull"
    return None


# category is the primary signal (it's already movement-direction-specific
# for the single-joint-direction categories); the five categories that mix
# push/pull/squat/carry work under one label (Full Body, Power, Carry,
# Conditioning, Sport Specific) fall through to movement_pattern instead.
_CATEGORY_UPPER_LOWER = {
    "Horizontal Push": "Upper", "Vertical Push": "Upper",
    "Horizontal Pull": "Upper", "Vertical Pull": "Upper",
    "Grip": "Upper", "Pull": "Upper",
    "Squat": "Lower", "Hinge": "Lower", "Calf Raise": "Lower", "Jump": "Lower",
    "Core": "Core", "Rotational": "Core",
}
_PATTERN_UPPER_LOWER = {
    "Push": "Upper", "Pull": "Upper", "Hang": "Upper",
    # Explosive Pull = the clean/snatch pull off the floor - triple
    # extension driven by the hips/legs, not an arm pull - so it's Full
    # Body, not Upper, despite the "Pull" name.
    "Explosive Pull": "Full Body",
    "Squat": "Lower", "Hinge": "Lower", "Lunge": "Lower", "Jump": "Lower",
    "Sprint": "Lower", "Shuttle Run": "Lower", "Lateral": "Lower", "Agility": "Lower",
    "Rotational": "Core", "Rotation": "Core", "Anti-Rotation": "Core",
    "Anti-Extension": "Core", "Flexion": "Core", "Extension": "Core",
}


def _upper_lower(ex: Dict) -> str:
    category = ex.get("category")
    if category in _CATEGORY_UPPER_LOWER:
        return _CATEGORY_UPPER_LOWER[category]
    # heterogeneous category -> defer to the specific movement pattern
    return _PATTERN_UPPER_LOWER.get(ex.get("movement_pattern"), "Full Body")


# Classic S&C "chain" framing: posterior chain (glutes, hamstrings, spinal
# erectors, lats/traps/rear delts, calves) vs. anterior chain (quads, hip
# flexors, abs, chest, front delts, biceps). Muscles with no clear side
# (rotator cuff, generic "forearms", stabilizer-only tags) are left out of
# the count rather than guessed. Weighted 2x for primary muscles vs. 1x for
# secondary so the prime mover decides close calls; a >=1.3x lean either way
# calls it, otherwise "Mixed" (true of most Full Body / Carry / Conditioning
# work, which is the honest answer for those).
_POSTERIOR_CHAIN = {
    "Gluteus Maximus", "Gluteus Medius", "Gluteus Minimus", "Glutes",
    "Hamstrings", "Erector Spinae", "Latissimus Dorsi", "Lats",
    "Trapezius", "Upper Trapezius", "Traps", "Rhomboids",
    "Rear Deltoid", "Posterior Deltoid", "Calves", "Gastrocnemius",
    "Soleus", "Neck Extensors", "Lower Back",
}
_ANTERIOR_CHAIN = {
    "Quadriceps", "Anterior Deltoid", "Pectoralis Major", "Biceps Brachii",
    "Rectus Abdominis", "Obliques", "Core", "Hip Flexors",
    "Forearm Flexors", "Transverse Abdominis", "Tibialis Anterior",
    "Sternocleidomastoid", "Neck Flexors", "Serratus Anterior",
}


def _chain_emphasis(ex: Dict) -> str:
    posterior = 0
    anterior = 0
    for m in ex.get("primary_muscles", []):
        if m in _POSTERIOR_CHAIN:
            posterior += 2
        elif m in _ANTERIOR_CHAIN:
            anterior += 2
    for m in ex.get("secondary_muscles", []):
        if m in _POSTERIOR_CHAIN:
            posterior += 1
        elif m in _ANTERIOR_CHAIN:
            anterior += 1
    if posterior == 0 and anterior == 0:
        return "Mixed"
    if posterior >= anterior * 1.3 and posterior > anterior:
        return "Posterior"
    if anterior >= posterior * 1.3 and anterior > posterior:
        return "Anterior"
    return "Mixed"


def derive_taxonomy_groups(ex: Dict) -> Dict:
    """Return the v5.18 additive grouping fields for one exercise. Same
    additive contract as enrich_exercise(): never reads or overwrites an
    existing key."""
    return {
        "is_compound": not _is_isolation(ex),
        "is_olympic_lift": _is_olympic_lift(ex),
        "push_pull": _push_pull(ex),
        "upper_lower": _upper_lower(ex),
        "chain_emphasis": _chain_emphasis(ex),
    }


# ==========================================================================
# 7. CONNECTIVE-TISSUE & PHASE BIOMECHANICS (v5.19) — which tendon/ligament
# is loaded at each stressed joint, in which phase of the rep, plus a
# generated prose explanation. This is exercise-specific (not just a static
# per-joint anatomy list) because it's built from signal that already varies
# exercise-to-exercise: joint_stress (which joints), derive_tissue_demands()
# (the Phase 19 compression/shear/rotation/frontal-plane/impact flags this
# module already computes from chain_type/movement_plane/velocity_type), and
# push_pull (which prime-mover tendon is under tension).
#
# TENDONS load every rep an exercise's joint is stressed - that's just where
# muscle force transmits to bone, so a tendon entry is unconditional once its
# joint is in joint_stress. LIGAMENTS only resist a specific unwanted
# motion (anterior shear, valgus collapse, inversion, excessive rotation) -
# they're listed ONLY when a tissue-demand flag that actually implies that
# motion is present for THIS exercise, e.g. a Back Squat (closed-chain,
# sagittal, bilateral) does not get an ACL entry, but a Single-Leg Box Jump
# (open/hybrid chain, unilateral, high_impact) does. This mirrors how PTs
# actually reason about ligament risk - by loading mechanism, not by "the
# knee is involved so list every knee ligament every time."
#
# Anatomy is standard gross-anatomy fact (which tendon/ligament crosses which
# joint, what each ligament resists) - not fabricated. What's derived per
# exercise is WHICH of those already-known structures apply here and in what
# phase, from data the exercise already carries.
# ==========================================================================
CONNECTIVE_TISSUE_BY_JOINT: Dict[str, Dict] = {
    "Shoulder": dict(
        tendon_push="Pectoralis Major tendon, Anterior Deltoid tendon",
        tendon_pull="Latissimus Dorsi tendon, Teres Major tendon",
        tendon_default="Deltoid tendon",
        stabilizer_tendon="Rotator cuff tendons (supraspinatus, infraspinatus, subscapularis)",
        ligament="Glenohumeral ligaments (anterior band)",
        ligament_mechanism="resist anterior humeral-head translation when the shoulder is loaded in an unstable, open-chain, or end-range externally-rotated position",
        trigger=lambda t: t["high_shear"] or t["high_instability"],
    ),
    "Elbow": dict(
        tendon_push="Triceps Brachii tendon",
        tendon_pull="Biceps Brachii tendon (distal)",
        tendon_default="Biceps/Triceps tendon (elbow flexor-extensor)",
        stabilizer_tendon="Common flexor/extensor tendon (forearm origin at the epicondyles)",
        ligament="Ulnar Collateral Ligament (UCL)",
        ligament_mechanism="resists valgus stress when the elbow is loaded fast or eccentrically",
        trigger=lambda t: t["high_velocity"] or t["high_eccentric"],
    ),
    "Wrist": dict(
        tendon_default="Flexor carpi radialis/ulnaris tendons",
        stabilizer_tendon="Extensor carpi tendons",
        ligament="Triangular Fibrocartilage Complex (TFCC) / Scapholunate ligament",
        ligament_mechanism="absorbs compressive load through an extended, weight-bearing wrist",
        trigger=lambda t: t["high_compression"],
    ),
    "Hip": dict(
        tendon_push="Gluteal tendons (gluteus maximus insertion)",
        tendon_pull="Iliopsoas tendon (hip flexor)",
        tendon_default="Hamstring proximal tendon / Gluteal tendon",
        stabilizer_tendon="Adductor tendons",
        ligament="Iliofemoral Ligament",
        ligament_mechanism="limits hip extension range and stabilizes the femoral head at end-range or frontal-plane loading",
        trigger=lambda t: t["large_rom_demand"] or t["frontal_plane_loading"],
    ),
    "Knee": dict(
        tendon_default="Patellar tendon (quadriceps force transmission)",
        stabilizer_tendon="Hamstring distal tendons",
        ligament="Anterior Cruciate Ligament (ACL)",
        ligament_mechanism="resists anterior tibial translation during deceleration, single-leg loading, or impact absorption",
        trigger=lambda t: t["high_shear"] or t["high_impact"] or t["unilateral_loading"],
        ligament2="Medial Collateral Ligament (MCL)",
        ligament2_mechanism="resists inward (valgus) knee collapse under frontal-plane loading",
        trigger2=lambda t: t["frontal_plane_loading"],
    ),
    "Ankle": dict(
        tendon_default="Achilles tendon (gastrocnemius-soleus)",
        stabilizer_tendon="Peroneal tendons",
        ligament="Anterior Talofibular Ligament (ATFL)",
        ligament_mechanism="resists inversion/rolling under impact, frontal-plane, or single-leg loading",
        trigger=lambda t: t["high_impact"] or t["frontal_plane_loading"] or t["unilateral_loading"],
    ),
    "Lower Back": dict(
        tendon_default="Erector Spinae tendinous attachments / thoracolumbar fascia",
        stabilizer_tendon=None,
        ligament="Posterior Longitudinal Ligament / Iliolumbar Ligament",
        ligament_mechanism="resists excessive spinal flexion/shear under large range-of-motion or open-chain low-back loading",
        trigger=lambda t: t["large_rom_demand"] or t["high_shear"],
    ),
    "Neck": dict(
        tendon_default="Sternocleidomastoid / Neck extensor tendons",
        stabilizer_tendon=None,
        ligament="Nuchal Ligament",
        ligament_mechanism="resists sudden flexion/whiplash-type loading under impact",
        trigger=lambda t: t["high_impact"],
    ),
}


def _phase_label(force_type: str, category: str) -> str:
    if force_type == "Isometric":
        return "Isometric Hold (Loaded Carry)" if category == "Carry" else "Isometric Hold"
    if force_type == "Stretch-Shortening Cycle":
        return "Eccentric Preload -> Concentric Drive (SSC)"
    return "Eccentric (lowering) -> Concentric (lifting)"


def _muscle_action_by_phase(ex: Dict) -> Dict:
    primary = ex.get("primary_muscles", [])
    secondary = ex.get("secondary_muscles", [])
    stabilizers = ex.get("stabilizers", [])
    force_type = ex.get("force_type")

    if force_type == "Isometric":
        return {"Isometric Hold": {"prime_movers": primary, "synergists": secondary, "stabilizers": stabilizers}}
    if force_type == "Stretch-Shortening Cycle":
        return {
            "Eccentric Preload": {"prime_movers": primary, "synergists": secondary, "stabilizers": stabilizers},
            "Concentric Drive": {"prime_movers": primary, "synergists": secondary, "stabilizers": stabilizers},
        }
    return {
        "Eccentric (lowering/loading)": {"prime_movers": primary, "synergists": secondary, "stabilizers": stabilizers},
        "Concentric (lifting/driving)": {"prime_movers": primary, "synergists": secondary, "stabilizers": stabilizers},
    }


def _biomechanics_notes(ex: Dict, tendons_loaded: List[Dict], ligaments_stressed: List[Dict], phase_label: str) -> str:
    if not tendons_loaded:
        return f"{ex.get('name')} carries no joint_stress entries, so no connective-tissue load is derived for it."

    by_joint: Dict[str, List[Dict]] = {}
    for t in tendons_loaded:
        by_joint.setdefault(t["joint"], []).append(t)

    sentences = []
    for joint, entries in by_joint.items():
        primary_tendons = [e["tendon"] for e in entries if e["role"] == "prime_mover"]
        stabilizer_tendons = [e["tendon"] for e in entries if e["role"] == "stabilizer"]
        s = f"{joint}: {', '.join(primary_tendons)} transmits force through the {phase_label.lower()} phase"
        if stabilizer_tendons:
            s += f", while {', '.join(stabilizer_tendons)} stabilize isometrically throughout"
        s += "."
        sentences.append(s)

    for lig in ligaments_stressed:
        sentences.append(f"{lig['joint']} ligament load: {lig['ligament']} {lig['mechanism']}.")

    return " ".join(sentences)


def derive_connective_tissue(ex: Dict) -> Dict:
    """Return the v5.19 additive connective-tissue/phase fields for one
    exercise: tendons_loaded, ligaments_stressed, muscle_action_by_phase,
    biomechanics_notes. Same additive contract as the rest of this module -
    never reads or overwrites an existing key. Built on derive_tissue_demands()
    (already computed from real per-exercise signal) rather than a second,
    independently-guessed set of flags."""
    joints = ex.get("joint_stress", [])
    tissue = derive_tissue_demands(ex)
    push_pull = _push_pull(ex)
    force_type = ex.get("force_type")
    category = ex.get("category")
    phase_label = _phase_label(force_type, category)

    tendons_loaded: List[Dict] = []
    ligaments_stressed: List[Dict] = []

    for joint in joints:
        spec = CONNECTIVE_TISSUE_BY_JOINT.get(joint)
        if not spec:
            continue
        if push_pull == "Push" and spec.get("tendon_push"):
            tendon = spec["tendon_push"]
        elif push_pull == "Pull" and spec.get("tendon_pull"):
            tendon = spec["tendon_pull"]
        else:
            tendon = spec["tendon_default"]
        tendons_loaded.append({"tendon": tendon, "joint": joint, "phase": phase_label, "role": "prime_mover"})
        if spec.get("stabilizer_tendon"):
            tendons_loaded.append({
                "tendon": spec["stabilizer_tendon"], "joint": joint,
                "phase": "Isometric (stabilizer)", "role": "stabilizer",
            })
        if spec["trigger"](tissue):
            ligaments_stressed.append({
                "ligament": spec["ligament"], "joint": joint, "mechanism": spec["ligament_mechanism"],
            })
        if spec.get("trigger2") and spec["trigger2"](tissue):
            ligaments_stressed.append({
                "ligament": spec["ligament2"], "joint": joint, "mechanism": spec["ligament2_mechanism"],
            })

    muscle_action_by_phase = _muscle_action_by_phase(ex)
    biomechanics_notes = _biomechanics_notes(ex, tendons_loaded, ligaments_stressed, phase_label)

    return {
        "tendons_loaded": tendons_loaded,
        "ligaments_stressed": ligaments_stressed,
        "muscle_action_by_phase": muscle_action_by_phase,
        "biomechanics_notes": biomechanics_notes,
    }

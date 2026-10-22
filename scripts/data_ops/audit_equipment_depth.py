"""
audit_equipment_depth.py — FORGE spec 1.2, section 3 ("Expand Thin
Equipment Groups"): "Audit current depth per equipment tag and rank by gap
size (target minus current count) to prioritize which groups get expanded
first."

This is the audit half of that approach only - it reports the gaps, it
doesn't write any new exercises (that's a genuine content-authoring task:
name/description/muscle-groups/progression-links for each new movement,
not something this script should be guessing at). Run it, then use the
output to decide which equipment group's batch generator to write next
(see scripts/generators/generate_batchN_*.py for the existing pattern -
generate_batch6_thin_equipment.py already did an earlier pass of exactly
this for a different set of groups).

TARGET DEPTH
The spec explicitly rejects one flat target for every equipment type
("scaled to how central that equipment is to supported program types
... rather than a flat number applied to everything"). _EQUIPMENT_TIERS
below is that scaling: a small, hand-maintained set of tiers rather than
a formula, because "how central is this equipment to a supported program
type" is a product judgment call, not something derivable from the data
itself. Add new equipment names to a tier as they're introduced -
anything not listed falls back to _DEFAULT_TARGET (the spec's own
suggested 15-20 range, floored at 15).

Usage:
    python3 scripts/data_ops/audit_equipment_depth.py
    python3 scripts/data_ops/audit_equipment_depth.py --under-target-only
    python3 scripts/data_ops/audit_equipment_depth.py --json
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EXERCISES_PATH = ROOT / "data" / "exercises.json"

# Equipment that's central to the most commonly-supported program types
# (general strength/hypertrophy, powerlifting-style programming) needs the
# deepest bench of variations to avoid repeats across a multi-month block.
_TIER_CORE = 30
# Broadly-used but usually one part of a session rather than its backbone.
_TIER_SECONDARY = 20
# Specialty/niche implements (strongman, sport-specific conditioning tools)
# support fewer program types, so a program built around them repeats less
# often across a training week - still needs enough for variety, per the
# spec's own "15-20 exercises" example, but not core-lift depth.
_TIER_NICHE = 15
_DEFAULT_TARGET = _TIER_NICHE

_EQUIPMENT_TIERS = {
    _TIER_CORE: ["Barbell", "Dumbbell", "Bodyweight"],
    _TIER_SECONDARY: [
        "Kettlebell", "Rings", "Pull-up Bar", "Cable Machine", "Power Rack",
        "Resistance Band", "Squat Rack", "Smith Machine",
    ],
    # Everything else (strongman implements, single-station machines,
    # sport-conditioning tools, etc.) defaults to _TIER_NICHE below -
    # listed explicitly here anyway so the target is self-documenting
    # rather than a silent fallback, and so it's obvious where to add a
    # newly-introduced equipment tag.
    _TIER_NICHE: [
        "Log Bar", "Husafell Stone", "Atlas Stone", "Axle Bar", "Yoke",
        "Sled", "Sandbag", "Keg", "Tire", "Conan's Wheel", "Fingal's Fingers",
        "Farmer Handles", "Trap Bar", "Cambered Bar", "Buffalo Bar",
        "Swiss Bar", "Safety Squat Bar", "EZ Curl Bar", "Landmine",
        "Belt Squat", "Belt Squat Machine", "Leg Press Machine",
        "Hack Squat Machine", "Leg Curl Machine", "Leg Extension Machine",
        "Seated Row Machine", "Lat Pulldown Machine", "Chest Press Machine",
        "Shoulder Press Machine", "Pec Deck Machine", "High Row Machine",
        "V Squat Machine", "Pendulum Squat Machine",
        "Plate-Loaded Lever Machine", "GHD", "Reverse Hyper",
        "Hyperextension Bench", "Captain's Chair", "Seal Row Bench", "Bench",
        "Sit-Up Bench", "Ab Wheel", "Suspension Trainer", "Weighted Vest",
        "Battle Ropes", "Jump Rope", "Assault Bike", "Rowing Erg",
        "Agility Ladder", "Plyo Box", "Medicine Ball", "Balance Board",
        "Neck Harness", "Climbing Hangboard", "Climbing Hold / Hangboard",
        "Boxing Heavy Bag", "Speed Bag", "Tackle Bag", "Wrestling Dummy",
        "Partner / Clinch Bag",
    ],
}


def _target_for(equipment: str) -> int:
    for target, names in _EQUIPMENT_TIERS.items():
        if equipment in names:
            return target
    return _DEFAULT_TARGET


def audit(exercises_path: Path = EXERCISES_PATH):
    data = json.loads(exercises_path.read_text())
    exercises = data["exercises"]

    counts = {}
    for ex in exercises:
        eq = ex.get("equipment") or "Unknown"
        counts[eq] = counts.get(eq, 0) + 1

    rows = []
    for equipment, count in counts.items():
        target = _target_for(equipment)
        rows.append({
            "equipment": equipment,
            "current_count": count,
            "target": target,
            "gap": max(0, target - count),
        })
    # Rank by gap size, largest first (ties broken by the thinnest group
    # first) - the spec's own prioritization rule.
    rows.sort(key=lambda r: (-r["gap"], r["current_count"]))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--under-target-only", action="store_true",
                         help="Only list equipment groups with a nonzero gap.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")
    args = parser.parse_args()

    rows = audit()
    if args.under_target_only:
        rows = [r for r in rows if r["gap"] > 0]

    if args.json:
        print(json.dumps(rows, indent=2))
        return

    total_gap = sum(r["gap"] for r in rows)
    under_target = sum(1 for r in rows if r["gap"] > 0)
    print(f"{'Equipment':<32} {'Current':>8} {'Target':>8} {'Gap':>6}")
    print("-" * 56)
    for r in rows:
        marker = " *" if r["gap"] > 0 else ""
        print(f"{r['equipment']:<32} {r['current_count']:>8} {r['target']:>8} {r['gap']:>6}{marker}")
    print("-" * 56)
    print(f"{under_target} of {len(rows)} equipment groups under target - "
          f"{total_gap} exercises short of target depth in total.")


if __name__ == "__main__":
    main()

"""
fix_ankle_joint_stress_gaps.py (v5.31) — closes a joint_stress gap distinct
from fix_joint_stress_gaps.py's (v5.21): that script syncs joint_stress to
each exercise's OWN injuries_to_avoid list. This one addresses standing,
weight-bearing, closed-chain exercises (barbell/dumbbell/kettlebell squats,
hinges/deadlifts, loaded carries, sled work, explosive Olympic-pull
variants) that never had 'Ankle' in joint_stress at all, even though the
ankle bears load and stabilizes throughout the movement — e.g. Barbell Back
Squat, Barbell Conventional Deadlift, and Hang High Pull were previously
untagged for Ankle while near-identical lifts (Hang Clean, Hang Power
Snatch) were correctly tagged.

Practical effect: without this tag, someone with an ankle injury (e.g. an
ATFL sprain) entered into the app would have these exercises pass straight
through the injury filter untouched, because progression_engine's
contraindication check is a set-intersection against joint_stress /
injuries_to_avoid — a joint that's never listed can never be caught.

Scope (deliberately conservative, additive-only):
  - Categories treated as standing/weight-bearing by default: Squat, Hinge,
    Power, Carry, Conditioning.
  - Exclusions (seated/lying/isolated-joint movements where the foot isn't
    loaded under load): leg curl, leg extension, GHD, hyperextension,
    reverse hyper, rowing erg, assault bike, superman, bird dog, nordic
    hamstring curl, cable pull-through, band hamstring curl.
  - Full Body: only the standing loaded/explosive subset (Turkish Get-Up,
    Thrusters, Atlas Stone/sandbag/tire work, American Swing, etc.) is
    included; gymnastics/isometric upper-body work (planche, human flag,
    ring holds) is left alone.
  - Sport Specific (kicks, takedowns, strikes, sprawls) is explicitly NOT
    auto-tagged here — ankle involvement varies too much movement-to-
    movement for a blanket rule and needs individual clinical review.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

SRC = ROOT / "data" / "exercises.json"
BACKUP = ROOT / "data" / "backups" / "exercises_pre_ankle_joint_stress_gap_fix_backup.json"

EXCLUDE_PATTERNS = [
    "leg curl", "leg extension", "ghd", "hyperextension", "reverse hyper",
    "rowing erg", "assault bike", "superman", "bird dog", "nordic hamstring",
    "cable pull through", "band hamstring curl",
]

AUTO_CATEGORIES = {"Squat", "Hinge", "Power", "Carry", "Conditioning"}

FULL_BODY_INCLUDE = {
    "Kettlebell Turkish Get-Up", "Turkish Get-Up Partial (To Elbow)",
    "Sandbag Shouldering", "Dumbbell Thruster", "Dumbbell Man Maker",
    "Atlas Stone Load", "Stone to Shoulder", "Stone Over Bar",
    "Sandbag Load", "Sandbag to Shoulder", "Tire Flip", "Fingal's Fingers",
    "American Swing", "Kettlebell Long Cycle", "Thruster",
    "Tire Bear Crawl Push", "Atlas Stone Circuit Medley",
    "Fingal's Fingers Bear Hug Lift", "Standing March in Place (Post-Surgical Reconditioning)",
    "Supported Sit-to-Stand (Post-Surgical Reconditioning)",
}


def should_include(e):
    name = e["name"]
    cat = e["category"]
    nl = name.lower()
    if any(p in nl for p in EXCLUDE_PATTERNS):
        return False
    if cat in AUTO_CATEGORIES:
        return True
    if cat == "Full Body" and name in FULL_BODY_INCLUDE:
        return True
    return False


def main():
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)

    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    exercises = data["exercises"]
    fixed = []
    for ex in exercises:
        js = ex.get("joint_stress") or []
        if "Ankle" in js:
            continue
        if should_include(ex):
            ex["joint_stress"] = sorted(set(js) | {"Ankle"})
            fixed.append(ex["id"])

    data["version"] = "5.31.0"
    data["schema_notes"] += (
        "\n\nv5.31 closes a second joint_stress gap (see "
        "scripts/data_ops/fix_ankle_joint_stress_gaps.py): "
        f"{len(fixed)} standing/weight-bearing exercises (Squat, Hinge, "
        "Power, Carry, Conditioning, plus a curated Full Body subset) were "
        "missing an 'Ankle' joint_stress tag entirely, so an ankle injury "
        "entered by a user never intersected with these exercises in the "
        "contraindication check. Sport Specific movements were left for "
        "manual review, not auto-tagged."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Fixed {len(fixed)} exercises. Backup at {BACKUP}")


if __name__ == "__main__":
    main()

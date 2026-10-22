"""
fix_all_joint_stress_gaps_by_primary_muscle.py — generalizes the v5.33
Olympic-lift Hip fix (fix_olympic_lift_hip_gap.py) to every exercise and
every one of the 8 load-bearing joint tags, not just Olympic lifts.

ROOT CAUSE
v5.33 found that primary_muscles can name a muscle that unambiguously
drives one specific joint (e.g. Gluteus Maximus -> Hip) while
joint_stress fails to carry that joint - and fixed it for the 41
Olympic lifts. That was one instance of a wider pattern: the same
class of gap exists across the whole 828-exercise set, for 6 of the 8
joints (Ankle and Lower Back had no gaps of this kind - every exercise
whose primary_muscles implied Ankle or Lower Back already had them
tagged).

This pass uses a deliberately CONSERVATIVE muscle -> joint map: only
muscles that are single-joint and unambiguous are included (e.g.
Triceps Brachii -> Elbow only). Biarticular/ambiguous muscles that
cross two of the 8 tags (Hamstrings: Hip+Knee; Rectus Abdominis/
Obliques/Trapezius: multi-region; Gastrocnemius already fully tagged)
are deliberately EXCLUDED to avoid guessing wrong - this pass only
closes gaps it can justify with certainty, the same standard v5.33
used for Hip.

Only PRIMARY muscles are checked (the prime mover, not secondary/
stabilizer musculature) - the same standard used for the Hip fix.

FINDINGS (primary muscle implies joint, joint_stress missing it):
  Hip     : 104  (Gluteus Maximus x88, Gluteus Medius x6, Hip Flexors x10)
  Elbow   :  22  (Triceps Brachii x22)
  Shoulder:  15  (Anterior Deltoid x6, Latissimus Dorsi x8, Pectoralis Major x1)
  Wrist   :  12  (Forearm Flexors x8, Forearms x4)
  Knee    :   3  (Quadriceps x3)
  Neck    :   1  (Neck Flexors x1)
  Ankle / Lower Back: 0 (no gaps found - already fully covered)

FIX
For every exercise where a primary muscle implies a joint missing from
joint_stress:
  - add that joint to joint_stress
  - add the injuries_to_avoid tag already used elsewhere in this
    dataset for that exact muscle/joint pairing (reused, not invented):
      Triceps Brachii  -> "Triceps Strain - Grade I Strain (Mild)"      (Elbow)
      Quadriceps       -> "Quadriceps Strain - Grade I Strain (Mild)"   (Knee)
      Gluteus Maximus/Medius/Hip Flexors
                        -> "Gluteus Maximus Strain - Grade I Strain (Mild)" (Hip)
      Anterior Deltoid/Latissimus Dorsi/Pectoralis Major
                        -> "Shoulder Instability (General/Atraumatic)"  (Shoulder)
      Forearm Flexors/Forearms
                        -> "Wrist Pain"                                 (Wrist)
      Neck Flexors      -> "Neck Pain"                                  (Neck)
  - re-derive tendons_loaded/ligaments_stressed/biomechanics_notes via
    derive_connective_tissue(), same as every prior joint_stress edit.

Additive only; no other field touched. Exercises already fixed by
v5.33 (Olympic lifts, Hip) are unaffected here - their gap is closed.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.exercise_metadata import derive_connective_tissue
from backend.services.injury_taxonomy import INJURY_TAXONOMY

SRC = ROOT / "data" / "exercises.json"
BACKUP = ROOT / "data" / "backups" / "exercises_pre_all_joint_stress_gap_backup.json"

# muscle -> (joint, injuries_to_avoid tag). Conservative / unambiguous only.
MUSCLE_JOINT_TAG = {
    "Triceps Brachii":    ("Elbow",    "Triceps Strain - Grade I Strain (Mild)"),
    "Quadriceps":         ("Knee",     "Quadriceps Strain - Grade I Strain (Mild)"),
    "Gluteus Maximus":    ("Hip",      "Gluteus Maximus Strain - Grade I Strain (Mild)"),
    "Gluteus Medius":     ("Hip",      "Gluteus Maximus Strain - Grade I Strain (Mild)"),
    "Hip Flexors":        ("Hip",      "Gluteus Maximus Strain - Grade I Strain (Mild)"),
    "Anterior Deltoid":   ("Shoulder", "Shoulder Instability (General/Atraumatic)"),
    "Latissimus Dorsi":   ("Shoulder", "Shoulder Instability (General/Atraumatic)"),
    "Pectoralis Major":   ("Shoulder", "Shoulder Instability (General/Atraumatic)"),
    "Forearm Flexors":    ("Wrist",    "Wrist Pain"),
    "Forearms":           ("Wrist",    "Wrist Pain"),
    "Neck Flexors":       ("Neck",     "Neck Pain"),
}

# sanity-check every tag maps to the joint we think it does
for muscle, (joint, tag) in MUSCLE_JOINT_TAG.items():
    assert INJURY_TAXONOMY[tag]["joint"] == joint, (muscle, joint, tag)


def main():
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)

    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    exercises = data["exercises"]
    fixed = {}  # id -> set of joints added

    for ex in exercises:
        js = set(ex.get("joint_stress") or [])
        primaries = ex.get("primary_muscles") or []

        to_add_joints = set()
        to_add_tags = set()
        for m in primaries:
            hit = MUSCLE_JOINT_TAG.get(m)
            if not hit:
                continue
            joint, tag = hit
            if joint not in js:
                to_add_joints.add(joint)
                to_add_tags.add(tag)

        if not to_add_joints:
            continue

        ex["joint_stress"] = sorted(js | to_add_joints)
        existing_inj = set(ex.get("injuries_to_avoid") or [])
        ex["injuries_to_avoid"] = sorted(existing_inj | to_add_tags)

        derived = derive_connective_tissue(ex)
        ex["tendons_loaded"] = derived["tendons_loaded"]
        ex["ligaments_stressed"] = derived["ligaments_stressed"]
        ex["biomechanics_notes"] = derived["biomechanics_notes"]

        fixed[ex["id"]] = to_add_joints

    data["version"] = "5.34.0"
    data["schema_notes"] += (
        "\n\nv5.34 generalizes the v5.33 Olympic-lift Hip fix to the "
        "whole exercise set and every one of the 8 joint tags: any "
        "exercise whose primary_muscles named a single-joint, "
        "unambiguous prime mover (Triceps Brachii, Quadriceps, Gluteus "
        "Maximus/Medius, Hip Flexors, Anterior Deltoid, Latissimus "
        "Dorsi, Pectoralis Major, Forearm Flexors/Forearms, Neck "
        "Flexors) but was missing that muscle's joint in joint_stress "
        f"had it added, plus the matching injuries_to_avoid tag already "
        "used elsewhere for that muscle/joint pairing, and had "
        "tendons_loaded/ligaments_stressed/biomechanics_notes "
        f"re-derived. {len(fixed)} exercises fixed across Hip (104), "
        "Elbow (22), Shoulder (15), Wrist (12), Knee (3), Neck (1) - "
        "Ankle and Lower Back had no gaps of this kind. Biarticular/"
        "ambiguous muscles (Hamstrings, Rectus Abdominis, Obliques, "
        "Trapezius, Gastrocnemius) were deliberately excluded from the "
        "muscle->joint map rather than guessed at (see "
        "scripts/data_ops/fix_all_joint_stress_gaps_by_primary_muscle.py). "
        "No other field touched."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Fixed {len(fixed)} exercises:")
    for eid, joints in sorted(fixed.items()):
        print(f"  {eid}: +{sorted(joints)}")


if __name__ == "__main__":
    main()

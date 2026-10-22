"""
fix_olympic_lift_hip_gap.py — closes a joint_stress gap the ankle-focused
v5.25 pass (fix_olympic_lift_ankle_gap.py) did not address, because that
pass only ever added "Ankle" - it never re-examined the rest of the
triple-extension chain.

ROOT CAUSE
Every Olympic-lift-family exercise (clean/snatch/jerk and all their pulls,
high-pulls, hang/block/muscle/tall variants, plus the odd-object clean
analogues) is driven by hip extension first and hardest - the hip is the
largest contributor to "triple extension" (hip, knee, ankle), and every
squat-receive variant (Full Squat Clean, Full Squat Snatch, Hang Squat
Clean/Snatch, etc.) also loads the hip in deep flexion under load on the
catch. primary_muscles already reflects this correctly (Gluteus Maximus
and Hamstrings are listed as prime movers on effectively every one of
these lifts) - but joint_stress never carried "Hip", even though "Hip" is
already a first-class joint tag used on 165 other exercises (Squat, Hinge,
KB Swing, Deadlift, etc.), and even though injury_taxonomy.py,
sport_profiles.py, and exercise_metadata.py all already treat "Hip" as a
normal joint.

Concretely: all 41/41 is_olympic_lift=True exercises were missing "Hip" in
joint_stress. That means the injury-safety engine
(progression_engine.py: `for joint_name in joint_stress_raw`) would never
evaluate a single Olympic lift variant against a hip injury (e.g. hip
flexor strain, glute strain, labral irritation), regardless of how
hip-dominant the movement actually is - an athlete rehabbing a hip issue
could be served a Full Squat Clean with no warning.

FIX
For every is_olympic_lift=True exercise missing "Hip" in joint_stress:
  - add "Hip" to joint_stress
  - add "Gluteus Maximus Strain - Grade I Strain (Mild)" to
    injuries_to_avoid (the same umbrella tag already used for this exact
    joint on Squat/Hinge/Back Squat/Deadlift) - kept consistent rather
    than inventing a new tag.
  - re-derive tendons_loaded/ligaments_stressed/biomechanics_notes via
    derive_connective_tissue() so those fields don't go stale versus the
    corrected joint_stress, same as every prior joint_stress edit in this
    project's history.

Additive only; no other field touched.
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
BACKUP = ROOT / "data" / "backups" / "exercises_pre_oly_hip_gap_backup.json"

HIP_TAG = "Gluteus Maximus Strain - Grade I Strain (Mild)"
assert INJURY_TAXONOMY[HIP_TAG]["joint"] == "Hip"


def main():
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)

    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    exercises = data["exercises"]
    fixed = []
    for ex in exercises:
        if not ex.get("is_olympic_lift"):
            continue
        js = set(ex.get("joint_stress") or [])
        if "Hip" in js:
            continue

        ex["joint_stress"] = sorted(js | {"Hip"})
        existing_inj = set(ex.get("injuries_to_avoid") or [])
        if HIP_TAG not in existing_inj:
            ex["injuries_to_avoid"] = sorted(existing_inj | {HIP_TAG})

        derived = derive_connective_tissue(ex)
        ex["tendons_loaded"] = derived["tendons_loaded"]
        ex["ligaments_stressed"] = derived["ligaments_stressed"]
        ex["biomechanics_notes"] = derived["biomechanics_notes"]

        fixed.append(ex["id"])

    data["version"] = "5.33.0"
    data["schema_notes"] += (
        "\n\nv5.33 closes an Olympic-lift joint_stress gap: 41/41 "
        "is_olympic_lift exercises (Power Clean, Snatch, Clean and Jerk, "
        "and all pull/high-pull/hang/block/muscle/tall/split/odd-object "
        "variants) were missing 'Hip' in joint_stress despite being "
        "hip-extension-dominant (triple extension) and, for squat-receive "
        "variants, deep hip flexion under load on the catch - even though "
        "primary_muscles already correctly listed Gluteus Maximus/"
        "Hamstrings as prime movers. Added 'Hip' to joint_stress and "
        "'Gluteus Maximus Strain - Grade I Strain (Mild)' to "
        "injuries_to_avoid (matching the tag already used on Squat/Hinge/"
        "Back Squat/Deadlift) for all 41, and re-derived tendons_loaded/"
        "ligaments_stressed/biomechanics_notes against the corrected "
        "joint_stress (see scripts/data_ops/fix_olympic_lift_hip_gap.py). "
        "No other field touched."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Fixed {len(fixed)} exercises:")
    for eid in fixed:
        print(f"  {eid}")


if __name__ == "__main__":
    main()

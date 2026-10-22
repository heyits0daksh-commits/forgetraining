"""
fix_olympic_lift_ankle_gap.py — closes a joint_stress gap the earlier
v5.24 pass (fix_missing_joint_injury_coverage.py) could not catch, because
that pass only ever added injuries_to_avoid tags for joints already
present in joint_stress — it never added a missing joint_stress tag.

ROOT CAUSE
Every Olympic-lift-family exercise (clean/snatch/jerk and all their pulls,
high-pulls, hang/block/muscle/tall variants, plus the odd-object clean
analogues - log/axle/keg/sandbag/kettlebell/dumbbell clean & snatch) relies
on an explosive ankle-drive (the "triple extension" - hip, knee, AND ankle
plantarflexion is what actually finishes the pull) and, for every variant
that receives the bar in a squat, lands in deep ankle dorsiflexion under
load immediately after. That's precisely why competitive weightlifting
shoes exist with an elevated, rigid heel - ankle mobility/loading is a
first-order demand of this whole exercise family, not an edge case.

Despite that, only the 4 split-stance lifts (Split Jerk, Barbell Push Jerk,
Split Clean, Split Snatch) had "Ankle" in joint_stress. The other 37
is_olympic_lift=True exercises had none - so an exercise the injury-safety
engine (progression_engine.py: `for joint_name in joint_stress_raw`) would
never even evaluate against an ankle injury, regardless of how good its
injuries_to_avoid list was. This is why an ankle sprain still surfaced
Olympic lifts: the earlier pass fixed the tag<->joint consistency, but
never questioned whether joint_stress itself was complete.

FIX
For every is_olympic_lift=True exercise missing "Ankle" in joint_stress:
  - add "Ankle" to joint_stress
  - add "Lateral Ankle Sprain - Grade 1 (Mild)" to injuries_to_avoid (the
    same umbrella tag already used on the 4 split-stance lifts for this
    exact joint - kept consistent rather than inventing a second tag).
    None of these 37 exercises carry a calf muscle (Gastrocnemius/Soleus)
    in primary/secondary_muscles - the data model doesn't track
    plantarflexor musculature for this family at all - so there is no
    muscle-derived tag available; the umbrella tag is the correct choice,
    not a fallback of convenience.
  - re-derive tendons_loaded/ligaments_stressed/biomechanics_notes via
    derive_connective_tissue() so those fields don't go stale versus the
    new joint_stress, same as v5.23.1 did after prior joint_stress edits.

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
BACKUP = ROOT / "data" / "backups" / "exercises_pre_oly_ankle_gap_backup.json"

ANKLE_TAG = "Lateral Ankle Sprain - Grade 1 (Mild)"
assert INJURY_TAXONOMY[ANKLE_TAG]["joint"] == "Ankle"


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
        if "Ankle" in js:
            continue

        ex["joint_stress"] = sorted(js | {"Ankle"})
        existing_inj = set(ex.get("injuries_to_avoid") or [])
        if ANKLE_TAG not in existing_inj:
            ex["injuries_to_avoid"] = sorted(existing_inj | {ANKLE_TAG})

        derived = derive_connective_tissue(ex)
        ex["tendons_loaded"] = derived["tendons_loaded"]
        ex["ligaments_stressed"] = derived["ligaments_stressed"]
        ex["biomechanics_notes"] = derived["biomechanics_notes"]

        fixed.append(ex["id"])

    data["version"] = "5.25.0"
    data["schema_notes"] += (
        "\n\nv5.25 closes an Olympic-lift joint_stress gap: 37/41 "
        "is_olympic_lift exercises (Power Clean, Snatch, Clean and Jerk, "
        "and all pull/high-pull/hang/block/muscle/tall/odd-object "
        "variants) were missing 'Ankle' in joint_stress despite relying on "
        "explosive ankle plantarflexion (triple extension) and, for catch "
        "variants, deep ankle dorsiflexion on landing - only the 4 "
        "split-stance lifts had it. Added 'Ankle' to joint_stress and "
        "'Lateral Ankle Sprain - Grade 1 (Mild)' to injuries_to_avoid "
        "(matching the tag already used on the split-stance lifts) for "
        "all 37, and re-derived tendons_loaded/ligaments_stressed/"
        "biomechanics_notes against the corrected joint_stress (see "
        "scripts/data_ops/fix_olympic_lift_ankle_gap.py). No other field "
        "touched."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Fixed {len(fixed)} exercises:")
    for eid in fixed:
        print(f"  {eid}")


if __name__ == "__main__":
    main()

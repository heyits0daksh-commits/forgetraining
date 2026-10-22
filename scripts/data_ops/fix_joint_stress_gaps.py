"""
fix_joint_stress_gaps.py — closes Gap 2: exercises whose injuries_to_avoid
tags name an injury whose taxonomy `joint` isn't in that exercise's own
joint_stress list.

The taxonomy's joint mapping is the deliberately-curated side (see
injury_taxonomy.py's module docstring: joints are chosen to reflect real
anatomy within the 8-tag vocabulary, e.g. Hamstring Strain -> Knee because
the hamstring crosses the knee, not just the hip). So this script does NOT
touch the taxonomy - it adds the missing joint_stress tag to the exercise,
which is where the actual data gap is.

Additive only: never removes/reorders existing joint_stress entries beyond
appending the missing tag.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.injury_taxonomy import INJURY_TAXONOMY

SRC = ROOT / "data" / "exercises.json"
BACKUP = ROOT / "data" / "backups" / "exercises_pre_joint_stress_gap_fix_backup.json"


def main():
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)

    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    exercises = data["exercises"]
    fixed = {}
    for ex in exercises:
        js = set(ex.get("joint_stress") or [])
        added = set()
        for inj in ex.get("injuries_to_avoid") or []:
            entry = INJURY_TAXONOMY.get(inj)
            if entry is None:
                continue
            joint = entry.get("joint")
            if joint and joint not in js:
                added.add(joint)
        if added:
            new_js = sorted(js | added)
            fixed[ex["id"]] = {"added": sorted(added), "joint_stress": new_js}
            ex["joint_stress"] = new_js

    data["version"] = "5.21.0"
    data["schema_notes"] += (
        "\n\nv5.21 closes a joint_stress/injuries_to_avoid consistency gap: "
        f"{len(fixed)} exercises were missing a joint_stress tag for a joint "
        "their own injuries_to_avoid list already implicates (see "
        "scripts/data_ops/fix_joint_stress_gaps.py). Taxonomy joint mappings "
        "were left untouched; only joint_stress was appended to."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Fixed {len(fixed)} exercises:")
    for eid, info in fixed.items():
        print(f"  {eid}: +{info['added']} -> {info['joint_stress']}")


if __name__ == "__main__":
    main()

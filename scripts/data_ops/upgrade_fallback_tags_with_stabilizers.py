"""
upgrade_fallback_tags_with_stabilizers.py — v5.27.

fix_missing_joint_injury_coverage.py (v5.24) only ever checked
primary_muscles/secondary_muscles when looking for a muscle-specific tag,
and its MUSCLE_NAME_TO_GROUP dict was missing 3 spellings that only ever
appear in `stabilizers` ("Rotator Cuff", "Forearm Extensors", "Shoulder
Stabilizers"). Both gaps are fixed at the source in
fix_missing_joint_injury_coverage.py (_muscle_tag_for_joint now checks
primary -> secondary -> stabilizers in that priority; the 3 missing names
are now in MUSCLE_NAME_TO_GROUP).

This script re-derives, for every exercise, every joint whose ONLY
covering injuries_to_avoid tag(s) are a generic JOINT_FALLBACK umbrella
(Wrist Pain / Medial Epicondylalgia / Rotator Cuff / Neck Pain / Low Back
Pain / Hip Flexors Strain / Patellar Tendon / Lateral Ankle Sprain) - i.e.
never got a specific muscle-strain tag - and adds the specific tag
wherever the corrected _muscle_tag_for_joint now finds one from the
exercise's OWN muscle data. This is exactly the same "most specific,
mildest representative" convention already established for every other
injuries_to_avoid tag in this file (see injury_taxonomy.py v5.11 notes).

Additive only: existing fallback tags are left in place (removing them
is out of scope here - not every joint-fallback exercise gets a muscle
match, so blanket removal would re-open coverage gaps); this only adds
the more specific tag alongside where one is now derivable.
"""
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.injury_taxonomy import INJURY_TAXONOMY
from scripts.data_ops.fix_missing_joint_injury_coverage import (
    JOINT_FALLBACK,
    TAG_JOINT,
    _muscle_tag_for_joint,
)

SRC = ROOT / "data" / "exercises.json"
BACKUP = ROOT / "data" / "backups" / "exercises_pre_v5_27_stabilizer_upgrade_backup.json"

FALLBACK_TAGS = set(JOINT_FALLBACK.values())


def main():
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)

    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    exercises = data["exercises"]
    additions_log = {}

    for ex in exercises:
        existing = set(ex.get("injuries_to_avoid") or [])
        covered = {}
        for t in existing:
            j = TAG_JOINT.get(t)
            if j:
                covered.setdefault(j, []).append(t)

        new_tags = []
        for joint in sorted(set(ex.get("joint_stress") or [])):
            tags_here = covered.get(joint, [])
            only_fallback = bool(tags_here) and all(t in FALLBACK_TAGS for t in tags_here)
            if not only_fallback:
                continue
            tag = _muscle_tag_for_joint(ex, joint)
            if tag and tag not in existing and tag not in new_tags:
                assert tag in INJURY_TAXONOMY, f"{tag!r} not in INJURY_TAXONOMY"
                new_tags.append(tag)

        if new_tags:
            ex["injuries_to_avoid"] = sorted(existing | set(new_tags))
            additions_log[ex["id"]] = new_tags

    data["version"] = "5.27.0"
    data["schema_notes"] += (
        "\n\nv5.27 upgrades generic joint-fallback injuries_to_avoid tags "
        "to specific muscle-strain tags wherever the exercise's own "
        "muscle data now supports one. Two source-level fixes in "
        "fix_missing_joint_injury_coverage.py made this possible: "
        "_muscle_tag_for_joint now also checks stabilizers (after "
        "primary/secondary, same priority order), and MUSCLE_NAME_TO_GROUP "
        "gained 3 muscle-name spellings that only ever appear in "
        "stabilizers lists (\"Rotator Cuff\", \"Forearm Extensors\", "
        "\"Shoulder Stabilizers\") and were previously unresolvable "
        "there. Ran the corrected muscle-first lookup against every "
        f"exercise whose joint_stress joint was covered ONLY by a generic "
        "JOINT_FALLBACK umbrella tag (Wrist Pain / Medial Epicondylalgia "
        "/ Rotator Cuff / Neck Pain / Low Back Pain / Hip Flexors Strain "
        "/ Patellar Tendon / Lateral Ankle Sprain); wherever a specific "
        "tag is now derivable, it's added alongside the existing umbrella "
        "tag (additive only, umbrella tags not removed) - see "
        "scripts/data_ops/upgrade_fallback_tags_with_stabilizers.py."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Updated {len(additions_log)}/{len(exercises)} exercises.")
    tag_freq = Counter(t for tags in additions_log.values() for t in tags)
    print("\nTags added (frequency):")
    for tag, n in tag_freq.most_common():
        print(f"  {n:4d}  {tag}")


if __name__ == "__main__":
    main()

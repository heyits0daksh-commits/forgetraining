"""
fix_missing_joint_injury_coverage.py — closes Gap 1: exercises whose
joint_stress lists a joint that NO tag in injuries_to_avoid actually maps
to (via INJURY_TAXONOMY[tag]["joint"]). This is the mirror image of what
fix_joint_stress_gaps.py (v5.21) fixed — that script added a missing
joint_stress tag when injuries_to_avoid already implicated a joint; this
one adds a missing injuries_to_avoid tag when joint_stress already
implicates a joint that no tag covers.

v5.20's k-NN model (map_injuries_to_avoid.py) already closed most of this
gap, but only added a tag when a confident neighbor-vote existed; it never
guaranteed every joint gets *at least one* tag. As of this pass, 534/828
exercises still had an uncovered joint.

APPROACH — muscle-first, joint-umbrella fallback
For each exercise, for each joint in joint_stress with zero covering tag:
  1. Look at this exercise's OWN primary_muscles (then secondary_muscles)
     for a muscle that anatomically belongs to that joint (see
     MUSCLE_NAME_TO_GROUP below, which resolves the ~40 muscle-name
     spellings actually used in exercises.json to the canonical
     MUSCLE_GROUPS entries already in injury_taxonomy.py). If found, add
     that muscle's Grade I (mild) strain tag — the same "most specific,
     mildest representative" convention already used everywhere else in
     the hand-curated data (e.g. "Biceps Strain - Grade I Strain (Mild)").
  2. If no muscle in this exercise's own muscle lists maps to that joint
     (e.g. a joint that's stressed passively/structurally rather than by a
     working muscle), fall back to a single fixed generic/umbrella tag per
     joint (JOINT_FALLBACK below) — reusing the exact umbrella tags
     (Low Back Pain, Neck Pain, Wrist Pain, Rotator Cuff, Patellar Tendon,
     Lateral Ankle Sprain - Grade 1) already established and in heavy use
     across the file for this purpose (see injury_taxonomy.py v5.11 notes
     on "bare/vernacular umbrella terms"). Hip and Elbow had no existing
     umbrella in use, so this pass adds the same fallback-of-last-resort
     logic for them (Hip Flexors Strain - Grade I; Medial Epicondylalgia).

SAME SAFEGUARDS AS v5.20
- Corrective/rehab-pattern exercises are skipped entirely (same
  _is_corrective check) — a false-positive contraindication is worse than
  a missing one for exercises prescribed BECAUSE of an injury.
- Additive only: never removes/reorders existing injuries_to_avoid.
- Every added tag must already resolve in INJURY_TAXONOMY.
"""
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.injury_taxonomy import INJURY_TAXONOMY, MUSCLE_GROUPS
from scripts.data_ops.map_injuries_to_avoid import _is_corrective

SRC = ROOT / "data" / "exercises.json"
BACKUP = ROOT / "data" / "backups" / "exercises_pre_joint_injury_coverage_backup.json"

TAG_JOINT = {name: entry["joint"] for name, entry in INJURY_TAXONOMY.items()}

# canonical MUSCLE_GROUPS name -> joint (from injury_taxonomy.py)
GROUP_JOINT = {name: joint for name, joint, _region in MUSCLE_GROUPS}
GROUP_NAMES = {name for name, _joint, _region in MUSCLE_GROUPS}

# Resolves every muscle-name spelling actually used in exercises.json's
# primary_muscles/secondary_muscles to a canonical MUSCLE_GROUPS name.
MUSCLE_NAME_TO_GROUP = {
    "Quadriceps": "Quadriceps",
    "Gluteus Maximus": "Gluteus Maximus",
    "Anterior Deltoid": "Deltoids",
    "Lateral Deltoid": "Deltoids",
    "Posterior Deltoid": "Deltoids",
    "Rear Deltoid": "Deltoids",
    "Deltoids": "Deltoids",
    "Shoulders": "Deltoids",
    "Hamstrings": "Hamstrings",
    "Triceps Brachii": "Triceps",
    "Erector Spinae": "Erector Spinae",
    "Lower Back": "Erector Spinae",
    "Latissimus Dorsi": "Latissimus Dorsi",
    "Lats": "Latissimus Dorsi",
    "Trapezius": "Trapezius",
    "Upper Trapezius": "Trapezius",
    "Traps": "Trapezius",
    "Neck Extensors": "Trapezius",
    "Biceps Brachii": "Biceps",
    "Brachialis": "Biceps",
    "Pectoralis Major": "Pectoralis Major",
    "Rhomboids": "Rhomboids",
    "Upper Back": "Rhomboids",
    "Rectus Abdominis": "Rectus Abdominis",
    "Core": "Rectus Abdominis",
    "Forearm Flexors": "Forearm Flexors",
    "Wrist Flexors": "Forearm Flexors",
    "Forearms": "Forearm Flexors",
    "Obliques": "Obliques",
    "Hip Flexors": "Hip Flexors",
    "Glutes": "Gluteus Maximus",
    "Calves": "Gastrocnemius",
    "Gastrocnemius": "Gastrocnemius",
    "Adductors": "Adductors",
    "Gluteus Medius": "Gluteus Medius",
    "Gluteus Minimus": "Gluteus Minimus",
    "Soleus": "Soleus",
    "Neck Flexors": "Neck Muscles (Sternocleidomastoid/Scalenes)",
    "Sternocleidomastoid": "Neck Muscles (Sternocleidomastoid/Scalenes)",
    "Serratus Anterior": "Serratus Anterior",
    "Hip Abductors": "Abductors",
    "Ankle Stabilizers": "Peroneals",
    "Transverse Abdominis": "Transverse Abdominis",
    "Tibialis Anterior": "Tibialis Anterior",
    "Peroneals": "Peroneals",
    "Tensor Fasciae Latae (TFL)": "Tensor Fasciae Latae (TFL)",
    # v5.27: these 3 spellings are used in exercises.json's `stabilizers`
    # lists (never primary/secondary) but were absent from this dict, so
    # _muscle_tag_for_joint could never resolve them even after v5.28
    # extended it to check stabilizers too.
    "Rotator Cuff": "Rotator Cuff Muscles",
    "Forearm Extensors": "Forearm Extensors",
    "Shoulder Stabilizers": "Rotator Cuff Muscles",
}

# Last-resort per-joint tag when this exercise's own muscle lists have
# nothing that maps to the uncovered joint. Reuses existing umbrella
# convention where one was already established (v5.11); adds the same
# pattern for Hip/Elbow, which had none.
JOINT_FALLBACK = {
    "Wrist": "Wrist Pain",
    "Elbow": "Medial Epicondylalgia (Golfer's Elbow)",
    "Shoulder": "Rotator Cuff",
    "Neck": "Neck Pain",
    "Lower Back": "Low Back Pain",
    "Hip": "Hip Flexors Strain - Grade I Strain (Mild)",
    "Knee": "Patellar Tendon",
    "Ankle": "Lateral Ankle Sprain - Grade 1 (Mild)",
}

assert set(JOINT_FALLBACK.values()) <= set(INJURY_TAXONOMY), "fallback tag not in taxonomy"


def _strain_tag(group_name: str) -> str:
    return f"{group_name} Strain - Grade I Strain (Mild)"


def _muscle_tag_for_joint(ex: dict, joint: str) -> str | None:
    """v5.27: checks stabilizers as a third priority tier, after primary
    then secondary muscles - a muscle that's only ever listed as a
    stabilizer (e.g. "Forearm Extensors" on close-grip pressing work) can
    still supply a specific tag instead of falling all the way to the
    generic per-joint JOINT_FALLBACK umbrella. Priority order matters: a
    prime-mover match always wins over a stabilizer match for the same
    joint, same as before."""
    for pool_key in ("primary_muscles", "secondary_muscles", "stabilizers"):
        for m in ex.get(pool_key) or []:
            group = MUSCLE_NAME_TO_GROUP.get(m)
            if group and GROUP_JOINT.get(group) == joint:
                tag = _strain_tag(group)
                if tag in INJURY_TAXONOMY:
                    return tag
    return None


def main():
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)

    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    exercises = data["exercises"]
    skipped_corrective = []
    additions_log = {}
    source_log = {}  # eid -> list of (joint, tag, "muscle"|"fallback")

    for ex in exercises:
        if _is_corrective(ex):
            skipped_corrective.append(ex["id"])
            continue

        joints = set(ex.get("joint_stress") or [])
        existing = set(ex.get("injuries_to_avoid") or [])
        covered = {TAG_JOINT[t] for t in existing if t in TAG_JOINT}
        missing = joints - covered
        if not missing:
            continue

        new_tags = []
        per_ex_sources = []
        for joint in sorted(missing):
            tag = _muscle_tag_for_joint(ex, joint)
            source = "muscle"
            if tag is None:
                tag = JOINT_FALLBACK.get(joint)
                source = "fallback"
            if tag is None:
                continue
            if tag not in existing and tag not in new_tags:
                new_tags.append(tag)
                per_ex_sources.append((joint, tag, source))

        if new_tags:
            ex["injuries_to_avoid"] = sorted(existing | set(new_tags))
            additions_log[ex["id"]] = new_tags
            source_log[ex["id"]] = per_ex_sources

    data["version"] = "5.24.0"
    data["schema_notes"] += (
        "\n\nv5.24 closes Gap 1: exercises whose joint_stress named a joint "
        "that no tag in their injuries_to_avoid actually maps to (534/828 "
        "exercises, post-v5.20/v5.23). For each uncovered joint, adds the "
        "exercise's own primary/secondary muscle's Grade I strain tag when "
        "one of its muscles anatomically belongs to that joint, else a "
        "fixed per-joint umbrella tag (see JOINT_FALLBACK in "
        "scripts/data_ops/fix_missing_joint_injury_coverage.py). Corrective/"
        "rehab-pattern exercises skipped, same as v5.20. Additive only."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Skipped (corrective/rehab pattern): {len(skipped_corrective)}")
    print(f"Updated {len(additions_log)}/{len(exercises)} exercises.")

    tag_freq = Counter(t for tags in additions_log.values() for t in tags)
    print("\nTags added (frequency):")
    for tag, n in tag_freq.most_common():
        print(f"  {n:4d}  {tag}")

    src_freq = Counter(s for sources in source_log.values() for _, _, s in sources)
    print(f"\nSource breakdown: muscle-derived={src_freq['muscle']}  fallback={src_freq['fallback']}")

    with open("/tmp/joint_injury_coverage_additions.json", "w") as f:
        json.dump(source_log, f, indent=2)


if __name__ == "__main__":
    main()

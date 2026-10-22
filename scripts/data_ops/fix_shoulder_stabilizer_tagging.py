"""
fix_shoulder_stabilizer_tagging.py — closes a gap the v5.22 shoulder-swap
pass left open: exercises where the load is held/stabilized by the hands
and shoulders (front-rack, goblet, Zercher, overhead-carry, suitcase-carry
positions) but joint_stress never carried "Shoulder", so the injury-safety
engine never considered them shoulder-risky in the first place.

Root cause: joint_stress had implicitly meant "which joint does the WORKING
motion" (e.g. squat -> Knee/Hip) rather than "which joint has to bear/
stabilize load, working or not." A goblet squat's knees and hips do the
moving, but the shoulders/rotator cuff isometrically hold the kettlebell at
chest the entire set - for someone with an actual rotator cuff injury, that
static hold can be exactly as provocative as a working shoulder movement,
sometimes more so (no rest between reps). This pass tags every exercise
where an unsupported external load is held in the hand(s) against gravity
for the duration of the set - not just where the shoulder is the prime
mover.

TWO FIXES:

1. JOINT_STRESS: adds "Shoulder" to 20 exercises across the front-rack
   squat, goblet squat, Zercher, and loaded-carry families that hold weight
   in front of/across the shoulders but were missing the tag (the base
   Barbell Front Squat and its pause/tempo/clean-grip variants were
   inconsistently tagged - Zombie/Cross Arm/Zercher variants of the same
   family already had "Shoulder"; the standard rack-grip ones didn't).
   Belt Squat / Belt Squat Machine / Leg Press / Hack Squat Machine are
   deliberately left untouched - the load is carried by a hip belt or a
   machine track, never by the arms, so there's genuinely nothing for the
   shoulder to stabilize.

2. ALTERNATIVES: v5.22 declared Dumbbell Goblet Squat and Landmine Squat as
   the "shoulder-friendly" swap for the front-squat/Zercher family. Fix #1
   means that's no longer true - both are themselves hand-held front-rack
   holds and get the same "Shoulder" tag here. Re-points those 10
   exercises' alternatives at genuinely shoulder-free equipment instead:
   Belt Squat, Belt Squat Machine, Leg Press, Hack Squat Machine - nothing
   for the hands/shoulders to hold at all.

Additive/corrective only for the two fixes above; nothing else touched.
Re-runnable (checks before adding/removing).
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

SRC = ROOT / "data" / "exercises.json"
BACKUP = ROOT / "data" / "backups" / "exercises_pre_shoulder_stabilizer_fix_backup.json"

# Every exercise where the hands/arms hold or carry an external load in
# front of, across, or overhead of the shoulders for the duration of the
# set, but joint_stress didn't say "Shoulder".
SHOULDER_STABILIZER_FIX = [
    "bb_front_squat_001", "pause_frontsquat_001", "tempo_frontsquat_001",
    "cleangrip_frontsquat_001",
    "goblet_squat_001", "db_goblet_squat_001", "kb_racked_squat_001",
    "goblet_boxsquat_001", "goblet_cyclist_001", "goblet_splitsquat_001",
    "goblet_lateralsquat_001", "goblet_reverselunge_001",
    "dbl_kb_frontsquat_001", "landmine_squat_001",
    "yoke_turncarry_001", "logbar_frontsquat_001",
    "husafell_zercher_001", "farmerhandles_suitcase_001",
    "camberedbar_frontsquat_001", "buffalobar_frontsquat_001",
]

# Exercises whose `alternatives` pointed at db_goblet_squat_001 /
# landmine_squat_001 specifically *as a shoulder-safe swap* (the v5.22
# ALTERNATIVE_GROUPS front-squat/Zercher entries) - re-point these at
# equipment that never touches the hands/shoulders at all.
SHOULDER_SAFE_REALTERNATIVES = [
    "bb_front_squat_001", "pause_frontsquat_001", "tempo_frontsquat_001",
    "cleangrip_frontsquat_001", "zombie_frontsquat_001", "crossarm_frontsquat_001",
    "zercher_squat_001", "zercher_reverselunge_001", "zercher_splitsquat_001",
    "zercher_boxsquat_001",
]
NEW_SHOULDER_FREE_ALTS = ["beltsquat_001", "belt_squat_machine_001", "legpress_bilateral_001", "hacksquat_001"]
OLD_NO_LONGER_SAFE_ALTS = {"db_goblet_squat_001", "landmine_squat_001"}


def main():
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)

    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    exercises = data["exercises"]
    by_id = {ex["id"]: ex for ex in exercises}
    all_ids = set(by_id)

    referenced = set(SHOULDER_STABILIZER_FIX) | set(SHOULDER_SAFE_REALTERNATIVES) \
        | set(NEW_SHOULDER_FREE_ALTS) | OLD_NO_LONGER_SAFE_ALTS
    missing = referenced - all_ids
    if missing:
        raise SystemExit(f"Unknown exercise id(s), aborting: {sorted(missing)}")

    js_fixed = []
    for eid in SHOULDER_STABILIZER_FIX:
        ex = by_id[eid]
        js = set(ex.get("joint_stress") or [])
        if "Shoulder" not in js:
            ex["joint_stress"] = sorted(js | {"Shoulder"})
            js_fixed.append(eid)

    alts_fixed = {}
    for eid in SHOULDER_SAFE_REALTERNATIVES:
        ex = by_id[eid]
        existing = list(ex.get("alternatives") or [])
        kept = [a for a in existing if a not in OLD_NO_LONGER_SAFE_ALTS]
        to_add = [a for a in NEW_SHOULDER_FREE_ALTS if a != eid and a not in kept]
        new_alts = kept + to_add
        if new_alts != existing:
            ex["alternatives"] = new_alts
            alts_fixed[eid] = {"removed": [a for a in existing if a in OLD_NO_LONGER_SAFE_ALTS], "added": to_add}

    data["version"] = "5.23.0"
    data["schema_notes"] += (
        "\n\nv5.23 fixes a shoulder-stabilizer joint_stress gap: 20 exercises that hold "
        "an external load in the hand(s) against the shoulders/chest for the whole set "
        "(front-rack, goblet, Zercher, and loaded-carry positions) were missing "
        "'Shoulder' in joint_stress, so a rotator-cuff (or other shoulder) injury never "
        "excluded them even though the hold is a real isometric shoulder demand, not "
        "just whatever joint does the working motion. Also re-points the 10 front-squat/"
        "Zercher exercises v5.22 had pointed at Dumbbell Goblet Squat / Landmine Squat as "
        "a 'shoulder-friendly' swap - those two get the same fix here, so they're no "
        "longer shoulder-safe - at genuinely hands-free equipment instead: Belt Squat, "
        "Belt Squat Machine, Leg Press, Hack Squat Machine "
        "(see scripts/data_ops/fix_shoulder_stabilizer_tagging.py)."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"joint_stress fixed ({len(js_fixed)}): {js_fixed}")
    print(f"\nalternatives re-pointed ({len(alts_fixed)} exercises):")
    for eid, change in alts_fixed.items():
        print(f"  {eid}: -{change['removed']} +{change['added']}")


if __name__ == "__main__":
    main()

"""
add_shoulder_friendly_swaps.py — two related fixes for shoulder-injury
substitution across the barbell "big lift" families (squat, bench, overhead
press, row, deadlift):

1. JOINT_STRESS FIX: 16 straight-bar back-squat-pattern exercises (Barbell
   Back Squat and its powerlifting-style variants - high/low bar, pause,
   tempo, banded, chain, reverse-band, accommodating, dynamic/max effort,
   monolift, speed, box, narrow/wide stance) were missing "Shoulder" in
   joint_stress even though racking a straight bar across the traps
   requires real shoulder extension/external rotation - exactly the
   mobility a shoulder-injured lifter often doesn't have. Without the tag,
   the injury-safety engine (classify_injury_risk / clears_joints) never
   even considers these exercises risky for a shoulder injury in the first
   place. Front-rack/overhead/Zercher squat variants were left alone -
   they already carry their own correct joint tags (Wrist, Elbow, Shoulder
   as appropriate) and this fix only concerns the back-rack subfamily.

2. ALTERNATIVES: declares existing, already-in-database equipment swaps as
   preferred `alternatives` for barbell exercises that load the shoulder,
   grouped by movement family:
     - Back squat family      -> Safety Squat Bar Squat, Belt Squat,
                                  Belt Squat Machine
     - Front squat family      -> Dumbbell Goblet Squat, Landmine Squat
     - Zercher squat family     -> Dumbbell Goblet Squat, Landmine Squat
     - Bench press family       -> Swiss Bar Bench Press, Cambered Bar
                                    Bench Press (neutral grip - reduces
                                    shoulder external rotation at the
                                    bottom vs. a straight bar)
     - Overhead press family    -> Landmine Press, Swiss Bar Overhead Press
     - Bent-over row family      -> Trap Bar Bent-Over Row, Landmine Row
                                    (neutral grip)
     - Straight-bar deadlift    -> Trap Bar Deadlift

   NOTE (worth a human look, not auto-fixed here): Safety Squat Bar Squat
   (ssb_squat_001) and Safety Bar Squat (safetybar_squat_001) themselves
   still carry "Shoulder" in joint_stress - the yoke still rests on/loads
   the shoulder girdle even though the front handles remove the external-
   rotation demand a straight bar requires. That's plausible (compressive
   shoulder load without the ER component), but it means SSB won't
   actually clear a strict shoulder-injury filter the way Belt Squat /
   Goblet Squat / Landmine Squat will. Left as-is rather than guessed at,
   since "does SSB still count as shoulder-risky" is a judgment call this
   script shouldn't make unilaterally - flagging for review.

   Additive only: never removes/replaces existing alternatives or
   joint_stress entries, only appends. Re-runnable.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

SRC = ROOT / "data" / "exercises.json"
BACKUP = ROOT / "data" / "backups" / "exercises_pre_shoulder_swaps_backup.json"

BACK_SQUAT_JOINT_STRESS_FIX = [
    "bb_back_squat_001", "highbar_backsquat_001", "lowbar_backsquat_001",
    "pause_backsquat_001", "tempo_backsquat_001", "banded_backsquat_001",
    "chain_backsquat_001", "reverseband_squat_001", "accommodating_squat_001",
    "dynamiceffort_squat_001", "maxeffort_squat_001", "monolift_squat_001",
    "speed_squat_001", "concentric_box_squat_001", "narrow_stance_squat_001",
    "wide_stance_squat_001",
]

ALTERNATIVE_GROUPS = {
    tuple(BACK_SQUAT_JOINT_STRESS_FIX): ["ssb_squat_001", "beltsquat_001", "belt_squat_machine_001"],
    (
        "bb_front_squat_001", "pause_frontsquat_001", "tempo_frontsquat_001",
        "cleangrip_frontsquat_001", "zombie_frontsquat_001", "crossarm_frontsquat_001",
        "zercher_squat_001", "zercher_reverselunge_001", "zercher_splitsquat_001",
        "zercher_boxsquat_001",
    ): ["db_goblet_squat_001", "landmine_squat_001"],
    (
        "floor_press_001", "flat_bench_001", "incline_bench_001", "decline_bench_001",
        "closegrip_bench_001", "widegrip_bench_001", "reversegrip_bench_001",
        "spoto_press_001", "larsen_press_001", "board_press_001", "guillotine_press_001",
        "slingshot_bench_001", "chain_bench_001", "speed_bench_001",
        "bb_closegripfloorpress_001", "bb_jmpress_001",
    ): ["swissbar_bench_001", "camberedbar_bench_001"],
    (
        "bb_overhead_press_001", "push_press_001", "push_jerk_001", "split_jerk_001",
        "strict_press_001", "military_press_001", "zpress_001", "bradford_press_001",
        "behindneck_press_001",
    ): ["landmine_press_001", "swissbar_press_001"],
    (
        "bb_bent_over_row_001", "pendlay_row_001", "meadows_row_001", "yates_row_001",
        "singlearm_bb_row_001", "inverted_row_bent_001", "inverted_row_straight_001",
    ): ["trapbar_row_001", "landmine_row_001"],
    ("bb_deadlift_001", "zercher_deadlift_001"): ["trap_bar_deadlift_001"],
}


def main():
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)

    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    exercises = data["exercises"]
    by_id = {ex["id"]: ex for ex in exercises}
    all_ids = set(by_id)

    # Sanity check every id referenced below actually exists before touching anything.
    referenced = set(BACK_SQUAT_JOINT_STRESS_FIX)
    for group, alts in ALTERNATIVE_GROUPS.items():
        referenced.update(group)
        referenced.update(alts)
    missing = referenced - all_ids
    if missing:
        raise SystemExit(f"Unknown exercise id(s), aborting: {sorted(missing)}")

    js_fixed = []
    for eid in BACK_SQUAT_JOINT_STRESS_FIX:
        ex = by_id[eid]
        js = set(ex.get("joint_stress") or [])
        if "Shoulder" not in js:
            ex["joint_stress"] = sorted(js | {"Shoulder"})
            js_fixed.append(eid)

    alts_fixed = {}
    for group, alt_ids in ALTERNATIVE_GROUPS.items():
        for eid in group:
            ex = by_id[eid]
            existing = list(ex.get("alternatives") or [])
            existing_set = set(existing)
            to_add = [a for a in alt_ids if a != eid and a not in existing_set]
            if to_add:
                ex["alternatives"] = existing + to_add
                alts_fixed[eid] = to_add

    data["version"] = "5.22.0"
    data["schema_notes"] += (
        "\n\nv5.22 adds shoulder-injury-aware equipment substitution across "
        "the barbell squat/bench/press/row/deadlift families: (a) fixes a "
        "joint_stress gap where 16 straight-bar back-squat variants were "
        "missing 'Shoulder' despite racking the bar across the traps, and "
        "(b) declares existing Safety Squat Bar / Belt Squat / Landmine / "
        "Goblet / Swiss Bar / Cambered Bar / Trap Bar exercises as "
        "preferred `alternatives` for their straight-barbell equivalents "
        "(see scripts/data_ops/add_shoulder_friendly_swaps.py)."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"joint_stress fixed ({len(js_fixed)}): {js_fixed}")
    print(f"\nalternatives added ({len(alts_fixed)} exercises):")
    for eid, added in alts_fixed.items():
        print(f"  {eid}: +{added}")


if __name__ == "__main__":
    main()

"""
enrich_batch21_only.py — one-off companion to
generate_batch21_missing_gym_staples.py. Same reasoning as
enrich_batch6-20_only.py: enrich ONLY the batch21 exercises (by id), leave
every pre-existing exercise byte-for-byte untouched, append a new
schema_notes entry and bump the version forward rather than overwriting.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:
    from backend.core.config import settings
    SRC = settings.EXERCISES_JSON_PATH
except ModuleNotFoundError:
    SRC = Path(__file__).resolve().parent.parent.parent / "data" / "exercises.json"
from backend.services.exercise_metadata import enrich_exercise, derive_taxonomy_groups, derive_connective_tissue

BATCH21_IDS = {
    "shrug_barbell_001", "calf_standingmachine_001", "calf_seatedmachine_001",
    "core_abcrunchmachine_001", "shoulder_dblateralraise_001",
    "triceps_cablepushdown_001", "triceps_cableoverheadext_001",
    "triceps_ezskullcrusher_001", "triceps_dipmachine_001",
    "biceps_preachermachine_001", "back_assistedpullupmachine_001",
    "glutes_barbellhipthrust_001", "glutes_hipthrustmachine_001",
    "glutes_cablekickback_001", "shoulder_dbseatedpress_001",
    "legs_trapbarsquat_001", "core_landminepallof_001",
    "forearm_barbellwristcurl_001", "forearm_barbellreversewristcurl_001",
}


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    found = {e["id"] for e in data["exercises"] if e["id"] in BATCH21_IDS}
    missing = BATCH21_IDS - found
    if missing:
        raise SystemExit(f"Expected batch21 ids not found in file, aborting: {missing}")

    enriched_count = 0
    for e in data["exercises"]:
        if e["id"] in BATCH21_IDS:
            e.update(enrich_exercise(e))
            e.update(derive_taxonomy_groups(e))
            e.update(derive_connective_tissue(e))
            enriched_count += 1

    data["version"] = "5.36.0"
    data["schema_notes"] += (
        "\n\nv5.36 adds 19 new exercises (generate_batch21_missing_gym_staples.py, "
        "827 -> 846) closing genuine gaps found while auditing the FORGE S&C "
        "Template Libraries against exercises.json for v5.35: common gym "
        "staples that were referenced by name dozens to hundreds of times "
        "across the ten sport template libraries but had no exercises.json "
        "entry at all (a plain Barbell Shrug, a Dumbbell Lateral Raise, "
        "Standing/Seated Calf Raise Machine, Ab Crunch Machine, a Cable "
        "Triceps Pushdown / Overhead Cable Triceps Extension / EZ Bar Skull "
        "Crusher - exercises.json had no triceps pushdown/extension family "
        "at all before this, Preacher Curl Machine, Triceps Dip Machine, "
        "Assisted Pull-Up Machine, a bilateral Barbell Hip Thrust / Hip "
        "Thrust Machine / Cable Glute Kickback - only single-leg hip thrust "
        "variants existed before, DB Seated Press, Trap Bar Squat, Landmine "
        "Pallof Press, and Barbell Wrist Curl / Reverse Wrist Curl - no "
        "wrist curl of any kind existed before, only the unrelated Wrist "
        "Roller). Six new, more accurate equipment strings were introduced "
        "for six of these (Calf Raise Machine, Ab Crunch Machine, Preacher "
        "Curl Machine, Triceps Dip Machine, Hip Thrust Machine, Assisted "
        "Pull-up Machine) and added to EQUIPMENT_CATEGORIES's Machines group "
        "in exercise_metadata.py. Every muscle/joint_stress/injuries_to_avoid/"
        "strength_requirements/sport_priority value was copied byte-for-byte "
        "from the single closest already-existing sibling exercise (named in "
        "each entry's comment in the generator script) rather than invented; "
        "every other field was generated through the same "
        "enrich_exercise()/derive_taxonomy_groups()/derive_connective_tissue() "
        "pipeline as the rest of the database. See "
        "scripts/generators/generate_batch21_missing_gym_staples.py for the "
        "full reasoning and scripts/data_ops/dedupe_and_rematch_v5_35.py for "
        "the audit that found these gaps."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Enriched {enriched_count} batch21 exercises. "
          f"Version bumped to {data['version']}.")


if __name__ == "__main__":
    main()

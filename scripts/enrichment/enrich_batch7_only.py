"""
enrich_batch7_only.py — one-off companion to generate_batch7_equipment_rehab.py.

Same reasoning as enrich_batch6_only.py: enrich ONLY the batch7 exercises
(by id), leave every pre-existing exercise byte-for-byte untouched, append
a new schema_notes entry and bump the version forward rather than
overwriting.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from backend.core.config import settings
from backend.services.exercise_metadata import enrich_exercise

SRC = settings.EXERCISES_JSON_PATH

BATCH7_IDS = {
    "battleropes_slams_001", "battleropes_circles_001",
    "rowingerg_steady_001", "rowingerg_sprint_001",
    "tacklebag_sprawl_001", "tacklebag_hipdrive_001",
    "captainschair_kneeraise_001", "captainschair_obliqueraise_001",
    "abwheel_standing_001", "abwheel_lateral_001",
    "yoke_statichold_001", "yoke_turncarry_001",
    "agilityladder_icky_001", "agilityladder_lateral_001",
    "buffalobar_deadlift_001", "buffalobar_bench_001",
    "tire_sledgehammer_001", "tire_jumpover_001",
    "conanswheel_hold_001", "conanswheel_halflap_001",
    "fingalsfingers_toss_001", "fingalsfingers_carry_001",
    "husafell_squat_001", "husafell_shouldercarry_001",
    "vsquat_singleleg_001", "vsquat_pause_001",
    "pendulum_singleleg_001", "pendulum_pause_001",
    "beltsquatmachine_march_001", "beltsquatmachine_splitsquat_001",
    "assaultbike_steady_001", "assaultbike_tabata_001",
    "trapbar_farmercarry_001", "trapbar_shrug_001",
    "hangboard_repeaters_001", "hangboard_onearm_001",
    "parallelbars_support_001", "parallelbars_walkingdip_001",
    "ezbar_reversecurl_001", "ezbar_uprightrow_001",
    "jumprope_highknees_001", "jumprope_singleleg_001",
    "reversehyper_pulse_001", "reversehyper_widestance_001",
    "sealrow_widegrip_001", "sealrow_pause_001",
    "camberedbar_bench_001", "camberedbar_row_001",
    "swissbar_floorpress_001", "swissbar_row_001",
    "keg_clean_001", "keg_shouldercarry_001",
    "lever_shoulderpress_001", "lever_pulldown_001",
    "neckharness_flexion_001", "neckharness_extension_001",
    "neckharness_lateral_001", "band_neckrotation_001",
    "bodyweight_chintuck_001", "bodyweight_prone_neckextension_001",
    "balanceboard_singleleg_001", "balanceboard_squat_001",
    "band_ankledorsiflexion_001", "band_ankleeversion_001",
    "band_ankleinversion_001", "bodyweight_singlelegcalfraise_001",
}


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    found = {e["id"] for e in data["exercises"] if e["id"] in BATCH7_IDS}
    missing = BATCH7_IDS - found
    if missing:
        raise SystemExit(f"Expected batch7 ids not found in file, aborting: {missing}")

    enriched_count = 0
    for e in data["exercises"]:
        if e["id"] in BATCH7_IDS:
            enrichment = enrich_exercise(e)
            e.update(enrichment)
            enriched_count += 1

    data["version"] = "5.8.0"
    data["schema_notes"] += (
        "\n\nv5.8 adds 66 new exercises (generate_batch7_equipment_rehab.py). "
        "Two things: (1) equipment depth - the 15 equipment types sitting at "
        "exactly 1 exercise and 12 sitting at exactly 2 each get +2, so every "
        "equipment type in the database now has at least 3 (most at least 4) "
        "instead of unlocking 1-2 repeats when picked. (2) rehab gap - querying "
        "is_rehab_candidate() (knowledge_graph.py) against the pre-batch7 file "
        "showed Neck had ZERO rehab-candidate exercises at any severity (no "
        "exercise trained Neck stability at a low enough difficulty to "
        "qualify) and Ankle had only 6 next to Shoulder/Hip/Knee's 50+. Added "
        "6 difficulty=2 Neck-stability exercises and 6 difficulty=2 "
        "Ankle-stability exercises - difficulty=2 is the ceiling "
        "is_rehab_candidate() enforces, and 30 + difficulty*8 = 46 clears the "
        "40 stability-quality floor the joint_stress loop awards, so both "
        "joints have real rehab candidates for the first time / at real "
        "depth. Two new equipment types (Neck Harness, Balance Board) were "
        "added for the rehab work, plus a new 'Rehab & Mobility' group in "
        "exercise_metadata.py's EQUIPMENT_CATEGORIES so they're grouped "
        "correctly in the equipment catalog instead of falling into 'Other'. "
        "Enriched through the same exercise_metadata.enrich_exercise() "
        "pipeline as the rest of the database, applied only to these 66 new "
        "ids (enrich_batch7_only.py), same reasoning as enrich_batch6_only.py "
        "for why. No pre-existing exercise or field was changed."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Enriched {enriched_count} batch7 exercises. "
          f"Version bumped to {data['version']}. "
          f"Total exercises in file: {len(data['exercises'])}.")


if __name__ == "__main__":
    main()

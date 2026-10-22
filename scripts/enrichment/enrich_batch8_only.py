"""
enrich_batch8_only.py — one-off companion to generate_batch8_equipment_depth.py.

Same reasoning as enrich_batch6_only.py / enrich_batch7_only.py: enrich ONLY
the batch8 exercises (by id), leave every pre-existing exercise byte-for-byte
untouched, append a new schema_notes entry and bump the version forward
rather than overwriting.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from backend.services.exercise_metadata import enrich_exercise

SRC = ROOT / "data" / "exercises.json"

BATCH8_IDS = {
    "balanceboard_reach_001", "balanceboard_plank_001",
    "wrestlingdummy_doubleleg_001", "wrestlingdummy_sprawl_001",
    "sled_row_001", "sled_lateraldrag_001",
    "battleropes_snake_001", "battleropes_jumpingwaves_001",
    "rowingerg_2ktt_001", "rowingerg_pyramid_001",
    "tacklebag_choptackle_001", "tacklebag_wrapdrive_001",
    "captainschair_windshield_001", "captainschair_lhold_001",
    "hacksquat_singleleg_001", "hacksquat_pause_001",
    "legextension_partial_001", "legextension_slowecc_001",
    "pecdeck_isohold_001", "pecdeck_partialsqueeze_001",
    "ssb_carry_001", "ssb_boxsquat_001",
    "abwheel_pike_001", "abwheel_singlearm_001",
    "trx_fallout_001", "trx_hamstringcurl_001",
    "weightedvest_pushup_001", "weightedvest_boxjump_001",
    "yoke_march_001", "yoke_speedcarry_001",
    "agilityladder_crossover_001", "agilityladder_2insprint_001",
    "heavybag_elbowstrikes_001", "heavybag_footwork_001",
    "squatrack_pinpull_001", "squatrack_spotopress_001",
    "beltsquat_lateralstep_001", "beltsquat_goodmorning_001",
    "hyperextbench_singleleg_001", "hyperextbench_obliqueraise_001",
    "buffalobar_press_001", "buffalobar_goodmorning_001",
    "logbar_bearhug_001", "logbar_frontsquat_001",
    "atlasstone_carry_001", "atlasstone_maxheight_001",
    "tire_drag_001", "tire_bearcrawlpush_001",
    "conanswheel_fulllap_001", "conanswheel_press_001",
    "fingalsfingers_relayflip_001", "fingalsfingers_press_001",
    "husafell_overbar_001", "husafell_zercher_001",
    "vsquat_widestance_001", "vsquat_15rep_001",
    "pendulum_deficit_001", "pendulum_tempoecc_001",
    "chestpress_decline_001", "chestpress_isohold_001",
    "shoulderpress_partial_001", "shoulderpress_arnoldstyle_001",
    "highrow_closegrip_001", "highrow_isohold_001",
    "beltsquatmachine_lateralstep_001", "beltsquatmachine_pulse_001",
    "neckharness_rotation_001", "neckharness_weightednod_001",
    "farmerhandles_suitcase_001", "farmerhandles_overheadcarry_001",
    "assaultbike_reversepedal_001", "assaultbike_emom_001",
    "trapbar_deficit_001", "trapbar_row_001",
    "hangboard_weighteddeadhang_001", "hangboard_pullup_001",
    "parallelbars_straddle_001", "parallelbars_muscleuptransition_001",
    "legcurl_isohold_001", "legcurl_stretchpartial_001",
    "ezbar_preachercurl_001", "ezbar_closegripbench_001",
    "ghd_obliqueraise_001", "ghd_pronelegraise_001",
    "jumprope_boxerskip_001", "jumprope_crisscross_001",
    "reversehyper_bentknee_001", "reversehyper_rotational_001",
    "sealrow_closegrip_001", "sealrow_isohold_001",
    "camberedbar_press_001", "camberedbar_frontsquat_001",
    "axlebar_row_001", "axlebar_farmercarry_001",
    "swissbar_press_001", "swissbar_closegripbench_001",
    "keg_squat_001", "keg_bearhug_001",
    "lever_legpress_001", "lever_squat_001",
}


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    found = {e["id"] for e in data["exercises"] if e["id"] in BATCH8_IDS}
    missing = BATCH8_IDS - found
    if missing:
        raise SystemExit(f"Expected batch8 ids not found in file, aborting: {missing}")

    enriched_count = 0
    for e in data["exercises"]:
        if e["id"] in BATCH8_IDS:
            enrichment = enrich_exercise(e)
            e.update(enrichment)
            enriched_count += 1

    data["version"] = "5.9.0"
    data["schema_notes"] += (
        "\n\nv5.9 adds 100 new exercises (generate_batch8_equipment_depth.py). "
        "Closes out the equipment-depth pass batch6/7 started: the 50 "
        "equipment types still sitting at only 3 or 4 exercises (mostly "
        "single-purpose machines, specialty bars, strongman implements, and "
        "conditioning tools batch6's general-machine pass and batch7's "
        "1-2-count/rehab pass didn't reach) each get +2, following the exact "
        "same per-equipment pattern as those two batches. No equipment type "
        "in the database is under 5 exercises anymore. Enriched through the "
        "same exercise_metadata.enrich_exercise() pipeline as the rest of "
        "the database, applied only to these 100 new ids "
        "(enrich_batch8_only.py), same reasoning as enrich_batch6/7_only.py "
        "for why. No pre-existing exercise or field was changed."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Enriched {enriched_count} batch8 exercises. "
          f"Version bumped to {data['version']}. "
          f"Total exercises in file: {len(data['exercises'])}.")


if __name__ == "__main__":
    main()

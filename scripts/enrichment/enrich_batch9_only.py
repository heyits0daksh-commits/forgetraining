"""
enrich_batch9_only.py — one-off companion to generate_batch9_equipment_depth2.py.

Same reasoning as enrich_batch6/7/8_only.py: enrich ONLY the batch9
exercises (by id), leave every pre-existing exercise byte-for-byte
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

BATCH9_IDS = {
    "abwheel_feetelevated_001", "abwheel_reversecrunch_001",
    "agilityladder_hipturns_001", "agilityladder_backwardrun_001",
    "atlasstone_medley_001", "atlasstone_statichold_001",
    "balanceboard_lateralshift_001", "balanceboard_rotationalreach_001",
    "battleropes_squatwaves_001", "battleropes_slamintervals_001",
    "beltsquat_pulse_001", "beltsquat_singlelegrdl_001",
    "beltsquatmachine_singleleg_001", "beltsquatmachine_goodmorning_001",
    "heavybag_clinchwork_001", "heavybag_lowkicks_001",
    "buffalobar_frontsquat_001", "buffalobar_row_001",
    "captainschair_reversecrunch_001", "captainschair_sidekneeraise_001",
    "chestpress_partial_001", "chestpress_explosive_001",
    "conanswheel_bearhugcarry_001", "conanswheel_speedlap_001",
    "fingalsfingers_drag_001", "fingalsfingers_bearhuglift_001",
    "hacksquat_15rep_001", "hacksquat_deficit_001",
    "highrow_neutralgrip_001", "highrow_partialsqueeze_001",
    "husafell_statichold_001", "husafell_lungecarry_001",
    "hyperextbench_isohold_001", "hyperextbench_rotationaltwist_001",
    "legextension_15rep_001", "legextension_pulse_001",
    "legpress_pause_001", "legpress_highfoot_001",
    "logbar_pushpress_001", "logbar_row_001",
    "neckharness_isohold_001", "neckharness_diagonalflexion_001",
    "pecdeck_hightolow_001", "pecdeck_pulse_001",
    "pendulum_15rep_001", "pendulum_narrowstance_001",
    "rowingerg_100msprint_001", "rowingerg_10kendurance_001",
    "ssb_splitsquat_001", "ssb_deadstartsquat_001",
    "seatedrow_lowhandle_001", "seatedrow_isohold_001",
    "shoulderpress_widegrip_001", "shoulderpress_isohold_001",
    "sled_harnessdrag_001", "sled_heavypush_001",
    "squatrack_pinpress_001", "squatrack_pinsquathold_001",
    "trx_yfly_001", "trx_chestpress_001",
    "tacklebag_reactionread_001", "tacklebag_lowdrivefinish_001",
    "tire_lateralhopovers_001", "tire_stepovers_001",
    "vsquat_deficit_001", "vsquat_tempoecc_001",
    "weightedvest_sprint_001", "weightedvest_dip_001",
    "wrestlingdummy_singlelegfinish_001", "wrestlingdummy_snapdown_001",
    "yoke_lateralcarry_001", "yoke_racksupporthold_001",
}


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    found = {e["id"] for e in data["exercises"] if e["id"] in BATCH9_IDS}
    missing = BATCH9_IDS - found
    if missing:
        raise SystemExit(f"Expected batch9 ids not found in file, aborting: {missing}")

    enriched_count = 0
    for e in data["exercises"]:
        if e["id"] in BATCH9_IDS:
            enrichment = enrich_exercise(e)
            e.update(enrichment)
            enriched_count += 1

    data["version"] = "5.10.0"
    data["schema_notes"] += (
        "\n\nv5.10 adds 72 new exercises (generate_batch9_equipment_depth2.py). "
        "Follow-up to batch8: the 36 equipment types batch8 left sitting "
        "exactly at the 5-exercise floor (isolation machines, strongman "
        "implements, and combat/conditioning tools) each get +2 more, same "
        "per-equipment pattern as batch6/7/8. Every equipment type touched "
        "by this batch is now at 7 exercises. Enriched through the same "
        "exercise_metadata.enrich_exercise() pipeline as the rest of the "
        "database, applied only to these 72 new ids (enrich_batch9_only.py), "
        "same reasoning as enrich_batch6/7/8_only.py for why. No "
        "pre-existing exercise or field was changed."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Enriched {enriched_count} batch9 exercises. "
          f"Version bumped to {data['version']}. "
          f"Total exercises in file: {len(data['exercises'])}.")


if __name__ == "__main__":
    main()

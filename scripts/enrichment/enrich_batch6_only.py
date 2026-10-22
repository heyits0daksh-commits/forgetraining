"""
enrich_batch6_only.py — one-off companion to generate_batch6_thin_equipment.py.

enrich_exercises.py (the general-purpose migration script) re-derives
movement-analysis/athletic-quality fields for EVERY exercise in the file
and unconditionally resets data["version"] to "4.0.0" and overwrites
data["schema_notes"] with the v4.0-only note — appropriate the first time
it ever ran, but re-running it today would (a) silently drift a handful of
already-enriched exercises' fields, since enrich_exercise's stability
computation isn't perfectly idempotent when fed its own prior output, and
(b) blow away the v4.0-5.6 schema_notes history and bump the version
backwards. Neither is acceptable for a routine "add more exercises" pass.

This script instead enriches ONLY the batch6 exercises (identified by id
prefix, matching every id generate_batch6_thin_equipment.py just wrote),
leaves all 447 pre-existing exercises byte-for-byte untouched, and appends
a new schema_notes entry / bumps version forward instead of overwriting.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from backend.core.config import settings
from backend.services.exercise_metadata import enrich_exercise

SRC = settings.EXERCISES_JSON_PATH

BATCH6_IDS = {
    "cable_triceppushdown_001", "cable_bicepcurl_001", "cable_facepull_001",
    "cable_woodchopper_001", "cable_lateralraise_001", "cable_chestfly_001",
    "cable_overheadtricep_001", "cable_pallofpress_001",
    "latpulldown_vbar_001", "latpulldown_reversegrip_001", "latpulldown_straightarm_001",
    "legpress_narrow_001", "legpress_wide_001", "legpress_calfpress_001",
    "legcurl_standing_001", "legcurl_singleleg_001",
    "legext_singleleg_001", "legext_isohold_001",
    "seatedrow_closegrip_001", "seatedrow_neutralgrip_001", "seatedrow_highhandle_001",
    "chest_press_incline_machine_001", "chest_press_singlearm_machine_001",
    "shoulder_press_singlearm_machine_001", "shoulder_press_neutralgrip_machine_001",
    "pecdeck_reverse_001", "pecdeck_singlearm_001",
    "smith_row_001", "smith_reverselunge_001", "smith_rdl_001", "smith_inclinepress_001",
    "hacksquat_narrow_001", "hacksquat_wide_001",
    "high_row_machine_singlearm_001", "high_row_machine_widegrip_001",
    "band_facepull_001", "band_lateralwalk_001", "band_overheadtricep_001",
    "band_row_001", "band_deadlift_001", "band_woodchopper_001",
    "medball_situpthrow_001", "medball_russiantwist_001", "medball_wallball_001",
    "medball_pushup_001",
}


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    found = {e["id"] for e in data["exercises"] if e["id"] in BATCH6_IDS}
    missing = BATCH6_IDS - found
    if missing:
        raise SystemExit(f"Expected batch6 ids not found in file, aborting: {missing}")

    enriched_count = 0
    for e in data["exercises"]:
        if e["id"] in BATCH6_IDS:
            enrichment = enrich_exercise(e)
            e.update(enrichment)
            enriched_count += 1

    data["version"] = "5.7.0"
    data["schema_notes"] += (
        "\n\nv5.7 adds 45 new exercises (generate_batch6_thin_equipment.py) to "
        "the 14 machine/cable/band/medicine-ball equipment types that were "
        "thinnest relative to how common they are in a real commercial gym "
        "(Cable Machine 3->11, Lat Pulldown 3->6, Leg Press 2->5, Leg Curl "
        "2->4, Leg Extension 1->3, Seated Row 2->5, Chest Press Machine 1->3, "
        "Shoulder Press Machine 1->3, Pec Deck 1->3, Smith Machine 3->7, Hack "
        "Squat Machine 1->3, High Row Machine 1->3, Resistance Band 6->12, "
        "Medicine Ball 4->8). Enriched through the same exercise_metadata."
        "enrich_exercise() pipeline as the rest of the database, but applied "
        "only to these 45 new ids (enrich_batch6_only.py) rather than "
        "re-running enrich_exercises.py over the whole file, since that "
        "script's version/schema_notes overwrite would have reverted this "
        "file's version history and its re-derivation is not perfectly "
        "idempotent on exercises that were already enriched. No pre-existing "
        "exercise or field was changed."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Enriched {enriched_count} batch6 exercises. "
          f"Version bumped to {data['version']}. "
          f"Total exercises in file: {len(data['exercises'])}.")


if __name__ == "__main__":
    main()

"""
enrich_batch12_only.py — one-off companion to
generate_batch12_bodyweight_category_coverage.py. Same reasoning as
enrich_batch6/7/8/9/10/11_only.py: enrich ONLY the batch12 exercises (by
id), leave every pre-existing exercise byte-for-byte untouched, append a
new schema_notes entry and bump the version forward rather than
overwriting.
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
from backend.services.exercise_metadata import enrich_exercise

BATCH12_IDS = {
    "burpee_001", "mountain_climber_001",
    "bear_crawl_001", "crabwalk_carry_001",
    "doorframe_deadhang_001", "fingertip_pushup_hold_001",
    "clap_pushup_001", "power_skip_001",
    "standing_woodchop_bw_001", "shadow_pivot_drill_001",
}


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    found = {e["id"] for e in data["exercises"] if e["id"] in BATCH12_IDS}
    missing = BATCH12_IDS - found
    if missing:
        raise SystemExit(f"Expected batch12 ids not found in file, aborting: {missing}")

    enriched_count = 0
    for e in data["exercises"]:
        if e["id"] in BATCH12_IDS:
            enrichment = enrich_exercise(e)
            e.update(enrichment)
            enriched_count += 1

    data["version"] = "5.14.0"
    data["schema_notes"] += (
        "\n\nv5.14 adds 10 new exercises (generate_batch12_bodyweight_category_"
        "coverage.py) closing the largest bodyweight gap found in the batch10/11 "
        "investigation: a full audit of equipment=Bodyweight against every category "
        "in the file showed FIVE categories with ZERO bodyweight exercises at all - "
        "Carry, Conditioning, Grip, Power, and Rotational - despite every one of "
        "those categories being well-stocked for every other equipment type "
        "(Conditioning alone had 33 exercises, none bodyweight) and despite every "
        "SPLIT_TEMPLATES day slot in program_builder.py including several of these "
        "categories. A pure equipment_available=['Bodyweight'] athlete wasn't just "
        "getting repeats (batch10) or a thin pulling pool (batch11) - for these 5 "
        "categories they were getting nothing at all, since generate_session's "
        "category filter had an empty pool to search. Added 2 exercises per "
        "category: Burpee/Mountain Climbers (Conditioning), Bear Crawl/Crab Walk "
        "Carry (Carry), Doorframe Dead Hang/Fingertip Push-Up Hold (Grip), Clap "
        "Push-Up/Bodyweight Power Skip (Power), Standing Bodyweight Woodchopper/"
        "Shadow Rotational Pivot Drill (Rotational) - standard, commonly-coached "
        "bodyweight substitutes for each category's training purpose, spanning "
        "Beginner through Advanced. Enriched through the same "
        "exercise_metadata.enrich_exercise() pipeline as the rest of the database, "
        "applied only to these 10 new ids (enrich_batch12_only.py), same reasoning "
        "as enrich_batch6/7/8/9/10/11_only.py for why. No pre-existing exercise or "
        "field was changed."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Enriched {enriched_count} batch12 exercises. "
          f"Version bumped to {data['version']}. "
          f"Total exercises in file: {len(data['exercises'])}.")


if __name__ == "__main__":
    main()

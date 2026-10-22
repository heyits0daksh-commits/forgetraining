"""
enrich_batch11_only.py — one-off companion to
generate_batch11_bodyweight_pull_depth.py. Same reasoning as
enrich_batch6/7/8/9/10_only.py: enrich ONLY the batch11 exercises (by id),
leave every pre-existing exercise byte-for-byte untouched (the 2 regression
list patches batch11's generator already made to ropeclimb_pull_001 /
inverted_table_row_001 are plain list edits, not re-enrichment, so those
two are intentionally left out of this script's re-enrich pass), append a
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

BATCH11_IDS = {
    "scapular_wall_slide_001", "doorframe_pullup_001",
    "prone_ytw_raise_001", "doorframe_row_001",
}


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    found = {e["id"] for e in data["exercises"] if e["id"] in BATCH11_IDS}
    missing = BATCH11_IDS - found
    if missing:
        raise SystemExit(f"Expected batch11 ids not found in file, aborting: {missing}")

    enriched_count = 0
    for e in data["exercises"]:
        if e["id"] in BATCH11_IDS:
            enrichment = enrich_exercise(e)
            e.update(enrichment)
            enriched_count += 1

    data["version"] = "5.13.0"
    data["schema_notes"] += (
        "\n\nv5.13 adds 4 new exercises (generate_batch11_bodyweight_pull_depth.py) "
        "closing a second gap found while investigating the batch10 variety bug: "
        "category=Horizontal Pull and category=Vertical Pull under "
        "equipment=Bodyweight had exactly ONE exercise each in the whole database "
        "(inverted_table_row_001, needs a table; ropeclimb_pull_001, needs a rope AND "
        "gates on strength_requirements.pullups=8) - so a genuinely zero-equipment "
        "athlete had no rotation in either pulling pattern, and Vertical Pull had no "
        "entry point below an advanced, pull-up-dependent exercise at all. Added "
        "Scapular Wall Slide (Vertical Pull, difficulty 1, the missing beginner "
        "on-ramp), Doorframe Pull-Up / Ledge Grip (Vertical Pull, difficulty 3, "
        "pullups-gated at 2 not 8), Prone Y-T-W Raise (Horizontal Pull, difficulty 1, "
        "floor only), and Doorframe Row (Horizontal Pull, difficulty 2). Wired into "
        "the existing progression/regression DAG in both directions "
        "(ropeclimb_pull_001 and inverted_table_row_001 now list the new easier "
        "variants as regressions). Enriched through the same "
        "exercise_metadata.enrich_exercise() pipeline as the rest of the database, "
        "applied only to these 4 new ids (enrich_batch11_only.py), same reasoning as "
        "enrich_batch6/7/8/9/10_only.py for why. No pre-existing exercise field was "
        "changed other than those two regressions lists."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Enriched {enriched_count} batch11 exercises. "
          f"Version bumped to {data['version']}. "
          f"Total exercises in file: {len(data['exercises'])}.")


if __name__ == "__main__":
    main()

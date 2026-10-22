"""
enrich_batch14_only.py — one-off companion to
generate_batch14_ring_skill_completion.py. Same reasoning as
enrich_batch6-13_only.py: enrich ONLY the batch14 exercises (by id), leave
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
from backend.services.exercise_metadata import enrich_exercise

BATCH14_IDS = {
    "ring_hspu_001", "ring_vsit_001",
    "ring_muscleuptransition_001", "victorian_cross_001",
}


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    found = {e["id"] for e in data["exercises"] if e["id"] in BATCH14_IDS}
    missing = BATCH14_IDS - found
    if missing:
        raise SystemExit(f"Expected batch14 ids not found in file, aborting: {missing}")

    enriched_count = 0
    for e in data["exercises"]:
        if e["id"] in BATCH14_IDS:
            enrichment = enrich_exercise(e)
            e.update(enrichment)
            enriched_count += 1

    data["version"] = "5.16.0"
    data["schema_notes"] += (
        "\n\nv5.16 adds 4 new equipment=Rings exercises (generate_batch14_"
        "ring_skill_completion.py) closing the last empty progression slots "
        "in the ring skill tree: Ring Handstand Push-Up (Ring Handstand had "
        "no progression built on it), Ring V-Sit (Ring L-Sit Hold had no "
        "harder static-hold skill past it), Ring Muscle-Up Transition Drill "
        "(every other muscle-up variant had a dedicated transition drill "
        "except the ring version), and Victorian Cross (the standard "
        "gymnastics-strength skill sitting between Iron Cross and Maltese "
        "Cross, previously the file's two hardest ring skills with no step "
        "between them). Five pre-existing ring exercises' progressions/"
        "regressions lists were spliced (not replaced) to link these in; no "
        "other field on any pre-existing exercise was touched. Enriched "
        "through the same exercise_metadata.enrich_exercise() pipeline as "
        "the rest of the database, applied only to these 4 new ids "
        "(enrich_batch14_only.py), same reasoning as enrich_batch6-13_only.py "
        "for why."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Enriched {enriched_count} batch14 exercises. "
          f"Version bumped to {data['version']}. "
          f"Total exercises in file: {len(data['exercises'])}.")


if __name__ == "__main__":
    main()

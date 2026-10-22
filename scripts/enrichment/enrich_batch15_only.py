"""
enrich_batch15_only.py — one-off companion to
generate_batch15_final_chain_gaps.py. Same reasoning as
enrich_batch6-14_only.py: enrich ONLY the batch15 exercises (by id), leave
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

BATCH15_IDS = {
    "one_arm_pushup_001", "weighted_pistol_squat_001", "legless_ropeclimb_001",
}


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    found = {e["id"] for e in data["exercises"] if e["id"] in BATCH15_IDS}
    missing = BATCH15_IDS - found
    if missing:
        raise SystemExit(f"Expected batch15 ids not found in file, aborting: {missing}")

    enriched_count = 0
    for e in data["exercises"]:
        if e["id"] in BATCH15_IDS:
            enrichment = enrich_exercise(e)
            e.update(enrichment)
            enriched_count += 1

    data["version"] = "5.17.0"
    data["schema_notes"] += (
        "\n\nv5.17 is a final gap-closing audit of every calisthenics-"
        "accessible equipment type (Bodyweight, Pull-up Bar, Parallel Bars, "
        "Rings, Resistance Band, Suspension Trainer) for dead-end progression "
        "chains, filtering out legitimate dead ends (accessory/isolation "
        "moves, sport drills, conditioning work) to find 3 real gaps: "
        "One-Arm Push-Up was missing from the database entirely despite both "
        "Archer Push-Up and Archer Ring Push-Up dead-ending with nothing to "
        "progress to; Pistol Squat had no progression (added Weighted Pistol "
        "Squat); Rope Climb Pull had no progression (added Legless Rope "
        "Climb). Also spliced two pre-existing exercises that were sitting "
        "disconnected from an obvious neighbor already in the file: Ring Dip "
        "-> Ring Archer Dip, and Archer Ring Pull-Up -> One-Arm Pull-Up (same "
        "as the existing bar Archer Pull-Up already progressing there). No "
        "other field on any pre-existing exercise was touched. Enriched "
        "through the same exercise_metadata.enrich_exercise() pipeline as "
        "the rest of the database, applied only to the 3 new ids "
        "(enrich_batch15_only.py), same reasoning as enrich_batch6-14_only.py "
        "for why."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Enriched {enriched_count} batch15 exercises. "
          f"Version bumped to {data['version']}. "
          f"Total exercises in file: {len(data['exercises'])}.")


if __name__ == "__main__":
    main()

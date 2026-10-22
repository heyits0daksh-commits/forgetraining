"""
enrich_batch13_only.py — one-off companion to
generate_batch13_calisthenics_skill_bridge.py. Same reasoning as
enrich_batch6-12_only.py: enrich ONLY the batch13 exercises (by id), leave
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

BATCH13_IDS = {
    "wall_walk_001", "tiger_bend_pushup_001",
    "pseudo_planche_pushup_001", "frog_stand_001",
}


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    found = {e["id"] for e in data["exercises"] if e["id"] in BATCH13_IDS}
    missing = BATCH13_IDS - found
    if missing:
        raise SystemExit(f"Expected batch13 ids not found in file, aborting: {missing}")

    enriched_count = 0
    for e in data["exercises"]:
        if e["id"] in BATCH13_IDS:
            enrichment = enrich_exercise(e)
            e.update(enrichment)
            enriched_count += 1

    data["version"] = "5.15.0"
    data["schema_notes"] += (
        "\n\nv5.15 adds 4 new bodyweight-only exercises (generate_batch13_"
        "calisthenics_skill_bridge.py) closing gaps in the pure-calisthenics "
        "skill progressions so a Pull-up Bar + Parallel Bars (or literally "
        "zero-equipment) athlete has a complete beginner-to-elite path: Wall "
        "Walk (bridges Decline Pike Push-Up to Wall-Supported Handstand "
        "Push-Up, which previously jumped straight from diff 3 to diff 4 with "
        "no intermediate skill step), Tiger Bend Push-Up (Freestanding HSPU "
        "previously had no progression at all beyond it), Pseudo Planche "
        "Push-Up (Planche Lean previously had no regression, so there was no "
        "on-ramp into planche work from ordinary push-ups), and Frog Stand / "
        "Crow Pose (a second, easier balance-based entry into the planche "
        "line alongside Planche Lean). Seven pre-existing exercises' "
        "progressions/regressions lists were spliced (not replaced) to link "
        "these in; no other field on any pre-existing exercise was touched. "
        "Enriched through the same exercise_metadata.enrich_exercise() "
        "pipeline as the rest of the database, applied only to these 4 new "
        "ids (enrich_batch13_only.py), same reasoning as "
        "enrich_batch6-12_only.py for why."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Enriched {enriched_count} batch13 exercises. "
          f"Version bumped to {data['version']}. "
          f"Total exercises in file: {len(data['exercises'])}.")


if __name__ == "__main__":
    main()

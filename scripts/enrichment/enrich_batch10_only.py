"""
enrich_batch10_only.py — one-off companion to
generate_batch10_bodyweight_skill_variety.py. Same reasoning as
enrich_batch6/7/8/9_only.py: enrich ONLY the batch10 exercises (by id),
leave every pre-existing exercise byte-for-byte untouched, append a new
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

BATCH10_IDS = {
    "shadow_uchikomi_001", "sprawl_sprint_001", "bridge_hipescape_001",
    "shadow_combo_footwork_001", "obstacle_circuit_001",
}


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    found = {e["id"] for e in data["exercises"] if e["id"] in BATCH10_IDS}
    missing = BATCH10_IDS - found
    if missing:
        raise SystemExit(f"Expected batch10 ids not found in file, aborting: {missing}")

    enriched_count = 0
    for e in data["exercises"]:
        if e["id"] in BATCH10_IDS:
            enrichment = enrich_exercise(e)
            e.update(enrichment)
            enriched_count += 1

    data["version"] = "5.12.0"
    data["schema_notes"] += (
        "\n\nv5.12 adds 5 new exercises (generate_batch10_bodyweight_skill_variety.py) "
        "fixing a reported bug where equipment=Bodyweight athletes saw the exact same "
        "Skill/Technical exercise (usually 'Wrestler's Neck Bridge' for grappling sports, "
        "or 'Shadow Boxing Rounds' for striking sports) on every day-tab and every week-tab "
        "of a generated program, with an identical prescription each time. Root cause: "
        "category=Sport Specific x equipment=Bodyweight only had 3 exercises total in the "
        "whole database (neck_bridge_001, ruck_march_001, shadow_boxing_001), and for most "
        "sports one of those three outscored the other two by well outside "
        "progression_engine._VARIETY_BAND's 12% tolerance - so _pick_with_variety had a "
        "single candidate to 'choose' between, every single call, for every week and every "
        "day-label. Added Shadow Uchikomi Entries (No Partner), Sprawl-to-Sprint, "
        "Bridge-to-Hip-Escape Flow, Shadow Combination Footwork Drilling, and Bodyweight "
        "Functional Obstacle Circuit - all named or directly implied by the manual's own "
        "Sport-Specific/Grip/Core exercise banks - with sport_priority scores placed inside "
        "the relevant sports' existing 12% variety band (not above it, which would just "
        "crown a new lone winner) so _pick_with_variety now has 2-3 genuinely tied "
        "candidates to rotate between for every combat/contact sport in the manual. "
        "Enriched through the same exercise_metadata.enrich_exercise() pipeline as the rest "
        "of the database, applied only to these 5 new ids (enrich_batch10_only.py), same "
        "reasoning as enrich_batch6/7/8/9_only.py for why. No pre-existing exercise or field "
        "was changed."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Enriched {enriched_count} batch10 exercises. "
          f"Version bumped to {data['version']}. "
          f"Total exercises in file: {len(data['exercises'])}.")


if __name__ == "__main__":
    main()

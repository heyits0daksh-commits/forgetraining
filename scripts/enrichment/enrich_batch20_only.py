"""
enrich_batch20_only.py — one-off companion to
generate_batch20_rehab_mobility.py. Same reasoning as enrich_batch6-15_only.py:
enrich ONLY the batch20 exercises (by id), leave every pre-existing exercise
byte-for-byte untouched, append a new schema_notes entry and bump the
version forward rather than overwriting.
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

BATCH20_IDS = {
    "hamstring_wallisohold_001", "hamstring_bandcurl_seated_001",
    "quad_isoset_seated_001", "quad_bandtermext_001",
    "hipabd_sidelying_001", "hipabd_clamshell_001",
    "hipabd_bandstanding_001", "hipabd_bandmonsterwalk_001",
    "chest_wallisopress_001", "chest_bandstandingpress_001",
    "biceps_isoneutralhold_001", "biceps_bandcurl_light_001",
    "triceps_wallisopress_001", "triceps_bandext_light_001",
    "back_bandrow_isohold_001", "back_prone_ytw_001",
    "back_birddog_001", "back_gentlesupermanhold_001",
    "postop_marchinplace_001", "postop_supportedsit2stand_001",
}


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    found = {e["id"] for e in data["exercises"] if e["id"] in BATCH20_IDS}
    missing = BATCH20_IDS - found
    if missing:
        raise SystemExit(f"Expected batch20 ids not found in file, aborting: {missing}")

    enriched_count = 0
    for e in data["exercises"]:
        if e["id"] in BATCH20_IDS:
            enrichment = enrich_exercise(e)
            e.update(enrichment)
            enriched_count += 1

    data["version"] = "5.16.0"
    data["schema_notes"] += (
        "\n\nv5.16 adds 20 new rehab & mobility exercises "
        "(generate_batch20_rehab_mobility.py, 808 -> 828) closing the "
        "biggest early-recovery gap in the database: the hip abductor group "
        "(Gluteus Medius, Gluteus Minimus, Tensor Fasciae Latae) had almost "
        "no difficulty-1 exercises and Gluteus Minimus/TFL had none at any "
        "difficulty, so REHAB_STAGE_CEILING's early_recovery stage "
        "(injury_taxonomy.py, difficulty <= 1) had nothing to prescribe for "
        "a hip abductor strain. Also adds difficulty-1 isometric/activation "
        "work for Hamstrings, Quadriceps, Pectoralis Major, Biceps Brachii/"
        "Brachialis (which had zero difficulty-1 entries), Triceps Brachii, "
        "and the back group (Latissimus Dorsi, Rhomboids, Trapezius, "
        "Erector Spinae via Bird Dog / Prone Y-T-W / gentle Superman hold), "
        "plus two general post-surgical reconditioning drills (Standing "
        "March in Place, Supported Sit-to-Stand). Every injuries_to_avoid "
        "tag is the exact Grade I (Mild) strain name from "
        "injury_taxonomy.py's MUSCLE_GROUPS strain table, so these "
        "register as rehab-safe early-stage candidates in "
        "classify_exercise_safety() / resolve_rehab_stage() the same way "
        "every other muscle strain already does. Enriched through the same "
        "exercise_metadata.enrich_exercise() pipeline as the rest of the "
        "database, applied only to the 20 new ids (enrich_batch20_only.py), "
        "same reasoning as enrich_batch6-15_only.py for why."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Enriched {enriched_count} batch20 exercises. "
          f"Version bumped to {data['version']}. "
          f"Total exercises in file: {len(data['exercises'])}.")


if __name__ == "__main__":
    main()

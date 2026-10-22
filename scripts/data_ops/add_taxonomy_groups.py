"""
add_taxonomy_groups.py — one-time (re-runnable) migration that adds the
v5.18 grouping-taxonomy fields to every exercise in exercises.json:
is_compound, is_olympic_lift, push_pull, upper_lower, chain_emphasis.

Purely additive, same contract as enrich_exercises.py: every existing key on
every exercise is preserved byte-for-byte. Derivation logic lives in
exercise_metadata.derive_taxonomy_groups() (single source of truth) — see
that module for the reasoning behind each field. Safe to re-run any time new
exercises are added to the file.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.core.config import settings
from backend.services.exercise_metadata import derive_taxonomy_groups

SRC = settings.EXERCISES_JSON_PATH
BACKUP = settings.BACKUP_DIR / "exercises_pre_taxonomy_groups_backup.json"


def main():
    settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)

    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    for ex in data["exercises"]:
        ex.update(derive_taxonomy_groups(ex))

    data["version"] = "5.18.0"
    data["schema_notes"] += (
        "\n\nv5.18 adds a five-field grouping taxonomy to every exercise — "
        "is_compound (bool), is_olympic_lift (bool), push_pull "
        "('Push'/'Pull'/null), upper_lower ('Upper'/'Lower'/'Full Body'/"
        "'Core'), and chain_emphasis ('Posterior'/'Anterior'/'Mixed') — so "
        "the library and session builder can filter/group by these axes "
        "directly. All derived from existing fields (name, category, "
        "movement_pattern, primary/secondary_muscles) via "
        "exercise_metadata.derive_taxonomy_groups(); no hand-typed values. "
        "is_compound corrects for category NOT tracking compound vs. "
        "isolation (e.g. curls and pushdowns share a category with "
        "genuinely multi-joint lifts) by checking movement-name keywords "
        "plus a single-primary-muscle/no-secondary/no-stabilizer fallback. "
        "is_olympic_lift flags Clean/Snatch/Jerk and their standard "
        "training variants, excluding the 5 exercises that only borrow the "
        "clean/snatch grip on an ordinary squat/deadlift/RDL. push_pull is "
        "null (not just Push/Pull) for patterns it doesn't apply to, e.g. "
        "Squat/Hinge/Carry. chain_emphasis weights primary muscles 2x vs. "
        "secondary 1x and requires a >=1.3x lean to call Posterior/"
        "Anterior, otherwise Mixed. No other field changed."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Tagged {len(data['exercises'])} exercises. Backup written to {BACKUP}.")


if __name__ == "__main__":
    main()

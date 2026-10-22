"""
add_connective_tissue_biomechanics.py — one-time (re-runnable) migration
that adds the v5.19 connective-tissue & phase-biomechanics fields to every
exercise in exercises.json: tendons_loaded, ligaments_stressed,
muscle_action_by_phase, biomechanics_notes.

Purely additive, same contract as enrich_exercises.py / add_taxonomy_groups.py:
every existing key on every exercise is preserved byte-for-byte. Derivation
logic lives in exercise_metadata.derive_connective_tissue() (single source
of truth) — see that module's section-7 docstring for the reasoning.
Safe to re-run any time new exercises are added to the file.
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.core.config import settings
from backend.services.exercise_metadata import derive_connective_tissue

SRC = settings.EXERCISES_JSON_PATH
BACKUP = settings.BACKUP_DIR / "exercises_pre_connective_tissue_backup.json"


def main():
    settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)

    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    for ex in data["exercises"]:
        ex.update(derive_connective_tissue(ex))

    data["version"] = "5.19.0"
    data["schema_notes"] += (
        "\n\nv5.19 adds exercise-specific connective-tissue & phase "
        "biomechanics to every exercise: tendons_loaded (which tendon "
        "transmits force at each joint in joint_stress, tagged prime_mover "
        "vs. stabilizer, push- vs. pull-tendon picked via the v5.18 "
        "push_pull field), ligaments_stressed (which ligament resists an "
        "unwanted motion at that joint - listed ONLY when this specific "
        "exercise's already-derived tissue-demand flags, from "
        "derive_tissue_demands(), imply that motion is actually present, "
        "e.g. ACL only appears for shear/impact/unilateral-loaded knee "
        "work, not every knee exercise), muscle_action_by_phase (prime "
        "movers/synergists/stabilizers split across Isometric Hold, or "
        "Eccentric Preload -> Concentric Drive for SSC movements, or "
        "Eccentric -> Concentric for standard biphasic lifts, keyed off "
        "force_type), and biomechanics_notes (a generated prose summary "
        "of the above, per exercise). All derived from fields already on "
        "the exercise (joint_stress, force_type, category, and the "
        "already-existing derive_tissue_demands() signals) via "
        "exercise_metadata.derive_connective_tissue() — no hand-typed "
        "per-exercise values; the underlying anatomy (which tendon/"
        "ligament crosses which joint) is standard gross anatomy, not "
        "invented. No other field changed."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Tagged {len(data['exercises'])} exercises. Backup written to {BACKUP}.")


if __name__ == "__main__":
    main()

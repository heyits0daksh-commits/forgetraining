"""
generate_batch20_rehab_mobility.py — adds 20 new difficulty-1/2 rehab &
mobility exercises targeting muscles that had little-to-no early-recovery
(difficulty-1) coverage: Hamstrings, Quadriceps, the hip abductor group
(Gluteus Medius/Minimus, Tensor Fasciae Latae), Pectoralis Major, Biceps
Brachii/Brachialis, Triceps Brachii, and the back group (Latissimus Dorsi,
Rhomboids, Trapezius, Erector Spinae) — plus two general post-surgical
reconditioning drills.

WHY THESE: an audit of data/exercises.json found the hip-abductor group was
the single biggest gap in the whole database — Gluteus Medius had only 1
difficulty-1 exercise (Side Plank) and Gluteus Minimus / Tensor Fasciae
Latae (TFL) had ZERO exercises of any difficulty, so REHAB_STAGE_CEILING's
early_recovery ceiling (injury_taxonomy.py, difficulty <= 1) had nothing to
offer someone rehabbing a hip abductor strain. Brachialis was similarly at
0 difficulty-1 entries despite 10 exercises tagging it at higher
difficulty. The other muscles the batch also covers (Hamstrings,
Quadriceps, Pectoralis Major, Triceps Brachii, Latissimus Dorsi, Rhomboids,
Erector Spinae) already had some difficulty-1 coverage but benefit from
dedicated low-load isometric/activation work rather than only bodyweight
compound movements (e.g. push-ups, squats) standing in as their "easy"
option.

Every entry here is difficulty 1 or 2, uses only Bodyweight or Resistance
Band equipment (both already >= 5-exercise equipment types, so this batch
doesn't need a new EQUIPMENT_LEVEL entry), and every injuries_to_avoid tag
is the exact Grade I (Mild) strain name already in
backend/services/injury_taxonomy.py's generated MUSCLE_GROUPS strain table
- see test_every_injuries_to_avoid_tag_resolves_in_taxonomy in
tests/test_exercise_data_integrity.py for why that match has to be exact.

Follows the exact pattern of generate_batch6/7_*.py: hand-tagged
joint_stress / injuries_to_avoid per exercise, small and reviewable rather
than exhaustive.

Run: python scripts/generators/generate_batch20_rehab_mobility.py
Then: python scripts/enrichment/enrich_batch20_only.py
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:
    from backend.core.config import settings
    SRC = settings.EXERCISES_JSON_PATH
    BACKUP_DIR = settings.BACKUP_DIR
except ModuleNotFoundError:
    # backend.core.config needs pydantic-settings, which isn't always
    # installed in every environment that just wants to run this script
    # against the data file directly - fall back to the known repo layout.
    PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    SRC = PROJECT_ROOT / "data" / "exercises.json"
    BACKUP_DIR = PROJECT_ROOT / "data" / "_backups"

BACKUP = BACKUP_DIR / "exercises_pre_batch20_backup.json"

EQUIPMENT_LEVEL = {"Bodyweight": 1, "Resistance Band": 8}

# general prehab/rehab work — useful across every combat/field sport as
# durability/return-to-training work, not a specialty movement for any one
# of them, so kept flat and moderate rather than sport-differentiated.
TEMPLATE_REHAB = {
    "Wrestling": 40, "Judo": 40, "Sambo": 40, "BJJ": 40, "Boxing": 40,
    "Muay Thai": 40, "Kickboxing": 40, "Sanda": 40, "Rugby": 40,
    "Rock Climbing": 40, "HYROX": 35, "Special Forces": 40, "MMA": 40,
}


def ex(id_, name, category, pattern, difficulty, equipment,
       primary, secondary, stabilizers, joint_stress, injuries, notes=None):
    return {
        "id": id_, "name": name, "category": category, "movement_pattern": pattern,
        "difficulty": difficulty,
        "experience_level": "Beginner" if difficulty == 1 else "Novice",
        "equipment": equipment, "equipment_level": EQUIPMENT_LEVEL[equipment],
        "primary_muscles": primary, "secondary_muscles": secondary, "stabilizers": stabilizers,
        "joint_stress": joint_stress, "injuries_to_avoid": injuries,
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0,
                                   "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": [], "alternatives": [],
        "sport_priority": dict(TEMPLATE_REHAB),
    }


NEW = []

# ---- Hamstrings (+2) ----
NEW += [
ex("hamstring_wallisohold_001", "Standing Hamstring Wall Isometric Hold", "Hinge", "Isometric", 1, "Bodyweight",
   ["Hamstrings"], ["Gluteus Maximus"], ["Core"],
   ["Knee", "Hip"], ["Hamstrings Strain - Grade I Strain (Mild)"]),
ex("hamstring_bandcurl_seated_001", "Seated Band Hamstring Curl", "Hinge", "Flexion", 1, "Resistance Band",
   ["Hamstrings"], [], [],
   ["Knee"], ["Hamstrings Strain - Grade I Strain (Mild)"]),
]

# ---- Quadriceps (+2) ----
NEW += [
ex("quad_isoset_seated_001", "Seated Quad Isometric Set", "Squat", "Isometric", 1, "Bodyweight",
   ["Quadriceps"], [], [],
   ["Knee"], ["Quadriceps Strain - Grade I Strain (Mild)"]),
ex("quad_bandtermext_001", "Band Terminal Knee Extension", "Squat", "Extension", 1, "Resistance Band",
   ["Quadriceps"], [], [],
   ["Knee"], ["Quadriceps Strain - Grade I Strain (Mild)"]),
]

# ---- Hip Abductors: Gluteus Medius/Minimus, TFL (+4 — the biggest gap) ----
NEW += [
ex("hipabd_sidelying_001", "Side-Lying Hip Abduction", "Core", "Lateral", 1, "Bodyweight",
   ["Gluteus Medius", "Gluteus Minimus"], [], ["Core"],
   ["Hip"], ["Gluteus Medius Strain - Grade I Strain (Mild)", "Gluteus Minimus Strain - Grade I Strain (Mild)"]),
ex("hipabd_clamshell_001", "Clamshell", "Core", "Lateral", 1, "Bodyweight",
   ["Gluteus Medius", "Gluteus Minimus"], [], ["Core"],
   ["Hip"], ["Gluteus Medius Strain - Grade I Strain (Mild)", "Gluteus Minimus Strain - Grade I Strain (Mild)"]),
ex("hipabd_bandstanding_001", "Standing Band Hip Abduction", "Core", "Lateral", 1, "Resistance Band",
   ["Gluteus Medius", "Tensor Fasciae Latae (TFL)"], [], ["Core"],
   ["Hip"], ["Gluteus Medius Strain - Grade I Strain (Mild)", "Tensor Fasciae Latae (TFL) Strain - Grade I Strain (Mild)"]),
ex("hipabd_bandmonsterwalk_001", "Band Monster Walk", "Core", "Lateral", 2, "Resistance Band",
   ["Gluteus Medius", "Tensor Fasciae Latae (TFL)"], ["Gluteus Minimus"], ["Core"],
   ["Hip", "Knee"], ["Gluteus Medius Strain - Grade I Strain (Mild)", "Tensor Fasciae Latae (TFL) Strain - Grade I Strain (Mild)"]),
]

# ---- Chest / Pectoralis Major (+2) ----
NEW += [
ex("chest_wallisopress_001", "Wall Isometric Chest Press", "Horizontal Push", "Isometric", 1, "Bodyweight",
   ["Pectoralis Major"], ["Anterior Deltoid"], ["Core"],
   ["Shoulder"], ["Pectoralis Major Strain - Grade I Strain (Mild)"]),
ex("chest_bandstandingpress_001", "Standing Band Chest Press", "Horizontal Push", "Push", 1, "Resistance Band",
   ["Pectoralis Major"], ["Anterior Deltoid", "Triceps Brachii"], ["Core"],
   ["Shoulder"], ["Pectoralis Major Strain - Grade I Strain (Mild)"]),
]

# ---- Biceps Brachii / Brachialis (+2) ----
NEW += [
ex("biceps_isoneutralhold_001", "Isometric Neutral-Grip Bicep Hold", "Vertical Pull", "Isometric", 1, "Resistance Band",
   ["Brachialis", "Biceps Brachii"], ["Forearms"], [],
   ["Elbow"], ["Biceps Strain - Grade I Strain (Mild)"]),
ex("biceps_bandcurl_light_001", "Light Band Bicep Curl", "Vertical Pull", "Pull", 1, "Resistance Band",
   ["Biceps Brachii", "Brachialis"], ["Forearms"], [],
   ["Elbow"], ["Biceps Strain - Grade I Strain (Mild)"]),
]

# ---- Triceps Brachii (+2) ----
NEW += [
ex("triceps_wallisopress_001", "Wall Isometric Tricep Press", "Vertical Push", "Isometric", 1, "Bodyweight",
   ["Triceps Brachii"], [], ["Core"],
   ["Elbow"], ["Triceps Strain - Grade I Strain (Mild)"]),
ex("triceps_bandext_light_001", "Light Band Tricep Extension", "Vertical Push", "Push", 1, "Resistance Band",
   ["Triceps Brachii"], [], [],
   ["Elbow"], ["Triceps Strain - Grade I Strain (Mild)"]),
]

# ---- Back: Latissimus Dorsi, Rhomboids, Trapezius, Erector Spinae (+4) ----
NEW += [
ex("back_bandrow_isohold_001", "Band Seated Row Isometric Hold", "Horizontal Pull", "Isometric", 1, "Resistance Band",
   ["Rhomboids", "Latissimus Dorsi"], ["Trapezius"], ["Core"],
   ["Shoulder"], ["Rhomboids Strain - Grade I Strain (Mild)", "Latissimus Dorsi Strain - Grade I Strain (Mild)"]),
ex("back_prone_ytw_001", "Prone Y-T-W Raise", "Horizontal Pull", "Complex", 1, "Bodyweight",
   ["Rhomboids", "Trapezius"], ["Rear Deltoid"], ["Erector Spinae"],
   ["Shoulder"], ["Rhomboids Strain - Grade I Strain (Mild)"]),
ex("back_birddog_001", "Bird Dog", "Hinge", "Isometric", 1, "Bodyweight",
   ["Erector Spinae"], ["Gluteus Maximus", "Rectus Abdominis"], ["Core"],
   ["Lower Back"], ["Erector Spinae Strain - Grade I Strain (Mild)"]),
ex("back_gentlesupermanhold_001", "Gentle Prone Superman Hold", "Hinge", "Isometric", 1, "Bodyweight",
   ["Erector Spinae"], ["Gluteus Maximus"], ["Core"],
   ["Lower Back"], ["Erector Spinae Strain - Grade I Strain (Mild)"]),
]

# ---- General post-surgical reconditioning (+2) ----
NEW += [
ex("postop_marchinplace_001", "Standing March in Place (Post-Surgical Reconditioning)", "Full Body", "Complex", 1, "Bodyweight",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings", "Core"], ["Core"],
   ["Hip", "Knee"], []),
ex("postop_supportedsit2stand_001", "Supported Sit-to-Stand (Post-Surgical Reconditioning)", "Full Body", "Complex", 1, "Bodyweight",
   ["Quadriceps", "Gluteus Maximus"], ["Hamstrings"], ["Core"],
   ["Hip", "Knee"], []),
]

print(f"Generated {len(NEW)} new exercises across "
      f"{len(set(e['equipment'] for e in NEW))} equipment types.")


def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_ids = {e["id"] for e in data["exercises"]}
    dupes = [e["id"] for e in NEW if e["id"] in existing_ids]
    if dupes:
        raise SystemExit(f"Duplicate IDs, aborting: {dupes}")

    seen = set()
    internal_dupes = [e["id"] for e in NEW if e["id"] in seen or seen.add(e["id"])]
    if internal_dupes:
        raise SystemExit(f"Duplicate IDs within this batch, aborting: {internal_dupes}")

    data["exercises"].extend(NEW)
    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(data['exercises'])} total exercises to {SRC}. "
          f"Backup at {BACKUP}. Now run scripts/enrichment/enrich_batch20_only.py.")


if __name__ == "__main__":
    main()

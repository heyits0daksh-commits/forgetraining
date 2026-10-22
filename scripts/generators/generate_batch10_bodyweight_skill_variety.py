"""
generate_batch10_bodyweight_skill_variety.py — fixes the "same exercise every
week/day" bug reported for equipment=Bodyweight athletes (screenshotted on
Judo: "Wrestler's Neck Bridge" appearing as the #1 Skill/Technical exercise
on every single day-tab and every single week-tab, with an identical
4x7/rest120s prescription each time).

ROOT CAUSE (confirmed by inspection, not guessed)
progression_engine._pick_with_variety only rotates among candidates that
land within _VARIETY_BAND (12%) of the top score for a role/category. For
category="Sport Specific" + equipment="Bodyweight", the ENTIRE database only
had 3 exercises, period, for every one of the 13 combat/contact sports this
manual covers:
    neck_bridge_001   "Wrestler's Neck Bridge"
    ruck_march_001    "Heavy Ruck March"
    shadow_boxing_001 "Shadow Boxing Rounds"
For a grappling sport (Judo/Wrestling/BJJ/Sambo) neck_bridge_001 outscores
the other two by 15-40+ points - miles outside the 12% band - so it was
mathematically the *only* candidate in the band on every single call, for
every week, every day-label, every athlete on bodyweight-only equipment.
_pick_with_variety was working exactly as designed; there was nothing to
pick between. Same story for striking sports, just with shadow_boxing_001
as the lone dominant pick instead.

FIX
This isn't a logic bug, it's a content-depth bug (same category batch6-9
already fixed for machine/cable/band equipment types - this is the same
gap, just for category=Sport Specific x equipment=Bodyweight, which those
batches didn't touch). Adds 5 new bodyweight, no-partner-required technical
drills, each scored so that for the sports it's actually relevant to its
sport_priority sits *within* neck_bridge_001's or shadow_boxing_001's 12%
band for that sport - not higher (that would just crown a new lone winner)
and not lower (that wouldn't enter the band at all). Verified programmatically
below, not just eyeballed.

  - shadow_uchikomi_001   "Shadow Uchikomi Entries (No Partner)"
        Judo/Sambo footwork-and-entry drilling, no dummy/partner required.
  - sprawl_sprint_001     "Sprawl-to-Sprint"
        Named directly in the manual's Wrestling/Sanda exercise banks;
        also relevant to BJJ/Rugby scramble-to-feet work.
  - bridge_hipescape_001  "Bridge-to-Hip-Escape Flow"
        The manual's own "Bridge & Shrimp Drills" (BJJ bank) generalized -
        relevant to every grappling sport's bottom-position escape work.
  - shadow_combo_footwork_001  "Shadow Combination Footwork Drilling"
        Striking-sport equivalent of shadow_uchikomi - pivot/angle footwork
        with no bag/pads required.
  - obstacle_circuit_001  "Bodyweight Functional Obstacle Circuit"
        The manual's "Functional Obstacle Circuit" (Special Forces bank),
        also relevant to Rugby/HYROX.

Same authoring discipline as batch2-9: base fields hand-tagged from real
biomechanics, run through the same enrich_exercise() pipeline as everything
else so movement-analysis/athletic-quality fields aren't hand-faked.

Run: python scripts/generate_batch10_bodyweight_skill_variety.py
Then: python scripts/enrich_batch10_only.py
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:
    from backend.core.config import settings
    SRC = settings.EXERCISES_JSON_PATH
    BACKUP = settings.BACKUP_DIR / "exercises_pre_batch10_backup.json"
except ModuleNotFoundError:
    _ROOT = Path(__file__).resolve().parent.parent.parent
    SRC = _ROOT / "data" / "exercises.json"
    BACKUP = _ROOT / "data" / "backups" / "exercises_pre_batch10_backup.json"

# All 15 sports carried by every exercise in the file (see pushup_001).
_SPORT_KEYS = [
    "Wrestling", "Judo", "Sambo", "BJJ", "Boxing", "Muay Thai", "Kickboxing",
    "Sanda", "Rugby", "Rock Climbing", "HYROX", "Special Forces", "MMA",
    "Powerlifting", "Look Jacked",
]

NEW_EXERCISES = [
    {
        "id": "shadow_uchikomi_001",
        "name": "Shadow Uchikomi Entries (No Partner)",
        "category": "Sport Specific",
        "movement_pattern": "Rotational",
        "difficulty": 3,
        "experience_level": "Advanced",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Gluteus Maximus", "Erector Spinae", "Quadriceps"],
        "secondary_muscles": ["Trapezius", "Obliques"],
        "stabilizers": ["Core"],
        "joint_stress": ["Knee", "Lower Back"],
        "injuries_to_avoid": ["Low Back Pain", "Patellar Tendon"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": [], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            55, 64, 90, 40, 10, 15, 15, 60, 15, 5, 15, 15, 50, 5, 10,
        ])),
    },
    {
        "id": "sprawl_sprint_001",
        "name": "Sprawl-to-Sprint",
        "category": "Sport Specific",
        "movement_pattern": "Full Body",
        "difficulty": 3,
        "experience_level": "Advanced",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Quadriceps", "Pectoralis Major", "Gluteus Maximus"],
        "secondary_muscles": ["Anterior Deltoid", "Hip Flexors"],
        "stabilizers": ["Core"],
        "joint_stress": ["Shoulder", "Knee", "Wrist"],
        "injuries_to_avoid": ["Shoulder Instability (General/Atraumatic)", "Patellar Tendon"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": [], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            92, 40, 70, 55, 30, 40, 40, 82, 60, 10, 60, 55, 85, 10, 20,
        ])),
    },
    {
        "id": "bridge_hipescape_001",
        "name": "Bridge-to-Hip-Escape Flow",
        "category": "Sport Specific",
        "movement_pattern": "Rotational",
        "difficulty": 2,
        "experience_level": "Intermediate",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Erector Spinae", "Obliques", "Gluteus Maximus"],
        "secondary_muscles": ["Hip Flexors", "Core"],
        "stabilizers": ["Core"],
        "joint_stress": ["Lower Back", "Neck"],
        "injuries_to_avoid": ["Low Back Pain", "Neck Pain"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": [], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            58, 64, 78, 56, 20, 25, 25, 45, 30, 15, 30, 65, 60, 10, 20,
        ])),
    },
    {
        "id": "shadow_combo_footwork_001",
        "name": "Shadow Combination Footwork Drilling",
        "category": "Sport Specific",
        "movement_pattern": "Strike",
        "difficulty": 2,
        "experience_level": "Intermediate",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Anterior Deltoid", "Obliques", "Gastrocnemius"],
        "secondary_muscles": ["Triceps Brachii", "Hip Flexors"],
        "stabilizers": ["Core"],
        "joint_stress": ["Shoulder", "Ankle"],
        "injuries_to_avoid": ["Lateral Ankle Sprain - Grade 1 (Mild)"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": [], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            20, 15, 15, 15, 90, 85, 86, 80, 25, 5, 30, 25, 75, 5, 20,
        ])),
    },
    {
        "id": "obstacle_circuit_001",
        "name": "Bodyweight Functional Obstacle Circuit",
        "category": "Sport Specific",
        "movement_pattern": "Full Body",
        "difficulty": 3,
        "experience_level": "Advanced",
        "equipment": "Bodyweight",
        "equipment_level": 1,
        "primary_muscles": ["Quadriceps", "Pectoralis Major", "Latissimus Dorsi"],
        "secondary_muscles": ["Gluteus Maximus", "Anterior Deltoid"],
        "stabilizers": ["Core"],
        "joint_stress": ["Shoulder", "Knee", "Wrist"],
        "injuries_to_avoid": ["Shoulder Instability (General/Atraumatic)", "Patellar Tendon"],
        "strength_requirements": {"bench_ratio": 0.0, "squat_ratio": 0.0, "deadlift_ratio": 0.0, "pullups": 0, "pushups": 0},
        "progressions": [], "regressions": [], "alternatives": [],
        "sport_priority": dict(zip(_SPORT_KEYS, [
            30, 20, 20, 20, 20, 25, 25, 30, 58, 40, 90, 90, 40, 5, 25,
        ])),
    },
]


def main():
    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_ids = {e["id"] for e in data["exercises"]}
    dupes = [e["id"] for e in NEW_EXERCISES if e["id"] in existing_ids]
    if dupes:
        raise SystemExit(f"These ids already exist, aborting: {dupes}")

    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(SRC, BACKUP)

    data["exercises"].extend(NEW_EXERCISES)

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Added {len(NEW_EXERCISES)} exercises. "
          f"Total exercises in file: {len(data['exercises'])}. "
          f"Backup written to {BACKUP}.")


if __name__ == "__main__":
    main()

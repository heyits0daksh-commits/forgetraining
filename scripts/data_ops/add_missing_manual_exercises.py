"""
add_missing_manual_exercises.py — adds the small set of manual exercises
that had NO reasonable existing exercises.json match (see
tag_manual_exercises.py's printed gap list) as brand-new, fully-structured
entries, cloned from the closest analogous entry already in the database
and hand-adjusted (name, id, equipment, sport_priority) rather than
auto-generated with fabricated numbers.

Run tag_manual_exercises.py again after this - these entries are named
identically to their manual counterpart, so they'll match on the exact-name
pass without needing a new alias.

This intentionally does NOT attempt the ~19 pure protocol/interval strings
(e.g. "5 x 2min hard / 1min rest") - those describe a work/rest scheme, not
a single exercise, and adding a fake "exercise" for one would be worse than
leaving the gap (see tag_manual_exercises.py's docstring).
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
EXERCISES_PATH = ROOT / "data" / "exercises.json"
BACKUP_PATH = ROOT / "data" / "backups" / "exercises_pre_missing_manual_add_backup.json"


def clone(template: dict, **overrides) -> dict:
    new = json.loads(json.dumps(template))  # deep copy
    new.update(overrides)
    return new


def main():
    with open(EXERCISES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    exercises = data["exercises"]
    by_name = {e["name"]: e for e in exercises}
    existing_ids = {e["id"] for e in exercises}

    def uid(base: str) -> str:
        cand = f"{base}_001"
        n = 1
        while cand in existing_ids:
            n += 1
            cand = f"{base}_{n:03d}"
        existing_ids.add(cand)
        return cand

    new_entries = []

    # 1. Band-Resisted Kick Drills (Muay Thai/Kickboxing/Sanda) - cloned
    # from Heavy Bag Low Kick Conditioning, swapped to band equipment/lower
    # fatigue since it's a drilling tool, not full-contact bag work.
    t = by_name["Heavy Bag Low Kick Conditioning"]
    new_entries.append(clone(
        t,
        id=uid("band_kick_drill"),
        name="Band-Resisted Kick Drills",
        equipment="Resistance Band",
        equipment_level=3,
        difficulty=2,
        fatigue_cost=22,
        CNS_fatigue=32,
        recovery_time_hours=26,
        in_manual=True,
    ))

    # 2. Clinch Grip Carries (Muay Thai/Sanda) - cloned from Farmer Handles
    # Carry (same Carry category/isometric-grip demand) but equipment/
    # muscle emphasis shifted to neck-tie/collar grip instead of handles.
    t = by_name["Farmer Handles Carry"]
    new_entries.append(clone(
        t,
        id=uid("clinch_grip_carry"),
        name="Clinch Grip Carries",
        equipment="Partner / Clinch Bag",
        equipment_level=2,
        primary_muscles=["Forearm Flexors", "Trapezius", "Neck Flexors"],
        secondary_muscles=["Erector Spinae", "Core"],
        in_manual=True,
    ))

    # 3. Change-of-Direction 5-10-5 (Rugby/Sanda) - the classic 5-10-5
    # pro-agility shuttle test, cloned from the closest existing agility
    # drill (Sprawl-to-Sprint) with plane/pattern adjusted to a lateral
    # shuttle instead of a sprawl-specific movement.
    t = by_name["Sprawl-to-Sprint"]
    new_entries.append(clone(
        t,
        id=uid("cod_5_10_5"),
        name="Change-of-Direction 5-10-5",
        movement_pattern="Agility",
        equipment="Bodyweight",
        equipment_level=1,
        primary_muscles=["Quadriceps", "Gluteus Maximus", "Hip Flexors"],
        secondary_muscles=["Hamstrings", "Gastrocnemius"],
        joint_stress=["Knee", "Ankle"],
        injuries_to_avoid=["Patellar Tendon"],
        in_manual=True,
    ))

    # 4. Hill or Stair Sprints (Boxing/general conditioning) - cloned from
    # Assault Bike Sprint Intervals (same alactic/lactic sprint-repeat
    # intent) but equipment swapped to bodyweight outdoor running.
    t = by_name["Assault Bike Sprint Intervals"]
    new_entries.append(clone(
        t,
        id=uid("hill_stair_sprint"),
        name="Hill or Stair Sprints",
        category="Conditioning",
        equipment="Bodyweight",
        equipment_level=1,
        joint_stress=["Knee", "Ankle", "Hip"],
        in_manual=True,
    ))

    # 5. Leg-Lock Defense Mobility Flow (Sambo) - cloned from
    # Bridge-to-Hip-Escape Flow (same "mobility flow" role/force profile
    # in the manual's own Sport-Specific/Grip/Core slot).
    t = by_name["Bridge-to-Hip-Escape Flow"]
    new_entries.append(clone(
        t,
        id=uid("leglock_defense_flow"),
        name="Leg-Lock Defense Mobility Flow",
        in_manual=True,
    ))

    # 6. Lock-Off Holds (Rock Climbing) - cloned from Ring Support Hold
    # (same isometric upper-body static-hold profile), equipment swapped
    # to a climbing hold/hangboard instead of rings.
    t = by_name["Ring Support Hold"]
    new_entries.append(clone(
        t,
        id=uid("lockoff_hold"),
        name="Lock-Off Holds",
        equipment="Climbing Hold / Hangboard",
        equipment_level=6,
        in_manual=True,
    ))

    # 7. Shuttle Runs (Yo-Yo IR1 style) (Rugby) - cloned from Assault Bike
    # Sprint Intervals, equipment swapped to bodyweight incremental shuttle
    # running (the actual Yo-Yo IR1 test protocol).
    t = by_name["Assault Bike Sprint Intervals"]
    new_entries.append(clone(
        t,
        id=uid("yoyo_shuttle_run"),
        name="Shuttle Runs (Yo-Yo IR1 style)",
        category="Conditioning",
        equipment="Bodyweight",
        equipment_level=1,
        movement_pattern="Shuttle Run",
        recovery_time_hours=45,
        in_manual=True,
    ))

    # 8. Speed Bag / Double-End Bag (Boxing) - cloned from Heavy Bag
    # Combinations, equipment/muscle emphasis shifted toward hand-speed/
    # timing (shoulders/forearms) rather than full-power striking.
    t = by_name["Heavy Bag Combinations"]
    new_entries.append(clone(
        t,
        id=uid("speed_bag_work"),
        name="Speed Bag / Double-End Bag",
        equipment="Speed Bag",
        equipment_level=15,
        difficulty=2,
        primary_muscles=["Anterior Deltoid", "Forearm Flexors"],
        secondary_muscles=["Triceps Brachii", "Core"],
        fatigue_cost=20,
        CNS_fatigue=30,
        recovery_time_hours=24,
        in_manual=True,
    ))

    names_added = [e["name"] for e in new_entries]
    already = [n for n in names_added if n in by_name]
    if already:
        raise SystemExit(f"Refusing to add duplicates already present: {already}")

    BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(EXERCISES_PATH, BACKUP_PATH)
    print(f"Backed up -> {BACKUP_PATH}")

    exercises.extend(new_entries)
    data["exercises"] = exercises

    with open(EXERCISES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Added {len(new_entries)} new exercises:")
    for n in names_added:
        print(f"  - {n}")


if __name__ == "__main__":
    main()

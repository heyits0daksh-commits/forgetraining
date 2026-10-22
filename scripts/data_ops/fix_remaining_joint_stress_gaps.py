"""
fix_remaining_joint_stress_gaps.py (v5.32) — extends the "entirely missing
joint_stress tag" fix (v5.31, Ankle) to the other 7 joints, using the same
underlying bug pattern: an exercise that genuinely loads/stabilizes a joint
but was never tagged for it at all, so the injury-safety engine's set-
intersection check (progression_engine.py) has nothing to catch it against.

METHOD
For every (category, equipment) group with >=3 members, computed what
fraction of members already carry each joint tag. Where a strong majority
(>=60%) of close peers carry a tag and a minority doesn't, that's a
candidate gap — the same signal that caught Barbell Back Squat/Deadlift/
Hang High Pull for Ankle in v5.31, generalized across all 8 joints.

Every candidate was then reviewed by hand (not auto-applied on the
threshold alone) because peer groups get noisy at the edges — e.g. the
"Hinge, Barbell" group's Knee-tag majority comes from conventional/sumo
deadlift variants; Romanian Deadlift and Good Morning sit in the same
group but are deliberately knee-neutral hip-hinges and correctly lack the
tag, so they were excluded despite matching the raw signal. Likewise
"Chest Supported Row" and "Rack-Supported Split Squat" were excluded from
Lower Back — the whole point of that equipment choice is to remove the
brace-against-flexion demand the peer group's tag reflects. Corrective/
rehab-pattern exercises (Standing Hamstring Wall Isometric Hold, Supported
Sit-to-Stand, Seated Quad Isometric Set) were excluded on the same
_is_corrective precedent v5.24/v5.26 already established.

Sport Specific candidates (Tackle Bag Sprawl/Wrap and Drive/Chop Tackle)
are NOT included here, same reasoning as v5.31 - movement-to-movement
variance in that category is too high for a rule (or a hand-reviewed list
this size) to be reliable; flagged in ROADMAP for individual review.

Each joint's additions below are a hand-curated list, not a category
blanket rule (unlike v5.31's Ankle pass, where the categories involved were
homogeneous enough for a rule). See inline comments per joint for the
biomechanical reasoning.

After tagging, re-derives tendons_loaded/ligaments_stressed/
muscle_action_by_phase/biomechanics_notes (exercise_metadata.
derive_connective_tissue()) for every touched exercise only, same pattern
v5.23.1 used to keep those fields from going stale after a joint_stress
edit.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.exercise_metadata import derive_connective_tissue

SRC = ROOT / "data" / "exercises.json"
BACKUP = ROOT / "data" / "backups" / "exercises_pre_remaining_joint_stress_gap_fix_backup.json"

# name -> set of joints to add. Reviewed by hand against the peer-group
# candidate list; see module docstring for exclusion reasoning.
FIXES = {
    # --- Wrist: hand/wrist bears load in a pressing or front-rack hold ---
    "Wall Isometric Chest Press": {"Wrist"},
    "Bench Dip": {"Wrist"},
    "Wall Isometric Tricep Press": {"Wrist", "Shoulder"},
    "Thruster": {"Wrist"},
    "Swiss Bar Floor Press": {"Wrist"},

    # --- Elbow: straight-arm hang/support holds and pressing movements ---
    "Wall Push-Up": {"Elbow"},
    "Planche Lean": {"Elbow"},
    "Pseudo Planche Push-Up": {"Elbow"},
    "Active Scapular Shrug": {"Elbow"},
    "L-Sit Pull-Up": {"Elbow"},
    "Tucked Front Lever": {"Elbow"},
    "Advanced Tucked Front Lever": {"Elbow"},
    "Full Front Lever": {"Elbow"},
    "Single Arm Dumbbell Bench Press": {"Elbow"},
    "Dumbbell Incline Press": {"Elbow"},
    "Ring Support Hold": {"Elbow"},
    "Ring Handstand": {"Elbow"},
    "Wide Grip Bench Press": {"Elbow"},
    "Reverse Grip Bench Press": {"Elbow"},
    "Larsen Press": {"Elbow"},
    "Guillotine Press": {"Elbow"},
    "Ring Planche": {"Elbow"},
    "Rack-Supported Push-Up": {"Elbow"},
    "Straight-Arm Pulldown": {"Elbow"},
    "Seal Row Iso Hold": {"Elbow"},
    "Circus Dumbbell Press": {"Elbow"},
    "Arnold Press": {"Elbow"},
    "Dumbbell Push Press": {"Elbow"},

    # --- Shoulder: hand-held/racked load stabilized by the shoulder, or a
    # pressing/pulling/explosive-pull movement missing the tag its close
    # siblings already carry ---
    "Dumbbell Skullcrusher": {"Shoulder"},
    "Dumbbell Tate Press": {"Shoulder"},
    "Kettlebell Deadlift": {"Shoulder"},
    "Kettlebell Romanian Deadlift": {"Shoulder"},
    "Jefferson Squat": {"Shoulder"},
    "Farmer Handles Carry": {"Shoulder"},
    "Hangboard Repeaters": {"Shoulder"},
    "Kettlebell Reverse Lunge": {"Shoulder"},
    "Kettlebell-Loaded Pistol Squat": {"Shoulder"},
    "Cossack Squat": {"Shoulder"},
    "Barbell Skullcrusher": {"Shoulder"},
    "Seated Row Machine Low-Handle Row": {"Shoulder"},
    "Ab Wheel Reverse Crunch": {"Shoulder"},
    "Dumbbell Tricep Kickback": {"Shoulder"},
    "Barbell Clean Pull": {"Shoulder"},
    "Atlas Stone Circuit Medley": {"Shoulder"},
    "Keg Bear Hug Carry": {"Shoulder"},

    # --- Hip: hip-driven squat/hinge variants missing the tag their
    # near-identical siblings already carry ---
    "Kettlebell High Pull": {"Hip"},
    "Narrow-Stance Leg Press": {"Hip"},
    "Leg Press Machine Pause Rep": {"Hip"},
    "Safety Squat Bar Box Squat": {"Hip"},
    "Safety Squat Bar Anderson Squat (Dead Start)": {"Hip"},
    "Squat Rack Isometric Pin Squat Hold": {"Hip"},
    "Belt Squat Pulse Squat": {"Hip"},
    "Reverse Hyper Pulse Reps": {"Hip"},
    "Reverse Hyper Bent-Knee Variation": {"Hip"},

    # --- Knee: genuine dynamic knee flexion/extension under load or
    # bodyweight (rowing drive, loaded yoke walk, jump-rope landings,
    # mountain-climber knee drive, agility footwork) ---
    "Rowing Erg 100m Sprint Repeats": {"Knee"},
    "Yoke Lateral Carry": {"Knee"},
    "Yoke Partial Rack Support Hold": {"Knee"},
    "Ladder Hip Turns": {"Knee"},
    "Jump Rope Boxer Skip": {"Knee"},
    "Jump Rope Criss-Cross": {"Knee"},
    "Mountain Climbers": {"Knee"},

    # --- Lower Back: front-rack/Zercher spinal bracing under axial load,
    # hanging core work matching its own sibling, explosive loaded lifts,
    # and rows where the torso isn't externally supported ---
    "Pause Front Squat": {"Lower Back"},
    "Tempo Front Squat": {"Lower Back"},
    "Zombie Front Squat": {"Lower Back"},
    "Cross Arm Front Squat": {"Lower Back"},
    "Clean Grip Front Squat": {"Lower Back"},
    "Zercher Reverse Lunge": {"Lower Back"},
    "Zercher Split Squat": {"Lower Back"},
    "Hanging Knee Raise": {"Lower Back"},
    "Kettlebell Jerk": {"Lower Back"},
    "Renegade Row": {"Lower Back"},
    "Inverted Bar Row (Knees Bent)": {"Lower Back"},
    "Fat-Grip Row": {"Lower Back"},
    "Safety Squat Bar Split Squat": {"Lower Back"},

    # --- Ankle: standing/loaded stance work v5.31's category rule didn't
    # reach (Full Body/Kettlebell mixed group, strongman toss/strike work) ---
    "Kettlebell Windmill": {"Ankle"},
    "Dumbbell Renegade Row": {"Ankle"},
    "Tire Sledgehammer Strike": {"Ankle"},
    "Fingal's Fingers Toss": {"Ankle"},

    # --- Neck: heavy overhead barbell lockout puts the loaded bar directly
    # over the cervical spine; sibling overhead-press variants already
    # carry the tag ---
    "Strict Press": {"Neck"},
    "Z Press": {"Neck"},
}


def main():
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)

    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    exercises = data["exercises"]
    by_name = {e["name"]: e for e in exercises}

    touched = []
    joint_counts = {}
    missing_names = [n for n in FIXES if n not in by_name]
    if missing_names:
        raise SystemExit(f"Names not found in exercises.json: {missing_names}")

    for name, joints in FIXES.items():
        ex = by_name[name]
        js = set(ex.get("joint_stress") or [])
        new_joints = joints - js
        if not new_joints:
            continue
        ex["joint_stress"] = sorted(js | new_joints)
        ex.update(derive_connective_tissue(ex))
        touched.append(ex["id"])
        for j in new_joints:
            joint_counts[j] = joint_counts.get(j, 0) + 1

    data["version"] = "5.32.0"
    data["schema_notes"] += (
        "\n\nv5.32 extends v5.31's joint_stress completeness fix to the "
        "other 7 joints (see scripts/data_ops/fix_remaining_joint_stress_gaps.py): "
        f"{len(touched)} exercises hand-reviewed against a peer-group "
        "consistency signal (close (category, equipment) neighbors that "
        "already carry a joint tag) each gained one or more missing "
        f"joint_stress tags — {joint_counts}. tendons_loaded/"
        "ligaments_stressed/muscle_action_by_phase/biomechanics_notes were "
        "re-derived for every touched exercise so those fields don't go "
        "stale versus the corrected joint_stress, same as v5.23.1. Sport "
        "Specific candidates were deliberately left untagged, same "
        "reasoning as v5.31."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Touched {len(touched)} exercises. Joint tag additions: {joint_counts}")
    print(f"Backup at {BACKUP}")


if __name__ == "__main__":
    main()

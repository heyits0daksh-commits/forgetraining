"""
volume_engine.py — computes actual weekly SET volume per muscle group from a
generated program and checks it against experience/goal-scaled landmarks.

WHY THIS EXISTS
`program_builder._weekly_muscle_frequency` already answers "how many days/
week does each muscle get direct work" (a frequency question) and flags
anything under a flat 2x/week minimum. It does not answer the volume
question a coach actually programs around: how many total SETS/week is
each muscle getting, and is that number appropriate for this person's
experience level and goal - too little to grow/get strong, or piled high
enough to outrun recovery. Nothing in the engine computed that before this
module; `pl_hypertrophy_manual.py`'s LOOK_JACKED_LEVELS table has the
per-experience-level set ranges (transcribed from a real hypertrophy
guide), but that module is explicitly a read-only reference layer never
wired into the live engine (see its own docstring) - so those numbers
existed on paper but were never checked against what a real generated
program actually prescribes.

DESIGN
- Muscle-group mapping: `data/exercises.json` tags muscles at a fine
  anatomical grain (e.g. "Anterior Deltoid", "Lateral Deltoid", "Rear
  Deltoid", "Deltoids" all denoting the same trainable unit under
  different exercises' authoring). Volume landmarks are a per-muscle-GROUP
  concept in the training literature (nobody programs "12-16 sets/week of
  Anterior Deltoid specifically" as distinct from Lateral/Rear) - so this
  module first collapses the raw tags into ~13 canonical groups
  (`_MUSCLE_GROUP_MAP`) before counting anything.
- Set counting: a set of a compound exercise counts in FULL toward each of
  its primary movers (each set genuinely stimulates each primary muscle to
  a real training effect) and at HALF credit toward secondary/assisting
  muscles - the same primary=full/secondary=half convention the volume-
  landmark literature this table is built from (Israetel/RP-style MEV-MAV-
  MRV work) itself uses, so the counted numbers are comparable to the
  landmarks they're being checked against. Stabilizers are not counted -
  a muscle bracing isometrically isn't accumulating the same kind of
  progressive-overload volume a mover is.
- Landmarks: reuses `pl_hypertrophy_manual.LOOK_JACKED_LEVELS`'s own
  `weekly_sets_per_muscle` ranges (Beginner 8-10 ... Elite 20-22) as the
  Build-Muscle-goal baseline, since those numbers are already real,
  sourced content living in this codebase rather than a second invented
  table. Every other goal scales that baseline down via
  `GOAL_VOLUME_MULTIPLIER`: a "Get Strong"/"Power" program is correctly
  not trying to hit hypertrophy-literature muscle volume - it's built
  around a handful of main lifts at low reps/high intensity, so holding
  it to the same 14-18 sets/muscle standard as a bodybuilding block would
  be evaluating it against the wrong target, not a real deficiency. Only
  the 9 muscle groups with real literature volume-landmark grounding are
  hard-checked; minor stabilizer/support groups (Forearms, Adductors, Hip
  Flexors, Neck, Lower Leg/Ankle, Lower Back) are counted and reported but
  not flagged under/over - the literature doesn't have a well-established
  per-week set target for those the way it does for the 9 major groups.
"""

import re
from typing import Dict, List, Optional

from backend.services.pl_hypertrophy_manual import LOOK_JACKED_LEVELS

# ---------------------------------------------------------------------------
# Raw exercises.json muscle tag -> canonical trainable muscle group.
# Anything not listed falls back to Title Case of itself (see _canonical_group)
# rather than being silently dropped, so a future/typo'd tag still shows up
# in the report instead of vanishing from volume accounting.
# ---------------------------------------------------------------------------
_MUSCLE_GROUP_MAP: Dict[str, str] = {
    "Pectoralis Major": "Chest",
    "Latissimus Dorsi": "Back",
    "Rhomboids": "Back",
    "Trapezius": "Traps",
    "Traps": "Traps",
    "Upper Trapezius": "Traps",
    "Anterior Deltoid": "Shoulders",
    "Lateral Deltoid": "Shoulders",
    "Rear Deltoid": "Shoulders",
    "Posterior Deltoid": "Shoulders",
    "Deltoids": "Shoulders",
    "Biceps Brachii": "Biceps",
    "Brachialis": "Biceps",
    "Triceps Brachii": "Triceps",
    "Forearm Flexors": "Forearms",
    "Forearms": "Forearms",
    "Quadriceps": "Quads",
    "Hamstrings": "Hamstrings",
    "Gluteus Maximus": "Glutes",
    "Gluteus Medius": "Glutes",
    "Glutes": "Glutes",
    "Hip Abductors": "Glutes",
    "Adductors": "Adductors",
    "Hip Flexors": "Hip Flexors",
    "Calves": "Calves",
    "Gastrocnemius": "Calves",
    "Soleus": "Calves",
    "Rectus Abdominis": "Abs",
    "Obliques": "Abs",
    "Core": "Abs",
    "Transverse Abdominis": "Abs",
    "Erector Spinae": "Lower Back",
    "Neck Flexors": "Neck",
    "Neck Extensors": "Neck",
    "Sternocleidomastoid": "Neck",
    "Ankle Stabilizers": "Lower Leg/Ankle",
    "Tibialis Anterior": "Lower Leg/Ankle",
    "Peroneals": "Lower Leg/Ankle",
}

# The 9 groups the LOOK_JACKED_LEVELS "8-10 ... 20-22 sets" range actually
# describes (the guide's own subject: major hypertrophy-trainable muscles).
# Everything else in _MUSCLE_GROUP_MAP is counted but not landmark-checked.
_LANDMARK_TRACKED_GROUPS = {
    "Chest", "Back", "Traps", "Shoulders", "Biceps", "Triceps",
    "Quads", "Hamstrings", "Glutes",
}

# How far a goal's real target volume sits from the Build-Muscle/hypertrophy
# baseline. Not literature-measured per goal - a reasoned scaling of the one
# real sourced number this codebase has (LOOK_JACKED_LEVELS), grounded in
# how each goal actually trains: fewer, heavier, lower-rep sets for pure
# strength/power (volume lives in the main lift's intensity, not in stacking
# isolation sets), versus full hypertrophy volume for Build Muscle itself.
GOAL_VOLUME_MULTIPLIER: Dict[str, float] = {
    "Build Muscle": 1.0,
    "Strength + Hypertrophy": 0.8,
    "General Fitness": 0.7,
    "Get Strong": 0.5,
    "Athletic Performance": 0.45,
    "Power / Explosiveness": 0.4,
    "Conditioning": 0.35,
    "Skill Development": 0.35,
}
_DEFAULT_GOAL_MULTIPLIER = 0.6

# A real coach doesn't size gym-session volume as if the gym is the
# athlete's only training - every session/week already spent on outside
# sport practice, team conditioning, etc. carries real muscular/systemic
# fatigue and movement volume of its own, on top of whatever the goal-based
# multiplier above already accounts for. ~6%/session, floored at 0.55x: a
# genuinely heavy outside schedule still leaves the gym landmark
# meaningfully non-zero - the main lifts are still what keeps this athlete
# strong for their sport, only the "extra" accessory volume on top should
# shrink aggressively as outside load stacks up. Independent of (and
# multiplies with) GOAL_VOLUME_MULTIPLIER, not a replacement for it.
_OUTSIDE_TRAINING_PER_SESSION_DISCOUNT = 0.06
_OUTSIDE_TRAINING_FLOOR_MULTIPLIER = 0.55


def outside_training_volume_multiplier(outside_training_sessions_per_week: Optional[int]) -> float:
    """1.0 (no-op) when outside_training_sessions_per_week is None/0 - every
    existing caller that doesn't pass this keeps identical landmarks."""
    if not outside_training_sessions_per_week:
        return 1.0
    return max(
        _OUTSIDE_TRAINING_FLOOR_MULTIPLIER,
        1.0 - _OUTSIDE_TRAINING_PER_SESSION_DISCOUNT * outside_training_sessions_per_week,
    )


def _canonical_group(raw_muscle: str) -> str:
    return _MUSCLE_GROUP_MAP.get(raw_muscle, raw_muscle)


def _parse_range(range_str: str) -> Optional[tuple]:
    """'14-18 sets' -> (14.0, 18.0). Returns None if unparseable (defensive -
    LOOK_JACKED_LEVELS is hand-authored prose, not a machine-generated field,
    so this is checked rather than assumed)."""
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", range_str)]
    if len(nums) >= 2:
        return (nums[0], nums[1])
    return None


def landmark_for(
    muscle_group: str,
    experience_level: str,
    primary_goal: Optional[str],
    outside_training_sessions_per_week: Optional[int] = None,
) -> Optional[tuple]:
    """(low, high) weekly-set target for one landmark-tracked muscle group,
    or None if this group isn't one of the 9 tracked (see module docstring)
    or the experience level isn't recognized. `outside_training_sessions_per_week`
    (default None, fully backward compatible) further scales the goal-based
    target down - see outside_training_volume_multiplier above."""
    if muscle_group not in _LANDMARK_TRACKED_GROUPS:
        return None
    level_row = LOOK_JACKED_LEVELS.get(experience_level)
    if not level_row:
        return None
    base = _parse_range(level_row["weekly_sets_per_muscle"])
    if not base:
        return None
    multiplier = (
        GOAL_VOLUME_MULTIPLIER.get(primary_goal, _DEFAULT_GOAL_MULTIPLIER)
        * outside_training_volume_multiplier(outside_training_sessions_per_week)
    )
    return (round(base[0] * multiplier, 1), round(base[1] * multiplier, 1))


def compute_weekly_muscle_sets(engine, day_results: List[Dict]) -> Dict[str, float]:
    """Sums this one week's real prescribed sets per canonical muscle group -
    primary movers at full credit, secondary/assisting muscles at half
    credit (see module docstring for why). `day_results` is the same list
    `program_builder._weekly_muscle_frequency` already consumes."""
    totals: Dict[str, float] = {}
    for day in day_results:
        for pe in day["prescribed_workout"]:
            data = engine.exercises_by_id.get(pe["id"], {})
            sets = pe.get("prescription", {}).get("sets")
            if not isinstance(sets, (int, float)) or sets <= 0:
                continue
            for m in data.get("primary_muscles", []):
                group = _canonical_group(m)
                totals[group] = totals.get(group, 0.0) + sets
            for m in data.get("secondary_muscles", []):
                group = _canonical_group(m)
                totals[group] = totals.get(group, 0.0) + (sets * 0.5)
    return {g: round(v, 1) for g, v in totals.items()}


def evaluate_weekly_volume(
    weekly_sets: Dict[str, float],
    experience_level: str,
    primary_goal: Optional[str],
    outside_training_sessions_per_week: Optional[int] = None,
) -> Dict[str, Dict]:
    """Per muscle group: actual sets this week, the target range (if this
    group is landmark-tracked), and a status a coach would actually give -
    'under', 'optimal', 'high' (above range but not alarmingly so), or
    'excessive' (>1.3x the top of range - the point where junk volume /
    recovery-outrunning-adaptation becomes the more likely story than
    honest extra work capacity). `outside_training_sessions_per_week`
    (default None, backward compatible) is forwarded to landmark_for so a
    program already trimmed for outside training load isn't then flagged
    'under' against an un-trimmed target."""
    result: Dict[str, Dict] = {}
    for group, actual in weekly_sets.items():
        landmark = landmark_for(group, experience_level, primary_goal, outside_training_sessions_per_week)
        if landmark is None:
            result[group] = {
                "weekly_sets": actual,
                "target_range": None,
                "status": "not_tracked",
                "note": "No established weekly-set landmark for this muscle group - logged for visibility, not flagged.",
            }
            continue
        low, high = landmark
        if actual < low:
            status = "under"
            note = f"Below the {low}-{high} set/week target for this goal/experience level - likely not enough stimulus to reliably drive progress."
        elif actual <= high:
            status = "optimal"
            note = f"Within the {low}-{high} set/week target."
        elif actual <= high * 1.3:
            status = "high"
            note = f"Above the {low}-{high} set/week target - fine short-term if recovery (sleep/nutrition/soreness) is holding up, worth trimming if it isn't."
        else:
            status = "excessive"
            note = f"Well above the {low}-{high} set/week target ({actual} vs. a {high} ceiling) - likely to outrun recovery; trim sets or spread across more days."
        result[group] = {
            "weekly_sets": actual,
            "target_range": {"low": low, "high": high},
            "status": status,
            "note": note,
        }
    # Also surface any landmark-tracked group that got ZERO sets this week -
    # otherwise a muscle with no entry in weekly_sets (never touched by any
    # exercise's primary/secondary list) silently disappears from the report
    # instead of showing up as the clearest possible "under" case.
    for group in _LANDMARK_TRACKED_GROUPS:
        if group not in result:
            landmark = landmark_for(group, experience_level, primary_goal, outside_training_sessions_per_week)
            if landmark is None:
                continue
            low, high = landmark
            result[group] = {
                "weekly_sets": 0,
                "target_range": {"low": low, "high": high},
                "status": "under",
                "note": f"Not trained this week - target is {low}-{high} sets/week for this goal/experience level.",
            }
    return dict(sorted(result.items()))

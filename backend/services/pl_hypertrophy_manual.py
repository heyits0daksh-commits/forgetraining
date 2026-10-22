"""
pl_hypertrophy_manual.py — sourced reasoning inputs for the "Powerlifting",
"Look Jacked", and "Strength + Hypertrophy" modes, derived from two source
guides ("Powerlifting Programs" and "Muscle-Building Workout Splits").

WHY THIS EXISTS (post-cleanup)
This module used to also serve those guides' printed tables verbatim
through dedicated `/api/v1/manual/strength/*` endpoints, bypassing the
live, personalized engine entirely — every person got the same static
split regardless of their equipment, injuries, level, or goals. That
verbatim-serving code (`mode_reference()`, `build_split()`, and the
now-removed routes that called them) has been deleted.

What remains is only the two things the LIVE engine actually reasons
over:
- STRENGTH_MODE_EXERCISE_NAMES: the pool of exercises these two guides
  legitimately prescribe, used by progression_engine.py to scope
  candidate selection for these two goal-driven modes — every other
  personalization check (equipment/injury/strength/level) still runs on
  top of this pool exactly as it does for every sport.
- LOOK_JACKED_LEVELS: per-experience-level weekly-sets-per-muscle
  landmarks, used by volume_engine.py as the hypertrophy-goal volume
  baseline that a *generated* program's actual set counts are checked
  against.

Neither of those hands a static split back to a caller — they're just
sourced numbers/pools the live engine's own logic reasons over, same as
sport_profiles.py's data does for every other sport.
"""

from typing import Dict, List

MODES: List[str] = ["Powerlifting", "Look Jacked", "Strength + Hypertrophy"]
LEVELS: List[str] = ["Beginner", "Novice", "Intermediate", "Advanced", "Elite"]

# ---------------------------------------------------------------------------
# Powerlifting Programs guide (Revised Edition)
# ---------------------------------------------------------------------------

POWERLIFTING_SPLITS: Dict[str, Dict] = {
    "5day": {
        "name": "5-Day Split — Squat / Bench / Deadlift / Bench / Squat",
        "note": "High frequency on the big three — best for intermediate/advanced lifters chasing a total who recover well between sessions",
        "days": [
            {"label": "Day 1 — Squat (Heavy)", "rows": [
                {"exercise": "Competition Squat", "loading": "5x5 @ 75-80%"},
                {"exercise": "Front Squat", "loading": "3x8"},
                {"exercise": "Leg Press", "loading": "3x10"},
                {"exercise": "Weighted Plank", "loading": "3x45s"},
            ]},
            {"label": "Day 2 — Bench (Heavy)", "rows": [
                {"exercise": "Competition Bench Press", "loading": "5x5 @ 75-80%"},
                {"exercise": "Close-Grip Bench Press", "loading": "3x6"},
                {"exercise": "DB Bench Press", "loading": "3x10"},
                {"exercise": "Face Pull", "loading": "3x15"},
            ]},
            {"label": "Day 3 — Deadlift (Heavy)", "rows": [
                {"exercise": "Competition Deadlift", "loading": "5x3 @ 80-85%"},
                {"exercise": "Romanian Deadlift", "loading": "3x8"},
                {"exercise": "Barbell Row", "loading": "3x8"},
                {"exercise": "Hanging Leg Raise", "loading": "3x12"},
            ]},
            {"label": "Day 4 — Bench (Volume / Technique)", "rows": [
                {"exercise": "Paused Bench Press", "loading": "4x6 @ 70%"},
                {"exercise": "Overhead Press", "loading": "3x8"},
                {"exercise": "Lateral Raise", "loading": "3x15"},
                {"exercise": "Skull Crusher", "loading": "3x12"},
            ]},
            {"label": "Day 5 — Squat (Volume) + Posterior Chain", "rows": [
                {"exercise": "Paused Squat", "loading": "4x5 @ 70%"},
                {"exercise": "Good Morning", "loading": "3x8"},
                {"exercise": "Leg Curl", "loading": "3x12"},
                {"exercise": "Ab Wheel Rollout", "loading": "3x10"},
            ]},
        ],
    },
    "4day": {
        "name": "4-Day Split — Squat / Bench / Deadlift / Bench",
        "note": "The classic powerlifting template — one dedicated day per lift plus a second bench day",
        "days": [
            {"label": "Day 1 — Squat", "rows": [
                {"exercise": "Competition Squat", "loading": "5x5 @ 75%"},
                {"exercise": "Front Squat", "loading": "3x8"},
                {"exercise": "Leg Press", "loading": "3x10"},
                {"exercise": "Weighted Plank", "loading": "3x45s"},
            ]},
            {"label": "Day 2 — Bench", "rows": [
                {"exercise": "Competition Bench Press", "loading": "5x5 @ 75%"},
                {"exercise": "Close-Grip Bench Press", "loading": "3x8"},
                {"exercise": "DB Bench Press", "loading": "3x10"},
                {"exercise": "Face Pull", "loading": "3x15"},
            ]},
            {"label": "Day 3 — Deadlift", "rows": [
                {"exercise": "Competition Deadlift", "loading": "5x3 @ 80%"},
                {"exercise": "Romanian Deadlift", "loading": "3x8"},
                {"exercise": "Barbell Row", "loading": "3x8"},
                {"exercise": "Hanging Leg Raise", "loading": "3x12"},
            ]},
            {"label": "Day 4 — Bench (2nd) / Overhead", "rows": [
                {"exercise": "Paused Bench Press", "loading": "4x6 @ 70%"},
                {"exercise": "Overhead Press", "loading": "3x8"},
                {"exercise": "Skull Crusher", "loading": "3x12"},
                {"exercise": "Lateral Raise", "loading": "3x15"},
            ]},
        ],
    },
    "3day": {
        "name": "3-Day Split — Full Body (Squat / Bench / Deadlift each week)",
        "note": "All three lifts trained weekly across three sessions. Lower frequency per lift, so each session runs 2 main lifts + 2 accessories",
        "days": [
            {"label": "Day A — Squat + Bench", "rows": [
                {"exercise": "Competition Squat", "loading": "5x5 @ 75%"},
                {"exercise": "Competition Bench Press", "loading": "5x5 @ 75%"},
                {"exercise": "Close-Grip Bench Press", "loading": "3x8"},
                {"exercise": "Barbell Row", "loading": "3x8"},
            ]},
            {"label": "Day B — Deadlift + Overhead Press", "rows": [
                {"exercise": "Competition Deadlift", "loading": "5x3 @ 80%"},
                {"exercise": "Overhead Press", "loading": "3x6"},
                {"exercise": "Romanian Deadlift", "loading": "3x8"},
                {"exercise": "Face Pull", "loading": "3x15"},
            ]},
            {"label": "Day C — Squat Variation + Bench Variation", "rows": [
                {"exercise": "Paused Squat", "loading": "4x5 @ 70%"},
                {"exercise": "Paused Bench Press", "loading": "4x6 @ 70%"},
                {"exercise": "Leg Press", "loading": "3x10"},
                {"exercise": "DB Bench Press", "loading": "3x10"},
            ]},
        ],
    },
    "2day": {
        "name": "2-Day Split — Squat+Bench / Deadlift+Bench",
        "note": "Minimal days while still touching all three lifts weekly. Lowest frequency in this guide, so each session runs slightly fuller — 2 main lifts + 3 accessories",
        "days": [
            {"label": "Day 1 — Squat + Bench", "rows": [
                {"exercise": "Competition Squat", "loading": "5x5 @ 75%"},
                {"exercise": "Competition Bench Press", "loading": "5x5 @ 75%"},
                {"exercise": "Front Squat", "loading": "3x8"},
                {"exercise": "Close-Grip Bench Press", "loading": "3x8"},
                {"exercise": "Barbell Row", "loading": "3x8"},
            ]},
            {"label": "Day 2 — Deadlift + Bench Variation", "rows": [
                {"exercise": "Competition Deadlift", "loading": "5x3 @ 80%"},
                {"exercise": "Paused Bench Press", "loading": "4x6 @ 70%"},
                {"exercise": "Romanian Deadlift", "loading": "3x8"},
                {"exercise": "Overhead Press", "loading": "3x8"},
                {"exercise": "Face Pull", "loading": "3x15"},
            ]},
        ],
    },
}

# ---------------------------------------------------------------------------
# Muscle-Building Workout Splits guide ("Look Jacked", Revised Edition)
# ---------------------------------------------------------------------------

LOOK_JACKED_LEVELS: Dict[str, Dict[str, str]] = {
    "Beginner": {
        "training_age": "0-6 months", "weekly_sets_per_muscle": "8-10 sets", "sets_per_exercise": "2-3 sets",
        "rep_range": "10-15 reps", "rest": "90-120s", "effort_rir": "3-4 RIR",
        "exercise_selection": "Main lifts only — master the pattern.",
    },
    "Novice": {
        "training_age": "6-18 months", "weekly_sets_per_muscle": "10-14 sets", "sets_per_exercise": "3 sets",
        "rep_range": "8-12 reps", "rest": "90s", "effort_rir": "2-3 RIR",
        "exercise_selection": "Main lift + 1 accessory.",
    },
    "Intermediate": {
        "training_age": "1.5-3 years", "weekly_sets_per_muscle": "14-18 sets", "sets_per_exercise": "3-4 sets",
        "rep_range": "6-12 reps", "rest": "60-90s", "effort_rir": "1-2 RIR",
        "exercise_selection": "Full S+A as programmed below.",
    },
    "Advanced": {
        "training_age": "3-5 years", "weekly_sets_per_muscle": "18-20 sets", "sets_per_exercise": "4 sets",
        "rep_range": "6-10 reps", "rest": "60-90s", "effort_rir": "0-2 RIR",
        "exercise_selection": "As programmed + intensity techniques on the last set.",
    },
    "Elite": {
        "training_age": "5+ years / competitive", "weekly_sets_per_muscle": "20-22 sets", "sets_per_exercise": "4-5 sets",
        "rep_range": "Undulating 4-15", "rest": "60-120s", "effort_rir": "0-1 RIR",
        "exercise_selection": "Full bank rotated weekly, periodized blocks, planned overreach.",
    },
}
LOOK_JACKED_SPLITS: Dict[str, Dict] = {
    "5day": {
        "name": "5-Day Split — Push / Pull / Legs / Upper / Lower",
        "note": "Best for intermediate/advanced lifters — each muscle trained ~2x/week. High frequency means each session stays lean: 2 main lifts + 2-3 accessories, no more",
        "days": [
            {"label": "Day 1 — Push (Chest, Shoulders, Triceps)", "rows": [
                {"exercise": "Barbell Bench Press", "sets_reps": "4x6-10"},
                {"exercise": "Standing Overhead Press", "sets_reps": "3x6-10"},
                {"exercise": "Weighted Dips", "sets_reps": "3x10-15"},
                {"exercise": "Cable Lateral Raise", "sets_reps": "3x12-15"},
                {"exercise": "Overhead Cable Triceps Extension", "sets_reps": "3x10-15"},
            ]},
            {"label": "Day 2 — Pull (Back, Biceps)", "rows": [
                {"exercise": "Weighted Pull-Up", "sets_reps": "4x6-10"},
                {"exercise": "Barbell Row", "sets_reps": "3x6-10"},
                {"exercise": "Face Pull", "sets_reps": "3x12-15"},
                {"exercise": "Barbell Curl", "sets_reps": "3x10-12"},
                {"exercise": "Meadows Row", "sets_reps": "3x10-12"},
            ]},
            {"label": "Day 3 — Legs (Quads, Hams, Glutes, Calves)", "rows": [
                {"exercise": "Back Squat", "sets_reps": "4x6-10"},
                {"exercise": "Romanian Deadlift", "sets_reps": "3x8-10"},
                {"exercise": "Leg Press", "sets_reps": "3x10-15"},
                {"exercise": "Leg Curl", "sets_reps": "3x10-15"},
                {"exercise": "Standing Calf Raise", "sets_reps": "3x10-15"},
            ]},
            {"label": "Day 4 — Upper (2nd hit, different angles)", "rows": [
                {"exercise": "Incline DB Press", "sets_reps": "3x8-12"},
                {"exercise": "Chest-Supported Row", "sets_reps": "3x8-12"},
                {"exercise": "Seated DB Shoulder Press", "sets_reps": "3x10-12"},
                {"exercise": "Rear Delt Fly", "sets_reps": "3x12-15"},
                {"exercise": "Hammer Curl / Skull Crusher (superset)", "sets_reps": "3x10-12 each"},
            ]},
            {"label": "Day 5 — Lower (2nd hit, different angles)", "rows": [
                {"exercise": "Front Squat or Hack Squat", "sets_reps": "3x8-12"},
                {"exercise": "Conventional Deadlift", "sets_reps": "3x5-8"},
                {"exercise": "Hip Thrust", "sets_reps": "3x10-12"},
                {"exercise": "Hanging Leg Raise", "sets_reps": "3x10-15"},
            ]},
        ],
    },
    "4day": {
        "name": "4-Day Split — Upper / Lower x2",
        "note": "Best overall balance of frequency and recovery for most lifters. 3 main lifts + 2 accessories per session",
        "days": [
            {"label": "Day 1 — Upper A", "rows": [
                {"exercise": "Barbell Bench Press", "sets_reps": "4x6-10"},
                {"exercise": "Barbell Row", "sets_reps": "3x6-10"},
                {"exercise": "Standing Overhead Press", "sets_reps": "3x6-10"},
                {"exercise": "Lat Pulldown", "sets_reps": "3x10-12"},
                {"exercise": "Barbell Curl", "sets_reps": "3x10-12"},
            ]},
            {"label": "Day 2 — Lower A", "rows": [
                {"exercise": "Back Squat", "sets_reps": "4x6-10"},
                {"exercise": "Romanian Deadlift", "sets_reps": "3x8-10"},
                {"exercise": "Leg Press", "sets_reps": "3x10-15"},
                {"exercise": "Leg Curl", "sets_reps": "3x10-15"},
                {"exercise": "Standing Calf Raise", "sets_reps": "3x10-15"},
            ]},
            {"label": "Day 3 — Upper B", "rows": [
                {"exercise": "Incline DB Press", "sets_reps": "3x8-12"},
                {"exercise": "Weighted Pull-Up", "sets_reps": "4x6-10"},
                {"exercise": "Seated DB Shoulder Press", "sets_reps": "3x10-12"},
                {"exercise": "Weighted Dips", "sets_reps": "3x10-15"},
                {"exercise": "Face Pull", "sets_reps": "3x12-15"},
            ]},
            {"label": "Day 4 — Lower B", "rows": [
                {"exercise": "Deadlift", "sets_reps": "3x5-8"},
                {"exercise": "Front Squat", "sets_reps": "3x8-12"},
                {"exercise": "Hip Thrust", "sets_reps": "3x10-12"},
                {"exercise": "Seated Calf Raise", "sets_reps": "3x10-15"},
                {"exercise": "Hanging Leg Raise", "sets_reps": "3x10-15"},
            ]},
        ],
    },
    "3day": {
        "name": "3-Day Split — Full Body x3",
        "note": "Strong frequency (3x/muscle/week); emphasis rotates each day. 3 main lifts + 2 accessories per session",
        "days": [
            {"label": "Day 1 — Full Body A", "rows": [
                {"exercise": "Back Squat", "sets_reps": "3x6-10"},
                {"exercise": "Barbell Bench Press", "sets_reps": "3x6-10"},
                {"exercise": "Barbell Row", "sets_reps": "3x6-10"},
                {"exercise": "Leg Curl", "sets_reps": "3x10-15"},
                {"exercise": "Face Pull", "sets_reps": "3x12-15"},
            ]},
            {"label": "Day 2 — Full Body B", "rows": [
                {"exercise": "Deadlift", "sets_reps": "3x5-8"},
                {"exercise": "Weighted Pull-Up", "sets_reps": "3x6-10"},
                {"exercise": "Incline DB Press", "sets_reps": "3x8-12"},
                {"exercise": "Bulgarian Split Squat", "sets_reps": "3x10-12/leg"},
                {"exercise": "Hammer Curl", "sets_reps": "3x10-12"},
            ]},
            {"label": "Day 3 — Full Body C", "rows": [
                {"exercise": "Front Squat or Leg Press", "sets_reps": "3x8-12"},
                {"exercise": "Seated DB Shoulder Press", "sets_reps": "3x10-12"},
                {"exercise": "Chest-Supported Row", "sets_reps": "3x8-12"},
                {"exercise": "Cable Fly", "sets_reps": "3x12-15"},
                {"exercise": "Standing Calf Raise", "sets_reps": "3x10-15"},
            ]},
        ],
    },
    "2day": {
        "name": "2-Day Split — Full Body x2",
        "note": "Minimal days, still hits every major muscle group twice a week. Lowest frequency in this guide, so each session runs slightly fuller — 4 main lifts + 2 accessories",
        "days": [
            {"label": "Day 1 — Full Body A", "rows": [
                {"exercise": "Back Squat", "sets_reps": "3x6-10"},
                {"exercise": "Barbell Bench Press", "sets_reps": "3x6-10"},
                {"exercise": "Barbell Row", "sets_reps": "3x6-10"},
                {"exercise": "Standing Overhead Press", "sets_reps": "3x6-10"},
                {"exercise": "Romanian Deadlift", "sets_reps": "3x8-10"},
                {"exercise": "Barbell Curl", "sets_reps": "3x10-12"},
            ]},
            {"label": "Day 2 — Full Body B", "rows": [
                {"exercise": "Deadlift", "sets_reps": "3x5-8"},
                {"exercise": "Incline DB Press", "sets_reps": "3x8-12"},
                {"exercise": "Weighted Pull-Up", "sets_reps": "3x6-10"},
                {"exercise": "Bulgarian Split Squat", "sets_reps": "3x10-12/leg"},
                {"exercise": "Lateral Raise", "sets_reps": "3x12-15"},
                {"exercise": "Face Pull", "sets_reps": "3x12-15"},
            ]},
        ],
    },
    "5day_bro_split": {
        "name": "5-Day Split — Bro Split (Body-Part x5)",
        "note": "One muscle group per day, trained once a week — lowest frequency in this guide, so each session runs fuller (2 main lifts + 3 accessories). Best suited to advanced bodybuilders training for physique; if natural and still building your base, an Upper/Lower or Full Body split will grow you faster per hour — run this by choice, not by default",
        "days": [
            {"label": "Day 1 — Chest", "rows": [
                {"exercise": "Barbell Bench Press", "sets_reps": "4x6-10"},
                {"exercise": "Incline DB Press", "sets_reps": "3x8-12"},
                {"exercise": "Weighted Dips", "sets_reps": "3x10-15"},
                {"exercise": "Mid Cable Fly", "sets_reps": "3x12-15"},
                {"exercise": "Pec Deck", "sets_reps": "3x12-15"},
            ]},
            {"label": "Day 2 — Back", "rows": [
                {"exercise": "Weighted Pull-Up", "sets_reps": "4x6-10"},
                {"exercise": "Barbell Row", "sets_reps": "3x6-10"},
                {"exercise": "Lat Pulldown", "sets_reps": "3x10-12"},
                {"exercise": "Chest-Supported Row", "sets_reps": "3x10-12"},
                {"exercise": "Straight-Arm Pulldown", "sets_reps": "3x12-15"},
            ]},
            {"label": "Day 3 — Shoulders", "rows": [
                {"exercise": "Standing Overhead Press", "sets_reps": "4x6-10"},
                {"exercise": "Seated DB Shoulder Press", "sets_reps": "3x8-12"},
                {"exercise": "Cable Lateral Raise", "sets_reps": "3x12-15"},
                {"exercise": "Rear Delt Fly", "sets_reps": "3x12-15"},
                {"exercise": "Face Pull", "sets_reps": "3x12-15"},
            ]},
            {"label": "Day 4 — Arms (Biceps, Triceps)", "rows": [
                {"exercise": "Barbell Curl", "sets_reps": "3x8-12"},
                {"exercise": "Close-Grip Bench Press", "sets_reps": "3x8-12"},
                {"exercise": "Incline DB Curl", "sets_reps": "3x10-12"},
                {"exercise": "Overhead Cable Triceps Extension", "sets_reps": "3x10-15"},
                {"exercise": "Cable Pushdown", "sets_reps": "3x10-15"},
            ]},
            {"label": "Day 5 — Legs", "rows": [
                {"exercise": "Back Squat", "sets_reps": "4x6-10"},
                {"exercise": "Romanian Deadlift", "sets_reps": "3x8-10"},
                {"exercise": "Leg Press", "sets_reps": "3x10-15"},
                {"exercise": "Leg Curl", "sets_reps": "3x10-15"},
                {"exercise": "Standing Calf Raise", "sets_reps": "3x10-15"},
            ]},
        ],
    },
}

# The printed guide names a movement generically ("Competition Squat",
# "DB Bench Press") or with phrasing (hyphens, "X or Y" choices, an "A / B
# (superset)" pair) that doesn't exist byte-for-byte as an exercises.json
# `name` - the database catalogs dozens of loaded variants of the same
# pattern (Barbell Back Squat, Buffalo Bar Squat, ...) rather than a single
# generic entry. This maps every guide row to the closest real catalog
# exercise (same equipment/pattern the row calls for) so the mode-restricted
# pool in progression_engine.py actually resolves to real exercises instead
# of silently going empty. A guide name already identical to a catalog name
# needs no entry here. A handful of guide movements (Hammer Curl, Incline DB
# Curl) have no equivalent anywhere in the catalog - they're left unmapped,
# so that single slot is simply not offered rather than substituted with
# something that isn't the same movement.
# ---------------------------------------------------------------------------
# "Strength + Hypertrophy" tier — third mode, added alongside the two guides
# above. UNLIKE Powerlifting/Look Jacked, its source PDF gives only the raw
# prescription (5-8 reps, 70-82% 1RM) with no day-by-day split tables to
# transcribe — so the splits/bank below are designed in-house, not
# transcribed verbatim, and are laid out to sit deliberately between the
# other two: main lifts stay in the PDF's 5-8 rep / 70-82% band (heavier
# than Look Jacked, higher-rep than most of Powerlifting), each followed by
# 8-12 rep accessories so real hypertrophy volume gets banked every session
# instead of only on "off" days.
# ---------------------------------------------------------------------------

STRENGTH_HYPERTROPHY_SPLITS: Dict[str, Dict] = {
    "5day": {
        "name": "5-Day Split — Push / Pull / Legs / Upper / Lower",
        "note": "Highest frequency here — each session stays lean (2 main lifts + 2-3 accessories) so the 5-8 rep main work doesn't stack into excess fatigue",
        "days": [
            {"label": "Day 1 — Push (Chest, Shoulders, Triceps)", "rows": [
                {"exercise": "Barbell Bench Press", "sets_reps": "4x5-8 @ 70-82%"},
                {"exercise": "Standing Overhead Press", "sets_reps": "3x6-8"},
                {"exercise": "Weighted Dips", "sets_reps": "3x8-12"},
                {"exercise": "Cable Lateral Raise", "sets_reps": "3x12-15"},
                {"exercise": "Cable Pushdown", "sets_reps": "3x10-12"},
            ]},
            {"label": "Day 2 — Pull (Back, Biceps)", "rows": [
                {"exercise": "Barbell Row", "sets_reps": "4x5-8 @ 70-82%"},
                {"exercise": "Weighted Pull-Up", "sets_reps": "3x6-8"},
                {"exercise": "Face Pull", "sets_reps": "3x12-15"},
                {"exercise": "Barbell Curl", "sets_reps": "3x10-12"},
            ]},
            {"label": "Day 3 — Legs (Quads, Hams, Glutes, Calves)", "rows": [
                {"exercise": "Back Squat", "sets_reps": "4x5-8 @ 70-82%"},
                {"exercise": "Romanian Deadlift", "sets_reps": "3x6-8"},
                {"exercise": "Leg Press", "sets_reps": "3x10-15"},
                {"exercise": "Leg Curl", "sets_reps": "3x10-15"},
                {"exercise": "Standing Calf Raise", "sets_reps": "3x10-15"},
            ]},
            {"label": "Day 4 — Upper (2nd hit, different angles)", "rows": [
                {"exercise": "Incline DB Press", "sets_reps": "3x8-12"},
                {"exercise": "Chest-Supported Row", "sets_reps": "3x8-12"},
                {"exercise": "Seated DB Shoulder Press", "sets_reps": "3x10-12"},
                {"exercise": "Rear Delt Fly", "sets_reps": "3x12-15"},
            ]},
            {"label": "Day 5 — Lower (2nd hit, different angles)", "rows": [
                {"exercise": "Front Squat", "sets_reps": "3x6-8 @ 70-82%"},
                {"exercise": "Conventional Deadlift", "sets_reps": "3x5-8 @ 70-82%"},
                {"exercise": "Hip Thrust", "sets_reps": "3x10-12"},
                {"exercise": "Hanging Leg Raise", "sets_reps": "3x10-15"},
            ]},
        ],
    },
    "4day": {
        "name": "4-Day Split — Upper / Lower x2",
        "note": "The default recommendation for this mode — dedicated heavy Upper/Lower days for the 5-8 rep main lifts, plus a second Upper/Lower pass built almost entirely from 8-12 rep hypertrophy accessories",
        "days": [
            {"label": "Day 1 — Upper A (Strength)", "rows": [
                {"exercise": "Barbell Bench Press", "sets_reps": "4x5-8 @ 70-82%"},
                {"exercise": "Barbell Row", "sets_reps": "4x5-8 @ 70-82%"},
                {"exercise": "Standing Overhead Press", "sets_reps": "3x6-8"},
                {"exercise": "Lat Pulldown", "sets_reps": "3x8-12"},
                {"exercise": "Barbell Curl", "sets_reps": "3x8-12"},
                {"exercise": "Cable Pushdown", "sets_reps": "3x8-12"},
            ]},
            {"label": "Day 2 — Lower A (Strength)", "rows": [
                {"exercise": "Back Squat", "sets_reps": "4x5-8 @ 70-82%"},
                {"exercise": "Romanian Deadlift", "sets_reps": "3x6-8"},
                {"exercise": "Leg Press", "sets_reps": "3x8-12"},
                {"exercise": "Leg Curl", "sets_reps": "3x8-12"},
                {"exercise": "Standing Calf Raise", "sets_reps": "3x10-15"},
            ]},
            {"label": "Day 3 — Upper B (Hypertrophy)", "rows": [
                {"exercise": "Incline DB Press", "sets_reps": "4x8-12"},
                {"exercise": "Chest-Supported Row", "sets_reps": "4x8-12"},
                {"exercise": "Seated DB Shoulder Press", "sets_reps": "3x10-12"},
                {"exercise": "Face Pull", "sets_reps": "3x12-15"},
                {"exercise": "Skull Crusher", "sets_reps": "3x10-12"},
            ]},
            {"label": "Day 4 — Lower B (Hypertrophy)", "rows": [
                {"exercise": "Front Squat", "sets_reps": "3x8-12"},
                {"exercise": "Conventional Deadlift", "sets_reps": "3x5-8 @ 70-82%"},
                {"exercise": "Hip Thrust", "sets_reps": "3x10-12"},
                {"exercise": "Leg Extension", "sets_reps": "3x12-15"},
                {"exercise": "Hanging Leg Raise", "sets_reps": "3x10-15"},
            ]},
        ],
    },
    "3day": {
        "name": "3-Day Split — Full Body",
        "note": "Lower frequency, so each of the three main lifts (squat/bench/deadlift-pattern) is hit once per session alongside 2-3 accessories",
        "days": [
            {"label": "Day A", "rows": [
                {"exercise": "Back Squat", "sets_reps": "4x5-8 @ 70-82%"},
                {"exercise": "Barbell Bench Press", "sets_reps": "4x5-8 @ 70-82%"},
                {"exercise": "Barbell Row", "sets_reps": "3x8-12"},
                {"exercise": "Leg Curl", "sets_reps": "3x10-12"},
            ]},
            {"label": "Day B", "rows": [
                {"exercise": "Conventional Deadlift", "sets_reps": "3x5-8 @ 70-82%"},
                {"exercise": "Standing Overhead Press", "sets_reps": "3x6-8"},
                {"exercise": "Lat Pulldown", "sets_reps": "3x8-12"},
                {"exercise": "Standing Calf Raise", "sets_reps": "3x10-15"},
            ]},
            {"label": "Day C", "rows": [
                {"exercise": "Front Squat", "sets_reps": "3x6-8 @ 70-82%"},
                {"exercise": "Incline DB Press", "sets_reps": "3x8-12"},
                {"exercise": "Chest-Supported Row", "sets_reps": "3x8-12"},
                {"exercise": "Face Pull", "sets_reps": "3x12-15"},
            ]},
        ],
    },
    "2day": {
        "name": "2-Day Split — Upper / Lower",
        "note": "Minimal days while still hitting every main lift weekly at the full 5-8 rep / 70-82% prescription; each session runs slightly fuller to cover the muscle group in one pass",
        "days": [
            {"label": "Day 1 — Upper", "rows": [
                {"exercise": "Barbell Bench Press", "sets_reps": "4x5-8 @ 70-82%"},
                {"exercise": "Barbell Row", "sets_reps": "4x5-8 @ 70-82%"},
                {"exercise": "Standing Overhead Press", "sets_reps": "3x8-12"},
                {"exercise": "Lat Pulldown", "sets_reps": "3x8-12"},
                {"exercise": "Barbell Curl", "sets_reps": "3x10-12"},
                {"exercise": "Cable Pushdown", "sets_reps": "3x10-12"},
            ]},
            {"label": "Day 2 — Lower", "rows": [
                {"exercise": "Back Squat", "sets_reps": "4x5-8 @ 70-82%"},
                {"exercise": "Conventional Deadlift", "sets_reps": "3x5-8 @ 70-82%"},
                {"exercise": "Leg Press", "sets_reps": "3x8-12"},
                {"exercise": "Leg Curl", "sets_reps": "3x8-12"},
                {"exercise": "Hip Thrust", "sets_reps": "3x10-12"},
                {"exercise": "Standing Calf Raise", "sets_reps": "3x10-15"},
            ]},
        ],
    },
}

GUIDE_TO_CATALOG_NAME: Dict[str, str] = {
    "competition squat": "Barbell Back Squat",
    "competition bench press": "Flat Bench Press",
    "competition deadlift": "Barbell Conventional Deadlift",
    "conventional deadlift": "Barbell Conventional Deadlift",
    "deadlift": "Barbell Conventional Deadlift",
    "back squat": "Barbell Back Squat",
    "barbell bench press": "Flat Bench Press",
    "front squat": "Barbell Front Squat",
    "hack squat": "Hack Squat Machine",
    "db bench press": "Dumbbell Bench Press",
    "incline db press": "Incline Dumbbell Bench Press",
    "close-grip bench press": "Close Grip Bench Press",
    "paused bench press": "Pin Bench Press (Mid-Range)",
    "paused squat": "Pause Back Squat",
    "barbell row": "Barbell Bent-Over Row",
    "chest-supported row": "Chest Supported Row",
    "face pull": "Cable Face Pull",
    "overhead press": "Barbell Overhead Press",
    "standing overhead press": "Barbell Overhead Press",
    "seated db shoulder press": "Standing Dumbbell Shoulder Press",
    "lateral raise": "Cable Lateral Raise",
    "rear delt fly": "Reverse Pec Deck (Rear Delt Fly)",
    "cable fly": "Cable Chest Fly",
    "mid cable fly": "Cable Chest Fly",
    "pec deck": "Pec Deck Fly",
    "skull crusher": "EZ Bar Skullcrusher",
    "overhead cable triceps extension": "Cable Overhead Tricep Extension",
    "cable pushdown": "Cable Tricep Pushdown",
    "barbell curl": "EZ Bar Curl",
    "weighted dips": "Weighted Vest Dip",
    "leg curl": "Lying Leg Curl",
    "good morning": "Good Morning",
    "hip thrust": "Single-Leg Hip Thrust",
    "standing calf raise": "Calf Press on Leg Press Machine",
    "seated calf raise": "Calf Press on Leg Press Machine",
    "weighted plank": "Front Plank",
}

# Rows that name two exercises in one string (a coach's "either works" call
# or an explicit superset) - split so both resolve as separate candidates
# instead of the whole phrase failing to match anything.
_MULTI_EXERCISE_SEPARATORS = (" or ", " / ")


def _split_row_exercise(raw: str) -> List[str]:
    text = raw.split("(")[0].strip()  # drop a trailing "(superset)" qualifier
    for sep in _MULTI_EXERCISE_SEPARATORS:
        if sep in text:
            return [part.strip() for part in text.split(sep)]
    return [text]


# mode -> lowercase set of every real catalog exercise name the guide itself
# prescribes for that mode (every day-table row across every split, resolved
# through GUIDE_TO_CATALOG_NAME, deduped) - used to restrict the live
# session/program engine's candidate pool to exactly what the guide lists
# for "Powerlifting" and "Look Jacked" mode, instead of the generic
# Transfer-score sport engine picking from the full database (see
# progression_engine.py's STRENGTH_MODE_EXERCISE_NAMES usage). Built from the
# printed day tables, not the Master Exercise Bank, so an alternate that's
# only in the bank (never in a programmed day) doesn't get pulled into a
# live session - it stays a manual reference-only alternate, same as before.
def _names_from_splits(splits: Dict[str, Dict]) -> set:
    names = set()
    for split in splits.values():
        for day in split["days"]:
            for row in day["rows"]:
                for exercise in _split_row_exercise(row["exercise"]):
                    key = exercise.strip().lower()
                    resolved = GUIDE_TO_CATALOG_NAME.get(key, exercise.strip())
                    names.add(resolved.strip().lower())
    return names


STRENGTH_MODE_EXERCISE_NAMES: Dict[str, set] = {
    "Powerlifting": _names_from_splits(POWERLIFTING_SPLITS),
    "Look Jacked": _names_from_splits(LOOK_JACKED_SPLITS),
    "Strength + Hypertrophy": _names_from_splits(STRENGTH_HYPERTROPHY_SPLITS),
}

# NOTE: the verbatim "give me the guide's literal printed table" reader
# (formerly `_DATA` / `mode_reference()` / `build_split()`) has been removed.
# Only STRENGTH_MODE_EXERCISE_NAMES (the exercise-name pool derived from the
# splits below) and LOOK_JACKED_LEVELS (per-level weekly-set landmarks) are
# real reasoning inputs the live engine uses — see progression_engine.py and
# volume_engine.py. Nothing in this file serves a printed table directly to
# an API caller anymore; everything below only feeds the live engine's own
# personalization logic.

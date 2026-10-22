"""
schemas.py - all request/response Pydantic models for the FORGE API, plus the
two constant lists (EXPERIENCE_LEVELS, PRIMARY_GOALS) that both the engine and
the schemas need to agree on.

WHY THIS EXISTS
This used to live inline at the top of backend/main.py. Pulled out so that:
  - backend/services/program_builder.py can import WorkoutRequest/ProgramRequest
    without importing all of main.py (which would import program_builder.py
    right back - a cycle).
  - main.py stays focused on the engine + routes (Phase 2 of the roadmap:
    api/models/services split).

Nothing about field names, defaults, or validation changed for the schemas
that already existed in main.py - this is a pure move, except for the two
new WorkoutRequest fields (target_categories, target_muscles, exercise_limit)
and the new ProgramRequest model, both added to support the Program Builder
(backend/services/program_builder.py).
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Deliberately not pydantic's EmailStr: that type requires the optional
# `email-validator` package, which isn't in requirements.txt or installed in
# every environment this runs in. This regex is intentionally permissive
# (format sanity, not full RFC 5322/mailbox-existence checking) - real
# deliverability is verified by the confirmation-email flow, when that's
# built, not by request validation.
_EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"

EXPERIENCE_LEVELS = ["Beginner", "Novice", "Intermediate", "Advanced", "Elite"]


def _normalize_to_canonical(value: Any, canonical_values: List[str]) -> Any:
    """Case-insensitive match of `value` against `canonical_values`, returning
    the canonically-cased entry when found (e.g. "intermediate" -> "Intermediate",
    "BUILD MUSCLE" -> "Build Muscle"). Returns `value` unchanged when it isn't a
    string, is empty, or doesn't match anything - the field's own Literal
    validation is still the source of truth for what's actually accepted, this
    only fixes casing so a real value doesn't 422 purely because a caller sent
    different capitalization than GET /api/v1/metadata's /goals returns. Used
    as a `mode="before"` field_validator, so it runs before Literal validation,
    not instead of it.
    """
    if not isinstance(value, str) or not value.strip():
        return value
    stripped = value.strip()
    lowered = stripped.lower()
    for candidate in canonical_values:
        if candidate.lower() == lowered:
            return candidate
    return value

# The goals the Program Builder wizard offers (spec: "Program Builder ->
# Primary Goal", extended with "Power / Explosiveness" for power/speed-
# focused athletes previously unserved by "Get Strong" (max strength) or
# "Athletic Performance" (general sport athleticism)). This was originally a
# performance S&C tool for combat/tactical/field-sport athletes only, and
# aesthetics-driven goals ("Build Muscle", "Lose Fat") were deliberately left
# out - see the v-prior note this replaces. "Build Muscle" has since been
# added back as a hypertrophy-focused goal (higher reps, lower load%, more
# sets - same GOAL_PROFILES["bias"]="hypertrophy" mechanism the DUP day
# cycle already uses in program_builder.py, plus an athletic_qualities
# "Hypertrophy"-score ranking nudge in sport_profiles.hypertrophy_quality_multiplier).
# "Strength + Hypertrophy" was added the same way, to close the gap
# program_builder._GOAL_WINDOWS used to flag directly: the FORGE Complete
# Exercise Prescription Packet's Section 1 table has a dedicated "Strength +
# hypertrophy" row (5-8 reps, 3-4 sets, 70-82% 1RM) sitting between "Get
# Strong" (2-6 reps, 75-90%) and "Build Muscle" (6-12 reps, 60-80%) that
# neither existing goal reproduces - picking either as a stand-in always
# lands outside that row's own window.
# Neither addition touches any of the existing performance goals or the
# safety/injury/equipment/strength filtering every goal shares. Keys of
# GOAL_PROFILES in program_builder.py must match this list exactly -
# GOAL_PROFILES falls back to "General Fitness" for anything unrecognized,
# but the API-facing list of *valid* choices is this one.
PRIMARY_GOALS = [
    "Get Strong",
    "Strength + Hypertrophy",
    "Build Muscle",
    "Power / Explosiveness",
    "Athletic Performance",
    "Conditioning",
    "Skill Development",
    "General Fitness",
]

# The 4 energy-system emphases a coach would actually program a Conditioning/
# Jump/Power exercise's work:rest interval around, instead of one flat
# difficulty-only formula regardless of what the athlete is training:
#   - Alactic (Power/Speed) - phosphagen system, ~5-15s max-effort bursts,
#     near-full recovery between them (long rest so quality never degrades).
#   - Lactic (Anaerobic Capacity) - glycolytic system, ~20-60s sustained
#     high-output efforts, moderate incomplete recovery (the "burn" zone).
#   - Aerobic (Endurance) - steady-state / long intervals, short rest
#     relative to work so heart rate stays elevated across the set.
#   - Mixed - no specific emphasis; reproduces the engine's original
#     difficulty-only formula (default, fully backward compatible).
CONDITIONING_EMPHASES = ["Alactic", "Lactic", "Aerobic", "Mixed"]

# The 5 phases a competition-calendar-driven mesocycle moves through, per
# Combat Sports & Rugby S&C Manual Part 9.3 ("Periodization: Fitting S&C
# Into a Training Year"). Optional on ProgramRequest - omitting it (None,
# the default) preserves every existing caller's behavior exactly
# (days_per_week/goal/sport picks the split, as before). Setting it lets
# the Program Builder follow the manual's phase -> split -> volume ->
# conditioning-focus table instead (see program_builder.PHASE_GUIDANCE).
TRAINING_PHASES = [
    "Off-Season",
    "Pre-Season",
    "In-Season / Fight Camp",
    "Fight Week",
    "Post-Competition",
]


# ==========================================
# Shared building blocks
# ==========================================

class ProgressionOverride(BaseModel):
    exercise_id: str
    # Bounded length: this string round-trips straight into API responses
    # (and from there into the frontend's DOM), so it's kept short and plain
    # even though the web UI already HTML-escapes every name it renders -
    # belt and suspenders, and it stops absurdly large payloads too.
    custom_name: Optional[str] = Field(default=None, max_length=120)
    prerequisites: Optional[List[str]] = None
    equipment: Optional[str] = None
    difficulty: Optional[int] = None


class ReadinessInputs(BaseModel):
    """Optional breakdown behind the single `readiness` slider. Every field is
    optional and independent - send just the ones you actually collected (a
    quick-start caller can still send only `readiness` and skip this entirely).
    When any of these are present, the engine builds a weighted composite
    recovery score instead of using the flat `readiness` number alone, and
    poor sleep / high soreness specifically cap heavy compound-lift intensity
    even on a day where the overall composite doesn't dip into deload range -
    matching how a coach actually reasons ("bad sleep -> lighter on the big
    barbell lifts today", not just "everything x0.9").
    """
    sleep_hours: Optional[float] = Field(default=None, ge=0, le=14, description="Hours slept last night.")
    soreness: Optional[int] = Field(default=None, ge=1, le=5, description="Muscle soreness: 1=none, 5=very sore.")
    stress: Optional[int] = Field(default=None, ge=1, le=5, description="Life/training stress: 1=low, 5=high.")
    energy: Optional[int] = Field(default=None, ge=1, le=5, description="Subjective energy: 1=low, 5=high.")
    motivation: Optional[int] = Field(default=None, ge=1, le=5, description="Motivation to train: 1=low, 5=high.")


class UserBiometrics(BaseModel):
    height_cm: float = Field(..., gt=0, description="Height in cm")
    weight_kg: float = Field(..., gt=0, description="Weight in kg")
    bench_press_1rm: Optional[float] = Field(default=0.0, ge=0, description="Bench Press 1RM in kg")
    squat_1rm: Optional[float] = Field(default=0.0, ge=0, description="Squat 1RM in kg")
    deadlift_1rm: Optional[float] = Field(default=0.0, ge=0, description="Deadlift 1RM in kg")
    pullups_max_reps: Optional[int] = Field(default=0, ge=0, description="Max unbroken bodyweight pull-ups")
    pushups_max_reps: Optional[int] = Field(default=0, ge=0, description="Max unbroken bodyweight push-ups")
    # Optional, and used for exactly one thing: picking which table
    # strength_standards.classify_strength_level() reads (male/female
    # thresholds diverge most in upper-body pressing, less in hip-dominant
    # lifts - see that module's docstring). Omitting it falls back to a
    # blended table, flagged lower-confidence rather than guessed.
    sex: Optional[Literal["male", "female"]] = Field(
        default=None,
        description="Optional - improves the accuracy of the strength-level estimate (GET/POST .../estimate-level). Omit for a blended, lower-confidence estimate.",
    )


# ==========================================
# Single-session request
# ==========================================

class WorkoutRequest(BaseModel):
    mode: Literal["preset", "custom"] = "preset"
    sport: str = "Special Forces"
    experience_level: Literal["Beginner", "Novice", "Intermediate", "Advanced", "Elite"] = "Intermediate"

    @field_validator("experience_level", mode="before")
    @classmethod
    def _normalize_experience_level(cls, v):
        return _normalize_to_canonical(v, EXPERIENCE_LEVELS)
    equipment_available: List[str] = Field(default_factory=lambda: ["Bodyweight"])
    readiness: int = Field(default=80, ge=1, le=100)
    readiness_inputs: Optional[ReadinessInputs] = Field(
        default=None,
        description="Optional sleep/soreness/stress/energy/motivation breakdown - see ReadinessInputs.",
    )
    injuries: List[str] = Field(
        default_factory=list,
        description=(
            "Active injuries. Prefer specific, severity-tagged entries from "
            "GET /api/v1/metadata's 'injuries' list, e.g. "
            "['ACL/Ligament Tear - Grade 2 (Partial Tear)', 'Rotator Cuff Tear - Small (<1cm)']"
            " - these carry a severity tier that scales how much difficulty is still safe "
            "on that joint. Bare joint names or legacy flat tags (e.g. 'Knee', "
            "'Tennis Elbow') still work as a hard block on any exercise stressing that joint."
        ),
    )
    injury_stages: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            "Optional {injury_name: rehab_stage} map for entries also present in `injuries`, "
            "keyed the same way (case-insensitive). rehab_stage is one of GET /api/v1/metadata's "
            "'rehab_stages' list: 'early_recovery', 'controlled_loading', 'strength_rebuilding', "
            "'advanced_strength', 'plyometric_reactive', 'return_to_performance'. An injury left "
            "out of this map (or when the map is omitted entirely) keeps today's severity-only "
            "behavior for that joint - a stage only ever narrows what severity+difficulty already "
            "allowed, e.g. keeping plyometric/reactive work out of a session until the person is "
            "actually in a stage meant to reintroduce it."
        ),
    )
    injury_sides: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            "Optional {injury_name: side} map for entries also present in `injuries`, keyed the "
            "same way (case-insensitive). side is one of 'left', 'right', 'bilateral'. Only "
            "matters for exercises the database already marks as trained one side at a time "
            "(movement_type == 'Unilateral', e.g. Single-Leg Leg Press, Single-Arm Dumbbell Row, "
            "Pistol Squat) - for those, a one-sided injury no longer blocks the exercise outright; "
            "the engine still prescribes it, with a note to train the uninjured side only. An "
            "injury left out of this map (or the map omitted entirely) is treated as affecting "
            "both sides, keeping today's behavior for that joint. Exercises where both limbs work "
            "in the same set (movement_type 'Bilateral' or 'Alternating', e.g. Back Squat, Walking "
            "Lunge) are unaffected by this field - a one-sided injury still loads through them."
        ),
    )
    biometrics: Optional[UserBiometrics] = None
    custom_progressions: Optional[List[ProgressionOverride]] = None

    # When True, restricts eligible candidates to exercises tagged
    # "in_manual": true in exercises.json (i.e. exercises that also appear
    # in the old printed Combat & Contact Sports Manual / Equipment
    # Expansion Addendum). Defaults to False: a generated session draws on
    # the FULL exercise database, personalized per-person through the live
    # engine's normal equipment/injury/level/sport-transfer logic, the same
    # way every other candidate-pool filter on this request works. Capping
    # every session to a fixed ~70-exercise manual allowlist by default was
    # actively working against the live engine - it silently threw away
    # better-fitting real candidates in favor of whatever the static manual
    # happened to print, regardless of this person's equipment, injuries,
    # or sport-transfer fit. Set True only to intentionally narrow the pool
    # to that legacy subset.
    manual_only: bool = Field(
        default=False,
        description="Restrict candidates to exercises sourced from the manual/addendum only. Defaults to False so generation uses the full personalized exercise database.",
    )

    # Which energy system Conditioning/Jump/Power exercises should be
    # prescribed for - see CONDITIONING_EMPHASES above. "Mixed" (default)
    # is fully backward compatible with every existing caller.
    conditioning_emphasis: Literal["Alactic", "Lactic", "Aerobic", "Mixed"] = "Mixed"

    # Single-session equivalent of the Program Builder's per-day "power"/
    # "hypertrophy" emphasis (see program_builder.py's DUP day cycle and
    # GOAL_PROFILES["Build Muscle"]) - lets a standalone /generate-workout
    # call ask for a power-, strength-, or hypertrophy-biased session
    # (different rep/load%/rest windows, more sets for hypertrophy, and
    # exercise ranking nudged toward whichever *safe* candidates score
    # highest on the matching athletic_qualities entry - see
    # sport_profiles.hypertrophy_quality_multiplier) without going through
    # the multi-week Program Builder. None (default) is fully backward
    # compatible - every existing caller keeps identical prescriptions and
    # ranking. This never changes which exercises are safe - the same
    # equipment/injury/strength/experience-level checks run regardless.
    #
    # "power" (explosive power) and "strength" (maximum strength) are
    # deliberately separate values, not two names for the same thing: per
    # the exercise-programming reference this engine follows, Power work
    # stays submaximal (~60-85% 1RM) and prioritizes bar speed, while
    # Strength work is the heaviest end of the board (~70-90% 1RM) with
    # reps driven all the way down to singles/doubles - conflating them
    # (as this field used to, by only offering "power" for both) meant a
    # pure max-strength goal was always getting an explosive-work
    # prescription instead of a true heavy one.
    # "strength_hypertrophy" fills the same kind of gap for the packet's own
    # "Strength + hypertrophy" row (5-8 reps, 70-82% 1RM, 3-4 sets) - a
    # window that sits between "strength" and "hypertrophy" and was
    # previously unreachable through this field (you could only land on one
    # of its two neighbors, never the row itself). See
    # program_builder._apply_prescription_bias / _GOAL_WINDOWS for the exact
    # windows each of these four values maps onto.
    training_emphasis: Optional[Literal["power", "strength", "strength_hypertrophy", "hypertrophy"]] = Field(
        default=None,
        description="Bias this session's prescription and exercise ranking toward power, strength, strength_hypertrophy (a blended strength+muscle window), or hypertrophy. Omit for the engine's default balanced prescription.",
    )

    # How many sessions/week this athlete already trains OUTSIDE this gym
    # program (sport practice, skill sessions, team conditioning, etc.).
    # A real coach doesn't size gym-session accessory/finisher volume as if
    # the gym is the athlete's only training - the rest of that athlete's
    # week already carries real muscular/systemic fatigue and movement
    # volume of its own. None/0 (the default) is fully backward compatible -
    # every existing caller keeps the exact same exercise counts. See
    # program_builder._outside_training_exercise_trim for how this trims
    # accessory/finisher slots (never the compound/secondary main lifts -
    # those stay protected regardless of outside training load) and
    # volume_engine.outside_training_volume_multiplier for the matching
    # discount applied to the weekly-set landmarks this session's volume
    # gets checked against.
    outside_training_sessions_per_week: Optional[int] = Field(
        default=None, ge=0, le=14,
        description="Sessions/week this athlete trains outside this gym program (sport practice, team conditioning, etc.) - trims gym accessory/finisher volume and the weekly-set landmarks it's checked against, without touching the main lifts.",
    )

    # --- Custom mode (mode="custom") ---
    # When mode is "custom", the engine skips its own exercise selection,
    # its own session ordering, and its manual_only/session-length/target-
    # category filtering, and instead builds the session from exactly this
    # list, in exactly this order - a single "Custom Session" phase, not the
    # usual role-based phases. Every equipment/injury/strength/level safety
    # check still runs per exercise, but in custom mode it's a warning, not
    # a wall: an unsafe pick is never dropped from the session - it comes
    # back in prescribed_workout with a `safety_warning` (reasons + a note)
    # attached instead of being moved to excluded_exercises ("custom" means
    # "you choose the exercises", and now the safety net only tells you why
    # it would have said no, it doesn't say no for you). An id that doesn't
    # exist in the database at all still lands in excluded_exercises, since
    # there's nothing to build a session entry from.
    # Ignored (behaves exactly as before) when mode is "preset" or this is empty.
    selected_exercise_ids: Optional[List[str]] = Field(
        default=None,
        description="Exercise ids to build the session from when mode='custom'. See GET /api/v1/exercises.",
    )

    # --- Program Builder support (backend/services/program_builder.py) ---
    # None/None/None (the default, and every existing single-session caller)
    # means "no session-focus filtering" - unchanged behavior for the plain
    # /api/v1/generate-workout endpoint. A program request scopes each day
    # to a slice of the database (e.g. a PPL "Push" day) by setting one or
    # both of target_categories/target_muscles; exercise_limit caps how many
    # exercises come back, sized off the requested session duration.
    target_categories: Optional[List[str]] = Field(
        default=None,
        description="Restrict to exercises whose category or movement_pattern is in this list.",
    )
    target_muscles: Optional[List[str]] = Field(
        default=None,
        description="Restrict to exercises whose primary/secondary muscles intersect this list.",
    )
    exercise_limit: Optional[int] = Field(default=None, ge=1, le=20)

    # Soft bias, not a filter or a substitution - see
    # progression_engine.template_seed_multiplier's docstring. Set by
    # program_builder.generate_program from a matched FORGE S&C Template
    # (sc_template_library.py) day's own exercise names when one exists for
    # this sport/level/days_per_week; every equipment/injury/strength/level
    # safety check above still runs exactly as before and can still exclude
    # a seeded name. This is deliberately NOT selected_exercise_ids/
    # mode="custom": a seeded name that fails a safety check is just
    # outscored by whatever the engine picks instead, never force-included
    # and never turned into a warning-only pick the way custom mode does.
    template_seed_names: Optional[List[str]] = Field(
        default=None,
        description="Exercise names (case-insensitive) to bias ranking toward, from a matched FORGE S&C Template day - a soft preference among exercises that already passed every safety check, not a filter.",
    )

    # How long this session should run. For a plain single-session request
    # (no target_categories/target_muscles - see
    # ProgressionEngine._select_compound_accessory_finisher), this just
    # decides 2 vs 3 compound lifts; accessories/finisher stay fixed at 2/1
    # so the session comes back shaped like compounds + accessories +
    # finisher instead of every exercise that merely qualified on
    # equipment/injury/strength/level. For a Program Builder day
    # (target_categories/target_muscles set) it sizes the exercise count
    # the older way (~9 min/exercise) when exercise_limit isn't set
    # explicitly.
    session_duration_minutes: int = Field(
        default=60, ge=15, le=180,
        description="How long this session should run. Sizes compound-lift count for a single session, or total exercise count for a Program Builder day, when exercise_limit isn't set explicitly.",
    )

    # --- Exercise variety / anti-repetition ---
    # Exercise ids used recently (e.g. last session, or the same day-slot in
    # a previous week of a program) - when the engine has to trim down to
    # exercise_limit, it prefers NOT to repeat these among near-tied
    # candidates for the same role, instead of always returning the single
    # highest-scoring exercise every time. Doesn't exclude them outright
    # (if nothing else qualifies, a repeat is still better than an empty
    # slot) - just deprioritizes them.
    exclude_exercise_ids: Optional[List[str]] = Field(
        default=None,
        description="Exercise ids to deprioritize (not hard-exclude) when trimming to exercise_limit, to avoid repeating recent picks.",
    )
    # Unlike exclude_exercise_ids above (soft, recency-based deprioritization),
    # this is a real hard filter - an id in this list is removed from the
    # candidate pool entirely before role/pattern selection ever runs, the
    # same way an injury-excluded exercise is removed. Used by
    # program_builder.py to enforce a real weekly cap on same-movement-family
    # repeats (e.g. stop a Judo program's Hinge slot from cycling through
    # every "High Pull" variant across a week) once soft deprioritization
    # alone isn't enough - see that module's _MAX_SAME_FAMILY_PER_WEEK.
    hard_exclude_exercise_ids: Optional[List[str]] = Field(
        default=None,
        description="Exercise ids to remove from the candidate pool entirely (unlike exclude_exercise_ids, which only deprioritizes).",
    )
    # Seeds the rotation among near-tied candidates so the same request run
    # twice with the same seed reproduces the same pick, but a different
    # seed (e.g. a different week number) can surface a different, equally
    # valid exercise instead of always the top scorer.
    variety_seed: int = Field(default=0, description="Seed controlling rotation among near-tied exercise choices.")


# ==========================================
# Multi-week program request (Program Builder)
# ==========================================

class CustomProgramDay(BaseModel):
    """One day-slot in a custom program's rotation - the Program Builder
    equivalent of WorkoutRequest's mode="custom"/selected_exercise_ids, just
    one entry per day of the split instead of one flat list. See
    ProgramRequest.custom_days below for how the rotation/labeling works."""
    label: str = Field(..., min_length=1, max_length=80, description="Display name for this day, e.g. 'Push Day A'.")
    selected_exercise_ids: List[str] = Field(
        ..., min_length=1,
        description="Exercise ids to build this day from, in order - exactly like WorkoutRequest.selected_exercise_ids. See GET /api/v1/exercises.",
    )


class ProgramRequest(BaseModel):
    mode: Literal["preset", "custom"] = Field(
        default="preset",
        description=(
            "'preset' (default): the existing split-template behavior - the engine picks every "
            "day's exercises from SPLIT_TEMPLATES categories/muscles, unchanged. "
            "'custom': the program is built from custom_days instead - the engine runs its usual "
            "per-exercise equipment/injury/strength/level safety checks (as warnings, never a "
            "silent drop - same contract as WorkoutRequest's custom mode) but does none of its own "
            "exercise selection. preferred_split/manual_only are ignored in this mode."
        ),
    )
    custom_days: Optional[List[CustomProgramDay]] = Field(
        default=None,
        description=(
            "Required (and must be non-empty) when mode='custom'. One entry per day slot in the "
            "rotation - cycled across days_per_week exactly like a preset split's own day list "
            "(e.g. 2 custom days over a 4-day week alternates Day A/Day B/Day A/Day B, matching "
            "SPLIT_TEMPLATES' own _cycle_days behavior). Ignored when mode='preset'."
        ),
    )
    # This used to be its own hardcoded Literal, a duplicate of PRIMARY_GOALS
    # above that had already drifted out of sync with it (missing "Strength
    # + Hypertrophy" when that goal was added) - GOAL_PROFILES in
    # program_builder.py falls back to "General Fitness" for anything not in
    # its own dict, but this field is the actual request-validation gate, so
    # a value present in PRIMARY_GOALS/GOAL_PROFILES could still be rejected
    # here before ever reaching that fallback. Built from PRIMARY_GOALS
    # itself instead, so the two can't diverge again.
    primary_goal: Literal[tuple(PRIMARY_GOALS)] = "General Fitness"
    sport: str = "Special Forces"
    experience_level: Literal["Beginner", "Novice", "Intermediate", "Advanced", "Elite"] = "Intermediate"

    @field_validator("primary_goal", mode="before")
    @classmethod
    def _normalize_primary_goal(cls, v):
        return _normalize_to_canonical(v, PRIMARY_GOALS)

    @field_validator("experience_level", mode="before")
    @classmethod
    def _normalize_experience_level(cls, v):
        return _normalize_to_canonical(v, EXPERIENCE_LEVELS)

    equipment_available: List[str] = Field(default_factory=lambda: ["Bodyweight"])
    readiness: int = Field(default=80, ge=1, le=100)
    readiness_inputs: Optional[ReadinessInputs] = Field(
        default=None,
        description="Optional sleep/soreness/stress/energy/motivation breakdown - see ReadinessInputs.",
    )
    injuries: List[str] = Field(default_factory=list)
    injury_stages: Optional[Dict[str, str]] = Field(
        default=None,
        description="Same {injury_name: rehab_stage} map as WorkoutRequest.injury_stages, applied to every day of the program.",
    )
    injury_sides: Optional[Dict[str, str]] = Field(
        default=None,
        description="Same {injury_name: side} map as WorkoutRequest.injury_sides, applied to every day of the program.",
    )
    biometrics: Optional[UserBiometrics] = None
    conditioning_emphasis: Literal["Alactic", "Lactic", "Aerobic", "Mixed"] = "Mixed"

    # See WorkoutRequest.manual_only - same meaning, applied to every
    # day's session for the whole generated program. Defaults to False -
    # see WorkoutRequest.manual_only's comment for why capping every session
    # to the legacy manual allowlist by default was actively hurting program
    # quality.
    manual_only: bool = Field(
        default=False,
        description="Restrict candidates to exercises sourced from the manual/addendum only. Defaults to False so generation uses the full personalized exercise database.",
    )

    # Optional competition-calendar phase (see TRAINING_PHASES above). When
    # set, overrides the days/goal/sport split heuristic with the manual's
    # Part 9.3 phase table and scales session volume accordingly (see
    # program_builder.PHASE_GUIDANCE / _apply_phase_volume_scaling). None
    # (default) = unchanged legacy behavior.
    training_phase: Optional[Literal[
        "Off-Season", "Pre-Season", "In-Season / Fight Camp", "Fight Week", "Post-Competition",
    ]] = None

    days_per_week: int = Field(default=3, ge=1, le=7)
    weeks: int = Field(default=4, ge=1, le=16, description="Mesocycle length. 3+ weeks auto-appends a deload week.")
    session_duration_minutes: int = Field(default=60, ge=15, le=180)

    # See WorkoutRequest.outside_training_sessions_per_week - same meaning,
    # applied to every day of the program. Independent of (and stacks
    # with) training_phase above: training_phase is about WHERE in the
    # competition calendar the athlete is, this is about how much real
    # sport/skill practice load they're carrying week to week regardless of
    # calendar phase (e.g. a hobbyist playing weekend league games isn't
    # "In-Season / Fight Camp" the way a fighter in camp is, but still
    # shouldn't get a gym program sized as if the gym were their only
    # training). None/0 (default) is fully backward compatible.
    outside_training_sessions_per_week: Optional[int] = Field(
        default=None, ge=0, le=14,
        description="Sessions/week this athlete trains outside this gym program (sport practice, team conditioning, etc.), applied to every day of the program - trims accessory/finisher volume and the weekly-set landmarks it's checked against, without touching the main lifts.",
    )

    # COACH-STYLE CONTINUATION (a mesocycle used to always start over at
    # week-1 baseline load, even when the person had just finished a prior
    # cycle - a real coach doesn't reset a lifter back to their very first
    # week's working weight every time a new block starts; they pick up
    # roughly where the last block left off, so week 1 of block 2 is
    # already ahead of week 1 of block 1). When the frontend passes back
    # the `next_cycle_start_week` this same endpoint returned for the PRIOR
    # program (see GenerateProgramResponse), _apply_week_progression treats
    # this program's week 1 as if it were that overall week number instead
    # of a fresh week 1 - so load_pct_1rm/reps/etc. continue climbing from
    # where the last cycle's final week left off, deload weeks included.
    # None (default, and every caller before this field existed) is a
    # complete no-op: behavior is unchanged - week 1 is baseline, exactly
    # as before.
    continue_from_week: Optional[int] = Field(
        default=None, ge=1,
        description=(
            "Overall progression week this program's week 1 should continue from - pass the "
            "`next_cycle_start_week` value the previous generate-program call returned to keep "
            "load/rep progression climbing across cycles instead of resetting to baseline each "
            "time a new mesocycle is generated. Omit (or leave null) to start a fresh baseline."
        ),
    )

    # A specific SPLIT_TEMPLATES key (see GET /api/v1/splits), or "auto" to
    # let recommend_split() pick one from days_per_week + primary_goal.
    preferred_split: str = "auto"


# Request body for POST /api/v1/sc-templates/{global_id}/build (see
# program_builder.build_template_fidelity_program) - deliberately just the
# four fields that check actually needs, not the full ProgramRequest,
# since a template already fixes sport/level/days_per_week/goal; the only
# things this endpoint needs from the caller are what could make one of
# the template's own exercise picks unsafe right now.
class SCTemplateBuildRequest(BaseModel):
    equipment_available: List[str] = Field(default_factory=lambda: ["Bodyweight"])
    injuries: List[str] = Field(default_factory=list)
    injury_stages: Optional[Dict[str, str]] = Field(
        default=None,
        description="Same {injury_name: rehab_stage} map as WorkoutRequest.injury_stages.",
    )
    injury_sides: Optional[Dict[str, str]] = Field(
        default=None,
        description="Same {injury_name: side} map as WorkoutRequest.injury_sides.",
    )
    biometrics: Optional[UserBiometrics] = Field(
        default=None,
        description=(
            "Optional - same shape as WorkoutRequest.biometrics. When supplied, every "
            "template exercise slot that carries a coach-written %1RM (e.g. '@ 70-78% e1RM') "
            "gets a recommended working_weight_kg computed off the athlete's own tested "
            "maxes, the same way a normal generated program does. Omit to see the %1RM "
            "as written with no computed weight."
        ),
    )


# ==========================================
# Custom-workout / saved-program sync (backend/services/sync_service.py)
# ==========================================
# Both follow the same upsert-on-(athlete_id, client_id) shape: `client_id`
# is the frontend-generated id it already uses locally (localStorage), so
# saving from a device that's seen this record before updates the same row
# instead of creating a duplicate - see CustomWorkoutDB/SavedProgramDB
# docstrings in backend/models/db_models.py for the full reasoning.

class CustomWorkoutCreate(BaseModel):
    client_id: str = Field(min_length=1, max_length=120)
    name: str = Field(default="Custom Workout", max_length=80)
    sport: Optional[str] = None
    experience: Optional[str] = None
    exercises: List[Any] = Field(default_factory=list)
    groups: Dict[str, Any] = Field(default_factory=dict)
    group_order: List[str] = Field(default_factory=list)
    warmup: List[Any] = Field(default_factory=list)


class CustomWorkoutOut(BaseModel):
    id: int
    client_id: str
    name: str
    sport: Optional[str] = None
    experience: Optional[str] = None
    exercises: List[Any] = Field(default_factory=list)
    groups: Dict[str, Any] = Field(default_factory=dict)
    group_order: List[str] = Field(default_factory=list)
    warmup: List[Any] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SavedProgramCreate(BaseModel):
    client_id: str = Field(min_length=1, max_length=120)
    label: str = Field(default="Saved Program", max_length=120)
    sport: Optional[str] = None
    experience_level: Optional[str] = None
    weeks: Optional[int] = None
    days_per_week: Optional[int] = None
    program: Dict[str, Any] = Field(default_factory=dict)


class SavedProgramOut(BaseModel):
    id: int
    client_id: str
    label: str
    sport: Optional[str] = None
    experience_level: Optional[str] = None
    weeks: Optional[int] = None
    days_per_week: Optional[int] = None
    program: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==========================================
# Session history / adaptive readiness (backend/services/readiness_service.py)
# ==========================================

class SessionLogCreate(BaseModel):
    """What the frontend POSTs to /api/v1/sessions once a person hits
    'Finish & Save Session'. `exercises` and `log` are passed through as-is
    (already-shaped JSON from the compiled session / the person's inline set
    logging) - the backend doesn't need to understand their internal shape,
    it just needs to store and return them, so this stays a thin pass-through
    rather than re-declaring the whole prescription schema here."""
    athlete_id: str = Field(default="default", max_length=120)
    date: Optional[datetime] = Field(
        default=None, description="When the session happened. Defaults to now (server time) if omitted."
    )
    sport: str
    program_label: Optional[str] = Field(default=None, max_length=200)
    deload_mode: bool = False
    prescribed_count: int = Field(default=0, ge=0)
    readiness_used: Optional[int] = Field(
        default=None, ge=1, le=100, description="The readiness score this session was generated with."
    )
    post_soreness: Optional[int] = Field(
        default=None, ge=1, le=5, description="How sore, after this session (or the next day): 1=none, 5=very sore."
    )
    post_fatigue: Optional[int] = Field(
        default=None, ge=1, le=5, description="Overall fatigue after this session: 1=fresh, 5=wiped out."
    )
    rpe: Optional[float] = Field(default=None, ge=1, le=10, description="Optional overall session RPE.")
    notes: Optional[str] = Field(default=None, max_length=2000)
    exercises: List[Dict[str, Any]] = Field(default_factory=list)
    log: List[Dict[str, Any]] = Field(default_factory=list)


class SessionLogOut(BaseModel):
    id: int
    athlete_id: str
    date: datetime
    sport: str
    program_label: Optional[str] = None
    deload_mode: bool
    prescribed_count: int
    readiness_used: Optional[int] = None
    post_soreness: Optional[int] = None
    post_fatigue: Optional[int] = None
    rpe: Optional[float] = None
    notes: Optional[str] = None
    exercises: List[Dict[str, Any]] = Field(default_factory=list)
    log: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SuggestedReadinessOut(BaseModel):
    """Response for GET /api/v1/readiness/suggested - a starting-point
    readiness score derived from recent logged sessions, meant to pre-fill
    (not silently override) the wizard's readiness slider. The person can
    always drag it - this is a suggestion, not a lockout."""
    suggested_readiness: int = Field(ge=1, le=100)
    basis: Literal["no_history", "history"]
    sessions_considered: int
    days_since_last_session: Optional[int] = None
    trending_worse: bool = False
    recommend_deload: bool = False
    explanation: str


# --- Auth / user profiles (Phase 6) -------------------------------------


class UserCreate(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=120)
    # Required, must be true - the registration-screen checkbox for the
    # Terms of Service / Privacy Policy / Medical Disclaimer (see
    # frontend's authFormHtml). Not a UI nicety: this is what lets
    # register_user() actually record `terms_accepted_at`, which is the
    # thing worldwide (GDPR-style) launches need on file - see UserDB's
    # docstring in db_models.py.
    accepted_terms: bool = Field(
        description="Must be true - confirms the person accepted the "
        "Terms of Service, Privacy Policy, and Medical Disclaimer before "
        "the account is created."
    )

    @field_validator("email")
    @classmethod
    def _lowercase_email(cls, v: str) -> str:
        # So "Sam@Example.com" and "sam@example.com" collide on the unique
        # index instead of silently creating two accounts.
        return v.strip().lower()

    @field_validator("accepted_terms")
    @classmethod
    def _must_accept_terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "You must accept the Terms of Service, Privacy Policy, "
                "and Medical Disclaimer to create an account."
            )
        return v


class UserLogin(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=254)
    password: str

    @field_validator("email")
    @classmethod
    def _lowercase_email(cls, v: str) -> str:
        return v.strip().lower()


class UserProfileUpdate(BaseModel):
    """All optional - PUT /api/v1/auth/me only touches fields actually sent,
    so a client can update just `display_name` without resending everything
    else (see main.py's use of `exclude_unset=True`)."""
    display_name: Optional[str] = Field(default=None, max_length=120)
    primary_sport: Optional[str] = Field(default=None, max_length=60)
    experience_level: Optional[str] = None
    equipment: Optional[List[str]] = None
    injuries: Optional[List[str]] = None
    # Only meaningful (and only required) when `injuries` is being set to a
    # non-empty list in THIS request - see auth_service.update_profile's
    # enforcement. A client can freely update display_name/equipment/etc.
    # without ever touching this field.
    health_data_consent: Optional[bool] = None

    @field_validator("experience_level")
    @classmethod
    def _valid_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in EXPERIENCE_LEVELS:
            raise ValueError(f"experience_level must be one of {EXPERIENCE_LEVELS}")
        return v


class UserOut(BaseModel):
    id: int
    email: str
    display_name: Optional[str] = None
    primary_sport: Optional[str] = None
    experience_level: Optional[str] = None
    equipment: List[str] = Field(default_factory=list)
    injuries: List[str] = Field(default_factory=list)
    created_at: datetime
    # Whether health-data consent is currently on file - lets the frontend
    # know, without a second request, whether it needs to show the consent
    # checkbox next time this person tries to save a non-empty injuries list.
    health_data_consent_given: bool = False

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=254)

    @field_validator("email")
    @classmethod
    def _lowercase_email(cls, v: str) -> str:
        return v.strip().lower()


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)

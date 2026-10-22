"""
program_builder.py — turns a goal + split + schedule into a full multi-week,
multi-day training program, by calling the existing single-session engine
once per (week, day) rather than re-implementing its safety/equipment/
injury/strength filtering.

WHY THIS EXISTS
`ProgressionEngine.generate_session` (main.py) already does the hard part of
"is this exercise safe and appropriate for this person right now" - equipment
check, injury contraindication + severity tiering, strength-requirement
gating, experience-level ceiling, sport-transfer scoring, and coach-order
sequencing. A program is not a different problem, it's the same problem
run repeatedly with two things layered on top:

  1. WHICH exercises a given day should even be considering (a "Push" day
     shouldn't be offered squats) - see `target_categories`/`target_muscles`
     on WorkoutRequest, added alongside this module.
  2. HOW the prescription should shift week to week (progressive overload)
     and day to day (a "Power" day trains differently than a "Hypertrophy"
     day even on the same split) - handled here as a post-processing pass
     over what the engine already prescribed, not a parallel prescription
     engine.

This keeps exactly one place responsible for "is this exercise allowed" and
one place responsible for "how should a program shape what's allowed" -
duplicating the ~150 lines of filtering logic into a second engine would be
the actual mistake here (two places that both decide safety, drifting apart
the first time one gets a bugfix the other doesn't).

SPLIT TEMPLATES
Each split is a named, ordered list of "day slots" - a label and either
`categories` (matched against an exercise's `category`/`movement_pattern`,
e.g. Squat/Hinge for a leg day) or `muscles` (matched against
`primary_muscles`/`secondary_muscles`, used where body-part splits don't map
cleanly onto movement categories, e.g. a bro-split "Shoulders" day). A day
may also carry `emphasis` ("power" or "hypertrophy"), which biases the
engine's own sets/reps/load prescription rather than replacing it.

The spec's full split list also names variants that aren't really different
*templates* here: "Beginner/Intermediate/Advanced" is `experience_level`,
"Home/Dumbbell Only/Minimal Equipment" is `equipment_available`, and
"Bodybuilding"/"Powerlifting"/"Hybrid" are closer to `primary_goal` (Build
Muscle / Get Strong / a blend) than to a distinct weekly structure - so
those are handled as parameters on top of the 8 structural splits below
rather than as 17 near-duplicate templates.
"""

from typing import Dict, List, Optional
import re

from backend.core.exceptions import SevereInjuryBlockedError
from backend.models.schemas import EXPERIENCE_LEVELS, ProgramRequest, WorkoutRequest
from backend.services.strength_standards import classify_strength_level, level_check
from backend.services.load_prescription import add_working_weight
from backend.services.sport_profiles import sport_conditioning_profile, top_sport_qualities
from backend.services.conditioning_protocols import conditioning_reference
from backend.services.grappling_playbook import (
    GRAPPLING_SPORTS,
    discipline_supplemental_block,
    level_loading_table,
    wave_week_pct,
    GRAPPLING_PROGRESSION_RULE,
    ARMOR_PLACEMENT_RULE,
)
from backend.services.sc_template_library import LIBRARY_SPORTS, templates_for_program, get_template, normalize_exercise_name, fuzzy_resolve_exercise_name, resolve_wizard_sport, SPECIAL_FORCES_LEVEL_ALIASES
from backend.services.conditioning_engine import resolve_conditioning_exercise
from backend.services.ai_hooks import ProgramContext, get_insight_provider
from backend.services.coach_notes import build_program_coach_notes
from backend.services.volume_engine import (
    compute_weekly_muscle_sets, evaluate_weekly_volume, outside_training_volume_multiplier,
)
from backend.services.injury_taxonomy import (
    INJURY_SIDES,
    INJURY_TAXONOMY,
    REHAB_STAGES,
    classify_injury_risk,
    find_alternatives,
    laterality_applicable,
    resolve_severe_injuries,
    resolve_systemic_injury,
)

_LEVEL_RANK: Dict[str, int] = {lvl: i for i, lvl in enumerate(EXPERIENCE_LEVELS)}

SPLIT_TEMPLATES: Dict[str, Dict] = {
    "full_body": {
        "name": "Full Body",
        "description": "Every major movement pattern trained each session - squat, hinge, push, pull, and a power/conditioning element all in one sitting. Best when you're only lifting 1-4x/week, since each session has to stand on its own rather than being one slice of a weekly split.",
        "supported_days_per_week": [1, 2, 3, 4],
        # Both A and B carry the FULL pattern set (all six loaded-strength
        # categories, not a push/pull half-split) plus Power/Jump/
        # Conditioning/Sport Specific - this is the template every
        # combat-sport/grappling/climbing/HYROX profile in
        # SPORT_SPLIT_GUIDANCE below is routed to, and those athletes only
        # lift 2-4x/week total, so every single session needs to look like a
        # complete strength-and-conditioning session on its own (squat AND
        # hinge, push AND pull in both planes, an explosive/ballistic
        # movement, core, a conditioning finisher, and sport-specific skill
        # transfer work) rather than one half of a bodybuilding-style
        # rotation. ProgressionEngine's role- and pattern-coverage selection
        # (main.py _select_role_balanced / _COVERAGE_PATTERNS) does the
        # actual per-session balancing within this pool, and variety_seed/
        # exclude_exercise_ids keep A and B (and week-to-week repeats)
        # from converging on the exact same picks.
        "days": [
            {"label": "Full Body A", "categories": [
                "Full Body", "Squat", "Hinge", "Horizontal Push", "Vertical Push",
                "Horizontal Pull", "Vertical Pull", "Power", "Jump",
                "Core", "Carry", "Conditioning", "Sport Specific",
            ]},
            {"label": "Full Body B", "categories": [
                "Full Body", "Squat", "Hinge", "Horizontal Push", "Vertical Push",
                "Horizontal Pull", "Vertical Pull", "Power", "Jump",
                "Core", "Carry", "Conditioning", "Sport Specific",
            ]},
        ],
    },
    "upper_lower": {
        "name": "Upper / Lower",
        "description": "Alternates upper-body and lower-body sessions, so each region gets a full session's worth of dedicated volume roughly twice a week. A middle ground between full-body frequency and single-region isolation.",
        "supported_days_per_week": [2, 4, 6],
        # Squat/Hinge stay Lower-only and Push/Pull stay Upper-only (that
        # split is the point of this template), but Power/Jump/Conditioning/
        # Sport Specific are added to BOTH days - this template is what
        # every striking/field/tactical sport in SPORT_SPLIT_GUIDANCE below
        # uses, and an athlete training for Boxing, Rugby, MMA, etc. needs
        # explosive output, a conditioning piece, and sport-skill transfer
        # work available on every session, not confined to whichever day
        # happens to also be leg day.
        "days": [
            {"label": "Upper Body", "categories": [
                "Horizontal Push", "Vertical Push", "Horizontal Pull", "Vertical Pull",
                "Power", "Jump", "Core", "Conditioning", "Sport Specific",
            ]},
            {"label": "Lower Body", "categories": [
                "Squat", "Hinge", "Carry", "Full Body",
                "Power", "Jump", "Core", "Conditioning", "Sport Specific",
            ]},
        ],
    },
    "push_pull_legs": {
        "name": "Push / Pull / Legs",
        "description": "Groups sessions by movement direction - all pushing muscles together, all pulling muscles together, legs on their own day. Lets you push each muscle group harder per session since nothing else on that day is competing with it for recovery.",
        "supported_days_per_week": [3],
        "days": [
            {"label": "Push", "categories": ["Horizontal Push", "Vertical Push"]},
            {"label": "Pull", "categories": ["Horizontal Pull", "Vertical Pull", "Grip"]},
            {"label": "Legs", "categories": ["Squat", "Hinge", "Carry", "Full Body"]},
        ],
    },
}
# These three structural templates (Full Body / Upper-Lower / Push-Pull-Legs)
# cover every day-count from 1-6x/week between them. The per-sport 1/2/3/4-day
# splits (Judo, Wrestling, BJJ, ...) layer on top via `sport` +
# `days_per_week` on ProgramRequest - see SPORT_SPLIT_GUIDANCE below for the
# per-sport day-count guidance and sport_profiles.py for what each sport's
# split actually prioritizes.

GOAL_PROFILES: Dict[str, Dict] = {
    # BUGFIX: this used to be bias="power", identical to "Power /
    # Explosiveness" below - meaning a pure max-strength goal never
    # actually got a true heavy/low-rep/long-rest prescription, it got the
    # *explosive* one instead (lower relative load, shorter rest than a
    # real strength day calls for). "Get Strong" == the reference guide's
    # "Maximum strength" quality (reps 1-6, ~70-90% 1RM, 2-5 min rest) and
    # is now its own bias, distinct from "Power" (reps 1-5, ~60-85% 1RM,
    # speed-focused). See _apply_prescription_bias for the exact windows.
    "Get Strong": {"category_boost": ["Full Body"], "bias": "strength"},
    # The packet's own "Strength + hypertrophy" row (5-8 reps, 3-4 sets,
    # 70-82% 1RM) sits strictly between "Get Strong" (2-6 reps, 75-90%) and
    # "Build Muscle" (6-12 reps, 60-80%) below - close enough to both that
    # picking either as a stand-in used to land outside this row's own
    # window on every rep/load/rest field. "Full Body" is boosted the same
    # way "Get Strong" boosts it (this is still a loaded-strength-leaning
    # goal, just at a lighter relative intensity with more accessory
    # volume), not "Core" - that boost belongs to the pure-hypertrophy goal
    # below where visible midsection work is the explicit ask.
    "Strength + Hypertrophy": {"category_boost": ["Full Body"], "bias": "strength_hypertrophy"},
    # Hypertrophy goal: reuses the exact bias="hypertrophy" mechanism the DUP
    # day cycle already applies to any split's "Hypertrophy" day
    # (_apply_prescription_bias below - higher reps, lower load%, sets from
    # the packet's own 3-4 hypertrophy window),
    # just as this goal's flat, every-day bias instead of one day in three.
    # "Core" is boosted on top of the split's own day categories (additive,
    # see the category_boost merge below - this never narrows what a day
    # trains) since visible midsection work is part of what people asking
    # for this goal actually want and every split template already includes
    # it on at least one day but not necessarily every day. No new split
    # template and no changes to the safety/equipment/injury/strength
    # filtering every other goal already shares - generate_session decides
    # what's safe exactly as before, this only shapes sets/reps/load and
    # (via sport_profiles.hypertrophy_quality_multiplier) which of the safe
    # candidates rank highest.
    "Build Muscle": {"category_boost": ["Core"], "bias": "hypertrophy"},
    "Power / Explosiveness": {"category_boost": ["Power", "Jump", "Full Body"], "bias": "power"},
    "Athletic Performance": {"category_boost": ["Power", "Jump", "Sport Specific", "Full Body"], "bias": "power"},
    "Conditioning": {"category_boost": ["Conditioning", "Jump", "Power", "Carry"], "bias": None, "override_categories": True},
    "Skill Development": {"category_boost": ["Sport Specific"], "bias": None},
    "General Fitness": {"category_boost": [], "bias": None},
}

# Which structural split (from SPLIT_TEMPLATES) a strength coach would actually
# reach for given each sport's own demands - grounded in how S&C programs for
# each sport family are commonly built, not just the generic days/goal
# heuristic below (which has no idea a person is training for Judo vs.
# bodybuilding). Two sport families show up here:
#   - Grappling combat sports (Wrestling, Judo, Sambo, BJJ) and Rock Climbing:
#     S&C guidance for these consistently caps lifting at 2-4 sessions/week,
#     full-body each time, so it never competes with mat/wall time or
#     compounds fatigue on top of skill training - see e.g. BJJ/grappling S&C
#     writeups (youjiujitsu.com, strongfirst.com, crazy88mma.com), which
#     converge on a 3x/week full-body template as the default.
#   - Striking combat sports (Boxing, Muay Thai, Kickboxing, Sanda), Rugby,
#     Special Forces prep, and MMA: these need more total strength volume
#     (explosive power, contact tolerance, load carriage) and commonly run a
#     4-day Upper/Lower split - the standard step up from full-body once
#     4 dedicated sessions/week are available.
#   - HYROX: hybrid running + functional-station racing; programs for it are
#     built as full-body strength-conditioning hybrids rather than a
#     body-part split, run 4x/week.
# `days_per_week` is what's suggested when the split is chosen for this sport
# specifically (not a hard requirement) - recommend_split still falls back to
# the generic heuristic if the caller's own days_per_week doesn't fit this
# split's supported_days_per_week.
SPORT_SPLIT_GUIDANCE: Dict[str, Dict] = {
    "Wrestling": {"split": "full_body", "days_per_week": 3, "rationale": "Combat Sports & Rugby S&C Manual, Part 5: in-season, run 3-Day Full Body; step up to 4-Day Upper/Lower off-season for more total strength volume. Lactic-dominant conditioning (35% aerobic / 65% lactic)."},
    "Judo": {"split": "full_body", "days_per_week": 3, "rationale": "Manual guidance: 3-Day Full Body, prioritizing pulling power for grip-and-throw exchanges. Lactic-dominant conditioning (30% aerobic / 70% lactic)."},
    "Sambo": {"split": "full_body", "days_per_week": 3, "rationale": "Manual guidance: in-season 3-Day Full Body; 4-Day Upper/Lower off-season for more total strength volume, same pattern as Wrestling. Lactic-dominant conditioning (35% aerobic / 65% lactic)."},
    "BJJ": {"split": "full_body", "days_per_week": 3, "rationale": "Manual guidance: 3-Day Full Body or 3-Day Push/Pull/Legs (extra pulling volume suits grapplers). Aerobic-leaning conditioning (55% aerobic / 45% lactic) - matches/rolls run long."},
    "Boxing": {"split": "upper_lower", "days_per_week": 2, "rationale": "Manual guidance: 2-Day Upper/Lower protects recovery for pad work/sparring; step up to 3-Day Full Body off-season. Conditioning skews lactic (40% aerobic / 60% lactic) with classic round-based intervals."},
    "Muay Thai": {"split": "full_body", "days_per_week": 3, "rationale": "Manual guidance: 3-Day Full Body or 2-Day Upper/Lower. Conditioning: 45% aerobic / 55% lactic, plus clinch strength and shin/leg durability work."},
    "Kickboxing": {"split": "full_body", "days_per_week": 3, "rationale": "Manual guidance: 3-Day Full Body or 2-Day Upper/Lower. Conditioning: 45% aerobic / 55% lactic, round-based intervals matching competition round length."},
    "Sanda": {"split": "full_body", "days_per_week": 3, "rationale": "Manual guidance: 3-Day Full Body for balanced striking-and-throwing carryover. Conditioning: 40% aerobic / 60% lactic."},
    "Rugby": {"split": "upper_lower", "days_per_week": 4, "rationale": "Manual guidance: 4-Day Upper/Lower in-season (strength maintenance) or 3-Day Push/Pull/Legs off-season (strength-building block). Conditioning: 45% aerobic / 55% lactic, repeated-sprint focus."},
    "Rock Climbing": {"split": "full_body", "days_per_week": 3, "rationale": "Climbing-specific strength guidance keeps lifting to 2-3x/week full-body, since grip/pulling volume is already high from wall time."},
    "HYROX": {"split": "full_body", "days_per_week": 4, "rationale": "HYROX programs are built as full-body strength-conditioning hybrids rather than a body-part split - matches the race's mixed running/functional-station format."},
    "Special Forces": {"split": "upper_lower", "days_per_week": 4, "rationale": "Manual guidance: 4-Day Upper/Lower, built to support heavy weekly aerobic/ruck volume without excess soreness. Aerobic-dominant conditioning (70% aerobic / 30% lactic)."},
    "MMA": {"split": "full_body", "days_per_week": 3, "rationale": "Manual guidance: 3-Day Full Body in-season (step up to 4-Day Upper/Lower off-season for more strength volume). MMA needs the broadest conditioning base of any combat sport here - 50% aerobic / 50% lactic."},
    # Not manual-sourced (see SPORT_QUALITY_PROFILES note above) - these two
    # route to the closest of the six manual splits by structure rather than
    # carrying a manual-page rationale: Powerlifting wants the squat/bench/
    # deadlift pattern spread across dedicated heavy days, which is exactly
    # what 4-Day Upper/Lower gives; "Look Jacked" wants every pattern trained
    # with real volume and no session skipped, which is what Push/Pull/Legs
    # is built for.
    "Powerlifting": {"split": "upper_lower", "days_per_week": 4, "rationale": "4-Day Upper/Lower spreads squat/bench/deadlift-pattern work across dedicated heavy sessions with enough recovery between repeats of the same lift."},
    "Look Jacked": {"split": "push_pull_legs", "days_per_week": 3, "rationale": "3-Day Push/Pull/Legs gives every pattern its own dedicated session, so nothing gets short volume the way it can on a full-body day."},
    # "Strength + Hypertrophy" sits between the two above (5-8 reps, 70-82%
    # 1RM) - routed to 4-Day Upper/Lower for the same reason as Powerlifting
    # (dedicated heavy days for the main lifts), but the second Upper/Lower
    # pass each week is built almost entirely from 8-12 rep accessories, so
    # the split still banks real hypertrophy volume Powerlifting's version doesn't.
    "Strength + Hypertrophy": {"split": "upper_lower", "days_per_week": 4, "rationale": "4-Day Upper/Lower runs the 5-8 rep / 70-82% main lifts on dedicated heavy days, then a second Upper/Lower pass built from 8-12 rep accessories banks real hypertrophy volume without disrupting the main-lift recovery."},
}


# Combat Sports & Rugby S&C Manual, Part 9.3 ("Periodization: Fitting S&C
# Into a Training Year") - which split to run and how hard to push it
# should shift with the competition calendar, not stay identical
# year-round. Purely additive: only consulted when a caller sets
# `ProgramRequest.training_phase` (see schemas.TRAINING_PHASES); every
# existing caller that leaves it unset keeps the exact days/goal/sport
# heuristic behavior from `_recommend_split_raw` above. `split_candidates`
# is tried in order against the caller's own `days_per_week` (first one
# whose `supported_days_per_week` matches wins, same "don't override what
# the person actually asked for" principle as `_recommend_split_raw`);
# `volume_multiplier` scales exercise count and set count for the phase
# (see `_apply_phase_volume_scaling`).
PHASE_GUIDANCE: Dict[str, Dict] = {
    "Off-Season": {
        "duration": "6-10 weeks",
        "split_candidates": ["upper_lower", "push_pull_legs"],
        "volume_multiplier": 1.0,
        "lifting_focus": "4-Day Upper/Lower or 3-Day Push/Pull/Legs - higher volume, build max strength and muscle.",
        "conditioning_focus": "Aerobic base building, 2-3x/week.",
    },
    "Pre-Season": {
        "duration": "4-6 weeks",
        "split_candidates": ["full_body"],
        "volume_multiplier": 0.9,
        "lifting_focus": "3-Day Full Body - moderate volume; add Olympic-lift/jump power work.",
        "conditioning_focus": "Shift toward lactic, sport-specific round work.",
    },
    "In-Season / Fight Camp": {
        "duration": "Ongoing",
        "split_candidates": ["upper_lower", "full_body"],
        "volume_multiplier": 0.5,
        "lifting_focus": "2-Day Upper/Lower or 1-Day Full Body - volume cut roughly in half; keep some intensity, protect recovery for skill work.",
        "conditioning_focus": "Lactic work matched to round length; taper hard in the final 7-10 days.",
    },
    "Fight Week": {
        "duration": "Final week",
        "split_candidates": ["full_body"],
        "volume_multiplier": 0.25,
        "lifting_focus": "Very light or off, 3-4 days out - minimal, technique and neural activation only.",
        "conditioning_focus": "Skill/tactical focus only; prioritize full recovery.",
    },
    "Post-Competition": {
        "duration": "1-2 weeks",
        "split_candidates": ["full_body"],
        "volume_multiplier": 0.6,
        "lifting_focus": "Optional light full body - low volume, easy movement.",
        "conditioning_focus": "Easy aerobic only; let bumps and bruises heal.",
    },
}


def _split_for_phase(training_phase: Optional[str], days_per_week: int) -> Optional[str]:
    """First split from the phase's candidate list that actually supports
    the caller's requested days_per_week - None if no phase is set (falls
    through to the ordinary heuristic) or if none of the phase's candidates
    fit that day count (falls through the same way, rather than silently
    changing days_per_week out from under the caller)."""
    phase = PHASE_GUIDANCE.get(training_phase) if training_phase else None
    if not phase:
        return None
    for candidate in phase["split_candidates"]:
        if days_per_week in SPLIT_TEMPLATES[candidate]["supported_days_per_week"]:
            return candidate
    return None


_ACCESSORY_TRIM_ROLES = {"Accessory / Hypertrophy", "Conditioning / Finisher"}


def _apply_outside_training_set_scaling(prescription: Dict, role: str, multiplier: float) -> Dict:
    """Companion to _apply_phase_volume_scaling, same mechanics, but only
    ever touches Accessory/Hypertrophy and Conditioning/Finisher sets -
    never Primary/Secondary Strength or the sport-identity Skill/Power
    slots. Matches _outside_training_exercise_trim's own "cut the extra
    work, protect the main lifts" rule: those are the sets a coach adds on
    TOP of the main lifts, and they're what should shrink as an athlete's
    outside sport-practice load stacks up - the main lifts stay dosed
    exactly as the goal/experience level calls for regardless."""
    if multiplier >= 0.999 or role not in _ACCESSORY_TRIM_ROLES:
        return prescription
    result = dict(prescription)
    if "sets" in result:
        result["sets"] = max(1, round(result["sets"] * multiplier))
    return result


def _apply_phase_volume_scaling(prescription: Dict, multiplier: float) -> Dict:
    """Scales set count (and conditioning work volume) by the phase's
    volume_multiplier - the mechanism behind Part 9.3's 'volume cut roughly
    in half' (In-Season/Fight Camp) and 'minimal' (Fight Week) guidance.
    A multiplier of 1.0 (Off-Season) is a no-op. Never drops a lift below 1
    set or a conditioning interval below 1 round - a scaled-down session is
    still a real session, not zero exercise."""
    if multiplier >= 0.999:
        return prescription
    result = dict(prescription)
    if "sets" in result:
        result["sets"] = max(1, round(result["sets"] * multiplier))
    return result


def recommend_split(
    days_per_week: int, goal: str, sport: Optional[str] = None,
    experience_level: Optional[str] = None,
) -> str:
    """Heuristic used when preferred_split == "auto". Not the only reasonable
    choice for any given (days, goal) pair - just a sensible default a person
    can override via GET /api/v1/splits.

    Sport-specific guidance (SPORT_SPLIT_GUIDANCE) takes priority over the
    generic days/goal heuristic below whenever it applies - but only when
    the goal isn't already a strong, explicit signal of its own (a pure
    "Get Strong" max-strength ask still wins even for a combat-sport
    athlete, since that's what they're literally asking for) and only when
    the caller's requested
    days_per_week actually fits that sport's recommended split - otherwise
    this falls through to the generic heuristic exactly as before.

    `experience_level` is applied last, as a ceiling, not an input to the
    heuristic itself - see `_apply_experience_ceiling` for why. Thin
    wrapper around `_recommend_split_raw` + `_apply_experience_ceiling` so
    callers that need to know *whether* the ceiling actually changed
    anything (generate_program's `experience_capped` response field) can
    call those two pieces separately instead of guessing from the output."""
    raw = _recommend_split_raw(days_per_week, goal, sport)
    return _apply_experience_ceiling(raw, days_per_week, experience_level)


def _sport_preferred_split(days_per_week: int, sport: str) -> Optional[str]:
    """The structural split the sport's own guidance would pick for this
    exact days_per_week, including the simplest-first fallback when the
    sport's default structural split doesn't cover this day count. Returns
    None only when the sport has no guidance row at all - callers use that
    to fall through to the generic days/goal heuristic, not to silently
    drop the sport once a fallback has already been chosen. Split out of
    `_recommend_split_raw` so `generate_program` can ask "did the sport
    actually decide this?" using the exact same logic instead of a looser
    equality check against the raw guidance dict."""
    sport_guidance = SPORT_SPLIT_GUIDANCE.get(sport)
    if not sport_guidance:
        return None
    candidate = sport_guidance["split"]
    if days_per_week in SPLIT_TEMPLATES[candidate]["supported_days_per_week"]:
        return candidate
    # The sport's preferred structural split (e.g. Boxing -> Upper/Lower)
    # doesn't cover this exact days_per_week - don't drop the sport's
    # identity just because the day count is off the manual's default; step
    # to the next structural split that does cover it, in the same
    # simplest-first order used by _apply_experience_ceiling. A 3-day/wk
    # Boxer still gets a real, sport-aware recommendation this way instead
    # of silently falling through to the generic heuristic (which has no
    # idea Boxing was ever in the picture).
    for fallback in ("full_body", "upper_lower", "push_pull_legs"):
        if days_per_week in SPLIT_TEMPLATES[fallback]["supported_days_per_week"]:
            return fallback
    return None


def _recommend_split_raw(days_per_week: int, goal: str, sport: Optional[str] = None) -> str:
    """The days/goal/sport heuristic alone, with no experience-level ceiling
    applied yet - see `recommend_split` for the full picture."""
    if sport and goal != "Get Strong":
        candidate = _sport_preferred_split(days_per_week, sport)
        if candidate:
            return candidate

    if days_per_week <= 3:
        return "full_body" if goal == "Conditioning" or days_per_week <= 2 else "push_pull_legs"
    # 4+ days/week: the manual's largest named split is the 4-Day Upper/Lower
    # (Part 4.5) - used as-is at 4 days, and cycled for anything higher, since
    # the manual doesn't define a 5- or 6-day template of its own.
    return "upper_lower"


def sport_split_rationale(sport: Optional[str], days_per_week: int, split_id: str) -> Optional[str]:
    """Why this split for this sport at this exact days_per_week - computed
    from the sport's own data (SPORT_QUALITY_PROFILES + conditioning ratio)
    rather than one fixed sentence per sport. When days_per_week matches
    SPORT_SPLIT_GUIDANCE's own recommended count, that entry's manual-sourced
    rationale is more specific and is used as-is; for any other day count
    (which the old fixed text never covered - see _recommend_split_raw above)
    this builds an equivalent sentence live, so every day count a sport can
    land on has real, sport-specific reasoning instead of silence."""
    guidance = SPORT_SPLIT_GUIDANCE.get(sport) if sport else None
    if not guidance or _sport_preferred_split(days_per_week, sport) != split_id:
        return None
    if days_per_week == guidance.get("days_per_week"):
        return guidance["rationale"]

    template_name = SPLIT_TEMPLATES[split_id]["name"]
    qualities = top_sport_qualities(sport, limit=3)
    quality_note = f" prioritizing {', '.join(qualities)}" if qualities else ""
    conditioning = sport_conditioning_profile(sport)
    conditioning_note = (
        f" Conditioning stays {conditioning['aerobic_pct']}% aerobic / "
        f"{conditioning['lactic_pct']}% lactic regardless of gym frequency."
        if conditioning else ""
    )
    return (
        f"{days_per_week}-Day {template_name} for {sport}{quality_note} - "
        f"the manual's own default for {sport} is {guidance['days_per_week']} "
        f"days/week, but the same structural split scales to {days_per_week} "
        f"without losing what actually matters for the sport.{conditioning_note}"
    )


# What a beginner/novice is actually limited by isn't per-muscle training
# volume, it's neural adaptation and bar-path technique on a handful of
# compound lifts - the entire premise behind every classic novice linear
# progression (Starting Strength, StrongLifts 5x5, GreySkull LP - see
# full_body's own `reference` above) is full-body work at high per-lift
# frequency, not specialization. Body-part/specialization templates (Bro
# Split, Arnold Split, PHAT, PHUL, Powerbuilding) assume a work-capacity and
# technical base a true beginner hasn't built yet: splitting a beginner's
# already-modest weekly volume across 5-6 narrow sessions spreads it too
# thin to drive the adaptation that actually matters at this stage, and
# adds session-to-session variability before the basics are grooved in.
# Manual-only mode only has three templates left (full_body, upper_lower,
# push_pull_legs) - this ceiling still keeps a true beginner off the
# 3-Day Push/Pull/Legs split until Novice, same logic as before.
EXPERIENCE_SPLIT_ALLOWLIST: Dict[str, set] = {
    "Beginner": {"full_body", "upper_lower"},
    "Novice": {"full_body", "upper_lower", "push_pull_legs"},
    # Intermediate and above: no ceiling.
}


def _apply_experience_ceiling(
    split_id: str, days_per_week: int, experience_level: Optional[str],
) -> str:
    """If the split the heuristic/sport-guidance landed on is above what's
    appropriate for this person's stated experience level, step back down
    to the highest-frequency template that's still on the allowlist and
    actually supports the requested days/week - preferring the simplest
    structure (full-body) first, same order a coach would fall back
    through."""
    allowlist = EXPERIENCE_SPLIT_ALLOWLIST.get(experience_level or "")
    if not allowlist or split_id in allowlist:
        return split_id
    for candidate in ("full_body", "upper_lower", "push_pull_legs"):
        if candidate in allowlist and days_per_week in SPLIT_TEMPLATES[candidate]["supported_days_per_week"]:
            return candidate
    # Nothing on the allowlist officially "supports" this exact day count
    # (e.g. a Beginner asking for 5 days/week, and full_body/upper_lower
    # only advertise 2/3/4/6) - fall back to full_body regardless.
    # _cycle_days() will still repeat it sensibly, and running full-body an
    # "unsupported" number of times is a far smaller mismatch for a
    # beginner than jumping to a body-part specialization split.
    return "full_body"




def _outside_training_exercise_trim(outside_training_sessions_per_week: Optional[int]) -> int:
    """How many exercise slots a coach trims off a session when this
    athlete already carries real training load outside this gym program
    (sport practice, team conditioning, etc.) - independent of
    _estimate_exercise_count/_session_composition's own duration-based
    sizing, which only reasons about how long THIS session runs. 1 slot
    per 2 outside sessions/week, capped at 3 so a heavy in-season sport
    schedule thins the session (accessory/finisher first - see both call
    sites below) rather than hollowing it out entirely; the main
    compound/secondary lifts are never touched by this trim - they're what
    actually keeps this athlete strong for their sport, and a coach
    protects those first, cutting the "extra" volume on top instead.
    0 (no-op) when outside_training_sessions_per_week is None/0 - every
    existing caller that doesn't pass this keeps identical counts."""
    if not outside_training_sessions_per_week:
        return 0
    return min(3, outside_training_sessions_per_week // 2)


def _estimate_exercise_count(
    session_duration_minutes: int,
    outside_training_sessions_per_week: Optional[int] = None,
) -> int:
    """~9 minutes per exercise (working sets + rest + transitions), clamped
    to a sane range so a 15-minute request doesn't come back with 1 exercise
    and a 5-hour request doesn't come back with 40. Upper bound raised to 16
    (was 10) so a genuinely long Program Builder day (90/120/150 min) still
    gets more exercises than a 75-minute one instead of being capped at the
    same ceiling - see _SESSION_COMPOSITION_TABLE below for the equivalent
    ladder on the plain-single-session path. `outside_training_sessions_per_week`
    (default None, backward compatible) trims further via
    _outside_training_exercise_trim above, floored at the same 4-exercise
    minimum every duration already respects."""
    base = max(4, min(16, round(session_duration_minutes / 9)))
    return max(4, base - _outside_training_exercise_trim(outside_training_sessions_per_week))


# Duration -> exercise-composition ladder for a plain single session (the
# "compound + accessory + finisher" shape - see
# _select_compound_accessory_finisher). Each tuple is
# (compound, skill, power, secondary, accessory, finisher) exercise counts,
# in the order a coach would decide what to cut first as time shrinks and
# what to add first as time grows:
#   - Below 45 min: no room for sport-identity Power work or a second big
#     lift - just the primary compounds, one skill drill, and a single
#     accessory to leave time for warm-up/cool-down.
#   - 45-59 min: the "full" identity slate turns on (skill + power +
#     secondary compound), same as before.
#   - 60-74 min: a third primary compound fits.
#   - 75-89 min: a second Secondary Strength slot fits (a genuine "second
#     big lift" tier, not just more accessories).
#   - 90+ min: composition is already coach-complete (3 compounds, both
#     identity slots, 2 secondary lifts) - so *this* is where the
#     90/120/150 buckets differ from 75: more Accessory/Hypertrophy volume
#     (and, at 150, a second Conditioning/Finisher), which is exactly what
#     a lifter with genuinely more time asks their coach to add - more
#     total work, not a different shape of session.
_SESSION_COMPOSITION_TABLE = [
    # (min_minutes, compound, skill, power, secondary, accessory, finisher)
    (0, 2, 1, 0, 0, 1, 0),
    (30, 2, 1, 0, 0, 1, 0),
    (45, 2, 1, 1, 1, 2, 1),
    (60, 3, 1, 1, 1, 2, 1),
    (75, 3, 1, 1, 2, 2, 1),
    (90, 3, 1, 1, 2, 3, 1),
    (120, 3, 1, 1, 2, 4, 1),
    (150, 3, 1, 1, 2, 5, 2),
]


def _session_composition(
    session_duration_minutes: int,
    outside_training_sessions_per_week: Optional[int] = None,
) -> Dict[str, int]:
    """Looks up the row in _SESSION_COMPOSITION_TABLE for the largest
    threshold <= session_duration_minutes (so e.g. 50 min lands on the 45
    row, 100 min lands on the 90 row - any value between two named buckets
    just inherits the lower one, same "round down to the last coached
    tier" logic as before, just table-driven instead of nested if/elif).

    `outside_training_sessions_per_week` (default None, backward
    compatible) applies _outside_training_exercise_trim on top of the
    duration-based row - accessory slots first, then finisher, exactly the
    "cut the extra work, protect the main lifts" order a coach would use
    (compound/skill/power/secondary counts are never reduced by this)."""
    row = _SESSION_COMPOSITION_TABLE[0]
    for candidate in _SESSION_COMPOSITION_TABLE:
        if session_duration_minutes >= candidate[0]:
            row = candidate
        else:
            break
    _, compound, skill, power, secondary, accessory, finisher = row

    trim = _outside_training_exercise_trim(outside_training_sessions_per_week)
    accessory_trim = min(accessory, trim)
    accessory -= accessory_trim
    trim -= accessory_trim
    finisher = max(0, finisher - trim)

    return {
        "compound_count": compound,
        "skill_count": skill,
        "power_count": power,
        "secondary_count": secondary,
        "accessory_count": accessory,
        "finisher_count": finisher,
    }


def _day_target_categories(day_slot: Dict, goal_profile: Dict, sport: str) -> List[str]:
    """The exact target_categories a day's WorkoutRequest gets - factored
    out of the day-build loop so the FORGE S&C Template seed alignment
    below (which needs to know each day's focus BEFORE the loop runs, to
    pick which seed day fits which split day) uses the identical rule
    rather than a second, driftable copy of it."""
    if goal_profile.get("override_categories"):
        return list(goal_profile["category_boost"])
    base_categories = day_slot.get("categories") or []
    if sport in _MANUAL_NO_INLINE_CONDITIONING_SPORTS:
        base_categories = [c for c in base_categories if c != "Conditioning"]
    return list(dict.fromkeys(base_categories + goal_profile.get("category_boost", [])))


def _seed_days_by_label(
    engine, day_slots: List[Dict], seed_days: Optional[List[Dict]], goal_profile: Dict, sport: str,
) -> Dict[str, List[str]]:
    """Which FORGE S&C Template day (by exercise names) fits each split day
    best, keyed by day_label - resolved ONCE per program, not per week
    (day_slots and seed_days are both fixed for the whole program, so this
    would recompute an identical answer every week).

    A seed template's own day structure (e.g. "squat/hinge emphasis day"
    vs "press/pull emphasis day") doesn't line up positionally with a
    split's day structure (e.g. Push/Pull/Legs) - cycling them by index
    would hand a Push day a squat-heavy seed list that can't match anything
    in a Push day's own category filter, silently making the seed a no-op
    most of the time. Instead, each seed day's exercises are resolved back
    to the exercise database (via normalize_exercise_name - same matcher
    template_seed_multiplier uses) to read their own category/movement_
    pattern/muscles, and each split day is paired with whichever seed day's
    resolved categories/muscles overlap its own target_categories/
    target_muscles the most. A seed day can be reused for more than one
    split day if it's genuinely the best fit for both (e.g. two squat-
    biased days in a 4-day split); ties break toward the earliest seed day
    for determinism. Falls back to None-per-label (no seed) for any split
    day where nothing overlaps at all, rather than forcing a bad pairing.
    """
    if not seed_days:
        return {}

    name_to_data: Dict[str, Dict] = {}
    for ex in engine.exercises_by_id.values():
        name_to_data.setdefault(normalize_exercise_name(ex.get("name", "")), ex)

    seed_day_signatures = []
    for seed_day in seed_days:
        names = [e.get("name") for e in seed_day.get("exercises", []) if e.get("name")]
        cats: set = set()
        muscles: set = set()
        for name in names:
            resolved = name_to_data.get(normalize_exercise_name(name))
            if not resolved:
                continue
            cats.update(x for x in (resolved.get("category"), resolved.get("movement_pattern")) if x)
            muscles.update(resolved.get("primary_muscles", []))
            muscles.update(resolved.get("secondary_muscles", []))
        seed_day_signatures.append({"names": names, "categories": cats, "muscles": muscles})

    result: Dict[str, List[str]] = {}
    for day_slot in day_slots:
        label = day_slot["label"]
        if label in result:
            continue
        target_categories = set(_day_target_categories(day_slot, goal_profile, sport))
        target_muscles = set(day_slot.get("muscles") or [])
        best_score = -1
        best_names = None
        for sig in seed_day_signatures:
            score = len(sig["categories"] & target_categories) + len(sig["muscles"] & target_muscles)
            if score > best_score:
                best_score = score
                best_names = sig["names"]
        result[label] = best_names if best_score > 0 else None
    return result


def _cycle_days(days: List[Dict], days_per_week: int) -> List[Dict]:
    """Repeats a template's day list to fill the requested days_per_week
    (e.g. a 3-day PPL template run as 6 days/week). Repeated passes get a
    "(2)" etc. suffix on the label so the program output stays readable."""
    if days_per_week <= len(days):
        return days[:days_per_week]
    result = []
    for i in range(days_per_week):
        template_day = days[i % len(days)]
        pass_number = i // len(days) + 1
        day = dict(template_day)
        if pass_number > 1:
            day["label"] = f"{template_day['label']} ({pass_number})"
        result.append(day)
    return result


# PERIODIZATION MODEL
# Which model actually applies depends on training age, not just personal
# preference - this isn't a style toggle, it's grounded in what the
# periodization literature consistently finds:
#   - Novice lifters (Beginner/Novice here) respond best to plain LINEAR
#     progression - the same lift trained the same way, load nudged up
#     each week. Layering daily/weekly undulation on top of a novice's
#     program adds complexity without benefit; the classic novice linear
#     progressions this app already models the full_body split on
#     (StrongLifts, GreySkull, Starting Strength - see full_body's own
#     `reference` above) are linear precisely because a beginner's neural
#     adaptations are still fast enough that "just add weight" keeps
#     working for months.
#   - Intermediate+ lifters plateau on pure linear progression - the same
#     stimulus every session stops producing a novel-enough signal to keep
#     adapting. Daily Undulating Periodization (DUP) - varying the
#     load/rep target session to session instead of only trending it
#     upward week to week - is the standard response, and has direct
#     empirical support: Rhea et al. (2002, Med Sci Sports Exerc) had
#     trained lifters rotate heavy/moderate/light-style rep targets
#     within the same week and found significantly larger strength gains
#     than an equal-volume linear group; a 2017 systematic review/
#     meta-analysis (Grgic et al., covering the broader LP-vs-UP
#     literature) found undulating at least matches, and in several
#     studies exceeds, linear periodization once someone is already
#     trained - the "plateau on linear" pattern this models is exactly
#     why PHUL/PHAT/Powerbuilding (this file's own specialization splits)
#     are built around explicit Power/Hypertrophy day-to-day contrast
#     rather than one flat prescription - here that same logic is
#     extended to every split, not just the three that happened to be
#     named for it.
# The oldest real-world version of this same idea is the Heavy/Medium/
# Light (HLM) weekly template used in Olympic-weightlifting-adjacent
# strength circles for decades: the same lift is trained 2-3x/week, but
# each session sits at a different relative intensity instead of
# identical heavy work every time - functionally the same session-to-
# session undulation as DUP, just under an older name.
_UNDULATION_NOVICE_CEILING = 1  # LEVEL_RANK for "Novice" - Beginner/Novice stay linear, no cycle.

# Cycle applied to whichever days *don't* already carry a split-authored
# emphasis (PHUL/PHAT/Powerbuilding's "power"/"hypertrophy" labels are
# left alone - they're already hand-built undulation and take priority).
# Heavy -> Light -> Medium(baseline, i.e. no override - the goal's own
# bias/prescription runs unmodified) mirrors classic HLM ordering: heavy
# first while freshest in the training cycle, light as the built-in
# recovery session, medium bridging back up to the next heavy day.
# BUGFIX: the "Heavy" slot used to be "power", which - now that "power"
# and "strength" are distinct biases (see GOAL_PROFILES's "Get Strong"
# note) - is the wrong one: a classic HLM Heavy day is a true max-strength
# day (heaviest relative load, lowest reps, longest rest), not an
# explosive/speed day. "strength" is the correct Heavy-day bias.
_DUP_DAY_CYCLE = ["strength", "hypertrophy", None]


def _daily_undulation_emphasis(day_index: int, experience_level: str, authored_emphasis: Optional[str]) -> Optional[str]:
    """What emphasis (if any) this specific day-in-the-week should carry.

    A split's own authored emphasis (PHUL's "Upper Power" etc.) always wins -
    that's already a real coach's explicit day-to-day contrast, not something
    to override. Otherwise: Beginner/Novice get no override (None - plain
    linear, goal's own bias applies uniformly, see module docstring above),
    Intermediate+ get the HLM/DUP-style rotation so the same split (e.g. a
    4-day Upper/Lower run by an Advanced lifter) isn't hypertrophy-biased
    (or power-biased) on every single day, the way it would be if the
    fallback in `_apply_prescription_bias` (goal_profile's flat bias) were
    left to apply unmodified to every day of the week."""
    if authored_emphasis:
        return authored_emphasis
    if _LEVEL_RANK.get(experience_level, 2) <= _UNDULATION_NOVICE_CEILING:
        return None
    return _DUP_DAY_CYCLE[day_index % len(_DUP_DAY_CYCLE)]



# Goal-quality windows, sourced from the FORGE Complete Exercise
# Prescription Packet's Section 1 "Goal-Based Prescription Framework" table
# and its Section 13 "Rest Periods" table:
#
#   Quality                Reps    Sets   Load(%1RM)   Rest
#   Power / Olympic        1-3     3-6    70-85        120-300s (2-5 min)
#   Heavy compound strength 2-6    3-5    75-90        180-300s (3-5 min)
#   Strength + hypertrophy 5-8     3-4    70-82        rest not separately
#                                                       listed - interpolated
#                                                       between the Heavy-
#                                                       strength and Compound-
#                                                       hypertrophy rows
#                                                       above/below it
#   Hypertrophy compound   6-12    3-4    60-80        120-180s (2-3 min)
#
# (the packet's own "power"/"strength" rows both said "Power / Olympic" and
# "Heavy compound strength" - mapped onto this app's existing "power" and
# "strength" bias names 1:1; "Hypertrophy compound" maps onto "hypertrophy".
# The packet's "Strength + hypertrophy" row is now wired to its own
# selectable bias, "strength_hypertrophy" - see
# WorkoutRequest.training_emphasis and GOAL_PROFILES["Strength + Hypertrophy"]
# for the two end-to-end entry points into it.)
#
# Previously sourced from an earlier, less precise reference guide (Power
# 1-5/60-85/120-240s, Strength 1-6/70-90/150-270s, Hypertrophy 6-15/65-
# 80/75-180s) - updated to the packet's exact numbers, including SETS
# windows, which the earlier version didn't model at all (only a "+1 set
# for hypertrophy" hack - see the removed `if bias == "hypertrophy":
# result["sets"] = min(5, result["sets"] + 1)` this replaced).
#
# Rather than nudging the base prescription by a fixed delta (which drifts
# outside the packet's windows at the extremes - e.g. a base 92% load plus
# a flat "+8" clamps into the ceiling and can't come back down for a
# lighter-difficulty exercise), each bias remaps onto its target window
# using `idx`: where the *base* (pre-bias) load_pct_1rm already sits
# between the engine's own 40-92% floor/ceiling. idx acts as a 0-1 proxy
# for "how hard/heavy this specific exercise+difficulty+readiness already
# is" - low idx (an easier exercise, or a lighter readiness day) lands
# near the bottom of the target window, high idx lands near the top -
# so the packet's ranges are respected exactly regardless of the
# exercise's difficulty rating or today's readiness, instead of being a
# fixed offset that can overshoot them. Sets follow the same idx (heavier
# day -> more sets, within the packet's own sets range for that quality).
_GOAL_WINDOWS = {
    # bias: (load_pct_low, load_pct_high, reps_low, reps_high, rest_low, rest_high, sets_low, sets_high)
    "power":       (70, 85, 1, 3, 120, 300, 3, 6),
    "strength":    (75, 90, 2, 6, 180, 300, 3, 5),
    # Packet gives an explicit reps/sets/load band for this row (5-8, 3-4,
    # 70-82) but no rest window of its own - rest is interpolated as the
    # midpoint of the "strength" row above and the "hypertrophy" row below
    # it (180-300s and 120-180s -> 150-240s), the same "sits between its two
    # neighbors" relationship the packet's own table shows for reps/load.
    "strength_hypertrophy": (70, 82, 5, 8, 150, 240, 3, 4),
    "hypertrophy": (60, 80, 6, 12, 120, 180, 3, 4),
}


def _round_rest_seconds(raw_seconds: float) -> int:
    """Snaps an interpolated rest time to the nearest 15s.

    BUG FIXED (v5.22): `_apply_prescription_bias` linearly interpolates
    rest between a goal window's low/high bound (e.g. strength_hypertrophy
    is 150-240s) and previously just `round()`-ed straight to the nearest
    whole second - so a real prescription came back "rest 158s" or "rest
    256s". No coach or program ever writes rest in single seconds; every
    real rest prescription (and every other hand-typed rest value already
    in this codebase - 60/90/120/180/75 in progression_engine.py) is a
    multiple of 15. A precise-looking but nonsensical number like 158s
    reads as a bug to anyone using the app, even though the underlying
    math was "working as designed" - so the fix is rounding the interpolated
    value to something a coach would actually write, not changing the
    interpolation itself.
    """
    return max(15, round(raw_seconds / 15) * 15)


# Heavy, maximal-effort barbell hinge patterns - a full-ROM conventional/
# sumo deadlift off the floor, a rack pull, a Good Morning - all load the
# spine near a 1RM technical limit on every single rep, unlike a Romanian
# Deadlift or a kettlebell swing (both deliberately submaximal, partial-ROM
# or dynamic patterns that are routinely programmed for 8-12+ reps in real
# hypertrophy plans). No real strength coach lets these creep to
# strength_hypertrophy/hypertrophy-window rep counts (5-8, 6-12) - the risk
# isn't the load, it's that a lifter grinding out rep 7-8 of a heavy floor
# deadlift is doing so with a rounding back and fried grip, which is where
# the injuries actually happen. Capped independent of goal/bias below.
_MAX_EFFORT_HINGE_FAMILIES = frozenset({
    "hinge__deadlift",       # Barbell Conventional Deadlift, Sumo Deadlift
    "hinge__pull",           # Rack Pull
    "hinge__good_morning",   # Good Morning
})
_MAX_EFFORT_HINGE_REP_CAP = 6


def _apply_prescription_bias(
    prescription: Dict, emphasis: Optional[str], goal_profile: Dict,
    movement_family: Optional[str] = None,
) -> Dict:
    """Remaps the engine's own sets/reps/load/rest prescription onto the
    reference guide's Power / Strength / Hypertrophy windows (see
    _GOAL_WINDOWS above). A day's own `emphasis` wins over the goal's
    general `bias` (a DUP "Hypertrophy" day still runs higher-rep even if
    the overall goal is Get Strong - that Heavy/Light/Medium contrast is
    the entire point of daily undulation).

    `movement_family` (optional, defaults to None = no cap applied) is
    checked against _MAX_EFFORT_HINGE_FAMILIES below - see that set's own
    comment for why a heavy floor deadlift/rack pull/Good Morning can't be
    allowed to ride the same hypertrophy-window rep count as everything
    else."""
    bias = emphasis or goal_profile.get("bias")
    ptype = prescription.get("type")
    if not bias or bias not in _GOAL_WINDOWS or ptype not in ("strength", "strength_bodyweight"):
        return prescription
    # BUGFIX (goal selection was corrupting KB ballistic and Core/Grip
    # numbers - see the "ballistic"/"accessory" flags set in
    # progression_engine._prescribe_volume_core for the full bug report).
    # Both flags mark a type=="strength"/"strength_bodyweight" prescription
    # that was deliberately hand-tuned for its own movement (kettlebell
    # swings/cleans/snatches; dynamic core & grip bracing work) and was
    # never meant to be remapped onto the barbell-lift Power/Strength/
    # Hypertrophy windows below - those windows describe how to load a
    # squat/bench/deadlift/pull-up, not a kettlebell swing or a hanging
    # knee raise. Returning early here (same escape hatch the "isolation"
    # type already gets, one level up, for the identical reason) keeps
    # these exercises' own readiness/difficulty-scaled reps, sets, and load
    # intact regardless of which goal is selected, instead of every goal
    # silently collapsing them into a near-max low-rep barbell prescription.
    if prescription.get("ballistic") or prescription.get("accessory"):
        return prescription

    pct_lo, pct_hi, reps_lo, reps_hi, rest_lo, rest_hi, sets_lo, sets_hi = _GOAL_WINDOWS[bias]
    if movement_family in _MAX_EFFORT_HINGE_FAMILIES:
        reps_hi = min(reps_hi, _MAX_EFFORT_HINGE_REP_CAP)
        reps_lo = min(reps_lo, reps_hi)
    result = dict(prescription)

    if ptype == "strength":
        base_pct = result.get("load_pct_1rm", 55)
        # engine's own base load_pct_1rm floor/ceiling (load_prescription's
        # is_loaded_strength branch) is 40-92 - normalize onto 0-1.
        idx = max(0.0, min(1.0, (base_pct - 40) / (92 - 40)))
        result["load_pct_1rm"] = round(pct_lo + idx * (pct_hi - pct_lo))
        # Higher idx (heavier day) -> fewer reps within the window, not more.
        result["reps"] = round(reps_hi - idx * (reps_hi - reps_lo))
        result["rest_seconds"] = _round_rest_seconds(rest_lo + idx * (rest_hi - rest_lo))
        # Sets now come from the packet's own per-quality sets window (e.g.
        # Power 3-6, Strength 3-5, Hypertrophy 3-4) via the same idx, instead
        # of the old flat "+1 set for hypertrophy, nothing for power/
        # strength" hack - that hack never touched power/strength sets at
        # all and capped hypertrophy at a fixed +1 regardless of how heavy
        # the day already was.
        result["sets"] = round(sets_lo + idx * (sets_hi - sets_lo))
    else:  # strength_bodyweight - no load field, so idx comes from reps instead
        base_reps = result.get("reps", 8)
        # base bodyweight reps run roughly 3-13 (harder exercise -> fewer
        # reps) - normalize the same direction as idx above (harder -> idx closer to 1).
        idx = max(0.0, min(1.0, (13 - base_reps) / (13 - 3)))
        result["reps"] = round(reps_hi - idx * (reps_hi - reps_lo))
        result["rest_seconds"] = _round_rest_seconds(rest_lo + idx * (rest_hi - rest_lo))
        result["sets"] = round(sets_lo + idx * (sets_hi - sets_lo))
        if bias == "power":
            result["note"] = ((result.get("note", "") + " ") if result.get("note") else "") + \
                "Power day: move each rep as explosively as the variation allows."
    return result


def _apply_week_progression(
    prescription: Dict, week_number: int, is_deload: bool, continue_from_week: Optional[int] = None,
) -> Dict:
    """Simple linear progressive overload across the mesocycle. Deload weeks
    get no extra bump here - the deload's actual lightening already happened
    inside generate_session (readiness was forced low for that week, which
    triggers its built-in deload_mode: fewer sets, capped difficulty).

    `continue_from_week` (see ProgramRequest.continue_from_week's docstring)
    shifts what "week_number" means for the progression math only - week 1
    of THIS program is treated as overall week `continue_from_week` instead
    of a fresh baseline, so a person generating their second/third/... block
    keeps climbing from where the last one left off rather than resetting.
    None (default) reproduces the exact old behavior: week_number is used as-is.
    """
    result = dict(prescription)
    effective_week = (continue_from_week + week_number - 1) if continue_from_week else week_number
    if is_deload:
        result["progression_note"] = f"Week {week_number}: deload - reduced volume and intensity to recover."
        return result

    step = effective_week - 1  # 0 only on the very first week of the very first cycle
    if step == 0:
        result["progression_note"] = f"Week {week_number}: baseline."
        return result

    ptype = result.get("type")
    if ptype == "strength":
        result["load_pct_1rm"] = min(95, result["load_pct_1rm"] + step * 3)
        result["progression_note"] = f"Week {week_number}: +{step * 3}% load vs. week 1."
    elif ptype == "strength_bodyweight":
        result["reps"] = result["reps"] + step
        result["progression_note"] = f"Week {week_number}: +{step} rep(s) vs. week 1 - add load (vest/band) once this gets easy."
    elif ptype == "isolation":
        result["reps"] = result["reps"] + step
        result["progression_note"] = f"Week {week_number}: +{step} rep(s) vs. week 1 - add a small load increase once the top of the range feels easy."
    elif ptype == "conditioning":
        result["work_seconds"] = round(result["work_seconds"] * (1 + 0.05 * step))
        result["rest_seconds"] = max(15, round(result["rest_seconds"] * (1 - 0.05 * step)))
        result["progression_note"] = f"Week {week_number}: longer work intervals, shorter rest vs. week 1."
    elif ptype == "isometric":
        result["hold_seconds"] = round(result["hold_seconds"] * (1 + 0.08 * step))
        result["progression_note"] = f"Week {week_number}: longer holds vs. week 1."
    elif ptype == "carry":
        result["distance_meters"] = round(result["distance_meters"] * (1 + 0.06 * step))
        result["progression_note"] = f"Week {week_number}: longer carry distance vs. week 1."
    else:
        result["progression_note"] = f"Week {week_number}: hold technique steady, add a rep if it's clean."
    return result


# Combat Sports & Rugby S&C Manual, Parts 5-9 (per-sport "Strength Training"
# vs. "Conditioning Program" sections) + Part 1 core principle ("manage the
# interference effect... separate heavy lifting and hard conditioning by 6+
# hours where possible"). The manual never puts a conditioning exercise
# inside a lifting session for these 11 sports - conditioning is its own
# block, scheduled by the sport's aerobic:lactic ratio, entirely separate
# from the Squat/Hinge/Push/Pull/Power slots. That separate block is exactly
# what `conditioning_guidance` (below, from SPORT_SPLIT_GUIDANCE +
# conditioning_reference()) already builds, so for this sport set the
# "Conditioning" category is dropped from each day's *template* categories
# before exercises are picked - it should never compete with squat/hinge/
# push/pull for a slot in the same session. This only strips the category
# that SPLIT_TEMPLATES bakes in by default; an explicit user goal like "Lose
# Fat" or "Conditioning" (see GOAL_PROFILES category_boost) still adds
# Conditioning back in, since that's the person's own explicit intent for
# that request, not a template default. "Sport Specific" is left untouched -
# only Conditioning was the manual mismatch. Sports outside the manual
# (HYROX, Rock Climbing, generic goals) keep the original in-session
# conditioning-finisher behavior; that's a deliberate design choice for
# those, not a mismatch with a source manual, so it's out of scope here.
_MANUAL_NO_INLINE_CONDITIONING_SPORTS = {
    "MMA", "BJJ", "Wrestling", "Judo", "Boxing", "Kickboxing",
    "Muay Thai", "Sanda", "Sambo", "Special Forces", "Rugby",
}


def _weekly_muscle_frequency(engine, day_results: List[Dict]) -> Dict[str, Dict]:
    """How many distinct days in this one week each muscle got direct
    (primary-mover) vs. only secondary/assisting work - the actual
    "kitni baar train karna chahiye" question, answered per muscle instead
    of left implicit in whichever split template happened to be picked.

    Counts DAYS, not exercises/sets: 3 chest exercises stacked into one
    Push day is still "1x/week" for frequency purposes, same as a coach
    would read it - frequency is about how often the muscle gets a fresh
    training stimulus with recovery in between, not raw exercise count.
    """
    primary_days: Dict[str, set] = {}
    secondary_days: Dict[str, set] = {}
    for day in day_results:
        day_label = day["day_label"]
        for pe in day["prescribed_workout"]:
            data = engine.exercises_by_id.get(pe["id"], {})
            for m in data.get("primary_muscles", []):
                primary_days.setdefault(m, set()).add(day_label)
            for m in data.get("secondary_muscles", []):
                secondary_days.setdefault(m, set()).add(day_label)

    result: Dict[str, Dict] = {}
    for muscle in sorted(set(primary_days) | set(secondary_days)):
        direct = len(primary_days.get(muscle, ()))
        secondary_only = len(secondary_days.get(muscle, set()) - primary_days.get(muscle, set()))
        if direct >= 2:
            flag = "On target - 2x/week+ direct work, the research-backed minimum for reliable hypertrophy/strength gains at a given weekly volume."
        elif direct == 1:
            flag = "Below optimal - only 1x/week direct work this week; 2x/week generally beats 1x/week at equal total volume."
        elif secondary_only:
            flag = "Indirect only - hit as a secondary/assisting mover this week, no dedicated primary work."
        else:
            flag = "Not trained this week."
        result[muscle] = {
            "direct_sessions_per_week": direct,
            "secondary_only_sessions_per_week": secondary_only,
            "flag": flag,
        }
    return result


def generate_program(engine, req: ProgramRequest, athlete_id=None, db=None) -> Dict:
    from fastapi import HTTPException  # local import: keeps this module importable/testable without FastAPI wired up
    # Phase 5 (roadmap): threaded straight through to each day's
    # generate_session call below exactly like every other per-day
    # parameter here - None/None (every caller before this pass) is a
    # complete no-op, see ProgressionEngine.generate_session's own
    # docstring for why.

    # Custom mode (mirrors WorkoutRequest.mode="custom"): the person supplies
    # every day's exercises themselves via custom_days, so there's no split
    # template to pick or recommend - split_id/raw_split_id/template become a
    # synthetic stand-in just so the rest of this function (which reads
    # template["name"]/["description"] for the response, and day_slots for
    # the week/day loop below) doesn't need two parallel code paths further
    # down. preferred_split/training_phase's split-matching are meaningless
    # here and simply skipped.
    phase_split = None  # only ever set in the preset branch below; stays None for custom mode
    if req.mode == "custom":
        if not req.custom_days:
            raise HTTPException(
                status_code=400,
                detail="custom_days is required (and must be non-empty) when mode='custom'.",
            )
        raw_split_id = split_id = "custom"
        template = {
            "name": "Custom Program",
            "description": "Built from your own exercise picks for each day - the engine still runs its equipment/injury/strength/level safety checks per exercise, it just does none of the exercise selection itself.",
        }
        day_slots = _cycle_days(
            [{"label": d.label, "custom_exercise_ids": d.selected_exercise_ids} for d in req.custom_days],
            req.days_per_week,
        )
    else:
        phase_split = _split_for_phase(req.training_phase, req.days_per_week) if req.preferred_split == "auto" else None
        if phase_split:
            raw_split_id = phase_split
            split_id = _apply_experience_ceiling(raw_split_id, req.days_per_week, req.experience_level)
        elif req.preferred_split == "auto":
            raw_split_id = _recommend_split_raw(req.days_per_week, req.primary_goal, req.sport)
            split_id = _apply_experience_ceiling(raw_split_id, req.days_per_week, req.experience_level)
        else:
            raw_split_id = split_id = req.preferred_split
        template = SPLIT_TEMPLATES.get(split_id)
        if template is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown split '{split_id}'. See GET /api/v1/splits for valid ids.",
            )
        day_slots = _cycle_days(template["days"], req.days_per_week)

    # FORGE S&C Template seed (see progression_engine.template_seed_multiplier's
    # docstring for the full contract - this only ever biases ranking among
    # exercises the engine already judged safe, never substitutes or filters).
    # One template for the whole program, picked the same way
    # sc_template_guidance below already picks its top match (sport + level +
    # days_per_week) - not per day, since re-querying per day/week could land
    # on a different template mid-program for no reason visible to the
    # caller. None for mode="custom" (the person is already choosing every
    # exercise themselves) and for any sport with no library coverage
    # (LIBRARY_SPORTS), same "None means not covered" contract every other
    # sc_template_library-backed field in this function already uses.
    seed_template = None
    if req.mode != "custom" and resolve_wizard_sport(req.sport) in LIBRARY_SPORTS:
        seed_matches = templates_for_program(req.sport, req.experience_level, req.days_per_week, limit=1)
        if seed_matches:
            seed_template = get_template(seed_matches[0]["global_id"])
    seed_days = seed_template["days"] if seed_template else None

    # Independent, advisory-only read on whether req.experience_level - which
    # _apply_experience_ceiling above already used as a hard ceiling on which
    # split gets offered (EXPERIENCE_SPLIT_ALLOWLIST), and which every day's
    # WorkoutRequest below uses as its own exercise-level ceiling - actually
    # matches what the entered numbers say. See strength_standards.py. This
    # never changes split_id, day_slots, or the periodization model computed
    # further down; computed once here (not per day/week) and just rides
    # along in the response so a mis-stated level is visible instead of
    # silently flowing through both of those, per that module's docstring.
    bio = req.biometrics
    level_estimate = classify_strength_level(
        weight_kg=bio.weight_kg if bio else 0.0,
        bench_press_1rm=(bio.bench_press_1rm or 0.0) if bio else 0.0,
        squat_1rm=(bio.squat_1rm or 0.0) if bio else 0.0,
        deadlift_1rm=(bio.deadlift_1rm or 0.0) if bio else 0.0,
        pullups_max_reps=(bio.pullups_max_reps or 0) if bio else 0,
        pushups_max_reps=(bio.pushups_max_reps or 0) if bio else 0,
        sex=bio.sex if bio else None,
    )
    level_check_result = level_check(req.experience_level, level_estimate)

    goal_profile = GOAL_PROFILES.get(req.primary_goal, GOAL_PROFILES["General Fitness"])
    # Resolved once for the whole program - see _seed_days_by_label's
    # docstring for why this can't just be seed_days[day_index % len(...)].
    # Needs goal_profile (just above) since a day's real target_categories
    # depends on it (see _day_target_categories).
    seed_names_by_label = _seed_days_by_label(engine, day_slots, seed_days, goal_profile, req.sport)
    # day_slots is already set above (custom_days for mode="custom", the
    # split template's own days otherwise).
    exercise_count = _estimate_exercise_count(req.session_duration_minutes, req.outside_training_sessions_per_week)

    # A mesocycle shorter than 3 weeks doesn't get an automatic deload week -
    # there's no accumulated fatigue yet to deload from.
    deload_week = req.weeks if req.weeks >= 3 else None

    # Per-day-label exercise history across the mesocycle - e.g. every
    # "Full Body A" across every week shares one history list. Passed back
    # to the engine as exclude_exercise_ids so it can deprioritize (not
    # hard-ban) repeats and rotate toward other near-tied candidates instead
    # of mechanically returning the exact same exercises week after week for
    # the same day-type. See WorkoutRequest.exclude_exercise_ids /
    # ProgressionEngine._pick_with_variety for how that rotation works.
    history_by_day_label: Dict[str, List[str]] = {}
    personalization_applied = False

    # Movement-family variety cap (regression fix): exclude_exercise_ids
    # above only ever bans exact exercise ids already used this week, but
    # a "Hinge" slot can still land on Clean High Pull / Snatch High Pull /
    # Hang High Pull / Kettlebell High Pull on four separate days - four
    # distinct ids that are functionally the same drill under one
    # movement_family. Once a family hits _MAX_SAME_FAMILY_PER_WEEK uses in
    # a week, every other exercise sharing that family gets added to the
    # exclude list too, so the engine is forced toward a genuinely
    # different movement for the rest of that week - reset every week, same
    # as used_this_week below.
    _MAX_SAME_FAMILY_PER_WEEK = 2
    family_by_id: Dict[str, Optional[str]] = {
        ex_id: ex.get("movement_family") for ex_id, ex in engine.exercises_by_id.items()
    }
    ids_by_family: Dict[str, List[str]] = {}
    for ex_id, fam in family_by_id.items():
        if fam:
            ids_by_family.setdefault(fam, []).append(ex_id)

    weeks_output = []
    for week_number in range(1, req.weeks + 1):
        is_deload = week_number == deload_week
        effective_readiness = min(req.readiness, 35) if is_deload else req.readiness

        # Exercises already picked *this week*, across every day so far -
        # separate from history_by_day_label (which only rotates the same
        # day-label week to week, e.g. "Full Body A" vs its own past picks).
        # Without this, "Full Body A" and "Full Body B" in the same week
        # never knew about each other and could independently land on the
        # same top-scoring exercise for the same day. Reset every week
        # (a Monday/Thursday repeat of the same lift within one week is
        # normal programming - it's only a same-week, same-slot-type
        # collision that's the bug).
        used_this_week: List[str] = []
        family_counts_this_week: Dict[str, int] = {}

        day_results = []
        for day_index, day_slot in enumerate(day_slots):
            day_label = day_slot["label"]

            if req.mode == "custom":
                # Custom mode: no category/muscle targeting, no exercise_limit
                # trimming, no exclude_exercise_ids rotation - generate_session
                # skips all of that for mode="custom" anyway (an explicit pick
                # is never silently dropped or substituted), so there's nothing
                # useful to pass here beyond the day's own exercise list. The
                # week-to-week progression/emphasis bias below still applies -
                # picking the exercises is the person's job, prescribing them
                # week to week is still the program builder's.
                categories = None
                # No FORGE S&C Template seeding in custom mode - the person is
                # already choosing every exercise themselves (seed_template is
                # always None here anyway, see its own resolution above).
                template_seed_names = None
                day_request = WorkoutRequest(
                    mode="custom",
                    sport=req.sport,
                    experience_level=req.experience_level,
                    equipment_available=req.equipment_available,
                    readiness=effective_readiness,
                    injuries=req.injuries,
                    injury_stages=req.injury_stages,
                    injury_sides=req.injury_sides,
                    biometrics=req.biometrics,
                    conditioning_emphasis=req.conditioning_emphasis,
                    selected_exercise_ids=day_slot["custom_exercise_ids"],
                    variety_seed=week_number * len(day_slots) + day_index,
                    outside_training_sessions_per_week=req.outside_training_sessions_per_week,
                )
            else:
                if goal_profile.get("override_categories"):
                    categories = list(goal_profile["category_boost"])
                else:
                    base_categories = day_slot.get("categories") or []
                    if req.sport in _MANUAL_NO_INLINE_CONDITIONING_SPORTS:
                        base_categories = [c for c in base_categories if c != "Conditioning"]
                    categories = list(dict.fromkeys(
                        base_categories + goal_profile.get("category_boost", [])
                    ))

                # Alignment resolved once before the week loop (see
                # _seed_days_by_label) - by day_label, not day_index, so
                # every week's "Push" day (etc.) consistently gets the same
                # best-fit seed day rather than index-cycling through the
                # seed template's own day list independently of what this
                # split day actually trains.
                template_seed_names = seed_names_by_label.get(day_label)

                day_request = WorkoutRequest(
                    sport=req.sport,
                    experience_level=req.experience_level,
                    equipment_available=req.equipment_available,
                    readiness=effective_readiness,
                    injuries=req.injuries,
                    injury_stages=req.injury_stages,
                    injury_sides=req.injury_sides,
                    biometrics=req.biometrics,
                    conditioning_emphasis=req.conditioning_emphasis,
                    manual_only=req.manual_only,
                    target_categories=categories or None,
                    target_muscles=day_slot.get("muscles"),
                    exercise_limit=exercise_count,
                    template_seed_names=template_seed_names,
                    exclude_exercise_ids=list(dict.fromkeys(
                        history_by_day_label.get(day_label, []) + used_this_week
                    )) or None,
                    hard_exclude_exercise_ids=[
                        fam_ex_id
                        for fam, count in family_counts_this_week.items()
                        if count >= _MAX_SAME_FAMILY_PER_WEEK
                        for fam_ex_id in ids_by_family.get(fam, [])
                    ] or None,
                    variety_seed=week_number * len(day_slots) + day_index,
                    # Goal-level bias (e.g. "Build Muscle"'s flat "hypertrophy",
                    # "Strength + Hypertrophy"'s flat "strength_hypertrophy"),
                    # so generate_session's own exercise ranking (see
                    # sport_profiles.hypertrophy_quality_multiplier) already
                    # favors the same emphasis _apply_prescription_bias below
                    # applies to sets/reps/load - not just prescription shape but
                    # which safe exercises get picked in the first place. Left
                    # unset (None) for every goal whose bias isn't one
                    # hypertrophy_quality_multiplier actually reads ("power" and
                    # "strength" only affect _apply_prescription_bias's sets/
                    # reps/load remap below, not ranking), so this stays a
                    # no-op for every goal outside these two.
                    training_emphasis=goal_profile.get("bias") if goal_profile.get("bias") in ("hypertrophy", "strength_hypertrophy") else None,
                    outside_training_sessions_per_week=req.outside_training_sessions_per_week,
                )
            session_result = engine.generate_session(
                day_request, athlete_id=athlete_id, db=db,
                training_phase=req.training_phase, expected_days_per_week=req.days_per_week,
            )
            personalization_applied = personalization_applied or bool(
                session_result.get("personalization_applied")
            )
            picked_ids = [pe["id"] for pe in session_result["prescribed_workout"]]
            history_by_day_label.setdefault(day_label, []).extend(picked_ids)
            used_this_week.extend(picked_ids)
            for picked_id in picked_ids:
                fam = family_by_id.get(picked_id)
                if fam:
                    family_counts_this_week[fam] = family_counts_this_week.get(fam, 0) + 1

            emphasis = _daily_undulation_emphasis(day_index, req.experience_level, day_slot.get("emphasis"))
            phase_info = PHASE_GUIDANCE.get(req.training_phase) if req.training_phase else None
            outside_training_multiplier = outside_training_volume_multiplier(req.outside_training_sessions_per_week)
            for pe in session_result["prescribed_workout"]:
                pe["prescription"] = _apply_prescription_bias(
                    pe["prescription"], emphasis, goal_profile, movement_family=pe.get("movement_family"),
                )
                pe["prescription"] = _apply_week_progression(
                    pe["prescription"], week_number, is_deload, req.continue_from_week,
                )
                if phase_info:
                    pe["prescription"] = _apply_phase_volume_scaling(pe["prescription"], phase_info["volume_multiplier"])
                pe["prescription"] = _apply_outside_training_set_scaling(
                    pe["prescription"], pe.get("programming_role"), outside_training_multiplier,
                )
                # load_pct_1rm just moved (bias/week progression/phase scaling all touch
                # it) - re-derive working_weight_kg from the *final* percentage rather
                # than the pre-adjustment one generate_session already attached, so the
                # displayed kg always matches the displayed %.
                exercise_data = engine.exercises_by_id.get(pe["id"], {})
                pe["prescription"] = add_working_weight(
                    pe["prescription"], pe.get("category"), req.biometrics, equipment=pe.get("equipment"),
                    strength_requirements=exercise_data.get("strength_requirements"),
                    movement_type=exercise_data.get("movement_type"),
                )

            day_results.append({
                "day_label": day_slot["label"],
                "emphasis": emphasis,
                "focus_categories": categories or None,
                "focus_muscles": day_slot.get("muscles"),
                "exercise_count": len(session_result["prescribed_workout"]),
                "prescribed_workout": session_result["prescribed_workout"],
                "session_structure": session_result["session_structure"],
                "deload_mode": session_result["deload_mode"],
                # Same transparency contract as personalization_applied/
                # history_signals (see generate_session's own docstring) -
                # previously computed here and then silently dropped before
                # ever reaching the response, so a day's deload_mode/implied
                # readiness could shift from RPE trend/volume spike/missed-
                # session gap with no way for the frontend to explain why.
                # "active": false (empty reasons) for anonymous callers or
                # too little logged history - same no-op shape as before
                # this field was forwarded.
                "adaptive_training_load": session_result["adaptive_training_load"],
                # (v5.18) Was silently dropped here even though
                # generate_session always computes it - a program day with a
                # moderate/mild injury exclusion had no way to surface which
                # exercises got locked out or what to swap them for, unlike
                # the single-session /generate-workout endpoint which always
                # returned this. See progression_engine.py's excluded{}
                # assembly for what each entry carries (reasons,
                # alternatives, manual_guidance, alternatives_note).
                "excluded_exercises": session_result["excluded_exercises"],
                # None when no FORGE S&C Template matched this program's
                # sport/level/days_per_week (seed_template is None) - same
                # shape as every other "not covered" field in this response.
                # matched_count is how many of prescribed_workout's own
                # exercises the seed actually influenced (see
                # sc_template_seed_matched on each prescribed exercise) -
                # 0 is a normal outcome (the coach's picks didn't clear this
                # athlete's own safety/equipment/level checks this time),
                # not a bug.
                "sc_template_seed": (
                    {
                        "global_id": seed_template["global_id"],
                        "name": seed_template["name"],
                        "seeded_names": template_seed_names,
                        "matched_count": sum(
                            1 for pe in session_result["prescribed_workout"]
                            if pe.get("sc_template_seed_matched")
                        ),
                    }
                    if seed_template else None
                ),
            })

        weekly_muscle_sets = compute_weekly_muscle_sets(engine, day_results)
        weeks_output.append({
            "week_number": week_number,
            "is_deload": is_deload,
            "days": day_results,
            "muscle_frequency": _weekly_muscle_frequency(engine, day_results),
            # Real weekly SET volume per muscle group, checked against an
            # experience/goal-scaled target range - see volume_engine.py.
            # Deload weeks are still reported (their lower set counts are
            # the whole point of a deload) but excluded from the program-
            # level average below, same as muscle_frequency_summary already
            # excludes them.
            "weekly_volume": evaluate_weekly_volume(
                weekly_muscle_sets, req.experience_level, req.primary_goal,
                req.outside_training_sessions_per_week,
            ),
        })

    # Program-level view: average each muscle's direct (primary-mover)
    # training frequency across every non-deload week, so a single light
    # week doesn't make an otherwise-fine split look under-trained, and
    # flag anything that's chronically under the 2x/week mark the training
    # literature treats as the minimum for reliably driving hypertrophy/
    # strength gains at a given weekly volume (e.g. Schoenfeld et al. 2016).
    muscle_totals: Dict[str, int] = {}
    counted_weeks = 0
    for week in weeks_output:
        if week["is_deload"]:
            continue
        counted_weeks += 1
        for muscle, info in week["muscle_frequency"].items():
            muscle_totals[muscle] = muscle_totals.get(muscle, 0) + info["direct_sessions_per_week"]
    counted_weeks = counted_weeks or len(weeks_output) or 1
    muscle_frequency_summary = {
        muscle: {
            "avg_direct_sessions_per_week": round(total / counted_weeks, 1),
            "meets_2x_minimum": round(total / counted_weeks, 1) >= 2,
        }
        for muscle, total in sorted(muscle_totals.items())
    }
    under_trained_muscles = sorted(
        m for m, info in muscle_frequency_summary.items() if not info["meets_2x_minimum"]
    )

    # Program-level volume view: average each landmark-tracked muscle
    # group's weekly SET total across non-deload weeks (same exclusion as
    # muscle_frequency_summary above, for the same reason - a deload week's
    # intentionally-low volume shouldn't make an otherwise well-dosed
    # program look under-volumed), then re-run it through the same
    # low/optimal/high/excessive bands a single week gets. This is the
    # actual "is total weekly volume appropriate for this goal/experience"
    # answer muscle_frequency_summary's day-count view can't give - a
    # muscle can hit 2x/week frequency at 6 sets/week (badly under-dosed)
    # or at 24 sets/week (likely excessive) and look identical to that view.
    volume_set_totals: Dict[str, float] = {}
    for week in weeks_output:
        if week["is_deload"]:
            continue
        for muscle, info in week["weekly_volume"].items():
            volume_set_totals[muscle] = volume_set_totals.get(muscle, 0.0) + info["weekly_sets"]
    weekly_volume_summary = evaluate_weekly_volume(
        {m: round(total / counted_weeks, 1) for m, total in volume_set_totals.items()},
        req.experience_level, req.primary_goal, req.outside_training_sessions_per_week,
    )
    under_dosed_muscles = sorted(m for m, info in weekly_volume_summary.items() if info["status"] == "under")
    over_dosed_muscles = sorted(m for m, info in weekly_volume_summary.items() if info["status"] in ("high", "excessive"))

    sport_guidance = SPORT_SPLIT_GUIDANCE.get(req.sport)
    sport_recommended = bool(
        sport_guidance and req.preferred_split == "auto"
        and _sport_preferred_split(req.days_per_week, req.sport) == split_id
    )
    sport_rationale = (
        sport_split_rationale(req.sport, req.days_per_week, split_id) if sport_recommended else None
    )

    experience_capped = req.preferred_split == "auto" and raw_split_id != split_id
    experience_rationale = (
        f"Stepped down to {template['name']} for a {req.experience_level.lower()} lifter - "
        "body-part specialization splits assume a technique/work-capacity base this stage "
        "hasn't built yet; full-body/upper-lower frequency is what drives progress here."
        if experience_capped else None
    )

    is_novice = _LEVEL_RANK.get(req.experience_level, 2) <= _UNDULATION_NOVICE_CEILING
    periodization_model = "Linear" if is_novice else "Daily Undulating (DUP / Heavy-Light-Medium)"
    periodization_rationale = (
        "Straight linear progression - the same lift trained the same way each session, load "
        "nudged up week to week. This is what the periodization literature consistently finds "
        "works best at this training age; undulating/DUP schemes add complexity a beginner "
        "doesn't yet need to keep progressing."
        if is_novice else
        "Each day in the split rotates a Heavy / Light / Medium (or Power / Hypertrophy) target "
        "instead of repeating the same stimulus every session, layered on top of the same "
        "week-to-week load progression. Rhea et al. (2002) found this kind of daily undulation "
        "produced larger strength gains than equal-volume linear training in already-trained "
        "lifters, and it's the same logic behind classic HLM weekly templates - a split-authored "
        "day (e.g. PHUL's 'Upper Power') keeps its own explicit emphasis; everything else "
        "rotates automatically."
    )

    training_phase_block = None
    if req.training_phase:
        phase = PHASE_GUIDANCE.get(req.training_phase, {})
        training_phase_block = {
            "phase": req.training_phase,
            "typical_duration": phase.get("duration"),
            "lifting_focus": phase.get("lifting_focus"),
            "conditioning_focus": phase.get("conditioning_focus"),
            "volume_multiplier": phase.get("volume_multiplier"),
            "split_matched_phase": bool(phase_split and split_id == phase_split),
        }

    sport_conditioning = sport_conditioning_profile(req.sport)
    conditioning_guidance = None
    if sport_conditioning:
        ref = conditioning_reference(req.sport)
        aerobic_pct = sport_conditioning["aerobic_pct"]
        lactic_pct = sport_conditioning["lactic_pct"]
        conditioning_guidance = {
            "sport": req.sport,
            "aerobic_pct": aerobic_pct,
            "lactic_pct": lactic_pct,
            "best_splits": sport_conditioning["best_splits"],
            "gym_emphasis": sport_conditioning["gym_emphasis"],
            "conditioning_notes": sport_conditioning["conditioning_notes"],
            "time_saver": sport_conditioning["time_saver"],
            # Weighted picks from the manual's Part 6 menus - biased toward
            # aerobic or lactic sessions/week in proportion to the sport's
            # own ratio, not just "here's every option that exists".
            "suggested_aerobic_sessions_per_week": round(aerobic_pct / 100 * 3) or (1 if aerobic_pct > 0 else 0),
            "suggested_lactic_sessions_per_week": round(lactic_pct / 100 * 2.5) or (1 if lactic_pct > 0 else 0),
            "aerobic_session_menu": ref["aerobic_session_menu"],
            "lactic_session_menu": ref["lactic_session_menu"],
            "weekly_fitting_note": ref["weekly_fitting_note"],
            "universal_add_ons": ref["universal_add_ons"],
            "warmup_protocol": ref["warmup_protocol"],
            "warmup_note": ref["warmup_note"],
        }

    # Iowa State Grappling S&C Playbook (grappling_playbook.py) - only
    # populated for the four sports that playbook actually covers
    # (GRAPPLING_SPORTS), same "None means not covered" contract
    # conditioning_guidance already uses above. Week 1 of the requested
    # block anchors the wave lookup; a program that runs longer than 4
    # weeks repeats the same wave every 4 weeks (see wave_week_pct's own
    # docstring for why callers wrap week-of-block before calling it), so
    # this reports week 1's band as the block's starting point rather than
    # trying to project every week's number into one response.
    grappling_guidance = None
    if req.sport in GRAPPLING_SPORTS:
        loading = level_loading_table(req.experience_level)
        grappling_guidance = {
            "sport": req.sport,
            "supplemental_block": discipline_supplemental_block(req.sport),
            "level_loading": loading,
            "week_1_wave_pct": wave_week_pct(req.experience_level, 1),
            "progression_rule": GRAPPLING_PROGRESSION_RULE,
            "armor_placement_rule": ARMOR_PLACEMENT_RULE,
        }

    # FORGE S&C Template Libraries (sc_template_library.py) - only
    # populated for sports with real coverage (LIBRARY_SPORTS), same
    # "None means not covered" contract conditioning_guidance and
    # grappling_guidance already use. Surfaces a short list of matching
    # *named templates the caller can browse via GET /api/v1/sc-templates/
    # {global_id}* for reference/comparison.
    #
    # The top match of this same list (seed_template, resolved earlier in
    # this function) is also used as a SEED: each day's WorkoutRequest gets
    # that template's own day exercise names via template_seed_names, which
    # progression_engine.template_seed_multiplier uses to bias ranking
    # among exercises the live engine already independently judged safe for
    # this athlete (equipment/injury/strength/level - every check runs
    # exactly as before). This still isn't the old removed-for-good static
    # "Manual" mode (see routes.py's module docstring): a template's fixed
    # exercise list is never served as-is, never bypasses a safety check,
    # and never overrides what the live engine selects when the template's
    # pick doesn't clear this athlete's own checks - see
    # day_results["sc_template_seed"]["matched_count"] per day for how much
    # of a given day actually came from the seed vs. the engine's own pick.
    sc_template_guidance = None
    if resolve_wizard_sport(req.sport) in LIBRARY_SPORTS:
        matches = templates_for_program(req.sport, req.experience_level, req.days_per_week)
        sc_template_guidance = {
            "sport": req.sport,
            "matching_templates": matches,
            "seeded_template": (
                {"global_id": seed_template["global_id"], "name": seed_template["name"]}
                if seed_template else None
            ),
            "browse_endpoint": "/api/v1/sc-templates/{global_id}",
        }

    # AI-hooks pass follow-up (docs/ROADMAP.md's own "not done in this pass"
    # note): the program-level equivalent of generate_session's ai_insight -
    # built from summary fields already computed above (split, periodization
    # model, muscle-frequency coverage), not from re-walking every week/day.
    # get_insight_provider() already returns NullInsightProvider unless both
    # AI_FEATURES_ENABLED and a real ANTHROPIC_API_KEY are set, so this is a
    # byte-for-byte no-op for every deployment that hasn't opted in - same
    # contract as the session-level hook.
    program_insight = get_insight_provider().annotate_program(ProgramContext(
        primary_goal=req.primary_goal,
        sport=req.sport,
        experience_level=req.experience_level,
        weeks=req.weeks,
        days_per_week=req.days_per_week,
        split_name=template["name"],
        periodization_model=periodization_model,
        training_phase=req.training_phase,
        personalization_applied=personalization_applied,
        under_trained_muscles=under_trained_muscles or [],
    ))

    response = {
        "status": "success",
        "engine": "FORGE Program Builder v1.1",
        "personalization_applied": personalization_applied,
        "primary_goal": req.primary_goal,
        "sport": req.sport,
        "experience_level": req.experience_level,
        "level_check": level_check_result,
        "conditioning_emphasis": req.conditioning_emphasis,
        "training_phase": training_phase_block,
        "conditioning_guidance": conditioning_guidance,
        "grappling_guidance": grappling_guidance,
        "sc_template_guidance": sc_template_guidance,
        "periodization_model": periodization_model,
        "periodization_rationale": periodization_rationale,
        "split": {
            "id": split_id,
            "name": template["name"],
            "description": template["description"],
            "recommended_for_sport": sport_recommended,
            "sport_rationale": sport_rationale,
            "experience_capped": experience_capped,
            "experience_rationale": experience_rationale,
        },
        "days_per_week": req.days_per_week,
        "weeks": req.weeks,
        "deload_week": deload_week,
        # Pass this straight back in as the NEXT program request's
        # continue_from_week to keep progressive overload climbing across
        # cycles instead of resetting to baseline - see
        # ProgramRequest.continue_from_week / _apply_week_progression.
        "next_cycle_start_week": (req.continue_from_week or 1) + req.weeks,
        "muscle_frequency_summary": muscle_frequency_summary,
        "under_trained_muscles": under_trained_muscles or None,
        "weekly_volume_summary": weekly_volume_summary,
        "under_dosed_muscles": under_dosed_muscles or None,
        "over_dosed_muscles": over_dosed_muscles or None,
        "program": weeks_output,
    }
    # Deterministic program-level "pro coach" read - see coach_notes.py's
    # module docstring for why this exists alongside (not instead of)
    # program_insight below: no API key needed, always present.
    response["coach_notes"] = build_program_coach_notes(
        sport=req.sport,
        primary_goal=req.primary_goal,
        weeks=req.weeks,
        days_per_week=req.days_per_week,
        split_name=template["name"],
        periodization_model=periodization_model,
        experience_level=req.experience_level,
        under_trained_muscles=under_trained_muscles or [],
    )
    if program_insight:
        response["ai_insight"] = program_insight
    return response


# ==========================================
# TEMPLATE FIDELITY BUILDER
# ==========================================
#
# generate_program()/_seed_days_by_label() above treat a FORGE S&C Template
# as a soft SEED: the live engine still picks and safety-gates every
# exercise itself, and a template's own pick is only nudged ahead of an
# equally-safe alternative (see progression_engine.template_seed_multiplier's
# docstring for the full "why" - this preserves the distinction from the
# old removed-for-good static "Manual" mode).
#
# build_template_fidelity_program() below is the deliberate exception to
# that rule, scoped narrowly: run the coach-authored template AS WRITTEN -
# same exercises, same order, same sets/reps/rest/tempo - and only hand a
# single exercise slot to the live engine when the template's own pick
# fails this specific athlete's equipment or injury check right now. Every
# other exercise in the template passes through untouched. This still
# isn't the old static Manual mode: nothing here ever serves an exercise
# the athlete can't safely do, and every exclusion/substitution is decided
# by the exact same equipment/injury logic generate_session already uses -
# it just runs template-first instead of engine-first for the ones that
# were already safe to begin with.
#
# WHY THE INJURY RESOLVERS ARE DUPLICATED HERE
# ProgressionEngine._resolve_injury_severity/_tissue/_stage/_side
# (progression_engine.py) do exactly this same {joint: ...} resolution,
# but progression_engine.py imports FROM this module (program_builder.py)
# at module level - importing ProgressionEngine back into program_builder.py
# would be a circular import. These four resolvers are pure functions of
# (user_injuries, injury_stages/injury_sides) over INJURY_TAXONOMY/
# REHAB_STAGES/INJURY_SIDES alone (no engine instance state), so they're
# safely duplicated here rather than restructured - any future change to
# the resolution rule has to be made in both places, same as any other
# intentionally-duplicated pure function in this codebase.

def _template_injury_severity(user_injuries: set) -> Dict[str, int]:
    taxonomy_lower = {name.lower(): info for name, info in INJURY_TAXONOMY.items()}
    joint_severity: Dict[str, int] = {}
    for inj in user_injuries:
        entry = taxonomy_lower.get(inj)
        if entry is None:
            continue
        joint = entry["joint"]
        joint_severity[joint] = max(joint_severity.get(joint, 0), entry["severity"])
    return joint_severity


def _template_injury_tissue(user_injuries: set) -> Dict[str, str]:
    taxonomy_lower = {name.lower(): info for name, info in INJURY_TAXONOMY.items()}
    joint_severity: Dict[str, int] = {}
    joint_tissue: Dict[str, str] = {}
    for inj in user_injuries:
        entry = taxonomy_lower.get(inj)
        if entry is None:
            continue
        joint, severity = entry["joint"], entry["severity"]
        if severity >= joint_severity.get(joint, 0):
            joint_severity[joint] = severity
            joint_tissue[joint] = entry.get("tissue")
    return joint_tissue


def _template_injury_stage(user_injuries: set, injury_stages: Optional[Dict[str, str]]) -> Dict[str, str]:
    if not injury_stages:
        return {}
    stage_by_injury = {k.strip().lower(): v for k, v in injury_stages.items()}
    taxonomy_lower = {name.lower(): info for name, info in INJURY_TAXONOMY.items()}
    joint_severity: Dict[str, int] = {}
    joint_stage: Dict[str, str] = {}
    for inj in user_injuries:
        entry = taxonomy_lower.get(inj)
        if entry is None:
            continue
        stage = stage_by_injury.get(inj)
        if stage not in REHAB_STAGES:
            continue
        joint, severity = entry["joint"], entry["severity"]
        if severity >= joint_severity.get(joint, 0):
            joint_severity[joint] = severity
            joint_stage[joint] = stage
    return joint_stage


def _template_injury_side(user_injuries: set, injury_sides: Optional[Dict[str, str]]) -> Dict[str, str]:
    if not injury_sides:
        return {}
    side_by_injury = {k.strip().lower(): v.strip().lower() for k, v in injury_sides.items()}
    taxonomy_lower = {name.lower(): info for name, info in INJURY_TAXONOMY.items()}
    joint_side: Dict[str, str] = {}
    for inj in user_injuries:
        entry = taxonomy_lower.get(inj)
        if entry is None:
            continue
        side = side_by_injury.get(inj)
        if side not in INJURY_SIDES or not laterality_applicable(entry):
            continue
        joint = entry["joint"]
        if joint not in joint_side:
            joint_side[joint] = side
        elif joint_side[joint] != side:
            joint_side[joint] = "bilateral"
    return joint_side


_SETS_REPS_RE = re.compile(r"(\d+)(?:\s*-\s*(\d+))?\s*sets?\s*x\s*(\d+)(?:\s*-\s*(\d+))?\s*(?:reps?|s\b)", re.IGNORECASE)
_REST_SECONDS_RE = re.compile(r"(\d+)\s*s\b", re.IGNORECASE)
# Matches the "@ 65-75% e1RM" / "@ 70% 1RM" style intensity coaches write
# into a template's free-text prescription (~43% of the 1,730 templates'
# exercise slots carry one - the rest are RPE-only, bodyweight, or a
# conditioning protocol, which correctly get no weight recommendation).
_LOAD_PCT_RE = re.compile(r"@\s*(\d+)(?:\s*-\s*(\d+))?\s*%\s*e?1rm", re.IGNORECASE)


def _parse_template_prescription(ex_entry: Dict) -> Dict:
    """Best-effort structured {sets, reps, rest_seconds, notes} pulled out
    of a FORGE S&C Template exercise's free-text `prescription`/`intensity`/
    `rest` fields (e.g. "4-5 sets x 4-8 reps @ 75-85% e1RM, RPE 7-8" / "150s")
    so a template-fidelity exercise can use the exact same editable
    prescription widget (renderPrescriptionEditable, exercise-editing.js)
    the engine's own program output uses - same look, same set/rep/rest/
    weight inputs, same "Log Set" flow - instead of a separate read-only
    text blob. The original free-text is kept in full in `notes` (the %1RM/
    RPE context the coach wrote isn't itself editable, but it's not lost
    either), and the upper end of any "X-Y" range is used as the starting
    editable default, since that's the harder/later end of the range.

    WEIGHT RECOMMENDER
    When the text also carries a "@ NN-NN% e1RM" intensity, this now pulls
    that percentage out into `load_pct_1rm` and switches `type` to
    "strength" instead of "custom" - the exact shape add_working_weight
    (load_prescription.py) already knows how to turn into a real
    working_weight_kg off the athlete's own tested maxes, and the exact
    shape renderPrescriptionEditable already renders as an editable weight
    box with an "X% 1RM ref" pill instead of a bare "your own pick" input
    starting at 0. build_template_fidelity_program calls add_working_weight
    on this result once it has the resolved exercise's category/equipment
    in hand (see its own docstring) - this function only extracts the
    percentage; it doesn't have that exercise data itself. A slot with no
    %1RM in its text (RPE-only, bodyweight, conditioning) is left exactly
    as before - "custom", no weight recommendation, since none applies."""
    text = ex_entry.get("prescription") or ""
    rest_text = ex_entry.get("rest") or ""
    sets, reps = 3, 8
    m = _SETS_REPS_RE.search(text)
    if m:
        s_lo, s_hi, r_lo, r_hi = m.groups()
        sets = int(s_hi or s_lo)
        reps = int(r_hi or r_lo)
    rest_seconds = 90
    rm = _REST_SECONDS_RE.search(rest_text)
    if rm:
        rest_seconds = int(rm.group(1))
    notes = " · ".join(p for p in (text, ex_entry.get("notes")) if p)
    result = {"type": "custom", "sets": sets, "reps": reps, "rest_seconds": rest_seconds, "notes": notes}
    pm = _LOAD_PCT_RE.search(text)
    if pm:
        p_lo, p_hi = pm.groups()
        result["type"] = "strength"
        result["load_pct_1rm"] = int(p_hi or p_lo)
    return result


def _db_display_fields(data: Dict) -> Dict:
    """id/category/equipment/experience_level/difficulty pulled off a
    resolved exercises.json entry - added onto a template-fidelity
    exercise so it can render through the exact same card/pill/swap
    machinery a normal engine-generated exercise does (see
    build_template_fidelity_program's docstring)."""
    return {
        "id": data.get("id"),
        "category": data.get("category"),
        "equipment": data.get("equipment"),
        "experience_level": data.get("experience_level"),
        "difficulty": data.get("difficulty"),
    }


def _template_exercise_block_reason(
    data: Dict,
    user_equipment: set,
    user_injuries: set,
    injury_joint_severity: Dict[str, int],
    injury_joint_tissue: Dict[str, str],
    injury_joint_stage: Dict[str, str],
    injury_joint_side: Dict[str, str],
    systemic_severity: Optional[int],
    systemic_stage: Optional[str],
) -> Optional[str]:
    """None if `data` (a resolved exercises.json entry) is safe and
    equipped-for as-is; otherwise a short reason it isn't - same
    equipment-check / four-tier injury-risk-check / systemic-injury-check
    generate_session's own `qualifies`/`is_safe` gate runs, just returning
    a reason string instead of silently dropping the candidate, since here
    the caller needs to know WHY a swap is being made."""
    eq = data.get("equipment", "Bodyweight")
    if user_equipment and eq.lower() != "bodyweight" and eq.lower() not in user_equipment:
        return f"Equipment not available ({eq})"

    joint_stress_raw = data.get("joint_stress", [])
    joint_stress = {j.lower() for j in joint_stress_raw}
    injuries_to_avoid = {i.lower() for i in data.get("injuries_to_avoid", [])}
    if user_injuries & (joint_stress | injuries_to_avoid):
        return "Contraindicated for a listed injury"

    difficulty = data.get("difficulty", 1)
    for joint_name in joint_stress_raw:
        severity = injury_joint_severity.get(joint_name)
        if severity is None:
            continue
        tier = classify_injury_risk(
            severity, difficulty,
            tissue=injury_joint_tissue.get(joint_name), exercise=data,
            stage=injury_joint_stage.get(joint_name), side=injury_joint_side.get(joint_name),
        )
        if tier in ("high_risk", "contraindicated"):
            return f"{joint_name} injury risk too high at this difficulty"

    if systemic_severity is not None:
        systemic_tier = classify_injury_risk(systemic_severity, difficulty, stage=systemic_stage)
        if systemic_tier in ("high_risk", "contraindicated"):
            return "Systemic injury restriction"

    return None


def build_template_fidelity_program(
    engine,
    global_id: str,
    equipment_available: List[str],
    injuries: List[str],
    injury_stages: Optional[Dict[str, str]] = None,
    injury_sides: Optional[Dict[str, str]] = None,
    biometrics=None,
) -> Optional[Dict]:
    """Run one FORGE S&C Template (see sc_template_library.py) AS WRITTEN -
    same exercises, same order, same prescription - swapping out only the
    individual exercise slots that fail THIS athlete's equipment or injury
    check right now. See this section's module comment above for why this
    is a deliberate, narrowly-scoped exception to the "templates are only
    ever a soft seed" rule the rest of program_builder.py follows.

    Returns None if `global_id` doesn't resolve to a real template (caller
    turns that into a 404, same as get_template's own None contract).
    Raises SevereInjuryBlockedError up front - before touching any
    exercise - for the same severity-3 injuries that block
    generate_session/generate_program entirely; a template run is not a
    lower-safety path than either of those.

    Each output exercise carries `template_source` (True if this is the
    template's own untouched pick), and either nothing else (kept as-is),
    or `substituted_for`/`substitution_reason` (the engine found a safe
    swap) or `excluded`/`exclusion_reason` (nothing in the database cleared
    this athlete's checks for that slot, so it's flagged rather than
    silently prescribed or silently dropped). A template exercise name
    that doesn't resolve to anything in exercises.json can't be equipment/
    injury-checked at all - it's passed through unchanged with
    `verified: False`, the same "don't force a bad pairing on data we
    can't read" posture `_seed_days_by_label` takes for an unresolvable
    seed name.

    WEIGHT RECOMMENDER
    `biometrics` (optional - a UserBiometrics instance, same as every other
    generate-* endpoint) is threaded down to add_working_weight for every
    slot _parse_template_prescription flagged with a %1RM (see that
    function's docstring), using the resolved/substituted exercise's own
    category/equipment/strength_requirements/movement_type the exact same
    way generate_program's own week-progression pipeline does. Omitting
    biometrics (or an exercise whose category has no anchor lift on file)
    leaves the %1RM visible with no working_weight_kg - the same
    "prove it first" fallback add_working_weight already uses everywhere
    else, never a guessed number.
    """
    template = get_template(global_id)
    if template is None:
        return None

    user_equipment = {e.strip().lower() for e in equipment_available if e and e.strip()}
    user_injuries = {i.strip().lower() for i in injuries if i and i.strip()}

    # Same whole-program severe-injury gate generate_session runs before
    # any exercise selection - a template run isn't exempt from it.
    severe_injuries = resolve_severe_injuries(user_injuries)
    if severe_injuries:
        names = ", ".join(i["name"] for i in severe_injuries)
        raise SevereInjuryBlockedError(
            f"No workout can be built from this template: {names} "
            f"{'is' if len(severe_injuries) == 1 else 'are'} classified as a "
            "severe (grade/structural) injury. This requires evaluation and "
            "clearance from an orthopedic physician or physical therapist "
            "before any exercise program - including a template run as-is - "
            "should be treated as safe to follow.",
            details={"blocked_injuries": severe_injuries},
        )

    injury_joint_severity = _template_injury_severity(user_injuries)
    injury_joint_tissue = _template_injury_tissue(user_injuries)
    injury_joint_stage = _template_injury_stage(user_injuries, injury_stages)
    injury_joint_side = _template_injury_side(user_injuries, injury_sides)
    systemic_severity, systemic_stage = resolve_systemic_injury(user_injuries, injury_stages)

    # conditioning_engine.prescribe_conditioning scales by the wizard's own
    # five-tier Beginner..Elite vocabulary, but a Special Forces template's
    # `level` is that library's own domain spelling (e.g. "Elite / Tier 1" -
    # see SPECIAL_FORCES_LEVEL_ALIASES). Invert that alias map once here so
    # every conditioning-protocol slot in this template gets scaled off the
    # athlete's real experience tier instead of silently falling back to
    # resolve_conditioning_exercise's Intermediate default for every
    # Special Forces template run - the inverse conditioning_engine's own
    # module docstring says a caller should apply before calling in.
    _sf_level_inverse = {v: k for k, v in SPECIAL_FORCES_LEVEL_ALIASES.items()}
    conditioning_experience_level = (
        _sf_level_inverse.get(template.get("level"), template.get("level"))
        or "Intermediate"
    )

    # Same normalize_exercise_name resolution _seed_days_by_label uses to
    # read a template exercise's own category/joint_stress/equipment back
    # out of the live database.
    name_to_data: Dict[str, Dict] = {}
    for ex in engine.exercises_by_id.values():
        name_to_data.setdefault(normalize_exercise_name(ex.get("name", "")), ex)

    out_days = []
    substitutions_made = 0
    exercises_excluded = 0
    for day in template.get("days", []):
        out_exercises = []
        for ex_entry in day.get("exercises", []):
            name = ex_entry.get("name", "")
            resolved = name_to_data.get(normalize_exercise_name(name))
            if resolved is None:
                # Exact normalized match failed - try the equipment-word-only
                # fuzzy fallback (see fuzzy_resolve_exercise_name's docstring)
                # before giving up, so a name like "Front Squat (Rack)" or
                # "Chest-Supported DB Row" still resolves to real exercise
                # data and gets a real equipment/injury check instead of
                # being passed through unchecked as Unverified.
                resolved = fuzzy_resolve_exercise_name(name, engine.exercises_by_id)

            if resolved is None:
                # Exact/fuzzy exercises.json resolution failed - before
                # giving up and passing this through completely unchecked,
                # check whether it's one of the 85 Category A conditioning
                # names (see forge_category_audit.md) conditioning_engine.py
                # knows how to gate and prescribe for. A protocol match
                # always comes back with its own verified/excluded/
                # prescription fields already set - either safely gated-
                # and-dosed for this athlete, or explicitly excluded with a
                # reason (conditioning protocols have no exercises.json
                # alternative to substitute in, so a failed gate here is
                # never silently dropped, same as a lift's own excluded
                # branch below).
                conditioning = resolve_conditioning_exercise(
                    name, user_equipment, injury_joint_severity, injury_joint_tissue,
                    injury_joint_stage, injury_joint_side, systemic_severity, systemic_stage,
                    experience_level=conditioning_experience_level, phase="build",
                )
                if conditioning is not None:
                    if conditioning.get("excluded"):
                        exercises_excluded += 1
                    out_exercises.append({**ex_entry, "template_source": True, **conditioning})
                    continue

                out_exercises.append({**ex_entry, "template_source": True, "verified": False,
                                       "prescription": _parse_template_prescription(ex_entry)})
                continue

            reason = _template_exercise_block_reason(
                resolved, user_equipment, user_injuries,
                injury_joint_severity, injury_joint_tissue, injury_joint_stage, injury_joint_side,
                systemic_severity, systemic_stage,
            )
            if reason is None:
                prescription = _parse_template_prescription(ex_entry)
                prescription = add_working_weight(
                    prescription, resolved.get("category"), biometrics,
                    equipment=resolved.get("equipment"),
                    strength_requirements=resolved.get("strength_requirements"),
                    movement_type=resolved.get("movement_type"),
                )
                out_exercises.append({
                    **ex_entry, "template_source": True, "verified": True,
                    **_db_display_fields(resolved),
                    "prescription": prescription,
                })
                continue

            alts = find_alternatives(
                resolved, engine.exercises_by_id, injury_joint_severity,
                max_results=1, user_equipment=user_equipment or None,
                injury_joint_tissue=injury_joint_tissue, injury_joint_stage=injury_joint_stage,
                user_injuries=user_injuries, injury_joint_side=injury_joint_side,
            )
            if alts:
                substitutions_made += 1
                sub = alts[0]
                prescription = _parse_template_prescription(ex_entry)
                prescription = add_working_weight(
                    prescription, sub.get("category"), biometrics,
                    equipment=sub.get("equipment"),
                    strength_requirements=sub.get("strength_requirements"),
                    movement_type=sub.get("movement_type"),
                )
                out_exercises.append({
                    **ex_entry,
                    "name": sub.get("name", sub["id"]),
                    "template_source": False,
                    "verified": True,
                    "substituted_for": name,
                    "substitution_reason": reason,
                    **_db_display_fields(sub),
                    "prescription": prescription,
                })
            else:
                exercises_excluded += 1
                out_exercises.append({
                    **ex_entry,
                    "template_source": True,
                    "verified": False,
                    "excluded": True,
                    "exclusion_reason": reason,
                })

        out_days.append({**day, "exercises": out_exercises})

    return {
        "status": "success",
        "engine": "FORGE Template Fidelity Builder v1.0",
        "global_id": template["global_id"],
        "id": template["id"],
        "library": template["library"],
        "name": template["name"],
        "sport": template["sport"],
        "level": template["level"],
        "goal": template["goal"],
        "days_per_week": template.get("days_per_week"),
        "duration_weeks": template.get("duration_weeks"),
        "equipment_required": template.get("equipment_required"),
        "substitutions_made": substitutions_made,
        "exercises_excluded": exercises_excluded,
        "days": out_days,
    }

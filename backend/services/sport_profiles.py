"""
sport_profiles.py — what "transfers" to each sport, encoded once per sport
rather than once per exercise.

WHY THIS EXISTS
Before this module, `sport_priority` in exercises.json was a single hand-typed
0-100 number per (exercise, sport) pair, authored directly in
generate_new_exercises.py with no stated reasoning attached — a Bulgarian Split
Squat scores 70 for Judo and nobody downstream can say *why*. That's the same
problem exercise_metadata.py solved for the movement-analysis and
athletic-quality fields: numbers that look precise but aren't checkable against
anything are worse than an engine that can explain itself.

This module encodes a strength coach's mental model of each sport ONCE — "what
physical qualities actually win in this sport" — as a weighted subset of the
same ATHLETIC_QUALITY_TAGS every exercise is already scored against
(exercise_metadata.ATHLETIC_QUALITY_TAGS). The engine then computes transfer
as a weighted overlap between an exercise's real, derived qualities and the
sport's profile, and can point at exactly which qualities drove the number.

The original hand-authored `sport_priority` isn't discarded — a coach's flat
judgment call ("this exercise just matters for this sport") still carries
real information the quality-tag overlap can't fully capture (e.g. a highly
sport-specific drill). `blended_transfer_score` below averages the two, so
the number is grounded in something checkable but doesn't lose whatever
judgment was already baked into the original data.

Reviewable and editable exactly like CATEGORY_PROFILES: change one sport's
row here and every exercise's transfer score for that sport updates
consistently, instead of hand-editing 175 individual numbers.
"""

from typing import Dict, List, Optional, Tuple

# One row per sport in exercises.json's sport_priority keys. Each maps a
# subset of ATHLETIC_QUALITY_TAGS to an importance weight (0-100). Qualities
# left out of a sport's profile simply don't contribute to that sport's
# transfer score - they're not "zero", they're "not part of the model" (a
# sport's profile is deliberately the ~6-10 qualities that actually
# distinguish it, not a full re-ranking of all 33 tags).
#
# NECK STRENGTH WEIGHTS: the manual gives neck training its own universal
# table (frequency + per-sport rationale) exactly parallel to how it treats
# grip - but before this pass, Grip Strength/Endurance was weighted into
# nearly every sport below while Neck Strength appeared in exactly one
# (Boxing, at 30), leaving Wrestling ("a bulletproof neck" - one of its own
# four stated Primary Physical Qualities), Sambo ("direct neck work is
# non-negotiable"), Judo and Rugby with zero neck transfer credit despite
# the manual training their necks 3x+/week for reasons it states explicitly.
# Weights below are tiered directly off the manual's own "Neck Training -
# How Often and Why" text per sport, so an exercise's neck-training value
# actually moves its transfer score for the sports the manual says it
# should:
#   55 Wrestling      - 3-4x/wk, "a bulletproof neck" is a named Primary Quality
#   50 Sambo           - 3x/wk, "direct neck work is non-negotiable"; a
#                        "resilient neck/spine" is also a named Primary Quality
#   45 Judo/Rugby/Boxing - 3x/wk, manual calls it an injury-risk factor either
#                        way (throws/osaekomi, scrums/tackles, concussion risk)
#   35 Muay Thai/Sanda - 2-3x/wk, absorbs clinch knees/elbows or strikes
#   30 Kickboxing      - 2x/wk, stabilizes the head through rotational strikes
#   25 BJJ/Special Forces - 2x/wk, and the manual itself downplays it here
#                        ("less direct neck-on-neck contact", "not the top
#                        priority")
#   (omitted) Rock Climbing - manual: "Not a primary demand of the sport -
#                        don't add fatigue that isn't needed" - so, per this
#                        module's own convention, it's left out of the model
#                        entirely rather than given a token weight.
SPORT_QUALITY_PROFILES: Dict[str, Dict[str, int]] = {
    "Wrestling": {
        "Relative Strength": 70, "Power": 65, "Explosiveness": 60,
        "Grip Strength": 70, "Grip Endurance": 65, "Hip Stability": 60,
        "Core Stability": 55, "Anaerobic Capacity": 60,
        "Reactive Strength": 50, "Change of Direction": 45, "Neck Strength": 55,
    },
    "Judo": {
        "Grip Strength": 75, "Grip Endurance": 60, "Rotational Power": 65,
        "Power": 60, "Hip Stability": 55, "Explosiveness": 55,
        "Core Stability": 50, "Anti Rotation": 45, "Reactive Strength": 45,
        "Neck Strength": 45,
    },
    "Sambo": {
        "Grip Strength": 65, "Grip Endurance": 55, "Power": 60,
        "Hip Stability": 55, "Rotational Power": 50, "Explosiveness": 50,
        "Core Stability": 50, "Anaerobic Capacity": 50, "Neck Strength": 50,
    },
    "BJJ": {
        "Grip Endurance": 70, "Grip Strength": 55, "Core Stability": 60,
        "Anti Rotation": 45, "Muscular Endurance": 55, "Hip Stability": 55,
        "Work Capacity": 50, "Anaerobic Capacity": 45, "Neck Strength": 25,
    },
    "Boxing": {
        "Rotational Power": 70, "Power": 60, "Explosiveness": 65,
        "Rate of Force Development": 55, "Core Stability": 50,
        "Anti Rotation": 45, "Anaerobic Capacity": 55,
        "Aerobic Capacity": 45, "Change of Direction": 40, "Neck Strength": 45,
    },
    "Muay Thai": {
        "Rotational Power": 65, "Power": 65, "Hip Stability": 55,
        "Explosiveness": 55, "Grip Strength": 40, "Anaerobic Capacity": 55,
        "Core Stability": 50, "Muscular Endurance": 45, "Neck Strength": 35,
    },
    "Kickboxing": {
        "Rotational Power": 60, "Explosiveness": 60, "Power": 55,
        "Change of Direction": 50, "Agility": 50, "Anaerobic Capacity": 55,
        "Core Stability": 45, "Neck Strength": 30,
    },
    "Sanda": {
        "Power": 65, "Explosiveness": 60, "Rotational Power": 55,
        "Hip Stability": 50, "Reactive Strength": 45,
        "Anaerobic Capacity": 50, "Core Stability": 45, "Neck Strength": 35,
    },
    "Rugby": {
        "Max Strength": 60, "Power": 65, "Deceleration": 55,
        "Acceleration": 55, "Work Capacity": 55, "Core Stability": 50,
        "Grip Strength": 45, "Anaerobic Capacity": 55, "Change of Direction": 45,
        "Neck Strength": 45,
    },
    "Rock Climbing": {
        "Grip Strength": 80, "Grip Endurance": 75, "Core Stability": 60,
        "Anti Rotation": 40, "Relative Strength": 55,
        "Anti Lateral Flexion": 35, "Muscular Endurance": 45,
        # No Neck Strength entry - manual explicitly says neck is "not a
        # primary demand of the sport" for climbing, maintenance-only 1x/wk.
    },
    "HYROX": {
        "Work Capacity": 75, "Aerobic Capacity": 65, "Anaerobic Capacity": 55,
        "Muscular Endurance": 60, "Grip Endurance": 50, "Conditioning": 65,
        "Core Stability": 40,
    },
    "Special Forces": {
        "Work Capacity": 60, "Max Strength": 50, "Relative Strength": 50,
        "Grip Strength": 50, "Grip Endurance": 50, "Core Stability": 50,
        "Aerobic Capacity": 50, "Anaerobic Capacity": 50, "Muscular Endurance": 55,
        "Neck Strength": 25,
    },
    # MMA blends the striking (Boxing/Muay Thai) and grappling (Wrestling/BJJ/Judo)
    # profiles rather than being its own thing - a fighter needs rotational power
    # for striking AND grip/pulling strength for the clinch and ground game, plus
    # the gas tank to do both across rounds. Weights below sit roughly at the
    # average of its component sports' rows, nudged so nothing gets zeroed out
    # the way a naive "pick one archetype" profile would.
    "MMA": {
        "Grip Strength": 60, "Grip Endurance": 55, "Rotational Power": 60,
        "Power": 60, "Explosiveness": 55, "Hip Stability": 55,
        "Core Stability": 55, "Anaerobic Capacity": 60, "Work Capacity": 50,
        "Change of Direction": 40, "Reactive Strength": 40, "Muscular Endurance": 45,
        # Blends its grappling (Wrestling/Judo/BJJ) and striking (Boxing/Muay
        # Thai) component sports' Neck Strength weights the same way every
        # other quality here is blended - roughly their average, nudged so
        # it isn't zeroed out.
        "Neck Strength": 40,
    },
    # Powerlifting and "Look Jacked" aren't in the Combat Sports & Rugby S&C
    # Manual this app is built from (see program_builder.py's note on why
    # Bro Split/PHUL/PHAT/Powerbuilding templates were removed) - there's no
    # aerobic:lactic ratio or manual-sourced split narrative to source for
    # them the way there is for a combat sport. What they DO have is a
    # clean, well-established quality profile from the strength literature,
    # so they're added here (transfer score only). sport_conditioning_profile()
    # already returns {} gracefully for sports outside the manual (same as
    # Rock Climbing/HYROX today).
    "Powerlifting": {
        "Max Strength": 90, "Relative Strength": 75, "Rate of Force Development": 55,
        "Power": 45, "Core Stability": 40, "Grip Strength": 35,
    },
    # "Look Jacked" = the bodybuilding/aesthetics goal (muscle size over a
    # 1RM number) - weighted almost entirely on each exercise's own derived
    # Hypertrophy score plus the volume-tolerance qualities that let someone
    # actually rack up the sets/reps that grow muscle.
    "Look Jacked": {
        "Hypertrophy": 90, "Muscular Endurance": 55, "Work Capacity": 40,
        "Relative Strength": 30,
    },
    # "Strength + Hypertrophy" = the third tier added alongside the two
    # above, from a PDF that prescribes 5-8 reps at 70-82% 1RM - a band that
    # sits deliberately between Powerlifting's low-rep/near-max work and
    # Look Jacked's higher-rep/moderate-load work. Same blending convention
    # as MMA above (roughly the average of its parent profiles, nudged so
    # nothing zeroes out): Max Strength/Rate of Force Development pulled
    # from Powerlifting, Hypertrophy pulled from Look Jacked, everything
    # else averaged.
    "Strength + Hypertrophy": {
        "Max Strength": 65, "Hypertrophy": 65, "Relative Strength": 50,
        "Rate of Force Development": 35, "Power": 45, "Muscular Endurance": 45,
        "Work Capacity": 35, "Core Stability": 30, "Grip Strength": 25,
    },
}

# Below this per-quality contribution, a quality isn't worth naming in a
# "why this exercise, for this sport" explanation - it's noise, not signal.
_EXPLAIN_FLOOR = 30


def quality_overlap_score(athletic_qualities: Dict[str, int], sport: str) -> float:
    """Weighted average of an exercise's athletic-quality scores against a
    sport's profile weights. 0-100, same scale as the input scores, because
    it's a weighted *average* (not sum) of numbers already on that scale."""
    profile = SPORT_QUALITY_PROFILES.get(sport)
    if not profile or not athletic_qualities:
        return 0.0
    total_weight = sum(profile.values())
    if total_weight == 0:
        return 0.0
    weighted_sum = sum(
        weight * athletic_qualities.get(quality, 0) for quality, weight in profile.items()
    )
    return weighted_sum / total_weight


def top_contributing_qualities(
    athletic_qualities: Dict[str, int], sport: str, limit: int = 3
) -> List[Tuple[str, int]]:
    """The qualities actually driving this exercise's transfer score for this
    sport, ranked by (sport's weight on that quality) x (exercise's score on
    it) - i.e. what a coach would point at if asked to justify the number."""
    profile = SPORT_QUALITY_PROFILES.get(sport)
    if not profile or not athletic_qualities:
        return []
    scored = [
        (quality, athletic_qualities.get(quality, 0))
        for quality in profile
        if athletic_qualities.get(quality, 0) >= _EXPLAIN_FLOOR
    ]
    scored.sort(key=lambda pair: profile[pair[0]] * pair[1], reverse=True)
    return scored[:limit]


def top_sport_qualities(sport: str, limit: int = 3) -> List[str]:
    """The `limit` highest-weighted entries in this sport's own
    SPORT_QUALITY_PROFILES row - i.e. "what actually matters most for this
    sport", independent of any single exercise. Used to generate split/
    program-level rationale text (e.g. `program_builder.recommend_split`'s
    day-count fallback) directly from the sport's profile instead of a
    second hand-authored sentence per sport that can drift out of sync with
    the weights above. Empty list for a sport with no profile row."""
    profile = SPORT_QUALITY_PROFILES.get(sport)
    if not profile:
        return []
    return [q for q, _ in sorted(profile.items(), key=lambda kv: -kv[1])[:limit]]


def blended_transfer_score(data: Dict, sport: str) -> int:
    """The number the engine actually ranks/sorts on: half the original
    hand-authored sport_priority (real coach judgment, kept), half the
    quality-overlap score (checkable against the exercise's own derived
    profile). If a sport has no quality profile or the exercise has no
    quality tags yet, falls back to whichever of the two is available."""
    authored = data.get("sport_priority", {}).get(sport)
    qualities = data.get("athletic_qualities", {})
    overlap = quality_overlap_score(qualities, sport) if qualities else None

    if authored is not None and overlap is not None:
        return round(0.5 * authored + 0.5 * overlap)
    if authored is not None:
        return round(authored)
    if overlap is not None:
        return round(overlap)
    return 0


SPORT_MOVEMENT_EMPHASIS: Dict[str, Dict[str, float]] = {
    # NOTE on "Rotational"/"Rotation": these are movement_pattern values, and
    # only 5 of 442 exercises in exercises.json carry either one (the rest of
    # the database's genuinely rotational work - shadow boxing, heavy bag
    # combinations, clinch knees, throws - is tagged with the movement_pattern
    # values "Strike" and "Throw" instead, under category "Sport Specific").
    # Keying only on "Rotational"/"Rotation" meant this boost almost never
    # fired for the sports it exists for. "Strike" and "Throw" are added below
    # for every sport where striking or throwing actually transfers, so the
    # boost reaches the exercises real coaches would call rotational-power
    # work for these sports.
    "Boxing": {
        "Horizontal Push": 1.25, "Vertical Push": 1.15, "Rotational": 1.3,
        "Rotation": 1.3, "Strike": 1.3, "Power": 1.15,
        "Horizontal Pull": 0.85, "Squat": 0.9,
    },
    "Muay Thai": {
        "Horizontal Push": 1.15, "Vertical Push": 1.1, "Rotational": 1.25,
        "Rotation": 1.25, "Strike": 1.25, "Hinge": 1.15,
        "Horizontal Pull": 0.9,
    },
    "Kickboxing": {
        "Rotational": 1.25, "Rotation": 1.25, "Strike": 1.25,
        "Horizontal Push": 1.1, "Hinge": 1.1, "Horizontal Pull": 0.9,
    },
    "Sanda": {
        "Rotational": 1.2, "Rotation": 1.2, "Strike": 1.2, "Throw": 1.15,
        "Horizontal Push": 1.15, "Hinge": 1.1, "Horizontal Pull": 0.9,
    },
    # Grappling sports (Judo/Wrestling/Sambo/BJJ below): pulling genuinely IS
    # primary here - grip fighting, throws, and takedowns are pulling-
    # dominant, which is why Pull categories/Grip/Throw all sit well above
    # 1.0. But these tables previously also pushed Vertical/Horizontal Push
    # BELOW 1.0 (0.85-0.9), which stacks on top of push exercises already
    # scoring lower on quality-overlap (grappling's SPORT_QUALITY_PROFILES
    # rows don't weight Shoulder Stability at all, which is where Vertical
    # Push exercises score highest) - the combined effect was pushing
    # movements getting crowded out of programs almost entirely. That's not
    # what a real S&C coach does for these sports: pushing strength is still
    # trained on purpose - Horizontal Push underpins pummeling/hand-fighting
    # and base in the tie-up, and BJJ specifically leans on pushing strength
    # for framing and guard-passing (posting a hand/forearm and driving an
    # opponent off you is a horizontal-push pattern). So push stays
    # secondary to pulling (no boost above 1.0 in Judo, where gripping/
    # throwing dominates even more than the other three) but is no longer
    # actively suppressed below neutral the way pulling is boosted above it.
    "Judo": {
        "Horizontal Pull": 1.35, "Vertical Pull": 1.3, "Grip": 1.3,
        "Throw": 1.35, "Hinge": 1.15, "Horizontal Push": 1.0,
        "Vertical Push": 0.95,
    },
    "Wrestling": {
        "Horizontal Pull": 1.25, "Vertical Pull": 1.2, "Hinge": 1.2,
        "Squat": 1.15, "Grip": 1.2, "Throw": 1.25,
        "Horizontal Push": 1.05, "Vertical Push": 1.0,
    },
    "Sambo": {
        "Horizontal Pull": 1.25, "Vertical Pull": 1.2, "Hinge": 1.15,
        "Grip": 1.2, "Throw": 1.25,
        "Horizontal Push": 1.05, "Vertical Push": 1.0,
    },
    "BJJ": {
        "Horizontal Pull": 1.3, "Vertical Pull": 1.25, "Grip": 1.25,
        "Core": 1.15, "Throw": 1.1, "Squat": 0.9,
        "Horizontal Push": 1.05, "Vertical Push": 1.0,
    },
    "Rock Climbing": {
        "Vertical Pull": 1.4, "Horizontal Pull": 1.2, "Grip": 1.35,
        "Core": 1.15, "Horizontal Push": 0.8, "Squat": 0.85,
    },
    "Rugby": {
        "Hinge": 1.25, "Squat": 1.2, "Horizontal Push": 1.1,
        "Horizontal Pull": 1.1, "Carry": 1.15, "Throw": 1.1,
    },
    "HYROX": {
        "Carry": 1.3, "Hinge": 1.15, "Squat": 1.1, "Conditioning": 1.2,
    },
    "Special Forces": {
        "Carry": 1.2, "Hinge": 1.15, "Squat": 1.1, "Vertical Pull": 1.1,
    },
    # Unlike a pure striking or pure grappling sport, MMA doesn't want any
    # movement pattern de-emphasized below 1.0 - a fighter who neglects pulling
    # for pressing (or vice versa) has an exploitable hole in the clinch or on
    # the feet. Everything gets a modest, roughly even bump instead of the
    # sharp push-vs-pull skew a single-discipline sport's table has.
    "MMA": {
        "Horizontal Push": 1.15, "Vertical Push": 1.1, "Rotational": 1.2,
        "Rotation": 1.2, "Strike": 1.2, "Throw": 1.15,
        "Horizontal Pull": 1.15, "Vertical Pull": 1.15,
        "Grip": 1.15, "Hinge": 1.1, "Squat": 1.05,
    },
    # The three competition lifts and their close variants live under
    # Squat/Hinge/Horizontal Push - everything else (Power/Jump/Conditioning/
    # Sport Specific) is accessory work a powerlifting program still uses,
    # just not the priority, so it's left at neutral (1.0) rather than
    # suppressed the way a single-discipline combat sport's off-pattern work is.
    "Powerlifting": {
        "Squat": 1.4, "Hinge": 1.35, "Horizontal Push": 1.3,
        "Vertical Push": 1.05, "Horizontal Pull": 1.05, "Vertical Pull": 1.0,
    },
    # Bodybuilding trains every pattern on purpose (nothing is a "weak link"
    # you can skip) - a small even bump across every pressing/pulling
    # pattern reflects "everything gets trained hard," not a push/pull skew.
    "Look Jacked": {
        "Horizontal Push": 1.1, "Vertical Push": 1.1,
        "Horizontal Pull": 1.1, "Vertical Pull": 1.1,
        "Squat": 1.05, "Hinge": 1.05,
    },
}


# Equipment/movement priority — independent of sport, applied to every
# session by default. Encodes the manual's own stated hierarchy (Part 3:
# "Compound lifts first, always... Squat, hinge, press, pull, carry patterns
# give you the most strength and durability per minute"; Part 4 rep-range
# key: "Olympic lifts must be performed first in the session while fresh")
# plus the equipment ordering every template in Part 4 actually follows -
# barbell main lift, then barbell/kettlebell accessory work, then
# core/carry/grip finishers. This is a ranking bias, not a filter: it
# nudges which exercises win ties (and near-ties) inside a role/pattern
# slot in main.py's selection pass, it never overrides the safety/equipment/
# injury/strength gating that already decided an exercise is allowed.
_COMPOUND_CATEGORIES = {
    "Squat", "Hinge", "Full Body",
    "Horizontal Push", "Vertical Push", "Horizontal Pull", "Vertical Pull",
}

# TOP-TIER STRENGTH IMPLEMENTS (reported request: Barbell should rank
# level with - never below - the dedicated low-injury-risk implements,
# since a straight barbell takes more absolute load than any of them and
# is still the #1 tool for building raw strength; the low-risk implements
# are what a coach reaches for alongside it, not above it). Each of the
# non-Barbell members here is a real, widely-used substitute for the
# straight-barbell version of its pattern, specifically because it removes
# (not just reduces) the exact loading that makes the straight-bar version
# riskier for a given joint/segment:
#   - Belt Squat / Belt Squat Machine: the load hangs from a belt at the
#     hips, not across the back - genuinely ZERO axial spinal loading,
#     the lowest-back-risk way to load a squat pattern that exists.
#   - Seal Row Bench: torso braced flat and fully supported, prone - no
#     bent-over hip-hinge position at all, so it removes the lower-back
#     shear/momentum a standard bent-over barbell row asks the lifter to
#     control under fatigue.
#   - Reverse Hyper: posterior-chain/lower-back work through a
#     freely-swinging, unloaded-spine range of motion - decompressive
#     rather than compressive, unlike a barbell good-morning/hyperextension.
#   - Safety Squat Bar: the yoke/handles shift the load forward and remove
#     the need for the overhead shoulder external rotation a straight bar
#     back-squat position demands - meaningfully lower shoulder/wrist/
#     elbow strain for the same squat pattern.
#   - Landmine: the pivoting bar end arcs rather than tracking a straight
#     bar path, taking direct spinal/shoulder loading out of press and
#     rotational patterns while still allowing heavy load.
#   - Trap Bar: the load sits lateral to the body (not in front of it), so
#     a Trap Bar Deadlift keeps the load closer to the body's center of
#     mass and needs meaningfully less lumbar flexion/shear than a
#     straight-bar conventional deadlift to reach the same weight.
# All tied with Barbell at the top tier - among equally sport-appropriate
# candidates these are genuinely preferred, but none outranks a barbell
# lift just for being "lower risk", and a straight barbell still wins
# whenever none of these alternates is available (the normal, much more
# common case).
_LOW_RISK_EQUIPMENT = {
    "Trap Bar", "Safety Squat Bar", "Belt Squat", "Belt Squat Machine",
    "Seal Row Bench", "Reverse Hyper", "Landmine",
}
_TOP_TIER_EQUIPMENT = _LOW_RISK_EQUIPMENT | {"Barbell"}

# Second tier for strength work: Dumbbell/Kettlebell/Weighted Vest.
# Genuinely useful and still prioritized ahead of Rings/generic accessory
# work, but a notch below the Barbell/low-risk-implement group above -
# these cap out at a lower absolute load than a barbell or dedicated
# machine can, so they're the "next best thing", not co-equal with the
# top tier, for a strength-focused session. Weighted Vest belongs here
# (reported request: a Weighted Vest Dip/Push-Up/Pull-Up was only getting
# the generic compound-category bump (1.15, same as an unweighted
# bodyweight dip), because equipment_movement_priority_multiplier had no
# tier for it at all - it was never checked as "loadable", just fell
# through to the category branch below like any plain bodyweight
# exercise. That's wrong: a weighted vest lets you strap on real, heavy
# external load exactly like a dumbbell or kettlebell can, so it should
# outrank a same-pattern bodyweight-only exercise the same way DB/KB
# already does, not just tie with it on category alone.
_SECOND_TIER_EQUIPMENT = {"Dumbbell", "Kettlebell", "Weighted Vest"}

# Equipment/movement priority beginner-power exception (reported request):
# a true beginner's power work should be built around Dumbbell/Kettlebell
# ballistic patterns (dumbbell snatch/clean variations, kettlebell swings/
# cleans) rather than barbell Olympic lifts - the technical demand of a
# full barbell snatch/clean is a poor fit for someone this early, while the
# dumbbell/kettlebell versions teach the same hip-drive/triple-extension
# pattern with far less coaching overhead. Only the two lowest experience
# ranks (Beginner, Novice) get this swap; Intermediate and up are assumed
# ready for actual barbell Olympic-lift work instead (which already lands
# in the top tier via the Barbell equipment check).
_BEGINNER_POWER_RANKS = {"Beginner", "Novice"}

# Rings (ring push-up/dip/row/muscle-up work etc.) - checked BEFORE the
# generic _COMPOUND_CATEGORIES branch below, same "equipment before
# category" rule the rest of this function already follows for Barbell.
# Deliberately the lowest explicit tier of any named equipment: rings are
# a calisthenics-specialist's tool (bodyweight-only loading, no way to add
# external load the way a barbell/dumbbell/kettlebell can), so a
# general-purpose default session shouldn't reach for them ahead of any
# loadable implement. They're still a fine, safe accessory option - just
# not one the default ranking should favor over any loadable implement.
_RING_EQUIPMENT = {"Rings"}


# Named technique/limited-ROM/specialty-bar variations of a bigger lift
# (reported bug: "Larsen Press" - a barbell bench variation done with legs
# up on the bench to remove leg drive - was surfacing in rotation as often
# as Flat Bench Press itself, because it shares Barbell equipment with the
# plain lift, so it ties on equipment_movement_priority_multiplier's top
# tier, AND its authored sport_priority/quality numbers are nearly
# identical to the plain lift's - nothing in the scoring distinguished
# "the lift" from "a specialist's technique variation of the lift"). A
# real coach defaults a general session to the plain, simple version of a
# pattern (Flat Bench Press, Incline Bench Press, Barbell Overhead Press,
# Push Press, Pin Press, Landmine Press) and only reaches for a named
# variation (limited ROM, accommodating resistance, a specialty bar, an
# altered grip) when there's a specific reason to - it's an accessory
# choice, not a default one. This is a discount (0.75x), not an
# exclusion - these stay fully selectable (e.g. via Swap or in
# custom_progressions) and can still win when nothing else clears the
# bar, they just stop tying with/beating the plain lift in normal
# rotation. Pin Bench Press and Pin Press (Overhead) themselves are
# deliberately NOT in this set - a plain pin press is exactly the kind of
# simple, default-appropriate lift this list is trying to protect;
# Pin Bench Press (Mid-Range), Bottom-Up Pin Bench, Deficit Pin Press, and
# Squat Rack Pin Press ARE included - those are the more specialized
# range/position variations of the same tool, not the base version.
_PRESS_VARIATION_DISCOUNT_IDS = frozenset({
    # Bench-press family: technique/ROM/accommodating-resistance/specialty-bar variations
    "larsen_press_001", "spoto_press_001", "squatrack_spotopress_001",
    "slingshot_bench_001", "chain_bench_001", "band_bench_001", "speed_bench_001",
    "reversegrip_bench_001", "closegrip_bench_001", "widegrip_bench_001",
    "board_press_001", "guillotine_press_001",
    "swissbar_bench_001", "footballbar_bench_001", "swissbar_closegripbench_001",
    "buffalobar_bench_001", "camberedbar_bench_001", "ezbar_closegripbench_001",
    "smith_bench_001", "smith_inclinepress_001",
    "pin_bench_mid_001", "bottom_up_pin_bench_001", "deficit_pin_press_001", "squatrack_pinpress_001",
    "bb_closegripfloorpress_001", "swissbar_floorpress_001", "floor_press_001",
    # Overhead-press family: same reasoning
    "bradford_press_001", "behindneck_press_001", "zpress_001",
    "buffalobar_press_001", "camberedbar_press_001", "swissbar_press_001",
    "smith_ohp_001", "fingalsfingers_press_001", "log_press_001", "logbar_pushpress_001",
})


def press_variation_multiplier(data: Dict) -> float:
    """0.75x for a named technique/ROM/specialty-bar variation of a bigger
    press (see _PRESS_VARIATION_DISCOUNT_IDS docstring above), 1.0
    (no-op) for every other exercise - including the plain lift each of
    these is a variation of."""
    return 0.75 if data.get("id") in _PRESS_VARIATION_DISCOUNT_IDS else 1.0


def equipment_movement_priority_multiplier(
    data: Dict, training_emphasis: Optional[str] = None, experience_level: Optional[str] = None,
) -> float:
    """Default ranking bias, in this order: Barbell and the dedicated
    low-injury-risk implements as one tied top tier (_TOP_TIER_EQUIPMENT -
    see its docstring above), then Dumbbell/Kettlebell, then compound
    movement patterns (squat/hinge/press/pull/full-body), then
    Olympic-lift-style explosive work (category "Power"), then Rings, then
    Core/Grip accessory work, then everything else unchanged (1.0). Each
    exercise gets exactly one tier - equipment is checked before category
    so a barbell Olympic lift (e.g. Barbell Hang Power Clean) lands in the
    top tier rather than the Power tier, matching "barbell first".

    `training_emphasis` and `experience_level` together decide what a
    "power" goal prefers instead of the barbell-first default:
      - Beginner/Novice (_BEGINNER_POWER_RANKS): Dumbbell/Kettlebell work
        is bumped up to (just under) the top tier - dumbbell snatches/
        cleans and kettlebell swings/cleans build the same explosive
        hip-drive pattern as an Olympic lift with far less technical
        overhead, so that's what a true beginner's power session should
        be built around, not a barbell snatch/clean.
      - Intermediate and up: barbell Olympic-lift work already sits in the
        top tier via the Barbell equipment check above, which is exactly
        "easy/entry Olympic lifts first" for this group - no extra bump
        needed. Category "Power" work more broadly still gets a smaller
        bump ahead of the generic compound-pattern tier, same as before.
    Every other goal (including "strength" and the default None) leaves
    Olympic-lift-style work in its normal, lower tier - a pure strength
    goal has no reason to rank explosive Olympic work above a heavy
    compound barbell-adjacent lift.

    RING DISCOUNT (reported bug, in two parts):
    Part 1 (strength/power): an Archer Ring Push-Up/Ring Archer Dip was
    outranking Flat Bench Press, Overhead Press, and other loadable
    presses with training_emphasis="strength" or "power" set. Rings are
    bodyweight-only - there is no way to add external load the way a
    barbell/dumbbell/kettlebell can - so for a goal that is specifically
    about building maximal load-bearing strength or power, a ring variant
    should never outrank a genuinely loadable press just because its
    authored sport_priority/quality-overlap happens to be high for a
    given combat/climbing sport (e.g. Ring Archer Dip is authored 80+ for
    BJJ/Judo and 95 for Rock Climbing - enough to beat the top equipment
    tier's 1.22x on sport-transfer score alone). Gets the strongest
    discount, 0.55x.
    Part 2 (default/balanced - no training_emphasis set at all): the same
    failure mode reproduces with training_emphasis omitted (the engine's
    default "balanced" prescription, and what the wizard sends unless the
    person explicitly picks a Strength/Power goal) - the plain 1.05x this
    branch used to return in every non-strength/power case still lost to
    a combat-sport-authored Rings score often enough to surface in a
    default "commercial gym, no goal picked" session, contradicting this
    module's own stated philosophy just above (_RING_EQUIPMENT's
    docstring: "a general-purpose default session shouldn't reach for
    them ahead of any loadable implement"). The default case now actually
    enforces that instead of only stating it: 0.85x, a real discount but
    lighter than the strength/power case, since a default/balanced goal
    isn't as singularly focused on maximal external load. hypertrophy and
    strength_hypertrophy are the only goals that keep the original 1.05x
    - genuine bodyweight/ring strength-endurance work is a legitimate
    hypertrophy stimulus, and hypertrophy_quality_multiplier already
    scores that on its own merits rather than this equipment tier."""
    equipment = data.get("equipment")
    category = data.get("category")
    is_beginner_power = training_emphasis == "power" and experience_level in _BEGINNER_POWER_RANKS
    if equipment in _TOP_TIER_EQUIPMENT:
        return 1.22
    if equipment in _SECOND_TIER_EQUIPMENT:
        return 1.19 if is_beginner_power else 1.10
    if equipment in _RING_EQUIPMENT:
        if training_emphasis in ("strength", "power"):
            return 0.55
        if training_emphasis in ("hypertrophy", "strength_hypertrophy"):
            return 1.05
        return 0.85
    if category == "Power" and training_emphasis == "power":
        return 1.17
    if category in _COMPOUND_CATEGORIES:
        return 1.15
    if category == "Power":
        return 1.10
    if category in ("Core", "Grip"):
        return 1.03
    return 1.0


# Per-joint, curated "dedicated joint-sparing equipment" table - the thing
# that lets an athlete with a knee/leg injury who happens to have a Seal Row
# Bench get it actually prioritized, not merely allowed. Every entry here was
# checked against data/exercises.json: for each joint, only equipment where
# NOT ONE exercise in the whole database tags that joint under joint_stress
# (i.e. the database itself never associates this equipment with loading
# that joint at all) is eligible - this list is a hand-picked, genuinely-
# useful subset of that larger data-cleared set (e.g. Jump Rope also clears
# the "never touches Wrist" check but obviously isn't a wrist-friendly swap
# in the sense that matters here, so it's left out).
#
# Knee/Hip/Ankle share one list ("leg/lower-body") since a leg-muscle
# complaint (hamstring/quad/calf/hip flexor strain etc.) maps onto one of
# these three canonical joints in injury_taxonomy.py's 8-tag vocabulary,
# not a 4th "leg" tag of its own - see that file's module docstring.
_LEG_JOINT_EQUIPMENT = {
    "Seal Row Bench", "Chest Press Machine", "Shoulder Press Machine",
    "Pec Deck Machine", "Lat Pulldown Machine", "Seated Row Machine",
    "High Row Machine", "Cable Machine",
}

INJURY_JOINT_PREFERRED_EQUIPMENT: Dict[str, set] = {
    "Knee": _LEG_JOINT_EQUIPMENT,
    "Hip": _LEG_JOINT_EQUIPMENT,
    "Ankle": _LEG_JOINT_EQUIPMENT,
    "Lower Back": {
        "Seal Row Bench", "Chest Press Machine", "Shoulder Press Machine",
        "Pec Deck Machine", "Lat Pulldown Machine", "Leg Press Machine",
        "Leg Extension Machine", "Leg Curl Machine",
    },
    "Shoulder": {
        "Leg Press Machine", "Hack Squat Machine", "Leg Extension Machine",
        "Leg Curl Machine", "Belt Squat Machine", "V Squat Machine",
        "Pendulum Squat Machine",
    },
    "Elbow": {
        "Leg Press Machine", "Hack Squat Machine", "Leg Extension Machine",
        "Leg Curl Machine", "Belt Squat", "Belt Squat Machine", "Sled", "Trap Bar",
    },
    "Wrist": {
        "Leg Press Machine", "Hack Squat Machine", "Leg Extension Machine",
        "Leg Curl Machine", "Belt Squat", "Belt Squat Machine", "Landmine", "Trap Bar",
    },
    "Neck": {
        "Leg Press Machine", "Chest Press Machine", "Shoulder Press Machine",
        "Seated Row Machine", "Pec Deck Machine", "Lat Pulldown Machine",
    },
}


def injury_avoidant_equipment_multiplier(data: Dict, injured_joints: Optional[set]) -> float:
    """Extra ranking boost - stacked ON TOP of equipment_movement_priority_multiplier
    above, not a replacement for it - for an exercise whose equipment is a
    curated, dedicated joint-sparing substitute (INJURY_JOINT_PREFERRED_EQUIPMENT)
    for a joint THIS athlete actually has a tracked injury on.

    This is the difference between "Seal Row Bench gets a small universal
    bump because it's generally low-risk" (equipment_movement_priority_multiplier,
    applied to every athlete regardless of injury) and "this athlete has a
    knee injury and their gym has a Seal Row Bench, so it should actually be
    the row variation that surfaces first" - the latter only makes sense
    conditioned on the injury actually being present.

    Deliberately does not re-check the candidate's own joint_stress/severity
    here - generate_session's existing four-tier injury gate has already
    excluded (or capped) anything genuinely unsafe for the injured joint
    before this multiplier ever runs on it; this only re-orders the
    survivors. No-op (1.0) whenever `injured_joints` is empty/None or the
    exercise's equipment isn't a preferred one for any joint the athlete has
    listed - the overwhelming majority of calls, same as every other
    multiplier in this module.
    """
    if not injured_joints:
        return 1.0
    equipment = data.get("equipment")
    for joint in injured_joints:
        if equipment in INJURY_JOINT_PREFERRED_EQUIPMENT.get(joint, ()):
            return 1.35
    return 1.0


def hypertrophy_quality_multiplier(data: Dict, training_emphasis: Optional[str]) -> float:
    """Ranking bias for "Build Muscle" / hypertrophy-mode requests, applied on
    top of sport transfer rather than instead of it - a hypertrophy-focused
    session should still favor movements that fit the person's sport/goals,
    just with an extra thumb on the scale toward whichever *safe* candidates
    (this only ever runs on exercises that already cleared every equipment/
    injury/strength/level check in generate_session) actually build the most
    muscle. Reuses each exercise's own derived `athletic_qualities["Hypertrophy"]`
    score (0-100, see exercise_metadata.CATEGORY_PROFILES) rather than a second
    hand-authored table, for the same "one source of truth" reason
    movement_emphasis_multiplier reuses SPORT_MOVEMENT_EMPHASIS instead of a
    parallel scoring path. No-op (1.0) whenever training_emphasis isn't
    "hypertrophy" or "strength_hypertrophy" (including the default None), so
    every existing caller that doesn't set it keeps identical ranking
    behavior. "strength_hypertrophy" (the packet's blended 5-8 rep/70-82%
    row) gets the same tilt at half strength - a real thumb toward
    muscle-building candidates, but lighter than a pure "Build Muscle"
    request, since this goal is still a strength goal first."""
    if training_emphasis not in ("hypertrophy", "strength_hypertrophy"):
        return 1.0
    score = (data.get("athletic_qualities") or {}).get("Hypertrophy", 50)
    # 0-100 Hypertrophy score -> ~0.80x-1.30x, the same spread used by
    # equipment_movement_priority_multiplier's own tiers above.
    full = 0.80 + (score / 100.0) * 0.50
    if training_emphasis == "strength_hypertrophy":
        # Halve the distance from 1.0 (neutral) rather than halving the
        # multiplier itself, so a low-Hypertrophy-score exercise is still
        # discounted (not accidentally boosted) at this lighter strength.
        return 1.0 + (full - 1.0) * 0.5
    return full


def movement_emphasis_multiplier(data: Dict, sport: str) -> float:
    """Sport-specific bias for this exercise's pattern (category takes
    precedence over movement_pattern when both are present in the sport's
    table, since category is the coarser/more reliable field). Returns 1.0
    (no change) when the sport has no table or the pattern isn't in it."""
    table = SPORT_MOVEMENT_EMPHASIS.get(sport)
    if not table:
        return 1.0
    category = data.get("category")
    if category in table:
        return table[category]
    pattern = data.get("movement_pattern")
    if pattern in table:
        return table[pattern]
    return 1.0


# Combat Sports & Rugby S&C Manual, Part 5 — "Quick-Reference Summary" table
# plus each sport's own subsection. One row per sport the manual actually
# covers (MMA, BJJ, Wrestling, Judo, Boxing, Kickboxing, Muay Thai, Sanda,
# Sambo, Special Forces, Rugby — 11 sports; Rock Climbing and HYROX aren't
# in the manual and keep whatever guidance they already had elsewhere in
# this module). `aerobic_pct`/`lactic_pct` always sum to 100 and drive how
# many of AEROBIC_SESSION_MENU vs. LACTIC_SESSION_MENU sessions a program
# should surface per week (conditioning_protocols.py has the menus
# themselves — this table only carries the per-sport ratio + narrative).
SPORT_CONDITIONING_PROFILES: Dict[str, Dict] = {
    "MMA": {
        "best_splits": ["3-Day Full Body (in-season)", "4-Day Upper/Lower (off-season)"],
        "aerobic_pct": 50, "lactic_pct": 50,
        "gym_emphasis": "Balanced full-body strength; the biggest aerobic base of all combat sports here (longest, most varied rounds).",
        "conditioning_notes": "2x/week aerobic (30-40 min Zone 2) to build the base + 1-2x/week lactic interval work matching your fight's round length (e.g. 5-min rounds/1-min rest x3-5).",
        "time_saver": "Pair your lactic conditioning with skill work — hard sparring/rolling rounds count toward your lactic volume, you don't need to double up.",
    },
    "BJJ": {
        "best_splits": ["3-Day Full Body", "3-Day Push/Pull/Legs"],
        "aerobic_pct": 55, "lactic_pct": 45,
        "gym_emphasis": "Pulling strength (rows, pull-ups), isometric holds, hip strength for guard/sweeps, heavy grip and forearm work.",
        "conditioning_notes": "Aerobic base is priority (rolls can be long) — 2-3x/week Zone 2, plus 1x/week lactic work in 5-8 min 'round' efforts to mimic hard rolling.",
        "time_saver": "Rolling itself is excellent lactic conditioning — 4-5 hard 5-minute rolls covers your weekly lactic quota.",
    },
    "Wrestling": {
        "best_splits": ["4-Day Upper/Lower (off-season)", "3-Day Full Body (in-season)"],
        "aerobic_pct": 35, "lactic_pct": 65,
        "gym_emphasis": "Hip and posterior chain power (deadlifts, hip thrust), explosive pulling, heavy neck training (bridging), grip.",
        "conditioning_notes": "Lactic-dominant — 2x/week interval work (e.g. 20-30s max effort bike/sled x8-10, short rest) plus 1x/week aerobic base session.",
        "time_saver": "Live wrestling/scramble drilling doubles as lactic conditioning — don't stack extra hard intervals on heavy practice days.",
    },
    "Judo": {
        "best_splits": ["3-Day Full Body"],
        "aerobic_pct": 30, "lactic_pct": 70,
        "gym_emphasis": "Maximal grip strength, explosive hip extension (cleans/high pulls or trap bar jumps), single-leg strength for off-balancing.",
        "conditioning_notes": "Mostly lactic — short, very hard intervals (15-30s max effort) mirroring throw exchanges, 2x/week; 1x/week light aerobic for recovery capacity.",
        "time_saver": "Uchikomi (repeated throw entries) at high speed is a built-in lactic/power session.",
    },
    "Boxing": {
        "best_splits": ["2-Day Upper/Lower", "3-Day Full Body (off-season)"],
        "aerobic_pct": 40, "lactic_pct": 60,
        "gym_emphasis": "Rotational core power (landmine press, medicine ball throws), upper-back and shoulder endurance, single-leg stability for footwork.",
        "conditioning_notes": "Classic round-based lactic intervals (3 min on/1 min off x3-6, bike or shadowboxing) 2x/week, plus 2x/week aerobic running for the historic 'roadwork' base.",
        "time_saver": "Structure your interval conditioning in literal round/rest ratios so it transfers directly.",
    },
    "Kickboxing": {
        "best_splits": ["3-Day Full Body", "2-Day Upper/Lower"],
        "aerobic_pct": 45, "lactic_pct": 55,
        "gym_emphasis": "Single-leg strength and hip power for kicks (split squats, hip thrust, trap bar jumps), core rotation, shoulder endurance.",
        "conditioning_notes": "Round-based lactic intervals 2x/week (matching competition round length) + 2x/week aerobic base.",
        "time_saver": "Heavy-bag combination rounds at competition pace double as lactic work — track them as a session.",
    },
    "Muay Thai": {
        "best_splits": ["3-Day Full Body", "2-Day Upper/Lower"],
        "aerobic_pct": 45, "lactic_pct": 55,
        "gym_emphasis": "Hip and knee-drive power, clinch/grip strength (heavy carries, isometric holds), single-leg balance, calf/shin conditioning work.",
        "conditioning_notes": "Round-based lactic intervals 2x/week + 2x/week aerobic running/cycling (traditional Muay Thai roadwork).",
        "time_saver": "Clinch sparring rounds are simultaneously strength-endurance and lactic conditioning.",
    },
    "Sanda": {
        "best_splits": ["3-Day Full Body"],
        "aerobic_pct": 40, "lactic_pct": 60,
        "gym_emphasis": "Full-body explosive power (trap bar jumps, medicine ball throws), grip for clinch throws, single-leg strength for sprawl/takedown defense.",
        "conditioning_notes": "Lactic-dominant intervals 2x/week (mix striking-pace and grappling-pace efforts) + 1x/week aerobic base.",
        "time_saver": "Combine throw-entry drilling with striking combinations in the same hard round to cover both qualities at once.",
    },
    "Sambo": {
        "best_splits": ["4-Day Upper/Lower (off-season)", "3-Day Full Body (in-season)"],
        "aerobic_pct": 35, "lactic_pct": 65,
        "gym_emphasis": "Grip strength, explosive hip extension, posterior chain strength, joint-friendly single-leg work to protect knees/hips from leg-lock stress.",
        "conditioning_notes": "Lactic-dominant, similar to wrestling/judo — 2x/week short hard intervals + 1x/week aerobic base.",
        "time_saver": "Live grappling rounds at full intensity substitute directly for a lactic conditioning session.",
    },
    "Special Forces": {
        "best_splits": ["4-Day Upper/Lower"],
        "aerobic_pct": 70, "lactic_pct": 30,
        "gym_emphasis": "Max strength in squat/deadlift/press, heavy loaded carries, pulling strength for climbing/casualty drags.",
        "conditioning_notes": "Aerobic-dominant — 3-4x/week (rucking, running, swimming, rowing) building toward longer durations, plus 1-2x/week lactic work (sandbag/sled intervals, hill sprints) for the short maximal-effort demand.",
        "time_saver": "Ruck marches and loaded carries double as both conditioning and posterior-chain/grip strength work.",
    },
    "Rugby": {
        "best_splits": ["4-Day Upper/Lower (in-season)", "3-Day Push/Pull/Legs (off-season)"],
        "aerobic_pct": 45, "lactic_pct": 55,
        "gym_emphasis": "Maximal squat/deadlift/press strength for scrums and tackling, explosive power (jumps, sled pushes), neck strength for contact.",
        "conditioning_notes": "Repeated-sprint lactic training 2x/week (e.g. 10x40m sprint with short rest) + 2-3x/week aerobic running to build match-duration capacity.",
        "time_saver": "Team conditioning/repeated-sprint drills at training count as your lactic sessions — add gym work on separate or lighter days.",
    },
}


def sport_conditioning_profile(sport: str) -> Dict:
    """Aerobic:lactic ratio + gym emphasis + weekly conditioning guidance for
    a sport, straight out of the manual's Part 5. Returns an empty dict for
    sports the manual doesn't cover (e.g. Rock Climbing, HYROX) rather than
    guessing a ratio for them."""
    return SPORT_CONDITIONING_PROFILES.get(sport, {})


# ==========================================================================
# ATHLETE-APPROVED MOVEMENT LIST (reported coach request)
# ==========================================================================
# The athlete supplied FORGE with a standing list of the movement families
# they want the program built around — big barbell/dumbbell/kettlebell
# compounds, sled/carry conditioning, and a curated set of arm/shoulder/
# hamstring/calf accessory work — and asked that FORGE actively favor those
# over the database's much larger catalog of niche cable/machine isolation
# variants ("pencil neck" work, in their words).
#
# Matched by KEYWORD against the exercise's own name, not by a hand-typed
# id list — every named loading variant of an approved movement family
# (Chain Back Squat, Paused Back Squat, Barbell Back Squat, Safety Bar Box
# Squat, ...) should count the same as the plain lift, since the athlete
# asked for the movement pattern, not one specific bar/tempo/ROM variant of
# it. This mirrors _PRESS_VARIATION_DISCOUNT_IDS's own point just above —
# a named variation is still fundamentally the same movement family as the
# plain lift — applied as an inclusion list here instead of a discount list.
#
# Each string is checked as a substring of the lowercased exercise name.
# Deliberately broad on compound patterns (squat/deadlift/row/press/curl)
# so the whole family scores as approved; deliberately specific on
# accessory work (lateral raise, face pull, upright row, skull crusher,
# rear delt, calf raise, hip thrust, leg press/extension) so it only
# matches the exact accessory movements the athlete actually listed, not
# every unrelated isolation exercise in the database.
ATHLETE_APPROVED_KEYWORDS: List[str] = [
    # Push / pressing
    "bench press", "overhead press", "push press", "dip",
    "landmine press", "kettlebell press", "incline press",
    # Pull / back
    "pull-up", "pull up", "chin-up", "chin up", "lat pulldown", "row",
    # Squat / lower body
    "squat", "step-up", "step up",
    # Deadlift / posterior chain
    "deadlift", "reverse hyper", "ghd", "nordic", "good morning",
    # Conditioning / sled
    "sled push", "sled drag",
    # Carries / grip
    "farmer", "carry", "plate pinch", "rope climb", "dead hang",
    # Core
    "sit-up", "sit up", "leg raise", "landmine rotation",
    # Power / explosive
    "clean", "snatch", "jerk", "medicine ball", "kettlebell swing",
    # Arms
    "curl", "tricep", "skull crusher",
    # Shoulders / chest / traps
    "lateral raise", "shrug", "fly", "flye", "face pull", "front raise",
    "rear delt", "upright row", "pec deck",
    # Extra accessory work from the athlete's list
    "leg press", "leg extension", "hip thrust", "calf raise",
]


def is_athlete_approved_movement(data: Dict) -> bool:
    """True if this exercise's name matches one of the athlete's approved
    movement-family keywords above."""
    name = (data.get("name") or "").lower()
    return any(keyword in name for keyword in ATHLETE_APPROVED_KEYWORDS)


def athlete_movement_priority_multiplier(data: Dict) -> float:
    """1.25x for anything matching the athlete's standing approved-movement
    list (ATHLETE_APPROVED_KEYWORDS) - real compounds and the specific
    accessory work they named - and 0.80x for everything else, so the big
    barbell/dumbbell/kettlebell lifts and named accessories consistently
    outrank the database's long tail of niche cable/machine isolation
    variants they didn't ask for.

    This is a ranking nudge only, exactly like every other multiplier in
    this module - it stacks on top of blended_transfer_score and friends
    and never touches `qualifies` in generate_session, so the safety/
    equipment/strength/level gate (and the manual's own stated rule,
    \"Safety overrides exercise preference\") is completely unaffected. A
    non-approved exercise can still be picked whenever it's genuinely the
    best/only safe qualifying option - it just stops winning ties against
    an approved compound the way it might have before.
    """
    return 1.25 if is_athlete_approved_movement(data) else 0.80


def transfer_rationale(data: Dict, sport: str) -> str:
    """One sentence a coach could actually say out loud."""
    qualities = data.get("athletic_qualities", {})
    top = top_contributing_qualities(qualities, sport)
    name = data.get("name", data.get("id", "This exercise"))
    multiplier = movement_emphasis_multiplier(data, sport)
    pattern_note = ""
    if multiplier >= 1.1:
        pattern_note = f" Boosted for {sport}: {data.get('category', 'this pattern')} is a priority pattern for the sport."
    elif multiplier <= 0.9:
        pattern_note = f" De-emphasized for {sport}: {data.get('category', 'this pattern')} matters less than other patterns here."
    if not top:
        return f"{name} contributes general conditioning value for {sport}.{pattern_note}"
    quality_list = ", ".join(f"{q} ({v})" for q, v in top)
    return f"Transfers to {sport} primarily through {quality_list}.{pattern_note}"

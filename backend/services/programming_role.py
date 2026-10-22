"""
programming_role.py — what job an exercise does INSIDE a session, and where
a coach would put it in the running order.

WHY THIS EXISTS
Every prior version of FORGE produced a workout as a bag of qualifying
exercises sorted by a single sport-priority number. That's a filter, not a
session - a real coach doesn't run a max-effort deadlift after twelve minutes
of conditioning, and doesn't bury a technical throw-entry drill at the end of
a session once the CNS is fried. Sequencing is part of what "reasoning like a
coach" means, and it's driven by fields the engine already derives (category,
force_type, CNS_fatigue, difficulty) - so, same principle as
exercise_metadata.py and sport_profiles.py, this is one small ruleset applied
consistently rather than a hand-typed order per exercise.

ROLE TAXONOMY (session_order_rank = the order a coach runs them in):
    1. Primer / Activation   - low-fatigue, low-difficulty stability/mobility
                                work that wakes a joint/pattern up.
    2. Skill / Technical     - sport-specific technical work; needs a fresh
                                CNS more than it needs load.
    3. Power & Explosive     - jumps/throws/ballistic work; also needs CNS
                                freshness, done before heavy grinding lifts.
    4. Primary Strength      - the heaviest loaded lift(s) the session is
                                built around.
    5. Secondary Strength    - a second, still genuinely-loaded compound
                                lift in the same six strength categories
                                (Squat/Hinge/Horizontal-Vertical Push/Pull)
                                as Primary Strength, one difficulty notch
                                down - a real coach's "second big lift"
                                slot (e.g. a Front Squat after a Back
                                Squat), run before lighter accessory work
                                while there's still CNS/technical capacity
                                for a genuinely loaded lift, but after the
                                single heaviest lift of the day.
    6. Accessory / Hypertrophy - lighter loaded work, built after the main
                                lift(s), tolerant of accumulated fatigue.
    7. Core & Stability      - trunk/grip/carry work; deliberately placed
                                after strength work, since a fatigued trunk
                                under light load is still safe and effective.
    8. Conditioning / Finisher - the highest metabolic-fatigue work, run last
                                so it doesn't compromise technique or load
                                elsewhere in the session.
"""

from typing import Dict, Tuple

ROLE_ORDER = [
    "Primer / Activation",
    "Skill / Technical",
    "Power & Explosive",
    "Primary Strength",
    "Secondary Strength",
    "Accessory / Hypertrophy",
    "Core & Stability",
    "Conditioning / Finisher",
]
ROLE_RANK = {role: i + 1 for i, role in enumerate(ROLE_ORDER)}

# Deliberately NOT in ROLE_ORDER. Live striking work (heavy bag rounds,
# shadow boxing, band-resisted kick drills, etc. - anything tagged
# movement_pattern == "Strike") plays no role in this app's strength &
# conditioning programming, for any sport - this app is a gym program
# builder, not a striking coach; that skill work happens elsewhere with an
# actual coach. Tagging it with this role (instead of Skill/Technical, its
# category would otherwise imply) is what lets progression_engine exclude
# it from a generated session entirely, cleanly, in one place.
#
# BUG FIXED: this exclusion only ever covered striking. Every grappling/
# tackle equivalent - drilling a takedown entry against a Wrestling Dummy,
# a leg-lock defense flow, Judo Uchikomi entries, a suplex throw, footwork
# circling or clinch work on a Heavy Bag - stayed routed to "Skill /
# Technical" and got pulled into ANY sport whose hand-authored
# sport_priority score cleared the role floor, not just the sport it
# actually belongs to. Concretely: a Special Forces or HYROX plan could
# come back with "Leg-Lock Defense Mobility Flow" or "Bridge-to-Hip-Escape
# Flow" (both BJJ-specific submission-grappling technique, sport_priority
# 65 for Special Forces in the hand-authored data) even though a Special
# Forces athlete has no more use for BJJ leg-lock technique in a gym S&C
# plan than a boxer's program has for a Judo throw-entry drill - both need
# an actual grappling/combat coach to teach correctly, exactly the same
# argument that already excluded Strike. So the same treatment now applies
# to every "Sport Specific" exercise that's really "how to execute
# technique X against a bag/dummy/opponent" rather than a generic loaded
# conditioning tool - see PARTNER_SKILL_EXCLUDED_IDS below for the list and
# reasoning on what stayed in vs. what got excluded.
STRIKE_SKILL_EXCLUDED_ROLE = "Technical Skill Work (Excluded - Trained With a Coach, Not This App)"

# "Sport Specific" exercise IDs that drill one combat/grappling sport's
# specific technique against a bag/dummy/opponent-simulator (a takedown
# entry, a submission escape, a throw, footwork or clinch drilling) -
# these need a live coach correcting technique the same way Strike-pattern
# bag/pad work does, so they get the same STRIKE_SKILL_EXCLUDED_ROLE
# treatment for every sport, including the sport they were authored for.
# NOT included here (deliberately kept as normal, sport-scored Skill/
# Technical or Conditioning/Finisher work): hyrox_sled_push_001 (a loaded
# push tool, no technique-correctness component), ruck_march_001 (a
# continuous loaded walk, already routed to Conditioning/Finisher above),
# neck_bridge_001 (an isometric strength hold, already routed to Core &
# Stability above), obstacle_circuit_001 and cod_5_10_5_001 (generic
# functional-fitness/agility drills used across many sports, not one
# sport's competition technique) - none of these need a specialist coach
# to perform safely and correctly the way a leg-lock or a suplex entry
# does.
PARTNER_SKILL_EXCLUDED_IDS = frozenset({
    "dummy_suplex_001",              # Wrestling Dummy Suplex Throw
    "judo_uchikomi_001",             # Judo Uchikomi Entries
    "shadow_uchikomi_001",           # Shadow Uchikomi Entries (No Partner)
    "bridge_hipescape_001",          # Bridge-to-Hip-Escape Flow (BJJ)
    "leglock_defense_flow_001",      # Leg-Lock Defense Mobility Flow (BJJ)
    "tackle_bag_drive_001",          # Rugby Tackle Bag Drive
    "tacklebag_sprawl_001",          # Tackle Bag Sprawl
    "tacklebag_hipdrive_001",        # Tackle Bag Explosive Hip Drive
    "tacklebag_choptackle_001",      # Tackle Bag Chop Tackle
    "tacklebag_wrapdrive_001",       # Tackle Bag Wrap and Drive
    "tacklebag_reactionread_001",    # Tackle Bag Reaction Read Tackle
    "tacklebag_lowdrivefinish_001",  # Tackle Bag Low Drive Finish
    "wrestlingdummy_doubleleg_001",  # Wrestling Dummy Double-Leg Takedown
    "wrestlingdummy_sprawl_001",     # Wrestling Dummy Sprawl Drill
    "wrestlingdummy_singlelegfinish_001",  # Wrestling Dummy Single-Leg Finish
    "wrestlingdummy_snapdown_001",   # Wrestling Dummy Snap-Down Drill
    "heavybag_footwork_001",         # Heavy Bag Footwork Circling Drill (boxing footwork technique)
    "heavybag_clinchwork_001",       # Heavy Bag Clinch Work (Muay Thai clinch technique)
})

_LOADED_STRENGTH_CATEGORIES = {
    "Horizontal Push", "Vertical Push", "Horizontal Pull", "Vertical Pull",
    "Squat", "Hinge",
}
_TRUNK_CATEGORIES = {"Core", "Grip", "Carry"}


def classify_programming_role(ex: Dict) -> Tuple[str, str]:
    """Returns (role, rationale). Pure function of fields the exercise
    already carries (category, force_type, CNS_fatigue, fatigue_cost,
    difficulty) - no per-exercise hand-tagging required."""
    category = ex.get("category", "")
    force_type = ex.get("force_type", "")
    movement_pattern = ex.get("movement_pattern", "")
    difficulty = ex.get("difficulty", 1)
    cns_fatigue = ex.get("CNS_fatigue", difficulty * 15)
    fatigue_cost = ex.get("fatigue_cost", difficulty * 14)

    if movement_pattern == "Strike":
        return (
            STRIKE_SKILL_EXCLUDED_ROLE,
            "Live striking/bag skill work - trained separately with an actual striking coach, not "
            "part of this app's strength & conditioning programming, so it's excluded from the "
            "generated session entirely rather than assigned any strength-training slot.",
        )

    if ex.get("id") in PARTNER_SKILL_EXCLUDED_IDS:
        return (
            STRIKE_SKILL_EXCLUDED_ROLE,
            "Live technique drilling against a bag/dummy/opponent-simulator (a takedown entry, "
            "submission escape, throw, or footwork/clinch drill) - trained separately with an "
            "actual grappling/combat coach, not part of this app's strength & conditioning "
            "programming, for any sport including the one it was authored for.",
        )

    # Ruck March (any variant) is a single continuous time/distance loaded
    # walk, not a technical skill drill and not a carry accessory set -
    # checked before the category/fatigue_cost branches below so it can't
    # get routed to "Skill / Technical" (early, via its "Sport Specific"
    # category) or "Core & Stability" (via "Carry"). It belongs at the very
    # end of the session like any other conditioning finisher, run once
    # everything else is done.
    if "ruck march" in ex.get("name", "").lower():
        return (
            "Conditioning / Finisher",
            "Ruck march is a single continuous time/distance effort, not sets/reps or a technical "
            "drill - run last, after all lifting is done, same as any other conditioning finisher.",
        )

    # BUG FIXED: this used to fire on ANY exercise with fatigue_cost >= 60,
    # not just genuine "Conditioning"-category work - and fatigue_cost is
    # just difficulty*14 (+10 for Conditioning/Full Body/Carry), so EVERY
    # difficulty-5 exercise in ANY category (fatigue_cost 70) tripped this
    # before it ever reached its own dedicated branch below. Concretely:
    # every Olympic-lift/strongman explosive movement (Power Clean, Power
    # Snatch, Clean and Jerk, Split Jerk, Atlas Stone Load, ...) is filed
    # under category "Full Body" or "Power" and fatigue_cost 66-80, and
    # every hardest-tier compound/skill lift in the six loaded-strength
    # categories (Max Effort Squat, Overhead Squat, Bar Muscle-Up, One-Arm
    # Pull-Up, Split Jerk, ...) sits at difficulty 5 / fatigue_cost 70 -
    # all of it was getting yanked out of "Power & Explosive"/"Primary
    # Strength" (where the branches below correctly place it) and dumped
    # into "Conditioning / Finisher" instead, meaning a session's heaviest
    # squat or its Power Clean ran dead last, after every other lift and
    # after actual conditioning work - the exact opposite of correct
    # placement, and the opposite of what this function's own docstring
    # says ("needs a fresh CNS", "run before the grinding strength work").
    # Only category == "Conditioning" is treated as this branch's real
    # signal now - a bare fatigue_cost number was never a reliable proxy
    # for "this is metabolic conditioning work" once every category's own
    # hardest exercises also cross 60 purely from difficulty. The generic
    # fatigue_cost >= 60 check is kept, but only as the final fallback (see
    # the bottom of this function) for exercises that don't match any of
    # the more specific categories below - Jump/Power/Sport
    # Specific/Trunk/loaded-strength all get their own correct branch
    # first, exactly like before this fix broke them.
    if category == "Conditioning":
        return (
            "Conditioning / Finisher",
            "Metabolic conditioning work - placed last so it doesn't compromise technique or load elsewhere.",
        )

    if category == "Sport Specific":
        # Every "Sport Specific" exercise in the data is a live, dynamic
        # technical drill (Concentric or Stretch-Shortening Cycle) EXCEPT
        # Wrestler's Neck Bridge, which is a static Isometric hold. Routing
        # it through this branch put neck training at rank 2 - right after
        # the warm-up and before every strength/power lift - when the
        # manual is explicit, in every single sport chapter, that the
        # neck/grip block runs "at the very end of a training day...
        # not before" (pre-fatiguing the neck before heavy pulling/
        # squatting is called out as an injury risk). A static hold also
        # doesn't need the fresh-CNS precision this branch exists for in
        # the first place - that's a Concentric/SSC concern, not an
        # Isometric one. So an Isometric "Sport Specific" exercise gets
        # the same treatment as the rest of the neck & grip block instead.
        if force_type == "Isometric":
            return (
                "Core & Stability",
                "Static isometric hold (e.g. neck bridge) - not a fresh-CNS skill drill; belongs with the rest of the neck/grip block, run after strength work per the manual's explicit placement note.",
            )
        return (
            "Skill / Technical",
            "Sport-specific technical work - sequenced early, while the CNS is still fresh enough for precision.",
        )

    if category in ("Jump", "Power") or force_type == "Stretch-Shortening Cycle":
        return (
            "Power & Explosive",
            "Reactive/ballistic output degrades fast with fatigue - run before the grinding strength work.",
        )

    if category in _TRUNK_CATEGORIES:
        # Bar was `difficulty >= 3`, but every Carry exercise in the data
        # starts at difficulty 2 (fatigue_cost 38+) - a farmer's carry or
        # ruck march is never a joint-activation drill, yet the old bar
        # routed the entire easy/mid half of Carry (and most of Core/Grip)
        # into Primer/Activation, front-loading loaded trunk work into
        # every session instead of running it after strength like the rest
        # of this function's own docstring says trunk/grip/carry work
        # should. fatigue_cost cleanly jumps 14 -> 28+ exactly at
        # difficulty 2 across Core/Grip/Carry alike, so difficulty >= 2 is
        # the real boundary between a true low-load primer (plank, dead
        # bug, passive dead hang) and everything heavier.
        if difficulty >= 2:
            return (
                "Core & Stability",
                "Demanding trunk/grip/carry work - tolerant of accumulated fatigue, so it runs after strength work.",
            )
        return (
            "Primer / Activation",
            "Low-difficulty stability work - suited to waking the pattern up before the session loads it.",
        )

    if category in _LOADED_STRENGTH_CATEGORIES:
        # Three-tier split (v5.23), not two: the data's own difficulty scale
        # (1-5, roughly evenly populated at 3/4/5) already distinguishes a
        # true max-effort lift (Barbell Back Squat, difficulty 5) from a
        # still-genuinely-loaded-but-secondary compound (a Goblet Squat or
        # machine-assisted press, difficulty 3) from real light/isolation
        # accessory work (a band pull-apart, difficulty 1-2) - collapsing
        # 3/4/5 all into "Primary Strength" put a heavy barbell lift and a
        # goblet squat in the same undifferentiated bucket, and the
        # selection/sequencing logic upstream (progression_engine's
        # `_select_compound_accessory_finisher`) could then hand back two
        # "Primary Strength" picks that were really a main lift plus what
        # any coach would call a secondary lift, sequenced and volumed
        # identically. difficulty >= 4 stays Primary Strength (the true
        # 1-2 heaviest lift classes); difficulty == 3 is the new Secondary
        # Strength tier; difficulty <= 2 stays Accessory / Hypertrophy,
        # unchanged from before.
        if difficulty >= 4:
            return (
                "Primary Strength",
                "The heaviest loaded lift class in this category - the session is built around it.",
            )
        if difficulty == 3:
            return (
                "Secondary Strength",
                "A genuinely loaded compound lift, one notch below the session's heaviest - a coach's "
                "'second big lift' slot, run after Primary Strength but before lighter accessory work.",
            )
        return (
            "Accessory / Hypertrophy",
            "Lighter loaded work - built around the main lift(s), tolerant of accumulated fatigue.",
        )

    # Last-resort fatigue_cost check - only reached now by exercises that
    # didn't match Conditioning, Sport Specific, Power & Explosive, Trunk,
    # or any loaded-strength category above (see the BUG FIXED note near
    # the top of this function for why this can no longer short-circuit
    # those categories' own, more specific branches).
    if fatigue_cost >= 60:
        return (
            "Conditioning / Finisher",
            "High metabolic fatigue cost with no more specific category - placed last so it doesn't compromise technique or load elsewhere.",
        )

    if difficulty <= 2 and cns_fatigue < 30:
        return (
            "Primer / Activation",
            "Low CNS demand - suited to waking the pattern up early in the session.",
        )

    return (
        "Accessory / Hypertrophy",
        "General supporting work - slotted after the session's primary demands.",
    )


def session_order_rank(role: str) -> int:
    return ROLE_RANK.get(role, len(ROLE_ORDER))

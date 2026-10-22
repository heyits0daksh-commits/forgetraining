"""
load_prescription.py — converts an exercise's %1RM load prescription into an
actual working weight in kg, using the person's own tested 1RM numbers,
instead of leaving them to do that math from a bare percentage mid-session.

ANCHOR LIFT MAPPING
`UserBiometrics` (schemas.py) only tracks three tested maxes - bench, squat,
deadlift - but `load_pct_1rm` prescriptions apply to every "loaded strength"
category the engine uses (Horizontal/Vertical Push, Horizontal/Vertical
Pull, Squat, Hinge - see main.py's `is_loaded_strength`), not just those
three named lifts. Squat and Hinge patterns map directly onto the squat and
deadlift maxes - that's an exact match, not a proxy, so PATTERN_RATIO is
1.00 for both. Every other category is a genuinely different lift, not a
scaled-down version of the same one, so a flat 100%-of-anchor mapping
produced physically impossible numbers: a Vertical Push (overhead press)
anchored straight off bench_press_1rm came back as "80% of your bench" AS
the press weight - nobody overhead-presses 80% of their bench for reps, an
overhead press maxes out around 60-65% of bench in the strength-standards
literature. Same failure on the pull side: Horizontal Pull (bent-over row)
anchored straight off deadlift_1rm handed back numbers like a 97kg barbell
row off a 120kg deadlift - a heavy row is closer to 50-60% of deadlift, not
a 1:1 stand-in for it. PATTERN_RATIO below is that missing conversion: the
target pattern's own 1RM as a fraction of the anchor lift's 1RM, applied
BEFORE the difficulty-based load_pct_1rm - so "73% load" now means 73% of a
realistic estimated row/press max, not 73% of an unrelated lift's max.
These ratios are well-worn S&C coaching heuristics (used for programming
when a lift isn't directly tested), not lab-measured for any one person -
that's exactly why every category except Squat/Hinge/Horizontal Push is
still flagged "estimated", same as before.

VERTICAL PULL'S OWN DIRECT ANCHOR
Vertical Pull (lat pulldown, cable pulldown, assisted/banded pull-up
progressions) is the one exception to the deadlift-ratio table above: a
person's tested pull-up reps + bodyweight are a direct measurement of this
exact movement pattern, so add_working_weight tries that first (Epley
estimate, see _estimated_vertical_pull_1rm) and only falls back to
deadlift*0.40 when no pull-up reps are on file. Deadlift is a hinge-pattern,
posterior-chain lift and doesn't reliably track pulling strength - two
people with the same deadlift can have very different pull-up capacity,
which is exactly why relying on deadlift alone was producing prescriptions
far below what an athlete had already proven they could pull (e.g. a
10-rep pull-up capacity at 80kg bodyweight being "estimated" at a 32.5kg
lat pulldown off a middling deadlift, despite pullups_max_reps already
being collected and simply never used for this).

PER-EXERCISE LOAD RATIO (FORGE spec 1.2, section 1)
_ANCHOR_BY_CATEGORY's ratio column is a CATEGORY-WIDE default - one number
for every exercise filed under that movement pattern. That was fine as a
fallback but wrong as the only source: a Good Morning and a Sumo Deadlift
are both "Hinge" and used to receive the exact same load_pct_1rm-of-deadlift
treatment (ratio 1.00 for both), despite a Good Morning maxing out around
40-50% of a deadlift, not 90-100% of one. exercises.json already carries a
per-exercise ratio for exactly this purpose - `strength_requirements.
{bench,squat,deadlift}_ratio` (populated for several hundred exercises;
originally added to gate prerequisite strength checks and to flag isolation
work, see progression_engine.py) - it just was never consulted here. This
module now prefers that per-exercise number over the flat category default
whenever it's set (>0), via `_exercise_ratio_override`, and only falls back
to the category default when the exercise doesn't have its own value yet
(most of the library, as of this writing) - exactly the incremental-
migration resolution order the spec calls for: exercise-level ratio, then
category-level default, then (implicitly) the hardcoded 20-92% clamp
already applied to load_pct_1rm upstream in progression_engine.py as the
last-resort floor/ceiling.

UNILATERAL LOAD ADJUSTMENT (FORGE spec 1.2, section 2)
A Dumbbell/Kettlebell exercise already gets a per-implement discount below
(DB_KB_LOAD_RATIO) purely from being loaded with one separate implement per
hand - that mechanism already produces a lighter, per-hand number for e.g.
a Single-Arm Dumbbell Row without any extra adjustment. What it doesn't
cover is a unilateral exercise on BARBELL or MACHINE equipment (e.g. Single
Arm Barbell Row, Single-Leg Leg Press), which used to be rounded exactly
like its bilateral counterpart with no discount at all. `_unilateral_factor`
supplies that: a global default (0.55 - mid-point of the 0.5-0.6 starting
estimate the spec suggests), overridable per exercise via
`strength_requirements.unilateral_adjustment_factor`, applied ONLY when the
exercise's own ratio field is unset (0/missing) - if a person has already
hand-calibrated an exercise's ratio (Single Arm Barbell Row's deadlift_ratio
0.45 already reads as a per-hand number, well below Pendlay Row's 0.6),
that number is trusted as-is and the global factor is not stacked on top of
it, to avoid double-discounting a value someone already tuned by hand. This
is deliberately the "Option A" bridge from the spec (one global constant,
not yet split per movement pattern) - flagged in-line as a bridge, not the
end state, same as the spec's own Option A/B framing.

EQUIPMENT-AWARE LOAD (Dumbbell / Kettlebell)
The math above computes a barbell-style TOTAL load - the number on a bar a
person pushes/pulls with both hands working together against one fixed
implement. A Dumbbell or Kettlebell exercise is a different loading
situation even at identical relative effort: each hand carries its own
separate, less-stable implement (or, for a single-arm movement, ALL the
load is in one hand with no bar to share it with) - so the number that
belongs in front of the athlete is "how heavy is the one dumbbell/kettlebell
I pick up", not the barbell-equivalent total. Applying the barbell total
directly (the previous behavior) is why a single-arm Kroc Row came back
prescribed at 87.5kg - identical to a two-handed barbell Pendlay Row.
DB_KB_LOAD_RATIO converts the computed barbell-equivalent total into that
one-implement number, and the result is then rounded to what that implement
actually comes in: a dumbbell rack's ~2kg jumps, or the nearest real
kettlebell size off _KETTLEBELL_SIZES_KG (kettlebells aren't sold in
arbitrary 2.5kg/5kg increments - they're cast in a small set of standard
sizes) - rather than pretending either one loads in smooth barbell-plate
increments.

WHY WEIGHT, NOT JUST PERCENTAGE
"72% 1RM" asks the lifter to do that math themselves, against a number they
may not have memorized mid-session. Converting it here, once, off the same
biometrics the rest of the engine already collects, means the session output
can say "62.5 kg" - a number they can actually load a bar to. The percentage
is kept alongside it, not replaced - it's still the number that matters if
they've since tested a new max, and it's the only output at all when no
anchor 1RM has been entered.
"""

from typing import Dict, Optional

# category -> (which tested 1RM field anchors its %1RM prescriptions,
# whether that anchor is a direct measurement of *this* exact pattern or a
# cross-pattern estimate, and the ratio that converts the anchor's own 1RM
# into an estimate of THIS pattern's 1RM - see the module docstring for why
# a flat 1.0 ratio across the board was the actual bug). Sources for the
# non-1.0 ratios: standard S&C programming heuristics for estimating an
# untested lift off a tested one (e.g. Wendler-style / conjugate norms) -
# real individual ratios vary by leverages and training history, which is
# exactly why these stay "estimated" and get a visible caveat rather than
# presented as a measured max.
_ANCHOR_BY_CATEGORY = {
    "Squat":           ("squat_1rm", "direct", 1.00),
    "Hinge":           ("deadlift_1rm", "direct", 1.00),
    "Horizontal Push": ("bench_press_1rm", "direct", 1.00),
    # Strict overhead press typically maxes out ~60-65% of bench press 1RM.
    "Vertical Push":   ("bench_press_1rm", "estimated", 0.62),
    # A heavy barbell row is commonly benchmarked around 50-60% of deadlift.
    "Horizontal Pull": ("deadlift_1rm", "estimated", 0.55),
    # The loosest proxy of the six - pull-up/lat-pulldown strength doesn't
    # track deadlift as reliably as a row does, so this stays conservative.
    "Vertical Pull":   ("deadlift_1rm", "estimated", 0.40),
    # Olympic-lift complexes (Power Clean, Hang Clean, Clean and Jerk,
    # Power Snatch, Split Snatch, ...) and their Power-category relatives
    # (Barbell Hang Power Clean, Barbell Clean Pull, DB Snatch) are
    # quad/hip-driven explosive-pull patterns - closer to a back squat than
    # to a bench or deadlift max. ~60-65% of back squat 1RM is the
    # standard coaching estimate for a recreational lifter's clean/snatch
    # capacity (technique, not raw strength, is usually what actually caps
    # the load on these, so this stays conservative rather than assuming
    # weightlifting-specialist proficiency). These two categories were
    # simply missing from this table before - progression_engine.py's
    # is_loaded_power_lift already classifies loaded Full Body/Power
    # barbell lifts as `type: "strength"` with a load_pct_1rm, but
    # add_working_weight had no anchor to look them up under, so every
    # Olympic lift came back as a bare "X% 1RM" with no actual kg number
    # at all (the "add 1RM for weight" case) even for someone who'd
    # entered a squat max.
    "Full Body":       ("squat_1rm", "estimated", 0.65),
    "Power":           ("squat_1rm", "estimated", 0.55),
}

_ANCHOR_LABEL = {
    "bench_press_1rm": "Bench Press",
    "squat_1rm": "Squat",
    "deadlift_1rm": "Deadlift",
}

# Maps each anchor lift onto the strength_requirements field that carries
# THIS exercise's own ratio to that anchor - see the "PER-EXERCISE LOAD
# RATIO" module note above for why this is preferred over the flat
# per-category default in _ANCHOR_BY_CATEGORY whenever it's populated.
_RATIO_FIELD_BY_ANCHOR = {
    "bench_press_1rm": "bench_ratio",
    "squat_1rm": "squat_ratio",
    "deadlift_1rm": "deadlift_ratio",
}

# "Option A" bridge default from the spec - a starting estimate, not a
# per-movement-pattern-accurate number (see "UNILATERAL LOAD ADJUSTMENT"
# module note above). Only ever applied when the exercise has no
# hand-calibrated ratio of its own to fall back on.
_UNILATERAL_ADJUSTMENT_FACTOR_DEFAULT = 0.55


def _exercise_ratio_override(strength_requirements: Optional[Dict], field: str) -> Optional[float]:
    """The exercise's own {bench,squat,deadlift}_ratio for the anchor lift
    `field` maps to, if one has been set (>0). Returns None - "use the
    category default instead" - for exercises that haven't been migrated
    yet, exactly mirroring is_isolation's own reading of this same field in
    progression_engine.py (0.0 there means "never meant to be validated
    against, or loaded off, that compound max" - here it means "no
    exercise-specific override yet, fall back").
    """
    ratio_field = _RATIO_FIELD_BY_ANCHOR.get(field)
    if not ratio_field or not strength_requirements:
        return None
    value = strength_requirements.get(ratio_field)
    return value if value and value > 0 else None


def _unilateral_factor(strength_requirements: Optional[Dict]) -> float:
    """Per-exercise override (`unilateral_adjustment_factor`) if set,
    otherwise the global bridge default. Only ever consulted by callers
    that have already decided a unilateral discount is warranted (i.e. no
    exercise-specific ratio was available to trust instead) - see the
    module note.
    """
    if strength_requirements:
        override = strength_requirements.get("unilateral_adjustment_factor")
        if override and override > 0:
            return override
    return _UNILATERAL_ADJUSTMENT_FACTOR_DEFAULT

_PLATE_ROUNDING_KG = 2.5  # nearest practically-loadable barbell/machine-stack increment

# A pair of dumbbells (or one kettlebell in a single-arm movement) that's
# genuinely equal effort to a barbell lift is lighter, combined, than the
# barbell number - no fixed bar to brace against and share the load across
# both sides at once. ~40% of the barbell-equivalent total per implement is
# a standard coaching rule of thumb for converting barbell numbers to
# dumbbell numbers (some use a 40-50% range depending on the lift; 0.40
# stays on the conservative/safer side rather than over-loading someone).
_DB_KB_LOAD_RATIO = 0.40
_DUMBBELL_ROUNDING_KG = 2.0  # typical fixed dumbbell rack increment
# Kettlebells are cast in a small standard set of sizes, not sold in smooth
# increments - rounding to the nearest *real* size (instead of nearest 2kg)
# is what actually lets someone walk up and grab the right bell.
_KETTLEBELL_SIZES_KG = [4, 6, 8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 44, 48]


def _round_to_kettlebell(weight_kg: float) -> float:
    return float(min(_KETTLEBELL_SIZES_KG, key=lambda s: abs(s - weight_kg)))


def _estimated_vertical_pull_1rm(biometrics) -> Optional[float]:
    """Epley-style estimate of vertical-pull one-rep max straight from the
    person's own tested strict pull-up reps and bodyweight - a DIRECT
    measurement of the exact Vertical Pull pattern (pull-up, lat pulldown,
    assisted pull-up, cable pulldown all load the same
    lats/biceps/scapular-depression chain), not a cross-lift proxy.

    This is what add_working_weight now prefers over the deadlift*0.40
    anchor below whenever it's available - the actual bug report this
    fixes: pull-up strength doesn't reliably track deadlift (a hinge
    pattern, different muscle chain entirely), so an 80kg lifter doing 10
    strict pull-ups - proven capacity well above their own bodyweight -
    was still coming back with a ~32.5kg lat pulldown prescription, purely
    because the estimate was 40% of THEIR deadlift instead of anything
    measured about their actual pulling strength. pullups_max_reps is
    collected on UserBiometrics specifically for this pattern and
    previously wasn't used for load prescription at all.

    Returns None (falls back to the deadlift anchor) when no pull-up reps
    or bodyweight are on file - can't estimate what wasn't tested.
    """
    if not biometrics:
        return None
    reps = getattr(biometrics, "pullups_max_reps", None) or 0
    bodyweight = getattr(biometrics, "weight_kg", None) or 0.0
    if reps <= 0 or bodyweight <= 0:
        return None
    # Epley: 1RM = load moved * (1 + reps/30). A strict pull-up moves the
    # full bodyweight, so this estimates the total load (bodyweight + any
    # added weight) the person could pull for one rep - directly
    # transferable to a lat pulldown/cable stack number.
    return bodyweight * (1 + reps / 30.0)


def add_working_weight(
    prescription: Dict, category: Optional[str], biometrics, equipment: Optional[str] = None,
    strength_requirements: Optional[Dict] = None, movement_type: Optional[str] = None,
) -> Dict:
    """Adds `working_weight_kg` (+`anchor_lift`/`weight_confidence`) to a
    strength OR carry prescription dict - never removing the underlying
    percentage (`load_pct_1rm` / `load_pct_bodyweight`), since that's still
    what a lifter needs if they've since tested a new max or changed
    bodyweight. Every other prescription type (bodyweight-strength,
    conditioning, isometric) has no percentage field to convert and is
    returned unchanged.

    `equipment` (the exercise's own equipment string, e.g. "Dumbbell",
    "Kettlebell", "Barbell") picks which rounding/per-implement conversion
    applies - see the module docstring's "EQUIPMENT-AWARE LOAD" section.
    Optional and defaults to barbell-style rounding for backward
    compatibility with any caller that doesn't pass it.

    `strength_requirements` (the exercise's own strength_requirements dict
    from exercises.json) supplies the per-exercise ratio override and
    unilateral-adjustment override described in the module docstring's
    "PER-EXERCISE LOAD RATIO" / "UNILATERAL LOAD ADJUSTMENT" sections.
    `movement_type` ("Bilateral"/"Unilateral"/"Alternating") decides
    whether the unilateral discount applies at all. Both optional and
    default to None - a caller that doesn't pass them gets the same
    category-flat behavior as before these sections existed.

    Returns the prescription unchanged (no weight added) whenever the anchor
    isn't available - no biometrics entered, or this category's specific
    anchor lift is zero/missing. Leaving the percentage as the only output in
    that case is the same "prove it first" convention `main.py`'s
    `evaluate_biometrics_and_strength` already uses rather than guessing.
    """
    if prescription.get("type") == "carry":
        return _add_carry_weight(prescription, biometrics, equipment)
    if prescription.get("type") != "strength" or not category:
        return prescription

    pct = prescription.get("load_pct_1rm")
    if pct is None:
        return prescription

    # Vertical Pull gets its own direct anchor - see
    # _estimated_vertical_pull_1rm docstring for the bug this fixes. Tried
    # first and, when pull-up data exists, used INSTEAD of the generic
    # deadlift-ratio anchor below (not blended with it - a direct
    # measurement of this exact pattern beats a cross-lift estimate).
    # Falls through to the normal deadlift-anchor path only when no
    # pull-up reps are on file, so nothing changes for a person who hasn't
    # entered that number.
    if category == "Vertical Pull":
        pull_1rm = _estimated_vertical_pull_1rm(biometrics)
        if pull_1rm:
            raw_weight = pull_1rm * pct / 100.0
            # AUDIT FIX: this branch used to skip the dumbbell/kettlebell
            # per-implement conversion every other category gets below,
            # always rounding as a barbell-style combined total. No real
            # Vertical Pull exercise in the current database hits this
            # (Dumbbell-equipment ones are all curls, now correctly routed
            # to the isolation branch above this function instead), but a
            # future Kettlebell-assisted pulldown or similar would have
            # silently shown a combined-total number instead of a
            # per-implement one. Mirrors the generic path's equipment
            # handling exactly.
            equipment_lower = (equipment or "").lower()
            per_implement = None
            if "dumbbell" in equipment_lower:
                raw_weight *= _DB_KB_LOAD_RATIO
                working_weight = round(raw_weight / _DUMBBELL_ROUNDING_KG) * _DUMBBELL_ROUNDING_KG
                per_implement = "per dumbbell"
            elif "kettlebell" in equipment_lower:
                raw_weight *= _DB_KB_LOAD_RATIO
                working_weight = _round_to_kettlebell(raw_weight)
                per_implement = "per kettlebell"
            else:
                working_weight = round(raw_weight / _PLATE_ROUNDING_KG) * _PLATE_ROUNDING_KG
            result = dict(prescription)
            result["working_weight_kg"] = round(working_weight, 1)
            result["anchor_lift"] = "Pull-ups"
            result["weight_confidence"] = "direct"
            if per_implement:
                result["load_basis"] = per_implement
            note = (
                "Estimated from your tested pull-up reps and bodyweight (Epley formula) - "
                "a direct read on this exact movement, not a cross-lift proxy."
            )
            if per_implement:
                note += f" Shown {per_implement}, not combined total."
            result["weight_note"] = note + " Adjust by feel."
            return result

    anchor = _ANCHOR_BY_CATEGORY.get(category)
    if not anchor or not biometrics:
        return prescription
    field, category_confidence, category_ratio = anchor
    max_kg = getattr(biometrics, field, None) or 0.0
    if max_kg <= 0:
        return prescription

    # Per-exercise override, when this exercise has one (see "PER-EXERCISE
    # LOAD RATIO" in the module docstring) - otherwise the flat category
    # default, same behavior as before this section existed.
    exercise_ratio = _exercise_ratio_override(strength_requirements, field)
    if exercise_ratio is not None:
        ratio = exercise_ratio
        # An exercise-specific ratio is a real per-exercise calibration,
        # not the category's blanket assumption - always "estimated"
        # (never silently upgraded to "direct") since it's still not a
        # tested max for this exact movement, same caveat the category
        # path already carried for its non-1.00 ratios.
        confidence = "estimated"
        ratio_is_exercise_specific = True
    else:
        ratio = category_ratio
        confidence = category_confidence
        ratio_is_exercise_specific = False

    raw_weight = max_kg * ratio * pct / 100.0

    # Unilateral discount (see "UNILATERAL LOAD ADJUSTMENT" in the module
    # docstring) - only when no exercise-specific ratio already accounts
    # for it, to avoid stacking a second discount on top of a number
    # someone already hand-tuned for this exact movement.
    unilateral_adjusted = movement_type == "Unilateral" and not ratio_is_exercise_specific
    equipment_lower = (equipment or "").lower()
    if unilateral_adjusted and "dumbbell" not in equipment_lower and "kettlebell" not in equipment_lower:
        raw_weight *= _unilateral_factor(strength_requirements)
    else:
        unilateral_adjusted = False

    per_implement = None
    if "dumbbell" in equipment_lower:
        raw_weight *= _DB_KB_LOAD_RATIO
        working_weight = round(raw_weight / _DUMBBELL_ROUNDING_KG) * _DUMBBELL_ROUNDING_KG
        per_implement = "per dumbbell"
    elif "kettlebell" in equipment_lower:
        raw_weight *= _DB_KB_LOAD_RATIO
        working_weight = _round_to_kettlebell(raw_weight)
        per_implement = "per kettlebell"
    else:
        working_weight = round(raw_weight / _PLATE_ROUNDING_KG) * _PLATE_ROUNDING_KG

    result = dict(prescription)
    result["working_weight_kg"] = round(working_weight, 1)
    result["anchor_lift"] = _ANCHOR_LABEL[field]
    result["weight_confidence"] = confidence
    if per_implement:
        result["load_basis"] = per_implement
    if confidence == "estimated" or per_implement or unilateral_adjusted:
        pieces = []
        if ratio != 1.00:
            basis = (
                "based on this specific exercise, not just its movement category"
                if ratio_is_exercise_specific
                else "no tested max for this pattern - a real proxy, not a direct measurement"
            )
            pieces.append(f"estimated at ~{round(ratio * 100)}% of your {_ANCHOR_LABEL[field]} 1RM ({basis})")
        if unilateral_adjusted:
            pieces.append("adjusted for single-arm/single-leg loading")
        if per_implement:
            pieces.append(f"shown {per_implement}, not combined total")
        result["weight_note"] = "; ".join(pieces).capitalize() + ". Adjust by feel."
    return result


# Carry implements (kettlebells, farmer handles, plates) are usually loadable
# in coarser jumps than a barbell - 2.5kg plate-rounding implies a precision
# these tools don't actually offer. 5kg still lands on something realistic
# to grab off a rack while staying close to the prescribed %bodyweight.
_CARRY_ROUNDING_KG = 5.0


def _add_carry_weight(prescription: Dict, biometrics, equipment: Optional[str] = None) -> Dict:
    """Converts a Carry prescription's `load_pct_bodyweight` (+`load_basis`,
    "total load carried" or "per hand" - see progression_engine._prescribe_volume)
    into an actual working_weight_kg, off the person's own tested bodyweight -
    the only anchor a carry exercise actually has, since there's no 1RM for a
    farmer's walk. Bodyweight is a required field on UserBiometrics whenever
    biometrics is supplied at all, so - unlike the strength-lift anchors,
    which can be individually missing - this only ever skips when biometrics
    itself wasn't provided.

    Same equipment-aware rounding as add_working_weight above: a Kettlebell
    or Dumbbell carry (e.g. Suitcase Carry, Dumbbell Farmer's Carry) rounds
    to a real implement size instead of an arbitrary 5kg jump meant for
    farmer handles/plates/sandbags.
    """
    pct = prescription.get("load_pct_bodyweight")
    if pct is None or not biometrics:
        return prescription
    weight_kg = getattr(biometrics, "weight_kg", None) or 0.0
    if weight_kg <= 0:
        return prescription

    raw_weight = weight_kg * pct / 100.0
    equipment_lower = (equipment or "").lower()
    if "kettlebell" in equipment_lower:
        working_weight = _round_to_kettlebell(raw_weight)
    elif "dumbbell" in equipment_lower:
        working_weight = round(raw_weight / _DUMBBELL_ROUNDING_KG) * _DUMBBELL_ROUNDING_KG
    else:
        working_weight = round(raw_weight / _CARRY_ROUNDING_KG) * _CARRY_ROUNDING_KG

    result = dict(prescription)
    result["working_weight_kg"] = round(working_weight, 1)
    result["anchor_lift"] = "Bodyweight"
    result["weight_confidence"] = "direct"
    result["weight_note"] = (
        f"~{pct}% of your bodyweight ({prescription.get('load_basis', 'total load carried')}) - "
        "a starting point, not a rule; load whatever implement is closest and adjust by feel."
    )
    return result


def missing_anchor_note(category: Optional[str], biometrics) -> Optional[str]:
    """Message the frontend can show in place of a weight when this
    category *has* an anchor mapping but biometrics doesn't have that lift
    entered - e.g. "Add your Squat 1RM to see this in kg instead of %."
    Returns None whenever a weight was (or could never be) shown, so callers
    don't have to re-do the anchor lookup themselves to decide whether to
    display this.

    Vertical Pull is checked against its own direct pull-up anchor first
    (see _estimated_vertical_pull_1rm) - a person who's entered pull-up
    reps + bodyweight already has a weight shown for this category via
    that path, so telling them to also "add your Deadlift 1RM" would be
    misleading (add_working_weight never even looks at deadlift for them).
    """
    if category == "Vertical Pull" and _estimated_vertical_pull_1rm(biometrics):
        return None
    anchor = _ANCHOR_BY_CATEGORY.get(category or "")
    if not anchor:
        return None
    field, _, _ = anchor
    max_kg = getattr(biometrics, field, None) if biometrics else None
    if max_kg and max_kg > 0:
        return None
    if category == "Vertical Pull":
        return "Add your tested pull-up reps (or your Deadlift 1RM) in biometrics to see this prescribed in kg instead of %."
    return f"Add your {_ANCHOR_LABEL[field]} 1RM in biometrics to see this prescribed in kg instead of %."

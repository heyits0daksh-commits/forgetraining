"""
Injury taxonomy — v5.0 comprehensive musculoskeletal injury library.

WHAT THIS FILE IS
Maps specific, named injuries (as a user would actually describe their
problem, e.g. "ACL Tear - Grade 3 (Complete Rupture)") to structured metadata
used to filter/adapt exercise prescription: which joint it affects, how
severe it is, what to avoid, what progression/return-to-sport looks like,
and so on.

BACKWARD COMPATIBILITY (v3.0 -> v4.0 -> v5.0)
The engine (backend/main.py, backend/services/knowledge_graph.py) has only
ever read two keys off each entry: `entry["joint"]` and `entry["severity"]`.
That contract is unchanged here — every entry, old or new, still carries
those two keys with the same meaning and the same 1/2/3 severity scale, so
nothing downstream needs to change. Everything else below (~28 extra fields
per entry) is additive: richer reference/decision-support data that the
current engine doesn't read yet, but that a future UI, rehab-candidacy
scorer, or clinician-facing view can.

SEVERITY TIERS (unchanged from v4.0)
    3 = Severe   — structural failure: complete ruptures/tears, dislocations,
                   fractures, advanced collapse, cord/nerve involvement. The
                   joint cannot be trusted under any real load. Every
                   exercise stressing this joint is excluded outright.
    2 = Moderate — partial tears, subluxation, Grade 2 sprains, marginal/
                   displaced fractures. Light, controlled work only
                   (difficulty 3+ excluded).
    1 = Mild     — Grade 1 sprains/strains, fraying, early degeneration,
                   stable injuries. Most training tolerated; only the
                   highest-demand movements (difficulty 4+) excluded.

EXTENSIBILITY
The requirement driving this file's structure is that new injuries, new
exercises, and new movement patterns must be addable *without touching the
core decision engine* (classify_injury_risk / find_alternatives / main.py).
That's achieved two ways:
  1. Every field beyond joint/severity is inert as far as the engine is
     concerned — adding fields, or whole new injuries, never changes how
     filtering behaves unless main.py is explicitly updated to read them.
  2. Large, structurally repetitive families (muscle strains across every
     major muscle group, ligament sprains across every major joint, tendon
     injuries across every major tendon) are generated from small data
     tables (MUSCLE_GROUPS, LIGAMENTS, TENDONS below) plus a builder
     function, rather than hand-duplicated. Adding a new muscle/ligament/
     tendon to those tables — or a new named condition to
     NAMED_CONDITIONS — is the entire diff needed to add a fully-specified
     injury entry.

`joint` values are deliberately kept aligned with the joint_stress vocabulary
already used in exercises.json (Wrist, Elbow, Shoulder, Neck, Lower Back,
Hip, Knee, Ankle) — those are the only 8 tags exercises.json actually carries
— so no changes to exercises.json are required. Injuries whose tissue doesn't
map to one of those 8 1:1 (e.g. thoracic spine, TMJ, forearm compartments)
are assigned the closest functionally-relevant tag; this is noted per entry
via the `region` field, which is free-text and carries the real anatomical
detail the 8-tag `joint` field can't.

v5.11 ADDITION
Added 11 new named conditions (Concussion x3 grades, Rib Fracture x2,
Intercostal Muscle Strain x2 grades, Costochondritis, Sports Hernia) covering
head/thorax injuries relevant to the combat and collision sports this app
targets (Boxing, Muay Thai, MMA, Wrestling, BJJ, Judo, Sanda, Rugby) that
nothing here covered before. Also added 8 severity-1 "umbrella" entries
(Low Back Pain, Lower Back Strain, Neck Pain, Wrist Pain, Rotator Cuff,
Achilles, Patellar Tendon, Hamstring Strain) whose exact names match
non-specific/ungraded tags that were already in use across
data/exercises.json's injuries_to_avoid field but had no taxonomy entry at
all — see "Bare/vernacular umbrella terms" below for why those are kept
separate from (rather than merged into) the graded conditions they relate
to. 7 other previously-unmatched exercises.json tags were near-duplicates of
an existing entry under different formatting and were renamed in
exercises.json itself instead (e.g. "Tennis Elbow" -> "Lateral
Epicondylalgia (Tennis Elbow)") — see data/exercises.json's v5.11
schema_notes for the full list. Total taxonomy size: 364 -> 381 entries.

CLINICAL DISCLAIMER
This is a *programming heuristic layer* for an exercise-prescription app —
it is not a diagnostic tool and isn't a substitute for evaluation by a
qualified clinician (physician, physical therapist, athletic trainer). Field
content (healing phases, red flags, return-to-sport criteria, etc.) reflects
general, widely-taught rehabilitation principles for each injury category,
not an individualized medical assessment. Anyone with a suspected injury —
especially anything flagged severity 3 or listed under `clinical_red_flags`
— should be directed to seek appropriate medical evaluation before an
exercise program (including one FORGE generates) is treated as clearance to
train.
"""

from typing import Dict, List, Optional, Tuple

from backend.core.cache import cache_forever
from backend.services.exercise_metadata import derive_tissue_demands
from backend.services.sport_profiles import INJURY_JOINT_PREFERRED_EQUIPMENT

# ============================================================================
# SCHEMA
# ============================================================================
# Every entry in INJURY_TAXONOMY carries these keys. `joint` and `severity`
# are load-bearing for the engine; everything else is reference/decision-
# support metadata.
INJURY_FIELDS = [
    "name", "alt_names", "tissue", "joint", "region", "severity",
    "severity_grades", "healing_phases", "pain_pattern", "mechanism",
    "movement_restrictions", "joint_position_restrictions", "rom_restrictions",
    "loading_restrictions", "velocity_restrictions", "impact_restrictions",
    "technical_faults_to_avoid", "biomechanical_stresses_to_avoid",
    "muscles_to_protect", "muscles_to_strengthen", "safe_movement_patterns",
    "contraindicated_movement_patterns", "exercise_modifications",
    "progression_criteria", "regression_criteria", "return_to_sport_criteria",
    "absolute_contraindications", "relative_contraindications",
    "clinical_red_flags", "risk_score_logic", "systemic",
]


# ============================================================================
# DIFFICULTY CEILING (unchanged from v4.0) — an exercise whose difficulty
# exceeds the ceiling for a joint the user has flagged is excluded. Severity
# 3 has no ceiling (None = block every difficulty, i.e. avoid the joint
# entirely).
# ============================================================================
SEVERITY_DIFFICULTY_CEILING = {
    1: 3,     # mild: only the top two difficulty tiers (4, 5) are excluded
    2: 2,     # moderate: only light/rehab-level work (1-2) is allowed
    3: None,  # severe: joint is excluded outright, no difficulty is safe
}


# ==========================================================================
# INJURY INTELLIGENCE — four-tier risk model (v4.0 severity/difficulty core,
# unchanged; v5.12 adds an optional tissue-demand refinement on top)
# ==========================================================================
RiskTier = str  # Literal["safe", "caution", "high_risk", "contraindicated"]


# ==========================================================================
# TISSUE-DEMAND SENSITIVITY (v5.12) — which of exercise_metadata's derived
# demand flags (see derive_tissue_demands()'s docstring for exactly what
# each one means and how it's computed) a given tissue TYPE is, in general,
# more sensitive to reloading. This is standard, widely-taught tissue-
# mechanics/rehab-programming knowledge (the same reasoning behind e.g.
# graduated open- vs. closed-chain progressions in ACL rehab, or restricting
# impact loading during a bone stress injury) applied at the tissue-type
# level, not a diagnostic claim about any specific named injury - the same
# "derive from the general category, not hand-type per entry" approach the
# rest of this file already uses for healing_phases (see _phases()).
#
# Deliberately keyed by `tissue`, not by individual injury name: adding a
# new named injury under an existing tissue type (e.g. a new ligament
# sprain) automatically gets the right sensitivity profile with zero
# changes here, matching this file's stated extensibility goal.
# ==========================================================================
TISSUE_DEMAND_SENSITIVITY: Dict[str, List[str]] = {
    "Muscle": ["high_eccentric", "high_velocity", "large_rom_demand"],
    "Tendon": ["high_eccentric", "high_velocity", "high_impact"],
    "Ligament": ["high_shear", "high_rotation", "frontal_plane_loading", "large_rom_demand", "high_instability"],
    "Joint": ["high_compression", "large_rom_demand", "high_instability", "high_rotation"],
    "Cartilage": ["high_compression", "high_shear", "high_rotation"],
    "Bone": ["high_impact", "high_compression"],
    "Spine": ["high_compression", "high_shear", "high_rotation"],
    "Nerve": ["large_rom_demand", "high_instability"],
    "Fascia": ["high_eccentric", "large_rom_demand"],
}
# Escalate a tier (safe->caution, caution->high_risk) only once at least
# this many tissue-relevant demand flags are present - a single matching
# axis is common enough (most exercises trip at least one) that requiring
# 2+ keeps this a meaningful signal rather than escalating almost everything.
_DEMAND_ESCALATION_THRESHOLD = 2
_TIER_ESCALATION = {"safe": "caution", "caution": "high_risk"}

# ==========================================================================
# PRESSING / TENDON-COMPRESSION OVERRIDE (v5.24) — the difficulty-ceiling
# model above treats "difficulty" as technical/coordinative complexity, so a
# mechanically simple lift (Flat Bench Press, difficulty 2) reads as no more
# risky than any other difficulty-2 exercise even though pressing is
# specifically what drives subacromial compression/impingement - the actual
# aggravating mechanism for a rotator cuff (or long head biceps) tendon
# injury, independent of how technically easy the lift is to perform. The
# generic tissue-demand escalation above can't catch this either: "Tendon"'s
# TISSUE_DEMAND_SENSITIVITY axes were tuned for degenerative overuse tendon
# injuries (Achilles/patellar - eccentric/velocity/impact sensitive), not
# impingement-type shoulder tendon injuries, and even adding a compression
# axis there would need 2 matched axes (_DEMAND_ESCALATION_THRESHOLD) to
# move the needle - pressing exercises typically only trip one.
#
# Product decision (explicit, not inferred): for a Shoulder tendon injury
# (tissue == "Tendon" - i.e. the Rotator Cuff Tear / Tendinopathy / Long
# Head Biceps Tendon entries, not e.g. a labral or AC-joint injury, which
# have a different mechanism), a pressing-pattern exercise (Horizontal Push
# / Vertical Push category - bench press, overhead press, dips) is:
#   severity 1 (mild)      -> always at least "caution" (never a silent
#                              "safe", regardless of the lift's difficulty)
#   severity 2+ (moderate+) -> always "contraindicated" (blocked outright,
#                              regardless of difficulty) - severity 3 already
#                              hits this via the severity>=3 check above;
#                              this extends the same hard block down to
#                              severity 2, where the difficulty-ceiling model
#                              alone would otherwise still allow a
#                              low-difficulty press through.
# This only ever makes the tier MORE restrictive (via _worse_tier), never
# loosens what the ceiling/tissue-escalation model already decided, and only
# fires for the specific (Shoulder, Tendon, pressing-pattern) combination -
# it leaves every other joint/tissue/exercise combination unaffected.
# ==========================================================================
PRESSING_CATEGORIES = {"Horizontal Push", "Vertical Push"}


def _pressing_tendon_override(severity: int, tissue: Optional[str], exercise: Optional[dict]) -> Optional["RiskTier"]:
    """See module comment above. Returns None (no opinion - caller keeps
    whatever tier it already had) unless this is specifically a Shoulder
    tendon injury and a pressing-pattern exercise."""
    if tissue != "Tendon" or exercise is None:
        return None
    if exercise.get("category") not in PRESSING_CATEGORIES:
        return None
    if "Shoulder" not in (exercise.get("joint_stress") or []):
        return None
    if severity >= 2:
        return "contraindicated"
    if severity == 1:
        return "caution"
    return None


def _matched_demand_axes(tissue: Optional[str], exercise: Optional[dict]) -> int:
    """How many of `tissue`'s TISSUE_DEMAND_SENSITIVITY axes this exercise's
    own derived demand profile (exercise_metadata.derive_tissue_demands)
    actually trips. Shared by classify_injury_risk's escalation and
    classify_exercise_safety's color below, so the two can never drift
    apart on what counts as "this exercise stresses this tissue's known
    weak point." Returns 0 (never matches) for an unrecognized tissue or a
    missing exercise, same as omitting tissue/exercise entirely."""
    if not tissue or exercise is None:
        return 0
    sensitive_axes = TISSUE_DEMAND_SENSITIVITY.get(tissue)
    if not sensitive_axes:
        return 0
    demands = derive_tissue_demands(exercise)
    return sum(1 for axis in sensitive_axes if demands.get(axis))


# ==========================================================================
# REHAB STAGE PROGRESSION (v5.14) — models WHERE in the recovery timeline an
# injury currently is, layered on top of (not replacing) the static
# severity -> difficulty-ceiling model above. Severity classifies how bad
# the injury *is*; stage classifies how far the person has progressed
# through rehabbing it. Six stages, matching the ones real return-to-sport
# protocols use for soft-tissue/joint rehab:
#   early_recovery         - protect the tissue; pain/symptom control only
#   controlled_loading     - progressive pain-free ROM + light resistance
#   strength_rebuilding    - progressive loading back toward working loads
#   advanced_strength      - heavier, closer-to-normal strength work
#   plyometric_reactive    - stretch-shortening-cycle/reactive/impact work
#                            reintroduced
#   return_to_performance  - full sport-specific loading
#
# Deliberately opt-in and additive, the same way v5.12's tissue-demand
# escalation is: `stage` is an optional kwarg on classify_injury_risk /
# classify_exercise_safety (default None). Omitting it reproduces the exact
# pre-v5.14 severity-only behavior for every existing call site/test -
# stage only ever narrows what severity+difficulty already allowed, never
# loosens past it. Severity 3 (structural failure) is never unblocked by a
# self-reported stage: classify_injury_risk returns "contraindicated" for
# severity >= 3 before stage is ever consulted, matching this file's own
# SEVERITY TIERS docstring ("the joint cannot be trusted under any real
# load") and the CLINICAL DISCLAIMER's "clinician-directed" rehab loading
# for severity 3 - an actual clinician decides that, not a self-reported
# stage in this app.
#
# Two things per stage, generated from small tables (the same pattern this
# file already uses for _phases()/TISSUE_DEMAND_SENSITIVITY, not
# hand-authored per injury):
#   REHAB_STAGE_CEILING      - a difficulty ceiling on the same 1-5 scale as
#                              SEVERITY_DIFFICULTY_CEILING. The effective
#                              ceiling is min(stage ceiling, severity
#                              ceiling) - stage can tighten a severity
#                              ceiling but can never loosen past it.
#   REHAB_STAGE_BLOCKED_AXES - which of exercise_metadata.derive_tissue_
#                              demands()'s flags are hard-blocked (i.e.
#                              force "contraindicated") at that stage,
#                              regardless of difficulty. Only axes the
#                              injury's own tissue is actually sensitive to
#                              (TISSUE_DEMAND_SENSITIVITY) apply - this is
#                              the mechanism that keeps plyometric/reactive
#                              work (high_impact/high_velocity/high_
#                              eccentric) out of a session until the person
#                              has actually reached a stage meant to
#                              reintroduce it, independent of how generous
#                              that stage's raw difficulty ceiling is.
# ==========================================================================
REHAB_STAGES: List[str] = [
    "early_recovery",
    "controlled_loading",
    "strength_rebuilding",
    "advanced_strength",
    "plyometric_reactive",
    "return_to_performance",
]

REHAB_STAGE_LABEL: Dict[str, str] = {
    "early_recovery": "Early Recovery",
    "controlled_loading": "Controlled Loading",
    "strength_rebuilding": "Strength Rebuilding",
    "advanced_strength": "Advanced Strength",
    "plyometric_reactive": "Plyometric / Reactive",
    "return_to_performance": "Return to Performance",
}

REHAB_STAGE_DESCRIPTION: Dict[str, str] = {
    "early_recovery": "Protect the tissue; pain/symptom control and pain-free motion only.",
    "controlled_loading": "Progressive pain-free ROM plus light, controlled resistance.",
    "strength_rebuilding": "Progressive resistance work, rebuilding toward normal working loads.",
    "advanced_strength": "Heavier, closer-to-normal strength work; still no reactive/impact loading.",
    "plyometric_reactive": "Stretch-shortening-cycle and reactive/impact demand reintroduced progressively.",
    "return_to_performance": "Full sport-specific loading, including plyometric/reactive and impact demand.",
}

# Same 1-5 scale as SEVERITY_DIFFICULTY_CEILING.
REHAB_STAGE_CEILING: Dict[str, int] = {
    "early_recovery": 1,
    "controlled_loading": 2,
    "strength_rebuilding": 3,
    "advanced_strength": 4,
    "plyometric_reactive": 4,
    "return_to_performance": 5,
}

REHAB_STAGE_BLOCKED_AXES: Dict[str, List[str]] = {
    "early_recovery": [
        "high_impact", "high_velocity", "high_eccentric",
        "high_instability", "high_rotation", "large_rom_demand",
    ],
    "controlled_loading": ["high_impact", "high_velocity", "high_eccentric"],
    "strength_rebuilding": ["high_impact", "high_velocity"],
    "advanced_strength": ["high_impact"],
    "plyometric_reactive": [],
    "return_to_performance": [],
}

# Only used when a caller opts into the stage gate but doesn't say which
# stage the person is actually in - a reasonable default starting point per
# severity tier, not a claim about how long recovery actually takes.
DEFAULT_REHAB_STAGE_FOR_SEVERITY: Dict[int, str] = {
    1: "strength_rebuilding",
    2: "controlled_loading",
    3: "early_recovery",
}

_REHAB_TIER_ORDER = ["safe", "caution", "high_risk", "contraindicated"]


def resolve_rehab_stage(severity: int, stage: Optional[str] = None) -> str:
    """The stage to actually gate against: the caller's explicit stage if
    it's a recognized one, else the default starting stage for this
    severity tier."""
    if stage in REHAB_STAGE_CEILING:
        return stage
    return DEFAULT_REHAB_STAGE_FOR_SEVERITY.get(severity, "early_recovery")


def resolve_systemic_injury(
    user_injuries: set, injury_stages: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[int], Optional[str]]:
    """(v5.16, expanded v5.30) Worst-severity match among the user's
    injuries that's flagged `systemic=True` - the three concussion grades,
    plus (v5.30) both acute compartment syndrome entries, three unstable/
    emergency spine entries (unstable lumbar fracture, massive central disc
    herniation, burst fracture), spinal cord injury, bilateral cervical
    facet dislocation, and displaced/flail-chest rib fracture - see
    _generic's/`_muscle_condition`'s `systemic` param docstring for why
    these need separate handling from every other injury here. Every other
    injury only restricts exercises whose
    joint_stress includes the joint it's mapped to (e.g. a knee injury never
    touches a bench press); a systemic injury restricts every exercise in
    the session by its own severity/stage, regardless of which joints that
    exercise happens to tag, because what makes it unsafe is exertion in
    general, not loading one specific joint.

    Mirrors progression_engine._resolve_injury_severity/_resolve_injury_stage's
    {joint: ...} resolution, collapsed to one severity/stage since a
    systemic injury isn't scoped to a joint. `user_injuries` is the same
    lower-cased injury-name set those resolvers take; `injury_stages` is the
    same optional {injury_string: stage} shape (WorkoutRequest.injury_stages),
    case-insensitive. Returns (None, None) when nothing matched is systemic
    - callers pass that straight to classify_injury_risk's existing
    severity/stage params, which already no-op on None, so this is inert for
    every caller/test that predates it."""
    taxonomy_lower = {name.lower(): info for name, info in INJURY_TAXONOMY.items()}
    stage_by_injury = {k.strip().lower(): v for k, v in (injury_stages or {}).items()}
    best_severity: Optional[int] = None
    best_stage: Optional[str] = None
    for inj in user_injuries:
        entry = taxonomy_lower.get(inj)
        if entry is None or not entry.get("systemic"):
            continue
        severity = entry["severity"]
        if best_severity is None or severity >= best_severity:
            best_severity = severity
            stage = stage_by_injury.get(inj)
            best_stage = stage if stage in REHAB_STAGES else None
    return best_severity, best_stage


def resolve_severe_injuries(user_injuries: set) -> List[dict]:
    """(v5.18) Every taxonomy-matched entry among the user's reported
    injuries whose `severity == 3` - regardless of which joint it maps to
    or whether it's flagged `systemic`. This is the whole-PROGRAM gate:
    unlike the per-joint difficulty ceiling above (which only removes
    exercises that load the injured joint, so a severe knee injury still
    lets someone train their upper body) and unlike resolve_systemic_injury
    (which only fires for the handful of entries explicitly flagged
    systemic, e.g. concussion), this is the "any severity-3 injury on file
    means no program is generated at all, full stop, until a clinician
    clears them" rule - the intended reading of SEVERITY_DIFFICULTY_CEILING's
    "the joint cannot be trusted under any real load" language extended to
    the whole plan rather than just that joint's exercises.

    Returns one dict per matched severe injury (empty list if none match):
        {"name": <taxonomy key>, "joint": ..., "region": ...,
         "clinical_red_flags": [...]}
    sorted by name for deterministic output/messages. Callers (currently
    just ProgressionEngine.generate_session) use a non-empty return to
    short-circuit generation entirely, before any exercise selection runs,
    and surface `clinical_red_flags` verbatim in the block message so the
    person sees *why* - not just that they're blocked."""
    taxonomy_lower = {name.lower(): (name, info) for name, info in INJURY_TAXONOMY.items()}
    matches = []
    seen = set()
    for inj in user_injuries:
        hit = taxonomy_lower.get(inj)
        if hit is None:
            continue
        name, entry = hit
        if entry["severity"] != 3 or name in seen:
            continue
        seen.add(name)
        matches.append({
            "name": name,
            "joint": entry["joint"],
            "region": entry.get("region", ""),
            "clinical_red_flags": entry.get("clinical_red_flags") or [],
        })
    return sorted(matches, key=lambda m: m["name"])


def _worse_tier(a: RiskTier, b: RiskTier) -> RiskTier:
    """The more restrictive of two tiers - safe < caution < high_risk <
    contraindicated, same ordering worst_safety_color uses for colors."""
    return max([a, b], key=_REHAB_TIER_ORDER.index)


def _tier_for_ceiling(ceiling: Optional[int], difficulty: int) -> RiskTier:
    if ceiling is None:
        return "contraindicated"
    if difficulty <= ceiling - 1:
        return "safe"
    if difficulty == ceiling:
        return "caution"
    if difficulty == ceiling + 1:
        return "high_risk"
    return "contraindicated"


def _rehab_stage_tier(
    severity: int,
    severity_ceiling: int,
    difficulty: int,
    stage: str,
    tissue: Optional[str],
    exercise: Optional[dict],
) -> RiskTier:
    """The tier `stage` alone implies, independent of whatever tier severity
    already computed: "contraindicated" if the exercise trips a demand axis
    this stage blocks for this tissue (e.g. a plyometric exercise during
    early_recovery), else a ceiling-based tier off
    min(stage ceiling, severity ceiling) - so stage can tighten a severity
    ceiling but never loosen past it."""
    resolved = resolve_rehab_stage(severity, stage)

    if tissue and exercise is not None:
        blocked = set(REHAB_STAGE_BLOCKED_AXES.get(resolved, []))
        sensitive = set(TISSUE_DEMAND_SENSITIVITY.get(tissue, []))
        relevant = blocked & sensitive
        if relevant:
            demands = derive_tissue_demands(exercise)
            if any(demands.get(axis) for axis in relevant):
                return "contraindicated"

    stage_ceiling = min(REHAB_STAGE_CEILING.get(resolved, severity_ceiling), severity_ceiling)
    return _tier_for_ceiling(stage_ceiling, difficulty)


def rehab_stage_reference() -> List[Dict]:
    """Ordered, UI-ready description of the six rehab stages - what
    `/api/v1/metadata`'s `rehab_stages` key returns."""
    return [
        {
            "stage": stage,
            "label": REHAB_STAGE_LABEL[stage],
            "description": REHAB_STAGE_DESCRIPTION[stage],
            "difficulty_ceiling": REHAB_STAGE_CEILING[stage],
        }
        for stage in REHAB_STAGES
    ]


# ==========================================================================
# LATERALITY (v5.15) — an injury isn't just "which joint" and "how bad", it
# can also be one-sided ("left", "right") or affect both ("bilateral").
# That distinction only changes anything for exercises whose data already
# says the two limbs are trained independently (`movement_type ==
# "Unilateral"` - e.g. Single-Leg Leg Press, Single-Arm Dumbbell Row, Pistol
# Squat: a set is performed one side at a time, so the person can simply
# train the uninjured side and skip the injured one entirely).
#
# "Alternating" exercises (Walking Lunge, Farmer's Carry) do NOT get this
# treatment even though they also load one limb per rep - both legs/arms
# still work within the same set, so the injured side can't be skipped.
# Bilateral exercises (Back Squat, Bench Press) obviously can't either - a
# one-sided injury on a bilateral lift still loads that side every rep.
#
# This is purely a RELAXATION on top of the existing severity/difficulty
# model, and only fires when the caller actually supplies a one-sided
# `side` - omitting it (every pre-v5.15 call site) reproduces identical
# behavior. It also never touches severity 3: a structural failure still
# needs a clinician's sign-off before any loading of that joint, on either
# side, is programmed by this app - see this file's CLINICAL DISCLAIMER.
# ==========================================================================
INJURY_SIDES: List[str] = ["left", "right", "bilateral"]
OPPOSITE_SIDE: Dict[str, str] = {"left": "right", "right": "left"}

# v5.19 — which injuries can even BE "left" or "right" in the first place.
# Laterality (a paired muscle group, ligament, or tendon that the body has
# one of on each side - e.g. Trapezius, ACL, Rotator Cuff Tendons) only
# makes sense for the limb/joint tags (Wrist/Elbow/Shoulder/Hip/Knee/Ankle).
# The spine (this taxonomy's `joint` tag is "Neck" or "Lower Back" - see
# this module's docstring on how cervical/thoracic/lumbar structures map
# onto those 8 tags) is a single midline column, not a left/right pair, so
# a side picker doesn't apply there regardless of tissue type - not even
# for an entry like Trapezius Strain or Erector Spinae Strain, which are
# nominally "Muscle" tissue but are grouped under the spine joint tags.
# This gates the UI (grouped_injury_taxonomy's per-grade
# `laterality_applicable`) AND the engine (_resolve_injury_side below), so
# a stale/hand-built request can't smuggle a side onto a spine injury
# either.
SPINE_JOINTS = {"Neck", "Lower Back"}


def laterality_applicable(entry: dict) -> bool:
    """True when a left/right/bilateral side selection is meaningful for
    this taxonomy entry - i.e. it isn't part of the spine. See the module
    note above."""
    return entry.get("joint") not in SPINE_JOINTS


def _unilateral_capable(exercise: Optional[dict]) -> bool:
    """True when this exercise's own data already says a set is trained one
    side at a time - the only case where "skip the injured side" is a real,
    prescribable option rather than a guess about how someone might modify
    the movement on their own."""
    return bool(exercise) and exercise.get("movement_type") == "Unilateral"


def laterality_clears_joint(side: Optional[str], severity: int, exercise: Optional[dict]) -> bool:
    """Does a one-sided injury, on a side-selectable exercise, neutralize
    this joint's contribution to the risk check entirely? Severity 3 is
    deliberately excluded - see module note above."""
    return side in ("left", "right") and severity < 3 and _unilateral_capable(exercise)


def classify_injury_risk(
    severity: int,
    difficulty: int,
    tissue: Optional[str] = None,
    exercise: Optional[dict] = None,
    stage: Optional[str] = None,
    side: Optional[str] = None,
) -> RiskTier:
    """Classify how risky a given exercise is for a joint injury of the given
    severity tier. Base classification is the unchanged v4.0 pure function of
    severity + difficulty, so every existing 2-argument call site (and every
    test) behaves exactly as before.

    `tissue` + `exercise` are optional (v5.12): when both are supplied, the
    base tier can be escalated (never de-escalated - this only adds
    caution/exclusion, never removes an existing protection) if the
    exercise's own demand profile (see exercise_metadata.derive_tissue_demands)
    hits enough axes that tissue type is generally sensitive to. Omitting
    either argument reproduces the exact pre-v5.12 behavior.

    `stage` is optional (v5.14, see the REHAB STAGE PROGRESSION section
    above): when supplied, the tier can only be held or made MORE
    restrictive, never loosened, by the person's self-reported rehab stage
    - see _rehab_stage_tier. Omitting it reproduces the exact pre-v5.14
    behavior.

    `side` is optional (v5.15, "left"/"right"/"bilateral"): when the injury
    is one-sided and `exercise` is side-selectable (see
    laterality_clears_joint above), this joint's risk check is bypassed
    entirely ("safe") - the person trains the uninjured side only. Omitting
    it, or a "bilateral" injury, reproduces the exact pre-v5.15 behavior.
    """
    if laterality_clears_joint(side, severity, exercise):
        return "safe"

    if severity >= 3:
        return "contraindicated"

    ceiling = SEVERITY_DIFFICULTY_CEILING.get(severity)
    if ceiling is None:
        return "contraindicated"

    if difficulty <= ceiling - 1:
        tier = "safe"
    elif difficulty == ceiling:
        tier = "caution"
    elif difficulty == ceiling + 1:
        tier = "high_risk"
    else:
        return "contraindicated"

    if tissue and exercise is not None and tier in _TIER_ESCALATION:
        if _matched_demand_axes(tissue, exercise) >= _DEMAND_ESCALATION_THRESHOLD:
            tier = _TIER_ESCALATION[tier]

    if stage is not None:
        tier = _worse_tier(tier, _rehab_stage_tier(severity, ceiling, difficulty, stage, tissue, exercise))

    pressing_override = _pressing_tendon_override(severity, tissue, exercise)
    if pressing_override is not None:
        tier = _worse_tier(tier, pressing_override)

    return tier


# ==========================================================================
# GREEN / YELLOW / RED SAFETY CLASSIFICATION (v5.13) — a coach/athlete-facing
# label for "is this specific exercise appropriate for this specific
# injury", layered on top of (not a replacement for) the four-tier
# safe/caution/high_risk/contraindicated model above, which continues to
# drive prescription/exclusion exactly as before.
#
# DELIBERATELY NOT a severity->color lookup table (severity 1->GREEN,
# 2->YELLOW, 3->RED). That would throw away the one piece of information
# that actually determines whether a given exercise is a problem for a
# given injury: whether the exercise's own mechanical demands
# (derive_tissue_demands) land on the specific axes that tissue type is
# vulnerable to (TISSUE_DEMAND_SENSITIVITY) - the same relationship
# classify_injury_risk's v5.12 escalation already uses, just surfaced here
# as its own first-class output instead of a silent tier-nudge. Two
# exercises against the exact same severity-1 hamstring strain can land on
# different colors (a controlled isometric hold: GREEN; a maximal sprint
# start, which is high-eccentric + high-velocity - precisely how a Grade I
# strain becomes a Grade III one: RED) even though severity, joint, and
# tissue are all identical - the color tracks the exercise, not the injury
# label.
#
# The one place severity alone *does* decide the color outright: severity 3
# (structural failure - complete rupture/fracture/dislocation). At that
# tier the tissue has no integrity left to relate an exercise's demands to
# - per this file's own SEVERITY TIERS docstring, "the joint cannot be
# trusted under any real load" - so RED there isn't a demand judgment, it's
# the same "every exercise stressing this joint is excluded outright" fact
# classify_injury_risk already encodes as severity>=3 -> contraindicated.
#
# For severity 1-2, the color is the WORSE (more restrictive) of:
#   - a difficulty-ceiling floor (translated from the existing base tier,
#     so a raw-load mismatch the demand-axis model doesn't capture - e.g. a
#     max-effort grinding lift with none of the tracked demand flags set -
#     still can't read as fully clear), and
#   - a demand-match color from _matched_demand_axes: 0 matches -> GREEN
#     (this exercise doesn't stress anything this tissue is known to fear),
#     1 match -> YELLOW (touches one relevant axis - modify: reduce that
#     specific demand rather than avoid the movement entirely), 2+ matches
#     -> RED (recreates enough of this tissue's injury mechanism that it
#     shouldn't be prescribed without a clinician's okay, independent of
#     how "mild" the severity label reads).
# ==========================================================================
SafetyColor = str  # Literal["GREEN", "YELLOW", "RED"]

_COLOR_RANK = {"GREEN": 0, "YELLOW": 1, "RED": 2}
_BASE_TIER_TO_COLOR = {
    "safe": "GREEN",
    "caution": "YELLOW",
    # high_risk is a raw difficulty-ceiling overshoot, not (yet) a specific
    # demand-mechanism match - real, but a "modify heavily" signal rather
    # than the "get it cleared" signal RED is reserved for below.
    "high_risk": "YELLOW",
    "contraindicated": "RED",
}


def worst_safety_color(colors: List[SafetyColor]) -> SafetyColor:
    """GREEN < YELLOW < RED. Used to collapse several joints/injuries worth
    of colors for one exercise (or several alternates' colors) down to a
    single label - the most restrictive one wins, same "never hide a real
    caution" principle classify_injury_risk's escalation already follows.
    Defaults to GREEN for an empty list (no injury applies -> nothing to warn about)."""
    if not colors:
        return "GREEN"
    return max(colors, key=lambda c: _COLOR_RANK.get(c, 0))


def classify_exercise_safety(
    severity: int,
    difficulty: int,
    tissue: Optional[str] = None,
    exercise: Optional[dict] = None,
    stage: Optional[str] = None,
    side: Optional[str] = None,
) -> Dict[str, str]:
    """The GREEN/YELLOW/RED label for one (injury, exercise) pair - see the
    module-level comment above for the full reasoning. Returns
    {"color": ..., "rationale": ...} so a caller (API response, UI) always
    has a human-readable "why" alongside the label, not just a bare enum.

    `tissue`/`exercise` are optional the same way they are on
    classify_injury_risk: omit either one (e.g. the injury didn't resolve
    to a taxonomy entry with a known tissue) and the color falls back to
    the difficulty-ceiling floor alone, with a rationale that says so.

    `stage` is optional (v5.14): when supplied, a rehab-stage color (see
    _rehab_stage_tier) is folded in the same worst-wins way as the demand
    color - it can only hold or worsen the result, never improve it, and
    the rationale notes it only when it actually changed the outcome.
    Omitting it reproduces the exact pre-v5.14 result.

    `side` is optional (v5.15): a one-sided injury on a side-selectable
    exercise (see laterality_clears_joint) reads as GREEN with a rationale
    that says so, same relaxation classify_injury_risk applies. Omitting it,
    or a "bilateral" injury, reproduces the exact pre-v5.15 result.
    """
    if laterality_clears_joint(side, severity, exercise):
        return {
            "color": "GREEN",
            "rationale": (
                f"One-sided ({side}) injury on a side-selectable exercise - "
                f"train the {OPPOSITE_SIDE.get(side, 'uninjured')} side only "
                "and the injured side isn't loaded at all."
            ),
        }

    if severity >= 3:
        return {
            "color": "RED",
            "rationale": (
                "Severity 3 (structural failure) - this tissue has no integrity to "
                "relate exercise demands to; every exercise is excluded until a "
                "clinician clears it, regardless of how light or targeted it is."
            ),
        }

    base_tier = classify_injury_risk(severity, difficulty)
    base_color = _BASE_TIER_TO_COLOR.get(base_tier, "YELLOW")

    matched = _matched_demand_axes(tissue, exercise)
    if matched == 0:
        demand_color = "GREEN"
        demand_reason = (
            f"doesn't load any of the axes {tissue} tissue is known to be sensitive to"
            if tissue else "no tissue-demand profile available"
        )
    elif matched == 1:
        demand_color = "YELLOW"
        demand_reason = f"touches one {tissue}-sensitive demand axis - modify that specific demand"
    else:
        demand_color = "RED"
        demand_reason = (
            f"matches {matched} of {tissue}'s sensitive demand axes - recreates enough of this "
            "tissue's injury mechanism to need professional clearance"
        )

    color = worst_safety_color([base_color, demand_color])
    rationale = (
        f"Difficulty {difficulty} vs. severity-{severity} ceiling reads as '{base_tier}'; "
        f"exercise demand profile {demand_reason}. Combined: {color}."
    )

    if stage is not None:
        severity_ceiling = SEVERITY_DIFFICULTY_CEILING.get(severity)
        stage_tier = _rehab_stage_tier(severity, severity_ceiling, difficulty, stage, tissue, exercise)
        stage_color = _BASE_TIER_TO_COLOR.get(stage_tier, "YELLOW")
        combined = worst_safety_color([color, stage_color])
        if combined != color:
            resolved = resolve_rehab_stage(severity, stage)
            rationale += (
                f" Rehab stage '{REHAB_STAGE_LABEL.get(resolved, resolved)}' narrows this "
                f"further to {combined}."
            )
        color = combined

    pressing_override = _pressing_tendon_override(severity, tissue, exercise)
    if pressing_override is not None:
        override_color = _BASE_TIER_TO_COLOR.get(pressing_override, "YELLOW")
        combined = worst_safety_color([color, override_color])
        if combined != color:
            rationale += (
                f" Pressing pattern loads a Shoulder tendon injury through compression "
                f"regardless of the lift's technical difficulty - narrows this further to {combined}."
            )
        color = combined

    return {"color": color, "rationale": rationale}





def find_alternatives(
    exercise: dict,
    all_exercises: Dict[str, dict],
    injury_joint_severity: Dict[str, int],
    max_results: int = 3,
    user_equipment: Optional[set] = None,
    injury_joint_tissue: Optional[Dict[str, str]] = None,
    injury_joint_stage: Optional[Dict[str, str]] = None,
    user_injuries: Optional[set] = None,
    injury_joint_side: Optional[Dict[str, str]] = None,
) -> List[dict]:
    """When an exercise is excluded on injury grounds, don't just say no —
    point at exercises that cover the same movement pattern / category without
    loading the joint(s) that got it excluded. Live search over the database,
    not a hand-authored per-exercise alternatives list.

    Preference order:
      1. An exercise the data already declares as an alternative/regression
         of this one, if it clears the joint check.
      2. Any other exercise sharing this one's movement_pattern (or failing
         that, its category) that clears the joint check, ranked by pattern
         match, then whether the person actually has the equipment for it,
         then difficulty.

    `user_equipment` (lower-cased equipment strings the person has available)
    is optional so every existing caller keeps working unchanged. When
    provided, an alternative the person can actually do right now (e.g. a
    Belt Squat swap for a barbell squat, when they have a belt squat) is
    ranked ahead of an equally-valid one they'd need to buy new equipment
    for — a "safe" alternative nobody can act on isn't actually useful. Both
    are still returned if there's room; this only affects ordering, not
    what's included.

    `injury_joint_tissue` (optional, {joint: tissue}) enables the same
    tissue-demand-aware risk check generate_session uses (see
    classify_injury_risk's v5.12 docstring) so a suggested "safe" swap isn't
    still high-demand on an axis this tissue type is sensitive to. Omitted
    -> identical pre-v5.12 behavior.

    `injury_joint_stage` (optional, {joint: rehab_stage}, v5.14) is the same
    stage-gating classify_injury_risk accepts - a suggested swap can't be
    plyometric/reactive for a joint the person is still in early_recovery
    on, even if it would otherwise clear the severity/tissue check. Omitted
    -> identical pre-v5.14 behavior.

    `user_injuries` (optional, lower-cased injury-name strings, same set
    shape generate_session/get_injury_aware_swap already build) closes a gap
    the joint/severity check above can't: a candidate can clear every
    joint's severity/difficulty ceiling and still carry the person's exact
    named injury in its OWN `injuries_to_avoid` tag (e.g. a Wide-Grip
    Pull-Up explicitly tagged "Rotator Cuff" is still difficulty-legal for
    a mild, severity-1 Rotator Cuff joint ceiling, but the exercise's own
    data says it's contraindicated for that specific condition regardless).
    generate_session's main qualifies/is_safe gate already checks this exact
    tag match (`contraindications = user_injuries & (joint_stress |
    injuries_to_avoid)`) before an exercise is ever prescribed - this makes
    find_alternatives honor that same rule when it's the one choosing what
    to suggest, instead of only checking severity/tissue/stage. Omitted ->
    identical pre-fix behavior (name-tag contraindications aren't screened
    here), so this is opt-in exactly like the tissue/stage params above.

    `injury_joint_side` (optional, {joint: side}, v5.15) is the same
    laterality relaxation classify_injury_risk accepts - a one-sided injury
    can still be offered a side-selectable (movement_type == "Unilateral")
    alternative even at a difficulty that would otherwise be excluded, since
    the injured side just isn't trained. Omitted -> identical pre-v5.15
    behavior.
    """
    ex_id = exercise.get("id")
    pattern = exercise.get("movement_pattern")
    category = exercise.get("category")

    def clears_joints(candidate: dict) -> bool:
        if user_injuries:
            candidate_tags = {t.lower() for t in candidate.get("injuries_to_avoid", [])}
            if user_injuries & candidate_tags:
                return False
        for j in candidate.get("joint_stress", []):
            severity = injury_joint_severity.get(j)
            if severity is None:
                continue
            tissue = injury_joint_tissue.get(j) if injury_joint_tissue else None
            stage = injury_joint_stage.get(j) if injury_joint_stage else None
            side = injury_joint_side.get(j) if injury_joint_side else None
            tier = classify_injury_risk(
                severity, candidate.get("difficulty", 1), tissue=tissue, exercise=candidate, stage=stage, side=side,
            )
            if tier in ("high_risk", "contraindicated"):
                return False
        return True

    def equipment_tier(candidate: dict) -> int:
        """-1 = a dedicated piece of equipment the person owns that is ALSO a
        curated joint-sparing substitute (sport_profiles.
        INJURY_JOINT_PREFERRED_EQUIPMENT) for one of this person's own
        injured joints - e.g. a knee/leg injury plus an owned Seal Row
        Bench. Ranked ahead of every other owned equipment, not merely tied
        with it, since that's exactly the swap a coach would lead with.
        0 = any other dedicated piece of equipment the person actually owns
        (e.g. Belt Squat) - the strongest general-purpose swap, since it
        lets them keep training the pattern loaded rather than dropping to
        bodyweight. 1 = bodyweight (always available, but a step down in
        training stimulus from what they were doing). 2 = equipment they
        don't have. Without this, a low-difficulty bodyweight version always
        outranked an owned dedicated substitute purely because "difficulty"
        sorts ascending - which is backwards when the whole point of asking
        about available equipment is that a Belt Squat (or, for an injured
        athlete, a Seal Row Bench) swap is what they'd actually want offered
        first."""
        if user_equipment is None:
            return 0
        eq_raw = candidate.get("equipment", "Bodyweight")
        eq = eq_raw.lower()
        if eq != "bodyweight" and eq in user_equipment:
            if injury_joint_severity:
                for joint in injury_joint_severity:
                    if eq_raw in INJURY_JOINT_PREFERRED_EQUIPMENT.get(joint, ()):
                        return -1
            return 0
        if eq == "bodyweight":
            return 1
        return 2

    declared: List[dict] = []
    seen = set()

    declared_ids = list(exercise.get("alternatives", [])) + list(exercise.get("regressions", []))
    for cand_id in declared_ids:
        cand = all_exercises.get(cand_id)
        if cand and cand_id not in seen and clears_joints(cand):
            declared.append(cand)
            seen.add(cand_id)
    # Declared alternatives were previously left in raw data order - sorted
    # here too so an owned dedicated substitute (e.g. Belt Squat) still
    # outranks a declared-but-generic bodyweight option instead of only the
    # fallback pool below getting equipment-aware ordering.
    declared.sort(key=lambda c: (equipment_tier(c), c.get("difficulty", 1)))
    candidates: List[dict] = list(declared)

    if len(candidates) < max_results:
        own_difficulty = exercise.get("difficulty", 1)
        pool = [
            c for cid, c in all_exercises.items()
            if cid != ex_id
            and cid not in seen
            and (c.get("movement_pattern") == pattern or c.get("category") == category)
            and clears_joints(c)
        ]
        # Closest-difficulty-first, not lowest-difficulty-first: raw ascending
        # difficulty meant an advanced exercise's swap pool was always won by
        # the single easiest bodyweight exercise in the category (e.g. Wall
        # Push-Up for an Archer Ring Push-Up), regardless of how much harder
        # the original was - burying same-pattern, similarly-advanced options
        # (Ring Dip, Ring Archer Dip) that are what a coach would actually
        # suggest laterally. clears_joints() already screened out anything
        # unsafe, so among the survivors the best swap is the one nearest the
        # athlete's own level, not the floor of the category.
        pool.sort(key=lambda c: (
            c.get("movement_pattern") != pattern,
            equipment_tier(c),
            abs(c.get("difficulty", 1) - own_difficulty),
        ))
        candidates.extend(pool)

    return candidates[:max_results]


def _risk_note(severity: int, joint: str) -> str:
    ceiling = SEVERITY_DIFFICULTY_CEILING.get(severity)
    return (
        f"Severity {severity}/3 on '{joint}' -> difficulty ceiling "
        f"{ceiling if ceiling is not None else 'none (joint excluded outright)'}; "
        f"classify_injury_risk() applies the standard four-tier model to any "
        f"exercise whose joint_stress includes '{joint}'."
    )


def _phases(tissue: str) -> List[str]:
    return {
        "Muscle": [
            "Acute/inflammatory (0-72h): protect from further tearing, manage pain/swelling, gentle pain-free motion.",
            "Proliferative/repair (~3 days-3 weeks): progressive pain-free ROM, isometrics -> light isotonics.",
            "Remodeling/strengthening (~3-8+ weeks, longer for Grade III): progressive loading toward pre-injury capacity, then eccentrics/plyometrics.",
        ],
        "Ligament": [
            "Acute (0-1 week): protect the joint, control swelling, gentle protected ROM.",
            "Proliferative (~1-6 weeks): progressive ROM, proprioception/balance work, light resistance.",
            "Remodeling (~6 weeks-6+ months, longer if surgical): progressive loading, sport-specific stability and reactive work.",
        ],
        "Tendon": [
            "Reactive/acute (0-2 weeks): load management, isometrics for pain modulation.",
            "Dysrepair (~2-6 weeks): heavy slow resistance introduced cautiously, monitor 24h pain response.",
            "Degenerative/remodeling (~6 weeks-6+ months): progressive tendon loading, energy-storage/plyometric reintroduction.",
        ],
        "Bone": [
            "Inflammatory (0-1 week): protect, offload per fracture/stress-injury stability.",
            "Soft callus (~1-4 weeks): protected/partial weight-bearing progression per clinical guidance.",
            "Hard callus/remodeling (~4-12+ weeks): progressive loading as imaging/clinical status allows.",
        ],
        "Joint": [
            "Acute/protective phase: control swelling and pain, protect the joint from provocative positions.",
            "Motion & light-loading phase: restore ROM, begin light closed-chain and stability work.",
            "Progressive loading & return-to-activity phase: rebuild strength/power specific to the joint's demands.",
        ],
        "Cartilage": [
            "Acute/protective phase: offload per weight-bearing status, control effusion.",
            "Progressive loading phase: closed-chain loading introduced gradually, monitor for reactive swelling.",
            "Return-to-activity phase: sport/task-specific loading once pain- and effusion-free.",
        ],
        "Spine": [
            "Acute (0-2 weeks): relative rest from provocative positions, pain-modulating movement, avoid prolonged static postures.",
            "Sub-acute (~2-6 weeks): progressive mobility and motor-control (core/segmental stability) work.",
            "Remodeling (~6 weeks+): progressive loading, capacity-building for sport/occupational demand.",
        ],
        "Nerve": [
            "Acute irritation phase: reduce compressive/tensile load on the nerve, address contributing posture/positions.",
            "Desensitization & gliding phase: nerve-gliding/flossing, graded exposure to provocative positions.",
            "Progressive loading & functional phase: rebuild strength/endurance in the affected distribution.",
        ],
        "Fascia": [
            "Acute (0-2 weeks): reduce provocative loading, address contributing mechanical factors.",
            "Sub-acute (~2-6 weeks): progressive loading, soft-tissue and mobility work.",
            "Remodeling (~6 weeks+): progressive return to full activity/impact loading.",
        ],
    }.get(tissue, [
        "Acute/protective phase.",
        "Progressive loading phase.",
        "Return-to-activity phase.",
    ])


def _generic_pain(severity: int, label: str) -> str:
    return {
        1: f"Mild, often intermittent pain related to {label}; typically activity-related, resolves with rest.",
        2: f"Moderate, more consistent pain related to {label}; functional limitation present, may include swelling/instability.",
        3: f"Severe pain and/or significant functional loss related to {label}; may include instability, deformity, or neurological symptoms.",
    }[severity]


def _generic_restrictions(severity: int, target: str) -> str:
    return {
        1: f"Avoid the highest-demand loading/positions for the {target} until asymptomatic; most other training tolerated.",
        2: f"Avoid moderate-to-high loading and end-range positions for the {target}; light, controlled work only.",
        3: f"Avoid loading the {target} in any capacity until medically cleared.",
    }[severity]


# ============================================================================
# LEGACY ENTRIES (v3.0/v4.0) — names, joints, and severities unchanged.
# Enriched here with the full field set via generic, severity-driven
# defaults rather than hand-authored per-entry prose, since the specific
# clinical detail already lives in each name (grade, mechanism, structure).
# ============================================================================
_LEGACY = {
    # KNEE - Ligament
    "ACL/Ligament Sprain - Grade 1 (Mild)": {"joint": "Knee", "severity": 1},
    "ACL/Ligament Tear - Grade 2 (Partial Tear)": {"joint": "Knee", "severity": 2},
    "ACL/Ligament Tear - Grade 3 (Complete Rupture)": {"joint": "Knee", "severity": 3},
    # KNEE - Meniscus
    "Meniscus Tear - Grade 1 (Early Fraying)": {"joint": "Knee", "severity": 1},
    "Meniscus Tear - Grade 2 (Deep Linear Tear)": {"joint": "Knee", "severity": 2},
    "Meniscus Tear - Grade 3 (True Structural Tear)": {"joint": "Knee", "severity": 3},
    # KNEE - Patella / loose bodies
    "Patellar Dislocation - Acute (First-Time)": {"joint": "Knee", "severity": 3},
    "Patellar Dislocation - Chronic Recurrent": {"joint": "Knee", "severity": 2},
    "Knee Loose Bodies - Stable/Non-Obstructive": {"joint": "Knee", "severity": 1},
    "Knee Loose Bodies - Unstable/Obstructive": {"joint": "Knee", "severity": 2},
    # ANKLE
    "Lateral Ankle Sprain - Grade 1 (Mild)": {"joint": "Ankle", "severity": 1},
    "Lateral Ankle Sprain - Grade 2 (Partial Tear)": {"joint": "Ankle", "severity": 2},
    "Lateral Ankle Sprain - Grade 3 (Complete Rupture)": {"joint": "Ankle", "severity": 3},
    "High Ankle Sprain (Syndesmosis Tear)": {"joint": "Ankle", "severity": 3},
    "Peroneal Tendon Subluxation": {"joint": "Ankle", "severity": 2},
    "Osteochondral Lesion / Ankle Loose Bodies": {"joint": "Ankle", "severity": 1},
    "Ankle Fracture - Weber Type A (Stable)": {"joint": "Ankle", "severity": 1},
    "Ankle Fracture - Weber Type B (Variable Stability)": {"joint": "Ankle", "severity": 2},
    "Ankle Fracture - Weber Type C (Highly Unstable)": {"joint": "Ankle", "severity": 3},
    "Ankle Fracture-Dislocation": {"joint": "Ankle", "severity": 3},
    # HIP
    "Snapping Hip Syndrome": {"joint": "Hip", "severity": 1},
    "Hip Labral Tear - Grade 1 (Fraying)": {"joint": "Hip", "severity": 1},
    "Hip Labral Tear - Grade 2 (Partial Tear)": {"joint": "Hip", "severity": 2},
    "Hip Labral Tear - Grade 3 (Complete Avulsion)": {"joint": "Hip", "severity": 3},
    "Avascular Necrosis (Hip) - Stage I/II": {"joint": "Hip", "severity": 1},
    "Avascular Necrosis (Hip) - Stage III/IV (Collapse)": {"joint": "Hip", "severity": 3},
    "Hip Dislocation - Grade 1 (Simple)": {"joint": "Hip", "severity": 3},
    "Hip Dislocation - Grade 2-4 (With Fracture)": {"joint": "Hip", "severity": 3},
    "Femoral Neck / Acetabular Fracture": {"joint": "Hip", "severity": 3},
}


def _enrich_legacy(name: str, joint: str, severity: int) -> dict:
    label = name.lower()
    return {
        "name": name,
        "alt_names": [],
        "tissue": "Musculoskeletal (see name for specific structure)",
        "joint": joint,
        "region": joint,
        "severity": severity,
        "severity_grades": "Grade/type is encoded in the injury name; severity tier below is this system's 1 (mild) - 3 (severe) load-tolerance model, not a separate clinical grading scale.",
        "healing_phases": _phases("Joint"),
        "pain_pattern": _generic_pain(severity, label),
        "mechanism": "Mechanism is specific to this diagnosis — refer to clinical literature for the named structure/grade.",
        "movement_restrictions": _generic_restrictions(severity, joint.lower()),
        "joint_position_restrictions": f"Avoid end-range/provocative positions of the {joint.lower()} associated with this injury.",
        "rom_restrictions": "Pain-free ROM only until re-evaluated; avoid forcing ROM into a symptomatic range." if severity < 3 else "ROM work is clinician-directed only.",
        "loading_restrictions": {1: "Light-to-moderate loading tolerated if pain-free.", 2: "Light, controlled loading only.", 3: "No loading until medically cleared."}[severity],
        "velocity_restrictions": "Avoid high-velocity/ballistic loading of the joint until cleared." if severity > 1 else "Avoid maximal-velocity efforts until asymptomatic.",
        "impact_restrictions": "Avoid impact loading (running, jumping, cutting/pivoting) on the joint until cleared." if severity > 1 else "Impact tolerated in moderation if pain-free.",
        "technical_faults_to_avoid": ["Loading through pain", "Skipping graded-exposure progression", "Ignoring swelling/symptom flare after loading"],
        "biomechanical_stresses_to_avoid": [f"High shear/compressive/rotational load through the {joint.lower()}"],
        "muscles_to_protect": [],
        "muscles_to_strengthen": [f"Stabilizing musculature around the {joint.lower()}"],
        "safe_movement_patterns": ["Pain-free, controlled ROM within the current tolerance"],
        "contraindicated_movement_patterns": ["High-load/high-velocity/end-range movement at this joint"] if severity > 1 else ["Maximal-effort loading at this joint"],
        "exercise_modifications": ["Reduce ROM/load and rebuild gradually", "Substitute exercises that don't stress this joint while symptomatic"],
        "progression_criteria": ["Pain-free through current ROM/load", "No swelling or symptom flare 24h post-session", "Clinician sign-off for severity 2-3 before advancing"],
        "regression_criteria": ["Pain or swelling returns/increases with current loading", "Loss of ROM or strength versus prior session"],
        "return_to_sport_criteria": ["Full, pain-free ROM and strength symmetric to the uninjured side", "Sport-specific movement tolerated at full intensity without symptoms", "Clinician/PT clearance for severity 2-3"],
        "absolute_contraindications": ["Loading through sharp/mechanical pain", "Training through instability, locking, or giving-way episodes"],
        "relative_contraindications": ["High training volume/frequency before symptom resolution"],
        "clinical_red_flags": ["Neurovascular compromise (numbness, pallor, pulselessness)", "Joint locking or true instability/giving-way", "Signs of fracture or dislocation", "Progressive neurological symptoms"],
        "risk_score_logic": _risk_note(severity, joint),
    }


# ============================================================================
# MUSCLE STRAINS — generated across every major muscle group (v5.0 addition)
# ============================================================================
MUSCLE_GROUPS = [
    ("Neck Muscles (Sternocleidomastoid/Scalenes)", "Neck", "Anterior/Lateral Neck"),
    ("Trapezius", "Neck", "Neck/Upper Back"),
    ("Levator Scapulae", "Neck", "Neck/Upper Back"),
    ("Deltoids", "Shoulder", "Shoulder"),
    ("Rotator Cuff Muscles", "Shoulder", "Shoulder"),
    ("Pectoralis Major", "Shoulder", "Chest"),
    ("Pectoralis Minor", "Shoulder", "Chest"),
    ("Serratus Anterior", "Shoulder", "Chest/Scapula"),
    ("Latissimus Dorsi", "Shoulder", "Upper Back"),
    ("Rhomboids", "Shoulder", "Upper Back"),
    ("Erector Spinae", "Lower Back", "Spine"),
    ("Multifidus", "Lower Back", "Lumbar Spine"),
    ("Quadratus Lumborum", "Lower Back", "Lumbar Spine"),
    ("Rectus Abdominis", "Lower Back", "Abdomen/Core"),
    ("Obliques", "Lower Back", "Abdomen/Core"),
    ("Transverse Abdominis", "Lower Back", "Abdomen/Core"),
    ("Hip Flexors", "Hip", "Anterior Hip"),
    ("Iliopsoas", "Hip", "Anterior Hip/Deep"),
    ("Gluteus Maximus", "Hip", "Hip/Glute"),
    ("Gluteus Medius", "Hip", "Hip/Glute"),
    ("Gluteus Minimus", "Hip", "Hip/Glute"),
    ("Tensor Fasciae Latae (TFL)", "Hip", "Lateral Hip"),
    ("Piriformis", "Hip", "Deep Hip/Glute"),
    ("Adductors", "Hip", "Groin/Inner Thigh"),
    ("Abductors", "Hip", "Lateral Hip/Thigh"),
    ("Quadriceps", "Knee", "Anterior Thigh"),
    ("Hamstrings", "Knee", "Posterior Thigh"),
    ("Gastrocnemius", "Ankle", "Calf"),
    ("Soleus", "Ankle", "Calf (deep)"),
    ("Tibialis Anterior", "Ankle", "Shin"),
    ("Tibialis Posterior", "Ankle", "Deep Calf/Shin"),
    ("Peroneals", "Ankle", "Lateral Lower Leg"),
    ("Forearm Flexors", "Wrist", "Forearm (volar)"),
    ("Forearm Extensors", "Wrist", "Forearm (dorsal)"),
    ("Biceps", "Elbow", "Upper Arm (anterior)"),
    ("Triceps", "Elbow", "Upper Arm (posterior)"),
    ("Wrist Muscles", "Wrist", "Wrist"),
    ("Intrinsic Hand Muscles", "Wrist", "Hand"),
    ("Foot Intrinsic Muscles", "Ankle", "Foot"),
]

_STRAIN_LABEL = {1: "Grade I Strain (Mild)", 2: "Grade II Strain (Partial Tear)", 3: "Grade III Tear (Complete Rupture)"}
_STRAIN_ALT = {1: "Pull", 2: "Partial Tear", 3: "Complete Tear/Rupture"}


def _muscle_strain(muscle: str, joint: str, region: str, grade: int) -> dict:
    m = muscle.lower()
    pain = {
        1: f"Mild, localized soreness in the {m} during or shortly after activity; no significant strength loss, minimal swelling.",
        2: f"Moderate, well-localized pain with palpable tenderness in the {m}; noticeable strength loss, swelling/bruising common.",
        3: f"Sudden, severe pain often described as a 'pop' or tearing sensation in the {m}; marked strength loss, possible palpable defect, significant swelling/bruising.",
    }[grade]
    loading = {
        1: "Light-to-moderate isotonic loading tolerated once pain-free.",
        2: "Isometrics progressing to light isotonic loading only; avoid end-range eccentrics.",
        3: "No loading until cleared by a clinician; rehab loading thereafter is clinician-directed.",
    }[grade]
    prog = {
        1: ["Full pain-free active ROM", "No pain with isometric resistance", "No pain with functional movement at low intensity"],
        2: ["Full pain-free passive and active ROM", "Isometric strength ~80%+ of uninjured side", "Pain-free light functional loading"],
        3: ["Clinician clearance (with imaging follow-up as indicated)", "Progressive rehab-supervised strength restoration", "Pain-free full ROM before any resisted work resumes"],
    }[grade]
    rts = {
        1: ["Full, pain-free ROM and strength symmetric to the uninjured side", "No pain with sport-specific movement at full intensity"],
        2: ["Strength >=90% of uninjured side on objective testing", "Pain-free through sport-specific speed/agility work", "No apprehension with high-velocity or eccentric demand"],
        3: ["Clinician/physical therapist sign-off", "Strength and functional (hop/throw/lift) testing symmetric to uninjured side", "Full pain-free sport-specific movement at competition intensity"],
    }[grade]
    return {
        "name": f"{muscle} Strain - {_STRAIN_LABEL[grade]}",
        "alt_names": [f"{muscle} {_STRAIN_ALT[grade]}"],
        "tissue": "Muscle",
        "joint": joint,
        "region": region,
        "severity": grade,
        "severity_grades": "Grade I (mild, minimal fiber disruption) / Grade II (moderate, partial tear) / Grade III (severe, complete rupture) — standard muscle strain grading.",
        "healing_phases": _phases("Muscle"),
        "pain_pattern": pain,
        "mechanism": f"Sudden eccentric overload, forceful/ballistic contraction, or overstretch of the {m}.",
        "movement_restrictions": {
            1: f"Avoid maximal-effort or ballistic use of the {m} for 1-2 weeks; keep loaded work pain-free.",
            2: f"Avoid resisted and eccentric loading of the {m} until pain-free through full ROM; no ballistic/plyometric use.",
            3: f"Avoid all loading of the {m} until medically cleared; protected motion/immobilization may be indicated early on.",
        }[grade],
        "joint_position_restrictions": f"Avoid end-range lengthened positions of the {m} under load until healing progresses.",
        "rom_restrictions": "Pain-free active ROM only in the acute phase; avoid stretching into pain until subacute (Grade I/II) or clinician-cleared (Grade III).",
        "loading_restrictions": loading,
        "velocity_restrictions": "Avoid ballistic/high-velocity contraction until strength and pain-free ROM are restored." if grade > 1 else "Avoid maximal-velocity efforts for 1-2 weeks.",
        "impact_restrictions": "Avoid impact activity that loads this muscle (running, jumping, cutting) until pain-free strength is restored.",
        "technical_faults_to_avoid": ["Loading through pain / compensating with poor form", "Skipping the isometric -> isotonic -> eccentric progression", "Returning to ballistic work before strength symmetry is confirmed"],
        "biomechanical_stresses_to_avoid": [f"Rapid eccentric loading of the {m}", "Overstretching into end-range under load"],
        "muscles_to_protect": [muscle],
        "muscles_to_strengthen": [muscle, "surrounding synergists and antagonists for balanced loading"],
        "safe_movement_patterns": ["Pain-free isometric holds", "Controlled, short-range isotonic work with gradual load progression"],
        "contraindicated_movement_patterns": ["Ballistic/plyometric use of the muscle", "Maximal eccentric loading", "End-range stretching under load"] if grade > 1 else ["Maximal-effort ballistic use of the muscle"],
        "exercise_modifications": ["Reduce range/load and rebuild via isometrics -> isotonics -> eccentrics -> plyometrics", "Substitute exercises that don't stress this muscle group while it heals"],
        "progression_criteria": prog,
        "regression_criteria": ["Return/increase of pain with current loading", "Loss of strength or ROM versus the prior session", "Swelling or bruising recurs"],
        "return_to_sport_criteria": rts,
        "absolute_contraindications": ["Loading through sharp/tearing pain", "Return to sport before functional symmetry testing (Grade II/III)"] if grade > 1 else ["Loading through sharp pain"],
        "relative_contraindications": ["High-volume ballistic training before full strength is restored", "Training this muscle to failure in early rehab"],
        "clinical_red_flags": [
            "Sudden severe pain with a palpable gap/defect (possible complete rupture) — refer for imaging.",
            "Signs of compartment syndrome (severe pain out of proportion, tense swelling, numbness, pallor) — emergency referral.",
            "Inability to voluntarily contract the muscle at all.",
        ],
        "risk_score_logic": _risk_note(grade, joint),
    }


# ============================================================================
# GENERAL MUSCLE CONDITIONS — non-grade-specific muscle injury types
# ============================================================================
def _muscle_condition(name: str, joint: str, region: str, severity: int, pain: str, mechanism: str, red_flags: List[str], systemic: bool = False) -> dict:
    return {
        "name": name, "alt_names": [], "tissue": "Muscle", "joint": joint, "region": region, "severity": severity,
        "systemic": systemic,
        "severity_grades": "Not graded I-III; severity reflects functional impact using this system's 1 (mild)-3 (severe) model.",
        "healing_phases": _phases("Muscle"),
        "pain_pattern": pain, "mechanism": mechanism,
        "movement_restrictions": _generic_restrictions(severity, joint.lower()),
        "joint_position_restrictions": f"Avoid sustained or end-range positions that reproduce symptoms near the {region.lower()}.",
        "rom_restrictions": "Gentle pain-free ROM/stretching generally tolerated and often therapeutic; avoid forcing through sharp pain.",
        "loading_restrictions": {1: "Normal training tolerated with monitoring.", 2: "Reduce volume/intensity until symptoms settle.", 3: "Avoid loading until re-evaluated."}[severity],
        "velocity_restrictions": "No specific restriction beyond symptom-guided loading." if severity == 1 else "Avoid high-velocity/ballistic loading until symptoms settle.",
        "impact_restrictions": "Generally tolerated if asymptomatic." if severity == 1 else "Reduce impact loading until symptoms resolve.",
        "technical_faults_to_avoid": ["Ignoring early warning symptoms and continuing to overload the area", "Poor recovery/sleep/hydration compounding tissue irritability"],
        "biomechanical_stresses_to_avoid": ["Repetitive overload without adequate recovery", "Sudden spikes in training load"],
        "muscles_to_protect": [], "muscles_to_strengthen": ["General strength/conditioning of the affected region once symptoms allow"],
        "safe_movement_patterns": ["Light aerobic activity, mobility work, self-myofascial release as tolerated"],
        "contraindicated_movement_patterns": ["High-load training through unresolved symptoms"],
        "exercise_modifications": ["Reduce training load/volume", "Address contributing factors (load management, technique, recovery)"],
        "progression_criteria": ["Symptom resolution or return to baseline", "No recurrence with graded return to full training load"],
        "regression_criteria": ["Symptoms recur or worsen with current training load"],
        "return_to_sport_criteria": ["Full training tolerance without symptom recurrence"],
        "absolute_contraindications": [] if severity < 3 else ["Continuing to train through the acute presentation"],
        "relative_contraindications": ["Rapid return to prior training volume without a graded reintroduction"],
        "clinical_red_flags": red_flags,
        "risk_score_logic": _risk_note(severity, joint),
    }


_MUSCLE_CONDITIONS = [
    _muscle_condition("Muscle Contusion - Thigh", "Knee", "Thigh (quad/hamstring)", 2,
        "Localized pain, swelling, bruising following direct blunt trauma; pain with contraction and passive stretch.",
        "Direct blunt trauma (contact, collision, equipment impact) to the muscle belly.",
        ["Rapidly expanding swelling or severe pain out of proportion (possible compartment syndrome) — emergency referral.",
         "Progressive loss of knee flexion/extension ROM over days (myositis ossificans risk) — refer for evaluation."]),
    _muscle_condition("Muscle Contusion - Calf", "Ankle", "Calf", 2,
        "Localized pain, swelling, bruising following direct blunt trauma to the calf.",
        "Direct blunt trauma to the gastrocnemius/soleus.",
        ["Severe pain, tense swelling, numbness (possible compartment syndrome) — emergency referral."]),
    _muscle_condition("Muscle Contusion - Shoulder/Upper Arm", "Shoulder", "Shoulder/Upper Arm", 1,
        "Localized pain, swelling, bruising following direct blunt trauma.",
        "Direct blunt trauma (contact, fall, equipment impact).",
        ["Rapidly expanding swelling or severe pain out of proportion — refer for evaluation."]),
    _muscle_condition("Muscle Contusion - Forearm", "Wrist", "Forearm", 2,
        "Localized pain, swelling, bruising in the forearm following direct trauma.",
        "Direct blunt trauma to the forearm musculature.",
        ["Severe pain, tense swelling, numbness/tingling in the hand (possible compartment syndrome) — emergency referral."]),
    _muscle_condition("Muscle Spasm", "Lower Back", "Variable (commonly low back/neck)", 1,
        "Sudden, involuntary, painful muscle contraction; palpable tightness/knot.",
        "Overload, dehydration, fatigue, or protective response to underlying irritation.",
        ["Spasm accompanied by neurological symptoms (numbness, weakness) — refer for evaluation."]),
    _muscle_condition("Muscle Cramp", "Lower Back", "Variable (commonly calf/hamstring)", 1,
        "Sudden, brief, painful involuntary muscle contraction, usually during or after exertion.",
        "Fatigue, dehydration/electrolyte imbalance, or unaccustomed load.",
        ["Frequent/severe cramping with muscle weakness or dark urine (possible rhabdomyolysis) — urgent medical evaluation."]),
    _muscle_condition("Delayed Onset Muscle Soreness (DOMS)", "Lower Back", "Variable (whichever muscle group was loaded)", 1,
        "Diffuse, dull soreness peaking 24-72h after unaccustomed or high-eccentric-load exercise; resolves within a week.",
        "Unaccustomed eccentric loading or a sharp increase in training volume/intensity.",
        ["Severe swelling, dark urine, disproportionate pain (possible exertional rhabdomyolysis) — urgent medical evaluation."]),
    _muscle_condition("Myofascial Pain Syndrome / Trigger Points", "Neck", "Variable (commonly neck/upper back)", 1,
        "Localized deep, aching pain from a hyperirritable point in a taut muscle band; may refer pain to a predictable pattern.",
        "Repetitive strain, sustained postures, or unresolved muscle overload.",
        ["Progressive neurological symptoms rather than typical referred pain pattern — refer for evaluation."]),
    _muscle_condition("Chronic Muscle Tightness / Overuse Syndrome", "Lower Back", "Variable", 1,
        "Persistent tightness/stiffness with cumulative overload; may include mild ache with activity.",
        "Repetitive loading without adequate recovery over weeks to months.",
        ["Progressive weakness or symptoms unrelieved by rest and load management — refer for evaluation."]),
    # v5.30 fix: both compartment syndrome entries' own red-flag text already
    # says this is a surgical emergency requiring immediate care "not
    # exercise programming" - i.e. no training of any kind, not just no
    # ankle-loading exercises. `systemic` was never set, so the app only
    # ever blocked Ankle-tagged exercises and would happily hand someone
    # with acute compartment syndrome a bench-press or overhead-press
    # session. Flagging both systemic=True closes that gap.
    _muscle_condition("Acute Compartment Syndrome - Anterior Leg", "Ankle", "Anterior Lower Leg", 3,
        "Severe pain out of proportion to injury, worsened by passive stretch of the compartment; tightness, paresthesia, and pallor may develop.",
        "Direct trauma, fracture, or rarely severe exertional overload causing intracompartmental pressure to rise.",
        ["This is a surgical emergency — the 5 P's (Pain out of proportion, Paresthesia, Pallor, Pulselessness, Paralysis) require IMMEDIATE emergency care, not exercise programming."],
        systemic=True),
    _muscle_condition("Acute Compartment Syndrome - Deep Posterior Leg", "Ankle", "Deep Posterior Lower Leg", 3,
        "Severe pain out of proportion to injury, worsened by passive stretch of the toes; tightness and paresthesia in the sole.",
        "Direct trauma, fracture, or severe exertional overload.",
        ["Surgical emergency — immediate emergency care required; do not attempt to manage with exercise/rest alone."],
        systemic=True),
    _muscle_condition("Chronic Exertional Compartment Syndrome - Anterior Leg", "Ankle", "Anterior Lower Leg", 2,
        "Predictable, reproducible tightness/aching pain that builds during exertion and resolves with rest, over weeks-months of training.",
        "Repetitive exertional loading (typically running) in a susceptible individual.",
        ["Symptoms that fail to resolve with rest, or develop suddenly and severely (possible acute conversion) — urgent evaluation."]),
]


# ============================================================================
# LIGAMENT SPRAINS — generated across major joints not already covered by
# name in the legacy set (v5.0 addition)
# ============================================================================
LIGAMENTS = [
    ("PCL", "Knee", "Knee (posterior)"),
    ("MCL", "Knee", "Knee (medial)"),
    ("LCL", "Knee", "Knee (lateral)"),
    ("MPFL", "Knee", "Knee (patellofemoral)"),
    ("ATFL", "Ankle", "Ankle (lateral)"),
    ("CFL", "Ankle", "Ankle (lateral)"),
    ("PTFL", "Ankle", "Ankle (lateral, deep)"),
    ("Deltoid Ligament", "Ankle", "Ankle (medial)"),
    ("AC Ligament", "Shoulder", "Shoulder (AC joint)"),
    ("Coracoclavicular Ligament", "Shoulder", "Shoulder (AC joint)"),
    ("Glenohumeral Ligaments", "Shoulder", "Shoulder (capsule)"),
    ("UCL", "Elbow", "Elbow (medial)"),
    ("RCL", "Elbow", "Elbow (lateral)"),
    ("Iliofemoral Ligament", "Hip", "Hip (anterior)"),
    ("Pubofemoral Ligament", "Hip", "Hip (anteroinferior)"),
    ("Ischiofemoral Ligament", "Hip", "Hip (posterior)"),
    ("Posterior Ligament Complex", "Lower Back", "Lumbar Spine"),
    ("Interspinous Ligaments", "Lower Back", "Lumbar Spine"),
    ("SI Joint Ligaments", "Hip", "Sacroiliac Joint"),
]


def _ligament_sprain(ligament: str, joint: str, region: str, grade: int) -> dict:
    lg = ligament.lower()
    label = {1: "Grade I Sprain (Mild)", 2: "Grade II Sprain (Partial Tear)", 3: "Grade III Sprain (Complete Rupture)"}[grade]
    pain = {
        1: f"Mild pain/tenderness over the {lg} with minimal swelling; no instability.",
        2: f"Moderate pain and swelling over the {lg}; mild-to-moderate laxity on stress testing, some functional loss.",
        3: "Significant pain (may paradoxically be less if the ligament is fully torn), marked swelling, and frank instability on stress testing.",
    }[grade]
    return {
        "name": f"{ligament} Sprain - {label}",
        "alt_names": [f"{ligament} Tear"] if grade > 1 else [f"{ligament} Strain"],
        "tissue": "Ligament", "joint": joint, "region": region, "severity": grade,
        "severity_grades": "Grade I (stretched, stable) / Grade II (partial tear, mild-moderate laxity) / Grade III (complete tear, gross instability).",
        "healing_phases": _phases("Ligament"),
        "pain_pattern": pain,
        "mechanism": f"Forced motion beyond the {lg}'s normal range — twisting, valgus/varus force, hyperextension, or direct trauma depending on joint.",
        "movement_restrictions": {
            1: f"Avoid end-range/stress positions for the {lg} for 1-2 weeks; otherwise well tolerated.",
            2: f"Avoid loaded end-range and rotational/shear stress on the {lg} until proprioception and strength are restored.",
            3: f"Avoid any stress on the {lg} until medically evaluated; bracing/surgical consult often indicated.",
        }[grade],
        "joint_position_restrictions": f"Avoid the specific end-range position that stresses the {lg} (per its anatomical line of pull) until cleared.",
        "rom_restrictions": "Protected ROM early, progressing as swelling and pain allow; avoid forcing end-range." if grade > 1 else "Full pain-free ROM generally tolerated within days.",
        "loading_restrictions": {1: "Light-to-moderate loading tolerated once pain-free.", 2: "Light, controlled loading with bracing/taping as needed.", 3: "No loading until medically cleared."}[grade],
        "velocity_restrictions": "Avoid cutting/pivoting or high-velocity direction changes until proprioceptive control and strength are restored.",
        "impact_restrictions": "Avoid impact and multidirectional loading until cleared for return-to-sport testing." if grade > 1 else "Impact generally tolerated once pain-free.",
        "technical_faults_to_avoid": ["Skipping proprioceptive/balance retraining", "Returning to cutting/pivoting before strength and stability are restored"],
        "biomechanical_stresses_to_avoid": [f"Valgus/varus, rotational, or shear load across the joint that stresses the {lg}"],
        "muscles_to_protect": [], "muscles_to_strengthen": ["Dynamic stabilizers of the joint (proprioceptive and strength training)"],
        "safe_movement_patterns": ["Closed-chain, controlled-ROM loading within the pain-free range", "Balance/proprioceptive drills"],
        "contraindicated_movement_patterns": ["Open-chain end-range loading that stresses the ligament", "Uncontrolled cutting/pivoting/twisting"] if grade > 1 else ["Maximal-effort stress on the ligament"],
        "exercise_modifications": ["Brace/tape as indicated", "Progress from closed-chain to open-chain, straight-line to multidirectional loading"],
        "progression_criteria": ["Full pain-free ROM", "Strength and proprioception restored toward symmetry", "No pain/instability with progressively demanding loading"],
        "regression_criteria": ["Pain, swelling, or a sense of instability returns with current loading"],
        "return_to_sport_criteria": ["Strength and single-leg/functional testing symmetric to the uninjured side", "No instability or apprehension with sport-specific cutting/pivoting at full speed", "Clinician clearance for Grade II/III"],
        "absolute_contraindications": ["Return to cutting/pivoting sport before instability is resolved (Grade II/III)", "Loading through a positive instability/apprehension test"],
        "relative_contraindications": ["Unbraced high-demand training in the early post-injury period"],
        "clinical_red_flags": ["Gross instability or a joint that gives way with normal activity", "Neurovascular compromise distal to the joint", "Signs of associated fracture (point bony tenderness, inability to bear weight)"],
        "risk_score_logic": _risk_note(grade, joint),
    }


# ============================================================================
# TENDON INJURIES — generated across major tendons (v5.0 addition)
# ============================================================================
TENDONS = [
    ("Achilles Tendon", "Ankle", "Posterior Ankle/Heel"),
    ("Patellar Tendon", "Knee", "Anterior Knee"),
    ("Quadriceps Tendon", "Knee", "Anterior Knee (suprapatellar)"),
    ("Hamstring Tendons", "Knee", "Posterior Thigh/Ischial"),
    ("Rotator Cuff Tendons", "Shoulder", "Shoulder"),
    ("Long Head Biceps Tendon", "Shoulder", "Anterior Shoulder"),
    ("Distal Biceps Tendon", "Elbow", "Anterior Elbow"),
    ("Triceps Tendon", "Elbow", "Posterior Elbow"),
    ("Tibialis Posterior Tendon", "Ankle", "Medial Ankle"),
    ("Tibialis Anterior Tendon", "Ankle", "Anterior Ankle"),
    ("Peroneal Tendons", "Ankle", "Lateral Ankle"),
    ("Wrist Flexor Tendons", "Wrist", "Volar Wrist/Forearm"),
    ("Wrist Extensor Tendons", "Wrist", "Dorsal Wrist/Forearm (lateral epicondyle common origin)"),
]

# v5.29 fix: the rupture red-flag text below used to hardcode ONE example
# functional test ("can't do a single-leg heel raise, can't extend the
# elbow against resistance") on EVERY tendon regardless of which one it
# actually was - so a Wrist Flexor Tendon or Rotator Cuff Tendons rupture
# cited a heel-raise test, which is meaningless for those joints (Triceps
# Tendon happened to accidentally read correctly, since its own test really
# is elbow extension - that's what masked this for so long). Each tendon
# now gets the actual clinical function test a clinician would check for
# a suspected rupture of that specific tendon.
TENDON_KEY_FUNCTION_TEST = {
    "Achilles Tendon": "can't do a single-leg heel raise or push off the foot",
    "Patellar Tendon": "can't actively extend the knee or do a straight-leg raise",
    "Quadriceps Tendon": "can't actively extend the knee or do a straight-leg raise",
    "Hamstring Tendons": "can't flex the knee against resistance",
    "Rotator Cuff Tendons": "can't actively lift/hold the arm overhead against resistance",
    "Long Head Biceps Tendon": "can't flex/supinate the elbow against resistance, or a visible distal muscle-belly bulge ('Popeye' sign)",
    "Distal Biceps Tendon": "can't flex the elbow against resistance, or a visible proximal muscle-belly retraction ('Popeye' deformity)",
    "Triceps Tendon": "can't extend the elbow against resistance",
    "Tibialis Posterior Tendon": "can't invert the foot or do a single-leg heel raise",
    "Tibialis Anterior Tendon": "can't actively dorsiflex the foot (foot drop)",
    "Peroneal Tendons": "can't evert the foot against resistance",
    "Wrist Flexor Tendons": "can't flex the wrist or fingers against resistance",
    "Wrist Extensor Tendons": "can't extend the wrist against resistance",
}

_TENDON_KIND = {
    "tendinopathy": ("Tendinitis/Tendinosis (Tendinopathy)", 1,
                      "Gradual-onset, activity-related pain and stiffness, often worse at the start of activity and easing with warm-up, then returning after."),
    "partial_tear": ("Partial Tear", 2,
                      "More constant pain with palpable tenderness and weakness; may follow a sudden load after a period of tendinopathy."),
    "rupture": ("Complete Rupture", 3,
                 "Sudden, often audible pop with acute severe pain, marked weakness/loss of function, and possibly a palpable gap or altered contour."),
}


def _tendon_injury(tendon: str, joint: str, region: str, kind: str) -> dict:
    label, severity, pain = _TENDON_KIND[kind]
    t = tendon.lower()
    return {
        "name": f"{tendon} - {label}",
        "alt_names": [f"{tendon.split()[0]} Tendinitis"] if kind == "tendinopathy" else [],
        "tissue": "Tendon", "joint": joint, "region": region, "severity": severity,
        "severity_grades": "Tendinopathy/tendinitis (reactive-to-degenerative overload, no structural tear) -> partial tear -> complete rupture (structural failure).",
        "healing_phases": _phases("Tendon"),
        "pain_pattern": pain,
        "mechanism": f"Cumulative overload (tendinopathy) or a sudden forceful/eccentric load (partial-to-complete tear) on the {t}.",
        "movement_restrictions": {
            1: f"Manage load rather than rest completely — reduce the aggravating volume/intensity on the {t} while maintaining some pain-guided loading.",
            2: f"Avoid resisted and end-range loading of the {t} until re-evaluated; isometrics for pain relief may still be appropriate.",
            3: f"Avoid all loading of the {t} until medically evaluated — surgical repair is often indicated for complete rupture.",
        }[severity],
        "joint_position_restrictions": f"Avoid end-range stretch positions that load the {t} under tension until symptoms/healing allow.",
        "rom_restrictions": "Gentle pain-guided ROM; avoid aggressive stretching of a reactive or torn tendon.",
        "loading_restrictions": {1: "Isometric-to-heavy-slow-resistance loading is the core of tendinopathy rehab, dosed to a tolerable pain response.", 2: "Light, controlled isometric loading only until re-evaluated.", 3: "No loading until medically cleared."}[severity],
        "velocity_restrictions": "Avoid plyometric/energy-storage loading of the tendon until the later stages of rehab (tendinopathy) or until fully cleared (tear/rupture).",
        "impact_restrictions": "Reduce impact loading that reproduces symptoms; reintroduce gradually once tolerating heavier strength work." if severity == 1 else "Avoid impact loading until cleared.",
        "technical_faults_to_avoid": ["Complete rest without any loading (delays tendon adaptation)", "Too-rapid return to high-volume plyometric/impact work", "Ignoring a rising 24h pain response as a sign to back off"],
        "biomechanical_stresses_to_avoid": [f"Rapid spikes in the volume of high-load/energy-storage activity for the {t}"],
        "muscles_to_protect": [], "muscles_to_strengthen": [f"The muscle-tendon unit of the {tendon.lower()} via progressive resistance training"],
        "safe_movement_patterns": ["Isometric holds for pain modulation", "Slow, heavy resistance training within tolerable load"],
        "contraindicated_movement_patterns": ["Plyometric/ballistic loading of a reactive or torn tendon", "Loading through sharp/worsening pain"],
        "exercise_modifications": ["Isometrics -> isotonic (heavy slow resistance) -> energy-storage/plyometric progression", "Reduce aggravating volume while maintaining general training elsewhere"],
        "progression_criteria": ["24h pain response acceptable and trending down", "Strength improving toward symmetry", "Tolerates increasing load without symptom flare"],
        "regression_criteria": ["Pain increases and persists >24h after loading", "Morning stiffness/pain worsens"],
        "return_to_sport_criteria": ["Strength and function symmetric to the uninjured side", "Tolerates full sport-specific energy-storage/plyometric demand without symptom flare", "Clinician clearance for partial tear/rupture"],
        "absolute_contraindications": ["Continuing high-load training through a suspected partial/complete rupture"],
        "relative_contraindications": ["Rapid reintroduction of plyometric volume without a graded buildup"],
        "clinical_red_flags": [
            f"Sudden pop with inability to perform the tendon's key function ({TENDON_KEY_FUNCTION_TEST.get(tendon, 'a marked, function-specific weakness')}) — suspect rupture, refer urgently.",
            "Palpable gap or defect in the tendon",
        ],
        "risk_score_logic": _risk_note(severity, joint),
    }


# ============================================================================
# NAMED CONDITIONS — Joint Disorders, Cartilage, Bone, Spine, Nerve, Fascia,
# Overuse, and Degenerative categories (v5.0 addition). Each hand-specified
# via the shared `_generic` builder for condition-specific accuracy.
# ============================================================================
def _generic(name, alt_names, tissue, joint, region, severity, pain, mechanism,
             move_restr, red_flags, rts_extra=None, contraindicated=None, systemic=False) -> dict:
    """`systemic` (v5.16, default False; expanded v5.30): most injuries here
    only restrict exercises that stress the specific `joint` they're mapped
    to - that's the entire premise of the joint-keyed severity model this
    file's module docstring describes. A small number of injuries (the
    three concussion grades, plus - as of v5.30 - both acute compartment
    syndrome entries, three unstable/emergency spine entries, spinal cord
    injury, bilateral cervical facet dislocation, and displaced/flail-chest
    rib fracture) don't work that way - the thing that makes continued
    training unsafe
    isn't loading a specific joint, it's exertion/symptom-provocation in
    general, so gating only exercises tagged joint="Neck" would let a
    concussed user get a full "safe" squat/bench/deadlift session, which
    contradicts every one of this entry's own movement_restrictions /
    absolute_contraindications fields above. `systemic=True` flags an entry
    for progression_engine's resolve_systemic_injury() to gate every
    exercise in a session by this injury's severity/stage, independent of
    joint_stress tags - see that function's docstring. Inert unless a
    caller actually reads it, same as every other field here."""
    return {
        "name": name, "alt_names": alt_names, "tissue": tissue, "joint": joint, "region": region, "severity": severity,
        "systemic": systemic,
        "severity_grades": f"Severity tier {severity}/3 in this system's mild(1)-severe(3) load-tolerance model.",
        "healing_phases": _phases(tissue),
        "pain_pattern": pain, "mechanism": mechanism,
        "movement_restrictions": move_restr,
        "joint_position_restrictions": f"Avoid positions that reproduce symptoms in the {region.lower()}.",
        "rom_restrictions": "Pain-free ROM only; avoid forcing through a symptomatic range." if severity > 1 else "Gentle pain-free ROM/mobility work generally tolerated and often therapeutic.",
        "loading_restrictions": {1: "Light-to-moderate loading tolerated if pain-free.", 2: "Light, controlled loading only.", 3: "No loading until medically cleared."}[severity],
        "velocity_restrictions": "Avoid high-velocity/ballistic loading until symptoms resolve." if severity > 1 else "No specific restriction beyond symptom-guided loading.",
        "impact_restrictions": "Avoid impact loading until cleared." if severity > 1 else "Generally tolerated if asymptomatic.",
        "technical_faults_to_avoid": ["Loading through pain", "Ignoring a worsening symptom trend", "Skipping graded-exposure progression back to full activity"],
        "biomechanical_stresses_to_avoid": [f"Repetitive or high-magnitude load through the {region.lower()} beyond current tolerance"],
        "muscles_to_protect": [], "muscles_to_strengthen": [f"Stabilizing/supporting musculature around the {region.lower()}"],
        "safe_movement_patterns": ["Pain-free, controlled loading within current tolerance"],
        "contraindicated_movement_patterns": contraindicated or ["High-load or end-range movement that reproduces symptoms"],
        "exercise_modifications": ["Reduce load/ROM/volume and rebuild gradually", "Substitute exercises that don't stress the affected area while symptomatic"],
        "progression_criteria": ["Symptom-free through current loading", "No flare 24h after loading", "Clinician sign-off for severity 2-3 before advancing"],
        "regression_criteria": ["Symptoms return or worsen with current loading"],
        "return_to_sport_criteria": ["Full pain-free ROM and strength", "Sport-specific movement tolerated at full intensity"] + (rts_extra or []),
        "absolute_contraindications": ["Loading through sharp/mechanical pain"],
        "relative_contraindications": ["Rapid return to prior training load without a graded buildup"],
        "clinical_red_flags": red_flags,
        "risk_score_logic": _risk_note(severity, joint),
    }


NAMED_CONDITIONS = [
    # --- Joint Disorders ---
    _generic("Shoulder Impingement Syndrome", ["Subacromial Impingement"], "Joint", "Shoulder", "Shoulder (subacromial space)", 1,
        "Pain with overhead/reaching motion, often a painful arc between ~60-120 degrees of abduction.",
        "Repetitive overhead activity, poor scapular control, or rotator cuff weakness narrowing the subacromial space.",
        "Avoid sustained/repetitive overhead loading until scapular control and cuff strength improve.",
        ["Sudden severe weakness (possible acute cuff tear) — refer for evaluation."]),
    _generic("Shoulder Instability (General/Atraumatic)", ["Multidirectional Instability"], "Joint", "Shoulder", "Shoulder", 1,
        "A sense of looseness/apprehension with certain positions rather than sharp pain; may include subluxation episodes.",
        "Repetitive microtrauma, generalized ligamentous laxity, or inadequate dynamic stabilizer strength.",
        "Avoid end-range positions that reproduce apprehension; build rotator cuff/scapular strength.",
        ["Frank dislocation event or persistent neurological symptoms — refer for evaluation."]),

    # --- Shoulder Injuries (Traumatic Instability / Labrum / Rotator Cuff) ---
    _generic("Shoulder Instability - Grade 1 (Micro-instability)", ["Shoulder Micro-instability"], "Ligament/Capsule", "Shoulder", "Shoulder (glenohumeral capsule/labrum)", 1,
        "A subtle sense of looseness or 'dead arm' with overhead/throwing positions rather than clear pain, sometimes with mild discomfort at end-range external rotation and abduction.",
        "Repetitive overhead/throwing loading gradually stretching the anterior capsule and labrum beyond their normal tolerance, without a discrete traumatic event or true subluxation.",
        "Avoid loaded end-range overhead positions (heavy overhead pressing at end-range external rotation, aggressive stretching into apprehension) until scapular and rotator cuff control improve.",
        ["A true subluxation or dislocation event, or persistent numbness/tingling into the arm — refer for evaluation."],
        rts_extra=["Pain/apprehension-free overhead ROM under load", "Rotator cuff and scapular strength within normal limits before returning to full overhead/throwing volume"]),
    _generic("Shoulder Subluxation - Grade 2", ["Shoulder Partial Dislocation"], "Ligament/Capsule", "Shoulder", "Shoulder (glenohumeral joint)", 2,
        "A distinct episode of the shoulder partially slipping out of the socket and spontaneously reducing, with pain, apprehension, and often temporary weakness immediately after; the joint feels unstable with the arm in abduction/external rotation afterward.",
        "A forceful or awkward shoulder position (commonly abduction + external rotation, as in a fall onto an outstretched arm or a mistimed overhead/throwing motion) partially displacing the humeral head before it returns to place.",
        "No loaded overhead pressing, loaded external rotation at end-range, or contact/collision activity until stability is reassessed; light, pain-free ROM and rotator cuff isometrics in safe ranges only.",
        ["Numbness/tingling down the arm, or a sense the shoulder is 'about to go out' with normal daily movements — refer for evaluation; recurrent subluxation raises the likelihood of an underlying labral (Bankart) injury."],
        rts_extra=["Clinician-confirmed stability on exam", "Rotator cuff/scapular strength restored symmetric to the uninjured side before resuming overhead or contact activity"],
        contraindicated=["Loaded abduction + external rotation ('throwing position') until cleared"]),
    _generic("Shoulder Dislocation - Grade 3 (Anterior, First-Time)", ["First-Time Anterior Shoulder Dislocation"], "Joint", "Shoulder", "Shoulder (glenohumeral joint, anterior)", 3,
        "Severe pain and visible deformity at the moment of injury, with the arm held guarded away from the body; significant apprehension and weakness persist even after the joint is reduced.",
        "Forceful abduction and external rotation (a fall onto an outstretched, raised arm, or a direct blow) displacing the humeral head anteriorly out of the glenoid socket — this is the most common shoulder dislocation pattern.",
        "No shoulder loading until reduction is confirmed and a clinician has assessed for associated injury (labrum, bone, nerve); even after successful reduction, this needs a structured, graded rehabilitation rather than a quick return.",
        ["Check for numbness over the 'regimental badge' area of the shoulder and arm movement immediately after reduction (axillary nerve injury is a recognized complication) — refer for evaluation; first-time dislocations in younger, active people also carry a high recurrence risk that should be discussed with a specialist."],
        rts_extra=["Clinician-confirmed stability and full, pain-free strength before returning to overhead or contact/collision sport", "Consideration of surgical stabilization discussed with a specialist for younger/high-recurrence-risk individuals"],
        contraindicated=["Any shoulder loading before reduction and clinician clearance"]),
    _generic("Shoulder Dislocation - Posterior or Chronic Anterior", ["Posterior Shoulder Dislocation", "Recurrent Anterior Shoulder Dislocation"], "Joint", "Shoulder", "Shoulder (glenohumeral joint)", 3,
        "Posterior dislocations often present with the arm held in internal rotation and adduction with restricted external rotation (sometimes subtler and missed on initial exam); chronic anterior dislocation presents as recurrent instability with progressively lower-force triggers and increasing apprehension.",
        "Posterior dislocation typically follows a seizure, electric shock, or a direct posteriorly-directed force with the arm flexed/adducted; chronic anterior instability follows repeated dislocation events that progressively damage the labrum, capsule, and sometimes bone (glenoid/humeral head), lowering the threshold for further episodes.",
        "No shoulder loading until reduction (if applicable) and specialist assessment; recurrent/chronic cases usually need surgical stabilization rather than continued conservative management, since the structural damage tends to worsen with each episode.",
        ["A posterior dislocation is frequently missed on standard imaging views — if suspected (especially after a seizure or electrical injury), insist on views specifically looking for it; recurrent dislocations at progressively lower force are themselves a red flag for significant structural (labral/bony) damage requiring specialist evaluation."],
        rts_extra=["Specialist evaluation to determine whether surgical stabilization is needed given the recurrence/chronic pattern", "A full post-treatment rehabilitation protocol with clearance before returning to overhead or contact activity"],
        contraindicated=["Any shoulder loading until specialist assessment and reduction/stabilization are complete"]),
    _generic("Bony Bankart Lesion", ["Glenoid Rim Fracture (Bankart)"], "Bone/Labrum", "Shoulder", "Shoulder (anterior-inferior glenoid rim)", 3,
        "Pain and marked apprehension with the shoulder in abduction and external rotation, typically following a dislocation event, often with a persistent sense of instability even after the initial episode has settled.",
        "A shoulder dislocation forceful enough to fracture a fragment of the anterior-inferior glenoid rim along with the labral (Bankart) injury — the added bone loss meaningfully increases the risk of recurrent instability compared to a soft-tissue-only Bankart lesion.",
        "No shoulder loading until surgical evaluation; a bony fragment of meaningful size typically changes management toward surgical stabilization rather than conservative rehab alone.",
        ["This is itself a structural, often surgical-grade injury — any recurrent apprehension or instability episode should prompt referral, and bony involvement should specifically be discussed as a factor affecting recurrence risk and surgical decision-making."],
        rts_extra=["A full post-surgical rehabilitation protocol completed with surgeon/PT sign-off before returning to overhead or contact/collision sport"],
        contraindicated=["Any shoulder loading until surgical evaluation is complete"]),
    _generic("SLAP Tear - Type I (Frayed)", ["Superior Labral Fraying"], "Labrum", "Shoulder", "Shoulder (superior labrum)", 1,
        "Deep, poorly localized shoulder pain with overhead activity, sometimes a catching or clicking sensation; often subtle and easily confused with rotator cuff or impingement symptoms.",
        "Degenerative fraying of the superior labrum at the biceps anchor, typically from repetitive overhead loading (throwing, overhead lifting) rather than a single traumatic event.",
        "Reduce repetitive loaded overhead volume until symptoms settle; most other training, including moderate-load work below shoulder height, is generally tolerated.",
        ["Mechanical catching/locking or a positive apprehension-relocation pattern on exam (possible progression to a higher-grade tear) — refer for evaluation."],
        rts_extra=["Pain-free loaded overhead ROM before resuming full throwing/overhead volume"]),
    _generic("SLAP Tear - Type II (Detached)", ["Detached Superior Labral Tear"], "Labrum", "Shoulder", "Shoulder (superior labrum, biceps anchor)", 2,
        "Deep shoulder pain with overhead/throwing motion plus a sense of weakness or 'giving way' during the deceleration phase of throwing, sometimes with painful clicking.",
        "The superior labrum and biceps anchor detach from the glenoid rim — the most common SLAP tear pattern — usually from repetitive overhead/throwing overload or a traumatic traction event (e.g. falling on an outstretched, abducted arm).",
        "No loaded overhead pressing or throwing until formally evaluated; light, pain-free ROM and below-shoulder-height strength work only in the interim.",
        ["Persistent mechanical symptoms (catching, popping) with functional weakness despite rest — refer for evaluation, as this pattern often requires surgical repair in throwing athletes."],
        rts_extra=["Clinician/specialist clearance before resuming loaded overhead work", "A supervised, graded throwing progression rather than an abrupt return to full volume"],
        contraindicated=["Loaded overhead pressing or throwing until cleared"]),
    _generic("SLAP Tear - Type III/IV (Bucket-Handle Flap)", ["Bucket-Handle SLAP Tear"], "Labrum", "Shoulder", "Shoulder (superior labrum, with unstable flap fragment)", 3,
        "Mechanical catching, locking, or a sense of the shoulder 'jamming' during overhead motion, often more disabling and consistent than the pain-predominant presentation of lower-grade SLAP tears; Type IV additionally involves extension of the tear into the biceps tendon itself, adding biceps-related weakness/pain.",
        "A displaced ('bucket-handle') fragment of torn labrum, sometimes extending into the long head of the biceps tendon (Type IV), catching within the joint during motion — usually from a traumatic traction/overhead mechanism.",
        "No shoulder loading, particularly overhead or loaded elbow flexion/supination (which tensions the biceps anchor), until surgical evaluation; unstable flap tears typically require surgical repair or debridement.",
        ["True mechanical locking or a fixed block to motion — refer for evaluation without delay, as this pattern rarely resolves with conservative management alone."],
        rts_extra=["A full post-surgical rehabilitation protocol completed with surgeon/PT sign-off before returning to loaded overhead work or throwing"],
        contraindicated=["Any shoulder loading, particularly overhead or resisted elbow flexion/supination, until surgical evaluation is complete"]),
    _generic("Rotator Cuff Tear - Small (<1cm)", ["Small Rotator Cuff Tear"], "Tendon", "Shoulder", "Shoulder (rotator cuff)", 1,
        "Pain with overhead activity and a painful arc similar to impingement, with mild weakness in the specific movement (external rotation or abduction) tied to the involved tendon, but overall strength largely preserved.",
        "Degenerative wear or a relatively low-energy traumatic event causing a small, partial-to-full-thickness tear in one of the rotator cuff tendons, most commonly supraspinatus.",
        "Avoid sustained/repetitive overhead loading and heavy pressing until pain settles and cuff strength improves; most other training tolerated in a pain-free range given the small tear size.",
        ["A sudden increase in pain and weakness, or new inability to actively lift the arm overhead (possible extension of the tear) — refer for evaluation."],
        rts_extra=["Pain-free overhead strength testing symmetric to the uninjured side before resuming full overhead training volume"]),
    _generic("Rotator Cuff Tear - Medium (1-3cm)", ["Medium Rotator Cuff Tear"], "Tendon", "Shoulder", "Shoulder (rotator cuff)", 2,
        "More consistent pain and noticeably reduced strength in the involved movement (external rotation or abduction), often with night pain and difficulty sleeping on the affected side.",
        "A more substantial degenerative or traumatic tear involving a meaningful portion of a rotator cuff tendon's width, enough to produce a clear strength deficit on testing.",
        "No loaded overhead pressing or lifting until formally evaluated; light, pain-free ROM and low-load isometric cuff work only in the interim, since further loading risks tear extension.",
        ["Progressive weakness or an inability to hold the arm elevated against gravity (possible progression toward a large/full-thickness tear) — refer for evaluation to discuss conservative versus surgical management."],
        rts_extra=["Clinician/specialist clearance", "Restored strength on formal testing before resuming loaded overhead training"],
        contraindicated=["Loaded overhead pressing or lifting until cleared"]),
    _generic("Rotator Cuff Tear - Large (3-5cm)", ["Large Rotator Cuff Tear"], "Tendon", "Shoulder", "Shoulder (rotator cuff)", 2,
        "Significant pain and marked weakness in the involved movement, often with real functional limitation (difficulty reaching overhead or behind the back) and frequent night pain.",
        "A large tear spanning a substantial width of one or more rotator cuff tendons, typically resulting from either a significant traumatic event or advanced degenerative tearing, with meaningful risk of further retraction if left unaddressed.",
        "No shoulder loading beyond clinician-directed light ROM/isometrics until specialist evaluation; this size of tear commonly needs surgical discussion given the risk of progression to a massive, harder-to-repair tear.",
        ["Marked, functionally limiting weakness or a sudden worsening of function — refer promptly, as delaying evaluation on a large tear can allow it to progress toward a massive, retracted tear that's harder to repair."],
        rts_extra=["A full post-surgical (or specialist-directed conservative) rehabilitation protocol", "Clinician clearance before any return to loaded overhead work"],
        contraindicated=["Any shoulder loading beyond clinician-directed rehab until specialist evaluation is complete"]),
    _generic("Rotator Cuff Tear - Massive (>5cm, Retracted)", ["Massive Retracted Rotator Cuff Tear"], "Tendon", "Shoulder", "Shoulder (rotator cuff, multiple tendons)", 3,
        "Marked weakness — often a true inability to actively lift the arm overhead (pseudoparalysis in severe cases) — with the tendon retracted away from its normal insertion, usually involving more than one rotator cuff tendon.",
        "Longstanding, progressive degenerative tearing (or a severe traumatic event) that has gone unaddressed long enough for the tendon to retract and, often, undergo fatty infiltration — a pattern that significantly limits surgical repair options the longer it's left.",
        "No shoulder loading of any kind until surgical/specialist evaluation; this is a surgical-grade injury where the repair window and options are time-sensitive.",
        ["A true inability to actively raise the arm overhead is itself a red flag requiring prompt specialist evaluation — the longer a massive tear goes unaddressed, the more the repair options narrow due to tendon retraction and muscle quality changes."],
        rts_extra=["A full post-surgical rehabilitation protocol (or a specialist-directed functional/compensatory program if repair isn't feasible) with clearance before any return to loaded training"],
        contraindicated=["Any shoulder loading until surgical/specialist evaluation is complete"]),
    _generic("Adhesive Capsulitis (Frozen Shoulder)", ["Frozen Shoulder"], "Capsule", "Shoulder", "Shoulder (glenohumeral capsule)", 2,
        "Progressive, often severe loss of both active and passive shoulder ROM in multiple directions, with an initial painful ('freezing') phase, a stiff plateau phase, and a gradual ('thawing') recovery phase that can span many months.",
        "Inflammatory thickening and contracture of the glenohumeral joint capsule; often idiopathic, but associated with prolonged immobilization, diabetes, and thyroid disease.",
        "Avoid forcing end-range stretching or loaded positions that reproduce sharp pain, especially during the acute 'freezing' phase; gentle, consistent mobility work within tolerance is the mainstay rather than aggressive stretching or heavy loading.",
        ["ROM loss that is asymmetric in an unusual pattern, or accompanies neurological symptoms (possible cervical or nerve involvement rather than a true frozen shoulder) — refer for evaluation to confirm the diagnosis."],
        rts_extra=["Progressive, symptom-guided ROM recovery through the phases rather than a fixed timeline — this condition frequently takes many months and forcing it can prolong the painful phase"]),

    _generic("Lateral Epicondylalgia (Tennis Elbow)", ["Lateral Epicondylitis"], "Tendon", "Elbow", "Lateral Elbow", 1,
        "Pain over the lateral elbow with gripping or wrist extension against resistance.",
        "Repetitive wrist extension/gripping overload (racquet sports, manual work).",
        "Reduce repetitive gripping/wrist-extension load; isometric-to-progressive resistance loading is the core rehab strategy.",
        ["Persistent pain despite load management over months — refer for evaluation."]),
    _generic("Medial Epicondylalgia (Golfer's Elbow)", ["Medial Epicondylitis"], "Tendon", "Elbow", "Medial Elbow", 1,
        "Pain over the medial elbow with gripping or resisted wrist flexion/pronation.",
        "Repetitive wrist flexion/pronation overload (golf, throwing, manual work).",
        "Reduce repetitive gripping/wrist-flexion load; progressive resistance loading is the core rehab strategy.",
        ["Numbness/tingling into the ring/little fingers (possible ulnar nerve involvement) — refer for evaluation."]),

    # --- Elbow Injuries ---
    _generic("Elbow Ligament Sprain (MCL/LUCL) - Grade 1", ["Elbow UCL Sprain Grade 1"], "Ligament", "Elbow", "Elbow (medial or lateral collateral ligament)", 1,
        "Mild pain over the medial (MCL) or lateral (LUCL) elbow reproduced by valgus or varus stress, with tenderness on palpation but no felt instability.",
        "A single forceful valgus stress (throwing, arm wrestling) for the MCL, or a varus/posterolateral stress (fall onto an outstretched hand) for the LUCL, straining the ligament fibers without structural laxity.",
        "Avoid loaded valgus stress (throwing, heavy single-arm work) or varus/rotational stress until pain-free; light grip and ROM work tolerated throughout.",
        ["Any sense of the elbow shifting or 'giving way', locking, or increasing rather than decreasing pain over a few days — refer for evaluation."],
        rts_extra=["Pain-free valgus/varus stress test", "Full strength symmetric to the uninjured side before returning to throwing or pushing sports"]),
    _generic("Elbow Ligament Sprain (MCL/LUCL) - Grade 2", ["Elbow UCL Sprain Grade 2"], "Ligament", "Elbow", "Elbow (medial or lateral collateral ligament)", 2,
        "More persistent, often sharper medial or lateral elbow pain with mild-to-moderate laxity on valgus/varus stress testing, swelling, and pain with gripping.",
        "A greater-magnitude valgus or varus/rotational stress producing a partial ligament tear — fibers are disrupted and laxity is measurable, but the ligament remains in continuity.",
        "No loaded valgus or varus stress (throwing, heavy pressing with the elbow flared, arm wrestling) until stability is confirmed; light isometrics and pain-free ROM only in the interim.",
        ["Frank instability or apprehension on stress testing, or numbness/tingling into the ring and little fingers with an MCL-pattern injury (possible ulnar nerve involvement) — refer for evaluation."],
        rts_extra=["Clinician-confirmed stability on stress testing", "A completed, supervised graded throwing/loading progression before full return"],
        contraindicated=["Loaded valgus stress (throwing, heavy single-arm pressing/pulling) until cleared"]),
    _generic("Elbow Ligament Sprain (MCL/LUCL) - Grade 3 (Complete Rupture)", ["Elbow UCL Rupture", "Complete Elbow Collateral Ligament Tear"], "Ligament", "Elbow", "Elbow (medial or lateral collateral ligament)", 3,
        "Severe pain at the moment of injury followed by marked weakness, apprehension, and a subjective sense of instability; swelling and bruising are common.",
        "High-force valgus loading (common in overhead throwing athletes, classically leading to UCL/'Tommy John' injuries) or a traumatic fall/dislocation-type mechanism causing complete ligament disruption.",
        "No elbow loading of any kind until surgical evaluation; this grade is a surgical-candidacy injury, particularly for athletes in throwing or overhead sports.",
        ["This is itself a structural, often surgical-grade injury — any numbness/tingling into the ring and little fingers should also be flagged as possible concurrent ulnar nerve involvement; refer promptly."],
        rts_extra=["A full post-surgical (e.g. ligament reconstruction) or supervised conservative rehabilitation protocol completed with surgeon/PT sign-off before any return to loaded elbow work or throwing"],
        contraindicated=["Any elbow loading until surgical evaluation is complete"]),
    _generic("Radial Head Fracture - Type I (Non-Displaced)", ["Mason Type I Radial Head Fracture"], "Bone", "Elbow", "Elbow (radial head)", 2,
        "Lateral elbow pain worse with forearm rotation (pronation/supination) and gripping, tenderness directly over the radial head, often with painful or mildly limited elbow extension.",
        "A fall onto an outstretched hand with the forearm pronated, transmitting axial force up the radius into the radial head; the fracture line is stable and non-displaced.",
        "Avoid loaded forearm rotation and axial loading through the elbow (push-ups, planks, pressing) until healed; early gentle pain-free ROM is often encouraged to prevent stiffness.",
        ["A mechanical block to forearm rotation, marked joint effusion, or any numbness — refer for evaluation, as this can indicate a higher fracture grade than initially apparent."],
        rts_extra=["Full pain-free forearm rotation and elbow extension", "Radiographic confirmation of healing before resuming loaded elbow/forearm work"]),
    _generic("Radial Head Fracture - Type II (Displaced)", ["Mason Type II Radial Head Fracture"], "Bone", "Elbow", "Elbow (radial head)", 2,
        "Similar lateral elbow pain to a non-displaced fracture but often with a more definite mechanical block or catching sensation during forearm rotation.",
        "A fall onto an outstretched, pronated hand producing a fracture fragment displaced enough (typically >2mm or a meaningful articular step-off) to risk blocking normal forearm rotation.",
        "No elbow or forearm-rotation loading until an orthopedic evaluation determines whether the fragment needs surgical fixation.",
        ["A persistent mechanical block to pronation/supination — this often indicates a fragment large or displaced enough to need surgical fixation; refer for evaluation."],
        rts_extra=["Orthopedic clearance — whether managed operatively or non-operatively — before resuming loaded elbow/forearm work"]),
    _generic("Radial Head Fracture - Type III (Comminuted)", ["Mason Type III Radial Head Fracture"], "Bone", "Elbow", "Elbow (radial head)", 3,
        "Severe elbow pain, significant swelling, and marked loss of both elbow and forearm-rotation motion immediately after injury.",
        "A high-energy fall or direct impact producing a multi-fragment (comminuted) fracture of the radial head that usually cannot be anatomically reduced without surgery (fixation or radial head replacement).",
        "No elbow loading of any kind until surgical management and clearance; this is a surgical-grade fracture.",
        ["This is itself a surgical-grade injury — watch for associated ligament injury or elbow instability, which is common with this fracture pattern; refer promptly."],
        rts_extra=["A full post-surgical rehabilitation protocol completed with surgeon/PT sign-off before any return to loaded elbow training"],
        contraindicated=["Any elbow loading until surgical management and clearance"]),
    _generic("Radial Head Fracture - Type IV (Fracture-Dislocation)", ["Mason Type IV Radial Head Fracture"], "Bone", "Elbow", "Elbow (radial head, with associated dislocation)", 3,
        "Severe pain with visible deformity and gross elbow instability alongside the fracture; the elbow may appear grossly out of position.",
        "A combined, high-energy mechanism producing a radial head fracture together with elbow dislocation (frequently part of a 'terrible triad' injury pattern with coronoid and ligament involvement).",
        "No elbow loading of any kind — this requires emergency reduction/stabilization and orthopedic/surgical management.",
        ["This is an orthopedic emergency: assess and monitor distal pulses and sensation for neurovascular compromise, and seek immediate medical evaluation."],
        rts_extra=["A full post-surgical rehabilitation protocol and specialist clearance before any return to loading, given the high risk of residual instability with this pattern"],
        contraindicated=["Any elbow loading or forced motion until emergency evaluation and surgical management are complete"]),
    _generic("Osteochondritis Dissecans (OCD) / Elbow Loose Bodies", ["Elbow OCD", "Capitellar OCD"], "Cartilage/Bone", "Elbow", "Elbow (radiocapitellar joint)", 2,
        "Activity-related lateral elbow pain, often with catching, locking, or a grinding sensation, typically worse with valgus loading such as throwing.",
        "Repetitive valgus and compressive loading of the radiocapitellar joint — classically seen in young throwing or gymnastics athletes — causing localized cartilage/subchondral bone injury that can progress to an unstable fragment.",
        "Avoid repetitive valgus loading (throwing) and axial loading through an extended elbow (handstands, heavy pressing) until imaging clarifies whether the lesion is stable.",
        ["True mechanical locking or a fixed block to elbow motion (suggesting an unstable fragment) — refer for evaluation, as unstable lesions often require surgical management."],
        rts_extra=["Imaging confirming a stable, healing lesion", "A clinician-supervised, graded return to throwing/loading volume rather than an abrupt return to full sport"]),
    _generic("Distal Biceps Tendon Rupture", ["Distal Biceps Tear"], "Tendon", "Elbow", "Elbow (distal biceps insertion)", 3,
        "Sudden, sharp pain at the front of the elbow during forceful resisted flexion, often with an audible pop, followed by bruising and a visible/palpable proximal retraction of the biceps muscle belly (\"Popeye deformity\").",
        "A forceful eccentric load against a flexed, supinated elbow — classically, trying to catch or control a heavy falling/swinging object, or a sudden maximal resisted curl.",
        "No elbow flexion or forearm supination loading until surgical evaluation; in active individuals this is typically managed surgically to restore full flexion/supination strength.",
        ["This is itself a surgical-grade injury — a visible defect/retraction and marked supination weakness confirm the diagnosis; refer promptly, as outcomes are best with earlier repair."],
        rts_extra=["A full post-surgical rehabilitation protocol completed with surgeon/PT sign-off before resuming loaded elbow flexion/supination work"],
        contraindicated=["Any resisted elbow flexion or forearm supination loading until surgical evaluation is complete"]),
    _generic("LUCL Tear (Posterolateral Rotator Instability)", ["Lateral Ulnar Collateral Ligament Tear", "Posterolateral Rotatory Instability"], "Ligament", "Elbow", "Elbow (lateral ulnar collateral ligament)", 3,
        "Recurrent lateral elbow pain or apprehension with pushing up from a chair or extending the elbow from a flexed, forearm-supinated, valgus-loaded position; some report episodes of clunking or subluxation.",
        "Injury to the lateral ulnar collateral ligament, most often following a prior elbow dislocation (or, less commonly, iatrogenic injury), producing posterolateral rotatory instability of the elbow.",
        "Avoid the provocative position — elbow extension from flexion with the forearm supinated under valgus load (push-ups, dips, pressing) — until stability is confirmed.",
        ["Recurrent subluxation or dislocation episodes — refer for evaluation, as this pattern often requires surgical reconstruction."],
        rts_extra=["Surgical/hand-specialist clearance", "Full strength through the provocative position without apprehension before returning to pushing/pressing sports"],
        contraindicated=["Pushing/pressing or extending the elbow from a flexed, supinated position under load until cleared"]),
    _generic("Simple Elbow Dislocation", ["Elbow Dislocation (Uncomplicated)"], "Joint", "Elbow", "Elbow (ligamentous complex, no fracture)", 3,
        "Severe pain and obvious deformity at the moment of injury; the elbow is held guarded in slight flexion and appears visibly out of position before reduction.",
        "A fall onto an outstretched hand forcing the elbow into hyperextension and valgus, or a direct blow, disrupting the joint's ligamentous stability without an associated fracture (hence 'simple').",
        "No elbow loading until reduction and stability are confirmed by a clinician; even after a successful closed reduction, this remains a joint-stability injury requiring a graded, supervised return.",
        ["Check distal pulses and hand sensation immediately — neurovascular compromise is the urgent concern with this mechanism and needs emergency evaluation before or immediately after reduction."],
        rts_extra=["Full, pain-free ROM and strength", "Clinician confirmation of joint stability before any return to contact or loaded training"],
        contraindicated=["Any elbow loading before reduction and clinician-confirmed stability"]),
    _generic("Elbow Fracture-Dislocation", ["Complex Elbow Fracture-Dislocation", "Terrible Triad Injury"], "Joint", "Elbow", "Elbow (with associated fracture, e.g. coronoid/radial head)", 3,
        "Severe pain, visible deformity, and marked instability, with an associated fracture (commonly the coronoid and/or radial head — the 'terrible triad' pattern) making the joint substantially less stable than a simple dislocation.",
        "High-energy trauma combining a dislocation with a fracture of one or more of the elbow's bony stabilizers, at high risk for recurrent instability if not appropriately managed.",
        "No elbow loading — this requires orthopedic/surgical management given the combined bony and ligamentous injury.",
        ["Check distal pulses and hand sensation for neurovascular compromise; this is an orthopedic emergency requiring prompt reduction and surgical evaluation."],
        rts_extra=["A full post-surgical rehabilitation protocol and specialist clearance before any return to loading, given the high recurrent-instability risk of this pattern"],
        contraindicated=["Any elbow loading or forced motion until emergency evaluation and surgical management are complete"]),

    _generic("Hip Impingement (Femoroacetabular Impingement, FAI)", ["FAI Syndrome"], "Joint", "Hip", "Hip", 1,
        "Groin pain with deep hip flexion, often with a pinching sensation (e.g. deep squat, prolonged sitting).",
        "Bony morphology (cam/pincer) causing abnormal contact between femur and acetabulum at end-range flexion/rotation.",
        "Avoid deep, loaded hip flexion combined with internal rotation until symptoms settle; work within a pain-free range.",
        ["Locking or catching with true mechanical block (possible labral tear) — refer for evaluation."]),
    _generic("Hip Instability (Atraumatic/Microinstability)", [], "Joint", "Hip", "Hip", 1,
        "A sense of looseness or 'giving way' rather than sharp pain, often with pivoting/end-range rotation.",
        "Capsular laxity, repetitive end-range loading, or after labral injury.",
        "Avoid uncontrolled end-range rotation under load; build hip/pelvic stabilizer strength.",
        ["True instability/subluxation episodes — refer for evaluation."]),
    _generic("Patellofemoral Pain Syndrome (PFPS)", ["Runner's Knee"], "Joint", "Knee", "Anterior Knee", 1,
        "Diffuse anterior knee pain, worse with stairs, squatting, or prolonged sitting (theater sign).",
        "Altered patellar tracking/loading, often from hip/quad strength or movement-pattern deficits.",
        "Reduce high-flexion loaded knee positions (deep squats, lunges) until symptoms settle; address hip/quad strength.",
        ["True mechanical locking or giving-way (possible loose body/instability) — refer for evaluation."]),
    _generic("Chondromalacia Patella", [], "Cartilage", "Knee", "Patellofemoral Joint", 1,
        "Anterior knee pain and grinding/crepitus with knee flexion under load (stairs, squats).",
        "Cartilage softening/breakdown on the underside of the patella from repetitive/abnormal patellofemoral loading.",
        "Reduce deep-flexion loaded knee positions until symptoms settle; build quad/hip control.",
        ["Significant effusion or locking — refer for evaluation."]),
    _generic("Patellar Instability (Recurrent)", [], "Joint", "Knee", "Anterior Knee", 2,
        "Apprehension or a sense of the kneecap shifting, especially with combined flexion and rotation.",
        "Prior dislocation, structural predisposition (trochlear dysplasia), or MPFL insufficiency.",
        "Avoid combined knee flexion + rotation under load; avoid positions that reproduce apprehension.",
        ["A dislocation event — refer for urgent evaluation."]),
    _generic("Osteochondral Injury (General)", ["OCD Lesion"], "Cartilage", "Knee", "Joint Surface (variable)", 2,
        "Deep, poorly localized joint pain, sometimes with catching/locking if a fragment is unstable.",
        "Repetitive microtrauma or an acute traumatic impact to the joint surface.",
        "Avoid high-impact/pivoting loading on the joint until imaging/clinical status clarifies stability.",
        ["Locking, catching, or a loose-body sensation — refer for evaluation."]),
    _generic("Chronic Ankle Instability", [], "Joint", "Ankle", "Ankle", 1,
        "Recurrent 'giving way' or a sense of looseness, often after prior sprains, without necessarily acute pain.",
        "Residual laxity and impaired proprioception following prior ankle sprain(s).",
        "Avoid uneven/unstable surfaces and uncontrolled cutting until proprioceptive control improves; brace/tape as needed.",
        ["Recurrent frank giving-way episodes causing falls — refer for evaluation."]),
    _generic("Carpal Instability", [], "Joint", "Wrist", "Wrist", 2,
        "Pain and a clicking/clunking sensation with wrist loading or specific motions.",
        "Ligamentous injury (often scapholunate) altering normal carpal bone kinematics.",
        "Avoid loaded end-range wrist extension and axial loading (e.g. planks, push-ups) until evaluated.",
        ["Progressive weakness or grip loss — refer for evaluation."]),
    _generic("Wrist Loose Bodies", ["Wrist Joint Mice"], "Cartilage/Synovium", "Wrist", "Wrist Joint", 1,
        "Intermittent, activity-related wrist pain with occasional catching, locking, or a sense of something shifting inside the joint; often worse with weight-bearing wrist extension.",
        "A loose cartilage or synovial fragment (from prior trauma, OCD, or degenerative change) moving freely within the joint and intermittently catching between the joint surfaces.",
        "Avoid loaded weight-bearing wrist extension (planks, push-ups, handstands, front-rack loading) during symptomatic episodes; light ROM/grip work tolerated between episodes.",
        ["True mechanical locking that doesn't self-resolve with gentle movement, or rapidly increasing swelling — refer for evaluation/imaging."],
        rts_extra=["No catching/locking through a full loaded ROM check before resuming weight-bearing wrist work"]),
    _generic("TFCC Tear - Class 1 Type A (Central Perforation)", ["TFCC Central Tear"], "Fibrocartilage", "Wrist", "Triangular Fibrocartilage Complex (central disc)", 2,
        "Ulnar-sided wrist pain, worse with gripping, loaded wrist rotation (forearm pronation/supination under load), or ulnar deviation; often a dull ache with occasional clicking.",
        "Traumatic (a fall on an outstretched, rotated hand) or degenerative central-disc perforation of the TFCC — this is the most common TFCC tear pattern and, being in the disc's avascular central zone, has limited intrinsic healing capacity.",
        "Avoid loaded ulnar deviation, forceful gripping combined with forearm rotation, and axial loading through an extended wrist (planks, push-ups, heavy pulling with a hook/rotated grip) until symptoms settle.",
        ["Persistent mechanical clicking/catching with pain despite activity modification, or a sense of DRUJ (distal radioulnar joint) instability — refer for evaluation; central perforations that fail conservative management are managed differently (debridement) than peripheral tears."],
        rts_extra=["Pain-free grip strength symmetric to the uninjured side", "No pain with loaded forearm rotation under axial load"]),
    _generic("TFCC Tear - Class 1 Type B/C (Torn from Bone)", ["TFCC Peripheral Tear", "Ulnar-Sided TFCC Avulsion"], "Fibrocartilage", "Wrist", "Triangular Fibrocartilage Complex (peripheral/foveal attachment)", 2,
        "Ulnar-sided wrist pain with a sense of instability or 'giving way' during loaded rotation, often more pronounced than a central tear; pain with pressing up from a chair or loaded pulling.",
        "Traumatic avulsion of the TFCC from its ulnar (foveal) or dorsal/volar peripheral attachment, typically from a fall on an outstretched hand with forceful rotation — because this zone is well-vascularized, it has better healing potential than a central tear but a higher associated instability risk.",
        "Avoid loaded ulnar deviation, forearm rotation under load, and any pushing/pulling through an extended, weight-bearing wrist until DRUJ stability is confirmed; immobilization is more often indicated here than for central tears.",
        ["Clinical signs of DRUJ instability (a palpable clunk or excess translation of the ulna) — refer for evaluation, as peripheral avulsions are frequently repaired surgically rather than managed conservatively."],
        rts_extra=["Confirmed DRUJ stability on clinical exam", "Full pain-free grip and loaded rotation before returning to pulling/pressing movements"],
        contraindicated=["Loaded forearm rotation (e.g. rotating dumbbell presses, loaded hammer curls at end-range) until DRUJ stability is confirmed"]),
    _generic("TFCC Tear - Class 2 (Degenerative)", ["Ulnocarpal Impaction Syndrome", "TFCC Degenerative Wear"], "Fibrocartilage", "Wrist", "Triangular Fibrocartilage Complex", 1,
        "Gradual-onset, activity-related ulnar-sided wrist ache without a specific injury moment; worse with repetitive loaded gripping/rotation over time, better with rest.",
        "Cumulative degenerative wear of the TFCC, often associated with ulnar-positive variance (a relatively longer ulna) causing chronic impaction between the ulna and carpus rather than a single traumatic event.",
        "Reduce repetitive loaded ulnar deviation and gripping volume; most training tolerated in a pain-free range since this is a low-grade, gradual-onset presentation.",
        ["New onset of instability, sudden increase in pain, or mechanical catching (possible progression to a structural tear) — refer for evaluation."]),
    _generic("Scapholunate Ligament Tear - Grade I (Mild Stretch)", ["Scapholunate Sprain", "Predynamic Scapholunate Instability"], "Ligament", "Wrist", "Scapholunate Ligament (dorsal wrist)", 1,
        "Dorsal wrist pain localized just distal to the wrist crease, worse with weight-bearing wrist extension (push-ups, planks) or forceful gripping; no clunking or visible deformity.",
        "A fall on an outstretched, extended and ulnarly-deviated wrist, or forceful wrist extension under load, straining the scapholunate ligament without disrupting normal carpal alignment (a 'predynamic' injury — imaging is often normal).",
        "Avoid loaded weight-bearing wrist extension (planks, push-ups, front-rack barbell positions, handstands) until pain-free; grip and forearm work in neutral wrist positions is generally tolerated.",
        ["A popping sensation at time of injury, or any clicking/clunking with wrist motion (possible progression to a higher-grade tear) — refer for evaluation before resuming loaded wrist extension."],
        rts_extra=["Pain-free loaded wrist extension (e.g. full push-up position) held under bodyweight before resuming heavier axial wrist loading"]),
    _generic("Scapholunate Ligament Tear - Grade II (Partial Tear)", ["Dynamic Scapholunate Instability"], "Ligament", "Wrist", "Scapholunate Ligament", 2,
        "Dorsal wrist pain with a distinct clicking or clunking sensation during wrist motion under load, plus a sense of weakness or instability with gripping; symptoms appear or worsen specifically under load even if the wrist looks/feels normal at rest.",
        "A partial tear of the scapholunate ligament sufficient to allow abnormal (but not yet fixed) scapholunate motion under load — the classic 'dynamic instability' stage, often missed on standard static X-rays and requiring stress views or MRI.",
        "No loaded weight-bearing wrist extension or axial loading (planks, push-ups, heavy pulling/gripping) until formally evaluated; light, pain-free ROM and grip work only.",
        ["A positive 'catch-up clunk' with wrist motion, or grip weakness disproportionate to pain — refer for evaluation; missed dynamic instability commonly progresses to fixed instability and eventual SLAC wrist."],
        rts_extra=["Clinician/hand-specialist clearance confirming stability before resuming any loaded wrist extension or axial loading"],
        contraindicated=["Loaded weight-bearing wrist extension (push-ups, planks, handstands, front-rack barbell work) until cleared"]),
    _generic("Scapholunate Ligament Tear - Grade III (Advanced Tear)", ["Static Scapholunate Instability"], "Ligament", "Wrist", "Scapholunate Ligament (with secondary stabilizer involvement)", 2,
        "Persistent dorsal wrist pain and weakness with visible or palpable abnormal carpal alignment on exam; grip strength is markedly reduced compared to the uninjured side.",
        "A more extensive scapholunate ligament tear with failure of secondary stabilizing structures, producing a fixed (static) abnormal relationship between the scaphoid and lunate that is now visible on standard imaging (widened scapholunate gap).",
        "No loading of the wrist in any capacity until surgical evaluation; this stage typically requires ligament reconstruction rather than conservative management, and continuing to load it risks accelerating cartilage wear toward SLAC wrist.",
        ["Fixed carpal malalignment on imaging with ongoing symptoms — refer promptly; delayed treatment at this stage is a major risk factor for progression to SLAC wrist."],
        rts_extra=["Surgical/hand-specialist clearance and a supervised post-reconstruction rehab progression before any return to loaded wrist training"],
        contraindicated=["Any axial or weight-bearing loading of the wrist until surgical evaluation is complete"]),
    _generic("Scapholunate Ligament Tear - Grade IV (Complete Tear)", ["Complete Scapholunate Dissociation"], "Ligament", "Wrist", "Scapholunate Ligament (complete disruption)", 3,
        "Significant wrist pain, weakness, and instability with obvious abnormal carpal mechanics; grip is severely limited and the wrist may feel like it 'gives way' with basic tasks.",
        "Complete disruption of the scapholunate ligament and its secondary stabilizers, producing frank scapholunate dissociation — the carpus can no longer transmit load normally, and this is a surgical condition.",
        "No wrist loading of any kind until surgical management and a formal post-operative rehabilitation protocol are underway.",
        ["This is a structural, surgical-grade injury on its own — any further loading before repair risks irreversible cartilage damage and progression to SLAC wrist; refer for surgical evaluation without delay."],
        rts_extra=["Full post-surgical rehabilitation protocol completed with hand-therapist/surgeon sign-off before any return to axial wrist loading or contact/collision sport"],
        contraindicated=["Any wrist loading until surgical repair and formal post-operative clearance"]),
    _generic("SLAC Wrist (Scapholunate Advanced Collapse)", [], "Joint (Degenerative)", "Wrist", "Wrist (radioscaphoid and later midcarpal joints)", 3,
        "Chronic, progressive dorsal wrist pain and stiffness with reduced grip strength, developing over months to years as a late-stage consequence of untreated scapholunate instability.",
        "The predictable, staged pattern of degenerative arthritis that follows chronic, uncorrected scapholunate ligament instability, as the unstable carpus wears down first the radioscaphoid joint and eventually the midcarpal joint.",
        "No axial or weight-bearing wrist loading; this is an established arthritic/degenerative condition managed by a hand specialist (salvage procedures such as proximal row carpectomy or fusion are common), not something to load through in training.",
        ["This is itself an established degenerative diagnosis requiring specialist management — any new instability, sudden pain increase, or nerve symptoms warrant prompt referral."],
        rts_extra=["Hand-specialist clearance defining safe long-term loading limits, since the underlying joint changes are permanent even after surgical management"],
        contraindicated=["Axial/weight-bearing wrist loading (push-ups, planks, front-rack/overhead barbell positions, heavy pulling) without specialist-defined limits"]),
    _generic("Perilunate Dislocation", ["Perilunate Dislocation/Fracture-Dislocation"], "Joint (Complex Ligamentous Injury)", "Wrist", "Wrist (carpus around the lunate)", 3,
        "Severe wrist pain, swelling, and deformity immediately following a high-energy trauma; often accompanied by numbness or tingling in the hand from associated median nerve compression.",
        "A high-energy fall on an outstretched, hyperextended wrist (e.g. from height, high-speed sport, or a heavy loaded fall) causing progressive ligamentous disruption around the lunate — this is a severe wrist trauma, not a training-load injury, and is frequently missed on initial X-ray if not specifically looked for.",
        "No wrist loading or movement outside emergency immobilization and surgical management; this is an orthopedic emergency given the high risk of median nerve injury and, if reduction is delayed, avascular necrosis of the lunate.",
        ["Numbness/tingling in the median nerve distribution (thumb, index, middle finger) after this mechanism is an emergency sign of acute carpal tunnel/nerve compression — seek immediate medical evaluation; this injury is commonly missed on a single X-ray view and needs a clinician who is specifically looking for it."],
        rts_extra=["Full surgical reduction/fixation and a formal hand-therapy rehabilitation protocol completed with surgeon sign-off before any return to loaded wrist training or contact sport"],
        contraindicated=["Any wrist loading or forced motion until emergency evaluation and surgical management are complete"]),
    _generic("Temporomandibular Joint (TMJ) Disorder", ["TMJ Dysfunction"], "Joint", "Neck", "Jaw/TMJ", 1,
        "Jaw pain, clicking/popping, or restricted opening, sometimes with associated headache/neck tension.",
        "Clenching/grinding, direct trauma, or postural/cervical contributing factors.",
        "Avoid loaded neck positions that aggravate jaw tension (e.g. heavy overhead bracing with jaw clenching); no major exercise-programming impact beyond general awareness.",
        ["Jaw locking that cannot self-reduce, or trauma with suspected fracture — refer for evaluation."]),

    # --- Cartilage (beyond meniscus, already in legacy) ---
    _generic("Articular Cartilage Lesion - Knee", ["Chondral Defect - Knee"], "Cartilage", "Knee", "Knee Joint Surface", 2,
        "Deep joint-line pain and swelling with loading, sometimes with mechanical catching.",
        "Acute impact/shear injury or chronic overload of the articular surface.",
        "Avoid high-impact/pivoting loading until imaging/clinical status clarifies severity.",
        ["Locking or a loose-body sensation — refer for evaluation."]),
    _generic("Articular Cartilage Lesion - Hip", [], "Cartilage", "Hip", "Hip Joint Surface", 2,
        "Deep groin/hip pain with weight-bearing and rotational loading.",
        "Chronic FAI-related overload or acute traumatic shear injury.",
        "Avoid deep, loaded hip flexion/rotation until evaluated.",
        ["Mechanical locking or catching — refer for evaluation."]),
    _generic("Articular Cartilage Lesion - Ankle", ["Talar Dome Lesion"], "Cartilage", "Ankle", "Ankle Joint Surface", 2,
        "Deep ankle pain with weight-bearing, sometimes with catching/locking.",
        "Often follows an ankle sprain with an associated impaction injury to the talar dome.",
        "Avoid high-impact/pivoting loading until evaluated.",
        ["Persistent locking/catching — refer for evaluation."]),

    # --- Bone Injuries ---
    _generic("Stress Reaction - Tibia", ["Bone Stress Reaction"], "Bone", "Knee", "Tibia", 1,
        "Gradual-onset, activity-related bone pain that initially resolves with rest and progressively worsens if training continues.",
        "Cumulative repetitive loading (running/jumping volume) exceeding the bone's adaptive capacity.",
        "Reduce impact loading immediately; avoid running/jumping until re-evaluated.",
        ["Pain at rest or with normal walking (possible progression to stress fracture) — refer for evaluation."]),
    _generic("Stress Fracture - Tibia", [], "Bone", "Knee", "Tibia", 2,
        "Focal, well-localized bone pain, worse with impact, often present with walking; point tenderness on exam.",
        "Continued repetitive loading beyond a stress reaction without adequate offloading.",
        "Non-impact activity only (pool running, cycling as tolerated) until cleared; no running/jumping.",
        ["Anterior (tension-side) tibial stress fracture — higher nonunion/complication risk, requires prompt medical evaluation."]),
    _generic("Stress Fracture - Metatarsal", [], "Bone", "Ankle", "Foot (Metatarsal)", 2,
        "Focal forefoot pain with weight-bearing, point tenderness over a specific metatarsal.",
        "Repetitive impact loading (running, jumping, marching).",
        "Non-impact activity only until cleared; may require protected weight-bearing (boot).",
        ["5th metatarsal (Jones) fracture — higher nonunion risk, requires prompt medical evaluation."]),
    _generic("Stress Fracture - Femoral Neck", [], "Bone", "Hip", "Femoral Neck", 3,
        "Groin or anterior thigh pain with weight-bearing, may be poorly localized early on.",
        "Repetitive impact loading, often in the context of relative energy deficiency/low bone density.",
        "Non-weight-bearing/protected weight-bearing per medical guidance; no impact loading.",
        ["This is a high-risk stress fracture site with fracture-displacement risk — requires prompt medical evaluation, do not continue training."]),
    _generic("Stress Fracture - Pars Interarticularis (Spondylolysis)", ["Pars Stress Fracture"], "Bone", "Lower Back", "Lumbar Spine (Pars)", 2,
        "Focal low back pain with extension/rotation loading, common in young athletes in extension-heavy sports.",
        "Repetitive lumbar extension/rotation loading (gymnastics, cricket fast bowling, weightlifting).",
        "Avoid lumbar extension/rotation loading until cleared; core stability work in neutral spine.",
        ["Bilateral pars defects with slip progression (spondylolisthesis) or neurological symptoms — refer for evaluation."]),
    _generic("Avulsion Fracture - Pelvis/Hip", [], "Bone", "Hip", "Pelvis", 2,
        "Sudden, sharp pain at a tendon attachment site (e.g. ASIS, ischial tuberosity) during forceful contraction, often in adolescents.",
        "Forceful, often eccentric muscle contraction pulling a bone fragment from its attachment (sprinting, kicking).",
        "Avoid loading the involved muscle-tendon-bone unit until imaging-confirmed healing.",
        ["Significant fragment displacement — may require surgical evaluation."]),
    _generic("Compression Fracture - Thoracic/Lumbar Spine", [], "Bone", "Lower Back", "Thoracic/Lumbar Spine", 2,
        "Localized back pain, worse with axial loading/flexion, may follow a fall or, in older adults, minimal trauma.",
        "Axial loading beyond bone tolerance — trauma, or low bone density with minor mechanical stress.",
        "Avoid axial loading and spinal flexion until medically cleared; screen for underlying bone health.",
        ["Neurological symptoms (numbness, weakness, bowel/bladder changes) — emergency evaluation for possible cord/cauda equina involvement."]),
    _generic("Bone Bruise (Bone Contusion)", [], "Bone", "Knee", "Variable (commonly knee)", 1,
        "Deep, diffuse joint pain and swelling following an impact, without a fracture line on imaging.",
        "Direct impact or compressive trauma to the bone (contact injury, fall).",
        "Reduce impact/high-load activity on the joint until pain and swelling resolve.",
        ["Pain significantly worse than expected, or non-weight-bearing — refer for evaluation to rule out fracture."]),
    _generic("Periostitis (Shin)", ["Periosteal Reaction"], "Bone", "Ankle", "Tibial Shaft (periosteum)", 1,
        "Aching, diffuse pain along the shin during/after impact activity.",
        "Repetitive impact loading irritating the periosteum, often an early-stage MTSS/stress-reaction presentation.",
        "Reduce impact loading volume; address contributing training-load/footwear factors.",
        ["Pain progressing to focal point tenderness (possible progression to stress fracture) — refer for evaluation."]),
    _generic("Shin Splints (Medial Tibial Stress Syndrome, MTSS)", [], "Bone", "Ankle", "Medial Tibial Border", 1,
        "Diffuse aching pain along the medial tibial border, worse at the start of a run and easing with warm-up, then returning after.",
        "Rapid increase in running volume/intensity, often combined with biomechanical or footwear factors.",
        "Reduce running volume/intensity; address load progression, footwear, and surface.",
        ["Focal point tenderness rather than diffuse pain (possible progression to stress fracture) — refer for evaluation."]),

    # --- Spine Disorders ---
    _generic("Cervical Strain (Acute)", ["Neck Strain"], "Spine", "Neck", "Cervical Spine", 1,
        "Localized neck pain and stiffness, often with reduced ROM, following an awkward load or sustained posture.",
        "Muscular overload, sustained poor posture, or minor traumatic mechanism.",
        "Avoid loaded end-range neck positions and heavy overhead/loaded carries until pain settles.",
        ["Radiating arm pain/numbness/weakness (possible radiculopathy) — refer for evaluation."]),
    _generic("Cervical Disc Herniation", [], "Spine", "Neck", "Cervical Spine", 2,
        "Neck pain that may radiate into the arm following a dermatomal pattern, sometimes with numbness/weakness.",
        "Disc material displacement from repetitive flexion/loading or an acute traumatic mechanism.",
        "Avoid loaded cervical flexion and axial loading (heavy overhead work) until symptoms settle.",
        ["Progressive weakness, or myelopathic signs (gait/balance changes, hand clumsiness) — urgent evaluation."]),
    _generic("Cervical Radiculopathy", [], "Nerve", "Neck", "Cervical Nerve Root", 2,
        "Neck pain radiating into the arm in a specific nerve-root distribution, with possible numbness/weakness.",
        "Nerve root compression from disc herniation, foraminal narrowing, or facet hypertrophy.",
        "Avoid positions that reproduce or worsen radicular symptoms (loaded cervical extension/rotation toward the symptomatic side).",
        ["Progressive motor weakness or myelopathic signs — urgent evaluation."]),
    _generic("Whiplash-Associated Disorder", ["Whiplash"], "Spine", "Neck", "Cervical Spine", 1,
        "Neck pain and stiffness, sometimes with headache/dizziness, following a rapid acceleration-deceleration mechanism.",
        "Rapid, forceful acceleration-deceleration of the neck (commonly a motor vehicle collision).",
        "Avoid loaded end-range neck positions until pain/ROM improve; early gentle movement is generally favored over prolonged rest.",
        ["Severe headache, visual changes, or neurological symptoms — refer for evaluation."]),
    _generic("Cervical Facet Injury - Stage 1 (Distraction Instability)", ["Cervical Facet Sprain", "Cervical Facet Capsular Injury"], "Ligament", "Neck", "Cervical Facet Joint Capsule", 1,
        "Localized, one-sided neck pain over the facet line, worse with end-range extension or rotation toward the involved side; tender to palpation over the joint, no arm symptoms.",
        "Hyperflexion, hyperextension, or forced rotation (whiplash-type mechanism, awkward fall, or a mistimed loaded neck position) straining the facet joint capsule without frank subluxation.",
        "Avoid loaded end-range cervical extension/rotation (e.g. heavy overhead pressing with neck craned back, loaded neck bridges/wrestler's bridges) until pain-free through full active ROM.",
        ["Any numbness, tingling, or weakness radiating into the arm", "Bilateral symptoms or a sense of neck instability/giving way", "Headache with neck stiffness and fever (rule out other causes) — any of these warrant referral for imaging before continuing to train."],
        rts_extra=["Full, pain-free active cervical ROM in all planes", "No pain or apprehension with sport-specific end-range neck positions"]),
    _generic("Cervical Facet Injury - Stage 2 (Unilateral Subluxation)", ["Unilateral Facet Subluxation"], "Ligament", "Neck", "Cervical Facet Joint", 2,
        "More constant, often sharper neck pain with a visibly restricted or held rotated/tilted head position (torticollis-like), pain with any attempt to actively correct it; possible referred pain toward the shoulder blade.",
        "Higher-energy rotational/flexion trauma (heavier whiplash mechanism, contact-sport collision, hard fall) causing partial displacement of one facet joint surface on the other, with capsular and ligamentous disruption.",
        "No axial loading of the cervical spine and no end-range rotation/extension of any kind until imaging has ruled out instability and a clinician has cleared graded return; light, pain-free ROM inside the available range only once cleared.",
        ["Any numbness, tingling, or weakness in the arm/hand (possible nerve root involvement from the displaced joint)", "Increasing neck pain or new deformity", "Any change in gait, hand coordination, or bladder/bowel function — this is an emergency presentation."],
        rts_extra=["Imaging-confirmed joint congruency/stability", "Clinician/PT clearance before any loaded or end-range cervical work", "Full strength and pain-free ROM symmetric to the uninjured side before contact/collision exposure"],
        contraindicated=["Any axial loading of the neck (loaded carries, overhead work, neck bridges)", "Any forced or resisted rotation/extension", "Contact or collision activity of any kind until cleared"]),
    _generic("Cervical Facet Injury - Stage 3 (Bilateral Dislocation)", ["Bilateral Facet Dislocation"], "Ligament", "Neck", "Cervical Facet Joint (bilateral)", 3,
        "Severe, often disabling neck pain immediately following a high-energy trauma, frequently with neurological symptoms (numbness, weakness, or paralysis) given the high association with spinal cord injury at this stage.",
        "High-energy axial-loading or hyperflexion trauma (e.g. head-first impact, heavy diving/collision mechanism) causing bilateral facet joints to dislocate — this is a spine-stability emergency, not a training injury.",
        "No cervical spine loading or movement of any kind outside emergency stabilization and medical management; this is not a training-programmable condition until formal medical clearance is obtained.",
        ["This entire presentation is a clinical red flag: bilateral facet dislocation carries a high risk of spinal cord injury and requires emergency immobilization and evaluation — do not move the neck, do not attempt any exercise, seek emergency care immediately."],
        rts_extra=["Formal spine surgery/rehabilitation clearance confirming stability", "Neurosurgical or spine-specialist sign-off before any return to loaded training, let alone contact sport"],
        contraindicated=["Any cervical spine loading, positioning, or movement outside medically supervised rehabilitation"],
        # v5.30 fix: the entry's own text already says "do not attempt any
        # exercise" and "not a training-programmable condition" - systemic
        # was never set, so the app only blocked Neck-tagged exercises and
        # would still hand this person a leg or lower-back session.
        systemic=True),
    _generic("Thoracic Strain", [], "Spine", "Lower Back", "Thoracic Spine", 1,
        "Localized mid-back pain, often related to a specific loaded rotational or flexion movement.",
        "Muscular overload or sustained poor posture through the thoracic spine.",
        "Avoid loaded thoracic rotation/flexion until pain settles.",
        ["Chest pain, breathing difficulty, or radicular symptoms — refer for evaluation to rule out other causes."]),
    _generic("Thoracic Facet Dysfunction", [], "Spine", "Lower Back", "Thoracic Spine (facet joints)", 1,
        "Localized mid-back pain, often with a specific movement direction that reproduces it, and restricted segmental motion.",
        "Repetitive or sustained loading/positioning stressing the facet joints.",
        "Avoid the specific loaded movement direction that reproduces symptoms until it settles.",
        ["Radicular or band-like chest pain — refer for evaluation."]),
    _generic("Lumbar Strain (Acute)", ["Low Back Strain"], "Spine", "Lower Back", "Lumbar Spine", 1,
        "Localized low back pain and stiffness, often following a lifting or twisting mechanism.",
        "Muscular/ligamentous overload from lifting, twisting, or sustained poor posture.",
        "Avoid loaded spinal flexion/rotation until pain settles; maintain gentle movement rather than complete rest.",
        ["Radiating leg pain, numbness, or saddle anesthesia/bowel-bladder changes (possible cauda equina) — emergency evaluation."]),
    _generic("Lumbar Disc Herniation", [], "Spine", "Lower Back", "Lumbar Spine", 2,
        "Low back pain often radiating down the leg (sciatica) following a dermatomal pattern; worse with sitting/flexion.",
        "Disc material displacement from repetitive flexion/loading or a sudden loaded flexion-rotation mechanism.",
        "Avoid loaded lumbar flexion and prolonged sitting; favor extension-biased positions if they reduce symptoms (McKenzie-style, individualized).",
        ["Saddle anesthesia, bowel/bladder changes, or progressive bilateral leg weakness (cauda equina syndrome) — EMERGENCY, immediate medical care."]),
    _generic("Lumbar Disc Bulge", [], "Spine", "Lower Back", "Lumbar Spine", 1,
        "Low back pain, sometimes with mild referred leg symptoms, without frank nerve root compression.",
        "Disc degeneration/loading without full herniation.",
        "Avoid loaded end-range flexion under high load; otherwise generally well tolerated with graded loading.",
        ["Progressive radicular symptoms — refer for evaluation."]),
    _generic("Sciatica", [], "Nerve", "Lower Back", "Sciatic Nerve / Lumbosacral", 2,
        "Pain radiating from the low back/buttock down the posterior leg, sometimes with numbness/tingling, following the sciatic distribution.",
        "Nerve root or sciatic nerve irritation/compression (disc herniation, piriformis, spinal stenosis).",
        "Avoid positions that reproduce or worsen leg symptoms; nerve-gliding and graded loading as tolerated.",
        ["Progressive weakness, foot drop, or saddle anesthesia/bowel-bladder changes — urgent/emergency evaluation."]),
    _generic("Lumbar Facet Syndrome", [], "Spine", "Lower Back", "Lumbar Spine (facet joints)", 1,
        "Localized low back pain, often worse with extension/rotation, easing with flexion.",
        "Repetitive extension/rotation loading stressing the facet joints.",
        "Avoid loaded spinal extension/rotation until symptoms settle; flexion-biased core work often tolerated.",
        ["Radicular symptoms into the leg — refer for evaluation."]),
    _generic("Spondylolysis (Stable)", [], "Bone", "Lower Back", "Lumbar Spine (Pars)", 1,
        "Focal low back pain with extension loading; may be asymptomatic and found incidentally.",
        "Repetitive lumbar extension/rotation loading, often in adolescent extension-sport athletes.",
        "Avoid lumbar extension/rotation loading until cleared; maintain neutral-spine core training.",
        ["Progressive slip (spondylolisthesis) or neurological symptoms — refer for evaluation."]),
    _generic("Spondylolisthesis (Low-Grade, Stable)", [], "Spine", "Lower Back", "Lumbar Spine", 2,
        "Low back pain, sometimes with hamstring tightness or mild radicular symptoms, worse with extension.",
        "Anterior slippage of one vertebra on another, often from a pars defect or degenerative facet changes.",
        "Avoid loaded lumbar extension and high-shear loading (heavy loaded hyperextension, deep loaded lunges) until stable and cleared.",
        ["Progressive slip, neurological symptoms, or bowel/bladder changes — urgent evaluation."]),
    _generic("Lumbar Spinal Stenosis", [], "Spine", "Lower Back", "Lumbar Spine (canal)", 1,
        "Low back and leg pain/heaviness that worsens with walking/standing (extension) and eases with sitting/flexion.",
        "Degenerative narrowing of the spinal canal or neural foramina.",
        "Favor flexion-biased positions/exercise; avoid prolonged loaded extension/standing.",
        ["Progressive bilateral leg weakness or bowel/bladder changes (possible cauda equina) — emergency evaluation."]),
    # v5.30 fix: this entry is severity 1 in the original data despite (a)
    # its own name ("Severe Spinal Stenosis"), (b) its own mechanism text
    # explicitly saying "advanced degenerative change" - directly
    # contradicting this file's own severity-1 tier definition ("early
    # degeneration, stable injuries"), and (c) describing bilateral leg
    # involvement and a mechanical block/lock at end-range that the base
    # "Lumbar Spinal Stenosis" entry (also severity 1, correctly) doesn't
    # have. Both entries being severity 1 meant the taxonomy had no way to
    # tell a routine stenosis presentation apart from an advanced one with
    # bony locking - bumped to 2 (Moderate) to match "partial ...
    # displaced" tier language and its own "advanced"/"locking" framing.
    _generic("Severe Spinal Stenosis / Osteophyte Locking", ["Advanced Lumbar Stenosis", "Mechanical Lumbar Locking"], "Bone/Joint (Degenerative)", "Lower Back", "Lumbar Spine (canal, with bony osteophyte formation)", 2,
        "Low back and bilateral leg pain, cramping, or heaviness (neurogenic claudication) that reliably worsens with standing/walking extension and eases within minutes of sitting or bending forward; some report an actual catching or mechanical 'locking' sensation with extension as bony osteophytes narrow the canal further at end-range.",
        "Advanced degenerative change — osteophyte (bone spur) formation, disc bulging, and ligamentum flavum thickening — progressively narrowing the spinal canal, with extension postures mechanically worsening the narrowing to the point of a felt block or lock.",
        "Avoid sustained or loaded lumbar extension (heavy overhead work with an arched back, loaded back extensions, prolonged standing under load); flexion-biased positions (seated work, supported core work) are typically far more comfortable and generally well tolerated.",
        ["Progressive bilateral leg weakness, saddle-area numbness, or new bowel/bladder changes (possible cauda equina compression) — this needs emergency evaluation, not routine follow-up."],
        rts_extra=["Symptom-guided pacing rather than a fixed return-to-sport timeline, since this is a degenerative rather than a fully resolving condition", "Clinician input on safe long-term loading limits"]),
    _generic("Lumbar Fracture - Stable (One Column)", ["Stable Vertebral Compression Fracture"], "Bone", "Lower Back", "Lumbar Spine (single spinal column)", 2,
        "Localized, often severe low back pain following a traumatic mechanism (or, in someone with low bone density, a minimal-trauma event like a fall from standing); pain is worse with movement and loading, with focal tenderness over the involved level.",
        "Axial loading or flexion trauma — or an osteoporotic minimal-trauma injury — affecting only one of the spine's three structural columns (using the standard anterior/middle/posterior column model), leaving the segment mechanically stable.",
        "No axial loading or loaded spinal flexion/extension until imaging and clinician follow-up confirm healing; protected, often brace-supported mobility as directed medically in the interim.",
        ["Any new numbness, tingling, weakness, or bowel/bladder change (possible progression to neurological involvement) — refer for urgent evaluation; also screen for underlying low bone density given the mechanism."],
        rts_extra=["Radiographic confirmation of healing", "Clinician clearance", "A graded return to spinal loading rather than resuming prior training loads immediately"]),
    _generic("Lumbar Fracture - Unstable (Two/Three Column)", ["Unstable Vertebral Fracture"], "Bone", "Lower Back", "Lumbar Spine (two or three spinal columns)", 3,
        "Severe back pain with possible visible deformity, and — because two or three structural columns are disrupted — a meaningfully higher chance of associated neurological symptoms (numbness, weakness) than a single-column fracture.",
        "High-energy trauma (fall from height, high-speed impact, heavy axial loading failure) disrupting two or three of the spine's structural columns, producing a mechanically unstable segment.",
        "No spinal loading or movement outside emergency stabilization; this pattern frequently requires surgical fixation given the instability.",
        ["This pattern is itself a spine-stability emergency — any neurological symptom (numbness, weakness, bowel/bladder change) needs immediate evaluation, and the fracture itself needs prompt specialist management before any movement outside medical care."],
        rts_extra=["A full post-surgical (or specialist-directed conservative) rehabilitation protocol", "Spine-specialist clearance confirming stability before any return to loaded training"],
        contraindicated=["Any spinal loading or movement outside medically supervised care until stabilized"],
        # v5.30 fix: an unstable spine fracture isn't a "no lower-back
        # exercises" restriction - any exertion or Valsalva (even a seated
        # shoulder press) transmits load through an unstable spinal
        # segment, and the text above already treats this as an emergency,
        # not a joint-scoped training limitation.
        systemic=True),
    _generic("Massive Central Disc Herniation", ["Massive Central Lumbar Disc Herniation"], "Spine", "Lower Back", "Lumbar Spine (Disc, central canal)", 3,
        "Severe low back pain, often with bilateral leg symptoms (numbness, weakness, or radicular pain down both legs) rather than the one-sided pattern of a typical disc herniation — this bilateral, central pattern is what makes it high-risk for cauda equina involvement.",
        "A large disc fragment herniating centrally into the spinal canal, compressing multiple nerve roots (or the cauda equina itself), usually from a severe flexion-loading event or an acute-on-chronic degenerative process.",
        "No lumbar loading, particularly flexion or axial loading, until emergency evaluation has ruled out cauda equina syndrome — this is not a condition to try to train around.",
        ["Saddle-area numbness, new bowel or bladder dysfunction (retention or incontinence), or progressive bilateral leg weakness are cauda equina red flags and constitute a surgical emergency — seek immediate emergency care, do not wait for a routine appointment."],
        rts_extra=["Surgical or spine-specialist clearance", "Resolution of any neurological deficit (or a clear specialist-defined plateau) before considering a graded return to loaded training"],
        contraindicated=["Any lumbar flexion or axial loading until cauda equina has been ruled out and a clinician has cleared movement"],
        # v5.30 fix: possible cauda equina syndrome is a same-day surgical
        # emergency, not a "reduce lumbar loading" situation - the entry's
        # own text says as much ("not a condition to try to train around").
        systemic=True),
    _generic("Unstable Spondylolisthesis / Facet Dislocation", ["High-Grade Spondylolisthesis", "Traumatic Facet Dislocation"], "Spine", "Lower Back", "Lumbar Spine (vertebral segment/facet joints)", 3,
        "Significant back pain, often with a palpable step-off or visible postural change, frequently accompanied by radicular or bilateral leg symptoms if nerve roots are compromised by the instability.",
        "Either a high-grade (advanced, mechanically unstable) progression of vertebral slippage, or an acute traumatic facet joint dislocation — both leave the spinal segment unable to control normal load transfer.",
        "No loaded flexion, extension, or rotation of the lumbar spine; this level of instability typically requires surgical stabilization (fusion) rather than conservative management.",
        ["Any new or worsening neurological symptom, or bowel/bladder change, needs immediate evaluation — instability at this grade carries a real risk of progressive neurological injury without stabilization."],
        rts_extra=["A full post-surgical fusion/stabilization rehabilitation protocol", "Spine-specialist clearance before any return to loaded spinal training"],
        contraindicated=["Any loaded spinal flexion, extension, or rotation until surgically stabilized and cleared"]),
    _generic("Burst Fracture (Spine)", ["Vertebral Burst Fracture"], "Bone", "Lower Back", "Lumbar/Thoracolumbar Spine (vertebral body)", 3,
        "Severe, focal axial back pain immediately following high-energy trauma; neurological symptoms (numbness, weakness, or worse) may be present if bone fragments have retropulsed into the spinal canal.",
        "High-energy axial compression (a fall from height, high-speed impact, or a heavy axial loading failure) causing the vertebral body to fail outward in multiple directions ('burst'), with fragments potentially pushed back into the canal.",
        "No spinal loading of any kind — management depends on canal compromise and neurological status and is decided by a spine specialist, often surgically.",
        ["Any numbness, weakness, or bowel/bladder change after this mechanism is an emergency — assess for canal compromise and neurological injury immediately; do not attempt to move the person's spine unnecessarily before evaluation."],
        rts_extra=["A full post-surgical (or specialist-directed) rehabilitation protocol", "Spine-specialist clearance before any return to loaded training"],
        contraindicated=["Any spinal loading until specialist evaluation and clearance"],
        # v5.30 fix: a burst fracture with possible canal compromise is a
        # whole-body stop, not a lower-back-only restriction - text above
        # already says "management ... decided by a spine specialist."
        systemic=True),
    _generic("Fracture-Dislocation with Spinal Cord Injury", ["Traumatic Spine Fracture-Dislocation with Cord Injury"], "Spine", "Lower Back", "Spine (vertebral column and spinal cord)", 3,
        "Severe pain at the level of injury combined with neurological deficit below that level (numbness, weakness, or paralysis), reflecting direct injury to the spinal cord alongside the structural fracture-dislocation.",
        "High-energy trauma producing simultaneous vertebral fracture, dislocation, and direct compression or injury of the spinal cord itself.",
        "None — this is an emergency medical condition, not a training or rehabilitation-programming scenario in any active phase.",
        ["This entire presentation is itself the red flag: any suspected spinal cord injury requires immediate emergency medical care, full spinal precautions, and should never be assessed or managed through an exercise-prescription context."],
        # v5.30 fix: the entry's own text already says this is "not a
        # training ... scenario in any active phase" - systemic was never
        # set, so previously only Lower-Back-tagged exercises were blocked.
        systemic=True),
    _generic("Spinal Cord Injury - ASIA Grade D/E (Mild Incomplete/Normal)", ["Incomplete Spinal Cord Injury (Mild)"], "Nerve", "Lower Back", "Spinal Cord", 2,
        "Variable, often mild sensory or motor changes below the level of a prior spinal cord injury; ASIA D indicates most key muscles below the injury level retain functional (grade 3+) strength, and ASIA E indicates normal function has returned.",
        "A prior traumatic or medical spinal cord injury with substantial preservation or recovery of motor and sensory function, now in a stable or improving neurological state.",
        "No loaded spinal training until a spine/rehabilitation specialist defines safe limits based on the individual's specific residual deficits — neurological injuries at this level vary enormously person to person and cannot be generically programmed around.",
        ["Any new or worsening weakness, numbness, or change in bowel/bladder/autonomic function — this needs urgent re-evaluation by the person's spinal cord injury care team, not adjustment of a training plan."],
        rts_extra=["Confirmed neurological stability or continued improvement on specialist exam", "Individualized clearance and loading limits from the treating spinal cord injury/rehabilitation team", "Sport-specific screening appropriate to the residual deficit before contact or high-risk activity"]),
    _generic("Spinal Cord Injury - ASIA Grade A/B/C (Severe/Complete)", ["Complete or Severe Incomplete Spinal Cord Injury"], "Nerve", "Lower Back", "Spinal Cord", 3,
        "Substantial or complete loss of motor and/or sensory function below the level of injury; presentation is dominated by neurological deficit rather than pain, and the specific pattern depends heavily on the injury level and completeness.",
        "A severe or complete traumatic spinal cord injury, producing major, often permanent loss of function below the injured level.",
        "Standard resistance-training programming does not straightforwardly apply to this population; any exercise program must be built individually with a spinal cord injury rehabilitation specialist (adaptive/para-sport and SCI-specific rehab expertise), not derived from general exercise-prescription logic.",
        ["This is a severe, specialist-managed condition on its own — this app is not a substitute for a spinal cord injury rehabilitation program, and any training decisions should be deferred entirely to the person's specialized care team."],
        rts_extra=["Ongoing, individualized guidance from a spinal cord injury rehabilitation/adaptive sport specialist for any exercise participation"],
        contraindicated=["Generic (non-individualized) resistance training programming of any kind"]),
    _generic("Sacroiliac (SI) Joint Dysfunction", [], "Joint", "Hip", "Sacroiliac Joint", 1,
        "Localized low back/buttock pain, often unilateral, provoked by single-leg loading or transitional movements.",
        "Altered SI joint mechanics from asymmetric loading, pregnancy-related laxity, or direct trauma.",
        "Avoid single-leg loaded positions and asymmetric loading that reproduce pain until it settles; pelvic stability work.",
        ["Progressive neurological symptoms — refer for evaluation (SI dysfunction itself is not a red-flag condition)."]),

    # --- Nerve Disorders ---
    _generic("Carpal Tunnel Syndrome", [], "Nerve", "Wrist", "Wrist (median nerve)", 1,
        "Numbness/tingling in the thumb-index-middle fingers, often worse at night, with possible grip weakness.",
        "Repetitive wrist flexion/extension or sustained loaded wrist positions compressing the median nerve.",
        "Avoid sustained/loaded wrist flexion or extension (e.g. front rack, deep push-up wrist position) until symptoms settle.",
        ["Progressive thenar (thumb-base) muscle wasting or constant numbness — refer for evaluation."]),
    _generic("Cubital Tunnel Syndrome", [], "Nerve", "Elbow", "Elbow (ulnar nerve)", 1,
        "Numbness/tingling in the ring and little fingers, often worse with prolonged elbow flexion.",
        "Repetitive/sustained elbow flexion or direct pressure over the medial elbow compressing the ulnar nerve.",
        "Avoid sustained/loaded end-range elbow flexion and direct pressure on the medial elbow until symptoms settle.",
        ["Progressive hand intrinsic muscle weakness/wasting — refer for evaluation."]),
    _generic("Thoracic Outlet Syndrome", [], "Nerve", "Shoulder", "Neck/Shoulder (brachial plexus/subclavian vessels)", 1,
        "Numbness, tingling, heaviness, or pain in the arm/hand, often provoked by overhead positions.",
        "Compression of the neurovascular bundle between the neck and shoulder (scalenes, first rib, pec minor).",
        "Avoid sustained overhead positions and heavy shrug-dominant loading until symptoms settle; address postural/scalene tightness.",
        ["Arm swelling/color change (possible vascular TOS) or progressive weakness — refer for evaluation."]),
    _generic("Common Peroneal Neuropathy", [], "Nerve", "Knee", "Lateral Knee/Fibular Head (peroneal nerve)", 1,
        "Numbness on the top of the foot/lateral shin, possible foot drop, often from pressure at the fibular head.",
        "Direct compression (e.g. prolonged kneeling/crossed legs, tight bracing) or traction injury near the fibular head.",
        "Avoid sustained direct pressure over the fibular head and positions that reproduce symptoms.",
        ["Foot drop or progressive weakness — refer for evaluation."]),
    _generic("Tarsal Tunnel Syndrome", [], "Nerve", "Ankle", "Medial Ankle (tibial nerve)", 1,
        "Numbness/tingling/burning on the sole of the foot, often worse with standing/walking.",
        "Compression of the tibial nerve as it passes behind the medial malleolus.",
        "Avoid sustained loaded ankle eversion/pronation and prolonged standing until symptoms settle.",
        ["Progressive intrinsic foot muscle weakness — refer for evaluation."]),
    _generic("Peripheral Nerve Entrapment (General)", [], "Nerve", "Wrist", "Variable", 1,
        "Numbness, tingling, or burning in a specific nerve distribution, sometimes with associated weakness.",
        "Mechanical compression or repetitive irritation of a peripheral nerve at a vulnerable anatomical site.",
        "Avoid the specific sustained/repetitive position that reproduces symptoms until the entrapment is addressed.",
        ["Progressive motor weakness or muscle wasting in the nerve's distribution — refer for evaluation."]),

    # --- Fascia & Connective Tissue ---
    _generic("Plantar Fasciitis", ["Plantar Fasciopathy"], "Fascia", "Ankle", "Plantar Foot (heel)", 1,
        "Sharp heel pain with the first steps in the morning or after rest, easing somewhat with activity then worsening later in the day.",
        "Repetitive loading of the plantar fascia, often from a training-load spike, footwear change, or calf tightness.",
        "Reduce high-impact loading volume; avoid prolonged barefoot walking on hard surfaces until symptoms settle.",
        ["Sudden, sharp tearing pain with a pop (possible plantar fascia rupture) — refer for evaluation."]),
    _generic("IT Band Syndrome", ["Iliotibial Band Syndrome"], "Fascia", "Knee", "Lateral Knee/Thigh", 1,
        "Sharp or aching lateral knee pain, typically appearing at a consistent point during running and easing with rest.",
        "Repetitive knee flexion/extension (running/cycling) with altered hip control causing friction/compression near the lateral femoral condyle.",
        "Reduce running volume/downhill running until symptoms settle; address hip abductor strength and running mechanics.",
        ["Symptoms that fail to respond to load management over several weeks — refer for evaluation."]),
    _generic("Fascial Adhesions", [], "Fascia", "Lower Back", "Variable", 1,
        "Localized stiffness/restriction and dull ache with movement in the affected region.",
        "Post-injury or post-surgical scar tissue formation, or chronic under-mobilized tissue.",
        "Gentle mobility/soft-tissue work generally tolerated and often therapeutic; avoid aggressive loading that reproduces sharp pain.",
        ["Rapidly worsening pain or new neurological symptoms — refer for evaluation."]),

    # --- Overuse Conditions (named/aliased) ---
    _generic("Jumper's Knee (Patellar Tendinopathy)", ["Patellar Tendinitis"], "Tendon", "Knee", "Anterior Knee (patellar tendon)", 1,
        "Localized pain at the inferior pole of the patella, worse with jumping/landing and after sitting.",
        "Repetitive jump-landing loading exceeding the tendon's adaptive capacity.",
        "Reduce jumping/landing volume; isometric-to-heavy-slow-resistance loading is the core rehab strategy.",
        ["Persistent pain despite load management over months — refer for evaluation."]),
    _generic("Thrower's Shoulder (Internal Impingement)", [], "Joint", "Shoulder", "Posterior Shoulder", 1,
        "Posterior shoulder pain during the late-cocking/acceleration phase of throwing.",
        "Repetitive overhead throwing load causing posterior capsule tightness and internal impingement.",
        "Reduce high-velocity overhead/throwing volume until symptoms settle; address posterior capsule mobility and scapular control.",
        ["Sudden loss of velocity/control with pain (possible labral or cuff injury) — refer for evaluation."]),
    _generic("Swimmer's Shoulder", [], "Joint", "Shoulder", "Shoulder", 1,
        "Anterior/lateral shoulder pain with repetitive overhead stroke mechanics, especially at higher training volumes.",
        "High-volume repetitive overhead loading with relative rotator cuff/scapular stabilizer fatigue.",
        "Reduce overhead training volume until symptoms settle; build rotator cuff and scapular stabilizer strength.",
        ["Sudden weakness or night pain unrelated to activity — refer for evaluation."]),
    _generic("Osgood-Schlatter Disease", [], "Bone", "Knee", "Tibial Tuberosity (pediatric)", 1,
        "Pain and a bony prominence at the tibial tuberosity in a growing adolescent, worse with jumping/kneeling.",
        "Repetitive traction from the patellar tendon on the tibial tuberosity growth plate during a growth spurt.",
        "Reduce jumping/loaded knee-extension volume during symptomatic periods; generally self-limiting with skeletal maturity.",
        ["Severe pain with minimal activity, or signs suggesting avulsion fracture — refer for evaluation."]),
    _generic("Sever's Disease (Calcaneal Apophysitis)", [], "Bone", "Ankle", "Calcaneus (pediatric, heel)", 1,
        "Heel pain in a growing child/adolescent, worse with running/jumping, often bilateral.",
        "Repetitive traction/compression at the calcaneal growth plate during a growth spurt.",
        "Reduce running/jumping volume during symptomatic periods; generally self-limiting with skeletal maturity.",
        ["Pain that persists significantly beyond the expected growth window, or is unilateral with atypical features — refer for evaluation."]),
    _generic("Repetitive Strain Injury (RSI) - Forearm/Wrist", [], "Muscle", "Wrist", "Forearm/Wrist", 1,
        "Gradual-onset aching, tightness, or pain with repetitive hand/wrist tasks, easing with rest.",
        "Repetitive, high-frequency low-load activity (typing, manual work, repetitive gripping) without adequate recovery.",
        "Reduce repetitive load/frequency; address ergonomics and build progressive tolerance.",
        ["Numbness/tingling suggesting nerve involvement, or progressive weakness — refer for evaluation."]),

    # --- Degenerative Conditions ---
    _generic("Osteoarthritis - Knee", [], "Cartilage", "Knee", "Knee", 1,
        "Aching joint pain and stiffness, worse with activity and after rest (gel phenomenon), possibly with crepitus.",
        "Progressive cartilage degeneration from cumulative joint loading, prior injury, or biomechanical factors.",
        "Favor lower-impact loading modalities; avoid high-impact/deep-flexion loading during symptomatic flares.",
        ["Rapidly progressive pain, significant effusion, or joint deformity — refer for evaluation."]),
    _generic("Osteoarthritis - Hip", [], "Cartilage", "Hip", "Hip", 1,
        "Groin/lateral hip pain and stiffness, worse with activity and prolonged sitting, reduced rotation ROM.",
        "Progressive cartilage degeneration from cumulative joint loading or prior structural factors (e.g. FAI).",
        "Favor lower-impact loading; avoid deep, loaded end-range hip flexion/rotation during symptomatic flares.",
        ["Rapidly progressive pain or significant loss of function — refer for evaluation."]),
    _generic("Osteoarthritis - Shoulder", [], "Cartilage", "Shoulder", "Shoulder", 1,
        "Deep shoulder ache and stiffness, worse with overhead activity, possible crepitus.",
        "Progressive glenohumeral cartilage degeneration from cumulative loading or prior injury.",
        "Reduce high-load overhead work during symptomatic flares; maintain ROM within comfort.",
        ["Rapidly progressive pain or significant loss of function — refer for evaluation."]),
    _generic("Osteoarthritis - Ankle", [], "Cartilage", "Ankle", "Ankle", 1,
        "Aching ankle pain and stiffness with weight-bearing, often following prior significant ankle trauma.",
        "Progressive cartilage degeneration, frequently post-traumatic after fracture/severe sprain.",
        "Favor lower-impact loading; avoid high-impact/pivoting activity during symptomatic flares.",
        ["Rapidly progressive pain or significant loss of function — refer for evaluation."]),
    _generic("Osteoarthritis - Wrist/Hand", [], "Cartilage", "Wrist", "Wrist/Hand", 1,
        "Aching joint pain and stiffness with gripping/loading, possible reduced grip strength.",
        "Progressive cartilage degeneration, sometimes post-traumatic (e.g. after SLAC wrist).",
        "Reduce high-load gripping/axial wrist loading during symptomatic flares.",
        ["Rapidly progressive pain or significant loss of function — refer for evaluation."]),
    _generic("Degenerative Disc Disease - Cervical", [], "Spine", "Neck", "Cervical Spine", 1,
        "Chronic neck stiffness/ache, sometimes with intermittent radicular symptoms, worse with prolonged static postures.",
        "Progressive disc dehydration/height loss over time, altering segmental spine mechanics.",
        "Avoid prolonged loaded end-range neck positions during symptomatic periods; maintain mobility and strength.",
        ["New or progressive radicular/myelopathic symptoms — refer for evaluation."]),
    _generic("Degenerative Disc Disease - Lumbar", [], "Spine", "Lower Back", "Lumbar Spine", 1,
        "Chronic low back stiffness/ache, worse with prolonged static postures, often better with movement.",
        "Progressive disc dehydration/height loss over time, altering segmental spine mechanics.",
        "Avoid prolonged loaded end-range flexion during symptomatic periods; maintain general mobility and progressive strength training.",
        ["New or progressive radicular symptoms or bowel/bladder changes — refer for evaluation."]),

    # --- Head & Thorax (v5.11 addition) ---
    # Combat sports (Boxing, Muay Thai, MMA, Wrestling, BJJ, Judo, Sanda) and
    # collision sports (Rugby) carry real head- and rib-injury exposure that
    # nothing in the taxonomy covered before this. None of these tissues map
    # cleanly onto the 8-tag joint_stress vocabulary; each is assigned the
    # closest functionally-relevant tag (see module docstring's `region`
    # note) — Neck for head/brain (head/neck loading exercises are the ones
    # that already carry a "Neck" joint_stress tag), Shoulder for the
    # ribcage (chest/trunk-loading press and rotational exercises are
    # tagged "Shoulder", not any spine tag), Hip for the groin/pubic region.
    _generic("Concussion - Grade 1 (No LOC, Symptoms <15min)", ["Mild TBI", "Mild Concussion"], "Nerve", "Neck", "Brain/Head", 1,
        "Brief confusion, headache, or dizziness immediately after head impact; no loss of consciousness; symptoms clear within 15 minutes.",
        "Direct blow to the head or a whiplash-type force transmitted to the brain (strike, takedown, fall).",
        "No contact training or sparring until fully asymptomatic at rest AND with exertion; light non-contact aerobic activity only once acutely asymptomatic.",
        ["Any worsening headache, repeated vomiting, increasing confusion, slurred speech, seizure, or one pupil larger than the other — emergency evaluation immediately.", "Any loss of consciousness, amnesia, or symptoms lasting beyond 15 minutes reclassifies this as Grade 2/3."],
        rts_extra=["Graded return-to-sport/contact protocol completed step-wise with no symptom recurrence at each stage", "Medical clearance before any return to sparring or live contact"],
        contraindicated=["Any sparring, live contact, or heavy impact/head-loading exercise (e.g. heavy overhead work, inversions) until cleared", "Return to training same day as the injury"],
        systemic=True),
    _generic("Concussion - Grade 2 (No LOC, Symptoms >15min)", ["Moderate Concussion"], "Nerve", "Neck", "Brain/Head", 2,
        "Confusion, headache, dizziness, or cognitive fogginess persisting beyond 15 minutes; no loss of consciousness.",
        "Direct blow to the head or a whiplash-type force transmitted to the brain (strike, takedown, fall).",
        "Complete physical and cognitive rest until asymptomatic, then a clinician-supervised graded return; no contact training or sparring during this period.",
        ["Any worsening headache, repeated vomiting, increasing confusion, slurred speech, seizure, or one pupil larger than the other — emergency evaluation immediately.", "Symptoms that fail to trend downward over days — refer for evaluation."],
        rts_extra=["Graded return-to-sport/contact protocol completed step-wise with no symptom recurrence at each stage", "Medical clearance required before any return to sparring or live contact"],
        contraindicated=["Any sparring, live contact, or heavy impact/head-loading exercise until cleared", "Cognitively demanding training or competition preparation while symptomatic"],
        systemic=True),
    _generic("Concussion - Grade 3 (Loss of Consciousness)", ["Severe Concussion", "TBI with LOC"], "Nerve", "Neck", "Brain/Head", 3,
        "Loss of consciousness (brief or extended) at the time of injury, with or without ongoing confusion, amnesia, or other symptoms afterward.",
        "Direct blow to the head or a whiplash-type force transmitted to the brain (strike, takedown, fall) severe enough to cause LOC.",
        "No training of any kind until medically cleared; this is an emergency-evaluation-first injury, not a train-around-it injury.",
        ["Loss of consciousness itself is the red flag — requires immediate medical evaluation.", "Any worsening headache, repeated vomiting, increasing confusion, slurred speech, seizure, weakness/numbness, or one pupil larger than the other — emergency evaluation immediately."],
        rts_extra=["Formal neurological/medical clearance required before any return to training", "Full graded return-to-sport/contact protocol with no symptom recurrence at each stage"],
        contraindicated=["Any training until formally medically cleared"],
        systemic=True),
    _generic("Rib Fracture - Simple (Single, Non-Displaced)", [], "Bone", "Shoulder", "Ribcage", 2,
        "Sharp, well-localized chest-wall pain over the fracture site, worse with deep breathing, coughing, twisting, or direct pressure.",
        "Direct blunt impact to the ribcage (strike, fall, heavy impact) or, less commonly, forceful coughing/repetitive stress.",
        "Avoid any loading, impact, or rotation through the trunk until pain-free; breathing exercises for pain-free lung expansion are still important.",
        ["Shortness of breath, chest tightness disproportionate to pain, or coughing up blood (possible pneumothorax/lung injury) — emergency evaluation immediately.", "Multiple rib involvement or a flail segment (paradoxical chest-wall movement) — emergency evaluation immediately."]),
    _generic("Rib Fracture - Displaced/Multiple (Flail Chest Risk)", [], "Bone", "Shoulder", "Ribcage", 3,
        "Severe, diffuse chest-wall pain, often with visible deformity or a paradoxical (inward-on-inhale) segment of chest-wall movement.",
        "High-force direct blunt trauma to the ribcage (heavy impact, crush mechanism, significant fall).",
        "No training until medically cleared; this is a medical-emergency-first injury.",
        ["Paradoxical chest-wall movement, significant shortness of breath, or coughing up blood — emergency evaluation immediately.", "Signs of underlying lung injury (pneumothorax/hemothorax) — emergency evaluation immediately."],
        # v5.30 fix: flail chest is a breathing/respiratory-mechanics
        # emergency, not a chest-wall-loading restriction - exertion of any
        # kind (a squat, a run, anything raising ventilatory demand) is
        # unsafe here, not just Shoulder-tagged pressing exercises. The
        # entry's own restriction text already says "no training until
        # medically cleared"; systemic was never set to match it.
        systemic=True),
    _generic("Intercostal Muscle Strain - Grade I Strain (Mild)", ["Rib Strain"], "Muscle", "Shoulder", "Ribcage (between ribs)", 1,
        "Sharp, localized pain between the ribs, worse with deep breathing, twisting, or reaching overhead; no significant bruising.",
        "Sudden trunk rotation/overreach (throwing/swinging motions, forceful twisting) or a direct strike to the chest wall.",
        "Reduce trunk-rotation and overhead-reach loading that reproduces pain; breathing normally (not breath-holding through pain) is still encouraged.",
        ["Symptoms disproportionate to a muscular mechanism, or breathing difficulty — refer for evaluation to rule out rib fracture."]),
    _generic("Intercostal Muscle Strain - Grade II Strain (Partial Tear)", ["Rib Strain"], "Muscle", "Shoulder", "Ribcage (between ribs)", 2,
        "Moderate, well-localized chest-wall pain with palpable tenderness, notable pain with deep breathing/coughing, and pain-limited trunk rotation.",
        "Forceful trunk rotation/overreach or a direct strike to the chest wall.",
        "Avoid loaded trunk rotation and overhead pressing/reaching until pain-free; light breathing/mobility work still encouraged.",
        ["Symptoms disproportionate to a muscular mechanism, or breathing difficulty — refer for evaluation to rule out rib fracture."]),
    _generic("Costochondritis", ["Chest Wall Pain Syndrome"], "Joint", "Shoulder", "Costochondral Junction (Ribcage/Sternum)", 1,
        "Sharp or aching pain at the costochondral junctions (where ribs meet the sternum), reproducible with direct palpation, worse with deep breathing or chest-loading movements.",
        "Repetitive chest-wall loading (heavy pressing volume) or a direct blow to the sternal/costochondral region.",
        "Reduce heavy pressing volume and direct chest-wall loading/impact until symptoms settle; deep breathing is still encouraged, not restricted.",
        ["Chest pain with cardiac risk features (radiating pain, shortness of breath, sweating, exertional onset) — treat as a medical emergency, not costochondritis, until ruled out."]),
    _generic("Sports Hernia (Athletic Pubalgia)", ["Core Muscle Injury", "Inguinal Disruption"], "Muscle", "Hip", "Groin/Lower Abdomen (pubic region)", 2,
        "Deep, poorly-localized groin/lower-abdominal pain that builds with training and eases with rest, worse with sprinting, cutting, or sit-up/twisting motions; typically no palpable hernia bulge.",
        "Chronic repetitive shearing stress across the pubic symphysis from asymmetric hip/abdominal loading (cutting, kicking, sprinting sports).",
        "Reduce sprinting, cutting, kicking, and resisted trunk-rotation/sit-up loading until symptoms settle; isolated hip and core strengthening within the pain-free range is still appropriate.",
        ["A true palpable bulge or signs of an inguinal/femoral hernia — refer for surgical evaluation.", "Pain that fails to improve with several weeks of load management — refer for evaluation."]),

    # --- Bare/vernacular umbrella terms (v5.11 addition) ---
    # exercises.json's injuries_to_avoid field has always allowed short,
    # plain-language tags a user might actually type ("Low Back Pain",
    # "Rotator Cuff") alongside the specific graded diagnoses above — that's
    # a deliberate, real difference in meaning (a caution flag vs. a
    # diagnosed grade), not a typo. Until now those short tags had no
    # taxonomy entry at all, so _resolve_injury_severity() (progression_engine.py)
    # silently couldn't find them and every exercise carrying one of these
    # tags fell back to the older flat literal-tag match instead of the
    # four-tier severity model everything else in this file gets. Adding
    # them here — as their own severity-1 (mild/non-specific) entries,
    # distinct from the graded conditions they're related to via alt_names —
    # fixes that gap without touching a single line of exercises.json.
    _generic("Low Back Pain", ["Non-Specific Low Back Pain", "LBP"], "Spine", "Lower Back", "Lumbar Spine", 1,
        "Non-specific aching or tightness in the lower back, without a confirmed structural diagnosis; may be positional or activity-related.",
        "Cumulative loading, postural factors, or a minor mechanical irritation without a specific identified structural injury.",
        "Reduce loaded spinal flexion/extension volume that reproduces symptoms; general movement and progressive loading (not rest) is the standard first-line approach.",
        ["Radiating leg pain, numbness, or weakness; bowel/bladder changes; or pain that is worse at rest/at night — refer for evaluation."]),
    _generic("Lower Back Strain", ["Low Back Muscle Strain"], "Muscle", "Lower Back", "Lumbar Spine (paraspinal musculature)", 1,
        "Localized muscular tightness/soreness or spasm across the lower back, often after a specific loading event, worse with movement into the strained direction.",
        "Sudden or cumulative overload of the lumbar paraspinal musculature (e.g. lifting with poor mechanics, an unaccustomed load).",
        "Reduce loaded spinal flexion/extension/rotation that reproduces symptoms while maintaining general activity; avoid prolonged bed rest.",
        ["Radiating leg pain, numbness, or weakness; bowel/bladder changes; or pain that is worse at rest/at night — refer for evaluation."]),
    _generic("Neck Pain", ["Non-Specific Neck Pain", "Cervicalgia"], "Spine", "Neck", "Cervical Spine", 1,
        "Non-specific ache, tightness, or stiffness in the neck, without a confirmed structural diagnosis; may be positional or postural.",
        "Cumulative postural loading, a minor mechanical irritation, or muscular tightness without a specific identified structural injury.",
        "Reduce sustained loaded end-range neck positions (e.g. heavy overhead bracing, prolonged neck-flexed positions) that reproduce symptoms.",
        ["Radiating arm pain, numbness, or weakness; or symptoms following significant trauma — refer for evaluation."]),
    _generic("Wrist Pain", ["Non-Specific Wrist Pain"], "Joint", "Wrist", "Wrist", 1,
        "Non-specific ache or discomfort in the wrist with loading or end-range positions, without a confirmed structural diagnosis.",
        "Cumulative loading (pressing, gripping, weight-bearing through the wrist) without a specific identified structural injury.",
        "Reduce axial loading and end-range wrist extension (e.g. front-rack, planks, heavy pressing) that reproduces symptoms; neutral-wrist tools/grips as needed.",
        ["Numbness/tingling into the hand, night pain, or a visible deformity — refer for evaluation."]),
    _generic("Rotator Cuff", ["Rotator Cuff Injury (General)"], "Musculoskeletal (see name for specific structure)", "Shoulder", "Shoulder", 1,
        "Shoulder pain and/or weakness with overhead or rotational loading, localized to the rotator cuff region, without a confirmed specific diagnosis (strain vs. tendinopathy vs. tear).",
        "Repetitive overhead/rotational loading or an acute strain of one or more rotator cuff muscles/tendons.",
        "Reduce loaded overhead and end-range rotational work until symptoms settle; build cuff and scapular stabilizer strength within the pain-free range.",
        ["Sudden significant weakness (possible acute tear), night pain, or symptoms following a traumatic event — refer for evaluation."]),
    _generic("Achilles", ["Achilles Tendon Issue (General)"], "Tendon", "Ankle", "Posterior Ankle/Heel", 1,
        "Ache, stiffness, or tenderness at the Achilles tendon, often worse at the start of activity (e.g. jumping, sprinting) and after rest, without a confirmed specific diagnosis (tendinopathy vs. tear).",
        "Repetitive jumping/sprinting/calf-loading volume exceeding the tendon's current tolerance.",
        "Reduce jumping/plyometric and sprinting volume that reproduces symptoms; isometric-to-progressive calf loading is the standard first-line approach.",
        ["A sudden pop with acute severe pain and inability to push off/rise onto the toes — possible rupture, refer for urgent evaluation."]),
    _generic("Patellar Tendon", ["Patellar Tendon Issue (General)"], "Tendon", "Knee", "Anterior Knee", 1,
        "Localized pain at the inferior pole of the patella/patellar tendon, worse with jumping, landing, or squatting, without a confirmed specific diagnosis (tendinopathy vs. tear).",
        "Repetitive jump-landing or heavy knee-extension loading exceeding the tendon's current tolerance.",
        "Reduce jumping/landing and deep-flexion loaded knee volume that reproduces symptoms; isometric-to-heavy-slow-resistance loading is the standard first-line approach.",
        ["A sudden pop with acute severe pain and inability to actively extend the knee/bear weight — possible rupture, refer for urgent evaluation."]),
    _generic("Hamstring Strain", ["Hamstring Strain (Ungraded)"], "Muscle", "Knee", "Posterior Thigh", 1,
        "Localized posterior-thigh pain with sprinting, kicking, or hip-hinge loading, without a confirmed grade/severity.",
        "Sudden high-speed eccentric overload of the hamstring (sprinting, kicking) or cumulative overuse.",
        "Reduce sprinting, kicking, and loaded hip-hinge volume that reproduces symptoms until re-evaluated for grade.",
        ["A sudden 'pop', significant swelling/bruising, or marked strength loss (possible higher-grade tear) — refer for evaluation to confirm grade before resuming sprinting/plyometric loading."]),
]


# ============================================================================
# ASSEMBLE THE FULL TAXONOMY
# ============================================================================
INJURY_TAXONOMY: Dict[str, dict] = {}

for _name, _info in _LEGACY.items():
    INJURY_TAXONOMY[_name] = _enrich_legacy(_name, _info["joint"], _info["severity"])

for _muscle, _joint, _region in MUSCLE_GROUPS:
    for _grade in (1, 2, 3):
        _entry = _muscle_strain(_muscle, _joint, _region, _grade)
        INJURY_TAXONOMY[_entry["name"]] = _entry

for _entry in _MUSCLE_CONDITIONS:
    INJURY_TAXONOMY[_entry["name"]] = _entry

for _ligament, _joint, _region in LIGAMENTS:
    for _grade in (1, 2, 3):
        _entry = _ligament_sprain(_ligament, _joint, _region, _grade)
        INJURY_TAXONOMY[_entry["name"]] = _entry

for _tendon, _joint, _region in TENDONS:
    for _kind in ("tendinopathy", "partial_tear", "rupture"):
        _entry = _tendon_injury(_tendon, _joint, _region, _kind)
        INJURY_TAXONOMY[_entry["name"]] = _entry

for _entry in NAMED_CONDITIONS:
    INJURY_TAXONOMY[_entry["name"]] = _entry


# Sanity: every entry must carry the load-bearing keys the engine reads, and
# every entry name must be unique (dict construction above already guarantees
# uniqueness by key, but this also catches an empty/malformed entry early).
for _n, _e in INJURY_TAXONOMY.items():
    assert "joint" in _e and "severity" in _e, f"Malformed injury entry: {_n}"
    assert _e["severity"] in (1, 2, 3), f"Invalid severity for: {_n}"

del _name, _info, _muscle, _joint, _region, _grade, _entry, _ligament, _tendon, _kind, _n, _e


# ============================================================================
# GROUPED VIEW — Section (joint) -> Subsection (condition) -> Grades
# ============================================================================
# Powers the frontend's injury browser: sections like "Knee" / "Shoulder" /
# "Wrist", each broken into named conditions ("ACL Tear", "Meniscus Tear",
# ...), each of those broken into its severity/grade variants where the
# condition has more than one (most muscle/ligament/tendon entries are
# generated in 2-3 grades; many named conditions only have one severity).
#
# The grouping key is everything in `name` before " - " (every generated
# entry follows "{Condition} - {Grade label}"; single-severity named
# conditions have no " - " at all, so they're their own one-grade group).
# This is derived at import time from INJURY_TAXONOMY itself, so it can never
# drift out of sync with the actual data - same principle as
# ProgressionEngine.load_database deriving all_injuries from the live graph.
SEVERITY_LABEL = {1: "Mild", 2: "Moderate", 3: "Severe"}


def _condition_group(name: str) -> str:
    return name.split(" - ", 1)[0].strip()


# ============================================================================
# COMBAT SPORTS & RUGBY S&C MANUAL, PART 7.7 — NAMED SUBSTITUTION TABLE
# ============================================================================
# `find_alternatives` above already does general-purpose, live substitution
# by movement-pattern + joint-clearance for ANY exercise/injury combination
# it's asked about - that's the engine's actual safety mechanism and this
# table doesn't change it. What was missing (flagged in the README as not
# yet ported) is the manual's own *named* version of that same idea: a
# coach-readable "if this common issue shows up, here's what a coach would
# reach for" reference, matched to a joint the same way the rest of this
# file already keys everything (Lower Back, Shoulder, Knee, Wrist, Elbow),
# plus the manual's own default-culprit exercises and its explicit
# clinical caveat. `part7_recommended_swap` cross-checks each named
# substitute against exercises.json by name so the ids returned are real
# and clickable, not just text.
PART7_SUBSTITUTION_TABLE: List[Dict] = [
    {
        "joint": "Lower Back",
        "issue": "Low back irritation",
        "typical_culprit": ["Barbell Back Squat", "Barbell Conventional Deadlift"],
        "safer_substitutes": ["Belt Squat", "Trap Bar Deadlift", "Single-Leg Hip Thrust", "GHD Hip Extension"],
        "note": "Trap bar's higher handles reduce forward lean vs. a conventional pull; belt squat loads the hips instead of the spine.",
    },
    {
        "joint": "Shoulder",
        "issue": "Shoulder pain / impingement",
        "typical_culprit": ["Flat Bench Press", "Barbell Overhead Press"],
        "safer_substitutes": ["Landmine Press", "Floor Press", "Neutral-Grip Dumbbell Press"],
        "note": "The landmine's arc path and the floor press's shortened range both reduce end-range shoulder stress vs. a straight barbell bar path.",
    },
    {
        "joint": "Knee",
        "issue": "Knee pain",
        "typical_culprit": ["Barbell Back Squat", "Walking Lunge"],
        "safer_substitutes": ["Belt Squat", "Box Squat (Barbell)", "Backward Sled Drag", "Leg Press"],
        "note": "A higher box and belt-loaded squat both reduce knee shear vs. a deep barbell back squat; reverse sled drag trains the quads with minimal joint compression.",
    },
    {
        "joint": "Wrist",
        "issue": "Wrist pain",
        "typical_culprit": ["Barbell Front Squat", "Flat Bench Press"],
        "safer_substitutes": ["Dumbbell Goblet Squat", "Kettlebell Floor Press", "Landmine Press"],
        "note": "Kettlebell/dumbbell grips let the wrist stay neutral instead of loaded in extension the way a barbell front rack or bench grip does; straps help on pulling movements.",
    },
    {
        "joint": "Elbow",
        "issue": "Elbow pain (grappler's elbow)",
        "typical_culprit": ["EZ Bar Curl", "Weighted Pull-Up"],
        "safer_substitutes": ["Neutral Grip Pull-Up", "Fat-Grip Row"],
        "note": "Neutral-grip pulling and a fatter bar/handle both reduce direct forearm/elbow isolation load; reduce direct arm isolation work temporarily.",
    },
    {
        "joint": "Hip",
        "issue": "Hamstring strain history",
        "typical_culprit": ["Speed Deadlift", "Romanian Deadlift"],
        "safer_substitutes": ["Nordic Hamstring Curl", "Dumbbell Goblet Squat", "Belt Squat"],
        "note": "Start Nordic curls light; reintroduce heavy hinge loading gradually rather than jumping back to full-intensity sprinting or RDLs.",
    },
    {
        "joint": "Knee",  # "returning from any lower-body injury" - keyed to Knee since that's this table's closest 8-tag match; Hip/Ankle injuries route here too via the generic find_alternatives path.
        "issue": "Returning from any lower-body injury",
        "typical_culprit": ["Barbell Back Squat", "Barbell Conventional Deadlift"],
        "safer_substitutes": ["Belt Squat", "Dumbbell Goblet Squat"],
        "note": "Belt squat and goblet squat let you keep training the pattern while unloading the spine - progress back to the barbell once pain-free.",
    },
]

PART7_DISCLAIMER = (
    "Persistent pain is a signal to see a physiotherapist or sports medicine "
    "professional, not just to swap exercises - these substitutions are for "
    "training around minor niggles, not diagnosing or treating injuries."
)


def part7_substitution_guidance(joint: Optional[str] = None) -> List[Dict]:
    """The manual's Part 7.7 table, optionally filtered to one joint (the
    same 8-tag vocabulary as everything else in this file). Returns the
    full table when `joint` is None."""
    if joint is None:
        return PART7_SUBSTITUTION_TABLE
    return [row for row in PART7_SUBSTITUTION_TABLE if row["joint"] == joint]


def part7_recommended_swap(exercise: dict, all_exercises: Dict[str, dict], joint: str) -> List[dict]:
    """Cross-reference this exercise's joint against the manual's named
    substitution table and resolve each named substitute to a real
    exercises.json entry by name (case-insensitive), so the result is a
    clickable exercise, not just a string a UI would have to re-parse.
    Only returns rows whose `typical_culprit` list actually contains this
    exercise's name - a generic knee-pain row shouldn't attach itself to
    every squat variant regardless of which one the person was doing."""
    name = exercise.get("name", "")
    by_name = {e.get("name", "").lower(): e for e in all_exercises.values()}
    matches = []
    for row in part7_substitution_guidance(joint):
        if name.lower() not in [c.lower() for c in row["typical_culprit"]]:
            continue
        resolved = []
        for sub_name in row["safer_substitutes"]:
            cand = by_name.get(sub_name.lower())
            if cand:
                resolved.append({"id": cand["id"], "name": cand["name"]})
        matches.append({
            "issue": row["issue"],
            "note": row["note"],
            "substitutes": resolved,
        })
    return matches


# ============================================================================
# MUSCLE-GROUP BROWSING (v5.12 addition) — a second, purely presentational
# grouping dimension for the injury browser UI, alongside the load-bearing
# 8-tag `joint` vocabulary above. `joint` answers "which of the 8 tags does
# the engine filter on" (Shoulder covers deltoids, pecs, lats, and the
# rotator cuff alike); this answers "how would someone browsing for their
# injury describe where it is" (chest vs. back vs. shoulder are different
# places to a user even though they're all tagged Shoulder for filtering).
# Every *muscle* entry (tissue == "Muscle") is bucketed into an anatomical
# muscle-group category; everything else (ligament, tendon, joint/bone/
# nerve/fascia conditions, etc.) is bucketed by joint but labeled as a joint
# category — so the browser can offer "Chest / Back / Legs / ..." muscle
# categories distinctly from "Knee / Shoulder / ..." joint categories,
# instead of one flat list. Purely additive: nothing here changes `joint`
# or `severity`, so the engine's filtering behavior is untouched.
# ============================================================================
_MUSCLE_REGION_KEYWORDS = ("Thigh", "Groin", "Calf", "Shin", "Foot", "Lower Leg")
_CHEST_REGION_KEYWORDS = ("Chest", "Rib")
_JOINT_TO_MUSCLE_GROUP = {
    "Hip": "Hips & Glutes",
    "Wrist": "Arms & Hands",
    "Elbow": "Arms & Hands",
}
JOINT_CATEGORY_SUFFIX = " (Joints, Ligaments & Tendons)"


def _browse_body_region(entry: dict) -> str:
    """The muscle-group (or joint-category) label for one taxonomy entry -
    see module note above. Order matters: more specific region text is
    checked before falling back to the coarser `joint` tag."""
    joint = entry["joint"]
    tissue = entry.get("tissue", "")
    region = entry.get("region") or ""

    if tissue != "Muscle":
        # Non-muscle tissue (Ligament, Tendon, Joint, Bone, Nerve, Fascia,
        # legacy "Musculoskeletal", etc.) - keep the existing joint grouping,
        # just labeled distinctly so it doesn't read as a muscle category.
        return joint + JOINT_CATEGORY_SUFFIX

    if any(k in region for k in _CHEST_REGION_KEYWORDS):
        return "Chest"
    if "Abdomen" in region:
        return "Core & Abs"
    if any(k in region for k in _MUSCLE_REGION_KEYWORDS):
        return "Legs"
    if joint == "Neck":
        return "Neck"
    if joint == "Shoulder":
        return "Back" if "Back" in region else "Shoulder"
    if joint == "Lower Back":
        return "Back"
    return _JOINT_TO_MUSCLE_GROUP.get(joint, joint)


def _grade_summary(name: str, entry: dict) -> dict:
    """The per-grade dict both browse groupings (by-joint and
    by-muscle-group) return - factored out so `clinical_red_flags` (v5.17)
    only has to be added in one place. `clinical_red_flags` was already a
    fully-authored field on every taxonomy entry (see INJURY_FIELDS) but
    neither browse endpoint - the only place this data reaches the frontend
    - returned it, so a user could select e.g. "Concussion - Grade 3 (Loss
    of Consciousness)" without ever seeing its red flags text. Empty list
    when an entry has none, so existing consumers that don't read this key
    are unaffected."""
    return {
        "name": name,
        "severity": entry["severity"],
        "severity_label": SEVERITY_LABEL[entry["severity"]],
        "tissue": entry.get("tissue", ""),
        "region": entry.get("region", ""),
        "clinical_red_flags": entry.get("clinical_red_flags") or [],
        # v5.19 - see laterality_applicable's docstring. Only the browse
        # endpoints reach the frontend, so this is the one place that needs
        # to carry it for the injury browser to gate its side selector.
        "laterality_applicable": laterality_applicable(entry),
    }


@cache_forever
def grouped_injury_taxonomy_by_muscle_group() -> Dict[str, List[dict]]:
    """Same shape and same per-entry fields as `grouped_injury_taxonomy()`
    below (top-level category -> [{condition, grades: [...]}, ...]) but
    grouped by `_browse_body_region()` instead of the raw `joint` tag, so
    the UI can offer a "browse by muscle group" view (Chest / Back / Legs /
    Core & Abs / Hips & Glutes / Shoulder / Arms & Hands / Neck) alongside
    the existing "browse by joint" view, with the latter's ligament/tendon/
    joint-disorder entries kept separate under their own "<Joint> (Joints,
    Ligaments & Tendons)" categories rather than mixed into the muscle
    groups. Cached for the same reason as `grouped_injury_taxonomy()` -
    this is static, process-lifetime data.

    Category ordering: muscle-group categories first (a fixed anatomical
    order a user would scan top-to-bottom), then joint categories
    alphabetically."""
    by_region: Dict[str, Dict[str, list]] = {}
    for name, entry in INJURY_TAXONOMY.items():
        region_group = _browse_body_region(entry)
        condition = _condition_group(name)
        by_region.setdefault(region_group, {}).setdefault(condition, []).append(
            _grade_summary(name, entry)
        )

    result: Dict[str, List[dict]] = {}
    for region_group, conditions in by_region.items():
        result[region_group] = [
            {
                "condition": cond,
                "grades": sorted(grades, key=lambda g: g["severity"]),
            }
            for cond, grades in sorted(conditions.items())
        ]
        result[region_group].sort(key=lambda c: c["condition"])

    muscle_order = ["Chest", "Back", "Shoulder", "Neck", "Core & Abs", "Hips & Glutes", "Legs", "Arms & Hands"]
    muscle_keys = [k for k in muscle_order if k in result]
    joint_keys = sorted(k for k in result if k.endswith(JOINT_CATEGORY_SUFFIX))
    ordered = {k: result[k] for k in muscle_keys + joint_keys}
    return ordered


@cache_forever
def grouped_injury_taxonomy() -> Dict[str, List[dict]]:
    """{joint: [{condition, grades: [{name, severity, severity_label, tissue,
    region}, ...]}, ...]}, sections and subsections alphabetical, grades
    ordered mild -> severe.

    Cached (Phase 8): this re-walks the full INJURY_TAXONOMY dict (static,
    module-level, never mutated after import) on every call, and gets called
    twice per `/api/v1/metadata` request path (directly, and via
    `/api/v1/injuries/grouped`) - real duplicated work for a value that's
    identical for the life of the process. See backend/core/cache.py's
    docstring for why @cache_forever (not @ttl_cache) is correct here."""
    by_joint: Dict[str, Dict[str, list]] = {}
    for name, entry in INJURY_TAXONOMY.items():
        joint = entry["joint"]
        condition = _condition_group(name)
        by_joint.setdefault(joint, {}).setdefault(condition, []).append(
            _grade_summary(name, entry)
        )

    result: Dict[str, List[dict]] = {}
    for joint, conditions in by_joint.items():
        result[joint] = [
            {
                "condition": cond,
                "grades": sorted(grades, key=lambda g: g["severity"]),
            }
            for cond, grades in sorted(conditions.items())
        ]
        result[joint].sort(key=lambda c: c["condition"])
    return dict(sorted(result.items()))

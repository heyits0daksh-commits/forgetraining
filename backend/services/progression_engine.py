"""ProgressionEngine: the DAG/knowledge-graph exercise engine.

Split out of backend/main.py (Phase 2 of docs/ROADMAP.md - main.py
previously bundled routes + engine in one 1697-line file). No behavior
changed in the move: this is the same class, same helper functions
(level_fit_multiplier/level_fit_label), same module-level constants,
and the same single `engine = ProgressionEngine()` instance every
route used before - just relocated so backend/api/routes.py and
backend/main.py can both import it without main.py owning the engine
implementation itself.
"""
import copy
import json
import os
from collections import Counter
from typing import Dict, List, Optional

import networkx as nx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.exceptions import SevereInjuryBlockedError
from backend.models.schemas import (
    EXPERIENCE_LEVELS as _EXPERIENCE_LEVELS,
    ProgressionOverride,
    ReadinessInputs,
    UserBiometrics,
    WorkoutRequest,
)
from backend.services.injury_taxonomy import (
    INJURY_SIDES,
    INJURY_TAXONOMY,
    OPPOSITE_SIDE,
    REHAB_STAGES,
    classify_exercise_safety,
    classify_injury_risk,
    find_alternatives,
    laterality_applicable,
    laterality_clears_joint,
    part7_recommended_swap,
    resolve_severe_injuries,
    resolve_systemic_injury,
    worst_safety_color,
)
from backend.services.knowledge_graph import build_knowledge_graph, is_rehab_candidate
from backend.services.programming_role import ROLE_ORDER, STRIKE_SKILL_EXCLUDED_ROLE, classify_programming_role, session_order_rank
from backend.services.pl_hypertrophy_manual import STRENGTH_MODE_EXERCISE_NAMES
from backend.services.strength_standards import classify_strength_level, level_check, conservative_default_ratios
from backend.services.load_prescription import add_working_weight, missing_anchor_note
from backend.services.sport_profiles import (
    athlete_movement_priority_multiplier,
    blended_transfer_score,
    equipment_movement_priority_multiplier,
    hypertrophy_quality_multiplier,
    injury_avoidant_equipment_multiplier,
    movement_emphasis_multiplier,
    press_variation_multiplier,
    transfer_rationale,
)
from backend.services.conditioning_protocols import conditioning_reference
from backend.services.sc_template_library import normalize_exercise_name
from backend.services.program_builder import (
    _apply_prescription_bias,
    _estimate_exercise_count,
    _session_composition,
    _MAX_EFFORT_HINGE_FAMILIES,
    _MAX_EFFORT_HINGE_REP_CAP,
)
from backend.services.recommendation_engine import (
    PLATEAU_NOTE,
    build_history_signals,
    compute_adaptive_load_adjustment,
    personalization_multiplier,
)
from backend.services.ai_hooks import SessionContext, get_insight_provider
from backend.services.coach_notes import build_coach_notes
import random

EXPERIENCE_LEVELS = _EXPERIENCE_LEVELS
LEVEL_RANK = {lvl: i for i, lvl in enumerate(EXPERIENCE_LEVELS)}
# How many rungs above the user's own level we'll still show (a controlled "stretch").
LEVEL_STRETCH = 1

# LEVEL_STRETCH above only ever answers "is this exercise too advanced to show
# at all" - it's a ceiling, not a preference. Nothing else in the engine used
# to care whether a *qualifying* exercise actually matched the user's level,
# so sorting/selection ran purely on sport_priority_score. In practice that
# meant an Elite lifter and a Beginner asking for the same sport/equipment got
# the exact same ranked list, because a Beginner-tier movement with a high
# sport score (e.g. Push-Up scoring 85 for Boxing) would consistently
# out-rank Advanced/Elite-tier lifts with a merely-good sport score - "better"
# here meaning "more appropriate to train at this person's level", not just
# "more sport-relevant in isolation".
#
# level_fit_multiplier fixes that by discounting an exercise's score based on
# how many rungs its own experience_level sits from the user's stated level -
# 0 rungs away = no discount, further away = progressively discounted. The
# discount is asymmetric: exercises *below* the user's level are penalized
# more per rung than exercises *above* it, because the ceiling check above
# already keeps "above" in check (at most LEVEL_STRETCH rungs get through at
# all), so once an above-level exercise clears that gate it should still
# compete normally - while nothing upstream stops a trivially-easy exercise
# from clearing every other check and dominating on sport score alone.
LEVEL_FIT_PENALTY_PER_RUNG_BELOW = 0.15
LEVEL_FIT_PENALTY_PER_RUNG_ABOVE = 0.05
LEVEL_FIT_MIN_MULTIPLIER = 0.35


def level_fit_multiplier(ex_level_rank: int, user_level_rank: int) -> float:
    gap = ex_level_rank - user_level_rank
    if gap >= 0:
        penalty = gap * LEVEL_FIT_PENALTY_PER_RUNG_ABOVE
    else:
        penalty = -gap * LEVEL_FIT_PENALTY_PER_RUNG_BELOW
    return max(LEVEL_FIT_MIN_MULTIPLIER, 1 - penalty)


TEMPLATE_SEED_BOOST = 1.4


def template_seed_multiplier(ex_name_normalized: str, seed_names_normalized: Optional[set]) -> Dict:
    """{"multiplier": float, "matched": bool} for one exercise, given the
    normalized set of names from WorkoutRequest.template_seed_names (see
    sc_template_library.normalize_exercise_name - both sides of this
    comparison must already be normalized the same way; this function does
    no normalization itself). (1.0, False) - a complete no-op - when
    seed_names_normalized is empty/None, which is every existing caller
    (single /generate-workout requests, and any program day where no FORGE
    S&C Template matched this sport/level/days_per_week - see
    program_builder.generate_program).

    This is a SOFT re-rank, not a filter: it runs after `qualifies` is
    already decided (equipment/injury/strength/level all already gated the
    exercise in or out) and only nudges sport_score among exercises that
    already passed. A seeded name that got excluded upstream never reaches
    this function at all - it shows up in excluded_exercises exactly like
    any other unsafe pick, same as before FORGE S&C Template seeding
    existed. This is the deliberate difference from the old removed-for-good
    static "Manual" mode (see routes.py's module docstring): that mode
    served a template's fixed list AS the session; this only asks "if the
    engine independently judges this exercise safe and appropriate, should
    it be ranked above an equally-safe alternative because a coach's named
    template also picked it for this exact sport/level/day?" - the engine
    still makes every safety call itself, on every exercise, every time.

    Exact match on the normalized form only - a template name that still
    doesn't resolve to anything in the exercise database after
    normalization just doesn't get a boost, it doesn't error or skip the
    exercise, and it never falls back to a substring/fuzzy match that could
    boost the wrong lift.
    """
    if not seed_names_normalized or ex_name_normalized not in seed_names_normalized:
        return {"multiplier": 1.0, "matched": False}
    return {"multiplier": TEMPLATE_SEED_BOOST, "matched": True}


def level_fit_label(ex_level_rank: int, user_level_rank: int) -> str:
    gap = ex_level_rank - user_level_rank
    if gap == 0:
        return "Matched to your level"
    if gap > 0:
        return "A stretch above your level" if gap <= LEVEL_STRETCH else "Above your level"
    return "Below your level (still safe, but not your ceiling)" if gap == -1 else "Well below your level"


def _name_plateau_progression(note: str, exercise: Dict, exercises_by_id: Dict[str, Dict]) -> str:
    """Recommendation-engine pass follow-up (docs/ROADMAP.md's own "not done
    in this pass" note): a plateau note used to just say "consider its next
    progression" without naming one, even though the specific next-tier
    exercise is already sitting right in this same exercise's own
    `progressions` field (knowledge_graph.py builds its progression edges
    from this exact field). Only rewrites the generic PLATEAU_NOTE text -
    every other personalization note (freshness/repeat/progressing) is
    returned unchanged, and a plateaued exercise with no authored
    progressions (or one whose progression id doesn't resolve - shouldn't
    happen per test_exercise_data_integrity.py's dangling-reference check,
    but this stays defensive rather than assuming) keeps the generic
    phrasing too, since there's nothing real to name.
    """
    if note != PLATEAU_NOTE:
        return note
    for next_id in exercise.get("progressions") or []:
        next_ex = exercises_by_id.get(next_id)
        if next_ex and next_ex.get("name"):
            return f"Flat for a few sessions - consider progressing to {next_ex['name']}"
    return note

# Request/response schemas (ProgressionOverride, UserBiometrics, WorkoutRequest,
# ProgramRequest) now live in backend/models/schemas.py - see that module's
# docstring for why. Imported above; nothing about their fields or defaults
# changed in the move.


# ==========================================
# 2. DAG & KNOWLEDGE ENGINE
# ==========================================

class ProgressionEngine:
    def __init__(self, json_path: str = None):
        if json_path is None:
            json_path = str(settings.EXERCISES_JSON_PATH)

        self.json_path = json_path
        self.base_dag = nx.DiGraph()
        self.knowledge_graph = None  # built in load_database: multi-relational graph (see knowledge_graph.py)
        self.exercises_by_id: Dict[str, Dict] = {}
        self.all_sports: List[str] = []
        self.all_equipment: List[str] = []
        self.all_injuries: List[str] = []
        self.load_database()

    def load_database(self):
        if not os.path.exists(self.json_path):
            raise FileNotFoundError(f"Database file '{self.json_path}' not found.")

        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        exercises = data.get("exercises", [])
        self.exercises_by_id = {ex["id"]: ex for ex in exercises}

        for ex in exercises:
            self.base_dag.add_node(ex["id"], **ex)

        # Edge direction: regression -> progression (completing the regression unlocks the progression)
        for ex in exercises:
            for prog_id in ex.get("progressions", []):
                if prog_id in self.base_dag:
                    self.base_dag.add_edge(ex["id"], prog_id)

        if not nx.is_directed_acyclic_graph(self.base_dag):
            cycle = nx.find_cycle(self.base_dag)
            raise ValueError(f"Progression database contains a cycle, engine cannot resolve order: {cycle}")

        # Metadata derived straight from the data, so the frontend can never drift out of
        # sync with what the engine actually knows about (this used to be hand-typed twice).
        # Injuries now come primarily from INJURY_TAXONOMY (specific, severity-tagged
        # conditions like "ACL Tear - Grade 3 (Complete Rupture)") rather than the bare
        # joint_stress tags, so the user can say *how bad* an injury is, not just *where*
        # it is. The raw joint/tag strings from exercises.json are still unioned in below
        # so nothing that was previously selectable disappears.
        sports, equipment, injuries = set(), set(), set()
        injuries.update(INJURY_TAXONOMY.keys())
        for _, d in self.base_dag.nodes(data=True):
            sports.update(d.get("sport_priority", {}).keys())
            equipment.add(d.get("equipment", "Bodyweight"))
            injuries.update(d.get("joint_stress", []))
            injuries.update(d.get("injuries_to_avoid", []))
        self.all_sports = sorted(sports)
        self.all_equipment = sorted(equipment)
        self.all_injuries = sorted(injuries)

        # The actual multi-relational knowledge graph: progressions, equipment
        # substitutes, joint stress, rehab-candidacy, and sport transfer as
        # first-class typed edges - see knowledge_graph.py for why this exists
        # alongside base_dag rather than replacing it (base_dag stays the
        # per-request-mutable progression graph custom_progressions edits;
        # this is the queryable, base-data relationship map).
        self.knowledge_graph = build_knowledge_graph(exercises)

    def _apply_overrides(self, dag: nx.DiGraph, overrides: List[ProgressionOverride]):
        """Applies per-request customizations to a private COPY of the DAG.

        The engine previously mutated the single shared `self.base_dag` here, which meant
        one user's custom progression overrides would silently leak into and permanently
        corrupt every other user's results (and stack up over time). Every request now
        gets its own working graph.
        """
        for override in overrides:
            ex_id = override.exercise_id
            if ex_id not in dag:
                continue
            if override.custom_name:
                dag.nodes[ex_id]["name"] = override.custom_name
            if override.difficulty is not None:
                dag.nodes[ex_id]["difficulty"] = override.difficulty
            if override.equipment:
                dag.nodes[ex_id]["equipment"] = override.equipment
            if override.prerequisites:
                for prereq in override.prerequisites:
                    if prereq in dag:
                        dag.add_edge(prereq, ex_id)

        if not nx.is_directed_acyclic_graph(dag):
            cycle = nx.find_cycle(dag)
            raise HTTPException(
                status_code=400,
                detail=f"custom_progressions introduced a cycle: {cycle}",
            )

    def evaluate_biometrics_and_strength(
        self, biometrics: Optional[UserBiometrics], experience_level: Optional[str] = None,
    ) -> Dict:
        if not biometrics:
            # Previously this defaulted to a flat 0.0/0.0/0.0/0/0 regardless of the
            # person's stated experience_level - safe for a self-rated Beginner, but
            # for anyone Novice+ it meant EVERY strength_requirements-gated exercise
            # (bench press, overhead press, weighted pull-ups, ...) got excluded from
            # every session/program with no numbers entered, since a required ratio
            # like bench_ratio: 0.6 can never clear a hard 0.0 floor. What was left
            # to build a session from was only the zero-requirement bodyweight/
            # accessory pool - a "Push day" with no press in it, an "Upper Body" day
            # that's all planks/jumps/rows - technically safe, but not what "prove it
            # first" was meant to produce, and it read as an incoherent, mixed-up
            # program rather than a real one.
            # conservative_default_ratios keeps the same "never assume more than
            # they've told the engine" spirit, but ties the floor to their own stated
            # tier (one tier below what they claim) instead of ignoring it entirely -
            # see that function's docstring in strength_standards.py.
            defaults = conservative_default_ratios(experience_level)
            return {
                "bmi": None,
                "relative_bench_ratio": defaults["bench_ratio"],
                "relative_squat_ratio": defaults["squat_ratio"],
                "relative_deadlift_ratio": defaults["deadlift_ratio"],
                "pullups_max_reps": defaults["pullups"],
                "pushups_max_reps": defaults["pushups"],
                "status": (
                    "No biometrics provided - conservative (bodyweight-only) defaults applied"
                    if not experience_level or experience_level == "Beginner" else
                    f"No biometrics provided - conservative defaults for a self-reported "
                    f"{experience_level} lifter applied (enter your 1RMs for a precise plan)"
                ),
                # classify_strength_level(weight_kg=0.0) hits its own "nothing usable
                # entered" branch (same 0-means-untested convention as every other
                # field here), so this stays the single source of that shape instead
                # of a hand-typed duplicate of it.
                "level_estimate": classify_strength_level(weight_kg=0.0),
            }

        height_m = biometrics.height_cm / 100.0
        bmi = biometrics.weight_kg / (height_m ** 2)
        rel_bench = (biometrics.bench_press_1rm or 0.0) / biometrics.weight_kg
        rel_squat = (biometrics.squat_1rm or 0.0) / biometrics.weight_kg
        rel_deadlift = (biometrics.deadlift_1rm or 0.0) / biometrics.weight_kg

        # Independent, advisory-only estimate of overall training level from
        # these same numbers - see strength_standards.py. This never touches
        # strength_qualified/level_ok below (those still key off the
        # exercise's own strength_requirements and the person's *stated*
        # experience_level exactly as before); it just rides along in the
        # response so a mis-stated level is visible instead of silent (see
        # that module's docstring for why this was previously a real gap).
        level_estimate = classify_strength_level(
            weight_kg=biometrics.weight_kg,
            bench_press_1rm=biometrics.bench_press_1rm or 0.0,
            squat_1rm=biometrics.squat_1rm or 0.0,
            deadlift_1rm=biometrics.deadlift_1rm or 0.0,
            pullups_max_reps=biometrics.pullups_max_reps or 0,
            pushups_max_reps=biometrics.pushups_max_reps or 0,
            sex=biometrics.sex,
        )

        return {
            "bmi": round(bmi, 2),
            "relative_bench_ratio": round(rel_bench, 2),
            "relative_squat_ratio": round(rel_squat, 2),
            "relative_deadlift_ratio": round(rel_deadlift, 2),
            "pullups_max_reps": biometrics.pullups_max_reps or 0,
            "pushups_max_reps": biometrics.pushups_max_reps or 0,
            "status": "Biometrics analyzed",
            "level_estimate": level_estimate,
        }

    @staticmethod
    def _strength_gap(bio_eval: Dict, reqs: Dict) -> Dict:
        """How far the user is from qualifying for a locked exercise, per metric."""
        gap = {}
        pairs = [
            ("bench_ratio", "relative_bench_ratio", "x bodyweight bench"),
            ("squat_ratio", "relative_squat_ratio", "x bodyweight squat"),
            ("deadlift_ratio", "relative_deadlift_ratio", "x bodyweight deadlift"),
            ("pullups", "pullups_max_reps", "strict pull-ups"),
            ("pushups", "pushups_max_reps", "unbroken push-ups"),
        ]
        for req_key, bio_key, label in pairs:
            need = reqs.get(req_key, 0)
            have = bio_eval.get(bio_key, 0)
            if need and have < need:
                gap[req_key] = {"have": have, "need": need, "label": label}
        return gap

    # Weight each sub-factor contributes to the composite recovery score when
    # present. Renormalized over whatever subset was actually sent (a caller
    # who only sends sleep_hours still gets a sensible composite - sleep just
    # ends up carrying its full relative weight rather than being diluted by
    # missing fields defaulting to "neutral").
    _RECOVERY_WEIGHTS = {"sleep": 0.35, "soreness": 0.20, "stress": 0.15, "energy": 0.15, "motivation": 0.15}

    @classmethod
    def _compute_recovery(cls, flat_readiness: int, inputs: Optional[ReadinessInputs]) -> Dict:
        """Turns the readiness slider plus (optionally) a sleep/soreness/stress/
        energy/motivation breakdown into one recovery score and a couple of
        actionable flags. With no `inputs` at all this degrades exactly to the
        old behavior (the flat slider value, no flags) - nothing before this
        change gets a different result.
        """
        if inputs is None:
            return {
                "score": flat_readiness, "components": None,
                "poor_sleep": False, "high_soreness": False, "high_stress": False,
            }

        components = {}
        if inputs.sleep_hours is not None:
            # 8h -> 100, 4h or less -> 0, linear between, capped at 100 for long sleep.
            components["sleep"] = max(0.0, min(100.0, (inputs.sleep_hours - 4) / 4 * 100))
        if inputs.soreness is not None:
            components["soreness"] = (5 - inputs.soreness) / 4 * 100
        if inputs.stress is not None:
            components["stress"] = (5 - inputs.stress) / 4 * 100
        if inputs.energy is not None:
            components["energy"] = (inputs.energy - 1) / 4 * 100
        if inputs.motivation is not None:
            components["motivation"] = (inputs.motivation - 1) / 4 * 100

        if not components:
            return {
                "score": flat_readiness, "components": None,
                "poor_sleep": False, "high_soreness": False, "high_stress": False,
            }

        total_weight = sum(cls._RECOVERY_WEIGHTS[k] for k in components)
        composite = sum(components[k] * cls._RECOVERY_WEIGHTS[k] for k in components) / total_weight

        # Blend with the flat slider rather than replacing it outright - the slider
        # still carries the person's own overall gut-check even when they've also
        # filled in specifics (e.g. "I know my sleep/soreness look fine but I just
        # feel flat today").
        score = round(0.7 * composite + 0.3 * flat_readiness)
        score = max(1, min(100, score))

        return {
            "score": score,
            "components": {k: round(v) for k, v in components.items()},
            "poor_sleep": inputs.sleep_hours is not None and inputs.sleep_hours < 6,
            "high_soreness": inputs.soreness is not None and inputs.soreness >= 4,
            "high_stress": inputs.stress is not None and inputs.stress >= 4,
        }

    @staticmethod
    def _recovery_label(score: int) -> str:
        if score >= 80:
            return "Primed - ready for heavy training"
        if score >= 60:
            return "Ready - normal training"
        if score >= 40:
            return "Moderate - train smart, watch your top sets"
        return "Deload - prioritize recovery today"

    @staticmethod
    def _prescribe_volume(
        data: Dict, readiness_factor: float, deload: bool, poor_sleep: bool = False,
        conditioning_emphasis: str = "Mixed", volume_multiplier: float = 1.0,
    ) -> Dict:
        """Thin wrapper around `_prescribe_volume_core` that also applies the
        adaptive-load `volume_multiplier` (see recommendation_engine.
        compute_adaptive_load_adjustment) to whatever `sets` count the core
        prescription came back with. Kept as a separate wrapper rather than
        threading the multiplier through every one of the core function's
        return points individually, since it has several category-specific
        branches that each return their own dict shape - this applies in one
        place, after the fact, to whichever shape came back.

        1.0 (the default, and every caller before this existed) is a
        complete no-op: `sets` is returned exactly as the core function
        produced it.
        """
        prescription = ProgressionEngine._prescribe_volume_core(
            data, readiness_factor, deload, poor_sleep, conditioning_emphasis,
        )
        if volume_multiplier != 1.0 and "sets" in prescription:
            original_sets = prescription["sets"]
            adjusted_sets = max(1, round(original_sets * volume_multiplier))
            if adjusted_sets != original_sets:
                prescription["sets"] = adjusted_sets
                prescription["volume_adjusted"] = True
        return prescription

    @staticmethod
    def _prescribe_volume_core(
        data: Dict, readiness_factor: float, deload: bool, poor_sleep: bool = False,
        conditioning_emphasis: str = "Mixed",
    ) -> Dict:
        """Turns a bare exercise definition into an actual sets/reps/load prescription.

        This is intentionally simple (it's a rules engine, not a coach), but it reacts to
        difficulty, category and today's readiness instead of returning a single flat
        "intensity factor" the old engine produced regardless of what the movement was.
        `poor_sleep` specifically trims heavy compound-lift intensity even on a day
        that isn't in overall deload range - a coach backs off the big bar lifts on
        bad sleep well before overall readiness collapses to 40%.
        `conditioning_emphasis` picks which energy system a Conditioning/Jump/Power
        exercise's work:rest interval is actually built around - see
        schemas.CONDITIONING_EMPHASES for what each one means.
        """
        category = data.get("category", "")
        movement_pattern = data.get("movement_pattern", "")
        equipment_lower = data.get("equipment", "Bodyweight").lower()
        difficulty = data.get("difficulty", 1)
        reqs = data.get("strength_requirements") or {}
        is_loaded_strength = category in {
            "Horizontal Push", "Vertical Push", "Horizontal Pull", "Vertical Pull", "Squat", "Hinge",
        }

        # ISOLATION FIX (reported bug: prescribed weight "sometimes comes
        # wrong" - e.g. a Cable Lateral Raise or Dumbbell Hammer Curl coming
        # back at 35-60kg). Root cause: every exercise inside these six
        # movement-pattern categories used to get routed through the SAME
        # heavy-compound branch below (40-92% of the person's tested
        # Bench/Squat/Deadlift, via load_prescription._ANCHOR_BY_CATEGORY) -
        # correct for Bench Press, Back Squat, Pendlay Row, etc, but the same
        # six categories also hold single-joint accessory/isolation work
        # filed there for muscle-balance purposes only (Cable Lateral Raise
        # and Pec Deck Fly are "Vertical Push"/"Horizontal Push" by movement
        # pattern; Dumbbell Hammer Curl, Cable Bicep Curl and Reverse Pec
        # Deck/Rear-Delt Fly are "Vertical Pull"/"Horizontal Pull"). Loading
        # a rear-delt fly or a bicep curl to 55-65% of a deadlift produces a
        # weight nobody can or should put on that machine.
        # `strength_requirements` (already collected above as `reqs`) is
        # per-exercise, not per-category - the exercise database already
        # marks which lifts are actually gated behind a fraction of the
        # anchor lift (Pendlay Row: deadlift_ratio 0.6) vs which aren't
        # (Cable Lateral Raise, Cable Bicep Curl, Reverse Pec Deck, Pec Deck
        # Fly, Leg Extension, Leg Curl: ratio 0.0 for their category's own
        # field) - a ratio of 0 is the database's own signal that this
        # exercise was never meant to be validated against, or loaded off,
        # that compound max. That's the split used here instead of a flat
        # category check.
        _ISOLATION_RATIO_FIELD = {
            "Squat": "squat_ratio", "Hinge": "deadlift_ratio",
            "Horizontal Push": "bench_ratio", "Vertical Push": "bench_ratio",
            "Horizontal Pull": "deadlift_ratio", "Vertical Pull": "deadlift_ratio",
        }
        # NOTE (audit fix): "barbell" was previously in this exemption set
        # alongside the genuinely-bodyweight equipment types below. That was
        # too broad - a barbell IS a real, tested %1RM-anchored implement
        # (unlike bodyweight/rings/etc, which never had an anchor to begin
        # with), so its exercises' own strength_requirements ratio field is
        # a trustworthy isolation signal, not one that needs blanket
        # protection. With "barbell" included, every barbell isolation
        # movement whose ratio was correctly set to 0 (Standing Barbell
        # Curl, Barbell Drag Curl, Barbell 21s, Barbell Reverse Curl,
        # Barbell Skullcrusher) fell through to the heavy compound branch
        # instead - e.g. a Barbell Skullcrusher coming back prescribed at
        # 110kg for a strong lifter, using the Horizontal Push category's
        # bench-based anchor. The handful of legitimate barbell compound/
        # bodyweight-loaded lifts that used to lean on this exemption
        # because their own ratio was left at the 0 default (Good Morning,
        # Kang Squat, Zercher Reverse Lunge/Split Squat, Meadows Row, Single
        # Arm Barbell Row, Fat-Grip Row, both Inverted Bar Row variants) now
        # have real nonzero ratios set directly in exercises.json instead -
        # the ratio field is the correct place for that signal to live, not
        # an equipment-wide carve-out.
        # ORDERING FIX (reported bug: "kettlebell swing and many more
        # exercises" getting the wrong reps/sets/weight). exercises.json
        # only has a nonzero deadlift_ratio for ONE of the seven Hinge-
        # category kettlebell movements (Russian Kettlebell Swing: 0.5) -
        # One-Handed Kettlebell Swing, Kettlebell Deadlift, Kettlebell High
        # Pull, and Kettlebell Romanian Deadlift are all left at the 0.0
        # default, same as a genuinely unloaded isolation accessory. The
        # is_isolation check below reads that 0.0 exactly the same way it
        # reads Cable Lateral Raise's 0.0 - "never meant to be loaded off
        # the deadlift max" - and, since is_isolation was being evaluated
        # BEFORE is_kb_ballistic further down, it intercepted these
        # exercises first: they got the generic 10-20 rep, no-weight-at-all
        # isolation prescription instead of the moderate-load/higher-rep
        # kettlebell-appropriate one is_kb_ballistic exists specifically to
        # give them (and which its own docstring below explicitly claims
        # covers "Russian/One-Handed Swing"). Computing and checking
        # is_kb_ballistic first - before is_isolation gets a chance to
        # short-circuit on a merely-unfilled ratio field - means every
        # Kettlebell Hinge/Full-Body movement reaches the branch that was
        # actually built for it, regardless of whether its ratio field
        # happens to be filled in. Full Body kettlebell work (Clean,
        # Snatch, Jerk, Windmill, Turkish Get-Up, ...) was never affected
        # by this ordering - "Full Body" isn't in _ISOLATION_RATIO_FIELD at
        # all, so is_isolation was already structurally False for it.
        is_kb_ballistic = equipment_lower == "kettlebell" and category in {"Hinge", "Full Body"}

        _ratio_field = _ISOLATION_RATIO_FIELD.get(category)
        is_isolation = (
            is_loaded_strength and _ratio_field is not None
            and not (reqs.get(_ratio_field) or 0) > 0
            and equipment_lower not in {"bodyweight", "pull-up bar", "rings", "suspension trainer", "parallel bars"}
            and not is_kb_ballistic
        )
        if is_isolation:
            # Reference packet's "Isolation" row: 10-20 reps, 2-4 sets,
            # "Moderate" intensity, 60-120s rest - no %1RM figure at all
            # (unlike Power/Strength/Hypertrophy, which the packet gives an
            # explicit %1RM band for). Matching that exactly: no working
            # weight is fabricated off an unrelated compound max here -
            # reps/sets/rest only, same "don't invent a load the source
            # doesn't give a basis for" rule the bodyweight-strength branch
            # below already follows for pull-ups/push-ups/dips.
            iso_sets = 2 if deload else (4 if difficulty >= 3 else 3)
            iso_reps = max(10, min(20, 20 - difficulty * 3))
            if deload:
                iso_reps = max(10, iso_reps - 2)
            return {
                "type": "isolation",
                "sets": iso_sets,
                "reps": iso_reps,
                "rest_seconds": 60 if difficulty <= 1 else 90,
                "note": "Isolation/accessory work - pick a moderate, challenging load for this rep range "
                        "(leave ~0-2 reps in reserve on the last set); not anchored to your tested 1RMs.",
            }

        # Kettlebell ballistic work (Russian/One-Handed Swing - category
        # "Hinge", same category barbell RDL/deadlift work uses - and KB
        # Clean/Snatch/Jerk/Double KB Clean and Jerk - category "Full
        # Body") is genuinely loaded, but NOT a near-1RM barbell lift: the
        # reference guide programs it with moderate load and shorter rest
        # for higher-rep ballistic sets, not a heavy 2-3min-rest strength
        # prescription. Two bugs previously stacked here for these same
        # exercises:
        #   1. KB Swing's category ("Hinge") is one of the six base
        #      is_loaded_strength categories above, checked before any
        #      equipment distinction exists - so it was silently getting
        #      the FULL heavy-strength branch below (deadlift-anchored,
        #      up to 92% 1RM, 2-3min rest), identical treatment to a
        #      Barbell RDL, despite the comment on is_loaded_power_lift
        #      just below claiming kettlebell was "deliberately excluded"
        #      from exactly this heavy-strength treatment.
        #   2. KB Clean/Snatch/Jerk's category ("Full Body") isn't in
        #      is_loaded_strength OR in the Conditioning/Jump/Power branch
        #      further down, so it fell all the way through to the bare
        #      reps-only "technical" fallback at the bottom of this
        #      function - no load information (weight or %1RM) at all.
        # Checked up front, before is_loaded_power_lift and the ordinary
        # is_loaded_strength branches, so it can't be shadowed by either.
        # Barbell/Dumbbell Hinge and Full Body work (RDL, Deadlift, Clean
        # and Jerk, Power Snatch, ...) is untouched - this only fires for
        # the kettlebell versions of these two categories.
        # (is_kb_ballistic itself is now computed earlier, before the
        # is_isolation check above - see the ORDERING FIX comment there.)
        if is_kb_ballistic:
            kb_sets = 2 if deload else (4 if difficulty >= 3 else 3)
            reps = max(8, 20 - difficulty * 2)
            base_pct = 30 + difficulty * 5
            load_pct_1rm = round(min(60, max(20, base_pct * (0.8 + 0.2 * readiness_factor))))
            if deload:
                load_pct_1rm = round(load_pct_1rm * 0.8)
            return {
                # Kept as "strength" (not a distinct type) so
                # load_prescription.add_working_weight - which only converts
                # %1RM to an actual kg number for type=="strength" - still
                # fires and shows a real kettlebell weight, not just a bare
                # percentage.
                "type": "strength",
                # BUGFIX (goal selection was corrupting KB ballistic
                # numbers): program_builder._apply_prescription_bias remaps
                # any type=="strength" prescription onto the selected goal's
                # Power/Strength/Hypertrophy window (e.g. Get Strong -> 2-6
                # reps @ 75-90%, Power -> 1-3 reps @ 70-85%) - correct for a
                # barbell squat/bench/deadlift, but it was ALSO catching this
                # branch's output, since both share the plain "strength"
                # type. That silently threw away the ballistic-appropriate
                # numbers computed just above (8-20 reps, 20-60% load,
                # 60-90s rest) and replaced a Kettlebell Swing with
                # something like "3x3 @ 82% 1RM" the moment any goal was
                # selected - a near-max-effort low-rep prescription that is
                # not how swings/cleans/snatches are ever programmed, and
                # not what this branch (and the module docstring above it)
                # exists to prevent. This "ballistic" flag lets
                # _apply_prescription_bias recognize and skip this specific
                # prescription while every other type=="strength" lift
                # keeps remapping normally.
                "ballistic": True,
                "sets": kb_sets,
                "reps": reps,
                "load_pct_1rm": load_pct_1rm,
                "rest_seconds": 60 if difficulty <= 2 else 90,
            }

        # The "Power" and "Full Body" categories both conflate genuine loaded
        # barbell/implement lifts (Clean Pull, Hang Power Clean, Power
        # Snatch, DB Snatch, Push Press/Jerk, Sandbag Clean, Log Clean,
        # Axle Clean, Keg Clean, Atlas Stone, Fingal's Fingers, Husafell
        # Stone) with true single-effort throws/slams (Medicine Ball Slam/
        # Rotational Throw/Chest Pass, Keg Toss). Only the former are
        # actually programmed by reps and a working load - nobody
        # prescribes a clean pull, a power snatch, or a sandbag clean as
        # "X sec work" with no weight, which is what every one of these was
        # getting before (they all fell through to the generic no-load
        # reps fallback at the bottom of this function, since neither
        # "Power" nor "Full Body" had a dedicated branch). Distinguish by
        # equipment (a held/loaded implement vs. a thrown one) and exclude
        # genuine throw/rotational patterns even on loaded implements (Keg
        # Toss uses a Keg but is a throw, not a lift). Kettlebell is
        # deliberately excluded - KB ballistic work (swings, KB
        # clean/snatch/jerk) is programmed with shorter rest and moderate
        # load per the reference guide, not this branch's heavier
        # near-1RM/2-3min-rest treatment, so it's left on the generic path
        # rather than force-fit here.
        #
        # "Jump" carries the exact same gap "Power"/"Full Body" had before
        # this branch existed - a loaded Jump Squat (Barbell) or Trap Bar
        # Jump is still a weighted lift programmed by reps and a working
        # load, not a bodyweight-style timed plyo interval. Both were still
        # falling through to the Conditioning/Jump/Power branch below ("X
        # sec work" with no weight) because that branch only ever checked
        # category, and "trap bar" wasn't even in the loaded-implement set -
        # unlike every bodyweight/Plyo-Box/Tire/Weighted-Vest jump in this
        # same category, which genuinely IS timed bodyweight plyo work and
        # is left on that path unchanged.
        _LOADED_POWER_EQUIPMENT = {
            "barbell", "dumbbell", "keg", "sandbag", "log bar", "axle bar",
            "atlas stone", "fingal's fingers", "husafell stone", "trap bar",
        }
        is_loaded_power_lift = (
            category in {"Power", "Full Body", "Jump"}
            and equipment_lower in _LOADED_POWER_EQUIPMENT
            and movement_pattern not in {"Throw", "Rotational", "Isometric"}
        )
        # BARBELL "HIGH PULL" FAMILY FIX (reported bug: Snatch High Pull
        # coming back prescribed 4x8 @ 75% 1RM - an 8-rep hypertrophy-style
        # set on a maximal-velocity explosive pull, which is exactly the
        # "grinding technique breaks down under fatigue" injury risk
        # is_loaded_power_lift exists to prevent for Power Clean/Power
        # Snatch/Clean Pull above). Root cause: the barbell/power-rack
        # "High Pull" family (Clean High Pull, Snatch High Pull, Hang High
        # Pull, plain "High Pull", Snatch Pull, Rack Pull High Pull) is
        # filed under category "Hinge" in exercises.json, alongside every
        # ordinary Romanian Deadlift/Deadlift/Good Morning variant -
        # is_loaded_power_lift only ever checked category in {"Power",
        # "Full Body", "Jump"}, so "Hinge" was never in scope no matter what
        # the exercise actually was, and every one of these fell straight
        # into the generic is_loaded_strength branch below (built for slow,
        # technically-stable compounds that hold their form to 8-12 reps).
        # velocity_type=="Explosive" + force_type=="Stretch-Shortening
        # Cycle" is the same signal the exercise database already uses to
        # mark these as maximal-velocity catch-and-pull movements, and
        # cleanly separates them from the rest of Hinge: every ordinary
        # Deadlift/RDL/Good Morning variant is "Slow Strength"/"Concentric".
        # Kettlebell High Pull carries the same velocity/force pair but is
        # already routed correctly above by is_kb_ballistic (checked and
        # returned before this point); Mid-Thigh Pull and Isometric
        # Mid-Thigh Pull are "Isometric" force_type, not SSC, so they're
        # untouched and stay on their existing path.
        is_explosive_hinge_pull = (
            category == "Hinge"
            and data.get("velocity_type") == "Explosive"
            and data.get("force_type") == "Stretch-Shortening Cycle"
        )
        is_loaded_power_lift = is_loaded_power_lift or is_explosive_hinge_pull
        is_loaded_strength = is_loaded_strength or is_loaded_power_lift

        if deload:
            sets = 2
        elif difficulty >= 4:
            sets = 5
        elif difficulty >= 3:
            sets = 4
        else:
            sets = 3

        # Ruck March (any variant: "Heavy Ruck March", "Weighted Vest Ruck
        # March") is a single continuous loaded-walk effort measured in time
        # and distance by every actual ruck program (military PT, GORUCK,
        # etc.) - it has no sets/reps or rounds-of-work structure at all,
        # unlike every other exercise this function prescribes. Checked
        # before the loaded-strength/Conditioning/Carry branches below so it
        # can never fall into "sets x distance" (the Carry branch) or "sets
        # x reps" (the generic Sport-Specific fallback) by category alone.
        if "ruck march" in data.get("name", "").lower():
            distance_km = round((3 + difficulty * 1.5) * (0.7 + 0.3 * readiness_factor), 1)
            if deload:
                distance_km = round(distance_km * 0.6, 1)
            pace_min_per_km = 12  # brisk loaded-ruck pace under a weighted vest/pack
            duration_minutes = round(distance_km * pace_min_per_km)
            return {
                "type": "ruck",
                "distance_km": distance_km,
                "duration_minutes": duration_minutes,
                "note": (
                    "Single continuous ruck, prescribed by time and distance - not sets/reps. "
                    "Run it at the very end of the session as the conditioning finisher, after "
                    "all lifting is done, not as an early technical or carry-accessory slot."
                ),
            }

        # A static hold is a static hold regardless of what category the
        # exercise happens to be filed under - Front Lever, Planche, Human
        # Flag, and Maltese Cross (Full Body), Passive Dead Hang and Wall
        # Sit-style holds (whatever loaded-strength category they inherit),
        # the ankle/calf isometric holds (Calf Raise), and the genuine
        # plank/hang work in Core/Grip all share the same "hold_seconds,
        # not reps, no fabricated load %" shape. This used to only fire for
        # the six loaded-strength categories with bodyweight-only
        # equipment, or for anything filed under Core/Grip - so a Full
        # Planche or Human Flag (category "Full Body") or a "Single-Leg
        # Calf Raise Isometric Hold" (category "Calf Raise") fell through
        # to the generic reps fallback instead ("hold a Full Planche for
        # 6 reps" isn't a real prescription). Checked by movement_pattern
        # up front, before any category branch, so it can't be missed by
        # category alone. "Hang" (dead hangs, hangboard/campus-board work)
        # gets the same hold-based shape - a hang is timed, not reps.
        if movement_pattern in {"Isometric", "Hang"}:
            hold_s = round((15 + difficulty * 10) * (0.7 + 0.3 * readiness_factor))
            if deload:
                hold_s = round(hold_s * 0.7)
            return {"type": "isometric", "sets": sets, "hold_seconds": hold_s, "rest_seconds": 60}

        # Push-Ups, Pull-Ups, Dips, Pistol Squats, Ring Rows, and their
        # rep-based progressions all carry one of the six "loaded strength"
        # categories above because that's genuinely the movement-pattern
        # family they belong to - but there's no barbell, dumbbell, or
        # machine involved, so "X reps @ Y% of 1RM" has nothing to actually
        # reference. That "% 1RM" load previously got generated anyway,
        # purely from the exercise's difficulty rating, completely
        # disconnected from any real max the person has - it showed up as
        # e.g. "Negative Pull-Up: 3x6 reps @ 66% 1RM" (a bodyweight skill
        # with a fabricated barbell-style load). Bodyweight-equipment work
        # gets routed here instead: reps only, no fabricated load % (the
        # Isometric/Hang case above is already handled and can't reach
        # here).
        _BODYWEIGHT_ONLY_EQUIPMENT = {"bodyweight", "pull-up bar", "rings", "suspension trainer", "parallel bars"}
        if is_loaded_strength and equipment_lower in _BODYWEIGHT_ONLY_EQUIPMENT:
            reps = max(3, 15 - difficulty * 2)
            prescription = {
                "type": "strength_bodyweight",
                "sets": sets,
                "reps": reps,
                # Same guide-aligned baseline as the loaded-strength branch above.
                "rest_seconds": 120 if difficulty <= 2 else 180,
            }
            if difficulty >= 4:
                prescription["note"] = (
                    "Advanced bodyweight skill - prioritize clean reps over chasing more; "
                    "add reps before progressing to a harder variation."
                )
            return prescription

        # THRUSTER FIX (reported bug: Dumbbell Thruster/Thruster coming back
        # prescribed ~3-4 reps at ~70% 1RM, flagged `ballistic: True` with a
        # "stop the set the moment bar speed or technique drops" note. Root
        # cause: a Thruster (barbell or dumbbell) is category "Full Body",
        # equipment barbell/dumbbell, movement_pattern "Complex" - exactly
        # the shape `is_loaded_power_lift` above was built to catch, so it
        # fell into the TRUE-OLYMPIC-LIFT branch just below alongside Power
        # Clean/Power Snatch/Push Jerk. But a Thruster is a squat-to-
        # overhead-press GRIND, not a catch-and-pull: its own
        # velocity_type is "Slow Strength" (Power Clean/Snatch/Push Jerk
        # are "Explosive"/"Max Strength" - the exercise database already
        # marks the difference). Real programming for it - CrossFit/HYROX
        # metcon work, general strength-conditioning - runs it for
        # moderate-to-higher reps (8-15 typical), never a 1-5-rep "stop at
        # the first sign of slowing down" cap meant for a maximal-velocity
        # barbell catch. Checked by name (same approach the ruck-march
        # special-case below already uses) and returned before
        # `is_loaded_power_lift` gets a chance to intercept it, so it can
        # never fall into that branch regardless of category/equipment.
        is_thruster = "thruster" in data.get("name", "").lower()
        if is_thruster:
            sets = 2 if deload else (4 if difficulty >= 3 else 3)
            base_pct = 45 + difficulty * 5
            load_pct_1rm = round(min(70, max(35, base_pct * (0.85 + 0.15 * readiness_factor))))
            reps = max(8, min(15, 16 - difficulty * 2))
            if deload:
                reps = max(8, reps - 2)
            return {
                "type": "strength",
                "sets": sets,
                "reps": reps,
                "load_pct_1rm": load_pct_1rm,
                "rest_seconds": 90 if difficulty <= 2 else 120,
                "note": "Squat-to-press compound, not a catch/pull lift - programmed for "
                        "moderate-higher reps, not capped low like an Olympic lift.",
            }

        # TRUE OLYMPIC-LIFT-STYLE PRESCRIPTION (reported bug: an explosive
        # loaded lift - Power Clean, Hang Power Clean, Power Snatch, Clean
        # Pull, Push Press/Jerk, Sandbag/Log/Axle Clean, Atlas Stone, ... -
        # could come back prescribed for up to 8 reps at low difficulty/
        # light load. Root cause: `is_loaded_power_lift` (computed above)
        # was only ever OR'd into the generic `is_loaded_strength` flag and
        # then fell straight through to that branch's formula below, which
        # is built for slow, technically-STABLE compounds - a bench press
        # or back squat holds its technique fine all the way to 8-12 reps.
        # An explosive barbell pull/catch does not: technique - and the
        # injury risk that comes with it breaking down under fatigue -
        # degrades fast past a handful of near-max-effort explosive reps,
        # which is exactly why the reference guide's own Part 4 rep-range
        # key puts these first in the session while fresh and caps them
        # low (1-5, most commonly 2-3), never treats them as an 8-rep
        # hypertrophy-style set. Checked and returned here, BEFORE the
        # generic is_loaded_strength branch, so it can never fall into that
        # branch's higher-rep formula. `ballistic: True` (same flag the KB
        # ballistic branch above already uses) keeps
        # program_builder._apply_prescription_bias from remapping these
        # hand-tuned low-rep numbers onto a goal's Power/Strength/
        # Hypertrophy window - those windows describe how to load a
        # squat/bench/deadlift, not a Power Clean.
        if is_loaded_power_lift:
            sets = 2 if deload else (5 if difficulty >= 4 else (4 if difficulty >= 3 else 3))
            # Capped noticeably below the generic 92% ceiling below - a
            # genuine near-max single on an explosive catch/pull is a
            # competition/testing effort, not a normal training day's
            # working set.
            base_pct = 55 + difficulty * 5
            load_pct_1rm = round(min(85, max(45, base_pct * (0.85 + 0.15 * readiness_factor))))
            # 1-5 reps across the whole 1-5 difficulty scale - a harder/more
            # technical variant (higher difficulty rating) gets FEWER reps,
            # not more, the opposite of how the generic formula below scales.
            reps = max(1, min(5, 6 - difficulty))
            if deload:
                reps = max(1, reps - 1)
            return {
                "type": "strength",
                "ballistic": True,
                "sets": sets,
                "reps": reps,
                "load_pct_1rm": load_pct_1rm,
                "rest_seconds": 150 if difficulty <= 2 else 180,
                "note": "Explosive/technical lift - low reps by design; stop the set the moment bar "
                        "speed or technique drops, not at a fixed rep-count.",
            }

        if is_loaded_strength:
            base_pct = 55 + difficulty * 7
            load_pct_1rm = round(min(92, max(40, base_pct * (0.8 + 0.2 * readiness_factor))))
            # Bad sleep specifically caps intensity on the heavier compounds (difficulty
            # 3+) even when overall readiness/deload_mode wouldn't otherwise trigger it -
            # this is the "chest soreness / bad sleep -> lighter today" behavior a flat
            # readiness-only multiplier can't express, since it treats every exercise the
            # same regardless of how CNS-demanding it actually is.
            sleep_adjusted = poor_sleep and difficulty >= 3 and not deload
            if sleep_adjusted:
                load_pct_1rm = round(max(40, load_pct_1rm * 0.92))
                sets = max(2, sets - 1)
            reps = max(3, 14 - difficulty * 2 - int(load_pct_1rm / 15))
            # MAX-EFFORT HINGE CAP (reported bug: "compounds like deadlift"
            # getting too many reps). A full-ROM conventional/sumo deadlift,
            # rack pull, or Good Morning loads the spine near a technical
            # limit on every single rep, unlike a Romanian Deadlift or
            # kettlebell swing (both deliberately submaximal/partial-ROM,
            # routinely programmed for 8-12+ reps) - no real strength coach
            # lets these creep past ~6 reps, since the risk isn't the load,
            # it's grinding out rep 7-8 with a rounding back and fried grip.
            # program_builder._apply_prescription_bias already caps these
            # same families at _MAX_EFFORT_HINGE_REP_CAP once a goal/
            # emphasis is selected (see its own docstring) - but the base
            # formula above, run whenever NO goal is selected at all (the
            # default request), had no such cap and could still hand back
            # up to 8 reps on a heavy floor deadlift at low difficulty/
            # light readiness-scaled load. Applying the same cap here closes
            # that gap for the un-biased path too, instead of only ever
            # protecting it when a goal happens to be set.
            movement_family = data.get("movement_family")
            if movement_family in _MAX_EFFORT_HINGE_FAMILIES:
                reps = min(reps, _MAX_EFFORT_HINGE_REP_CAP)
            # Baseline (no training_emphasis/goal selected) sits in the
            # reference guide's "Strength + muscle" master range - reps
            # 5-10, rest 2-3 min - the sensible middle ground between the
            # guide's dedicated Power/Strength (2-5 min) and Hypertrophy
            # (1-3 min) windows that program_builder._apply_prescription_bias
            # remaps onto when a goal IS selected. Previously 90/150s
            # (1.5/2.5 min) here, under the guide's floor either way.
            prescription = {
                "type": "strength",
                "sets": sets,
                "reps": reps,
                "load_pct_1rm": load_pct_1rm,
                "rest_seconds": 120 if difficulty <= 2 else 180,
            }
            if sleep_adjusted:
                prescription["sleep_adjusted"] = True
                prescription["note"] = "Load trimmed for poor sleep - this is a CNS-demanding lift."
            return prescription

        if category in {"Conditioning", "Jump", "Power"}:
            if conditioning_emphasis == "Alactic":
                # Phosphagen system: short max-effort bursts, near-full recovery
                # so output quality never degrades rep to rep (a coach would
                # never let these turn into a lactic-burn set).
                work_s = round((5 + difficulty * 2) * (0.85 + 0.15 * readiness_factor))
                rest_s = round(work_s * (6 if not deload else 8))
            elif conditioning_emphasis == "Aerobic":
                # Steady-state / long intervals: rest stays short relative to
                # work so heart rate never fully recovers between efforts.
                work_s = round((45 + difficulty * 15) * (0.7 + 0.3 * readiness_factor))
                rest_s = round(work_s * (0.4 if not deload else 0.7))
            elif conditioning_emphasis == "Lactic":
                # Glycolytic "burn" zone: sustained high output with
                # incomplete recovery.
                work_s = round((20 + difficulty * 10) * (0.7 + 0.3 * readiness_factor))
                rest_s = round(work_s * (1.3 if not deload else 2.2))
            else:  # "Mixed" - original difficulty-only formula, unchanged behavior
                work_s = round((15 + difficulty * 8) * (0.7 + 0.3 * readiness_factor))
                rest_s = round(work_s * (1.5 if not deload else 2.5))
            prescription = {
                "type": "conditioning",
                "sets": sets,
                "work_seconds": work_s,
                "rest_seconds": rest_s,
            }
            if conditioning_emphasis != "Mixed":
                prescription["energy_system"] = conditioning_emphasis
            return prescription

        if category == "Carry":
            distance_m = round((25 + difficulty * 10) * (0.7 + 0.3 * readiness_factor))
            # Carries had NO load prescription at all before this - distance
            # only, with nothing telling the athlete how heavy to load the
            # implement. Fixed the same way strength lifts get a load: %
            # bodyweight (the standard way carries are actually programmed,
            # since there's no 1RM for a farmer's walk), converted to kg by
            # load_prescription.add_working_weight downstream.
            #
            # Bilateral/centrally-loaded carries (Farmer's Walk, Yoke, Bear
            # Hug, Zercher) and one-sided carries (Suitcase Carry) are NOT
            # the same prescription - a suitcase carry's limiting factor is
            # resisting lateral spinal flexion on the unloaded side, not raw
            # grip/trunk load capacity, so it's programmed meaningfully
            # lighter per hand than a two-handed farmer's walk's total load.
            # movement_type=="Unilateral" is the primary signal; the name
            # check catches "Suitcase Carry"/"Single-Arm ..." entries whose
            # movement_type is itself mistagged "Bilateral" in the data
            # (see data/exercises.json suitcase_carry_001 - also corrected
            # directly in this same fix) so a name change or new addition
            # isn't silently missed if the tag drifts again.
            name_lower = data.get("name", "").lower()
            movement_type = data.get("movement_type", "")
            is_one_sided = (
                movement_type == "Unilateral"
                or "suitcase" in name_lower
                or "single-arm" in name_lower
                or "single arm" in name_lower
            )
            base_pct = 35 + difficulty * 9
            if is_one_sided:
                base_pct *= 0.55  # per-hand load on a one-sided carry, not total
            cap = 65 if is_one_sided else 140
            load_pct_bodyweight = round(min(cap, max(20, base_pct * (0.8 + 0.2 * readiness_factor))))
            if deload:
                load_pct_bodyweight = round(load_pct_bodyweight * 0.8)
            return {
                "type": "carry",
                "sets": sets,
                "distance_meters": distance_m,
                "load_pct_bodyweight": load_pct_bodyweight,
                "load_basis": "per hand" if is_one_sided else "total load carried",
                "rest_seconds": 90,
            }

        if category in {"Core", "Grip"}:
            # The genuine holds (Isometric/Hang) are already routed away
            # above - what reaches this branch is the dynamic Core/Grip
            # work (Anti-Extension, Flexion, Rotational, Lateral, Rotation,
            # Anti-Rotation: GHD Sit-Up, Hanging Knee Raise, Captain's
            # Chair Leg Raise, Ab Wheel Rollout, Landmine Rotation, Cable
            # Pallof Press, Medicine Ball Russian Twist, Decline Sit-Up,
            # etc.). Every one of those used to get forced into a timed
            # hold too ("hold a GHD Sit-Up for 35 seconds" isn't a real
            # exercise) purely because it shared a category with the
            # actual planks and dead hangs. These are reps-based bodyweight/
            # light-resistance work - no barbell 1RM to reference, same as
            # the bodyweight-strength branch above, but with the higher rep
            # range the reference guide's Isolation/accessory row uses
            # (10-20 reps) rather than a big-compound-lift rep count.
            reps = max(8, 20 - difficulty * 2)
            return {
                # Kept as "strength_bodyweight" (not a new type) so
                # _apply_week_progression's existing strength_bodyweight
                # branch (add a rep each week) still applies to this work.
                "type": "strength_bodyweight",
                # BUGFIX (goal selection was corrupting Core/Grip numbers):
                # this shares its "strength_bodyweight" type with genuine
                # weighted bodyweight-skill work (Pull-Ups, Dips, Pistol
                # Squats), which program_builder._apply_prescription_bias
                # deliberately remaps onto the selected goal's Power/
                # Strength/Hypertrophy window - correct for a skill lift,
                # but it was ALSO catching this branch's dynamic Core/Grip
                # output (GHD Sit-Up, Hanging Knee Raise, Ab Wheel Rollout,
                # Cable Pallof Press, Landmine Rotation, farmer's-grip work,
                # etc.), collapsing the 8-20 rep bracing/anti-rotation range
                # computed just above into a barbell-lift-style 1-6 rep
                # "power"/"strength" prescription the moment any goal was
                # selected - nobody programs a hanging knee raise for 2
                # reps at "explosive" intent. This "accessory" flag lets
                # _apply_prescription_bias recognize and skip this specific
                # prescription while genuine bodyweight-strength skills keep
                # remapping normally.
                "accessory": True,
                "sets": sets,
                "reps": reps,
                "rest_seconds": 75,
            }

        # Sport specific / throws / strikes / complexes - technical quality over fatigue
        reps = max(4, 10 - difficulty)
        return {"type": "technical", "sets": sets, "reps": reps, "rest_seconds": 120}

    # How close to the top score a candidate has to be to count as "also a
    # reasonable pick" for rotation purposes. 12% keeps rotation among
    # exercises a coach would genuinely consider interchangeable - it won't
    # swap a clearly-best lift for a clearly-worse one just for variety.
    _VARIETY_BAND = 0.12

    # A percentage band alone fails whenever the *pool itself* is thin (e.g.
    # Bodyweight-only equipment, or an Advanced/Elite level with few
    # exercises tagged at that level - see level_fit_multiplier above). In
    # that situation the single top-scoring exercise can legitimately clear
    # every other candidate by 20-40%+ even though a coach would still
    # freely rotate through the next few options rather than run the exact
    # same movement every single session forever (the reported bug: an
    # Advanced Bodyweight-only Boxing athlete's "Power & Explosive" slot
    # always resolved to Clap Push-Up - 75 - because every bodyweight jump
    # variant landed in the 29-49 range once the below-level penalty was
    # applied, well outside the 12% band). _VARIETY_MIN_POOL guarantees at
    # least this many candidates are eligible for rotation (score order,
    # topped up past the percentage band if needed) whenever that many
    # actually exist, so a thin-but-not-empty pool still rotates instead of
    # calcifying on one exercise. It never overrides the absolute quality
    # floor callers already apply upstream (_ROLE_FILL_ABS_FLOOR /
    # role_floor) - this only widens *which already-qualified* candidates
    # are treated as "close enough to rotate among", not which ones qualify
    # to be candidates in the first place.
    # 3 was the first value tried here and it under-shoots for a 4x/week
    # program: with only 3 candidates ever eligible for rotation, a 4-day
    # week exhausts all 3 as "recently used" by day 3, so day 4 falls back
    # to the unrestricted tied pool again and can still land back on the
    # same top exercise by chance (confirmed empirically - Clap Push-Up
    # still won 15/16 sessions in a 4-day/week x 4-week program with
    # _VARIETY_MIN_POOL=3, because rotation had nothing left to rotate
    # into partway through almost every week). 5 keeps at least a week's
    # worth of genuinely distinct options in play before recency exclusion
    # has to start reusing anything.
    _VARIETY_MIN_POOL = 5

    # _select_role_balanced used to force *something* into every role slot
    # in ROLE_ORDER as long as anything at all qualified for it - even the
    # single worst-scoring exercise in the entire session. In practice this
    # surfaced worst when equipment/sport combinations left a role with only
    # one thin, badly-matched candidate: e.g. a bodyweight-only Judo session
    # has no grappling-relevant Conditioning finisher, so the engine forced
    # in "Shadow Boxing Rounds" (a Boxing-specific striking drill, authored
    # sport_priority 40/Judo, blended score ~25) ahead of exercises the same
    # session had already picked at 55-75 - a real coach would rather run a
    # second strength/accessory set than bolt on an off-discipline drill
    # just to fill a role checkbox. A role now only gets force-filled if its
    # best candidate actually clears a quality bar (an absolute floor, and a
    # floor relative to the best score anywhere else in this same session);
    # otherwise that slot is left to the normal score-ranked backfill below,
    # which pulls from every role's leftovers - so the seat still gets
    # filled, just with whatever is genuinely the next-best exercise for
    # this person's sport/equipment/level, not the weakest thing that
    # happened to be the only option in one specific role bucket.
    _ROLE_FILL_ABS_FLOOR = 30
    _ROLE_FILL_RELATIVE_FLOOR = 0.5

    @classmethod
    def _pick_with_variety(
        cls, candidates: List[Dict], recent_ids: set, rng: random.Random,
        recent_families: Optional[set] = None,
    ) -> Dict:
        """Picks one exercise from a role's score-sorted candidate list.

        Previously this was always candidates[0] - deterministic, so calling
        the engine again with the same filters (same sport/equipment/
        injuries/level) always returned the exact same exercise. That's
        correct for a single session, but it's *why* multi-week programs
        (program_builder.py calls this once per week per day-type with
        identical filters) came back with the same "Full Body A" exercises
        in week 4 as week 1 - there was never any mechanism that could
        produce a different answer.

        Fix: find every candidate within _VARIETY_BAND of the top score
        (the pool a coach would genuinely call "interchangeable" for this
        slot), prefer ones NOT in `recent_ids` (what the last call already
        used), and choose among those with a seeded RNG so the same seed
        always reproduces the same pick (deterministic per call, varied
        across calls) rather than picking randomly every single time.

        The percentage band alone can still collapse to a single candidate
        when the pool is thin and the score gap is unusually wide (see
        _VARIETY_MIN_POOL above) - when that happens, top up the tied pool
        with the next best-scoring candidates (already quality-gated by the
        caller) until it hits _VARIETY_MIN_POOL or the candidate list is
        exhausted, so a thin pool still rotates instead of locking onto one
        exercise for the rest of the program.

        BUG FIXED: `recent_ids` only ever excluded the *exact same exercise
        ID*, so a thin-but-not-empty pool of near-duplicate movements (e.g.
        the 8 "High Pull" variants in Hinge - Clean/Snatch/Hang/Rack-Pull/
        Kettlebell/Mid-Thigh, all scored 60-80 for Judo) still rotated
        freely among *themselves* - a coach never sees this as "variety",
        just the same drill under a different name 4 days in a row. Every
        exercise now carries a `movement_family` tag (the same base
        movement across equipment/tempo/stance variants - see
        exercises.json's schema_notes). `recent_families` is the set of
        families used by the id's already excluded via `recent_ids` (see
        generate_session/_select_role_balanced for how callers build it).
        Preference order is now three-tiered: (1) fresh id AND fresh
        family, (2) fresh id but same family as something recent (better
        than an outright repeat, so still preferred over group 3), (3) the
        full tied pool. This only ever *prefers* a different family when
        one is genuinely available at a comparable score - it never hard-
        excludes same-family candidates, so a thin pool (e.g. a sport/
        equipment match where only one family clears the quality floor)
        still fills the slot instead of coming back empty.
        """
        if not candidates:
            return None
        recent_families = recent_families or set()
        top_score = candidates[0]["sport_priority_score"]
        floor = top_score * (1 - cls._VARIETY_BAND)
        tied = [c for c in candidates if c["sport_priority_score"] >= floor]
        if len(tied) < min(cls._VARIETY_MIN_POOL, len(candidates)):
            tied_ids = {c["id"] for c in tied}
            for c in candidates:  # already sorted by score, descending
                if len(tied) >= cls._VARIETY_MIN_POOL:
                    break
                if c["id"] not in tied_ids:
                    tied.append(c)
                    tied_ids.add(c["id"])

        # CLASSIC-LIFT BIAS (reported bug: a tied score band routinely
        # handed back a one-off barbell/equipment trick - Board Press,
        # Spoto Press, Larsen Press, Guillotine Press, ... - with equal
        # odds to the plain lift, because sport_priority_score alone
        # doesn't distinguish "the classic movement" from "a named
        # specialty variation of it": Board Press and Flat Bench Press
        # score identically for most sports. Every batch-generated
        # specialty variation got its own singleton `movement_family`
        # (e.g. "horizontal_push__board_press", exactly 1 member),
        # while the plain lift and its ordinary angle/grip/equipment
        # variants share one large family (e.g. "horizontal_push__press",
        # 12 members: Flat/Incline/Decline/Dumbbell Bench Press, ...).
        # Family size within the candidate pool is therefore a reliable,
        # self-maintaining signal for "is this the classic pattern" -
        # no hand-curated exercise-name list to maintain. Among the
        # score-tied pool, narrow to whichever family is best-represented
        # before applying the existing recency/variety logic below, so a
        # session still rotates between Flat/Incline/Decline Bench Press
        # week to week but essentially never surfaces Board Press while a
        # classic alternative is tied on score. Falls back to the full
        # tied pool untouched when nothing in it belongs to a multi-member
        # family (every tied candidate is itself a one-off variation) -
        # a thin pool where a niche variation is genuinely the only fit
        # still fills the slot instead of coming back empty.
        def _family_key(c: Dict) -> str:
            fam = c.get("movement_family")
            return fam if fam else c["id"]  # untagged exercises never "share" a family

        family_counts = Counter(_family_key(c) for c in candidates)
        max_family_size = max((family_counts[_family_key(c)] for c in tied), default=0)
        classic_tied = (
            [c for c in tied if family_counts[_family_key(c)] == max_family_size]
            if max_family_size > 1 else tied
        )
        pool_for_recency = classic_tied or tied

        fresh = [c for c in pool_for_recency if c["id"] not in recent_ids]
        fresh_family = [
            c for c in fresh if c.get("movement_family") not in recent_families
        ]
        pool = fresh_family or fresh or pool_for_recency
        return rng.choice(pool)

    # How many exercises of the same `category` (movement-pattern family -
    # Horizontal Push, Full Body, Vertical Pull, etc.) the backfill loop
    # below will stack into one session before it starts avoiding that
    # category. The one-per-role pass already guarantees the 7 role slots
    # get filled with genuinely different job assignments; without this
    # cap, any *extra* slots beyond that (a longer session, or a role that
    # got skipped by the quality floor above) were filled purely by raw
    # score across the whole remaining pool, which could - and did -
    # stack multiple near-identical high-scoring movements into one
    # session (e.g. three separate explosive kettlebell drills: Windmill,
    # Flip, and Tactical Juggle, all "Full Body"/ballistic, while the
    # session had zero squat, hinge, or horizontal-push work). 2 keeps
    # legitimate intentional pairs (a primary bench press + a secondary
    # incline press both being "Horizontal Push" is completely normal
    # programming) while stopping a third and beyond from crowding out
    # other movement patterns the session is otherwise missing entirely.
    _BACKFILL_MAX_PER_CATEGORY = 2

    # `programming_role` groups exercises by the JOB they do in a session
    # (Primary Strength, Accessory, ...), not by WHICH movement pattern they
    # train - and the one-per-role pass above only ever takes a single
    # "Primary Strength" pick and a single "Accessory / Hypertrophy" pick
    # across all six loaded-strength categories combined (Squat, Hinge,
    # Horizontal Push, Horizontal Pull, Vertical Push, Vertical Pull). That's
    # how a real session could satisfy every role slot and still come back
    # with two squat variations and zero hinge work, or all pressing and no
    # pulling, while "Power & Explosive" quietly went to a single jump/throw
    # and nothing else. A coach programming for ANY sport - grappling,
    # striking, field sport, whatever - reaches for a vertical push AND
    # pull, a horizontal push AND pull, a hinge, a squat pattern, a loaded
    # carry, and an explosive/ballistic movement (jump, Olympic-lift
    # variant, medball throw) before calling a session balanced. This list
    # is what the coverage pass right after role-selection tops up, one
    # pattern at a time, only when a session's target_categories/limit
    # actually leaves room for it and a genuinely qualified candidate
    # exists - it never forces in a bad exercise just to check a box (same
    # _ROLE_FILL floor as everything else), and WHICH exercise wins each
    # pattern is still whatever scores highest for this person's specific
    # sport, since sport_priority_score already bakes in that sport's own
    # movement-pattern emphasis (sport_profiles.movement_emphasis_multiplier).
    # "Carry" is included alongside the other six loaded-strength patterns
    # because the manual itself names it as one of the five foundational
    # compound patterns ("Squat, hinge, press, pull, carry patterns give you
    # the most strength and durability per minute" - see the equipment/
    # movement priority note in sport_profiles.py) - without a guaranteed
    # slot, Carry only ever competed in the generic score-only backfill
    # below and regularly lost out to higher-scoring Pull/Grip work for
    # grappling sports, so a session's carry work (including the Dumbbell/
    # Kettlebell farmer-carry-family substitutes for anyone without
    # dedicated Farmer Handles) was often dropped entirely rather than
    # swapped to what equipment the person actually has.
    # Order matters here: interleaved lower/upper, push/pull rather than
    # grouped (all lower-body patterns first) so that even a short session
    # whose slot budget can't fit all nine still comes away with a spread
    # across the body instead of front-loading e.g. Squat+Hinge and running
    # out of room before an upper-body pull or push ever gets picked.
    #
    # BUG FIXED: this fixed order put Vertical Pull (position 3) well ahead
    # of Horizontal Pull (position 7). Most real sessions (a typical 45-70
    # min session, exercise_limit ~5-7) don't have room for all 9 patterns
    # after the structural-role pass (Power/Core/Conditioning/Skill/Primer)
    # already claimed a few slots - so whichever pattern sits earlier in
    # this list wins almost every single session, session after session,
    # for the whole mesocycle. In practice that meant pull-ups (Vertical
    # Pull) got picked in essentially every session while rows (Horizontal
    # Pull) barely ever made the cut - not a scoring difference, just fixed
    # list position starving whatever comes later whenever both compete for
    # the same last slot. Same risk existed between Horizontal Push and
    # Vertical Push. Fix: alternate between this order and its push/pull-
    # swapped twin (_COVERAGE_PATTERNS_ALT) by variety_seed parity, so
    # across a program roughly half the sessions prioritize
    # horizontal-pull-before-vertical-pull (and horizontal-push-before-
    # vertical-push) and half do the reverse - long-run exposure balances
    # out instead of one pattern in each pair permanently starving the
    # other, while a single session still gets the same interleaved
    # lower/upper spread as before.
    _COVERAGE_PATTERNS = [
        "Squat", "Horizontal Push", "Vertical Pull",
        "Hinge", "Carry", "Vertical Push", "Horizontal Pull",
        "Power", "Jump",
    ]
    _COVERAGE_PATTERNS_ALT = [
        "Squat", "Vertical Push", "Horizontal Pull",
        "Hinge", "Carry", "Horizontal Push", "Vertical Pull",
        "Power", "Jump",
    ]

    # Roles handled by the per-role pass below, in ROLE_ORDER's coaching
    # sequence, MINUS Primary Strength / Secondary Strength / Accessory -
    # those three all draw from the same six loaded-strength categories the
    # coverage pass now owns (see _COVERAGE_PATTERNS), and picking just one
    # exercise per role from that combined bucket is exactly what let a
    # session end up all-squat-no-hinge or all-press-no-pull despite
    # "filling" every role slot. The coverage pass below replaces that job
    # with per-pattern picks; anything it doesn't use still gets a fair shot
    # in the generic backfill afterwards (still labeled Primary/Secondary
    # Strength/Accessory per its own difficulty tier, still capped by
    # _BACKFILL_MAX_PER_CATEGORY), so no candidate is actually excluded -
    # just no longer limited to one combined pick before pattern coverage
    # has had its turn.
    _STRUCTURAL_ROLES = [
        r for r in ROLE_ORDER
        if r not in ("Primary Strength", "Secondary Strength", "Accessory / Hypertrophy")
    ]

    @classmethod
    def _select_role_balanced(
        cls,
        prescribed_exercises: List[Dict],
        limit: int,
        recent_exercise_ids: Optional[set] = None,
        variety_seed: int = 0,
        recent_exercise_families: Optional[set] = None,
    ) -> List[Dict]:
        """Trims a qualifying-exercise pool to `limit` while keeping role
        variety instead of just keeping the first N by score - a session
        capped at 6 exercises should still look like a session (something
        primary, something accessory, something conditioning) rather than
        6 near-duplicate accessory movements that happened to score highest.

        Also rotates among near-tied top candidates per role (see
        `_pick_with_variety`) so the same request run again - or the same
        day-slot run again next week in a program - doesn't mechanically
        return the identical exercise list every time.

        `recent_exercise_families` (see generate_session for how it's built
        from recent_exercise_ids via movement_family) is threaded into
        every `_pick_with_variety` call below, unioned with the families
        already picked *this session* (`selected_families`) - same pattern
        as `selected_ids` unioning with `recent_exercise_ids` - so a
        near-duplicate movement (e.g. a second "High Pull" variant) is only
        picked again once no genuinely different family clears the floor.
        """
        recent_exercise_ids = recent_exercise_ids or set()
        recent_exercise_families = recent_exercise_families or set()
        rng = random.Random(variety_seed)

        by_role: Dict[str, List[Dict]] = {}
        for ex in prescribed_exercises:
            by_role.setdefault(ex["programming_role"], []).append(ex)
        for role_list in by_role.values():
            role_list.sort(key=lambda x: -x["sport_priority_score"])

        # The floor a role's best candidate has to clear to be worth forcing
        # into the session at all - see the class docstring above. Relative
        # to this session's own top score, so a request where nothing
        # scores especially high (a thin sport/equipment match overall)
        # doesn't get every role wiped out - only a role whose best option
        # is genuinely an outlier-bad pick next to what the rest of the
        # session already found.
        session_top_score = max(
            (ex["sport_priority_score"] for ex in prescribed_exercises), default=0
        )
        role_floor = max(cls._ROLE_FILL_ABS_FLOOR, session_top_score * cls._ROLE_FILL_RELATIVE_FLOOR)

        selected: List[Dict] = []
        selected_ids = set()
        selected_families: set = set()
        category_counts: Dict[str, int] = {}
        for role in cls._STRUCTURAL_ROLES:
            candidates = by_role.get(role, [])
            if candidates and len(selected) < limit and candidates[0]["sport_priority_score"] >= role_floor:
                pick = cls._pick_with_variety(
                    candidates, recent_exercise_ids, rng,
                    recent_families=recent_exercise_families | selected_families,
                )
                selected.append(pick)
                selected_ids.add(pick["id"])
                selected_families.add(pick.get("movement_family"))
                category_counts[pick.get("category")] = category_counts.get(pick.get("category"), 0) + 1

        # Movement-pattern coverage pass - see _COVERAGE_PATTERNS docstring
        # above. Runs after the one-per-role pass (which already grabbed
        # whatever it found for Primary Strength/Accessory/Power & Explosive)
        # and before the generic score-only backfill, so any of the eight
        # fundamental patterns that role-selection happened to skip still
        # gets a genuine shot at a session slot - grouped by the exercise's
        # own `category` field, same quality floor, same recency-aware
        # variety pick as every other selection in this method.
        by_category: Dict[str, List[Dict]] = {}
        for ex in prescribed_exercises:
            by_category.setdefault(ex.get("category"), []).append(ex)
        for cat_list in by_category.values():
            cat_list.sort(key=lambda x: -x["sport_priority_score"])

        for pattern in (cls._COVERAGE_PATTERNS if variety_seed % 2 == 0 else cls._COVERAGE_PATTERNS_ALT):
            if len(selected) >= limit:
                break
            if category_counts.get(pattern, 0) > 0:
                continue  # already represented by the role pass above
            candidates = [c for c in by_category.get(pattern, []) if c["id"] not in selected_ids]
            if candidates and candidates[0]["sport_priority_score"] >= role_floor:
                pick = cls._pick_with_variety(
                    candidates, recent_exercise_ids, rng,
                    recent_families=recent_exercise_families | selected_families,
                )
                selected.append(pick)
                selected_ids.add(pick["id"])
                selected_families.add(pick.get("movement_family"))
                category_counts[pattern] = category_counts.get(pattern, 0) + 1

        remaining = [ex for ex in prescribed_exercises if ex["id"] not in selected_ids]
        remaining.sort(key=lambda x: -x["sport_priority_score"])
        # Fill the rest with the same recency-aware rotation, one slot at a
        # time (so each pick can react to what the previous pick already
        # used) - now also preferring categories that aren't already
        # stacked up, per _BACKFILL_MAX_PER_CATEGORY above.
        while remaining and len(selected) < limit:
            under_cap = [
                ex for ex in remaining
                if category_counts.get(ex.get("category"), 0) < cls._BACKFILL_MAX_PER_CATEGORY
            ]
            pool = under_cap if under_cap else remaining
            pick = cls._pick_with_variety(
                pool, recent_exercise_ids | selected_ids, rng,
                recent_families=recent_exercise_families | selected_families,
            )
            selected.append(pick)
            selected_ids.add(pick["id"])
            selected_families.add(pick.get("movement_family"))
            category_counts[pick.get("category")] = category_counts.get(pick.get("category"), 0) + 1
            remaining = [ex for ex in remaining if ex["id"] != pick["id"]]

        return selected

    # Standalone single-session shape (not the Program Builder, which still
    # uses _select_role_balanced above to fill a whole split day against
    # target_categories/target_muscles): a plain "generate me a workout"
    # request isn't trying to cover every role a full training block would,
    # but it DOES need to look and feel like the sport it was generated
    # for, not a generic strength template that happens to have sport-
    # scored exercises plugged into it.
    #
    # BUG FIXED (v5.22): this method only ever pulled from Primary
    # Strength / Accessory / Conditioning. Skill/Technical and Power &
    # Explosive - the two roles that actually carry sport IDENTITY (a
    # Judo grip drill, a Wrestling sprawl-to-sprint, a reactive jump) -
    # were never selected at all in single-session mode, only in the
    # Program Builder's per-day path. Concretely: a Judo session and a
    # Wrestling session, both generated with identical equipment/biometrics,
    # came back as near-identical generic strength templates (Zercher
    # Squat, Meadows Row, an RDL) with zero grip work, zero reactive/
    # explosive work, zero sport-specific drills - exactly the "not
    # actually sport-specific" gap. Fixed by adding a small,
    # duration-gated sport-identity slot (skill_count/power_count below)
    # that Primary Strength/Accessory can no longer crowd out, since it's
    # filled FIRST, before the compound lifts, not backfilled after.
    #
    # Defaults only - the real per-duration counts now come from
    # _session_composition() (program_builder.py), which scales
    # compound/skill/power/secondary AND accessory/finisher against the
    # full 30/45/60/75/90/120/150-minute ladder. These two stay as
    # fallbacks for any caller that invokes _select_compound_accessory_finisher
    # without passing accessory_count/finisher_count explicitly.
    _SINGLE_SESSION_ACCESSORY_COUNT = 2
    _SINGLE_SESSION_FINISHER_COUNT = 1

    @classmethod
    def _select_compound_accessory_finisher(
        cls,
        prescribed_exercises: List[Dict],
        compound_count: int,
        recent_exercise_ids: Optional[set] = None,
        variety_seed: int = 0,
        recent_exercise_families: Optional[set] = None,
        skill_count: int = 0,
        power_count: int = 0,
        secondary_count: int = 0,
        accessory_count: Optional[int] = None,
        finisher_count: Optional[int] = None,
    ) -> List[Dict]:
        """Composes a plain single session as sport-identity work (skill +
        power) + compounds + accessories + a finisher, instead of the
        Program Builder's one-per-role-plus-pattern-coverage fill (see
        _select_role_balanced). Falls back to the closest available role,
        then to the next-best exercise overall, whenever a bucket comes up
        short (e.g. an all-bodyweight equipment list with nothing that
        qualifies as "Primary Strength"), so a thin match still returns a
        real session instead of 2-3 exercises total.

        `skill_count`/`power_count` are the sport-identity slots (see the
        class-level comment above this method for why they exist) - 0 for
        either is a legitimate value (e.g. a sport/equipment combo with no
        qualifying Skill/Technical exercise at all), handled the same way
        an empty Primary Strength bucket already is: `take()` is a no-op
        on an empty candidate list, and the shortfall backfill below fills
        the gap from whatever else qualified.

        `secondary_count` (v5.23) is the Secondary Strength slot count - a
        second, still genuinely-loaded compound lift one difficulty notch
        below Primary Strength (see programming_role.py's three-tier split).
        0 is legitimate (a short session with no room for a second big
        lift), handled the same no-op-then-backfill way as every other
        count here.

        `recent_exercise_families` is threaded the same way as in
        `_select_role_balanced` - see that docstring.

        `accessory_count`/`finisher_count` default to the class constants
        (_SINGLE_SESSION_ACCESSORY_COUNT/_SINGLE_SESSION_FINISHER_COUNT)
        when not passed - callers that want the full duration-aware ladder
        (see _session_composition in program_builder.py) pass them
        explicitly instead."""
        recent_exercise_ids = recent_exercise_ids or set()
        recent_exercise_families = recent_exercise_families or set()
        accessory_count = cls._SINGLE_SESSION_ACCESSORY_COUNT if accessory_count is None else accessory_count
        finisher_count = cls._SINGLE_SESSION_FINISHER_COUNT if finisher_count is None else finisher_count
        rng = random.Random(variety_seed)

        by_role: Dict[str, List[Dict]] = {}
        for ex in prescribed_exercises:
            by_role.setdefault(ex["programming_role"], []).append(ex)
        for role_list in by_role.values():
            role_list.sort(key=lambda x: -x["sport_priority_score"])

        selected: List[Dict] = []
        selected_ids: set = set()
        selected_families: set = set()
        # Tracks how many already-picked exercises share each `category`
        # (Squat, Hinge, Vertical Push, ...) - not just each `role` - so
        # take() below can cap repeats per category the same way the
        # generic backfill loop does (_BACKFILL_MAX_PER_CATEGORY). Without
        # this, "Primary Strength" picks the top N candidates by score
        # with no regard for category: with a large, varied candidate pool
        # that rarely showed, but a thin pool (e.g. manual_only=True, ~96
        # exercises instead of 761) reliably collapses into e.g. 3
        # Vertical Push exercises as "your main lifts" for a session,
        # because Squat/Hinge for that sport/equipment/biometric
        # combination scored lower or had nothing qualify at all.
        category_counts: Dict[str, int] = {}

        def take(role: str, count: int, diversify: bool = False):
            candidates = [c for c in by_role.get(role, []) if c["id"] not in selected_ids]
            for _ in range(count):
                if not candidates:
                    break
                if diversify:
                    under_cap = [
                        c for c in candidates
                        if category_counts.get(c.get("category"), 0) < cls._BACKFILL_MAX_PER_CATEGORY
                    ]
                    pool = under_cap if under_cap else candidates
                else:
                    pool = candidates
                pick = cls._pick_with_variety(
                    pool, recent_exercise_ids | selected_ids, rng,
                    recent_families=recent_exercise_families | selected_families,
                )
                if pick is None:
                    break
                selected.append(pick)
                selected_ids.add(pick["id"])
                selected_families.add(pick.get("movement_family"))
                category_counts[pick.get("category")] = category_counts.get(pick.get("category"), 0) + 1
                candidates = [c for c in candidates if c["id"] != pick["id"]]

        # Skill/Technical and Power & Explosive go FIRST, not last - these
        # are the sport-identity slots (see class-level comment above this
        # method), and filling them before the compound lifts means they
        # can't get crowded out the way a backfill-only approach would let
        # happen. Left undiversified (category variety inside a 0-1 pick
        # doesn't mean anything); a genuine miss (0 qualifying candidates
        # for the sport/equipment combo) is a legitimate no-op here, same
        # as an empty Primary Strength bucket already was.
        take("Skill / Technical", skill_count)
        take("Power & Explosive", power_count)

        # Primary Strength, Secondary Strength, and Accessory all diversify
        # by category (a session's "main lifts" should span movement
        # patterns, not repeat one); Conditioning/Finisher is left
        # undiversified since it's capped at _SINGLE_SESSION_FINISHER_COUNT=1
        # anyway. Secondary Strength is taken right after Primary Strength,
        # before Accessory - a coach's "second big lift" still comes before
        # the lighter accessory work, not after it.
        take("Primary Strength", compound_count, diversify=True)
        take("Secondary Strength", secondary_count, diversify=True)
        take("Accessory / Hypertrophy", accessory_count, diversify=True)
        take("Conditioning / Finisher", finisher_count)

        target_total = (
            skill_count + power_count + compound_count + secondary_count
            + accessory_count + finisher_count
        )
        if len(selected) < target_total:
            # A bucket came up short (thin equipment/sport match) - fill the
            # remaining slots from whatever else qualified, best score first,
            # rather than handing back a shorter-than-requested session.
            # Same category cap applied here for the same reason as above.
            remaining = [ex for ex in prescribed_exercises if ex["id"] not in selected_ids]
            remaining.sort(key=lambda x: -x["sport_priority_score"])
            while remaining and len(selected) < target_total:
                under_cap = [
                    ex for ex in remaining
                    if category_counts.get(ex.get("category"), 0) < cls._BACKFILL_MAX_PER_CATEGORY
                ]
                pool = under_cap if under_cap else remaining
                pick = cls._pick_with_variety(
                    pool, recent_exercise_ids | selected_ids, rng,
                    recent_families=recent_exercise_families | selected_families,
                )
                if pick is None:
                    break
                selected.append(pick)
                selected_ids.add(pick["id"])
                selected_families.add(pick.get("movement_family"))
                category_counts[pick.get("category")] = category_counts.get(pick.get("category"), 0) + 1
                remaining = [ex for ex in remaining if ex["id"] != pick["id"]]

        return selected

    @staticmethod
    def _resolve_injury_severity(user_injuries: set) -> Dict[str, int]:
        """Turn the user's selected injury strings into a {joint: worst_severity} map
        using INJURY_TAXONOMY. If someone has two flagged injuries on the same joint
        (unlikely but possible), the more severe one wins - a joint is only ever as
        safe as its worst injury. Strings that don't match a taxonomy entry (e.g. a
        raw joint name like "Knee", or a legacy flat tag like "Tennis Elbow" typed
        exactly as it appears in injuries_to_avoid) are simply skipped here and left
        for the existing literal-tag contraindication check further down, so nothing
        that worked before this taxonomy existed stops working now."""
        taxonomy_lower = {name.lower(): info for name, info in INJURY_TAXONOMY.items()}
        joint_severity: Dict[str, int] = {}
        for inj in user_injuries:
            entry = taxonomy_lower.get(inj)
            if entry is None:
                continue
            joint = entry["joint"]
            severity = entry["severity"]
            joint_severity[joint] = max(joint_severity.get(joint, 0), severity)
        return joint_severity

    @staticmethod
    def _resolve_injury_tissue(user_injuries: set) -> Dict[str, str]:
        """Companion to _resolve_injury_severity (v5.12): {joint: tissue} for
        the same worst-severity-per-joint taxonomy matches, so the demand-
        aware risk check (injury_taxonomy.TISSUE_DEMAND_SENSITIVITY) knows
        which tissue type's sensitivities to weigh, not just how severe the
        injury is. Kept as a separate method rather than changing
        _resolve_injury_severity's return shape, so that method and its
        existing caller in routes.py are untouched."""
        taxonomy_lower = {name.lower(): info for name, info in INJURY_TAXONOMY.items()}
        joint_severity: Dict[str, int] = {}
        joint_tissue: Dict[str, str] = {}
        for inj in user_injuries:
            entry = taxonomy_lower.get(inj)
            if entry is None:
                continue
            joint = entry["joint"]
            severity = entry["severity"]
            if severity >= joint_severity.get(joint, 0):
                joint_severity[joint] = severity
                joint_tissue[joint] = entry.get("tissue")
        return joint_tissue

    @staticmethod
    def _resolve_injury_stage(user_injuries: set, injury_stages: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Companion to _resolve_injury_severity/_resolve_injury_tissue
        (v5.14): {joint: rehab_stage} for whichever of the user's matched
        injuries they also gave an explicit rehab stage for (via
        WorkoutRequest.injury_stages, keyed by the same injury string as
        `injuries`, case-insensitive).

        Deliberately NOT defaulted per-joint here - a joint with no
        explicit stage in `injury_stages` gets left out of the returned
        dict, so `.get(joint)` on it returns None and classify_injury_risk
        is called with stage=None for that joint, reproducing the exact
        pre-v5.14 severity-only behavior. Only once the person actually
        tells FORGE what stage they're in does the extra stage-based
        gating (injury_taxonomy.REHAB_STAGE_BLOCKED_AXES) kick in for that
        joint. The worst-severity injury on a joint still decides which
        taxonomy entry's stage applies, matching the other two resolvers."""
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
            joint = entry["joint"]
            severity = entry["severity"]
            if severity >= joint_severity.get(joint, 0):
                joint_severity[joint] = severity
                joint_stage[joint] = stage
        return joint_stage

    @staticmethod
    def _resolve_injury_side(user_injuries: set, injury_sides: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Companion to _resolve_injury_severity/_resolve_injury_tissue/
        _resolve_injury_stage (v5.15): {joint: side} for whichever of the
        user's matched injuries they also gave a side for (via
        WorkoutRequest.injury_sides, keyed the same way as `injuries`,
        case-insensitive). Values other than "left"/"right"/"bilateral" are
        ignored, same as an unrecognized rehab_stage is in
        _resolve_injury_stage.

        Deliberately NOT defaulted per-joint - a joint with no side given
        gets left out of the returned dict, so `.get(joint)` returns None
        and classify_injury_risk's laterality relaxation never fires for
        it, reproducing the exact pre-v5.15 (always-bilateral) behavior.

        When two matched injuries land on the same joint with different
        sides (e.g. a left knee sprain and a separate right knee sprain),
        the combined result is "bilateral" - loading is restricted on both
        sides, so no side can be assumed clear, regardless of which of the
        two injuries is more severe."""
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
            if side not in INJURY_SIDES:
                continue
            # v5.19 - a side only means something for a paired limb
            # structure (muscle/ligament/tendon), never the spine (Neck/
            # Lower Back) - see injury_taxonomy.laterality_applicable. A
            # stale UI or a hand-built request can't smuggle a one-sided
            # relaxation onto a spine injury this way.
            if not laterality_applicable(entry):
                continue
            joint = entry["joint"]
            if joint not in joint_side:
                joint_side[joint] = side
            elif joint_side[joint] != side:
                joint_side[joint] = "bilateral"
        return joint_side

    def generate_session(
        self,
        request: WorkoutRequest,
        athlete_id: Optional[str] = None,
        db: Optional[Session] = None,
        training_phase: Optional[str] = None,
        expected_days_per_week: Optional[int] = None,
    ):
        # Phase 5 (roadmap): personalize ranking from the athlete's own
        # logged history, not just static sport/equipment/injury/level
        # scoring. Both athlete_id and db must be supplied (routes.py only
        # passes them for a logged-in caller - see auth_service.get_current_user_optional)
        # and there must be enough logged history to say anything - see
        # recommendation_engine.MIN_SESSIONS_FOR_SIGNAL. Anonymous callers
        # and accounts with little/no history get history_signals={},
        # which makes personalization_multiplier() a no-op (1.0, None) for
        # every exercise below - identical scoring/output to before this
        # existed.
        history_signals = (
            build_history_signals(db, athlete_id, sport=request.sport)
            if athlete_id and db is not None
            else {}
        )

        # Recovery/fatigue: with no readiness_inputs this is exactly the old flat
        # slider behavior (see _compute_recovery docstring for why that's safe).
        # Computed here, BEFORE the adaptive-load call below, so the adaptive
        # engine can be told whether readiness/soreness (which itself already
        # reflects program_builder's calendar-forced deload week - it clamps
        # readiness to <=35 for that week, see generate_program) has already
        # put this session into deload_mode. This ordering fix is what closes
        # the "four uncoordinated deload signals" gap flagged in the roadmap:
        # previously this block ran AFTER the adaptive-load call, so a
        # progressing-trend/plateau-busting nudge (which can push
        # intensity/volume ABOVE baseline - see the plateau/progressing
        # branches below) had no way to know a calendar deload week or a
        # 5/5 soreness/low-readiness entry had already put the session into
        # deload_mode, and could partially undo that deload. See
        # compute_adaptive_load_adjustment's new `forced_deload` parameter.
        recovery = self._compute_recovery(request.readiness, request.readiness_inputs)
        effective_readiness = recovery["score"]
        poor_sleep = recovery["poor_sleep"]
        # Below 40% effective readiness (or a stand-alone 5/5 soreness report, which
        # a merely-averaged composite could otherwise mask) the session auto-switches
        # to a deload: shorter, lighter, capped at moderate difficulty. This used to
        # just multiply intensity by readiness with no floor or ceiling, which could
        # still hand out max-effort barbell work at 5% readiness.
        max_soreness = bool(request.readiness_inputs and request.readiness_inputs.soreness == 5)
        pre_adaptive_deload_mode = effective_readiness < 40 or max_soreness

        # Adaptive load/volume adjustment: a whole-session (not per-exercise)
        # read of the athlete's actual recent training - session RPE trend,
        # logged weekly set volume, missed-session gaps, and the aggregate
        # progressing/plateau read above - layered on top of today's
        # readiness. Same gating as history_signals: no athlete_id/db, or
        # not enough logged history yet, and this is a complete no-op
        # (both multipliers 1.0) - see compute_adaptive_load_adjustment's
        # docstring. `training_phase`/`expected_days_per_week` are plain
        # Python kwargs (not part of WorkoutRequest) that program_builder.
        # generate_program threads through from the enclosing ProgramRequest;
        # a standalone /generate-workout call simply omits them and the
        # missed-session check falls back to the athlete's own historical
        # cadence instead of a program's stated days_per_week. `forced_deload`
        # tells the adaptive engine this specific session is already going
        # into deload_mode for a reason it has no visibility into (readiness
        # slider, soreness report, or - via program_builder's readiness
        # clamp - a calendar deload week) so it caps itself at "never push
        # harder than baseline" the same way a Fight Week phase already does,
        # instead of a progressing-trend nudge fighting the deload.
        adaptive_load = (
            compute_adaptive_load_adjustment(
                db, athlete_id, sport=request.sport, exercise_signals=history_signals,
                training_emphasis=request.training_emphasis, training_phase=training_phase,
                expected_days_per_week=expected_days_per_week,
                forced_deload=pre_adaptive_deload_mode,
            )
            if athlete_id and db is not None
            else {
                "active": False, "volume_multiplier": 1.0, "intensity_multiplier": 1.0,
                "auto_deload_recommended": False, "sessions_considered": 0, "reasons": [],
            }
        )

        # Work on a private copy so custom_progressions never bleeds into other requests
        # or persists across them (see _apply_overrides docstring).
        dag = copy.deepcopy(self.base_dag) if request.custom_progressions else self.base_dag

        if request.custom_progressions:
            self._apply_overrides(dag, request.custom_progressions)

        bio_eval = self.evaluate_biometrics_and_strength(request.biometrics, request.experience_level)
        user_injuries = {inj.strip().lower() for inj in request.injuries}

        # See template_seed_multiplier's docstring - None/empty for every
        # caller except a program_builder day that matched a FORGE S&C
        # Template, which is a complete no-op (identical scores to before
        # this existed). Normalized once here (not per-candidate below) via
        # the same normalize_exercise_name program_builder used to build
        # this list, so the comparison in the loop is a cheap set lookup.
        seed_names_normalized = (
            {normalize_exercise_name(n) for n in request.template_seed_names if n and n.strip()}
            if request.template_seed_names else None
        )

        # (v5.18) Whole-program gate: any severity-3 ("structural failure -
        # the joint cannot be trusted under any real load") injury on file
        # blocks generation entirely, before any exercise selection runs -
        # not just the joint it maps to. See
        # injury_taxonomy.resolve_severe_injuries's docstring for why this
        # is deliberately broader than the per-joint difficulty ceiling
        # below and separate from resolve_systemic_injury (which only
        # covers the handful of entries flagged `systemic`). Every matched
        # injury's own `clinical_red_flags` are surfaced in the error
        # detail, not just its name, so the person sees what to describe to
        # a clinician - not just that they're blocked.
        severe_injuries = resolve_severe_injuries(user_injuries)
        if severe_injuries:
            names = ", ".join(i["name"] for i in severe_injuries)
            raise SevereInjuryBlockedError(
                f"No workout program can be generated: {names} "
                f"{'is' if len(severe_injuries) == 1 else 'are'} classified as a "
                "severe (grade/structural) injury. This requires evaluation and "
                "clearance from an orthopedic physician or physical therapist "
                "before any exercise program - including one generated here - "
                "should be treated as safe to follow.",
                details={"blocked_injuries": severe_injuries},
            )

        # {joint_name: worst_severity_tier} for any user injury that matches the taxonomy -
        # this is what makes exclusion severity-aware instead of a blanket joint ban.
        injury_joint_severity = self._resolve_injury_severity(user_injuries)
        # {joint: tissue} for the same matches, feeding the tissue-demand-aware
        # refinement in classify_injury_risk (v5.12) - see that function's
        # docstring. Empty dict when no injury string matches the taxonomy,
        # same as injury_joint_severity, so classify_injury_risk below just
        # gets tissue=None per joint and behaves exactly as before.
        injury_joint_tissue = self._resolve_injury_tissue(user_injuries)
        # {joint: rehab_stage} (v5.14) for any joint the person also gave an
        # explicit stage for via request.injury_stages - see
        # _resolve_injury_stage's docstring. Empty dict when injury_stages
        # is omitted or none of it matches, so classify_injury_risk/
        # classify_exercise_safety/find_alternatives below all get
        # stage=None per joint and behave exactly as before v5.14.
        injury_joint_stage = self._resolve_injury_stage(user_injuries, request.injury_stages)
        # {joint: side} (v5.15) for any joint the person also gave an
        # explicit left/right/bilateral side for via request.injury_sides -
        # see _resolve_injury_side's docstring. Empty dict when injury_sides
        # is omitted or none of it matches, so classify_injury_risk/
        # classify_exercise_safety/find_alternatives below all get
        # side=None per joint and behave exactly as before v5.15.
        injury_joint_side = self._resolve_injury_side(user_injuries, request.injury_sides)
        # (severity, stage) (v5.16) for any matched injury flagged `systemic`
        # in the taxonomy (currently: concussion) - see
        # injury_taxonomy.resolve_systemic_injury's docstring for why this
        # is separate from the {joint: ...} resolvers above. A systemic
        # injury restricts every exercise in the session by its own
        # severity/stage below, independent of joint_stress, unlike every
        # other injury here which only restricts exercises tagged with the
        # joint it's mapped to. (None, None) when nothing matched is
        # systemic, so the check below never fires and every existing call
        # site behaves exactly as before v5.16.
        systemic_severity, systemic_stage = resolve_systemic_injury(user_injuries, request.injury_stages)
        user_equipment = {eq.strip().lower() for eq in request.equipment_available}
        user_level_rank = LEVEL_RANK.get(request.experience_level, 2)

        # effective_readiness/poor_sleep/max_soreness were already computed
        # above, before the adaptive-load call, so the adaptive engine could
        # be told about a readiness/soreness-driven deload via
        # forced_deload= - see that block's comment. readiness_factor is
        # derived here (needs effective_readiness, computed either way);
        # deload_mode starts from that same pre-adaptive read.
        readiness_factor = effective_readiness / 100.0
        deload_mode = pre_adaptive_deload_mode

        # Fold the adaptive-load intensity nudge into readiness_factor itself
        # (clamped back to 0-1) - every downstream %1RM/hold/work-interval
        # formula in _prescribe_volume already reacts to readiness_factor, so
        # this makes the adjustment apply everywhere readiness already does,
        # without threading a second multiplier through each of those
        # formulas individually. A trending-up RPE spike (or the composite
        # signal crossing its own high-fatigue threshold) can also trigger
        # deload_mode here, exactly like max_soreness/effective_readiness
        # above - real recent training data overriding a readiness slider
        # that hasn't caught up to what the logs already show.
        readiness_factor = max(0.0, min(1.0, readiness_factor * adaptive_load["intensity_multiplier"]))
        deload_mode = deload_mode or adaptive_load["auto_deload_recommended"]

        prescribed_exercises = []
        excluded_exercises = []
        # Built once per request (not per exercise) - find_alternatives searches this
        # to recommend a safer swap instead of only reporting that something's excluded.
        all_exercises_by_id = {n: d for n, d in dag.nodes(data=True)}

        # Custom mode: evaluate exactly the exercises the person picked (in their
        # order) instead of the whole database - same safety checks below still
        # apply per exercise, so an unsafe pick still surfaces in excluded_exercises
        # with why, it's just scoped to their list rather than everything qualified.
        custom_mode = request.mode == "custom" and bool(request.selected_exercise_ids)
        unknown_custom_ids: List[str] = []
        if custom_mode:
            seen = set()
            node_pool = []
            for raw_id in request.selected_exercise_ids:
                cid = raw_id.strip()
                if not cid or cid in seen:
                    continue
                seen.add(cid)
                if cid in all_exercises_by_id:
                    node_pool.append((cid, all_exercises_by_id[cid]))
                else:
                    unknown_custom_ids.append(cid)
        else:
            node_pool = list(dag.nodes(data=True))

        # Session-focus filter (Program Builder support): when a request scopes
        # itself to specific categories/muscles (e.g. a "Push" day), exercises
        # outside that focus are skipped entirely up front - they're not
        # "excluded for a reason" (that list is for equipment/injury/strength/
        # level reasons a person can act on), they're just not part of what
        # this particular session is about. None/None (the default for every
        # existing caller) means no filtering at all - unchanged behavior.
        # Not applied in custom mode - an explicit exercise pick shouldn't be
        # silently dropped by a focus filter the person never set for it.
        has_focus_filter = (not custom_mode) and bool(request.target_categories or request.target_muscles)

        # "Powerlifting" and "Look Jacked" are goal-driven strength/
        # hypertrophy modes, not combat-sport disciplines - a person in
        # these modes wants the guide's own exercises (Competition Squat,
        # Barbell Row, ...) at the right volume/level, not whichever
        # exercise happens to score highest on sport-transfer overlap (that
        # scoring, and the "Transfer N" number built from it, describes
        # transfer to a sport's on-field qualities, which doesn't mean
        # anything for a pure strength/muscle goal). So the candidate pool
        # is restricted up front to exactly the exercises those two guides
        # prescribe (see pl_hypertrophy_manual.STRENGTH_MODE_EXERCISE_NAMES)
        # - every other check below (equipment/injury/strength/level) still
        # runs unchanged on that narrower pool, so a guide exercise the
        # person can't safely do is still excluded with a reason, same as
        # any other sport. Skipped in custom_mode for the same reason
        # has_focus_filter is - an explicit pick shouldn't be silently
        # dropped.
        strength_mode_names = STRENGTH_MODE_EXERCISE_NAMES.get(request.sport) if not custom_mode else None

        for node_id, data in node_pool:
            if strength_mode_names is not None:
                if data.get("name", "").strip().lower() not in strength_mode_names:
                    continue
                # `in_manual` marks an exercise as sourced from the Combat
                # Sports & Rugby S&C Manual - a different, unrelated source
                # from the two strength/hypertrophy guides these two modes
                # are built from (see pl_hypertrophy_manual.py). The
                # strength_mode_names membership check just above is
                # already this pool's own "is it in the (right) manual"
                # gate, so the Combat Sports one is skipped rather than
                # stacked on top of it - stacking it would silently drop
                # every guide exercise the Combat Sports manual doesn't
                # also happen to carry (most of them).
            # manual_only (default True): drop any exercise not sourced from
            # the printed manual/addendum before any other check runs. Not
            # applied in custom_mode for the same reason has_focus_filter
            # isn't - an explicit pick shouldn't be silently dropped. Not
            # applied for Powerlifting/Look Jacked either - see above.
            elif request.manual_only and not custom_mode and not data.get("in_manual", False):
                continue
            if has_focus_filter:
                category = data.get("category")
                movement_pattern = data.get("movement_pattern")
                ex_muscles = set(data.get("primary_muscles", [])) | set(data.get("secondary_muscles", []))
                matches_category = bool(
                    request.target_categories
                    and (category in request.target_categories or movement_pattern in request.target_categories)
                )
                matches_muscle = bool(
                    request.target_muscles and ex_muscles & set(request.target_muscles)
                )
                if not (matches_category or matches_muscle):
                    continue

            eq = data.get("equipment", "Bodyweight")
            joint_stress_raw = data.get("joint_stress", [])
            joint_stress = {j.lower() for j in joint_stress_raw}
            injuries_to_avoid = {i.lower() for i in data.get("injuries_to_avoid", [])}
            reqs = data.get("strength_requirements", {})
            ex_level_rank = LEVEL_RANK.get(data.get("experience_level", "Intermediate"), 2)
            difficulty = data.get("difficulty", 1)

            has_equipment = eq.lower() == "bodyweight" or eq.lower() in user_equipment

            contraindications = sorted(user_injuries & (joint_stress | injuries_to_avoid))

            # Four-tier injury risk check (v4.0): a joint the user has a taxonomy-matched
            # injury in isn't just "off" or "on". We classify every joint this exercise
            # stresses into safe / caution / high_risk / contraindicated (see
            # injury_taxonomy.classify_injury_risk) and block on the first one that lands
            # in the excluded half (high_risk or contraindicated) - which is exactly the
            # same allowed/excluded boundary v3.0 used, just with the reasoning kept.
            # "caution" joints are still allowed but recorded so the person (and the UI)
            # can see the exercise is at the edge of what that injury tolerates.
            severity_blocked_joint = None
            blocked_tier = None
            caution_joints = []
            # v5.15: joints where a one-sided injury was cleared only
            # because this exercise is side-selectable (movement_type ==
            # "Unilateral") - tracked separately from caution_joints so the
            # prescribed exercise can carry an explicit "train X side only"
            # note instead of silently prescribing bilateral-looking reps.
            laterality_cleared_joints = []
            for joint_name in joint_stress_raw:
                severity = injury_joint_severity.get(joint_name)
                if severity is None:
                    continue
                side = injury_joint_side.get(joint_name)
                tier = classify_injury_risk(
                    severity, difficulty,
                    tissue=injury_joint_tissue.get(joint_name), exercise=data,
                    stage=injury_joint_stage.get(joint_name), side=side,
                )
                if tier == "safe" and laterality_clears_joint(side, severity, data):
                    laterality_cleared_joints.append((joint_name, side))
                if tier == "caution":
                    caution_joints.append(joint_name)
                elif tier in ("high_risk", "contraindicated"):
                    severity_blocked_joint = joint_name
                    blocked_tier = tier
                    break

            # GREEN/YELLOW/RED safety classification (v5.13, see
            # injury_taxonomy.classify_exercise_safety's module comment):
            # a coach/athlete-facing label layered on top of the four-tier
            # check above, not a replacement for it - `is_safe`/`qualifies`
            # below still gate prescription exactly as before. Evaluated
            # over every matched joint (not just the one the break above
            # stopped on) since the label is meant to describe the whole
            # exercise-vs-injuries relationship, and the worst color across
            # joints wins - the same "never hide a real caution" rule
            # worst_safety_color documents.
            safety_colors = []
            safety_rationales = []
            for joint_name in joint_stress_raw:
                severity = injury_joint_severity.get(joint_name)
                if severity is None:
                    continue
                classification = classify_exercise_safety(
                    severity, difficulty,
                    tissue=injury_joint_tissue.get(joint_name), exercise=data,
                    stage=injury_joint_stage.get(joint_name), side=injury_joint_side.get(joint_name),
                )
                safety_colors.append(classification["color"])
                safety_rationales.append(f"{joint_name}: {classification['rationale']}")
            safety_classification = (
                {"color": worst_safety_color(safety_colors), "details": safety_rationales}
                if safety_colors else None
            )

            # (v5.16) A systemic injury (see resolve_systemic_injury above)
            # gates this exercise on its own severity/stage regardless of
            # which joints joint_stress lists - unlike severity_blocked_joint
            # above, which only ever fires for a joint this specific
            # exercise actually tags. Without this, an exercise that doesn't
            # happen to tag "Neck" (e.g. a squat, a bench press) would sail
            # through a concussion check entirely, contradicting that
            # injury's own movement_restrictions/absolute_contraindications.
            systemic_blocked_tier = None
            if systemic_severity is not None:
                systemic_tier = classify_injury_risk(systemic_severity, difficulty, stage=systemic_stage)
                if systemic_tier in ("high_risk", "contraindicated"):
                    systemic_blocked_tier = systemic_tier

            is_safe = (
                len(contraindications) == 0
                and severity_blocked_joint is None
                and systemic_blocked_tier is None
            )

            strength_qualified = (
                bio_eval["relative_bench_ratio"] >= reqs.get("bench_ratio", 0.0)
                and bio_eval["relative_squat_ratio"] >= reqs.get("squat_ratio", 0.0)
                and bio_eval["relative_deadlift_ratio"] >= reqs.get("deadlift_ratio", 0.0)
                and bio_eval["pullups_max_reps"] >= reqs.get("pullups", 0)
                and bio_eval["pushups_max_reps"] >= reqs.get("pushups", 0)
            )

            # Experience level is now actually used: an exercise is allowed at most one
            # rung above the user's stated level, even if their entered numbers happen to
            # clear the raw strength thresholds. Previously `experience_level` was accepted
            # by the API and shown in the UI but never once read by the engine.
            level_ok = ex_level_rank <= user_level_rank + LEVEL_STRETCH

            if deload_mode and data.get("difficulty", 1) >= 4:
                level_ok = False

            # Sport transfer is no longer just the hand-authored sport_priority number -
            # it's blended with a weighted overlap of this exercise's own derived
            # athletic_qualities against the sport's quality profile (sport_profiles.py),
            # so the ranking is grounded in something explainable rather than a single
            # opaque authored score.
            # blended_transfer_score is "how good is this exercise's overall
            # quality profile for this sport"; movement_emphasis_multiplier
            # is the separate "is this specifically the push/pull/hinge/etc.
            # pattern this sport actually needs more of" signal (see
            # sport_profiles.py docstring - a Boxing session should skew
            # toward pressing, a Judo session toward pulling, even when both
            # exercises score similarly on raw quality overlap).
            # equipment_movement_priority_multiplier is sport-independent - it's the
            # manual's own default hierarchy (barbell > compound patterns > Olympic
            # lifts > kettlebell > core/grip > everything else), applied on top of
            # the sport-specific transfer/emphasis score rather than instead of it.
            # injury_avoidant_equipment_multiplier: on top of the unconditional
            # equipment_movement_priority_multiplier bump every athlete gets for
            # low-risk implements, this adds a further boost specifically when
            # THIS athlete has a tracked injury on a joint this exercise's
            # equipment is a curated, dedicated substitute for (e.g. a knee or
            # other leg-joint injury + a Seal Row Bench available -> the Seal
            # Row actually ranks ahead of other qualifying row variations,
            # rather than only being one point among many with the same
            # everyone-gets-it bonus). Injured joints come straight from
            # injury_joint_severity's keys - the exact same joint set the
            # safety gate above already used to decide what's allowed at all.
            personalization = personalization_multiplier(node_id, history_signals)
            template_seed = template_seed_multiplier(normalize_exercise_name(data.get("name", node_id)), seed_names_normalized)
            sport_score = round(
                blended_transfer_score(data, request.sport) * movement_emphasis_multiplier(data, request.sport)
                * level_fit_multiplier(ex_level_rank, user_level_rank)
                * equipment_movement_priority_multiplier(data, request.training_emphasis, request.experience_level)
                * injury_avoidant_equipment_multiplier(data, set(injury_joint_severity.keys()))
                * hypertrophy_quality_multiplier(data, request.training_emphasis)
                * press_variation_multiplier(data)
                * athlete_movement_priority_multiplier(data)
                * personalization["multiplier"]
                * template_seed["multiplier"]
            )
            sport_score = max(0, min(100, sport_score))
            role, role_rationale = classify_programming_role(data)

            qualifies = has_equipment and is_safe and strength_qualified and level_ok

            # Reasons a plain (non-custom) request would exclude this exercise -
            # computed unconditionally now because custom mode needs the same
            # list to build a warning instead of a wall (see below).
            reasons = []
            if not has_equipment:
                reasons.append(f"Missing equipment: {eq}")
            if contraindications:
                reasons.append(f"Injury contraindication: {', '.join(contraindications)}")
            if severity_blocked_joint:
                severity_for_reason = injury_joint_severity[severity_blocked_joint]
                tier_label = {1: "mild", 2: "moderate", 3: "severe"}.get(severity_for_reason, "flagged")
                stage_for_reason = injury_joint_stage.get(severity_blocked_joint)
                stage_note = f", rehab stage: {stage_for_reason}" if stage_for_reason else ""
                reasons.append(
                    f"Too demanding for a {tier_label} {severity_blocked_joint} injury "
                    f"(difficulty {difficulty}, risk tier: {blocked_tier}{stage_note})"
                )
            if systemic_blocked_tier:
                tier_label = {1: "mild", 2: "moderate", 3: "severe"}.get(systemic_severity, "flagged")
                stage_note = f", rehab stage: {systemic_stage}" if systemic_stage else ""
                reasons.append(
                    f"Too much overall exertion for a {tier_label} systemic injury "
                    f"(difficulty {difficulty}, risk tier: {systemic_blocked_tier}{stage_note}) — "
                    f"this restricts the whole session, not just exercises for one joint"
                )
            if not strength_qualified:
                reasons.append("Below relative-strength threshold")
            if not level_ok:
                reasons.append(f"Above your experience level ({data.get('experience_level')})")

            # Custom mode: an explicit pick is never silently dropped for a
            # safety reason - the person chose it, so it still comes back in
            # prescribed_workout (their sets/reps/weight for it survive)
            # flagged with a `safety_warning` explaining what the engine
            # would normally have excluded it for, instead of being moved to
            # excluded_exercises and disappearing from the session (see the
            # WorkoutRequest.selected_exercise_ids docstring - "custom" means
            # "you choose the exercises", and now the safety net is a
            # warning attached to your pick rather than a wall in front of
            # it). Non-custom requests are completely unaffected: `qualifies`
            # alone still gates them exactly as before.
            if qualifies or custom_mode:
                prescribed = {
                    "id": node_id,
                    "name": data.get("name", node_id),
                    "category": data.get("category"),
                    "movement_family": data.get("movement_family"),
                    "movement_pattern": data.get("movement_pattern"),
                    "difficulty": data.get("difficulty"),
                    "experience_level": data.get("experience_level"),
                    "experience_level_fit": level_fit_label(ex_level_rank, user_level_rank),
                    "equipment": eq,
                    "sport_priority_score": sport_score,
                    "sport_transfer_rationale": transfer_rationale(data, request.sport),
                    "sc_template_seed_matched": template_seed["matched"],
                    "programming_role": role,
                    "programming_role_rationale": role_rationale,
                    "session_order_rank": session_order_rank(role),
                    "prescription": add_working_weight(
                        # training_emphasis nudges reps/load/sets toward a
                        # power or hypertrophy bias (see program_builder's
                        # _apply_prescription_bias docstring) - a no-op when
                        # it's unset (the default), so every existing caller
                        # gets the exact same prescription as before.
                        # add_working_weight has to run *after* the bias
                        # (not before) since the bias can change
                        # load_pct_1rm, and the displayed kg needs to match
                        # the final percentage, not the pre-bias one.
                        _apply_prescription_bias(
                            self._prescribe_volume(
                                data, readiness_factor, deload_mode, poor_sleep, request.conditioning_emphasis,
                                volume_multiplier=adaptive_load["volume_multiplier"],
                            ),
                            request.training_emphasis,
                            {},
                            movement_family=data.get("movement_family"),
                        ),
                        data.get("category"),
                        request.biometrics,
                        equipment=eq,
                        strength_requirements=data.get("strength_requirements"),
                        movement_type=data.get("movement_type"),
                    ),
                }
                weight_note = missing_anchor_note(data.get("category"), request.biometrics)
                if weight_note and prescribed["prescription"].get("type") == "strength":
                    prescribed["prescription"]["weight_note"] = weight_note
                if personalization["note"]:
                    prescribed["personalization_note"] = _name_plateau_progression(
                        personalization["note"], data, self.exercises_by_id,
                    )
                if caution_joints:
                    stage_notes = [
                        f"{j} ({injury_joint_stage[j]})" if injury_joint_stage.get(j) else j
                        for j in sorted(caution_joints)
                    ]
                    prescribed["injury_caution"] = (
                        f"At the edge of what your {', '.join(stage_notes)} "
                        f"injury currently tolerates - monitor how it feels."
                    )
                if safety_classification:
                    prescribed["safety_classification"] = safety_classification
                if laterality_cleared_joints:
                    notes = [
                        f"{joint} ({side} side injured) - train your {OPPOSITE_SIDE[side]} side only"
                        for joint, side in sorted(laterality_cleared_joints)
                    ]
                    prescribed["laterality_note"] = "; ".join(notes)
                # v4.0 movement/athletic-quality metadata, when present (backward compatible:
                # exercises enriched before running enrich_exercises.py simply omit these).
                for field in (
                    "movement_plane", "movement_type", "chain_type", "force_type",
                    "velocity_type", "technical_complexity", "CNS_fatigue",
                    "recovery_time_hours", "athletic_qualities",
                ):
                    if field in data:
                        prescribed[field] = data[field]
                if custom_mode and not qualifies:
                    prescribed["safety_warning"] = {
                        "reasons": reasons,
                        "note": (
                            "This pick would normally be excluded by the engine's safety "
                            "checks - it's still included because you chose it in Custom "
                            "Mode. Review the reason(s) before training it."
                        ),
                    }
                prescribed_exercises.append(prescribed)
            else:
                excluded = {
                    "id": node_id,
                    "name": data.get("name", node_id),
                    "reasons": reasons,
                }
                if safety_classification:
                    excluded["safety_classification"] = safety_classification


                if severity_blocked_joint:
                    excluded["risk_tier"] = blocked_tier
                    alts = find_alternatives(
                        data, all_exercises_by_id, injury_joint_severity,
                        user_equipment=user_equipment,
                        injury_joint_tissue=injury_joint_tissue,
                        injury_joint_stage=injury_joint_stage,
                        user_injuries=user_injuries,
                        injury_joint_side=injury_joint_side,
                    )
                    if alts:
                        severity = injury_joint_severity.get(severity_blocked_joint, 0)
                        stage = injury_joint_stage.get(severity_blocked_joint)
                        side = injury_joint_side.get(severity_blocked_joint)
                        excluded["alternatives"] = [
                            {
                                "id": a["id"],
                                "name": a.get("name", a["id"]),
                                "equipment": a.get("equipment", "Bodyweight"),
                                # Whether the person's own equipment list covers this
                                # swap right now - a belt squat swap is only actually
                                # useful to surface first if they have a belt squat.
                                "equipment_available": (
                                    a.get("equipment", "Bodyweight").lower() == "bodyweight"
                                    or a.get("equipment", "").lower() in user_equipment
                                ),
                                "difficulty": a.get("difficulty"),
                                # Not just "doesn't aggravate it" - actively trains that
                                # joint's stability at a load the injury can tolerate.
                                "rehab_pick": is_rehab_candidate(
                                    a, severity_blocked_joint, severity,
                                    tissue=injury_joint_tissue.get(severity_blocked_joint),
                                    stage=stage,
                                ),
                                # Same GREEN/YELLOW/RED label the exercise it's
                                # replacing carries, computed against the same
                                # blocked joint - so a suggested swap can't read
                                # as a plain "alternative" while still secretly
                                # sitting at RED for this injury.
                                "safety_classification": classify_exercise_safety(
                                    severity, a.get("difficulty", 1),
                                    tissue=injury_joint_tissue.get(severity_blocked_joint),
                                    exercise=a,
                                    stage=stage, side=side,
                                ),
                            }
                            for a in alts
                        ]
                    else:
                        # (v5.18) Previously silent: an empty `alts` list
                        # left `excluded` with no "alternatives" key at all
                        # and no other signal that a substitute was even
                        # searched for - from the frontend/user's side that
                        # was indistinguishable from an exercise that was
                        # simply never checked for alternatives. A moderate/
                        # mild injury with a tight enough joint ceiling (or a
                        # movement pattern with few same-pattern options) can
                        # legitimately have zero safe same-pattern swaps in
                        # the catalog - that's a real, actionable finding
                        # (this exercise's whole movement pattern is off the
                        # table right now, not just this one variant) and
                        # should say so explicitly rather than disappear.
                        excluded["alternatives_note"] = (
                            "No safe substitute for this movement pattern was found given your "
                            "current injury - this isn't just this specific exercise, the whole "
                            "movement pattern is likely off the table for now. Check with your "
                            "coach, physical therapist, or physician before working around it."
                        )

                    # Combat Sports & Rugby S&C Manual, Part 7.7: if this
                    # exercise/joint pair is one the manual specifically
                    # names (e.g. Back Squat + Lower Back -> Belt Squat),
                    # attach that named guidance alongside the generic
                    # live-search alternatives above - same underlying
                    # joint-clearance logic, but with the manual's own
                    # coach-readable rationale attached.
                    manual_swaps = part7_recommended_swap(
                        data, all_exercises_by_id, severity_blocked_joint,
                    )
                    if manual_swaps:
                        excluded["manual_guidance"] = manual_swaps
                elif systemic_blocked_tier:
                    # No alternatives suggested here (unlike the joint-scoped
                    # branch above): a systemic injury (concussion) means
                    # "reduce/stop overall exertion", not "swap this specific
                    # exercise for one that misses one joint" - there usually
                    # isn't a same-pattern substitute that's actually safer
                    # in the way a joint-specific swap is.
                    excluded["risk_tier"] = systemic_blocked_tier

                # DAG payoff: if the only thing blocking this exercise is strength, tell the
                # user exactly what's missing and, if its regression (predecessor in the
                # graph) is something they CAN already do, point them at it directly. This
                # is the actual reason the engine builds a graph instead of a flat list -
                # previously the DAG was built and then never read from again.
                if has_equipment and is_safe and level_ok and not strength_qualified:
                    gap = self._strength_gap(bio_eval, reqs)
                    excluded["progress_needed"] = gap
                    prereqs = list(dag.predecessors(node_id))
                    unlocked_prereq = next(
                        (p for p in prereqs if any(pe["id"] == p for pe in prescribed_exercises)),
                        None,
                    )
                    if unlocked_prereq:
                        excluded["next_step"] = (
                            f"Build up on '{dag.nodes[unlocked_prereq].get('name', unlocked_prereq)}' first"
                        )

                excluded_exercises.append(excluded)

        # Any custom-mode ids that don't exist in the database at all (typo, stale
        # id from a previous data version) - reported distinctly from an id that
        # exists but got excluded for a safety reason.
        for bad_id in unknown_custom_ids:
            excluded_exercises.append({
                "id": bad_id,
                "name": bad_id,
                "reasons": ["Unknown exercise id - not found in the current database"],
            })

        # Session-length cap. Exercises trimmed here still qualified on
        # every safety/equipment/strength check; they're just not in this
        # session for space reasons, so they're not added to
        # excluded_exercises. Skipped in custom mode - the person already
        # chose exactly which exercises they want.
        #
        # Two shapes, depending on who's calling:
        #  - Program Builder day (target_categories/target_muscles set, and
        #    it always passes its own exercise_limit): keeps the older
        #    one-per-role-plus-pattern-coverage fill, since a program day
        #    genuinely needs primer/skill/power/core coverage across a
        #    whole split, not just a single ad-hoc session.
        #  - A plain single-session request (the common case - no
        #    target_categories/target_muscles): composed as compounds +
        #    accessories + one finisher, the shape an actual coach hands
        #    someone for a single day - not every programming role crammed
        #    into one session. compound_count scales 2->3 with a longer
        #    requested session.
        recent_ids = {i.strip() for i in (request.exclude_exercise_ids or [])}
        # Same recency signal, one level up: which movement_family each
        # already-recently-used id belongs to, so _pick_with_variety can
        # prefer a genuinely different movement over a same-family
        # relabeled repeat (see that method's docstring for the bug this
        # fixes - e.g. Judo's Hinge slot cycling through every "High Pull"
        # variant across a week instead of rotating movements).
        recent_families = {
            self.exercises_by_id[i].get("movement_family")
            for i in recent_ids
            if i in self.exercises_by_id
        }

        # Live striking/bag work (movement_pattern == "Strike") plays no role in this
        # app's actual job: strength & conditioning programming. Nobody uses a gym
        # program to learn to throw a heavy-bag combination - that's trained
        # separately, at the actual sport, with a coach. So these drills are simply
        # excluded from the session entirely (not selected as strength work, and not
        # tacked on as a warm-up suggestion either) rather than routed anywhere.
        # Not applied in custom_mode - same reasoning as everywhere else in this
        # function tagged "not applied in custom_mode": an explicit pick is never
        # silently dropped, it's the person's own session.
        if not custom_mode:
            prescribed_exercises = [e for e in prescribed_exercises if e["programming_role"] != STRIKE_SKILL_EXCLUDED_ROLE]

        # Real hard exclusion (unlike recent_ids/recent_families above, which
        # only deprioritize) - not applied in custom_mode, same reasoning as
        # every other filter here: an explicit pick is never silently dropped.
        if not custom_mode and request.hard_exclude_exercise_ids:
            _hard_excluded = {i.strip() for i in request.hard_exclude_exercise_ids}
            prescribed_exercises = [e for e in prescribed_exercises if e["id"] not in _hard_excluded]

        is_program_day = request.target_categories is not None or request.target_muscles is not None
        if not custom_mode:
            if is_program_day:
                effective_limit = (
                    request.exercise_limit
                    if request.exercise_limit is not None
                    else _estimate_exercise_count(
                        request.session_duration_minutes, request.outside_training_sessions_per_week
                    )
                )
                if len(prescribed_exercises) > effective_limit:
                    prescribed_exercises = self._select_role_balanced(
                        prescribed_exercises, effective_limit,
                        recent_exercise_ids=recent_ids, variety_seed=request.variety_seed,
                        recent_exercise_families=recent_families,
                    )
            else:
                # Full 30/45/60/75/90/120/150-minute composition ladder -
                # see _session_composition's docstring (program_builder.py)
                # for the coaching rationale behind each threshold. Below
                # 75 min this reproduces exactly what used to be inlined
                # here (2/3 compounds, skill+power turning on at 45,
                # secondary turning on at 45 and doubling at 75); at 90+
                # min it's the new part - accessory volume (and, at 150, a
                # second finisher) keeps scaling instead of staying frozen
                # at the 75-minute shape. outside_training_sessions_per_week
                # trims accessory/finisher slots on top of the duration-based
                # shape - see _session_composition's docstring.
                composition = _session_composition(
                    request.session_duration_minutes, request.outside_training_sessions_per_week
                )
                prescribed_exercises = self._select_compound_accessory_finisher(
                    prescribed_exercises, composition["compound_count"],
                    recent_exercise_ids=recent_ids, variety_seed=request.variety_seed,
                    recent_exercise_families=recent_families,
                    skill_count=composition["skill_count"],
                    power_count=composition["power_count"],
                    secondary_count=composition["secondary_count"],
                    accessory_count=composition["accessory_count"],
                    finisher_count=composition["finisher_count"],
                )

        # Sequencing, not just filtering: within each programming-role phase (primer ->
        # skill -> power -> primary strength -> secondary strength -> accessory -> core ->
        # conditioning), rank
        # by sport transfer. Across phases, always respect the coaching order - a
        # high-transfer conditioning finisher still runs last, never before the main lift.
        # Skipped entirely in custom_mode - the engine's own role/transfer ordering is
        # exactly the kind of thing "custom" means the person doesn't want; their pick
        # order (the order selected_exercise_ids arrived in, already preserved through
        # node_pool above) is the session order, full stop.
        if not custom_mode:
            prescribed_exercises.sort(key=lambda x: (x["session_order_rank"], -x["sport_priority_score"]))

        session_structure = []
        if custom_mode:
            if prescribed_exercises:
                session_structure.append({
                    "phase": "Custom Session",
                    "exercises": [e["id"] for e in prescribed_exercises],
                })
        else:
            for role in ROLE_ORDER:
                phase_exercises = [e for e in prescribed_exercises if e["programming_role"] == role]
                if phase_exercises:
                    session_structure.append({
                        "phase": role,
                        "exercises": [e["id"] for e in phase_exercises],
                    })

        # Roadmap: the top sport-relevant exercises that are locked on strength alone,
        # closest gap first, using the DAG's own strength gap data computed above.
        roadmap = sorted(
            (e for e in excluded_exercises if "progress_needed" in e and e["progress_needed"]),
            key=lambda e: (len(e["progress_needed"]), e["id"]),
        )[:5]

        # Part 9.1 - the manual's generic pre-lift warm-up protocol (general
        # warm-up, dynamic mobility, ramp-up sets for the main lift). Sport-
        # agnostic on purpose - this is the "before you touch a weight"
        # routine, not sport skill work (which is deliberately excluded from
        # this session entirely - see STRIKE_SKILL_EXCLUDED_ROLE above).
        session_warmup = conditioning_reference(request.sport)

        response = {
            "status": "success",
            "engine": "FORGE Knowledge Graph Engine v5.8",
            "mode": "custom" if custom_mode else "preset",
            # Phase 5 (roadmap): whether this response's ranking was
            # actually nudged by logged history (see history_signals
            # above) - false for anonymous callers and for any logged-in
            # athlete without MIN_SESSIONS_FOR_SIGNAL logged sessions yet.
            "personalization_applied": bool(history_signals),
            "sport": request.sport,
            "experience_level": request.experience_level,
            # Advisory only - see level_check's own docstring. level_ok above
            # already ran against request.experience_level exactly as before;
            # this doesn't change which exercises got selected, it just shows
            # whether the entered numbers actually agree with that level.
            "level_check": level_check(request.experience_level, bio_eval["level_estimate"]),
            "deload_mode": deload_mode,
            "readiness_factor": round(readiness_factor, 2),
            # Whole-session history read (RPE trend, weekly volume trend,
            # missed-session gap, aggregate progressing/plateau) that fed
            # into readiness_factor/deload_mode/every prescribed exercise's
            # sets above - see compute_adaptive_load_adjustment. "active"
            # is false (both multipliers 1.0, empty reasons) for anonymous
            # callers and any account without enough logged history yet,
            # same gating as personalization_applied.
            "adaptive_training_load": adaptive_load,
            "recovery": {
                "score": recovery["score"],
                "label": self._recovery_label(recovery["score"]),
                "components": recovery["components"],
                "poor_sleep": recovery["poor_sleep"],
                "high_soreness": recovery["high_soreness"],
                "high_stress": recovery["high_stress"],
            },
            "biometric_analysis": bio_eval,
            "session_summary": {
                "total_prescribed": len(prescribed_exercises),
                "total_excluded": len(excluded_exercises),
            },
            "prescribed_workout": prescribed_exercises,
            **{k: session_warmup[k] for k in ("warmup_protocol", "warmup_note")},
            "session_structure": session_structure,
            "excluded_exercises": excluded_exercises,
            "progression_roadmap": roadmap,
        }

        # Deterministic "pro coach" summary (see coach_notes.py) - unlike
        # ai_insight below, this needs no API key/feature flag and never
        # fails silently to nothing-shown; it's built entirely from data
        # already in `response` above. Attached before ai_insight so both
        # can coexist: coach_notes is the grounded/always-on read, ai_insight
        # is the optional free-text one on top.
        coach_notes = build_coach_notes(
            sport=request.sport,
            session_duration_minutes=request.session_duration_minutes,
            prescribed_exercises=prescribed_exercises,
            deload_mode=deload_mode,
            readiness_factor=readiness_factor,
            recovery=recovery,
            level_check_result=response["level_check"],
            injury_cautions=[e["injury_caution"] for e in prescribed_exercises if e.get("injury_caution")],
            progression_roadmap=roadmap,
        )
        if coach_notes is not None:
            response["coach_notes"] = coach_notes

        # Phase 17 (roadmap): the one seam a future AI feature attaches
        # through - see backend/services/ai_hooks.py. NullInsightProvider
        # (the only provider wired in today) always returns None, so this
        # is a no-op and `response` is unchanged, for every deployment
        # today (AI_FEATURES_ENABLED defaults to False). Built from data
        # already in hand above - nothing extra computed or fetched here.
        insight = get_insight_provider().annotate_session(SessionContext(
            sport=request.sport,
            experience_level=request.experience_level,
            deload_mode=deload_mode,
            readiness_factor=round(readiness_factor, 2),
            personalization_applied=bool(history_signals),
            prescribed_exercise_ids=[e["id"] for e in prescribed_exercises],
            excluded_exercise_ids=[e["id"] for e in excluded_exercises],
            history_signals=history_signals,
            prescribed_exercise_names=[e["name"] for e in prescribed_exercises],
            injury_cautions=[e["injury_caution"] for e in prescribed_exercises if e.get("injury_caution")],
            personalization_notes=[e["personalization_note"] for e in prescribed_exercises if e.get("personalization_note")],
        ))
        if insight is not None:
            response["ai_insight"] = insight

        return response


engine = ProgressionEngine()

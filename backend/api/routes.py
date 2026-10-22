"""All FastAPI routes for FORGE.

Split out of backend/main.py (Phase 2 of docs/ROADMAP.md - main.py
previously bundled routes + engine in one 1697-line file). Every route
below is unchanged from main.py: same path, same params, same body -
only the `@app.get/post/put/delete` decorators became `@router.*` so
this module can be mounted with `app.include_router(router)` from a
now-thin main.py. The module-level `_apply_profile_defaults` helper
moved here too since it's only ever used by routes in this file.

NOTE: static "Manual" mode - the verbatim printed-table endpoints
(`/api/v1/manual/sports*`, `/api/v1/manual/strength/*`, and their earlier
`/api/v1/manual-templates*`/`/api/v1/combat-manual/*` predecessors) plus
the `manual_only` allowlist that defaulted every generated session to a
fixed subset of exercises - has been removed for good. Every sport
chapter of the Combat & Contact Sports manual, and both strength/
hypertrophy guides - exercise banks, category order, level progression,
conditioning protocols, neck/grip prescriptions, and the equipment/injury
substitution addendum - is expressed as data the live engine reasons over
(sport_profiles.py, conditioning_protocols.py, injury_taxonomy.py,
programming_role.py, pl_hypertrophy_manual.py) rather than as a second,
disconnected copy of a guide's printed pages. `/api/v1/generate-workout`
and `/api/v1/generate-program` are the only ways to get a session, and
both draw on the full exercise database by default (`manual_only` now
defaults to False - see schemas.py), not a stale allowlist.
"""
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.cache import cache_forever, ttl_cache
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from backend.core.logging import get_logger
from backend.core.rate_limit import rate_limit
from backend.models.db_models import UserDB
from backend.models.schemas import (
    CONDITIONING_EMPHASES,
    PRIMARY_GOALS,
    TRAINING_PHASES,
    CustomWorkoutCreate,
    CustomWorkoutOut,
    PasswordResetConfirm,
    PasswordResetRequest,
    ProgramRequest,
    RefreshRequest,
    SCTemplateBuildRequest,
    SavedProgramCreate,
    SavedProgramOut,
    SessionLogCreate,
    SessionLogOut,
    SuggestedReadinessOut,
    Token,
    UserBiometrics,
    UserCreate,
    UserLogin,
    UserOut,
    UserProfileUpdate,
    WorkoutRequest,
)
from backend.services import auth_service, readiness_service, sync_service
from backend.services.injury_taxonomy import (
    grouped_injury_taxonomy,
    grouped_injury_taxonomy_by_muscle_group,
    part7_substitution_guidance,
    PART7_DISCLAIMER,
    find_alternatives,
    classify_exercise_safety,
    worst_safety_color,
    rehab_stage_reference,
    INJURY_SIDES,
)
from backend.services.exercise_metadata import build_equipment_catalog
from backend.services.knowledge_graph import explain_exercise, is_rehab_candidate
from backend.services import video_lookup
from backend.services.program_builder import (
    SPLIT_TEMPLATES, SPORT_SPLIT_GUIDANCE, PHASE_GUIDANCE, generate_program,
    build_template_fidelity_program,
)
from backend.services.progression_engine import (
    EXPERIENCE_LEVELS,
    ProgressionEngine,
    engine,
)
from backend.services.sport_profiles import (
    SPORT_QUALITY_PROFILES,
    SPORT_MOVEMENT_EMPHASIS,
    sport_conditioning_profile,
)
from backend.services.conditioning_protocols import conditioning_reference
from backend.services.grappling_playbook import (
    GRAPPLING_SPORTS,
    LEVELS as GRAPPLING_LEVELS,
    grappling_playbook_reference,
)
from backend.services.sc_template_library import (
    get_template,
    sport_question,
    all_sport_questions,
    library_summary,
    list_templates,
    sports_covered as sc_template_sports_covered,
)
from backend.services.strength_standards import classify_strength_level
from backend.services.recommendation_engine import (
    MIN_SESSIONS_FOR_SIGNAL,
    build_history_signals,
)

router = APIRouter()
logger = get_logger("routes")

@router.get("/api/v1/metadata")
def get_metadata():
    """Single source of truth for what the frontend can offer - derived from the same
    data file the engine filters against, so the UI's dropdowns can never fall out of
    sync with what exercises.json actually contains (previously they were hand-typed
    separately in app.py and had drifted: several equipment types and most injury tags
    in the data had no matching UI option at all)."""
    return {
        "sports": engine.all_sports,
        "equipment": engine.all_equipment,
        "injuries": engine.all_injuries,
        "injuries_grouped": grouped_injury_taxonomy(),
        "injuries_by_muscle_group": grouped_injury_taxonomy_by_muscle_group(),
        "rehab_stages": rehab_stage_reference(),
        "injury_sides": INJURY_SIDES,
        "experience_levels": EXPERIENCE_LEVELS,
        "conditioning_emphases": CONDITIONING_EMPHASES,
        "training_phases": TRAINING_PHASES,
        "exercise_count": len(engine.exercises_by_id),
    }


@router.get("/api/v1/sports/{sport}")
def get_sport_profile(sport: str):
    """What the engine actually knows about a sport's training demands - the
    athletic-quality weights (sport_profiles.SPORT_QUALITY_PROFILES) and the
    movement-pattern bias (SPORT_MOVEMENT_EMPHASIS) that together decide why,
    e.g., a Boxing session leans toward pressing/rotational work and a Judo
    session leans toward pulling/grip work. Makes that reasoning inspectable
    instead of only visible indirectly through which exercises rank highest."""
    if sport not in engine.all_sports:
        raise NotFoundError(f"Unknown sport: {sport}")
    quality_profile = SPORT_QUALITY_PROFILES.get(sport, {})
    movement_emphasis = SPORT_MOVEMENT_EMPHASIS.get(sport, {})
    emphasized = sorted(
        ((k, v) for k, v in movement_emphasis.items() if v > 1.0),
        key=lambda kv: -kv[1],
    )
    de_emphasized = sorted(
        ((k, v) for k, v in movement_emphasis.items() if v < 1.0),
        key=lambda kv: kv[1],
    )
    return {
        "sport": sport,
        "athletic_quality_profile": quality_profile,
        "movement_pattern_emphasis": movement_emphasis,
        "prioritized_patterns": [p for p, _ in emphasized],
        "deprioritized_patterns": [p for p, _ in de_emphasized],
        "has_custom_profile": sport in SPORT_QUALITY_PROFILES or sport in SPORT_MOVEMENT_EMPHASIS,
        "recommended_split": SPORT_SPLIT_GUIDANCE.get(sport),
        # Combat Sports & Rugby S&C Manual, Part 5 - aerobic:lactic ratio,
        # gym emphasis, and weekly conditioning notes. None for sports the
        # manual doesn't cover (e.g. Rock Climbing, HYROX).
        "conditioning_profile": sport_conditioning_profile(sport) or None,
    }


@router.get("/api/v1/conditioning-protocols")
def get_conditioning_protocols():
    """Sport-agnostic reference material from the Combat Sports & Rugby S&C
    Manual: what aerobic vs. lactic conditioning actually is (Part 2), the
    pick-one-of-these aerobic and lactic session menus (Part 6), the
    pre-lift warm-up protocol (Part 9.1), and the two add-ons the manual
    says apply regardless of sport or split - neck training and grip/
    forearm work (Part 1). Program-specific aerobic:lactic weighting for a
    given sport lives on /api/v1/sports/{sport} and inside
    /api/v1/generate-program's `conditioning_guidance` block instead."""
    return conditioning_reference()


@router.get("/api/v1/grappling-playbook")
def get_grappling_playbook(sport: str = "", level: str = ""):
    """Iowa State Grappling Strength & Conditioning Playbook (BJJ / Judo /
    Sambo / Wrestling, Beginner->Elite): athlete classification + testing
    battery, the RAMP warm-up system, the 5-level rotational-strength
    spectrum, the gated Olympic-lift progression ladder, each level's full
    per-quality loading grid and 4-week wave, the %1RM-to-rep chart, the
    body-area injury-armor system, the exercise selection matrix, the
    16-week macrocycle, the seven session cards, and recovery/fueling
    guidance. Pass `sport` (one of GRAPPLING_SPORTS) to include that
    sport's own discipline-specific supplemental block, and/or `level`
    (Beginner/Novice/Intermediate/Advanced/Elite) to narrow the loading
    grid and wave to just that level - same optional-filter pattern as
    `/api/v1/conditioning-protocols`. Invalid sport/level values are
    silently ignored (return the unfiltered tables), not rejected, since
    this is reference data, not a request that can fail.
    """
    return grappling_playbook_reference(sport=sport or None, level=level or None)


@router.get("/api/v1/sc-templates/sport-questions")
def get_sc_template_sport_questions(sport: str = ""):
    """The extra sport-specific question(s) the wizard should ask before
    browsing/building an SC template, beyond the shared goal/experience/
    schedule/equipment/injury questions every sport already asks - e.g.
    Rugby gets Positional Emphasis (+ optional Detailed Position), MMA
    gets Fight-Style Emphasis, Rock Climbing gets Discipline Emphasis,
    Powerlifting gets Periodization Style, and so on. Sports whose
    dimension IS the sport choice itself (Judo, BJJ, Wrestling, Sanda,
    Boxing, Muay Thai, Kickboxing), and any sport with no SC template
    coverage at all, simply don't appear.

    Pass `sport` (a wizard-facing sport name) to get just that one sport's
    `questions` list ([] if it has none). Omit `sport` to get every
    covered sport's questions at once, keyed by sport name, in `by_sport`
    - one round trip for the wizard to cache at startup instead of one
    call per sport."""
    if sport:
        return {"sport": sport, "questions": sport_question(sport)}
    return {"by_sport": all_sport_questions()}


@router.get("/api/v1/sc-templates")
def get_sc_templates(
    sport: str = "", level: str = "", goal: str = "", days_per_week: int = 0,
    library: str = "", include_generic: bool = True,
    emphasis: str = "", position: str = "",
):
    """Browse the FORGE S&C Template Libraries (1,730 pre-built named
    templates across grappling, striking, MMA, rock climbing, rugby,
    special forces / military operator, HYROX, powerlifting, natural
    bodybuilding, and general strength + hypertrophy) — a reference
    catalog, not a second program-generation path (see
    sc_template_library.py's docstring for why). Every filter is optional
    and combines with AND; `sport` also matches its library's
    sport-agnostic pool unless `include_generic=false`. `library` narrows
    to one of "grappling", "striking", "mma", "climbing", "rugby",
    "special_forces", "hyrox", "powerlifting", "natural_bodybuilding", or
    "strength_hypertrophy" directly. Returns a summarized list (id, name,
    sport, level, goal, days_per_week, duration_weeks) - fetch a specific
    template's full day-by-day breakdown from
    `/api/v1/sc-templates/{global_id}`. Invalid filter values return an
    empty list, not an error, same reference-data contract
    `/api/v1/grappling-playbook` uses.
    """
    return {
        "templates": list_templates(
            sport=sport or None,
            level=level or None,
            goal=goal or None,
            days_per_week=days_per_week or None,
            library=library or None,
            include_generic=include_generic,
            emphasis=emphasis or None,
            position=position or None,
        ),
        "sports_covered": sc_template_sports_covered(),
        "libraries": library_summary(),
    }


@router.get("/api/v1/sc-templates/{global_id}")
def get_sc_template(global_id: str):
    """One template's full day-by-day exercise breakdown by its
    `library:id` global id (e.g. `grappling:SC-001`, `mma:MMA-SC-042`) -
    see /api/v1/sc-templates to find one."""
    template = get_template(global_id)
    if template is None:
        raise NotFoundError(f"Unknown SC template id: {global_id}")
    return template


@router.post("/api/v1/sc-templates/{global_id}/build")
def build_sc_template(global_id: str, payload: SCTemplateBuildRequest):
    """Run one FORGE S&C Template as the coach who wrote it intended -
    same exercises, same order, same sets/reps/rest - handing an
    individual exercise slot to the live engine ONLY when the template's
    own pick fails this athlete's equipment or injury check right now
    (see program_builder.build_template_fidelity_program's docstring for
    the full reasoning, and how this differs from the soft "seed" role
    templates play in /api/v1/generate-program).

    Every returned exercise carries `template_source`/`verified`, plus
    either nothing else (kept as the template wrote it),
    `substituted_for`/`substitution_reason` (the engine found a safe
    swap), or `excluded`/`exclusion_reason` (nothing in the database
    cleared this athlete's checks for that slot). `substitutions_made`
    and `exercises_excluded` summarize how much of the template survived
    untouched.

    Pass `biometrics` (optional) to also get a recommended working weight
    in kg on every slot that carries a coach-written %1RM - computed off
    the athlete's own tested maxes, same as a normal generated program.
    """
    result = build_template_fidelity_program(
        engine, global_id,
        equipment_available=payload.equipment_available,
        injuries=payload.injuries,
        injury_stages=payload.injury_stages,
        injury_sides=payload.injury_sides,
        biometrics=payload.biometrics,
    )
    if result is None:
        raise NotFoundError(f"Unknown SC template id: {global_id}")
    return result


@router.get("/api/v1/injury-substitutions")
def get_injury_substitutions(joint: str = ""):
    """Combat Sports & Rugby S&C Manual, Part 7.7's named issue -> typical
    culprit -> safer substitute(s) table (Lower Back, Shoulder, Knee,
    Wrist, Elbow, Hip), each substitute resolved to a real exercises.json
    id/name where the database has one. Optionally filter to one joint
    (same 8-tag vocabulary as `/api/v1/injuries/grouped`). This is the
    manual's own reference table for common training niggles - the
    per-exercise `manual_guidance` already returned when an exercise is
    excluded on generate-workout/generate-program (see
    injury_taxonomy.part7_recommended_swap) covers the same ground for a
    specific exercise/injury pair in context."""
    all_ex = engine.exercises_by_id
    rows = part7_substitution_guidance(joint or None)
    by_name = {e.get("name", "").lower(): e for e in all_ex.values()}
    resolved = []
    for row in rows:
        subs = [
            {"id": by_name[s.lower()]["id"], "name": by_name[s.lower()]["name"]}
            for s in row["safer_substitutes"] if s.lower() in by_name
        ]
        resolved.append({**row, "safer_substitutes_resolved": subs})
    return {"substitutions": resolved, "disclaimer": PART7_DISCLAIMER}


@router.get("/api/v1/training-phases")
def get_training_phases():
    """The 5 competition-calendar phases from the manual's Part 9.3
    periodization table (Off-Season through Post-Competition) - what split
    each phase points to, its volume multiplier, and its lifting/
    conditioning focus. Pass one of these ids as `training_phase` on
    POST /api/v1/generate-program to have the split and weekly volume
    follow this table instead of the plain days/goal/sport heuristic."""
    return {
        "training_phases": [
            {"id": phase_id, **phase_data}
            for phase_id, phase_data in PHASE_GUIDANCE.items()
        ]
    }


@router.get("/api/v1/exercises")
def list_exercises(search: str = "", sport: str = "", equipment: str = "", limit: int = 500):
    """Lightweight catalog for building a custom session (mode="custom") - a person
    browses/searches this instead of the engine picking for them, then sends the
    ids they want as `selected_exercise_ids`. Deliberately thin (no safety/strength
    evaluation here - that only happens once, in generate_session, against the
    actual request) so this stays fast for a live search-as-you-type UI.
    `sport` filters to exercises that have any authored sport_priority for that
    sport; `equipment` matches the exercise's own equipment field case-insensitively.
    """
    search_lower = search.strip().lower()
    equipment_lower = equipment.strip().lower()
    results = []
    for node_id, data in engine.exercises_by_id.items():
        if search_lower and search_lower not in data.get("name", "").lower():
            continue
        if sport and sport not in data.get("sport_priority", {}):
            continue
        if equipment_lower and data.get("equipment", "Bodyweight").lower() != equipment_lower:
            continue
        results.append({
            "id": node_id,
            "name": data.get("name", node_id),
            "category": data.get("category"),
            "movement_pattern": data.get("movement_pattern"),
            "equipment": data.get("equipment", "Bodyweight"),
            "difficulty": data.get("difficulty"),
            "experience_level": data.get("experience_level"),
        })
        if len(results) >= limit:
            break
    return {"count": len(results), "exercises": results}


@ttl_cache(settings.METADATA_CACHE_TTL_SECONDS)
def _cached_equipment_catalog():
    """Phase 8: `build_equipment_catalog` re-groups all 731 exercises on
    every call - real work for a value that's only ever a function of
    `data/exercises.json`, which is loaded once at startup and never changes
    for the life of the process. TTL (not forever) to match
    `METADATA_CACHE_TTL_SECONDS`'s existing intent, in case a future pass
    adds hot-reloading of exercises.json without a restart."""
    return build_equipment_catalog(list(engine.exercises_by_id.values()))


@router.get("/api/v1/equipment")
def get_equipment_catalog():
    """Every equipment type in the database, grouped into browsable sections
    (Free Weights, Machines, Strongman, ...) with an exercise count and the
    movement categories it unlocks - what the old flat alphabetical checkbox
    list couldn't show. Lets someone see, before selecting it, that e.g.
    Kettlebell covers pushing/pulling/hinging/carrying/core (not just
    swings), or that Belt Squat is available as a squat-pattern option for
    someone avoiding axial spinal load."""
    return {"equipment": _cached_equipment_catalog()}


@router.get("/api/v1/injuries/grouped")
def get_injuries_grouped():
    """Same data as the `injuries_grouped` key on /api/v1/metadata, as its own
    endpoint - joint (section) -> condition (subsection) -> severity grades.
    Kept separate too so a client only interested in the injury browser
    doesn't need to pull sports/equipment along with it."""
    return grouped_injury_taxonomy()


@router.get("/api/v1/injuries/by-muscle-group")
def get_injuries_by_muscle_group():
    """Same data as the `injuries_by_muscle_group` key on /api/v1/metadata,
    as its own endpoint - muscle group / joint category (section) ->
    condition (subsection) -> severity grades. A second browsing dimension
    over the same injury taxonomy as `/api/v1/injuries/grouped`: that
    endpoint groups everything by the engine's 8-tag `joint` vocabulary;
    this one groups muscle strains by anatomical muscle group (Chest, Back,
    Legs, ...) and keeps ligament/tendon/joint-disorder entries in their
    own joint-labeled categories, so a UI can offer both browsing styles
    off the same underlying data."""
    return grouped_injury_taxonomy_by_muscle_group()


@cache_forever
def _cached_explain_exercise(exercise_id: str):
    """Phase 8: `explain_exercise` walks every in/out edge of one node in
    `engine.knowledge_graph` (progressions, regressions, substitutes, joints,
    rehab-candidacy, sport transfer x ~13 sports, then a sort) on every call.
    `engine.knowledge_graph` and `engine.exercises_by_id` are the same two
    objects, built once in `load_database` and never mutated per-request
    (unlike `engine.base_dag`, which a request's `custom_progressions` can
    deep-copy and edit - see progression_engine.py) - so for a given
    `exercise_id` this result is fixed for the life of the process.
    @cache_forever (not @ttl_cache): correct even under hot-reload, since a
    reload rebuilds a new `ProgressionEngine`/module state entirely rather
    than mutating this one in place. Bounded memory: at most one cache entry
    per real exercise id (731 today)."""
    return explain_exercise(engine.knowledge_graph, exercise_id, engine.exercises_by_id)


@router.get("/api/v1/knowledge-graph/{exercise_id}")
def get_exercise_knowledge(exercise_id: str):
    """Everything the knowledge graph knows about one exercise - progressions,
    regressions, equipment substitutes, joints it stresses, which injuries it's
    a genuine rehab candidate for, and its transfer score + rationale for every
    sport in the database. This is the graph made directly inspectable, not
    just a side effect of running a full workout generation."""
    result = _cached_explain_exercise(exercise_id)
    if result is None:
        raise NotFoundError(f"Unknown exercise id: {exercise_id}")
    return result


@router.get("/api/v1/exercises/{exercise_id}/video")
def get_exercise_video(exercise_id: str):
    """Demo video for one exercise. Checks a hand-curated link first
    (backend/data/exercise_video_links.py - always wins when present, no
    API key needed), then falls back to a live search (then disk-cached)
    on a single hand-picked YouTube channel per category - see
    backend/services/video_lookup.py's module docstring for exactly which
    channel each equipment type maps to and why. The frontend embeds the
    returned `embed_url` directly in the exercise modal (youtube-nocookie.com
    iframe, or a plain <video> tag for a direct file link) when
    `embeddable` is true; when it's false (a curated link to a site that
    doesn't embed cleanly, e.g. Instagram/TikTok) the frontend shows a
    "Watch on <source>" button that opens `watch_url` in a new tab instead.

    Returns `{"available": false, "reason": ...}` (not a 404) when there's
    no curated link AND (no assigned channel, no YOUTUBE_API_KEY
    configured, or no matching video found) - all "nothing to show", not
    errors.
    """
    exercise = engine.exercises_by_id.get(exercise_id)
    if exercise is None:
        raise NotFoundError(f"Unknown exercise id: {exercise_id}")

    has_curated_link = exercise_id in video_lookup.EXERCISE_VIDEO_LINKS
    if not has_curated_link:
        channel_id = video_lookup.pick_channel_for_exercise(exercise)
        if channel_id is None:
            return {"available": False, "reason": "no_channel_for_equipment_type"}
        if not settings.YOUTUBE_API_KEY:
            return {"available": False, "reason": "youtube_api_key_not_configured"}

    result = video_lookup.get_video_for_exercise(exercise_id, exercise)
    if result is None:
        return {"available": False, "reason": "no_matching_video_found"}
    return {"available": True, **result}


@router.get("/api/v1/exercises/{exercise_id}/injury-swap")
def get_injury_aware_swap(
    exercise_id: str,
    injuries: str = "",
    equipment: str = "",
    max_results: int = 5,
    injury_stages: str = "",
    injury_sides: str = "",
):
    """The same injury+equipment-aware substitute search generate-workout
    already runs for an exercise it had to EXCLUDE outright (see
    generate_session's `find_alternatives` call) - exposed standalone so the
    frontend can offer a swap for an exercise that's still IN the session
    (e.g. sitting at `injury_caution` - allowed, but at the edge of what the
    injury tolerates) without needing a full workout regeneration first.

    `injuries`/`equipment` are comma-separated strings (same shape the rest
    of the API already accepts them in via WorkoutRequest) so this can be
    called with exactly the values the person already has selected in the
    wizard/session, not a re-typed subset.

    `injury_stages` (v5.14, optional) is a comma-separated list of
    `injury_name:rehab_stage` pairs - the same {injury_name: rehab_stage}
    idea as WorkoutRequest.injury_stages, flattened for a query string.
    An injury left out keeps today's severity-only behavior for that joint.

    `injury_sides` (v5.15, optional) is a comma-separated list of
    `injury_name:side` pairs (side is 'left'/'right'/'bilateral') - the same
    {injury_name: side} idea as WorkoutRequest.injury_sides, flattened for a
    query string. An injury left out is treated as bilateral.
    """
    all_exercises_by_id = engine.exercises_by_id
    exercise = all_exercises_by_id.get(exercise_id)
    if exercise is None:
        raise NotFoundError(f"Unknown exercise id: {exercise_id}")

    user_injuries = {i.strip().lower() for i in injuries.split(",") if i.strip()}
    user_equipment = {e.strip().lower() for e in equipment.split(",") if e.strip()}
    injury_joint_severity = ProgressionEngine._resolve_injury_severity(user_injuries)
    # {joint: tissue} companion (v5.12) - see classify_injury_risk's docstring
    # in injury_taxonomy.py for what this enables. Empty dict when nothing
    # matches, same as injury_joint_severity, so behavior is unchanged when
    # the person's injuries don't resolve to a taxonomy entry.
    injury_joint_tissue = ProgressionEngine._resolve_injury_tissue(user_injuries)
    # {injury_name: rehab_stage} parsed from the flattened query string, fed
    # through the same resolver generate_session uses (v5.14) - empty dict
    # (and therefore stage=None per joint below) when injury_stages is
    # omitted or malformed, reproducing pre-v5.14 behavior.
    injury_stage_pairs = {}
    for pair in injury_stages.split(","):
        if ":" not in pair:
            continue
        name, _, stage = pair.partition(":")
        if name.strip():
            injury_stage_pairs[name.strip()] = stage.strip()
    injury_joint_stage = ProgressionEngine._resolve_injury_stage(user_injuries, injury_stage_pairs)
    # {injury_name: side} parsed the same way as injury_stage_pairs above
    # (v5.15) - empty dict (and therefore side=None per joint below) when
    # injury_sides is omitted or malformed, reproducing pre-v5.15 behavior.
    injury_side_pairs = {}
    for pair in injury_sides.split(","):
        if ":" not in pair:
            continue
        name, _, side = pair.partition(":")
        if name.strip():
            injury_side_pairs[name.strip()] = side.strip()
    injury_joint_side = ProgressionEngine._resolve_injury_side(user_injuries, injury_side_pairs)

    alts = find_alternatives(
        exercise, all_exercises_by_id, injury_joint_severity,
        max_results=max_results, user_equipment=user_equipment or None,
        injury_joint_tissue=injury_joint_tissue,
        injury_joint_stage=injury_joint_stage,
        user_injuries=user_injuries,
        injury_joint_side=injury_joint_side,
    )
    options = [
        {
            "id": a["id"],
            "name": a.get("name", a["id"]),
            "category": a.get("category"),
            "movement_pattern": a.get("movement_pattern"),
            "equipment": a.get("equipment", "Bodyweight"),
            "equipment_available": (
                not user_equipment
                or a.get("equipment", "Bodyweight").lower() == "bodyweight"
                or a.get("equipment", "").lower() in user_equipment
            ),
            "difficulty": a.get("difficulty"),
            "rehab_pick": any(
                is_rehab_candidate(
                    a, joint, sev,
                    tissue=injury_joint_tissue.get(joint),
                    stage=injury_joint_stage.get(joint),
                )
                for joint, sev in injury_joint_severity.items()
            ) if injury_joint_severity else False,
            # GREEN/YELLOW/RED for this candidate against every joint it
            # actually stresses that the person also has a matched injury
            # in - see injury_taxonomy.classify_exercise_safety. Worst
            # color across joints wins, same as the generate-workout
            # response; GREEN (nothing to warn about) if no joint overlaps.
            "safety_classification": worst_safety_color([
                classify_exercise_safety(
                    injury_joint_severity[joint], a.get("difficulty", 1),
                    tissue=injury_joint_tissue.get(joint), exercise=a,
                    stage=injury_joint_stage.get(joint),
                )["color"]
                for joint in a.get("joint_stress", [])
                if joint in injury_joint_severity
            ]),
        }
        for a in alts
    ]
    return {"exercise_id": exercise_id, "options": options}


@router.post("/api/v1/estimate-level")
def estimate_level(payload: UserBiometrics):
    """Independent, standalone estimate of overall training level from raw
    lift/rep-max numbers - see strength_standards.py for the standards used
    and why this exists. Meant to run *before* the person has necessarily
    committed to an experience_level: the frontend can call this once
    biometrics are entered and use the result to suggest/pre-fill the
    experience_level dropdown on the session/program wizard, while the
    person keeps final say over what's actually submitted. Doesn't set or
    change anything server-side - the same estimate also rides along inside
    generate-workout/generate-program responses as `level_check`, once an
    experience_level has actually been chosen, so a mismatch stays visible
    there too instead of only at this one-off pre-fill step."""
    return classify_strength_level(
        weight_kg=payload.weight_kg,
        bench_press_1rm=payload.bench_press_1rm or 0.0,
        squat_1rm=payload.squat_1rm or 0.0,
        deadlift_1rm=payload.deadlift_1rm or 0.0,
        pullups_max_reps=payload.pullups_max_reps or 0,
        pushups_max_reps=payload.pushups_max_reps or 0,
        sex=payload.sex,
    )


def _normalize_sport_casing(payload):
    """`sport` on WorkoutRequest/ProgramRequest is deliberately free text (no
    Literal/enum - custom/unlisted sports must still work, see the field's own
    docstring precedent), so unlike experience_level/primary_goal it can't be
    fixed with a schemas.py field_validator without importing the runtime-built
    `engine.all_sports` list into schemas.py, which would create the exact
    schemas<->progression_engine import cycle backend/models/schemas.py's own
    module docstring says this split exists to avoid. Casing here has a bigger
    real-world impact than the two 422-then-fixable fields, though: a mismatch
    doesn't error, it just silently misses every sport_profiles.py dict lookup
    (SPORT_QUALITY_PROFILES.get(sport, {}) etc. all default to {} on a miss),
    so a caller sending "powerlifting" instead of "Powerlifting" gets a
    generic, non-sport-specific session with zero signal that anything went
    wrong. Fixed here instead, right where the request is already resolved
    against the live engine and profile - case-insensitive match against
    engine.all_sports, corrected to the canonical casing when found. A sport
    string genuinely not in engine.all_sports (custom text) is left untouched -
    that's real free-text, not a casing bug, and generate_session already
    handles an unrecognized sport by degrading gracefully, same as before."""
    if not isinstance(payload.sport, str) or not payload.sport.strip():
        return payload
    stripped = payload.sport.strip()
    lowered = stripped.lower()
    for candidate in engine.all_sports:
        if candidate.lower() == lowered:
            payload.sport = candidate
            break
    return payload


def _apply_profile_defaults(payload, user: Optional[UserDB]):
    """For a logged-in caller, fills in sport/experience_level/equipment/
    injuries from their saved profile - but ONLY for fields the request body
    didn't actually set (`model_fields_set` reflects what was present in the
    JSON, not what ended up populated by the schema's own defaults), so an
    explicit request value always wins over the stored profile. Anonymous
    requests (user is None) are untouched - existing callers see zero
    behavior change. This is deliberately light-touch personalization, not
    the full scored-recommendation engine (roadmap Phase 5) - it saves a
    returning person from re-picking their sport/equipment/injuries every
    time, nothing more."""
    if user is None:
        return payload
    profile = auth_service.user_to_out(user)
    set_fields = payload.model_fields_set
    if "sport" not in set_fields and profile.primary_sport:
        payload.sport = profile.primary_sport
    if "experience_level" not in set_fields and profile.experience_level:
        payload.experience_level = profile.experience_level
    if "equipment_available" not in set_fields and profile.equipment:
        payload.equipment_available = profile.equipment
    if "injuries" not in set_fields and profile.injuries:
        payload.injuries = profile.injuries
    return payload


@router.post(
    "/api/v1/generate-workout",
    # Phase 16 (roadmap): flagged since the AI-hooks pass ("no rate limiting
    # specific to this endpoint's AI cost - the existing per-IP rate limits on
    # auth endpoints don't cover generate-workout at all, AI-enabled or not")
    # as a real gap - this is the endpoint that (when AI_FEATURES_ENABLED is
    # on) makes a real, billed Anthropic API call per request via ai_hooks.py,
    # and even with AI features off it's still the single most compute-heavy
    # endpoint in the app (full DAG scoring across every eligible exercise).
    # 30/minute per IP is generous for a real user building sessions
    # interactively (the web UI generates at most a handful per minute even
    # during active use/regeneration) while still bounding the worst case for
    # a scripted abuse/cost-exhaustion attempt. Same _client_key/X-Forwarded-
    # For-aware IP resolution as the auth endpoints, so this doesn't collapse
    # onto one bucket behind a reverse proxy either.
    dependencies=[Depends(rate_limit("generate_workout", max_attempts=30, window_seconds=60))],
)
def generate_workout(
    payload: WorkoutRequest,
    current_user: Optional[UserDB] = Depends(auth_service.get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        payload = _normalize_sport_casing(payload)
        payload = _apply_profile_defaults(payload, current_user)
        # Phase 5 (roadmap): only a logged-in caller has an athlete_id worth
        # building history signals for - anonymous requests get athlete_id=None,
        # which generate_session already treats as a no-op (see its docstring).
        athlete_id = str(current_user.id) if current_user else None
        return engine.generate_session(payload, athlete_id=athlete_id, db=db)
    except HTTPException:
        raise
    except Exception:
        # Phase 10: no longer builds its own 500 here - logs with context
        # specific to this endpoint, then re-raises so the global catch-all
        # handler in backend/core/exceptions.py builds the actual response
        # (same DEBUG-gated detail behavior as before, just centralized so
        # every endpoint gets it instead of each one repeating the logic).
        logger.error("generate_workout_failed", exc_info=True)
        raise


# ==========================================
# 4. PROGRAM BUILDER ENDPOINTS
# ==========================================

@router.get("/api/v1/splits")
def get_splits():
    """Every training split the Program Builder can generate - id, display
    name, description, and which days-per-week counts it's designed for.
    Same principle as /api/v1/metadata: derived from SPLIT_TEMPLATES itself
    so this list can't drift out of sync with what generate-program actually
    supports. `preferred_split: "auto"` on a program request picks from
    these based on days_per_week + goal (and, where it applies, the sport -
    see `recommended_for_sports` below and SPORT_SPLIT_GUIDANCE) instead of
    the caller choosing one."""
    recommended_by_split: Dict[str, List[str]] = {}
    for sport, guidance in SPORT_SPLIT_GUIDANCE.items():
        recommended_by_split.setdefault(guidance["split"], []).append(sport)
    return {
        "splits": [
            {
                "id": split_id,
                "name": template["name"],
                "description": template["description"],
                "supported_days_per_week": template["supported_days_per_week"],
                "recommended_for_sports": sorted(recommended_by_split.get(split_id, [])),
            }
            for split_id, template in SPLIT_TEMPLATES.items()
        ]
    }


@router.get("/api/v1/goals")
def get_goals():
    """Primary goals accepted by /api/v1/generate-program."""
    return {"goals": PRIMARY_GOALS}


@router.post(
    "/api/v1/generate-program",
    # Same Phase 16 gap as generate-workout above, tighter budget here: this
    # calls generate_session once per (week, day) - a real request with e.g.
    # 6 weeks x 5 days/week is already 30 underlying session generations (plus
    # a program-level AI insight call when AI features are on), so the
    # per-request cost is meaningfully higher than a single generate-workout
    # call. 10/minute per IP is still generous for genuine interactive use
    # (nobody regenerates a multi-week program more than a few times a
    # minute) while bounding worst-case cost/compute exposure harder than the
    # single-session endpoint needs.
    dependencies=[Depends(rate_limit("generate_program", max_attempts=10, window_seconds=60))],
)
def generate_program_endpoint(
    payload: ProgramRequest,
    current_user: Optional[UserDB] = Depends(auth_service.get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        payload = _normalize_sport_casing(payload)
        payload = _apply_profile_defaults(payload, current_user)
        athlete_id = str(current_user.id) if current_user else None
        return generate_program(engine, payload, athlete_id=athlete_id, db=db)
    except HTTPException:
        raise
    except Exception:
        logger.error("generate_program_failed", exc_info=True)
        raise


# ==========================================
# 5. AUTH / USER PROFILES (Phase 6)
# ==========================================

@router.post(
    "/api/v1/auth/register",
    response_model=Token,
    status_code=201,
    dependencies=[Depends(rate_limit("register", max_attempts=5, window_seconds=3600))],
)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Creates an account and immediately signs them in (returns an access
    token in the same response) - one round trip instead of register-then-
    login. Rate-limited (5/hour per IP) against signup-spam/account-farming."""
    try:
        user = auth_service.register_user(db, payload)
    except auth_service.EmailAlreadyRegistered:
        raise ConflictError("An account with this email already exists.")
    return auth_service.issue_token(user, db)


@router.post(
    "/api/v1/auth/login",
    response_model=Token,
    dependencies=[Depends(rate_limit("login", max_attempts=10, window_seconds=60))],
)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Rate-limited (10/min per IP, shared across every email attempted from
    that IP) against credential stuffing / brute force."""
    user = auth_service.authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise UnauthorizedError("Incorrect email or password.")
    return auth_service.issue_token(user, db)


@router.post("/api/v1/auth/refresh", response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Exchanges a still-valid refresh token for a new access token + a
    rotated refresh token (see auth_service.refresh_access_token)."""
    return auth_service.refresh_access_token(db, payload.refresh_token)


@router.post("/api/v1/auth/logout", status_code=204)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Revokes one refresh token (this device/session). Does not invalidate
    an already-issued access token - see revoke_refresh_token's docstring."""
    auth_service.revoke_refresh_token(db, payload.refresh_token)
    return None


@router.post(
    "/api/v1/auth/password-reset/request",
    status_code=202,
    dependencies=[Depends(rate_limit("password_reset", max_attempts=5, window_seconds=3600))],
)
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    """Always returns the same generic response whether or not the email
    has an account - see auth_service.request_password_reset's docstring
    for why, and for the honest gap (no email provider wired up yet)."""
    auth_service.request_password_reset(db, payload.email)
    return {"detail": "If an account exists for that email, a reset link has been sent."}


@router.post("/api/v1/auth/password-reset/confirm", status_code=204)
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    auth_service.confirm_password_reset(db, payload.token, payload.new_password)
    return None


@router.get("/api/v1/auth/me", response_model=UserOut)
def read_profile(current_user: UserDB = Depends(auth_service.get_current_user)):
    return auth_service.user_to_out(current_user)


@router.put("/api/v1/auth/me", response_model=UserOut)
def update_profile(
    payload: UserProfileUpdate,
    current_user: UserDB = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """Partial update - only fields present in the request body are changed
    (see UserProfileUpdate's docstring). Saved here is what
    generate-workout/generate-program prefill from for this person going
    forward (see _apply_profile_defaults above)."""
    user = auth_service.update_profile(db, current_user, payload)
    return auth_service.user_to_out(user)


@router.delete("/api/v1/auth/me", status_code=204)
def delete_account(
    current_user: UserDB = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
):
    """Permanently deletes the caller's account and every row tied to it
    (session logs, custom workouts, saved programs, tokens) - see
    auth_service.delete_account's docstring. Irreversible; the frontend is
    expected to confirm with the person before ever calling this."""
    auth_service.delete_account(db, current_user)
    return None


# ==========================================
# 6. SESSION HISTORY / ADAPTIVE READINESS
# ==========================================
# athlete_id resolution: every route below (read, write, and delete) always
# resolves athlete_id = str(current_user.id) if current_user else "default" -
# a logged-in person can never read, write, or delete a DIFFERENT athlete_id
# just by passing one in the URL/body, and an anonymous caller can never
# supply an arbitrary athlete_id string either (always forced to "default").
# This used to be true only for GET/DELETE (see each route's own "Security
# note" below); create_session's POST body field was still trusted as-is for
# anonymous callers until this pass, letting an anonymous request inject
# fabricated session-log rows under someone else's real numeric user id -
# now fixed to resolve the exact same way as every other route here.


@router.post("/api/v1/sessions", response_model=SessionLogOut)
def create_session(
    payload: SessionLogCreate,
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(auth_service.get_current_user_optional),
):
    """Persist a completed session (prescribed exercises + logged sets +
    optional post-session soreness/fatigue self-report) to the database, so
    it survives across devices/browsers and feeds the next call to
    /api/v1/readiness/suggested. Sport-agnostic - any sport string the
    person was training that day is accepted as-is.

    Security note: same IDOR class as list_sessions/delete_session/
    get_suggested_readiness below, but on the write side - an anonymous
    caller's athlete_id body field was previously trusted as-is, so an
    unauthenticated request could pass any athlete_id string, including a
    real, guessable numeric user id, and inject fabricated session-log
    rows into that account's history (which then fed
    /api/v1/readiness/suggested for that athlete_id too). The other three
    routes already forced athlete_id to "default" for anonymous callers;
    this one didn't, because it only overrode athlete_id when
    current_user was not None and otherwise left the client-supplied value
    untouched. Fixed to resolve the same way on every request, matching
    the read/delete routes: a verified JWT can be the only source of a
    non-"default" athlete_id, full stop."""
    athlete_id = str(current_user.id) if current_user is not None else "default"
    payload = payload.model_copy(update={"athlete_id": athlete_id})
    row = readiness_service.create_session_log(db, payload)
    return SessionLogOut(**readiness_service.row_to_dict(row))


@router.get("/api/v1/sessions", response_model=List[SessionLogOut])
def list_sessions(
    athlete_id: str = "default",
    sport: str = "",
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(auth_service.get_current_user_optional),
):
    """Logged-session history, most recent first - what the History tab and
    Calendar render. Optional `sport` filter; `athlete_id` defaults to the
    single-person "default" for anonymous use, or the caller's own account
    when authenticated (see the resolution note above).

    Security note (fixed in the Phase-13 test-suite pass): an anonymous
    caller's athlete_id query param is now always forced to "default",
    never trusted as-is. Previously an unauthenticated request could pass
    any athlete_id string - including a real, guessable numeric user id -
    and read that account's private session history with no login at all
    (an IDOR / broken-access-control bug caught by
    tests/test_sessions_and_readiness.py). Only a verified JWT can ever
    resolve athlete_id to a real account id now."""
    athlete_id = str(current_user.id) if current_user is not None else "default"
    rows = readiness_service.list_session_logs(db, athlete_id=athlete_id, sport=sport or None, limit=limit)
    return [SessionLogOut(**readiness_service.row_to_dict(r)) for r in rows]


@router.delete("/api/v1/sessions/{session_id}")
def delete_session(
    session_id: int,
    athlete_id: str = "default",
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(auth_service.get_current_user_optional),
):
    """Delete one logged session permanently (mirrors the History tab's
    per-session delete button).

    Security note (fixed in the Phase-13 test-suite pass): same IDOR fix
    as list_sessions above - an anonymous caller's athlete_id query param
    is now always forced to "default" rather than trusted as-is, so an
    unauthenticated request can no longer delete another account's
    session by guessing/passing its numeric user id."""
    athlete_id = str(current_user.id) if current_user is not None else "default"
    ok = readiness_service.delete_session_log(db, athlete_id=athlete_id, session_id=session_id)
    if not ok:
        raise NotFoundError(f"No session with id {session_id} for athlete {athlete_id!r}.")
    return {"deleted": True, "id": session_id}


# ==========================================
# 6b. CUSTOM WORKOUT / SAVED PROGRAM SYNC
# ==========================================
# Same athlete_id resolution as the session-history routes above: a
# verified JWT is the only source of a non-"default" athlete_id, on every
# read/write/delete below - an anonymous caller can never read, write, or
# delete another athlete_id's saved workouts/programs just by passing one.
# Anonymous callers still get a working "default" bucket (matching
# session_logs' existing single-person-install behavior) rather than a
# 401, since the frontend calls these opportunistically alongside its own
# localStorage copy - see frontend/web/js/custom-workout-builder.js and
# program-wizard-steps.js.


@router.post("/api/v1/custom-workouts", response_model=CustomWorkoutOut)
def upsert_custom_workout(
    payload: CustomWorkoutCreate,
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(auth_service.get_current_user_optional),
):
    """Create or update (by the frontend's own `client_id`) a saved Custom
    Mode workout, so it follows the account across devices instead of
    living only in this browser's localStorage."""
    athlete_id = str(current_user.id) if current_user is not None else "default"
    row = sync_service.upsert_custom_workout(db, athlete_id, payload)
    return CustomWorkoutOut(**sync_service.custom_workout_to_dict(row))


@router.get("/api/v1/custom-workouts", response_model=List[CustomWorkoutOut])
def list_custom_workouts(
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(auth_service.get_current_user_optional),
):
    """Every saved Custom Mode workout for this athlete, most recently
    updated first - what Custom Mode's \"saved workouts\" list renders."""
    athlete_id = str(current_user.id) if current_user is not None else "default"
    rows = sync_service.list_custom_workouts(db, athlete_id)
    return [CustomWorkoutOut(**sync_service.custom_workout_to_dict(r)) for r in rows]


@router.delete("/api/v1/custom-workouts/{client_id}")
def delete_custom_workout(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(auth_service.get_current_user_optional),
):
    athlete_id = str(current_user.id) if current_user is not None else "default"
    ok = sync_service.delete_custom_workout(db, athlete_id, client_id)
    if not ok:
        raise NotFoundError(f"No custom workout {client_id!r} for athlete {athlete_id!r}.")
    return {"deleted": True, "client_id": client_id}


@router.post("/api/v1/programs", response_model=SavedProgramOut)
def upsert_saved_program(
    payload: SavedProgramCreate,
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(auth_service.get_current_user_optional),
):
    """Create or update (by `client_id`) a saved generated program - the
    Program Builder result was previously view-only per generation with
    nothing kept afterward; this lets a person keep one and pick it back
    up on another device."""
    athlete_id = str(current_user.id) if current_user is not None else "default"
    row = sync_service.upsert_saved_program(db, athlete_id, payload)
    return SavedProgramOut(**sync_service.saved_program_to_dict(row))


@router.get("/api/v1/programs", response_model=List[SavedProgramOut])
def list_saved_programs(
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(auth_service.get_current_user_optional),
):
    athlete_id = str(current_user.id) if current_user is not None else "default"
    rows = sync_service.list_saved_programs(db, athlete_id)
    return [SavedProgramOut(**sync_service.saved_program_to_dict(r)) for r in rows]


@router.delete("/api/v1/programs/{client_id}")
def delete_saved_program(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(auth_service.get_current_user_optional),
):
    athlete_id = str(current_user.id) if current_user is not None else "default"
    ok = sync_service.delete_saved_program(db, athlete_id, client_id)
    if not ok:
        raise NotFoundError(f"No saved program {client_id!r} for athlete {athlete_id!r}.")
    return {"deleted": True, "client_id": client_id}


@router.get("/api/v1/readiness/suggested", response_model=SuggestedReadinessOut)
def get_suggested_readiness(
    athlete_id: str = "default",
    sport: str = "",
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(auth_service.get_current_user_optional),
):
    """Starting-point readiness for the NEXT session, derived from recently
    logged soreness/fatigue - see readiness_service.compute_suggested_readiness
    for exactly how. Meant to pre-fill the wizard's readiness slider (still
    editable, never a silent override) - this is the piece that closes the
    loop from 'save a workout' to 'the next one accounts for how beat-up you
    actually are', without needing generate-workout/generate-program
    themselves to know anything about history.

    Security note (fixed in the Phase-13 test-suite pass): same IDOR fix
    as list_sessions/delete_session above - an anonymous caller's
    athlete_id query param is now always forced to "default" rather than
    trusted as-is, so an unauthenticated request can no longer read
    another account's derived readiness/soreness signal by guessing its
    numeric user id."""
    athlete_id = str(current_user.id) if current_user is not None else "default"
    return readiness_service.compute_suggested_readiness(db, athlete_id=athlete_id, sport=sport or None)


@router.get("/api/v1/recommendations/history")
def get_recommendation_history(
    sport: str = "",
    db: Session = Depends(get_db),
    current_user: UserDB = Depends(auth_service.get_current_user),
):
    """Phase 5 (roadmap): the raw per-exercise history signals (times
    logged, days since last logged, progression/plateau trend) generate-workout
    and generate-program already fold into their ranking as `personalization_note`
    on each prescribed exercise - exposed here directly so the frontend can
    show a standalone 'your training patterns' view without generating a
    fresh session. Requires login (this is personal history, not the
    generic metadata every other GET here returns for anyone)."""
    signals = build_history_signals(db, athlete_id=str(current_user.id), sport=sport or None)
    if not signals:
        return {
            "status": "success",
            "has_enough_history": False,
            "min_sessions_required": MIN_SESSIONS_FOR_SIGNAL,
            "exercises": {},
        }
    exercises = {}
    for ex_id, sig in signals.items():
        name = engine.exercises_by_id.get(ex_id, {}).get("name", ex_id)
        exercises[ex_id] = {"name": name, **sig}
    return {"status": "success", "has_enough_history": True, "exercises": exercises}

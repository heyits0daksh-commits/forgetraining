"""coach_notes.py — a deterministic, always-on "pro coach" summary.

WHY THIS EXISTS
`ai_hooks.py` already has a coach-note feature (`ai_insight`), but it's
LLM-backed: it does nothing unless a deployment sets `AI_FEATURES_ENABLED`
*and* pays for an Anthropic/NVIDIA key, and even then it isn't wired into
the frontend anywhere. That means the actual product, out of the box,
never shows anyone a coach's read on their session even though the engine
already computes everything a coach's explanation would draw on -
`sport_priority_score`, `sport_transfer_rationale`,
`programming_role_rationale`, `CNS_fatigue`, deload/readiness state, the
level-check, the progression roadmap.

This module turns that already-computed data into a short, structured,
rule-based summary - no network call, no API key, no failure mode beyond
"the fields it reads weren't there" (handled by treating everything as
optional). It runs for every session/program, every deployment, always.
It is *not* a replacement for `ai_insight` - a real LLM note can say
things this can't - it's the free floor everyone gets whether or not
`ai_insight` is configured. Both keys can be present on the same response;
they serve different jobs (`coach_notes` = grounded/deterministic,
`ai_insight` = free-text/optional).

Same read-only-in-spirit contract as SessionContext/ProgramContext in
ai_hooks.py: this only describes an already-finalized session or program,
never influences exercise selection.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _first_sentence(text: Optional[str], max_chars: int = 140) -> str:
    """Trims a rationale string (e.g. sport_transfer_rationale, which can
    run to 2-3 sentences of dense scoring detail) down to something that
    reads like a coach's one-line explanation rather than a data dump."""
    if not text:
        return ""
    sentence = text.split(". ")[0].strip()
    if not sentence.endswith("."):
        sentence += "."
    if len(sentence) > max_chars:
        sentence = sentence[: max_chars - 1].rsplit(" ", 1)[0] + "…"
    return sentence


def _dominant_role(prescribed_exercises: List[Dict[str, Any]]) -> Optional[str]:
    """The programming_role with the most total CNS_fatigue in the
    session - a better "what is today actually built around" signal than
    just counting exercises per role, since one heavy Primary Strength
    lift can carry more of the session's identity than three light
    Accessory ones."""
    load_by_role: Dict[str, float] = {}
    for ex in prescribed_exercises:
        role = ex.get("programming_role")
        if not role:
            continue
        load_by_role[role] = load_by_role.get(role, 0.0) + float(ex.get("CNS_fatigue") or 0)
    if not load_by_role:
        return None
    return max(load_by_role, key=load_by_role.get)


def build_coach_notes(
    *,
    sport: Optional[str],
    session_duration_minutes: Optional[int],
    prescribed_exercises: List[Dict[str, Any]],
    deload_mode: bool = False,
    readiness_factor: float = 1.0,
    recovery: Optional[Dict[str, Any]] = None,
    level_check_result: Optional[Dict[str, Any]] = None,
    injury_cautions: Optional[List[str]] = None,
    progression_roadmap: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Builds the `coach_notes` block attached to a generate_session
    response. Returns None only if there's nothing to summarize (an empty
    session - e.g. every candidate got excluded), so callers can attach it
    unconditionally, the same `if result is not None: response[...] = ...`
    pattern ai_hooks.py already uses.
    """
    if not prescribed_exercises:
        return None

    recovery = recovery or {}
    injury_cautions = injury_cautions or []
    progression_roadmap = progression_roadmap or []

    # --- headline -----------------------------------------------------
    role = _dominant_role(prescribed_exercises)
    sport_label = sport or "General Fitness"
    duration_label = f"{session_duration_minutes}-min " if session_duration_minutes else ""
    if role:
        headline = f"{duration_label}{sport_label} session — built around {role}"
    else:
        headline = f"{duration_label}{sport_label} session"

    # --- key lifts: the 2-3 highest sport_priority_score exercises, ---
    # each with its own rationale trimmed to a coach-length line
    ranked = sorted(
        prescribed_exercises,
        key=lambda e: e.get("sport_priority_score", 0),
        reverse=True,
    )
    key_lifts = []
    for ex in ranked[:3]:
        rationale = _first_sentence(
            ex.get("sport_transfer_rationale") or ex.get("programming_role_rationale")
        )
        key_lifts.append({
            "name": ex.get("name"),
            "role": ex.get("programming_role"),
            "why": rationale,
        })

    # --- watch_for: anything a coach would flag before the athlete ----
    # starts, ordered roughly by how much it should change their approach
    # today (deload/readiness first, since those affect every exercise;
    # injury/level notes are exercise- or athlete-specific, so last)
    watch_for: List[str] = []
    if deload_mode:
        watch_for.append(
            "This is a deload week — intensity and volume are intentionally "
            "pulled back. Don't chase extra sets or add weight just because "
            "it feels easy."
        )
    elif readiness_factor < 0.85:
        watch_for.append(
            "Readiness is running lower than usual — today's loads are already "
            "trimmed to match. Treat any prescribed weight as a ceiling, not a target."
        )
    if recovery.get("poor_sleep"):
        watch_for.append("Sleep has been poor recently — expect bar speed and focus to lag a bit.")
    if recovery.get("high_soreness"):
        watch_for.append("Soreness is elevated — warm up longer than usual before the first working set.")
    if recovery.get("high_stress"):
        watch_for.append("Reported stress is high — this is a fine day to leave a rep or two in the tank.")
    for caution in injury_cautions[:2]:
        watch_for.append(caution)
    if level_check_result and level_check_result.get("agrees") is False:
        note = level_check_result.get("note")
        if note:
            watch_for.append(note)

    # --- coach_tip: one forward-looking line -------------------------
    if progression_roadmap:
        nearest = progression_roadmap[0]
        name = nearest.get("name") or nearest.get("id")
        next_step = nearest.get("next_step")
        if next_step:
            coach_tip = f"Longer-term: {next_step} to unlock '{name}'."
        else:
            coach_tip = f"Longer-term: keep building toward '{name}' — it's close on strength alone."
    elif deload_mode:
        coach_tip = "Come out of this week ready to push loads again — that's the point of the deload."
    else:
        coach_tip = "Run this again next week and nudge the numbers up on anything that felt clean today."

    return {
        "headline": headline,
        "key_lifts": key_lifts,
        "watch_for": watch_for,
        "coach_tip": coach_tip,
    }


def build_program_coach_notes(
    *,
    sport: Optional[str],
    primary_goal: str,
    weeks: int,
    days_per_week: int,
    split_name: str,
    periodization_model: str,
    experience_level: Optional[str],
    under_trained_muscles: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Program-level equivalent of build_coach_notes - a short deterministic
    read on the mesocycle as a whole, built from generate_program's own
    already-computed summary fields (same "read from what's already there,
    nothing re-derived" rule as the session version)."""
    sport_label = sport or primary_goal
    headline = f"{weeks}-week {split_name} — {days_per_week}x/week, {periodization_model.lower()}"

    watch_for: List[str] = []
    under_trained_muscles = under_trained_muscles or []
    if under_trained_muscles:
        shown = ", ".join(under_trained_muscles[:3])
        watch_for.append(
            f"This split is naturally light on {shown} — worth adding a set or "
            "two of direct work there if that's a priority for you."
        )

    coach_tip = (
        f"Stick with this exactly as written for the full {weeks} weeks before judging it — "
        "consistency is what makes the periodization model actually work."
    )

    return {
        "headline": headline,
        "watch_for": watch_for,
        "coach_tip": coach_tip,
    }

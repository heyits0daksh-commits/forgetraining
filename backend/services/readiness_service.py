"""
Session-history persistence + the adaptive-readiness algorithm.

This is what makes "save a workout, then have the next one account for how
beat-up/fresh you actually are" real: every completed session is written to
the database (backend/models/db_models.py) with an optional post-session
soreness/fatigue self-report, and compute_suggested_readiness() turns recent
history into a starting-point readiness score for the *next* session -
surfaced via GET /api/v1/readiness/suggested and meant to pre-fill (not
silently replace) the readiness slider the person already controls.

The algorithm is a deliberately simple, explainable heuristic - not a
trained model - so every number it produces can be justified in one sentence
to the person looking at it:

  1. Start from how sore/fatigued the most recent relevant session left them
     (their own post-session self-report - the actual ground truth signal).
  2. Blend in how many days have passed since then (recovery accrues with
     rest; a soreness-5 session two days ago is a different situation than a
     soreness-5 session logged an hour ago).
  3. If soreness/fatigue has been trending worse over the last few sessions
     (accumulating fatigue instead of dissipating between them), nudge the
     suggestion down further and flag it - a coach would notice that pattern
     before any single day's number looks alarming on its own.
"""
import json
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.models.db_models import SessionLogDB
from backend.models.schemas import SessionLogCreate, SuggestedReadinessOut
from backend.repositories.session_log_repository import SessionLogRepository


def create_session_log(db: Session, payload: SessionLogCreate) -> SessionLogDB:
    row = SessionLogDB(
        athlete_id=payload.athlete_id,
        date=payload.date or datetime.now(timezone.utc),
        sport=payload.sport,
        program_label=payload.program_label,
        deload_mode=payload.deload_mode,
        prescribed_count=payload.prescribed_count,
        readiness_used=payload.readiness_used,
        post_soreness=payload.post_soreness,
        post_fatigue=payload.post_fatigue,
        rpe=payload.rpe,
        notes=payload.notes,
        exercises_json=json.dumps(payload.exercises),
        log_json=json.dumps(payload.log),
    )
    return SessionLogRepository(db).create(row)


def list_session_logs(
    db: Session, athlete_id: str = "default", sport: Optional[str] = None, limit: int = 200
) -> List[SessionLogDB]:
    return SessionLogRepository(db).list_for_athlete(athlete_id, sport=sport, limit=limit)


def delete_session_log(db: Session, athlete_id: str, session_id: int) -> bool:
    return SessionLogRepository(db).delete_for_athlete(athlete_id, session_id)


def row_to_dict(row: SessionLogDB) -> dict:
    return {
        "id": row.id,
        "athlete_id": row.athlete_id,
        "date": row.date,
        "sport": row.sport,
        "program_label": row.program_label,
        "deload_mode": row.deload_mode,
        "prescribed_count": row.prescribed_count,
        "readiness_used": row.readiness_used,
        "post_soreness": row.post_soreness,
        "post_fatigue": row.post_fatigue,
        "rpe": row.rpe,
        "notes": row.notes,
        "exercises": json.loads(row.exercises_json or "[]"),
        "log": json.loads(row.log_json or "[]"),
    }


# --- Adaptive readiness ------------------------------------------------

_DEFAULT_SUGGESTION = 80  # matches WorkoutRequest/ProgramRequest's own default


def compute_suggested_readiness(
    db: Session, athlete_id: str = "default", sport: Optional[str] = None
) -> SuggestedReadinessOut:
    # Sport-specific history first (soreness from a heavy Judo grip session
    # says more about tomorrow's Judo readiness than a generic average
    # would), falling back to all-sport history if there isn't enough of it
    # yet, so a brand-new sport doesn't return "no_history" just because
    # every OTHER sport has logs.
    rows = list_session_logs(db, athlete_id=athlete_id, sport=sport, limit=10)
    if len(rows) < 2 and sport:
        rows = list_session_logs(db, athlete_id=athlete_id, sport=None, limit=10)

    reported = [r for r in rows if r.post_soreness is not None or r.post_fatigue is not None]
    if not reported:
        return SuggestedReadinessOut(
            suggested_readiness=_DEFAULT_SUGGESTION,
            basis="no_history",
            sessions_considered=0,
            explanation=(
                "No logged soreness/fatigue history yet - using the default starting "
                f"readiness of {_DEFAULT_SUGGESTION}%. Log how you felt after your next "
                "session to start getting a real suggestion."
            ),
        )

    last = reported[0]  # most recent (rows already ordered desc by date)
    now = datetime.now(timezone.utc)
    last_date = last.date if last.date.tzinfo else last.date.replace(tzinfo=timezone.utc)
    days_since = max(0, (now - last_date).days)

    soreness_score = (5 - last.post_soreness) / 4 * 100 if last.post_soreness is not None else 75.0
    fatigue_score = (5 - last.post_fatigue) / 4 * 100 if last.post_fatigue is not None else 75.0
    last_session_score = (soreness_score + fatigue_score) / 2

    # Recovery-from-rest curve: same-day ~55, 1 day off ~77, 2+ days off caps
    # near full. Deliberately conservative early (soreness doesn't vanish
    # overnight) and flattens out rather than climbing forever.
    recovery_from_rest = min(100.0, 55 + days_since * 22)

    # Weight the person's own most recent self-report more heavily than the
    # generic rest-curve - it's real signal, the curve is just a fallback
    # shape for when they haven't told us anything more specific.
    blended = 0.65 * last_session_score + 0.35 * recovery_from_rest

    # Trend check across up to the last 3 reported sessions: is soreness
    # accumulating rather than clearing between sessions?
    soreness_trend = [r.post_soreness for r in reported[:3] if r.post_soreness is not None]
    trending_worse = len(soreness_trend) >= 2 and soreness_trend[0] > soreness_trend[-1]
    if trending_worse:
        blended -= 10

    suggested = round(max(1.0, min(100.0, blended)))
    recommend_deload = suggested < 40 or (last.post_soreness == 5) or (last.post_fatigue == 5)

    parts = [f"Based on your last {len(reported)} logged session(s)"]
    if sport and any(r.sport == sport for r in reported):
        parts[0] += f" for {sport}"
    parts.append(f"most recent was {days_since} day(s) ago")
    if last.post_soreness is not None:
        parts.append(f"soreness {last.post_soreness}/5")
    if last.post_fatigue is not None:
        parts.append(f"fatigue {last.post_fatigue}/5")
    explanation = ", ".join(parts) + "."
    if trending_worse:
        explanation += " Soreness has been trending up across recent sessions - dialing this back further."
    if recommend_deload:
        explanation += " This suggests a lighter session or deload today."

    return SuggestedReadinessOut(
        suggested_readiness=suggested,
        basis="history",
        sessions_considered=len(reported),
        days_since_last_session=days_since,
        trending_worse=trending_worse,
        recommend_deload=recommend_deload,
        explanation=explanation,
    )

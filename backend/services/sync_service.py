"""
Server-side sync for the two pieces of FORGE state that were still
localStorage-only after the Phase 6 accounts pass: Custom Mode workouts
(backend/models/db_models.py's CustomWorkoutDB) and generated programs
someone chose to keep (SavedProgramDB). Same shape as
readiness_service.py's session-log functions - upsert/list/delete plus a
row_to_dict for the JSON-blob columns - just doubled up for two tables
instead of one, since both follow the identical
upsert-on-(athlete_id, client_id) pattern.
"""
import json
from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from backend.models.db_models import CustomWorkoutDB, SavedProgramDB
from backend.models.schemas import CustomWorkoutCreate, SavedProgramCreate
from backend.repositories.custom_workout_repository import CustomWorkoutRepository
from backend.repositories.saved_program_repository import SavedProgramRepository


# --- Custom workouts ----------------------------------------------------

def upsert_custom_workout(db: Session, athlete_id: str, payload: CustomWorkoutCreate) -> CustomWorkoutDB:
    return CustomWorkoutRepository(db).upsert(
        athlete_id,
        payload.client_id,
        name=payload.name,
        sport=payload.sport,
        experience=payload.experience,
        exercises_json=json.dumps(payload.exercises),
        groups_json=json.dumps(payload.groups),
        group_order_json=json.dumps(payload.group_order),
        warmup_json=json.dumps(payload.warmup),
        updated_at=datetime.now(timezone.utc),
    )


def list_custom_workouts(db: Session, athlete_id: str) -> List[CustomWorkoutDB]:
    return CustomWorkoutRepository(db).list_for_athlete(athlete_id)


def delete_custom_workout(db: Session, athlete_id: str, client_id: str) -> bool:
    return CustomWorkoutRepository(db).delete_for_athlete(athlete_id, client_id)


def custom_workout_to_dict(row: CustomWorkoutDB) -> dict:
    return {
        "id": row.id,
        "client_id": row.client_id,
        "name": row.name,
        "sport": row.sport,
        "experience": row.experience,
        "exercises": json.loads(row.exercises_json or "[]"),
        "groups": json.loads(row.groups_json or "{}"),
        "group_order": json.loads(row.group_order_json or "[]"),
        "warmup": json.loads(row.warmup_json or "[]"),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


# --- Saved programs -------------------------------------------------------

def upsert_saved_program(db: Session, athlete_id: str, payload: SavedProgramCreate) -> SavedProgramDB:
    return SavedProgramRepository(db).upsert(
        athlete_id,
        payload.client_id,
        label=payload.label,
        sport=payload.sport,
        experience_level=payload.experience_level,
        weeks=payload.weeks,
        days_per_week=payload.days_per_week,
        program_json=json.dumps(payload.program),
        updated_at=datetime.now(timezone.utc),
    )


def list_saved_programs(db: Session, athlete_id: str) -> List[SavedProgramDB]:
    return SavedProgramRepository(db).list_for_athlete(athlete_id)


def delete_saved_program(db: Session, athlete_id: str, client_id: str) -> bool:
    return SavedProgramRepository(db).delete_for_athlete(athlete_id, client_id)


def saved_program_to_dict(row: SavedProgramDB) -> dict:
    return {
        "id": row.id,
        "client_id": row.client_id,
        "label": row.label,
        "sport": row.sport,
        "experience_level": row.experience_level,
        "weeks": row.weeks,
        "days_per_week": row.days_per_week,
        "program": json.loads(row.program_json or "{}"),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }

"""
Repository for CustomWorkoutDB. Same shape as session_log_repository.py,
plus upsert-on-(athlete_id, client_id) since a saved custom workout is
edited in place from the frontend (see CustomWorkoutDB's docstring) rather
than only ever appended to like a session log.
"""
from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.models.db_models import CustomWorkoutDB


class CustomWorkoutRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_client_id(self, athlete_id: str, client_id: str) -> Optional[CustomWorkoutDB]:
        return (
            self.db.query(CustomWorkoutDB)
            .filter(CustomWorkoutDB.athlete_id == athlete_id, CustomWorkoutDB.client_id == client_id)
            .first()
        )

    def upsert(self, athlete_id: str, client_id: str, **fields) -> CustomWorkoutDB:
        row = self.get_by_client_id(athlete_id, client_id)
        if row is None:
            row = CustomWorkoutDB(athlete_id=athlete_id, client_id=client_id)
            self.db.add(row)
        for k, v in fields.items():
            setattr(row, k, v)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_for_athlete(self, athlete_id: str) -> List[CustomWorkoutDB]:
        return (
            self.db.query(CustomWorkoutDB)
            .filter(CustomWorkoutDB.athlete_id == athlete_id)
            .order_by(desc(CustomWorkoutDB.updated_at))
            .all()
        )

    def delete_for_athlete(self, athlete_id: str, client_id: str) -> bool:
        row = self.get_by_client_id(athlete_id, client_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

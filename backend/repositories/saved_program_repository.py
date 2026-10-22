"""
Repository for SavedProgramDB. Same upsert-on-(athlete_id, client_id)
shape as custom_workout_repository.py - see that module's docstring.
"""
from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.models.db_models import SavedProgramDB


class SavedProgramRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_client_id(self, athlete_id: str, client_id: str) -> Optional[SavedProgramDB]:
        return (
            self.db.query(SavedProgramDB)
            .filter(SavedProgramDB.athlete_id == athlete_id, SavedProgramDB.client_id == client_id)
            .first()
        )

    def upsert(self, athlete_id: str, client_id: str, **fields) -> SavedProgramDB:
        row = self.get_by_client_id(athlete_id, client_id)
        if row is None:
            row = SavedProgramDB(athlete_id=athlete_id, client_id=client_id)
            self.db.add(row)
        for k, v in fields.items():
            setattr(row, k, v)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_for_athlete(self, athlete_id: str) -> List[SavedProgramDB]:
        return (
            self.db.query(SavedProgramDB)
            .filter(SavedProgramDB.athlete_id == athlete_id)
            .order_by(desc(SavedProgramDB.updated_at))
            .all()
        )

    def delete_for_athlete(self, athlete_id: str, client_id: str) -> bool:
        row = self.get_by_client_id(athlete_id, client_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

"""
Repository for SessionLogDB.

Every method here is a straight extraction of a query that used to live
inline in backend/services/readiness_service.py - same filters, same
ordering, same commit points. No behavior change; this pass only gives
those queries a name and a home.
"""
from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.models.db_models import SessionLogDB


class SessionLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, row: SessionLogDB) -> SessionLogDB:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_for_athlete(
        self, athlete_id: str, sport: Optional[str] = None, limit: int = 200
    ) -> List[SessionLogDB]:
        q = self.db.query(SessionLogDB).filter(SessionLogDB.athlete_id == athlete_id)
        if sport:
            q = q.filter(SessionLogDB.sport == sport)
        return q.order_by(desc(SessionLogDB.date)).limit(limit).all()

    def delete_for_athlete(self, athlete_id: str, session_id: int) -> bool:
        row = (
            self.db.query(SessionLogDB)
            .filter(SessionLogDB.athlete_id == athlete_id, SessionLogDB.id == session_id)
            .first()
        )
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

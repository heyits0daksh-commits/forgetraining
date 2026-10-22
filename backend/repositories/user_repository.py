"""
Repository for UserDB.

Extraction of every db.query(UserDB...) call that used to live inline in
backend/services/auth_service.py - same filters, same commit points.
"""
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.db_models import UserDB


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> Optional[UserDB]:
        return self.db.query(UserDB).filter(UserDB.email == email).first()

    def get_by_id(self, user_id: int) -> Optional[UserDB]:
        return self.db.query(UserDB).filter(UserDB.id == user_id).first()

    def create(self, user: UserDB) -> UserDB:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def save(self, user: UserDB) -> UserDB:
        """Persists changes to an already-loaded, already-mutated row
        (profile updates) - same add/commit/refresh shape as create(),
        just named for the "update an existing row" call site so it
        reads correctly there. Only used where the write stands alone as
        its own transaction - see auth_service.confirm_password_reset for
        the one case that composes a user-row change with other writes
        into a single transaction instead, which calls db.add(user)
        directly rather than through this method, precisely so it can
        share one commit with those other writes."""
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

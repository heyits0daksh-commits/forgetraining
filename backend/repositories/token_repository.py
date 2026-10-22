"""
Repositories for RefreshTokenDB and PasswordResetTokenDB.

Extraction of every db.query(...TokenDB...) call that used to live inline
in backend/services/auth_service.py. One method - revoke_all_for_user -
deliberately does NOT commit; see its docstring for why.
"""
from typing import Optional

from sqlalchemy.orm import Session

from backend.models.db_models import PasswordResetTokenDB, RefreshTokenDB


class RefreshTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, row: RefreshTokenDB) -> RefreshTokenDB:
        self.db.add(row)
        self.db.commit()
        return row

    def get_by_hash(self, token_hash: str) -> Optional[RefreshTokenDB]:
        return self.db.query(RefreshTokenDB).filter(RefreshTokenDB.token_hash == token_hash).first()

    def revoke(self, row: RefreshTokenDB) -> None:
        """Revokes one token and commits immediately - for standalone
        single-token revocation (logout; rotating out the old token
        during a refresh)."""
        row.revoked = True
        self.db.add(row)
        self.db.commit()

    def revoke_all_for_user(self, user_id: int) -> None:
        """Bulk-revokes every non-revoked refresh token for a user, WITHOUT
        committing - auth_service.confirm_password_reset calls this
        alongside its own password-hash change and commits both together
        in one transaction (a password reset revoking sessions is one
        atomic action, not two - if the commit failed partway, we don't
        want a reset password with the old sessions still valid, or vice
        versa)."""
        self.db.query(RefreshTokenDB).filter(
            RefreshTokenDB.user_id == user_id, RefreshTokenDB.revoked.is_(False)
        ).update({"revoked": True})


class PasswordResetTokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, row: PasswordResetTokenDB) -> PasswordResetTokenDB:
        self.db.add(row)
        self.db.commit()
        return row

    def get_by_hash(self, token_hash: str) -> Optional[PasswordResetTokenDB]:
        return self.db.query(PasswordResetTokenDB).filter(PasswordResetTokenDB.token_hash == token_hash).first()

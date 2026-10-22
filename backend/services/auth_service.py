"""
User registration/authentication + the FastAPI dependencies that resolve a
request's Authorization header into a UserDB row (Phase 6).

Two dependencies are exported, for two different situations:
  - get_current_user: for routes that REQUIRE an account (profile read/update).
    Raises 401 if there's no valid token.
  - get_current_user_optional: for routes that predate accounts and must keep
    working without one (session logs, readiness suggestion, workout/program
    generation) - returns None instead of raising, so an anonymous request
    behaves exactly as it did before this pass, while an authenticated
    request gets personalized automatically.
"""
import json
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.exceptions import BadRequestError, UnauthorizedError
from backend.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)
from backend.models.db_models import PasswordResetTokenDB, RefreshTokenDB, UserDB
from backend.models.schemas import Token, UserCreate, UserOut, UserProfileUpdate
from backend.repositories.token_repository import PasswordResetTokenRepository, RefreshTokenRepository
from backend.repositories.user_repository import UserRepository

# tokenUrl is documentation-only here (points Swagger's "Authorize" button at
# the right route) - login itself takes a JSON body (UserLogin), not the
# OAuth2 form-encoded username/password this class is normally paired with,
# since every other endpoint in this API is JSON and the frontend is plain
# fetch(), not an OAuth client.
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)


class EmailAlreadyRegistered(Exception):
    pass


def get_user_by_email(db: Session, email: str) -> Optional[UserDB]:
    return UserRepository(db).get_by_email(email)


def get_user_by_id(db: Session, user_id: int) -> Optional[UserDB]:
    return UserRepository(db).get_by_id(user_id)


def register_user(db: Session, payload: UserCreate) -> UserDB:
    if get_user_by_email(db, payload.email) is not None:
        raise EmailAlreadyRegistered(payload.email)
    # payload.accepted_terms is already guaranteed True here (UserCreate's
    # own validator rejects False/missing before this function ever runs) -
    # this just turns that boolean into the actual consent record.
    user = UserDB(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name,
        terms_accepted_at=datetime.now(timezone.utc),
    )
    return UserRepository(db).create(user)


def authenticate_user(db: Session, email: str, password: str) -> Optional[UserDB]:
    user = get_user_by_email(db, email.strip().lower())
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def update_profile(db: Session, user: UserDB, payload: UserProfileUpdate) -> UserDB:
    data = payload.model_dump(exclude_unset=True)
    # health_data_consent is a control flag, not a stored profile field -
    # pop it up front so it never falls through to the generic
    # setattr loop below (there's no such column on UserDB).
    consent_sent = data.pop("health_data_consent", None)
    if "equipment" in data:
        user.equipment_json = json.dumps(data.pop("equipment") or [])
    if "injuries" in data:
        new_injuries = data.pop("injuries") or []
        if new_injuries:
            # Saving a NON-EMPTY injuries list requires explicit consent to
            # process that health data - either given in this same request
            # (consent_sent is True) or already on file from a previous
            # request. Clearing the list back to [] never requires consent.
            if consent_sent is not True and user.health_data_consent_at is None:
                raise BadRequestError(
                    "Saving injury/condition information requires consent "
                    "to process health data (set health_data_consent: true)."
                )
            if consent_sent is True:
                user.health_data_consent_at = datetime.now(timezone.utc)
        user.injuries_json = json.dumps(new_injuries)
    for field, value in data.items():
        setattr(user, field, value)
    return UserRepository(db).save(user)


def user_to_out(user: UserDB) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        primary_sport=user.primary_sport,
        experience_level=user.experience_level,
        equipment=_safe_json_list(user.equipment_json),
        injuries=_safe_json_list(user.injuries_json),
        created_at=user.created_at,
        health_data_consent_given=user.health_data_consent_at is not None,
    )


def delete_account(db: Session, user: UserDB) -> None:
    """Permanently deletes this account and everything tied to it (GDPR-
    style "right to erasure" - see privacy.html's "Your Choices" section).
    Cascades across every table that references this person, in an order
    that respects foreign keys (tokens first, since RefreshTokenDB/
    PasswordResetTokenDB have a real FK to users.id; the JSON-blob tables
    use the string athlete_id convention - see their docstrings in
    db_models.py - so they're matched on str(user.id) instead), then the
    user row itself, all in one transaction.
    """
    from backend.models.db_models import CustomWorkoutDB, SavedProgramDB, SessionLogDB

    athlete_id = str(user.id)
    db.query(RefreshTokenDB).filter(RefreshTokenDB.user_id == user.id).delete()
    db.query(PasswordResetTokenDB).filter(PasswordResetTokenDB.user_id == user.id).delete()
    db.query(SessionLogDB).filter(SessionLogDB.athlete_id == athlete_id).delete()
    db.query(CustomWorkoutDB).filter(CustomWorkoutDB.athlete_id == athlete_id).delete()
    db.query(SavedProgramDB).filter(SavedProgramDB.athlete_id == athlete_id).delete()
    db.delete(user)
    db.commit()


def _safe_json_list(raw: str) -> List[str]:
    try:
        value = json.loads(raw or "[]")
        return value if isinstance(value, list) else []
    except (TypeError, ValueError):
        return []


def _issue_refresh_token(db: Session, user: UserDB) -> str:
    """Creates a new opaque refresh token, stores its hash, and returns the
    raw token (only time the raw value exists outside the client)."""
    raw = generate_opaque_token()
    row = RefreshTokenDB(
        user_id=user.id,
        token_hash=hash_opaque_token(raw),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    RefreshTokenRepository(db).create(row)
    return raw


def issue_token(user: UserDB, db: Session) -> Token:
    """Issues both halves of a login response: a short-lived JWT access
    token (sent on every request) and a long-lived, revocable refresh token
    (sent only to /auth/refresh - see _issue_refresh_token / refresh_access_token)."""
    return Token(
        access_token=create_access_token(subject=str(user.id)),
        refresh_token=_issue_refresh_token(db, user),
        user=user_to_out(user),
    )


def refresh_access_token(db: Session, raw_refresh_token: str) -> Token:
    """Validates a refresh token, rotates it (issues a new one and revokes
    the old), and returns a fresh access token alongside it. Rotation means
    a stolen-and-reused refresh token is only usable once before the
    legitimate holder's next refresh invalidates it."""
    token_hash = hash_opaque_token(raw_refresh_token)
    refresh_repo = RefreshTokenRepository(db)
    row = refresh_repo.get_by_hash(token_hash)
    now = datetime.now(timezone.utc)
    if row is None or row.revoked or row.expires_at.replace(tzinfo=timezone.utc) < now:
        raise UnauthorizedError("Invalid or expired refresh token. Please log in again.")
    user = get_user_by_id(db, row.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Account no longer available.")
    refresh_repo.revoke(row)
    return issue_token(user, db)


def revoke_refresh_token(db: Session, raw_refresh_token: str) -> None:
    """Logout: revokes one refresh token so it can no longer be used to
    mint new access tokens. The already-issued access token (if any) still
    works until its own short expiry - this app has no access-token
    blacklist, which is an accepted tradeoff given how short-lived access
    tokens now are (settings.ACCESS_TOKEN_EXPIRE_MINUTES)."""
    token_hash = hash_opaque_token(raw_refresh_token)
    refresh_repo = RefreshTokenRepository(db)
    row = refresh_repo.get_by_hash(token_hash)
    if row is not None:
        refresh_repo.revoke(row)


def request_password_reset(db: Session, email: str) -> None:
    """Generates a reset token if the email matches an account, does
    nothing (but still returns normally) if it doesn't - the route layer
    always replies with the same generic message either way, so this can't
    be used to enumerate which emails have accounts.

    NOTE - honest gap: this repo has no outbound email provider wired up
    (no SMTP/SES/SendGrid config anywhere in requirements.txt or
    config.py), so there's nowhere to actually send the reset link yet.
    Until that's wired in, the token is logged server-side only (never
    returned in the API response - that WOULD be a real vulnerability,
    handing out a password-reset credential to anyone who requests one).
    Wiring a real provider here is a self-contained follow-up: generate the
    token below, then replace the `print` with your provider's send call.
    """
    user = get_user_by_email(db, email.strip().lower())
    if user is None:
        return
    raw = generate_opaque_token()
    row = PasswordResetTokenDB(
        user_id=user.id,
        token_hash=hash_opaque_token(raw),
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    )
    PasswordResetTokenRepository(db).create(row)
    # Placeholder for real email delivery - see docstring above.
    print(f"[password-reset] token for user_id={user.id}: {raw} (expires in "
          f"{settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES}m) - wire this to a "
          f"real email provider before shipping.")


def confirm_password_reset(db: Session, raw_token: str, new_password: str) -> None:
    reset_repo = PasswordResetTokenRepository(db)
    refresh_repo = RefreshTokenRepository(db)
    token_hash = hash_opaque_token(raw_token)
    row = reset_repo.get_by_hash(token_hash)
    now = datetime.now(timezone.utc)
    if row is None or row.used or row.expires_at.replace(tzinfo=timezone.utc) < now:
        raise BadRequestError("Invalid or expired reset token.")
    user = get_user_by_id(db, row.user_id)
    if user is None:
        raise BadRequestError("Invalid or expired reset token.")
    user.hashed_password = hash_password(new_password)
    row.used = True
    db.add(user)
    db.add(row)
    # Revoke every outstanding refresh token on password reset - a
    # password change should log out every other session, since the
    # threat model for "I'm resetting my password" often includes "I think
    # someone else has access". Deliberately NOT committed inside
    # revoke_all_for_user itself - see that method's docstring: this needs
    # to land in the same transaction as the password-hash change above.
    refresh_repo.revoke_all_for_user(user.id)
    db.commit()


def _resolve_user_from_token(token: Optional[str], db: Session) -> Optional[UserDB]:
    if not token:
        return None
    try:
        claims = decode_access_token(token)
    except TokenError:
        return None
    user_id = claims.get("sub")
    if user_id is None:
        return None
    try:
        user = get_user_by_id(db, int(user_id))
    except (TypeError, ValueError):
        return None
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(
    token: Optional[str] = Depends(_oauth2_scheme), db: Session = Depends(get_db)
) -> UserDB:
    user = _resolve_user_from_token(token, db)
    if user is None:
        raise UnauthorizedError(
            "Invalid or expired credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user_optional(
    token: Optional[str] = Depends(_oauth2_scheme), db: Session = Depends(get_db)
) -> Optional[UserDB]:
    return _resolve_user_from_token(token, db)

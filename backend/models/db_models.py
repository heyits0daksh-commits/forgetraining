"""
ORM models for the persistence layer (backend/core/database.py).

Two tables: UserDB (Phase 6 - persistent user profiles/auth) and
SessionLogDB (Phase 4's first slice - training-session history). Exercise/set
detail on SessionLogDB is stored as JSON text columns rather than being fully
normalized into their own tables - the frontend already treats a logged
session as one JSON-shaped blob (see frontend/web/index.html's `record`
object in saveProgramDay/btnSaveSession), and the only fields the
adaptive-readiness algorithm actually needs to query on are the scalar ones
(date, sport, soreness, fatigue) - so normalizing the exercise list into rows
would add real complexity for no query benefit right now. Worth revisiting
if/when there's a feature that needs to query *inside* the exercise list
server-side (e.g. "show me every session that logged a Back Squat PR").
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text

from backend.core.database import Base


class UserDB(Base):
    """A registered account. `equipment_json`/`injuries_json` mirror the
    same JSON-blob-column approach as SessionLogDB above (the wizard already
    treats these as lists of strings/ids, and nothing server-side needs to
    query *inside* them yet - only ever reads the whole list back out to
    prefill a request). SessionLogDB.athlete_id is left as a plain string
    column (not a real foreign key) deliberately - it already accepted
    arbitrary athlete-id strings before accounts existed (default "default"),
    so an authenticated request just starts sending str(user.id) as that
    string instead; anonymous/no-account usage of the session-log endpoints
    keeps working exactly as before."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Profile defaults - used to prefill generate-workout/generate-program
    # requests for a logged-in person who doesn't explicitly override them
    # (see main.py's generate_workout/generate_program_endpoint).
    primary_sport = Column(String, nullable=True)
    experience_level = Column(String, nullable=True)
    equipment_json = Column(Text, nullable=False, default="[]")
    injuries_json = Column(Text, nullable=False, default="[]")

    # Consent tracking (worldwide-launch / GDPR-style compliance - see
    # migrations/versions/m0003_consent_tracking.py). Presence of a
    # timestamp IS the consent record: `terms_accepted_at` is set once,
    # at registration, when the account-creation checkbox (Terms of
    # Service + Privacy Policy + Medical Disclaimer) is accepted -
    # registration is rejected if it isn't. `health_data_consent_at` is
    # set whenever the person explicitly consents to FORGE processing
    # injury/health information they report (self-reported condition
    # data is treated as sensitive - see privacy.html); nullable because
    # a user who never reports any injuries never needs to give it.
    terms_accepted_at = Column(DateTime, nullable=True)
    health_data_consent_at = Column(DateTime, nullable=True)


class RefreshTokenDB(Base):
    """Opaque (non-JWT) refresh tokens, stored hashed - never the raw token
    the client holds (same reasoning as password hashing: if the DB leaks,
    stored rows should be useless to an attacker). Lets a session be
    revoked server-side (logout / "log out other devices"), which a bare
    JWT refresh token can't do before its own expiry. See
    backend/core/security.py for the hashing/issuing helpers and
    backend/services/auth_service.py for issue/rotate/revoke logic."""
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)


class PasswordResetTokenDB(Base):
    """Single-use password-reset tokens, stored hashed (same reasoning as
    RefreshTokenDB above). `used` is set the moment the token is consumed so
    a captured/leaked reset link can't be replayed even before it expires.

    NOTE: this repo has no outbound-email integration yet (no SMTP/provider
    configured anywhere in requirements.txt or config.py) - see
    auth_service.request_password_reset()'s docstring for exactly what
    happens instead in the meantime."""
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)


class CustomWorkoutDB(Base):
    """A saved Custom-Mode workout (see frontend/web/js/custom-workout-
    builder.js's serializeCurrentCustomWorkout()). Mirrors SessionLogDB's
    athlete_id convention exactly (plain string, "default" for anonymous
    use, str(user.id) once authenticated) so the same sync pattern applies:
    anonymous use keeps working against localStorage only, an authenticated
    request syncs the same record here.

    `client_id` is the frontend-generated id (e.g. "cw1699999999999") - the
    stable identity the frontend already uses for load/duplicate/delete, so
    a save from a device that's seen this workout before updates the same
    row (upsert on (athlete_id, client_id)) instead of creating a duplicate
    every time. Exercises/groups/warm-up are JSON-blob columns for the same
    reason as SessionLogDB.exercises_json - the frontend already treats
    this whole record as one JSON-shaped object and nothing server-side
    needs to query *inside* it.
    """
    __tablename__ = "custom_workouts"

    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(String, default="default", index=True, nullable=False)
    client_id = Column(String, index=True, nullable=False)

    name = Column(String, nullable=False, default="Custom Workout")
    sport = Column(String, nullable=True)
    experience = Column(String, nullable=True)

    exercises_json = Column(Text, nullable=False, default="[]")
    groups_json = Column(Text, nullable=False, default="{}")
    group_order_json = Column(Text, nullable=False, default="[]")
    warmup_json = Column(Text, nullable=False, default="[]")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class SavedProgramDB(Base):
    """A saved generated program (see frontend/web/js/program-wizard-
    steps.js's S.lastProgram - the full generate-program response). Same
    athlete_id/client_id/upsert conventions as CustomWorkoutDB above.
    `program_json` stores the entire response object as-is (split,
    sport, experience_level, the week-by-week `program` array, and the
    `_used*` regeneration-context fields) - same "don't re-model something
    the frontend already treats as one JSON blob" reasoning as elsewhere
    in this file.
    """
    __tablename__ = "saved_programs"

    id = Column(Integer, primary_key=True, index=True)
    athlete_id = Column(String, default="default", index=True, nullable=False)
    client_id = Column(String, index=True, nullable=False)

    label = Column(String, nullable=False, default="Saved Program")
    sport = Column(String, nullable=True)
    experience_level = Column(String, nullable=True)
    weeks = Column(Integer, nullable=True)
    days_per_week = Column(Integer, nullable=True)

    program_json = Column(Text, nullable=False, default="{}")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class SessionLogDB(Base):
    __tablename__ = "session_logs"

    id = Column(Integer, primary_key=True, index=True)
    # No auth/accounts yet (see database.py's docstring) - "default" for a
    # single-person install, but every query is already scoped by this
    # column so multi-athlete support is a matter of the frontend sending a
    # real id, not a schema change.
    athlete_id = Column(String, default="default", index=True, nullable=False)

    date = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True, nullable=False)
    sport = Column(String, index=True, nullable=False)
    program_label = Column(String, nullable=True)
    deload_mode = Column(Boolean, default=False)
    prescribed_count = Column(Integer, default=0)

    # What readiness score this session was actually *generated* with (the
    # slider value / adaptive suggestion the person trained off of) -
    # distinct from post_soreness/post_fatigue below, which is how they felt
    # AFTER the session. Keeping both is what lets the suggestion algorithm
    # compare "what we predicted" against "how it actually landed" over time.
    readiness_used = Column(Integer, nullable=True)

    # Post-session self-report - the actual signal the adaptive-readiness
    # feature reads. Both optional: logging sets without answering these
    # still saves the session, it just can't contribute to the next
    # suggestion (see readiness_service.compute_suggested_readiness).
    post_soreness = Column(Integer, nullable=True)   # 1 (none) - 5 (very sore), next-day feel
    post_fatigue = Column(Integer, nullable=True)    # 1 (fresh) - 5 (wiped out)
    rpe = Column(Float, nullable=True)               # 1-10, optional overall session RPE

    notes = Column(Text, nullable=True)

    # JSON-encoded (as text) - see module docstring for why these aren't
    # normalized. exercises_json mirrors S.lastResult.prescribed_workout /
    # day.prescribed_workout; log_json mirrors S.sessionLog /
    # S.programSessionLog[dayKey] once flattened to a list.
    exercises_json = Column(Text, nullable=False, default="[]")
    log_json = Column(Text, nullable=False, default="[]")

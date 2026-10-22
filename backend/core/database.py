"""
Persistence layer (Phase 4 of the roadmap).

Backs logged training sessions, accounts, and auth tokens with a real
SQLite (or any SQLAlchemy-supported) database. Schema creation/changes are
tracked via backend/migrations/ (see that package's runner.py for why a
small custom runner instead of Alembic), and per-table query construction
lives in backend/repositories/ instead of inline db.query(...) calls
scattered across the service modules (see that package too).

Usage:
    from backend.core.database import get_db, init_db
    init_db()  # called once at app startup (see main.py)

    @app.get(...)
    def route(db: Session = Depends(get_db)):
        ...
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.core.config import settings

# check_same_thread=False is the standard SQLite/FastAPI pairing - FastAPI
# can hand a request to a different thread than the one that opened the
# connection, and SQLite's default is otherwise overly strict about that.
# Harmless for any non-SQLite DATABASE_URL (the connect_args are only
# meaningful to the sqlite driver).
_connect_args = {"check_same_thread": False} if settings.SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.SQLALCHEMY_DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db() -> None:
    """Applies any migrations not yet recorded for this database (see
    backend/migrations/runner.py). Safe to call on every startup - a
    no-op against an already-current schema, same as the old bare
    create_all() was, but now with a tracked history so future schema
    changes are explicit migrations instead of silent re-derivation."""
    # Imported here (not at module top) to avoid a circular import -
    # runner.py's _discover_migrations() imports migration modules that
    # themselves import Base from this module.
    from backend.migrations.runner import run_migrations
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    run_migrations(engine)


def get_db():
    """FastAPI dependency - yields a session, always closes it after the
    request, even on an exception."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

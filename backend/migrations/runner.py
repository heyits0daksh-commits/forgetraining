"""
Lightweight, stdlib+SQLAlchemy-only migration runner.

Why this exists instead of Alembic: this sandbox has no PyPI access (see
requirements.txt / every prior pass's "fastapi isn't installable here"
caveat), so `pip install alembic` cannot even be attempted, let alone
verified working, in this environment. Rather than add an unverifiable
dependency and an `alembic.ini`/`env.py` nobody here can prove runs,
this is a small, honest substitute that solves the actual problem Phase 4
flagged: schema changes need to be tracked and applied in order, not just
silently re-derived every startup via `Base.metadata.create_all` with no
record of what's actually been applied to a given database file.

Design, deliberately minimal:
  - A `schema_migrations` table (revision, applied_at) tracks what's run.
  - Each migration is a module under `backend/migrations/versions/` named
    `mNNNN_description.py`, exposing:
        revision: str                    - unique, e.g. "0001_initial_schema"
        def upgrade(connection): ...     - forward-only DDL/DML
  - `run_migrations(engine)` applies every not-yet-recorded revision, in
    ascending revision order, each in its own transaction, and records it
    immediately after that transaction commits.

Explicitly NOT attempted: downgrade/rollback, branching migrations,
autogenerate-from-model diffing, or multi-head resolution - none of those
are problems this codebase has yet (one linear history, one contributor
at a time). If/when real PyPI access is available, swapping this for
actual Alembic is a reasonable follow-up; this is meant to be a real,
working stand-in for right now, not a permanent architecture decision.
"""
from __future__ import annotations

import importlib
import pkgutil
from datetime import datetime, timezone
from typing import List

from sqlalchemy import text
from sqlalchemy.engine import Engine

_TRACKING_TABLE = "schema_migrations"


def _ensure_tracking_table(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text(
            f"CREATE TABLE IF NOT EXISTS {_TRACKING_TABLE} ("
            "revision VARCHAR PRIMARY KEY, "
            "applied_at DATETIME NOT NULL)"
        ))


def _applied_revisions(engine: Engine) -> set:
    with engine.begin() as conn:
        rows = conn.execute(text(f"SELECT revision FROM {_TRACKING_TABLE}")).fetchall()
    return {row[0] for row in rows}


def _discover_migrations() -> List:
    """Imports every module under backend/migrations/versions/, sorted by
    `revision` so e.g. "0002_..." always runs after "0001_...". A missing
    or duplicate `revision` attribute is a programming error in the
    migration file itself, not something to silently skip - let it raise."""
    from backend.migrations import versions

    modules = []
    for _, name, _ in pkgutil.iter_modules(versions.__path__):
        if name.startswith("_"):
            continue
        mod = importlib.import_module(f"backend.migrations.versions.{name}")
        modules.append(mod)
    modules.sort(key=lambda m: m.revision)
    return modules


def run_migrations(engine: Engine) -> List[str]:
    """Applies every migration not yet recorded, in order. Returns the
    list of revisions actually applied this call (empty list if the
    database was already current) - callers can log/ignore this as
    appropriate; init_db() currently ignores it (safe no-op on every
    startup once a database is current, same as the old create_all did)."""
    _ensure_tracking_table(engine)
    already_applied = _applied_revisions(engine)
    newly_applied: List[str] = []
    for mod in _discover_migrations():
        if mod.revision in already_applied:
            continue
        with engine.begin() as conn:
            mod.upgrade(conn)
            conn.execute(
                text(f"INSERT INTO {_TRACKING_TABLE} (revision, applied_at) VALUES (:rev, :ts)"),
                {"rev": mod.revision, "ts": datetime.now(timezone.utc)},
            )
        newly_applied.append(mod.revision)
    return newly_applied

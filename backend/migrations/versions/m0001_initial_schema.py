"""
Initial schema - creates every table `Base.metadata` already knows about
as of the Phase-6 (accounts) + Phase-4-first-slice (session_logs) passes:
`users`, `refresh_tokens`, `password_reset_tokens`, `session_logs`.

This migration deliberately reuses the existing SQLAlchemy model metadata
(`backend/models/db_models.py`) via `create_all` rather than hand-writing
the same column definitions a second time in raw DDL - duplicating them
here would just be a second place for the schema to drift out of sync
with the actual model classes. Its job is narrower than that: mark "the
schema as it already exists in every database created before this
migration framework existed" as a tracked revision, so a fresh database's
history starts at a known point and every *future* schema change goes
through a new numbered migration file instead of silently appearing.

Safe against pre-existing (pre-migration-framework) databases too:
`create_all` only creates tables that don't already exist, so running this
against an existing v5.x database with `session_logs`/`users`/etc. already
present is a no-op for that connection - it just gets recorded as applied.
"""
revision = "0001_initial_schema"


def upgrade(connection):
    from backend.core.database import Base
    from backend.models import db_models  # noqa: F401  (populates Base.metadata)

    Base.metadata.create_all(bind=connection)

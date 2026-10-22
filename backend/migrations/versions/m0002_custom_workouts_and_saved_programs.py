"""
Adds `custom_workouts` and `saved_programs` tables (server-side sync for
Custom Mode workouts and generated programs - previously localStorage-only,
see CustomWorkoutDB/SavedProgramDB docstrings in
backend/models/db_models.py). Same create_all-against-current-metadata
approach as m0001_initial_schema.py, for the same reason: these two
tables are brand new, so create_all only ever creates them here and is a
no-op on every subsequent startup once applied.
"""
revision = "0002_custom_workouts_and_saved_programs"


def upgrade(connection):
    from backend.core.database import Base
    from backend.models import db_models  # noqa: F401  (populates Base.metadata)

    Base.metadata.create_all(bind=connection)

"""Repository layer (Phase 4 roadmap). One class per table, wrapping the
db.query(...)/db.add(...)/db.commit() calls that used to live inline in
backend/services/*.py, so a service module says "give me this athlete's
sessions" rather than constructing SQLAlchemy queries itself. Pure
extraction where it replaced existing code - see each module's docstring
for the exact commit boundaries preserved from the code it replaced.

custom_workout_repository.py and saved_program_repository.py additionally
support upsert-on-(athlete_id, client_id), since those two records are
edited in place from the frontend rather than only ever appended to."""

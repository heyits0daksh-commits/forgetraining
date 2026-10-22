"""
Shared fixtures for the FastAPI/SQLAlchemy layer (Phase 13 test suite).

This is the "real end-to-end smoke test" the roadmap has flagged as
outstanding since the Phase-2 modularization pass — every prior pass could
only run `python -m py_compile` / import-with-stub-modules because the
sandbox had no network access to `pip install` the real fastapi/sqlalchemy
stack. That's no longer true, so these fixtures spin up the *real* app
(`backend.main.app`) against a throwaway on-disk SQLite file per test,
instead of hand-built stand-ins.

Each test gets its own empty database (via a temp-dir DATABASE_URL override
+ get_db dependency override) so tests never see another test's rows and
can run in any order.
"""
import sys
from pathlib import Path

import pytest

# Make sure `backend` is importable regardless of the cwd pytest is invoked from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient wired to a fresh temp SQLite DB for this test only."""
    db_path = tmp_path / "test_forge.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    # Force production-style SECRET_KEY handling off so the startup hook's
    # hard-fail branch doesn't fire; tests run with ENVIRONMENT=development
    # (the settings default) unless a specific test overrides it.
    monkeypatch.setenv("ENVIRONMENT", "development")

    # backend.core.config.settings is a module-level singleton built at
    # import time from the environment, and backend.core.database builds its
    # `engine`/`SessionLocal` from that singleton at import time too — so
    # both modules (plus anything that already imported them) must be
    # re-imported fresh *after* the env vars above are set, or every test
    # would silently share the first test's engine/DB file.
    for mod in list(sys.modules):
        if mod == "backend" or mod.startswith("backend."):
            del sys.modules[mod]

    from backend.core.database import Base, engine, get_db, SessionLocal
    from backend.main import app

    Base.metadata.create_all(bind=engine)

    def _get_test_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db

    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def registered_user(client):
    """Registers a fresh account and returns (access_token, refresh_token, email)."""
    email = "athlete@example.com"
    password = "correct-horse-battery-staple"
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "accepted_terms": True},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return {
        "email": email,
        "password": password,
        "access_token": body["access_token"],
        "refresh_token": body["refresh_token"],
    }


@pytest.fixture()
def auth_headers(registered_user):
    return {"Authorization": f"Bearer {registered_user['access_token']}"}

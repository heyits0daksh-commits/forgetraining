"""
Custom-workout and saved-program server-side sync
(/api/v1/custom-workouts, /api/v1/programs) - the two pieces of state that
were still localStorage-only after the Phase 6 accounts pass. Mirrors
test_sessions_and_readiness.py's shape: anonymous default-bucket use,
account scoping/IDOR checks, and upsert-not-duplicate on repeated saves.
"""


def _workout_payload(client_id="cw1", **overrides):
    payload = {
        "client_id": client_id,
        "name": "Leg Day",
        "sport": "Powerlifting",
        "experience": "Intermediate",
        "exercises": [["sq1", {"sets": 5, "reps": 5}]],
        "groups": {},
        "group_order": [],
        "warmup": [],
    }
    payload.update(overrides)
    return payload


def _program_payload(client_id="pg1", **overrides):
    payload = {
        "client_id": client_id,
        "label": "My 4-week block",
        "sport": "Powerlifting",
        "experience_level": "Intermediate",
        "weeks": 4,
        "days_per_week": 4,
        "program": {"split": {"name": "Upper/Lower"}, "program": []},
    }
    payload.update(overrides)
    return payload


# --- Custom workouts ------------------------------------------------------

def test_anonymous_can_save_and_list_custom_workouts(client):
    r = client.post("/api/v1/custom-workouts", json=_workout_payload())
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Leg Day"

    listing = client.get("/api/v1/custom-workouts").json()
    assert len(listing) == 1


def test_saving_same_client_id_twice_updates_not_duplicates(client, auth_headers):
    r1 = client.post("/api/v1/custom-workouts", json=_workout_payload(name="v1"), headers=auth_headers)
    assert r1.status_code == 200, r1.text
    first_id = r1.json()["id"]

    r2 = client.post("/api/v1/custom-workouts", json=_workout_payload(name="v2"), headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["id"] == first_id
    assert r2.json()["name"] == "v2"

    listing = client.get("/api/v1/custom-workouts", headers=auth_headers).json()
    assert len(listing) == 1
    assert listing[0]["name"] == "v2"


def test_custom_workouts_are_scoped_to_account_not_visible_anonymously(client, auth_headers):
    client.post("/api/v1/custom-workouts", json=_workout_payload(), headers=auth_headers)

    anon = client.get("/api/v1/custom-workouts").json()
    assert anon == []

    mine = client.get("/api/v1/custom-workouts", headers=auth_headers).json()
    assert len(mine) == 1


def test_can_delete_own_custom_workout_but_not_someone_elses(client, auth_headers):
    client.post("/api/v1/custom-workouts", json=_workout_payload(), headers=auth_headers)

    # anonymous caller can't delete the authenticated user's workout - it
    # resolves to the "default" bucket, which has no such client_id
    anon_delete = client.delete("/api/v1/custom-workouts/cw1")
    assert anon_delete.status_code == 404

    real_delete = client.delete("/api/v1/custom-workouts/cw1", headers=auth_headers)
    assert real_delete.status_code == 200
    assert real_delete.json()["deleted"] is True

    listing = client.get("/api/v1/custom-workouts", headers=auth_headers).json()
    assert listing == []


# --- Saved programs ---------------------------------------------------

def test_anonymous_can_save_and_list_programs(client):
    r = client.post("/api/v1/programs", json=_program_payload())
    assert r.status_code == 200, r.text
    assert r.json()["label"] == "My 4-week block"

    listing = client.get("/api/v1/programs").json()
    assert len(listing) == 1
    assert listing[0]["program"]["split"]["name"] == "Upper/Lower"


def test_saving_same_program_client_id_twice_updates_not_duplicates(client, auth_headers):
    r1 = client.post("/api/v1/programs", json=_program_payload(label="v1"), headers=auth_headers)
    first_id = r1.json()["id"]

    r2 = client.post("/api/v1/programs", json=_program_payload(label="v2"), headers=auth_headers)
    assert r2.json()["id"] == first_id
    assert r2.json()["label"] == "v2"

    listing = client.get("/api/v1/programs", headers=auth_headers).json()
    assert len(listing) == 1


def test_programs_are_scoped_to_account_not_visible_anonymously(client, auth_headers):
    client.post("/api/v1/programs", json=_program_payload(), headers=auth_headers)

    anon = client.get("/api/v1/programs").json()
    assert anon == []

    mine = client.get("/api/v1/programs", headers=auth_headers).json()
    assert len(mine) == 1


def test_can_delete_own_program_but_not_someone_elses(client, auth_headers):
    client.post("/api/v1/programs", json=_program_payload(), headers=auth_headers)

    anon_delete = client.delete("/api/v1/programs/pg1")
    assert anon_delete.status_code == 404

    real_delete = client.delete("/api/v1/programs/pg1", headers=auth_headers)
    assert real_delete.status_code == 200

    listing = client.get("/api/v1/programs", headers=auth_headers).json()
    assert listing == []

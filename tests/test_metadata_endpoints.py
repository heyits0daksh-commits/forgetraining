"""
Read-only metadata/reference endpoints — no auth, no DB writes. These are
the endpoints the frontend calls on first load (sports, equipment, goals,
splits, exercises, etc.), so a break here breaks the whole app before a
person can do anything.
"""


def test_metadata(client):
    r = client.get("/api/v1/metadata")
    assert r.status_code == 200
    body = r.json()
    assert "sports" in body


def test_goals(client):
    r = client.get("/api/v1/goals")
    assert r.status_code == 200
    goals = r.json()["goals"]
    assert "Get Strong" in goals


def test_splits(client):
    r = client.get("/api/v1/splits")
    assert r.status_code == 200
    splits = r.json()["splits"]
    ids = {s["id"] for s in splits}
    assert "full_body" in ids


def test_equipment(client):
    r = client.get("/api/v1/equipment")
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_exercises_list(client):
    r = client.get("/api/v1/exercises")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["exercises"], list)
    assert body["count"] == len(body["exercises"])


def test_injuries_grouped(client):
    r = client.get("/api/v1/injuries/grouped")
    assert r.status_code == 200


def test_injuries_by_muscle_group(client):
    r = client.get("/api/v1/injuries/by-muscle-group")
    assert r.status_code == 200
    body = r.json()
    # A handful of muscle-group categories a person browsing for "chest",
    # "back", or "leg" muscles would expect to see, distinct from the
    # joint-based categories on /api/v1/injuries/grouped.
    for expected in ("Chest", "Back", "Legs"):
        assert expected in body
    assert any(k.endswith("(Joints, Ligaments & Tendons)") for k in body)


def test_metadata_includes_injuries_by_muscle_group(client):
    r = client.get("/api/v1/metadata")
    assert r.status_code == 200
    assert "injuries_by_muscle_group" in r.json()


def test_conditioning_protocols(client):
    r = client.get("/api/v1/conditioning-protocols")
    assert r.status_code == 200


def test_training_phases(client):
    r = client.get("/api/v1/training-phases")
    assert r.status_code == 200


def test_unknown_sport_is_404_not_500(client):
    r = client.get("/api/v1/sports/not-a-real-sport")
    assert r.status_code == 404


def test_knowledge_graph_for_real_exercise(client):
    exercises = client.get("/api/v1/exercises").json()["exercises"]
    ex_id = exercises[0]["id"]
    r = client.get(f"/api/v1/knowledge-graph/{ex_id}")
    assert r.status_code == 200


def test_knowledge_graph_unknown_id_is_404_not_500(client):
    r = client.get("/api/v1/knowledge-graph/not-a-real-id")
    assert r.status_code == 404


def test_knowledge_graph_exposes_tissue_demand_flags(client):
    """v5.12: the same derive_tissue_demands() profile classify_injury_risk's
    escalation reads off of should be visible on the exercise-detail
    endpoint too, so a client can show why an exercise reads as higher-risk
    for a given tissue type instead of it being a server-only adjustment."""
    exercises = client.get("/api/v1/exercises").json()["exercises"]
    ex_id = exercises[0]["id"]
    r = client.get(f"/api/v1/knowledge-graph/{ex_id}")
    assert r.status_code == 200
    body = r.json()
    assert "tissue_demand_flags" in body
    flags = body["tissue_demand_flags"]
    # Every flag derive_tissue_demands() defines should be present and
    # boolean, regardless of which ones happen to be true for this exercise.
    expected_flags = {
        "high_compression", "high_shear", "high_rotation", "frontal_plane_loading",
        "high_impact", "high_velocity", "large_rom_demand", "high_eccentric",
        "unilateral_loading", "high_instability",
    }
    assert expected_flags <= flags.keys()
    assert all(isinstance(v, bool) for v in flags.values())

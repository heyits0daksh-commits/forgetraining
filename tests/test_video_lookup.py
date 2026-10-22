"""Tests for backend/data/exercise_video_links.py's curated-link feature
and its wiring through backend/services/video_lookup.py and the
GET /api/v1/exercises/{id}/video route.
"""
from backend.services import video_lookup


# ---------------------------------------------------------------------------
# resolve_static_video_link - URL-shape detection
# ---------------------------------------------------------------------------

def test_resolve_youtube_watch_url():
    r = video_lookup.resolve_static_video_link(
        "https://www.youtube.com/watch?v=SW_C1A-rejs", "Back Squat"
    )
    assert r["source_type"] == "youtube"
    assert r["embeddable"] is True
    assert r["video_id"] == "SW_C1A-rejs"
    assert r["embed_url"] == "https://www.youtube-nocookie.com/embed/SW_C1A-rejs"
    assert r["watch_url"] == "https://www.youtube.com/watch?v=SW_C1A-rejs"


def test_resolve_youtube_short_url():
    r = video_lookup.resolve_static_video_link("https://youtu.be/YSx28dwjm2A", "KB Swing")
    assert r["source_type"] == "youtube"
    assert r["video_id"] == "YSx28dwjm2A"


def test_resolve_youtube_shorts_url():
    r = video_lookup.resolve_static_video_link(
        "https://www.youtube.com/shorts/abcdEFGh123", "Jump"
    )
    assert r["source_type"] == "youtube"
    assert r["video_id"] == "abcdEFGh123"


def test_resolve_vimeo_url():
    r = video_lookup.resolve_static_video_link("https://vimeo.com/123456789", "Ring MU")
    assert r["source_type"] == "vimeo"
    assert r["embeddable"] is True
    assert r["embed_url"] == "https://player.vimeo.com/video/123456789"


def test_resolve_direct_file_url():
    r = video_lookup.resolve_static_video_link(
        "https://example.com/videos/squat-demo.mp4", "Squat"
    )
    assert r["source_type"] == "direct_file"
    assert r["embeddable"] is True
    assert r["embed_url"] == "https://example.com/videos/squat-demo.mp4"


def test_resolve_non_embeddable_external_link():
    r = video_lookup.resolve_static_video_link(
        "https://www.instagram.com/reel/Cabc123/", "Deadlift"
    )
    assert r["source_type"] == "external"
    assert r["embeddable"] is False
    assert r["embed_url"] == ""
    assert r["watch_url"] == "https://www.instagram.com/reel/Cabc123/"


# ---------------------------------------------------------------------------
# get_video_for_exercise - a curated link always wins, bypasses the
# channel/API-key checks and the on-disk cache entirely
# ---------------------------------------------------------------------------

def test_curated_link_wins_over_missing_channel_and_api_key(monkeypatch):
    monkeypatch.setitem(video_lookup.EXERCISE_VIDEO_LINKS, "pushup_001", "https://youtu.be/abc123DEF45")
    monkeypatch.setattr(video_lookup.settings, "YOUTUBE_API_KEY", None)
    result = video_lookup.get_video_for_exercise(
        "pushup_001", {"id": "pushup_001", "name": "Standard Push-Up", "equipment": "Bodyweight"}
    )
    assert result is not None
    assert result["source_type"] == "youtube"
    assert result["video_id"] == "abc123DEF45"


def test_no_curated_link_falls_through_to_existing_behavior(monkeypatch):
    # This test isolates itself from EXERCISE_VIDEO_LINKS's real, growing
    # content (pushup_001 now legitimately has a curated link - see
    # docs/ROADMAP.md's "curated exercise demo videos" entry) instead of
    # asserting on the live dict's current state, which drifts every time a
    # new link is pasted in and made this test flaky-by-design.
    monkeypatch.setattr(video_lookup.settings, "YOUTUBE_API_KEY", None)
    monkeypatch.delitem(video_lookup.EXERCISE_VIDEO_LINKS, "pushup_001", raising=False)
    result = video_lookup.get_video_for_exercise(
        "pushup_001", {"id": "pushup_001", "name": "Standard Push-Up", "equipment": "Bodyweight"}
    )
    assert result is None  # no API key, no curated link - unchanged from before this feature


# ---------------------------------------------------------------------------
# Route: GET /api/v1/exercises/{id}/video
# ---------------------------------------------------------------------------

def test_route_returns_curated_link_even_without_api_key(client, monkeypatch):
    from backend.services import video_lookup as vl  # fresh module - conftest reloads backend.* per test
    monkeypatch.setitem(vl.EXERCISE_VIDEO_LINKS, "pushup_001", "https://vimeo.com/987654321")
    monkeypatch.setattr(vl.settings, "YOUTUBE_API_KEY", None)
    resp = client.get("/api/v1/exercises/pushup_001/video")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["source_type"] == "vimeo"
    assert data["embeddable"] is True


def test_route_reports_non_embeddable_curated_link(client, monkeypatch):
    from backend.services import video_lookup as vl
    monkeypatch.setitem(
        vl.EXERCISE_VIDEO_LINKS, "pushup_001", "https://www.tiktok.com/@someone/video/123"
    )
    resp = client.get("/api/v1/exercises/pushup_001/video")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is True
    assert data["embeddable"] is False
    assert data["watch_url"] == "https://www.tiktok.com/@someone/video/123"


def test_route_unknown_exercise_id_still_404s(client):
    resp = client.get("/api/v1/exercises/not_a_real_id/video")
    assert resp.status_code == 404

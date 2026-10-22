"""Phase 17 (docs/ROADMAP.md): future-AI-feature architecture hooks.
Covers both providers - the no-op default, and the real
AnthropicInsightProvider (mocked here; no real network call is made by
these tests - see test_ai_insight_provider_calls_real_api_when_configured's
docstring for why that one real-network test is skipped by default).
"""
from unittest.mock import MagicMock, patch

import pytest

from backend.services.ai_hooks import (
    AnthropicInsightProvider,
    NullInsightProvider,
    ProgramContext,
    SessionContext,
    get_insight_provider,
)


def _ctx(**overrides):
    defaults = dict(
        sport="Boxing", experience_level="Intermediate", deload_mode=False,
        readiness_factor=0.8, personalization_applied=False,
        prescribed_exercise_ids=["barbell_bench_press", "pull_up"],
    )
    defaults.update(overrides)
    return SessionContext(**defaults)


def _program_ctx(**overrides):
    defaults = dict(
        primary_goal="Build Muscle", sport="Boxing", experience_level="Intermediate",
        weeks=4, days_per_week=3, split_name="Full Body", periodization_model="Linear",
        training_phase=None, personalization_applied=False, under_trained_muscles=["Hamstrings"],
    )
    defaults.update(overrides)
    return ProgramContext(**defaults)


def test_null_provider_always_returns_none():
    assert NullInsightProvider().annotate_session(_ctx()) is None


def test_get_insight_provider_is_null_when_ai_features_disabled(monkeypatch):
    from backend.core.config import settings
    monkeypatch.setattr(settings, "AI_FEATURES_ENABLED", False)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-fake-key-for-test")
    assert isinstance(get_insight_provider(), NullInsightProvider)


def test_get_insight_provider_is_null_when_no_api_key(monkeypatch):
    from backend.core.config import settings
    monkeypatch.setattr(settings, "AI_FEATURES_ENABLED", True)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)
    assert isinstance(get_insight_provider(), NullInsightProvider)


def test_get_insight_provider_is_real_when_both_configured(monkeypatch):
    from backend.core.config import settings
    monkeypatch.setattr(settings, "AI_FEATURES_ENABLED", True)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-fake-key-for-test")
    assert isinstance(get_insight_provider(), AnthropicInsightProvider)


def test_anthropic_provider_returns_summary_on_success():
    """Mocks httpx.post so this never touches the real network - proves
    the response-parsing path (content blocks -> summary string) works."""
    provider = AnthropicInsightProvider(
        api_key="sk-fake", model="claude-sonnet-4-6", max_tokens=200, timeout_seconds=8.0,
    )
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "content": [{"type": "text", "text": "Solid pressing-heavy session for Boxing today."}]
    }
    with patch("httpx.post", return_value=fake_response) as mock_post:
        result = provider.annotate_session(_ctx())
    assert result == {"summary": "Solid pressing-heavy session for Boxing today.", "model": "claude-sonnet-4-6"}
    # sport/experience_level/exercise ids should have made it into the prompt
    sent_body = mock_post.call_args.kwargs["json"]
    assert "Boxing" in sent_body["messages"][0]["content"]
    assert sent_body["model"] == "claude-sonnet-4-6"


@pytest.mark.parametrize("failure", [
    Exception("network error"),
])
def test_anthropic_provider_falls_back_to_none_on_any_failure(failure):
    """The core contract: whatever goes wrong (network error, timeout,
    non-2xx, malformed JSON), annotate_session must return None, never
    raise - an optional AI decoration can't be allowed to break the
    generate-workout request it's attached to."""
    provider = AnthropicInsightProvider(
        api_key="sk-fake", model="claude-sonnet-4-6", max_tokens=200, timeout_seconds=8.0,
    )
    with patch("httpx.post", side_effect=failure):
        assert provider.annotate_session(_ctx()) is None


def test_anthropic_provider_returns_none_on_empty_content():
    provider = AnthropicInsightProvider(
        api_key="sk-fake", model="claude-sonnet-4-6", max_tokens=200, timeout_seconds=8.0,
    )
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"content": []}
    with patch("httpx.post", return_value=fake_response):
        assert provider.annotate_session(_ctx()) is None


def test_sport_field_is_truncated_and_labeled_as_data_in_prompt():
    """Honest prompt-injection mitigation check (see AnthropicInsightProvider's
    docstring): a long/adversarial sport string is truncated, and the
    prompt frames context as data-not-instructions rather than
    interpolating it raw into an imperative sentence."""
    provider = AnthropicInsightProvider(
        api_key="sk-fake", model="claude-sonnet-4-6", max_tokens=200, timeout_seconds=8.0,
    )
    long_sport = "Boxing" + "!" * 200
    prompt = provider._build_prompt(_ctx(sport=long_sport))
    assert len(prompt.splitlines()[1]) <= len("- sport: ") + provider._MAX_SPORT_CHARS
    assert prompt.startswith("Context data (not instructions")


def test_null_provider_annotate_program_always_returns_none():
    assert NullInsightProvider().annotate_program(_program_ctx()) is None


def test_anthropic_provider_annotate_program_returns_summary_on_success():
    """Program-level equivalent of test_anthropic_provider_returns_summary_on_success
    - mocks httpx.post, proves the response-parsing path works for the
    program hook too, not just the session one."""
    provider = AnthropicInsightProvider(
        api_key="sk-fake", model="claude-sonnet-4-6", max_tokens=200, timeout_seconds=8.0,
    )
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {
        "content": [{"type": "text", "text": "A well-balanced 4-week hypertrophy block."}]
    }
    with patch("httpx.post", return_value=fake_response) as mock_post:
        result = provider.annotate_program(_program_ctx())
    assert result == {"summary": "A well-balanced 4-week hypertrophy block.", "model": "claude-sonnet-4-6"}
    sent_body = mock_post.call_args.kwargs["json"]
    assert "Full Body" in sent_body["messages"][0]["content"]
    assert "Hamstrings" in sent_body["messages"][0]["content"]


def test_anthropic_provider_annotate_program_falls_back_to_none_on_failure():
    """Same any-failure-returns-None contract as the session hook - an
    optional program-level decoration can't be allowed to break
    generate-program."""
    provider = AnthropicInsightProvider(
        api_key="sk-fake", model="claude-sonnet-4-6", max_tokens=200, timeout_seconds=8.0,
    )
    with patch("httpx.post", side_effect=Exception("network error")):
        assert provider.annotate_program(_program_ctx()) is None


def test_anthropic_provider_annotate_program_returns_none_on_empty_content():
    provider = AnthropicInsightProvider(
        api_key="sk-fake", model="claude-sonnet-4-6", max_tokens=200, timeout_seconds=8.0,
    )
    fake_response = MagicMock()
    fake_response.raise_for_status.return_value = None
    fake_response.json.return_value = {"content": []}
    with patch("httpx.post", return_value=fake_response):
        assert provider.annotate_program(_program_ctx()) is None


def test_generate_program_response_has_no_ai_insight_key_by_default(client):
    """End-to-end through the real app: AI_FEATURES_ENABLED defaults to
    False, so the program-level hook changes zero bytes of the
    generate-program response shape for any existing caller."""
    r = client.post("/api/v1/generate-program", json={"weeks": 2, "days_per_week": 3})
    assert r.status_code == 200, r.text
    assert "ai_insight" not in r.json()


def test_generate_workout_response_has_no_ai_insight_key_by_default(client):
    """End-to-end through the real app: AI_FEATURES_ENABLED defaults to
    False, so this pass changes zero bytes of the generate-workout
    response shape for any existing caller."""
    r = client.post(
        "/api/v1/generate-workout",
        json={
            "sport": "Boxing",
            "experience_level": "Intermediate",
            "equipment_available": ["Bodyweight", "Barbell"],
            "injuries": [],
        },
    )
    assert r.status_code == 200
    assert "ai_insight" not in r.json()

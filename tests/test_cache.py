"""Tests for backend/core/cache.py (Phase 8: Performance / caching).

Stdlib-only, no fastapi/sqlalchemy needed - these exercise the decorators
directly, same as tests/test_config.py does for Settings.
"""
import time

from backend.core.cache import cache_forever, ttl_cache


def test_ttl_cache_returns_cached_value_within_window():
    calls = {"n": 0}

    @ttl_cache(10)
    def fn(x):
        calls["n"] += 1
        return x * 2

    assert fn(5) == 10
    assert fn(5) == 10
    assert calls["n"] == 1


def test_ttl_cache_different_args_are_separate_entries():
    calls = {"n": 0}

    @ttl_cache(10)
    def fn(x):
        calls["n"] += 1
        return x * 2

    fn(5)
    fn(6)
    assert calls["n"] == 2


def test_ttl_cache_expires_after_ttl():
    calls = {"n": 0}

    @ttl_cache(0.05)
    def fn(x):
        calls["n"] += 1
        return x

    fn(1)
    time.sleep(0.1)
    fn(1)
    assert calls["n"] == 2


def test_ttl_cache_clear_forces_recompute():
    calls = {"n": 0}

    @ttl_cache(10)
    def fn(x):
        calls["n"] += 1
        return x

    fn(1)
    fn.cache_clear()
    fn(1)
    assert calls["n"] == 2


def test_ttl_cache_never_caches_a_raised_exception():
    calls = {"n": 0}

    @ttl_cache(10)
    def fn(x):
        calls["n"] += 1
        if x == 0:
            raise ValueError("boom")
        return x

    for _ in range(2):
        try:
            fn(0)
        except ValueError:
            pass
    assert calls["n"] == 2


def test_cache_forever_never_recomputes_same_arg():
    calls = {"n": 0}

    @cache_forever
    def fn(x):
        calls["n"] += 1
        return x + 1

    assert fn(1) == 2
    assert fn(1) == 2
    assert calls["n"] == 1


def test_grouped_injury_taxonomy_is_cached():
    """Real call site (Phase 8 wiring in injury_taxonomy.py): a second call
    must return the identical cached object, not recompute from
    INJURY_TAXONOMY again."""
    from backend.services.injury_taxonomy import grouped_injury_taxonomy

    first = grouped_injury_taxonomy()
    second = grouped_injury_taxonomy()
    assert first is second
    assert len(first) > 0

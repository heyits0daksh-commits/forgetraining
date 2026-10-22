"""
backend/core/cache.py — stdlib-only, in-process caching (Phase 8: Performance / caching).

WHY THIS EXISTS
`backend/core/config.py` has shipped a `METADATA_CACHE_TTL_SECONDS` setting
since the Phase 3 config pass, but nothing ever read it. Several endpoints
recomputed their entire response on every single request from data that's
actually loaded once at startup (`ProgressionEngine.load_database`,
`INJURY_TAXONOMY`) and never changes again for the life of the process —
`grouped_injury_taxonomy()` re-walked the full injury taxonomy on every call
to `/api/v1/metadata` *and* `/api/v1/injuries/grouped`, `build_equipment_catalog`
re-grouped all 731 exercises on every `/api/v1/equipment` call, and
`explain_exercise` re-walked the knowledge graph's in/out edges on every
`/api/v1/knowledge-graph/{id}` call.

Same stdlib-only, in-memory, per-process philosophy as `rate_limit.py` (see
that module's own docstring) — no redis/memcached dependency for a
single-instance app. If you run multiple workers/replicas, each one keeps its
own cache (same caveat `rate_limit.py` already documents for its counters) —
harmless here since every worker loads the same `exercises.json` at startup
and would compute the same cached values anyway, just once per worker instead
of once per process-lifetime-shared-cache.

Two decorators:
  - `@ttl_cache(seconds)` — cache a function's return value, keyed on its
    (hashable) args, for `seconds`. Used for values that plausibly *could*
    change if a future pass adds hot-reloading of exercises.json without a
    restart — kept to `settings.METADATA_CACHE_TTL_SECONDS` (30s default)
    rather than forever, so that stays a safe upper bound on staleness.
  - `@cache_forever` — `functools.lru_cache(maxsize=None)` under a clearer
    name. Use only for values provably fixed at startup and never mutated by
    anything else in-process (e.g. the injury taxonomy, or a per-exercise
    knowledge-graph lookup against the single `engine.knowledge_graph` built
    once in `load_database`).

Neither decorator caches an exception — a call that raises is simply not
stored and is recomputed next time, so e.g. an unknown exercise id on
`/api/v1/knowledge-graph/{id}` (which raises HTTPException) never pollutes
the cache with a 404.
"""
import threading
import time
from functools import lru_cache, wraps


def ttl_cache(seconds: int):
    """Cache a function's return value per distinct (args, kwargs), expiring
    after `seconds`. Thread-safe (a single lock per decorated function -
    fine at this call volume; not meant for hot inner loops)."""

    def decorator(func):
        lock = threading.Lock()
        store: dict = {}  # key -> (expires_at_monotonic, value)

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            with lock:
                hit = store.get(key)
                if hit is not None and hit[0] > now:
                    return hit[1]
            value = func(*args, **kwargs)
            with lock:
                store[key] = (now + seconds, value)
            return value

        def cache_clear():
            with lock:
                store.clear()

        wrapper.cache_clear = cache_clear
        return wrapper

    return decorator


def cache_forever(func):
    """functools.lru_cache(maxsize=None), renamed so the call site states the
    intent (this value never changes for the life of the process) instead of
    just an arbitrary cache size."""
    return lru_cache(maxsize=None)(func)

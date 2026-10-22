"""
Regression tests for the "every user shares one rate-limit budget behind a
reverse proxy" bug: backend/core/rate_limit.py's _client_key() used to key
solely on request.client.host, which on Render/Cloud Run/nginx/any proxied
deployment is the PROXY's address, not the visitor's - so all real users
collapsed onto one bucket and started getting 429 "Too many attempts" after
only a handful of genuine signups/logins from *different* people, well
before any single person actually exceeded the limit. Fixed by trusting the
standard X-Forwarded-For header (set by every major PaaS/proxy) when
present, falling back to request.client.host for direct/local connections.
"""
from backend.core.rate_limit import _client_key


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, headers=None, client_host="10.0.0.1"):
        self.headers = headers or {}
        self.client = _FakeClient(client_host) if client_host else None


def test_client_key_prefers_x_forwarded_for_over_proxy_address():
    """Two different visitors behind the same proxy (same request.client.host)
    must resolve to two different keys, or they share one rate-limit budget."""
    req_a = _FakeRequest(headers={"x-forwarded-for": "203.0.113.5"}, client_host="10.0.0.1")
    req_b = _FakeRequest(headers={"x-forwarded-for": "198.51.100.9"}, client_host="10.0.0.1")
    assert _client_key(req_a) != _client_key(req_b)
    assert _client_key(req_a) == "203.0.113.5"
    assert _client_key(req_b) == "198.51.100.9"


def test_client_key_uses_first_hop_of_forwarded_chain():
    """X-Forwarded-For can list multiple hops ('client, proxy1, proxy2') -
    the first entry is the original visitor, which is the one that must be
    rate-limited individually."""
    req = _FakeRequest(headers={"x-forwarded-for": "203.0.113.5, 10.0.0.1, 10.0.0.2"})
    assert _client_key(req) == "203.0.113.5"


def test_client_key_falls_back_to_direct_connection_without_proxy():
    """No proxy in front (local dev, direct connection) - behave as before."""
    req = _FakeRequest(headers={}, client_host="127.0.0.1")
    assert _client_key(req) == "127.0.0.1"


def test_client_key_falls_back_to_unknown_when_nothing_available():
    req = _FakeRequest(headers={}, client_host=None)
    assert _client_key(req) == "unknown"


def test_two_different_ips_each_get_their_own_login_rate_limit_budget(client, registered_user):
    """End-to-end: 10 failed logins from one visitor (IP A) must not affect
    a completely different visitor (IP B) attempting to log in right after -
    this is the exact symptom users hit ('login/signup keeps failing for
    everyone') when the rate limiter couldn't tell visitors apart."""
    for _ in range(10):
        client.post(
            "/api/v1/auth/login",
            json={"email": registered_user["email"], "password": "wrong-pw-each-time"},
            headers={"X-Forwarded-For": "203.0.113.5"},
        )
    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": "wrong-pw-each-time"},
        headers={"X-Forwarded-For": "203.0.113.5"},
    )
    assert blocked.status_code == 429

    # A different visitor, same proxy/app instance, must still be able to log in.
    other_visitor = client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
        headers={"X-Forwarded-For": "198.51.100.9"},
    )
    assert other_visitor.status_code == 200, other_visitor.text

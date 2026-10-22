"""
Password hashing + JWT access tokens for Phase 6 (persistent user profiles).

Deliberately built on stdlib `hashlib` (PBKDF2-HMAC-SHA256) instead of
bcrypt/passlib: this repo's `requirements.txt` doesn't pin either of those,
and adding a dependency that can't actually be verified to install/import in
this environment would be worse than using a well-known stdlib primitive.
PBKDF2-HMAC-SHA256 with a per-password random salt and a high iteration
count is still an accepted password-hashing scheme (NIST SP 800-63B lists
it explicitly) - if you'd rather run bcrypt/argon2 in production, swapping
`hash_password`/`verify_password` below for a passlib-backed version is a
self-contained change; nothing else in the app needs to know which scheme
produced the stored hash.

JWTs use PyJWT (already present in this environment / commonly available)
rather than hand-rolling signing.

Usage:
    from backend.core.security import hash_password, verify_password, create_access_token, decode_access_token
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

from backend.core.config import settings

_PBKDF2_ALGORITHM = "sha256"
_PBKDF2_ITERATIONS = 260_000  # OWASP (2023) minimum recommendation for PBKDF2-SHA256
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    """Returns `pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>` - the
    iteration count is stored alongside the hash so it can be raised later
    without invalidating already-hashed passwords (verify just reads
    whatever count is embedded)."""
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(_PBKDF2_ALGORITHM, password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time comparison against a hash produced by hash_password().
    Returns False (rather than raising) for any malformed/unrecognized
    stored value, so a corrupted row fails closed instead of 500ing."""
    try:
        scheme, iterations_str, salt_hex, hash_hex = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False
    candidate = hashlib.pbkdf2_hmac(_PBKDF2_ALGORITHM, password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


def create_access_token(subject: str, extra_claims: Optional[Dict[str, Any]] = None) -> str:
    """`subject` is the value that ends up in the token's `sub` claim -
    always the user's id (as a string), never their email, so a later email
    change doesn't invalidate outstanding tokens or require re-issuing them."""
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


class TokenError(Exception):
    """Raised for any invalid/expired/malformed token - callers (the
    get_current_user dependency in auth_service.py) turn this into a 401
    without needing to know which of PyJWT's several exception types fired."""


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc


# --- Opaque tokens (refresh tokens, password-reset tokens) ---
#
# Deliberately NOT JWTs, unlike the access token above: these are long-lived
# (refresh) or security-sensitive/single-use (reset) credentials, so they're
# stored server-side (RefreshTokenDB / PasswordResetTokenDB) and can be
# individually revoked or marked used - a self-contained JWT can't be
# un-issued before its own expiry. The client only ever holds the raw random
# token; the DB stores its hash (`hash_opaque_token`), so a DB leak alone
# doesn't hand out usable credentials, same reasoning as password hashing.

def generate_opaque_token() -> str:
    """URL-safe random token for refresh/reset links - 32 bytes of entropy,
    plenty for a single-use or revocable-server-side credential."""
    return secrets.token_urlsafe(32)


def hash_opaque_token(token: str) -> str:
    """Deterministic hash (no per-token salt) is correct here, unlike
    password hashing: we need to look the token up by its hash in one query
    (`WHERE token_hash = ?`), and the token itself already has 256 bits of
    random entropy, so it isn't guessable/rainbow-tableable the way a human
    password is."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

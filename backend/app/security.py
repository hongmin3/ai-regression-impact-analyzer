"""Password hashing and session-token handling.

Passwords use Argon2id (argon2-cffi defaults, which are the OWASP-recommended
parameters).  Plain-text passwords are never stored, logged, or returned by any
endpoint.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from .config import settings

_hasher = PasswordHasher()

SESSION_TOKEN_BYTES = 32


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _hasher.check_needs_rehash(hashed)
    except (InvalidHashError, ValueError):
        return False


def validate_password_strength(plain: str) -> str | None:
    """Return an error message, or ``None`` when the password is acceptable.

    Length only, driven entirely by ``PASSWORD_MIN_LENGTH``.  The default of 1
    means any non-empty password is accepted; raising the setting is the whole
    change needed to enforce a minimum again.
    """
    if not plain:
        return "비밀번호를 입력하세요."
    if len(plain) < settings.password_min_length:
        return f"비밀번호는 최소 {settings.password_min_length}자 이상이어야 합니다."
    if plain.strip() != plain:
        return "비밀번호의 앞뒤에 공백을 사용할 수 없습니다."
    return None


def new_session_token() -> str:
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """SHA-256 is right here (not Argon2): the token is 256 bits of entropy, so
    there is nothing to brute-force, and session lookup happens on every
    request."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry(now: datetime | None = None) -> datetime:
    base = now or datetime.now(UTC)
    return base + timedelta(hours=settings.session_lifetime_hours)

"""JWT authentication utilities."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from hqmts.core.enums import UserRole


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(
    user_id: str,
    role: UserRole,
    session_id: str,
    secret_key: str,
    expires_minutes: int = 15,
) -> str:
    """Create a JWT access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role.value,
        "session_id": session_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def create_refresh_token(
    user_id: str,
    session_id: str,
    secret_key: str,
    expires_days: int = 7,
) -> str:
    """Create a JWT refresh token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "session_id": session_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=expires_days),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def decode_token(token: str, secret_key: str) -> dict:
    """Decode and validate a JWT token. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, secret_key, algorithms=["HS256"])


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return f"sess_{uuid.uuid4().hex[:16]}"

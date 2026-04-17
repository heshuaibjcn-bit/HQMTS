"""Tests for JWT auth core utilities."""

from __future__ import annotations

import pytest

from hqmts.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_session_id,
    hash_password,
    verify_password,
)
from hqmts.core.enums import UserRole


class TestPasswordHashing:
    def test_hash_and_verify(self):
        """Hash and verify password round-trip."""
        hashed = hash_password("secret123")
        assert hashed != "secret123"
        assert verify_password("secret123", hashed)

    def test_wrong_password_fails(self):
        """Wrong password returns False."""
        hashed = hash_password("secret123")
        assert not verify_password("wrong", hashed)

    def test_different_hashes_for_same_password(self):
        """bcrypt generates unique salts."""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2


class TestJWTTokens:
    def test_create_and_decode_access_token(self):
        """Access token round-trip with correct payload."""
        token = create_access_token(
            user_id="user_001",
            role=UserRole.TRADER,
            session_id="sess_abc",
            secret_key="test-secret",
            expires_minutes=15,
        )
        payload = decode_token(token, "test-secret")

        assert payload["sub"] == "user_001"
        assert payload["role"] == "trader"
        assert payload["session_id"] == "sess_abc"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_and_decode_refresh_token(self):
        """Refresh token round-trip with correct payload."""
        token = create_refresh_token(
            user_id="user_001",
            session_id="sess_abc",
            secret_key="test-secret",
            expires_days=7,
        )
        payload = decode_token(token, "test-secret")

        assert payload["sub"] == "user_001"
        assert payload["session_id"] == "sess_abc"
        assert payload["type"] == "refresh"

    def test_expired_token_raises(self):
        """Expired token raises PyJWTError."""
        import jwt as pyjwt

        token = create_access_token(
            user_id="user_001",
            role=UserRole.TRADER,
            session_id="sess_abc",
            secret_key="test-secret",
            expires_minutes=-1,  # Already expired
        )
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_token(token, "test-secret")

    def test_wrong_secret_raises(self):
        """Wrong secret key raises PyJWTError."""
        import jwt as pyjwt

        token = create_access_token(
            user_id="user_001",
            role=UserRole.TRADER,
            session_id="sess_abc",
            secret_key="correct-secret",
        )
        with pytest.raises(pyjwt.InvalidSignatureError):
            decode_token(token, "wrong-secret")

    def test_generate_session_id_format(self):
        """Session ID has expected prefix and length."""
        sid = generate_session_id()
        assert sid.startswith("sess_")
        assert len(sid) == 21  # "sess_" + 16 hex chars

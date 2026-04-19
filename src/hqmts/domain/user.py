"""User domain models (Pydantic, not ORM)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserInfo(BaseModel):
    """Public user information returned by /auth/me."""

    user_id: str
    username: str
    role: str
    display_name: str = ""
    is_active: bool = True


class SessionInfo(BaseModel):
    """Active session information."""

    session_id: str
    ip_address: str = ""
    created_at: datetime
    last_active_at: datetime

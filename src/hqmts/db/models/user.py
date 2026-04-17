"""User and Session ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base, TimestampMixin


class UserORM(Base, TimestampMixin):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # UserRole value
    display_name: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(default=True)


class SessionORM(Base):
    __tablename__ = "user_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)  # SessionStatus
    ip_address: Mapped[str] = mapped_column(String(45), default="")
    user_agent: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

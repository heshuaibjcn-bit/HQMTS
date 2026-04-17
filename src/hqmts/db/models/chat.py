"""Chat session and message ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from hqmts.db.base import Base


class ChatSessionORM(Base):
    __tablename__ = "chat_sessions"

    chat_session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.user_id"), nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(256), default="")
    model_provider: Mapped[str] = mapped_column(
        String(32), default="openai",
    )  # openai | ollama | claude
    environment: Mapped[str] = mapped_column(String(16), default="research")
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | idle | archived
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )


class ChatMessageORM(Base):
    __tablename__ = "chat_messages"

    chat_message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chat_session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("chat_sessions.chat_session_id"), nullable=False, index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant | tool_call | tool_result | system
    content: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")  # tool_calls, agent_task refs
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

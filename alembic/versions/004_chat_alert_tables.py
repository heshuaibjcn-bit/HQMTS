"""Add chat_sessions, chat_messages, alerts, alert_acknowledgments tables.

Revision ID: 004
Revises: 003
Create Date: 2026-04-18

"""
from alembic import op
import sqlalchemy as sa


revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("chat_session_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(256), nullable=True, server_default=""),
        sa.Column("model_provider", sa.String(32), nullable=True, server_default="openai"),
        sa.Column("environment", sa.String(16), nullable=True, server_default="research"),
        sa.Column("status", sa.String(16), nullable=True, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("chat_session_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])

    op.create_table(
        "chat_messages",
        sa.Column("chat_message_id", sa.String(64), nullable=False),
        sa.Column("chat_session_id", sa.String(64), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=True, server_default=""),
        sa.Column("metadata_json", sa.Text(), nullable=True, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("chat_message_id"),
        sa.ForeignKeyConstraint(["chat_session_id"], ["chat_sessions.chat_session_id"]),
    )
    op.create_index("ix_chat_messages_chat_session_id", "chat_messages", ["chat_session_id"])

    op.create_table(
        "alerts",
        sa.Column("alert_id", sa.String(64), nullable=False),
        sa.Column("rule_name", sa.String(64), nullable=False),
        sa.Column("level", sa.String(4), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.Column("threshold", sa.Numeric(18, 4), nullable=False),
        sa.Column("message", sa.Text(), nullable=True, server_default=""),
        sa.Column("acknowledged", sa.Boolean(), nullable=True, server_default=sa.text("0")),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("routing_target", sa.String(64), nullable=True, server_default=""),
        sa.PrimaryKeyConstraint("alert_id"),
    )

    op.create_table(
        "alert_acknowledgments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("alert_id", sa.String(64), nullable=False),
        sa.Column("acknowledged_by", sa.String(64), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True, server_default=""),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.alert_id"]),
    )
    op.create_index("ix_alert_ack_alert_id", "alert_acknowledgments", ["alert_id"])


def downgrade() -> None:
    op.drop_index("ix_alert_ack_alert_id", table_name="alert_acknowledgments")
    op.drop_table("alert_acknowledgments")
    op.drop_table("alerts")
    op.drop_index("ix_chat_messages_chat_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")

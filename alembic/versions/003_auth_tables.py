"""Add users and user_sessions tables.

Revision ID: 003
Revises: 002
Create Date: 2026-04-18

"""
from alembic import op
import sqlalchemy as sa


revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=True, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "user_sessions",
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True, server_default=""),
        sa.Column("user_agent", sa.String(256), nullable=True, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("session_id"),
    )

    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_table("users")

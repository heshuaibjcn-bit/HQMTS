"""Add backtest_results table.

Revision ID: 002
Revises: 001
Create Date: 2026-04-16

"""
from alembic import op
import sqlalchemy as sa


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backtest_results",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("backtest_id", sa.String(64), nullable=False),
        sa.Column("strategy_name", sa.String(64), nullable=False),
        sa.Column("strategy_version", sa.String(16), nullable=False),
        sa.Column("strategy_params", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("instruments", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("cycle", sa.String(8), nullable=False),
        sa.Column("start_date", sa.String(8), nullable=False),
        sa.Column("end_date", sa.String(8), nullable=False),
        sa.Column("initial_cash", sa.Numeric(18, 4), nullable=False),
        sa.Column("final_total_asset", sa.Numeric(18, 4), nullable=False),
        sa.Column("total_return", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("annualized_return", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("max_drawdown", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("sharpe_ratio", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("total_trades", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("win_rate", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("profit_factor", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("trades", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("daily_values", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("cost_summary", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("data_version", sa.String(16), nullable=False, server_default="v1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("backtest_id"),
    )
    op.create_index("ix_backtest_strategy", "backtest_results", ["strategy_name", "strategy_version"])
    op.create_index("ix_backtest_dates", "backtest_results", ["start_date", "end_date"])


def downgrade() -> None:
    op.drop_index("ix_backtest_dates", table_name="backtest_results")
    op.drop_index("ix_backtest_strategy", table_name="backtest_results")
    op.drop_table("backtest_results")

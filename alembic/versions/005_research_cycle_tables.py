"""Add research_cycles, factor_discoveries, strategy_candidates tables.

Revision ID: 005
Revises: 004
Create Date: 2026-04-19

"""
from alembic import op
import sqlalchemy as sa


revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_cycles",
        sa.Column("research_cycle_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("opportunity_type", sa.String(32), nullable=False),
        sa.Column("opportunity_signal_json", sa.Text, server_default="{}"),
        sa.Column("status", sa.String(32), server_default="opportunity_identified"),
        sa.Column("research_project_id", sa.String(64), nullable=True),
        sa.Column("budget_json", sa.Text, server_default="{}"),
        sa.Column("budget_consumed_json", sa.Text, server_default="{}"),
        sa.Column("factor_discovery_ids_json", sa.Text, server_default="[]"),
        sa.Column("strategy_candidate_ids_json", sa.Text, server_default="[]"),
        sa.Column("autonomy_level", sa.String(16), server_default="level_2"),
        sa.Column("cycle_outcome", sa.String(32), nullable=True),
        sa.Column("outcome_reason", sa.Text, server_default=""),
        sa.Column("source_strategy_instance_id", sa.String(64), server_default=""),
        sa.Column("triggered_by", sa.String(64), server_default=""),
        sa.Column("agent_task_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("research_cycle_id"),
    )
    op.create_index("ix_rc_status", "research_cycles", ["status"])
    op.create_index("ix_rc_project", "research_cycles", ["research_project_id"])

    op.create_table(
        "factor_discoveries",
        sa.Column("factor_discovery_id", sa.String(64), nullable=False),
        sa.Column("research_cycle_id", sa.String(64), nullable=False),
        sa.Column("research_project_id", sa.String(64), nullable=False),
        sa.Column("factor_names_json", sa.Text, server_default="[]"),
        sa.Column("factor_combination", sa.String(256), server_default=""),
        sa.Column("discovery_type", sa.String(32), server_default="statistical"),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("hypothesis_id", sa.String(64), nullable=True),
        sa.Column("trial_plan_id", sa.String(64), nullable=True),
        sa.Column("metric_value", sa.Float, server_default="0"),
        sa.Column("adjusted_alpha", sa.Float, server_default="0.05"),
        sa.Column("is_significant", sa.Integer, server_default="0"),
        sa.Column("confidence", sa.Float, server_default="0.5"),
        sa.Column("market_regime", sa.String(32), server_default=""),
        sa.Column("instrument_scope_json", sa.Text, server_default="[]"),
        sa.Column("status", sa.String(16), server_default="candidate"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("factor_discovery_id"),
    )
    op.create_index("ix_fd_cycle", "factor_discoveries", ["research_cycle_id"])
    op.create_index("ix_fd_project", "factor_discoveries", ["research_project_id"])
    op.create_index("ix_fd_status", "factor_discoveries", ["status"])

    op.create_table(
        "strategy_candidates",
        sa.Column("strategy_candidate_id", sa.String(64), nullable=False),
        sa.Column("research_cycle_id", sa.String(64), nullable=False),
        sa.Column("factor_discovery_ids_json", sa.Text, server_default="[]"),
        sa.Column("source_factors_json", sa.Text, server_default="[]"),
        sa.Column("strategy_template_name", sa.String(64), server_default=""),
        sa.Column("strategy_params_json", sa.Text, server_default="{}"),
        sa.Column("param_ranges_json", sa.Text, server_default="{}"),
        sa.Column("ai_rationale", sa.Text, server_default=""),
        sa.Column("signal_logic_description", sa.Text, server_default=""),
        sa.Column("status", sa.String(16), server_default="generated"),
        sa.Column("backtest_result_ref", sa.String(64), nullable=True),
        sa.Column("backtest_sharpe", sa.Float, nullable=True),
        sa.Column("backtest_return", sa.Float, nullable=True),
        sa.Column("backtest_drawdown", sa.Float, nullable=True),
        sa.Column("backtest_trades", sa.Integer, nullable=True),
        sa.Column("evaluation_score", sa.Float, nullable=True),
        sa.Column("evaluation_verdict", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("strategy_candidate_id"),
    )
    op.create_index("ix_sc_cycle", "strategy_candidates", ["research_cycle_id"])
    op.create_index("ix_sc_status", "strategy_candidates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sc_status", table_name="strategy_candidates")
    op.drop_index("ix_sc_cycle", table_name="strategy_candidates")
    op.drop_table("strategy_candidates")

    op.drop_index("ix_fd_status", table_name="factor_discoveries")
    op.drop_index("ix_fd_project", table_name="factor_discoveries")
    op.drop_index("ix_fd_cycle", table_name="factor_discoveries")
    op.drop_table("factor_discoveries")

    op.drop_index("ix_rc_project", table_name="research_cycles")
    op.drop_index("ix_rc_status", table_name="research_cycles")
    op.drop_table("research_cycles")

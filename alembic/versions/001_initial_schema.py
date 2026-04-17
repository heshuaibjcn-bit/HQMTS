"""Initial HQMTS schema — all 25 tables.

Revision ID: 001
Revises:
Create Date: 2026-04-16 17:56:01

"""
from alembic import op
import sqlalchemy as sa


revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('accounts',
        sa.Column('account_id', sa.String(32)),
        sa.Column('total_asset', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('available_cash', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('frozen_cash', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('market_value', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('pnl_intraday', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('drawdown_intraday', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('currency', sa.String(8), nullable=False),
        sa.Column('risk_status', sa.String(16), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    op.create_table('agent_proposals',
        sa.Column('proposal_id', sa.String(64)),
        sa.Column('proposal_type', sa.String(32), nullable=False),
        sa.Column('source_agent_task_id', sa.String(64), nullable=False),
        sa.Column('target_object_type', sa.String(32), nullable=False),
        sa.Column('target_object_id', sa.String(64), nullable=False),
        sa.Column('proposal_payload', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('policy_result', sa.String(24), nullable=False),
        sa.Column('policy_check_id', sa.String(64)),
        sa.Column('status', sa.String(24), nullable=False, server_default='drafted'),
        sa.Column('approval_request_id', sa.String(64)),
        sa.Column('executed_result', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_ap_target", "agent_proposals", ['target_object_type', 'target_object_id'], unique=False)
    op.create_index("ix_ap_dedup", "agent_proposals", ['source_agent_task_id', 'proposal_type', 'target_object_id'], unique=True)
    op.create_index("ix_ap_task_status", "agent_proposals", ['source_agent_task_id', 'status'], unique=False)

    op.create_table('agent_tasks',
        sa.Column('agent_task_id', sa.String(64)),
        sa.Column('agent_role', sa.String(32), nullable=False),
        sa.Column('task_type', sa.String(32), nullable=False),
        sa.Column('environment', sa.String(16), nullable=False),
        sa.Column('input_ref', sa.Text()),
        sa.Column('output_ref', sa.Text()),
        sa.Column('workflow_version', sa.String(32), nullable=False),
        sa.Column('tool_plan', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('failure_reason', sa.Text(), nullable=False),
        sa.Column('triggered_by', sa.String(64), nullable=False),
        sa.Column('correlation_id', sa.String(64)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_at_correlation", "agent_tasks", ['correlation_id'], unique=False)
    op.create_index("ix_at_role_status", "agent_tasks", ['agent_role', 'status'], unique=False)
    op.create_index("ix_at_environment_status", "agent_tasks", ['environment', 'status'], unique=False)

    op.create_table('approval_requests',
        sa.Column('approval_request_id', sa.String(64)),
        sa.Column('source_type', sa.String(32), nullable=False),
        sa.Column('source_id', sa.String(64), nullable=False),
        sa.Column('approval_type', sa.String(32), nullable=False),
        sa.Column('requested_by', sa.String(64), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('approver', sa.String(64), nullable=False),
        sa.Column('approved_at', sa.DateTime(timezone=True)),
        sa.Column('decision', sa.String(16), nullable=False),
        sa.Column('decision_reason', sa.Text(), nullable=False),
        sa.Column('approval_snapshot_ref', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_ar_source", "approval_requests", ['source_type', 'source_id'], unique=False)
    op.create_index("ix_ar_status", "approval_requests", ['decision'], unique=False)
    op.create_index("ix_ar_dedup", "approval_requests", ['source_type', 'source_id', 'approval_type'], unique=True)

    op.create_table('audit_events',
        sa.Column('audit_event_id', sa.String(64)),
        sa.Column('event_type', sa.String(32), nullable=False),
        sa.Column('entity_type', sa.String(32), nullable=False),
        sa.Column('entity_id', sa.String(64), nullable=False),
        sa.Column('environment', sa.String(16), nullable=False),
        sa.Column('actor', sa.String(64), nullable=False),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('details_json', sa.Text(), nullable=False),
        sa.Column('alert_level', sa.String(4), nullable=False),
        sa.Column('correlation_id', sa.String(64)),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ae_timestamp", "audit_events", ['timestamp'], unique=False)
    op.create_index("ix_ae_event_type", "audit_events", ['event_type'], unique=False)
    op.create_index("ix_ae_correlation", "audit_events", ['correlation_id'], unique=False)
    op.create_index("ix_ae_entity", "audit_events", ['entity_type', 'entity_id'], unique=False)

    op.create_table('bars',
        sa.Column('id', sa.Integer()),
        sa.Column('instrument_id', sa.String(32), nullable=False),
        sa.Column('cycle', sa.String(4), nullable=False),
        sa.Column('bar_start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('bar_end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('open', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('high', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('low', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('close', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('volume', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('is_completed', sa.Boolean(), nullable=False),
        sa.Column('source', sa.String(32), nullable=False),
        sa.Column('data_version', sa.String(32), nullable=False),
        sa.Column('quality', sa.String(8), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_bars_instrument_cycle_version", "bars", ['instrument_id', 'cycle', 'data_version'], unique=False)
    op.create_index("ix_bars_instrument_cycle_time", "bars", ['instrument_id', 'cycle', 'bar_end_time'], unique=False)

    op.create_table('cash_reservations',
        sa.Column('reservation_id', sa.String(64)),
        sa.Column('account_id', sa.String(32), nullable=False),
        sa.Column('strategy_instance_id', sa.String(64), nullable=False),
        sa.Column('signal_id', sa.String(64)),
        sa.Column('execution_intent_id', sa.String(64)),
        sa.Column('reserved_amount', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('consumed_amount', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('currency', sa.String(8), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('released_reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_reservations_account_status", "cash_reservations", ['account_id', 'status'], unique=False)
    op.create_index("ix_reservations_dedup", "cash_reservations", ['account_id', 'execution_intent_id'], unique=True)

    op.create_table('controlled_executions',
        sa.Column('controlled_execution_id', sa.String(64)),
        sa.Column('source_proposal_id', sa.String(64), nullable=False),
        sa.Column('approval_request_id', sa.String(64)),
        sa.Column('action_type', sa.String(32), nullable=False),
        sa.Column('target_object_type', sa.String(32), nullable=False),
        sa.Column('target_object_id', sa.String(64), nullable=False),
        sa.Column('execution_status', sa.String(16), nullable=False),
        sa.Column('executed_by_service', sa.String(64), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('result_ref', sa.Text(), nullable=False),
        sa.Column('failure_reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_ce_target", "controlled_executions", ['target_object_type', 'target_object_id'], unique=False)
    op.create_index("ix_ce_proposal", "controlled_executions", ['source_proposal_id'], unique=False)
    op.create_index("ix_ce_status", "controlled_executions", ['execution_status'], unique=False)

    op.create_table('decision_snapshots',
        sa.Column('decision_snapshot_id', sa.String(64)),
        sa.Column('strategy_instance_id', sa.String(64), nullable=False),
        sa.Column('decision_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cycle', sa.String(4), nullable=False),
        sa.Column('feature_snapshot_id', sa.String(64)),
        sa.Column('bar_set_id', sa.String(64)),
        sa.Column('snapshot_completeness', sa.String(20), nullable=False),
        sa.Column('universe_scope_json', sa.Text(), nullable=False),
        sa.Column('data_version', sa.String(32)),
        sa.Column('feature_version', sa.String(32)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_ds_dedup", "decision_snapshots", ['strategy_instance_id', 'decision_time', 'bar_set_id'], unique=True)
    op.create_index("ix_ds_strategy_decision_time", "decision_snapshots", ['strategy_instance_id', 'decision_time'], unique=False)

    op.create_table('execution_intents',
        sa.Column('execution_intent_id', sa.String(64)),
        sa.Column('signal_id', sa.String(64), nullable=False),
        sa.Column('strategy_instance_id', sa.String(64), nullable=False),
        sa.Column('account_id', sa.String(32), nullable=False),
        sa.Column('instrument_id', sa.String(32), nullable=False),
        sa.Column('side', sa.String(8), nullable=False),
        sa.Column('target_quantity', sa.Integer(), nullable=False),
        sa.Column('reference_price', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('reservation_id', sa.String(64)),
        sa.Column('risk_check_id', sa.String(64)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    op.create_table('external_manual_events',
        sa.Column('external_event_id', sa.String(64)),
        sa.Column('account_id', sa.String(32), nullable=False),
        sa.Column('event_type', sa.String(32), nullable=False),
        sa.Column('broker_order_id', sa.String(64)),
        sa.Column('broker_trade_id', sa.String(64)),
        sa.Column('instrument_id', sa.String(32)),
        sa.Column('side', sa.String(8)),
        sa.Column('quantity', sa.Integer()),
        sa.Column('price', sa.Numeric(precision=12, scale=4)),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_confidence', sa.String(16), nullable=False),
        sa.Column('linked_internal_order_id', sa.String(64)),
        sa.Column('action_taken', sa.Text(), nullable=False),
        sa.Column('audit_note', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_eme_account_detected", "external_manual_events", ['account_id', 'detected_at'], unique=False)

    op.create_table('feature_snapshots',
        sa.Column('feature_snapshot_id', sa.String(64)),
        sa.Column('instrument_id', sa.String(32), nullable=False),
        sa.Column('decision_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cycle', sa.String(4), nullable=False),
        sa.Column('feature_set_version', sa.String(32), nullable=False),
        sa.Column('feature_values_json', sa.Text(), nullable=False),
        sa.Column('source_bar_versions_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_fs_instrument_decision_time", "feature_snapshots", ['instrument_id', 'decision_time'], unique=False)

    op.create_table('instruments',
        sa.Column('instrument_id', sa.String(32)),
        sa.Column('ts_code', sa.String(16), nullable=False),
        sa.Column('exchange', sa.String(8), nullable=False),
        sa.Column('symbol', sa.String(10), nullable=False),
        sa.Column('name', sa.String(64), nullable=False),
        sa.Column('listing_status', sa.String(4), nullable=False),
        sa.Column('board_type', sa.String(16), nullable=False),
        sa.Column('is_st', sa.Boolean(), nullable=False),
        sa.Column('lot_size', sa.Integer(), nullable=False),
        sa.Column('upper_limit_rule', sa.String(16), nullable=False),
        sa.Column('lower_limit_rule', sa.String(16), nullable=False),
        sa.Column('sector', sa.String(32), nullable=False),
        sa.Column('industry', sa.String(32), nullable=False),
        sa.Column('listing_date', sa.DateTime(timezone=True)),
        sa.Column('delist_date', sa.DateTime(timezone=True)),
        sa.Column('is_index', sa.Boolean(), nullable=False),
        sa.Column('constituent_of', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    op.create_table('order_requests',
        sa.Column('order_request_id', sa.String(64)),
        sa.Column('signal_id', sa.String(64), nullable=False),
        sa.Column('action_id', sa.String(64), nullable=False),
        sa.Column('account_id', sa.String(32), nullable=False),
        sa.Column('instrument_id', sa.String(32), nullable=False),
        sa.Column('side', sa.String(8), nullable=False),
        sa.Column('order_type', sa.String(8), nullable=False),
        sa.Column('price', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('tif', sa.String(8), nullable=False),
        sa.Column('submit_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('idempotency_key', sa.String(128), nullable=False),
        sa.Column('execution_intent_id', sa.String(64)),
        sa.Column('reservation_id', sa.String(64)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_or_idempotency", "order_requests", ['idempotency_key'], unique=True)

    op.create_table('orders',
        sa.Column('order_id', sa.String(64)),
        sa.Column('order_request_id', sa.String(64)),
        sa.Column('broker_order_id', sa.String(64)),
        sa.Column('account_id', sa.String(32), nullable=False),
        sa.Column('instrument_id', sa.String(32), nullable=False),
        sa.Column('side', sa.String(8), nullable=False),
        sa.Column('price', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('order_type', sa.String(16), nullable=False),
        sa.Column('signal_id', sa.String(64)),
        sa.Column('execution_intent_id', sa.String(64)),
        sa.Column('action_id', sa.String(64)),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('submitted_time', sa.DateTime(timezone=True)),
        sa.Column('updated_time', sa.DateTime(timezone=True)),
        sa.Column('filled_quantity', sa.Integer(), nullable=False),
        sa.Column('avg_fill_price', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('reject_reason', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_orders_broker_order_id", "orders", ['broker_order_id'], unique=False)
    op.create_index("ix_orders_account_status", "orders", ['account_id', 'status'], unique=False)
    op.create_index("ix_orders_instrument", "orders", ['instrument_id', 'created_at'], unique=False)

    op.create_table('positions',
        sa.Column('id', sa.Integer()),
        sa.Column('account_id', sa.String(32), nullable=False),
        sa.Column('instrument_id', sa.String(32), nullable=False),
        sa.Column('total_quantity', sa.Integer(), nullable=False),
        sa.Column('available_quantity', sa.Integer(), nullable=False),
        sa.Column('frozen_quantity', sa.Integer(), nullable=False),
        sa.Column('cost_price', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('market_value', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('market_price', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('realized_pnl', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('strategy_instance_id', sa.String(64), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_positions_account_instrument", "positions", ['account_id', 'instrument_id'], unique=True)

    op.create_table('reconciliation_sessions',
        sa.Column('reconciliation_session_id', sa.String(64)),
        sa.Column('scope_type', sa.String(20), nullable=False),
        sa.Column('scope_id', sa.String(64), nullable=False),
        sa.Column('expected_snapshot_ref', sa.Text()),
        sa.Column('broker_snapshot_ref', sa.Text()),
        sa.Column('diff_summary_json', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(16), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('resolution_status', sa.String(20), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    op.create_table('recovery_sessions',
        sa.Column('recovery_session_id', sa.String(64)),
        sa.Column('scope_type', sa.String(20), nullable=False),
        sa.Column('scope_id', sa.String(64), nullable=False),
        sa.Column('trigger_reason', sa.Text(), nullable=False),
        sa.Column('current_state_snapshot_ref', sa.Text()),
        sa.Column('proposed_actions_ref', sa.Text()),
        sa.Column('approval_required', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('final_result', sa.Text(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    op.create_table('risk_check_results',
        sa.Column('risk_check_id', sa.String(64)),
        sa.Column('signal_id', sa.String(64)),
        sa.Column('order_request_id', sa.String(64)),
        sa.Column('result_type', sa.String(20), nullable=False),
        sa.Column('resized_quantity', sa.Integer()),
        sa.Column('reject_reason', sa.Text(), nullable=False),
        sa.Column('triggered_rules_json', sa.Text(), nullable=False),
        sa.Column('check_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    op.create_table('signals',
        sa.Column('signal_id', sa.String(64)),
        sa.Column('strategy_instance_id', sa.String(64), nullable=False),
        sa.Column('strategy_version', sa.String(32), nullable=False),
        sa.Column('decision_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('instrument_id', sa.String(32), nullable=False),
        sa.Column('signal_type', sa.String(20), nullable=False),
        sa.Column('target_direction', sa.String(10)),
        sa.Column('target_position', sa.Numeric(precision=8, scale=4)),
        sa.Column('signal_strength', sa.Float(), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reason_code', sa.String(64), nullable=False),
        sa.Column('feature_snapshot_id', sa.String(64)),
        sa.Column('decision_snapshot_id', sa.String(64)),
        sa.Column('cycle', sa.String(4), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_signals_strategy_decision_time", "signals", ['strategy_instance_id', 'decision_time'], unique=False)
    op.create_index("ix_signals_instrument", "signals", ['instrument_id', 'decision_time'], unique=False)

    op.create_table('strategies',
        sa.Column('strategy_id', sa.String(64)),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('version', sa.String(32), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('supported_cycles', sa.Text(), nullable=False),
        sa.Column('param_schema_json', sa.Text(), nullable=False),
        sa.Column('default_params_json', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    op.create_table('strategy_instances',
        sa.Column('strategy_instance_id', sa.String(64)),
        sa.Column('strategy_id', sa.String(64), nullable=False),
        sa.Column('strategy_version', sa.String(32), nullable=False),
        sa.Column('environment', sa.String(16), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('params_json', sa.Text(), nullable=False),
        sa.Column('instruments_json', sa.Text(), nullable=False),
        sa.Column('account_id', sa.String(32)),
        sa.Column('cycle', sa.String(4), nullable=False),
        sa.Column('risk_config_override_json', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    op.create_table('tool_invocations',
        sa.Column('invocation_id', sa.String(64)),
        sa.Column('agent_task_id', sa.String(64), nullable=False),
        sa.Column('tool_name', sa.String(64), nullable=False),
        sa.Column('tool_version', sa.String(16), nullable=False),
        sa.Column('input_digest', sa.Text(), nullable=False),
        sa.Column('output_digest', sa.Text(), nullable=False),
        sa.Column('side_effect_level', sa.String(24), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('error_code', sa.String(32), nullable=False),
        sa.Column('policy_check_id', sa.String(64)),
        sa.Column('correlation_id', sa.String(64)),
        sa.Column('idempotency_key', sa.String(128)),
        sa.Column('environment', sa.String(16), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_ti_task", "tool_invocations", ['agent_task_id'], unique=False)
    op.create_index("ix_ti_tool_status", "tool_invocations", ['tool_name', 'status'], unique=False)
    op.create_index("ix_ti_dedup", "tool_invocations", ['agent_task_id', 'tool_name', 'idempotency_key'], unique=True)

    op.create_table('trades',
        sa.Column('trade_id', sa.String(64)),
        sa.Column('order_id', sa.String(64), nullable=False),
        sa.Column('instrument_id', sa.String(32), nullable=False),
        sa.Column('traded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('trade_price', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('trade_quantity', sa.Integer(), nullable=False),
        sa.Column('commission', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('stamp_tax', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('slippage', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('broker_trade_id', sa.String(64)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_trades_broker_trade_id", "trades", ['broker_trade_id'], unique=True)
    op.create_index("ix_trades_order", "trades", ['order_id'], unique=False)

    op.create_table('version_bindings',
        sa.Column('version_binding_id', sa.String(64)),
        sa.Column('entity_type', sa.String(32), nullable=False),
        sa.Column('entity_id', sa.String(64), nullable=False),
        sa.Column('data_version', sa.String(32), nullable=False),
        sa.Column('feature_version', sa.String(32), nullable=False),
        sa.Column('strategy_version', sa.String(32), nullable=False),
        sa.Column('param_version', sa.String(32), nullable=False),
        sa.Column('risk_rule_version', sa.String(32), nullable=False),
        sa.Column('execution_policy_version', sa.String(32), nullable=False),
        sa.Column('engine_version', sa.String(32), nullable=False),
        sa.Column('qmt_adapter_version', sa.String(32), nullable=False),
        sa.Column('agent_workflow_version', sa.String(32), nullable=False),
        sa.Column('tool_version', sa.String(32), nullable=False),
        sa.Column('prompt_version', sa.String(32), nullable=False),
        sa.Column('live_config_version', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index("ix_vb_entity", "version_bindings", ['entity_type', 'entity_id'], unique=False)



def downgrade() -> None:
    op.drop_index("ix_vb_entity", table_name="version_bindings")
    op.drop_table("version_bindings")
    op.drop_index("ix_trades_broker_trade_id", table_name="trades")
    op.drop_index("ix_trades_order", table_name="trades")
    op.drop_table("trades")
    op.drop_index("ix_ti_task", table_name="tool_invocations")
    op.drop_index("ix_ti_tool_status", table_name="tool_invocations")
    op.drop_index("ix_ti_dedup", table_name="tool_invocations")
    op.drop_table("tool_invocations")
    op.drop_table("strategy_instances")
    op.drop_table("strategies")
    op.drop_index("ix_signals_strategy_decision_time", table_name="signals")
    op.drop_index("ix_signals_instrument", table_name="signals")
    op.drop_table("signals")
    op.drop_table("risk_check_results")
    op.drop_table("recovery_sessions")
    op.drop_table("reconciliation_sessions")
    op.drop_index("ix_positions_account_instrument", table_name="positions")
    op.drop_table("positions")
    op.drop_index("ix_orders_broker_order_id", table_name="orders")
    op.drop_index("ix_orders_account_status", table_name="orders")
    op.drop_index("ix_orders_instrument", table_name="orders")
    op.drop_table("orders")
    op.drop_index("ix_or_idempotency", table_name="order_requests")
    op.drop_table("order_requests")
    op.drop_table("instruments")
    op.drop_index("ix_fs_instrument_decision_time", table_name="feature_snapshots")
    op.drop_table("feature_snapshots")
    op.drop_index("ix_eme_account_detected", table_name="external_manual_events")
    op.drop_table("external_manual_events")
    op.drop_table("execution_intents")
    op.drop_index("ix_ds_dedup", table_name="decision_snapshots")
    op.drop_index("ix_ds_strategy_decision_time", table_name="decision_snapshots")
    op.drop_table("decision_snapshots")
    op.drop_index("ix_ce_target", table_name="controlled_executions")
    op.drop_index("ix_ce_proposal", table_name="controlled_executions")
    op.drop_index("ix_ce_status", table_name="controlled_executions")
    op.drop_table("controlled_executions")
    op.drop_index("ix_reservations_account_status", table_name="cash_reservations")
    op.drop_index("ix_reservations_dedup", table_name="cash_reservations")
    op.drop_table("cash_reservations")
    op.drop_index("ix_bars_instrument_cycle_version", table_name="bars")
    op.drop_index("ix_bars_instrument_cycle_time", table_name="bars")
    op.drop_table("bars")
    op.drop_index("ix_ae_timestamp", table_name="audit_events")
    op.drop_index("ix_ae_event_type", table_name="audit_events")
    op.drop_index("ix_ae_correlation", table_name="audit_events")
    op.drop_index("ix_ae_entity", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_ar_source", table_name="approval_requests")
    op.drop_index("ix_ar_status", table_name="approval_requests")
    op.drop_index("ix_ar_dedup", table_name="approval_requests")
    op.drop_table("approval_requests")
    op.drop_index("ix_at_correlation", table_name="agent_tasks")
    op.drop_index("ix_at_role_status", table_name="agent_tasks")
    op.drop_index("ix_at_environment_status", table_name="agent_tasks")
    op.drop_table("agent_tasks")
    op.drop_index("ix_ap_target", table_name="agent_proposals")
    op.drop_index("ix_ap_dedup", table_name="agent_proposals")
    op.drop_index("ix_ap_task_status", table_name="agent_proposals")
    op.drop_table("agent_proposals")
    op.drop_table("accounts")

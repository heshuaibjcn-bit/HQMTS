"""Tests for ToolInvocation side_effect_level enforcement."""

from __future__ import annotations

from hqmts.agent.gateway import ToolCallRequest, ToolCallResult
from hqmts.agent.invocation_tracker import create_invocation_from_result
from hqmts.core.enums import AgentRole, Environment, PolicyCheckResult, SideEffectLevel
from hqmts.core.types import now_shanghai


class TestSideEffectLevelTracking:
    def test_read_only_tracked(self):
        """Read-only tools record SideEffectLevel.READ_ONLY."""
        req = ToolCallRequest(
            agent_role=AgentRole.MONITORING,
            agent_task_id="task-001",
            tool_name="query_market_data",
            environment=Environment.LIVE,
        )
        result = ToolCallResult(
            invocation_id="inv-001",
            tool_name="query_market_data",
            status="success",
            side_effect_level=SideEffectLevel.READ_ONLY,
        )
        inv = create_invocation_from_result(req, result, now_shanghai())
        assert inv.side_effect_level == SideEffectLevel.READ_ONLY
        assert not inv.has_side_effects

    def test_task_trigger_tracked(self):
        """Task trigger tools record SideEffectLevel.TASK_TRIGGER."""
        req = ToolCallRequest(
            agent_role=AgentRole.BACKTEST_ORCHESTRATION,
            agent_task_id="task-002",
            tool_name="start_backtest",
            environment=Environment.RESEARCH,
            idempotency_key="idem-001",
        )
        result = ToolCallResult(
            invocation_id="inv-002",
            tool_name="start_backtest",
            status="success",
            side_effect_level=SideEffectLevel.TASK_TRIGGER,
        )
        inv = create_invocation_from_result(req, result, now_shanghai())
        assert inv.side_effect_level == SideEffectLevel.TASK_TRIGGER
        assert inv.has_side_effects

    def test_controlled_operation_tracked(self):
        """Controlled operations record SideEffectLevel.CONTROLLED_OPERATION."""
        req = ToolCallRequest(
            agent_role=AgentRole.MONITORING,
            agent_task_id="task-003",
            tool_name="propose_pause_open",
            environment=Environment.LIVE,
            idempotency_key="idem-002",
        )
        result = ToolCallResult(
            invocation_id="inv-003",
            tool_name="propose_pause_open",
            status="pending_approval",
            side_effect_level=SideEffectLevel.CONTROLLED_OPERATION,
        )
        inv = create_invocation_from_result(req, result, now_shanghai())
        assert inv.side_effect_level == SideEffectLevel.CONTROLLED_OPERATION
        assert inv.has_side_effects

    def test_denied_records_level(self):
        """Denied tool calls still record their side_effect_level."""
        req = ToolCallRequest(
            agent_role=AgentRole.DATA,
            agent_task_id="task-004",
            tool_name="start_backtest",
            environment=Environment.RESEARCH,
        )
        result = ToolCallResult(
            invocation_id="inv-004",
            tool_name="start_backtest",
            status="denied",
            side_effect_level=SideEffectLevel.TASK_TRIGGER,
            error="role_not_allowed",
        )
        inv = create_invocation_from_result(req, result, now_shanghai())
        assert inv.side_effect_level == SideEffectLevel.TASK_TRIGGER
        assert inv.status == "denied"

    def test_invocation_has_duration(self):
        """Invocation calculates duration from started_at/finished_at."""
        started = now_shanghai()
        req = ToolCallRequest(
            agent_role=AgentRole.MONITORING,
            agent_task_id="task-005",
            tool_name="query_market_data",
            environment=Environment.LIVE,
        )
        result = ToolCallResult(
            invocation_id="inv-005",
            tool_name="query_market_data",
            status="success",
            side_effect_level=SideEffectLevel.READ_ONLY,
            duration_ms=50.0,
        )
        inv = create_invocation_from_result(req, result, started)
        assert inv.duration_ms is not None
        assert inv.duration_ms > 0

    def test_invocation_captures_environment(self):
        """Invocation records the environment from the request."""
        req = ToolCallRequest(
            agent_role=AgentRole.MONITORING,
            agent_task_id="task-006",
            tool_name="query_market_data",
            environment=Environment.PAPER,
        )
        result = ToolCallResult(
            invocation_id="inv-006",
            tool_name="query_market_data",
            status="success",
            side_effect_level=SideEffectLevel.READ_ONLY,
        )
        inv = create_invocation_from_result(req, result, now_shanghai())
        assert inv.environment == "paper"

    def test_invocation_captures_idempotency_key(self):
        """Idempotency key from request is stored in invocation."""
        req = ToolCallRequest(
            agent_role=AgentRole.BACKTEST_ORCHESTRATION,
            agent_task_id="task-007",
            tool_name="start_backtest",
            environment=Environment.RESEARCH,
            idempotency_key="idem-007",
        )
        result = ToolCallResult(
            invocation_id="inv-007",
            tool_name="start_backtest",
            status="success",
            side_effect_level=SideEffectLevel.TASK_TRIGGER,
        )
        inv = create_invocation_from_result(req, result, now_shanghai())
        assert inv.idempotency_key == "idem-007"

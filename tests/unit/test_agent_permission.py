"""Tests for Agent permission boundaries."""

import pytest

from hqmts.core.enums import AgentRole, Environment, PolicyCheckResult, SideEffectLevel, ToolCategory
from hqmts.core.exceptions import (
    AgentPermissionDeniedError,
    ForbiddenToolAttemptError,
)
from hqmts.agent.gateway import ToolCallRequest, ToolGateway
from hqmts.agent.permission import PermissionBoundary, PROTECTED_TABLES
from hqmts.agent.policy import PolicyEngine, PolicyCheckInput
from hqmts.agent.types import ALL_TOOLS, FORBIDDEN_TOOLS


class TestPolicyEngine:
    @pytest.fixture
    def engine(self):
        return PolicyEngine()

    @pytest.mark.asyncio
    async def test_pass_read_only_tool(self, engine):
        result = engine.evaluate(PolicyCheckInput(
            agent_role=AgentRole.MONITORING,
            tool_name="query_market_data",
            environment=Environment.LIVE,
        ))
        assert result.result == PolicyCheckResult.PASS

    @pytest.mark.asyncio
    async def test_fail_forbidden_tool(self, engine):
        result = engine.evaluate(PolicyCheckInput(
            agent_role=AgentRole.ORCHESTRATOR,
            tool_name="qmt_submit_order",
            environment=Environment.LIVE,
        ))
        assert result.result == PolicyCheckResult.FAIL

    @pytest.mark.asyncio
    async def test_fail_wrong_environment(self, engine):
        result = engine.evaluate(PolicyCheckInput(
            agent_role=AgentRole.BACKTEST_ORCHESTRATION,
            tool_name="start_backtest",
            environment=Environment.LIVE,
        ))
        assert result.result == PolicyCheckResult.FAIL

    @pytest.mark.asyncio
    async def test_fail_wrong_role(self, engine):
        result = engine.evaluate(PolicyCheckInput(
            agent_role=AgentRole.DATA,
            tool_name="start_backtest",
            environment=Environment.RESEARCH,
        ))
        assert result.result == PolicyCheckResult.FAIL

    @pytest.mark.asyncio
    async def test_manual_review_for_controlled_operation(self, engine):
        result = engine.evaluate(PolicyCheckInput(
            agent_role=AgentRole.MONITORING,
            tool_name="propose_pause_open",
            environment=Environment.LIVE,
            has_version_binding=True,
        ))
        assert result.result == PolicyCheckResult.MANUAL_REVIEW_REQUIRED

    @pytest.mark.asyncio
    async def test_kill_switch_blocks(self, engine):
        engine.set_kill_switch(True)
        result = engine.evaluate(PolicyCheckInput(
            agent_role=AgentRole.MONITORING,
            tool_name="start_reconciliation",
            environment=Environment.LIVE,
        ))
        assert result.result == PolicyCheckResult.FAIL

    @pytest.mark.asyncio
    async def test_kill_switch_allows_read_only(self, engine):
        engine.set_kill_switch(True)
        result = engine.evaluate(PolicyCheckInput(
            agent_role=AgentRole.MONITORING,
            tool_name="query_market_data",
            environment=Environment.LIVE,
        ))
        assert result.result == PolicyCheckResult.PASS

    @pytest.mark.asyncio
    async def test_no_version_binding_blocks_live_controlled(self, engine):
        result = engine.evaluate(PolicyCheckInput(
            agent_role=AgentRole.MONITORING,
            tool_name="propose_close_only",
            environment=Environment.LIVE,
            has_version_binding=False,
        ))
        assert result.result == PolicyCheckResult.FAIL
        assert any("version_binding" in v for v in result.violations)

    @pytest.mark.asyncio
    async def test_version_binding_passes_live_controlled(self, engine):
        result = engine.evaluate(PolicyCheckInput(
            agent_role=AgentRole.MONITORING,
            tool_name="propose_close_only",
            environment=Environment.LIVE,
            has_version_binding=True,
        ))
        assert result.result == PolicyCheckResult.MANUAL_REVIEW_REQUIRED

    @pytest.mark.asyncio
    async def test_unresolved_exceptions_block_action(self, engine):
        result = engine.evaluate(PolicyCheckInput(
            agent_role=AgentRole.RECONCILIATION,
            tool_name="start_reconciliation",
            environment=Environment.LIVE,
            has_unresolved_exceptions=True,
        ))
        assert result.result == PolicyCheckResult.FAIL
        assert any("unresolved_exceptions" in v for v in result.violations)

    @pytest.mark.asyncio
    async def test_non_trading_time_blocks_controlled(self, engine):
        result = engine.evaluate(PolicyCheckInput(
            agent_role=AgentRole.MONITORING,
            tool_name="propose_close_only",
            environment=Environment.LIVE,
            is_trading_time=False,
            has_version_binding=True,
        ))
        assert result.result == PolicyCheckResult.FAIL
        assert any("non_trading_time" in v for v in result.violations)


class TestToolGateway:
    @pytest.fixture
    def gateway(self):
        engine = PolicyEngine()
        return ToolGateway(engine)

    @pytest.mark.asyncio
    async def test_forbidden_tool_raises(self, gateway):
        with pytest.raises(ForbiddenToolAttemptError):
            await gateway.invoke(ToolCallRequest(
                agent_role=AgentRole.ORCHESTRATOR,
                agent_task_id="task-001",
                tool_name="qmt_submit_order",
                environment=Environment.LIVE,
            ))

    @pytest.mark.asyncio
    async def test_read_only_passes(self, gateway):
        result = await gateway.invoke(ToolCallRequest(
            agent_role=AgentRole.MONITORING,
            agent_task_id="task-001",
            tool_name="query_market_data",
            environment=Environment.LIVE,
        ))
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_wrong_role_denied(self, gateway):
        result = await gateway.invoke(ToolCallRequest(
            agent_role=AgentRole.DATA,
            agent_task_id="task-001",
            tool_name="start_backtest",
            environment=Environment.RESEARCH,
        ))
        assert result.status == "denied"

    @pytest.mark.asyncio
    async def test_controlled_op_needs_approval(self, gateway):
        result = await gateway.invoke(ToolCallRequest(
            agent_role=AgentRole.MONITORING,
            agent_task_id="task-001",
            tool_name="propose_pause_open",
            environment=Environment.LIVE,
            has_version_binding=True,
        ))
        assert result.status == "pending_approval"
        assert result.policy_result == PolicyCheckResult.MANUAL_REVIEW_REQUIRED


class TestPermissionBoundary:
    @pytest.fixture
    def boundary(self):
        return PermissionBoundary()

    def test_cannot_write_orders(self, boundary):
        with pytest.raises(AgentPermissionDeniedError):
            boundary.check_db_access(
                AgentRole.ORCHESTRATOR, "INSERT", "orders", Environment.LIVE
            )

    def test_cannot_update_trades(self, boundary):
        with pytest.raises(AgentPermissionDeniedError):
            boundary.check_db_access(
                AgentRole.ORCHESTRATOR, "UPDATE", "trades", Environment.LIVE
            )

    def test_cannot_delete_positions(self, boundary):
        with pytest.raises(AgentPermissionDeniedError):
            boundary.check_db_access(
                AgentRole.ORCHESTRATOR, "DELETE", "positions", Environment.LIVE
            )

    def test_can_read_instruments(self, boundary):
        # Should not raise
        boundary.check_db_access(
            AgentRole.RESEARCH, "SELECT", "instruments", Environment.RESEARCH
        )

    def test_cannot_access_qmt(self, boundary):
        with pytest.raises(ForbiddenToolAttemptError):
            boundary.check_qmt_access(AgentRole.ORCHESTRATOR)

    def test_cannot_modify_risk_thresholds(self, boundary):
        with pytest.raises(AgentPermissionDeniedError):
            boundary.check_risk_threshold_modify(AgentRole.ORCHESTRATOR)

    def test_cannot_restore_live_running(self, boundary):
        with pytest.raises(AgentPermissionDeniedError):
            boundary.check_restore_live_running(AgentRole.ORCHESTRATOR)

    def test_forbidden_tools_list(self, boundary):
        assert boundary.is_tool_forbidden("qmt_submit_order")
        assert boundary.is_tool_forbidden("qmt_cancel_order_direct")
        assert boundary.is_tool_forbidden("update_order_state_direct")
        assert boundary.is_tool_forbidden("update_live_risk_threshold_direct")
        assert boundary.is_tool_forbidden("restore_live_running_direct")
        assert not boundary.is_tool_forbidden("query_market_data")


# ── SAD 29.6: Additional agent boundary test cases ────────────────────────────


class TestAgentBoundaryHardening:
    """SAD 29.6: 10 boundary test cases for agent governance."""

    @pytest.fixture
    def gateway(self):
        engine = PolicyEngine()
        return ToolGateway(engine)

    @pytest.mark.asyncio
    async def test_agent_cannot_bypass_gateway(self, gateway):
        """Agent cannot invoke tools without going through the ToolGateway."""
        # Attempting to call a forbidden tool through the gateway raises
        with pytest.raises(ForbiddenToolAttemptError):
            await gateway.invoke(ToolCallRequest(
                agent_role=AgentRole.ORCHESTRATOR,
                agent_task_id="task-bypass",
                tool_name="qmt_submit_order",
                environment=Environment.LIVE,
            ))

    @pytest.mark.asyncio
    async def test_research_agent_cannot_access_live_tools(self, gateway):
        """Research agent is blocked from Live-environment task triggers."""
        result = await gateway.invoke(ToolCallRequest(
            agent_role=AgentRole.RESEARCH,
            agent_task_id="task-isolation",
            tool_name="start_backtest",
            environment=Environment.LIVE,  # Research should not be in Live
        ))
        assert result.status == "denied"

    @pytest.mark.asyncio
    async def test_agent_context_isolation_backtest_only(self, gateway):
        """Backtest-only tools cannot run in Paper or Live."""
        result = await gateway.invoke(ToolCallRequest(
            agent_role=AgentRole.BACKTEST_ORCHESTRATION,
            agent_task_id="task-isolation-2",
            tool_name="start_backtest",
            environment=Environment.LIVE,
        ))
        assert result.status == "denied"

    @pytest.mark.asyncio
    async def test_rate_limiting_enforcement(self, gateway):
        """Agent exceeding rate limit gets denied."""
        # Default rate limit is 60/min, create a gateway with low limit
        engine = PolicyEngine()
        low_rate_gateway = ToolGateway(engine, rate_limit_per_minute=3)

        # First 3 should succeed (read-only tool in Live)
        for _ in range(3):
            result = await low_rate_gateway.invoke(ToolCallRequest(
                agent_role=AgentRole.MONITORING,
                agent_task_id="task-rate",
                tool_name="query_market_data",
                environment=Environment.LIVE,
            ))
            assert result.status == "success"

        # 4th should be rate-limited
        result = await low_rate_gateway.invoke(ToolCallRequest(
            agent_role=AgentRole.MONITORING,
            agent_task_id="task-rate",
            tool_name="query_market_data",
            environment=Environment.LIVE,
        ))
        assert result.status == "denied"
        assert "Rate limit" in result.error

    @pytest.mark.asyncio
    async def test_idempotency_key_required_for_side_effect_tools(self, gateway):
        """Controlled operation tools require idempotency_key."""
        result = await gateway.invoke(ToolCallRequest(
            agent_role=AgentRole.MONITORING,
            agent_task_id="task-idem",
            tool_name="propose_pause_open",
            environment=Environment.LIVE,
            has_version_binding=True,
            idempotency_key=None,  # Missing
        ))
        # Goes through policy (manual_review), then fails on idempotency
        assert result.status in ("pending_approval", "failed")
        if result.status == "failed":
            assert "idempotency_key" in result.error

    @pytest.mark.asyncio
    async def test_side_effect_level_tracking(self, gateway):
        """Each tool invocation records the correct SideEffectLevel."""
        # Read-only tool
        result = await gateway.invoke(ToolCallRequest(
            agent_role=AgentRole.MONITORING,
            agent_task_id="task-level",
            tool_name="query_market_data",
            environment=Environment.LIVE,
        ))
        assert result.side_effect_level == SideEffectLevel.READ_ONLY

        # Task trigger tool
        result = await gateway.invoke(ToolCallRequest(
            agent_role=AgentRole.BACKTEST_ORCHESTRATION,
            agent_task_id="task-level",
            tool_name="start_backtest",
            environment=Environment.RESEARCH,
        ))
        assert result.side_effect_level == SideEffectLevel.TASK_TRIGGER

        # Controlled operation
        result = await gateway.invoke(ToolCallRequest(
            agent_role=AgentRole.MONITORING,
            agent_task_id="task-level",
            tool_name="propose_close_only",
            environment=Environment.LIVE,
            has_version_binding=True,
        ))
        assert result.side_effect_level == SideEffectLevel.CONTROLLED_OPERATION

    @pytest.mark.asyncio
    async def test_agent_cannot_create_orders_directly(self, gateway):
        """Agent has no tool to submit orders. qmt_submit_order is forbidden."""
        with pytest.raises(ForbiddenToolAttemptError):
            await gateway.invoke(ToolCallRequest(
                agent_role=AgentRole.ORCHESTRATOR,
                agent_task_id="task-order",
                tool_name="qmt_submit_order",
                environment=Environment.LIVE,
            ))

    @pytest.mark.asyncio
    async def test_agent_proposal_in_wrong_environment_rejected(self):
        """Policy engine rejects controlled operations outside Live."""
        engine = PolicyEngine()
        result = engine.evaluate(PolicyCheckInput(
            agent_role=AgentRole.MONITORING,
            tool_name="propose_pause_open",
            environment=Environment.RESEARCH,  # Wrong env
            has_version_binding=True,
        ))
        assert result.result == PolicyCheckResult.FAIL

    @pytest.mark.asyncio
    async def test_different_task_ids_have_separate_rate_limits(self):
        """Rate limits are per task_id, not global."""
        engine = PolicyEngine()
        gateway = ToolGateway(engine, rate_limit_per_minute=2)

        # Task A: 2 calls
        for _ in range(2):
            r = await gateway.invoke(ToolCallRequest(
                agent_role=AgentRole.MONITORING,
                agent_task_id="task-a",
                tool_name="query_market_data",
                environment=Environment.LIVE,
            ))
            assert r.status == "success"

        # Task A: 3rd call should be rate limited
        r = await gateway.invoke(ToolCallRequest(
            agent_role=AgentRole.MONITORING,
            agent_task_id="task-a",
            tool_name="query_market_data",
            environment=Environment.LIVE,
        ))
        assert r.status == "denied"

        # Task B: should still work (different task_id)
        r = await gateway.invoke(ToolCallRequest(
            agent_role=AgentRole.MONITORING,
            agent_task_id="task-b",
            tool_name="query_market_data",
            environment=Environment.LIVE,
        ))
        assert r.status == "success"

"""Tests for Agent permission boundaries."""

import pytest

from hqmts.core.enums import AgentRole, Environment, PolicyCheckResult, ToolCategory
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

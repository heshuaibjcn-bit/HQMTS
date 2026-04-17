"""Tests for agent audit service."""

from __future__ import annotations

import pytest

from hqmts.core.enums import AlertLevel, Environment
from hqmts.agent.audit_service import AgentAuditService


class TestAgentAuditService:
    @pytest.mark.asyncio
    async def test_record_task_created(self):
        svc = AgentAuditService()
        event = await svc.record_task_created("task-1", "research_agent", "Analyze trend factors")
        assert event.event_type == "agent_task_created"
        assert event.entity_type == "agent_task"
        assert event.entity_id == "task-1"
        assert event.actor == "research_agent"
        assert event.details["description"] == "Analyze trend factors"

    @pytest.mark.asyncio
    async def test_record_policy_evaluation(self):
        svc = AgentAuditService()
        event = await svc.record_policy_evaluation("task-1", "research_agent", "denied", ["no_approval"])
        assert event.event_type == "agent_policy_evaluation"
        assert event.details["policy_result"] == "denied"
        assert event.details["violations"] == ["no_approval"]

    @pytest.mark.asyncio
    async def test_record_policy_denied_uses_p2(self):
        svc = AgentAuditService()
        event = await svc.record_policy_evaluation("task-1", "agent", "denied")
        assert event.alert_level == AlertLevel.P2

    @pytest.mark.asyncio
    async def test_record_proposal_submitted(self):
        svc = AgentAuditService()
        event = await svc.record_proposal_submitted("prop-1", "task-1", "data_agent", "data_query")
        assert event.event_type == "agent_proposal_submitted"
        assert event.entity_type == "agent_proposal"
        assert event.entity_id == "prop-1"
        assert event.details["proposal_type"] == "data_query"

    @pytest.mark.asyncio
    async def test_record_approval_decision_approved(self):
        svc = AgentAuditService()
        event = await svc.record_approval_decision("prop-1", "human_operator", "approved", "Looks good")
        assert event.event_type == "agent_approval_decision"
        assert event.details["decision"] == "approved"

    @pytest.mark.asyncio
    async def test_record_approval_decision_rejected(self):
        svc = AgentAuditService()
        event = await svc.record_approval_decision("prop-1", "human_operator", "rejected", "Risk too high")
        assert event.details["decision"] == "rejected"
        assert event.details["reason"] == "Risk too high"

    @pytest.mark.asyncio
    async def test_record_tool_invocation(self):
        svc = AgentAuditService()
        event = await svc.record_tool_invocation(
            "task-1", "research_agent", "query_data", "read_only", "success",
        )
        assert event.event_type == "agent_tool_invocation"
        assert event.action == "invoke_tool:query_data"
        assert event.details["side_effect_level"] == "read_only"

    @pytest.mark.asyncio
    async def test_record_controlled_execution(self):
        svc = AgentAuditService()
        event = await svc.record_controlled_execution("exec-1", "prop-1", "system", "completed")
        assert event.event_type == "agent_controlled_execution"
        assert event.entity_type == "controlled_execution"
        assert event.entity_id == "exec-1"

    @pytest.mark.asyncio
    async def test_record_unauthorized_attempt(self):
        svc = AgentAuditService()
        event = await svc.record_unauthorized_attempt("data_agent", "write_order", "No write permission")
        assert event.event_type == "agent_unauthorized_attempt"
        assert event.alert_level == AlertLevel.P1
        assert event.details["reason"] == "No write permission"

    @pytest.mark.asyncio
    async def test_record_task_state_change(self):
        svc = AgentAuditService()
        event = await svc.record_task_state_change("task-1", "research_agent", "created", "planning")
        assert event.event_type == "agent_task_state_change"
        assert event.action == "transition:created->planning"
        assert event.details["from_state"] == "created"

    @pytest.mark.asyncio
    async def test_events_are_immutable(self):
        svc = AgentAuditService()
        event = await svc.record_task_created("task-1", "research_agent", "test")
        assert event.model_config.get("frozen") is True

    @pytest.mark.asyncio
    async def test_environment_propagated(self):
        svc = AgentAuditService(environment=Environment.LIVE)
        event = await svc.record_task_created("task-1", "agent", "test")
        assert event.environment == Environment.LIVE

    @pytest.mark.asyncio
    async def test_correlation_id_propagated(self):
        svc = AgentAuditService()
        event = await svc.record_task_created("task-1", "agent", "test", correlation_id="corr-123")
        assert event.correlation_id == "corr-123"

    @pytest.mark.asyncio
    async def test_unique_audit_event_ids(self):
        svc = AgentAuditService()
        e1 = await svc.record_task_created("task-1", "agent", "a")
        e2 = await svc.record_task_created("task-2", "agent", "b")
        assert e1.audit_event_id != e2.audit_event_id

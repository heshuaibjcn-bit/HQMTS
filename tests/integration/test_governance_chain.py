"""Integration tests for Agent Governance Service.

Tests the full Proposal -> Approval -> Execution chain.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.core.enums import (
    AgentRole,
    AgentTaskStatus,
    ApprovalStatus,
    Environment,
    ExecutionStatus,
    PolicyCheckResult,
    ProposalStatus,
)
from hqmts.agent.policy import PolicyEngine
from hqmts.agent.service import AgentGovernanceService
from hqmts.db.repositories.agent_repos import (
    AgentProposalRepository,
    AgentTaskRepository,
    ApprovalRequestRepository,
    ControlledExecutionRepository,
)
from hqmts.domain.agent_proposal import AgentProposal
from hqmts.domain.agent_task import AgentTask
from hqmts.domain.approval_request import ApprovalRequest
from hqmts.domain.controlled_execution import ControlledExecution


@pytest.fixture
def policy_engine():
    return PolicyEngine()


@pytest.fixture
def service(session, policy_engine):
    return AgentGovernanceService(
        task_repo=AgentTaskRepository(session),
        proposal_repo=AgentProposalRepository(session),
        approval_repo=ApprovalRequestRepository(session),
        execution_repo=ControlledExecutionRepository(session),
        policy_engine=policy_engine,
    )


class TestAgentGovernanceService:
    """Full governance chain tests."""

    @pytest.mark.asyncio
    async def test_research_auto_approved(self, service, session):
        """Research environment auto-approves and executes."""
        result = await service.run_full_pipeline(
            agent_role=AgentRole.RESEARCH.value,
            environment=Environment.RESEARCH.value,
            task_type="analysis",
            proposal_type="pause_open",
            target_object_type="strategy_instance",
            target_object_id="strat-001",
            proposal_payload='{"reason": "market_analysis"}',
            confidence=0.8,
        )

        assert isinstance(result, ControlledExecution)
        assert result.execution_status == ExecutionStatus.PENDING
        assert result.action_type == "pause_open"
        assert result.target_object_id == "strat-001"

        await session.commit()

    @pytest.mark.asyncio
    async def test_live_needs_approval(self, service, session):
        """Live environment requires manual approval for controlled operations."""
        result = await service.run_full_pipeline(
            agent_role=AgentRole.MONITORING.value,
            environment=Environment.LIVE.value,
            task_type="risk_action",
            proposal_type="close_only",
            target_object_type="strategy_instance",
            target_object_id="strat-002",
        )

        assert isinstance(result, ApprovalRequest)
        assert result.decision == ApprovalStatus.PENDING
        assert result.source_type == "agent_proposal"

        await session.commit()

    @pytest.mark.asyncio
    async def test_full_chain_with_approval(self, service, session):
        """Full chain: create -> proposal -> policy -> approval -> execution."""
        result = await service.run_full_pipeline(
            agent_role=AgentRole.MONITORING.value,
            environment=Environment.LIVE.value,
            task_type="risk_action",
            proposal_type="close_only",
            target_object_type="strategy_instance",
            target_object_id="strat-003",
            approver="human_admin",  # Auto-approve for this test
        )

        assert isinstance(result, ControlledExecution)
        assert result.execution_status == ExecutionStatus.PENDING

        await session.commit()

    @pytest.mark.asyncio
    async def test_step_by_step_research_flow(self, service, session):
        """Step-by-step test: create task -> proposal -> policy -> execute."""
        # Step 1: Create task
        task = await service.create_task(
            agent_role=AgentRole.RESEARCH.value,
            task_type="analysis",
            environment=Environment.RESEARCH.value,
            triggered_by="user:test",
        )
        assert isinstance(task, AgentTask)
        assert task.status == AgentTaskStatus.CREATED
        await session.commit()

        # Step 2: Start task
        task = await service.start_task(task.agent_task_id)
        assert task.status == AgentTaskStatus.RUNNING
        await session.commit()

        # Step 3: Create proposal
        proposal = await service.create_proposal(
            agent_task_id=task.agent_task_id,
            proposal_type="pause_open",
            target_object_type="strategy_instance",
            target_object_id="strat-004",
            confidence=0.75,
        )
        assert isinstance(proposal, AgentProposal)
        assert proposal.confidence == 0.75
        assert proposal.policy_result == ""  # Not yet evaluated
        await session.commit()

        # Step 4: Policy check
        proposal = await service.evaluate_proposal_policy(
            proposal_id=proposal.proposal_id,
            agent_role=AgentRole.RESEARCH.value,
            environment=Environment.RESEARCH.value,
        )
        assert proposal.policy_result == PolicyCheckResult.PASS.value
        assert proposal.approval_status == ProposalStatus.APPROVED.value
        await session.commit()

        # Step 5: Execute
        execution = await service.execute_proposal(proposal.proposal_id)
        assert isinstance(execution, ControlledExecution)
        assert execution.execution_status == ExecutionStatus.PENDING
        assert execution.source_proposal_id == proposal.proposal_id
        await session.commit()

        # Step 6: Complete execution
        execution = await service.complete_execution(
            execution.controlled_execution_id,
            result_ref="action_completed:paused",
        )
        assert execution.execution_status == ExecutionStatus.COMPLETED
        assert execution.result_ref == "action_completed:paused"
        await session.commit()

    @pytest.mark.asyncio
    async def test_approval_rejection_blocks_execution(self, service, session):
        """Approval rejection prevents execution."""
        # Create proposal needing approval (Live + controlled operation)
        task = await service.create_task(
            agent_role=AgentRole.MONITORING.value,
            task_type="action",
            environment=Environment.LIVE.value,
            triggered_by="test",
        )
        await service.start_task(task.agent_task_id)
        await session.commit()

        proposal = await service.create_proposal(
            agent_task_id=task.agent_task_id,
            proposal_type="close_only",
            target_object_type="strategy_instance",
            target_object_id="strat-reject",
        )
        await session.commit()

        # Policy check -> manual review
        proposal = await service.evaluate_proposal_policy(
            proposal_id=proposal.proposal_id,
            agent_role=AgentRole.MONITORING.value,
            environment=Environment.LIVE.value,
        )
        assert proposal.policy_result == PolicyCheckResult.MANUAL_REVIEW_REQUIRED.value
        await session.commit()

        # Create approval request
        approval = await service.create_approval_request(
            proposal_id=proposal.proposal_id,
            approval_type="agent_close_only",
            requested_by="agent:risk_analyst",
        )
        assert approval.decision == ApprovalStatus.PENDING
        await session.commit()

        # Reject
        approval = await service.process_approval_decision(
            approval_request_id=approval.approval_request_id,
            approver="admin",
            decision=ApprovalStatus.REJECTED.value,
            reason="Not appropriate for current market",
        )
        assert approval.decision == ApprovalStatus.REJECTED
        await session.commit()

        # Verify proposal is now rejected
        proposal = await service._proposal_repo.get_domain(proposal.proposal_id)
        assert proposal.approval_status == ProposalStatus.REJECTED.value

        # Execution should fail
        from hqmts.core.exceptions import AgentPermissionDeniedError

        with pytest.raises(AgentPermissionDeniedError):
            await service.execute_proposal(proposal.proposal_id)

    @pytest.mark.asyncio
    async def test_execution_failure_tracking(self, service, session):
        """Failed executions are tracked with failure_reason."""
        # Research auto-approved
        result = await service.run_full_pipeline(
            agent_role=AgentRole.RESEARCH.value,
            environment=Environment.RESEARCH.value,
            task_type="analysis",
            proposal_type="correction",
            target_object_type="position",
            target_object_id="pos-001",
        )
        await session.commit()

        # Mark execution as failed
        execution = await service.complete_execution(
            result.controlled_execution_id,
            failure_reason="Target position not found",
        )
        assert execution.execution_status == ExecutionStatus.FAILED
        assert execution.failure_reason == "Target position not found"

    @pytest.mark.asyncio
    async def test_cannot_propose_from_terminal_task(self, service, session):
        """Terminal tasks cannot produce proposals."""
        task = await service.create_task(
            agent_role=AgentRole.RESEARCH.value,
            task_type="analysis",
            environment=Environment.RESEARCH.value,
            triggered_by="test",
        )
        # Manually set to completed
        task.status = AgentTaskStatus.COMPLETED
        task = await service._task_repo.update_domain(task)
        await session.commit()

        from hqmts.core.exceptions import AgentPermissionDeniedError

        with pytest.raises(AgentPermissionDeniedError):
            await service.create_proposal(
                agent_task_id=task.agent_task_id,
                proposal_type="pause_open",
                target_object_type="strategy_instance",
                target_object_id="strat-005",
            )

    @pytest.mark.asyncio
    async def test_kill_switch_blocks_live(self, service, session, policy_engine):
        """Kill switch blocks all live proposals."""
        policy_engine.set_kill_switch(True)

        result = await service.run_full_pipeline(
            agent_role=AgentRole.MONITORING.value,
            environment=Environment.LIVE.value,
            task_type="emergency",
            proposal_type="close_only",
            target_object_type="strategy_instance",
            target_object_id="strat-006",
        )
        await session.commit()

        # Should get rejected proposal
        assert isinstance(result, AgentProposal)
        assert result.policy_result == PolicyCheckResult.FAIL.value

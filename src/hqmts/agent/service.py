"""Agent governance service orchestrating Proposal → Approval → Execution.

Implements the full governance chain from SAD 24:
1. Agent creates a Proposal via AgentTask
2. Policy Engine evaluates the proposal
3. If manual_review_required → create ApprovalRequest
4. If approved (or auto-approved) → create ControlledExecution
5. ControlledExecution tracks the execution outcome
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.core.enums import (
    AgentTaskStatus,
    ApprovalStatus,
    Environment,
    ExecutionStatus,
    PolicyCheckResult,
    ProposalStatus,
)
from hqmts.core.exceptions import (
    AgentPermissionDeniedError,
    PolicyViolationError,
)
from hqmts.agent.gateway import ToolCallRequest, ToolCallResult, ToolGateway
from hqmts.agent.policy import PolicyCheckInput, PolicyEngine
from hqmts.db.models.agent_proposal import AgentProposalORM
from hqmts.db.models.agent_task import AgentTaskORM
from hqmts.db.models.approval_request import ApprovalRequestORM
from hqmts.db.models.controlled_execution import ControlledExecutionORM
from hqmts.db.repositories.base import BaseRepository


class AgentGovernanceService:
    """Full lifecycle: AgentTask → Proposal → Approval → Execution.

    This service enforces that NO Agent action directly modifies
    core trading state. All mutations go through the governance chain.
    """

    def __init__(self, session: AsyncSession, policy_engine: PolicyEngine) -> None:
        self._session = session
        self._policy_engine = policy_engine
        self._task_repo = BaseRepository(AgentTaskORM, session)
        self._proposal_repo = BaseRepository(AgentProposalORM, session)
        self._approval_repo = BaseRepository(ApprovalRequestORM, session)
        self._execution_repo = BaseRepository(ControlledExecutionORM, session)

    # ── Step 1: Create AgentTask ───────────────────────────────────────────

    async def create_task(
        self,
        agent_role: str,
        task_type: str,
        environment: str,
        triggered_by: str,
        input_ref: str | None = None,
        workflow_version: str = "v1",
        tool_plan: str = "[]",
        correlation_id: str | None = None,
    ) -> AgentTaskORM:
        """Create a new agent task."""
        now = datetime.now()
        task = AgentTaskORM(
            agent_task_id=str(uuid.uuid4()),
            agent_role=agent_role,
            task_type=task_type,
            environment=environment,
            input_ref=input_ref,
            workflow_version=workflow_version,
            tool_plan=tool_plan,
            status=AgentTaskStatus.CREATED.value,
            triggered_by=triggered_by,
            correlation_id=correlation_id,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        return await self._task_repo.create(task)

    async def start_task(self, task_id: str) -> AgentTaskORM:
        """Transition task to running."""
        task = await self._task_repo.get_by_id(task_id, id_column="agent_task_id")
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        task.status = AgentTaskStatus.RUNNING.value
        task.updated_at = datetime.now()
        return await self._task_repo.update(task)

    # ── Step 2: Create Proposal ────────────────────────────────────────────

    async def create_proposal(
        self,
        agent_task_id: str,
        proposal_type: str,
        target_object_type: str,
        target_object_id: str,
        proposal_payload: str = "{}",
        confidence: float = 0.0,
    ) -> AgentProposalORM:
        """Create a proposal from a running agent task.

        Validates: task must be in a state that can produce proposals.
        """
        task = await self._task_repo.get_by_id(agent_task_id, id_column="agent_task_id")
        if task is None:
            raise ValueError(f"Task {agent_task_id} not found")

        if task.status not in (
            AgentTaskStatus.RUNNING.value,
            AgentTaskStatus.WAITING_TOOL.value,
        ):
            raise AgentPermissionDeniedError(
                agent_role=task.agent_role,
                tool_name="create_proposal",
                reason=f"Task {agent_task_id} in status {task.status} cannot produce proposals",
            )

        now = datetime.now()
        proposal = AgentProposalORM(
            proposal_id=str(uuid.uuid4()),
            proposal_type=proposal_type,
            source_agent_task_id=agent_task_id,
            target_object_type=target_object_type,
            target_object_id=target_object_id,
            proposal_payload=proposal_payload,
            confidence=confidence,
            policy_result="",
            approval_status="",
            created_at=now,
            updated_at=now,
        )
        return await self._proposal_repo.create(proposal)

    # ── Step 3: Policy Check ───────────────────────────────────────────────

    async def evaluate_proposal_policy(
        self,
        proposal_id: str,
        agent_role: str,
        environment: str,
    ) -> AgentProposalORM:
        """Run the proposal through the Policy Engine.

        Updates proposal with policy_result:
        - pass → auto-approved, can proceed to execution
        - manual_review_required → needs ApprovalRequest
        - fail → rejected
        """
        proposal = await self._proposal_repo.get_by_id(
            proposal_id, id_column="proposal_id"
        )
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")

        # Build policy input — map proposal_type to a tool-like check
        policy_input = PolicyCheckInput(
            agent_role=agent_role,
            tool_name=f"proposal:{proposal.proposal_type}",
            environment=Environment(environment),
            target_object_type=proposal.target_object_type,
            target_object_id=proposal.target_object_id,
            proposal_type=proposal.proposal_type,
        )

        # For proposals, we check if the type itself is allowed
        # by using a simplified policy evaluation
        policy_output = self._evaluate_proposal_policy(policy_input)

        now = datetime.now()
        proposal.policy_check_id = str(uuid.uuid4())
        proposal.policy_result = policy_output.result.value
        proposal.updated_at = now

        if policy_output.result == PolicyCheckResult.FAIL:
            proposal.approval_status = ProposalStatus.POLICY_REJECTED.value
        elif policy_output.result == PolicyCheckResult.MANUAL_REVIEW_REQUIRED:
            proposal.approval_status = ProposalStatus.PENDING_APPROVAL.value
        else:
            # Auto-approved for non-live or low-risk proposals
            proposal.approval_status = ProposalStatus.APPROVED.value

        return await self._proposal_repo.update(proposal)

    def _evaluate_proposal_policy(self, input_data: PolicyCheckInput):
        """Simplified policy evaluation for proposals.

        Rules:
        - All proposals are allowed in research/backtest
        - In paper: read-only and task_trigger auto-approved, controlled_operation needs review
        - In live: all controlled_operations need manual review
        """
        from hqmts.agent.policy import PolicyCheckOutput

        violations: list[str] = []

        # Kill switch check
        if self._policy_engine._global_kill_switch:
            violations.append("kill_switch_active")

        if violations:
            return PolicyCheckOutput(
                result=PolicyCheckResult.FAIL,
                reason=f"Policy violations: {'; '.join(violations)}",
                violations=violations,
            )

        # Environment-based policy
        if input_data.environment in (Environment.RESEARCH, Environment.BACKTEST):
            return PolicyCheckOutput(
                result=PolicyCheckResult.PASS,
                reason="Auto-approved in research/backtest environment",
                violations=[],
            )

        if input_data.environment == Environment.PAPER:
            # Paper: controlled operations need review
            if input_data.proposal_type in (
                "close_only",
                "risk_param_change",
                "recovery_action",
            ):
                return PolicyCheckOutput(
                    result=PolicyCheckResult.MANUAL_REVIEW_REQUIRED,
                    reason=f"Proposal type '{input_data.proposal_type}' requires review in Paper",
                    violations=[],
                )
            return PolicyCheckOutput(
                result=PolicyCheckResult.PASS,
                reason="Auto-approved in Paper environment",
                violations=[],
            )

        # Live: all non-trivial proposals need manual review
        if input_data.proposal_type in (
            "pause_open",
            "close_only",
            "correction",
            "risk_param_change",
            "recovery_action",
        ):
            return PolicyCheckOutput(
                result=PolicyCheckResult.MANUAL_REVIEW_REQUIRED,
                reason=f"Proposal type '{input_data.proposal_type}' requires manual approval in Live",
                violations=[],
            )

        return PolicyCheckOutput(
            result=PolicyCheckResult.PASS,
            reason="Auto-approved",
            violations=[],
        )

    # ── Step 4: Create Approval Request ────────────────────────────────────

    async def create_approval_request(
        self,
        proposal_id: str,
        approval_type: str,
        requested_by: str,
        expires_at: datetime | None = None,
    ) -> ApprovalRequestORM:
        """Create an approval request for a proposal that requires manual review."""
        proposal = await self._proposal_repo.get_by_id(
            proposal_id, id_column="proposal_id"
        )
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.policy_result != PolicyCheckResult.MANUAL_REVIEW_REQUIRED.value:
            raise PolicyViolationError(
                f"Proposal {proposal_id} policy result is '{proposal.policy_result}', "
                f"expected 'manual_review_required'"
            )

        now = datetime.now()
        approval = ApprovalRequestORM(
            approval_request_id=str(uuid.uuid4()),
            source_type="agent_proposal",
            source_id=proposal_id,
            approval_type=approval_type,
            requested_by=requested_by,
            requested_at=now,
            decision="pending",
            expires_at=expires_at or now.replace(
                hour=23, minute=59, second=59
            ),
            created_at=now,
            updated_at=now,
        )
        approval = await self._approval_repo.create(approval)

        # Link proposal to approval request
        proposal.approval_request_id = approval.approval_request_id
        proposal.updated_at = now
        await self._proposal_repo.update(proposal)

        return approval

    # ── Step 5: Process Approval Decision ──────────────────────────────────

    async def process_approval_decision(
        self,
        approval_request_id: str,
        approver: str,
        decision: str,
        reason: str = "",
    ) -> ApprovalRequestORM:
        """Process a human approval decision.

        Updates both the ApprovalRequest and the linked Proposal.
        """
        approval = await self._approval_repo.get_by_id(
            approval_request_id, id_column="approval_request_id"
        )
        if approval is None:
            raise ValueError(f"Approval request {approval_request_id} not found")

        if approval.decision != "pending":
            raise ValueError(
                f"Approval request {approval_request_id} already decided: {approval.decision}"
            )

        now = datetime.now()
        approval.approver = approver
        approval.decision = decision
        approval.decision_reason = reason
        approval.approved_at = now
        approval.updated_at = now
        await self._approval_repo.update(approval)

        # Update linked proposal
        if approval.source_type == "agent_proposal":
            proposal = await self._proposal_repo.get_by_field(
                "approval_request_id", approval_request_id
            )
            if proposal is not None:
                if decision == ApprovalStatus.APPROVED.value:
                    proposal.approval_status = ProposalStatus.APPROVED.value
                elif decision == ApprovalStatus.REJECTED.value:
                    proposal.approval_status = ProposalStatus.REJECTED.value
                proposal.updated_at = now
                await self._proposal_repo.update(proposal)

        return approval

    # ── Step 6: Execute Approved Proposal ──────────────────────────────────

    async def execute_proposal(
        self,
        proposal_id: str,
        executed_by_service: str = "agent_governance",
    ) -> ControlledExecutionORM:
        """Execute an approved proposal via ControlledExecution.

        Validates: proposal must be approved (policy pass + approval pass).
        """
        proposal = await self._proposal_repo.get_by_id(
            proposal_id, id_column="proposal_id"
        )
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.approval_status != ProposalStatus.APPROVED.value:
            raise AgentPermissionDeniedError(
                agent_role="system",
                tool_name="execute_proposal",
                reason=f"Proposal {proposal_id} not approved (status: {proposal.approval_status})",
            )

        now = datetime.now()
        execution = ControlledExecutionORM(
            controlled_execution_id=str(uuid.uuid4()),
            source_proposal_id=proposal_id,
            approval_request_id=proposal.approval_request_id,
            action_type=proposal.proposal_type,
            target_object_type=proposal.target_object_type,
            target_object_id=proposal.target_object_id,
            execution_status=ExecutionStatus.PENDING.value,
            executed_by_service=executed_by_service,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        return await self._execution_repo.create(execution)

    async def complete_execution(
        self,
        execution_id: str,
        result_ref: str = "",
        failure_reason: str = "",
    ) -> ControlledExecutionORM:
        """Mark a ControlledExecution as completed or failed."""
        execution = await self._execution_repo.get_by_id(
            execution_id, id_column="controlled_execution_id"
        )
        if execution is None:
            raise ValueError(f"Execution {execution_id} not found")

        now = datetime.now()
        execution.completed_at = now
        execution.updated_at = now

        if failure_reason:
            execution.execution_status = ExecutionStatus.FAILED.value
            execution.failure_reason = failure_reason
        else:
            execution.execution_status = ExecutionStatus.COMPLETED.value
            execution.result_ref = result_ref

        return await self._execution_repo.update(execution)

    # ── Full Pipeline ──────────────────────────────────────────────────────

    async def run_full_pipeline(
        self,
        agent_role: str,
        environment: str,
        task_type: str,
        proposal_type: str,
        target_object_type: str,
        target_object_id: str,
        proposal_payload: str = "{}",
        confidence: float = 0.0,
        triggered_by: str = "system",
        approver: str | None = None,
    ) -> ControlledExecutionORM | ApprovalRequestORM | AgentProposalORM:
        """Run the full governance pipeline in one call.

        Returns:
        - ControlledExecutionORM if auto-approved and executed
        - ApprovalRequestORM if manual review required
        - AgentProposalORM if rejected by policy
        """
        # Step 1: Create and start task
        task = await self.create_task(
            agent_role=agent_role,
            task_type=task_type,
            environment=environment,
            triggered_by=triggered_by,
        )
        task = await self.start_task(task.agent_task_id)

        # Step 2: Create proposal
        proposal = await self.create_proposal(
            agent_task_id=task.agent_task_id,
            proposal_type=proposal_type,
            target_object_type=target_object_type,
            target_object_id=target_object_id,
            proposal_payload=proposal_payload,
            confidence=confidence,
        )

        # Step 3: Policy check
        proposal = await self.evaluate_proposal_policy(
            proposal_id=proposal.proposal_id,
            agent_role=agent_role,
            environment=environment,
        )

        # Step 4a: Rejected by policy
        if proposal.policy_result == PolicyCheckResult.FAIL.value:
            await self._complete_task(task.agent_task_id, "policy_rejected")
            return proposal

        # Step 4b: Needs manual approval
        if proposal.policy_result == PolicyCheckResult.MANUAL_REVIEW_REQUIRED.value:
            approval = await self.create_approval_request(
                proposal_id=proposal.proposal_id,
                approval_type=f"agent_{proposal_type}",
                requested_by=f"agent:{agent_role}",
            )
            await self._complete_task(task.agent_task_id, "waiting_approval")

            # If approver provided, auto-approve for testing
            if approver:
                approval = await self.process_approval_decision(
                    approval_request_id=approval.approval_request_id,
                    approver=approver,
                    decision=ApprovalStatus.APPROVED.value,
                )
                # Continue to execution
                execution = await self.execute_proposal(proposal.proposal_id)
                await self._complete_task(task.agent_task_id, "completed")
                return execution

            return approval

        # Step 4c: Auto-approved — execute
        execution = await self.execute_proposal(proposal.proposal_id)
        await self._complete_task(task.agent_task_id, "completed")
        return execution

    async def _complete_task(
        self, task_id: str, reason: str = ""
    ) -> None:
        """Mark task as completed."""
        task = await self._task_repo.get_by_id(task_id, id_column="agent_task_id")
        if task is not None:
            now = datetime.now()
            task.status = AgentTaskStatus.COMPLETED.value
            task.completed_at = now
            task.updated_at = now
            await self._task_repo.update(task)

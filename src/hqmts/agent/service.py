"""Agent governance service orchestrating Proposal -> Approval -> Execution.

Implements the full governance chain from SAD 24:
1. Agent creates a Proposal via AgentTask
2. Policy Engine evaluates the proposal
3. If manual_review_required -> create ApprovalRequest
4. If approved (or auto-approved) -> create ControlledExecution
5. ControlledExecution tracks the execution outcome
"""

from __future__ import annotations

import uuid
from datetime import datetime

from hqmts.core.enums import (
    AgentTaskStatus,
    AgentRole,
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
from hqmts.core.types import (
    AgentTaskId,
    ApprovalRequestId,
    ControlledExecutionId,
    ProposalId,
)
from hqmts.agent.gateway import ToolCallRequest, ToolCallResult, ToolGateway
from hqmts.agent.policy import PolicyCheckInput, PolicyEngine
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
from hqmts.statemachine.agent_task_fsm import agent_task_fsm
from hqmts.statemachine.agent_proposal_fsm import agent_proposal_fsm
from hqmts.statemachine.approval_fsm import approval_fsm
from hqmts.statemachine.controlled_execution_fsm import controlled_execution_fsm
from hqmts.core.types import now_shanghai


class AgentGovernanceService:
    """Full lifecycle: AgentTask -> Proposal -> Approval -> Execution.

    This service enforces that NO Agent action directly modifies
    core trading state. All mutations go through the governance chain.

    All public methods return Pydantic domain models, not ORM objects.
    """

    def __init__(
        self,
        task_repo: AgentTaskRepository,
        proposal_repo: AgentProposalRepository,
        approval_repo: ApprovalRequestRepository,
        execution_repo: ControlledExecutionRepository,
        policy_engine: PolicyEngine,
    ) -> None:
        self._task_repo = task_repo
        self._proposal_repo = proposal_repo
        self._approval_repo = approval_repo
        self._execution_repo = execution_repo
        self._policy_engine = policy_engine

    # -- Step 1: Create AgentTask ------------------------------------------

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
    ) -> AgentTask:
        """Create a new agent task. Returns domain model."""
        now = now_shanghai()
        task = AgentTask(
            agent_task_id=AgentTaskId(str(uuid.uuid4())),
            agent_role=agent_role,
            task_type=task_type,
            environment=Environment(environment),
            input_ref=input_ref,
            workflow_version=workflow_version,
            tool_plan=tool_plan,
            status=AgentTaskStatus.CREATED,
            triggered_by=triggered_by,
            correlation_id=correlation_id,
            created_at=now,
        )
        return await self._task_repo.create_domain(task)

    async def start_task(self, task_id: str) -> AgentTask:
        """Transition task: CREATED -> PLANNING -> RUNNING. Returns domain model."""
        task = await self._task_repo.get_domain(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        # CREATED -> PLANNING -> RUNNING (two-step per FSM)
        task.status = agent_task_fsm.transition(task.status, AgentTaskStatus.PLANNING)
        task.status = agent_task_fsm.transition(task.status, AgentTaskStatus.RUNNING)
        task.started_at = now_shanghai()
        return await self._task_repo.update_domain(task)

    # -- Step 2: Create Proposal -------------------------------------------

    async def create_proposal(
        self,
        agent_task_id: str,
        proposal_type: str,
        target_object_type: str,
        target_object_id: str,
        proposal_payload: str = "{}",
        confidence: float = 0.0,
    ) -> AgentProposal:
        """Create a proposal from a running agent task.

        Validates: task must be in a state that can produce proposals.
        Returns domain model.
        """
        task = await self._task_repo.get_domain(agent_task_id)
        if task is None:
            raise ValueError(f"Task {agent_task_id} not found")

        if not task.can_produce_proposals():
            raise AgentPermissionDeniedError(
                agent_role=task.agent_role,
                tool_name="create_proposal",
                reason=f"Task {agent_task_id} in status {task.status.value} cannot produce proposals",
            )

        now = now_shanghai()
        proposal = AgentProposal(
            proposal_id=ProposalId(str(uuid.uuid4())),
            proposal_type=proposal_type,
            source_agent_task_id=AgentTaskId(agent_task_id),
            target_object_type=target_object_type,
            target_object_id=target_object_id,
            proposal_payload=proposal_payload,
            confidence=confidence,
            status=ProposalStatus.DRAFTED,
            policy_result="",
            created_at=now,
        )
        return await self._proposal_repo.create_domain(proposal)

    # -- Step 3: Policy Check ----------------------------------------------

    async def evaluate_proposal_policy(
        self,
        proposal_id: str,
        agent_role: str,
        environment: str,
    ) -> AgentProposal:
        """Run the proposal through the Policy Engine.

        Updates proposal with policy_result. Returns domain model.
        """
        proposal = await self._proposal_repo.get_domain(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")

        policy_input = PolicyCheckInput(
            agent_role=agent_role,
            tool_name=f"proposal:{proposal.proposal_type}",
            environment=Environment(environment),
            target_object_type=proposal.target_object_type,
            target_object_id=proposal.target_object_id,
            proposal_type=proposal.proposal_type,
        )

        policy_output = self._evaluate_proposal_policy(policy_input)

        proposal.policy_check_id = str(uuid.uuid4())
        proposal.policy_result = policy_output.result.value

        if policy_output.result == PolicyCheckResult.FAIL:
            target_status = ProposalStatus.POLICY_REJECTED
        elif policy_output.result == PolicyCheckResult.MANUAL_REVIEW_REQUIRED:
            target_status = ProposalStatus.PENDING_APPROVAL
        else:
            target_status = ProposalStatus.APPROVED
        proposal.status = agent_proposal_fsm.transition(
            ProposalStatus.POLICY_CHECKING, target_status,
        )

        return await self._proposal_repo.update_domain(proposal)

    def _evaluate_proposal_policy(self, input_data: PolicyCheckInput):
        """Simplified policy evaluation for proposals.

        Rules:
        - All proposals are allowed in research/backtest
        - In paper: controlled_operation needs review
        - In live: all controlled_operations need manual review
        """
        from hqmts.agent.policy import PolicyCheckOutput

        violations: list[str] = []

        if self._policy_engine.is_kill_switch_active():
            violations.append("kill_switch_active")

        if violations:
            return PolicyCheckOutput(
                result=PolicyCheckResult.FAIL,
                reason=f"Policy violations: {'; '.join(violations)}",
                violations=violations,
            )

        if input_data.environment in (Environment.RESEARCH, Environment.BACKTEST):
            return PolicyCheckOutput(
                result=PolicyCheckResult.PASS,
                reason="Auto-approved in research/backtest environment",
                violations=[],
            )

        if input_data.environment == Environment.PAPER:
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

    # -- Step 4: Create Approval Request -----------------------------------

    async def create_approval_request(
        self,
        proposal_id: str,
        approval_type: str,
        requested_by: str,
        expires_at: datetime | None = None,
    ) -> ApprovalRequest:
        """Create an approval request for a proposal needing manual review."""
        proposal = await self._proposal_repo.get_domain(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.policy_result != PolicyCheckResult.MANUAL_REVIEW_REQUIRED.value:
            raise PolicyViolationError(
                f"Proposal {proposal_id} policy result is '{proposal.policy_result}', "
                f"expected 'manual_review_required'"
            )

        now = now_shanghai()
        approval = ApprovalRequest(
            approval_request_id=ApprovalRequestId(str(uuid.uuid4())),
            source_type="agent_proposal",
            source_id=proposal_id,
            approval_type=approval_type,
            requested_by=requested_by,
            requested_at=now,
            expires_at=expires_at or now.replace(hour=23, minute=59, second=59),
        )
        approval = await self._approval_repo.create_domain(approval)

        # Link proposal to approval request
        proposal.approval_request_id = approval.approval_request_id
        await self._proposal_repo.update_domain(proposal)

        return approval

    # -- Step 5: Process Approval Decision ---------------------------------

    async def process_approval_decision(
        self,
        approval_request_id: str,
        approver: str,
        decision: str,
        reason: str = "",
    ) -> ApprovalRequest:
        """Process a human approval decision. Returns domain model."""
        approval = await self._approval_repo.get_domain(approval_request_id)
        if approval is None:
            raise ValueError(f"Approval request {approval_request_id} not found")

        if approval.is_decided():
            raise ValueError(
                f"Approval request {approval_request_id} already decided: {approval.decision.value}"
            )

        now = now_shanghai()
        approval.approver = approver
        approval.decision = approval_fsm.transition(
            approval.decision, ApprovalStatus(decision),
        )
        approval.decision_reason = reason
        approval.approved_at = now
        approval = await self._approval_repo.update_domain(approval)

        # Update linked proposal
        if approval.source_type == "agent_proposal":
            proposal = await self._proposal_repo.get_domain(approval.source_id)
            if proposal is not None:
                if decision == ApprovalStatus.APPROVED.value:
                    proposal.status = agent_proposal_fsm.transition(
                        ProposalStatus.PENDING_APPROVAL, ProposalStatus.APPROVED,
                    )
                elif decision == ApprovalStatus.REJECTED.value:
                    proposal.status = agent_proposal_fsm.transition(
                        ProposalStatus.PENDING_APPROVAL, ProposalStatus.REJECTED,
                    )
                await self._proposal_repo.update_domain(proposal)

        return approval

    # -- Step 6: Execute Approved Proposal ---------------------------------

    async def execute_proposal(
        self,
        proposal_id: str,
        executed_by_service: str = "agent_governance",
    ) -> ControlledExecution:
        """Execute an approved proposal via ControlledExecution."""
        proposal = await self._proposal_repo.get_domain(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status != ProposalStatus.APPROVED:
            raise AgentPermissionDeniedError(
                agent_role="system",
                tool_name="execute_proposal",
                reason=f"Proposal {proposal_id} not approved (status: {proposal.status.value})",
            )

        # Transition proposal: approved -> execution_pending
        proposal.status = agent_proposal_fsm.transition(
            ProposalStatus.APPROVED, ProposalStatus.EXECUTION_PENDING,
        )
        await self._proposal_repo.update_domain(proposal)

        now = now_shanghai()
        execution = ControlledExecution(
            controlled_execution_id=ControlledExecutionId(str(uuid.uuid4())),
            source_proposal_id=ProposalId(proposal_id),
            approval_request_id=ApprovalRequestId(proposal.approval_request_id) if proposal.approval_request_id else None,
            action_type=proposal.proposal_type,
            target_object_type=proposal.target_object_type,
            target_object_id=proposal.target_object_id,
            execution_status=ExecutionStatus.EXECUTING,
            executed_by_service=executed_by_service,
            started_at=now,
        )
        return await self._execution_repo.create_domain(execution)

    async def complete_execution(
        self,
        execution_id: str,
        result_ref: str = "",
        failure_reason: str = "",
    ) -> ControlledExecution:
        """Mark a ControlledExecution as completed or failed."""
        execution = await self._execution_repo.get_domain(execution_id)
        if execution is None:
            raise ValueError(f"Execution {execution_id} not found")

        now = now_shanghai()
        execution.completed_at = now

        if failure_reason:
            execution.execution_status = controlled_execution_fsm.transition(
                execution.execution_status, ExecutionStatus.FAILED,
            )
            execution.failure_reason = failure_reason
        else:
            execution.execution_status = controlled_execution_fsm.transition(
                execution.execution_status, ExecutionStatus.COMPLETED,
            )
            execution.result_ref = result_ref

        return await self._execution_repo.update_domain(execution)

    # -- Full Pipeline -----------------------------------------------------

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
    ) -> ControlledExecution | ApprovalRequest | AgentProposal:
        """Run the full governance pipeline in one call.

        Returns:
        - ControlledExecution if auto-approved and executed
        - ApprovalRequest if manual review required
        - AgentProposal if rejected by policy
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
            # Transition task to WAITING_TOOL (waiting for approval result)
            await self._wait_task(task.agent_task_id)

            # If approver provided, auto-approve for testing
            # Guard: auto-approve only allowed in non-Live environments
            if approver and environment != Environment.LIVE.value:
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

        # Step 4c: Auto-approved - execute
        execution = await self.execute_proposal(proposal.proposal_id)
        await self._complete_task(task.agent_task_id, "completed")
        return execution

    async def _complete_task(
        self, task_id: str, reason: str = ""
    ) -> None:
        """Mark task as completed or failed based on reason."""
        task = await self._task_repo.get_domain(task_id)
        if task is not None:
            now = now_shanghai()
            if reason in ("policy_rejected",):
                target = AgentTaskStatus.FAILED
            else:
                target = AgentTaskStatus.COMPLETED
            # If waiting, resume to running first
            if task.status == AgentTaskStatus.WAITING_TOOL:
                task.status = agent_task_fsm.transition(
                    task.status, AgentTaskStatus.RUNNING,
                )
            task.status = agent_task_fsm.transition(task.status, target)
            task.completed_at = now
            task.failure_reason = reason if target == AgentTaskStatus.FAILED else ""
            await self._task_repo.update_domain(task)

    async def _wait_task(self, task_id: str) -> None:
        """Transition task from RUNNING to WAITING_TOOL."""
        task = await self._task_repo.get_domain(task_id)
        if task is not None:
            task.status = agent_task_fsm.transition(task.status, AgentTaskStatus.WAITING_TOOL)
            await self._task_repo.update_domain(task)

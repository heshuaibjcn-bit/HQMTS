"""Typed repositories for the agent governance domain.

Each repository handles ORM ↔ domain model mapping, keeping the service
layer clean of ORM details.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.core.enums import (
    AgentTaskStatus,
    ApprovalStatus,
    Environment,
    ExecutionStatus,
    ProposalStatus,
)
from hqmts.core.types import (
    AgentTaskId,
    ApprovalRequestId,
    ControlledExecutionId,
    PolicyCheckId,
    ProposalId,
)
from hqmts.db.models.agent_proposal import AgentProposalORM
from hqmts.db.models.agent_task import AgentTaskORM
from hqmts.db.models.approval_request import ApprovalRequestORM
from hqmts.db.models.controlled_execution import ControlledExecutionORM
from hqmts.db.repositories.base import BaseRepository
from hqmts.domain.agent_proposal import AgentProposal
from hqmts.domain.agent_task import AgentTask
from hqmts.domain.approval_request import ApprovalRequest
from hqmts.domain.controlled_execution import ControlledExecution
from hqmts.core.types import now_shanghai


# ---------------------------------------------------------------------------
# AgentTask
# ---------------------------------------------------------------------------


class AgentTaskRepository(BaseRepository[AgentTaskORM]):
    """Repository that returns AgentTask domain models."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AgentTaskORM, session)

    @staticmethod
    def to_domain(orm: AgentTaskORM) -> AgentTask:
        return AgentTask(
            agent_task_id=AgentTaskId(orm.agent_task_id),
            agent_role=orm.agent_role,
            task_type=orm.task_type,
            environment=Environment(orm.environment),
            input_ref=orm.input_ref,
            output_ref=orm.output_ref,
            workflow_version=orm.workflow_version,
            tool_plan=orm.tool_plan,
            status=AgentTaskStatus(orm.status),
            started_at=orm.started_at,
            completed_at=orm.completed_at,
            failure_reason=orm.failure_reason,
            triggered_by=orm.triggered_by,
            correlation_id=orm.correlation_id,
            created_at=orm.created_at,
        )

    async def get_domain(self, task_id: str) -> AgentTask | None:
        orm = await self.get_by_id(task_id, id_column="agent_task_id")
        return self.to_domain(orm) if orm else None

    async def create_domain(self, task: AgentTask) -> AgentTask:
        orm = AgentTaskORM(
            agent_task_id=task.agent_task_id,
            agent_role=task.agent_role.value if isinstance(task.agent_role, Environment) else task.agent_role,
            task_type=task.task_type,
            environment=task.environment.value,
            input_ref=task.input_ref,
            output_ref=task.output_ref,
            workflow_version=task.workflow_version,
            tool_plan=task.tool_plan,
            status=task.status.value,
            started_at=task.started_at,
            completed_at=task.completed_at,
            failure_reason=task.failure_reason,
            triggered_by=task.triggered_by,
            correlation_id=task.correlation_id,
            created_at=task.created_at,
            updated_at=task.created_at,
        )
        orm = await self.create(orm)
        return self.to_domain(orm)

    async def update_domain(self, task: AgentTask) -> AgentTask:
        orm = await self.get_by_id(task.agent_task_id, id_column="agent_task_id")
        if orm is None:
            raise ValueError(f"Task {task.agent_task_id} not found")
        orm.status = task.status.value
        orm.started_at = task.started_at
        orm.completed_at = task.completed_at
        orm.failure_reason = task.failure_reason
        orm.output_ref = task.output_ref
        orm.updated_at = now_shanghai()
        await self.update(orm)
        return self.to_domain(orm)


# ---------------------------------------------------------------------------
# AgentProposal
# ---------------------------------------------------------------------------


class AgentProposalRepository(BaseRepository[AgentProposalORM]):
    """Repository that returns AgentProposal domain models."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AgentProposalORM, session)

    @staticmethod
    def to_domain(orm: AgentProposalORM) -> AgentProposal:
        return AgentProposal(
            proposal_id=ProposalId(orm.proposal_id),
            proposal_type=orm.proposal_type,
            source_agent_task_id=AgentTaskId(orm.source_agent_task_id),
            target_object_type=orm.target_object_type,
            target_object_id=orm.target_object_id,
            proposal_payload=orm.proposal_payload,
            confidence=orm.confidence,
            policy_result=orm.policy_result,
            policy_check_id=PolicyCheckId(orm.policy_check_id) if orm.policy_check_id else None,
            approval_status=orm.approval_status,
            approval_request_id=orm.approval_request_id,
            executed_result=orm.executed_result,
            created_at=orm.created_at,
        )

    async def get_domain(self, proposal_id: str) -> AgentProposal | None:
        orm = await self.get_by_id(proposal_id, id_column="proposal_id")
        return self.to_domain(orm) if orm else None

    async def create_domain(self, proposal: AgentProposal) -> AgentProposal:
        orm = AgentProposalORM(
            proposal_id=proposal.proposal_id,
            proposal_type=proposal.proposal_type,
            source_agent_task_id=proposal.source_agent_task_id,
            target_object_type=proposal.target_object_type,
            target_object_id=proposal.target_object_id,
            proposal_payload=proposal.proposal_payload,
            confidence=proposal.confidence,
            policy_result=proposal.policy_result,
            policy_check_id=proposal.policy_check_id,
            approval_status=proposal.approval_status,
            approval_request_id=proposal.approval_request_id,
            executed_result=proposal.executed_result,
            created_at=proposal.created_at,
            updated_at=proposal.created_at,
        )
        orm = await self.create(orm)
        return self.to_domain(orm)

    async def update_domain(self, proposal: AgentProposal) -> AgentProposal:
        orm = await self.get_by_id(proposal.proposal_id, id_column="proposal_id")
        if orm is None:
            raise ValueError(f"Proposal {proposal.proposal_id} not found")
        orm.policy_result = proposal.policy_result
        orm.policy_check_id = proposal.policy_check_id
        orm.approval_status = proposal.approval_status
        orm.approval_request_id = proposal.approval_request_id
        orm.executed_result = proposal.executed_result
        orm.updated_at = now_shanghai()
        await self.update(orm)
        return self.to_domain(orm)


# ---------------------------------------------------------------------------
# ApprovalRequest
# ---------------------------------------------------------------------------


class ApprovalRequestRepository(BaseRepository[ApprovalRequestORM]):
    """Repository that returns ApprovalRequest domain models."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ApprovalRequestORM, session)

    @staticmethod
    def to_domain(orm: ApprovalRequestORM) -> ApprovalRequest:
        return ApprovalRequest(
            approval_request_id=ApprovalRequestId(orm.approval_request_id),
            source_type=orm.source_type,
            source_id=orm.source_id,
            approval_type=orm.approval_type,
            requested_by=orm.requested_by,
            requested_at=orm.requested_at,
            approver=orm.approver,
            approved_at=orm.approved_at,
            decision=ApprovalStatus(orm.decision),
            decision_reason=orm.decision_reason,
            approval_snapshot_ref=orm.approval_snapshot_ref,
            expires_at=orm.expires_at,
        )

    async def get_domain(self, approval_id: str) -> ApprovalRequest | None:
        orm = await self.get_by_id(approval_id, id_column="approval_request_id")
        return self.to_domain(orm) if orm else None

    async def create_domain(self, approval: ApprovalRequest) -> ApprovalRequest:
        orm = ApprovalRequestORM(
            approval_request_id=approval.approval_request_id,
            source_type=approval.source_type,
            source_id=approval.source_id,
            approval_type=approval.approval_type,
            requested_by=approval.requested_by,
            requested_at=approval.requested_at,
            approver=approval.approver,
            approved_at=approval.approved_at,
            decision=approval.decision.value,
            decision_reason=approval.decision_reason,
            approval_snapshot_ref=approval.approval_snapshot_ref,
            expires_at=approval.expires_at,
            created_at=approval.requested_at,
            updated_at=approval.requested_at,
        )
        orm = await self.create(orm)
        return self.to_domain(orm)

    async def update_domain(self, approval: ApprovalRequest) -> ApprovalRequest:
        orm = await self.get_by_id(approval.approval_request_id, id_column="approval_request_id")
        if orm is None:
            raise ValueError(f"Approval {approval.approval_request_id} not found")
        orm.approver = approval.approver
        orm.approved_at = approval.approved_at
        orm.decision = approval.decision.value
        orm.decision_reason = approval.decision_reason
        orm.updated_at = now_shanghai()
        await self.update(orm)
        return self.to_domain(orm)


# ---------------------------------------------------------------------------
# ControlledExecution
# ---------------------------------------------------------------------------


class ControlledExecutionRepository(BaseRepository[ControlledExecutionORM]):
    """Repository that returns ControlledExecution domain models."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ControlledExecutionORM, session)

    @staticmethod
    def to_domain(orm: ControlledExecutionORM) -> ControlledExecution:
        return ControlledExecution(
            controlled_execution_id=ControlledExecutionId(orm.controlled_execution_id),
            source_proposal_id=ProposalId(orm.source_proposal_id),
            approval_request_id=ApprovalRequestId(orm.approval_request_id) if orm.approval_request_id else None,
            action_type=orm.action_type,
            target_object_type=orm.target_object_type,
            target_object_id=orm.target_object_id,
            execution_status=ExecutionStatus(orm.execution_status),
            executed_by_service=orm.executed_by_service,
            started_at=orm.started_at,
            completed_at=orm.completed_at,
            result_ref=orm.result_ref,
            failure_reason=orm.failure_reason,
        )

    async def get_domain(self, execution_id: str) -> ControlledExecution | None:
        orm = await self.get_by_id(execution_id, id_column="controlled_execution_id")
        return self.to_domain(orm) if orm else None

    async def create_domain(self, execution: ControlledExecution) -> ControlledExecution:
        orm = ControlledExecutionORM(
            controlled_execution_id=execution.controlled_execution_id,
            source_proposal_id=execution.source_proposal_id,
            approval_request_id=execution.approval_request_id,
            action_type=execution.action_type,
            target_object_type=execution.target_object_type,
            target_object_id=execution.target_object_id,
            execution_status=execution.execution_status.value,
            executed_by_service=execution.executed_by_service,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            result_ref=execution.result_ref,
            failure_reason=execution.failure_reason,
            created_at=execution.started_at or now_shanghai(),
            updated_at=now_shanghai(),
        )
        orm = await self.create(orm)
        return self.to_domain(orm)

    async def update_domain(self, execution: ControlledExecution) -> ControlledExecution:
        orm = await self.get_by_id(execution.controlled_execution_id, id_column="controlled_execution_id")
        if orm is None:
            raise ValueError(f"Execution {execution.controlled_execution_id} not found")
        orm.execution_status = execution.execution_status.value
        orm.completed_at = execution.completed_at
        orm.result_ref = execution.result_ref
        orm.failure_reason = execution.failure_reason
        orm.updated_at = now_shanghai()
        await self.update(orm)
        return self.to_domain(orm)

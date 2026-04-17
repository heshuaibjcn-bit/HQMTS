"""Agent audit service for comprehensive agent action tracking (SAD 26).

Records all agent lifecycle events: task creation, policy evaluation,
proposal submission, approval decisions, tool invocations, and
controlled execution outcomes.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from hqmts.core.enums import AlertLevel, Environment
from hqmts.core.types import AuditEventId
from hqmts.domain.audit import AuditEvent


class AgentAuditService:
    """Tracks all agent actions as immutable audit events.

    Each method creates an AuditEvent recording what the agent did,
    why, and what the outcome was. Events are returned (not persisted)
    so callers can store them through the audit repository.
    """

    def __init__(self, environment: Environment = Environment.BACKTEST) -> None:
        self._environment = environment

    def record_task_created(
        self,
        task_id: str,
        agent_role: str,
        description: str,
        correlation_id: str | None = None,
    ) -> AuditEvent:
        """Record agent task creation."""
        return AuditEvent(
            audit_event_id=AuditEventId(str(uuid.uuid4())),
            event_type="agent_task_created",
            entity_type="agent_task",
            entity_id=task_id,
            environment=self._environment,
            actor=agent_role,
            action="create_task",
            details={"description": description},
            correlation_id=correlation_id,
            timestamp=datetime.now(),
        )

    def record_policy_evaluation(
        self,
        task_id: str,
        agent_role: str,
        policy_result: str,
        violations: list[str] | None = None,
        correlation_id: str | None = None,
    ) -> AuditEvent:
        """Record policy engine evaluation for an agent action."""
        return AuditEvent(
            audit_event_id=AuditEventId(str(uuid.uuid4())),
            event_type="agent_policy_evaluation",
            entity_type="agent_task",
            entity_id=task_id,
            environment=self._environment,
            actor="policy_engine",
            action="evaluate_policy",
            details={
                "agent_role": agent_role,
                "policy_result": policy_result,
                "violations": violations or [],
            },
            alert_level=AlertLevel.P3 if policy_result == "denied" else AlertLevel.P3,
            correlation_id=correlation_id,
            timestamp=datetime.now(),
        )

    def record_proposal_submitted(
        self,
        proposal_id: str,
        task_id: str,
        agent_role: str,
        proposal_type: str,
        correlation_id: str | None = None,
    ) -> AuditEvent:
        """Record agent proposal submission."""
        return AuditEvent(
            audit_event_id=AuditEventId(str(uuid.uuid4())),
            event_type="agent_proposal_submitted",
            entity_type="agent_proposal",
            entity_id=proposal_id,
            environment=self._environment,
            actor=agent_role,
            action="submit_proposal",
            details={
                "task_id": task_id,
                "proposal_type": proposal_type,
            },
            correlation_id=correlation_id,
            timestamp=datetime.now(),
        )

    def record_approval_decision(
        self,
        proposal_id: str,
        approver: str,
        decision: str,
        reason: str = "",
        correlation_id: str | None = None,
    ) -> AuditEvent:
        """Record approval or rejection of an agent proposal."""
        return AuditEvent(
            audit_event_id=AuditEventId(str(uuid.uuid4())),
            event_type="agent_approval_decision",
            entity_type="agent_proposal",
            entity_id=proposal_id,
            environment=self._environment,
            actor=approver,
            action=f"proposal_{decision}",
            details={"decision": decision, "reason": reason},
            alert_level=AlertLevel.P3,
            correlation_id=correlation_id,
            timestamp=datetime.now(),
        )

    def record_tool_invocation(
        self,
        task_id: str,
        agent_role: str,
        tool_name: str,
        side_effect_level: str,
        result: str,
        correlation_id: str | None = None,
    ) -> AuditEvent:
        """Record agent tool invocation through the gateway."""
        return AuditEvent(
            audit_event_id=AuditEventId(str(uuid.uuid4())),
            event_type="agent_tool_invocation",
            entity_type="agent_task",
            entity_id=task_id,
            environment=self._environment,
            actor=agent_role,
            action=f"invoke_tool:{tool_name}",
            details={
                "tool_name": tool_name,
                "side_effect_level": side_effect_level,
                "result": result,
            },
            alert_level=AlertLevel.P3,
            correlation_id=correlation_id,
            timestamp=datetime.now(),
        )

    def record_controlled_execution(
        self,
        execution_id: str,
        proposal_id: str,
        executor: str,
        outcome: str,
        details: dict | None = None,
        correlation_id: str | None = None,
    ) -> AuditEvent:
        """Record controlled execution outcome."""
        return AuditEvent(
            audit_event_id=AuditEventId(str(uuid.uuid4())),
            event_type="agent_controlled_execution",
            entity_type="controlled_execution",
            entity_id=execution_id,
            environment=self._environment,
            actor=executor,
            action=f"execute:{outcome}",
            details=details or {"proposal_id": proposal_id, "outcome": outcome},
            alert_level=AlertLevel.P3,
            correlation_id=correlation_id,
            timestamp=datetime.now(),
        )

    def record_unauthorized_attempt(
        self,
        agent_role: str,
        action: str,
        reason: str,
        correlation_id: str | None = None,
    ) -> AuditEvent:
        """Record an unauthorized access attempt by an agent."""
        return AuditEvent(
            audit_event_id=AuditEventId(str(uuid.uuid4())),
            event_type="agent_unauthorized_attempt",
            entity_type="agent_security",
            entity_id=str(uuid.uuid4()),
            environment=self._environment,
            actor=agent_role,
            action=action,
            details={"reason": reason},
            alert_level=AlertLevel.P1,
            correlation_id=correlation_id,
            timestamp=datetime.now(),
        )

    def record_task_state_change(
        self,
        task_id: str,
        agent_role: str,
        from_state: str,
        to_state: str,
        reason: str = "",
        correlation_id: str | None = None,
    ) -> AuditEvent:
        """Record agent task state transition."""
        return AuditEvent(
            audit_event_id=AuditEventId(str(uuid.uuid4())),
            event_type="agent_task_state_change",
            entity_type="agent_task",
            entity_id=task_id,
            environment=self._environment,
            actor=agent_role,
            action=f"transition:{from_state}->{to_state}",
            details={"from_state": from_state, "to_state": to_state, "reason": reason},
            alert_level=AlertLevel.P3,
            correlation_id=correlation_id,
            timestamp=datetime.now(),
        )

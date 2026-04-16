"""AuditEvent domain model."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from hqmts.core.enums import AlertLevel, Environment
from hqmts.core.types import AuditEventId


class AuditEvent(BaseModel):
    """Immutable audit event record (SAD 26).

    Records all significant system actions for traceability.
    Audit events are append-only and must not be modified.
    """

    audit_event_id: AuditEventId
    event_type: str  # order_created, risk_check, approval_decision, agent_tool_call, etc.
    entity_type: str  # order, signal, strategy_instance, agent_task, etc.
    entity_id: str
    environment: Environment
    actor: str  # system, user_id, agent_role
    action: str
    details: dict = Field(default_factory=dict)
    alert_level: AlertLevel = AlertLevel.P3
    correlation_id: str | None = None
    timestamp: datetime

    model_config = {"frozen": True}

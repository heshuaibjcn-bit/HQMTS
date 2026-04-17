"""ReconciliationSession domain model."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from hqmts.core.enums import ReconciliationStatus
from hqmts.core.types import ReconciliationId


class ReconciliationSession(BaseModel):
    """Reconciliation session for comparing local vs broker state (PRD 9.16, SAD 15.4)."""

    reconciliation_session_id: ReconciliationId
    scope_type: str  # order, trade, position, account
    scope_id: str  # The entity being reconciled
    expected_snapshot_ref: str | None = None  # Local state reference
    broker_snapshot_ref: str | None = None  # Broker state reference
    diff_summary: dict = Field(default_factory=dict)
    severity: str = "info"  # info, warning, critical
    status: ReconciliationStatus = ReconciliationStatus.INITIALIZED
    resolution_status: str = "pending"  # pending, resolved, escalated
    started_at: datetime
    completed_at: datetime | None = None

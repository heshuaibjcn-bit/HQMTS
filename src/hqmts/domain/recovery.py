"""RecoverySession domain model."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from hqmts.core.enums import RecoveryStatus
from hqmts.core.types import RecoveryId


class RecoverySession(BaseModel):
    """Recovery session for system restart/fault recovery (PRD 9.15, SAD 15.5).

    Agent can generate recovery suggestions but cannot bypass pending_confirmation.
    """

    recovery_session_id: RecoveryId
    scope_type: str  # strategy, account, system
    scope_id: str
    trigger_reason: str = ""
    current_state_snapshot_ref: str | None = None
    proposed_actions_ref: str | None = None
    approval_required: bool = True
    status: RecoveryStatus = RecoveryStatus.CREATED
    final_result: str = ""
    started_at: datetime
    completed_at: datetime | None = None

"""ToolInvocation domain model (PRD 9.13, SAD 7.8).

Represents a single Agent tool call — all side-effect calls must be audited.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from hqmts.core.enums import SideEffectLevel
from hqmts.core.types import AgentTaskId, CorrelationId, PolicyCheckId, ToolInvocationId


class ToolInvocation(BaseModel):
    """Record of a single Agent tool invocation through the Tool Gateway.

    Constraints:
    - All tool calls must be audited
    - Side-effect tools must have idempotency keys
    - Live-related tools must pass policy check
    - forbidden_attempt must trigger alert and audit
    """

    invocation_id: ToolInvocationId
    agent_task_id: AgentTaskId
    tool_name: str
    tool_version: str = "v1"
    input_digest: str = ""  # Hash/digest of input parameters
    output_digest: str = ""  # Hash/digest of output
    side_effect_level: SideEffectLevel = SideEffectLevel.NONE
    started_at: datetime
    finished_at: datetime | None = None
    status: str = "pending"  # pending, success, failed, denied, timeout
    error_code: str = ""
    policy_check_id: PolicyCheckId | None = None
    correlation_id: CorrelationId | None = None
    idempotency_key: str | None = None
    environment: str = "research"

    @property
    def duration_ms(self) -> float | None:
        """Duration of the invocation in milliseconds."""
        if self.finished_at and self.started_at:
            return (self.finished_at - self.started_at).total_seconds() * 1000
        return None

    @property
    def has_side_effects(self) -> bool:
        """Check if this invocation has side effects."""
        return self.side_effect_level in (
            SideEffectLevel.TASK_TRIGGER,
            SideEffectLevel.CONTROLLED_OPERATION,
        )

    @property
    def is_forbidden_attempt(self) -> bool:
        """Check if this was a forbidden tool attempt."""
        return self.side_effect_level == SideEffectLevel.FORBIDDEN_ATTEMPT

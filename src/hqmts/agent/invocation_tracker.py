"""ToolInvocation tracking: creates domain records from gateway results."""

from __future__ import annotations

from datetime import datetime

from hqmts.agent.gateway import ToolCallRequest, ToolCallResult
from hqmts.core.enums import SideEffectLevel
from hqmts.domain.tool_invocation import ToolInvocation


def create_invocation_from_result(
    request: ToolCallRequest,
    result: ToolCallResult,
    started_at: datetime,
) -> ToolInvocation:
    """Create a ToolInvocation domain record from gateway request/result.

    Enforces side_effect_level tracking on every tool call.
    """
    # Map forbidden tool attempts
    actual_level = result.side_effect_level
    if result.status == "denied" and result.error and "forbidden" in result.error.lower():
        actual_level = SideEffectLevel.FORBIDDEN_ATTEMPT

    return ToolInvocation(
        invocation_id=result.invocation_id,
        agent_task_id=request.agent_task_id,
        tool_name=result.tool_name,
        input_digest=str(hash(frozenset(request.parameters.items()))) if request.parameters else "",
        side_effect_level=actual_level,
        started_at=started_at,
        finished_at=datetime.now(),
        status=result.status,
        error_code=result.error[:32] if result.error else "",
        policy_check_id=None,
        correlation_id=request.correlation_id,
        idempotency_key=request.idempotency_key,
        environment=request.environment.value,
    )

"""Tool Gateway for Agent governance (SAD 24.3).

All Agent tool calls must pass through the Tool Gateway.
Responsibilities: auth, param validation, policy check, idempotency,
rate limiting, environment isolation, audit, output sanitization,
violation interception.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

from hqmts.core.enums import (
    AgentRole,
    Environment,
    PolicyCheckResult,
    SideEffectLevel,
    ToolCategory,
)
from hqmts.core.exceptions import (
    AgentPermissionDeniedError,
    ForbiddenToolAttemptError,
)
from hqmts.agent.policy import PolicyEngine, PolicyCheckInput
from hqmts.agent.types import ALL_TOOLS, FORBIDDEN_TOOLS, ToolDefinition

logger = logging.getLogger(__name__)


@dataclass
class ToolCallRequest:
    """A request to invoke an agent tool."""

    agent_role: AgentRole
    agent_task_id: str
    tool_name: str
    parameters: dict = field(default_factory=dict)
    idempotency_key: str | None = None
    correlation_id: str | None = None
    environment: Environment = Environment.RESEARCH
    has_version_binding: bool = False
    is_trading_time: bool = True
    has_unresolved_exceptions: bool = False


@dataclass
class ToolCallResult:
    """Result of a tool invocation."""

    invocation_id: str
    tool_name: str
    status: str  # success, failed, denied, timeout
    side_effect_level: SideEffectLevel
    output: dict = field(default_factory=dict)
    error: str = ""
    policy_result: PolicyCheckResult | None = None
    duration_ms: float = 0.0


class ToolGateway:
    """Gateway for all agent tool invocations.

    Enforces permission boundaries, policy checks, and audit logging.
    Agent cannot bypass this gateway to access system capabilities.
    """

    def __init__(
        self,
        policy_engine: PolicyEngine,
        rate_limit_per_minute: int = 60,
    ) -> None:
        self._policy_engine = policy_engine
        self._rate_limit = rate_limit_per_minute
        self._call_timestamps: dict[str, list[float]] = {}  # agent_task_id -> timestamps

    async def invoke(self, request: ToolCallRequest) -> ToolCallResult:
        """Process a tool invocation request through the gateway.

        Steps:
        1. Check forbidden tools
        2. Validate tool exists
        3. Policy check
        4. Rate limit check
        5. Idempotency check (for side-effect tools)
        6. Execute
        7. Audit
        """
        start_time = time.monotonic()
        invocation_id = str(uuid.uuid4())

        # Step 1: Forbidden tools check — return audited result, don't throw
        if request.tool_name in FORBIDDEN_TOOLS:
            result = ToolCallResult(
                invocation_id=invocation_id,
                tool_name=request.tool_name,
                status="denied",
                side_effect_level=SideEffectLevel.FORBIDDEN_ATTEMPT,
                error=f"Forbidden tool: {request.tool_name}",
                duration_ms=(time.monotonic() - start_time) * 1000,
            )
            logger.warning(
                "FORBIDDEN_TOOL_ATTEMPT invocation=%s role=%s tool=%s env=%s task=%s",
                invocation_id, request.agent_role.value, request.tool_name,
                request.environment.value, request.agent_task_id,
            )
            return result

        # Step 2: Tool existence
        tool_def = ALL_TOOLS.get(request.tool_name)
        if tool_def is None:
            return ToolCallResult(
                invocation_id=invocation_id,
                tool_name=request.tool_name,
                status="failed",
                side_effect_level=SideEffectLevel.NONE,
                error=f"Unknown tool: {request.tool_name}",
            )

        # Step 3: Policy check
        policy_input = PolicyCheckInput(
            agent_role=request.agent_role,
            tool_name=request.tool_name,
            environment=request.environment,
            has_version_binding=request.has_version_binding,
            is_trading_time=request.is_trading_time,
            has_unresolved_exceptions=request.has_unresolved_exceptions,
        )
        policy_output = self._policy_engine.evaluate(policy_input)

        if policy_output.result == PolicyCheckResult.FAIL:
            elapsed = (time.monotonic() - start_time) * 1000
            result = ToolCallResult(
                invocation_id=invocation_id,
                tool_name=request.tool_name,
                status="denied",
                side_effect_level=tool_def.side_effect_level,
                error=policy_output.reason,
                policy_result=policy_output.result,
                duration_ms=elapsed,
            )
            self._audit_log(result, request)
            return result

        # Step 4: Rate limit
        if not self._check_rate_limit(request.agent_task_id):
            elapsed = (time.monotonic() - start_time) * 1000
            result = ToolCallResult(
                invocation_id=invocation_id,
                tool_name=request.tool_name,
                status="denied",
                side_effect_level=tool_def.side_effect_level,
                error="Rate limit exceeded",
                policy_result=policy_output.result,
                duration_ms=elapsed,
            )
            self._audit_log(result, request)
            return result

        # Step 5: Idempotency check for side-effect tools
        if tool_def.idempotent and request.idempotency_key is None:
            elapsed = (time.monotonic() - start_time) * 1000
            result = ToolCallResult(
                invocation_id=invocation_id,
                tool_name=request.tool_name,
                status="failed",
                side_effect_level=tool_def.side_effect_level,
                error="Idempotent tool requires idempotency_key",
                policy_result=policy_output.result,
                duration_ms=elapsed,
            )
            self._audit_log(result, request)
            return result

        # Step 6 & 7: Return result with policy decision
        # (actual tool execution is delegated to handlers in production)
        elapsed = (time.monotonic() - start_time) * 1000

        if policy_output.result == PolicyCheckResult.MANUAL_REVIEW_REQUIRED:
            result = ToolCallResult(
                invocation_id=invocation_id,
                tool_name=request.tool_name,
                status="pending_approval",
                side_effect_level=tool_def.side_effect_level,
                output={"message": "Requires manual approval before execution"},
                policy_result=policy_output.result,
                duration_ms=elapsed,
            )
            self._audit_log(result, request)
            return result

        result = ToolCallResult(
            invocation_id=invocation_id,
            tool_name=request.tool_name,
            status="success",
            side_effect_level=tool_def.side_effect_level,
            policy_result=policy_output.result,
            duration_ms=elapsed,
        )
        self._audit_log(result, request)
        return result

    def _check_rate_limit(self, agent_task_id: str) -> bool:
        """Check if the agent task is within rate limits."""
        now = time.monotonic()

        # Evict old task IDs with no recent calls (prevents unbounded memory growth)
        if len(self._call_timestamps) > 1000:
            stale_keys = [
                k for k, v in self._call_timestamps.items()
                if not v or now - v[-1] > 120
            ]
            for k in stale_keys:
                del self._call_timestamps[k]

        timestamps = self._call_timestamps.get(agent_task_id, [])

        # Remove timestamps older than 60 seconds
        timestamps = [t for t in timestamps if now - t < 60]

        if len(timestamps) >= self._rate_limit:
            return False

        timestamps.append(now)
        self._call_timestamps[agent_task_id] = timestamps
        return True

    def _audit_log(
        self, result: ToolCallResult, request: ToolCallRequest,
    ) -> None:
        """Record tool invocation audit event.

        Per SAD 24.3 item 7, all tool calls must be audited.
        Uses structured logging so consumers can persist to audit store.
        """
        logger.info(
            "TOOL_INVOCATION invocation=%s tool=%s role=%s env=%s task=%s "
            "status=%s side_effect=%s duration_ms=%.1f idem_key=%s",
            result.invocation_id,
            result.tool_name,
            request.agent_role.value,
            request.environment.value,
            request.agent_task_id,
            result.status,
            result.side_effect_level.value,
            result.duration_ms,
            request.idempotency_key or "-",
        )
        if result.status == "denied":
            logger.warning(
                "TOOL_DENIED invocation=%s tool=%s role=%s error=%s",
                result.invocation_id, result.tool_name,
                request.agent_role.value, result.error,
            )

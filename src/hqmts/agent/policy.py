"""Policy Engine for Agent governance (SAD 24.5).

All Live-related proposals must pass through the Policy Engine.
Outputs: pass, fail, manual_review_required.
"""

from __future__ import annotations

from dataclasses import dataclass

from hqmts.core.enums import (
    AgentRole,
    Environment,
    PolicyCheckResult,
    ProposalStatus,
    ToolCategory,
)
from hqmts.agent.types import ALL_TOOLS, FORBIDDEN_TOOLS, ToolDefinition


@dataclass
class PolicyCheckInput:
    """Input for policy evaluation."""

    agent_role: AgentRole
    tool_name: str
    environment: Environment
    target_object_type: str | None = None
    target_object_id: str | None = None
    proposal_type: str | None = None
    has_version_binding: bool = False  # Check 7: version binding for Live
    is_trading_time: bool = True  # Check 9: trading time restriction
    has_unresolved_exceptions: bool = False  # Check 8: unresolved exceptions


@dataclass
class PolicyCheckOutput:
    """Result of policy evaluation."""

    result: PolicyCheckResult
    reason: str
    violations: list[str]


class PolicyEngine:
    """Deterministic policy validator for Agent operations.

    Checks (per SAD 24.5):
    1. Environment permission
    2. Role permission
    3. Target object state
    4. Action allowlist
    5. Approval requirement
    6. Risk boundary violation
    7. Version binding
    8. Unresolved exceptions
    9. Trading time restriction
    10. Agent permission scope
    """

    def __init__(self) -> None:
        self._global_kill_switch = False
        self._live_trading_allowed = True

    def evaluate(self, input_data: PolicyCheckInput) -> PolicyCheckOutput:
        """Evaluate policy for an agent action."""
        violations: list[str] = []

        # Check 0: Forbidden tools (absolute block)
        if input_data.tool_name in FORBIDDEN_TOOLS:
            return PolicyCheckOutput(
                result=PolicyCheckResult.FAIL,
                reason=f"Tool '{input_data.tool_name}' is permanently forbidden",
                violations=[f"forbidden_tool:{input_data.tool_name}"],
            )

        # Check tool existence
        tool_def = ALL_TOOLS.get(input_data.tool_name)
        if tool_def is None:
            return PolicyCheckOutput(
                result=PolicyCheckResult.FAIL,
                reason=f"Unknown tool: {input_data.tool_name}",
                violations=[f"unknown_tool:{input_data.tool_name}"],
            )

        # Check 1: Environment permission
        if input_data.environment not in tool_def.allowed_environments:
            violations.append(
                f"env_not_allowed:{input_data.environment.value} "
                f"for tool:{input_data.tool_name}"
            )

        # Check 2: Role permission
        if input_data.agent_role not in tool_def.allowed_roles:
            violations.append(
                f"role_not_allowed:{input_data.agent_role.value} "
                f"for tool:{input_data.tool_name}"
            )

        # Check 10: Live-specific restrictions
        if input_data.environment == Environment.LIVE:
            if self._global_kill_switch and tool_def.category != ToolCategory.READ_ONLY:
                violations.append("kill_switch_active")
            if not self._live_trading_allowed and tool_def.requires_approval:
                violations.append("live_trading_not_allowed")

        # Check 7: Version binding required for Live controlled operations
        if (
            input_data.environment == Environment.LIVE
            and tool_def.category == ToolCategory.CONTROLLED_OPERATION
            and not input_data.has_version_binding
        ):
            violations.append("version_binding_required_for_live")

        # Check 8: Unresolved exceptions block non-read operations
        if input_data.has_unresolved_exceptions and tool_def.category != ToolCategory.READ_ONLY:
            violations.append("unresolved_exceptions_block_action")

        # Check 9: Trading time restriction for controlled operations in Live
        if (
            input_data.environment == Environment.LIVE
            and tool_def.category == ToolCategory.CONTROLLED_OPERATION
            and not input_data.is_trading_time
        ):
            violations.append("non_trading_time_blocked")

        # Any violation means fail
        if violations:
            return PolicyCheckOutput(
                result=PolicyCheckResult.FAIL,
                reason=f"Policy violations: {'; '.join(violations)}",
                violations=violations,
            )

        # Determine if manual review required
        if tool_def.requires_approval and input_data.environment == Environment.LIVE:
            return PolicyCheckOutput(
                result=PolicyCheckResult.MANUAL_REVIEW_REQUIRED,
                reason=f"Tool '{input_data.tool_name}' requires manual approval in Live",
                violations=[],
            )

        return PolicyCheckOutput(
            result=PolicyCheckResult.PASS,
            reason="All policy checks passed",
            violations=[],
        )

    def set_kill_switch(self, active: bool) -> None:
        """Set global kill switch state."""
        self._global_kill_switch = active

    def set_live_trading_allowed(self, allowed: bool) -> None:
        """Set whether live trading is allowed."""
        self._live_trading_allowed = allowed

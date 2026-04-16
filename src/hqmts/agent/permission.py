"""Agent permission boundary enforcement (SAD 24, PRD 7.8).

Hard boundaries that prevent Agent from:
- Writing core trading tables
- Calling QMT directly
- Modifying risk thresholds
- Restoring live_running
- Modifying order/trade/position/account state
"""

from __future__ import annotations

from hqmts.core.enums import AgentRole, Environment, ToolCategory
from hqmts.core.exceptions import (
    AgentPermissionDeniedError,
    ForbiddenToolAttemptError,
)
from hqmts.agent.types import FORBIDDEN_TOOLS, ALL_TOOLS


# Core trading tables that Agent cannot write
PROTECTED_TABLES: set[str] = {
    "orders",
    "trades",
    "positions",
    "accounts",
    "cash_reservations",
    "risk_check_results",
    "execution_intents",
    "order_requests",
}

# Operations that Agent cannot perform on any table
PROTECTED_OPERATIONS: set[str] = {
    "INSERT",
    "UPDATE",
    "DELETE",
}

# Tables Agent can read
AGENT_READABLE_TABLES: set[str] = {
    "instruments",
    "bars",
    "feature_snapshots",
    "decision_snapshots",
    "strategies",
    "strategy_instances",
    "signals",
    "audit_events",
    "version_bindings",
    "reconciliation_sessions",
    "recovery_sessions",
}


class PermissionBoundary:
    """Enforces hard permission boundaries for Agent operations.

    These checks are in addition to ToolGateway — defense in depth.
    """

    def check_db_access(
        self,
        agent_role: AgentRole,
        operation: str,
        table: str,
        environment: Environment,
    ) -> None:
        """Check if an agent can perform a database operation.

        Raises:
            AgentPermissionDeniedError: If the operation is not allowed.
        """
        # Agent can always read readable tables
        if operation.upper() == "SELECT":
            if table in AGENT_READABLE_TABLES:
                return
            if table in PROTECTED_TABLES:
                # Agent can read protected tables for analysis but not in all environments
                if environment == Environment.LIVE:
                    raise AgentPermissionDeniedError(
                        agent_role=agent_role.value,
                        tool_name=f"db:{operation}:{table}",
                        reason=f"Agent cannot read Live protected table '{table}'",
                    )
                return
            return

        # Agent cannot write to protected tables in any environment
        if operation.upper() in PROTECTED_OPERATIONS and table in PROTECTED_TABLES:
            raise AgentPermissionDeniedError(
                agent_role=agent_role.value,
                tool_name=f"db:{operation}:{table}",
                reason=f"Agent cannot {operation} protected table '{table}'",
            )

    def check_qmt_access(self, agent_role: AgentRole) -> None:
        """Check if agent can access QMT directly. Always denied."""
        raise ForbiddenToolAttemptError(
            agent_role=agent_role.value,
            tool_name="qmt_direct_access",
        )

    def check_risk_threshold_modify(self, agent_role: AgentRole) -> None:
        """Check if agent can modify risk thresholds. Always denied."""
        raise AgentPermissionDeniedError(
            agent_role=agent_role.value,
            tool_name="modify_risk_threshold",
            reason="Agent cannot modify Live risk thresholds directly",
        )

    def check_restore_live_running(self, agent_role: AgentRole) -> None:
        """Check if agent can restore strategy to live_running. Always denied."""
        raise AgentPermissionDeniedError(
            agent_role=agent_role.value,
            tool_name="restore_live_running",
            reason="Agent cannot restore strategy to live_running directly",
        )

    def is_tool_forbidden(self, tool_name: str) -> bool:
        """Check if a tool is in the forbidden list."""
        return tool_name in FORBIDDEN_TOOLS

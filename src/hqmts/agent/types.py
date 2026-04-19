"""Agent governance types and enums."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hqmts.core.enums import (
    AgentRole,
    AgentTaskStatus,
    ApprovalStatus,
    Environment,
    ProposalStatus,
    SideEffectLevel,
    ToolCategory,
)
from hqmts.core.types import AgentTaskId, CorrelationId, ProposalId


# ── Tool Registry ────────────────────────────────────────────────────────────


class ToolDefinition(BaseModel):
    """Definition of an agent-accessible tool."""

    name: str
    category: ToolCategory
    description: str
    side_effect_level: SideEffectLevel
    allowed_environments: list[Environment]
    allowed_roles: list[AgentRole]
    requires_approval: bool = False
    idempotent: bool = False

    model_config = {"frozen": True}


# ── Forbidden tools (SAD 24.4) ───────────────────────────────────────────────

FORBIDDEN_TOOLS: set[str] = {
    "qmt_submit_order",
    "qmt_cancel_order_direct",
    "update_order_state_direct",
    "update_trade_direct",
    "update_position_direct",
    "update_account_direct",
    "update_live_risk_threshold_direct",
    "restore_live_running_direct",
}

# ── Tool Definitions ─────────────────────────────────────────────────────────

READ_ONLY_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="query_market_data",
        category=ToolCategory.READ_ONLY,
        description="Query current or historical market data",
        side_effect_level=SideEffectLevel.READ_ONLY,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER, Environment.LIVE],
        allowed_roles=list(AgentRole),
    ),
    ToolDefinition(
        name="query_backtest_result",
        category=ToolCategory.READ_ONLY,
        description="Query backtest results",
        side_effect_level=SideEffectLevel.READ_ONLY,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER],
        allowed_roles=[AgentRole.RESEARCH, AgentRole.BACKTEST_ORCHESTRATION, AgentRole.VALIDATION, AgentRole.ORCHESTRATOR],
    ),
    ToolDefinition(
        name="query_strategy_status",
        category=ToolCategory.READ_ONLY,
        description="Query strategy instance status",
        side_effect_level=SideEffectLevel.READ_ONLY,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER, Environment.LIVE],
        allowed_roles=list(AgentRole),
    ),
    ToolDefinition(
        name="query_order_status",
        category=ToolCategory.READ_ONLY,
        description="Query order status",
        side_effect_level=SideEffectLevel.READ_ONLY,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER, Environment.LIVE],
        allowed_roles=list(AgentRole),
    ),
    ToolDefinition(
        name="query_position_snapshot",
        category=ToolCategory.READ_ONLY,
        description="Query position snapshot",
        side_effect_level=SideEffectLevel.READ_ONLY,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER, Environment.LIVE],
        allowed_roles=list(AgentRole),
    ),
    ToolDefinition(
        name="query_reconciliation_diff",
        category=ToolCategory.READ_ONLY,
        description="Query reconciliation differences",
        side_effect_level=SideEffectLevel.READ_ONLY,
        allowed_environments=[Environment.RESEARCH, Environment.PAPER, Environment.LIVE],
        allowed_roles=[AgentRole.RECONCILIATION, AgentRole.RECOVERY_COPILOT, AgentRole.MONITORING, AgentRole.ORCHESTRATOR],
    ),
    ToolDefinition(
        name="query_audit_log",
        category=ToolCategory.READ_ONLY,
        description="Query audit logs",
        side_effect_level=SideEffectLevel.READ_ONLY,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER, Environment.LIVE],
        allowed_roles=[AgentRole.AUDIT_REPORTING, AgentRole.ORCHESTRATOR],
    ),
]

TASK_TRIGGER_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="start_backtest",
        category=ToolCategory.TASK_TRIGGER,
        description="Start a backtest run",
        side_effect_level=SideEffectLevel.TASK_TRIGGER,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST],
        allowed_roles=[AgentRole.BACKTEST_ORCHESTRATION, AgentRole.ORCHESTRATOR],
        idempotent=True,
    ),
    ToolDefinition(
        name="start_validation",
        category=ToolCategory.TASK_TRIGGER,
        description="Start a validation run",
        side_effect_level=SideEffectLevel.TASK_TRIGGER,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST],
        allowed_roles=[AgentRole.VALIDATION, AgentRole.ORCHESTRATOR],
        idempotent=True,
    ),
    ToolDefinition(
        name="start_paper_run",
        category=ToolCategory.TASK_TRIGGER,
        description="Start a paper trading run",
        side_effect_level=SideEffectLevel.TASK_TRIGGER,
        allowed_environments=[Environment.PAPER],
        allowed_roles=[AgentRole.ORCHESTRATOR],
        idempotent=True,
    ),
    ToolDefinition(
        name="start_reconciliation",
        category=ToolCategory.TASK_TRIGGER,
        description="Start a reconciliation session",
        side_effect_level=SideEffectLevel.TASK_TRIGGER,
        allowed_environments=[Environment.PAPER, Environment.LIVE],
        allowed_roles=[AgentRole.RECONCILIATION, AgentRole.ORCHESTRATOR],
        idempotent=True,
    ),
    ToolDefinition(
        name="start_recovery_analysis",
        category=ToolCategory.TASK_TRIGGER,
        description="Start a recovery analysis",
        side_effect_level=SideEffectLevel.TASK_TRIGGER,
        allowed_environments=[Environment.PAPER, Environment.LIVE],
        allowed_roles=[AgentRole.RECOVERY_COPILOT, AgentRole.ORCHESTRATOR],
        idempotent=True,
    ),
    ToolDefinition(
        name="create_approval_request",
        category=ToolCategory.TASK_TRIGGER,
        description="Create an approval request for human review",
        side_effect_level=SideEffectLevel.TASK_TRIGGER,
        allowed_environments=[Environment.PAPER, Environment.LIVE],
        allowed_roles=list(AgentRole),
        idempotent=True,
    ),
    ToolDefinition(
        name="generate_report",
        category=ToolCategory.TASK_TRIGGER,
        description="Generate an analysis report",
        side_effect_level=SideEffectLevel.TASK_TRIGGER,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER, Environment.LIVE],
        allowed_roles=[AgentRole.AUDIT_REPORTING, AgentRole.MONITORING, AgentRole.ORCHESTRATOR],
    ),
]

CONTROLLED_OPERATION_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="propose_pause_open",
        category=ToolCategory.CONTROLLED_OPERATION,
        description="Propose pausing new position openings",
        side_effect_level=SideEffectLevel.CONTROLLED_OPERATION,
        allowed_environments=[Environment.LIVE],
        allowed_roles=[AgentRole.MONITORING, AgentRole.ORCHESTRATOR],
        requires_approval=True,
    ),
    ToolDefinition(
        name="propose_close_only",
        category=ToolCategory.CONTROLLED_OPERATION,
        description="Propose switching to close-only mode",
        side_effect_level=SideEffectLevel.CONTROLLED_OPERATION,
        allowed_environments=[Environment.LIVE],
        allowed_roles=[AgentRole.MONITORING, AgentRole.ORCHESTRATOR],
        requires_approval=True,
    ),
    ToolDefinition(
        name="propose_correction",
        category=ToolCategory.CONTROLLED_OPERATION,
        description="Propose a data/state correction",
        side_effect_level=SideEffectLevel.CONTROLLED_OPERATION,
        allowed_environments=[Environment.PAPER, Environment.LIVE],
        allowed_roles=[AgentRole.RECONCILIATION, AgentRole.RECOVERY_COPILOT],
        requires_approval=True,
    ),
    ToolDefinition(
        name="propose_risk_param_change",
        category=ToolCategory.CONTROLLED_OPERATION,
        description="Propose a risk parameter change",
        side_effect_level=SideEffectLevel.CONTROLLED_OPERATION,
        allowed_environments=[Environment.LIVE],
        allowed_roles=[AgentRole.MONITORING, AgentRole.ORCHESTRATOR],
        requires_approval=True,
    ),
    ToolDefinition(
        name="propose_recovery_action",
        category=ToolCategory.CONTROLLED_OPERATION,
        description="Propose a recovery action",
        side_effect_level=SideEffectLevel.CONTROLLED_OPERATION,
        allowed_environments=[Environment.LIVE],
        allowed_roles=[AgentRole.RECOVERY_COPILOT, AgentRole.ORCHESTRATOR],
        requires_approval=True,
    ),
    ToolDefinition(
        name="propose_live_release",
        category=ToolCategory.CONTROLLED_OPERATION,
        description="Propose releasing strategy to live_running from pause_open/close_only",
        side_effect_level=SideEffectLevel.CONTROLLED_OPERATION,
        allowed_environments=[Environment.LIVE],
        allowed_roles=[AgentRole.RECOVERY_COPILOT, AgentRole.ORCHESTRATOR],
        requires_approval=True,
        idempotent=True,
    ),
]

# ── Research Agent Tools (FR-RES-006~013) ─────────────────────────────────────

RESEARCH_ROLES = [AgentRole.RESEARCH, AgentRole.ORCHESTRATOR]

RESEARCH_READ_ONLY_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="query_factor_library",
        category=ToolCategory.READ_ONLY,
        description="List and search the factor registry",
        side_effect_level=SideEffectLevel.READ_ONLY,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER],
        allowed_roles=RESEARCH_ROLES,
    ),
    ToolDefinition(
        name="query_factor_values",
        category=ToolCategory.READ_ONLY,
        description="Compute factor values for instruments over a time range",
        side_effect_level=SideEffectLevel.READ_ONLY,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER],
        allowed_roles=RESEARCH_ROLES,
    ),
    ToolDefinition(
        name="query_factor_correlations",
        category=ToolCategory.READ_ONLY,
        description="Compute correlation matrix between factors",
        side_effect_level=SideEffectLevel.READ_ONLY,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER],
        allowed_roles=RESEARCH_ROLES,
    ),
    ToolDefinition(
        name="query_market_regime",
        category=ToolCategory.READ_ONLY,
        description="Identify current market regime (trending/mean-reverting/volatile)",
        side_effect_level=SideEffectLevel.READ_ONLY,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER],
        allowed_roles=RESEARCH_ROLES,
    ),
    ToolDefinition(
        name="query_factor_anomalies",
        category=ToolCategory.READ_ONLY,
        description="Detect factor value anomalies (sudden spikes, extreme values)",
        side_effect_level=SideEffectLevel.READ_ONLY,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER],
        allowed_roles=RESEARCH_ROLES,
    ),
    ToolDefinition(
        name="query_instrument_universe",
        category=ToolCategory.READ_ONLY,
        description="Query available instruments in the universe",
        side_effect_level=SideEffectLevel.READ_ONLY,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER],
        allowed_roles=RESEARCH_ROLES,
    ),
]

RESEARCH_TASK_TRIGGER_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="create_hypothesis",
        category=ToolCategory.TASK_TRIGGER,
        description="Create a structured hypothesis record in a research project",
        side_effect_level=SideEffectLevel.TASK_TRIGGER,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST],
        allowed_roles=RESEARCH_ROLES,
        idempotent=True,
    ),
    ToolDefinition(
        name="create_trial_plan",
        category=ToolCategory.TASK_TRIGGER,
        description="Create a pre-registered trial plan for a hypothesis",
        side_effect_level=SideEffectLevel.TASK_TRIGGER,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST],
        allowed_roles=RESEARCH_ROLES,
        idempotent=True,
    ),
    ToolDefinition(
        name="execute_trial",
        category=ToolCategory.TASK_TRIGGER,
        description="Execute a trial plan (compute factors and evaluate metrics)",
        side_effect_level=SideEffectLevel.TASK_TRIGGER,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST],
        allowed_roles=RESEARCH_ROLES,
    ),
    ToolDefinition(
        name="generate_research_report",
        category=ToolCategory.TASK_TRIGGER,
        description="Generate a structured research report with provenance chain",
        side_effect_level=SideEffectLevel.TASK_TRIGGER,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER],
        allowed_roles=RESEARCH_ROLES + [AgentRole.AUDIT_REPORTING],
    ),
]

RESEARCH_CONTROLLED_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="propose_factor_registration",
        category=ToolCategory.CONTROLLED_OPERATION,
        description="Propose registering a new factor to the library",
        side_effect_level=SideEffectLevel.CONTROLLED_OPERATION,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST],
        allowed_roles=RESEARCH_ROLES,
        requires_approval=True,
    ),
]

# ── Autonomous Research Cycle Tools (SAD 24.10.6, FR-RES-014~020, FR-STR-006~012) ─

CYCLE_READ_ONLY_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="detect_factor_decay",
        category=ToolCategory.READ_ONLY,
        description="Detect decay in registered factors by comparing recent distributions to validation baselines",
        side_effect_level=SideEffectLevel.READ_ONLY,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER],
        allowed_roles=RESEARCH_ROLES,
    ),
]

CYCLE_TASK_TRIGGER_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="synthesize_strategy_candidates",
        category=ToolCategory.TASK_TRIGGER,
        description="Generate strategy candidates from validated factor discoveries using template mapping",
        side_effect_level=SideEffectLevel.TASK_TRIGGER,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST],
        allowed_roles=RESEARCH_ROLES,
        idempotent=True,
    ),
    ToolDefinition(
        name="evaluate_strategy_candidate",
        category=ToolCategory.TASK_TRIGGER,
        description="Evaluate a backtested strategy candidate with composite scoring",
        side_effect_level=SideEffectLevel.TASK_TRIGGER,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST],
        allowed_roles=RESEARCH_ROLES,
    ),
]

CYCLE_CONTROLLED_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="propose_strategy_promotion",
        category=ToolCategory.CONTROLLED_OPERATION,
        description="Propose promoting a strategy candidate to Paper or Live deployment",
        side_effect_level=SideEffectLevel.CONTROLLED_OPERATION,
        allowed_environments=[Environment.RESEARCH, Environment.BACKTEST, Environment.PAPER],
        allowed_roles=RESEARCH_ROLES,
        requires_approval=True,
    ),
]

ALL_TOOLS: dict[str, ToolDefinition] = {
    t.name: t
    for t in (
        READ_ONLY_TOOLS
        + TASK_TRIGGER_TOOLS
        + CONTROLLED_OPERATION_TOOLS
        + RESEARCH_READ_ONLY_TOOLS
        + RESEARCH_TASK_TRIGGER_TOOLS
        + RESEARCH_CONTROLLED_TOOLS
        + CYCLE_READ_ONLY_TOOLS
        + CYCLE_TASK_TRIGGER_TOOLS
        + CYCLE_CONTROLLED_TOOLS
    )
}

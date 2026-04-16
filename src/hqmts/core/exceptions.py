"""Domain exception hierarchy for HQMTS."""


class HQMTSError(Exception):
    """Base exception for all HQMTS errors."""


# ── State Machine Errors ────────────────────────────────────────────────────


class StateMachineError(HQMTSError):
    """Base error for state machine violations."""


class IllegalTransitionError(StateMachineError):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current: str, target: str, entity_type: str = "") -> None:
        self.current = current
        self.target = target
        self.entity_type = entity_type
        prefix = f"[{entity_type}] " if entity_type else ""
        msg = f"{prefix}Illegal transition: {current} -> {target}"
        super().__init__(msg)


class TerminalStateError(StateMachineError):
    """Raised when attempting to transition from a terminal state."""

    def __init__(self, state: str, entity_type: str = "") -> None:
        self.state = state
        self.entity_type = entity_type
        prefix = f"[{entity_type}] " if entity_type else ""
        msg = f"{prefix}Cannot transition from terminal state: {state}"
        super().__init__(msg)


# ── Domain Validation Errors ─────────────────────────────────────────────────


class DomainValidationError(HQMTSError):
    """Base error for domain model validation failures."""


class MissingDecisionSnapshotError(DomainValidationError):
    """Signal missing required DecisionSnapshot binding."""

    def __init__(self, signal_id: str = "", reason: str = "") -> None:
        self.signal_id = signal_id
        msg = f"Signal '{signal_id}' lacks DecisionSnapshot binding"
        if reason:
            msg += f": {reason}"
        msg += ". Fix: ensure DecisionSnapshot is created and bound before signal execution"
        super().__init__(msg)


class IncompleteSnapshotError(DomainValidationError):
    """DecisionSnapshot is not complete enough for Live execution."""

    def __init__(self, completeness: str, reason: str = "") -> None:
        self.completeness = completeness
        msg = f"Snapshot completeness '{completeness}' insufficient for Live"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class StalePriceError(DomainValidationError):
    """Reference price is too stale for order submission."""

    def __init__(self, age_seconds: float, threshold_seconds: float) -> None:
        self.age_seconds = age_seconds
        self.threshold_seconds = threshold_seconds
        msg = (
            f"Stale price: {age_seconds:.1f}s old, "
            f"threshold is {threshold_seconds:.1f}s"
        )
        super().__init__(msg)


class ExpiredSignalError(DomainValidationError):
    """Signal has expired and cannot be executed."""

    def __init__(self, signal_id: str = "", valid_until: str = "") -> None:
        self.signal_id = signal_id
        self.valid_until = valid_until
        msg = f"Signal '{signal_id}' expired at {valid_until}"
        msg += ". Fix: generate a fresh signal with updated valid_until"
        super().__init__(msg)


class IncompleteBarError(DomainValidationError):
    """Attempted to use incomplete bar for formal signal generation."""

    def __init__(self, bar_id: str = "", reason: str = "") -> None:
        self.bar_id = bar_id
        msg = f"Incomplete bar '{bar_id}' cannot be used for signal generation"
        if reason:
            msg += f": {reason}"
        msg += ". Fix: wait for bar completion or use backtest data"
        super().__init__(msg)


# ── Risk Errors ──────────────────────────────────────────────────────────────


class RiskError(HQMTSError):
    """Base error for risk-related failures."""


class RiskRejectError(RiskError):
    """Risk check rejected the order."""

    def __init__(self, reason: str, triggered_rules: list[str] | None = None) -> None:
        self.reason = reason
        self.triggered_rules = triggered_rules or []
        msg = f"Risk rejected: {reason}"
        super().__init__(msg)


class ForceFlattenError(RiskError):
    """Risk engine triggered force_flatten — caller must handle."""

    def __init__(self, reason: str = "", triggered_rules: list[str] | None = None) -> None:
        self.reason = reason
        self.triggered_rules = triggered_rules or []
        msg = f"Force flatten triggered: {reason}"
        super().__init__(msg)


class KillSwitchActiveError(RiskError):
    """Kill switch is active — no orders allowed."""

    def __init__(self, strategy_id: str = "") -> None:
        self.strategy_id = strategy_id
        msg = "Kill switch is active — all order submission blocked"
        if strategy_id:
            msg += f" for strategy '{strategy_id}'"
        msg += ". Fix: disable kill switch before submitting orders"
        super().__init__(msg)


class CloseOnlyModeError(RiskError):
    """Strategy is in close_only mode — no new opening positions."""

    def __init__(self, strategy_id: str = "") -> None:
        self.strategy_id = strategy_id
        msg = f"Strategy '{strategy_id}' is in close_only mode — no new opening positions"
        msg += ". Fix: change strategy mode or submit close orders only"
        super().__init__(msg)


class PauseOpenModeError(RiskError):
    """Strategy is in pause_open mode — new opening positions paused."""

    def __init__(self, strategy_id: str = "") -> None:
        self.strategy_id = strategy_id
        msg = f"Strategy '{strategy_id}' is in pause_open mode — opening positions paused"
        msg += ". Fix: resume strategy to allow new positions"
        super().__init__(msg)


# ── Execution Errors ─────────────────────────────────────────────────────────


class ExecutionError(HQMTSError):
    """Base error for execution-related failures."""


class OrderSubmissionError(ExecutionError):
    """Order submission failed."""

    def __init__(self, reject_reason: str, retryable: bool = False) -> None:
        self.reject_reason = reject_reason
        self.retryable = retryable
        super().__init__(f"Order submission failed: {reject_reason}")


class DuplicateOrderError(ExecutionError):
    """Duplicate order detected via idempotency key."""

    def __init__(self, idempotency_key: str = "") -> None:
        self.idempotency_key = idempotency_key
        msg = f"Duplicate order detected for idempotency key '{idempotency_key}'"
        msg += ". Fix: check if order was already submitted, use new key if retrying"
        super().__init__(msg)


class ReservationError(HQMTSError):
    """Base error for cash reservation failures."""


class InsufficientFundsError(ReservationError):
    """Not enough available funds for reservation."""


class ReservationExpiredError(ReservationError):
    """Cash reservation has expired."""


# ── Reconciliation Errors ────────────────────────────────────────────────────


class ReconciliationError(HQMTSError):
    """Base error for reconciliation failures."""


class PositionMismatchError(ReconciliationError):
    """Local position does not match QMT position."""


class ExternalTradeDetectedError(ReconciliationError):
    """External manual trade detected."""


# ── Agent Governance Errors ──────────────────────────────────────────────────


class AgentError(HQMTSError):
    """Base error for agent governance violations."""


class AgentPermissionDeniedError(AgentError):
    """Agent attempted a forbidden operation."""

    def __init__(self, agent_role: str, tool_name: str, reason: str = "") -> None:
        self.agent_role = agent_role
        self.tool_name = tool_name
        msg = f"Agent '{agent_role}' denied access to tool '{tool_name}'"
        if reason:
            msg += f": {reason}"
        super().__init__(msg)


class PolicyViolationError(AgentError):
    """Agent proposal failed policy check."""

    def __init__(self, proposal_type: str, reason: str) -> None:
        self.proposal_type = proposal_type
        self.reason = reason
        msg = f"Policy violation for proposal '{proposal_type}': {reason}"
        super().__init__(msg)


class ApprovalRequiredError(AgentError):
    """Agent proposal requires human approval."""

    def __init__(self, proposal_id: str = "", proposal_type: str = "") -> None:
        self.proposal_id = proposal_id
        self.proposal_type = proposal_type
        msg = f"Proposal '{proposal_id}' (type: {proposal_type}) requires human approval"
        msg += ". Fix: submit approval via governance API or wait for approver"
        super().__init__(msg)


class AgentTimeoutError(AgentError):
    """Agent task timed out."""

    def __init__(self, task_id: str, timeout_seconds: float) -> None:
        self.task_id = task_id
        self.timeout_seconds = timeout_seconds
        msg = f"Agent task '{task_id}' timed out after {timeout_seconds}s"
        super().__init__(msg)


class ForbiddenToolAttemptError(AgentError):
    """Agent attempted to call a forbidden tool."""

    def __init__(self, agent_role: str, tool_name: str) -> None:
        self.agent_role = agent_role
        self.tool_name = tool_name
        msg = f"Agent '{agent_role}' attempted forbidden tool '{tool_name}'"
        super().__init__(msg)

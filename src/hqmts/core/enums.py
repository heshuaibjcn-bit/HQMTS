"""Core enumerations for the HQMTS system.

All enums are defined here as the single source of truth, matching SAD V1.3 specifications.
"""

from __future__ import annotations

from enum import Enum


# ── Environment ──────────────────────────────────────────────────────────────


class Environment(str, Enum):
    """System environment isolation levels."""

    RESEARCH = "research"
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


# ── Trading Basics ───────────────────────────────────────────────────────────


class Cycle(str, Enum):
    """K-line bar cycle periods."""

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    M60 = "60m"


class Side(str, Enum):
    """Order side direction."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type."""

    LIMIT = "limit"
    MARKET = "market"


class TIF(str, Enum):
    """Time in force."""

    GTC = "gtc"  # Good till canceled
    IOC = "ioc"  # Immediate or cancel
    FAK = "fak"  # Fill and kill (A-stock specific)
    FOK = "fok"  # Fill or kill


# ── Signal ───────────────────────────────────────────────────────────────────


class SignalType(str, Enum):
    """Strategy signal types."""

    OPEN_LONG = "open_long"
    CLOSE_LONG = "close_long"
    OPEN_SHORT = "open_short"  # Reserved, A-stock has no short selling for stocks
    CLOSE_SHORT = "close_short"  # Reserved
    FLATTEN = "flatten"
    HOLD = "hold"


class TargetDirection(str, Enum):
    """Target position direction."""

    LONG = "long"
    FLAT = "flat"


# ── Order Status ─────────────────────────────────────────────────────────────


class OrderStatus(str, Enum):
    """Order lifecycle states (SAD 15.1)."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    REJECTED = "rejected"
    ERROR = "error"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


# ── Strategy Status ──────────────────────────────────────────────────────────


class StrategyStatus(str, Enum):
    """Strategy instance lifecycle states (SAD 15.3)."""

    DRAFT = "draft"
    BACKTEST_READY = "backtest_ready"
    VALIDATION_READY = "validation_ready"
    PAPER_RUNNING = "paper_running"
    LIVE_RUNNING = "live_running"
    PAUSE_OPEN = "pause_open"
    CLOSE_ONLY = "close_only"
    STOPPED = "stopped"
    PAUSED = "paused"
    ARCHIVED = "archived"


# ── Reconciliation Status ────────────────────────────────────────────────────


class ReconciliationStatus(str, Enum):
    """Reconciliation session states (SAD 15.4)."""

    INITIALIZED = "initialized"
    COMPARING = "comparing"
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    ADJUSTING = "adjusting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    ESCALATED = "escalated"


# ── Recovery Status ──────────────────────────────────────────────────────────


class RecoveryStatus(str, Enum):
    """Recovery session states (SAD 15.5)."""

    CREATED = "created"
    DIAGNOSING = "diagnosing"
    RECOVERING = "recovering"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


# ── Risk ─────────────────────────────────────────────────────────────────────


class RiskResultType(str, Enum):
    """Risk check result types (SAD 18, PRD 19)."""

    ALLOW = "allow"
    REJECT = "reject"
    RESIZE = "resize"
    DELAY = "delay"
    FORCE_FLATTEN = "force_flatten"


class RiskLayer(str, Enum):
    """Risk check layer ordering (PRD 19.2)."""

    MARKET = "market"
    ACCOUNT = "account"
    STRATEGY = "strategy"
    INSTRUMENT = "instrument"
    ORDER = "order"


class FinalCheckResult(str, Enum):
    """Final Pre-Submit Check result types (SAD 19.3)."""

    ALLOW = "allow"
    REJECT = "reject"
    RETRY_LATER = "retry_later"
    ESCALATE_MANUAL = "escalate_manual"


# ── Cash Reservation ─────────────────────────────────────────────────────────


class ReservationStatus(str, Enum):
    """Cash reservation lifecycle states (SAD 7.4)."""

    ACTIVE = "active"
    PARTIALLY_CONSUMED = "partially_consumed"
    FULLY_CONSUMED = "fully_consumed"
    RELEASED = "released"
    EXPIRED = "expired"
    INVALID = "invalid"


# ── Agent ────────────────────────────────────────────────────────────────────


class AgentTaskStatus(str, Enum):
    """Agent task states (SAD 7.6, 15.6)."""

    CREATED = "created"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_TOOL = "waiting_tool"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELED = "canceled"
    ESCALATED = "escalated"


class ProposalStatus(str, Enum):
    """Agent proposal states (SAD 7.7, 15.7)."""

    DRAFTED = "drafted"
    POLICY_CHECKING = "policy_checking"
    POLICY_REJECTED = "policy_rejected"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTION_PENDING = "execution_pending"
    EXECUTED = "executed"
    EXECUTION_FAILED = "execution_failed"
    EXPIRED = "expired"
    CANCELED = "canceled"


class ApprovalStatus(str, Enum):
    """Approval request states (SAD 7.9, 15.8)."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELED = "canceled"


class ExecutionStatus(str, Enum):
    """Controlled execution states (SAD 7.10)."""

    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class SideEffectLevel(str, Enum):
    """Tool invocation side effect levels (SAD 7.8)."""

    NONE = "none"
    READ_ONLY = "read_only"
    TASK_TRIGGER = "task_trigger"
    CONTROLLED_OPERATION = "controlled_operation"
    FORBIDDEN_ATTEMPT = "forbidden_attempt"


class AgentRole(str, Enum):
    """Agent role types (SAD 24.2)."""

    DATA = "data_agent"
    RESEARCH = "research_agent"
    STRATEGY_DESIGN = "strategy_design_agent"
    BACKTEST_ORCHESTRATION = "backtest_orchestration_agent"
    VALIDATION = "validation_agent"
    OPTIMIZATION = "optimization_agent"
    PORTFOLIO_ANALYSIS = "portfolio_analysis_agent"
    MONITORING = "monitoring_agent"
    RECONCILIATION = "reconciliation_agent"
    RECOVERY_COPILOT = "recovery_copilot_agent"
    AUDIT_REPORTING = "audit_reporting_agent"
    ORCHESTRATOR = "orchestrator_agent"


class ToolCategory(str, Enum):
    """Tool access categories (SAD 24.4)."""

    READ_ONLY = "read_only"
    TASK_TRIGGER = "task_trigger"
    CONTROLLED_OPERATION = "controlled_operation"
    FORBIDDEN = "forbidden"


# ── Rejection ────────────────────────────────────────────────────────────────


class RejectReason(str, Enum):
    """Order rejection taxonomy (SAD 20.1)."""

    NETWORK_ERROR = "network_error"
    ADAPTER_INTERNAL_ERROR = "adapter_internal_error"
    INVALID_PARAMETER = "invalid_parameter"
    BROKER_REJECT = "broker_reject"
    EXCHANGE_REJECT = "exchange_reject"
    MARKET_UNTRADABLE = "market_untradable"
    PRICE_OUT_OF_LIMIT = "price_out_of_limit"
    INSUFFICIENT_CASH = "insufficient_cash"
    INSUFFICIENT_POSITION = "insufficient_position"
    RISK_REJECT = "risk_reject"
    DUPLICATE_SUBMIT = "duplicate_submit"
    UNKNOWN_REJECT = "unknown_reject"
    UNAUTHORIZED_SOURCE = "unauthorized_source"
    POLICY_BLOCKED = "policy_blocked"
    KILL_SWITCH = "kill_switch"
    SIGNAL_EXPIRED = "signal_expired"
    STRATEGY_NOT_LIVE = "strategy_not_live"
    MARKET_CLOSED = "market_closed"
    ORDER_FREQUENCY_EXCEEDED = "order_frequency_exceeded"


# ── Data Quality ─────────────────────────────────────────────────────────────


class DataQualityGrade(str, Enum):
    """Data quality grades (SAD 10.2)."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"


class SnapshotCompleteness(str, Enum):
    """Decision snapshot completeness (SAD 11.3)."""

    COMPLETE = "complete"
    PARTIAL_ALLOWED = "partial_allowed"
    PARTIAL_BLOCKED = "partial_blocked"
    INVALID = "invalid"


# ── System ───────────────────────────────────────────────────────────────────


class AuthorityMode(str, Enum):
    """State authority modes (SAD 8.2)."""

    EVENT_PRIMARY = "event_primary"
    QUERY_PRIMARY = "query_primary"
    DEGRADED = "degraded"


class DegradationMode(str, Enum):
    """System degradation modes (SAD 23.1)."""

    NORMAL = "normal"
    PAUSE_OPEN = "pause_open"
    CLOSE_ONLY = "close_only"
    DEGRADED_QUERY_PRIMARY = "degraded_query_primary"
    EMERGENCY_STOP = "emergency_stop"


class AlertLevel(str, Enum):
    """Alert severity levels (SAD 28.3)."""

    P0 = "P0"  # 立即停机/仅平仓
    P1 = "P1"  # 立即人工介入
    P2 = "P2"  # 盘中关注，收盘处理
    P3 = "P3"  # 信息提醒


class PolicyCheckResult(str, Enum):
    """Policy check result (SAD 24.5)."""

    PASS = "pass"
    FAIL = "fail"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"

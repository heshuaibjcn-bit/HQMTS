"""Alert classification and monitoring service (SAD 28).

P0-P3 alert rules with evaluation and routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from hqmts.core.enums import AlertLevel


@dataclass(frozen=True)
class AlertRule:
    """Definition of an alert condition."""

    name: str
    metric: str  # The metric this rule evaluates
    description: str
    level: AlertLevel
    threshold: float  # Value that triggers the alert
    comparison: str = "gt"  # gt, lt, eq, gte, lte
    unit: str = ""  # e.g. "%", "count", "ms"


@dataclass
class Alert:
    """A triggered alert instance."""

    alert_id: str
    rule_name: str
    level: AlertLevel
    metric: str
    value: float
    threshold: float
    message: str
    detected_at: datetime = field(default_factory=datetime.now)
    routing_target: str = ""
    acknowledged: bool = False


# ── Pre-defined alert rules ────────────────────────────────────────────────────

P0_RULES: list[AlertRule] = [
    AlertRule(
        name="kill_switch_triggered",
        metric="kill_switch_active",
        description="Kill switch has been activated",
        level=AlertLevel.P0,
        threshold=1.0,
        comparison="eq",
    ),
    AlertRule(
        name="account_drawdown_breach",
        metric="account_drawdown_pct",
        description="Account drawdown exceeds maximum allowed threshold",
        level=AlertLevel.P0,
        threshold=15.0,
        comparison="gt",
        unit="%",
    ),
    AlertRule(
        name="order_failure_spike",
        metric="order_failure_rate_pct",
        description="Order failure rate exceeds 50% in 1 minute",
        level=AlertLevel.P0,
        threshold=50.0,
        comparison="gt",
        unit="%",
    ),
    AlertRule(
        name="position_mismatch",
        metric="position_mismatch_count",
        description="Position reconciliation found mismatches",
        level=AlertLevel.P0,
        threshold=0.0,
        comparison="gt",
        unit="count",
    ),
    AlertRule(
        name="qmt_connection_lost",
        metric="qmt_connected",
        description="QMT adapter connection lost",
        level=AlertLevel.P0,
        threshold=1.0,
        comparison="lt",
    ),
]

P1_RULES: list[AlertRule] = [
    AlertRule(
        name="order_failure_elevated",
        metric="order_failure_rate_pct",
        description="Order failure rate elevated above normal",
        level=AlertLevel.P1,
        threshold=20.0,
        comparison="gt",
        unit="%",
    ),
    AlertRule(
        name="signal_anomaly",
        metric="signal_anomaly_count",
        description="Unusual signal pattern detected",
        level=AlertLevel.P1,
        threshold=0.0,
        comparison="gt",
        unit="count",
    ),
    AlertRule(
        name="data_delay",
        metric="data_delay_ms",
        description="Market data delay exceeds threshold",
        level=AlertLevel.P1,
        threshold=5000.0,
        comparison="gt",
        unit="ms",
    ),
    AlertRule(
        name="bar_aggregation_error",
        metric="bar_aggregation_error_count",
        description="Bar aggregation errors detected",
        level=AlertLevel.P1,
        threshold=0.0,
        comparison="gt",
        unit="count",
    ),
    AlertRule(
        name="strategy_error_rate",
        metric="strategy_error_rate_pct",
        description="Strategy error rate exceeds threshold",
        level=AlertLevel.P1,
        threshold=5.0,
        comparison="gt",
        unit="%",
    ),
    AlertRule(
        name="qmt_latency_high",
        metric="qmt_latency_ms",
        description="QMT response latency exceeds threshold",
        level=AlertLevel.P1,
        threshold=3000.0,
        comparison="gt",
        unit="ms",
    ),
    AlertRule(
        name="agent_unauthorized_attempt",
        metric="agent_unauthorized_attempt_count",
        description="Agent attempted unauthorized action",
        level=AlertLevel.P1,
        threshold=0.0,
        comparison="gt",
        unit="count",
    ),
]

P2_RULES: list[AlertRule] = [
    AlertRule(
        name="fill_rate_low",
        metric="fill_rate_pct",
        description="Fill rate below expected level",
        level=AlertLevel.P2,
        threshold=80.0,
        comparison="lt",
        unit="%",
    ),
    AlertRule(
        name="system_cpu_high",
        metric="system_cpu_pct",
        description="System CPU usage high",
        level=AlertLevel.P2,
        threshold=85.0,
        comparison="gt",
        unit="%",
    ),
    AlertRule(
        name="system_memory_high",
        metric="system_memory_pct",
        description="System memory usage high",
        level=AlertLevel.P2,
        threshold=90.0,
        comparison="gt",
        unit="%",
    ),
    AlertRule(
        name="daily_pnl_drawdown",
        metric="daily_pnl_drawdown_pct",
        description="Daily P&L drawdown exceeding threshold",
        level=AlertLevel.P2,
        threshold=3.0,
        comparison="gt",
        unit="%",
    ),
]

P3_RULES: list[AlertRule] = [
    AlertRule(
        name="agent_task_timeout",
        metric="agent_task_timeout_count",
        description="Agent task timed out",
        level=AlertLevel.P3,
        threshold=0.0,
        comparison="gt",
        unit="count",
    ),
    AlertRule(
        name="agent_tool_failure",
        metric="agent_tool_failure_count",
        description="Agent tool invocation failed",
        level=AlertLevel.P3,
        threshold=0.0,
        comparison="gt",
        unit="count",
    ),
    AlertRule(
        name="agent_task_backlog",
        metric="agent_task_backlog_count",
        description="Agent task backlog exceeds threshold",
        level=AlertLevel.P3,
        threshold=10.0,
        comparison="gt",
        unit="count",
    ),
]

ALL_RULES: list[AlertRule] = P0_RULES + P1_RULES + P2_RULES + P3_RULES
RULES_BY_METRIC: dict[str, list[AlertRule]] = {}
for _r in ALL_RULES:
    RULES_BY_METRIC.setdefault(_r.metric, []).append(_r)


def _compare(value: float, threshold: float, comparison: str) -> bool:
    """Evaluate a comparison."""
    if comparison == "gt":
        return value > threshold
    elif comparison == "lt":
        return value < threshold
    elif comparison == "gte":
        return value >= threshold
    elif comparison == "lte":
        return value <= threshold
    elif comparison == "eq":
        return value == threshold
    return False


class AlertService:
    """Evaluates metrics against alert rules and produces alerts."""

    def __init__(self, rules: list[AlertRule] | None = None) -> None:
        self._rules = rules or ALL_RULES
        self._rules_by_metric: dict[str, list[AlertRule]] = {}
        for r in self._rules:
            self._rules_by_metric.setdefault(r.metric, []).append(r)

    def evaluate(self, metric_name: str, value: float) -> Alert | None:
        """Evaluate a metric value against matching rules.

        Returns the highest-severity triggered alert, or None.
        """
        rules = self._rules_by_metric.get(metric_name, [])
        best_alert: Alert | None = None

        for rule in rules:
            if _compare(value, rule.threshold, rule.comparison):
                import uuid
                alert = Alert(
                    alert_id=str(uuid.uuid4()),
                    rule_name=rule.name,
                    level=rule.level,
                    metric=rule.metric,
                    value=value,
                    threshold=rule.threshold,
                    message=f"{rule.description}: {value}{rule.unit} (threshold: {rule.threshold}{rule.unit})",
                    routing_target=self._route(rule.level),
                )
                # Keep highest severity
                if best_alert is None or self._level_priority(alert.level) < self._level_priority(best_alert.level):
                    best_alert = alert

        return best_alert

    def evaluate_all(self, metrics: dict[str, float]) -> list[Alert]:
        """Evaluate multiple metrics, return all triggered alerts sorted by severity."""
        alerts: list[Alert] = []
        for metric_name, value in metrics.items():
            alert = self.evaluate(metric_name, value)
            if alert:
                alerts.append(alert)
        alerts.sort(key=lambda a: self._level_priority(a.level))
        return alerts

    def _route(self, level: AlertLevel) -> str:
        """Determine routing target for an alert level."""
        if level == AlertLevel.P0:
            return "immediate_halt"
        elif level == AlertLevel.P1:
            return "human_intervention"
        elif level == AlertLevel.P2:
            return "intraday_watch"
        else:
            return "info_log"

    @staticmethod
    def _level_priority(level: AlertLevel) -> int:
        """Lower number = higher priority."""
        order = {AlertLevel.P0: 0, AlertLevel.P1: 1, AlertLevel.P2: 2, AlertLevel.P3: 3}
        return order.get(level, 99)

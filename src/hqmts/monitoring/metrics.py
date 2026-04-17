"""Metrics collection pipeline (SAD 28).

Collects trading kernel metrics, computes rates and aggregates,
feeds into AlertService for rule evaluation, and routes resulting
alerts through NotificationRouter.

This is the glue that connects the existing alert infrastructure
(rules, notification channels) to real metric data.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field

from hqmts.core.types import now_shanghai
from hqmts.monitoring.alerts import Alert, AlertService
from hqmts.monitoring.notification import NotificationRouter

logger = logging.getLogger(__name__)


# ── Metric data points ──────────────────────────────────────────────────────


@dataclass
class MetricPoint:
    """A single metric measurement."""

    name: str
    value: float
    timestamp: float  # time.monotonic for windowing
    tags: dict = field(default_factory=dict)


# ── Sliding window metric store ─────────────────────────────────────────────


class MetricStore:
    """In-memory time-series metric store with sliding window.

    Keeps metrics for a configurable duration (default 60s).
    Supports gauges (latest value) and counters (sum over window).
    """

    def __init__(self, window_seconds: float = 60.0) -> None:
        self._window = window_seconds
        self._points: dict[str, deque[MetricPoint]] = {}
        self._latest: dict[str, float] = {}

    def record(self, name: str, value: float, tags: dict | None = None) -> None:
        """Record a metric data point."""
        point = MetricPoint(
            name=name,
            value=value,
            timestamp=time.monotonic(),
            tags=tags or {},
        )
        if name not in self._points:
            self._points[name] = deque()
        self._points[name].append(point)
        self._latest[name] = value
        self._evict(name)

    def get_latest(self, name: str) -> float | None:
        """Get the most recent value for a metric."""
        return self._latest.get(name)

    def get_sum(self, name: str) -> float:
        """Get the sum of all values in the current window."""
        self._evict(name)
        points = self._points.get(name, deque())
        return sum(p.value for p in points)

    def get_count(self, name: str) -> int:
        """Get count of data points in the current window."""
        self._evict(name)
        return len(self._points.get(name, deque()))

    def get_rate(self, name: str) -> float:
        """Get rate (count per second) over the window."""
        self._evict(name)
        points = self._points.get(name, deque())
        if len(points) < 2:
            return 0.0
        duration = points[-1].timestamp - points[0].timestamp
        if duration <= 0:
            return 0.0
        return len(points) / duration

    def get_percentage(self, numerator_name: str, denominator_name: str) -> float:
        """Get numerator/denominator as percentage (0-100)."""
        denom = self.get_count(denominator_name)
        if denom == 0:
            return 0.0
        numer = self.get_count(numerator_name)
        return (numer / denom) * 100.0

    def snapshot(self) -> dict[str, float]:
        """Get all latest metric values as a flat dict."""
        self._evict_all()
        return dict(self._latest)

    def clear(self) -> None:
        """Clear all metrics."""
        self._points.clear()
        self._latest.clear()

    def _evict(self, name: str) -> None:
        """Remove points older than the window."""
        cutoff = time.monotonic() - self._window
        points = self._points.get(name)
        if points is None:
            return
        while points and points[0].timestamp < cutoff:
            points.popleft()

    def _evict_all(self) -> None:
        for name in self._points:
            self._evict(name)


# ── Metrics collector ───────────────────────────────────────────────────────


class MetricsCollector:
    """Collects trading metrics and feeds them to AlertService.

    Usage:
        collector = MetricsCollector(alert_service, router)
        collector.record_order_submitted()
        collector.record_order_filled()
        collector.record_order_failed("network_error")
        alerts = collector.evaluate()  # Runs all alert rules
    """

    def __init__(
        self,
        alert_service: AlertService | None = None,
        router: NotificationRouter | None = None,
        store: MetricStore | None = None,
    ) -> None:
        self._alert_service = alert_service or AlertService()
        self._router = router or NotificationRouter()
        self._store = store or MetricStore(window_seconds=60.0)
        self._alert_history: list[Alert] = []

    @property
    def store(self) -> MetricStore:
        return self._store

    @property
    def alert_history(self) -> list[Alert]:
        return list(self._alert_history)

    # ── Trading kernel metric recording ─────────────────────────────────

    def record_order_submitted(self) -> None:
        """Record an order submission."""
        self._store.record("order_submitted", 1.0)

    def record_order_accepted(self) -> None:
        """Record an order acceptance."""
        self._store.record("order_accepted", 1.0)

    def record_order_filled(self, latency_ms: float = 0.0) -> None:
        """Record an order fill."""
        self._store.record("order_filled", 1.0)
        if latency_ms > 0:
            self._store.record("fill_latency_ms", latency_ms)

    def record_order_failed(self, reason: str = "") -> None:
        """Record an order failure."""
        self._store.record("order_failed", 1.0)

    def record_order_rejected(self, reason: str = "") -> None:
        """Record an order rejection."""
        self._store.record("order_rejected", 1.0)

    def record_signal_generated(self) -> None:
        """Record a signal generation."""
        self._store.record("signal_generated", 1.0)

    def record_signal_anomaly(self) -> None:
        """Record a signal anomaly."""
        self._store.record("signal_anomaly_count", 1.0)

    # ── System health metrics ───────────────────────────────────────────

    def record_qmt_latency(self, latency_ms: float) -> None:
        """Record QMT adapter response latency."""
        self._store.record("qmt_latency_ms", latency_ms)

    def record_qmt_connected(self, connected: bool) -> None:
        """Record QMT connection status."""
        self._store.record("qmt_connected", 1.0 if connected else 0.0)

    def record_data_delay(self, delay_ms: float) -> None:
        """Record market data delay."""
        self._store.record("data_delay_ms", delay_ms)

    def record_bar_aggregation_error(self) -> None:
        """Record a bar aggregation error."""
        self._store.record("bar_aggregation_error_count", 1.0)

    def record_strategy_error(self) -> None:
        """Record a strategy execution error."""
        self._store.record("strategy_error_count", 1.0)

    def record_kill_switch(self, active: bool) -> None:
        """Record kill switch state change."""
        self._store.record("kill_switch_active", 1.0 if active else 0.0)

    def record_account_drawdown(self, drawdown_pct: float) -> None:
        """Record account drawdown percentage."""
        self._store.record("account_drawdown_pct", drawdown_pct)

    def record_daily_pnl(self, pnl_pct: float) -> None:
        """Record daily P&L as percentage."""
        self._store.record("daily_pnl_drawdown_pct", abs(min(0.0, pnl_pct)))

    def record_position_mismatch(self, count: int) -> None:
        """Record position reconciliation mismatches."""
        self._store.record("position_mismatch_count", float(count))

    def record_system_resources(self, cpu_pct: float, memory_pct: float) -> None:
        """Record system resource usage."""
        self._store.record("system_cpu_pct", cpu_pct)
        self._store.record("system_memory_pct", memory_pct)

    # ── Agent metrics ───────────────────────────────────────────────────

    def record_agent_task_timeout(self) -> None:
        self._store.record("agent_task_timeout_count", 1.0)

    def record_agent_tool_failure(self) -> None:
        self._store.record("agent_tool_failure_count", 1.0)

    def record_agent_unauthorized_attempt(self) -> None:
        self._store.record("agent_unauthorized_attempt_count", 1.0)

    def record_agent_task_backlog(self, count: int) -> None:
        self._store.record("agent_task_backlog_count", float(count))

    # ── Derived metric computation ──────────────────────────────────────

    def compute_order_failure_rate(self) -> float:
        """Compute order failure rate as percentage over window."""
        return self._store.get_percentage("order_failed", "order_submitted")

    def compute_fill_rate(self) -> float:
        """Compute fill rate as percentage over window."""
        total = self._store.get_count("order_accepted")
        if total == 0:
            return 100.0  # No orders, nothing to fail
        filled = self._store.get_count("order_filled")
        return (filled / total) * 100.0

    def compute_strategy_error_rate(self) -> float:
        """Compute strategy error rate as percentage of signals."""
        total = self._store.get_count("signal_generated")
        if total == 0:
            return 0.0
        errors = self._store.get_count("strategy_error_count")
        return (errors / total) * 100.0

    # ── Alert evaluation ────────────────────────────────────────────────

    def evaluate(self) -> list[Alert]:
        """Compute derived metrics and evaluate all alert rules.

        Returns triggered alerts, routes them through NotificationRouter.
        """
        # Compute derived metrics and add to snapshot
        self._store.record("order_failure_rate_pct", self.compute_order_failure_rate())
        self._store.record("fill_rate_pct", self.compute_fill_rate())
        self._store.record("strategy_error_rate_pct", self.compute_strategy_error_rate())

        # Get snapshot of all current metric values
        metrics = self._store.snapshot()

        # Evaluate all rules against current metrics
        alerts = self._alert_service.evaluate_all(metrics)

        # Route alerts and track history
        for alert in alerts:
            self._router.route(alert)
            self._alert_history.append(alert)
            logger.info(
                "ALERT_TRIGGERED [%s] %s value=%.2f threshold=%.2f",
                alert.level.value, alert.rule_name, alert.value, alert.threshold,
            )

        return alerts

    def record_and_evaluate(self, metric_name: str, value: float) -> list[Alert]:
        """Record a metric and immediately evaluate alerts. Convenience method."""
        self._store.record(metric_name, value)
        return self.evaluate()

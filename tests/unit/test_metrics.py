"""Tests for MetricsCollector pipeline (SAD 28)."""

from __future__ import annotations

import pytest
import time

from hqmts.monitoring.alerts import AlertLevel, AlertService, P0_RULES, P1_RULES
from hqmts.monitoring.metrics import MetricStore, MetricsCollector
from hqmts.monitoring.notification import InMemoryChannel, NotificationRouter


class TestMetricStore:
    def test_record_and_get_latest(self):
        store = MetricStore()
        store.record("cpu_pct", 75.0)
        assert store.get_latest("cpu_pct") == 75.0

    def test_latest_overwrites(self):
        store = MetricStore()
        store.record("cpu_pct", 75.0)
        store.record("cpu_pct", 80.0)
        assert store.get_latest("cpu_pct") == 80.0

    def test_get_sum(self):
        store = MetricStore()
        store.record("order_failed", 1.0)
        store.record("order_failed", 1.0)
        store.record("order_failed", 1.0)
        assert store.get_sum("order_failed") == 3.0

    def test_get_count(self):
        store = MetricStore()
        for _ in range(5):
            store.record("orders", 1.0)
        assert store.get_count("orders") == 5

    def test_get_percentage(self):
        store = MetricStore()
        # 3 failures out of 10 submissions = 30%
        for _ in range(10):
            store.record("order_submitted", 1.0)
        for _ in range(3):
            store.record("order_failed", 1.0)
        pct = store.get_percentage("order_failed", "order_submitted")
        assert pct == pytest.approx(30.0)

    def test_get_percentage_zero_denominator(self):
        store = MetricStore()
        assert store.get_percentage("failed", "submitted") == 0.0

    def test_snapshot(self):
        store = MetricStore()
        store.record("cpu", 50.0)
        store.record("mem", 60.0)
        snap = store.snapshot()
        assert snap["cpu"] == 50.0
        assert snap["mem"] == 60.0

    def test_window_eviction(self):
        store = MetricStore(window_seconds=0.05)
        store.record("test", 1.0)
        time.sleep(0.06)
        store.record("test", 2.0)  # triggers eviction
        assert store.get_count("test") == 1

    def test_clear(self):
        store = MetricStore()
        store.record("test", 1.0)
        store.clear()
        assert store.get_latest("test") is None

    def test_get_rate(self):
        store = MetricStore(window_seconds=5.0)
        store.record("orders", 1.0)
        time.sleep(0.02)
        store.record("orders", 1.0)
        rate = store.get_rate("orders")
        assert rate > 0  # Some positive rate

    def test_get_rate_single_point(self):
        store = MetricStore()
        store.record("test", 1.0)
        assert store.get_rate("test") == 0.0


class TestMetricsCollector:
    @pytest.fixture
    def channel(self):
        return InMemoryChannel()

    @pytest.fixture
    def router(self, channel):
        router = NotificationRouter()
        router.add_channel("immediate_halt", channel)
        router.add_channel("human_intervention", channel)
        router.add_channel("intraday_watch", channel)
        router.add_channel("info_log", channel)
        return router

    @pytest.fixture
    def collector(self, router):
        return MetricsCollector(
            alert_service=AlertService(),
            router=router,
        )

    def test_record_order_submitted(self, collector):
        collector.record_order_submitted()
        assert collector.store.get_count("order_submitted") == 1

    def test_record_order_filled(self, collector):
        collector.record_order_filled(latency_ms=150.0)
        assert collector.store.get_count("order_filled") == 1
        assert collector.store.get_latest("fill_latency_ms") == 150.0

    def test_record_qmt_latency(self, collector):
        collector.record_qmt_latency(200.0)
        assert collector.store.get_latest("qmt_latency_ms") == 200.0

    def test_compute_order_failure_rate(self, collector):
        for _ in range(10):
            collector.record_order_submitted()
        for _ in range(3):
            collector.record_order_failed()
        rate = collector.compute_order_failure_rate()
        assert rate == pytest.approx(30.0)

    def test_compute_fill_rate(self, collector):
        for _ in range(10):
            collector.record_order_accepted()
        for _ in range(8):
            collector.record_order_filled()
        rate = collector.compute_fill_rate()
        assert rate == pytest.approx(80.0)

    def test_compute_strategy_error_rate(self, collector):
        for _ in range(20):
            collector.record_signal_generated()
        collector.record_strategy_error()
        rate = collector.compute_strategy_error_rate()
        assert rate == pytest.approx(5.0)

    def test_evaluate_triggers_alert(self, collector, channel):
        """Recording a kill switch triggers P0 alert."""
        collector.record_kill_switch(True)
        alerts = collector.evaluate()
        assert len(alerts) >= 1
        assert any(a.level == AlertLevel.P0 for a in alerts)
        assert len(channel.alerts) >= 1

    def test_evaluate_no_alert_when_normal(self, collector, channel):
        """Normal metrics should not trigger alerts."""
        collector.record_order_submitted()
        collector.record_qmt_connected(True)
        collector.record_qmt_latency(100.0)
        alerts = collector.evaluate()
        # Should not have any critical alerts
        critical = [a for a in alerts if a.level in (AlertLevel.P0, AlertLevel.P1)]
        assert len(critical) == 0

    def test_evaluate_qmt_connection_lost(self, collector, channel):
        """QMT connection lost triggers P0 alert."""
        collector.record_qmt_connected(False)
        alerts = collector.evaluate()
        assert any(a.rule_name == "qmt_connection_lost" for a in alerts)

    def test_evaluate_high_failure_rate(self, collector, channel):
        """60% order failure triggers P0 alert."""
        for _ in range(10):
            collector.record_order_submitted()
        for _ in range(6):
            collector.record_order_failed()
        alerts = collector.evaluate()
        assert any(a.rule_name == "order_failure_spike" for a in alerts)

    def test_elevated_failure_rate_triggers_p1(self, collector, channel):
        """25% failure rate triggers P1 (not P0 which is 50%)."""
        for _ in range(20):
            collector.record_order_submitted()
        for _ in range(5):
            collector.record_order_failed()
        alerts = collector.evaluate()
        p1_alerts = [a for a in alerts if a.level == AlertLevel.P1]
        assert any(a.rule_name == "order_failure_elevated" for a in p1_alerts)

    def test_account_drawdown_alert(self, collector, channel):
        """20% drawdown triggers P0 alert."""
        collector.record_account_drawdown(20.0)
        alerts = collector.evaluate()
        assert any(a.rule_name == "account_drawdown_breach" for a in alerts)

    def test_alert_history(self, collector):
        """Alerts are tracked in history."""
        collector.record_kill_switch(True)
        collector.evaluate()
        assert len(collector.alert_history) >= 1

    def test_record_and_evaluate(self, collector, channel):
        """Convenience method records and evaluates in one call."""
        alerts = collector.record_and_evaluate("kill_switch_active", 1.0)
        assert any(a.level == AlertLevel.P0 for a in alerts)

    def test_system_resources(self, collector):
        collector.record_system_resources(90.0, 95.0)
        assert collector.store.get_latest("system_cpu_pct") == 90.0
        assert collector.store.get_latest("system_memory_pct") == 95.0

    def test_agent_metrics(self, collector):
        collector.record_agent_task_timeout()
        collector.record_agent_tool_failure()
        collector.record_agent_unauthorized_attempt()
        collector.record_agent_task_backlog(15)
        assert collector.store.get_count("agent_task_timeout_count") == 1
        assert collector.store.get_latest("agent_task_backlog_count") == 15.0

    def test_position_mismatch_alert(self, collector, channel):
        """Position mismatch count > 0 triggers P0 alert."""
        collector.record_position_mismatch(3)
        alerts = collector.evaluate()
        assert any(a.rule_name == "position_mismatch" for a in alerts)

    def test_data_delay_alert(self, collector, channel):
        """Data delay > 5000ms triggers P1 alert."""
        collector.record_data_delay(6000.0)
        alerts = collector.evaluate()
        assert any(a.rule_name == "data_delay" for a in alerts)

    def test_multiple_alerts_same_evaluate(self, collector, channel):
        """Multiple conditions can trigger multiple alerts at once."""
        collector.record_kill_switch(True)
        collector.record_account_drawdown(20.0)
        collector.record_qmt_connected(False)
        alerts = collector.evaluate()
        # Should have at least 3 P0 alerts
        p0 = [a for a in alerts if a.level == AlertLevel.P0]
        assert len(p0) >= 3

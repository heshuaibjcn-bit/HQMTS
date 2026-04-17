"""Tests for monitoring notification channels."""

from __future__ import annotations

from datetime import datetime

from hqmts.core.enums import AlertLevel
from hqmts.monitoring.alerts import Alert
from hqmts.monitoring.notification import (
    InMemoryChannel,
    LogChannel,
    NotificationRouter,
)


def _make_alert(level: AlertLevel = AlertLevel.P0) -> Alert:
    return Alert(
        alert_id="a-001",
        rule_name="test_rule",
        level=level,
        metric="test_metric",
        value=99.0,
        threshold=50.0,
        message="Test alert",
        detected_at=datetime(2024, 1, 2, 10, 0),
        routing_target="immediate_halt",
    )


class TestInMemoryChannel:
    def test_collects_alerts(self):
        ch = InMemoryChannel()
        alert = _make_alert()
        assert ch.send(alert) is True
        assert len(ch.alerts) == 1
        assert ch.alerts[0].alert_id == "a-001"

    def test_clear(self):
        ch = InMemoryChannel()
        ch.send(_make_alert())
        ch.send(_make_alert())
        assert len(ch.alerts) == 2
        ch.clear()
        assert len(ch.alerts) == 0


class TestLogChannel:
    def test_send_returns_true(self):
        ch = LogChannel()
        assert ch.send(_make_alert()) is True


class TestNotificationRouter:
    def test_default_channels_exist(self):
        router = NotificationRouter()
        assert "immediate_halt" in router._channels
        assert "human_intervention" in router._channels
        assert "intraday_watch" in router._channels
        assert "info_log" in router._channels

    def test_route_p0_alert(self):
        router = NotificationRouter()
        mem = InMemoryChannel()
        router.add_channel("immediate_halt", mem)
        alert = _make_alert(AlertLevel.P0)
        results = router.route(alert)
        assert all(results)
        assert len(mem.alerts) == 1

    def test_route_p1_alert(self):
        router = NotificationRouter()
        mem = InMemoryChannel()
        router.add_channel("human_intervention", mem)
        alert = _make_alert(AlertLevel.P1)
        alert.routing_target = "human_intervention"
        results = router.route(alert)
        assert all(results)
        assert len(mem.alerts) == 1

    def test_route_multiple_channels(self):
        router = NotificationRouter()
        mem1 = InMemoryChannel()
        mem2 = InMemoryChannel()
        router.add_channel("immediate_halt", mem1)
        router.add_channel("immediate_halt", mem2)
        router.route(_make_alert(AlertLevel.P0))
        assert len(mem1.alerts) == 1
        assert len(mem2.alerts) == 1

    def test_route_no_matching_channels(self):
        router = NotificationRouter()
        alert = _make_alert()
        alert.routing_target = "nonexistent"
        results = router.route(alert)
        assert results == []


class TestExtendedP1P3Rules:
    def test_p1_rules_count(self):
        from hqmts.monitoring.alerts import P1_RULES
        assert len(P1_RULES) >= 6

    def test_p2_rules_count(self):
        from hqmts.monitoring.alerts import P2_RULES
        assert len(P2_RULES) >= 4

    def test_p3_rules_count(self):
        from hqmts.monitoring.alerts import P3_RULES
        assert len(P3_RULES) >= 3

    def test_all_rules_cover_levels(self):
        from hqmts.monitoring.alerts import ALL_RULES
        levels = {r.level for r in ALL_RULES}
        assert AlertLevel.P0 in levels
        assert AlertLevel.P1 in levels
        assert AlertLevel.P2 in levels
        assert AlertLevel.P3 in levels

    def test_new_p1_rules_evaluable(self):
        from hqmts.monitoring.alerts import AlertService
        svc = AlertService()
        alert = svc.evaluate("bar_aggregation_error_count", 1.0)
        assert alert is not None
        assert alert.level == AlertLevel.P1

    def test_new_p2_rules_evaluable(self):
        from hqmts.monitoring.alerts import AlertService
        svc = AlertService()
        alert = svc.evaluate("system_cpu_pct", 90.0)
        assert alert is not None
        assert alert.level == AlertLevel.P2

    def test_new_p3_rules_evaluable(self):
        from hqmts.monitoring.alerts import AlertService
        svc = AlertService()
        alert = svc.evaluate("agent_tool_failure_count", 1.0)
        assert alert is not None
        assert alert.level == AlertLevel.P3

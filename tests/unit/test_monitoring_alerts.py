"""Tests for monitoring P0 alerts (SAD 28)."""

from __future__ import annotations

from hqmts.core.enums import AlertLevel
from hqmts.monitoring.alerts import (
    ALL_RULES,
    P0_RULES,
    P1_RULES,
    AlertRule,
    AlertService,
)


class TestAlertRules:
    def test_p0_rules_defined(self):
        assert len(P0_RULES) >= 5
        names = {r.name for r in P0_RULES}
        assert "kill_switch_triggered" in names
        assert "account_drawdown_breach" in names
        assert "order_failure_spike" in names
        assert "position_mismatch" in names
        assert "qmt_connection_lost" in names

    def test_all_p0_rules_level(self):
        for rule in P0_RULES:
            assert rule.level == AlertLevel.P0, f"{rule.name} should be P0"

    def test_p1_rules_defined(self):
        assert len(P1_RULES) >= 3
        for rule in P1_RULES:
            assert rule.level == AlertLevel.P1

    def test_all_rules_cover_multiple_levels(self):
        levels = {r.level for r in ALL_RULES}
        assert AlertLevel.P0 in levels
        assert AlertLevel.P1 in levels
        assert AlertLevel.P2 in levels or AlertLevel.P3 in levels


class TestAlertService:
    def test_kill_switch_triggered(self):
        svc = AlertService()
        alert = svc.evaluate("kill_switch_active", 1.0)
        assert alert is not None
        assert alert.level == AlertLevel.P0
        assert alert.rule_name == "kill_switch_triggered"

    def test_kill_switch_not_triggered(self):
        svc = AlertService()
        alert = svc.evaluate("kill_switch_active", 0.0)
        assert alert is None

    def test_account_drawdown_breach(self):
        svc = AlertService()
        alert = svc.evaluate("account_drawdown_pct", 16.0)
        assert alert is not None
        assert alert.level == AlertLevel.P0
        assert alert.value == 16.0

    def test_account_drawdown_ok(self):
        svc = AlertService()
        alert = svc.evaluate("account_drawdown_pct", 10.0)
        assert alert is None

    def test_order_failure_spike(self):
        svc = AlertService()
        alert = svc.evaluate("order_failure_rate_pct", 60.0)
        assert alert is not None
        assert alert.level == AlertLevel.P0

    def test_order_failure_elevated_p1(self):
        """25% failure triggers P1 but not P0."""
        svc = AlertService()
        alert = svc.evaluate("order_failure_rate_pct", 25.0)
        assert alert is not None
        assert alert.level == AlertLevel.P1

    def test_order_failure_normal(self):
        svc = AlertService()
        alert = svc.evaluate("order_failure_rate_pct", 10.0)
        assert alert is None

    def test_position_mismatch(self):
        svc = AlertService()
        alert = svc.evaluate("position_mismatch_count", 1.0)
        assert alert is not None
        assert alert.level == AlertLevel.P0

    def test_position_ok(self):
        svc = AlertService()
        alert = svc.evaluate("position_mismatch_count", 0.0)
        assert alert is None

    def test_qmt_connection_lost(self):
        svc = AlertService()
        alert = svc.evaluate("qmt_connected", 0.0)
        assert alert is not None
        assert alert.level == AlertLevel.P0

    def test_qmt_connected_ok(self):
        svc = AlertService()
        alert = svc.evaluate("qmt_connected", 1.0)
        assert alert is None

    def test_unknown_metric(self):
        svc = AlertService()
        alert = svc.evaluate("nonexistent_metric", 999.0)
        assert alert is None

    def test_evaluate_all(self):
        svc = AlertService()
        alerts = svc.evaluate_all({
            "kill_switch_active": 1.0,
            "account_drawdown_pct": 5.0,
            "order_failure_rate_pct": 60.0,
        })
        # kill_switch (P0) + failure_spike (P0)
        assert len(alerts) == 2
        assert all(a.level == AlertLevel.P0 for a in alerts)

    def test_evaluate_all_sorted_by_severity(self):
        svc = AlertService()
        alerts = svc.evaluate_all({
            "order_failure_rate_pct": 25.0,  # P1
            "kill_switch_active": 1.0,  # P0
        })
        assert alerts[0].level == AlertLevel.P0
        assert alerts[1].level == AlertLevel.P1

    def test_alert_has_routing_target(self):
        svc = AlertService()
        alert = svc.evaluate("kill_switch_active", 1.0)
        assert alert is not None
        assert alert.routing_target == "immediate_halt"

    def test_p1_routing(self):
        svc = AlertService()
        alert = svc.evaluate("data_delay_ms", 6000.0)
        assert alert is not None
        assert alert.routing_target == "human_intervention"

    def test_custom_rules(self):
        custom = [AlertRule(
            name="test_rule",
            metric="test_metric",
            description="Test",
            level=AlertLevel.P2,
            threshold=5.0,
            comparison="gt",
        )]
        svc = AlertService(rules=custom)
        assert svc.evaluate("test_metric", 6.0) is not None
        assert svc.evaluate("test_metric", 4.0) is None
        assert svc.evaluate("kill_switch_active", 1.0) is None  # Not in custom rules

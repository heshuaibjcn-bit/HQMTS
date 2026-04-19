"""Tests for core enums."""

from hqmts.core.enums import (
    AlertLevel,
    Cycle,
    Environment,
    OrderStatus,
    RejectReason,
    RiskResultType,
    StrategyStatus,
)


class TestEnvironment:
    def test_environments(self):
        assert Environment.RESEARCH.value == "research"
        assert Environment.BACKTEST.value == "backtest"
        assert Environment.PAPER.value == "paper"
        assert Environment.LIVE.value == "live"

    def test_all_environments(self):
        assert len(Environment) == 4


class TestCycle:
    def test_cycles(self):
        assert Cycle.M1.value == "1m"
        assert Cycle.M5.value == "5m"
        assert Cycle.M15.value == "15m"
        assert Cycle.M30.value == "30m"
        assert Cycle.M60.value == "60m"


class TestOrderStatus:
    def test_all_states(self):
        expected = {
            "created", "pending_submit", "submitted", "accepted",
            "partial_filled", "filled",
            "canceled", "rejected", "error", "suspended", "expired",
        }
        actual = {s.value for s in OrderStatus}
        assert actual == expected


class TestRejectReason:
    def test_all_19_types(self):
        assert len(RejectReason) == 19

    def test_specific_reasons(self):
        assert RejectReason.NETWORK_ERROR.value == "network_error"
        assert RejectReason.UNAUTHORIZED_SOURCE.value == "unauthorized_source"
        assert RejectReason.POLICY_BLOCKED.value == "policy_blocked"


class TestRiskResultType:
    def test_priority_order(self):
        types = list(RiskResultType)
        assert RiskResultType.FORCE_FLATTEN in types
        assert RiskResultType.ALLOW in types

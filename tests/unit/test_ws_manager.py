"""Tests for WebSocket connection manager."""

from __future__ import annotations

import pytest

from hqmts.api.ws_manager import ConnectionManager
from hqmts.core.enums import UserRole


class TestConnectionManager:
    def test_initial_state(self):
        mgr = ConnectionManager()
        assert mgr.active_count == 0

    def test_buffer_message_increments_sequence(self):
        mgr = ConnectionManager()
        msg = mgr.buffer_message("user_1", {"type": "order_update", "data": {}})
        assert msg["sequence"] == 1
        msg2 = mgr.buffer_message("user_1", {"type": "signal_new", "data": {}})
        assert msg2["sequence"] == 2

    def test_buffer_message_per_user_sequence(self):
        mgr = ConnectionManager()
        msg1 = mgr.buffer_message("user_1", {"type": "test"})
        msg2 = mgr.buffer_message("user_2", {"type": "test"})
        assert msg1["sequence"] == 1
        assert msg2["sequence"] == 1  # Independent per user

    def test_get_buffered_messages_after_sequence(self):
        mgr = ConnectionManager()
        mgr.buffer_message("user_1", {"type": "a"})
        mgr.buffer_message("user_1", {"type": "b"})
        mgr.buffer_message("user_1", {"type": "c"})

        buffered = mgr.get_buffered_messages("user_1", 1)
        assert len(buffered) == 2
        assert buffered[0]["sequence"] == 2
        assert buffered[1]["sequence"] == 3

    def test_get_buffered_messages_empty_for_unknown_user(self):
        mgr = ConnectionManager()
        assert mgr.get_buffered_messages("unknown", 0) == []

    def test_buffer_trims_to_max_size(self):
        mgr = ConnectionManager(buffer_size=5)
        for i in range(10):
            mgr.buffer_message("user_1", {"type": "test", "i": i})

        buffered = mgr.get_buffered_messages("user_1", 0)
        assert len(buffered) == 5
        assert buffered[0]["sequence"] == 6  # Oldest trimmed

    def test_get_connections_for_nonexistent_user(self):
        mgr = ConnectionManager()
        assert mgr.get_connections_for_user("nobody") == []


class TestWSBridgeRoleFiltering:
    """Test PipelineBusToWSBridge role-based filtering logic."""

    def _make_bridge(self):
        mgr = ConnectionManager()
        from hqmts.api.ws_bridge import PipelineBusToWSBridge
        return PipelineBusToWSBridge(mgr)

    def test_risk_change_blocked_for_researcher(self):
        bridge = self._make_bridge()
        msg = {"type": "risk_change", "data": {}}
        assert not bridge._should_deliver(
            msg, UserRole.QUANT_RESEARCHER.value, "u1", {},
        )

    def test_risk_change_allowed_for_trader(self):
        bridge = self._make_bridge()
        msg = {"type": "risk_change", "data": {}}
        assert bridge._should_deliver(msg, UserRole.TRADER.value, "u1", {})

    def test_risk_change_allowed_for_admin(self):
        bridge = self._make_bridge()
        msg = {"type": "risk_change", "data": {}}
        assert bridge._should_deliver(msg, UserRole.SYSTEM_ADMIN.value, "u1", {})

    def test_alert_p0_blocked_for_researcher(self):
        bridge = self._make_bridge()
        msg = {"type": "alert", "data": {}}
        assert not bridge._should_deliver(
            msg, UserRole.QUANT_RESEARCHER.value, "u1", {"level": "P0"},
        )

    def test_alert_p2_allowed_for_researcher(self):
        bridge = self._make_bridge()
        msg = {"type": "alert", "data": {}}
        assert bridge._should_deliver(
            msg, UserRole.QUANT_RESEARCHER.value, "u1", {"level": "P2"},
        )

    def test_alert_p1_allowed_for_trader(self):
        bridge = self._make_bridge()
        msg = {"type": "alert", "data": {}}
        assert bridge._should_deliver(
            msg, UserRole.TRADER.value, "u1", {"level": "P1"},
        )

    def test_order_update_allowed_for_all(self):
        bridge = self._make_bridge()
        msg = {"type": "order_update", "data": {}}
        for role in [UserRole.QUANT_RESEARCHER, UserRole.TRADER, UserRole.SYSTEM_ADMIN]:
            assert bridge._should_deliver(msg, role.value, "u1", {})

    def test_position_update_allowed_for_all(self):
        bridge = self._make_bridge()
        msg = {"type": "position_update", "data": {}}
        for role in [UserRole.QUANT_RESEARCHER, UserRole.TRADER, UserRole.SYSTEM_ADMIN]:
            assert bridge._should_deliver(msg, role.value, "u1", {})

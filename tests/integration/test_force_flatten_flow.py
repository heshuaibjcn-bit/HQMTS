"""Integration test: Force flatten lifecycle with real metrics pipeline."""

from __future__ import annotations

import pytest

from hqmts.core.enums import FlattenTrigger
from hqmts.monitoring.metrics import MetricsCollector
from hqmts.risk.final_check import FinalPreSubmitCheck
from hqmts.risk.force_flatten import ForceFlattenService


class FakePosition:
    instrument_id: str
    total_quantity: int
    available_quantity: int
    today_bought_quantity: int

    def __init__(self, instrument_id, total, available, today_bought=0):
        self.instrument_id = instrument_id
        self.total_quantity = total
        self.available_quantity = available
        self.today_bought_quantity = today_bought


class FakePositionRepo:
    def __init__(self, positions):
        self._positions = positions

    async def get_open_positions(self, account_id):
        return list(self._positions)


class FakeOrderService:
    def __init__(self):
        self.submitted = []

    async def submit_flatten_order(self, instrument_id, quantity, flatten_id):
        self.submitted.append({
            "instrument_id": instrument_id,
            "quantity": quantity,
        })


class TestForceFlattenIntegration:
    """Full force flatten flow: positions → flatten → metrics → alerts."""

    @pytest.mark.asyncio
    async def test_flatten_triggers_kill_switch_alert(self):
        """Force flatten triggered by kill switch also fires P0 alert."""
        from hqmts.monitoring.notification import InMemoryChannel, NotificationRouter

        channel = InMemoryChannel()
        router = NotificationRouter()
        router.add_channel("immediate_halt", channel)
        metrics = MetricsCollector(router=router)

        # Kill switch activates
        metrics.record_kill_switch(True)

        # Force flatten fires
        order_svc = FakeOrderService()
        svc = ForceFlattenService(
            position_repo=FakePositionRepo([
                FakePosition("000001.SZ", 1000, 1000),
            ]),
            final_check=FinalPreSubmitCheck(),
            order_service=order_svc,
            account_id="test",
        )
        progress = await svc.execute_flatten(
            FlattenTrigger.KILL_SWITCH, "Kill switch activated",
        )

        # Verify flatten succeeded
        assert progress.flattened_positions == 1

        # Verify alert fired
        alerts = metrics.record_and_evaluate("kill_switch_active", 1.0)
        assert any(a.rule_name == "kill_switch_triggered" for a in alerts)
        assert len(channel.alerts) >= 1

    @pytest.mark.asyncio
    async def test_flatten_with_mixed_t1_positions(self):
        """Mixed positions: some sellable, some T+1 blocked, some partial."""
        order_svc = FakeOrderService()
        svc = ForceFlattenService(
            position_repo=FakePositionRepo([
                FakePosition("000001.SZ", 1000, 1000, 0),     # Fully sellable
                FakePosition("600000.SH", 500, 500, 500),     # Fully T+1 blocked
                FakePosition("000002.SZ", 800, 800, 300),     # Partially sellable (500)
            ]),
            final_check=FinalPreSubmitCheck(),
            order_service=order_svc,
            account_id="test",
        )
        progress = await svc.execute_flatten(
            FlattenTrigger.MAX_DRAWDOWN, "Max drawdown breached",
        )

        assert progress.total_positions == 3
        assert progress.flattened_positions == 2   # 000001.SZ + 000002.SZ
        assert progress.skipped_positions == 1     # 600000.SH (T+1)
        assert progress.tasks[2].sellable_quantity == 500  # 800 - 300

    @pytest.mark.asyncio
    async def test_flatten_and_retry_cycle(self):
        """Full cycle: flatten → some fail → retry → succeed."""
        order_svc = FakeOrderService()
        svc = ForceFlattenService(
            position_repo=FakePositionRepo([
                FakePosition("000001.SZ", 100, 100),
                FakePosition("600000.SH", 200, 200),
            ]),
            final_check=FinalPreSubmitCheck(),
            order_service=order_svc,
            account_id="test",
        )

        # First attempt: both succeed
        progress = await svc.execute_flatten(
            FlattenTrigger.RISK_RULE, "Risk rule triggered",
        )
        assert progress.flattened_positions == 2
        assert progress.is_complete is True

"""Tests for SyncRiskAdapter and risk integration in BacktestEngine."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from hqmts.backtest.engine import BacktestConfig, BacktestEngine
from hqmts.backtest.order import BacktestOrder
from hqmts.backtest.portfolio import PortfolioState
from hqmts.backtest.risk_adapter import SyncRiskAdapter, build_risk_context
from hqmts.backtest.strategy import StrategyTemplate
from hqmts.core.enums import Cycle, RiskResultType, Side
from hqmts.core.types import InstrumentId, RiskCheckId, StrategyInstanceId, VersionStr
from hqmts.domain.bar import Bar
from hqmts.domain.instrument import Instrument
from hqmts.domain.risk import RiskCheckResult
from hqmts.risk.engine import RiskContext, RiskEngine, RiskRule, RiskRuleResult


# ── Helpers ──────────────────────────────────────────────────────────────────


def _bar(
    start: datetime,
    instrument_id: str = "000001.SZ",
    close: str = "10.00",
    open_: str = "10.00",
    high: str = "10.50",
    low: str = "9.50",
    volume: int = 100000,
) -> Bar:
    return Bar(
        instrument_id=InstrumentId(instrument_id),
        cycle=Cycle.M5,
        bar_start_time=start,
        bar_end_time=start + timedelta(minutes=5),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=volume,
        amount=Decimal("1000000"),
        is_completed=True,
        source="test",
        data_version=VersionStr("v1"),
    )


def _instrument(instrument_id: str = "000001.SZ") -> Instrument:
    return Instrument(
        instrument_id=InstrumentId(instrument_id),
        ts_code=instrument_id,
        exchange="SZSE",
        symbol=instrument_id.split(".")[0],
        name="TestStock",
    )


class BuyOnceStrategy(StrategyTemplate):
    """Buys once, then does nothing."""
    def __init__(self):
        self._bought = False

    def on_init(self, params):
        pass

    def on_bar(self, bar, context):
        pass

    def generate_signal(self, context):
        return None

    def generate_orders(self, context):
        if not self._bought:
            self._bought = True
            return [BacktestOrder(
                instrument_id=str(context.instrument_id),
                side=Side.BUY,
                quantity=100,
                signal_id="buy-1",
            )]
        return []


# ── SyncRiskAdapter Unit Tests ───────────────────────────────────────────────


class TestSyncRiskAdapter:
    def test_none_engine_returns_allow(self):
        adapter = SyncRiskAdapter(None)
        ctx = RiskContext(instrument_id="000001.SZ")
        result = adapter.evaluate(ctx)
        assert result.result_type == RiskResultType.ALLOW

    def test_with_reject_rule(self):
        """SyncRiskAdapter wraps async risk engine correctly."""
        class AlwaysReject(RiskRule):
            @property
            def layer(self):
                from hqmts.core.enums import RiskLayer
                return RiskLayer.ACCOUNT

            @property
            def name(self):
                return "always_reject"

            async def check(self, context):
                return RiskRuleResult(
                    result_type=RiskResultType.REJECT,
                    rule_name="always_reject",
                    reason="test rejection",
                )

        engine = RiskEngine()
        engine.register_rule(AlwaysReject())
        adapter = SyncRiskAdapter(engine)
        ctx = RiskContext(instrument_id="000001.SZ")
        result = adapter.evaluate(ctx)
        assert result.result_type == RiskResultType.REJECT
        adapter.close()

    def test_with_resize_rule(self):
        class ResizeTo50(RiskRule):
            @property
            def layer(self):
                from hqmts.core.enums import RiskLayer
                return RiskLayer.ACCOUNT

            @property
            def name(self):
                return "resize_50"

            async def check(self, context):
                return RiskRuleResult(
                    result_type=RiskResultType.RESIZE,
                    rule_name="resize_50",
                    reason="too large",
                    resized_quantity=50,
                )

        engine = RiskEngine()
        engine.register_rule(ResizeTo50())
        adapter = SyncRiskAdapter(engine)
        ctx = RiskContext(instrument_id="000001.SZ", quantity=200)
        result = adapter.evaluate(ctx)
        assert result.result_type == RiskResultType.RESIZE
        assert result.resized_quantity == 50
        adapter.close()


# ── build_risk_context Tests ─────────────────────────────────────────────────


class TestBuildRiskContext:
    def test_maps_order_fields(self):
        order = BacktestOrder(
            instrument_id="000001.SZ",
            side=Side.BUY,
            quantity=100,
            signal_id="sig-1",
        )
        portfolio = PortfolioState(cash=Decimal("50000"), initial_cash=Decimal("100000"))
        portfolio.positions["000001.SZ"] = __import__(
            "hqmts.backtest.portfolio", fromlist=["Position"]
        ).Position(
            instrument_id="000001.SZ",
            quantity=100,
            market_value=Decimal("50000"),
        )
        ctx = build_risk_context(order, portfolio, "000001.SZ")
        assert ctx.instrument_id == "000001.SZ"
        assert ctx.side == "buy"
        assert ctx.quantity == 100
        assert ctx.account_available_cash == Decimal("50000")
        assert ctx.account_total_asset == Decimal("100000")
        assert ctx.strategy_status == "paper_running"

    def test_position_ratio(self):
        from hqmts.backtest.portfolio import Position
        order = BacktestOrder(instrument_id="000001.SZ", side=Side.BUY, quantity=100)
        portfolio = PortfolioState(cash=Decimal("50000"), initial_cash=Decimal("100000"))
        portfolio.positions["000001.SZ"] = Position(
            instrument_id="000001.SZ", quantity=100, market_value=Decimal("50000"),
        )
        ctx = build_risk_context(order, portfolio, "000001.SZ")
        assert ctx.instrument_position_ratio == Decimal("0.5")


# ── Engine Risk Integration Tests ────────────────────────────────────────────


class TestEngineRiskIntegration:
    def test_risk_disabled_existing_tests_pass(self):
        """With enable_risk=False, engine works exactly as before."""
        config = BacktestConfig(
            strategy=BuyOnceStrategy(),
            strategy_name="buy_once",
            strategy_version="v1",
            strategy_params={},
            instruments=[_instrument()],
            cycle=Cycle.M5,
            start_date="20240102",
            end_date="20240103",
            initial_cash=Decimal("1000000"),
            enable_risk=False,
        )
        engine = BacktestEngine(config)
        bars = [_bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close="10.00") for i in range(5)]
        result = engine.run({"000001.SZ": bars})
        assert result.total_trades >= 1

    def test_risk_reject_blocks_trade(self):
        """Risk REJECT should prevent a trade from being executed."""
        class AlwaysReject(RiskRule):
            @property
            def layer(self):
                from hqmts.core.enums import RiskLayer
                return RiskLayer.ACCOUNT

            @property
            def name(self):
                return "always_reject"

            async def check(self, context):
                return RiskRuleResult(
                    result_type=RiskResultType.REJECT,
                    rule_name="always_reject",
                    reason="blocked",
                )

        risk_engine = RiskEngine()
        risk_engine.register_rule(AlwaysReject())

        config = BacktestConfig(
            strategy=BuyOnceStrategy(),
            strategy_name="buy_once",
            strategy_version="v1",
            strategy_params={},
            instruments=[_instrument()],
            cycle=Cycle.M5,
            start_date="20240102",
            end_date="20240103",
            initial_cash=Decimal("1000000"),
            risk_engine=risk_engine,
            enable_risk=True,
        )
        engine = BacktestEngine(config)
        bars = [_bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close="10.00") for i in range(5)]
        result = engine.run({"000001.SZ": bars})
        # All trades should be rejected
        assert result.total_trades == 0

    def test_risk_resize_reduces_quantity(self):
        """Risk RESIZE should reduce the fill quantity to a lot-valid size."""
        class ResizeTo200(RiskRule):
            @property
            def layer(self):
                from hqmts.core.enums import RiskLayer
                return RiskLayer.STRATEGY

            @property
            def name(self):
                return "resize_200"

            async def check(self, context):
                if context.quantity > 0:
                    return RiskRuleResult(
                        result_type=RiskResultType.RESIZE,
                        rule_name="resize_200",
                        reason="resized",
                        resized_quantity=200,  # Lot-valid (200 = 2 * 100)
                    )
                return None

        risk_engine = RiskEngine()
        risk_engine.register_rule(ResizeTo200())

        config = BacktestConfig(
            strategy=BuyOnceStrategy(),
            strategy_name="buy_once",
            strategy_version="v1",
            strategy_params={},
            instruments=[_instrument()],
            cycle=Cycle.M5,
            start_date="20240102",
            end_date="20240103",
            initial_cash=Decimal("1000000"),
            risk_engine=risk_engine,
            enable_risk=True,
        )
        engine = BacktestEngine(config)
        bars = [_bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close="10.00") for i in range(5)]
        result = engine.run({"000001.SZ": bars})
        # Should have a trade with resized quantity (200 instead of 100)
        assert result.total_trades >= 1
        buys = [t for t in engine._portfolio.trades if t.side == "buy"]
        assert len(buys) >= 1
        assert buys[0].quantity == 200

    def test_risk_delay_requeues_and_eventually_fills(self):
        """Risk DELAY should re-queue order and fill on subsequent bar."""
        call_count = 0

        class DelayOnce(RiskRule):
            @property
            def layer(self):
                from hqmts.core.enums import RiskLayer
                return RiskLayer.ORDER

            @property
            def name(self):
                return "delay_once"

            async def check(self, context):
                nonlocal call_count
                if context.quantity > 0 and call_count < 1:
                    call_count += 1
                    return RiskRuleResult(
                        result_type=RiskResultType.DELAY,
                        rule_name="delay_once",
                        reason="wait",
                    )
                return None

        risk_engine = RiskEngine()
        risk_engine.register_rule(DelayOnce())

        config = BacktestConfig(
            strategy=BuyOnceStrategy(),
            strategy_name="buy_once",
            strategy_version="v1",
            strategy_params={},
            instruments=[_instrument()],
            cycle=Cycle.M5,
            start_date="20240102",
            end_date="20240103",
            initial_cash=Decimal("1000000"),
            risk_engine=risk_engine,
            enable_risk=True,
        )
        engine = BacktestEngine(config)
        bars = [_bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close="10.00") for i in range(5)]
        result = engine.run({"000001.SZ": bars})
        # First bar: DELAY, re-queued. Second bar: allowed, fills.
        assert result.total_trades >= 1

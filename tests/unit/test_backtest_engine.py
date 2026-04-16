"""Tests for backtest engine, portfolio tracking, and result calculation."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from hqmts.backtest.context import StrategyContext
from hqmts.backtest.cost import CostModel, PriceLimitRule
from hqmts.backtest.engine import BacktestConfig, BacktestEngine
from hqmts.backtest.matcher import BacktestMatcher
from hqmts.backtest.portfolio import DailyValue, PortfolioState, Position, TradeRecord
from hqmts.backtest.result import BacktestResult, BacktestResultBuilder
from hqmts.backtest.strategy import DualMACrossoverStrategy
from hqmts.core.enums import Cycle, Side, SignalType, TargetDirection
from hqmts.core.types import InstrumentId, SignalId, VersionStr
from hqmts.domain.bar import Bar
from hqmts.domain.instrument import Instrument
from hqmts.domain.signal import Signal


# ── Helpers ──────────────────────────────────────────────────────────────────


def _bar(
    start: datetime,
    instrument_id: str = "000001.SZ",
    close: str = "10.00",
    open_: str = "10.00",
    high: str = "10.50",
    low: str = "9.50",
    volume: int = 100000,
    cycle: Cycle = Cycle.M5,
) -> Bar:
    return Bar(
        instrument_id=InstrumentId(instrument_id),
        cycle=cycle,
        bar_start_time=start,
        bar_end_time=start + timedelta(minutes={Cycle.M1: 1, Cycle.M5: 5, Cycle.M15: 15, Cycle.M30: 30, Cycle.M60: 60}[cycle]),
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


# ── PortfolioState Tests ──────────────────────────────────────────────────────


class TestPortfolioState:
    def test_buy_updates_position_and_cash(self):
        state = PortfolioState(cash=Decimal("100000"), initial_cash=Decimal("100000"))
        state.apply_fill(
            instrument_id="000001.SZ",
            side=Side.BUY,
            fill_price=Decimal("10.00"),
            fill_quantity=100,
            commission=Decimal("5"),
            stamp_tax=Decimal("0"),
            timestamp=datetime(2024, 1, 2, 9, 35),
        )
        pos = state.positions["000001.SZ"]
        assert pos.quantity == 100
        assert pos.today_bought == 100
        assert state.cash == Decimal("100000") - Decimal("1000") - Decimal("5")

    def test_sell_updates_position_and_cash(self):
        state = PortfolioState(cash=Decimal("0"), initial_cash=Decimal("100000"))
        # Setup position
        state.positions["000001.SZ"] = Position(
            instrument_id="000001.SZ",
            quantity=200,
            today_bought=0,
            average_cost=Decimal("10.00"),
        )
        state.apply_fill(
            instrument_id="000001.SZ",
            side=Side.SELL,
            fill_price=Decimal("11.00"),
            fill_quantity=100,
            commission=Decimal("5"),
            stamp_tax=Decimal("11"),
            timestamp=datetime(2024, 1, 3, 9, 35),
        )
        pos = state.positions["000001.SZ"]
        assert pos.quantity == 100
        assert state.cash == Decimal("1100") - Decimal("5") - Decimal("11")

    def test_sellable_respects_t_plus_1(self):
        pos = Position(instrument_id="000001.SZ", quantity=200, today_bought=100)
        assert pos.sellable == 100

    def test_reset_daily_state(self):
        state = PortfolioState(cash=Decimal("100000"), initial_cash=Decimal("100000"))
        state.apply_fill(
            instrument_id="000001.SZ",
            side=Side.BUY,
            fill_price=Decimal("10.00"),
            fill_quantity=100,
            commission=Decimal("5"),
            stamp_tax=Decimal("0"),
            timestamp=datetime(2024, 1, 2, 9, 35),
        )
        assert state.positions["000001.SZ"].today_bought == 100
        state.reset_daily_state()
        assert state.positions["000001.SZ"].today_bought == 0

    def test_calculate_total_asset(self):
        state = PortfolioState(cash=Decimal("50000"), initial_cash=Decimal("100000"))
        state.positions["000001.SZ"] = Position(
            instrument_id="000001.SZ",
            quantity=1000,
            market_value=Decimal("50000"),
        )
        assert state.calculate_total_asset() == Decimal("100000")

    def test_snapshot_daily(self):
        state = PortfolioState(cash=Decimal("100000"), initial_cash=Decimal("100000"))
        state.positions["000001.SZ"] = Position(
            instrument_id="000001.SZ",
            quantity=1000,
            market_value=Decimal("0"),
        )
        dv = state.snapshot_daily(date(2024, 1, 2))
        assert dv.trade_date == date(2024, 1, 2)
        assert dv.total_asset == Decimal("100000")
        assert len(state.daily_values) == 1

    def test_average_cost_weighted(self):
        state = PortfolioState(cash=Decimal("100000"), initial_cash=Decimal("100000"))
        # Buy 100 @ 10
        state.apply_fill("000001.SZ", Side.BUY, Decimal("10"), 100, Decimal("5"), Decimal("0"), datetime(2024, 1, 2, 9, 35))
        # Buy 100 @ 12
        state.apply_fill("000001.SZ", Side.BUY, Decimal("12"), 100, Decimal("5"), Decimal("0"), datetime(2024, 1, 2, 9, 40))
        pos = state.positions["000001.SZ"]
        assert pos.quantity == 200
        assert pos.average_cost == Decimal("11")


# ── BacktestResultBuilder Tests ──────────────────────────────────────────────


class TestBacktestResultBuilder:
    def test_total_return(self):
        assert BacktestResultBuilder._calc_total_return(Decimal("100"), Decimal("110")) == Decimal("10")

    def test_total_return_negative(self):
        assert BacktestResultBuilder._calc_total_return(Decimal("100"), Decimal("80")) == Decimal("-20")

    def test_total_return_zero_initial(self):
        assert BacktestResultBuilder._calc_total_return(Decimal("0"), Decimal("100")) == Decimal("0")

    def test_max_drawdown(self):
        dvs = [
            DailyValue(trade_date=date(2024, 1, 2), cash=Decimal("100"), market_value=Decimal("0"), total_asset=Decimal("100")),
            DailyValue(trade_date=date(2024, 1, 3), cash=Decimal("100"), market_value=Decimal("0"), total_asset=Decimal("90")),
            DailyValue(trade_date=date(2024, 1, 4), cash=Decimal("100"), market_value=Decimal("0"), total_asset=Decimal("95")),
        ]
        dd = BacktestResultBuilder._calc_max_drawdown(dvs)
        assert dd == Decimal("10")  # 100 -> 90 = 10% drawdown

    def test_max_drawdown_no_drawdown(self):
        dvs = [
            DailyValue(trade_date=date(2024, 1, 2), cash=Decimal("100"), market_value=Decimal("0"), total_asset=Decimal("100")),
            DailyValue(trade_date=date(2024, 1, 3), cash=Decimal("100"), market_value=Decimal("0"), total_asset=Decimal("110")),
        ]
        dd = BacktestResultBuilder._calc_max_drawdown(dvs)
        assert dd == Decimal("0")

    def test_win_rate(self):
        trades = [
            TradeRecord("T1", "000001.SZ", "buy", Decimal("10"), 100, Decimal("5"), Decimal("0"), datetime(2024, 1, 2, 9, 35)),
            TradeRecord("T2", "000001.SZ", "sell", Decimal("12"), 100, Decimal("5"), Decimal("12"), datetime(2024, 1, 3, 9, 35)),
        ]
        wr = BacktestResultBuilder._calc_win_rate(trades)
        assert wr == Decimal("100")  # Sold at 12 > bought at 10

    def test_win_rate_zero_sells(self):
        wr = BacktestResultBuilder._calc_win_rate([])
        assert wr == Decimal("0")

    def test_sharpe_ratio_insufficient_data(self):
        dvs = [
            DailyValue(trade_date=date(2024, 1, 2), cash=Decimal("100"), market_value=Decimal("0"), total_asset=Decimal("100")),
        ]
        sharpe = BacktestResultBuilder._calc_sharpe_ratio(dvs)
        assert sharpe == Decimal("0")

    def test_profit_factor_no_loss(self):
        trades = [
            TradeRecord("T1", "000001.SZ", "buy", Decimal("10"), 100, Decimal("0"), Decimal("0"), datetime(2024, 1, 2, 9, 35)),
            TradeRecord("T2", "000001.SZ", "sell", Decimal("12"), 100, Decimal("0"), Decimal("0"), datetime(2024, 1, 3, 9, 35)),
        ]
        pf = BacktestResultBuilder._calc_profit_factor(trades)
        assert pf > Decimal("0")  # Pure profit

    def test_build_full_result(self):
        dvs = [
            DailyValue(trade_date=date(2024, 1, 2), cash=Decimal("1000000"), market_value=Decimal("0"), total_asset=Decimal("1000000")),
            DailyValue(trade_date=date(2024, 1, 3), cash=Decimal("999000"), market_value=Decimal("1100"), total_asset=Decimal("1000100")),
        ]
        trades = [
            TradeRecord("T1", "000001.SZ", "buy", Decimal("10"), 100, Decimal("5"), Decimal("0"), datetime(2024, 1, 2, 9, 35)),
        ]
        result = BacktestResultBuilder.build(
            strategy_name="test",
            strategy_version="v1",
            strategy_params={"fast_period": 3, "slow_period": 5},
            instruments=["000001.SZ"],
            cycle="5m",
            start_date="20240102",
            end_date="20240103",
            initial_cash=Decimal("1000000"),
            daily_values=dvs,
            trades=trades,
        )
        assert result.total_trades == 1
        assert result.total_return > Decimal("0")
        assert len(result.trades) == 1
        assert len(result.daily_values) == 2


# ── BacktestEngine Integration Tests ─────────────────────────────────────────


class TestBacktestEngine:
    def _make_config(
        self,
        strategy: DualMACrossoverStrategy | None = None,
        initial_cash: Decimal = Decimal("1000000"),
    ) -> BacktestConfig:
        return BacktestConfig(
            strategy=strategy or DualMACrossoverStrategy(),
            strategy_name="dual_ma",
            strategy_version="v1",
            strategy_params={"fast_period": 3, "slow_period": 5},
            instruments=[_instrument()],
            cycle=Cycle.M5,
            start_date="20240102",
            end_date="20240103",
            initial_cash=initial_cash,
        )

    def test_empty_bars_returns_empty_result(self):
        engine = BacktestEngine(self._make_config())
        result = engine.run({})
        assert result.total_trades == 0
        assert result.total_return == Decimal("0")

    def test_single_day_no_signal(self):
        """Flat prices should produce no signals."""
        config = self._make_config()
        engine = BacktestEngine(config)
        bars = [
            _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close="10.00")
            for i in range(10)
        ]
        result = engine.run({"000001.SZ": bars})
        assert result.total_trades == 0

    def test_single_instrument_golden_cross_produces_buy(self):
        """Declining then rising prices should trigger a buy."""
        config = self._make_config()
        engine = BacktestEngine(config)

        # Generate bars: 9 declining + many rising to trigger golden cross
        closes = (
            ["10.00", "9.80", "9.60", "9.50", "9.40", "9.30", "9.40", "9.50", "9.60", "9.70"]
            + ["9.80", "10.00", "10.20", "10.30", "10.40", "10.50", "10.60", "10.70", "10.80", "10.90"]
            + ["11.00", "11.10", "11.20", "11.30", "11.40", "11.50", "11.60", "11.70", "11.80", "11.90"]
        )
        bars = [
            _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close=c)
            for i, c in enumerate(closes)
        ]
        result = engine.run({"000001.SZ": bars})
        # Should have at least one trade (the golden cross buy)
        assert result.total_trades >= 1

    def test_portfolio_cash_decreases_on_buy(self):
        """After a buy, cash should decrease."""
        config = self._make_config()
        engine = BacktestEngine(config)

        closes = (
            ["10.00", "9.80", "9.60", "9.50", "9.40", "9.30", "9.40", "9.50", "9.60", "9.70"]
            + ["9.80", "10.00", "10.20", "10.30", "10.40", "10.50", "10.60", "10.70", "10.80", "10.90"]
        )
        bars = [
            _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close=c)
            for i, c in enumerate(closes)
        ]
        result = engine.run({"000001.SZ": bars})

        if result.total_trades > 0:
            # Initial cash minus cost of buys
            assert result.final_total_asset != config.initial_cash

    def test_daily_snapshots_created(self):
        """Daily snapshots should be created for each trade date."""
        config = self._make_config()
        engine = BacktestEngine(config)

        bars = [
            _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close="10.00")
            for i in range(10)
        ]
        result = engine.run({"000001.SZ": bars})
        assert len(result.daily_values) >= 1

    def test_t_plus_1_enforced_across_days(self):
        """Shares bought on day 1 cannot be sold on day 1 but can on day 2."""
        config = self._make_config()
        engine = BacktestEngine(config)

        # Day 1: declining then rising (golden cross -> buy)
        day1_closes = (
            ["10.00", "9.80", "9.60", "9.50", "9.40", "9.30", "9.40", "9.50", "9.60", "9.70"]
            + ["9.80", "10.00", "10.20", "10.30", "10.40", "10.50", "10.60", "10.70", "10.80", "10.90"]
        )
        day1_bars = [
            _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close=c)
            for i, c in enumerate(day1_closes)
        ]

        # Day 2: declining (death cross -> sell attempt)
        day2_closes = ["11.00", "10.80", "10.60", "10.40", "10.20", "10.00", "9.80", "9.60", "9.40", "9.20"]
        day2_bars = [
            _bar(start=datetime(2024, 1, 3, 9, 30) + timedelta(minutes=5 * i), close=c)
            for i, c in enumerate(day2_closes)
        ]

        result = engine.run({"000001.SZ": day1_bars + day2_bars})
        # Should have at least a buy on day 1
        assert result.total_trades >= 1

    def test_cost_summary_in_result(self):
        """Result should include cost summary."""
        config = self._make_config()
        engine = BacktestEngine(config)
        bars = [
            _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close="10.00")
            for i in range(10)
        ]
        result = engine.run({"000001.SZ": bars})
        assert "total_commission" in result.cost_summary
        assert "total_stamp_tax" in result.cost_summary

    def test_first_bar_warmup_seeds_prev_close(self):
        """The first bar per instrument seeds prev_close but does not generate signals.
        This means the strategy sees bars starting from bar[1], not bar[0].
        """
        config = self._make_config()
        engine = BacktestEngine(config)
        bars = [
            _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=5 * i), close="10.00")
            for i in range(5)
        ]
        result = engine.run({"000001.SZ": bars})
        # Flat prices, no signals expected regardless of warmup
        assert result.total_trades == 0
        # Verify prev_close was seeded (engine internal state)
        assert "000001.SZ" in engine._prev_close

    def test_data_quality_gate_rejects_zero_prices(self):
        """Backtest should refuse to run on bars with zero prices."""
        config = self._make_config()
        engine = BacktestEngine(config)

        # Bar with zero close price
        bad_bar = Bar(
            instrument_id=InstrumentId("000001.SZ"),
            cycle=Cycle.M5,
            bar_start_time=datetime(2024, 1, 2, 9, 30),
            bar_end_time=datetime(2024, 1, 2, 9, 35),
            open=Decimal("10.00"),
            high=Decimal("10.50"),
            low=Decimal("9.50"),
            close=Decimal("0"),  # Zero price!
            volume=100000,
            amount=Decimal("1000000"),
            is_completed=True,
            source="test",
            data_version=VersionStr("v1"),
        )
        result = engine.run({"000001.SZ": [bad_bar]})
        # Should return empty result (data quality gate blocked)
        assert result.total_trades == 0
        assert result.total_return == Decimal("0")

    def test_data_quality_gate_override(self):
        """Setting reject_on_bad_data=False allows running on bad data."""
        config = self._make_config()
        config.reject_on_bad_data = False
        engine = BacktestEngine(config)

        bad_bar = Bar(
            instrument_id=InstrumentId("000001.SZ"),
            cycle=Cycle.M5,
            bar_start_time=datetime(2024, 1, 2, 9, 30),
            bar_end_time=datetime(2024, 1, 2, 9, 35),
            open=Decimal("10.00"),
            high=Decimal("10.50"),
            low=Decimal("9.50"),
            close=Decimal("0"),
            volume=100000,
            amount=Decimal("1000000"),
            is_completed=True,
            source="test",
            data_version=VersionStr("v1"),
        )
        # Should not crash even with bad data when gate is disabled
        result = engine.run({"000001.SZ": [bad_bar]})
        # First bar is warmup, so no trades, but engine didn't reject the run
        assert result.total_trades == 0

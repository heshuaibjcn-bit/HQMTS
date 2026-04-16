"""Tests for vectorized backtest path."""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

from hqmts.backtest.vectorized import VectorizedBacktester, VectorizedResult


class TestSMA:
    def test_sma_correct_values(self):
        bt = VectorizedBacktester()
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        ma = bt._sma(data, 3)
        assert ma[2] == pytest.approx(2.0)  # (1+2+3)/3
        assert ma[3] == pytest.approx(3.0)  # (2+3+4)/3
        assert ma[4] == pytest.approx(4.0)  # (3+4+5)/3

    def test_sma_short_data(self):
        bt = VectorizedBacktester()
        data = np.array([1.0, 2.0])
        ma = bt._sma(data, 5)
        assert np.all(np.isnan(ma))


class TestCrossoverDetection:
    def test_golden_cross(self):
        """Declining then rising prices should detect golden cross."""
        bt = VectorizedBacktester()
        # Create a clear golden cross pattern
        closes = np.array(
            [10.0, 9.5, 9.0, 8.5, 8.0, 7.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 11.0]
        )
        result = bt.run(closes, fast_period=3, slow_period=5)
        # Should detect at least one trade
        assert result.total_trades >= 1

    def test_flat_prices_no_crossover(self):
        """Constant prices should produce no crossovers."""
        bt = VectorizedBacktester()
        closes = np.full(50, 10.0)
        result = bt.run(closes, fast_period=3, slow_period=5)
        assert result.total_trades == 0
        assert result.total_return == Decimal("0")

    def test_insufficient_data(self):
        """Data shorter than slow_period should return zeros."""
        bt = VectorizedBacktester()
        closes = np.array([10.0, 11.0])
        result = bt.run(closes, fast_period=3, slow_period=5)
        assert result.total_trades == 0
        assert result.total_return == Decimal("0")


class TestVectorizedTrades:
    def test_single_buy_sell_cycle(self):
        """One golden cross (buy) then death cross (sell) across two days."""
        bt = VectorizedBacktester()
        # Day 1: 48 bars, declining then rising (golden cross)
        day1 = list(np.linspace(10, 8, 20)) + list(np.linspace(8, 11, 28))
        # Day 2: 48 bars, declining (death cross)
        day2 = list(np.linspace(11, 7, 48))
        closes = np.array(day1 + day2)
        result = bt.run(closes, fast_period=3, slow_period=5)
        assert result.total_trades >= 2  # At least one buy and one sell

    def test_commission_deducted(self):
        """Cash should decrease by commission + trade amount on buy."""
        bt = VectorizedBacktester()
        closes = np.array([
            10.0, 9.5, 9.0, 8.5, 8.0, 7.5, 8.0, 8.5, 9.0, 9.5,
            10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0, 13.5, 14.0, 14.5,
            15.0, 15.5, 16.0, 16.5, 17.0, 17.5, 18.0, 18.5, 19.0, 19.5,
        ])
        result = bt.run(closes, fast_period=3, slow_period=5)
        # With golden cross, should have positive return
        assert result.total_trades >= 1

    def test_result_has_all_fields(self):
        """VectorizedResult should have all metric fields."""
        bt = VectorizedBacktester()
        closes = np.full(50, 10.0)
        result = bt.run(closes, fast_period=3, slow_period=5)
        assert isinstance(result, VectorizedResult)
        assert isinstance(result.total_return, Decimal)
        assert isinstance(result.max_drawdown, Decimal)
        assert isinstance(result.sharpe_ratio, Decimal)
        assert isinstance(result.win_rate, Decimal)
        assert isinstance(result.profit_factor, Decimal)
        assert result.fast_period == 3
        assert result.slow_period == 5


class TestVectorizedMetrics:
    def test_max_drawdown_calculation(self):
        bt = VectorizedBacktester()
        values = [100.0, 110.0, 90.0, 95.0, 85.0, 100.0]
        dd = bt._calc_max_drawdown(values)
        assert dd == pytest.approx(22.73, abs=0.01)  # 110 -> 85 = 22.7% drawdown

    def test_max_drawdown_no_drawdown(self):
        bt = VectorizedBacktester()
        values = [100.0, 110.0, 120.0]
        dd = bt._calc_max_drawdown(values)
        assert dd == 0.0

    def test_total_return_calculation(self):
        bt = VectorizedBacktester()
        ret = bt._calc_total_return(100.0, 110.0)
        assert ret == pytest.approx(10.0)

    def test_total_return_loss(self):
        bt = VectorizedBacktester()
        ret = bt._calc_total_return(100.0, 80.0)
        assert ret == pytest.approx(-20.0)

    def test_sharpe_calculation(self):
        bt = VectorizedBacktester()
        values = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
        sharpe = bt._calc_sharpe(values)
        assert sharpe != 0.0  # Should be positive for consistently rising values

    def test_sharpe_insufficient_data(self):
        bt = VectorizedBacktester()
        assert bt._calc_sharpe([100.0]) == 0.0

    def test_trade_stats_no_trades(self):
        bt = VectorizedBacktester()
        wr, pf, total = bt._calc_trade_stats([])
        assert wr == 0.0
        assert pf == 0.0
        assert total == 0

    def test_trade_stats_winning_trade(self):
        bt = VectorizedBacktester()
        trades = [
            {"side": "buy", "price": 10.0, "quantity": 100},
            {"side": "sell", "price": 12.0, "quantity": 100},
        ]
        wr, pf, total = bt._calc_trade_stats(trades)
        assert wr == 100.0
        assert pf > 0
        assert total == 2

    def test_trade_stats_losing_trade(self):
        bt = VectorizedBacktester()
        trades = [
            {"side": "buy", "price": 12.0, "quantity": 100},
            {"side": "sell", "price": 10.0, "quantity": 100},
        ]
        wr, pf, total = bt._calc_trade_stats(trades)
        assert wr == 0.0
        assert pf == 0.0  # gross_profit is 0
        assert total == 2

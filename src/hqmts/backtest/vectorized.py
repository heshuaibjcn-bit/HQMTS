"""Vectorized backtest path using numpy for fast parameter sweeps."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import numpy as np


@dataclass(frozen=True)
class VectorizedResult:
    """Metrics from a vectorized backtest run (subset of BacktestResult)."""

    fast_period: int
    slow_period: int
    total_return: Decimal  # percentage
    max_drawdown: Decimal  # percentage
    sharpe_ratio: Decimal
    total_trades: int
    win_rate: Decimal  # percentage
    profit_factor: Decimal


class VectorizedBacktester:
    """Fast backtest path using numpy for parameter sweeps.

    Restrictions (vs full BacktestEngine):
    - Market orders only (no SL/TP, no limit orders)
    - No risk engine integration
    - Single instrument at a time
    - Fixed lot_size=100, fixed commission rates
    - T+1 enforced per-trade

    Use case: sweep 50+ parameter combos quickly, then validate top-N with full engine.
    """

    def run(
        self,
        closes: np.ndarray,
        fast_period: int,
        slow_period: int,
        initial_cash: Decimal = Decimal("1000000"),
        commission_rate: Decimal = Decimal("0.0003"),
        commission_min: Decimal = Decimal("5"),
        stamp_tax_rate: Decimal = Decimal("0.001"),
        lot_size: int = 100,
        cycle_minutes: int = 5,
    ) -> VectorizedResult:
        """Run a vectorized dual MA crossover backtest.

        Args:
            closes: Array of closing prices (shape N,).
            fast_period: Fast moving average period.
            slow_period: Slow moving average period.
            initial_cash: Starting cash.
            commission_rate: Commission rate (fraction of trade amount).
            commission_min: Minimum commission per trade.
            stamp_tax_rate: Stamp tax rate on sells.
            lot_size: Share lot size (100 for A-shares).
            cycle_minutes: Bar cycle in minutes (1, 5, 15, 30, 60). Default 5.

        Returns:
            VectorizedResult with calculated metrics.
        """
        n = len(closes)
        if n < slow_period + 1:
            return VectorizedResult(
                fast_period=fast_period,
                slow_period=slow_period,
                total_return=Decimal("0"),
                max_drawdown=Decimal("0"),
                sharpe_ratio=Decimal("0"),
                total_trades=0,
                win_rate=Decimal("0"),
                profit_factor=Decimal("0"),
            )

        # Compute moving averages using convolution
        fast_ma = self._sma(closes, fast_period)
        slow_ma = self._sma(closes, slow_period)

        # Detect crossovers
        # diff[i] > 0 means fast crossed above slow at bar i (golden cross)
        # diff[i] < 0 means fast crossed below slow at bar i (death cross)
        diff = np.zeros(n)
        valid_start = slow_period - 1
        diff[valid_start:] = np.sign(fast_ma[valid_start:] - slow_ma[valid_start:])
        crossover = np.diff(diff, prepend=0)

        golden_crosses = set(np.where(crossover > 0)[0].tolist())
        death_crosses = set(np.where(crossover < 0)[0].tolist())

        # Simulate trades
        cash = float(initial_cash)
        position = 0
        cost_basis = 0.0  # average cost per share
        today_bought = 0
        current_bar_date_idx = 0  # Track day boundaries for T+1

        trades: list[dict] = []  # {"side": "buy"/"sell", "price": float, "quantity": int}
        portfolio_values: list[float] = []

        # Day boundary: 240 trading minutes per day, divided by cycle length
        bars_per_day = 240 // cycle_minutes

        for i in range(n):
            # Day boundary check for T+1 reset
            day_idx = i // bars_per_day
            if day_idx > current_bar_date_idx:
                today_bought = 0
                current_bar_date_idx = day_idx

            price = float(closes[i])
            portfolio_value = cash + position * price
            portfolio_values.append(portfolio_value)

            # Process golden cross -> buy
            if i in golden_crosses and position == 0:
                max_shares = int(cash / price) if price > 0 else 0
                max_shares = min(max_shares, lot_size * 10)  # Cap position
                shares = (max_shares // lot_size) * lot_size
                if shares > 0:
                    trade_amount = shares * price
                    commission = max(trade_amount * float(commission_rate), float(commission_min))
                    cash -= trade_amount + commission
                    position = shares
                    cost_basis = price
                    today_bought = shares
                    trades.append({"side": "buy", "price": price, "quantity": shares})

            # Process death cross -> sell (if holding and T+1 allows)
            elif i in death_crosses and position > 0:
                sellable = position - today_bought
                if sellable > 0:
                    shares = (sellable // lot_size) * lot_size
                    if shares > 0:
                        trade_amount = shares * price
                        commission = max(trade_amount * float(commission_rate), float(commission_min))
                        stamp_tax = trade_amount * float(stamp_tax_rate)
                        cash += trade_amount - commission - stamp_tax
                        trades.append({"side": "sell", "price": price, "quantity": shares})
                        position -= shares

        # Final portfolio value
        final_value = cash + position * float(closes[-1])

        # Calculate metrics
        total_return = self._calc_total_return(float(initial_cash), final_value)
        max_drawdown = self._calc_max_drawdown(portfolio_values)
        sharpe = self._calc_sharpe(portfolio_values, bars_per_day)
        win_rate, profit_factor, total_trades_count = self._calc_trade_stats(trades)

        return VectorizedResult(
            fast_period=fast_period,
            slow_period=slow_period,
            total_return=Decimal(str(round(total_return, 4))),
            max_drawdown=Decimal(str(round(max_drawdown, 4))),
            sharpe_ratio=Decimal(str(round(sharpe, 4))),
            total_trades=total_trades_count,
            win_rate=Decimal(str(round(win_rate, 4))),
            profit_factor=Decimal(str(round(profit_factor, 4))),
        )

    @staticmethod
    def _sma(data: np.ndarray, period: int) -> np.ndarray:
        """Simple moving average."""
        if len(data) < period:
            return np.full_like(data, np.nan, dtype=float)
        kernel = np.ones(period) / period
        ma = np.convolve(data, kernel, mode="full")[:len(data)]
        ma[:period - 1] = np.nan
        return ma

    @staticmethod
    def _calc_total_return(initial: float, final: float) -> float:
        if initial == 0:
            return 0.0
        return (final - initial) / initial * 100

    @staticmethod
    def _calc_max_drawdown(portfolio_values: list[float]) -> float:
        if not portfolio_values:
            return 0.0
        peak = portfolio_values[0]
        max_dd = 0.0
        for v in portfolio_values:
            if v > peak:
                peak = v
            if peak > 0:
                dd = (peak - v) / peak * 100
                if dd > max_dd:
                    max_dd = dd
        return max_dd

    @staticmethod
    def _calc_sharpe(portfolio_values: list[float], bars_per_day: int = 48) -> float:
        if len(portfolio_values) < 2:
            return 0.0
        returns = np.diff(portfolio_values) / np.array(portfolio_values[:-1])
        returns = returns[np.isfinite(returns)]
        if len(returns) < 2:
            return 0.0
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        if std == 0:
            return 0.0
        # Annualize: assuming bars_per_day bars/day, 252 trading days
        bars_per_year = bars_per_day * 252
        return mean * np.sqrt(bars_per_year) / std

    @staticmethod
    def _calc_trade_stats(trades: list[dict]) -> tuple[float, float, int]:
        """Returns (win_rate, profit_factor, total_trades)."""
        sells = [t for t in trades if t["side"] == "sell"]
        if not sells:
            return 0.0, 0.0, len(trades)

        buys = [t for t in trades if t["side"] == "buy"]
        if not buys:
            return 0.0, 0.0, len(trades)

        # Pair buys with sells
        wins = 0
        gross_profit = 0.0
        gross_loss = 0.0

        buy_queue = list(buys)
        for sell in sells:
            if buy_queue:
                buy = buy_queue.pop(0)
                pnl = (sell["price"] - buy["price"]) * sell["quantity"]
                if pnl > 0:
                    wins += 1
                    gross_profit += pnl
                else:
                    gross_loss += abs(pnl)

        total_trades = len(buys) + len(sells)
        win_rate = wins / len(sells) * 100 if sells else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        return win_rate, profit_factor, total_trades

"""Backtest result model and metrics calculation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Sequence
import uuid

from hqmts.backtest.portfolio import DailyValue, TradeRecord


@dataclass(frozen=True)
class BacktestResult:
    """Complete result of a backtest run."""

    backtest_id: str
    strategy_name: str
    strategy_version: str
    strategy_params: dict[str, Any]
    instruments: list[str]
    cycle: str
    start_date: str
    end_date: str
    initial_cash: Decimal
    final_total_asset: Decimal
    total_return: Decimal  # percentage
    annualized_return: Decimal  # percentage
    max_drawdown: Decimal  # percentage
    sharpe_ratio: Decimal
    total_trades: int
    win_rate: Decimal  # percentage
    profit_factor: Decimal
    trades: list[dict[str, Any]]
    daily_values: list[dict[str, Any]]
    cost_summary: dict[str, Any]
    data_version: str = "v1"
    created_at: datetime | None = None


class BacktestResultBuilder:
    """Calculates all performance metrics from portfolio state."""

    @staticmethod
    def build(
        strategy_name: str,
        strategy_version: str,
        strategy_params: dict[str, Any],
        instruments: list[str],
        cycle: str,
        start_date: str,
        end_date: str,
        initial_cash: Decimal,
        daily_values: Sequence[DailyValue],
        trades: Sequence[TradeRecord],
        data_version: str = "v1",
    ) -> BacktestResult:
        """Build a BacktestResult with all calculated metrics."""
        final_asset = daily_values[-1].total_asset if daily_values else initial_cash

        total_return = BacktestResultBuilder._calc_total_return(initial_cash, final_asset)
        annualized_return = BacktestResultBuilder._calc_annualized_return(
            total_return, start_date, end_date
        )
        max_drawdown = BacktestResultBuilder._calc_max_drawdown(daily_values)
        sharpe = BacktestResultBuilder._calc_sharpe_ratio(daily_values)
        win_rate = BacktestResultBuilder._calc_win_rate(trades)
        profit_factor = BacktestResultBuilder._calc_profit_factor(trades)

        total_commission = sum(t.commission for t in trades)
        total_stamp_tax = sum(t.stamp_tax for t in trades)
        buy_trades = [t for t in trades if t.side == "buy"]
        sell_trades = [t for t in trades if t.side == "sell"]

        return BacktestResult(
            backtest_id=str(uuid.uuid4()),
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            strategy_params=strategy_params,
            instruments=instruments,
            cycle=cycle,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            final_total_asset=final_asset,
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            total_trades=len(trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            trades=[BacktestResultBuilder._trade_to_dict(t) for t in trades],
            daily_values=[BacktestResultBuilder._daily_to_dict(d) for d in daily_values],
            cost_summary={
                "total_commission": str(total_commission),
                "total_stamp_tax": str(total_stamp_tax),
                "buy_count": len(buy_trades),
                "sell_count": len(sell_trades),
            },
            data_version=data_version,
            created_at=datetime.now(),
        )

    @staticmethod
    def _calc_total_return(initial: Decimal, final: Decimal) -> Decimal:
        if initial == 0:
            return Decimal("0")
        return (final - initial) / initial * Decimal("100")

    @staticmethod
    def _calc_annualized_return(total_return: Decimal, start: str, end: str) -> Decimal:
        if not start or not end:
            return Decimal("0")
        s = datetime.strptime(start, "%Y%m%d")
        e = datetime.strptime(end, "%Y%m%d")
        days = (e - s).days
        if days <= 0:
            return Decimal("0")
        years = Decimal(str(days)) / Decimal("365")
        # (1 + r) ^ (1/years) - 1
        r = total_return / Decimal("100")
        if years == 0 or (Decimal("1") + r) <= 0:
            return Decimal("0")
        # Simple approximation for annualized return
        try:
            ann = ((Decimal("1") + r) ** (Decimal("1") / years) - Decimal("1")) * Decimal("100")
            return ann.quantize(Decimal("0.01"))
        except Exception:
            return total_return  # Fallback to total return

    @staticmethod
    def _calc_max_drawdown(daily_values: Sequence[DailyValue]) -> Decimal:
        if not daily_values:
            return Decimal("0")
        peak = daily_values[0].total_asset
        max_dd = Decimal("0")
        for dv in daily_values:
            if dv.total_asset > peak:
                peak = dv.total_asset
            if peak > 0:
                dd = (peak - dv.total_asset) / peak * Decimal("100")
                if dd > max_dd:
                    max_dd = dd
        return max_dd

    @staticmethod
    def _calc_sharpe_ratio(daily_values: Sequence[DailyValue]) -> Decimal:
        """Annualized Sharpe ratio (risk-free rate = 0)."""
        if len(daily_values) < 2:
            return Decimal("0")

        returns: list[Decimal] = []
        for i in range(1, len(daily_values)):
            prev = daily_values[i - 1].total_asset
            curr = daily_values[i].total_asset
            if prev > 0:
                returns.append((curr - prev) / prev)

        if not returns:
            return Decimal("0")

        n = Decimal(len(returns))
        mean = sum(returns) / n
        if n <= 1:
            return Decimal("0")

        variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
        std = variance.sqrt() if variance > 0 else Decimal("0")

        if std == 0:
            return Decimal("0")

        # Annualize: mean * sqrt(252) / std
        sharpe = mean * Decimal("15.874507866387544") / std  # sqrt(252) ≈ 15.87
        return sharpe.quantize(Decimal("0.01"))

    @staticmethod
    def _calc_win_rate(trades: Sequence[TradeRecord]) -> Decimal:
        """Win rate based on sell trades that are profitable.

        Tracks buys per-instrument to avoid conflation across instruments.
        """
        sells = [t for t in trades if t.side == "sell"]
        if not sells:
            return Decimal("0")

        buy_queues: dict[str, list[TradeRecord]] = {}
        wins = 0

        for t in trades:
            if t.side == "buy":
                buy_queues.setdefault(t.instrument_id, []).append(t)
            elif t.side == "sell":
                inst_buys = buy_queues.get(t.instrument_id, [])
                if inst_buys:
                    avg_buy = sum(b.price for b in inst_buys) / Decimal(len(inst_buys))
                    if t.price > avg_buy:
                        wins += 1
                    buy_queues[t.instrument_id] = []

        return Decimal(str(wins)) / Decimal(str(len(sells))) * Decimal("100")

    @staticmethod
    def _calc_profit_factor(trades: Sequence[TradeRecord]) -> Decimal:
        """Gross profit / gross loss from sell trades."""
        buys_by_inst: dict[str, list[TradeRecord]] = {}
        gross_profit = Decimal("0")
        gross_loss = Decimal("0")

        for t in trades:
            if t.side == "buy":
                buys_by_inst.setdefault(t.instrument_id, []).append(t)
            elif t.side == "sell":
                inst_buys = buys_by_inst.get(t.instrument_id, [])
                if inst_buys:
                    avg_buy = sum(b.price for b in inst_buys) / Decimal(len(inst_buys))
                    pnl = (t.price - avg_buy) * Decimal(t.quantity) - t.commission - t.stamp_tax
                    if pnl > 0:
                        gross_profit += pnl
                    else:
                        gross_loss += abs(pnl)
                    buys_by_inst[t.instrument_id] = []

        if gross_loss == 0:
            return gross_profit if gross_profit > 0 else Decimal("0")
        return (gross_profit / gross_loss).quantize(Decimal("0.01"))

    @staticmethod
    def _trade_to_dict(t: TradeRecord) -> dict[str, Any]:
        return {
            "trade_id": t.trade_id,
            "instrument_id": t.instrument_id,
            "side": t.side,
            "price": str(t.price),
            "quantity": t.quantity,
            "commission": str(t.commission),
            "stamp_tax": str(t.stamp_tax),
            "timestamp": t.timestamp.isoformat(),
            "signal_id": t.signal_id,
        }

    @staticmethod
    def _daily_to_dict(d: DailyValue) -> dict[str, Any]:
        return {
            "trade_date": d.trade_date.isoformat(),
            "cash": str(d.cash),
            "market_value": str(d.market_value),
            "total_asset": str(d.total_asset),
        }

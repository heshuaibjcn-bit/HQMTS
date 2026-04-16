"""Backtest order matching engine (FR-BT-003)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Sequence

from hqmts.backtest.cost import CostModel, PriceLimitRule
from hqmts.core.enums import Side, SignalType
from hqmts.domain.bar import Bar
from hqmts.domain.instrument import Instrument
from hqmts.domain.signal import Signal


@dataclass
class MatchResult:
    """Result of a match attempt."""

    filled: bool
    fill_price: Decimal = Decimal("0")
    fill_quantity: int = 0
    commission: Decimal = Decimal("0")
    stamp_tax: Decimal = Decimal("0")
    reject_reason: str = ""


class BacktestMatcher:
    """Backtest order matching engine.

    Matching rules (PRD FR-BT-003):
    1. Signal at bar_end_time of cycle bar
    2. Matched at next tradeable bar's open price
    3. Price limit check: reject if bar hits daily limit
    4. Lot rounding: round down to lot_size (100)
    5. Volume cap: fill_quantity <= bar_volume * participation_rate
    6. T+1: cannot sell shares bought today
    7. Insufficient cash -> resize order
    """

    def __init__(
        self,
        cost_model: CostModel,
        price_limit_rule: PriceLimitRule,
        lot_size: int = 100,
        participation_rate: float = 0.25,
    ) -> None:
        self._cost_model = cost_model
        self._price_limit = price_limit_rule
        self._lot_size = lot_size
        self._participation_rate = participation_rate

    def match_order(
        self,
        signal: Signal,
        target_bar: Bar,
        prev_close: Decimal,
        instrument: Instrument,
        current_position: int,
        today_bought: int,
        available_cash: Decimal,
    ) -> MatchResult:
        """Attempt to match a signal against a target bar.

        Steps:
        1. Determine side from signal type
        2. Check T+1 for sells
        3. Determine fill price (open + slippage)
        4. Check price limits
        5. Calculate fill quantity
        6. Calculate costs
        """
        # Step 1: Determine side
        side = self._signal_to_side(signal.signal_type)
        if side is None:
            return MatchResult(filled=False, reject_reason="unsupported_signal_type")

        # Step 2: T+1 check for sells
        if side == Side.SELL:
            sellable = current_position - today_bought
            if sellable <= 0:
                return MatchResult(filled=False, reject_reason="t_plus_1_blocked")

        # Step 3: Fill price
        fill_price = target_bar.open
        if side == Side.BUY:
            fill_price += self._cost_model.slippage
        else:
            fill_price -= self._cost_model.slippage

        # Step 4: Price limit check
        is_st = getattr(instrument, "is_st", False)
        board_type = getattr(instrument, "board_type", "main")
        if not self._price_limit.is_within_limit(fill_price, prev_close, is_st, board_type):
            return MatchResult(filled=False, reject_reason="price_limit_hit")

        # Zero volume bar
        if target_bar.volume <= 0:
            return MatchResult(filled=False, reject_reason="zero_volume")

        # Step 5: Calculate fill quantity
        if side == Side.BUY:
            max_by_cash = int(available_cash / fill_price) if fill_price > 0 else 0
            max_by_volume = int(target_bar.volume * self._participation_rate)
            raw_quantity = min(max_by_cash, max_by_volume)
        else:
            sellable = current_position - today_bought
            max_by_volume = int(target_bar.volume * self._participation_rate)
            raw_quantity = min(sellable, max_by_volume)

        # Round to lot size
        quantity = self._round_to_lot(raw_quantity)

        if quantity <= 0:
            return MatchResult(filled=False, reject_reason="insufficient_funds_or_volume")

        # Step 6: Calculate costs
        trade_amount = fill_price * Decimal(quantity)
        commission = self._cost_model.calculate_commission(trade_amount)
        stamp_tax = self._cost_model.calculate_stamp_tax(trade_amount, side)

        return MatchResult(
            filled=True,
            fill_price=fill_price,
            fill_quantity=quantity,
            commission=commission,
            stamp_tax=stamp_tax,
        )

    def get_next_tradeable_bar(
        self,
        current_bar_end: "datetime",
        bars_1m: Sequence[Bar],
    ) -> Bar | None:
        """Find the next tradeable 1m bar after current_bar_end.

        Handles lunch break and end of day.
        """
        from datetime import datetime

        for bar in bars_1m:
            if bar.bar_start_time > current_bar_end and bar.is_completed:
                return bar
        return None

    def _round_to_lot(self, quantity: int) -> int:
        """Round quantity down to nearest lot_size."""
        return (quantity // self._lot_size) * self._lot_size

    @staticmethod
    def _signal_to_side(signal_type: SignalType) -> Side | None:
        if signal_type in (SignalType.OPEN_LONG, SignalType.CLOSE_SHORT):
            return Side.BUY
        if signal_type in (SignalType.CLOSE_LONG, SignalType.OPEN_SHORT):
            return Side.SELL
        return None

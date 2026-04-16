"""A-share transaction cost model and price limit rules (FR-BT-002)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from hqmts.core.enums import Side


@dataclass(frozen=True)
class CostModel:
    """A-share transaction cost model.

    - Commission: max(amount * rate, min) on both buy and sell
    - Stamp tax: amount * rate on sell only
    - Slippage: per-share price impact
    """

    commission_rate: Decimal = Decimal("0.0003")
    commission_min: Decimal = Decimal("5.0")
    stamp_tax_rate: Decimal = Decimal("0.001")
    slippage: Decimal = Decimal("0")

    def calculate_commission(self, trade_amount: Decimal) -> Decimal:
        return max(trade_amount * self.commission_rate, self.commission_min)

    def calculate_stamp_tax(self, trade_amount: Decimal, side: Side) -> Decimal:
        if side == Side.SELL:
            return trade_amount * self.stamp_tax_rate
        return Decimal("0")

    def calculate_total_cost(self, trade_amount: Decimal, side: Side, quantity: int) -> Decimal:
        commission = self.calculate_commission(trade_amount)
        stamp_tax = self.calculate_stamp_tax(trade_amount, side)
        slip = self.slippage * Decimal(quantity)
        return commission + stamp_tax + slip


@dataclass(frozen=True)
class PriceLimitRule:
    """A-share price limit rule.

    Normal board: +/- 10%
    ST stock: +/- 5%
    Registration board (创业板/科创板): +/- 20%
    """

    normal_limit: Decimal = Decimal("0.10")
    st_limit: Decimal = Decimal("0.05")
    registration_limit: Decimal = Decimal("0.20")

    def get_limit(self, is_st: bool, board_type: str) -> Decimal:
        if is_st:
            return self.st_limit
        if board_type in ("创业板", "科创板", "gem", "star"):
            return self.registration_limit
        return self.normal_limit

    def is_within_limit(
        self,
        price: Decimal,
        prev_close: Decimal,
        is_st: bool,
        board_type: str,
    ) -> bool:
        if prev_close == 0:
            return True
        limit = self.get_limit(is_st, board_type)
        upper = prev_close * (1 + limit)
        lower = prev_close * (1 - limit)
        return lower <= price <= upper

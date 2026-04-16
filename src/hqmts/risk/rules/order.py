"""Order-level risk rules (PRD 19.5, SAD 18)."""

from __future__ import annotations

from decimal import Decimal

from hqmts.core.enums import RiskLayer, RiskResultType
from hqmts.risk.engine import RiskContext, RiskRule, RiskRuleResult


class InvalidPriceCheckRule(RiskRule):
    """Reject orders with invalid prices (negative, zero, or outside limits)."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.ORDER

    @property
    def name(self) -> str:
        return "invalid_price_check"

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.price <= 0:
            return RiskRuleResult(
                result_type=RiskResultType.REJECT,
                rule_name=self.name,
                reason=f"Invalid price: {context.price}",
            )
        return None


class MinLotSizeCheckRule(RiskRule):
    """Ensure order quantity meets minimum lot size (100 shares for A-stock)."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.ORDER

    @property
    def name(self) -> str:
        return "min_lot_size_check"

    def __init__(self, lot_size: int = 100) -> None:
        self._lot_size = lot_size

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.quantity <= 0:
            return RiskRuleResult(
                result_type=RiskResultType.REJECT,
                rule_name=self.name,
                reason=f"Invalid quantity: {context.quantity}",
            )
        if context.quantity % self._lot_size != 0:
            # Resize to nearest valid lot size
            resized = (context.quantity // self._lot_size) * self._lot_size
            if resized == 0:
                return RiskRuleResult(
                    result_type=RiskResultType.REJECT,
                    rule_name=self.name,
                    reason=f"Quantity {context.quantity} is below minimum lot size {self._lot_size}",
                )
            return RiskRuleResult(
                result_type=RiskResultType.RESIZE,
                rule_name=self.name,
                reason=f"Quantity {context.quantity} not aligned to lot size {self._lot_size}",
                resized_quantity=resized,
            )
        return None


class DuplicateOrderCheckRule(RiskRule):
    """Detect potential duplicate orders.

    Checks if there are too many orders for the same instrument/side
    within a recent time window, indicating a potential duplicate submission.
    """

    def __init__(self, max_same_side_orders: int = 3) -> None:
        self._max_same_side = max_same_side_orders

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.ORDER

    @property
    def name(self) -> str:
        return "duplicate_order_check"

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.recent_same_side_orders >= self._max_same_side:
            return RiskRuleResult(
                result_type=RiskResultType.REJECT,
                rule_name=self.name,
                reason=f"Potential duplicate: {context.recent_same_side_orders} recent orders "
                       f"for same instrument/side (limit: {self._max_same_side})",
            )
        return None


class FrequentCancelLimitRule(RiskRule):
    """Limit frequent order cancellation."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.ORDER

    @property
    def name(self) -> str:
        return "frequent_cancel_limit"

    def __init__(self, max_orders_per_min: int = 10) -> None:
        self._max_per_min = max_orders_per_min

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.existing_order_count_last_min >= self._max_per_min:
            return RiskRuleResult(
                result_type=RiskResultType.DELAY,
                rule_name=self.name,
                reason=f"Order frequency {context.existing_order_count_last_min}/min exceeds limit {self._max_per_min}/min",
            )
        return None

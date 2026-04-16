"""Market-level risk rules (PRD 19.3, SAD 18)."""

from __future__ import annotations

from decimal import Decimal

from hqmts.core.enums import RiskLayer, RiskResultType
from hqmts.risk.engine import RiskContext, RiskRule, RiskRuleResult


class IndexDropHaltRule(RiskRule):
    """Halt new positions when the market index drops significantly."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.MARKET

    @property
    def name(self) -> str:
        return "index_drop_halt"

    def __init__(self, drop_threshold: float = -0.03) -> None:
        self._threshold = drop_threshold

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.index_drop_pct <= Decimal(str(self._threshold)):
            if not context.is_flatten:
                return RiskRuleResult(
                    result_type=RiskResultType.REJECT,
                    rule_name=self.name,
                    reason=f"Index drop {float(context.index_drop_pct):.2%} exceeds threshold {self._threshold:.2%}",
                )
        return None


class ExtremeVolatilityHaltRule(RiskRule):
    """Halt trading during extreme market volatility."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.MARKET

    @property
    def name(self) -> str:
        return "extreme_volatility_halt"

    def __init__(self, volatility_threshold: float = 0.05) -> None:
        self._threshold = volatility_threshold

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.market_volatility >= Decimal(str(self._threshold)):
            if not context.is_flatten:
                return RiskRuleResult(
                    result_type=RiskResultType.REJECT,
                    rule_name=self.name,
                    reason=f"Market volatility {float(context.market_volatility):.2%} exceeds threshold {self._threshold:.2%}",
                )
        return None


class SpecialTimeRestrictionRule(RiskRule):
    """Restrict trading near market open/close and during lunch break."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.MARKET

    @property
    def name(self) -> str:
        return "special_time_restriction"

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        from datetime import time

        check_time = context.check_time
        market_time = check_time.time() if check_time else None
        if market_time is None:
            return None

        # Block orders in first 2 minutes of market open (avoid volatility)
        if time(9, 30) <= market_time <= time(9, 32):
            if not context.is_flatten:
                return RiskRuleResult(
                    result_type=RiskResultType.DELAY,
                    rule_name=self.name,
                    reason="Market open volatility window — delaying non-flatten orders",
                )

        # Block new non-flatten positions near close
        if time(14, 55) <= market_time <= time(15, 0):
            if not context.is_flatten:
                return RiskRuleResult(
                    result_type=RiskResultType.DELAY,
                    rule_name=self.name,
                    reason="Near market close — delaying non-flatten orders",
                )

        return None

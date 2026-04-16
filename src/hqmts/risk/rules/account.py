"""Account-level risk rules (PRD 19.3, SAD 18)."""

from __future__ import annotations

from decimal import Decimal

from hqmts.core.enums import RiskLayer, RiskResultType
from hqmts.risk.engine import RiskContext, RiskRule, RiskRuleResult


class TotalPositionLimitRule(RiskRule):
    """Limit total position ratio across all strategies."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.ACCOUNT

    @property
    def name(self) -> str:
        return "total_position_limit"

    def __init__(self, max_ratio: float = 0.95) -> None:
        self._max_ratio = Decimal(str(max_ratio))

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.account_total_asset <= 0:
            return None

        current_ratio = context.account_market_value / context.account_total_asset
        if current_ratio >= self._max_ratio:
            return RiskRuleResult(
                result_type=RiskResultType.REJECT,
                rule_name=self.name,
                reason=f"Total position ratio {current_ratio:.2%} exceeds limit {self._max_ratio:.2%}",
            )
        return None


class DailyLossLimitRule(RiskRule):
    """Halt trading when daily loss exceeds threshold."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.ACCOUNT

    @property
    def name(self) -> str:
        return "daily_loss_limit"

    def __init__(self, loss_limit: float = 0.03) -> None:
        self._loss_limit = Decimal(str(loss_limit))

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.account_total_asset <= 0:
            return None

        loss_ratio = abs(context.account_pnl_intraday) / context.account_total_asset
        if context.account_pnl_intraday < 0 and loss_ratio >= self._loss_limit:
            return RiskRuleResult(
                result_type=RiskResultType.FORCE_FLATTEN,
                rule_name=self.name,
                reason=f"Daily loss {loss_ratio:.2%} exceeds limit {self._loss_limit:.2%}",
            )
        return None


class IntradayDrawdownRule(RiskRule):
    """Halt trading when intraday drawdown exceeds threshold."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.ACCOUNT

    @property
    def name(self) -> str:
        return "intraday_drawdown"

    def __init__(self, drawdown_limit: float = 0.02) -> None:
        self._drawdown_limit = Decimal(str(drawdown_limit))

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.account_total_asset <= 0:
            return None

        drawdown_ratio = abs(context.account_drawdown_intraday) / context.account_total_asset
        if context.account_drawdown_intraday < 0 and drawdown_ratio >= self._drawdown_limit:
            return RiskRuleResult(
                result_type=RiskResultType.REJECT,
                rule_name=self.name,
                reason=f"Intraday drawdown {drawdown_ratio:.2%} exceeds limit {self._drawdown_limit:.2%}",
            )
        return None


class MinAvailableCashRule(RiskRule):
    """Reject orders that would bring available cash below minimum."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.ACCOUNT

    @property
    def name(self) -> str:
        return "min_available_cash"

    def __init__(self, min_cash: float = 10000.0) -> None:
        self._min_cash = Decimal(str(min_cash))

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.side == "buy" and context.price > 0 and context.quantity > 0:
            order_value = context.price * context.quantity
            remaining = context.account_available_cash - order_value
            if remaining < self._min_cash:
                return RiskRuleResult(
                    result_type=RiskResultType.RESIZE,
                    rule_name=self.name,
                    reason=f"Order would leave available cash {remaining:.0f} below minimum {self._min_cash:.0f}",
                    resized_quantity=max(
                        0,
                        int(
                            (context.account_available_cash - self._min_cash)
                            / context.price
                        ),
                    ),
                )
        return None

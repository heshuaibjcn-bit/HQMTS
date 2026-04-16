"""Strategy-level risk rules (PRD 19.3, SAD 18)."""

from __future__ import annotations

from decimal import Decimal

from hqmts.core.enums import RiskLayer, RiskResultType
from hqmts.risk.engine import RiskContext, RiskRule, RiskRuleResult


class StrategyPositionLimitRule(RiskRule):
    """Limit single strategy's position ratio."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.STRATEGY

    @property
    def name(self) -> str:
        return "strategy_position_limit"

    def __init__(self, max_ratio: float = 0.30) -> None:
        self._max_ratio = Decimal(str(max_ratio))

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.strategy_position_ratio >= self._max_ratio:
            if not context.is_flatten:
                return RiskRuleResult(
                    result_type=RiskResultType.REJECT,
                    rule_name=self.name,
                    reason=f"Strategy position ratio {context.strategy_position_ratio:.2%} exceeds limit",
                )
        return None


class ConsecutiveLossHaltRule(RiskRule):
    """Halt strategy after consecutive losses."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.STRATEGY

    @property
    def name(self) -> str:
        return "consecutive_loss_halt"

    def __init__(self, max_consecutive_losses: int = 5) -> None:
        self._max_losses = max_consecutive_losses

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.strategy_consecutive_losses >= self._max_losses:
            if not context.is_flatten:
                return RiskRuleResult(
                    result_type=RiskResultType.REJECT,
                    rule_name=self.name,
                    reason=f"Strategy has {context.strategy_consecutive_losses} consecutive losses (limit: {self._max_losses})",
                )
        return None


class CooldownPeriodRule(RiskRule):
    """Enforce cooldown period between trades."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.STRATEGY

    @property
    def name(self) -> str:
        return "cooldown_period"

    def __init__(self, cooldown_seconds: int = 300) -> None:
        self._cooldown_seconds = cooldown_seconds

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.strategy_last_trade_time is not None and context.check_time is not None:
            from datetime import timedelta
            elapsed = (context.check_time - context.strategy_last_trade_time).total_seconds()
            if elapsed < self._cooldown_seconds:
                if not context.is_flatten:
                    return RiskRuleResult(
                        result_type=RiskResultType.DELAY,
                        rule_name=self.name,
                        reason=f"Cooldown: {elapsed:.0f}s elapsed, need {self._cooldown_seconds}s",
                    )
        return None


class StrategyDailyLossLimitRule(RiskRule):
    """Limit single strategy's daily loss."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.STRATEGY

    @property
    def name(self) -> str:
        return "strategy_daily_loss_limit"

    def __init__(self, max_daily_loss: float = 0.01) -> None:
        self._max_loss = Decimal(str(max_daily_loss))

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.account_total_asset <= 0:
            return None

        loss_ratio = abs(context.strategy_daily_loss) / context.account_total_asset
        if context.strategy_daily_loss < 0 and loss_ratio >= self._max_loss:
            if not context.is_flatten:
                return RiskRuleResult(
                    result_type=RiskResultType.REJECT,
                    rule_name=self.name,
                    reason=f"Strategy daily loss {loss_ratio:.2%} exceeds limit {self._max_loss:.2%}",
                )
        return None

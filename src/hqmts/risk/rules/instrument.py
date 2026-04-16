"""Instrument-level risk rules (PRD 19.4, SAD 18)."""

from __future__ import annotations

from decimal import Decimal

from hqmts.core.enums import RiskLayer, RiskResultType
from hqmts.risk.engine import RiskContext, RiskRule, RiskRuleResult


class SingleInstrumentMaxExposureRule(RiskRule):
    """Limit single instrument's position ratio."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.INSTRUMENT

    @property
    def name(self) -> str:
        return "single_instrument_max_exposure"

    def __init__(self, max_ratio: float = 0.20) -> None:
        self._max_ratio = Decimal(str(max_ratio))

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.instrument_position_ratio >= self._max_ratio:
            if not context.is_flatten:
                return RiskRuleResult(
                    result_type=RiskResultType.RESIZE,
                    rule_name=self.name,
                    reason=f"Instrument exposure {context.instrument_position_ratio:.2%} exceeds limit {self._max_ratio:.2%}",
                    resized_quantity=0,
                )
        return None


class LiquidityFilterRule(RiskRule):
    """Filter instruments with insufficient daily trading volume."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.INSTRUMENT

    @property
    def name(self) -> str:
        return "liquidity_filter"

    def __init__(self, min_daily_amount: float = 5_000_000.0) -> None:
        self._min_daily_amount = Decimal(str(min_daily_amount))

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.instrument_avg_daily_amount < self._min_daily_amount:
            if not context.is_flatten:
                return RiskRuleResult(
                    result_type=RiskResultType.REJECT,
                    rule_name=self.name,
                    reason=f"Instrument daily amount {context.instrument_avg_daily_amount:.0f} below minimum {self._min_daily_amount:.0f}",
                )
        return None


class BlacklistRule(RiskRule):
    """Block trading on blacklisted instruments."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.INSTRUMENT

    @property
    def name(self) -> str:
        return "blacklist"

    def __init__(self, blacklist: set[str] | None = None) -> None:
        self._blacklist = blacklist or set()

    def update_blacklist(self, instruments: set[str]) -> None:
        self._blacklist = instruments

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.instrument_id and context.instrument_id in self._blacklist:
            return RiskRuleResult(
                result_type=RiskResultType.REJECT,
                rule_name=self.name,
                reason=f"Instrument {context.instrument_id} is blacklisted",
            )
        return None


class STFilterRule(RiskRule):
    """Block new positions on ST stocks."""

    @property
    def layer(self) -> RiskLayer:
        return RiskLayer.INSTRUMENT

    @property
    def name(self) -> str:
        return "st_filter"

    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        if context.instrument_is_st and not context.is_flatten:
            return RiskRuleResult(
                result_type=RiskResultType.REJECT,
                rule_name=self.name,
                reason=f"Instrument {context.instrument_id} is ST",
            )
        return None

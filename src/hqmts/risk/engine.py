"""Risk engine orchestrator.

5-layer risk checking per SAD Section 18 and PRD Section 19.
Decision priority: force_flatten > reject > resize > delay > allow
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from hqmts.core.enums import RiskLayer, RiskResultType
from hqmts.core.types import RiskCheckId, now_shanghai
from hqmts.domain.risk import RiskCheckResult


class RiskContext(BaseModel):
    """Context provided to risk rules for evaluation."""

    signal_id: str | None = None
    order_request_id: str | None = None
    strategy_instance_id: str | None = None
    account_id: str | None = None
    instrument_id: str | None = None
    side: str | None = None
    quantity: int = 0
    price: Decimal = Decimal("0")
    account_total_asset: Decimal = Decimal("0")
    account_available_cash: Decimal = Decimal("0")
    account_market_value: Decimal = Decimal("0")
    account_pnl_intraday: Decimal = Decimal("0")
    account_drawdown_intraday: Decimal = Decimal("0")
    strategy_status: str = "live_running"
    strategy_position_ratio: Decimal = Decimal("0")
    strategy_daily_loss: Decimal = Decimal("0")
    strategy_consecutive_losses: int = 0
    instrument_is_st: bool = False
    instrument_avg_daily_amount: Decimal = Decimal("0")
    instrument_position_ratio: Decimal = Decimal("0")
    instrument_daily_pnl: Decimal = Decimal("0")
    existing_order_count_last_min: int = 0
    is_flatten: bool = False  # Whether this is a force_flatten action
    check_time: datetime = Field(default_factory=now_shanghai)
    # Market-level data
    index_drop_pct: Decimal = Decimal("0")  # Current index change percentage
    market_volatility: Decimal = Decimal("0")  # Current market-wide volatility
    # Duplicate detection
    recent_same_side_orders: int = 0  # Orders for same instrument/side in lookback window
    # Cooldown
    strategy_last_trade_time: datetime | None = None


class RiskRuleResult(BaseModel):
    """Result from a single risk rule."""

    result_type: RiskResultType
    rule_name: str
    reason: str = ""
    resized_quantity: int | None = None


class RiskRule(ABC):
    """Abstract base class for risk rules."""

    @property
    @abstractmethod
    def layer(self) -> RiskLayer:
        """Which risk layer this rule belongs to."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable rule name."""

    @abstractmethod
    async def check(self, context: RiskContext) -> RiskRuleResult | None:
        """Evaluate the risk rule. Returns None if the rule passes (no concern)."""


def _priority_value(result_type: RiskResultType) -> int:
    """Map result type to priority (higher = more restrictive)."""
    return {
        RiskResultType.FORCE_FLATTEN: 5,
        RiskResultType.REJECT: 4,
        RiskResultType.RESIZE: 3,
        RiskResultType.DELAY: 2,
        RiskResultType.ALLOW: 1,
    }[result_type]


class RiskEngine:
    """Orchestrates multi-layer risk evaluation.

    Execution order: Market → Account → Strategy → Instrument → Order
    Returns the most restrictive result across all rules.
    """

    def __init__(self) -> None:
        self._rules: list[RiskRule] = []

    def register_rule(self, rule: RiskRule) -> None:
        """Register a risk rule."""
        self._rules.append(rule)

    def get_rules_by_layer(self, layer: RiskLayer) -> list[RiskRule]:
        """Get all rules for a specific layer."""
        return [r for r in self._rules if r.layer == layer]

    async def evaluate(self, context: RiskContext) -> RiskCheckResult:
        """Evaluate all risk rules and return the most restrictive result."""
        layer_order = [
            RiskLayer.MARKET,
            RiskLayer.ACCOUNT,
            RiskLayer.STRATEGY,
            RiskLayer.INSTRUMENT,
            RiskLayer.ORDER,
        ]

        triggered_rules: list[str] = []
        most_restrictive: RiskRuleResult | None = None

        for layer in layer_order:
            layer_rules = self.get_rules_by_layer(layer)
            for rule in layer_rules:
                result = await rule.check(context)
                if result is not None:
                    triggered_rules.append(result.rule_name)
                    if (
                        most_restrictive is None
                        or _priority_value(result.result_type)
                        > _priority_value(most_restrictive.result_type)
                    ):
                        most_restrictive = result

                    # Short-circuit on force_flatten
                    if result.result_type == RiskResultType.FORCE_FLATTEN:
                        return self._build_result(
                            context, most_restrictive, triggered_rules
                        )

        return self._build_result(context, most_restrictive, triggered_rules)

    def _build_result(
        self,
        context: RiskContext,
        rule_result: RiskRuleResult | None,
        triggered_rules: list[str],
    ) -> RiskCheckResult:
        import uuid

        if rule_result is None:
            return RiskCheckResult(
                risk_check_id=RiskCheckId(str(uuid.uuid4())),
                signal_id=context.signal_id,
                order_request_id=context.order_request_id,
                result_type=RiskResultType.ALLOW,
                triggered_rules=[],
                check_time=context.check_time,
            )

        return RiskCheckResult(
            risk_check_id=RiskCheckId(str(uuid.uuid4())),
            signal_id=context.signal_id,
            order_request_id=context.order_request_id,
            result_type=rule_result.result_type,
            resized_quantity=rule_result.resized_quantity,
            reject_reason=rule_result.reason,
            triggered_rules=triggered_rules,
            check_time=context.check_time,
        )

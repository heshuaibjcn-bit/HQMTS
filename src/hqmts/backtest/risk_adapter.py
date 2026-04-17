"""SyncRiskAdapter: bridges async RiskEngine into sync BacktestEngine."""

from __future__ import annotations

import asyncio
import logging
import uuid
from decimal import Decimal

from hqmts.backtest.order import BacktestOrder
from hqmts.backtest.portfolio import PortfolioState
from hqmts.core.enums import RiskResultType
from hqmts.core.types import RiskCheckId
from hqmts.domain.risk import RiskCheckResult
from hqmts.risk.engine import RiskContext, RiskEngine

logger = logging.getLogger(__name__)


def _allow_result(context: RiskContext) -> RiskCheckResult:
    """Build an ALLOW result (used when risk engine is disabled)."""
    return RiskCheckResult(
        risk_check_id=RiskCheckId(str(uuid.uuid4())),
        signal_id=None,
        order_request_id=None,
        result_type=RiskResultType.ALLOW,
        triggered_rules=[],
        check_time=context.check_time,
    )


def build_risk_context(
    order: BacktestOrder,
    portfolio: PortfolioState,
    instrument_id: str,
) -> RiskContext:
    """Map backtest state to a RiskContext for risk evaluation."""
    total_asset = portfolio.calculate_total_asset()
    market_value = sum(pos.market_value for pos in portfolio.positions.values())
    pos = portfolio.positions.get(instrument_id)
    position_ratio = Decimal("0")
    if pos and total_asset > 0:
        position_ratio = pos.market_value / total_asset if pos.market_value > 0 else Decimal("0")

    logger.debug(
        "build_risk_context: defaulted fields strategy_status=paper_running, "
        "price=%s (from limit_price or 0), instrument=%s",
        order.limit_price or "0", instrument_id,
    )

    return RiskContext(
        signal_id=order.signal_id or None,
        instrument_id=instrument_id,
        side="buy" if order.side.value == "buy" else "sell",
        quantity=order.quantity,
        price=order.limit_price or Decimal("0"),
        account_total_asset=total_asset,
        account_available_cash=portfolio.cash,
        account_market_value=market_value,
        strategy_status="paper_running",
        instrument_position_ratio=position_ratio,
    )


class SyncRiskAdapter:
    """Bridges async RiskEngine into sync BacktestEngine.

    Internally runs an event loop to call RiskEngine.evaluate().
    Pass risk_engine=None to disable risk checks (always returns ALLOW).
    """

    def __init__(self, risk_engine: RiskEngine | None = None) -> None:
        self._engine = risk_engine
        self._loop: asyncio.AbstractEventLoop | None = None

    def evaluate(self, context: RiskContext) -> RiskCheckResult:
        """Evaluate risk rules synchronously."""
        if self._engine is None:
            return _allow_result(context)
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
        return self._loop.run_until_complete(self._engine.evaluate(context))

    def close(self) -> None:
        """Clean up the event loop."""
        if self._loop is not None:
            self._loop.close()
            self._loop = None

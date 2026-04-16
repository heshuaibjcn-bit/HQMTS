"""Strategy context for backtest decisions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from hqmts.core.enums import Cycle
from hqmts.core.types import InstrumentId, StrategyInstanceId, VersionStr
from hqmts.domain.bar import Bar


class StrategyContext(BaseModel):
    """Context provided to strategy at each decision point.

    Carries the information a strategy needs to make a decision,
    mirroring the Live DecisionSnapshot but simplified for backtest.
    """

    strategy_instance_id: StrategyInstanceId
    strategy_version: VersionStr
    instrument_id: InstrumentId
    cycle: Cycle
    decision_time: datetime
    current_position: int = 0
    available_cash: Decimal = Decimal("0")
    total_asset: Decimal = Decimal("0")
    bars: list[Bar] = Field(default_factory=list)
    portfolio_value: Decimal = Decimal("0")
    trade_history: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"frozen": True}

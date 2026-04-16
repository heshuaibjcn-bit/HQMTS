"""Strategy and StrategyInstance domain models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from hqmts.core.enums import Cycle, Environment, StrategyStatus
from hqmts.core.types import StrategyId, StrategyInstanceId, VersionStr


class StrategyParams(BaseModel):
    """Strategy parameter configuration with validation."""

    values: dict[str, float | int | str | bool] = Field(default_factory=dict)
    version: VersionStr = "v1"
    valid_ranges: dict[str, tuple[float, float]] = Field(default_factory=dict)


class Strategy(BaseModel):
    """Strategy template (PRD 13, SAD 13).

    Defines the strategy blueprint with its interface.
    """

    strategy_id: StrategyId
    name: str
    version: VersionStr
    description: str = ""
    supported_cycles: list[Cycle] = Field(min_length=1)
    param_schema: dict[str, dict] = Field(default_factory=dict)  # param_name -> {type, default, range}
    default_params: StrategyParams = Field(default_factory=StrategyParams)
    status: StrategyStatus = StrategyStatus.DRAFT
    created_at: datetime
    updated_at: datetime

    model_config = {"frozen": True}


class StrategyInstance(BaseModel):
    """Running instance of a strategy bound to specific parameters and environment (SAD 7.1).

    Tracks the operational state of a deployed strategy.
    """

    strategy_instance_id: StrategyInstanceId
    strategy_id: StrategyId
    strategy_version: VersionStr
    environment: Environment
    status: StrategyStatus = StrategyStatus.DRAFT
    params: StrategyParams = Field(default_factory=StrategyParams)
    instruments: list[str] = Field(default_factory=list)  # instrument_ids
    account_id: str | None = None
    cycle: Cycle = Cycle.M5
    risk_config_override: dict | None = None  # Per-strategy risk overrides
    created_at: datetime
    updated_at: datetime

    def is_live_active(self) -> bool:
        """Check if this instance is actively running in Live."""
        return self.status == StrategyStatus.LIVE_RUNNING

    def allows_new_positions(self) -> bool:
        """Check if new positions are allowed."""
        return self.status in (
            StrategyStatus.LIVE_RUNNING,
            StrategyStatus.PAPER_RUNNING,
        )

    def allows_trading(self) -> bool:
        """Check if any trading (including close-only) is allowed."""
        return self.status in (
            StrategyStatus.LIVE_RUNNING,
            StrategyStatus.PAPER_RUNNING,
            StrategyStatus.CLOSE_ONLY,
            StrategyStatus.PAUSE_OPEN,
        )

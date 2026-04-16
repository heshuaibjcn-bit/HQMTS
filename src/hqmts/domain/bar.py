"""Bar domain model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from hqmts.core.enums import Cycle, DataQualityGrade
from hqmts.core.types import InstrumentId, VersionStr


class Bar(BaseModel):
    """K-line bar (PRD 9.2, SAD 7.1).

    Key constraints:
    - All formal strategy decisions only use is_completed=True bars
    - System uses 1m bars as primary truth source
    - 5m/15m/30m/60m are aggregated by the system
    - Historical and real-time bar field semantics must be consistent
    """

    instrument_id: InstrumentId
    cycle: Cycle
    bar_start_time: datetime
    bar_end_time: datetime
    open: Decimal = Field(ge=0)
    high: Decimal = Field(ge=0)
    low: Decimal = Field(ge=0)
    close: Decimal = Field(ge=0)
    volume: int = Field(ge=0)
    amount: Decimal = Field(ge=0)
    is_completed: bool
    source: str  # tushare, qmt, aggregated
    data_version: VersionStr
    quality: DataQualityGrade = DataQualityGrade.PASS

    model_config = {"frozen": True}

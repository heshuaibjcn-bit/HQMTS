"""Instrument domain model."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hqmts.core.types import InstrumentId


class Instrument(BaseModel):
    """Represents a tradable security (PRD 9.1, SAD 7.1).

    All instruments use a unified internal ID across the system.
    No mixing of different code formats for the same security.
    """

    instrument_id: InstrumentId
    ts_code: str = Field(pattern=r"^\d{6}\.(SZ|SH|BJ)$")
    exchange: str = Field(pattern=r"^(SZSE|SSE|BSE)$")
    symbol: str = Field(min_length=1, max_length=10)
    name: str
    listing_status: str = Field(default="L")  # L=listed, D=delisted, P=paused
    board_type: str = Field(default="main")  # main, gem, star, bese
    is_st: bool = False
    lot_size: int = Field(default=100, gt=0)
    upper_limit_rule: str = "normal"  # normal, st, registration
    lower_limit_rule: str = "normal"

    model_config = {"frozen": True}

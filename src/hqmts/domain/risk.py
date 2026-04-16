"""RiskCheckResult domain model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from hqmts.core.enums import RiskResultType
from hqmts.core.types import RiskCheckId, SignalId


class RiskCheckResult(BaseModel):
    """Risk check result for a signal or order request (PRD 9.10).

    Result types:
    - allow: pass all risk checks
    - reject: hard reject
    - resize: reduce order quantity
    - delay: delay execution
    - force_flatten: force position reduction/liquidation
    """

    risk_check_id: RiskCheckId
    signal_id: SignalId | None = None
    order_request_id: str | None = None
    result_type: RiskResultType
    resized_quantity: int | None = None  # Set when result_type = resize
    reject_reason: str = ""
    triggered_rules: list[str] = Field(default_factory=list)
    check_time: datetime

    model_config = {"frozen": True}

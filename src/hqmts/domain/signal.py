"""Signal domain model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from hqmts.core.enums import Cycle, SignalType, TargetDirection
from hqmts.core.types import (
    ActionId,
    DecisionSnapshotId,
    InstrumentId,
    SignalId,
    StrategyInstanceId,
    VersionStr,
    now_shanghai,
)


class Signal(BaseModel):
    """Trading intent produced by a strategy at a decision time (PRD 9.4).

    Constraints:
    - Signal represents intent only, not a final order
    - All Signals must be traceable to strategy version and feature snapshot
    - Signal must have an expiration (valid_until)
    """

    signal_id: SignalId
    strategy_instance_id: StrategyInstanceId
    strategy_version: VersionStr
    decision_time: datetime
    instrument_id: InstrumentId
    signal_type: SignalType
    target_direction: TargetDirection | None = None
    target_position: Decimal | None = None  # Target position ratio (0.0 - 1.0)
    signal_strength: float = Field(default=1.0, ge=0.0, le=1.0)
    valid_until: datetime
    reason_code: str = ""
    feature_snapshot_id: str | None = None
    decision_snapshot_id: DecisionSnapshotId | None = None
    cycle: Cycle = Cycle.M5
    created_at: datetime

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check if the signal has expired."""
        check_time = now or now_shanghai()
        return check_time > self.valid_until

    def has_decision_binding(self) -> bool:
        """Check if signal has required DecisionSnapshot binding for Live."""
        return self.decision_snapshot_id is not None

    @classmethod
    def serialization_key(cls, entity_id: str) -> str:
        return f"signal:{entity_id}"

"""DecisionSnapshot domain model."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from hqmts.core.enums import Cycle, SnapshotCompleteness
from hqmts.core.types import (
    DecisionSnapshotId,
    FeatureSnapshotId,
    InstrumentId,
    StrategyInstanceId,
    VersionStr,
)


class DecisionSnapshot(BaseModel):
    """Complete input snapshot for a strategy decision (SAD 7.3).

    Constraints:
    - Live formal Signals must bind to a DecisionSnapshot
    - Signal without DecisionSnapshot cannot enter Live order path
    - Agent cannot forge or retroactively write DecisionSnapshots
    """

    decision_snapshot_id: DecisionSnapshotId
    strategy_instance_id: StrategyInstanceId
    decision_time: datetime
    cycle: Cycle
    feature_snapshot_id: FeatureSnapshotId | None = None
    bar_set_id: str | None = None  # Reference to the set of bars used
    snapshot_completeness: SnapshotCompleteness = SnapshotCompleteness.COMPLETE
    universe_scope: list[InstrumentId] = Field(default_factory=list)
    data_version: VersionStr | None = None
    feature_version: VersionStr | None = None
    created_at: datetime

    model_config = {"frozen": True}

    def is_live_eligible(self) -> bool:
        """Check if this snapshot is eligible for Live execution."""
        return self.snapshot_completeness in (
            SnapshotCompleteness.COMPLETE,
            SnapshotCompleteness.PARTIAL_ALLOWED,
        ) and self.feature_snapshot_id is not None

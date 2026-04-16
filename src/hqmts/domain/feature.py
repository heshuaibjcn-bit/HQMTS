"""FeatureSnapshot domain model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from hqmts.core.enums import Cycle
from hqmts.core.types import FeatureSnapshotId, InstrumentId, VersionStr


class FeatureValues(BaseModel):
    """Feature key-value container."""

    values: dict[str, Decimal | float | int | bool | None] = Field(default_factory=dict)


class FeatureSnapshot(BaseModel):
    """Strategy-visible feature snapshot at a decision time (PRD 9.3).

    Constraints:
    - Feature computation must be reproducible
    - Must record dependency on original Bar versions
    """

    feature_snapshot_id: FeatureSnapshotId
    instrument_id: InstrumentId
    decision_time: datetime
    cycle: Cycle
    feature_set_version: VersionStr
    feature_values: FeatureValues
    source_bar_versions: dict[str, VersionStr]  # bar_key -> version
    created_at: datetime

    model_config = {"frozen": True}

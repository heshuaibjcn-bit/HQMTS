"""VersionBinding domain model."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from hqmts.core.types import VersionBindingId, VersionStr


class VersionBinding(BaseModel):
    """Version binding record for reproducibility (SAD 26.2).

    Every backtest, paper run, and live deployment must bind all relevant versions.
    """

    version_binding_id: VersionBindingId
    entity_type: str  # strategy_instance, backtest_run, live_deployment
    entity_id: str
    data_version: VersionStr = ""
    feature_version: VersionStr = ""
    strategy_version: VersionStr = ""
    param_version: VersionStr = ""
    risk_rule_version: VersionStr = ""
    execution_policy_version: VersionStr = ""
    engine_version: VersionStr = ""
    qmt_adapter_version: VersionStr = ""
    agent_workflow_version: VersionStr = ""
    tool_version: VersionStr = ""
    prompt_version: VersionStr = ""
    live_config_version: VersionStr = ""
    created_at: datetime

    model_config = {"frozen": True}

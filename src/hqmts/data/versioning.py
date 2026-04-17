"""Data versioning service for reproducibility (FR-DATA-006, SAD 26.1).

Binds version information to entities for full traceability:
data → factor → strategy → param → risk → execution → engine → qmt → agent → tool → prompt → live_config
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class VersionBinding:
    """Immutable version binding record linking all component versions to an entity."""

    version_binding_id: str
    entity_type: str  # e.g. "backtest_result", "signal", "order"
    entity_id: str
    data_version: str = ""
    feature_version: str = ""
    strategy_version: str = ""
    param_version: str = ""
    risk_rule_version: str = ""
    execution_policy_version: str = ""
    engine_version: str = ""
    qmt_adapter_version: str = ""
    agent_workflow_version: str = ""
    tool_version: str = ""
    prompt_version: str = ""
    live_config_version: str = ""
    created_at: datetime = field(default_factory=datetime.now)


# In-memory store for testing / backtest. Production uses VersionBindingORM.
_binding_store: dict[tuple[str, str], VersionBinding] = {}

# HQMTS engine version (updated on release)
ENGINE_VERSION = "0.4.0"


class VersionBindingService:
    """Creates and retrieves version bindings for entity traceability.

    In production, this writes to VersionBindingORM via repository.
    For backtest, uses in-memory store.
    """

    def __init__(self, store: dict[tuple[str, str], VersionBinding] | None = None) -> None:
        self._store = store if store is not None else _binding_store

    def create_binding(
        self,
        entity_type: str,
        entity_id: str,
        versions: dict[str, str] | None = None,
    ) -> VersionBinding:
        """Create a version binding for an entity.

        Args:
            entity_type: Type of entity (backtest_result, signal, order, etc.)
            entity_id: Unique identifier of the entity.
            versions: Optional dict of version field overrides.

        Returns:
            The created VersionBinding.
        """
        versions = versions or {}
        binding = VersionBinding(
            version_binding_id=str(uuid.uuid4()),
            entity_type=entity_type,
            entity_id=entity_id,
            data_version=versions.get("data_version", ""),
            feature_version=versions.get("feature_version", ""),
            strategy_version=versions.get("strategy_version", ""),
            param_version=versions.get("param_version", ""),
            risk_rule_version=versions.get("risk_rule_version", ""),
            execution_policy_version=versions.get("execution_policy_version", ""),
            engine_version=versions.get("engine_version", ENGINE_VERSION),
            qmt_adapter_version=versions.get("qmt_adapter_version", ""),
            agent_workflow_version=versions.get("agent_workflow_version", ""),
            tool_version=versions.get("tool_version", ""),
            prompt_version=versions.get("prompt_version", ""),
            live_config_version=versions.get("live_config_version", ""),
        )
        self._store[(entity_type, entity_id)] = binding
        return binding

    def get_binding(self, entity_type: str, entity_id: str) -> VersionBinding | None:
        """Retrieve a version binding by entity type and id."""
        return self._store.get((entity_type, entity_id))

    def get_for_signal(self, signal_id: str) -> VersionBinding | None:
        """Look up version binding for a signal (traceability chain entry point)."""
        return self._store.get(("signal", signal_id))

    def get_for_backtest(self, backtest_id: str) -> VersionBinding | None:
        """Look up version binding for a backtest result."""
        return self._store.get(("backtest_result", backtest_id))

    def clear(self) -> None:
        """Clear the store (for testing)."""
        self._store.clear()

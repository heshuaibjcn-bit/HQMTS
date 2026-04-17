"""Backtest traceability: DecisionSnapshot and VersionBinding for backtest runs (SAD 26.1).

Creates lightweight DecisionSnapshot records during backtest to ensure
the same traceability chain as Live:
  StrategyInstance → DecisionSnapshot → Signal → RiskCheck → Order
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from hqmts.data.versioning import VersionBinding, VersionBindingService


@dataclass
class BacktestDecisionSnapshot:
    """Lightweight decision snapshot for backtest traceability."""

    decision_snapshot_id: str
    strategy_instance_id: str
    decision_time: datetime
    cycle: str
    bar_set_id: str = ""
    snapshot_completeness: str = "complete"
    signal_id: str = ""

    # Version traceability
    strategy_version: str = ""
    data_version: str = ""


class BacktestTraceability:
    """Tracks decision snapshots and version bindings during a backtest run.

    Usage:
        trace = BacktestTraceability(version_service)
        trace.start_run(backtest_id, strategy_version, ...)

        # For each signal generated:
        snapshot = trace.create_snapshot(strategy_instance_id, decision_time, cycle)
        signal.decision_snapshot_id = snapshot.decision_snapshot_id

        # After backtest:
        trace.finish_run()
    """

    def __init__(
        self,
        version_service: VersionBindingService | None = None,
    ) -> None:
        self._version_service = version_service or VersionBindingService()
        self._snapshots: list[BacktestDecisionSnapshot] = []
        self._backtest_id: str = ""
        self._versions: dict[str, str] = {}

    def start_run(
        self,
        backtest_id: str,
        strategy_version: str = "",
        data_version: str = "",
        extra_versions: dict[str, str] | None = None,
    ) -> None:
        """Initialize traceability for a new backtest run."""
        self._backtest_id = backtest_id
        self._snapshots = []
        self._versions = {
            "strategy_version": strategy_version,
            "data_version": data_version,
        }
        if extra_versions:
            self._versions.update(extra_versions)

    def create_snapshot(
        self,
        strategy_instance_id: str,
        decision_time: datetime,
        cycle: str,
        signal_id: str = "",
    ) -> BacktestDecisionSnapshot:
        """Create a DecisionSnapshot for a strategy decision point."""
        snapshot = BacktestDecisionSnapshot(
            decision_snapshot_id=str(uuid.uuid4()),
            strategy_instance_id=strategy_instance_id,
            decision_time=decision_time,
            cycle=cycle,
            signal_id=signal_id,
            strategy_version=self._versions.get("strategy_version", ""),
            data_version=self._versions.get("data_version", ""),
        )
        self._snapshots.append(snapshot)
        return snapshot

    def finish_run(self) -> VersionBinding:
        """Create a VersionBinding for the completed backtest run.

        Returns the binding linking all version info to this backtest.
        """
        binding = self._version_service.create_binding(
            entity_type="backtest_result",
            entity_id=self._backtest_id,
            versions=self._versions,
        )
        return binding

    @property
    def snapshots(self) -> list[BacktestDecisionSnapshot]:
        """All decision snapshots created during this run."""
        return list(self._snapshots)

    @property
    def snapshot_count(self) -> int:
        """Number of decision points recorded."""
        return len(self._snapshots)

    def get_version_binding(self) -> VersionBinding | None:
        """Get the version binding for this run (after finish_run)."""
        return self._version_service.get_for_backtest(self._backtest_id)

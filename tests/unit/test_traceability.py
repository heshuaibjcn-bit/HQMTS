"""Tests for backtest traceability chain (SAD 26.1)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from hqmts.backtest.traceability import BacktestTraceability
from hqmts.data.versioning import VersionBindingService


class TestBacktestTraceability:
    def test_start_run_initializes(self):
        trace = BacktestTraceability()
        trace.start_run("bt-001", strategy_version="v1", data_version="v2")
        assert trace.snapshot_count == 0

    def test_create_snapshot(self):
        trace = BacktestTraceability()
        trace.start_run("bt-002")
        now = datetime(2024, 1, 2, 10, 0)
        snap = trace.create_snapshot("strat-001", now, "5m", signal_id="sig-001")
        assert snap.decision_snapshot_id  # non-empty
        assert snap.strategy_instance_id == "strat-001"
        assert snap.decision_time == now
        assert snap.cycle == "5m"
        assert snap.signal_id == "sig-001"

    def test_multiple_snapshots(self):
        trace = BacktestTraceability()
        trace.start_run("bt-003")
        base = datetime(2024, 1, 2, 9, 30)
        for i in range(5):
            trace.create_snapshot("strat-001", base + timedelta(minutes=5 * i), "5m")
        assert trace.snapshot_count == 5

    def test_finish_run_creates_binding(self):
        svc = VersionBindingService()
        trace = BacktestTraceability(version_service=svc)
        trace.start_run(
            "bt-004",
            strategy_version="v2.0",
            data_version="v1.0",
            extra_versions={"param_version": "v3"},
        )
        trace.create_snapshot("strat-001", datetime.now(), "5m")
        binding = trace.finish_run()

        assert binding.entity_type == "backtest_result"
        assert binding.entity_id == "bt-004"
        assert binding.strategy_version == "v2.0"
        assert binding.data_version == "v1.0"
        assert binding.param_version == "v3"

    def test_get_version_binding_after_finish(self):
        svc = VersionBindingService()
        trace = BacktestTraceability(version_service=svc)
        trace.start_run("bt-005", strategy_version="v1")
        trace.finish_run()

        binding = trace.get_version_binding()
        assert binding is not None
        assert binding.strategy_version == "v1"

    def test_snapshot_has_version_info(self):
        trace = BacktestTraceability()
        trace.start_run("bt-006", strategy_version="v2", data_version="v1")
        snap = trace.create_snapshot("strat-001", datetime.now(), "5m")
        assert snap.strategy_version == "v2"
        assert snap.data_version == "v1"

    def test_snapshots_immutable_list(self):
        trace = BacktestTraceability()
        trace.start_run("bt-007")
        trace.create_snapshot("strat-001", datetime.now(), "5m")
        snaps = trace.snapshots
        assert len(snaps) == 1
        # Modifying returned list doesn't affect internal state
        snaps.clear()
        assert trace.snapshot_count == 1

    def test_full_traceability_chain(self):
        """End-to-end: start → create snapshots → finish → verify binding exists."""
        svc = VersionBindingService()
        trace = BacktestTraceability(version_service=svc)

        trace.start_run(
            "bt-chain",
            strategy_version="v1.0",
            data_version="v2.0",
            extra_versions={"engine_version": "0.4.0"},
        )

        # Simulate 3 decision points
        base = datetime(2024, 1, 2, 9, 30)
        for i in range(3):
            snap = trace.create_snapshot(
                "strat-001",
                base + timedelta(minutes=5 * i),
                "5m",
                signal_id=f"sig-{i:03d}",
            )
            # Each snapshot should have a unique ID
            assert snap.decision_snapshot_id

        binding = trace.finish_run()

        # Verify chain
        assert trace.snapshot_count == 3
        assert binding is not None
        assert binding.strategy_version == "v1.0"
        assert binding.data_version == "v2.0"

        # Verify binding is retrievable
        retrieved = svc.get_for_backtest("bt-chain")
        assert retrieved is not None
        assert retrieved.strategy_version == "v1.0"

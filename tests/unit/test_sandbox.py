"""Tests for StrategySandbox (SAD 13.2/13.3)."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from hqmts.core.enums import SandboxViolationType
from hqmts.execution.sandbox import (
    SandboxConfig,
    SandboxViolation,
    StrategySandbox,
)
from hqmts.core.types import now_shanghai


def _make_time(hour: int, minute: int):
    """Create a fixed now_shanghai return value at given time."""
    from datetime import datetime, timezone
    from dateutil import tz
    return datetime(
        2026, 4, 20, hour, minute, 0,
        tzinfo=tz.gettz("Asia/Shanghai"),
    )


class TestTradingHours:
    @pytest.mark.asyncio
    async def test_morning_allowed(self):
        """09:45 is within morning trading hours."""
        sandbox = StrategySandbox(SandboxConfig(enforce_trading_hours=True))
        with patch("hqmts.execution.sandbox.now_shanghai", return_value=_make_time(9, 45)):
            violation = sandbox.enforce_trading_hours("strat_001")
        assert violation is None

    @pytest.mark.asyncio
    async def test_morning_close_boundary(self):
        """11:30 is NOT within morning trading hours (exclusive end)."""
        sandbox = StrategySandbox(SandboxConfig(enforce_trading_hours=True))
        with patch("hqmts.execution.sandbox.now_shanghai", return_value=_make_time(11, 30)):
            violation = sandbox.enforce_trading_hours("strat_001")
        assert violation is not None
        assert violation.violation_type == SandboxViolationType.OUTSIDE_TRADING_HOURS

    @pytest.mark.asyncio
    async def test_lunch_blocked(self):
        """12:00 is outside trading hours (lunch break)."""
        sandbox = StrategySandbox(SandboxConfig(enforce_trading_hours=True))
        with patch("hqmts.execution.sandbox.now_shanghai", return_value=_make_time(12, 0)):
            violation = sandbox.enforce_trading_hours("strat_001")
        assert violation is not None
        assert violation.violation_type == SandboxViolationType.OUTSIDE_TRADING_HOURS

    @pytest.mark.asyncio
    async def test_afternoon_allowed(self):
        """14:00 is within afternoon trading hours."""
        sandbox = StrategySandbox(SandboxConfig(enforce_trading_hours=True))
        with patch("hqmts.execution.sandbox.now_shanghai", return_value=_make_time(14, 0)):
            violation = sandbox.enforce_trading_hours("strat_001")
        assert violation is None

    @pytest.mark.asyncio
    async def test_evening_blocked(self):
        """16:00 is outside trading hours."""
        sandbox = StrategySandbox(SandboxConfig(enforce_trading_hours=True))
        with patch("hqmts.execution.sandbox.now_shanghai", return_value=_make_time(16, 0)):
            violation = sandbox.enforce_trading_hours("strat_001")
        assert violation is not None

    @pytest.mark.asyncio
    async def test_trading_hours_disabled(self):
        """When enforce_trading_hours=False, any time is allowed."""
        sandbox = StrategySandbox(SandboxConfig(enforce_trading_hours=False))
        with patch("hqmts.execution.sandbox.now_shanghai", return_value=_make_time(23, 0)):
            violation = sandbox.enforce_trading_hours("strat_001")
        assert violation is None


class TestInstrumentWhitelist:
    @pytest.mark.asyncio
    async def test_whitelist_pass(self):
        sandbox = StrategySandbox(SandboxConfig(
            instrument_whitelist=["000001.SZ", "600000.SH"],
        ))
        violation = sandbox.enforce_instrument_whitelist("strat_001", "000001.SZ")
        assert violation is None

    @pytest.mark.asyncio
    async def test_whitelist_blocked(self):
        sandbox = StrategySandbox(SandboxConfig(
            instrument_whitelist=["000001.SZ"],
        ))
        violation = sandbox.enforce_instrument_whitelist("strat_001", "999999.SZ")
        assert violation is not None
        assert violation.violation_type == SandboxViolationType.INSTRUMENT_NOT_WHITELISTED

    @pytest.mark.asyncio
    async def test_empty_whitelist_allows_all(self):
        sandbox = StrategySandbox(SandboxConfig(instrument_whitelist=[]))
        violation = sandbox.enforce_instrument_whitelist("strat_001", "anything")
        assert violation is None


class TestCPUTimeLimit:
    @pytest.mark.asyncio
    async def test_within_limit(self):
        """Coroutine completing in time returns result normally."""
        sandbox = StrategySandbox(SandboxConfig(cpu_time_limit_seconds=1.0))

        async def fast_task():
            return 42

        result = await sandbox.wrap_bar_processing("strat_001", fast_task())
        assert result == 42

    @pytest.mark.asyncio
    async def test_cpu_timeout(self):
        """Coroutine exceeding time limit raises SandboxViolation."""
        sandbox = StrategySandbox(SandboxConfig(cpu_time_limit_seconds=0.05))

        async def slow_task():
            await asyncio.sleep(1.0)
            return 42

        with pytest.raises(SandboxViolation) as exc_info:
            await sandbox.wrap_bar_processing("strat_001", slow_task())

        assert exc_info.value.violation_type == SandboxViolationType.CPU_TIMEOUT
        # Violation should be recorded
        assert len(sandbox.violations) == 1


class TestMemoryLimit:
    @pytest.mark.asyncio
    async def test_within_limit(self):
        sandbox = StrategySandbox(SandboxConfig(memory_limit_mb=512))
        violation = sandbox.check_memory_usage("strat_001", 200.0)
        assert violation is None

    @pytest.mark.asyncio
    async def test_exceeds_limit(self):
        sandbox = StrategySandbox(SandboxConfig(memory_limit_mb=512))
        violation = sandbox.check_memory_usage("strat_001", 600.0)
        assert violation is not None
        assert violation.violation_type == SandboxViolationType.MEMORY_EXCEEDED

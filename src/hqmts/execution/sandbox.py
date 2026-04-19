"""Strategy sandbox for runtime enforcement (SAD 13.2/13.3).

Restricts strategy execution with CPU time limits, memory limits,
network blocking, instrument whitelisting, and trading hours enforcement.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import time

from hqmts.core.enums import SandboxViolationType
from hqmts.core.types import now_shanghai

logger = logging.getLogger(__name__)


@dataclass
class SandboxConfig:
    """Configuration for strategy sandbox restrictions."""

    cpu_time_limit_seconds: float = 5.0  # Per bar processing cycle
    memory_limit_mb: int = 512  # Per strategy instance
    allow_network: bool = False  # No outbound calls during live
    instrument_whitelist: list[str] = field(default_factory=list)
    enforce_trading_hours: bool = True
    # A-stock trading hours
    morning_open: str = "09:30"
    morning_close: str = "11:30"
    afternoon_open: str = "13:00"
    afternoon_close: str = "15:00"


class SandboxViolation(Exception):
    """A sandbox rule violation.

    Raised as an exception for CPU timeout.
    Stored as a record for other violations.
    """

    def __init__(
        self,
        strategy_instance_id: str,
        violation_type: SandboxViolationType,
        detail: str,
        timestamp: str = "",
    ) -> None:
        self.strategy_instance_id = strategy_instance_id
        self.violation_type = violation_type
        self.detail = detail
        self.timestamp = timestamp
        super().__init__(detail)


class StrategySandbox:
    """Runtime enforcement layer for strategy execution (SAD 13.2/13.3).

    Wraps strategy bar processing with safety constraints:
    - CPU time limit via asyncio.wait_for
    - Instrument whitelist enforcement
    - Trading hours enforcement (A-stock 09:30-11:30, 13:00-15:00)
    - Network access blocking (placeholder for production)
    """

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self._config = config or SandboxConfig()
        self._violations: list[SandboxViolation] = []

    @property
    def config(self) -> SandboxConfig:
        return self._config

    @property
    def violations(self) -> list[SandboxViolation]:
        return list(self._violations)

    def enforce_trading_hours(
        self, strategy_instance_id: str
    ) -> SandboxViolation | None:
        """Check if current time is within A-stock trading hours.

        Returns None if within hours, SandboxViolation otherwise.
        """
        if not self._config.enforce_trading_hours:
            return None

        now = now_shanghai()
        current_time = now.time()

        morning_open = time.fromisoformat(self._config.morning_open)
        morning_close = time.fromisoformat(self._config.morning_close)
        afternoon_open = time.fromisoformat(self._config.afternoon_open)
        afternoon_close = time.fromisoformat(self._config.afternoon_close)

        in_morning = morning_open <= current_time < morning_close
        in_afternoon = afternoon_open <= current_time < afternoon_close

        if in_morning or in_afternoon:
            return None

        violation = SandboxViolation(
            strategy_instance_id=strategy_instance_id,
            violation_type=SandboxViolationType.OUTSIDE_TRADING_HOURS,
            detail=f"Current time {current_time.strftime('%H:%M')} outside trading hours",
            timestamp=now.isoformat(),
        )
        self._violations.append(violation)
        return violation

    def enforce_instrument_whitelist(
        self, strategy_instance_id: str, instrument_id: str
    ) -> SandboxViolation | None:
        """Check if instrument is in the approved whitelist.

        Returns None if allowed, SandboxViolation otherwise.
        Empty whitelist means all instruments allowed.
        """
        if not self._config.instrument_whitelist:
            return None

        if instrument_id in self._config.instrument_whitelist:
            return None

        violation = SandboxViolation(
            strategy_instance_id=strategy_instance_id,
            violation_type=SandboxViolationType.INSTRUMENT_NOT_WHITELISTED,
            detail=f"Instrument {instrument_id} not in whitelist",
            timestamp=now_shanghai().isoformat(),
        )
        self._violations.append(violation)
        return violation

    async def wrap_bar_processing(
        self,
        strategy_instance_id: str,
        coroutine,
        timeout: float | None = None,
    ):
        """Wrap a strategy bar processing coroutine with CPU time limit.

        Uses asyncio.wait_for to enforce timeout.
        Raises SandboxViolation (as exception) on timeout.
        """
        limit = timeout or self._config.cpu_time_limit_seconds

        try:
            return await asyncio.wait_for(coroutine, timeout=limit)
        except asyncio.TimeoutError:
            violation = SandboxViolation(
                strategy_instance_id=strategy_instance_id,
                violation_type=SandboxViolationType.CPU_TIMEOUT,
                detail=f"Bar processing exceeded {limit}s limit",
                timestamp=now_shanghai().isoformat(),
            )
            self._violations.append(violation)
            raise violation from None

    def check_memory_usage(
        self, strategy_instance_id: str, current_mb: float
    ) -> SandboxViolation | None:
        """Check if strategy memory usage exceeds limit.

        Returns None if within limit, SandboxViolation otherwise.
        Caller must provide current_mb (measured externally).
        """
        if current_mb <= self._config.memory_limit_mb:
            return None

        violation = SandboxViolation(
            strategy_instance_id=strategy_instance_id,
            violation_type=SandboxViolationType.MEMORY_EXCEEDED,
            detail=f"Memory {current_mb:.0f}MB exceeds {self._config.memory_limit_mb}MB limit",
            timestamp=now_shanghai().isoformat(),
        )
        self._violations.append(violation)
        return violation

    def clear_violations(self) -> None:
        """Clear recorded violations (e.g. between processing cycles)."""
        self._violations.clear()

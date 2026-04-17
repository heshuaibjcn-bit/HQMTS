"""QMT health monitoring and degradation management (SAD 23).

Tracks QMT adapter health and determines system degradation mode.
Uses AuthorityMode for state authority and DegradationMode for
system-wide behavior constraints.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from hqmts.core.enums import AuthorityMode, DegradationMode
from hqmts.core.types import now_shanghai

logger = logging.getLogger(__name__)


@dataclass
class QMTHealthStatus:
    """Current health status of the QMT adapter."""

    last_report_time: datetime | None = None
    last_query_time: datetime | None = None
    report_healthy: bool = True
    query_healthy: bool = True
    consecutive_report_failures: int = 0
    consecutive_query_failures: int = 0
    authority_mode: AuthorityMode = AuthorityMode.EVENT_PRIMARY
    degradation_mode: DegradationMode = DegradationMode.NORMAL


class QMTHealthMonitor:
    """Monitors QMT adapter health and manages degradation transitions.

    Per SAD 23:
    - Report (push) failure → switch to query_primary
    - Query also fails → degraded / close_only
    - Both recovered → resume normal
    """

    def __init__(
        self,
        report_failure_threshold: int = 3,
        query_failure_threshold: int = 3,
        report_timeout_seconds: int = 60,
    ) -> None:
        self._report_failure_threshold = report_failure_threshold
        self._query_failure_threshold = query_failure_threshold
        self._report_timeout_seconds = report_timeout_seconds
        self._status = QMTHealthStatus()

    @property
    def status(self) -> QMTHealthStatus:
        return self._status

    @property
    def degradation_mode(self) -> DegradationMode:
        return self._status.degradation_mode

    @property
    def authority_mode(self) -> AuthorityMode:
        return self._status.authority_mode

    def record_report_received(self) -> None:
        """Call when a QMT push report is received successfully."""
        self._status.last_report_time = now_shanghai()
        self._status.report_healthy = True
        self._status.consecutive_report_failures = 0
        self._recompute()

    def record_report_failure(self) -> None:
        """Call when a QMT report is missed or fails."""
        self._status.consecutive_report_failures += 1
        if self._status.consecutive_report_failures >= self._report_failure_threshold:
            self._status.report_healthy = False
        self._recompute()

    def record_query_success(self) -> None:
        """Call when a QMT query succeeds."""
        self._status.last_query_time = now_shanghai()
        self._status.query_healthy = True
        self._status.consecutive_query_failures = 0
        self._recompute()

    def record_query_failure(self) -> None:
        """Call when a QMT query fails."""
        self._status.consecutive_query_failures += 1
        if self._status.consecutive_query_failures >= self._query_failure_threshold:
            self._status.query_healthy = False
        self._recompute()

    def _recompute(self) -> None:
        """Recompute authority and degradation modes based on current health."""
        old_degradation = self._status.degradation_mode
        old_authority = self._status.authority_mode

        # Authority mode
        if self._status.report_healthy:
            self._status.authority_mode = AuthorityMode.EVENT_PRIMARY
        else:
            self._status.authority_mode = AuthorityMode.QUERY_PRIMARY

        # Degradation mode
        if self._status.report_healthy and self._status.query_healthy:
            self._status.degradation_mode = DegradationMode.NORMAL
        elif not self._status.report_healthy and self._status.query_healthy:
            self._status.degradation_mode = DegradationMode.DEGRADED_QUERY_PRIMARY
        elif not self._status.report_healthy and not self._status.query_healthy:
            self._status.degradation_mode = DegradationMode.CLOSE_ONLY
        else:
            # report healthy but query not — unusual but treat as degraded
            self._status.degradation_mode = DegradationMode.PAUSE_OPEN

        # Log transitions
        if self._status.degradation_mode != old_degradation:
            logger.warning(
                "QMT_DEGRADATION_CHANGE %s -> %s (report=%s query=%s)",
                old_degradation.value,
                self._status.degradation_mode.value,
                self._status.report_healthy,
                self._status.query_healthy,
            )
        if self._status.authority_mode != old_authority:
            logger.info(
                "QMT_AUTHORITY_CHANGE %s -> %s",
                old_authority.value,
                self._status.authority_mode.value,
            )

    def check_report_timeout(self) -> bool:
        """Check if the report stream has timed out.

        Returns True if timed out (should call record_report_failure).
        """
        if self._status.last_report_time is None:
            return False  # No report ever received, don't timeout
        elapsed = (now_shanghai() - self._status.last_report_time).total_seconds()
        if elapsed > self._report_timeout_seconds:
            self.record_report_failure()
            return True
        return False

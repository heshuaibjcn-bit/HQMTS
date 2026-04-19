"""Tests for QMT health monitor and degradation management."""

import pytest

from hqmts.core.enums import AuthorityMode, DegradationMode
from hqmts.monitoring.qmt_health import QMTHealthMonitor


class TestQMTHealthMonitor:
    def test_initial_state(self):
        monitor = QMTHealthMonitor()
        assert monitor.degradation_mode == DegradationMode.NORMAL
        assert monitor.authority_mode == AuthorityMode.EVENT_PRIMARY

    def test_report_received_stays_normal(self):
        monitor = QMTHealthMonitor()
        monitor.record_report_received()
        assert monitor.degradation_mode == DegradationMode.NORMAL

    def test_report_failure_threshold_triggers_degraded(self):
        monitor = QMTHealthMonitor(report_failure_threshold=2)
        monitor.record_report_failure()
        assert monitor.degradation_mode == DegradationMode.NORMAL  # 1 failure
        monitor.record_report_failure()
        # Report down but query still up
        assert monitor.authority_mode == AuthorityMode.QUERY_PRIMARY
        assert monitor.degradation_mode == DegradationMode.DEGRADED_QUERY_PRIMARY

    def test_both_down_triggers_close_only(self):
        monitor = QMTHealthMonitor(
            report_failure_threshold=2,
            query_failure_threshold=2,
        )
        monitor.record_report_failure()
        monitor.record_report_failure()
        monitor.record_query_failure()
        monitor.record_query_failure()
        assert monitor.degradation_mode == DegradationMode.CLOSE_ONLY

    def test_recovery_back_to_normal(self):
        monitor = QMTHealthMonitor(report_failure_threshold=2)
        monitor.record_report_failure()
        monitor.record_report_failure()
        assert monitor.degradation_mode != DegradationMode.NORMAL

        # Recovery
        monitor.record_report_received()
        assert monitor.degradation_mode == DegradationMode.NORMAL
        assert monitor.authority_mode == AuthorityMode.EVENT_PRIMARY

    def test_query_recovery_while_report_down(self):
        monitor = QMTHealthMonitor(report_failure_threshold=2)
        monitor.record_report_failure()
        monitor.record_report_failure()
        # Query still healthy → degraded_query_primary
        assert monitor.degradation_mode == DegradationMode.DEGRADED_QUERY_PRIMARY

    def test_status_tracks_failure_counts(self):
        monitor = QMTHealthMonitor(report_failure_threshold=5)
        for _ in range(3):
            monitor.record_report_failure()
        assert monitor.status.consecutive_report_failures == 3
        monitor.record_report_received()
        assert monitor.status.consecutive_report_failures == 0

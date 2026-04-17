"""Tests for Paper-to-Live readiness assessment (SAD 25)."""

from __future__ import annotations

from hqmts.governance.readiness import (
    ReadinessAssessor,
    ReadinessCategory,
    ReadinessCheck,
    ReadinessReport,
)


def _passing_metrics() -> dict:
    """Metrics that should pass all readiness checks."""
    return dict(
        paper_total_return=15.0,
        paper_max_drawdown=5.0,
        paper_sharpe_ratio=1.5,
        paper_win_rate=55.0,
        paper_total_trades=50,
        paper_days=30,
        backtest_total_return=12.0,
        backtest_max_drawdown=4.0,
        backtest_sharpe_ratio=1.3,
        max_daily_loss_pct=1.5,
        max_single_order_pct=5.0,
        param_stability_score=0.85,
        has_approval=True,
        has_version_binding=True,
        has_kill_switch_test=True,
        has_recovery_drill=True,
    )


class TestReadinessReport:
    def test_total_score_all_passing(self):
        report = ReadinessReport(strategy_name="test", strategy_version="v1")
        report.checks = [
            ReadinessCheck("a", ReadinessCategory.PERFORMANCE, "test", True, weight=1.0),
            ReadinessCheck("b", ReadinessCategory.RISK, "test", True, weight=2.0),
        ]
        assert report.total_score == 100.0

    def test_total_score_partial(self):
        report = ReadinessReport(strategy_name="test", strategy_version="v1")
        report.checks = [
            ReadinessCheck("a", ReadinessCategory.PERFORMANCE, "test", True, weight=1.0),
            ReadinessCheck("b", ReadinessCategory.RISK, "test", False, weight=1.0),
        ]
        assert report.total_score == 50.0

    def test_is_ready(self):
        assessor = ReadinessAssessor()
        report = assessor.assess("test", "v1", **_passing_metrics())
        assert report.is_ready

    def test_not_ready_without_approval(self):
        metrics = _passing_metrics()
        metrics["has_approval"] = False
        assessor = ReadinessAssessor()
        report = assessor.assess("test", "v1", **metrics)
        assert not report.is_ready

    def test_not_ready_negative_return(self):
        metrics = _passing_metrics()
        metrics["paper_total_return"] = -5.0
        assessor = ReadinessAssessor()
        report = assessor.assess("test", "v1", **metrics)
        assert not report.is_ready  # Critical check fails

    def test_failed_checks(self):
        metrics = _passing_metrics()
        metrics["has_kill_switch_test"] = False
        metrics["paper_total_return"] = -1.0
        assessor = ReadinessAssessor()
        report = assessor.assess("test", "v1", **metrics)
        assert len(report.failed_checks) >= 2


class TestReadinessAssessor:
    def test_all_categories_covered(self):
        assessor = ReadinessAssessor()
        report = assessor.assess("test", "v1", **_passing_metrics())
        categories = {c.category for c in report.checks}
        assert ReadinessCategory.PERFORMANCE in categories
        assert ReadinessCategory.RISK in categories
        assert ReadinessCategory.STABILITY in categories
        assert ReadinessCategory.OPERATIONAL in categories
        assert ReadinessCategory.GOVERNANCE in categories

    def test_check_count(self):
        assessor = ReadinessAssessor()
        report = assessor.assess("test", "v1")
        assert len(report.checks) >= 14

    def test_insufficient_paper_days(self):
        metrics = _passing_metrics()
        metrics["paper_days"] = 5
        assessor = ReadinessAssessor(min_paper_days=20)
        report = assessor.assess("test", "v1", **metrics)
        # Should have a failed check for insufficient duration
        duration_checks = [c for c in report.checks if c.name == "sufficient_paper_duration"]
        assert len(duration_checks) == 1
        assert not duration_checks[0].is_passed

    def test_custom_min_paper_days(self):
        metrics = _passing_metrics()
        metrics["paper_days"] = 15
        assessor = ReadinessAssessor(min_paper_days=10)
        report = assessor.assess("test", "v1", **metrics)
        duration_checks = [c for c in report.checks if c.name == "sufficient_paper_duration"]
        assert duration_checks[0].is_passed

    def test_low_sharpe_fails(self):
        metrics = _passing_metrics()
        metrics["paper_sharpe_ratio"] = 0.3
        assessor = ReadinessAssessor()
        report = assessor.assess("test", "v1", **metrics)
        sharpe_checks = [c for c in report.checks if c.name == "sufficient_sharpe"]
        assert not sharpe_checks[0].is_passed

    def test_backtest_paper_consistency_check(self):
        metrics = _passing_metrics()
        metrics["paper_total_return"] = 50.0
        metrics["backtest_total_return"] = 10.0
        assessor = ReadinessAssessor()
        report = assessor.assess("test", "v1", **metrics)
        consistency = [c for c in report.checks if c.name == "backtest_paper_consistency"]
        # 50% vs 10% is a large gap
        assert not consistency[0].is_passed

    def test_empty_report_score(self):
        report = ReadinessReport(strategy_name="test", strategy_version="v1")
        assert report.total_score == 0.0

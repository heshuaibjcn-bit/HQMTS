"""Integration test: Full admission lifecycle from paper metrics to approval."""

from __future__ import annotations

import pytest

from hqmts.core.enums import AdmissionStatus
from hqmts.validation.admission import PaperLiveAdmissionService


class TestAdmissionFlow:
    """Full paper-to-live admission flow with readiness assessment."""

    @pytest.mark.asyncio
    async def test_full_admission_happy_path(self):
        """Strategy passes all checks and gets approved."""
        svc = PaperLiveAdmissionService()
        record = await svc.create_admission(
            strategy_instance_id="strat_001",
            strategy_version="v2.1",
        )
        assert record.status == AdmissionStatus.PENDING_METRICS

        # Collect strong paper metrics
        record = await svc.collect_paper_metrics(
            record.admission_id,
            total_return_pct=18.5,
            max_drawdown_pct=6.2,
            sharpe_ratio=1.8,
            win_rate_pct=62.0,
            total_trades=85,
            trading_days=45,
            max_daily_loss_pct=1.2,
        )
        assert record.status == AdmissionStatus.METRICS_COLLECTED

        # Evaluate readiness with full governance kwargs
        record = await svc.evaluate_readiness(
            record.admission_id,
            backtest_total_return=16.0,
            backtest_max_drawdown=7.0,
            backtest_sharpe_ratio=1.6,
            max_single_order_pct=5.0,
            param_stability_score=0.85,
            has_kill_switch_test=True,
            has_recovery_drill=True,
            has_approval=True,
            has_version_binding=True,
        )
        assert record.status == AdmissionStatus.PENDING_REVIEW
        assert record.readiness_passed is True
        assert record.readiness_score > 80.0

        # Submit for approval
        record = await svc.submit_for_approval(record.admission_id)

        # Approve
        record = await svc.process_approval_decision(
            record.admission_id,
            approver="portfolio_manager",
            decision="approved",
            reason="All criteria met, strong paper performance",
        )
        assert record.status == AdmissionStatus.APPROVED
        assert record.approver == "portfolio_manager"
        assert record.decided_at is not None

    @pytest.mark.asyncio
    async def test_admission_rejected_for_poor_metrics(self):
        """Strategy fails readiness and gets rejected."""
        svc = PaperLiveAdmissionService()
        record = await svc.create_admission("strat_002", "v1.0")

        # Poor metrics
        record = await svc.collect_paper_metrics(
            record.admission_id,
            total_return_pct=-5.0,
            max_drawdown_pct=20.0,
            sharpe_ratio=0.2,
            win_rate_pct=35.0,
            total_trades=10,
            trading_days=7,
            max_daily_loss_pct=4.5,
        )

        record = await svc.evaluate_readiness(record.admission_id)
        assert record.readiness_passed is False

        # Still goes to review (human decides)
        await svc.submit_for_approval(record.admission_id)
        record = await svc.process_approval_decision(
            record.admission_id,
            approver="risk_manager",
            decision="rejected",
            reason="Insufficient paper track record and poor Sharpe",
        )
        assert record.status == AdmissionStatus.REJECTED

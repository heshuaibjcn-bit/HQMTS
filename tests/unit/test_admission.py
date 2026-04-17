"""Tests for PaperLiveAdmissionService (SAD 25)."""

from __future__ import annotations

import pytest

from hqmts.core.enums import AdmissionStatus
from hqmts.validation.admission import (
    AdmissionChecklist,
    PaperLiveAdmissionService,
)


@pytest.fixture
def service():
    return PaperLiveAdmissionService()


class TestPaperLiveAdmissionService:
    @pytest.mark.asyncio
    async def test_create_admission(self, service):
        """Creates record in PENDING_METRICS state."""
        record = await service.create_admission(
            strategy_instance_id="strat_001",
            strategy_version="v1.0",
        )

        assert record.status == AdmissionStatus.PENDING_METRICS
        assert record.strategy_instance_id == "strat_001"
        assert record.admission_id  # Non-empty ID

    @pytest.mark.asyncio
    async def test_collect_paper_metrics(self, service):
        """Collects metrics and transitions to METRICS_COLLECTED."""
        record = await service.create_admission("strat_001")
        updated = await service.collect_paper_metrics(
            record.admission_id,
            total_return_pct=12.5,
            max_drawdown_pct=5.0,
            sharpe_ratio=1.2,
            win_rate_pct=55.0,
            total_trades=45,
            trading_days=35,
            max_daily_loss_pct=1.5,
        )

        assert updated.status == AdmissionStatus.METRICS_COLLECTED
        assert updated.paper_sharpe_ratio == 1.2
        assert updated.paper_trading_days == 35

    @pytest.mark.asyncio
    async def test_evaluate_readiness_pass(self, service):
        """All checks pass, transitions to PENDING_REVIEW."""
        record = await service.create_admission("strat_001")
        await service.collect_paper_metrics(
            record.admission_id,
            total_return_pct=15.0,
            max_drawdown_pct=8.0,
            sharpe_ratio=1.5,
            win_rate_pct=60.0,
            total_trades=50,
            trading_days=30,
            max_daily_loss_pct=1.0,
        )
        updated = await service.evaluate_readiness(record.admission_id)

        assert updated.status == AdmissionStatus.PENDING_REVIEW
        assert updated.readiness_score > 0

    @pytest.mark.asyncio
    async def test_evaluate_readiness_insufficient_days(self, service):
        """Insufficient paper days still transitions but records failed check."""
        record = await service.create_admission("strat_001")
        await service.collect_paper_metrics(
            record.admission_id,
            total_return_pct=10.0,
            max_drawdown_pct=5.0,
            sharpe_ratio=1.0,
            win_rate_pct=55.0,
            total_trades=30,
            trading_days=10,  # Below 30-day minimum
            max_daily_loss_pct=1.0,
        )
        updated = await service.evaluate_readiness(record.admission_id)

        assert updated.status == AdmissionStatus.PENDING_REVIEW
        # Readiness should not be fully passed (insufficient days)
        assert updated.readiness_passed is False

    @pytest.mark.asyncio
    async def test_submit_for_approval(self):
        """Creates approval request, links to admission."""
        # Use a mock approval service to verify ID is assigned
        class FakeApprovalService:
            pass

        svc = PaperLiveAdmissionService(approval_service=FakeApprovalService())
        record = await svc.create_admission("strat_001")
        await svc.collect_paper_metrics(
            record.admission_id,
            total_return_pct=10.0,
            sharpe_ratio=1.0,
            trading_days=30,
            total_trades=30,
        )
        await svc.evaluate_readiness(record.admission_id)
        updated = await svc.submit_for_approval(record.admission_id)

        assert updated.approval_request_id  # Non-empty when approval service set

    @pytest.mark.asyncio
    async def test_process_approval_approved(self, service):
        """Decision recorded, admission APPROVED."""
        record = await service.create_admission("strat_001")
        await service.collect_paper_metrics(
            record.admission_id,
            total_return_pct=10.0,
            sharpe_ratio=1.0,
            trading_days=30,
            total_trades=30,
        )
        await service.evaluate_readiness(record.admission_id)
        await service.submit_for_approval(record.admission_id)
        updated = await service.process_approval_decision(
            record.admission_id,
            approver="admin",
            decision="approved",
            reason="All checks pass",
        )

        assert updated.status == AdmissionStatus.APPROVED
        assert updated.approver == "admin"
        assert updated.decided_at is not None

    @pytest.mark.asyncio
    async def test_process_approval_rejected(self, service):
        """Decision recorded, admission REJECTED."""
        record = await service.create_admission("strat_001")
        await service.collect_paper_metrics(
            record.admission_id,
            total_return_pct=10.0,
            sharpe_ratio=1.0,
            trading_days=30,
            total_trades=30,
        )
        await service.evaluate_readiness(record.admission_id)
        await service.submit_for_approval(record.admission_id)
        updated = await service.process_approval_decision(
            record.admission_id,
            approver="admin",
            decision="rejected",
            reason="Drawdown too high",
        )

        assert updated.status == AdmissionStatus.REJECTED
        assert updated.decision_reason == "Drawdown too high"

    @pytest.mark.asyncio
    async def test_collect_metrics_wrong_status(self, service):
        """Cannot collect metrics if not in PENDING_METRICS."""
        record = await service.create_admission("strat_001")
        await service.collect_paper_metrics(
            record.admission_id,
            total_return_pct=10.0,
            sharpe_ratio=1.0,
            trading_days=30,
            total_trades=30,
        )
        # Second call should fail
        with pytest.raises(ValueError, match="expected pending_metrics"):
            await service.collect_paper_metrics(
                record.admission_id,
                total_return_pct=15.0,
                sharpe_ratio=1.5,
                trading_days=35,
                total_trades=40,
            )

    @pytest.mark.asyncio
    async def test_unknown_admission(self, service):
        """Unknown admission ID raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await service.collect_paper_metrics("nonexistent")

    @pytest.mark.asyncio
    async def test_get_admission(self, service):
        """Can retrieve admission by ID."""
        record = await service.create_admission("strat_001")
        found = service.get_admission(record.admission_id)
        assert found is not None
        assert found.admission_id == record.admission_id

        assert service.get_admission("nonexistent") is None

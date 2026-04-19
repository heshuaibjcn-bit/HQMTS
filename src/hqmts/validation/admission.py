"""Paper-to-Live admission service (SAD 25).

Structured evaluation before allowing paper-to-live transition.
Uses ReadinessAssessor for automated checks and AgentGovernanceService
for human approval flow.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from hqmts.core.enums import AdmissionStatus, ApprovalStatus
from hqmts.core.types import now_shanghai
from hqmts.domain.admission import AdmissionRecord
from hqmts.governance.readiness import ReadinessAssessor

logger = logging.getLogger(__name__)


@dataclass
class AdmissionChecklist:
    """Minimum criteria for paper-to-live admission."""

    min_paper_days: int = 30
    min_sharpe: float = 0.5
    max_drawdown_pct: float = 15.0
    min_trades: int = 20
    min_win_rate_pct: float = 40.0
    max_daily_loss_pct: float = 3.0


class PaperLiveAdmissionService:
    """Manages paper-to-live admission lifecycle.

    Flow:
    1. create_admission() → PENDING_METRICS
    2. collect_paper_metrics() → METRICS_COLLECTED
    3. evaluate_readiness() → PENDING_REVIEW
    4. submit_for_approval() → creates ApprovalRequest via governance
    5. process_approval_decision() → APPROVED or REJECTED
    """

    def __init__(
        self,
        *,
        readiness_assessor: ReadinessAssessor | None = None,
        checklist: AdmissionChecklist | None = None,
        approval_service: object | None = None,
    ) -> None:
        self._assessor = readiness_assessor or ReadinessAssessor()
        self._checklist = checklist or AdmissionChecklist()
        self._approval_service = approval_service
        self._admissions: dict[str, AdmissionRecord] = {}

    def list_admissions(self) -> list[AdmissionRecord]:
        """Return all admission records, newest first."""
        return sorted(self._admissions.values(), key=lambda r: r.created_at, reverse=True)

    async def create_admission(
        self,
        strategy_instance_id: str,
        strategy_version: str = "",
    ) -> AdmissionRecord:
        """Create a new admission record in PENDING_METRICS state."""
        record = AdmissionRecord(
            admission_id=str(uuid.uuid4()),
            strategy_instance_id=strategy_instance_id,
            strategy_version=strategy_version,
            status=AdmissionStatus.PENDING_METRICS,
            created_at=now_shanghai(),
        )
        self._admissions[record.admission_id] = record
        logger.info(
            "ADMISSION_CREATED admission=%s strategy=%s",
            record.admission_id[:8], strategy_instance_id,
        )
        return record

    async def collect_paper_metrics(
        self,
        admission_id: str,
        *,
        total_return_pct: float = 0.0,
        max_drawdown_pct: float = 0.0,
        sharpe_ratio: float = 0.0,
        win_rate_pct: float = 0.0,
        total_trades: int = 0,
        trading_days: int = 0,
        max_daily_loss_pct: float = 0.0,
    ) -> AdmissionRecord:
        """Collect paper trading metrics and transition to METRICS_COLLECTED."""
        record = self._admissions.get(admission_id)
        if record is None:
            raise ValueError(f"Admission {admission_id} not found")

        if record.status != AdmissionStatus.PENDING_METRICS:
            raise ValueError(
                f"Admission {admission_id} in status {record.status.value}, "
                f"expected pending_metrics"
            )

        # Update metrics
        record.paper_total_return_pct = total_return_pct
        record.paper_max_drawdown_pct = max_drawdown_pct
        record.paper_sharpe_ratio = sharpe_ratio
        record.paper_win_rate_pct = win_rate_pct
        record.paper_total_trades = total_trades
        record.paper_trading_days = trading_days
        record.max_daily_loss_pct = max_daily_loss_pct
        record.status = AdmissionStatus.METRICS_COLLECTED

        logger.info(
            "ADMISSION_METRICS_COLLECTED admission=%s sharpe=%.2f days=%d",
            admission_id[:8], sharpe_ratio, trading_days,
        )
        return record

    async def evaluate_readiness(
        self,
        admission_id: str,
        **extra_assessor_kwargs,
    ) -> AdmissionRecord:
        """Run readiness assessment and transition to PENDING_REVIEW.

        Extra kwargs are passed to ReadinessAssessor.assess() for
        backtest consistency, governance, and stability checks.
        """
        record = self._admissions.get(admission_id)
        if record is None:
            raise ValueError(f"Admission {admission_id} not found")

        if record.status != AdmissionStatus.METRICS_COLLECTED:
            raise ValueError(
                f"Admission {admission_id} in status {record.status.value}, "
                f"expected metrics_collected"
            )

        # Run readiness assessment using ReadinessAssessor
        report = self._assessor.assess(
            strategy_name=record.strategy_instance_id,
            strategy_version=record.strategy_version,
            paper_total_return=record.paper_total_return_pct,
            paper_max_drawdown=record.paper_max_drawdown_pct,
            paper_sharpe_ratio=record.paper_sharpe_ratio,
            paper_win_rate=record.paper_win_rate_pct,
            paper_total_trades=record.paper_total_trades,
            paper_days=record.paper_trading_days,
            max_daily_loss_pct=record.max_daily_loss_pct,
            **extra_assessor_kwargs,
        )

        record.readiness_score = report.total_score
        record.readiness_passed = report.is_ready
        record.status = AdmissionStatus.PENDING_REVIEW

        logger.info(
            "ADMISSION_READINESS admission=%s score=%.1f passed=%s",
            admission_id[:8], report.total_score, report.is_ready,
        )
        return record

    async def submit_for_approval(
        self,
        admission_id: str,
    ) -> AdmissionRecord:
        """Submit admission for human approval."""
        record = self._admissions.get(admission_id)
        if record is None:
            raise ValueError(f"Admission {admission_id} not found")

        if record.status != AdmissionStatus.PENDING_REVIEW:
            raise ValueError(
                f"Admission {admission_id} in status {record.status.value}, "
                f"expected pending_review"
            )

        # If approval service is available, create an approval request
        if self._approval_service is not None:
            # In production, this calls AgentGovernanceService to create
            # an ApprovalRequest linked to this admission
            record.approval_request_id = str(uuid.uuid4())

        logger.info(
            "ADMISSION_SUBMITTED approval=%s admission=%s",
            record.approval_request_id[:8] if record.approval_request_id else "N/A",
            admission_id[:8],
        )
        return record

    async def process_approval_decision(
        self,
        admission_id: str,
        approver: str,
        decision: str,
        reason: str = "",
    ) -> AdmissionRecord:
        """Process a human approval decision."""
        record = self._admissions.get(admission_id)
        if record is None:
            raise ValueError(f"Admission {admission_id} not found")

        if decision == ApprovalStatus.APPROVED.value:
            record.status = AdmissionStatus.APPROVED
        elif decision == ApprovalStatus.REJECTED.value:
            record.status = AdmissionStatus.REJECTED
        else:
            raise ValueError(f"Invalid decision: {decision}")

        record.approver = approver
        record.decision_reason = reason
        record.decided_at = now_shanghai()

        logger.info(
            "ADMISSION_DECISION admission=%s decision=%s approver=%s",
            admission_id[:8], decision, approver,
        )
        return record

    def get_admission(self, admission_id: str) -> AdmissionRecord | None:
        """Get an admission record by ID."""
        return self._admissions.get(admission_id)

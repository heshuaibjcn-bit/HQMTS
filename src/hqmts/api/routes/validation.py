"""Validation API routes (SAD 25)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from hqmts.core.enums import AdmissionStatus
from hqmts.validation.admission import PaperLiveAdmissionService

router = APIRouter(prefix="/validation", tags=["validation"])

# ── In-memory admission store (production: use DB session) ────────────────
_svc = PaperLiveAdmissionService()


class CreateAdmissionRequest(BaseModel):
    strategy_instance_id: str
    strategy_version: str = ""


class CollectMetricsRequest(BaseModel):
    total_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate_pct: float = 0.0
    total_trades: int = 0
    trading_days: int = 0
    max_daily_loss_pct: float = 0.0


class ApproveAdmissionRequest(BaseModel):
    approver: str
    decision: str  # approved, rejected
    reason: str = ""


def _admission_to_dict(record) -> dict:
    return {
        "admission_id": record.admission_id,
        "strategy_instance_id": record.strategy_instance_id,
        "strategy_version": record.strategy_version,
        "status": record.status.value,
        "paper_sharpe_ratio": record.paper_sharpe_ratio,
        "paper_trading_days": record.paper_trading_days,
        "readiness_score": record.readiness_score,
        "readiness_passed": record.readiness_passed,
        "approver": record.approver,
        "decision_reason": record.decision_reason,
        "created_at": record.created_at.isoformat(),
        "decided_at": record.decided_at.isoformat() if record.decided_at else None,
    }


@router.post("/admission")
async def create_admission(req: CreateAdmissionRequest) -> dict:
    """Create a paper-to-live admission record."""
    record = await _svc.create_admission(
        strategy_instance_id=req.strategy_instance_id,
        strategy_version=req.strategy_version,
    )
    return _admission_to_dict(record)


@router.get("/admission/{admission_id}")
async def get_admission(admission_id: str) -> dict:
    """Get admission record by ID."""
    record = _svc.get_admission(admission_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Admission not found")
    return _admission_to_dict(record)


@router.post("/admission/{admission_id}/metrics")
async def collect_metrics(
    admission_id: str,
    req: CollectMetricsRequest,
) -> dict:
    """Collect paper trading metrics for an admission."""
    try:
        record = await _svc.collect_paper_metrics(
            admission_id,
            total_return_pct=req.total_return_pct,
            max_drawdown_pct=req.max_drawdown_pct,
            sharpe_ratio=req.sharpe_ratio,
            win_rate_pct=req.win_rate_pct,
            total_trades=req.total_trades,
            trading_days=req.trading_days,
            max_daily_loss_pct=req.max_daily_loss_pct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _admission_to_dict(record)


@router.post("/admission/{admission_id}/evaluate")
async def evaluate_readiness(admission_id: str) -> dict:
    """Run readiness assessment for an admission."""
    try:
        record = await _svc.evaluate_readiness(admission_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _admission_to_dict(record)


@router.post("/admission/{admission_id}/approve")
async def approve_admission(
    admission_id: str,
    req: ApproveAdmissionRequest,
) -> dict:
    """Process approval decision for an admission."""
    try:
        record = await _svc.process_approval_decision(
            admission_id,
            approver=req.approver,
            decision=req.decision,
            reason=req.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _admission_to_dict(record)

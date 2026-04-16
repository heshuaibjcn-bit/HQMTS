"""Risk API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.db.models.risk import RiskCheckResultORM
from hqmts.db.repositories.base import BaseRepository

router = APIRouter(prefix="/risk", tags=["risk"])


def _risk_check_to_dict(r: RiskCheckResultORM) -> dict:
    return {
        "risk_check_id": r.risk_check_id,
        "signal_id": r.signal_id,
        "result_type": r.result_type,
        "reject_reason": r.reject_reason,
        "triggered_rules": r.triggered_rules,
        "check_time": r.check_time.isoformat() if r.check_time else None,
    }


@router.get("/status")
async def get_risk_status(db: AsyncSession = Depends(get_db)) -> dict:
    """Get current risk status across all layers."""
    repo = BaseRepository(RiskCheckResultORM, db)
    recent = await repo.get_many(limit=10)
    return {
        "market": {"status": "normal"},
        "account": {"status": "normal"},
        "strategy": [],
        "instrument": [],
        "order": {"status": "normal"},
        "recent_checks": [_risk_check_to_dict(r) for r in recent],
    }


@router.get("/checks/{risk_check_id}")
async def get_risk_check(
    risk_check_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get risk check result details."""
    repo = BaseRepository(RiskCheckResultORM, db)
    result = await repo.get_by_id(risk_check_id, id_column="risk_check_id")
    if result is None:
        raise HTTPException(status_code=404, detail="Risk check not found")
    return _risk_check_to_dict(result)

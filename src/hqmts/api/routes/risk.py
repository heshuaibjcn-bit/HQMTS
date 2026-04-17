"""Risk API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.core.enums import FlattenTrigger
from hqmts.db.models.risk import RiskCheckResultORM
from hqmts.db.repositories.base import BaseRepository
from hqmts.risk.final_check import FinalPreSubmitCheck
from hqmts.risk.force_flatten import ForceFlattenService

router = APIRouter(prefix="/risk", tags=["risk"])

# ── In-memory active flatten tracking (production: use DB) ────────────────
_active_flattens: dict[str, dict] = {}


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


# ── Force Flatten endpoints (SAD 18.3) ───────────────────────────────────


class FlattenRequest(BaseModel):
    trigger: str  # kill_switch, max_drawdown, manual_command, risk_rule
    reason: str
    account_id: str = ""


@router.post("/flatten")
async def trigger_force_flatten(
    req: FlattenRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger force flatten for all open positions.

    Bypasses signal flow, passes FinalPreSubmitCheck with is_flatten=True.
    """
    try:
        trigger = FlattenTrigger(req.trigger)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trigger: {req.trigger}. "
            f"Valid: {', '.join(t.value for t in FlattenTrigger)}",
        )

    svc = ForceFlattenService(
        final_check=FinalPreSubmitCheck(),
        account_id=req.account_id,
    )
    progress = await svc.execute_flatten(trigger, req.reason)

    result = {
        "flatten_id": progress.flatten_id,
        "trigger": progress.trigger.value,
        "total_positions": progress.total_positions,
        "flattened": progress.flattened_positions,
        "failed": progress.failed_positions,
        "skipped_t1": progress.skipped_positions,
        "is_complete": progress.is_complete,
    }
    _active_flattens[progress.flatten_id] = result
    return result


@router.get("/flatten/{flatten_id}")
async def get_flatten_progress(flatten_id: str) -> dict:
    """Get force flatten progress by ID."""
    if flatten_id not in _active_flattens:
        raise HTTPException(status_code=404, detail="Flatten not found")
    return _active_flattens[flatten_id]

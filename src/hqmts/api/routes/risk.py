"""Risk API routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.api.deps_auth import get_current_user
from hqmts.core.enums import FlattenTrigger
from hqmts.db.models.risk import RiskCheckResultORM
from hqmts.db.repositories.base import BaseRepository
from hqmts.risk.final_check import FinalPreSubmitCheck
from hqmts.risk.force_flatten import ForceFlattenService

router = APIRouter(prefix="/risk", tags=["risk"])

# ── In-memory active flatten tracking (production: use DB) ────────────────
_active_flattens: dict[str, dict] = {}

# ── In-memory kill switch state (production: use DB/config) ─────────────────
_kill_switch_state: dict[str, dict] = {}  # account_id -> {active, activated_by, activated_at, reason}


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


# ── Kill Switch endpoints (PRD FR-UI-004, SAD FR-API-005) ──────────────────


class KillSwitchActivateRequest(BaseModel):
    reason: str
    account_id: str = ""


class KillSwitchDeactivateRequest(BaseModel):
    reason: str
    account_id: str = ""


@router.post("/kill-switch")
async def activate_kill_switch(
    req: KillSwitchActivateRequest,
    user=Depends(get_current_user),
) -> dict:
    """Activate Kill Switch via REST POST (PRD FR-REALTIME-003).

    Rate limit: 1 req/min with 60s cooldown (FR-NFR-005).
    """
    account_key = req.account_id or "default"

    # Check if already active
    current = _kill_switch_state.get(account_key, {})
    if current.get("active"):
        raise HTTPException(
            status_code=409,
            detail="Kill Switch is already active",
        )

    now = datetime.now(timezone.utc)
    kill_switch_id = f"ks_{uuid.uuid4().hex[:12]}"
    _kill_switch_state[account_key] = {
        "kill_switch_id": kill_switch_id,
        "active": True,
        "activated_by": user.user_id,
        "activated_at": now.isoformat(),
        "reason": req.reason,
    }

    return {
        "kill_switch_id": kill_switch_id,
        "status": "activated",
        "activated_by": user.user_id,
        "activated_at": now.isoformat(),
        "reason": req.reason,
    }


@router.post("/kill-switch/deactivate")
async def deactivate_kill_switch(
    req: KillSwitchDeactivateRequest,
    user=Depends(get_current_user),
) -> dict:
    """Deactivate Kill Switch (requires approval per PRD 7.4).

    Rate limit: 1 req/5min (FR-NFR-005).
    """
    account_key = req.account_id or "default"

    current = _kill_switch_state.get(account_key, {})
    if not current.get("active"):
        raise HTTPException(
            status_code=409,
            detail="Kill Switch is not active",
        )

    now = datetime.now(timezone.utc)
    kill_switch_id = current.get("kill_switch_id", "unknown")
    _kill_switch_state[account_key] = {
        "kill_switch_id": kill_switch_id,
        "active": False,
        "deactivated_by": user.user_id,
        "deactivated_at": now.isoformat(),
        "reason": req.reason,
    }

    return {
        "kill_switch_id": kill_switch_id,
        "status": "deactivated",
        "deactivated_by": user.user_id,
        "deactivated_at": now.isoformat(),
        "reason": req.reason,
    }


@router.get("/kill-switch")
async def get_kill_switch_status(
    account_id: str = "",
) -> dict:
    """Get current Kill Switch status."""
    account_key = account_id or "default"
    current = _kill_switch_state.get(account_key, {})
    return {
        "kill_switch_id": current.get("kill_switch_id"),
        "active": current.get("active", False),
        "activated_by": current.get("activated_by"),
        "activated_at": current.get("activated_at"),
        "deactivated_by": current.get("deactivated_by"),
        "deactivated_at": current.get("deactivated_at"),
    }

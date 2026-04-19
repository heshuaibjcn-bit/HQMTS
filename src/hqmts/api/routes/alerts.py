"""Alerts API route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.api.deps_auth import get_current_user
from hqmts.db.models.alert import AlertAcknowledgmentORM
from hqmts.db.repositories.alert_repo import AlertAcknowledgmentRepository, AlertRepository

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AcknowledgeRequest(BaseModel):
    note: str = ""


def _alert_to_dict(a) -> dict:
    return {
        "alert_id": a.alert_id,
        "rule_name": a.rule_name,
        "level": a.level,
        "metric": a.metric,
        "value": float(a.value),
        "threshold": float(a.threshold),
        "message": a.message,
        "acknowledged": a.acknowledged,
        "detected_at": a.detected_at.isoformat() if a.detected_at else None,
        "routing_target": a.routing_target,
    }


@router.get("")
async def get_alerts(
    level: str | None = Query(None, description="Filter by level (P0/P1/P2/P3)"),
    acknowledged: bool | None = Query(None, description="Filter by acknowledged status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Get alerts with optional filtering (FR-API-004)."""
    repo = AlertRepository(db)
    alerts = await repo.get_many(
        level=level,
        acknowledged=acknowledged,
        limit=limit,
        offset=offset,
    )
    return {
        "alerts": [_alert_to_dict(a) for a in alerts],
        "total": len(alerts),
    }


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    req: AcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Acknowledge an alert."""
    alert_repo = AlertRepository(db)
    alert = await alert_repo.get_by_id(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.acknowledged:
        raise HTTPException(status_code=409, detail="Alert already acknowledged")

    await alert_repo.mark_acknowledged(alert_id)

    ack_repo = AlertAcknowledgmentRepository(db)
    ack = AlertAcknowledgmentORM(
        alert_id=alert_id,
        acknowledged_by=user.user_id,
        note=req.note,
    )
    await ack_repo.create(ack)

    alert = await alert_repo.get_by_id(alert_id)
    return _alert_to_dict(alert)

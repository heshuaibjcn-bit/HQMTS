"""Audit API routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.db.repositories.audit_repo import AuditRepository

router = APIRouter(prefix="/audit", tags=["audit"])


def _event_to_dict(e) -> dict:
    return {
        "audit_event_id": e.audit_event_id,
        "event_type": e.event_type,
        "entity_type": e.entity_type,
        "entity_id": e.entity_id,
        "environment": e.environment,
        "actor": e.actor,
        "action": e.action,
        "alert_level": e.alert_level,
        "correlation_id": e.correlation_id,
        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
    }


@router.get("/events")
async def list_audit_events(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    correlation_id: str | None = Query(None),
    start_time: datetime | None = Query(None),
    end_time: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List audit events with filtering."""
    repo = AuditRepository(db)

    if correlation_id:
        events = await repo.get_by_correlation_id(correlation_id)
    elif entity_type and entity_id:
        events = await repo.get_by_entity(entity_type, entity_id)
    elif start_time and end_time:
        events = await repo.get_by_time_range(start_time, end_time)
    else:
        events = []

    # Apply limit
    events = events[:limit]
    return {"events": [_event_to_dict(e) for e in events], "total": len(events)}


@router.get("/trace/{entity_type}/{entity_id}")
async def get_audit_trace(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get full audit trace for an entity."""
    repo = AuditRepository(db)
    events = await repo.get_by_entity(entity_type, entity_id)
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "events": [_event_to_dict(e) for e in events],
        "total": len(events),
    }

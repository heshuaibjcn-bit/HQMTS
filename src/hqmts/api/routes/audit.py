"""Audit API routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


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
    return {"events": [], "total": 0}


@router.get("/trace/{entity_type}/{entity_id}")
async def get_audit_trace(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get full audit trace for an entity."""
    return {"entity_type": entity_type, "entity_id": entity_id, "events": []}

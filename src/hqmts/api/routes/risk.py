"""Risk API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from hqmts.api.deps import get_db

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/status")
async def get_risk_status(db=Depends(get_db)) -> dict:
    """Get current risk status across all layers."""
    return {
        "market": {"status": "normal"},
        "account": {"status": "normal"},
        "strategy": [],
        "instrument": [],
        "order": {"status": "normal"},
    }


@router.get("/checks/{risk_check_id}")
async def get_risk_check(risk_check_id: str, db=Depends(get_db)) -> dict:
    """Get risk check result details."""
    return {"risk_check_id": risk_check_id}

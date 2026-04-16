"""Audit middleware for FastAPI (SAD 26).

Persists every write operation (POST, PUT, PATCH, DELETE) as an immutable
AuditEventORM row. Uses fire-and-forget via ``asyncio.create_task`` so the
audit write never blocks the response.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from hqmts.db.models.audit import AuditEventORM
from hqmts.db.repositories.audit_repo import AuditRepository

logger = logging.getLogger(__name__)

# Map URL path prefixes to entity_type values stored in audit_events.
_ENTITY_MAP: dict[str, str] = {
    "instruments": "instrument",
    "signals": "signal",
    "orders": "order",
    "strategies": "strategy",
    "audit": "audit_event",
    "risk": "risk_check",
}


_COLLECTION_KEYWORDS = {"checks", "events", "instances", "trace", "status"}


def _extract_entity(path: str) -> tuple[str, str]:
    """Return (entity_type, entity_id) from a URL path.

    Examples::

        /api/v1/orders/abc123       -> ("order", "abc123")
        /api/v1/orders              -> ("order", "")
        /api/v1/risk/checks/rc-42   -> ("risk_check", "rc-42")
        /api/v1/strategies/s1/instances -> ("strategy", "s1")
        /health                     -> ("", "")
    """
    parts = [p for p in path.split("/") if p]
    start = 0
    for i, p in enumerate(parts):
        if p in _ENTITY_MAP:
            start = i
            break
    else:
        return ("", "")

    prefix = parts[start]
    entity_type = _ENTITY_MAP.get(prefix, prefix)

    remaining = parts[start + 1 :]
    if not remaining:
        return (entity_type, "")

    # If the first remaining segment is a collection keyword (e.g. "checks",
    # "instances"), the actual entity_id is the next segment.
    if remaining[0] in _COLLECTION_KEYWORDS:
        entity_id = remaining[1] if len(remaining) > 1 else ""
    else:
        entity_id = remaining[0]

    return (entity_type, entity_id)


async def _persist_audit(
    session_factory,
    event: AuditEventORM,
) -> None:
    """Fire-and-forget task: write the audit event, swallow errors."""
    try:
        async with session_factory() as session:
            repo = AuditRepository(session)
            await repo.create(event)
            await session.commit()
    except Exception:
        logger.exception("Failed to persist audit event %s", event.audit_event_id)


class AuditMiddleware(BaseHTTPMiddleware):
    """Records all write operations (POST, PUT, PATCH, DELETE) as audit events."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        correlation_id = request.headers.get(
            "X-Correlation-ID", str(uuid.uuid4())
        )
        request.state.correlation_id = correlation_id

        start_time = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start_time) * 1000

        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            entity_type, entity_id = _extract_entity(str(request.url.path))

            event = AuditEventORM(
                audit_event_id=str(uuid.uuid4()),
                event_type="api_request",
                entity_type=entity_type or "unknown",
                entity_id=entity_id or str(uuid.uuid4()),
                environment=getattr(
                    request.app.state, "_env", "development"
                ) or "development",
                actor=request.headers.get("X-Actor", "anonymous"),
                action=f"{request.method} {request.url.path}",
                details_json=json.dumps(
                    {
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2),
                    }
                ),
                alert_level="P3",
                correlation_id=correlation_id,
                timestamp=datetime.now(timezone.utc),
            )

            # Fire-and-forget: don't block the response for audit writes
            session_factory = request.app.state.db_session_factory
            asyncio.create_task(_persist_audit(session_factory, event))

            response.headers["X-Correlation-ID"] = correlation_id

        return response

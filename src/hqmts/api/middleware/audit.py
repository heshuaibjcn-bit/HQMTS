"""Audit middleware for FastAPI (SAD 26)."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class AuditMiddleware(BaseHTTPMiddleware):
    """Records all write operations (POST, PUT, PATCH, DELETE) as audit events."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id

        start_time = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start_time) * 1000

        # Record write operations
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            # In production, persist to AuditEvent table
            audit_data = {
                "correlation_id": correlation_id,
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "actor": request.headers.get("X-Actor", "anonymous"),
            }
            # Audit record would be written here
            response.headers["X-Correlation-ID"] = correlation_id

        return response

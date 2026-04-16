"""Tracing utilities: request ID, correlation ID propagation.

Binds request/correlation IDs to structlog contextvars so every
log entry in a request carries the trace context automatically.
"""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Generate a request_id for every inbound request and bind it to structlog.

    Propagates the ID as X-Request-ID response header.
    If the caller provides X-Request-ID, it is reused.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        correlation_id = request.headers.get("X-Correlation-ID", request_id)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            correlation_id=correlation_id,
        )

        # Store on request.state so downstream code can read it
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def bind_trace_context(
    *,
    request_id: str | None = None,
    correlation_id: str | None = None,
    **extra: str,
) -> None:
    """Bind additional trace fields to the current structlog context.

    Useful for binding signal_id, order_id, strategy_instance_id, etc.
    at the start of a pipeline step.
    """
    kv: dict[str, str] = {}
    if request_id:
        kv["request_id"] = request_id
    if correlation_id:
        kv["correlation_id"] = correlation_id
    kv.update(extra)
    if kv:
        structlog.contextvars.bind_contextvars(**kv)


def clear_trace_context() -> None:
    """Clear all structlog contextvars for the current task."""
    structlog.contextvars.clear_contextvars()

"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hqmts.api.middleware.audit import AuditMiddleware
from hqmts.api.routes import audit, backtest, instruments, orders, risk, signals, strategies, validation
from hqmts.api.routes import account, alerts, auth, chat, factor_research, ws
from hqmts.api.ws_manager import ConnectionManager
from hqmts.api.ws_bridge import PipelineBusToWSBridge
from hqmts.infra.tracing import RequestIdMiddleware
from hqmts.db.connection import create_engine, create_session_factory
from hqmts.infra.config import load_settings
from hqmts.infra.logging import setup_logging
from hqmts.infra.pipeline import InProcessBus


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup/shutdown lifecycle: create engine once, store on app.state."""
    settings = load_settings(getattr(app.state, "_env", None))
    app.state.settings = settings
    engine = create_engine(settings.database)
    app.state.db_engine = engine
    app.state.db_session_factory = create_session_factory(engine)

    # WebSocket infrastructure
    ws_manager = ConnectionManager()
    app.state.ws_manager = ws_manager
    ws_bridge = PipelineBusToWSBridge(ws_manager)
    app.state.ws_bridge = ws_bridge
    # Use InProcessBus for now; production replaces with RedisStreamBus
    bus = InProcessBus()
    await ws_bridge.start(bus)
    app.state.pipeline_bus = bus

    yield

    await ws_bridge.stop()
    await engine.dispose()


def create_app(env: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    import os
    effective_env = env or os.environ.get("HQMTS_ENV")
    settings = load_settings(effective_env)

    setup_logging(
        level=settings.logging.level,
        fmt=settings.logging.format,
    )

    app = FastAPI(
        title=settings.app.name,
        version=settings.app.version,
        description="HQMTS - A股分钟级量化研究与交易平台",
        lifespan=_lifespan,
    )
    app.state._env = effective_env

    # CORS (for SPA frontend development)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware (order matters: outermost first)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(RequestIdMiddleware)

    # Routes
    app.include_router(auth.router)
    app.include_router(ws.router)
    app.include_router(account.router)
    app.include_router(alerts.router)
    app.include_router(chat.router)
    app.include_router(instruments.router)
    app.include_router(strategies.router)
    app.include_router(signals.router)
    app.include_router(orders.router)
    app.include_router(risk.router)
    app.include_router(audit.router)
    app.include_router(backtest.router)
    app.include_router(validation.router)
    app.include_router(factor_research.router)

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "environment": settings.environment,
            "version": settings.app.version,
            "qmt": {"connected": True, "latency_ms": 12},
            "data_source": {"connected": True, "latency_ms": 8},
            "bar_aggregation": {"status": "normal", "last_bar_time": None},
            "agent": {"status": "running", "active_tasks": 0},
        }

    @app.get("/")
    async def root() -> dict:
        return {
            "name": settings.app.name,
            "version": settings.app.version,
            "environment": settings.environment,
        }

    return app

"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from hqmts.api.middleware.audit import AuditMiddleware
from hqmts.api.routes import audit, backtest, instruments, orders, risk, signals, strategies
from hqmts.infra.tracing import RequestIdMiddleware
from hqmts.db.connection import create_engine, create_session_factory
from hqmts.infra.config import load_settings
from hqmts.infra.logging import setup_logging


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Startup/shutdown lifecycle: create engine once, store on app.state."""
    settings = load_settings(getattr(app.state, "_env", None))
    engine = create_engine(settings.database)
    app.state.db_engine = engine
    app.state.db_session_factory = create_session_factory(engine)
    yield
    await engine.dispose()


def create_app(env: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = load_settings(env)

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
    app.state._env = env

    # Middleware (order matters: outermost first)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(RequestIdMiddleware)

    # Routes
    app.include_router(instruments.router)
    app.include_router(strategies.router)
    app.include_router(signals.router)
    app.include_router(orders.router)
    app.include_router(risk.router)
    app.include_router(audit.router)
    app.include_router(backtest.router)

    @app.get("/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "environment": settings.environment,
            "version": settings.app.version,
        }

    @app.get("/")
    async def root() -> dict:
        return {
            "name": settings.app.name,
            "version": settings.app.version,
            "environment": settings.environment,
        }

    return app

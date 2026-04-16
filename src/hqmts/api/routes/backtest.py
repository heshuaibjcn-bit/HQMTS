"""Backtest API routes."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.db.repositories.backtest_repo import BacktestResultRepository

router = APIRouter(prefix="/backtest", tags=["backtest"])

# Strategy registry: maps strategy_name to (class, default_params)
_STRATEGY_REGISTRY: dict[str, tuple[type, dict[str, Any]]] = {}


def register_strategy(name: str, strategy_class: type, default_params: dict[str, Any] | None = None) -> None:
    """Register a strategy class for use via the API."""
    _STRATEGY_REGISTRY[name] = (strategy_class, default_params or {})


# Auto-register built-in strategies
try:
    from hqmts.backtest.strategy import DualMACrossoverStrategy
    register_strategy("dual_ma", DualMACrossoverStrategy, {"fast_period": 5, "slow_period": 20})
except ImportError:
    pass


# ── Request/Response Models ──────────────────────────────────────────────────


class BacktestRunRequest(BaseModel):
    """Request to trigger a backtest run."""

    strategy_name: str = Field(min_length=1, max_length=64)
    strategy_version: str = Field(default="v1")
    strategy_params: dict[str, Any] = Field(default_factory=dict)
    instruments: list[str] = Field(min_length=1)
    cycle: str = Field(default="5m")
    start_date: str = Field(pattern=r"^\d{8}$")
    end_date: str = Field(pattern=r"^\d{8}$")
    initial_cash: Decimal = Field(default=Decimal("1000000"))
    bars: dict[str, list[dict[str, Any]]] = Field(
        default_factory=dict,
        description="Optional pre-loaded bar data. If empty, runs with no bars (empty result).",
    )


class BacktestSummaryResponse(BaseModel):
    """Summary of a backtest result."""

    backtest_id: str
    strategy_name: str
    strategy_version: str
    instruments: list[str]
    cycle: str
    start_date: str
    end_date: str
    initial_cash: str
    final_total_asset: str
    total_return: str
    annualized_return: str
    max_drawdown: str
    sharpe_ratio: str
    total_trades: int
    win_rate: str
    profit_factor: str
    created_at: str | None = None


class BacktestDetailResponse(BacktestSummaryResponse):
    """Full backtest result including trades and daily values."""

    trades: list[dict[str, Any]] = []
    daily_values: list[dict[str, Any]] = []
    cost_summary: dict[str, Any] = {}
    strategy_params: dict[str, Any] = {}


# ── Routes ────────────────────────────────────────────────────────────────────


def _result_to_response(result: Any) -> BacktestSummaryResponse:
    """Convert BacktestResult to API response."""
    return BacktestSummaryResponse(
        backtest_id=result.backtest_id,
        strategy_name=result.strategy_name,
        strategy_version=result.strategy_version,
        instruments=result.instruments,
        cycle=result.cycle,
        start_date=result.start_date,
        end_date=result.end_date,
        initial_cash=str(result.initial_cash),
        final_total_asset=str(result.final_total_asset),
        total_return=str(result.total_return),
        annualized_return=str(result.annualized_return),
        max_drawdown=str(result.max_drawdown),
        sharpe_ratio=str(result.sharpe_ratio),
        total_trades=result.total_trades,
        win_rate=str(result.win_rate),
        profit_factor=str(result.profit_factor),
        created_at=result.created_at.isoformat() if result.created_at else None,
    )


@router.post("/run", response_model=BacktestSummaryResponse)
async def run_backtest(
    request: BacktestRunRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Run a backtest synchronously and return results.

    Accepts pre-loaded bar data in the request body. If no bars provided,
    returns an empty result. Strategy must be registered in the strategy registry.
    """
    # Resolve strategy
    if request.strategy_name not in _STRATEGY_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy: {request.strategy_name}. "
                   f"Available: {list(_STRATEGY_REGISTRY.keys())}",
        )

    strategy_class, default_params = _STRATEGY_REGISTRY[request.strategy_name]
    merged_params = {**default_params, **request.strategy_params}

    # Build bar data from request
    bars_by_instrument: dict[str, list] = {}
    if request.bars:
        from hqmts.core.enums import Cycle
        from hqmts.core.types import InstrumentId, VersionStr
        from hqmts.domain.bar import Bar

        cycle_map = {"1m": Cycle.M1, "5m": Cycle.M5, "15m": Cycle.M15, "30m": Cycle.M30, "60m": Cycle.M60}
        cycle = cycle_map.get(request.cycle, Cycle.M5)

        for iid, raw_bars in request.bars.items():
            built_bars: list[Bar] = []
            for rb in raw_bars:
                from datetime import timedelta
                start = datetime.fromisoformat(rb.get("bar_start_time", rb.get("start_time", "")))
                end = rb.get("bar_end_time")
                if end:
                    end = datetime.fromisoformat(end) if isinstance(end, str) else end
                else:
                    mins = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "60m": 60}.get(request.cycle, 5)
                    end = start + timedelta(minutes=mins)

                built_bars.append(Bar(
                    instrument_id=InstrumentId(iid),
                    cycle=cycle,
                    bar_start_time=start,
                    bar_end_time=end,
                    open=Decimal(str(rb.get("open", "0"))),
                    high=Decimal(str(rb.get("high", "0"))),
                    low=Decimal(str(rb.get("low", "0"))),
                    close=Decimal(str(rb.get("close", "0"))),
                    volume=int(rb.get("volume", 0)),
                    amount=Decimal(str(rb.get("amount", "0"))),
                    is_completed=rb.get("is_completed", True),
                    source=rb.get("source", "api"),
                    data_version=VersionStr(rb.get("data_version", "v1")),
                ))
            bars_by_instrument[iid] = built_bars

    # Build instruments
    from hqmts.domain.instrument import Instrument
    instruments = [
        Instrument(
            instrument_id=InstrumentId(iid),
            ts_code=iid,
            exchange="SZSE",
            symbol=iid.split(".")[0],
            name=iid,
        )
        for iid in request.instruments
    ]

    # Run engine
    from hqmts.backtest.engine import BacktestConfig, BacktestEngine
    from hqmts.core.enums import Cycle

    cycle_map = {"1m": Cycle.M1, "5m": Cycle.M5, "15m": Cycle.M15, "30m": Cycle.M30, "60m": Cycle.M60}
    config = BacktestConfig(
        strategy=strategy_class(),
        strategy_name=request.strategy_name,
        strategy_version=request.strategy_version,
        strategy_params=merged_params,
        instruments=instruments,
        cycle=cycle_map.get(request.cycle, Cycle.M5),
        start_date=request.start_date,
        end_date=request.end_date,
        initial_cash=request.initial_cash,
    )

    engine = BacktestEngine(config)
    result = engine.run(bars_by_instrument)

    # Persist result
    try:
        repo = BacktestResultRepository(db)
        await repo.save(result)
        await db.commit()
    except Exception:
        await db.rollback()
        # Return result even if persist fails

    return _result_to_response(result)


@router.get("/{backtest_id}", response_model=BacktestDetailResponse)
async def get_backtest_result(
    backtest_id: str,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get a backtest result by ID."""
    repo = BacktestResultRepository(db)
    result = await repo.get_by_backtest_id(backtest_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Backtest result not found")

    return BacktestDetailResponse(
        backtest_id=result.backtest_id,
        strategy_name=result.strategy_name,
        strategy_version=result.strategy_version,
        instruments=result.instruments,
        cycle=result.cycle,
        start_date=result.start_date,
        end_date=result.end_date,
        initial_cash=str(result.initial_cash),
        final_total_asset=str(result.final_total_asset),
        total_return=str(result.total_return),
        annualized_return=str(result.annualized_return),
        max_drawdown=str(result.max_drawdown),
        sharpe_ratio=str(result.sharpe_ratio),
        total_trades=result.total_trades,
        win_rate=str(result.win_rate),
        profit_factor=str(result.profit_factor),
        created_at=result.created_at.isoformat() if result.created_at else None,
        trades=result.trades,
        daily_values=result.daily_values,
        cost_summary=result.cost_summary,
        strategy_params=result.strategy_params,
    )


@router.get("/", response_model=list[BacktestSummaryResponse])
async def list_backtest_results(
    strategy_name: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """List recent backtest results, optionally filtered by strategy."""
    repo = BacktestResultRepository(db)

    if strategy_name:
        results = await repo.get_by_strategy(strategy_name, limit=limit)
    else:
        results = await repo.get_many(limit=limit)
        # Convert ORM objects if get_many returns ORM
        from hqmts.db.models.backtest import BacktestResultORM
        from hqmts.db.repositories.backtest_repo import _orm_to_result

        results = [_orm_to_result(r) for r in results if isinstance(r, BacktestResultORM)]

    return [
        BacktestSummaryResponse(
            backtest_id=r.backtest_id,
            strategy_name=r.strategy_name,
            strategy_version=r.strategy_version,
            instruments=r.instruments,
            cycle=r.cycle,
            start_date=r.start_date,
            end_date=r.end_date,
            initial_cash=str(r.initial_cash),
            final_total_asset=str(r.final_total_asset),
            total_return=str(r.total_return),
            annualized_return=str(r.annualized_return),
            max_drawdown=str(r.max_drawdown),
            sharpe_ratio=str(r.sharpe_ratio),
            total_trades=r.total_trades,
            win_rate=str(r.win_rate),
            profit_factor=str(r.profit_factor),
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in results
    ]

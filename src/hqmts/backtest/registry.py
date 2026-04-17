"""Shared strategy registry and constants for backtest system."""

from __future__ import annotations

from typing import Any

from hqmts.core.enums import Cycle

# Cycle string → Cycle enum mapping (single source of truth)
CYCLE_MAP: dict[str, Cycle] = {
    "1m": Cycle.M1,
    "5m": Cycle.M5,
    "15m": Cycle.M15,
    "30m": Cycle.M30,
    "60m": Cycle.M60,
}

VALID_CYCLE_STRINGS: set[str] = set(CYCLE_MAP.keys())

# Cycle string → minutes per bar (single source of truth)
CYCLE_MINUTES_MAP: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "60m": 60,
}

# Strategy registry: maps strategy_name to (class, default_params)
STRATEGY_REGISTRY: dict[str, tuple[type, dict[str, Any]]] = {}


def register_strategy(name: str, strategy_class: type, default_params: dict[str, Any] | None = None) -> None:
    """Register a strategy class for use via API and BacktestRunner."""
    STRATEGY_REGISTRY[name] = (strategy_class, default_params or {})


# Auto-register built-in strategies
try:
    from hqmts.backtest.strategy import DualMACrossoverStrategy
    register_strategy("dual_ma", DualMACrossoverStrategy, {"fast_period": 5, "slow_period": 20})
except ImportError:
    pass

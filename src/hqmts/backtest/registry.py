"""Shared strategy registry for backtest system."""

from __future__ import annotations

from typing import Any

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

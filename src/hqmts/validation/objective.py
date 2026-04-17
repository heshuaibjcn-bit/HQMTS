"""Unified objective function for strategy evaluation (FR-VAL-007).

Combines return, drawdown, stability, turnover, cost, capacity,
and parameter smoothness into a single score.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ObjectiveWeights:
    """Weights for the unified objective function."""

    return_weight: float = 1.0
    drawdown_weight: float = 0.5
    stability_weight: float = 0.3
    turnover_weight: float = 0.1
    cost_weight: float = 0.1
    trade_count_weight: float = 0.05
    sharpe_weight: float = 0.3


DEFAULT_WEIGHTS = ObjectiveWeights()


@dataclass
class StrategyMetrics:
    """All metrics needed for objective evaluation."""

    total_return: float  # percentage
    max_drawdown: float  # percentage (positive number)
    sharpe_ratio: float
    total_trades: int
    win_rate: float  # 0-100
    profit_factor: float
    turnover_rate: float = 0.0  # annual turnover ratio
    cost_ratio: float = 0.0  # cost as fraction of returns


def compute_objective_score(
    metrics: StrategyMetrics,
    weights: ObjectiveWeights | None = None,
) -> float:
    """Compute unified objective score for strategy ranking.

    Higher score = better strategy.

    Components:
    - Return: total_return * weight (positive is good)
    - Drawdown: -max_drawdown * weight (penalty)
    - Stability: win_rate/100 * profit_factor * weight
    - Sharpe: sharpe_ratio * weight (capped at [-3, 3])
    - Turnover: -turnover_rate * weight (penalty for excessive trading)
    - Cost: -cost_ratio * weight
    - Trade count: log(total_trades + 1) * weight (prefer some trades over none)
    """
    w = weights or DEFAULT_WEIGHTS

    sharpe_capped = max(-3.0, min(3.0, metrics.sharpe_ratio))

    score = (
        metrics.total_return * w.return_weight
        - metrics.max_drawdown * w.drawdown_weight
        + (metrics.win_rate / 100.0) * min(metrics.profit_factor, 10.0) * w.stability_weight
        + sharpe_capped * w.sharpe_weight
        - metrics.turnover_rate * w.turnover_weight
        - metrics.cost_ratio * w.cost_weight
        + (metrics.total_trades / 100.0) * w.trade_count_weight  # Normalize
    )

    return score


def rank_strategies(
    strategies: list[tuple[str, StrategyMetrics]],
    weights: ObjectiveWeights | None = None,
) -> list[tuple[str, float, StrategyMetrics]]:
    """Rank strategies by objective score, descending.

    Returns list of (strategy_name, score, metrics) sorted by score.
    """
    scored = []
    for name, metrics in strategies:
        score = compute_objective_score(metrics, weights)
        scored.append((name, score, metrics))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored

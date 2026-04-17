"""Strategy package: concrete strategy implementations."""

from hqmts.backtest.strategies.breakout import BreakoutStrategy
from hqmts.backtest.strategies.cross_cycle import CrossCycleStrategy
from hqmts.backtest.strategies.mean_reversion import MeanReversionStrategy
from hqmts.backtest.strategies.trend_follow import TrendFollowStrategy

__all__ = [
    "BreakoutStrategy",
    "CrossCycleStrategy",
    "MeanReversionStrategy",
    "TrendFollowStrategy",
]

"""Parameter stability analysis (FR-VAL-003).

Evaluates how strategy performance changes across parameter variations
to identify stable zones vs sensitive zones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class ParamPoint:
    """A single parameter combination and its performance."""

    params: dict[str, float | int]
    total_return: float
    max_drawdown: float
    sharpe_ratio: float
    total_trades: int


@dataclass
class StabilityReport:
    """Report on parameter stability across a grid of combinations."""

    param_name: str
    points: list[ParamPoint] = field(default_factory=list)
    stable_zone: tuple[float, float] | None = None  # (low, high) range
    sensitive_zones: list[tuple[float, float]] = field(default_factory=list)

    @property
    def is_stable(self) -> bool:
        """Check if the parameter has a wide stable zone."""
        if self.stable_zone is None:
            return False
        values = [p.params.get(self.param_name, 0) for p in self.points]
        if not values:
            return False
        total_range = max(values) - min(values)
        if total_range == 0:
            return True
        stable_range = self.stable_zone[1] - self.stable_zone[0]
        return stable_range / total_range >= 0.3

    @property
    def best_params(self) -> ParamPoint | None:
        """Return the parameter point with best risk-adjusted return."""
        if not self.points:
            return None
        return max(self.points, key=lambda p: p.total_return - abs(p.max_drawdown))


def analyze_stability(
    param_name: str,
    results: list[ParamPoint],
    stability_threshold: float = 0.5,
) -> StabilityReport:
    """Analyze parameter stability from grid search results.

    A stable zone is where performance doesn't drop more than
    stability_threshold * peak_return from the best result.

    Args:
        param_name: The parameter to analyze.
        results: Grid search results sorted by param value.
        stability_threshold: Max acceptable performance drop ratio.

    Returns:
        StabilityReport with zones identified.
    """
    if not results:
        return StabilityReport(param_name=param_name)

    # Find peak return
    best = max(results, key=lambda p: p.total_return)
    min_acceptable = best.total_return * stability_threshold

    # Identify contiguous stable zone
    sorted_results = sorted(results, key=lambda p: p.params.get(param_name, 0))

    # Find all points above threshold
    stable_points = [p for p in sorted_results if p.total_return >= min_acceptable]

    stable_zone = None
    sensitive_zones = []

    if stable_points:
        stable_vals = [p.params.get(param_name, 0) for p in stable_points]
        stable_zone = (min(stable_vals), max(stable_vals))

        # Sensitive zones: gaps in stable range
        all_vals = sorted(set(p.params.get(param_name, 0) for p in sorted_results))
        for i in range(len(all_vals) - 1):
            if all_vals[i] < stable_zone[0] or all_vals[i + 1] > stable_zone[1]:
                continue
            # Check if there's a drop between consecutive stable points
            prev_ret = next(
                (p.total_return for p in sorted_results
                 if p.params.get(param_name, 0) == all_vals[i]),
                0.0,
            )
            next_ret = next(
                (p.total_return for p in sorted_results
                 if p.params.get(param_name, 0) == all_vals[i + 1]),
                0.0,
            )
            if min(prev_ret, next_ret) < min_acceptable:
                sensitive_zones.append((all_vals[i], all_vals[i + 1]))

    return StabilityReport(
        param_name=param_name,
        points=sorted_results,
        stable_zone=stable_zone,
        sensitive_zones=sensitive_zones,
    )

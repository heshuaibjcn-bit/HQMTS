"""Cost stress testing (FR-VAL-004).

Tests strategy robustness under different cost assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class CostScenario:
    """A cost assumption scenario."""

    name: str
    commission_rate: Decimal  # e.g. Decimal("0.0003") for 万三
    commission_min: Decimal  # Minimum commission per trade
    stamp_tax_rate: Decimal  # e.g. Decimal("0.001") for 千一 (sell only)
    slippage_bps: Decimal  # Slippage in basis points
    fill_rate: float = 1.0  # 0.0 - 1.0, probability of fill


# Pre-defined scenarios
BASELINE = CostScenario(
    name="baseline",
    commission_rate=Decimal("0.0003"),
    commission_min=Decimal("5"),
    stamp_tax_rate=Decimal("0.001"),
    slippage_bps=Decimal("0"),
    fill_rate=1.0,
)

HIGH_COST = CostScenario(
    name="high_cost",
    commission_rate=Decimal("0.001"),
    commission_min=Decimal("10"),
    stamp_tax_rate=Decimal("0.002"),
    slippage_bps=Decimal("5"),
    fill_rate=1.0,
)

LOW_FILL_RATE = CostScenario(
    name="low_fill_rate",
    commission_rate=Decimal("0.0003"),
    commission_min=Decimal("5"),
    stamp_tax_rate=Decimal("0.001"),
    slippage_bps=Decimal("0"),
    fill_rate=0.7,
)

HIGH_SLIPPAGE = CostScenario(
    name="high_slippage",
    commission_rate=Decimal("0.0003"),
    commission_min=Decimal("5"),
    stamp_tax_rate=Decimal("0.001"),
    slippage_bps=Decimal("20"),
    fill_rate=1.0,
)

EXTREME = CostScenario(
    name="extreme",
    commission_rate=Decimal("0.002"),
    commission_min=Decimal("20"),
    stamp_tax_rate=Decimal("0.003"),
    slippage_bps=Decimal("30"),
    fill_rate=0.5,
)

DEFAULT_SCENARIOS = [BASELINE, HIGH_COST, LOW_FILL_RATE, HIGH_SLIPPAGE, EXTREME]


def apply_slippage(price: Decimal, side: str, slippage_bps: Decimal) -> Decimal:
    """Apply slippage to a fill price.

    Buy: price goes up. Sell: price goes down.
    """
    slip = price * slippage_bps / Decimal("10000")
    if side == "buy":
        return price + slip
    else:
        return price - slip

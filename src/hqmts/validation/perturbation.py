"""Perturbation testing (FR-VAL-005).

Tests strategy robustness against signal delay, price noise,
fill noise, and sequence shuffle.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from hqmts.domain.bar import Bar


@dataclass
class PerturbationConfig:
    """Configuration for perturbation tests."""

    signal_delay_bars: int = 1  # Delay signal by N bars
    price_noise_bps: float = 0.0  # Add noise to prices (basis points)
    fill_noise_bps: float = 0.0  # Add noise to fill prices
    sequence_shuffle: bool = False  # Randomly shuffle bar order
    seed: int = 42


def perturb_bars(bars: list[Bar], config: PerturbationConfig) -> list[Bar]:
    """Apply perturbation to bar data for robustness testing.

    Args:
        bars: Original bar data.
        config: Perturbation parameters.

    Returns:
        Perturbed bar data.
    """
    rng = random.Random(config.seed)
    result = list(bars)

    # Shuffle
    if config.sequence_shuffle:
        rng.shuffle(result)

    # Price noise
    if config.price_noise_bps > 0:
        result = [_add_price_noise(b, config.price_noise_bps, rng) for b in result]

    return result


def delay_signals(
    signals: list[dict],
    delay_bars: int,
) -> list[dict]:
    """Delay signal execution by N bars (FR-VAL-005).

    Moves each signal's effective bar index forward by delay_bars.
    """
    if delay_bars <= 0:
        return signals

    delayed = []
    for sig in signals:
        new_sig = dict(sig)
        if "bar_index" in new_sig:
            new_sig["bar_index"] = new_sig["bar_index"] + delay_bars
        delayed.append(new_sig)
    return delayed


def _add_price_noise(bar: Bar, noise_bps: float, rng: random.Random) -> Bar:
    """Add random noise to bar prices."""
    from decimal import Decimal

    factor = noise_bps / 10000.0
    noise_pct = rng.gauss(0, factor)

    def _perturb(val: Decimal) -> Decimal:
        return Decimal(str(float(val) * (1 + noise_pct)))

    return Bar(
        instrument_id=bar.instrument_id,
        cycle=bar.cycle,
        bar_start_time=bar.bar_start_time,
        bar_end_time=bar.bar_end_time,
        open=_perturb(bar.open),
        high=_perturb(bar.high),
        low=_perturb(bar.low),
        close=_perturb(bar.close),
        volume=bar.volume,
        amount=bar.amount,
        is_completed=bar.is_completed,
        source=bar.source,
        data_version=bar.data_version,
    )

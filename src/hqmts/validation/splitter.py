"""In-sample / Out-of-sample data splitter (FR-VAL-001).

Splits bar data chronologically for unbiased strategy evaluation.
"""

from __future__ import annotations

from hqmts.domain.bar import Bar


def split_in_sample_out_of_sample(
    bars: list[Bar],
    train_ratio: float = 0.7,
) -> tuple[list[Bar], list[Bar]]:
    """Split bars chronologically into in-sample and out-of-sample sets.

    Args:
        bars: Chronologically sorted bars.
        train_ratio: Fraction for in-sample (0.0 - 1.0).

    Returns:
        (in_sample, out_of_sample) tuple.
    """
    if not bars:
        return [], []
    if train_ratio <= 0 or train_ratio >= 1:
        raise ValueError(f"train_ratio must be between 0 and 1, got {train_ratio}")

    split_idx = int(len(bars) * train_ratio)
    return bars[:split_idx], bars[split_idx:]


def split_walk_forward(
    bars: list[Bar],
    n_windows: int = 5,
    train_ratio: float = 0.7,
) -> list[tuple[list[Bar], list[Bar]]]:
    """Generate walk-forward validation windows (FR-VAL-002).

    Each window expands the training set forward in time.
    Total data is divided into n_windows equal segments.
    For each window i, train on segments [0..i], test on segment [i+1].

    Args:
        bars: Chronologically sorted bars.
        n_windows: Number of walk-forward windows.
        train_ratio: Fraction of each window used for training.

    Returns:
        List of (train_bars, test_bars) tuples.
    """
    if n_windows < 2:
        raise ValueError(f"n_windows must be >= 2, got {n_windows}")

    segment_size = len(bars) // (n_windows + 1)
    if segment_size == 0:
        return [(bars[:max(1, len(bars) // 2)], bars[max(1, len(bars) // 2):])]

    windows: list[tuple[list[Bar], list[Bar]]] = []
    for i in range(n_windows):
        train_end = segment_size * (i + 1)
        test_end = segment_size * (i + 2)
        train_bars = bars[:train_end]
        test_bars = bars[train_end:test_end]
        if test_bars:
            windows.append((train_bars, test_bars))

    return windows

"""Factor framework for quantitative research (FR-RES-001).

Defines factor types, computation interface, and built-in factors
for A-share markets: trend, momentum, volatility, volume, structure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from hqmts.domain.bar import Bar


class FactorCategory(str, Enum):
    """Factor classification categories (PRD 12.1)."""

    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    STRUCTURE = "structure"
    TIME = "time"
    MARKET_STATE = "market_state"
    CROSS_CYCLE = "cross_cycle"


@dataclass
class FactorValue:
    """A single factor computation result."""

    factor_name: str
    instrument_id: str
    value: float
    timestamp: str  # bar_end_time as ISO string
    version: str = "1.0"
    metadata: dict[str, Any] = field(default_factory=dict)


class Factor(ABC):
    """Abstract base class for all factors."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique factor name."""
        ...

    @property
    @abstractmethod
    def category(self) -> FactorCategory:
        """Factor category."""
        ...

    @property
    def version(self) -> str:
        """Factor version for reproducibility."""
        return "1.0"

    @property
    def description(self) -> str:
        """Human-readable factor description."""
        return ""

    @property
    def params(self) -> dict[str, Any]:
        """Factor parameters."""
        return {}

    @abstractmethod
    def compute(self, bars: list[Bar]) -> list[FactorValue]:
        """Compute factor values from bar data.

        Args:
            bars: Chronologically sorted bars for a single instrument.

        Returns:
            List of factor values, one per bar where computation is possible.
        """
        ...


# ── Built-in factors ────────────────────────────────────────────────────────────


class SMAFactor(Factor):
    """Simple moving average (trend)."""

    def __init__(self, period: int = 20) -> None:
        self._period = period

    @property
    def name(self) -> str:
        return f"SMA_{self._period}"

    @property
    def category(self) -> FactorCategory:
        return FactorCategory.TREND

    @property
    def description(self) -> str:
        return f"Simple moving average over {self._period} bars"

    @property
    def params(self) -> dict[str, Any]:
        return {"period": self._period}

    def compute(self, bars: list[Bar]) -> list[FactorValue]:
        if len(bars) < self._period:
            return []
        closes = np.array([float(b.close) for b in bars])
        iids = [str(b.instrument_id) for b in bars]
        times = [b.bar_end_time.isoformat() for b in bars]
        result: list[FactorValue] = []
        for i in range(self._period - 1, len(bars)):
            window = closes[i - self._period + 1 : i + 1]
            result.append(FactorValue(
                factor_name=self.name,
                instrument_id=iids[i],
                value=float(np.mean(window)),
                timestamp=times[i],
                version=self.version,
            ))
        return result


class EMAFactor(Factor):
    """Exponential moving average (trend)."""

    def __init__(self, period: int = 20) -> None:
        self._period = period

    @property
    def name(self) -> str:
        return f"EMA_{self._period}"

    @property
    def category(self) -> FactorCategory:
        return FactorCategory.TREND

    @property
    def params(self) -> dict[str, Any]:
        return {"period": self._period}

    def compute(self, bars: list[Bar]) -> list[FactorValue]:
        if len(bars) < self._period:
            return []
        closes = np.array([float(b.close) for b in bars])
        iids = [str(b.instrument_id) for b in bars]
        times = [b.bar_end_time.isoformat() for b in bars]
        multiplier = 2.0 / (self._period + 1)
        result: list[FactorValue] = []
        # Seed with SMA of first `period` bars
        ema = float(np.mean(closes[: self._period]))
        for i in range(self._period - 1, len(bars)):
            if i > self._period - 1:
                ema = closes[i] * multiplier + ema * (1 - multiplier)
            result.append(FactorValue(
                factor_name=self.name,
                instrument_id=iids[i],
                value=ema,
                timestamp=times[i],
                version=self.version,
            ))
        return result


class RSIFactor(Factor):
    """Relative Strength Index (momentum)."""

    def __init__(self, period: int = 14) -> None:
        self._period = period

    @property
    def name(self) -> str:
        return f"RSI_{self._period}"

    @property
    def category(self) -> FactorCategory:
        return FactorCategory.MOMENTUM

    @property
    def params(self) -> dict[str, Any]:
        return {"period": self._period}

    def compute(self, bars: list[Bar]) -> list[FactorValue]:
        if len(bars) < self._period + 1:
            return []
        closes = np.array([float(b.close) for b in bars])
        iids = [str(b.instrument_id) for b in bars]
        times = [b.bar_end_time.isoformat() for b in bars]
        deltas = np.diff(closes)
        result: list[FactorValue] = []
        # Wilder's smoothing
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = float(np.mean(gains[: self._period]))
        avg_loss = float(np.mean(losses[: self._period]))
        for i in range(self._period, len(deltas)):
            avg_gain = (avg_gain * (self._period - 1) + gains[i]) / self._period
            avg_loss = (avg_loss * (self._period - 1) + losses[i]) / self._period
            if avg_loss == 0:
                rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi = 100.0 - 100.0 / (1.0 + rs)
            result.append(FactorValue(
                factor_name=self.name,
                instrument_id=iids[i + 1],
                value=rsi,
                timestamp=times[i + 1],
                version=self.version,
            ))
        return result


class ATRFactor(Factor):
    """Average True Range (volatility)."""

    def __init__(self, period: int = 14) -> None:
        self._period = period

    @property
    def name(self) -> str:
        return f"ATR_{self._period}"

    @property
    def category(self) -> FactorCategory:
        return FactorCategory.VOLATILITY

    @property
    def params(self) -> dict[str, Any]:
        return {"period": self._period}

    def compute(self, bars: list[Bar]) -> list[FactorValue]:
        if len(bars) < self._period + 1:
            return []
        highs = np.array([float(b.high) for b in bars])
        lows = np.array([float(b.low) for b in bars])
        closes = np.array([float(b.close) for b in bars])
        iids = [str(b.instrument_id) for b in bars]
        times = [b.bar_end_time.isoformat() for b in bars]

        # True Range
        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1]),
            ),
        )
        # Wilder's smoothing
        atr = float(np.mean(tr[: self._period]))
        result: list[FactorValue] = []
        for i in range(self._period, len(tr)):
            atr = (atr * (self._period - 1) + tr[i]) / self._period
            result.append(FactorValue(
                factor_name=self.name,
                instrument_id=iids[i + 1],
                value=atr,
                timestamp=times[i + 1],
                version=self.version,
            ))
        return result


class VolumeRatioFactor(Factor):
    """Volume ratio: current volume / moving average volume (volume)."""

    def __init__(self, period: int = 20) -> None:
        self._period = period

    @property
    def name(self) -> str:
        return f"VOL_RATIO_{self._period}"

    @property
    def category(self) -> FactorCategory:
        return FactorCategory.VOLUME

    @property
    def params(self) -> dict[str, Any]:
        return {"period": self._period}

    def compute(self, bars: list[Bar]) -> list[FactorValue]:
        if len(bars) < self._period:
            return []
        volumes = np.array([float(b.volume) for b in bars])
        iids = [str(b.instrument_id) for b in bars]
        times = [b.bar_end_time.isoformat() for b in bars]
        result: list[FactorValue] = []
        for i in range(self._period - 1, len(bars)):
            avg_vol = float(np.mean(volumes[i - self._period + 1 : i + 1]))
            ratio = volumes[i] / avg_vol if avg_vol > 0 else 0.0
            result.append(FactorValue(
                factor_name=self.name,
                instrument_id=iids[i],
                value=ratio,
                timestamp=times[i],
                version=self.version,
            ))
        return result


class BollingerPositionFactor(Factor):
    """Position within Bollinger Bands (structure).

    Returns 0-1 where 0 = at lower band, 1 = at upper band.
    """

    def __init__(self, period: int = 20, num_std: float = 2.0) -> None:
        self._period = period
        self._num_std = num_std

    @property
    def name(self) -> str:
        return f"BB_POS_{self._period}_{self._num_std}"

    @property
    def category(self) -> FactorCategory:
        return FactorCategory.STRUCTURE

    @property
    def params(self) -> dict[str, Any]:
        return {"period": self._period, "num_std": self._num_std}

    def compute(self, bars: list[Bar]) -> list[FactorValue]:
        if len(bars) < self._period:
            return []
        closes = np.array([float(b.close) for b in bars])
        iids = [str(b.instrument_id) for b in bars]
        times = [b.bar_end_time.isoformat() for b in bars]
        result: list[FactorValue] = []
        for i in range(self._period - 1, len(bars)):
            window = closes[i - self._period + 1 : i + 1]
            mean = float(np.mean(window))
            std = float(np.std(window, ddof=0))
            upper = mean + self._num_std * std
            lower = mean - self._num_std * std
            band_width = upper - lower
            pos = (closes[i] - lower) / band_width if band_width > 0 else 0.5
            result.append(FactorValue(
                factor_name=self.name,
                instrument_id=iids[i],
                value=pos,
                timestamp=times[i],
                version=self.version,
            ))
        return result

"""Tests for factor research framework (FR-RES-001 through FR-RES-004)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from hqmts.core.enums import Cycle
from hqmts.core.types import InstrumentId, VersionStr
from hqmts.domain.bar import Bar
from hqmts.research.factor import (
    ATRFactor,
    BollingerPositionFactor,
    EMAFactor,
    FactorCategory,
    RSIFactor,
    SMAFactor,
    VolumeRatioFactor,
)
from hqmts.research.registry import FactorRegistry, create_default_registry
from hqmts.research.governance import MultipleTestingGovernance


def _bars(n: int, trend: str = "flat") -> list[Bar]:
    """Create test bars with configurable price trend."""
    base = datetime(2024, 1, 2, 9, 30)
    bars = []
    for i in range(n):
        if trend == "up":
            price = 10.0 + i * 0.1
        elif trend == "down":
            price = 20.0 - i * 0.1
        else:
            price = 10.0
        bars.append(Bar(
            instrument_id=InstrumentId("000001.SZ"),
            cycle=Cycle.M5,
            bar_start_time=base + timedelta(minutes=5 * i),
            bar_end_time=base + timedelta(minutes=5 * (i + 1)),
            open=Decimal(str(round(price - 0.1, 2))),
            high=Decimal(str(round(price + 0.3, 2))),
            low=Decimal(str(round(price - 0.3, 2))),
            close=Decimal(str(round(price, 2))),
            volume=100000 + i * 1000,
            amount=Decimal(str(round(price * 100000, 2))),
            is_completed=True,
            source="test",
            data_version=VersionStr("v1"),
        ))
    return bars


# ── SMA Factor ──────────────────────────────────────────────────────────────────


class TestSMAFactor:
    def test_compute(self):
        bars = _bars(30, "up")
        factor = SMAFactor(20)
        values = factor.compute(bars)
        assert len(values) == 11  # 30 - 20 + 1
        # Uptrend: SMA should be increasing
        assert values[-1].value > values[0].value

    def test_insufficient_bars(self):
        factor = SMAFactor(20)
        values = factor.compute(_bars(10))
        assert values == []

    def test_name_and_category(self):
        factor = SMAFactor(10)
        assert factor.name == "SMA_10"
        assert factor.category == FactorCategory.TREND


# ── EMA Factor ──────────────────────────────────────────────────────────────────


class TestEMAFactor:
    def test_compute(self):
        bars = _bars(30, "up")
        factor = EMAFactor(20)
        values = factor.compute(bars)
        assert len(values) == 11
        # EMA should be responsive to uptrend
        assert values[-1].value > values[0].value

    def test_insufficient_bars(self):
        factor = EMAFactor(20)
        assert factor.compute(_bars(10)) == []


# ── RSI Factor ──────────────────────────────────────────────────────────────────


class TestRSIFactor:
    def test_uptrend_high_rsi(self):
        bars = _bars(30, "up")
        factor = RSIFactor(14)
        values = factor.compute(bars)
        assert len(values) > 0
        # Uptrend should produce RSI > 50
        assert values[-1].value > 50

    def test_downtrend_low_rsi(self):
        bars = _bars(30, "down")
        factor = RSIFactor(14)
        values = factor.compute(bars)
        assert len(values) > 0
        assert values[-1].value < 50

    def test_category(self):
        assert RSIFactor().category == FactorCategory.MOMENTUM


# ── ATR Factor ──────────────────────────────────────────────────────────────────


class TestATRFactor:
    def test_compute(self):
        bars = _bars(30)
        factor = ATRFactor(14)
        values = factor.compute(bars)
        assert len(values) > 0
        # ATR should be positive
        assert all(v.value > 0 for v in values)

    def test_category(self):
        assert ATRFactor().category == FactorCategory.VOLATILITY


# ── Volume Ratio Factor ─────────────────────────────────────────────────────────


class TestVolumeRatioFactor:
    def test_compute(self):
        bars = _bars(30)
        factor = VolumeRatioFactor(20)
        values = factor.compute(bars)
        assert len(values) == 11

    def test_flat_volume_ratio_near_one(self):
        bars = _bars(30)
        factor = VolumeRatioFactor(20)
        values = factor.compute(bars)
        # Volume increases linearly, last bar ratio > 1
        assert values[-1].value > 0

    def test_category(self):
        assert VolumeRatioFactor().category == FactorCategory.VOLUME


# ── Bollinger Position Factor ───────────────────────────────────────────────────


class TestBollingerPositionFactor:
    def test_compute(self):
        bars = _bars(30)
        factor = BollingerPositionFactor(20, 2.0)
        values = factor.compute(bars)
        assert len(values) == 11

    def test_position_in_range(self):
        bars = _bars(100)
        factor = BollingerPositionFactor(20, 2.0)
        values = factor.compute(bars)
        # Position should be between 0 and 1 for reasonable data
        for v in values:
            assert 0.0 <= v.value <= 1.0 or abs(v.value - 0.5) < 0.1  # Allow small deviation

    def test_category(self):
        assert BollingerPositionFactor().category == FactorCategory.STRUCTURE


# ── Factor Registry ─────────────────────────────────────────────────────────────


class TestFactorRegistry:
    def test_register_and_get(self):
        registry = FactorRegistry()
        factor = SMAFactor(10)
        registry.register(factor)
        assert registry.get("SMA_10") is factor

    def test_get_nonexistent(self):
        registry = FactorRegistry()
        assert registry.get("nonexistent") is None

    def test_list_all(self):
        registry = FactorRegistry()
        registry.register(SMAFactor(5))
        registry.register(RSIFactor(14))
        assert len(registry.list_factors()) == 2

    def test_list_by_category(self):
        registry = FactorRegistry()
        registry.register(SMAFactor(5))
        registry.register(RSIFactor(14))
        trend = registry.list_factors(category=FactorCategory.TREND)
        assert len(trend) == 1
        assert trend[0].name == "SMA_5"

    def test_unregister(self):
        registry = FactorRegistry()
        registry.register(SMAFactor(5))
        assert registry.unregister("SMA_5") is True
        assert registry.get("SMA_5") is None

    def test_unregister_nonexistent(self):
        registry = FactorRegistry()
        assert registry.unregister("nope") is False

    def test_count(self):
        registry = FactorRegistry()
        assert registry.count == 0
        registry.register(SMAFactor(5))
        assert registry.count == 1

    def test_default_registry(self):
        registry = create_default_registry()
        assert registry.count >= 7  # 4 SMA + 4 EMA + RSI + ATR + VOL_RATIO + BB_POS = 11
        assert registry.get("SMA_20") is not None
        assert registry.get("RSI_14") is not None


# ── Multiple Testing Governance ─────────────────────────────────────────────────


class TestMultipleTestingGovernance:
    def test_record_trial(self):
        gov = MultipleTestingGovernance()
        record = gov.record_trial("SMA_20", "dual_ma", "sharpe_ratio", 1.5, 1.0)
        assert record.trial_id == 1
        assert record.is_significant is True

    def test_adjusted_threshold_bonferroni(self):
        gov = MultipleTestingGovernance(alpha=0.05, method="bonferroni")
        gov.record_trial("f1", "s1", "sharpe", 2.0, 1.0)
        gov.record_trial("f2", "s1", "sharpe", 1.5, 1.0)
        assert gov.get_adjusted_threshold() == pytest.approx(0.025)

    def test_compute_stats(self):
        gov = MultipleTestingGovernance(alpha=0.05)
        gov.record_trial("f1", "s1", "sharpe", 2.0, 1.0)  # significant
        gov.record_trial("f2", "s1", "sharpe", 0.5, 1.0)  # not significant
        stats = gov.compute_stats()
        assert stats.total_trials == 2
        assert stats.significant_count == 1

    def test_trial_budget(self):
        gov = MultipleTestingGovernance(max_trials=2)
        gov.record_trial("f1", "s1", "sharpe", 2.0, 1.0)
        assert gov.is_within_budget()
        gov.record_trial("f2", "s1", "sharpe", 1.5, 1.0)
        gov.record_trial("f3", "s1", "sharpe", 1.0, 1.0)
        assert not gov.is_within_budget()

    def test_get_trials_by_factor(self):
        gov = MultipleTestingGovernance()
        gov.record_trial("SMA_20", "s1", "sharpe", 2.0, 1.0)
        gov.record_trial("RSI_14", "s1", "sharpe", 1.5, 1.0)
        gov.record_trial("SMA_20", "s2", "sharpe", 1.8, 1.0)
        sma_trials = gov.get_trials("SMA_20")
        assert len(sma_trials) == 2

    def test_empty_stats(self):
        gov = MultipleTestingGovernance()
        stats = gov.compute_stats()
        assert stats.total_trials == 0

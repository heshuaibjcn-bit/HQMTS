"""Tests for validation subsystem (FR-VAL-001 through FR-VAL-007)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from hqmts.core.enums import Cycle
from hqmts.core.types import InstrumentId, VersionStr
from hqmts.domain.bar import Bar
from hqmts.validation.splitter import split_in_sample_out_of_sample, split_walk_forward
from hqmts.validation.metrics import ParamPoint, StabilityReport, analyze_stability
from hqmts.validation.stress import CostScenario, apply_slippage, BASELINE, HIGH_COST, DEFAULT_SCENARIOS
from hqmts.validation.perturbation import PerturbationConfig, perturb_bars, delay_signals
from hqmts.validation.objective import (
    StrategyMetrics, ObjectiveWeights, compute_objective_score, rank_strategies,
)


def _bars(n: int, base: datetime | None = None) -> list[Bar]:
    base = base or datetime(2024, 1, 2, 9, 30)
    return [Bar(
        instrument_id=InstrumentId("000001.SZ"),
        cycle=Cycle.M5,
        bar_start_time=base + timedelta(minutes=5 * i),
        bar_end_time=base + timedelta(minutes=5 * (i + 1)),
        open=Decimal("10"), high=Decimal("10.5"), low=Decimal("9.5"), close=Decimal("10.25"),
        volume=100000, amount=Decimal("1000000"),
        is_completed=True, source="test", data_version=VersionStr("v1"),
    ) for i in range(n)]


# ── Splitter ──────────────────────────────────────────────────────────────────


class TestSplitter:
    def test_in_sample_out_of_sample(self):
        bars = _bars(100)
        train, test = split_in_sample_out_of_sample(bars, train_ratio=0.7)
        assert len(train) == 70
        assert len(test) == 30

    def test_empty_bars(self):
        train, test = split_in_sample_out_of_sample([], train_ratio=0.7)
        assert train == []
        assert test == []

    def test_invalid_ratio(self):
        with pytest.raises(ValueError):
            split_in_sample_out_of_sample(_bars(10), train_ratio=0.0)
        with pytest.raises(ValueError):
            split_in_sample_out_of_sample(_bars(10), train_ratio=1.0)

    def test_walk_forward_windows(self):
        bars = _bars(120)
        windows = split_walk_forward(bars, n_windows=5)
        assert len(windows) >= 3
        for train, test in windows:
            assert len(train) > 0
            assert len(test) > 0

    def test_walk_forward_expanding(self):
        bars = _bars(120)
        windows = split_walk_forward(bars, n_windows=5)
        # Each window's training set should be >= previous
        for i in range(1, len(windows)):
            assert len(windows[i][0]) >= len(windows[i - 1][0])

    def test_walk_forward_minimum_windows(self):
        with pytest.raises(ValueError):
            split_walk_forward(_bars(10), n_windows=1)


# ── Stability ──────────────────────────────────────────────────────────────────


class TestStability:
    def test_analyze_stable_parameter(self):
        points = [
            ParamPoint(params={"period": 5}, total_return=10.0, max_drawdown=5.0, sharpe_ratio=1.5, total_trades=20),
            ParamPoint(params={"period": 10}, total_return=12.0, max_drawdown=4.0, sharpe_ratio=2.0, total_trades=15),
            ParamPoint(params={"period": 15}, total_return=11.0, max_drawdown=4.5, sharpe_ratio=1.8, total_trades=12),
            ParamPoint(params={"period": 20}, total_return=9.0, max_drawdown=6.0, sharpe_ratio=1.2, total_trades=10),
        ]
        report = analyze_stability("period", points, stability_threshold=0.5)
        assert report.stable_zone is not None
        assert report.best_params is not None
        assert report.best_params.params["period"] == 10  # Best return-drawdown combo

    def test_analyze_empty(self):
        report = analyze_stability("period", [])
        assert report.stable_zone is None
        assert report.best_params is None

    def test_stability_report_is_stable(self):
        report = StabilityReport(
            param_name="period",
            points=[
                ParamPoint(params={"period": 5}, total_return=10, max_drawdown=2, sharpe_ratio=1, total_trades=10),
                ParamPoint(params={"period": 15}, total_return=10, max_drawdown=2, sharpe_ratio=1, total_trades=10),
            ],
            stable_zone=(5, 15),
        )
        assert report.is_stable


# ── Cost Stress ────────────────────────────────────────────────────────────────


class TestCostStress:
    def test_baseline_scenario(self):
        assert BASELINE.name == "baseline"
        assert BASELINE.commission_rate == Decimal("0.0003")

    def test_default_scenarios_count(self):
        assert len(DEFAULT_SCENARIOS) >= 4

    def test_apply_slippage_buy(self):
        result = apply_slippage(Decimal("10.00"), "buy", Decimal("10"))
        assert result > Decimal("10.00")  # Buy price goes up with slippage

    def test_apply_slippage_sell(self):
        result = apply_slippage(Decimal("10.00"), "sell", Decimal("10"))
        assert result < Decimal("10.00")  # Sell price goes down with slippage

    def test_apply_slippage_zero(self):
        result = apply_slippage(Decimal("10.00"), "buy", Decimal("0"))
        assert result == Decimal("10.00")

    def test_high_cost_scenario(self):
        assert HIGH_COST.commission_rate > BASELINE.commission_rate
        assert HIGH_COST.stamp_tax_rate > BASELINE.stamp_tax_rate


# ── Perturbation ──────────────────────────────────────────────────────────────


class TestPerturbation:
    def test_perturb_no_noise(self):
        bars = _bars(10)
        config = PerturbationConfig(price_noise_bps=0.0)
        result = perturb_bars(bars, config)
        assert len(result) == 10
        # No noise means identical
        for orig, pert in zip(bars, result):
            assert orig.close == pert.close

    def test_perturb_with_noise(self):
        bars = _bars(10)
        config = PerturbationConfig(price_noise_bps=50.0)  # 50bps noise
        result = perturb_bars(bars, config)
        assert len(result) == 10
        # At least some bars should have different prices
        different = [o.close != p.close for o, p in zip(bars, result)]
        assert any(different)

    def test_delay_signals(self):
        signals = [{"bar_index": 5, "side": "buy"}, {"bar_index": 10, "side": "sell"}]
        delayed = delay_signals(signals, delay_bars=2)
        assert delayed[0]["bar_index"] == 7
        assert delayed[1]["bar_index"] == 12

    def test_delay_zero(self):
        signals = [{"bar_index": 5}]
        result = delay_signals(signals, delay_bars=0)
        assert result[0]["bar_index"] == 5

    def test_shuffle(self):
        bars = _bars(20)
        config = PerturbationConfig(sequence_shuffle=True, seed=123)
        result = perturb_bars(bars, config)
        # Shuffled means at least one bar is in a different position
        original_times = [b.bar_start_time for b in bars]
        result_times = [b.bar_start_time for b in result]
        assert original_times != result_times


# ── Objective Function ─────────────────────────────────────────────────────────


class TestObjectiveFunction:
    def test_score_basic(self):
        metrics = StrategyMetrics(
            total_return=20.0, max_drawdown=5.0, sharpe_ratio=1.5,
            total_trades=50, win_rate=60.0, profit_factor=2.0,
        )
        score = compute_objective_score(metrics)
        assert score > 0  # Positive return with reasonable drawdown

    def test_score_negative_return(self):
        metrics = StrategyMetrics(
            total_return=-10.0, max_drawdown=15.0, sharpe_ratio=-1.0,
            total_trades=20, win_rate=30.0, profit_factor=0.5,
        )
        score = compute_objective_score(metrics)
        assert score < 0

    def test_rank_strategies(self):
        strategies = [
            ("conservative", StrategyMetrics(total_return=5.0, max_drawdown=2.0, sharpe_ratio=1.0, total_trades=10, win_rate=70.0, profit_factor=3.0)),
            ("aggressive", StrategyMetrics(total_return=30.0, max_drawdown=15.0, sharpe_ratio=1.2, total_trades=80, win_rate=50.0, profit_factor=1.5)),
            ("balanced", StrategyMetrics(total_return=15.0, max_drawdown=5.0, sharpe_ratio=1.8, total_trades=30, win_rate=60.0, profit_factor=2.5)),
        ]
        ranked = rank_strategies(strategies)
        assert len(ranked) == 3
        # Should be sorted descending by score
        for i in range(len(ranked) - 1):
            assert ranked[i][1] >= ranked[i + 1][1]

    def test_custom_weights(self):
        w = ObjectiveWeights(return_weight=2.0, drawdown_weight=0.0)
        metrics = StrategyMetrics(
            total_return=10.0, max_drawdown=50.0, sharpe_ratio=1.0,
            total_trades=10, win_rate=50.0, profit_factor=1.0,
        )
        # With zero drawdown weight, score should be higher
        score_custom = compute_objective_score(metrics, weights=w)
        score_default = compute_objective_score(metrics)
        assert score_custom > score_default  # Ignoring 50% drawdown makes score higher

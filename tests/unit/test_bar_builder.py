"""Tests for bar builder and data quality checker."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from hqmts.core.enums import Cycle, DataQualityGrade
from hqmts.core.types import InstrumentId, VersionStr
from hqmts.data.bar_builder import BarBuilder, _generate_1m_timestamps, _generate_cycle_boundaries
from hqmts.data.quality import DataQualityChecker
from hqmts.domain.bar import Bar


def _make_bar(
    instrument_id: str = "000001.SZ",
    cycle: Cycle = Cycle.M1,
    start: datetime | None = None,
    open_: str = "10.00",
    high: str = "10.50",
    low: str = "9.50",
    close: str = "10.20",
    volume: int = 1000,
    amount: str = "10000",
    is_completed: bool = True,
    source: str = "tushare",
) -> Bar:
    if start is None:
        start = datetime(2024, 1, 2, 9, 30)
    return Bar(
        instrument_id=InstrumentId(instrument_id),
        cycle=cycle,
        bar_start_time=start,
        bar_end_time=start + timedelta(minutes=_cycle_minutes(cycle)),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=volume,
        amount=Decimal(amount),
        is_completed=is_completed,
        source=source,
        data_version=VersionStr("v1"),
    )


def _cycle_minutes(cycle: Cycle) -> int:
    return {Cycle.M1: 1, Cycle.M5: 5, Cycle.M15: 15, Cycle.M30: 30, Cycle.M60: 60}[cycle]


class TestTimestampGeneration:
    def test_1m_slots_count(self):
        """240 one-minute slots per trade day."""
        slots = _generate_1m_timestamps("20240102")
        assert len(slots) == 240

    def test_1m_first_slot(self):
        slots = _generate_1m_timestamps("20240102")
        assert slots[0] == (datetime(2024, 1, 2, 9, 30), datetime(2024, 1, 2, 9, 31))

    def test_1m_last_morning_slot(self):
        slots = _generate_1m_timestamps("20240102")
        # 120th slot (index 119) is 11:29-11:30
        assert slots[119] == (datetime(2024, 1, 2, 11, 29), datetime(2024, 1, 2, 11, 30))

    def test_1m_first_afternoon_slot(self):
        slots = _generate_1m_timestamps("20240102")
        # Slot 120 is first afternoon: 13:00-13:01
        assert slots[120] == (datetime(2024, 1, 2, 13, 0), datetime(2024, 1, 2, 13, 1))

    def test_1m_no_lunch_break_bars(self):
        """No bars between 11:30 and 13:00."""
        slots = _generate_1m_timestamps("20240102")
        for start, end in slots:
            assert not (start.hour == 12 or (start.hour == 11 and start.minute >= 30 and start.hour == 11))

    def test_5m_boundaries_count(self):
        """24 five-minute bars per day (12 morning + 12 afternoon)."""
        boundaries = _generate_cycle_boundaries("20240102", Cycle.M5)
        assert len(boundaries) == 48

    def test_5m_first_boundary(self):
        boundaries = _generate_cycle_boundaries("20240102", Cycle.M5)
        assert boundaries[0] == (datetime(2024, 1, 2, 9, 30), datetime(2024, 1, 2, 9, 35))

    def test_60m_boundaries_count(self):
        """4 sixty-minute bars per day."""
        boundaries = _generate_cycle_boundaries("20240102", Cycle.M60)
        assert len(boundaries) == 4

    def test_60m_non_uniform_boundaries(self):
        boundaries = _generate_cycle_boundaries("20240102", Cycle.M60)
        assert boundaries[0] == (datetime(2024, 1, 2, 9, 30), datetime(2024, 1, 2, 10, 30))
        assert boundaries[1] == (datetime(2024, 1, 2, 10, 30), datetime(2024, 1, 2, 11, 30))
        assert boundaries[2] == (datetime(2024, 1, 2, 13, 0), datetime(2024, 1, 2, 14, 0))
        assert boundaries[3] == (datetime(2024, 1, 2, 14, 0), datetime(2024, 1, 2, 15, 0))


class TestBarBuilder:
    def test_build_1m_bars(self):
        builder = BarBuilder(data_version=VersionStr("v1"))
        rows = [
            {"bar_start_time": datetime(2024, 1, 2, 9, 30), "open": 10.0, "high": 10.5, "low": 9.8, "close": 10.2, "volume": 1000, "amount": 10000.0},
            {"bar_start_time": datetime(2024, 1, 2, 9, 31), "open": 10.2, "high": 10.3, "low": 10.0, "close": 10.1, "volume": 500, "amount": 5000.0},
        ]
        bars = builder.build_1m_bars("000001.SZ", rows)
        assert len(bars) == 2
        assert bars[0].cycle == Cycle.M1
        assert bars[0].source == "tushare"
        assert bars[0].is_completed is True

    def test_aggregate_5m(self):
        builder = BarBuilder(data_version=VersionStr("v1"))
        # Create 5 one-minute bars for 09:30-09:35
        bars_1m = [
            _make_bar(start=datetime(2024, 1, 2, 9, 30 + i), open_="10.00", high=f"{10.0 + i * 0.1}", low="9.90", close=f"{10.0 + i * 0.05}", volume=100 * (i + 1))
            for i in range(5)
        ]
        result = builder.aggregate(bars_1m, Cycle.M5)
        assert len(result) == 1
        assert result[0].cycle == Cycle.M5
        assert result[0].open == Decimal("10.00")  # first bar's open
        assert result[0].close == Decimal("10.20")  # last bar's close
        assert result[0].high == Decimal("10.40")  # max of highs
        assert result[0].low == Decimal("9.90")  # min of lows
        assert result[0].volume == 1500  # sum of volumes
        assert result[0].source == "aggregated"
        assert result[0].is_completed is True

    def test_aggregate_incomplete_bars(self):
        builder = BarBuilder(data_version=VersionStr("v1"))
        # Only 3 of 5 expected bars -> incomplete
        bars_1m = [
            _make_bar(start=datetime(2024, 1, 2, 9, 30 + i))
            for i in range(3)
        ]
        result = builder.aggregate(bars_1m, Cycle.M5)
        assert len(result) == 1
        assert result[0].is_completed is False

    def test_aggregate_60m_morning(self):
        builder = BarBuilder(data_version=VersionStr("v1"))
        # Create 60 one-minute bars for 09:30-10:30
        bars_1m = [
            _make_bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=i))
            for i in range(60)
        ]
        result = builder.aggregate(bars_1m, Cycle.M60)
        assert len(result) == 1
        assert result[0].is_completed is True

    def test_aggregate_empty_input(self):
        builder = BarBuilder(data_version=VersionStr("v1"))
        result = builder.aggregate([], Cycle.M5)
        assert result == []

    def test_aggregate_m1_returns_same(self):
        builder = BarBuilder(data_version=VersionStr("v1"))
        bars = [_make_bar(start=datetime(2024, 1, 2, 9, 30))]
        result = builder.aggregate(bars, Cycle.M1)
        assert result is bars

    def test_aggregate_multi_day(self):
        builder = BarBuilder(data_version=VersionStr("v1"))
        # Day 1: 5 bars
        day1 = [_make_bar(start=datetime(2024, 1, 2, 9, 30 + i)) for i in range(5)]
        # Day 2: 5 bars
        day2 = [_make_bar(start=datetime(2024, 1, 3, 9, 30 + i)) for i in range(5)]
        result = builder.aggregate(day1 + day2, Cycle.M5)
        assert len(result) == 2  # one per day

    def test_lunch_break_no_cross_aggregation(self):
        """Bars from 11:25-11:30 and 13:00-13:05 should not merge."""
        builder = BarBuilder(data_version=VersionStr("v1"))
        bars_1m = [
            _make_bar(start=datetime(2024, 1, 2, 11, 25 + i))  # 11:25, 11:26, 11:27, 11:28, 11:29
            for i in range(5)
        ]
        result = builder.aggregate(bars_1m, Cycle.M5)
        assert len(result) == 1
        assert result[0].bar_start_time == datetime(2024, 1, 2, 11, 25)


class TestDataQualityChecker:
    def test_completeness_pass(self):
        checker = DataQualityChecker()
        slots = [(datetime(2024, 1, 2, 9, 30), datetime(2024, 1, 2, 9, 31))]
        bars = [_make_bar(start=datetime(2024, 1, 2, 9, 30))]
        assert checker.check_completeness(bars, slots) == DataQualityGrade.PASS

    def test_completeness_fail(self):
        checker = DataQualityChecker()
        slots = _generate_1m_timestamps("20240102")  # 240 expected
        bars = [_make_bar(start=datetime(2024, 1, 2, 9, 30))]  # only 1
        assert checker.check_completeness(bars, slots) == DataQualityGrade.FAIL

    def test_no_duplicates(self):
        checker = DataQualityChecker()
        bars = [
            _make_bar(start=datetime(2024, 1, 2, 9, 30)),
            _make_bar(start=datetime(2024, 1, 2, 9, 31)),
        ]
        assert checker.check_no_duplicates(bars) is True

    def test_duplicates_detected(self):
        checker = DataQualityChecker()
        bars = [
            _make_bar(start=datetime(2024, 1, 2, 9, 30)),
            _make_bar(start=datetime(2024, 1, 2, 9, 30)),  # same time
        ]
        assert checker.check_no_duplicates(bars) is False

    def test_monotonic_time(self):
        checker = DataQualityChecker()
        bars = [
            _make_bar(start=datetime(2024, 1, 2, 9, 30)),
            _make_bar(start=datetime(2024, 1, 2, 9, 31)),
        ]
        assert checker.check_monotonic_time(bars) is True

    def test_non_monotonic_time(self):
        checker = DataQualityChecker()
        bars = [
            _make_bar(start=datetime(2024, 1, 2, 9, 31)),
            _make_bar(start=datetime(2024, 1, 2, 9, 30)),  # out of order
        ]
        assert checker.check_monotonic_time(bars) is False

    def test_ohlcv_consistent(self):
        checker = DataQualityChecker()
        bar = _make_bar(open_="10.00", high="10.50", low="9.50", close="10.20")
        assert checker.check_ohlcv_consistency(bar) is True

    def test_ohlcv_high_below_open(self):
        checker = DataQualityChecker()
        bar = _make_bar(open_="10.00", high="9.99", low="9.50", close="10.20")
        assert checker.check_ohlcv_consistency(bar) is False

    def test_zero_price_detected(self):
        checker = DataQualityChecker()
        bar = _make_bar(open_="0", high="10.50", low="9.50", close="10.20")
        assert checker.check_no_zero_price(bar) is False

    def test_full_check_pass(self):
        checker = DataQualityChecker()
        slots = [(datetime(2024, 1, 2, 9, 30), datetime(2024, 1, 2, 9, 31))]
        bars = [_make_bar(start=datetime(2024, 1, 2, 9, 30))]
        assert checker.run_full_check(bars, slots) == DataQualityGrade.PASS

    def test_full_check_empty_bars(self):
        checker = DataQualityChecker()
        assert checker.run_full_check([], []) == DataQualityGrade.UNKNOWN

    def test_worse_grade(self):
        assert DataQualityChecker._worse(DataQualityGrade.PASS, DataQualityGrade.WARN) == DataQualityGrade.WARN
        assert DataQualityChecker._worse(DataQualityGrade.FAIL, DataQualityGrade.WARN) == DataQualityGrade.FAIL
        assert DataQualityChecker._worse(DataQualityGrade.PASS, DataQualityGrade.PASS) == DataQualityGrade.PASS

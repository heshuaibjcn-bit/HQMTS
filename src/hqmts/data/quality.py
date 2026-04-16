"""Data quality checking for bar data (FR-DATA-005)."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

from hqmts.core.enums import DataQualityGrade
from hqmts.domain.bar import Bar

logger = logging.getLogger(__name__)


class DataQualityChecker:
    """Validates bar data quality.

    Checks: completeness, duplicates, time monotonicity, OHLCV consistency, zero prices.
    Returns DataQualityGrade (PASS/WARN/FAIL/UNKNOWN).
    """

    def check_completeness(
        self,
        bars: list[Bar],
        expected_slots: list[tuple[datetime, datetime]],
    ) -> DataQualityGrade:
        """Check if all expected bar slots are present."""
        if not expected_slots:
            return DataQualityGrade.UNKNOWN

        actual_ends = {b.bar_end_time for b in bars}
        expected_ends = {end for _, end in expected_slots}

        missing = expected_ends - actual_ends
        ratio = 1.0 - len(missing) / len(expected_ends)

        if ratio >= 0.99:
            return DataQualityGrade.PASS
        elif ratio >= 0.90:
            return DataQualityGrade.WARN
        return DataQualityGrade.FAIL

    def check_no_duplicates(self, bars: list[Bar]) -> bool:
        """Check for duplicate bar_end_time entries."""
        seen: set[datetime] = set()
        for bar in bars:
            key = (bar.instrument_id, bar.cycle, bar.bar_end_time)
            if key in seen:
                return False
            seen.add(key)
        return True

    def check_monotonic_time(self, bars: list[Bar]) -> bool:
        """Check that bars are in chronological order."""
        for i in range(1, len(bars)):
            if bars[i].bar_start_time <= bars[i - 1].bar_start_time:
                return False
        return True

    def check_ohlcv_consistency(self, bar: Bar) -> bool:
        """Check OHLCV consistency: high >= max(open, close), low <= min(open, close), volume >= 0."""
        max_oc = max(bar.open, bar.close)
        min_oc = min(bar.open, bar.close)

        if bar.high < max_oc:
            return False
        if bar.low > min_oc:
            return False
        if bar.volume < 0:
            return False
        return True

    def check_no_zero_price(self, bar: Bar) -> bool:
        """Check that no price field is zero."""
        return bool(bar.open and bar.high and bar.low and bar.close)

    def run_full_check(
        self,
        bars: list[Bar],
        expected_slots: list[tuple[datetime, datetime]],
    ) -> DataQualityGrade:
        """Run all quality checks and return the worst grade."""
        if not bars:
            return DataQualityGrade.UNKNOWN

        worst = DataQualityGrade.PASS

        # Completeness
        completeness = self.check_completeness(bars, expected_slots)
        worst = self._worse(worst, completeness)

        # Duplicates
        if not self.check_no_duplicates(bars):
            worst = self._worse(worst, DataQualityGrade.WARN)

        # Time monotonicity (only check if we have enough bars)
        if len(bars) > 1 and not self.check_monotonic_time(bars):
            worst = self._worse(worst, DataQualityGrade.WARN)

        # Per-bar OHLCV and zero-price checks
        for bar in bars:
            if not self.check_no_zero_price(bar):
                worst = self._worse(worst, DataQualityGrade.FAIL)
                break
            if not self.check_ohlcv_consistency(bar):
                worst = self._worse(worst, DataQualityGrade.WARN)

        return worst

    @staticmethod
    def _worse(a: DataQualityGrade, b: DataQualityGrade) -> DataQualityGrade:
        """Return the worse of two grades.

        Priority: UNKNOWN > FAIL > WARN > PASS
        """
        order = {
            DataQualityGrade.PASS: 0,
            DataQualityGrade.WARN: 1,
            DataQualityGrade.FAIL: 2,
            DataQualityGrade.UNKNOWN: 3,
        }
        return a if order[a] >= order[b] else b

"""Build Bar domain objects from raw data and aggregate across cycles."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Sequence

from hqmts.core.enums import Cycle, DataQualityGrade
from hqmts.core.types import InstrumentId, VersionStr
from hqmts.domain.bar import Bar

logger = logging.getLogger(__name__)

# A-stock trading sessions (Asia/Shanghai)
_MORNING_OPEN = timedelta(hours=9, minutes=30)
_MORNING_CLOSE = timedelta(hours=11, minutes=30)
_AFTERNOON_OPEN = timedelta(hours=13, minutes=0)
_AFTERNOON_CLOSE = timedelta(hours=15, minutes=0)

# Minutes per session
_MORNING_MINUTES = 120  # 09:30-11:30
_AFTERNOON_MINUTES = 120  # 13:00-15:00
_TOTAL_MINUTES = 240

# Cycle to minutes mapping
_CYCLE_MINUTES: dict[Cycle, int] = {
    Cycle.M1: 1,
    Cycle.M5: 5,
    Cycle.M15: 15,
    Cycle.M30: 30,
    Cycle.M60: 60,
}


def _generate_1m_timestamps(trade_date: str) -> list[tuple[datetime, datetime]]:
    """Generate all valid 1m bar [start, end) time slots for a trade date.

    A-stock has exactly 240 one-minute bars per day:
    - Morning: 09:30-11:30 (120 bars)
    - Afternoon: 13:00-15:00 (120 bars)
    """
    year = int(trade_date[:4])
    month = int(trade_date[4:6])
    day = int(trade_date[6:8])
    base = datetime(year, month, day)

    slots: list[tuple[datetime, datetime]] = []

    # Morning session
    for i in range(_MORNING_MINUTES):
        start = base + _MORNING_OPEN + timedelta(minutes=i)
        end = start + timedelta(minutes=1)
        slots.append((start, end))

    # Afternoon session
    for i in range(_AFTERNOON_MINUTES):
        start = base + _AFTERNOON_OPEN + timedelta(minutes=i)
        end = start + timedelta(minutes=1)
        slots.append((start, end))

    return slots


def _generate_cycle_boundaries(
    trade_date: str,
    cycle: Cycle,
) -> list[tuple[datetime, datetime]]:
    """Generate bar time boundaries for a given cycle on a trade date.

    Handles non-uniform boundaries:
    - 60m: [09:30-10:30), [10:30-11:30), [13:00-14:00), [14:00-15:00)
    - Shorter cycles split evenly within each session
    """
    year = int(trade_date[:4])
    month = int(trade_date[4:6])
    day = int(trade_date[6:8])
    base = datetime(year, month, day)

    cycle_min = _CYCLE_MINUTES[cycle]
    boundaries: list[tuple[datetime, datetime]] = []

    # Morning session
    t = base + _MORNING_OPEN
    session_end = base + _MORNING_CLOSE
    while t < session_end:
        end = min(t + timedelta(minutes=cycle_min), session_end)
        boundaries.append((t, end))
        t = end

    # Afternoon session
    t = base + _AFTERNOON_OPEN
    session_end = base + _AFTERNOON_CLOSE
    while t < session_end:
        end = min(t + timedelta(minutes=cycle_min), session_end)
        boundaries.append((t, end))
        t = end

    return boundaries


class BarBuilder:
    """Builds Bar domain objects from raw DataFrames and aggregates across cycles."""

    def __init__(self, data_version: VersionStr) -> None:
        self._data_version = data_version

    def build_1m_bars(
        self,
        instrument_id: str,
        rows: Sequence[dict],
    ) -> list[Bar]:
        """Convert raw data rows to Bar domain objects.

        Each row dict should have: bar_start_time (datetime), open, high, low, close,
        volume (int), amount (Decimal or float).
        """
        bars: list[Bar] = []
        for row in rows:
            start_time = row["bar_start_time"]
            end_time = start_time + timedelta(minutes=1)
            bars.append(
                Bar(
                    instrument_id=InstrumentId(instrument_id),
                    cycle=Cycle.M1,
                    bar_start_time=start_time,
                    bar_end_time=end_time,
                    open=Decimal(str(row["open"])),
                    high=Decimal(str(row["high"])),
                    low=Decimal(str(row["low"])),
                    close=Decimal(str(row["close"])),
                    volume=int(row["volume"]),
                    amount=Decimal(str(row.get("amount", 0))),
                    is_completed=True,  # Historical data is always completed
                    source="tushare",
                    data_version=self._data_version,
                )
            )
        return bars

    def aggregate(self, bars_1m: list[Bar], target_cycle: Cycle) -> list[Bar]:
        """Aggregate 1m bars into target cycle bars.

        Rules:
        - Group by trade date and cycle boundary
        - OHLCV combining: open=first, high=max, low=min, close=last, volume=sum, amount=sum
        - is_completed=True only if all constituent 1m bars are present
        - source='aggregated' for derived bars
        """
        if target_cycle == Cycle.M1:
            return bars_1m

        if not bars_1m:
            return []

        # Sort 1m bars by start time
        sorted_bars = sorted(bars_1m, key=lambda b: b.bar_start_time)
        instrument_id = sorted_bars[0].instrument_id

        # Group by trade date
        by_date: dict[str, list[Bar]] = {}
        for bar in sorted_bars:
            date_str = bar.bar_start_time.strftime("%Y%m%d")
            by_date.setdefault(date_str, []).append(bar)

        result: list[Bar] = []

        for trade_date, date_bars in by_date.items():
            boundaries = _generate_cycle_boundaries(trade_date, target_cycle)

            for start, end in boundaries:
                # Find constituent 1m bars within this boundary
                constituent = [
                    b for b in date_bars if start <= b.bar_start_time < end
                ]

                if not constituent:
                    continue

                open_price = constituent[0].open
                high_price = max(b.high for b in constituent)
                low_price = min(b.low for b in constituent)
                close_price = constituent[-1].close
                total_volume = sum(b.volume for b in constituent)
                total_amount = sum(b.amount for b in constituent)

                # Check completeness: all expected 1m bars should be present
                expected_count = int((end - start).total_seconds() / 60)
                is_completed = len(constituent) == expected_count and all(
                    b.is_completed for b in constituent
                )

                result.append(
                    Bar(
                        instrument_id=instrument_id,
                        cycle=target_cycle,
                        bar_start_time=start,
                        bar_end_time=end,
                        open=open_price,
                        high=high_price,
                        low=low_price,
                        close=close_price,
                        volume=total_volume,
                        amount=total_amount,
                        is_completed=is_completed,
                        source="aggregated",
                        data_version=self._data_version,
                    )
                )

        return result

    @staticmethod
    def get_expected_1m_slots(trade_date: str) -> list[tuple[datetime, datetime]]:
        """Public access to expected 1m bar time slots."""
        return _generate_1m_timestamps(trade_date)

    @staticmethod
    def get_cycle_boundaries(trade_date: str, cycle: Cycle) -> list[tuple[datetime, datetime]]:
        """Public access to cycle boundary generation."""
        return _generate_cycle_boundaries(trade_date, cycle)

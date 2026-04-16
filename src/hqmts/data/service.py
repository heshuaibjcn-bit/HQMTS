"""Data service: orchestrates data fetching, building, quality checking, and persistence."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Sequence

from hqmts.core.enums import Cycle, DataQualityGrade
from hqmts.core.types import InstrumentId, VersionStr
from hqmts.data.bar_builder import BarBuilder
from hqmts.data.client import TushareClient
from hqmts.data.quality import DataQualityChecker
from hqmts.db.models.instrument import InstrumentORM
from hqmts.db.repositories.bar_repo import BarRepository
from hqmts.domain.bar import Bar
from hqmts.domain.instrument import Instrument

logger = logging.getLogger(__name__)


class DataService:
    """Orchestrates the data pipeline: fetch → build → quality check → persist."""

    def __init__(
        self,
        client: TushareClient,
        bar_repo: BarRepository,
        data_version: VersionStr = VersionStr("v1"),
    ) -> None:
        self._client = client
        self._bar_repo = bar_repo
        self._builder = BarBuilder(data_version)
        self._quality = DataQualityChecker()
        self._data_version = data_version

    async def sync_instruments(self) -> int:
        """Fetch stock_basic from Tushare and upsert into instruments table.

        Returns the number of instruments synced.
        """
        df = await self._client.get_stock_basic()
        if df.empty:
            return 0

        # Access session from repository to add InstrumentORM objects
        session = self._bar_repo._session
        count = 0
        for _, row in df.iterrows():
            ts_code = row.get("ts_code", "")
            if not ts_code:
                continue

            instrument_id = ts_code  # Use ts_code as instrument_id for consistency
            symbol = ts_code.split(".")[0]
            exchange_map = {"SZ": "SZSE", "SH": "SSE", "BJ": "BSE"}
            exchange = exchange_map.get(ts_code.split(".")[-1], "UNKNOWN")

            orm = InstrumentORM(
                instrument_id=instrument_id,
                ts_code=ts_code,
                exchange=exchange,
                symbol=symbol,
                name=row.get("name", ""),
                listing_status=row.get("list_status", "L"),
                board_type=_map_board_type(row.get("ts_code", "")),
                is_st="ST" in row.get("name", "").upper(),
            )
            session.merge(orm)
            count += 1

        await session.flush()
        logger.info("Synced %d instruments from Tushare", count)
        return count

    async def get_trade_calendar(self, start: str, end: str) -> list[str]:
        """Get trade dates between start and end (YYYYMMDD format).

        Returns list of YYYYMMDD strings for open trading days.
        """
        df = await self._client.get_trade_cal(start, end)
        if df.empty:
            return []
        return df[df["is_open"] == 1]["cal_date"].tolist()

    async def fetch_and_store_1m_bars(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> list[Bar]:
        """Full pipeline: fetch 1m bars from Tushare → build → quality check → persist.

        Returns the list of Bar domain objects stored.
        """
        # Fetch raw data
        df = await self._client.get_stk_mins(ts_code, start_date, end_date)
        if df.empty:
            logger.warning("No 1m data returned for %s [%s, %s]", ts_code, start_date, end_date)
            return []

        # Convert DataFrame rows to dicts for BarBuilder
        rows = df.to_dict("records")

        # Build Bar domain objects
        instrument_id = ts_code  # ts_code as instrument_id
        bars = self._builder.build_1m_bars(instrument_id, rows)

        if not bars:
            return []

        # Quality check — run per-bar checks without completeness (partial fetches are normal)
        worst_grade = DataQualityGrade.PASS
        bars_by_date: dict[str, list[Bar]] = {}
        for b in bars:
            date_str = b.bar_start_time.strftime("%Y%m%d")
            bars_by_date.setdefault(date_str, []).append(b)

        for date_str, date_bars in bars_by_date.items():
            # Per-bar quality checks (OHLCV consistency, zero-price, duplicates, monotonicity)
            for bar in date_bars:
                if not self._quality.check_no_zero_price(bar):
                    worst_grade = DataQualityChecker._worse(worst_grade, DataQualityGrade.FAIL)
                if not self._quality.check_ohlcv_consistency(bar):
                    worst_grade = DataQualityChecker._worse(worst_grade, DataQualityGrade.WARN)
            if not self._quality.check_no_duplicates(date_bars):
                worst_grade = DataQualityChecker._worse(worst_grade, DataQualityGrade.WARN)
            if len(date_bars) > 1 and not self._quality.check_monotonic_time(date_bars):
                worst_grade = DataQualityChecker._worse(worst_grade, DataQualityGrade.WARN)

        logger.info(
            "1m bars quality for %s [%s, %s]: %s (%d bars)",
            ts_code, start_date, end_date, worst_grade.value, len(bars),
        )

        if worst_grade == DataQualityGrade.FAIL:
            logger.error("Data quality FAIL for %s, skipping persist", ts_code)
            return []

        inserted = await self._bar_repo.bulk_upsert(bars)
        logger.info("Persisted %d/%d 1m bars for %s", inserted, len(bars), ts_code)
        return bars

    async def build_and_store_aggregated_bars(
        self,
        instrument_id: str,
        trade_date: str,
        cycles: Sequence[Cycle],
    ) -> dict[Cycle, list[Bar]]:
        """Load 1m bars from DB, aggregate to target cycles, persist results.

        Returns a dict mapping cycle → list of aggregated bars.
        """
        # Parse trade_date
        year = int(trade_date[:4])
        month = int(trade_date[4:6])
        day = int(trade_date[6:8])
        start = datetime(year, month, day, 0, 0)
        end = datetime(year, month, day, 23, 59)

        # Load 1m bars from DB
        bars_1m = await self._bar_repo.get_bars_by_instrument_cycle(
            InstrumentId(instrument_id),
            Cycle.M1,
            start,
            end,
            completed_only=False,
        )

        if not bars_1m:
            logger.warning("No 1m bars found for %s on %s", instrument_id, trade_date)
            return {}

        results: dict[Cycle, list[Bar]] = {}
        for cycle in cycles:
            if cycle == Cycle.M1:
                continue  # Already have 1m bars

            aggregated = self._builder.aggregate(bars_1m, cycle)
            if aggregated:
                inserted = await self._bar_repo.bulk_upsert(aggregated)
                logger.info(
                    "Persisted %d/%d %s bars for %s on %s",
                    inserted, len(aggregated), cycle.value, instrument_id, trade_date,
                )
                results[cycle] = aggregated

        return results


def _map_board_type(ts_code: str) -> str:
    """Map ts_code suffix and symbol prefix to board type."""
    symbol = ts_code.split(".")[0]
    suffix = ts_code.split(".")[-1] if "." in ts_code else ""

    # GEM (创业板) codes start with 300xxx on SZSE
    if suffix == "SZ" and symbol.startswith("300"):
        return "gem"
    # STAR (科创板) codes start with 688xxx on SSE
    if suffix == "SH" and symbol.startswith("688"):
        return "star"
    # BSE (北交所) codes start with 8xxxxx or 4xxxxx
    if suffix == "BJ":
        return "bse"

    return "main"

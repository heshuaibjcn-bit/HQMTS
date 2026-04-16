"""Tests for BarRepository and DataService."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hqmts.core.enums import Cycle, DataQualityGrade
from hqmts.core.types import InstrumentId, VersionStr
from hqmts.data.service import DataService, _map_board_type
from hqmts.db.repositories.bar_repo import BarRepository, _bar_to_orm, _orm_to_bar
from hqmts.domain.bar import Bar


# ── Helpers ──────────────────────────────────────────────────────────────────


def _bar(
    start: datetime,
    instrument_id: str = "000001.SZ",
    cycle: Cycle = Cycle.M1,
    close: str = "10.00",
    volume: int = 1000,
) -> Bar:
    return Bar(
        instrument_id=InstrumentId(instrument_id),
        cycle=cycle,
        bar_start_time=start,
        bar_end_time=start + timedelta(minutes=1),
        open=Decimal("10.00"),
        high=Decimal("10.50"),
        low=Decimal("9.50"),
        close=Decimal(close),
        volume=volume,
        amount=Decimal("10000"),
        is_completed=True,
        source="tushare",
        data_version=VersionStr("v1"),
    )


def _make_bar_orm(**overrides: Any) -> MagicMock:
    """Create a mock BarORM-like object."""
    defaults = {
        "instrument_id": "000001.SZ",
        "cycle": "1m",
        "bar_start_time": datetime(2024, 1, 2, 9, 30),
        "bar_end_time": datetime(2024, 1, 2, 9, 31),
        "open": Decimal("10.00"),
        "high": Decimal("10.50"),
        "low": Decimal("9.50"),
        "close": Decimal("10.00"),
        "volume": 1000,
        "amount": Decimal("10000"),
        "is_completed": True,
        "source": "tushare",
        "data_version": "v1",
        "quality": "pass",
    }
    defaults.update(overrides)
    orm = MagicMock()
    for k, v in defaults.items():
        setattr(orm, k, v)
    return orm


# ── BarRepository Tests ──────────────────────────────────────────────────────


class TestBarRepository:
    def _make_repo(self) -> tuple[BarRepository, AsyncMock]:
        session = AsyncMock()
        repo = BarRepository(session)
        return repo, session

    @pytest.mark.asyncio
    async def test_get_bars_by_instrument_cycle(self):
        repo, session = self._make_repo()

        # Mock SQLAlchemy result chain
        mock_orm = _make_bar_orm()
        scalar_result = MagicMock()
        scalar_result.all.return_value = [mock_orm]
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalar_result
        session.execute = AsyncMock(return_value=exec_result)

        bars = await repo.get_bars_by_instrument_cycle(
            InstrumentId("000001.SZ"),
            Cycle.M1,
            datetime(2024, 1, 2, 9, 30),
            datetime(2024, 1, 2, 15, 0),
        )
        assert len(bars) == 1
        assert bars[0].instrument_id == InstrumentId("000001.SZ")

    @pytest.mark.asyncio
    async def test_get_latest_bar(self):
        repo, session = self._make_repo()

        mock_orm = _make_bar_orm()
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = mock_orm
        session.execute = AsyncMock(return_value=exec_result)

        bar = await repo.get_latest_bar(InstrumentId("000001.SZ"), Cycle.M1)
        assert bar is not None
        assert bar.instrument_id == InstrumentId("000001.SZ")

    @pytest.mark.asyncio
    async def test_get_latest_bar_none(self):
        repo, session = self._make_repo()

        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=exec_result)

        bar = await repo.get_latest_bar(InstrumentId("000001.SZ"), Cycle.M1)
        assert bar is None

    @pytest.mark.asyncio
    async def test_bulk_upsert_inserts_new(self):
        repo, session = self._make_repo()

        # Mock: no existing bar found
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=exec_result)

        bars = [_bar(start=datetime(2024, 1, 2, 9, 30))]
        inserted = await repo.bulk_upsert(bars)
        assert inserted == 1
        session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_bulk_upsert_skips_existing(self):
        repo, session = self._make_repo()

        # Mock: bar already exists
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = _make_bar_orm()
        session.execute = AsyncMock(return_value=exec_result)

        bars = [_bar(start=datetime(2024, 1, 2, 9, 30))]
        inserted = await repo.bulk_upsert(bars)
        assert inserted == 0

    @pytest.mark.asyncio
    async def test_bulk_upsert_empty(self):
        repo, session = self._make_repo()
        inserted = await repo.bulk_upsert([])
        assert inserted == 0


# ── Bar ORM Mapping Tests ────────────────────────────────────────────────────


class TestBarMapping:
    def test_bar_to_orm_round_trip(self):
        bar = _bar(start=datetime(2024, 1, 2, 9, 30))
        orm = _bar_to_orm(bar)
        assert orm.instrument_id == "000001.SZ"
        assert orm.cycle == "1m"
        assert orm.volume == 1000
        assert orm.is_completed is True

        # Round trip
        bar2 = _orm_to_bar(orm)
        assert bar2.instrument_id == bar.instrument_id
        assert bar2.cycle == bar.cycle
        assert bar2.close == bar.close
        assert bar2.volume == bar.volume
        assert bar2.source == bar.source


# ── DataService Tests ────────────────────────────────────────────────────────


class TestDataService:
    def _make_service(self) -> tuple[DataService, AsyncMock, AsyncMock]:
        client = AsyncMock()
        bar_repo = AsyncMock(spec=BarRepository)
        bar_repo._session = AsyncMock()
        service = DataService(client, bar_repo)
        return service, client, bar_repo

    @pytest.mark.asyncio
    async def test_sync_instruments(self):
        service, client, bar_repo = self._make_service()

        import pandas as pd
        df = pd.DataFrame({
            "ts_code": ["000001.SZ", "300001.SZ", "688001.SH"],
            "name": ["TestStock", "GEMStock", "STARStock"],
            "list_status": ["L", "L", "L"],
        })
        client.get_stock_basic = AsyncMock(return_value=df)

        count = await service.sync_instruments()
        assert count == 3
        bar_repo._session.merge.assert_called()

    @pytest.mark.asyncio
    async def test_get_trade_calendar(self):
        service, client, _ = self._make_service()

        import pandas as pd
        df = pd.DataFrame({
            "cal_date": ["20240102", "20240103", "20240104"],
            "is_open": [1, 1, 0],
        })
        client.get_trade_cal = AsyncMock(return_value=df)

        dates = await service.get_trade_calendar("20240102", "20240104")
        assert dates == ["20240102", "20240103"]

    @pytest.mark.asyncio
    async def test_get_trade_calendar_empty(self):
        service, client, _ = self._make_service()

        import pandas as pd
        client.get_trade_cal = AsyncMock(return_value=pd.DataFrame())

        dates = await service.get_trade_calendar("20240101", "20240101")
        assert dates == []

    @pytest.mark.asyncio
    async def test_fetch_and_store_1m_bars(self):
        service, client, bar_repo = self._make_service()

        import pandas as pd
        df = pd.DataFrame({
            "bar_start_time": [datetime(2024, 1, 2, 9, 30)],
            "open": [10.0],
            "high": [10.5],
            "low": [9.5],
            "close": [10.0],
            "volume": [1000],
            "amount": [10000.0],
        })
        client.get_stk_mins = AsyncMock(return_value=df)
        bar_repo.bulk_upsert = AsyncMock(return_value=1)

        bars = await service.fetch_and_store_1m_bars("000001.SZ", "20240102", "20240102")
        assert len(bars) == 1
        assert bars[0].instrument_id == InstrumentId("000001.SZ")
        bar_repo.bulk_upsert.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fetch_and_store_1m_bars_empty(self):
        service, client, _ = self._make_service()

        import pandas as pd
        client.get_stk_mins = AsyncMock(return_value=pd.DataFrame())

        bars = await service.fetch_and_store_1m_bars("000001.SZ", "20240102", "20240102")
        assert bars == []

    @pytest.mark.asyncio
    async def test_build_and_store_aggregated_bars(self):
        service, client, bar_repo = self._make_service()

        # Mock 1m bars from DB
        bars_1m = [
            _bar(start=datetime(2024, 1, 2, 9, 30) + timedelta(minutes=i), close=str(10 + i * 0.01))
            for i in range(5)
        ]
        bar_repo.get_bars_by_instrument_cycle = AsyncMock(return_value=bars_1m)
        bar_repo.bulk_upsert = AsyncMock(return_value=1)

        results = await service.build_and_store_aggregated_bars(
            "000001.SZ", "20240102", [Cycle.M5]
        )
        assert Cycle.M5 in results
        assert len(results[Cycle.M5]) == 1  # 5 bars fit into one 5m bar
        bar_repo.bulk_upsert.assert_awaited()

    @pytest.mark.asyncio
    async def test_build_and_store_no_1m_bars(self):
        service, client, bar_repo = self._make_service()

        bar_repo.get_bars_by_instrument_cycle = AsyncMock(return_value=[])

        results = await service.build_and_store_aggregated_bars(
            "000001.SZ", "20240102", [Cycle.M5]
        )
        assert results == {}


# ── Board Type Mapping Tests ─────────────────────────────────────────────────


class TestBoardTypeMapping:
    def test_gem_stock(self):
        assert _map_board_type("300001.SZ") == "gem"

    def test_star_stock(self):
        assert _map_board_type("688001.SH") == "star"

    def test_bse_stock(self):
        assert _map_board_type("830001.BJ") == "bse"

    def test_main_stock_sz(self):
        assert _map_board_type("000001.SZ") == "main"

    def test_main_stock_sh(self):
        assert _map_board_type("600001.SH") == "main"

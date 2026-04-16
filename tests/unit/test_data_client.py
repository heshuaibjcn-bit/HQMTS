"""Tests for Tushare data client."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from hqmts.data.client import TushareClient, TushareRateLimiter
from hqmts.infra.config import TushareConfig


class TestTushareRateLimiter:
    @pytest.mark.asyncio
    async def test_acquire_within_budget(self):
        limiter = TushareRateLimiter(calls_per_minute=10)
        # Should not block for 10 calls
        for _ in range(10):
            await limiter.acquire()
        # Tokens should be depleted
        assert limiter._tokens < 1.0

    @pytest.mark.asyncio
    async def test_tokens_refill_over_time(self):
        limiter = TushareRateLimiter(calls_per_minute=60)
        # Drain tokens
        limiter._tokens = 0.0
        # Simulate time passing
        limiter._last_refill = asyncio.get_event_loop().time() - 1.0
        limiter._refill()
        # Should have ~1 token after 1 second (60/min = 1/sec)
        assert limiter._tokens >= 0.9

    @pytest.mark.asyncio
    async def test_max_tokens_capped(self):
        limiter = TushareRateLimiter(calls_per_minute=10)
        # Refill with lots of time passed
        limiter._last_refill = 0.0
        limiter._refill()
        assert limiter._tokens <= 10.0


class TestTushareClient:
    def _make_config(self) -> TushareConfig:
        return TushareConfig(api_token="test_token", retry_max_attempts=2, retry_delay_seconds=0.01)

    def _make_client(self) -> TushareClient:
        return TushareClient(self._make_config())

    @pytest.mark.asyncio
    async def test_standardize_columns(self):
        df = pd.DataFrame({"trade_time": ["2024-01-01"], "vol": [1000], "close": [10.0]})
        result = TushareClient._standardize_columns(df)
        assert "bar_start_time" in result.columns
        assert "volume" in result.columns
        assert "close" in result.columns

    @pytest.mark.asyncio
    async def test_call_success(self):
        client = self._make_client()
        mock_api = MagicMock()
        mock_api.stock_basic.return_value = pd.DataFrame({"ts_code": ["000001.SZ"]})

        with patch.object(client, "_get_api", return_value=mock_api):
            df = await client.get_stock_basic()
            assert len(df) == 1
            assert "ts_code" in df.columns

    @pytest.mark.asyncio
    async def test_call_returns_empty_on_none(self):
        client = self._make_client()
        mock_api = MagicMock()
        mock_api.stock_basic.return_value = None

        with patch.object(client, "_get_api", return_value=mock_api):
            df = await client.get_stock_basic()
            assert df.empty

    @pytest.mark.asyncio
    async def test_call_retries_on_rate_limit(self):
        client = self._make_client()
        mock_api = MagicMock()

        # First call raises rate limit, second succeeds
        mock_api.daily.side_effect = [
            Exception("api limit exceeded"),
            pd.DataFrame({"ts_code": ["000001.SZ"], "close": [10.0]}),
        ]

        with patch.object(client, "_get_api", return_value=mock_api):
            df = await client.get_daily("000001.SZ", "20240101", "20240101")
            assert len(df) == 1
            assert mock_api.daily.call_count == 2

    @pytest.mark.asyncio
    async def test_call_raises_non_retryable_error(self):
        client = self._make_client()
        mock_api = MagicMock()
        mock_api.daily.side_effect = Exception("invalid parameter")

        with patch.object(client, "_get_api", return_value=mock_api):
            with pytest.raises(Exception, match="invalid parameter"):
                await client.get_daily("000001.SZ", "20240101", "20240101")

    @pytest.mark.asyncio
    async def test_call_raises_after_max_retries(self):
        config = TushareConfig(api_token="test", retry_max_attempts=2, retry_delay_seconds=0.01)
        client = TushareClient(config)
        mock_api = MagicMock()
        mock_api.daily.side_effect = Exception("api limit hit again")

        with patch.object(client, "_get_api", return_value=mock_api):
            with pytest.raises(Exception, match="api limit hit again"):
                await client.get_daily("000001.SZ", "20240101", "20240101")
            assert mock_api.daily.call_count == 2

    @pytest.mark.asyncio
    async def test_get_stk_mins_chunks_by_date(self):
        client = self._make_client()
        mock_api = MagicMock()

        # Trade calendar returns 2 trade dates
        mock_api.trade_cal.return_value = pd.DataFrame({
            "cal_date": ["20240102", "20240103"],
            "is_open": [1, 1],
        })
        # Each date returns some minute data
        mock_api.stk_mins.side_effect = [
            pd.DataFrame({"ts_code": ["000001.SZ"], "close": [10.0]}),
            pd.DataFrame({"ts_code": ["000001.SZ"], "close": [10.5]}),
        ]

        with patch.object(client, "_get_api", return_value=mock_api):
            df = await client.get_stk_mins("000001.SZ", "20240102", "20240103")
            assert len(df) == 2

    @pytest.mark.asyncio
    async def test_get_stk_mins_empty_calendar(self):
        client = self._make_client()
        mock_api = MagicMock()
        mock_api.trade_cal.return_value = pd.DataFrame(columns=["cal_date", "is_open"])

        with patch.object(client, "_get_api", return_value=mock_api):
            df = await client.get_stk_mins("000001.SZ", "20240101", "20240101")
            assert df.empty

    @pytest.mark.asyncio
    async def test_get_trade_cal(self):
        client = self._make_client()
        mock_api = MagicMock()
        mock_api.trade_cal.return_value = pd.DataFrame({
            "cal_date": ["20240101", "20240102"],
            "is_open": [0, 1],
        })

        with patch.object(client, "_get_api", return_value=mock_api):
            df = await client.get_trade_cal("20240101", "20240102")
            assert len(df) == 2

    @pytest.mark.asyncio
    async def test_get_suspend_d(self):
        client = self._make_client()
        mock_api = MagicMock()
        mock_api.suspend_d.return_value = pd.DataFrame({"ts_code": ["000001.SZ"]})

        with patch.object(client, "_get_api", return_value=mock_api):
            df = await client.get_suspend_d("20240102")
            assert len(df) == 1

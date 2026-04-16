"""Tushare Pro data client with rate limiting and retry."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import pandas as pd

from hqmts.infra.config import TushareConfig

logger = logging.getLogger(__name__)

# Tushare column name mapping to system convention
_COLUMN_MAP: dict[str, str] = {
    "trade_time": "bar_start_time",
    "vol": "volume",
    "pre_close": "pre_close",
    "change": "change",
    "pct_chg": "pct_chg",
}


class TushareRateLimiter:
    """Token-bucket rate limiter for Tushare API calls."""

    def __init__(self, calls_per_minute: int = 200) -> None:
        self._max_tokens = calls_per_minute
        self._tokens = float(calls_per_minute)
        self._refill_rate = calls_per_minute / 60.0  # tokens per second
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available."""
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
            # Wait a bit before checking again
            await asyncio.sleep(0.05)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._max_tokens, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now


class TushareClient:
    """Async wrapper around tushare.pro_api with retry and rate limiting.

    All methods return pandas DataFrames with standardized column names.
    Synchronous tushare calls are wrapped in asyncio.to_thread().
    """

    def __init__(self, config: TushareConfig) -> None:
        self._config = config
        self._limiter = TushareRateLimiter(config.rate_limit_per_minute)
        self._api: Any = None

    def _get_api(self) -> Any:
        """Lazy-initialize tushare pro_api."""
        if self._api is None:
            import tushare as ts

            ts.set_token(self._config.api_token)
            self._api = ts.pro_api()
        return self._api

    async def _call(self, method_name: str, **kwargs: Any) -> pd.DataFrame:
        """Execute a tushare API call with rate limiting and retry."""
        api = self._get_api()
        func = getattr(api, method_name)

        last_error: Exception | None = None
        for attempt in range(self._config.retry_max_attempts):
            await self._limiter.acquire()
            try:
                result = await asyncio.to_thread(func, **kwargs)
                if result is None:
                    return pd.DataFrame()
                return self._standardize_columns(result)
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                # Rate limit or temporary errors: retry with backoff
                if "limit" in error_str or "frequency" in error_str or "timeout" in error_str:
                    delay = self._config.retry_delay_seconds * (2 ** attempt)
                    logger.warning(
                        "Tushare API retry %d/%d for %s: %s",
                        attempt + 1,
                        self._config.retry_max_attempts,
                        method_name,
                        e,
                    )
                    await asyncio.sleep(delay)
                    continue
                # Non-retryable error
                raise
        raise last_error  # type: ignore[misc]

    @staticmethod
    def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Rename tushare columns to system convention."""
        return df.rename(columns=_COLUMN_MAP)

    async def get_stock_basic(self, **filters: Any) -> pd.DataFrame:
        """Fetch stock basic info (list_status='L' for listed stocks)."""
        return await self._call("stock_basic", exchange="", list_status="L", **filters)

    async def get_trade_cal(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch trade calendar. Dates in YYYYMMDD format."""
        return await self._call("trade_cal", exchange="SSE", start_date=start_date, end_date=end_date)

    async def get_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch daily bars for a stock."""
        return await self._call("daily", ts_code=ts_code, start_date=start_date, end_date=end_date)

    async def get_stk_mins(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        freq: str = "1min",
    ) -> pd.DataFrame:
        """Fetch minute-level bars, chunking by date if needed.

        Tushare stk_mins API returns max ~5000 rows per call.
        We chunk by date to stay within limits.
        """
        all_dfs: list[pd.DataFrame] = []

        # Get trade calendar for the range
        cal_df = await self.get_trade_cal(start_date, end_date)
        if cal_df.empty:
            return pd.DataFrame()

        trade_dates = cal_df[cal_df["is_open"] == 1]["cal_date"].tolist()

        for date in trade_dates:
            chunk = await self._call(
                "stk_mins",
                ts_code=ts_code,
                start_date=f"{date} 09:00:00",
                end_date=f"{date} 15:00:00",
                freq=freq,
            )
            if not chunk.empty:
                all_dfs.append(chunk)

        if not all_dfs:
            return pd.DataFrame()
        return pd.concat(all_dfs, ignore_index=True)

    async def get_index_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch index daily bars."""
        return await self._call("index_daily", ts_code=ts_code, start_date=start_date, end_date=end_date)

    async def get_adj_factor(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch adjustment factors."""
        return await self._call("adj_factor", ts_code=ts_code, start_date=start_date, end_date=end_date)

    async def get_suspend_d(self, trade_date: str) -> pd.DataFrame:
        """Fetch suspended stocks for a trade date."""
        return await self._call("suspend_d", trade_date=trade_date)

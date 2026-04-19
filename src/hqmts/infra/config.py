"""Configuration loader using Pydantic Settings with YAML overlay."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings

CONFIGS_DIR = Path(__file__).resolve().parents[3] / "configs"


class DatabaseConfig(BaseSettings):
    url: str = "postgresql+asyncpg://hqmts:hqmts@localhost:5432/hqmts"
    pool_size: int = 10
    max_overflow: int = 20
    echo: bool = False


class RedisConfig(BaseSettings):
    url: str = "redis://localhost:6379/0"
    pool_size: int = 10


class LoggingConfig(BaseSettings):
    level: str = "INFO"
    format: Literal["json", "text"] = "json"


class MarketConfig(BaseSettings):
    timezone: str = "Asia/Shanghai"
    morning_open: str = "09:30"
    morning_close: str = "11:30"
    afternoon_open: str = "13:00"
    afternoon_close: str = "15:00"
    lot_size: int = 100
    stamp_tax_rate: float = 0.001
    commission_rate: float = 0.0003
    commission_min: float = 5.0
    slippage_default: float = 0.0


class RiskConfig(BaseSettings):
    max_position_ratio: float = 0.95
    daily_loss_limit: float = 0.03
    intraday_drawdown_limit: float = 0.02
    min_available_cash: float = 10000.0
    single_instrument_max_ratio: float = 0.20
    order_frequency_limit_per_min: int = 10


class DataConfig(BaseSettings):
    bar_cycles: list[str] = Field(default=["1m", "5m", "15m", "30m", "60m"])
    primary_cycle: str = "1m"
    stale_price_threshold_seconds: int = 30
    data_quality_check: bool = True


class TushareConfig(BaseSettings):
    api_token: str = ""
    rate_limit_per_minute: int = 200
    retry_max_attempts: int = 3
    retry_delay_seconds: float = 0.5
    cache_dir: str = ".tushare_cache"


class BacktestSettings(BaseSettings):
    initial_cash: float = 1_000_000.0
    commission_rate: float = 0.0003
    commission_min: float = 5.0
    stamp_tax_rate: float = 0.001
    slippage: float = 0.0
    participation_rate: float = 0.25


class AgentConfig(BaseSettings):
    enabled: bool = False
    tool_gateway_enabled: bool = False
    max_concurrent_tasks: int = 5
    task_timeout_seconds: int = 300
    live_fail_closed: bool = True


class AuthConfig(BaseSettings):
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    max_sessions: int = 3


class LLMConfig(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"


class AppConfig(BaseSettings):
    name: str = "HQMTS"
    version: str = "0.1.0"


class Settings(BaseSettings):
    app: AppConfig = AppConfig()
    environment: Literal["research", "backtest", "paper", "live"] = "research"
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    logging: LoggingConfig = LoggingConfig()
    market: MarketConfig = MarketConfig()
    risk: RiskConfig = RiskConfig()
    data: DataConfig = DataConfig()
    tushare: TushareConfig = TushareConfig()
    backtest: BacktestSettings = BacktestSettings()
    agent: AgentConfig = AgentConfig()
    auth: AuthConfig = AuthConfig()
    llm: LLMConfig = LLMConfig()


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_settings(env: str | None = None) -> Settings:
    """Load settings with YAML overlay.

    1. Load base.yaml as defaults
    2. Overlay with environment-specific config (research/backtest/paper/live)
    3. Allow env var / .env file overrides via Pydantic Settings
    """
    base_data = _load_yaml(CONFIGS_DIR / "base.yaml")

    effective_env = env or base_data.get("environment", "research")
    env_data = _load_yaml(CONFIGS_DIR / f"{effective_env}.yaml")

    # Deep merge: env overrides base
    merged = _deep_merge(base_data, env_data)
    merged.pop("environment", None)  # handled by Settings.environment field

    settings = Settings(**merged)
    # Override environment if explicitly passed
    if env:
        settings.environment = env  # type: ignore[assignment]
    return settings


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result

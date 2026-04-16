"""Tests for risk rules."""

import pytest
from datetime import time
from decimal import Decimal

from hqmts.risk.engine import RiskContext
from hqmts.risk.rules.account import (
    DailyLossLimitRule,
    IntradayDrawdownRule,
    MinAvailableCashRule,
    TotalPositionLimitRule,
)
from hqmts.risk.rules.order import (
    InvalidPriceCheckRule,
    MinLotSizeCheckRule,
    FrequentCancelLimitRule,
    DuplicateOrderCheckRule,
)
from hqmts.risk.rules.strategy import (
    ConsecutiveLossHaltRule,
    StrategyDailyLossLimitRule,
    StrategyPositionLimitRule,
    CooldownPeriodRule,
)
from hqmts.risk.rules.instrument import (
    BlacklistRule,
    LiquidityFilterRule,
    SingleInstrumentMaxExposureRule,
    STFilterRule,
)
from hqmts.risk.rules.market import (
    IndexDropHaltRule,
    ExtremeVolatilityHaltRule,
)
from hqmts.core.enums import RiskResultType


@pytest.fixture
def base_context():
    return RiskContext(
        account_total_asset=1000000,
        account_available_cash=500000,
        account_market_value=500000,
        account_pnl_intraday=0,
        account_drawdown_intraday=0,
    )


# ── Account Rules ────────────────────────────────────────────────────────────


class TestTotalPositionLimitRule:
    @pytest.mark.asyncio
    async def test_pass_when_below_limit(self, base_context):
        rule = TotalPositionLimitRule(max_ratio=0.95)
        result = await rule.check(base_context)
        assert result is None  # Passes

    @pytest.mark.asyncio
    async def test_reject_when_at_limit(self, base_context):
        base_context.account_market_value = 950000
        rule = TotalPositionLimitRule(max_ratio=0.95)
        result = await rule.check(base_context)
        assert result is not None
        assert result.result_type == RiskResultType.REJECT


class TestDailyLossLimitRule:
    @pytest.mark.asyncio
    async def test_pass_when_no_loss(self, base_context):
        rule = DailyLossLimitRule()
        result = await rule.check(base_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_force_flatten_on_excessive_loss(self, base_context):
        base_context.account_pnl_intraday = -35000  # 3.5% of 1M
        rule = DailyLossLimitRule(loss_limit=0.03)
        result = await rule.check(base_context)
        assert result is not None
        assert result.result_type == RiskResultType.FORCE_FLATTEN


class TestMinAvailableCashRule:
    @pytest.mark.asyncio
    async def test_resize_when_below_min(self, base_context):
        base_context.side = "buy"
        base_context.price = Decimal("100")
        base_context.quantity = 5000  # 500,000 order > 500,000 - 10,000
        rule = MinAvailableCashRule(min_cash=10000)
        result = await rule.check(base_context)
        assert result is not None
        assert result.result_type == RiskResultType.RESIZE
        assert result.resized_quantity is not None


# ── Strategy Rules ───────────────────────────────────────────────────────────


class TestConsecutiveLossHaltRule:
    @pytest.mark.asyncio
    async def test_pass_when_below_threshold(self, base_context):
        base_context.strategy_consecutive_losses = 3
        rule = ConsecutiveLossHaltRule(max_consecutive_losses=5)
        result = await rule.check(base_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_reject_on_excessive_losses(self, base_context):
        base_context.strategy_consecutive_losses = 5
        rule = ConsecutiveLossHaltRule(max_consecutive_losses=5)
        result = await rule.check(base_context)
        assert result is not None
        assert result.result_type == RiskResultType.REJECT


# ── Instrument Rules ─────────────────────────────────────────────────────────


class TestBlacklistRule:
    @pytest.mark.asyncio
    async def test_reject_blacklisted(self, base_context):
        base_context.instrument_id = "000001.SZ"
        rule = BlacklistRule(blacklist={"000001.SZ"})
        result = await rule.check(base_context)
        assert result is not None
        assert result.result_type == RiskResultType.REJECT

    @pytest.mark.asyncio
    async def test_pass_non_blacklisted(self, base_context):
        base_context.instrument_id = "000001.SZ"
        rule = BlacklistRule(blacklist={"000002.SZ"})
        result = await rule.check(base_context)
        assert result is None


class TestSTFilterRule:
    @pytest.mark.asyncio
    async def test_reject_st_stock(self, base_context):
        base_context.instrument_is_st = True
        base_context.instrument_id = "000001.SZ"
        rule = STFilterRule()
        result = await rule.check(base_context)
        assert result is not None
        assert result.result_type == RiskResultType.REJECT

    @pytest.mark.asyncio
    async def test_pass_non_st(self, base_context):
        base_context.instrument_is_st = False
        rule = STFilterRule()
        result = await rule.check(base_context)
        assert result is None


# ── Order Rules ──────────────────────────────────────────────────────────────


class TestInvalidPriceCheckRule:
    @pytest.mark.asyncio
    async def test_reject_zero_price(self, base_context):
        base_context.price = 0
        rule = InvalidPriceCheckRule()
        result = await rule.check(base_context)
        assert result is not None
        assert result.result_type == RiskResultType.REJECT

    @pytest.mark.asyncio
    async def test_pass_valid_price(self, base_context):
        base_context.price = 100.50
        rule = InvalidPriceCheckRule()
        result = await rule.check(base_context)
        assert result is None


class TestMinLotSizeCheckRule:
    @pytest.mark.asyncio
    async def test_resize_non_aligned_quantity(self, base_context):
        base_context.quantity = 150  # Not aligned to 100
        rule = MinLotSizeCheckRule(lot_size=100)
        result = await rule.check(base_context)
        assert result is not None
        assert result.result_type == RiskResultType.RESIZE
        assert result.resized_quantity == 100

    @pytest.mark.asyncio
    async def test_pass_aligned_quantity(self, base_context):
        base_context.quantity = 300
        rule = MinLotSizeCheckRule(lot_size=100)
        result = await rule.check(base_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_reject_below_lot_size(self, base_context):
        base_context.quantity = 50
        rule = MinLotSizeCheckRule(lot_size=100)
        result = await rule.check(base_context)
        assert result is not None
        assert result.result_type == RiskResultType.REJECT


class TestFrequentCancelLimitRule:
    @pytest.mark.asyncio
    async def test_pass_within_limit(self, base_context):
        base_context.existing_order_count_last_min = 5
        rule = FrequentCancelLimitRule(max_orders_per_min=10)
        result = await rule.check(base_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_delay_on_exceeded(self, base_context):
        base_context.existing_order_count_last_min = 10
        rule = FrequentCancelLimitRule(max_orders_per_min=10)
        result = await rule.check(base_context)
        assert result is not None
        assert result.result_type == RiskResultType.DELAY


class TestDuplicateOrderCheckRule:
    @pytest.mark.asyncio
    async def test_pass_few_same_side_orders(self, base_context):
        base_context.recent_same_side_orders = 1
        rule = DuplicateOrderCheckRule(max_same_side_orders=3)
        result = await rule.check(base_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_reject_potential_duplicate(self, base_context):
        base_context.recent_same_side_orders = 3
        rule = DuplicateOrderCheckRule(max_same_side_orders=3)
        result = await rule.check(base_context)
        assert result is not None
        assert result.result_type == RiskResultType.REJECT
        assert "duplicate" in result.reason.lower()


class TestCooldownPeriodRule:
    @pytest.mark.asyncio
    async def test_pass_when_no_recent_trade(self, base_context):
        base_context.strategy_last_trade_time = None
        rule = CooldownPeriodRule(cooldown_seconds=300)
        result = await rule.check(base_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_delay_during_cooldown(self, base_context):
        from datetime import datetime, timedelta
        base_context.strategy_last_trade_time = datetime.now() - timedelta(seconds=60)
        base_context.check_time = datetime.now()
        rule = CooldownPeriodRule(cooldown_seconds=300)
        result = await rule.check(base_context)
        assert result is not None
        assert result.result_type == RiskResultType.DELAY

    @pytest.mark.asyncio
    async def test_pass_after_cooldown(self, base_context):
        from datetime import datetime, timedelta
        base_context.strategy_last_trade_time = datetime.now() - timedelta(seconds=400)
        base_context.check_time = datetime.now()
        rule = CooldownPeriodRule(cooldown_seconds=300)
        result = await rule.check(base_context)
        assert result is None


class TestIndexDropHaltRule:
    @pytest.mark.asyncio
    async def test_pass_normal_market(self, base_context):
        base_context.index_drop_pct = Decimal("-0.01")
        rule = IndexDropHaltRule(drop_threshold=-0.03)
        result = await rule.check(base_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_reject_on_index_crash(self, base_context):
        base_context.index_drop_pct = Decimal("-0.04")
        rule = IndexDropHaltRule(drop_threshold=-0.03)
        result = await rule.check(base_context)
        assert result is not None
        assert result.result_type == RiskResultType.REJECT


class TestExtremeVolatilityHaltRule:
    @pytest.mark.asyncio
    async def test_pass_normal_volatility(self, base_context):
        base_context.market_volatility = Decimal("0.02")
        rule = ExtremeVolatilityHaltRule(volatility_threshold=0.05)
        result = await rule.check(base_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_reject_on_extreme_volatility(self, base_context):
        base_context.market_volatility = Decimal("0.06")
        rule = ExtremeVolatilityHaltRule(volatility_threshold=0.05)
        result = await rule.check(base_context)
        assert result is not None
        assert result.result_type == RiskResultType.REJECT

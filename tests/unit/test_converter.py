"""Tests for SignalConverter — side mapping, validation, intent/order creation."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from hqmts.core.enums import (
    Cycle,
    RiskResultType,
    Side,
    SignalType,
)
from hqmts.core.exceptions import (
    ExpiredSignalError,
    MissingDecisionSnapshotError,
)
from hqmts.core.types import InstrumentId, SignalId, StrategyInstanceId, VersionStr, now_shanghai
from hqmts.domain.risk import RiskCheckResult
from hqmts.domain.signal import Signal
from hqmts.execution.converter import SignalConverter
from hqmts.risk.engine import RiskContext, RiskEngine
from hqmts.risk.final_check import FinalCheckContext, FinalCheckResult, FinalPreSubmitCheck


def _make_signal(
    signal_type: SignalType = SignalType.OPEN_LONG,
    expired: bool = False,
    with_decision: bool = True,
) -> Signal:
    now = now_shanghai()
    return Signal(
        signal_id=SignalId(str(uuid.uuid4())),
        strategy_instance_id=StrategyInstanceId("strat-001"),
        strategy_version=VersionStr("v1"),
        decision_time=now,
        instrument_id=InstrumentId("000001.SZ"),
        signal_type=signal_type,
        valid_until=now - timedelta(seconds=1) if expired else now + timedelta(minutes=5),
        decision_snapshot_id="ds-001" if with_decision else None,
        cycle=Cycle.M1,
        created_at=now,
    )


@pytest.fixture
def risk_engine():
    return RiskEngine()


@pytest.fixture
def final_check():
    return FinalPreSubmitCheck()


@pytest.fixture
def converter(risk_engine, final_check):
    return SignalConverter(risk_engine, final_check)


class TestDetermineSide:
    """Verify all 5 signal types map to correct Side."""

    @pytest.mark.parametrize(
        "signal_type,expected_side",
        [
            (SignalType.OPEN_LONG, Side.BUY),
            (SignalType.CLOSE_LONG, Side.SELL),
            (SignalType.OPEN_SHORT, Side.SELL),
            (SignalType.CLOSE_SHORT, Side.BUY),
            (SignalType.FLATTEN, Side.SELL),
        ],
    )
    async def test_side_mapping(self, converter, signal_type, expected_side):
        signal = _make_signal(signal_type)
        side = converter._determine_side(signal)
        assert side == expected_side

    async def test_hold_raises(self, converter):
        signal = _make_signal(SignalType.HOLD)
        with pytest.raises(ValueError, match="Cannot determine side"):
            converter._determine_side(signal)


class TestSignalValidation:
    async def test_expired_signal_raises(self, converter):
        signal = _make_signal(expired=True)
        with pytest.raises(ExpiredSignalError):
            await converter.validate_signal_for_live(signal)

    async def test_missing_decision_snapshot_raises(self, converter):
        signal = _make_signal(with_decision=False)
        with pytest.raises(MissingDecisionSnapshotError):
            await converter.validate_signal_for_live(signal)

    async def test_valid_signal_passes(self, converter):
        signal = _make_signal()
        # Should not raise
        await converter.validate_signal_for_live(signal)


class TestPreTradeRisk:
    async def test_risk_check_called(self, converter, risk_engine):
        signal = _make_signal()
        context = RiskContext(
            account_total_asset=1000000,
            account_available_cash=500000,
            account_market_value=500000,
            account_pnl_intraday=0,
            account_drawdown_intraday=0,
        )
        result = await converter.run_pre_trade_risk(signal, context)
        assert isinstance(result, RiskCheckResult)
        assert result.result_type == RiskResultType.ALLOW


class TestCreateExecutionIntent:
    async def test_creates_intent_with_correct_fields(self, converter):
        signal = _make_signal(SignalType.OPEN_LONG)
        intent = await converter.create_execution_intent(
            signal=signal,
            account_id="acc-001",
            reference_price=Decimal("10.50"),
            quantity=500,
            reservation_id="res-001",
            risk_check_id="rc-001",
        )
        assert intent.side == Side.BUY
        assert intent.target_quantity == 500
        assert intent.reference_price == Decimal("10.50")
        assert intent.reservation_id == "res-001"
        assert intent.instrument_id == "000001.SZ"

    async def test_short_signal_creates_sell_intent(self, converter):
        signal = _make_signal(SignalType.OPEN_SHORT)
        intent = await converter.create_execution_intent(
            signal=signal,
            account_id="acc-001",
            reference_price=Decimal("15.00"),
            quantity=300,
        )
        assert intent.side == Side.SELL


class TestConvertToOrderRequest:
    async def test_creates_order_request(self, converter):
        signal = _make_signal(SignalType.OPEN_LONG)
        intent = await converter.create_execution_intent(
            signal=signal,
            account_id="acc-001",
            reference_price=Decimal("10.50"),
            quantity=500,
        )
        order_request = await converter.convert_to_order_request(intent)
        assert order_request.signal_id == signal.signal_id
        assert order_request.side == Side.BUY
        assert order_request.price == Decimal("10.50")
        assert order_request.quantity == 500
        assert order_request.idempotency_key is not None
        assert len(order_request.idempotency_key) > 0

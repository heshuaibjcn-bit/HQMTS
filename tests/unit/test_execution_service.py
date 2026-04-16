"""Tests for ExecutionService — full pipeline orchestration."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hqmts.core.enums import (
    Cycle,
    FinalCheckResult,
    RiskResultType,
    Side,
    SignalType,
)
from hqmts.core.exceptions import RiskRejectError, ForceFlattenError
from hqmts.core.types import InstrumentId, SignalId, StrategyInstanceId, VersionStr
from hqmts.domain.execution import OrderRequest
from hqmts.domain.risk import RiskCheckResult
from hqmts.domain.signal import Signal
from hqmts.execution.converter import SignalConverter
from hqmts.execution.service import ExecutionService
from hqmts.reservation.manager import ReservationManager
from hqmts.risk.engine import RiskContext
from hqmts.risk.final_check import FinalCheckContext, FinalCheckResult as FCResult, FinalPreSubmitCheck


def _make_signal(signal_type: SignalType = SignalType.OPEN_LONG) -> Signal:
    now = datetime.now()
    return Signal(
        signal_id=SignalId(str(uuid.uuid4())),
        strategy_instance_id=StrategyInstanceId("strat-001"),
        strategy_version=VersionStr("v1"),
        decision_time=now,
        instrument_id=InstrumentId("000001.SZ"),
        signal_type=signal_type,
        valid_until=now + timedelta(minutes=5),
        decision_snapshot_id="ds-001",
        cycle=Cycle.M1,
        created_at=now,
    )


def _make_risk_context() -> RiskContext:
    return RiskContext(
        account_total_asset=1000000,
        account_available_cash=500000,
        account_market_value=500000,
        account_pnl_intraday=0,
        account_drawdown_intraday=0,
    )


def _make_final_check_context() -> FinalCheckContext:
    return FinalCheckContext(
        strategy_status="live_running",
        signal_valid_until=datetime.now() + timedelta(minutes=5),
        qmt_adapter_available=True,
        account_risk_status="normal",
        account_available_cash=Decimal("500000"),
        available_quantity=1000,
        reservation_status="active",
        reservation_expires_at=datetime.now() + timedelta(minutes=5),
        has_conflicting_inflight=False,
        kill_switch_active=False,
    )


@pytest.fixture
def mock_converter():
    converter = AsyncMock(spec=SignalConverter)
    converter.validate_signal_for_live = AsyncMock()
    converter.run_pre_trade_risk = AsyncMock(return_value=RiskCheckResult(
        result_type=RiskResultType.ALLOW,
        reject_reason="",
        triggered_rules=[],
        risk_check_id="rc-001",
        check_time=datetime.now(),
    ))
    converter.create_execution_intent = AsyncMock(return_value=MagicMock(
        execution_intent_id="ei-001",
        signal_id="sig-001",
        strategy_instance_id="strat-001",
        account_id="acc-001",
        instrument_id="000001.SZ",
        side=Side.BUY,
        target_quantity=500,
        reference_price=Decimal("10.50"),
        reservation_id=None,
        risk_check_id="rc-001",
        created_at=datetime.now(),
    ))
    converter.convert_to_order_request = AsyncMock(return_value=MagicMock(
        spec=OrderRequest,
        order_request_id="orq-001",
        signal_id="sig-001",
        side=Side.BUY,
        price=Decimal("10.50"),
        quantity=500,
    ))
    return converter


@pytest.fixture
def mock_final_check():
    check = AsyncMock(spec=FinalPreSubmitCheck)
    check.execute = AsyncMock(return_value=MagicMock(
        result=FinalCheckResult.ALLOW,
        reason="",
    ))
    return check


@pytest.fixture
def mock_reservation():
    return AsyncMock(spec=ReservationManager)


@pytest.fixture
def service(mock_converter, mock_final_check, mock_reservation):
    return ExecutionService(
        risk_engine=MagicMock(),
        final_check=mock_final_check,
        reservation_manager=mock_reservation,
        converter=mock_converter,
        reject_handler=MagicMock(),
    )


class TestProcessSignal:
    async def test_happy_path_returns_order_request(self, service, mock_converter):
        signal = _make_signal()
        result = await service.process_signal(
            signal=signal,
            account_id="acc-001",
            reference_price=Decimal("10.50"),
            target_quantity=500,
            risk_context=_make_risk_context(),
            final_check_context=_make_final_check_context(),
        )
        assert result is not None
        mock_converter.convert_to_order_request.assert_called_once()

    async def test_risk_rejection_raises(self, service, mock_converter):
        mock_converter.run_pre_trade_risk.return_value = RiskCheckResult(
            result_type=RiskResultType.REJECT,
            reject_reason="Index drop exceeds threshold",
            triggered_rules=["index_drop_halt"],
            risk_check_id="rc-002",
            check_time=datetime.now(),
        )
        signal = _make_signal()
        with pytest.raises(RiskRejectError):
            await service.process_signal(
                signal=signal,
                account_id="acc-001",
                reference_price=Decimal("10.50"),
                target_quantity=500,
                risk_context=_make_risk_context(),
                final_check_context=_make_final_check_context(),
            )

    async def test_final_check_failure_returns_none(
        self, service, mock_final_check
    ):
        mock_final_check.execute.return_value = MagicMock(
            result=FinalCheckResult.REJECT,
            reason="Kill switch active",
        )
        signal = _make_signal()
        result = await service.process_signal(
            signal=signal,
            account_id="acc-001",
            reference_price=Decimal("10.50"),
            target_quantity=500,
            risk_context=_make_risk_context(),
            final_check_context=_make_final_check_context(),
        )
        assert result is None

    async def test_resize_adjusts_quantity(self, service, mock_converter):
        mock_converter.run_pre_trade_risk.return_value = RiskCheckResult(
            result_type=RiskResultType.RESIZE,
            reject_reason="",
            triggered_rules=[],
            risk_check_id="rc-003",
            resized_quantity=300,
            check_time=datetime.now(),
        )
        signal = _make_signal()
        await service.process_signal(
            signal=signal,
            account_id="acc-001",
            reference_price=Decimal("10.50"),
            target_quantity=500,
            risk_context=_make_risk_context(),
            final_check_context=_make_final_check_context(),
        )
        # Verify create_execution_intent was called with resized quantity
        call_args = mock_converter.create_execution_intent.call_args
        assert call_args.kwargs.get("quantity") == 300 or call_args[1].get("quantity") == 300

    async def test_force_flatten_raises(self, service, mock_converter):
        mock_converter.run_pre_trade_risk.return_value = RiskCheckResult(
            result_type=RiskResultType.FORCE_FLATTEN,
            reject_reason="Daily loss exceeds limit",
            triggered_rules=["daily_loss_limit"],
            risk_check_id="rc-004",
            check_time=datetime.now(),
        )
        signal = _make_signal()
        with pytest.raises(ForceFlattenError):
            await service.process_signal(
                signal=signal,
                account_id="acc-001",
                reference_price=Decimal("10.50"),
                target_quantity=500,
                risk_context=_make_risk_context(),
                final_check_context=_make_final_check_context(),
            )

    async def test_delay_returns_none(self, service, mock_converter):
        mock_converter.run_pre_trade_risk.return_value = RiskCheckResult(
            result_type=RiskResultType.DELAY,
            reject_reason="Cooldown period active",
            triggered_rules=["cooldown_period"],
            risk_check_id="rc-005",
            check_time=datetime.now(),
        )
        signal = _make_signal()
        result = await service.process_signal(
            signal=signal,
            account_id="acc-001",
            reference_price=Decimal("10.50"),
            target_quantity=500,
            risk_context=_make_risk_context(),
            final_check_context=_make_final_check_context(),
        )
        assert result is None
        mock_converter.create_execution_intent.assert_not_called()

    async def test_open_short_reserves_cash(self, service, mock_converter, mock_reservation):
        signal = _make_signal(signal_type=SignalType.OPEN_SHORT)
        mock_reservation.reserve = AsyncMock(return_value=MagicMock(
            reservation_id="res-001",
        ))
        await service.process_signal(
            signal=signal,
            account_id="acc-001",
            reference_price=Decimal("10.50"),
            target_quantity=500,
            risk_context=_make_risk_context(),
            final_check_context=_make_final_check_context(),
        )
        mock_reservation.reserve.assert_called_once()

    async def test_close_long_no_reservation(self, service, mock_converter, mock_reservation):
        signal = _make_signal(signal_type=SignalType.CLOSE_LONG)
        await service.process_signal(
            signal=signal,
            account_id="acc-001",
            reference_price=Decimal("10.50"),
            target_quantity=500,
            risk_context=_make_risk_context(),
            final_check_context=_make_final_check_context(),
        )
        mock_reservation.reserve.assert_not_called()

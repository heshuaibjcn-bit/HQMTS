"""Final Pre-Submit Check (SAD Section 19).

12-point synchronous check before real QMT order submission.
This is the LAST check before actual execution — cannot be bypassed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from hqmts.core.enums import (
    FinalCheckResult,
    OrderStatus,
    ReservationStatus,
    StrategyStatus,
)
from hqmts.core.exceptions import KillSwitchActiveError
from hqmts.core.types import now_shanghai


@dataclass
class FinalCheckContext:
    """All data needed for the Final Pre-Submit Check."""

    # 1. Strategy state - must be explicitly set
    strategy_status: StrategyStatus | None = None

    # 2. Signal/Intent expiration
    signal_valid_until: datetime | None = None
    intent_created_at: datetime | None = None

    # 3. QMT Adapter - must be explicitly confirmed
    qmt_adapter_available: bool | None = None

    # 4. Account state
    account_risk_status: str | None = None
    account_available_cash: Decimal = Decimal("0")

    # 5. Position
    available_quantity: int = 0
    required_quantity: int = 0
    today_bought_quantity: int = 0  # T+1: shares bought today cannot be sold today
    side: str = "buy"

    # 6. Cash reservation
    reservation_status: ReservationStatus | None = None
    reservation_expires_at: datetime | None = None

    # 7. Conflicting orders
    has_conflicting_inflight: bool | None = None

    # 8. Kill switch / close_only
    kill_switch_active: bool | None = None
    close_only_mode: bool = False
    pause_open_mode: bool = False

    # 9. Order frequency
    orders_last_minute: int = 0
    max_orders_per_minute: int = 10

    # 10. Order params
    price: Decimal = Decimal("0")
    quantity: int = 0
    instrument_id: str = ""

    # 11. Source legitimacy
    source_is_deterministic: bool = True

    # 12. Request source verification
    request_from_execution_service: bool = True

    # Additional
    is_flatten: bool = False
    check_time: datetime = field(default_factory=now_shanghai)
    stale_price_threshold_seconds: int = 30
    reference_price_age_seconds: float = 0.0


@dataclass
class FinalCheckResultDetail:
    """Detailed result of the Final Pre-Submit Check."""

    result: FinalCheckResult
    check_id: str
    passed_checks: list[str] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)
    reason: str = ""


class FinalPreSubmitCheck:
    """12-point Final Pre-Submit Check.

    Must be synchronous. Cannot be bypassed by agent, strategy, or config.
    Returns: allow, reject, retry_later, escalate_manual
    """

    async def execute(self, ctx: FinalCheckContext) -> FinalCheckResultDetail:
        """Run all 12 checks synchronously."""
        import uuid

        check_id = str(uuid.uuid4())
        passed: list[str] = []
        failed: list[str] = []

        # 1. StrategyInstance status
        if ctx.strategy_status is None:
            failed.append("strategy_status_not_provided")
        elif ctx.strategy_status == StrategyStatus.LIVE_RUNNING or (
            ctx.strategy_status == StrategyStatus.CLOSE_ONLY and ctx.is_flatten
        ):
            passed.append("strategy_status")
        elif ctx.strategy_status == StrategyStatus.CLOSE_ONLY and not ctx.is_flatten:
            if ctx.side == "sell":
                passed.append("strategy_status_close_only_sell")
            else:
                failed.append("strategy_status_close_only")
        elif ctx.strategy_status == StrategyStatus.PAUSE_OPEN:
            if ctx.is_flatten or ctx.side == "sell":
                passed.append("strategy_status_pause_open_close")
            else:
                failed.append("strategy_status_pause_open")
        else:
            failed.append(f"strategy_status_{ctx.strategy_status.value}")

        # 2. Signal/Intent expiration
        if ctx.signal_valid_until and ctx.signal_valid_until < ctx.check_time:
            failed.append("signal_expired")
        else:
            passed.append("signal_valid")

        # 3. QMT Adapter availability
        if ctx.qmt_adapter_available is None:
            failed.append("qmt_status_not_provided")
        elif ctx.qmt_adapter_available:
            passed.append("qmt_available")
        else:
            failed.append("qmt_unavailable")

        # 4. Account status
        if ctx.account_risk_status is None:
            failed.append("account_status_not_provided")
        elif ctx.account_risk_status == "normal":
            passed.append("account_normal")
        elif ctx.account_risk_status == "warning":
            passed.append("account_warning")
        else:
            failed.append(f"account_{ctx.account_risk_status}")

        # 5. Position sufficiency (sell side) with T+1 enforcement
        if ctx.side == "sell":
            # T+1: subtract shares bought today from available quantity
            sellable_quantity = ctx.available_quantity - ctx.today_bought_quantity
            if sellable_quantity < 0:
                failed.append("position_insufficient_t1_all_blocked")
            elif sellable_quantity == 0 and ctx.today_bought_quantity > 0:
                failed.append("position_insufficient_t1_all_blocked")
            elif sellable_quantity >= ctx.quantity:
                passed.append("position_sufficient")
            else:
                failed.append("position_insufficient")
        else:
            passed.append("position_check_n_a_buy")

        # 6. CashReservation active & not expired
        if ctx.reservation_status == ReservationStatus.ACTIVE:
            if ctx.reservation_expires_at and ctx.reservation_expires_at < ctx.check_time:
                failed.append("reservation_expired")
            else:
                passed.append("reservation_active")
        elif ctx.reservation_status is None:
            passed.append("reservation_n_a")
        else:
            failed.append(f"reservation_{ctx.reservation_status.value}")

        # 7. No conflicting in-flight orders
        if ctx.has_conflicting_inflight is None:
            failed.append("inflight_status_not_provided")
        elif not ctx.has_conflicting_inflight:
            passed.append("no_conflict")
        else:
            failed.append("conflicting_inflight")

        # 8. Kill switch / close_only
        if ctx.kill_switch_active is None:
            failed.append("kill_switch_status_not_provided")
        elif ctx.kill_switch_active:
            if ctx.is_flatten:
                passed.append("kill_switch_flatten_allowed")
            else:
                failed.append("kill_switch_active")
        elif ctx.close_only_mode and not ctx.is_flatten and ctx.side == "buy":
            failed.append("close_only_no_buy")
        else:
            passed.append("mode_ok")

        # 9. Order frequency limit
        if ctx.orders_last_minute < ctx.max_orders_per_minute:
            passed.append("frequency_ok")
        else:
            failed.append("frequency_exceeded")

        # 10. Order parameter legality
        if ctx.price > 0 and ctx.quantity > 0 and ctx.instrument_id:
            passed.append("params_valid")
        else:
            failed.append("params_invalid")

        # 10b. Price staleness check
        if ctx.stale_price_threshold_seconds > 0:
            if ctx.reference_price_age_seconds > ctx.stale_price_threshold_seconds:
                failed.append("stale_price")
            else:
                passed.append("price_fresh")

        # 11. Source legitimacy (not from agent)
        if ctx.source_is_deterministic:
            passed.append("source_deterministic")
        else:
            failed.append("source_non_deterministic")

        # 12. Request from deterministic execution service
        if ctx.request_from_execution_service:
            passed.append("execution_service_source")
        else:
            failed.append("unauthorized_source")

        # Determine result
        if ctx.kill_switch_active and not ctx.is_flatten:
            result = FinalCheckResult.REJECT
            reason = "Kill switch active"
        elif failed:
            critical_failures = {
                "unauthorized_source",
                "source_non_deterministic",
                "kill_switch_active",
                "params_invalid",
            }
            if critical_failures.intersection(failed):
                result = FinalCheckResult.REJECT
                reason = f"Critical check failed: {', '.join(failed)}"
            elif "qmt_unavailable" in failed:
                result = FinalCheckResult.RETRY_LATER
                reason = "QMT adapter unavailable"
            elif {"signal_expired", "reservation_expired"}.intersection(failed):
                result = FinalCheckResult.REJECT
                reason = f"Expired: {', '.join(failed)}"
            else:
                result = FinalCheckResult.ESCALATE_MANUAL
                reason = f"Checks failed: {', '.join(failed)}"
        else:
            result = FinalCheckResult.ALLOW
            reason = "All checks passed"

        return FinalCheckResultDetail(
            result=result,
            check_id=check_id,
            passed_checks=passed,
            failed_checks=failed,
            reason=reason,
        )

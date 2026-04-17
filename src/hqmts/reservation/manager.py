"""Cash Reservation Manager (SAD Section 16).

Handles fund reservation lifecycle for multi-strategy shared accounts.
All operations for the same account are serialized via account_id.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from hqmts.core.enums import ReservationStatus
from hqmts.core.exceptions import InsufficientFundsError, ReservationExpiredError
from hqmts.core.types import AccountId, ReservationId, StrategyInstanceId
from hqmts.db.models.reservation import CashReservationORM
from hqmts.db.repositories.reservation_repo import ReservationRepository
from hqmts.domain.reservation import CashReservation


class ReservationManager:
    """Manages cash reservation lifecycle.

    Conservative available cash calculation:
        effective_available = QMT_available_cash - sum(active_reservations)
    """

    def __init__(
        self,
        reservation_repo: ReservationRepository,
        ttl_seconds: int = 120,
    ) -> None:
        self._repo = reservation_repo
        self._ttl_seconds = ttl_seconds

    async def get_effective_available_cash(
        self,
        account_id: AccountId,
        available_cash: Decimal | None = None,
    ) -> Decimal:
        """Calculate effective available cash after subtracting active reservations.

        Args:
            account_id: The account to check.
            available_cash: Current available cash from account/QMT.
                Must be provided — this method does not query account state.

        Raises:
            ValueError: If available_cash is not provided.
        """
        if available_cash is None:
            raise ValueError(
                "available_cash must be provided. "
                "Integration with AccountService required to fetch automatically."
            )
        total_reserved = await self._repo.get_total_reserved_amount(account_id)
        return available_cash - total_reserved

    async def reserve(
        self,
        account_id: AccountId,
        strategy_instance_id: StrategyInstanceId,
        amount: Decimal,
        signal_id: str | None = None,
        execution_intent_id: str | None = None,
        available_cash: Decimal | None = None,
    ) -> CashReservation:
        """Create a new cash reservation.

        Args:
            account_id: The shared account.
            strategy_instance_id: The strategy requesting reservation.
            amount: Amount to reserve.
            signal_id: Optional signal reference.
            execution_intent_id: Optional execution intent reference.
            available_cash: Current available cash (should include reservation deductions).

        Raises:
            InsufficientFundsError: If not enough available cash.
        """
        if available_cash is None:
            raise ValueError(
                "available_cash must be provided for sufficiency check. "
                "Use get_effective_available_cash() to calculate it first."
            )
        total_reserved = await self._repo.get_total_reserved_amount(account_id)
        effective = available_cash - total_reserved
        if amount > effective:
            raise InsufficientFundsError(
                f"Requested {amount}, effective available {effective}"
            )

        now = datetime.now()
        reservation = CashReservation(
            reservation_id=ReservationId(str(uuid.uuid4())),
            account_id=account_id,
            strategy_instance_id=strategy_instance_id,
            signal_id=signal_id,
            execution_intent_id=execution_intent_id,
            reserved_amount=amount,
            consumed_amount=Decimal("0"),
            status=ReservationStatus.ACTIVE,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
            created_at=now,
            updated_at=now,
        )

        # Persist via repo
        orm = CashReservationORM(
            reservation_id=reservation.reservation_id,
            account_id=str(reservation.account_id),
            strategy_instance_id=str(reservation.strategy_instance_id),
            signal_id=reservation.signal_id,
            execution_intent_id=reservation.execution_intent_id,
            reserved_amount=reservation.reserved_amount,
            consumed_amount=reservation.consumed_amount,
            status=reservation.status.value,
            expires_at=reservation.expires_at,
        )
        await self._repo.create(orm)

        return reservation

    async def consume(
        self,
        reservation_id: ReservationId,
        amount: Decimal,
    ) -> CashReservation:
        """Consume part or all of a reservation (on fill).

        Updates status: active → partially_consumed → fully_consumed.
        """
        reservation = await self._repo.get_by_id(reservation_id)
        if reservation is None:
            raise ReservationExpiredError(f"Reservation {reservation_id} not found")

        if reservation.status != ReservationStatus.ACTIVE.value:
            raise ReservationExpiredError(
                f"Reservation {reservation_id} is not active (status: {reservation.status})"
            )

        now = datetime.now()
        new_consumed = reservation.consumed_amount + amount
        reservation.consumed_amount = new_consumed
        reservation.status = (
            ReservationStatus.FULLY_CONSUMED.value
            if new_consumed >= reservation.reserved_amount
            else ReservationStatus.PARTIALLY_CONSUMED.value
        )
        reservation.updated_at = now
        await self._repo.update(reservation)
        return CashReservation(
            reservation_id=ReservationId(reservation.reservation_id),
            account_id=AccountId(reservation.account_id),
            strategy_instance_id=StrategyInstanceId(reservation.strategy_instance_id),
            signal_id=reservation.signal_id,
            execution_intent_id=reservation.execution_intent_id,
            reserved_amount=reservation.reserved_amount,
            consumed_amount=new_consumed,
            status=ReservationStatus(reservation.status),
            expires_at=reservation.expires_at,
            created_at=reservation.created_at,
            updated_at=now,
        )

    async def release(
        self,
        reservation_id: ReservationId,
        reason: str = "",
    ) -> CashReservation:
        """Release a reservation (on order failure or cancellation)."""
        reservation = await self._repo.get_by_id(reservation_id)
        if reservation is None:
            raise ReservationExpiredError(f"Reservation {reservation_id} not found")

        now = datetime.now()
        reservation.status = ReservationStatus.RELEASED.value
        reservation.released_reason = reason
        reservation.updated_at = now
        await self._repo.update(reservation)
        return CashReservation(
            reservation_id=ReservationId(reservation.reservation_id),
            account_id=AccountId(reservation.account_id),
            strategy_instance_id=StrategyInstanceId(reservation.strategy_instance_id),
            signal_id=reservation.signal_id,
            execution_intent_id=reservation.execution_intent_id,
            reserved_amount=reservation.reserved_amount,
            consumed_amount=reservation.consumed_amount,
            status=ReservationStatus.RELEASED,
            expires_at=reservation.expires_at,
            released_reason=reason,
            created_at=reservation.created_at,
            updated_at=now,
        )

    async def expire_reservations(self) -> list[CashReservation]:
        """Release all expired reservations. Called periodically."""
        expired = await self._repo.get_expired_reservations(datetime.now())
        results = []
        for res in expired:
            now = datetime.now()
            res.status = ReservationStatus.EXPIRED.value
            res.updated_at = now
            await self._repo.update(res)
            results.append(CashReservation(
                reservation_id=ReservationId(res.reservation_id),
                account_id=AccountId(res.account_id),
                strategy_instance_id=StrategyInstanceId(res.strategy_instance_id),
                signal_id=res.signal_id,
                execution_intent_id=res.execution_intent_id,
                reserved_amount=res.reserved_amount,
                consumed_amount=res.consumed_amount,
                status=ReservationStatus.EXPIRED,
                expires_at=res.expires_at,
                created_at=res.created_at,
                updated_at=now,
            ))
        return results

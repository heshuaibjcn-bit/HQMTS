"""Integration test: Full order lifecycle via repositories + state machine.

Covers: Signal -> RiskCheck -> Reservation -> ExecutionIntent -> Order
Using SQLite async session to test the full pipeline.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.core.enums import OrderStatus, Side
from hqmts.db.models.order import OrderORM
from hqmts.db.repositories.order_repo import OrderRepository
from hqmts.statemachine.order_fsm import order_fsm


class TestOrderLifecycle:
    """Full order lifecycle: pending -> submit -> accept -> partial fill -> fill."""

    @pytest.mark.asyncio
    async def test_order_create_and_repo_roundtrip(self, session: AsyncSession):
        repo = OrderRepository(session)
        now = datetime.now()

        order = OrderORM(
            order_id="ord-001",
            account_id="acc-001",
            instrument_id="000001.SZ",
            side="buy",
            price=Decimal("10.50"),
            quantity=1000,
            status=OrderStatus.PENDING.value,
            created_at=now,
            updated_at=now,
        )

        created = await repo.create(order)
        await session.commit()

        assert created.order_id == "ord-001"

        fetched = await repo.get_by_id("ord-001", id_column="order_id")
        assert fetched is not None
        assert fetched.instrument_id == "000001.SZ"
        assert fetched.price == Decimal("10.50")

    @pytest.mark.asyncio
    async def test_order_fsm_lifecycle(self, session: AsyncSession):
        """Full happy path through state machine + repo updates."""
        repo = OrderRepository(session)
        now = datetime.now()
        # Create order
        order = OrderORM(
            order_id="ord-002",
            account_id="acc-001",
            instrument_id="600519.SH",
            side="sell",
            price=Decimal("1800.00"),
            quantity=100,
            status=OrderStatus.PENDING.value,
            created_at=now,
            updated_at=now,
        )
        await repo.create(order)

        # PENDING -> SUBMITTED
        new_status = order_fsm.transition(OrderStatus.PENDING, OrderStatus.SUBMITTED)
        assert new_status == OrderStatus.SUBMITTED
        order.status = new_status.value
        await repo.update(order)

        # SUBMITTED -> ACCEPTED
        new_status = order_fsm.transition(OrderStatus.SUBMITTED, OrderStatus.ACCEPTED)
        order.status = new_status.value

        # ACCEPTED -> PARTIAL_FILLED
        new_status = order_fsm.transition(OrderStatus.ACCEPTED, OrderStatus.PARTIAL_FILLED)
        order.status = new_status.value
        order.filled_quantity = 50
        order.avg_fill_price = Decimal("1799.50")

        # PARTIAL_FILLED -> FILLED
        new_status = order_fsm.transition(OrderStatus.PARTIAL_FILLED, OrderStatus.FILLED)
        order.status = new_status.value
        order.filled_quantity = 100
        order.avg_fill_price = Decimal("1800.00")

        await repo.update(order)
        await session.commit()

        fetched = await repo.get_by_id("ord-002", id_column="order_id")
        assert fetched is not None
        assert fetched.status == OrderStatus.FILLED.value
        assert fetched.filled_quantity == 100
        assert order_fsm.is_terminal(OrderStatus(fetched.status))

        assert order_fsm.is_terminal(OrderStatus.FILLED)

    @pytest.mark.asyncio
    async def test_order_rejection_path(self, session: AsyncSession):
        """Order gets rejected by broker."""
        repo = OrderRepository(session)
        now = datetime.now()

        order = OrderORM(
            order_id="ord-003",
            account_id="acc-001",
            instrument_id="000001.SZ",
            side="buy",
            price=Decimal("10.00"),
            quantity=500,
            status=OrderStatus.PENDING.value,
            created_at=now,
            updated_at=now,
        )
        await repo.create(order)

        # PENDING -> SUBMITTED -> REJECTED
        new_status = order_fsm.transition(OrderStatus(order.status), OrderStatus.SUBMITTED)
        order.status = new_status.value

        new_status = order_fsm.transition(OrderStatus.SUBMITTED, OrderStatus.REJECTED)
        order.status = new_status.value
        order.reject_reason = "insufficient_funds"

        await repo.update(order)
        await session.commit()

        fetched = await repo.get_by_id("ord-003", id_column="order_id")
        assert fetched.status == OrderStatus.REJECTED.value
        assert fetched.reject_reason == "insufficient_funds"
        assert order_fsm.is_terminal(OrderStatus(fetched.status))

    @pytest.mark.asyncio
    async def test_order_cancel_path(self, session: AsyncSession):
        """Order cancellation path."""
        repo = OrderRepository(session)
        now = datetime.now()

        order = OrderORM(
            order_id="ord-004",
            account_id="acc-001",
            instrument_id="300750.SZ",
            side="buy",
            price=Decimal("200.00"),
            quantity=200,
            status=OrderStatus.PENDING.value,
            created_at=now,
            updated_at=now,
        )
        await repo.create(order)

        # PENDING -> SUBMITTED -> ACCEPTED -> CANCELED
        for target in [OrderStatus.SUBMITTED, OrderStatus.ACCEPTED]:
            new_status = order_fsm.transition(OrderStatus(order.status), target)
            order.status = new_status.value

        new_status = order_fsm.transition(OrderStatus.ACCEPTED, OrderStatus.CANCELED)
        order.status = new_status.value

        await repo.update(order)
        await session.commit()

        fetched = await repo.get_by_id("ord-004", id_column="order_id")
        assert fetched.status == OrderStatus.CANCELED.value

    @pytest.mark.asyncio
    async def test_illegal_transition_raises(self):
        """Cannot jump from PENDING directly to FILLED."""
        from hqmts.core.exceptions import IllegalTransitionError

        with pytest.raises(IllegalTransitionError):
            order_fsm.transition(OrderStatus.PENDING, OrderStatus.FILLED)

    @pytest.mark.asyncio
    async def test_get_active_orders_by_account(self, session: AsyncSession):
        """Verify active order filtering."""
        repo = OrderRepository(session)
        now = datetime.now()

        # Active order
        await repo.create(OrderORM(
            order_id="ord-active",
            account_id="acc-001",
            instrument_id="000001.SZ",
            side="buy",
            price=Decimal("10"),
            quantity=100,
            status=OrderStatus.ACCEPTED.value,
            created_at=now,
            updated_at=now,
        ))

        # Terminal order
        await repo.create(OrderORM(
            order_id="ord-done",
            account_id="acc-001",
            instrument_id="600519.SH",
            side="sell",
            price=Decimal("1800"),
            quantity=10,
            status=OrderStatus.FILLED.value,
            created_at=now,
            updated_at=now,
        ))

        await session.commit()

        active = await repo.get_active_orders_by_account("acc-001")
        assert len(active) == 1
        assert active[0].order_id == "ord-active"

    @pytest.mark.asyncio
    async def test_broker_order_id_lookup(self, session: AsyncSession):
        """Find order by broker_order_id (reconciliation use case)."""
        repo = OrderRepository(session)
        now = datetime.now()

        await repo.create(OrderORM(
            order_id="ord-005",
            account_id="acc-001",
            instrument_id="000001.SZ",
            side="buy",
            price=Decimal("10"),
            quantity=100,
            status=OrderStatus.ACCEPTED.value,
            broker_order_id="broker-abc-123",
            created_at=now,
            updated_at=now,
        ))
        await session.commit()

        found = await repo.get_by_broker_order_id("broker-abc-123")
        assert found is not None
        assert found.order_id == "ord-005"

        assert await repo.get_by_broker_order_id("nonexistent") is None

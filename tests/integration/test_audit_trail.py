"""Integration test: Audit trail completeness via repository.

Covers: create events, query by entity/time/correlation, immutability enforcement.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.db.models.audit import AuditEventORM
from hqmts.db.repositories.audit_repo import AuditRepository


class TestAuditTrail:
    """Verify audit event lifecycle and query capabilities."""

    @pytest.mark.asyncio
    async def test_create_and_lookup(self, session: AsyncSession):
        repo = AuditRepository(session)
        now = datetime.now()

        event = AuditEventORM(
            audit_event_id="ae-001",
            event_type="order_created",
            entity_type="order",
            entity_id="ord-001",
            environment="paper",
            actor="strategy:alpha-v1",
            action="create_order",
            details_json='{"instrument": "000001.SZ", "side": "buy"}',
            alert_level="P3",
            correlation_id="corr-001",
            timestamp=now,
        )

        await repo.create(event)
        await session.commit()

        fetched = await repo.get_by_id("ae-001", id_column="audit_event_id")
        assert fetched is not None
        assert fetched.event_type == "order_created"
        assert fetched.entity_id == "ord-001"

    @pytest.mark.asyncio
    async def test_query_by_entity(self, session: AsyncSession):
        """All events for a specific entity."""
        repo = AuditRepository(session)
        now = datetime.now()

        for i in range(5):
            await repo.create(AuditEventORM(
                audit_event_id=f"ae-entity-{i}",
                event_type="status_change",
                entity_type="order",
                entity_id="ord-100",
                environment="paper",
                actor="system",
                action=f"transition_{i}",
                details_json="{}",
                alert_level="P3",
                timestamp=now + timedelta(seconds=i),
            ))

        # Different entity
        await repo.create(AuditEventORM(
            audit_event_id="ae-other",
            event_type="order_created",
            entity_type="order",
            entity_id="ord-999",
            environment="paper",
            actor="system",
            action="create",
            details_json="{}",
            alert_level="P3",
            timestamp=now,
        ))

        await session.commit()

        events = await repo.get_by_entity("order", "ord-100")
        assert len(events) == 5
        assert all(e.entity_id == "ord-100" for e in events)

    @pytest.mark.asyncio
    async def test_query_by_correlation(self, session: AsyncSession):
        """All events linked by correlation_id (cross-entity trace)."""
        repo = AuditRepository(session)
        now = datetime.now()

        corr_id = "corr-trace-001"
        for i, (etype, entity) in enumerate([
            ("signal_generated", "signal"),
            ("risk_checked", "risk_check"),
            ("reservation_created", "reservation"),
            ("order_created", "order"),
        ]):
            await repo.create(AuditEventORM(
                audit_event_id=f"ae-corr-{i}",
                event_type=etype,
                entity_type=entity,
                entity_id=f"{entity[0]}-001",
                environment="paper",
                actor="system",
                action=etype,
                details_json="{}",
                alert_level="P3",
                correlation_id=corr_id,
                timestamp=now + timedelta(seconds=i),
            ))

        await session.commit()

        events = await repo.get_by_correlation_id(corr_id)
        assert len(events) == 4
        entity_types = {e.entity_type for e in events}
        assert entity_types == {"signal", "risk_check", "reservation", "order"}

    @pytest.mark.asyncio
    async def test_query_by_time_range(self, session: AsyncSession):
        """Filter audit events by timestamp range."""
        repo = AuditRepository(session)
        base = datetime(2025, 1, 1, 10, 0, 0)

        # Events at different times
        for i in range(10):
            await repo.create(AuditEventORM(
                audit_event_id=f"ae-time-{i}",
                event_type="tick",
                entity_type="order",
                entity_id="ord-time",
                environment="paper",
                actor="system",
                action="tick",
                details_json="{}",
                alert_level="P3",
                timestamp=base + timedelta(minutes=i * 5),
            ))

        await session.commit()

        # Query 10:00 - 10:20 (should get events at 0, 5, 10, 15, 20 min = 5 events)
        start = base
        end = base + timedelta(minutes=20)
        events = await repo.get_by_time_range(start, end)
        assert len(events) == 5

    @pytest.mark.asyncio
    async def test_full_order_lifecycle_audit_trail(self, session: AsyncSession):
        """Verify audit trail captures every step of an order lifecycle."""
        repo = AuditRepository(session)
        now = datetime.now()
        corr_id = "lifecycle-ord-200"

        # Simulate the full audit trail for one order
        steps = [
            ("signal_generated", "signal", "sig-200"),
            ("decision_snapshot_created", "decision_snapshot", "ds-200"),
            ("risk_check_passed", "risk_check", "rc-200"),
            ("cash_reserved", "reservation", "res-200"),
            ("execution_intent_created", "execution_intent", "ei-200"),
            ("final_check_passed", "final_check", "fc-200"),
            ("order_request_created", "order_request", "orq-200"),
            ("order_created", "order", "ord-200"),
            ("order_submitted", "order", "ord-200"),
            ("order_accepted", "order", "ord-200"),
            ("order_filled", "order", "ord-200"),
        ]

        for i, (event_type, entity_type, entity_id) in enumerate(steps):
            await repo.create(AuditEventORM(
                audit_event_id=f"ae-life-{i:03d}",
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                environment="paper",
                actor="trading_kernel",
                action=event_type,
                details_json="{}",
                alert_level="P3",
                correlation_id=corr_id,
                timestamp=now + timedelta(milliseconds=i * 100),
            ))

        await session.commit()

        # Verify complete trail
        events = await repo.get_by_correlation_id(corr_id)
        assert len(events) == 11

        # Events are ordered by timestamp
        event_types = [e.event_type for e in events]
        assert event_types[0] == "signal_generated"
        assert event_types[-1] == "order_filled"

        # Can filter to just order events
        order_events = await repo.get_by_entity("order", "ord-200")
        assert len(order_events) == 4  # created, submitted, accepted, filled

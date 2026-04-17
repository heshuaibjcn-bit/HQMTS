"""Tests for CorrectionEvent and CorrectionHandler (SAD 10.4)."""

from __future__ import annotations

import pytest
from decimal import Decimal

from hqmts.core.enums import CorrectionType
from hqmts.domain.correction import CorrectionEvent
from hqmts.reconciliation.correction_handler import CorrectionHandler


@pytest.fixture
def handler():
    return CorrectionHandler()


class TestCorrectionEvent:
    def test_create_price_correction(self):
        event = CorrectionEvent(
            correction_id="corr_001",
            broker_trade_id="trade_001",
            instrument_id="000001.SZ",
            correction_type=CorrectionType.PRICE_CORRECTION,
            original_price=Decimal("10.50"),
            corrected_price=Decimal("10.48"),
        )
        assert event.correction_type == CorrectionType.PRICE_CORRECTION
        assert event.original_price == Decimal("10.50")
        assert event.corrected_price == Decimal("10.48")
        assert event.is_processed is False

    def test_create_quantity_correction(self):
        event = CorrectionEvent(
            correction_id="corr_002",
            broker_trade_id="trade_002",
            instrument_id="600000.SH",
            correction_type=CorrectionType.QUANTITY_CORRECTION,
            original_quantity=1000,
            corrected_quantity=900,
        )
        assert event.correction_type == CorrectionType.QUANTITY_CORRECTION
        assert event.corrected_quantity == 900


class TestCorrectionHandler:
    @pytest.mark.asyncio
    async def test_record_price_correction(self, handler):
        event = await handler.record_correction(
            broker_trade_id="trade_001",
            instrument_id="000001.SZ",
            correction_type=CorrectionType.PRICE_CORRECTION,
            original_price=Decimal("10.50"),
            corrected_price=Decimal("10.48"),
            reason="Exchange price adjustment",
        )
        assert event.correction_id
        assert event.correction_type == CorrectionType.PRICE_CORRECTION
        assert event.reason == "Exchange price adjustment"

    @pytest.mark.asyncio
    async def test_record_quantity_correction(self, handler):
        event = await handler.record_correction(
            broker_trade_id="trade_002",
            instrument_id="600000.SH",
            correction_type=CorrectionType.QUANTITY_CORRECTION,
            original_quantity=1000,
            corrected_quantity=900,
        )
        assert event.original_quantity == 1000
        assert event.corrected_quantity == 900

    @pytest.mark.asyncio
    async def test_process_correction(self, handler):
        event = await handler.record_correction(
            broker_trade_id="trade_001",
            instrument_id="000001.SZ",
            correction_type=CorrectionType.PRICE_CORRECTION,
            original_price=Decimal("10.50"),
            corrected_price=Decimal("10.48"),
        )
        processed = await handler.process_correction(event.correction_id)
        assert processed.is_processed is True
        assert processed.processed_at is not None

    @pytest.mark.asyncio
    async def test_correction_with_reconciliation(self):
        class FakeReconService:
            pass

        svc = CorrectionHandler(reconciliation_service=FakeReconService())
        event = await svc.record_correction(
            broker_trade_id="trade_001",
            instrument_id="000001.SZ",
            correction_type=CorrectionType.PRICE_CORRECTION,
            original_price=Decimal("10.50"),
        )
        processed = await svc.process_correction(event.correction_id)
        assert processed.reconciliation_session_id  # Linked to recon session

    @pytest.mark.asyncio
    async def test_get_unprocessed_corrections(self, handler):
        await handler.record_correction(
            broker_trade_id="trade_001",
            instrument_id="000001.SZ",
            correction_type=CorrectionType.PRICE_CORRECTION,
            original_price=Decimal("10.50"),
        )
        await handler.record_correction(
            broker_trade_id="trade_002",
            instrument_id="600000.SH",
            correction_type=CorrectionType.QUANTITY_CORRECTION,
            original_quantity=500,
        )

        unprocessed = await handler.get_unprocessed_corrections()
        assert len(unprocessed) == 2

        # Process one
        await handler.process_correction(unprocessed[0].correction_id)
        remaining = await handler.get_unprocessed_corrections()
        assert len(remaining) == 1

    @pytest.mark.asyncio
    async def test_idempotent_processing(self, handler):
        event = await handler.record_correction(
            broker_trade_id="trade_001",
            instrument_id="000001.SZ",
            correction_type=CorrectionType.PRICE_CORRECTION,
            original_price=Decimal("10.50"),
        )
        first = await handler.process_correction(event.correction_id)
        second = await handler.process_correction(event.correction_id)
        assert first.correction_id == second.correction_id
        assert first.processed_at == second.processed_at

    @pytest.mark.asyncio
    async def test_process_unknown_correction(self, handler):
        with pytest.raises(ValueError, match="not found"):
            await handler.process_correction("nonexistent")

    @pytest.mark.asyncio
    async def test_get_correction(self, handler):
        event = await handler.record_correction(
            broker_trade_id="trade_001",
            instrument_id="000001.SZ",
            correction_type=CorrectionType.TRADE_CANCELLATION,
            original_quantity=100,
            reason="Trade cancelled by exchange",
        )
        found = handler.get_correction(event.correction_id)
        assert found is not None
        assert handler.get_correction("nonexistent") is None

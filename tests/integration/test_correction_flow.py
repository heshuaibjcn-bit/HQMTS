"""Integration test: Correction event triggers reconciliation flow."""

from __future__ import annotations

import pytest
from decimal import Decimal

from hqmts.core.enums import CorrectionType
from hqmts.reconciliation.correction_handler import CorrectionHandler


class FakeReconService:
    """Tracks reconciliation sessions triggered by corrections."""

    def __init__(self):
        self.sessions = []

    async def start_session(self, instrument_id, reason):
        session_id = f"recon-{len(self.sessions) + 1}"
        self.sessions.append({
            "session_id": session_id,
            "instrument_id": instrument_id,
            "reason": reason,
        })
        return session_id


class TestCorrectionFlow:
    """Full correction lifecycle: record → process → reconciliation."""

    @pytest.mark.asyncio
    async def test_price_correction_triggers_reconciliation(self):
        """Price correction creates recon session and gets processed."""
        recon = FakeReconService()
        handler = CorrectionHandler(reconciliation_service=recon)

        # Record a price correction
        event = await handler.record_correction(
            broker_trade_id="bk-trade-001",
            instrument_id="000001.SZ",
            correction_type=CorrectionType.PRICE_CORRECTION,
            original_price=Decimal("10.50"),
            corrected_price=Decimal("10.48"),
            reason="Exchange price adjustment",
        )

        assert event.is_processed is False
        assert len(await handler.get_unprocessed_corrections()) == 1

        # Process it
        processed = await handler.process_correction(event.correction_id)
        assert processed.is_processed is True
        assert processed.processed_at is not None
        assert processed.reconciliation_session_id  # Linked to recon

        # No more unprocessed
        assert len(await handler.get_unprocessed_corrections()) == 0

    @pytest.mark.asyncio
    async def test_trade_cancellation_flow(self):
        """Full trade cancellation: record, process, verify."""
        handler = CorrectionHandler()

        event = await handler.record_correction(
            broker_trade_id="bk-trade-002",
            instrument_id="600000.SH",
            correction_type=CorrectionType.TRADE_CANCELLATION,
            original_quantity=500,
            reason="Trade cancelled by exchange",
        )

        processed = await handler.process_correction(event.correction_id)
        assert processed.is_processed is True
        assert processed.correction_type == CorrectionType.TRADE_CANCELLATION

    @pytest.mark.asyncio
    async def test_multiple_corrections_batch_processing(self):
        """Multiple corrections processed in sequence."""
        handler = CorrectionHandler()

        # Record 3 corrections
        ids = []
        for i in range(3):
            event = await handler.record_correction(
                broker_trade_id=f"bk-trade-{i:03d}",
                instrument_id="000001.SZ",
                correction_type=CorrectionType.PRICE_CORRECTION,
                original_price=Decimal("10.50"),
                corrected_price=Decimal("10.48"),
            )
            ids.append(event.correction_id)

        # Process all
        unprocessed = await handler.get_unprocessed_corrections()
        assert len(unprocessed) == 3

        for cid in ids:
            result = await handler.process_correction(cid)
            assert result.is_processed is True

        assert len(await handler.get_unprocessed_corrections()) == 0

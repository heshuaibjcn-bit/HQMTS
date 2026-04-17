"""Tests for ExternalManualEvent detection service (SAD 21)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from hqmts.monitoring.external_detector import (
    BrokerTrade,
    ExternalEventDetector,
    InternalTrade,
)
from hqmts.domain.external_event import ExternalManualEvent


def _internal(trade_id: str = "t-001", instrument_id: str = "000001.SZ",
              side: str = "buy", quantity: int = 100, price: str = "10.50") -> InternalTrade:
    return InternalTrade(
        trade_id=trade_id,
        order_id=f"ord-{trade_id}",
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        price=Decimal(price),
        trade_time=datetime(2024, 1, 2, 10, 0),
    )


def _broker(broker_trade_id: str = "bt-001", instrument_id: str = "000001.SZ",
            side: str = "buy", quantity: int = 100, price: str = "10.50",
            broker_order_id: str | None = None) -> BrokerTrade:
    return BrokerTrade(
        broker_trade_id=broker_trade_id,
        broker_order_id=broker_order_id,
        instrument_id=instrument_id,
        side=side,
        quantity=quantity,
        price=Decimal(price),
        trade_time=datetime(2024, 1, 2, 10, 0),
    )


class TestExternalEventDetector:
    def test_no_external_events_when_matched(self):
        """Broker trades matching internal trades produce no events."""
        detector = ExternalEventDetector()
        internal = [_internal(trade_id="bt-001")]
        broker = [_broker(broker_trade_id="bt-001")]
        events = detector.detect_from_trades("acc-001", internal, broker)
        assert len(events) == 0

    def test_detect_unmatched_broker_trade(self):
        """Broker trade with no internal match produces an event."""
        detector = ExternalEventDetector()
        internal = [_internal(trade_id="t-001", price="10.50")]
        broker = [_broker(broker_trade_id="bt-002", broker_order_id="bo-002", price="11.00")]
        events = detector.detect_from_trades("acc-001", internal, broker)
        assert len(events) == 1
        assert events[0].event_type == "manual_buy"
        assert events[0].source_confidence == "high"

    def test_detect_manual_sell(self):
        """Sell side detected as manual_sell."""
        detector = ExternalEventDetector()
        internal = []
        broker = [_broker(broker_trade_id="bt-sell", side="sell")]
        events = detector.detect_from_trades("acc-001", internal, broker)
        assert len(events) == 1
        assert events[0].event_type == "manual_sell"
        assert events[0].side.value == "sell"

    def test_fuzzy_match_same_signature(self):
        """Broker trade matching by instrument+side+qty+price is not flagged."""
        detector = ExternalEventDetector()
        internal = [_internal(trade_id="t-001")]
        # Same signature but different trade_id
        broker = [_broker(broker_trade_id="bt-different")]
        events = detector.detect_from_trades("acc-001", internal, broker)
        # Should fuzzy match and produce no event
        assert len(events) == 0

    def test_fuzzy_match_different_price(self):
        """Different price means no fuzzy match, should flag."""
        detector = ExternalEventDetector()
        internal = [_internal(trade_id="t-001", price="10.50")]
        broker = [_broker(broker_trade_id="bt-diff", price="11.00")]
        events = detector.detect_from_trades("acc-001", internal, broker)
        assert len(events) == 1

    def test_multiple_external_events(self):
        """Multiple unmatched broker trades produce multiple events."""
        detector = ExternalEventDetector()
        internal = [_internal(trade_id="t-001")]
        broker = [
            _broker(broker_trade_id="bt-002", side="buy", price="11.00"),
            _broker(broker_trade_id="bt-003", side="sell"),
            _broker(broker_trade_id="bt-004", instrument_id="600000.SH"),
        ]
        events = detector.detect_from_trades("acc-001", internal, broker)
        assert len(events) == 3

    def test_unknown_trade_no_side(self):
        """Broker trade with no side info classified as unknown_trade."""
        detector = ExternalEventDetector()
        internal = []
        broker = [BrokerTrade(broker_trade_id="bt-no-side")]
        events = detector.detect_from_trades("acc-001", internal, broker)
        assert len(events) == 1
        assert events[0].event_type == "unknown_trade"
        assert events[0].source_confidence == "low"

    def test_medium_confidence_partial_info(self):
        """Broker trade with instrument and side but no qty/price gets medium confidence."""
        detector = ExternalEventDetector()
        internal = []
        broker = [BrokerTrade(
            broker_trade_id="bt-partial",
            instrument_id="000001.SZ",
            side="buy",
        )]
        events = detector.detect_from_trades("acc-001", internal, broker)
        assert len(events) == 1
        assert events[0].source_confidence == "medium"

    def test_auto_respond_high_confidence_live(self):
        """High confidence + live → escalate to pause_open."""
        detector = ExternalEventDetector()
        event = ExternalManualEvent(
            external_event_id="evt-001",
            account_id="acc-001",
            event_type="manual_buy",
            detected_at=datetime.now(),
            source_confidence="high",
        )
        action = detector.auto_respond(event, is_live=True)
        assert action == "escalate_pause_open"

    def test_auto_respond_high_confidence_paper(self):
        """High confidence + non-live → alert human."""
        detector = ExternalEventDetector()
        event = ExternalManualEvent(
            external_event_id="evt-002",
            account_id="acc-001",
            event_type="manual_sell",
            detected_at=datetime.now(),
            source_confidence="high",
        )
        action = detector.auto_respond(event, is_live=False)
        assert action == "alert_human"

    def test_auto_respond_medium_confidence(self):
        """Medium confidence → alert human."""
        detector = ExternalEventDetector()
        event = ExternalManualEvent(
            external_event_id="evt-003",
            account_id="acc-001",
            event_type="unknown_trade",
            detected_at=datetime.now(),
            source_confidence="medium",
        )
        action = detector.auto_respond(event, is_live=True)
        assert action == "alert_human"

    def test_auto_respond_low_confidence(self):
        """Low confidence → log only."""
        detector = ExternalEventDetector()
        event = ExternalManualEvent(
            external_event_id="evt-004",
            account_id="acc-001",
            event_type="unknown_trade",
            detected_at=datetime.now(),
            source_confidence="low",
        )
        action = detector.auto_respond(event, is_live=True)
        assert action == "log_only"

    def test_event_has_all_fields(self):
        """Detected event should have all required fields populated."""
        detector = ExternalEventDetector()
        broker = [_broker(
            broker_trade_id="bt-full",
            broker_order_id="bo-full",
            instrument_id="000001.SZ",
            side="buy",
            quantity=200,
            price="15.30",
        )]
        events = detector.detect_from_trades("acc-001", [], broker)
        assert len(events) == 1
        e = events[0]
        assert e.account_id == "acc-001"
        assert e.broker_order_id == "bo-full"
        assert e.broker_trade_id == "bt-full"
        assert e.instrument_id is not None
        assert e.side is not None
        assert e.quantity == 200
        assert e.price == Decimal("15.30")
        assert e.source_confidence == "high"
        assert e.audit_note != ""

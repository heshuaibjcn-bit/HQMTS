"""External Manual Event detection service (SAD 21, PRD 20.2).

Detects trades in broker reports that don't match internal order records,
and determines appropriate auto-response based on confidence level.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from hqmts.core.enums import Side, StrategyStatus
from hqmts.core.types import AccountId, ExternalEventId, InstrumentId, OrderId
from hqmts.domain.external_event import ExternalManualEvent
from hqmts.core.types import now_shanghai

logger = logging.getLogger(__name__)


class ExternalEventAction(str, Enum):
    """Actions the system can take in response to external events."""
    ESCALATE_PAUSE_OPEN = "escalate_pause_open"
    ESCALATE_CLOSE_ONLY = "escalate_close_only"
    ALERT_HUMAN = "alert_human"
    LOG_ONLY = "log_only"


@dataclass
class InternalTrade:
    """Simplified internal trade record for matching."""

    trade_id: str
    order_id: str
    instrument_id: str
    side: str  # buy, sell
    quantity: int
    price: Decimal
    trade_time: datetime


@dataclass
class BrokerTrade:
    """Broker-reported trade for comparison."""

    broker_trade_id: str
    broker_order_id: str | None = None
    instrument_id: str | None = None
    side: str | None = None  # buy, sell
    quantity: int | None = None
    price: Decimal | None = None
    trade_time: datetime | None = None


class ExternalEventDetector:
    """Detects external manual events by comparing internal vs broker trades.

    Response rules (PRD 20.2):
    - high confidence + live → escalate to pause_open
    - medium confidence → alert human
    - low confidence → log only
    """

    def detect_from_trades(
        self,
        account_id: str,
        internal_trades: list[InternalTrade],
        broker_trades: list[BrokerTrade],
        detect_time: datetime | None = None,
        time_window_seconds: int = 60,
    ) -> list[ExternalManualEvent]:
        """Compare internal trade records against broker reports.

        Returns events for broker trades with no matching internal record.

        Matching logic:
        1. Exact: broker_trade_id matches internal trade_id
        2. Fuzzy: same instrument+side+quantity+price within time window
        """
        now = detect_time or now_shanghai()
        internal_trade_ids = {t.trade_id for t in internal_trades}

        # Index internal trades by signature for fuzzy matching
        internal_signatures: dict[tuple, list[InternalTrade]] = {}
        for t in internal_trades:
            sig = (t.instrument_id, t.side, t.quantity, str(t.price))
            internal_signatures.setdefault(sig, []).append(t)

        events: list[ExternalManualEvent] = []
        for bt in broker_trades:
            # Skip if broker_trade_id matches an internal trade_id (direct match)
            if bt.broker_trade_id in internal_trade_ids:
                continue

            # Fuzzy match: same instrument, side, quantity, price within time window
            matched = False
            if bt.instrument_id and bt.side and bt.quantity and bt.price and bt.trade_time:
                sig = (bt.instrument_id, bt.side, bt.quantity, str(bt.price))
                candidates = internal_signatures.get(sig, [])
                for cand in candidates:
                    if cand.trade_time and abs((bt.trade_time - cand.trade_time).total_seconds()) <= time_window_seconds:
                        matched = True
                        break

            if matched:
                continue

            # No match found → external event
            event_type = self._classify_event(bt)
            confidence = self._assess_confidence(bt)

            events.append(ExternalManualEvent(
                external_event_id=ExternalEventId(str(uuid.uuid4())),
                account_id=AccountId(account_id),
                event_type=event_type,
                broker_order_id=bt.broker_order_id,
                broker_trade_id=bt.broker_trade_id,
                instrument_id=InstrumentId(bt.instrument_id) if bt.instrument_id else None,
                side=Side(bt.side) if bt.side else None,
                quantity=bt.quantity,
                price=bt.price,
                detected_at=now,
                source_confidence=confidence,
                linked_internal_order_id=None,
                action_taken="",
                audit_note=f"Detected unmatched broker trade {bt.broker_trade_id}",
            ))

        return events

    def auto_respond(self, event: ExternalManualEvent, is_live: bool = True) -> ExternalEventAction:
        """Determine auto-response action based on confidence and environment.

        Returns ExternalEventAction indicating what the caller should do.
        """
        if event.source_confidence == "high" and is_live:
            return ExternalEventAction.ESCALATE_PAUSE_OPEN
        elif event.source_confidence == "high" and not is_live:
            return ExternalEventAction.ALERT_HUMAN
        elif event.source_confidence == "medium":
            return ExternalEventAction.ALERT_HUMAN
        else:
            return ExternalEventAction.LOG_ONLY

    def determine_strategy_status(
        self, action: ExternalEventAction,
    ) -> StrategyStatus | None:
        """Map an ExternalEventAction to the required strategy status transition.

        Returns None if no transition needed (log_only, alert_human).
        """
        if action == ExternalEventAction.ESCALATE_PAUSE_OPEN:
            return StrategyStatus.PAUSE_OPEN
        elif action == ExternalEventAction.ESCALATE_CLOSE_ONLY:
            return StrategyStatus.CLOSE_ONLY
        return None

    def execute_response(
        self,
        events: list[ExternalManualEvent],
        is_live: bool = True,
    ) -> list[tuple[ExternalManualEvent, ExternalEventAction]]:
        """Evaluate all events and determine responses.

        Returns list of (event, action) pairs. The caller is responsible for
        actually transitioning strategy state and persisting events.
        Logs escalate-level responses as warnings.
        """
        results: list[tuple[ExternalManualEvent, ExternalEventAction]] = []
        for event in events:
            action = self.auto_respond(event, is_live=is_live)
            results.append((event, action))

            if action in (
                ExternalEventAction.ESCALATE_PAUSE_OPEN,
                ExternalEventAction.ESCALATE_CLOSE_ONLY,
            ):
                logger.warning(
                    "EXTERNAL_EVENT_ESCALATE event=%s type=%s confidence=%s action=%s",
                    event.external_event_id, event.event_type,
                    event.source_confidence, action.value,
                )
            elif action == ExternalEventAction.ALERT_HUMAN:
                logger.info(
                    "EXTERNAL_EVENT_ALERT event=%s type=%s",
                    event.external_event_id, event.event_type,
                )

        return results

    def _classify_event(self, broker_trade: BrokerTrade) -> str:
        """Classify the type of external event."""
        side = broker_trade.side
        if side == "buy":
            return "manual_buy"
        elif side == "sell":
            return "manual_sell"
        # No side info → unknown
        return "unknown_trade"

    def _assess_confidence(self, broker_trade: BrokerTrade) -> str:
        """Assess confidence level of the detection."""
        # High confidence: full trade details available
        if all([broker_trade.instrument_id, broker_trade.side,
                broker_trade.quantity, broker_trade.price,
                broker_trade.trade_time]):
            return "high"
        # Medium: partial info (at least instrument and side)
        if broker_trade.instrument_id and broker_trade.side:
            return "medium"
        # Low: minimal info
        return "low"

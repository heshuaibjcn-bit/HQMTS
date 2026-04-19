"""PipelineBus to WebSocket bridge.

Subscribes to PipelineBus streams and forwards messages to
WebSocket connections via ConnectionManager, with role-based filtering.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from hqmts.api.ws_manager import ConnectionManager
from hqmts.core.enums import UserRole
from hqmts.infra.pipeline import (
    PipelineBus,
    STREAM_ALERTS,
    STREAM_AGENT_TASKS,
    STREAM_ORDERS,
    STREAM_POSITIONS,
    STREAM_RISK_RESULTS,
    STREAM_SIGNALS,
)

logger = logging.getLogger(__name__)

# PipelineBus stream -> WS message type mapping
STREAM_TYPE_MAP: dict[str, str] = {
    STREAM_SIGNALS: "signal_new",
    STREAM_ORDERS: "order_update",
    STREAM_RISK_RESULTS: "risk_change",
    STREAM_POSITIONS: "position_update",
    STREAM_ALERTS: "alert",
    STREAM_AGENT_TASKS: "agent_task_update",
}


class PipelineBusToWSBridge:
    """Bridge from PipelineBus events to WebSocket connections."""

    def __init__(self, manager: ConnectionManager) -> None:
        self._manager = manager
        self._bus: PipelineBus | None = None
        self._group = f"ws-bridge-{uuid.uuid4().hex[:8]}"

    async def start(self, bus: PipelineBus) -> None:
        """Subscribe to all relevant streams."""
        self._bus = bus
        for stream in STREAM_TYPE_MAP:
            await bus.subscribe(stream, self._group, self._on_message)
        await bus.start()
        logger.info("WS Bridge started, listening on %d streams", len(STREAM_TYPE_MAP))

    async def stop(self) -> None:
        """Stop the bridge."""
        if self._bus:
            await self._bus.stop()
        logger.info("WS Bridge stopped")

    async def _on_message(self, msg: Any) -> None:
        """Handle a PipelineBus message and forward to relevant WS connections."""
        ws_type = STREAM_TYPE_MAP.get(msg.stream)
        if not ws_type:
            return

        ws_message = {
            "type": ws_type,
            "data": msg.payload,
            "event_id": msg.message_id,
            "timestamp": msg.timestamp,
        }

        for conn in self._manager.get_all_connections():
            if self._should_deliver(ws_message, conn.role, conn.user_id, msg.payload):
                enriched = self._manager.buffer_message(conn.user_id, ws_message)
                try:
                    await conn.websocket.send_json(enriched)
                except Exception:
                    logger.warning(
                        "WS forward failed: user=%s session=%s",
                        conn.user_id,
                        conn.session_id,
                    )
                    self._manager.disconnect(conn.session_id)

    def _should_deliver(
        self,
        message: dict,
        user_role: str,
        user_id: str,
        payload: dict,
    ) -> bool:
        """Role-based message filtering (PRD 30.6 FR-REALTIME-001)."""
        msg_type = message["type"]

        # signal_new: researchers see own strategies, traders see own, admins see all
        if msg_type == "signal_new":
            if user_role == UserRole.SYSTEM_ADMIN.value:
                return True
            # For now, deliver all; actual strategy filtering requires payload inspection
            return True

        # risk_change: researchers see none, traders see own account, admins see all
        if msg_type == "risk_change":
            if user_role == UserRole.QUANT_RESEARCHER.value:
                return False
            return True

        # alert: researchers see P2-P3, traders see P1-P3, admins see all
        if msg_type == "alert":
            level = payload.get("level", "P3")
            if user_role == UserRole.QUANT_RESEARCHER.value:
                return level in ("P2", "P3")
            if user_role == UserRole.TRADER.value:
                return level in ("P1", "P2", "P3")
            return True

        # position_update and order_update: deliver to all authenticated users
        # (actual account filtering done at data level)
        return True

"""WebSocket connection manager.

Tracks per-user connections, sequence counters, and message buffers
for reconnection recovery.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class _Connection:
    websocket: WebSocket
    user_id: str
    session_id: str
    role: str
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)


class ConnectionManager:
    """Manages WebSocket connections per user with sequence tracking."""

    def __init__(self, buffer_size: int = 100, buffer_ttl: int = 300) -> None:
        self._connections: dict[str, _Connection] = {}  # session_id -> Connection
        self._user_connections: dict[str, list[str]] = defaultdict(list)  # user_id -> [session_ids]
        self._sequences: dict[str, int] = {}  # user_id -> last sequence number
        self._buffers: dict[str, list[tuple[int, dict]]] = {}  # user_id -> [(seq, msg)]
        self._buffer_size = buffer_size
        self._buffer_ttl = buffer_ttl

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        session_id: str,
        role: str,
    ) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept(subprotocol="bearer")
        conn = _Connection(
            websocket=websocket,
            user_id=user_id,
            session_id=session_id,
            role=role,
        )
        self._connections[session_id] = conn
        self._user_connections[user_id].append(session_id)
        if user_id not in self._sequences:
            self._sequences[user_id] = 0
        logger.info("WS connected: user=%s session=%s", user_id, session_id)

    def disconnect(self, session_id: str) -> None:
        """Remove a WebSocket connection."""
        conn = self._connections.pop(session_id, None)
        if conn:
            user_conns = self._user_connections.get(conn.user_id, [])
            if session_id in user_conns:
                user_conns.remove(session_id)
            logger.info("WS disconnected: user=%s session=%s", conn.user_id, session_id)

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send a message to all connections of a user."""
        session_ids = self._user_connections.get(user_id, [])
        for sid in session_ids:
            conn = self._connections.get(sid)
            if conn:
                try:
                    await conn.websocket.send_json(message)
                except Exception:
                    logger.warning("WS send failed: user=%s session=%s", user_id, sid)
                    self.disconnect(sid)

    def buffer_message(self, user_id: str, message: dict) -> dict:
        """Buffer a message with a sequence number and return the enriched message."""
        seq = self._sequences.get(user_id, 0) + 1
        self._sequences[user_id] = seq

        enriched = {**message, "sequence": seq}

        if user_id not in self._buffers:
            self._buffers[user_id] = []
        self._buffers[user_id].append((seq, enriched))
        # Trim buffer
        if len(self._buffers[user_id]) > self._buffer_size:
            self._buffers[user_id] = self._buffers[user_id][-self._buffer_size:]

        return enriched

    def get_buffered_messages(self, user_id: str, after_sequence: int) -> list[dict]:
        """Get buffered messages after a given sequence number for reconnection."""
        buffer = self._buffers.get(user_id, [])
        return [msg for seq, msg in buffer if seq > after_sequence]

    def get_connections_for_user(self, user_id: str) -> list[_Connection]:
        """Get all active connections for a user."""
        return [
            self._connections[sid]
            for sid in self._user_connections.get(user_id, [])
            if sid in self._connections
        ]

    def get_all_connections(self) -> list[_Connection]:
        """Get all active connections."""
        return list(self._connections.values())

    @property
    def active_count(self) -> int:
        return len(self._connections)

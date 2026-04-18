"""WebSocket endpoint (/ws)."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from hqmts.core.auth import decode_token
from hqmts.core.enums import UserRole

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_ws_manager(websocket: WebSocket) -> tuple:
    """Extract manager and bridge from app state."""
    app = websocket.app
    manager = app.state.ws_manager
    settings = app.state.settings
    return manager, settings


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint with JWT auth via Sec-WebSocket-Protocol header.

    Protocol: Sec-WebSocket-Protocol: bearer, {token}
    """
    manager, settings = await _get_ws_manager(websocket)

    # Authenticate via Sec-WebSocket-Protocol header
    protocols = websocket.headers.get("sec-websocket-protocol", "")
    token = _extract_token_from_protocols(protocols)

    if not token:
        await websocket.close(code=4001, reason="Missing authentication")
        return

    try:
        payload = decode_token(token, settings.auth.secret_key)
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    if payload.get("type") != "access":
        await websocket.close(code=4001, reason="Invalid token type")
        return

    user_id = payload.get("sub")
    session_id = payload.get("session_id")
    role = payload.get("role")

    if not user_id or not session_id:
        await websocket.close(code=4001, reason="Invalid token payload")
        return

    # Connect
    await manager.connect(websocket, user_id, session_id, role)

    # Send any buffered messages for reconnection recovery
    buffered = manager.get_buffered_messages(user_id, 0)
    for msg in buffered[-20:]:  # Limit initial replay
        try:
            await websocket.send_json(msg)
        except Exception:
            manager.disconnect(session_id)
            return

    # Heartbeat + message loop
    heartbeat_task = asyncio.create_task(_heartbeat_loop(websocket, session_id, manager))
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "reconnect":
                last_seq = data.get("last_sequence", 0)
                missed = manager.get_buffered_messages(user_id, last_seq)
                for msg in missed:
                    await websocket.send_json(msg)
            # WebSocket is read-only push channel, ignore other client messages
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WS error: user=%s session=%s", user_id, session_id)
    finally:
        heartbeat_task.cancel()
        manager.disconnect(session_id)


def _extract_token_from_protocols(protocols: str) -> str | None:
    """Extract JWT from Sec-WebSocket-Protocol header.

    Expected format: "bearer, {token}"
    """
    parts = [p.strip() for p in protocols.split(",")]
    if len(parts) >= 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


async def _heartbeat_loop(
    websocket: WebSocket,
    session_id: str,
    manager,
) -> None:
    """Server-side heartbeat: check for client pings every 60s."""
    try:
        while True:
            await asyncio.sleep(60)
            # If connection is still alive, send a server ping
            try:
                await websocket.send_json({"type": "server_ping"})
            except Exception:
                manager.disconnect(session_id)
                break
    except asyncio.CancelledError:
        pass

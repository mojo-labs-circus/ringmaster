"""api/connections.py
Connection registry — maps user_id to all active WebSocket connections for that user.

Used by chat_ws to register/deregister connections, and by profile push to reach
all active sessions for a user when assistant_name or tier changes."""

import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Module-level registry — dict is fine here since FastAPI runs on a single event loop.
# Phase 6 (server deployment) may require a Redis-backed registry if multiple workers
# are introduced, but a single-process asyncio server needs nothing more than this.
_registry: dict[str, list[WebSocket]] = {}


def register(user_id: str, websocket: WebSocket) -> None:
    if user_id not in _registry:
        _registry[user_id] = []
    _registry[user_id].append(websocket)
    logger.debug("Registered connection for %s (%d active)", user_id, len(_registry[user_id]))


def deregister(user_id: str, websocket: WebSocket) -> None:
    if user_id not in _registry:
        return
    _registry[user_id].remove(websocket)
    if not _registry[user_id]:
        del _registry[user_id]
    logger.debug("Deregistered connection for %s", user_id)


async def push_profile(user_id: str) -> None:
    """Push a profile frame to all active connections for this user.
    Called when assistant_name or tier changes — client re-fetches GET /profile on receipt."""
    if user_id not in _registry:
        return
    # Iterate over a copy — dead connections are removed from the registry on disconnect,
    # but send_json may still raise if the connection closed between the check and the send.
    for ws in list(_registry[user_id]):
        try:
            await ws.send_json({"type": "profile", "message_id": "__push__"})
        except Exception:
            # Dead connection — will be cleaned up when WebSocketDisconnect fires in chat_ws
            pass

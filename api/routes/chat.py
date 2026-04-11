"""api/routes/chat.py
WebSocket endpoint for chat. LangGraph invocation is stubbed — returns a hardcoded response
so the frame contract can be verified before real graph wiring."""

import json
import logging
import secrets

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat")


@router.websocket("/ws")
async def chat_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("Client connected")

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                frame = json.loads(raw)
                message_id = frame["message_id"]
                content = frame["content"]  # noqa: F841 — will be passed to graph
            except (json.JSONDecodeError, KeyError) as exc:
                await websocket.send_json({
                    "type": "error",
                    "message_id": secrets.token_hex(4),
                    "message": f"Invalid frame: {exc}",
                })
                continue

            await websocket.send_json({
                "type": "status",
                "message_id": message_id,
                "message": "Processing...",
            })

            await websocket.send_json({
                "type": "token",
                "message_id": message_id,
                "content": "[stub] Hello from JARVIS.",
            })

            await websocket.send_json({
                "type": "done",
                "message_id": message_id,
                "refresh": [],
            })

    except WebSocketDisconnect:
        logger.info("Client disconnected")

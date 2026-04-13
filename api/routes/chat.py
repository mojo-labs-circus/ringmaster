"""api/routes/chat.py
WebSocket endpoint for chat. Owns all frame sending.
Uses astream_events to stream tokens and status frames as the graph executes."""

import json
import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from api import connections
from api.dependencies import ConnectedClient, get_connected_client_ws
from config import STATUS_MESSAGES
from db.auth.factory import get_auth_repository
from db.auth.repository import AuthRepository
from db.history.factory import get_history_repository
from db.history.models import HistoryEntry
from db.history.repository import HistoryRepository
from graph.graph import jarvis_graph
from graph.state import JarvisState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat")


@router.websocket("/ws")
async def chat_ws(
    websocket: WebSocket,
    client: ConnectedClient = Depends(get_connected_client_ws),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    history_repo: HistoryRepository = Depends(get_history_repository),
) -> None:
    await websocket.accept()

    user = client.user
    token_version_at_connect = user.token_version
    logger.info("Client connected: %s via %s", user.username, client.client_type)

    connections.register(user.username, websocket)
    is_busy = False

    try:
        while True:
            raw = await websocket.receive_text()

            # Re-check token_version on every message — catches forced deauth mid-session
            current_user = auth_repo.get_user(user.username)
            if current_user is None or current_user.token_version != token_version_at_connect:
                await websocket.send_json({
                    "type": "error",
                    "message_id": secrets.token_hex(4),
                    "message": "Session invalidated. Please log in again.",
                })
                break

            # Parse frame
            try:
                frame = json.loads(raw)
                message_id = frame["message_id"]
                content = frame["content"]
            except (json.JSONDecodeError, KeyError) as exc:
                await websocket.send_json({
                    "type": "error",
                    "message_id": secrets.token_hex(4),
                    "message": f"Invalid frame: {exc}",
                })
                continue

            # Busy — drop with status frame, no queuing
            if is_busy:
                await websocket.send_json({
                    "type": "status",
                    "message_id": message_id,
                    "message": "I'm still working on your last message.",
                })
                continue

            is_busy = True
            try:
                history = history_repo.load(user.username)
                state: JarvisState = {
                    "user_id": user.username,
                    "tier": user.tier,
                    "client_type": client.client_type,
                    "assistant_name": user.assistant_name,
                    "messages": history + [{"role": "user", "content": content}],
                    "current_input": content,
                    "active_project": None,
                    "intent": "",
                    "needs_memory": False,
                    "retrieved_context": "",
                    "skill_context": "",
                    "response": "",
                    "formatted_response": "",
                    "status_message": None,
                    "error": None,
                    "interrupt_payload": None,
                    "refresh": [],
                }

                final_state = None
                async for event in jarvis_graph.astream_events(state, version="v2"):
                    event_type = event["event"]
                    event_name = event["name"]

                    if event_type == "on_chain_start":
                        # Node entry — send status frame if configured in STATUS_MESSAGES
                        node_name = event.get("metadata", {}).get("langgraph_node")
                        if node_name and STATUS_MESSAGES.get(node_name):
                            await websocket.send_json({
                                "type": "status",
                                "message_id": message_id,
                                "message": STATUS_MESSAGES[node_name],
                            })

                    elif event_type == "on_custom_event" and event_name == "status_message":
                        # Mid-node status written by a node during execution
                        await websocket.send_json({
                            "type": "status",
                            "message_id": message_id,
                            "message": event["data"]["message"],
                        })

                    elif event_type == "on_chain_end" and event_name == "LangGraph":
                        final_state = event["data"]["output"]

                if final_state is None:
                    raise RuntimeError("Graph completed without final state")

                await websocket.send_json({
                    "type": "done",
                    "message_id": message_id,
                    "refresh": final_state["refresh"],
                })

                # Write exchange to history
                now = datetime.now(timezone.utc)
                history_repo.save(HistoryEntry(
                    id=None,
                    user_id=user.username,
                    role="user",
                    content=content,
                    created_at=now,
                ))
                history_repo.save(HistoryEntry(
                    id=None,
                    user_id=user.username,
                    role="assistant",
                    content=final_state["formatted_response"],
                    created_at=now,
                ))

                # TODO: fire memory/persist.py as asyncio background task — module not yet built

            except Exception:
                logger.exception("Error during graph invocation for %s", user.username)
                await websocket.send_json({
                    "type": "error",
                    "message_id": message_id,
                    "message": "An unexpected error occurred.",
                })

            finally:
                is_busy = False

    except WebSocketDisconnect:
        logger.info("Client disconnected: %s via %s", user.username, client.client_type)

    finally:
        connections.deregister(user.username, websocket)
